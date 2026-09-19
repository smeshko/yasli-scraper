# TASK-004: Final Validation

Depends on: all prior tasks
Suggested commit: `chore: final validation for scraper-promote-command`

## Goal

Confirm the plan is fully implemented and production-ready, and prove at
runtime that the bytes checked locally are the bytes serving from
`snapshots/varna/latest.json`.

## Steps

- [ ] All task checkboxes in `PLAN.md` are ticked
- [ ] `just sc-lint` passes with no issues
- [ ] `just sc-test` passes in full — paste the summary line
- [ ] Module/import boundaries respected: `check.py` still does no I/O, `r2.py`
      still knows nothing about `check`, and the `from yasli_scraper import r2`
      inside `_run_promote` still sits after the check, `validate_env` and
      dry-run guards — proven by all three cases of
      `test_promote_early_return_never_imports_boto3`, not by reading the code
      (the failing-file case alone would also pass with the import misplaced
      above `validate_env`)
- [ ] Every `PLAN.md` acceptance criterion is ticked only against the evidence
      in the map below — no criterion ticked on "the code looks right"

### Acceptance evidence map

| PLAN.md criterion | Evidence |
|---|---|
| 1 — both R2 objects byte-identical to the local file | `pytest tests/test_cli.py -v`: `test_promote_valid_file_uploads_the_files_exact_bytes` (moto, `make_client` and `_utc_iso_filename` patched, prefix listed, both object bodies read back) |
| 2 — `scraped_at` printed before the upload, keys after | `test_promote_prints_scraped_at_before_the_keys`, plus the live receipt pasted below |
| 3 — an upload that raises exits 1 with one `error: upload failed:` line | `test_promote_upload_failure_exits_one_with_one_error_line` (no `Traceback` in the captured output) |
| 4 — a failing file exits 1 with the same `check failed:` lines and zero S3 calls | `test_promote_failing_file_exits_one_and_never_touches_r2` (parametrised), `test_promote_early_return_never_imports_boto3`, and the negative proof below — whose stderr is diffed against `check`'s on the same file |
| 5 — `--dry-run` names the keys, makes no S3 call, exits 0 | `test_promote_dry_run_makes_no_s3_call_and_names_both_keys` (asserts the `<UTC-ISO-timestamp>` placeholder, not a real stamp) + the live dry-run transcript below |
| 6 — the success receipt names the exact timestamped key and the latest key | `test_promote_success_prints_both_keys` + the live receipt below |
| 7 — `--city` mismatch fails before upload; bare invocation uses the file's own city | `test_promote_city_mismatch_exits_one_before_upload`, and `test_promote_valid_file_uploads_the_files_exact_bytes` asserting the key sits under `snapshots/varna/` with no `--city` passed |
| 8 — missing R2 env var fails with the existing line, after the checks | `test_promote_missing_env_var_exits_one_after_the_summary` (summary on stdout, error line on stderr) |
| 9 — `run` behaviourally unchanged | `pytest tests/test_r2.py tests/test_run_e2e.py tests/test_cli.py -v` — every pre-existing test green (PLAN criterion 9 names all three files), plus `test_put_snapshot_serialises_with_indent_two` from TASK-001 |
| 10 — README + `docs/ARCHITECTURE.md` document `promote`, and the `sc-promote` recipe is carried | the README and ARCHITECTURE diffs, plus `just -n sc-promote /tmp/yasli-v2-snapshot.json --dry-run` showing the flag reaching the CLI |
| 11 — live: published `latest.json` byte-identical to the checked file and passes `check` | the two `cmp` invocations and the `sc-snapshot-check` exit code in the live section below |
| 12 — `just sc-test` and `just sc-lint` pass | their output, pasted |

### Live verification (the plan's reason for existing)

Do this **outside the Sunday 01:00 UTC cron window**. It overwrites production
`latest.json`.

- [ ] Capture the rollback source **first**: download the currently-served
      object to `/tmp/yasli-rollback.json`. That file — not "the newest
      timestamped key" — is the rollback source. A partial failure of an
      earlier run can leave a timestamped object newer than the live
      `latest.json` that was never served (`docs/DEPLOYMENT.md`,
      `tests/test_r2.py::test_put_snapshot_failure_on_first_write_does_not_touch_latest`)
- [ ] `just sc-snapshot-local /tmp/yasli-v2-snapshot.json` — scrape to a local
      file (the recipe takes a **required** FILE argument)
- [ ] `just sc-snapshot-check` — must exit `0`; paste the summary
- [ ] `just sc-promote /tmp/yasli-v2-snapshot.json --dry-run` — confirm it
      names `snapshots/varna/latest.json` exactly, shows the timestamped key as
      a `<UTC-ISO-timestamp>` placeholder, prints `scraped_at`, exits `0`, and
      adds no object to the prefix
- [ ] `just sc-promote /tmp/yasli-v2-snapshot.json` — paste the receipt,
      recording the exact timestamped key
- [ ] Download the published `latest.json` to `/tmp/yasli-latest.json` and
      prove byte identity: `cmp /tmp/yasli-v2-snapshot.json
      /tmp/yasli-latest.json` — must be silent
- [ ] `just sc-snapshot-check /tmp/yasli-latest.json` — must exit `0`
- [ ] Download the timestamped object from the receipt and `cmp` it against the
      same local file — both R2 objects must match, not just `latest.json`
- [ ] Confirm the backend still ingests it (`just be-ingest`) and spot-check a
      handful of rows — a published snapshot the backend rejects is not a
      success
- [ ] **Drill the restore command** against a throwaway key: upload
      `/tmp/yasli-rollback.json` to `snapshots/varna/rollback-drill.json` with
      the documented restore one-liner, download it back and `cmp` — this is
      the only way the emergency command gets executed on a clean run, and
      README's text is transcribed from it (TASK-003). Using a throwaway key
      keeps the drill off `latest.json`
- [ ] If anything above fails: re-upload `/tmp/yasli-rollback.json` over
      `snapshots/varna/latest.json` using the command documented in README,
      confirm the restored object matches that file with `cmp`, then record what
      broke in the plan before touching it again

### Negative proof

Run this **after** the live verification above, and take its baseline **here** —
a listing captured before the successful promote would always differ by the one
timestamped object that promote legitimately added.

- [ ] List `snapshots/varna/` now and keep it as the baseline
- [ ] Corrupt a copy of the snapshot (delete one institution) and run
      `promote` on it — confirm it exits `1` and that the prefix listing is
      unchanged against the baseline taken in the previous step
- [ ] Run `check` on the same corrupted copy and diff the two stderr outputs —
      the `check failed:` lines must be identical, which is what criterion 4's
      "the same lines as `check`" means

### Epic update

Not applicable — this plan is standalone (`Epic: none`, `Phase: none`). The
Linear issue is YAS-17; `create-pr` picks it up from `PLAN.md`'s `Linear:`
field for the `Closes` line.
