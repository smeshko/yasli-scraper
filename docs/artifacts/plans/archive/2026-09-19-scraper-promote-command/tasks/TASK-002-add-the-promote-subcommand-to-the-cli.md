# TASK-002: Add the promote subcommand to the CLI

Depends on: TASK-001
Suggested commit: `feat(cli): add promote subcommand for validated snapshots`

## Goal

`python -m yasli_scraper promote [--city CITY] [--dry-run] FILE` checks a local
snapshot and, only if every check passes, publishes those exact bytes to R2 and
prints the payload's `scraped_at` and the keys it wrote.

## Files

- `src/yasli_scraper/__main__.py` — a `promote` subparser; helpers extracted
  from `_run_check` so both commands share the read-and-report path; a
  `_run_promote(path, expected_city, dry_run)` function; dispatch in `main`.
- `tests/test_cli.py` — promote tests, reusing `_varna_snapshot()`,
  `_snapshot_dict()`, `_write_json()` and `_write_mutated()`, plus a moto
  fixture that patches `r2.make_client` the way `tests/test_run_e2e.py:117`
  already does (`monkeypatch.setattr(r2_module, "make_client", lambda env=None:
  client)`) so the real upload path runs against the mock bucket.

## Acceptance

- [ ] A valid file publishes: both R2 objects, read back with
      `get_object(…)["Body"].read()`, hold bytes identical to
      `path.read_bytes()`, and the command exits `0`
- [ ] `scraped_at` is printed before the upload runs; the two keys after it
- [ ] A `promote` that returns before the upload never imports boto3 — proven
      for all three early-return paths (failed check, missing env var,
      `--dry-run`)
- [ ] An upload that raises exits `1` with one `error: upload failed: …` line
      on stderr naming both object keys and the stage reached, and no traceback
- [ ] A file failing any check exits `1`, prints the same `check failed:` lines
      as `check`, and never reaches R2 — the test injects an `r2` double that
      raises if `put_snapshot_bytes` or `make_client` is called
- [ ] `--dry-run` on a valid file exits `0`, prints the exact `latest.json` key
      and the timestamped key as a `<UTC-ISO-timestamp>` placeholder, and makes
      no S3 call
- [ ] `--city sofia` on a Varna file exits `1` naming both cities, with no
      upload; omitting `--city` publishes under the file's own `city`
- [ ] A missing R2 env var exits `1` with the existing `required environment
      variable NAME is not set` line, after the check summary has printed
- [ ] An unreadable path exits `1` with one `error: cannot read …` line
- [ ] `check`'s stdout is still exactly one JSON object (existing tests pass)

Evidence: `pytest tests/test_cli.py -v` output, plus a terminal transcript of
`python -m yasli_scraper promote --dry-run /tmp/yasli-v2-snapshot.json` showing
the summary, the `scraped_at` line, the two key lines, and exit `0`.

## Steps

### RED
- [ ] Add a moto-backed promote fixture to `tests/test_cli.py`: `mock_aws()`, a
      created bucket, `monkeypatch.setenv` for the four `R2_*` vars **with
      `R2_BUCKET` set to the created bucket name** (the existing `all_env`
      fixture sets it to `test-r2_bucket`, which would give `NoSuchBucket` —
      `test_run_e2e.py:100` overrides it for exactly this reason), and
      `monkeypatch.setattr(r2_module, "make_client", lambda env=None: client)`
      — the `test_run_e2e.py:117` pattern. Also
      `monkeypatch.setattr(r2_module, "_utc_iso_filename", lambda now=None:
      "2026-09-19T09:00:00Z")` so the timestamped key is deterministic and the
      tests can name it. Pin it to an instant **different** from the fixture's
      `scraped_at` (`2026-09-15T13:05:33Z`): if the two matched, the same
      string would appear on both the `scraped_at` line and the key line and
      the ordering assertions below would be substring-ambiguous.
      **Do not patch `r2.put_snapshot_bytes`**: the whole point is that the
      real upload path runs, so the assertion can read the stored object
      bodies back
