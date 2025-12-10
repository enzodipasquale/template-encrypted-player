#!/usr/bin/env python3
"""Decrypt the encrypted strategy file."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from cryptography.fernet import Fernet


def decrypt_strategy(key: str, encrypted_path: Path, output_path: Path) -> None:
    """Decrypt the strategy file."""
    if not encrypted_path.exists():
        raise SystemExit(f"{encrypted_path} not found.")

    fernet = Fernet(key.encode("ascii"))
    encrypted = encrypted_path.read_bytes()
    decrypted = fernet.decrypt(encrypted)
    output_path.write_bytes(decrypted)
    print(f"✅ Decrypted {encrypted_path} → {output_path}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Decrypt the encrypted strategy file.")
    parser.add_argument(
        "--encrypted",
        default="strategy.py.encrypted",
        type=Path,
        help="Encrypted strategy file (default: strategy.py.encrypted).",
    )
    parser.add_argument(
        "--output",
        default="strategy.py",
        type=Path,
        help="Output plaintext file (default: strategy.py).",
    )
    parser.add_argument(
        "--key",
        help="Encryption key (or set ENCRYPTION_KEY environment variable).",
    )
    args = parser.parse_args()

    key = args.key or os.getenv("ENCRYPTION_KEY")
    if not key:
        raise SystemExit(
            "Encryption key required. Set ENCRYPTION_KEY environment variable "
            "or pass --key argument."
        )

    decrypt_strategy(key, args.encrypted, args.output)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        sys.stderr.write(f"Error: {exc}\n")
        sys.exit(1)

