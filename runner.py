#!/usr/bin/env python3
import argparse
import base64
import inspect
import json
import os
import sys
import time
from pathlib import Path

import httpx
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def _env(name, required=False):
    value = os.environ.get(name, "").strip()
    if required and not value:
        sys.exit(f"missing required env var: {name}")
    return value or None


def _cipher(key):
    key = key.strip()
    if len(key) == 44:
        return Fernet(key.encode("ascii"))
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"ubx-v2-salt",
        iterations=100000,
    )
    return Fernet(base64.urlsafe_b64encode(kdf.derive(key.encode("utf-8"))))


def cmd_keygen(_args):
    print(Fernet.generate_key().decode("ascii"))


def cmd_encrypt(args):
    key = _env("ENCRYPTION_KEY", required=True)
    src = Path(args.path)
    if not src.exists():
        sys.exit(f"not found: {src}")
    out = src.with_name(src.name + ".encrypted")
    out.write_text(_cipher(key).encrypt(src.read_bytes()).decode("ascii"))
    print(f"Encrypted -> {out}")


def cmd_decrypt(args):
    key = _env("ENCRYPTION_KEY", required=True)
    src = Path(args.path)
    if not src.exists():
        sys.exit(f"not found: {src}")
    if not src.name.endswith(".encrypted"):
        sys.exit("expected a .encrypted file")
    out = src.with_suffix("")
    out.write_text(_cipher(key).decrypt(src.read_text().encode("ascii")).decode("utf-8"))
    print(f"Decrypted -> {out}")


def _load_strategy(path):
    src = Path(path)
    if not src.exists() and Path(str(src) + ".encrypted").exists():
        src = Path(str(src) + ".encrypted")
    if not src.exists():
        sys.exit(f"strategy not found: {path}")

    source = src.read_text()
    if src.name.endswith(".encrypted"):
        key = _env("ENCRYPTION_KEY", required=True)
        source = _cipher(key).decrypt(source.encode("ascii")).decode("utf-8")

    mod = type(sys)("user_strategy")
    exec(compile(source, "strategy.py", "exec"), mod.__dict__)
    strategy = getattr(mod, "strategy", None)
    if strategy is None:
        sys.exit("strategy.py has no strategy(observation) function")
    return strategy


def _wants_history(strategy):
    # strategy(observation) or strategy(observation, history) — your choice.
    # History is only synced if your function takes a second parameter.
    try:
        params = list(inspect.signature(strategy).parameters.values())
    except (TypeError, ValueError):
        return False
    positional = [
        p for p in params
        if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
    ]
    return len(positional) >= 2 or any(p.kind == p.VAR_POSITIONAL for p in params)


def _jsonable(value):
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return item()
        except Exception:
            pass
    return value


def _server():
    return _env("SERVER_URL", required=True).rstrip("/")


def _slug():
    return _env("TOURNAMENT_SLUG", required=True)


def _headers():
    return {"Authorization": f"Bearer {_env('GAME_TOKEN', required=True)}"}


# Your full private history lives on the server; this file is only a local
# cache so each turn fetches just what is new. The play workflow persists it
# between runs via actions/cache; if the cache is evicted we transparently
# re-fetch everything from turn 0.

def _history_path():
    return Path(_env("HISTORY_PATH") or ".ubx_history.json")


def _sync_history(slug, player_name):
    path = _history_path()
    hist = {"next_since_turn": 0, "events": []}
    if path.exists():
        try:
            loaded = json.loads(path.read_text())
            if isinstance(loaded.get("events"), list) and \
                    isinstance(loaded.get("next_since_turn"), int):
                hist = loaded
        except (json.JSONDecodeError, AttributeError):
            pass  # corrupt cache -> full re-fetch

    synced_from = hist["next_since_turn"]
    while True:
        response = httpx.get(
            f"{_server()}/player/history",
            params={
                "tournament": slug,
                "player_name": player_name,
                "since_turn": hist["next_since_turn"],
            },
            headers=_headers(),
            timeout=30,
        )
        response.raise_for_status()
        page = response.json()
        hist["events"].extend(page["events"])
        hist["next_since_turn"] = page["next_since_turn"]
        if page["complete"]:
            break

    if hist["next_since_turn"] != synced_from:
        path.write_text(json.dumps(hist))
    return hist["events"]


def cmd_register(args):
    body = {
        "tournament_slug": _slug(),
        "player_name": _env("PLAYER_NAME", required=True),
        "github_repo": args.repo or _env("GITHUB_REPOSITORY", required=True),
    }
    response = httpx.post(
        f"{_server()}/player/register",
        json=body,
        headers=_headers(),
        timeout=15,
    )
    response.raise_for_status()
    print(json.dumps(response.json(), indent=2))