- [ ] `test_promote_valid_file_uploads_the_files_exact_bytes` — call
      `main(["promote", str(path)])`, then assert
      `list_objects_v2(Prefix="snapshots/varna/")` holds exactly the two
      expected keys (`snapshots/varna/2026-09-19T09:00:00Z.json` and
      `snapshots/varna/latest.json`, from the pinned `_utc_iso_filename`), and
      for each assert `s3.get_object(Bucket=…, Key=key)["Body"].read() ==
      path.read_bytes()`. `main()` returns an `int`, not the keys — the bucket
      listing is how the test learns them
- [ ] `test_promote_failing_file_exits_one_and_never_touches_r2` —
      parametrised over `_file_missing_phone_key`, `_file_null_phone`,
      `_file_wrong_nursery_count`, `_file_invalid_utf8`; patch both
      `r2.make_client` and `r2.put_snapshot_bytes` to raise `AssertionError`,
      and assert the bucket is still empty afterwards
- [ ] `test_promote_early_return_never_imports_boto3` — a `python -c` child
      (**not** `-m yasli_scraper`: that form exits before anything can inspect
      `sys.modules`), via `subprocess.run(capture_output=True,
      env={**os.environ, …}, timeout=60)` — the `tests/test_cli.py:436` idiom.
      The child **must** neutralise the repo `.env` before calling `main`:

      ```python
      import sys, pathlib
      import yasli_scraper.__main__ as m
      m.REPO_ENV_PATH = pathlib.Path("/nonexistent/.env")
      rc = m.main([...])
      print(rc, "boto3" in sys.modules)
      ```

      Parametrise over all three early-return paths, asserting `False` each
      time:
      1. a failing file (returns at the check guard)
      2. a valid file with `R2_BUCKET` set to `""` in the child env (returns at
         `validate_env`)
      3. `--dry-run` on a valid file with the full env (returns at the dry-run
         branch)

      Two hazards this spelling exists to avoid, both verified on this machine
      during validation (round-3 #1):
      - **Deleting `R2_BUCKET` from the child env does not work.**
        `validate_env()` calls `_load_repo_env()`, and `conftest.py` neutralises
        `REPO_ENV_PATH` only *in-process* — a subprocess reads the real
        repo-root `.env` and repopulates all four vars, so `validate_env()`
        returns `None`, case 2 falls through to the upload, and the test
        publishes the `example.com` fixture over production
        `snapshots/varna/latest.json` on every `pytest` run. Setting the var to
        `""` avoids this: `load_dotenv(override=False)` will not replace a key
        that is already present, and `validate_env` treats empty as missing
        (verified: returns `'R2_BUCKET'`).
      - **Case 3's "full env" would otherwise depend on the developer's
        `.env`.** Reassigning `REPO_ENV_PATH` in the child makes every case
        independent of whether that file exists (verified: with it neutralised
        and the vars unset, `validate_env()` returns `'R2_ACCOUNT_ID'`).

      Case 1 alone would pass even if the import sat above `validate_env`, so
      all three are needed to pin the position
- [ ] `test_promote_dry_run_makes_no_s3_call_and_names_both_keys` — the
      `latest.json` key appears exactly, the timestamped line carries the
      `<UTC-ISO-timestamp>` placeholder rather than a real stamp, and the
      bucket is still empty
- [ ] `test_promote_prints_scraped_at_before_the_keys` — the `scraped_at` value
      from `_varna_snapshot()` (fixed at `2026-09-15T13:05:33Z`, so the
      assertion is exact) appears on stdout at a lower line index than either
      key line, and the same line carries a rendered age
- [ ] `test_promote_upload_failure_exits_one_with_one_error_line` — patch
      `r2.put_snapshot_bytes` to raise `RuntimeError("simulated R2 failure")`;
      assert exit `1`, one `error: upload failed:` line on stderr naming
      **both** keys from the pinned clock, no `Traceback` in the captured
      output, and that `scraped_at` was already printed on stdout before the
      failure
- [ ] `test_promote_city_mismatch_exits_one_before_upload`
- [ ] `test_promote_missing_env_var_exits_one_after_the_summary` — the summary
      is on stdout and the `required environment variable …` line on stderr
- [ ] `test_promote_success_prints_both_keys` — both returned keys appear on
      stdout
- [ ] `test_promote_missing_path_exits_one_with_a_single_error_line`
- [ ] Run `pytest tests/test_cli.py` and watch the new tests fail

### GREEN
- [ ] Extract from `_run_check`: `_read_snapshot_bytes(path) -> bytes | None`
      (prints the `error: cannot read …` line **to stderr** and returns `None`
      on `OSError`) and `_print_report(report) -> None` — the summary **to
      stdout** with its console-encoding fallback, then one `check failed:` line
      per failure **to stderr** (`file=sys.stderr`), exactly as
      `__main__.py` does today. The stream split is the contract `check`'s
      existing tests pin and DECISIONS §6 depends on; do not collapse it.
      `_run_check` becomes those two plus `return 0 if report.ok else 1`, with
      its behaviour unchanged
- [ ] Add the `promote` subparser: positional `file` (`type=Path`), `--city`
      with the same help text as `check`'s, and `--dry-run` (`action=
      "store_true"`) documented as "validate, resolve the target keys and print
      them, but make no R2 write"
- [ ] Implement `_run_promote` in exactly this order, so every guard precedes
      the boto3 import:
      1. read bytes; return `1` if unreadable
      2. `report = check_snapshot(raw, expected_city)`; `_print_report(report)`;
         return `1` if not `report.ok`
      3. `payload = json.loads(raw.decode("utf-8"))` — one parse of the
         now-validated text — and take `city = payload["city"]` and
         `scraped_at = payload["scraped_at"]`, each guarded by
         `isinstance(…, str)`. A passing report guarantees the contract held,
         so both are strings and `city` is a known `EXPECTED_ROSTER` key; if a
         guard ever trips, print one error line and return `1`
      4. `validate_env()`; return `1` on a missing var (this runs for
         `--dry-run` too — DECISIONS §5)
      5. print the `scraped_at` line **now**, before any upload — on the real
         path as well as the dry-run one — rendering the age alongside the
         exact stamp, e.g.
         `scraped_at: 2026-09-15T13:05:33Z (4d 2h old)`. The ISO string stays
         verbatim in the line so tests can assert on it exactly; the age is
         what makes the value legible against a risk phrased as "a week-old
         snapshot" (DECISIONS §7). A line printed after `put_snapshot_bytes`
         returns would appear only once the object is already live, which is a
         post-mortem, not a mitigation
      6. if `dry_run`: print `snapshots/<city>/<UTC-ISO-timestamp>.json`
         (literal placeholder) and `snapshots/<city>/latest.json`, and return
         `0` — **before** any `r2` import
      7. otherwise `from yasli_scraper import r2` **here**, at the last possible
         point. Compute `now = datetime.now(timezone.utc)` and
         `timestamped, latest = r2.snapshot_keys(city, now)` **before** writing,
         then call `r2.put_snapshot_bytes(city, raw, now=now)` inside a
         `try/except Exception as exc`. On success print the timestamped key
         then the latest key, in write order, and return `0`. On failure print
         one `error: upload failed: {exc}` line to stderr naming both keys and
         which stage was reached — the timestamped object may already have
         landed, `latest.json` may not have been replaced — and return `1`.
         Computing the keys up front is the whole point:
         `put_snapshot_bytes` returns them only on success, so without
         `snapshot_keys` a partial write would leave no record of the key that
         landed, which is exactly the state PLAN's rollback risks are about
- [ ] The `r2` import must sit inside step 7, not at the top of `_run_promote`:
      `r2.py` imports boto3 at module scope (`r2.py:8`), so its position is the
      only thing making "a refused promote never imports boto3" true, and the
      subprocess test above is what proves it
- [ ] Dispatch `promote` in `main` before the `run` branch
- [ ] `pytest`

### REFACTOR
- [ ] Comment why `city` and `scraped_at` are read from the file after the
      report passes (rather than from `report.summary`, which carries `city`
      but not `scraped_at`, and whose field set is `check`'s contract), and why
      `--dry-run` still validates the environment
- [ ] Confirm the receipt wording is greppable and names the keys in write
      order (timestamped first, then latest)
- [ ] `ruff check src tests`

## Notes

- Do not reuse `MIN_EXPECTED_INSTITUTIONS` here — the roster check is strictly
  stronger, and importing the floor would imply a second, weaker gate.
- The dry-run's timestamped key is a placeholder on purpose: `_utc_iso_filename`
  stamps the real one at write time, so printing an exact key would be a lie by
  the time the real promote runs.
- Keep every failure line on one line — `check.py`'s `_printable` already
  guarantees this for check output; the new error lines must not reintroduce
  embedded newlines.
