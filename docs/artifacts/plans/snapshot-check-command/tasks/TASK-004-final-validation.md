# TASK-004: Final Validation

Depends on: all prior tasks
Suggested commit: `chore: final validation for snapshot-check-command`

## Goal

Confirm the plan is fully implemented and production-ready.

## Steps

- [ ] All task checkboxes in `PLAN.md` are ticked
- [ ] `just sc-lint` passes with no issues
- [ ] `just sc-test` passes in full (`tests/test_check.py` and the new
      `tests/test_cli.py` cases included)
- [ ] Module boundaries respected: `check.py` imports only `models`,
      `pydantic` (for `ValidationError`) and the standard library;
      `__main__.py` is the only caller of `check_snapshot`
- [ ] Manual smoke: download the published `latest.json` read-only and run
      `uv run python -m yasli_scraper check --city varna` on it — exit 0,
      empty stderr, summary shows 12 nurseries, 53 kindergartens, 12
      preschools (`total` 77), zero null address/contacts, 12 preschool
      websites, zero noisy values (PLAN.md criterion 1; `max_phone_length` is
      reported, not asserted)
- [ ] Manual smoke, fail path: the `jq '.institutions[0].phone = null'` copy
      exits 1 with a `check failed:` line naming `phone`
- [ ] `just sc-snapshot-check` on both files reproduces the two results above
      through the parent justfile (PLAN.md criterion 5)
- [ ] Every PLAN.md acceptance criterion is ticked only against the evidence
      in the map below — no criterion ticked on "the code looks right"

### Acceptance evidence map

| PLAN.md criterion | Evidence |
|---|---|
| 1 — live `latest.json` passes with the roster invariants | the manual-smoke command output above |
| 2 — `check_snapshot` reports every listed mutation (including invalid UTF-8, city mismatch, non-string `city`/`kind`/`external_id` and the combined contract + roster case); exact summary values on the synthetic fixture | `uv run pytest tests/test_check.py -v` listing one passing test per mutation |
| 3 — CLI exit 1 + `check failed:` line for the six-mutation sample; exit 0 / empty stderr for the valid fixture with and without `--city varna` | `uv run pytest tests/test_cli.py -v` listing the parametrised cases |
| 4 — missing and unreadable path give one `error: …` line, exit 1, no traceback | `uv run pytest tests/test_cli.py -v` (the two path tests) |
| 5 — `just sc-snapshot-check` pass and fail | the two `just` invocations with their exit codes |
| 6 — README documents the command and the recipe body | the README diff |
| 7 — `just sc-test` and `just sc-lint` pass | their output |

### Linear

- [ ] YAS-16 is closed by the PR's `Closes YAS-16` line on merge; no manual
      state change needed. The plan is standalone (`Epic: none`), so there is
      no epic or EPICS.md update.
