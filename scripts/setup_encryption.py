#!/usr/bin/env python3
"""Prepare the encrypted payload with a single encryption key."""

from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path

from cryptography.fernet import Fernet


def generate_key() -> str:
    """Generate a new Fernet encryption key."""
    return Fernet.generate_key().decode("ascii")


def encrypt_strategy(key: str, source: Path, output: Path) -> None:
    """Encrypt the strategy file using Fernet."""
    if not source.exists():
        raise SystemExit(f"{source} not found. Create your strategy first.")

    print(f"[setup] Encrypting {source} → {output}", flush=True)

    fernet = Fernet(key.encode("ascii"))
    plaintext = source.read_bytes()
    encrypted = fernet.encrypt(plaintext)
    output.write_bytes(encrypted)

    print(f"[setup] ✅ Encrypted successfully", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Encrypt your strategy file with a single encryption key."
    )
    parser.add_argument(
        "--source",
        default="strategy.py",
        type=Path,
        help="Plaintext strategy file (default: strategy.py).",
    )
    parser.add_argument(
        "--output",
        default="strategy.py.encrypted",
        type=Path,
        help="Encrypted output file (default: strategy.py.encrypted).",
    )
    parser.add_argument(
        "--key",
        help="Encryption key (if not provided, a new one will be generated).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Generate or use provided key
    if args.key:
        encryption_key = args.key
        print("[setup] Using provided encryption key", flush=True)
    else:
        encryption_key = generate_key()
        print("[setup] Generated new encryption key", flush=True)

    # Encrypt the strategy
    encrypt_strategy(encryption_key, args.source, args.output)

    print(
        "\n✅ Next steps:\n"
        f"  • Add this encryption key to GitHub Secrets → ENCRYPTION_KEY:\n"
        f"    {encryption_key}\n"
        f"  • Commit the encrypted file: git add {args.output}\n"
        f"  • Commit and push: git commit -m 'Add encrypted strategy' && git push\n"
        f"  • ⚠️  Important: Only commit {args.output} - do NOT commit {args.source}\n",
        flush=True,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        sys.stderr.write(f"Error: {exc}\n")
        sys.exit(1)
