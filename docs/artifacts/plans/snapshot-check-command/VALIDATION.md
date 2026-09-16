# Validation Summary — snapshot-check-command

**Rounds:** 3
**Plan status at validation:** draft
**Run on:** 2026-09-16
**Reviewer:** Codex (`/codex-local:adversarial-review --scope working-tree`), all rounds; validator-observed rows are marked as such in the round files.

## Rounds

| Round | Findings | Applied | Deferred | Rejected |
|-------|----------|---------|----------|----------|
| 1     | 6 (5 Codex + 1 validator) | 6 | 0 | 0 (row 1 partially rejected) |
| 2     | 4 | 4 | 0 | 0 (row 1 partially rejected) |
| 3     | 5 (3 Codex + 2 validator) | 4 | 1 | 0 |

Round 3 still produced apply rows, so per the three-round rule the author was asked: the identity-manifest question was resolved by narrowing the plan's claim and filing YAS-20, and validation stopped without a fourth round.

## Applied

### Round 1
- PLAN.md:Scope, PLAN.md:Decisions, PLAN.md:Acceptance, TASK-001, TASK-004 — roster check gains unique `(kind, external_id)` (grounded in `pipeline.coalesce_institutions`) and an explicit absent-marker case; the expected-id-list half of the finding was rejected as contradicting the per-city-table Decision (round-1 #1)
- PLAN.md:Scope, PLAN.md:Decisions, PLAN.md:Acceptance, TASK-001 — shape guard before the raw key scan so a list root, null `institutions` or scalar row is a `contract:` failure, not a `TypeError` (round-1 #2)
- PLAN.md:Acceptance, TASK-002, TASK-004 — criterion 2 split into a module mutation matrix and a parametrised CLI sample; TASK-004 gains a criterion → evidence map replacing the catch-all checkbox (round-1 #3)
- PLAN.md:Acceptance, TASK-002 — `read_bytes()` wrapped in `except OSError`; deterministic directory-path test (round-1 #4)
- PLAN.md:Acceptance, PLAN.md:Decisions, RESEARCH.md, TASK-004 — exact `total` / `max_phone_length` no longer asserted on the mutable `latest.json`; exact summary values asserted on the synthetic fixture (round-1 #5)
- TASK-004 — module-boundary statement corrected to models + pydantic + stdlib (`ValidationError` is needed) (round-1 #6, validator)

### Round 2
- PLAN.md:Scope, Out of Scope, Decisions, Risks, Acceptance, RESEARCH.md, TASK-001, TASK-004 — the per-city table now pins all three kinds (12 / 53 / 12) so `total` 77 is derived and a file that lost its kindergartens fails; the expected-id manifest was again rejected and substitution detection recorded as Out of Scope (round-2 #1)
- PLAN.md:Decisions, PLAN.md:Acceptance, TASK-001 — semantic checks run on the raw rows independently of `model_validate`, so a contract error no longer hides a roster or coverage defect; combined contract + roster test required (round-2 #2)
- PLAN.md:Scope, Decisions, Acceptance, RESEARCH.md, TASK-001, TASK-002, TASK-003, TASK-004 — `--city` becomes an assertion of the file's declared city instead of an override; the justfile passes `--city varna` like `sc-refresh` (round-2 #3)
- PLAN.md:Scope, PLAN.md:Acceptance, RESEARCH.md, TASK-001, TASK-002 — `UnicodeDecodeError` caught alongside `JSONDecodeError`; invalid-UTF-8 module and CLI cases (round-2 #4)

### Round 3
- TASK-001 — null-coverage wording fixed: coverage counts absent or `null` as missing, only noise/length scans are string-only (a defect the round-2 edit introduced) (round-3 #1)
- PLAN.md:Acceptance, TASK-001, TASK-004 — string guards before roster lookup and identity keys; non-string `city` / `kind` / `external_id` regression cases (round-3 #3)
- TASK-001 — valid fixture bullet and RED step updated to a 77-row `_varna_roster()` builder matching the 12 / 53 / 12 table (round-3 #4, validator)
- PLAN.md:Decisions — `total` 77 is derived from the table and asserted; only `max_phone_length` is reported-not-asserted on the live object (round-3 #5, validator)

## Deferred

- (round-3 #2) The gate proves roster shape, not identity: a file whose real institutions are replaced by novel unique ids passes with counts intact, and `external_id` is URL-derived so wholesale extraction drift is a plausible scraper failure — narrowed the plan's Goal/Scope claim and filed **YAS-20** (Backlog, `code-review` + `scraper`) with the manifest and anchor-id options; the author chose not to expand YAS-16's scope.

## Rejected

- (round-1 #1, round-2 #1 — partial) A per-city expected-id manifest of all 77 ids — contradicts the "roster expectations are a per-city table" Decision and the Risks mitigation that a roster change is a one-line table edit; every legitimate roster change would need a manifest edit as well. Escalated on the third push and resolved as the YAS-20 defer above rather than a rejection.
