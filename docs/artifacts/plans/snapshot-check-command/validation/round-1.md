# Adversarial Validation — Round 1

**Run:** 2026-09-16 03:45 UTC
**Plan:** snapshot-check-command
**Status at start:** draft
**Reviewer:** Codex (`/codex-local:adversarial-review --wait --scope working-tree`)

## Codex output

<!-- Paste /codex:adversarial-review stdout verbatim below this line. Do not edit. -->

# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

Do not implement this plan yet. The proposed gate can accept a corrupted roster, can crash on contract-invalid inputs, and its final validation is incomplete and nondeterministic.

Findings:
- [high] [apply] Count checks do not prove roster integrity (docs/artifacts/plans/snapshot-check-command/PLAN.md:18-25)
  The proposed “roster” validation checks only kind counts plus the Палечко marker. The current Snapshot model does not enforce unique external IDs, so duplicating one institution while omitting another can preserve all counts and pass every planned check. A missing marker is also not an explicit mutation case, despite the existing jq check rejecting it.
  Recommendation: Apply — add per-city expected identity sets or at minimum unique (kind, external_id) enforcement and an absent-marker test; update PLAN.md, TASK-001 and TASK-004.
- [high] [apply] Raw key inspection can crash before contract validation (docs/artifacts/plans/snapshot-check-command/tasks/TASK-001-add-the-snapshot-check-module.md:57-64)
  TASK-001 requires traversing raw institutions before Snapshot.model_validate. Valid JSON with the wrong shape—null, a list root, null institutions, or a scalar institution row—can therefore raise TypeError or KeyError instead of producing a contract failure and CLI exit 1. Existing tests cover invalid JSON syntax, not malformed JSON structure.
  Recommendation: Apply — require guarded root/list/row type checks before key scanning and add malformed-shape cases to PLAN.md, TASK-001 and TASK-004.
- [high] [apply] Final validation does not prove the CLI mutation criterion (docs/artifacts/plans/snapshot-check-command/tasks/TASK-004-final-validation.md:14-28)
  PLAN.md requires every listed mutation to exit 1 and emit a problem-naming failure line. TASK-001 tests CheckReport behavior, TASK-002 specifies only one generic broken-file CLI case, and TASK-004 manually exercises only null phone. Running the suite plus a catch-all checkbox does not demonstrate CLI exit/stderr behavior for the full mutation matrix.
  Recommendation: Apply — add a parameterized CLI mutation matrix to TASK-002 and explicitly map every PLAN.md criterion-2 mutation to test evidence in TASK-004.
- [medium] [apply] File read failures other than absence can escape as tracebacks (docs/artifacts/plans/snapshot-check-command/tasks/TASK-002-wire-the-check-subcommand-into-the-cli.md:39-44)
  The CLI steps prescribe read_bytes() but handle only a missing path. A directory path, permission failure, or other OSError can escape, contradicting the command's promised 0/1 behavior and the existing run command's convention of converting operational errors to error messages.
  Recommendation: Apply — catch OSError around file reads, return 1 with path and reason, and add a deterministic directory-path test in TASK-002.
- [medium] [apply] Validation is pinned to a mutable live object (docs/artifacts/plans/snapshot-check-command/PLAN.md:102-107)
  The acceptance gate requires current latest.json to remain exactly 77 rows with max_phone_length 24, but RESEARCH records those as a dated observation rather than contractual invariants. A legitimate new publication can make the same implementation pass or fail depending on execution time, so final evidence is not reproducible.
  Recommendation: Apply — assert exact summary values against a committed fixture or immutable timestamped object, retaining mutable latest.json only as a contract/coverage smoke test; update PLAN.md, RESEARCH.md, TASK-001 and TASK-004.

Next steps:
- Revise the plan artifacts for all apply findings, then repeat the adversarial review before implementation.

## Triage

<!--
Verdict values:
  apply   — real plan defect; edit PLAN.md / tasks / DECISIONS.md now
  defer   — has merit but out of scope for this plan; capture as a known limitation or follow-up
  reject  — contradicts an explicit Decision in PLAN.md/DECISIONS.md, or is taste/speculation/incorrect

Row 6 was not raised by Codex; the validator found it while grounding the plan
against `check.py`'s stated import boundary and records it here so round 2 can
see it.
-->

| # | Finding | Severity | Verdict | Rationale | Applied to |
|---|---------|----------|---------|-----------|------------|
| 1 | Count checks do not prove roster integrity: duplicate rows pass; absent marker not an explicit case | high | apply (uniqueness + absent marker); reject (expected-id sets) | `pipeline.coalesce_institutions` already keys rows by `(external_id, kind)` so a duplicate pair is a corrupt file and cheap to assert; a hardcoded id set contradicts the "per-city table" Decision and the Risks mitigation that a roster change is a one-line table edit | PLAN.md:Scope, PLAN.md:Decisions, PLAN.md:Acceptance, TASK-001, TASK-004 |
| 2 | Raw key scan can crash on valid-JSON-wrong-shape input before contract validation | high | apply | The plan orders the raw scan before `model_validate`; a list root, null `institutions` or scalar row would raise instead of failing; needs a shape guard and test cases | PLAN.md:Scope, PLAN.md:Decisions, PLAN.md:Acceptance, TASK-001 |
| 3 | Final validation does not prove the CLI-level mutation criterion; evidence mapping is a catch-all | high | apply | Criterion 2 mixed module and CLI behaviour with only module tests behind it; split it into a module matrix and a parametrised CLI sample, and give TASK-004 an explicit criterion → evidence map | PLAN.md:Acceptance, TASK-002, TASK-004 |
| 4 | File read failures other than absence (directory, permission) escape as tracebacks | med | apply | `read_bytes()` with only a missing-path branch contradicts the 0/1 contract and `run`'s error convention; catch `OSError`, add a deterministic directory-path test | PLAN.md:Acceptance, TASK-002 |
| 5 | Acceptance criterion 1 pins exact `total` 77 / `max_phone_length` 24 to the mutable `latest.json` | med | apply | Those are dated observations, not contract; the live smoke now asserts only roster invariants and exact summary values are asserted on the synthetic fixture in `tests/test_check.py` (no JSON snapshot fixture exists under `tests/fixtures/`, so a committed real file is not introduced) | PLAN.md:Acceptance, PLAN.md:Decisions, RESEARCH.md, TASK-004 |
| 6 | (validator) TASK-004 says `check.py` imports only `models` and stdlib, but collecting contract failures needs `pydantic.ValidationError` | low | apply | The boundary statement is unachievable as written; amend to models + pydantic + stdlib | TASK-004 |
