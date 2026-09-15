# Adversarial Validation — Round 2

**Run:** 2026-09-15 (UTC)
**Plan:** scraper-contact-metadata
**Status at start:** draft
**Reviewer:** Codex (`/codex-local:adversarial-review --wait --scope working-tree`)
**Prior rounds in scope:** validation/round-1.md

## Codex output

<!-- Paste /codex:adversarial-review stdout verbatim below this line. Do not edit. -->

# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

Do not ship this plan yet. TASK-003 still omits a pipeline projection, and the release gate can publish an artifact different from the one it validates before discovering backend incompatibility.

Findings:
- [high] TASK-003 omits the final merged-to-output projection (docs/artifacts/plans/scraper-contact-metadata/tasks/TASK-003-add-contact-fields-to-the-snapshot-models-and-pipeline.md:20-23)
  The implementation steps add contacts to both input constructors, MergedInstitution, and its seed/merge paths, but do not require copying them into the final Institution objects returned by coalesce_institutions. The current pipeline reconstructs those objects field-by-field, so following the listed GREEN steps can silently reset every contact to its model default.
  Recommendation: Explicitly add the final MergedInstitution-to-Institution reconstruction as a required edit and assert contact values on the fully coalesced, serialized pipeline result.
- [high] Production validation checks a different scrape than the artifact published to R2 (docs/artifacts/plans/scraper-contact-metadata/tasks/TASK-005-final-validation.md:25-44)
  TASK-005 validates coverage, noise, and phone length on a local scrape, then sc-refresh performs another live scrape and overwrites latest.json. Only ingest and a five-row query follow the write. Source changes, partial responses, or normalization differences in the second run can therefore publish an artifact that never received the stated checks. The vague deployed-backend confirmation also provides no behavioral compatibility test until after latest.json has been replaced.
  Recommendation: Publish the exact locally validated payload through a promotion mechanism, or fetch the newly written R2 latest.json and rerun every coverage, noise, count, length, and contract check before ingest. Define an executable deployed-version compatibility check and a rollback procedure for latest.json.
- [medium] The null-serialization acceptance criterion has no test (docs/artifacts/plans/scraper-contact-metadata/tasks/TASK-003-add-contact-fields-to-the-snapshot-models-and-pipeline.md:27-39)
  The tasks prove only that parsing produces None and that model defaults validate as None. They never prove serialized snapshot JSON contains each omitted field with value null. A serializer using exclude_none could omit the keys while every planned unit test and the live non-null coverage checks pass, violating PLAN acceptance criterion 4.
  Recommendation: Add a snapshot serialization test with omitted source contacts and assert that phone, email, director, and website keys are present with JSON null; repeat a key-presence assertion in final validation.
- [medium] Contact conflict handling remains order-dependent (docs/artifacts/plans/scraper-contact-metadata/PLAN.md:78-81)
  First-non-None-wins removes order dependence only when one reception is blank. If garden and infant provide different non-null contacts, the chosen value still depends on input order and the conflict is silent. The planned two-order test deliberately excludes this case, despite the plan identifying iteration-order-dependent contacts as a risk.
  Recommendation: Define semantics for unequal non-null values—preferably reject or visibly report the conflict, or use an explicit reception priority—and test conflicting values in both input orders.
- [medium] Final validation marks the epic done before its merge criterion can be true (docs/artifacts/plans/scraper-contact-metadata/tasks/TASK-005-final-validation.md:61-62)
  TASK-005 instructs the feature branch to tick epic-level acceptance criteria and promote the epic to Done, but the epic-level criterion requires every phase to be merged. TASK-005 itself has a suggested commit, so its branch cannot truthfully satisfy that criterion while executing these steps.
  Recommendation: Move epic-level completion and EPICS.md promotion to a post-merge follow-up, leaving only phase evidence/status preparation in TASK-005.

Next steps:
- Add the missing final pipeline projection and serialization assertions.
- Redesign final validation around the exact artifact promoted to R2, including compatibility and rollback checks.
- Define deterministic behavior for conflicting non-null contacts.
- Move epic completion to a post-merge step.

## Triage

<!--
Rows 1–5 are Codex's findings. Row 6 is the part of Codex #2 that is deferred
rather than applied. Rows 7–8 are validator-found follow-ups to the two
rejects, so the rejected findings still leave the plan text more precise.
-->

| # | Finding | Severity | Verdict | Rationale | Applied to |
|---|---------|----------|---------|-----------|------------|
| 1 | TASK-003 omits the final `MergedInstitution` → `Institution` rebuild at the end of `coalesce_institutions` | med | apply | `coalesce_institutions` has three contact-carrying sites (seed, merge block, and the return comprehension that rebuilds every field by name); the planned two-reception test would catch the omission, but the task claims to enumerate the edits and misses one | TASK-003 |
| 2 | Local validation and the R2 write are different scrapes; the deployed-backend precondition is not executable; no rollback path | med | apply | Grounded fixes applied: executable precondition (`alembic_version` = `0009` on the Railway Postgres, `/api/health` 200), post-ingest re-verification of the artifact that was actually published, a rollback line via the timestamped `snapshots/varna/<ts>.json` objects that `put_snapshot` already keeps, and a Risk naming the Sunday crons. The "promote a validated file" mechanism is new scraper capability — deferred as row 6 | PLAN.md:Risks, TASK-005 |
| 3 | AC #4 (`null`, never `""`) has no serialisation-level test or final check | med | apply | `model_dump_json(indent=2)` in `__main__.py` and `r2.py` has no `exclude_none` today, but nothing pins that; added a round-trip serialisation test to TASK-003 and a key-presence jq to TASK-005 and RESEARCH.md | PLAN.md:Acceptance Criteria, TASK-003, TASK-005, RESEARCH.md:Useful Commands |
| 4 | First-non-`None`-wins is order-dependent when both receptions carry different non-null values | med | reject | Contradicts the explicit Decision "Coalesce contacts first-non-`None`-wins, exactly like `address`"; `address` has the same semantics today, and the order is deterministic — `_run_dg_branch` emits rows in `PIPELINE_RECEPTIONS` order (`garden` before `infant`), so `garden` wins. Raising on conflict would make a cosmetic source discrepancy abort the whole snapshot | — |
| 5 | TASK-005 ticks epic-level criteria and promotes `EPICS.md` to Done before the merge that makes them true | low | reject | This is the documented lifecycle in `docs/artifacts/epics/EPICS.md` ("the plan's final-validation task ticks the phase + epic-level acceptance criteria and updates this table"); the tick rides the PR and becomes true at merge, and `archive-plan` handles the post-merge Linear side | — |
| 6 | (from #2) A `promote` command that uploads an already-validated local snapshot to R2 instead of re-scraping | low | defer | New scraper CLI capability, not part of emitting contact fields; worth a follow-up so validation and publication stop being separate scrapes | — |
| 7 | (validator) The coalescing Decision does not say the first-non-`None` winner is deterministic | low | apply | Added the `PIPELINE_RECEPTIONS` ordering fact so the reject in row 4 is grounded in the plan text itself | PLAN.md:Decisions |
| 8 | (validator) The epic-tick bullet in TASK-005 does not say the tick becomes true at merge | low | apply | One clause added, pointing at the `EPICS.md` workflow | TASK-005 |
