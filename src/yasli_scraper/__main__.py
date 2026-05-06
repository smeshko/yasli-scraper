from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import Sequence
from pathlib import Path

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
    run.add_argument(
        "--out",
        type=Path,
        default=None,
        help=(
            "Optional local file path. If set, write the snapshot JSON there "
            "and skip the R2 upload (R2 env vars are not required)."
        ),
    )

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

    if args.command == "run":
        if args.out is not None:
            parent = args.out.parent if str(args.out.parent) else Path(".")
            if not parent.exists():
                print(
                    f"error: parent directory does not exist: {parent}",
                    file=sys.stderr,
                )
                return 1
        else:
            missing = validate_env()
            if missing is not None:
                print(
                    f"error: required environment variable {missing} is not set",
                    file=sys.stderr,
                )
                return 1

        from yasli_scraper import pipeline

        try:
            snapshot = asyncio.run(pipeline.run(args.city))
        except Exception as exc:
            print(f"error: scrape failed: {exc}", file=sys.stderr)
            return 1

        if args.out is not None:
            args.out.write_bytes(
                snapshot.model_dump_json(indent=2).encode("utf-8")
            )
            return 0

        from yasli_scraper import r2

        r2.put_snapshot(args.city, snapshot)
        return 0

    # argparse with required=True should make this unreachable.
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
