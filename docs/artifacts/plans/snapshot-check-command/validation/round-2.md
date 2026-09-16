# Adversarial Validation — Round 2

**Run:** 2026-09-16 04:05 UTC
**Plan:** snapshot-check-command
**Status at start:** draft
**Reviewer:** Codex (`/codex-local:adversarial-review --wait --scope working-tree`)
**Prior rounds in scope:** validation/round-1.md

## Codex output

<!-- Paste /codex:adversarial-review stdout verbatim below this line. Do not edit. -->

# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

Do not implement yet. Round-1 fixed the shape, OSError, CLI-sample, and mutable-live-object gaps, but the planned gate can still approve catastrophic roster loss or a wrong-city artifact, and malformed inputs remain under-specified.

Findings:
- [high] [apply] The rejected identity check leaves roster integrity unproven (docs/artifacts/plans/snapshot-check-command/PLAN.md:18-25)
  A contract-valid snapshot containing 12 nurseries, 12 preschools, and only the Палечко kindergarten satisfies every planned roster check despite losing roughly 52 kindergartens. It can also replace a real institution with a novel unique ID without violating uniqueness. This contradicts the claim that the command proves roster publishability and is weaker than the existing run-path floor in src/yasli_scraper/__main__.py:19-22,99-105. The round-1 rejection rationale treats deliberate blocking on roster changes as undesirable brittleness, but that review is precisely what a publishability gate should force.
  Recommendation: Apply — add per-city expected identities, or at minimum kindergarten/total expectations and deletion/substitution tests; update PLAN.md, RESEARCH.md, TASK-001 and TASK-004.
- [medium] [apply] Contract failures contradict the all-failures guarantee (docs/artifacts/plans/snapshot-check-command/tasks/TASK-001-add-the-snapshot-check-module.md:67-80)
  The plan promises that several problems are reported in one call, but TASK-001 permits an early return after any Snapshot validation failure. A structurally traversable file with schema_version 3 plus a wrong nursery count or null contacts would therefore report only the contract error. This hides independent defects and makes repair iterative instead of producing the promised complete diagnosis.
  Recommendation: Apply — distinguish unusable structure from leaf contract errors, continue safe raw checks after leaf errors, and add a combined contract-plus-semantic test; update PLAN.md, TASK-001 and TASK-004.
- [medium] [apply] --city can bless an artifact whose declared city is wrong (docs/artifacts/plans/snapshot-check-command/PLAN.md:81-83)
  Snapshot.city is only a non-empty string in src/yasli_scraper/models.py:83. The proposed override selects EXPECTED_ROSTER without requiring equality with the validated file city, so a snapshot labeled sofia can pass as Varna via --city varna. The tests cover an unknown override but not this mismatch.
  Recommendation: Apply — remove the fixture-only CLI override or require it to equal Snapshot.city, with a mismatch regression test; update PLAN.md, TASK-001, TASK-002 and TASK-004.
- [medium] [apply] Invalid UTF-8 can escape the promised malformed-input handling (docs/artifacts/plans/snapshot-check-command/tasks/TASK-001-add-the-snapshot-check-module.md:32)
  check_snapshot accepts bytes, but the plan only requires a generic invalid-JSON test. json.loads on invalid UTF-8 raises UnicodeDecodeError rather than JSONDecodeError, so an ASCII syntax test can pass while arbitrary file bytes still produce a traceback instead of a CheckReport and CLI exit 1.
  Recommendation: Apply — explicitly catch UnicodeDecodeError with JSONDecodeError and add invalid-UTF-8 module and CLI cases; update PLAN.md, TASK-001, TASK-002 and TASK-004.

Next steps:
- Revise the four affected contracts and their evidence map, then run a third adversarial pass before implementation.

## Triage

<!--
Verdict values:
  apply   — real plan defect; edit PLAN.md / tasks / DECISIONS.md now
  defer   — has merit but out of scope for this plan; capture as a known limitation or follow-up
  reject  — contradicts an explicit Decision in PLAN.md/DECISIONS.md, or is taste/speculation/incorrect
-->

| # | Finding | Severity | Verdict | Rationale | Applied to |
|---|---------|----------|---------|-----------|------------|
| 1 | Roster integrity unproven: a file that lost ~52 kindergartens passes; substitution under a novel id passes | high | apply (kindergarten count); reject (expected-id list / substitution) | Codex is right that the gate was weaker than `run`'s 50-row floor on total count; the per-city table now pins all three kinds (12/53/12) so `total` 77 is derived and deletion fails. An expected-id list still contradicts the per-city-table Decision, and substitution detection is tamper detection, not a scraper failure mode — recorded as Out of Scope | PLAN.md:Scope, PLAN.md:Out of Scope, PLAN.md:Decisions, PLAN.md:Risks, PLAN.md:Acceptance, RESEARCH.md, TASK-001, TASK-004 |
| 2 | Early return after any contract failure contradicts "report every failure" | med | apply | The semantic checks only need raw row values, so they now run on the raw dict rows independently of `model_validate`; the only early exits are unparseable bytes and an unusable structure. A combined contract + roster test is required | PLAN.md:Decisions, PLAN.md:Acceptance, TASK-001 |
| 3 | `--city` override can bless a `sofia` file as Varna | med | apply | The override had no legitimate use (fixtures can carry `city: "varna"`); `--city` becomes an assertion that the file's declared city matches, the table is always selected by the file's `city`, and the justfile passes `--city varna` like its sibling `sc-refresh` | PLAN.md:Scope, PLAN.md:Decisions, PLAN.md:Acceptance, RESEARCH.md, TASK-001, TASK-002, TASK-003, TASK-004 |
| 4 | Invalid UTF-8 raises `UnicodeDecodeError`, escaping the invalid-JSON handling | med | apply | `json.loads(bytes)` decodes first; catch `UnicodeDecodeError` alongside `JSONDecodeError` and add module + CLI cases | PLAN.md:Scope, PLAN.md:Acceptance, RESEARCH.md, TASK-001, TASK-002 |
