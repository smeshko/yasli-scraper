# Adversarial Validation — Round 3

**Run:** 2026-09-15 (UTC)
**Plan:** scraper-contact-metadata
**Status at start:** draft
**Reviewer:** Codex (`/codex-local:adversarial-review --wait --scope working-tree`)
**Prior rounds in scope:** validation/round-1.md, validation/round-2.md

## Codex output

<!-- Paste /codex:adversarial-review stdout verbatim below this line. Do not edit. -->

# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

Do not ship the plan yet. Round 2 fixed the pipeline projection and serialization-test gaps, but its production-safety fix remains incomplete: compatibility is not proven before publication, published-artifact validation is partial, and a required noise-check command silently succeeds without checking anything on this workspace.

Findings:
- [high] The deployment precondition does not prove contract compatibility (docs/artifacts/plans/scraper-contact-metadata/tasks/TASK-005-final-validation.md:25-32)
  Migration 0009 only proves the contact columns exist, while `/api/health` executes only `SELECT 1`. An older deployed backend using `extra="forbid"` can therefore pass both checks and still reject snapshots containing the new fields. The first behavioral test occurs only after `sc-refresh` overwrites `latest.json`; moreover, `just be-ingest` runs backend code from the local checkout, not necessarily the deployed Railway ingest revision.
  Recommendation: Before publishing, verify the deployed API and ingest service revision includes the contact contract, or run a non-mutating behavioral validation through the deployed ingest artifact. Check column presence directly rather than requiring the database head to equal exactly 0009.
- [high] Round 2 still validates the published artifact too late and incompletely (docs/artifacts/plans/scraper-contact-metadata/tasks/TASK-005-final-validation.md:52-59)
  The prescribed order publishes and ingests the second scrape before validating it. The SQL alternative then checks only null counts and phone length; it does not verify whitespace, JSON key presence, schema version, or roster counts. It also scans retained historical institutions rather than rows belonging to the ingested snapshot, so it is not evidence about `latest.json`. This leaves PLAN acceptance criteria 3 and 4 proven only against the different local scrape. Deferring exact-file promotion is unsafe unless consumption is controlled and the uploaded object is fully validated before ingest.
  Recommendation: Prefer uploading the exact validated local payload. Otherwise suspend scheduled consumption, download `latest.json` immediately after upload, run every schema, coverage, noise, key-presence, count, and length assertion on that object, and only then trigger ingest.
- [high] The required noise check silently does no validation on this workspace (docs/artifacts/plans/scraper-contact-metadata/RESEARCH.md:106-108)
  The command referenced by TASK-005 uses `grep -P`, but this workspace's BSD grep rejects `-P` with exit 2. Because the command is piped into `head` without `pipefail`, the overall pipeline exits successfully with no output—the same appearance as clean data. Dirty contact values can therefore satisfy the release gate undetected.
  Recommendation: Replace the pipeline with a portable `jq -e` assertion that fails when any selected value violates the invariant, or use an available regex tool and explicitly preserve its failure status.
- [high] TASK-001 can serialize JSON null as the literal string "None" (docs/artifacts/plans/scraper-contact-metadata/tasks/TASK-001-carry-contacts-through-the-dg-uslugi-io-metadata-client.md:35-46)
  The RED fixtures cover absent and whitespace-only contacts but omit the explicitly required JSON-null case. The GREEN instruction then prescribes `str(value).split()` without the existing `_normalise_address` guard `if value is None: return None`, despite calling it the helper's exact body. Following the task converts null to the non-empty string `"None"`, which passes downstream non-empty validation and becomes user-visible contact data.
  Recommendation: Require the helper to return `None` before string conversion when its input is `None`, correct the pseudocode variable, and add an explicit-null fixture to the RED test list.
- [medium] The roster-change policy contradicts a mandatory validation recipe (docs/artifacts/plans/scraper-contact-metadata/tasks/TASK-005-final-validation.md:33-38)
  TASK-005 says a changed roster is informational rather than a failure, yet it requires `sc-snapshot-check` to pass. The actual recipe hard-fails unless nursery and preschool counts are both exactly 12. A legitimate portal roster change therefore blocks completion despite the edited acceptance rule.
  Recommendation: Update the recipe as part of this plan to validate invariants without fixed roster counts, or replace this task step with commands whose pass/fail semantics match the stated acceptance criterion.
