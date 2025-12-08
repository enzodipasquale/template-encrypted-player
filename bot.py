#!/usr/bin/env python3
"""CLI for running the strategy once as a local smoke test."""

from __future__ import annotations

import argparse
import os
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
    github_token = os.getenv("GAME_TOKEN")
    player_name = os.getenv("PLAYER_NAME")

    if not server_url:
        raise SystemExit("SERVER_URL env var required")
    if not player_name:
        raise SystemExit("PLAYER_NAME env var required")
    if not github_token:
        raise SystemExit("GAME_TOKEN env var required")

    strategy_func = load_strategy()

    headers = {"Authorization": f"Bearer {github_token}"}
    params = {"player_name": player_name}

    status = requests.get(
        f"{server_url}/status",
        headers=headers,
        params=params,
        timeout=10,
    )
    if not status.ok:
        error_detail = status.text or status.reason
        raise SystemExit(
            f"Failed to get game status: {status.status_code} {error_detail}\n"
            f"URL: {server_url}/status?player_name={player_name}\n"
            f"Check that GAME_TOKEN and PLAYER_NAME secrets are set correctly in GitHub."
        )
    status.raise_for_status()
    payload: Dict[str, Any] = status.json()

    action = strategy_func(payload)

    submit_headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {github_token}",
    }

    body: Dict[str, Any] = {"action": action, "player_name": player_name}

    response = requests.post(
        f"{server_url}/action",
        headers=submit_headers,
        json=body,
        timeout=10,
    )

    if not response.ok:
        detail = response.text or response.reason
        raise SystemExit(f"Submission failed: {response.status_code} {detail}")

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the bot once against the server.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Explicit flag for single submission (default behaviour).",
    )
    return parser.parse_args()


def main() -> None:
    parse_args()
    submit_once()


if __name__ == "__main__":
    main()

