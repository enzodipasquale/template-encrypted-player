#!/usr/bin/env python3
import argparse
import base64
import json
import os
import sys
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


def cmd_run(args):
    slug = _slug()
    player_name = _env("PLAYER_NAME", required=True)
    strategy = _load_strategy(args.strategy_path)

    response = httpx.get(
        f"{_server()}/player/status",
        params={"tournament": slug, "player_name": player_name},
        headers=_headers(),
        timeout=15,
    )
    response.raise_for_status()
    status = response.json()
    observation = status.get("observation")
    if observation is None:
        sys.exit("no observation returned by server")

    action = _jsonable(strategy(observation))
    turn = int(status.get("turn", 0)) + 1
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
    if response.status_code == 409:
        detail = response.json().get("detail", {})
        if detail.get("code") == "turn_locked":
            sys.exit("turn locked: the server is processing this turn; retry in a few seconds")
        sys.exit(
            f"turn mismatch: submitted for {detail.get('submitted_for')}, "
            f"server awaiting {detail.get('now_awaiting')}"
        )
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
    for i in range(args.turns):
        try:
            action = _jsonable(strategy(observation))
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
