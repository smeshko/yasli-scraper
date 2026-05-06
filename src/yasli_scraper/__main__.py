from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence

REQUIRED_ENV_VARS: tuple[str, ...] = (
    "R2_ACCOUNT_ID",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="yasli_scraper",
        description="Yasli scraper — produces JSON snapshots and uploads them to R2.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Run the scraper for a single city.")
    run.add_argument("--city", required=True, help="City slug (e.g. 'varna').")

    return parser


def validate_env(env: dict[str, str] | None = None) -> str | None:
    source = os.environ if env is None else env
    for name in REQUIRED_ENV_VARS:
        if not source.get(name):
            return name
    return None


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    missing = validate_env()
    if missing is not None:
        print(f"error: required environment variable {missing} is not set", file=sys.stderr)
        return 1

    if args.command == "run":
        # Imported here so env validation runs before any boto3/network setup.
        from yasli_scraper import r2, snapshot

        payload = snapshot.build_stub(args.city)
        r2.put_snapshot(args.city, payload)
        return 0

    # argparse with required=True should make this unreachable.
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
