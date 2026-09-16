# TASK-002: Wire the check subcommand into the CLI

Depends on: TASK-001
Suggested commit: `feat(cli): add check subcommand for snapshot files`

## Goal

`python -m yasli_scraper check FILE [--city CITY]` runs `check_snapshot` on a
local file, prints the summary as JSON, lists failures on stderr and exits 0
or 1, without requiring any R2 environment variables.

## Files

- `src/yasli_scraper/__main__.py` — `build_parser()` gains a `check` subparser
  (`file: Path`, `--city` optional — asserts the file's declared city, it
  does not override it); `main()` gains the `check` branch
- `tests/test_cli.py` — subcommand tests

## Acceptance

- [ ] `main(["check", <valid file>])` returns 0, prints one JSON object to
      stdout (parseable, `ensure_ascii=False`, indented) and nothing to stderr
- [ ] Parametrised over six mutations of the valid file — missing contact
      key, null `phone`, wrong nursery count, malformed shape (`institutions`
      set to `null`), invalid UTF-8 bytes, `--city sofia` on a Varna file —
      `main(["check", <file>, …])` returns 1, still prints the summary to
      stdout, and prints one `check failed: …` line per failure to stderr
      containing the expected substring (`phone`, `nursery`, `contract:`,
      both city names, …)
- [ ] `main(["check", <missing path>])` and `main(["check", <tmp_path>])`
      (a directory) each return 1 with a single `error: …` line naming the
      path on stderr and no traceback
- [ ] `--city varna` on a Varna file adds nothing (exit 0, empty stderr);
      without `--city` the file's own `city` selects the roster
- [ ] No R2 env var is required (the test runs with none set); the existing
      CLI tests still pass

Evidence: `uv run pytest tests/test_cli.py -v` output.

## Steps

### RED
- [ ] Add the CLI tests above using `tmp_path` files built from
      `Snapshot.model_dump_json()` (mutated via `json.loads`/`json.dumps` so
      keys can be deleted) and `capsys`; `pytest.mark.parametrize` for the
      six-mutation matrix (the invalid-UTF-8 case writes raw bytes), and
      `tmp_path` itself as the unreadable path

### GREEN
- [ ] Add the subparser and the `check` branch in `main()`: read bytes inside
      `try: … except OSError as exc` → `error: cannot read <path>: <reason>`
      on stderr, return 1 (one clause covers missing file, directory and
      permission errors); otherwise call
      `check_snapshot(data, expected_city=args.city)`,
      `print(json.dumps(report.summary, ensure_ascii=False, indent=2))`, then
      each failure as `check failed: <msg>` on stderr, return
      `0 if report.ok else 1`

### REFACTOR
- [ ] Keep `main()` flat: a small `_run_check(args) -> int` helper next to the
      existing `run` handling if the branch exceeds ~20 lines

## Notes

Do not call `validate_env()` on the `check` path; the command reads a local
file only. `_load_repo_env()` already runs for every command and is harmless.
