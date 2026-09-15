# Adversarial Validation — Round 1

**Run:** 2026-09-15 (UTC)
**Plan:** scraper-contact-metadata
**Status at start:** draft
**Reviewer:** Codex (`/codex-local:adversarial-review --wait --scope working-tree`)

## Codex output

<!-- Paste /codex:adversarial-review stdout verbatim below this line. Do not edit. -->

# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

Do not ship the plan yet: it contains contradictory phone-normalisation requirements, relies on commands absent from this repository, and its final-validation task does not explicitly verify all PLAN acceptance criteria.

Findings:
- [high] Phone handling is internally contradictory (docs/artifacts/plans/scraper-contact-metadata/PLAN.md:24-33)
  The scope says to “strip ... slash-separated phone forms,” but the decision and TASK-001 explicitly require preserving every slash and separator. An implementation can satisfy one reading while violating the other, producing either lossy contact data or a failed acceptance review. Verdict: apply — resolve this to “collapse whitespace only; preserve slashes and other phone punctuation” and update the scope/acceptance wording.
  Recommendation: apply; change PLAN.md and any affected TASK-001/TASK-002 wording so the normalisation rule is singular and testable.
- [high] The planned validation commands are not available in the target repository (docs/artifacts/plans/scraper-contact-metadata/tasks/TASK-005-final-validation.md:13-30)
  The plan and final task require `just sc-lint`, `sc-test`, `sc-snapshot-local`, `sc-snapshot-check`, `sc-refresh`, and `be-ingest`, but the scraper working tree has no justfile/Justfile and its documented README exposes Python CLI commands instead. Unless these commands are supplied by an external root-level orchestration file, TASK-005 cannot be executed from this checkout and its evidence cannot be produced as written. Verdict: apply — define the actual command locations/invocations or add the required orchestration as an explicit prerequisite.
  Recommendation: apply; update TASK-005 and RESEARCH.md with commands that exist in the current workspace, including the explicit backend working directory for ingest.
- [medium] Final validation does not explicitly cover the schema convergence criteria (docs/artifacts/plans/scraper-contact-metadata/tasks/TASK-005-final-validation.md:31-32)
  PLAN.md requires the schema artifact to match the models and the backend fixture to differ only by `minItems`, but TASK-005 only says all PLAN criteria are met after running general tests and a live ingest. The concrete schema-generation and backend-diff checks exist only in TASK-004, so the designated final gate can be marked complete without re-verifying two release-blocking contract conditions after later edits. Verdict: apply — add explicit generator/idempotence, schema-artifact test, and backend-fixture diff checks to TASK-005 or require attached TASK-004 evidence by exact command/output.
  Recommendation: apply; modify TASK-005 to enumerate PLAN acceptance criteria 2 and 5 with their exact commands and recorded evidence.
- [medium] The noise acceptance criterion conflicts with existing raw-field guarantees (docs/artifacts/plans/scraper-contact-metadata/tasks/TASK-005-final-validation.md:22-23)
  PLAN.md says no emitted field may contain leading/trailing whitespace, tabs, or `\r`, while the current schema README and parser contract deliberately preserve `AddressEntry.street` and `.number` verbatim. TASK-005's proposed jq check iterates every string value, so it tests those pre-existing raw fields too and can fail for unrelated source formatting; alternatively, narrowing the implementation to contacts would not satisfy the literal criterion. Verdict: apply — scope the criterion and noise check to the four new contact fields, or explicitly require and plan a separate change to normalise address-entry fields.
  Recommendation: apply; change the check to select `phone`, `email`, `director`, and `website`, preserving the documented raw street/number contract.

Next steps:
- Resolve the phone separator contradiction.
- Replace or formally provide the missing just-command orchestration.
- Make TASK-005 explicitly verify schema convergence and contact-only noise invariants.

## Triage