- [medium] Rejected conflict finding still leaves silent contact corruption unobservable (docs/artifacts/plans/scraper-contact-metadata/PLAN.md:78-85)
  Adding a fixed garden-before-infant priority removes iteration randomness, but it does not address the dangerous part of the rejected finding: unequal non-null phone, email, or director values are silently discarded. Calling every such discrepancy cosmetic is unsupported; it can represent a real contact update in only one reception. The chosen first-wins policy can remain, but the absence of detection makes source drift and stale published contacts hard to diagnose.
  Recommendation: Keep the explicit priority if desired, but emit a structured warning or conflict count whenever both non-null values differ, and test that behavior.

Next steps:
- Repair TASK-005 so compatibility and the exact published object are verified before ingest.
- Replace the broken noise check and reconcile fixed-count validation with the roster-change policy.
- Correct TASK-001's null-normalization instructions and add the missing explicit-null test.
- Add observability for conflicting non-null contact values.

## Triage

<!--
Round 3 still produced apply rows. Per the shared protocol no fourth round was
run; the unambiguous defects were applied and the structural question (continue
patching, or step back to create-plan) plus row 6 were put to the user.
-->

| # | Finding | Severity | Verdict | Rationale | Applied to |
|---|---------|----------|---------|-----------|------------|
| 1 | The precondition proves the contact columns exist, not that the deployed code carries the contract; `just be-ingest` runs the checkout's code, not the Railway ingest revision | high | apply | Confirmed: backend `docs/DEPLOYMENT.md` has `alembic upgrade head` run by hand before deploys, so head `0009` is a proxy. Applied a deployed-commit check (both Railway services built at or after backend phase 1.1's merge) before writing, and a one-shot run of the Railway `backend-ingest` cron after publishing so the deployed revision is what accepts the artifact | TASK-005, PLAN.md:Risks |
| 2 | The published artifact is validated too late and only partially; the SQL scans historical rows | high | apply | Reordered: after `sc-refresh`, download `snapshots/varna/latest.json` and run `sc-snapshot-check` plus every coverage, noise, key-presence and length assertion on that object before any ingest; SQL scoped with `last_seen_at`, the column `_count_disappeared` already uses. Exact-file promotion stays deferred (round-2 #6); the crons fire on Sundays, so a weekday run leaves days for a rollback | TASK-005 |
| 3 | The noise check (`grep -P … \| head`) silently passes on BSD grep | med | apply | Premise is environment-dependent — this session's `grep` is a ugrep shim where `-P` works, stock macOS grep would fail — but the shape is wrong regardless: an eyeball check whose exit status `head` masks. Replaced with a `jq -e` assertion verified to exit 0 on clean data and 1 (listing offenders) on tab, trailing-space and `\r` samples | RESEARCH.md:Useful Commands, TASK-005 |
| 4 | TASK-001's GREEN pseudo-code drops `_normalise_address`'s `None` guard, so an explicit JSON `null` becomes the string `"None"` | high | apply | Real: `str(None).split()` is `["None"]`, which passes every downstream validator. The acceptance already demanded `null → None` but the RED list had no explicit-null fixture. Fixed the pseudo-code and added the fixture to TASK-001 and TASK-002 | TASK-001, TASK-002 |
| 5 | "A roster change is not a failure" contradicts `sc-snapshot-check`, which hard-fails unless nurseries and preschools are exactly 12 | med | apply | Self-inflicted by round-1 #7. Restored the fixed counts as the pass bar — they are the epic's own wording and what the parent-repo recipe asserts — and made a mismatch a stop-and-investigate condition rather than something to tick past | PLAN.md:Acceptance Criteria, TASK-005 |
| 6 | Conflicting non-null contacts between `garden` and `infant` are discarded silently; wants a structured warning | med | defer | Does not contradict the Decision (first-wins stays) and would match the existing `address_extraction_failed` logging pattern, but it is scope the author did not ask for. Filed as a follow-up and surfaced to the user alongside the round-3 stop; pull it into this plan if wanted | — |
