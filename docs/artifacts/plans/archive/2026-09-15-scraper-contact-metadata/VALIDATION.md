# Validation Summary — scraper-contact-metadata

**Rounds:** 3
**Plan status at validation:** draft
**Run on:** 2026-09-15
**Reviewer:** Codex (`/codex-local:adversarial-review`, working-tree scope) in every round; validator-found rows are marked "(validator)" in the round files.

## Rounds

| Round | Findings | Applied | Deferred | Rejected |
|-------|----------|---------|----------|----------|
| 1     | 10 (4 Codex + 6 validator) | 9 | 1 | 0 |
| 2     | 8 (5 Codex + 1 spin-off + 2 validator) | 5 | 1 | 2 |
| 3     | 6 | 5 | 1 | 0 |

Round 3 still produced apply rows. Per the shared protocol no fourth round was
run: the unambiguous defects were applied and the structural question
(continue patching vs. step back to `create-plan`) was put to the author.

## Applied

### Round 1
- PLAN.md:Scope, Out of Scope, Decisions — phone rule made singular: whitespace-only, slashes preserved; new explicit Decision (round-1 #1)
- RESEARCH.md:Useful Commands, TASK-005 — note that every `just` recipe lives in the parent `yasli/justfile` and `just` walks up to it (round-1 #2)
- TASK-005 — re-checks the schema artifact (`gen_schema` idempotent + `test_schema_artifact.py`) and the backend-fixture diff (`minItems` only) as explicit steps (round-1 #3)
- PLAN.md:Acceptance Criteria, TASK-005, RESEARCH.md — noise criterion scoped to `phone`/`email`/`director`/`website`/`address`; `street`/`number` keep their verbatim contract (round-1 #4)
- TASK-005 — epic-update section uses `link_plan.py` (epics moved into this repo in 35e8b97); stale parent-repo prose removed (round-1 #5)
- TASK-005 — dead "tick backend phase 1.1's criterion" step replaced with the fact that all five are already ticked (round-1 #6)
- PLAN.md:Acceptance Criteria, TASK-005 — coverage counts reworded (later re-tightened by round-3 #5) (round-1 #7)
- TASK-003 — names the backend validator to mirror, `_optional_strings_non_empty(cls, value, info: ValidationInfo)` (round-1 #8)
- TASK-002 — `WEBSITE` acceptance covers absent and blank alike (round-1 #9)

### Round 2
- TASK-003 — the third contact-carrying site in `coalesce_institutions` (the final `Institution(...)` rebuild) added to Files and Steps (round-2 #1)
- PLAN.md:Risks, TASK-005 — validated-vs-published-scrape risk named; precondition made executable; rollback path via the timestamped R2 objects (round-2 #2)
- PLAN.md:Acceptance Criteria, TASK-003, TASK-005, RESEARCH.md — null keys must be present, not omitted: serialisation test in TASK-003, key-presence `jq -e` in TASK-005 (round-2 #3)
- PLAN.md:Decisions — first-non-`None` winner stated as deterministic (`garden` precedes `infant` in `PIPELINE_RECEPTIONS`) (round-2 #7)
- TASK-005 — epic tick noted as riding the PR and becoming true at merge (round-2 #8)

### Round 3
- TASK-005, PLAN.md:Risks — precondition now checks the deployed Railway commit (migrations are run by hand, so head `0009` alone proves columns, not code); a one-shot run of the Railway `backend-ingest` cron proves the deployed revision accepts the artifact (round-3 #1)
- TASK-005 — `latest.json` is downloaded and fully validated (`sc-snapshot-check`, coverage, noise, key presence, phone length) **before** any ingest; DB cross-check scoped with `last_seen_at` (round-3 #2)
- RESEARCH.md:Useful Commands, TASK-005 — eyeball `grep -P … | head` replaced by a `jq -e` assertion verified to exit 0 clean / 1 dirty with offenders listed (round-3 #3)
- TASK-001, TASK-002 — `None` guard restored in the normaliser pseudo-code (`str(None)` would ship as the string `"None"`); explicit-`null` fixtures added to RED (round-3 #4)
- PLAN.md:Acceptance Criteria, TASK-005 — fixed 77/12 counts restored as the pass bar (the epic's wording and what `sc-snapshot-check` asserts); a mismatch is stop-and-re-measure, not tick (round-3 #5)

## Deferred

- (round-1 #10) `sc-snapshot-check` asserts nothing about contacts; TASK-005 carries ad-hoc `jq` instead — the recipe lives in the parent `yasli/justfile`, outside this PR's reach. Filed as **YAS-16**.
- (round-2 #6) A `promote` command that uploads an already-validated local snapshot to R2 instead of re-scraping — new scraper capability, not part of emitting contact fields. Filed as **YAS-17**.
- (round-3 #6) Emit a structured warning when `garden` and `infant` carry different non-null contact values — compatible with the first-wins Decision and the existing `address_extraction_failed` log pattern, but scope the author did not ask for. Filed as **YAS-18**; pull into this plan if wanted.

## Rejected

- (round-2 #4) First-non-`None`-wins is order-dependent for differing non-null values — contradicts the explicit Decision "Coalesce contacts first-non-`None`-wins, exactly like `address`"; `address` has the same semantics today and the order is deterministic (`garden` before `infant`). Raising on conflict would let a cosmetic source discrepancy abort the whole snapshot. The observability half of the concern is YAS-18.
- (round-2 #5) TASK-005 ticks epic-level criteria and promotes `EPICS.md` to Done before the merge that makes them true — this is the documented lifecycle in `docs/artifacts/epics/EPICS.md`; the tick rides the PR and becomes true at merge, and `archive-plan` handles the post-merge Linear side.

## Interpretations confirmed by the author (2026-09-15)

Codex cannot see the conversation that produced this plan; two applied edits
interpret the epic's wording. Both were confirmed, as was proceeding to
`implement-plan` after round 3 and leaving YAS-18 as a backlog follow-up:

- "strip the stray tab and slash-separated phone forms" was read as *handle*
  those forms — tabs collapse to a space, slashes stay — consistent with the
  epic's "do not invent a canonical format" and the plan's own TASK-001
  acceptance.
- "no field contains a leading/trailing space or a `\r`" was read as the four
  contact fields plus `address`, since the §1 quirks are contact-field quirks
  and `street`/`number` are documented as verbatim.