def _fetch_status(slug, player_name):
    response = httpx.get(
        f"{_server()}/player/status",
        params={"tournament": slug, "player_name": player_name},
        headers=_headers(),
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def _warn_if_defaulted(status):
    outcome = status.get("last_turn_outcome")
    if outcome in ("defaulted", "no_action"):
        # ::warning:: renders as a prominent annotation on the workflow run.
        print(
            f"::warning::UBX: your action for turn {status.get('turn')} never "
            f"reached the server (outcome: {outcome}); a default was played "
            "for you. If this repeats, check the repo secrets/variables and "
            "recent workflow logs."
        )


_LOCKED_RETRIES = 3
_LOCKED_RETRY_DELAY = 2.0


def cmd_run(args):
    slug = _slug()
    player_name = _env("PLAYER_NAME", required=True)
    strategy = _load_strategy(args.strategy_path)

    # Outer loop: at most one extra pass, only after turn_mismatch (the turn
    # advanced while we were computing — refetch and resubmit for the new one).
    for attempt_round in range(2):
        status = _fetch_status(slug, player_name)
        if attempt_round == 0:
            _warn_if_defaulted(status)
        observation = status.get("observation")
        if observation is None:
            sys.exit("no observation returned by server")

        turn = int(status.get("submit_for_turn") or int(status.get("turn", 0)) + 1)
        if _wants_history(strategy):
            action = strategy(observation, _sync_history(slug, player_name))
        else:
            action = strategy(observation)
        action = _jsonable(action)

        detail = {}
        for locked_try in range(_LOCKED_RETRIES):
            response = httpx.post(
                f"{_server()}/player/action",
                json={
                    "tournament_slug": slug,
                    "player_name": player_name,
                    "turn": turn,
                    "action": action,
                    "sha": _env("GITHUB_SHA"),
                },
                headers=_headers(),
                timeout=15,
            )
            if response.status_code != 409:
                break
            detail = response.json().get("detail", {})
            if detail.get("code") == "turn_locked":
                print(f"turn locked; retrying in {_LOCKED_RETRY_DELAY:.0f}s "
                      f"({locked_try + 1}/{_LOCKED_RETRIES})")
                time.sleep(_LOCKED_RETRY_DELAY)
                continue
            break  # turn_mismatch — handled by the outer loop

        if response.status_code == 409 and detail.get("code") == "turn_mismatch" \
                and attempt_round == 0:
            print(
                f"turn advanced while computing (submitted {detail.get('submitted_for')}, "
                f"awaiting {detail.get('now_awaiting')}); refetching and resubmitting"
            )
            continue
        break

    if response.status_code == 409:
        detail = response.json().get("detail", {})
        if detail.get("code") == "turn_locked":
            sys.exit("turn still locked after retries; giving up (the next "
                     "dispatch plays the next turn normally).")
        sys.exit(f"turn mismatch persisted after refetch: {detail}")
    response.raise_for_status()
    print(json.dumps(response.json(), indent=2))


def cmd_validate(args):
    strategy = _load_strategy(args.strategy_path)
    game_name = args.game or _env("GAME_NAME")
    if not game_name:
        response = httpx.get(f"{_server()}/public/tournaments", timeout=15)
        response.raise_for_status()
        tournaments = response.json().get("tournaments", [])
        match = [t for t in tournaments if t.get("slug") == _slug()]
        game_name = match[0].get("game_name") if match else None
    if not game_name:
        sys.exit("set GAME_NAME or pass --game")

    response = httpx.get(f"{_server()}/validate/games", timeout=15)
    response.raise_for_status()
    game = next((g for g in response.json()["games"] if g["name"] == game_name), None)
    if not game:
        sys.exit(f"unknown game on server: {game_name}")

    errors = []
    observation = game["sample_observation"]
    wants_history = _wants_history(strategy)
    for i in range(args.turns):
        try:
            raw = strategy(observation, []) if wants_history else strategy(observation)
            action = _jsonable(raw)
        except Exception as exc:
            sys.exit(f"[FAIL] strategy() raised on call {i}: {exc!r}")
        response = httpx.post(
            f"{_server()}/validate/schema",
            json={
                "game_name": game_name,
                "action": action,
                "num_opponents": len(observation.get("opponent_ids", [])),
            },
            timeout=15,
        )
        response.raise_for_status()
        result = response.json()
        if not result.get("ok"):
            errors.append((i, result.get("error")))

    if errors:
        print(f"[FAIL] {game_name}: {len(errors)}/{args.turns} actions rejected")
        for i, error in errors[:3]:
            print(f"  call {i}: {str(error)[:200]}")
        sys.exit(1)
    print(f"[OK] {game_name}: strategy ran and all {args.turns} actions match the schema")


def main():
    parser = argparse.ArgumentParser(prog="runner.py")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("keygen").set_defaults(func=cmd_keygen)

    encrypt = sub.add_parser("encrypt")
    encrypt.add_argument("path", nargs="?", default="strategy.py")
    encrypt.set_defaults(func=cmd_encrypt)

    decrypt = sub.add_parser("decrypt")
    decrypt.add_argument("path", nargs="?", default="strategy.py.encrypted")
    decrypt.set_defaults(func=cmd_decrypt)

    register = sub.add_parser("register")
    register.add_argument("--repo", help="owner/repo; defaults to GITHUB_REPOSITORY")
    register.set_defaults(func=cmd_register)

    run = sub.add_parser("run")
    run.add_argument("strategy_path", nargs="?", default="strategy.py")
    run.set_defaults(func=cmd_run)

    validate = sub.add_parser("validate")
    validate.add_argument("strategy_path", nargs="?", default="strategy.py")
    validate.add_argument("--game")
    validate.add_argument("--turns", type=int, default=5)
    validate.set_defaults(func=cmd_validate)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
