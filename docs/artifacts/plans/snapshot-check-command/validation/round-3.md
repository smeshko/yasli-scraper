# Adversarial Validation — Round 3

**Run:** 2026-09-16 04:30 UTC
**Plan:** snapshot-check-command
**Status at start:** draft
**Reviewer:** Codex (`/codex-local:adversarial-review --wait --scope working-tree`)
**Prior rounds in scope:** validation/round-1.md, validation/round-2.md

## Codex output

<!-- Paste /codex:adversarial-review stdout verbatim below this line. Do not edit. -->

# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

Do not implement yet. Round-2’s count, city-assertion, UTF-8, and combined-failure edits landed, but the plan still permits a false pass on null contacts, overstates roster integrity, and can crash while diagnosing malformed leaf values.

Findings:
- [high] [apply] Coverage instructions skip the null values the gate must reject (docs/artifacts/plans/snapshot-check-command/tasks/TASK-001-add-the-snapshot-check-module.md:116-119)
  TASK-001 says coverage scans skip non-string contact values. That includes null, and the current Institution model explicitly permits null phone/email/director/website values. Implemented literally, null contacts reach neither a contract failure nor a coverage failure, contradicting TASK-001’s null-coverage acceptance cases and PLAN.md’s publishability gate.
  Recommendation: Apply — change TASK-001 so coverage counts missing/null values while only noise and length checks skip non-strings; retain isolated null-field tests. Plan files: TASK-001.
- [high] [apply] The expected-identity rejection still does not prove a roster (docs/artifacts/plans/snapshot-check-command/PLAN.md:50-53)
  Counts plus uniqueness allow one or all real institutions to be replaced by novel unique IDs while the checker declares the roster publishable. The rejection incorrectly classifies this solely as tamper detection: current pipeline code derives external_id from source URLs and coalesces on (external_id, kind), so source-format or extraction drift can create identity substitution as a scraper failure. Legitimate identity changes warrant the same stop-and-review already accepted for count changes.
  Recommendation: Apply — add a per-city expected-identity manifest and a same-count substitution regression test, or narrow every “roster”/“publishable” claim to per-kind count validation. Plan files: PLAN.md, RESEARCH.md, TASK-001, TASK-004.
- [medium] [apply] Continuing raw checks after validation can still crash on malformed leaf values (docs/artifacts/plans/snapshot-check-command/tasks/TASK-001-add-the-snapshot-check-module.md:78-82)
  Round-2 requires semantic checks to continue after contract errors, but roster lookup uses the raw city and duplicate detection uses raw kind/external_id. JSON values such as city: [] or external_id: [] are contract-invalid yet traversable; using them as dictionary or set keys raises TypeError instead of returning a CheckReport. Existing malformed-shape cases cover containers and non-object rows, not these leaf values.
  Recommendation: Apply — require explicit string guards before roster lookup and identity-key construction, and add malformed city/kind/external_id regression cases to the module evidence map. Plan files: PLAN.md, TASK-001, TASK-004.

Next steps:
- Resolve the contradictory null-coverage instruction.
- Reconsider the expected-identity rejection or narrow the advertised guarantee.
- Add malformed-leaf safety requirements and evidence, then run another adversarial pass.

## Triage

<!--
Verdict values:
  apply   — real plan defect; edit PLAN.md / tasks / DECISIONS.md now
  defer   — has merit but out of scope for this plan; capture as a known limitation or follow-up
  reject  — contradicts an explicit Decision in PLAN.md/DECISIONS.md, or is taste/speculation/incorrect

Rows 4 and 5 were not raised by Codex; the validator found them while
re-reading the plan after the round-2 edits. Row 2 is the third push on the
same design point and was escalated to the plan author per the three-round
rule; its final verdict is recorded once answered.
-->

| # | Finding | Severity | Verdict | Rationale | Applied to |
|---|---------|----------|---------|-----------|------------|
| 1 | TASK-001 note says coverage skips non-string values, which would skip `null` and pass a null contact | high | apply | Wording defect introduced by the round-2 edit; coverage counts absent or `null` as missing, only the noise and length scans are string-only | TASK-001 |
| 2 | Counts + uniqueness still do not prove identity; URL-derived ids could drift wholesale and pass | high | defer | Third push on the manifest vs counts design; escalated to the plan author, who chose to narrow the claim (roster = shape, not identity) and file the gap as backlog YAS-20 rather than expand scope; Goal and Out of Scope reworded accordingly | PLAN.md:Goal, PLAN.md:Out of Scope, Linear YAS-20 |
| 3 | Raw checks continuing after contract errors can `TypeError` on non-string `city` / `kind` / `external_id` | med | apply | Direct consequence of round-2 #2; string guards before roster lookup and identity keys, plus regression cases | PLAN.md:Acceptance, TASK-001, TASK-004 |
| 4 | (validator) TASK-001 valid-fixture bullet still says "12 nurseries, 12 preschools, kindergartens"; the table now pins 53 kindergartens so builders must generate 77 rows | low | apply | Inconsistent with the round-2 table edit | TASK-001 |
| 5 | (validator) The "exact summary values" Decision still lists `total` 77 as unasserted on the live object, though it now follows from the table | low | apply | Inconsistent with the round-2 Decision edit | PLAN.md:Decisions |
