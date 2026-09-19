from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path

import dotenv

from yasli_scraper.check import CheckReport, check_snapshot

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

    promote = subparsers.add_parser(
        "promote",
        help="Check a local snapshot and publish those exact bytes to R2.",
    )
    promote.add_argument("file", type=Path, help="Path to a snapshot JSON file.")
    promote.add_argument(
        "--city",
        default=None,
        help="Assert the file's declared city (e.g. 'varna'); it does not override it.",
    )
    promote.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Validate, resolve the target keys and print them, but make no R2 "
            "write. The R2 env vars are still required."
        ),
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


def _read_snapshot_bytes(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError as exc:
        print(f"error: cannot read {path}: {exc.strerror or exc}", file=sys.stderr)
        return None


def _print_report(report: CheckReport) -> None:
    """Summary to stdout, one `check failed:` line per failure to stderr.

    The stream split is `check`'s output contract: stdout stays exactly one JSON
    object so it can be piped, and failures go where this CLI's errors live.
    """
    summary = json.dumps(report.summary, ensure_ascii=False, indent=2)
    # Keep the summary readable on a UTF-8 console, but fall back to JSON's own
    # \uXXXX escapes when the console cannot encode it (a lone surrogate from a
    # "\ud800" escape, a Cyrillic or emoji city on an ASCII console): stdout
    # must stay valid JSON and print() must not raise after the checks already
    # ran. stderr escapes unencodable characters by default.
    try:
        summary.encode(sys.stdout.encoding or "utf-8")
    except UnicodeEncodeError:
        summary = json.dumps(report.summary, ensure_ascii=True, indent=2)
    print(summary)
    for failure in report.failures:
        print(f"check failed: {failure}", file=sys.stderr)


def _run_check(path: Path, expected_city: str | None) -> int:
    # Reads a local file only: no validate_env(), no R2.
    data = _read_snapshot_bytes(path)
    if data is None:
        return 1

    report = check_snapshot(data, expected_city=expected_city)
    _print_report(report)
    return 0 if report.ok else 1


def _render_age(delta: timedelta) -> str:
    """Human-readable age, so an operator need not subtract dates in their head."""
    seconds = int(delta.total_seconds())
    if seconds < 0:
        return "in the future"
    days, rest = divmod(seconds, 86_400)
    hours, rest = divmod(rest, 3_600)
    minutes, secs = divmod(rest, 60)
    if days:
        return f"{days}d {hours}h old"
    if hours:
        return f"{hours}h {minutes}m old"
    if minutes:
        return f"{minutes}m old"
    return f"{secs}s old"


def _scraped_at_line(scraped_at: str) -> str:
    """`scraped_at: <exact ISO stamp> (<age>)`.

    The ISO string stays verbatim so tests and greps can match it exactly; the
    age is what makes it legible against a risk phrased as "a week-old
    snapshot". Nothing here refuses on age — promote publishes the file you
    name (DECISIONS §7).
    """
    try:
        moment = datetime.fromisoformat(scraped_at.replace("Z", "+00:00"))
    except ValueError:
        return f"scraped_at: {scraped_at}"
    return (
        f"scraped_at: {scraped_at} "
        f"({_render_age(datetime.now(timezone.utc) - moment)})"
    )


def _one_line(text: str) -> str:
    return " ".join(str(text).split())


def _run_promote(path: Path, expected_city: str | None, dry_run: bool) -> int:
    raw = _read_snapshot_bytes(path)
    if raw is None:
        return 1

    report = check_snapshot(raw, expected_city=expected_city)
    _print_report(report)
    if not report.ok:
        return 1

    # `city` and `scraped_at` are read from the validated text rather than from
    # report.summary: summary carries `city` but not `scraped_at`, and its field
    # set is `check`'s stdout contract — promote's needs stay out of it. A
    # passing report guarantees the contract held, so both are strings and
    # `city` is a known EXPECTED_ROSTER key.
    payload = json.loads(raw.decode("utf-8"))
    city = payload.get("city")
    scraped_at = payload.get("scraped_at")
    if not isinstance(city, str) or not isinstance(scraped_at, str):
        print(
            "error: validated payload is missing a string city or scraped_at",
            file=sys.stderr,
        )
        return 1

    # --dry-run validates the environment too: a rehearsal should fail on
    # everything the real run would fail on except the write itself, and
    # `check` already covers the credential-free case (DECISIONS §5).
    missing = validate_env()
    if missing is not None:
        print(
            f"error: required environment variable {missing} is not set",
            file=sys.stderr,
        )
        return 1

    # Printed before any write: a line that appears only once the object is
    # live is a post-mortem, not a mitigation.
    print(_scraped_at_line(scraped_at))

    if dry_run:
        # The real stamp is taken at write time, so naming an exact key here
        # would be a lie by the time the real promote runs.
        print(f"would write: snapshots/{city}/<UTC-ISO-timestamp>.json")
        print(f"would write: snapshots/{city}/latest.json")
        return 0

    # Imported here, at the last possible point: r2.py imports boto3 at module
    # scope, so this position is the only thing making "a refused promote never
    # imports boto3" true.
    from yasli_scraper import r2

    now = datetime.now(timezone.utc)
    # Both keys are resolved up front: put_snapshot_bytes returns them only on
    # success, so without this a partial write would leave no record of the key
    # that landed — exactly the state the rollback story is about.
    timestamped_key, latest_key = r2.snapshot_keys(city, now)

    try:
        r2.put_snapshot_bytes(city, raw, now=now)
    except Exception as exc:
        print(
            f"error: upload failed: {_one_line(exc)} "
            f"[stage: two-phase write started; timestamped key {timestamped_key} "
            f"may already exist, latest key {latest_key} may still hold the "
            f"previous payload — verify both before rolling back]",
            file=sys.stderr,
        )
        return 1

    print(f"published: {timestamped_key}")
    print(f"published: {latest_key}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    _load_repo_env()

    if args.command == "check":
        return _run_check(args.file, args.city)

    if args.command == "promote":
        return _run_promote(args.file, args.city, args.dry_run)

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