<!--
Verdict values:
  apply   — real plan defect; edit PLAN.md / tasks / DECISIONS.md now
  defer   — has merit but out of scope for this plan; capture as a known limitation or follow-up
  reject  — contradicts an explicit Decision in PLAN.md/DECISIONS.md, or is taste/speculation/incorrect

Rows 1–4 are Codex's findings. Rows 5–10 are grounded defects found by the
validator while checking Codex's claims against the repo; they are marked
"(validator)" so round 2 can tell the two sources apart.
-->

| # | Finding | Severity | Verdict | Rationale | Applied to |
|---|---------|----------|---------|-----------|------------|
| 1 | Phone normalisation is stated two ways: Scope says "strip … slash-separated phone forms", Decisions/TASK-001 say keep every slash | high | apply | Scope copied the epic's ambiguous phrase; the plan's own Decision and TASK-001 acceptance already pin "collapse whitespace only, preserve slashes", which also matches the epic's "do not invent a canonical format" — align Scope, Out of Scope and add an explicit Decision | PLAN.md:Scope, PLAN.md:Out of Scope, PLAN.md:Decisions |
| 2 | `just sc-*` / `be-ingest` recipes are absent from this repo, so TASK-005 cannot run as written | low | apply | Premise is wrong: the recipes live in the parent `yasli/justfile` and `just` walks up from `scraper/` (verified with `just --list` from this checkout). Applied only a locator note so the next reader does not hit the same wall | RESEARCH.md:Useful Commands, TASK-005 |
| 3 | TASK-005 does not explicitly re-verify AC #2 (artifact matches models) or AC #5 (backend-fixture diff is only `minItems`) | med | apply | The final-validation task must cover every PLAN.md criterion; AC #5 lived only in TASK-004 and could be silently invalidated by a later edit | TASK-005 |
| 4 | "No emitted field contains …" collides with the verbatim `street`/`number` contract | med | apply | `parser._clean_text` already collapses whitespace on street/number so the jq would pass today, but the criterion must name the fields it governs; scoped to the four contact fields plus `address` | PLAN.md:Acceptance Criteria, TASK-005, RESEARCH.md:Useful Commands |
| 5 | (validator) TASK-005 says `link_plan.py` is unusable because epics live in the `yasli/` parent — stale since 35e8b97 moved them into `docs/artifacts/epics/` | med | apply | `link_plan.py` roots at the git toplevel (`scraper/`) and now resolves both the epic and the plan; replaced the hand-edit instructions with the script call and fixed the prose | TASK-005 |
| 6 | (validator) TASK-005's conditional "tick backend phase 1.1's second criterion" — all five are already `[x]` in `backend/docs/artifacts/epics/01-institution-data-foundation.md` | low | apply | Dead step that invites a pointless cross-repo commit; replaced with a statement of fact | TASK-005 |
| 7 | (validator) AC #1 and TASK-005 hard-code 77/12 counts measured 2026-08-17; a roster change on the portal would fail the criterion although the feature works | low | apply | Reworded as zero-null invariants with the measured counts as the expected value to record, not the pass/fail bar | PLAN.md:Acceptance Criteria, TASK-005 |
| 8 | (validator) TASK-003 says the model must match the backend "exactly" but does not name the backend's validator | low | apply | Named `_optional_strings_non_empty(cls, value, info: ValidationInfo)` from `../backend/src/yasli/snapshot_contract/models.py`; its message keeps the field name so the existing `match="address"` test still passes | TASK-003 |
| 9 | (validator) TASK-002 says `WEBSITE` is "absent" from jasla rows while RESEARCH.md says key presence is unverified (0/12 non-empty) | low | apply | Acceptance reworded so absent and blank are both covered and both yield `None` | TASK-002 |
| 10 | (validator) `sc-snapshot-check` asserts nothing about contacts; TASK-005 carries ad-hoc jq instead | low | defer | The recipe lives in the parent `yasli/justfile`, outside this PR's reach; worth a follow-up so the coverage check survives the plan | — |
