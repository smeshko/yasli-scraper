# Plan: Promote a validated local snapshot to R2

Status: done
Branch: feature/yas-17-scraper-promote-command
Risk: medium
Epic: none
Phase: none
Linear: YAS-17 (https://linear.app/ivo-tsonev/issue/YAS-17)
Created: 2026-09-19

## Goal

Make the snapshot validated locally and the object published to R2 the same
bytes, by adding a `promote <file>` subcommand that checks a local snapshot and
uploads exactly it — so **operator** publication stops being a second,
unchecked scrape. The weekly cron is untouched and keeps publishing unchecked
re-scrapes; see Risks.

## Scope

- `r2.snapshot_keys(city, now)` — the object-key layout in one place, so a
  caller can name both keys before the writes begin.
- `r2.put_snapshot_bytes(city, body, …)` — the two-phase write (timestamped
  object first, `latest.json` second) over caller-supplied bytes;
  `r2.put_snapshot` keeps its signature and delegates after serialising.
- `promote [--city CITY] [--dry-run] FILE` in `yasli_scraper.__main__`: read the
  file, run `check.check_snapshot` on its bytes, print the summary and any
  failures exactly as `check` does, refuse on any failure, then upload those
  bytes verbatim and print a receipt naming the payload's `scraped_at` and both
  object keys.
- Unit tests: verbatim bytes in both R2 objects (moto), refusal makes no S3
  call, `--dry-run` makes no S3 call, receipt lines, `run` unchanged.
- README `promote` section, a restorable `sc-promote` recipe for the untracked
  parent `yasli/justfile`, and the matching `docs/ARCHITECTURE.md` lines.
- Live proof in final validation: scrape → check → promote → download
  `latest.json` → re-check and byte-compare against the local file.

## Out of Scope

- Changing `run`. It keeps re-scraping and keeps `MIN_EXPECTED_INSTITUTIONS`;
  gating the weekly cron on `check_snapshot` is a separate decision with a
  bigger blast radius.
- A `--force` / `--no-check` escape hatch. A roster change is handled by
  updating `EXPECTED_ROSTER` in `check.py`, not by bypassing the gate.
- A freshness *guard* on `scraped_at` — `promote` prints the payload's
  `scraped_at` and its age before uploading, but never refuses on age.
  See Risks.
- Adding `scraped_at` to `check.CheckReport.summary`. `promote` reads it from
  the file itself; `check`'s stdout contract stays exactly as it is today.
- Rewriting, reformatting or canonicalising the promoted payload in any way.
- New cities. `promote` inherits `check`'s per-city roster table; an unknown
  city already fails the check.
- Deleting R2 objects. Rollback stays a manual re-upload of the **pre-promote
  copy of `latest.json`** — never a key chosen by timestamp; see Risks.

## Research Summary

See [RESEARCH.md](./RESEARCH.md). The load-bearing findings:

- `r2.put_snapshot` already owns the ordered two-phase write and takes a
  `Snapshot`, serialising it itself — so bytes cannot currently reach R2
  unmodified. Splitting out a bytes-level function is the smallest change that
  preserves every existing guarantee (`tests/test_r2.py` covers order and the
  partial-failure invariant).
- `check.check_snapshot(raw, expected_city)` is already pure, I/O-free and
  byte-oriented; it returns a `CheckReport` with a `summary` dict and a
  `failures` list. It is directly reusable as `promote`'s gate.
- `__main__._run_check` already does read-bytes → check → print summary →
  print `check failed:` lines → exit 0/1, including the console-encoding
  fallback. `promote` shares that path rather than reimplementing it.
- `check_snapshot` selects the roster by the file's own `city` and fails an
  unknown city, so a file that passes the gate is guaranteed to carry a
  known, string-typed `city` — safe to use for the object key prefix.

## Decisions

See [DECISIONS.md](./DECISIONS.md) for the alternatives weighed and rejected.

## Risks

- **Promoting a stale file.** Nothing *refuses* on `scraped_at`: a week-old
  snapshot that still passes every check publishes happily under a fresh
  timestamped key. *Mitigation:* `promote` prints the payload's `scraped_at`
  **before** it uploads, so the age of what is being published is on screen
  ahead of the write rather than in a post-mortem, and README states plainly
  that `promote` publishes the file you name. A refusal threshold was
  considered and deliberately not built — see DECISIONS.md §7.
- **The weekly cron still publishes unchecked.** `run` is out of scope, so the
  Railway cron (Sun 01:00 UTC) overwrites `latest.json` with an unchecked
  re-scrape within days of the live proof. This plan makes *operator*
  publication verifiable, not production publication. *Mitigation:* none in
  this plan — the Goal is worded to claim only what it delivers. Gating `run`
  on `check_snapshot` would close it; **no follow-up issue is filed** (a
  deliberate call during validation), so this paragraph is the only record.
- **The live verification overwrites production `latest.json`.** *Mitigation:*
  the currently-served payload is downloaded to a local file **before**
  promoting, and rollback re-uploads that exact file over `latest.json`. Do not
  roll back to "the newest timestamped object" — see the next risk.
- **The newest timestamped object may never have been served.** `put_snapshot`
  writes the timestamped object first and `latest.json` second, so a partial
  failure (documented in `docs/DEPLOYMENT.md`, pinned by
  `tests/test_r2.py::test_put_snapshot_failure_on_first_write_does_not_touch_latest`)
  leaves a timestamped object newer than the live `latest.json`. *Mitigation:*
  the rollback source is the pre-promote download of `latest.json` itself, not
  a key chosen by timestamp; TASK-003 puts a runnable rollback command in
  README.
- **Racing the weekly cron** (Railway, Sun 01:00 UTC) — a cron run mid-promote
  would interleave two writers of `latest.json`. *Mitigation:* do the live
  verification well outside the Sunday window.
- **Silent divergence from `run`'s payload.** If `put_snapshot` stops
  delegating, `run` and `promote` drift apart. *Mitigation:* TASK-001 keeps a
  test asserting `put_snapshot` writes exactly
  `payload.model_dump_json(indent=2).encode("utf-8")`.
- **`promote`'s stdout is not a single JSON document** (summary, then receipt
  lines), unlike `check`'s. *Mitigation:* documented in README; `check` remains
  the pipe-friendly command.

