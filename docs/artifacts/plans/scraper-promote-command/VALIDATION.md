# Validation Summary — scraper-promote-command

**Rounds:** 3
**Plan status at validation:** draft
**Run on:** 2026-09-19

Codex was usage-limited for the entire validation (the `adversarial-review` job
failed in 6s with `You've hit your usage limit`, confirmed via
`codex-companion.mjs status`). Per the shared protocol every round ran with a
clean `general-purpose` subagent given the same adversarial framing.

## Rounds

| Round | Findings | Applied | Deferred | Rejected |
|-------|----------|---------|----------|----------|
| 1     | 10       | 10      | 0        | 0        |
| 2     | 13       | 13      | 0        | 0        |
| 3     | 10       | 10      | 0        | 0        |

Round 3 again produced only `apply` rows, which the protocol treats as a
stop-and-ask signal. It was put to the user, who chose apply-all-then-stop: the
plan's *design* — the `r2` split, the promote control flow, the gates and all
seven decisions — went unchallenged for three rounds, while the recurring
defects were in the patches themselves. Each applied edit was re-verified
against the code here rather than by a fourth reviewer.

## Applied

### Round 1

- `TASK-002`, `PLAN.md:Acceptance Criteria` — the byte-identity test patched out
  the very upload path it was meant to prove; now patches `r2.make_client` and
  reads both object bodies back (round-1 #1)
- `TASK-004` — restored the repo's acceptance-evidence map, one row per
  criterion; three criteria had no covering step at all (round-1 #2)
- `TASK-004`, `TASK-003`, `PLAN.md:Risks` — the pre-promote rollback target was
  wrong in the partial-failure mode this repo documents; the source is now a
  download of the live `latest.json` (round-1 #3)
- `RESEARCH.md:Useful Commands`, `TASK-004` — `just sc-snapshot-local` takes a
  required FILE argument, so the first live step would have errored (round-1 #4)
- `TASK-003` — the drafted `sc-promote` recipe could not forward `--dry-run`,
  making the chosen rehearsal unreachable; now uses the `*ARGS` pattern
  (round-1 #5)
- `TASK-002`, `TASK-004` — "never touches boto3" was unfalsifiable; import
  position pinned and a subprocess assertion added (round-1 #6)
- `PLAN.md:Goal/Scope/Risks`, `TASK-002`, `DECISIONS.md §7`, `RESEARCH.md` — the
  stale-file mitigation was a restatement of the risk; `promote` now prints the
  payload's `scraped_at` (round-1 #7)
- `PLAN.md:Goal/Risks` — the Goal overclaimed against the plan's own
  Out-of-Scope: the weekly cron keeps publishing unchecked (round-1 #8)
- `TASK-002:GREEN` — named the stream split (`summary` → stdout, failures →
  stderr) that `check`'s tests pin (round-1 #9)
- `PLAN.md:header` — added the `Branch:` field both archived plans carry
  (round-1 #10)

### Round 2

- `TASK-002:RED`, `TASK-004` — the byte-identity test still had no way to learn
  the real-clock timestamped key; now pins `_utc_iso_filename` and lists the
  prefix (round-2 #1)
- `TASK-002:RED` — the boto3 test named two mutually exclusive forms and bolded
  the one that proves nothing; pinned to the `-c` form (round-2 #2)
- `TASK-002:RED`, `TASK-004` — the import-position claim was wider than its
  single proving test; parametrised over all three early-return paths
  (round-2 #3)
- `TASK-004` — the negative proof's baseline was taken before the successful
  promote, so its diff would always have shown one added key (round-2 #4)
- `TASK-002`, `TASK-003` — nothing specified what happens when the upload
  *raises*: the operator would get a bare traceback and no record, in exactly
  the partial-write state the rollback story is built on (round-2 #5)
- `TASK-003` — the drafted `aws s3 cp` rollback could not authenticate
  (`R2_ACCESS_KEY_ID` ≠ `AWS_ACCESS_KEY_ID`) (round-2 #6)
- `TASK-002:GREEN`, `PLAN.md:Risks`, `DECISIONS.md §7` — `scraped_at` was
  printed *after* the object went live, making the mitigation a post-mortem;
  moved ahead of the write (round-2 #7)
- `TASK-002:RED` — reusing the `all_env` fixture would have given
  `NoSuchBucket` (round-2 #8)
- `TASK-001:Files` — two incompatible `put_snapshot_bytes` signatures
  (round-2 #9)
- `TASK-003` — the "never roll back to the newest timestamped object" rule was
  framed as a special case when it is permanent (round-2 #10)
- `DECISIONS.md` — an orphaned `Option 3` bullet stranded in §7 by the round-1
  insertion anchor (round-2 #11)
- `TASK-004` — evidence map row omitted a test file the criterion names
  (round-2 #12)
- `PLAN.md:Risks` — "the obvious follow-up" implied a ticket exists; now states
  no issue is filed (round-2 #13)

### Round 3

- `TASK-002:RED` — **the most serious finding of the validation.** The boto3
  test's second case deleted `R2_BUCKET` from the child env to force an early
  return, but `validate_env()` calls `_load_repo_env()` and `conftest.py`
  neutralises `REPO_ENV_PATH` only in-process: a subprocess reads the real
  repo-root `.env` and repopulates every variable. Verified on this machine —
  `validate_env()` returns `None` with all four vars popped. The case would
  have fallen through to a real upload, publishing the 77-row `example.com`
  fixture over production `snapshots/varna/latest.json` on every `pytest` run.
  Fixed with both belts, each verified: `R2_BUCKET=""` (returns `'R2_BUCKET'`,
  since `load_dotenv(override=False)` will not replace a present key) and a
  neutralised `REPO_ENV_PATH` in the child (returns `'R2_ACCOUNT_ID'`)
  (round-3 #1)
- `TASK-003` — both rollback commands were unrunnable: `ModuleNotFoundError`
  without `cd scraper` (no root `pyproject.toml`), then
  `KeyError: 'R2_ACCOUNT_ID'` without `_load_repo_env()`. All three states
  verified; the corrected form is now in the plan, covering all four R2
  operations TASK-004 needs (round-3 #2, #5)
- `TASK-001`, `TASK-002`, `PLAN.md` — `PLAN`'s "naming how far the two-phase
  write got" was unproducible, because `put_snapshot_bytes` returns its keys
  only on success. Fixed properly rather than reworded down: `r2` now exposes
  `snapshot_keys(city, now)`, so `_run_promote` computes both keys before
  writing and the error line can name them (round-3 #3)
- `PLAN.md:Out of Scope`, `RESEARCH.md` — both still stated the unsafe
  "roll back to a timestamped object" rule that round-1 #3 fixed everywhere
  else (round-3 #4)
- `TASK-004`, `TASK-003` — the restore command only ever ran if something
  failed, so a clean run would ship an emergency command that had never
  executed; now drilled against a throwaway key (round-3 #6)
- `TASK-002:RED`, `TASK-004` — the pinned fake clock equalled the fixture's
  `scraped_at`, making the ordering assertions substring-ambiguous (round-3 #7)
- `TASK-001:Notes` — stale cross-reference telling the implementer to thread
  `now=` through `_run_promote` (round-3 #8)
- `TASK-002`, `DECISIONS.md §7`, `PLAN.md` — a bare ISO stamp is not legible
  against a risk phrased as "a week-old snapshot"; the line now renders the age
  alongside the exact stamp (round-3 #9)
- `PLAN.md:Scope/Acceptance Criteria`, `TASK-004` — TASK-003's
  `docs/ARCHITECTURE.md` deliverable had no criterion and no evidence row
  (round-3 #10)
- `DECISIONS.md §4` — a stale echo of the old rollback model ("rollback needs
  the identity of the previous timestamped object"), caught in the final sweep

## Deferred

None. Every finding across all three rounds was a real plan defect and was
applied.

## Rejected

None. No finding contradicted an explicit Decision, and every claim was
re-grounded against the code, the parent `justfile` or a live check on this
machine before triage — including three that were verified by executing them
(the `.env` repopulation, the `R2_BUCKET=""` behaviour, and the rollback
command's import and credential failures).

## User decisions during validation

Three findings touched choices made in the authoring interview and were put to
the user rather than decided in triage:

- **round-1 #7** — print `scraped_at` in the receipt only, **not** in
  `check`'s summary dict (which would change `check`'s stdout contract), and
  still no freshness guard.
- **round-1 #8** — reword the Goal and add a Risks bullet for the unchecked
  weekly cron, **without** filing a Linear follow-up. `PLAN.md`'s Risks section
  is therefore the only record of that gap.
- **round-3 #9** — render the age alongside the ISO stamp, keeping the exact
  string in the line so tests assert on it verbatim.
