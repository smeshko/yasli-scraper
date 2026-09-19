# Research: Promote a validated local snapshot to R2

Curated findings only — no raw conversation transcripts.

## Key Files & Directories

- `src/yasli_scraper/r2.py` — `make_client()` reads the four `R2_*` vars;
  `put_snapshot(city, payload, *, client=None, bucket=None, now=None)` owns the
  ordered two-phase write and serialises the `Snapshot` itself
  (`payload.model_dump_json(indent=2).encode("utf-8")`). `_utc_iso_filename()`
  builds `<UTC-ISO>Z` with microseconds dropped. Nothing here accepts bytes.
- `src/yasli_scraper/__main__.py` — argparse with `run` and `check`
  subparsers; `validate_env()` returns the first missing var name after loading
  the repo-root `.env`; `_run_check()` is the read → check → print → exit path
  `promote` will share, including the `sys.stdout.encoding` fallback that
  re-dumps the summary with `ensure_ascii=True` when the console cannot encode
  it. `MIN_EXPECTED_INSTITUTIONS = 50` guards `run` only.
- `src/yasli_scraper/check.py` — `check_snapshot(raw: bytes, expected_city)
  -> CheckReport`, pure and I/O-free. Decodes strictly as UTF-8, rejects a BOM,
  rejects NaN/Infinity, then runs contract (strict JSON-mode Pydantic), key
  presence, roster, coverage and noise checks on the raw rows. `EXPECTED_ROSTER`
  is keyed by city; an unknown city is a failure, never a skip.
- `src/yasli_scraper/models.py` — `Snapshot` (`extra="forbid"`, frozen) with
  `city: str = Field(min_length=1)`; `scraped_at` serialises to a Z-suffixed
  second-precision ISO string.
- `tests/test_r2.py` — moto (`mock_aws`) fixture creating a test bucket; three
  tests covering both keys, write order, and the partial-failure invariant. They
  call `put_snapshot(..., client=…, bucket=…, now=…)`, so the injection points
  the new function needs already exist.
- `tests/test_cli.py` — `_varna_snapshot()` builds a 12/53/12 roster matching
  `EXPECTED_ROSTER["varna"]`; `_snapshot_dict()` / `_write_mutated()` serialise
  it and mutate it as a plain dict so keys can be deleted. `promote`'s tests
  reuse these directly.
- `tests/conftest.py` — an autouse fixture points `REPO_ENV_PATH` at a
  nonexistent file so the real repo-root `.env` never bleeds into tests.

## Architecture Facts

- The scraper is the **only** writer of `snapshots/<city>/*.json`
  (`docs/ARCHITECTURE.md`). The object-key layout is the sole wire-level
  contract with the backend.
- Write order is load-bearing: the timestamped object first so a failed second
  write leaves `latest.json` on the previous good payload. Any new upload path
  must preserve this, and the existing order test must keep covering it.
- Production is a Railway **cron** service, `python -m yasli_scraper run --city
  varna`, Sunday 01:00 UTC. `promote` is an operator command, never a cron
  entry point.
- `check` is already wired into the untracked parent `yasli/justfile` as
  `sc-snapshot-check`; README carries a restorable copy of that recipe. The same
  pattern applies to `sc-promote`.
- Rollback for a bad `latest.json` is re-uploading a copy of the object that
  was live before the write. The archived contact-metadata plan's TASK-005
  says "copy a previous `snapshots/varna/<ts>.json` over it" — do **not** carry
  that forward: because the timestamped object is written first, a partial
  failure can leave a timestamped key newer than the live `latest.json` that
  was never served (`docs/DEPLOYMENT.md`, and
  `test_put_snapshot_failure_on_first_write_does_not_touch_latest`).

## Constraints

- The promoted bytes must not be re-serialised: byte identity between the
  checked file and the published objects is the entire point of YAS-17.
- `check`'s stdout contract (exactly one JSON summary object) must not change;
  `promote` is a separate command and may print more.
- `r2.put_snapshot`'s signature and behaviour are frozen — `run` and its tests
  depend on it.
- No new dependencies. moto, respx and pytest are already in the dev extra.
- Test files are UTF-8 explicitly (review #3.2 in the archived
  snapshot-check-command plan); keep writing fixtures with
  `encoding="utf-8"`.

## Useful Commands

```bash
# Scrape to a local file (no R2 env needed)
python -m yasli_scraper run --city varna --out /tmp/yasli-v2-snapshot.json

# Validate that file (no R2 access)
python -m yasli_scraper check --city varna /tmp/yasli-v2-snapshot.json

# Parent-repo recipes (untracked justfile, one level up)
# NOTE: sc-snapshot-local takes a REQUIRED FILE argument (justfile:120) —
# unlike sc-snapshot-check, which defaults to /tmp/yasli-v2-snapshot.json.
just sc-snapshot-local /tmp/yasli-v2-snapshot.json
just sc-snapshot-check   # check that file
just sc-refresh          # re-scrape AND upload — the thing promote replaces
just sc-test  /  just sc-lint

# Tests
pytest tests/test_r2.py tests/test_cli.py -q
```

## Uncertainty

- **How `promote` learns the city for the object key.** Resolved (revised in
  validation round 1): after the report passes, `_run_promote` does one
  `json.loads` of the validated text and reads both `city` and `scraped_at`
  from it, each guarded by `isinstance(…, str)`. `CheckReport.summary` carries
  `city` but not `scraped_at` (`check.py`'s `_summary()` field list), and that
  field set is `check`'s own stdout contract — reading the file directly keeps
  `promote`'s needs out of it.
- **Whether `--dry-run` should require the R2 env vars.** Resolved: yes — it is
  a rehearsal of the real precondition, and `check` already covers the
  credential-free case. The timestamped key is stamped at write time, so a
  dry-run prints it as a `<UTC-ISO-timestamp>` placeholder rather than
  implying an exact key.
- **Whether the receipt belongs on stdout or stderr.** Resolved: stdout, after
  the summary, accepting that `promote`'s stdout is not a single JSON document.
  The receipt is the operator's record of the rollback target.

## References

- [YAS-17](https://linear.app/ivo-tsonev/issue/YAS-17) — the originating issue.
- `docs/artifacts/plans/archive/2026-09-15-scraper-contact-metadata/validation/round-2.md`
  rows 2 and 6 — where Codex raised the "validation and publication are
  different scrapes" finding and it was deferred into this plan.
- `docs/artifacts/plans/archive/2026-09-16-snapshot-check-command/` — the plan
  that built `check`; its reviews explain the stdout-encoding and one-line
  failure rules this command inherits.
- `docs/ARCHITECTURE.md` (two-phase R2 write), `docs/DEPLOYMENT.md` (R2 setup,
  rollback context, cron schedule).
- Related: [YAS-20](https://linear.app/ivo-tsonev/issue/YAS-20) — `check` does
  not detect institution substitution under novel ids; `promote` inherits that
  blind spot.