## Acceptance Criteria

- [x] Both R2 objects written by `promote` are byte-identical to the local file
      — a moto test that patches `r2.make_client` (not `put_snapshot_bytes`) so
      the real upload path runs, then compares `get_object(…)["Body"].read()`
      for each key against `path.read_bytes()`
- [x] The payload's `scraped_at` is printed before the upload runs, with a
      rendered age alongside the exact ISO stamp, and the keys after it
- [x] An upload that raises exits `1` with one `error: upload failed: …` line
      naming both object keys and the stage reached — never a bare traceback
- [x] A file failing any check exits `1`, prints the same `check failed:` lines
      as `check`, and performs zero S3 calls (the test fails the run if a client
      is built or `put_object` is reached)
- [x] `--dry-run` prints the `latest.json` key and a `<UTC-ISO-timestamp>`
      placeholder for the timestamped key, performs zero S3 calls, and exits `0`
- [x] On success the receipt names the exact timestamped key and the latest key
- [x] `--city` mismatch fails before any upload; no `--city` publishes under the
      file's own declared city
- [x] Missing R2 env vars fail with the same `required environment variable …`
      line as `run`, after the checks have run
- [x] `run` is behaviourally unchanged: `tests/test_r2.py`,
      `tests/test_run_e2e.py` and `tests/test_cli.py` pass with additions only
- [x] README documents `promote` (including the stdout caveat) and carries the
      restorable `sc-promote` recipe; `docs/ARCHITECTURE.md` names the
      subcommand and the shared two-phase write
- [x] Live: a real scrape passes `sc-snapshot-check`, `promote` publishes it,
      and the downloaded `snapshots/varna/latest.json` is byte-identical to the
      local file and passes `sc-snapshot-check`
- [x] `just sc-test` and `just sc-lint` pass

## Tasks

Task state lives here. Tasks are appended by `scripts/add_task.py` and
`scripts/add_final_task.py`. Update the checkboxes as work progresses.

- [x] TASK-001: Upload snapshot bytes verbatim from r2.put_snapshot_bytes
- [x] TASK-002: Add the promote subcommand to the CLI (depends on TASK-001)
- [x] TASK-003: Document promote and add the sc-promote recipe (depends on TASK-002)
- [x] TASK-004: Final Validation
