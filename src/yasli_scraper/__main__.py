from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

import dotenv

from yasli_scraper.check import check_snapshot

REQUIRED_ENV_VARS: tuple[str, ...] = (
    "R2_ACCOUNT_ID",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET",
)

# Known floor for Varna is ~76 institutions (12 nurseries + ~52 kindergartens
# + 12 preschools). 50 sits well below that but far above "the scrape
# silently broke into emptiness".
MIN_EXPECTED_INSTITUTIONS = 50

# Repo-root `.env`, resolved relative to this file so cwd doesn't matter.
# scraper/src/yasli_scraper/__main__.py → parents[3] is the repo root.
REPO_ENV_PATH: Path = Path(__file__).resolve().parents[3] / ".env"


def _load_repo_env() -> None:
    # Silently no-op when the file is missing; existing exported values
    # in os.environ take precedence (override=False is the default).
    dotenv.load_dotenv(REPO_ENV_PATH)


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

    check = subparsers.add_parser(
        "check", help="Check a local snapshot file for publishability (no R2 access)."
    )
    check.add_argument("file", type=Path, help="Path to a snapshot JSON file.")
    check.add_argument(
        "--city",
        default=None,
        help="Assert the file's declared city (e.g. 'varna'); it does not override it.",
    )

    return parser


def validate_env(env: dict[str, str] | None = None) -> str | None:
    if env is None:
        _load_repo_env()
    source = os.environ if env is None else env
    for name in REQUIRED_ENV_VARS:
        if not source.get(name):
            return name
    return None


def _run_check(path: Path, expected_city: str | None) -> int:
    # Reads a local file only: no validate_env(), no R2.
    try:
        data = path.read_bytes()
    except OSError as exc:
        print(f"error: cannot read {path}: {exc.strerror or exc}", file=sys.stderr)
        return 1

    report = check_snapshot(data, expected_city=expected_city)
    summary = json.dumps(report.summary, ensure_ascii=False, indent=2)
    # Escape what the console cannot encode (a lone surrogate from a "\ud800"
    # escape on UTF-8, a non-ASCII city on an ASCII console) rather than let
    # print() raise after the checks already ran. stderr escapes by default.
    encoding = sys.stdout.encoding or "utf-8"
    print(summary.encode(encoding, "backslashreplace").decode(encoding))
    for failure in report.failures:
        print(f"check failed: {failure}", file=sys.stderr)
    return 0 if report.ok else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    _load_repo_env()

    if args.command == "check":
        return _run_check(args.file, args.city)

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

        if len(snapshot.institutions) < MIN_EXPECTED_INSTITUTIONS:
            print(
                f"error: scrape produced only {len(snapshot.institutions)} "
                f"institutions (< {MIN_EXPECTED_INSTITUTIONS}); refusing to upload",
                file=sys.stderr,
            )
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
