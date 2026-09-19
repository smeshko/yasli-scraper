# TASK-003: Document promote and add the sc-promote recipe

Depends on: TASK-002
Suggested commit: `docs(readme): document the promote command`

## Goal

An operator reading README knows how to publish a checked file, what `promote`
does not check, and how to restore the `sc-promote` recipe if the untracked
parent justfile is lost.

## Files

- `README.md` — a `### Promoting a snapshot` section after `### Checking a
  snapshot`, and a `sc-promote` recipe block alongside the existing
  `sc-snapshot-check` one.
- `docs/ARCHITECTURE.md` — one line in the "Two-phase R2 write" section noting
  that `run` and `promote` share it via `put_snapshot_bytes`.

## Acceptance

- [ ] README shows the `promote` invocation, the `--city` and `--dry-run`
      flags, and a real example of the receipt output
- [ ] README states that `promote` runs the full `check` suite and refuses on
      any failure, with no bypass
- [ ] README states that `promote`'s stdout is the summary **plus** the receipt
      lines — unlike `check`, it is not a single JSON document
- [ ] README states that `promote` publishes the file you name and does not
      check `scraped_at` freshness
- [ ] README carries a **runnable** rollback command that works with this
      repo's own `R2_*` env vars (the AWS CLI reads `AWS_ACCESS_KEY_ID` /
      `AWS_SECRET_ACCESS_KEY` and is not a documented tool here)
- [ ] README states that the rollback source is a pre-promote download of
      `latest.json` itself — never "the newest timestamped object", and that
      this rule is permanent, not a special case: a rollback supersedes but
      never deletes the object it replaced, so after any rollback the newest
      timestamped key is again a payload that was never served
- [ ] The `sc-promote` recipe block is present, matches the shape of the
      documented `sc-snapshot-check` block, and forwards extra flags so
      `just sc-promote <file> --dry-run` reaches the CLI as `--dry-run`
- [ ] `docs/ARCHITECTURE.md`'s CLI-entry line mentions the `promote` subcommand

Evidence: the rendered README diff, and a terminal transcript of the documented
`--dry-run` invocation whose output matches the example in the docs verbatim.

## Steps

- [ ] Draft the `### Promoting a snapshot` section: what it does, the exit
      codes (`0` published, `1` any check failure, env failure **or upload
      failure**, `2` argparse usage), the four `R2_*` vars being required even
      for `--dry-run`, and that a failed upload prints `error: upload failed: …`
      rather than a traceback
- [ ] Paste a real receipt from an actual `--dry-run` run rather than inventing
      one
- [ ] Add the recipe block, forwarding trailing flags the way
      `be-load-locations *ARGS:` (parent `justfile:90`) already does — a bare
      `FILE="…"` parameter would bind `--dry-run` to `FILE` and break the
      rehearsal DECISIONS §4 selected:
      ```just
      # Publish an already-validated local snapshot to R2, byte for byte.
      [group('scraper')]
      sc-promote FILE="/tmp/yasli-v2-snapshot.json" *ARGS:
          cd scraper && uv run python -m yasli_scraper promote --city varna "{{ FILE }}" {{ ARGS }}
      ```
- [ ] Add the recipe to the parent `yasli/justfile` itself (untracked — do it
      by hand, it is not part of the commit) and confirm both
      `just sc-promote /tmp/yasli-v2-snapshot.json --dry-run` and the bare
      `just sc-promote` form resolve correctly — check with `just -n sc-promote
      …` before running either for real
- [ ] Document runnable R2 operations built on the repo's own credentials path
      — `r2.make_client()` reads `R2_ACCOUNT_ID` / `R2_ACCESS_KEY_ID` /
      `R2_SECRET_ACCESS_KEY` and sets `region_name="auto"`, none of which the
      AWS CLI picks up from these variable names. Two details are load-bearing
      and were verified during validation (round-3 #2): the command **must**
      run from `scraper/` (`uv run python -c "import yasli_scraper"` from the
      repo root is `ModuleNotFoundError` — there is no root `pyproject.toml`,
      which is why every justfile recipe starts `cd scraper &&`), and it
      **must** load the repo `.env` itself (`make_client` reads `os.environ`
      directly, so without it you get `KeyError: 'R2_ACCOUNT_ID'` — the CLI's
      `_load_repo_env()` is what normally supplies these).

      Use a shared prelude and document all four operations TASK-004 needs:
      ```bash
      # prelude (each command below starts with this)
      cd scraper && uv run python -c "
      import os
      from yasli_scraper.__main__ import _load_repo_env; _load_repo_env()
      from yasli_scraper import r2
      s3, bucket = r2.make_client(), os.environ['R2_BUCKET']
      ...
      "
      ```
      1. **list** the prefix:
         `print([o['Key'] for o in s3.list_objects_v2(Bucket=bucket, Prefix='snapshots/varna/').get('Contents', [])])`
      2. **download** any key (used for `latest.json` and for the timestamped
         object named in the receipt):
         `open(DEST,'wb').write(s3.get_object(Bucket=bucket, Key=KEY)['Body'].read())`
      3. **restore** — the rollback:
         `s3.put_object(Bucket=bucket, Key='snapshots/varna/latest.json', Body=open('/tmp/yasli-rollback.json','rb').read(), ContentType='application/json')`
- [ ] Transcribe the README text from commands that actually ran in TASK-004 —
      including the restore, which TASK-004 drills against a throwaway key so
      it is not first executed during a real incident
- [ ] Update the `__main__.py` line in `docs/ARCHITECTURE.md`'s code-layout
      block and the two-phase-write section
- [ ] Re-read the `check` section and make sure the two read as one coherent
      workflow: `sc-snapshot-local` → `sc-snapshot-check` → `sc-promote`

## Notes

The parent `yasli/justfile` is not under version control, which is exactly why
the recipe text lives in README — the README block is the only durable copy.
