#!/usr/bin/env python3
"""CLI for running and encrypting the strategy."""

from __future__ import annotations

import argparse
import base64
import os
import subprocess
from pathlib import Path
from typing import Any, Dict

import requests


def load_strategy():
    try:
        from strategy import strategy as private_strategy  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "strategy.py is missing. Decrypt or restore your payload before running bot.py."
        ) from exc
    return private_strategy


def submit_once() -> None:
    server_url = os.getenv("SERVER_URL")
    github_token = os.getenv("GITHUB_TOKEN")
    player_name = os.getenv("PLAYER_NAME")

    if not server_url:
        raise SystemExit("SERVER_URL env var required")

    strategy_func = load_strategy()

    headers = {"Authorization": f"Bearer {github_token}"} if github_token else {}
    params = {"player_name": player_name} if player_name else None

    status = requests.get(
        f"{server_url}/status",
        headers=headers,
        params=params,
        timeout=10,
    )
    status.raise_for_status()
    payload: Dict[str, Any] = status.json()

    action = strategy_func(payload)

    submit_headers = {"Content-Type": "application/json"}
    if github_token:
        submit_headers["Authorization"] = f"Bearer {github_token}"

    body: Dict[str, Any] = {"action": action}
    if player_name:
        body["player_name"] = player_name

    response = requests.post(
        f"{server_url}/action",
        headers=submit_headers,
        json=body,
        timeout=10,
    )

    if not response.ok:
        detail = response.text or response.reason
        raise SystemExit(f"Submission failed: {response.status_code} {detail}")


def encrypt_strategy(recipient: str, source: Path, output: Path) -> None:
    if not source.exists():
        raise SystemExit(f"{source} not found. Create or decrypt your strategy first.")

    print(f"[encrypt] Encrypting {source} for '{recipient}' → {output}", flush=True)
    subprocess.run(
        [
            "gpg",
            "--yes",
            "--batch",
            "--output",
            str(output),
            "--encrypt",
            "--recipient",
            recipient,
            str(source),
        ],
        check=True,
    )

    secret = subprocess.run(
        ["gpg", "--armor", "--export-secret-keys", recipient],
        capture_output=True,
        check=True,
    ).stdout

    asc_path = Path("private-key.asc")
    asc_b64_path = Path("private-key.asc.b64")
    asc_path.write_bytes(secret)
    asc_b64_path.write_text(base64.b64encode(secret).decode("ascii"))

    print(f"[encrypt] Exported secret key to {asc_path} and {asc_b64_path}", flush=True)
    print(
        "[encrypt] Commit only the .gpg file. Add the base64 key and passphrase "
        "to GitHub secrets, then remove the plaintext copy before pushing.",
        flush=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bot utility CLI.")
    sub = parser.add_subparsers(dest="command")

    run_parser = sub.add_parser("run", help="Execute strategy once (default).")
    run_parser.set_defaults(func=lambda _: submit_once())

    encrypt_parser = sub.add_parser("encrypt", help="Encrypt strategy.py with GPG.")
    encrypt_parser.add_argument("--recipient", required=True, help="GPG key identifier.")
    encrypt_parser.add_argument(
        "--source",
        default="strategy.py",
        type=Path,
        help="Plaintext strategy file.",
    )
    encrypt_parser.add_argument(
        "--output",
        default="strategy.py.gpg",
        type=Path,
        help="Encrypted output file.",
    )
    encrypt_parser.set_defaults(func=lambda args: encrypt_strategy(args.recipient, args.source, args.output))

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not getattr(args, "command", None):
        submit_once()
    else:
        args.func(args)


if __name__ == "__main__":
    main()

