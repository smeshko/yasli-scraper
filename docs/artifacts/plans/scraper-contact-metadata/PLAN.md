# Plan: Emit contact metadata in the snapshot

Status: in-progress
Branch: feature/yas-10-scraper-contact-metadata
Risk: medium
Epic: 01 — Snapshot contact metadata ([epic](../../epics/01-contact-metadata.md))
Phase: 1.1 — Emit contact metadata in the snapshot
Linear: YAS-10
Created: 2026-08-17

## Goal

The scraper carries the phone, e-mail, director and website it already fetches
through to snapshot v2 instead of discarding them.

## Scope

- `source.py`: keep `TEL`, `EMAIL`, `NAME_D` and `WEBSITE` on
  `InstitutionMetadata` alongside `ADDRESS`.
- `source_jasla.py`: the same four on `JaslaRecord`.
- `models.py`: four optional fields on `Institution`, mirroring the backend
  contract landed in backend phase 1.1 exactly.
- `pipeline.py`: thread them through `_run_dg_branch`,
  `_institutions_from_jasla`, `MergedInstitution` and `coalesce_institutions`.
- Normalisation on the way in: collapse whitespace (tabs and runs of spaces
  become one space) and strip the `\r\r\n` tails on `WEBSITE`. Slashes and
  every other separator inside `TEL` are preserved — see Decisions.
- Regenerate `schemas/snapshot.v2.schema.json` and update the field table in
  `schemas/README.md`.

## Out of Scope

- Bumping `schema_version`. The fields are additive and optional; it stays `2`.
- Inventing a canonical phone format. Multiple numbers are kept as the source
  gives them, slashes included — only whitespace is collapsed.
- Anything from `/lv/api/free-places` or `/lv/api/new-public-last-rating`.
- The backend side of the contract — backend phase 1.1, which **must be deployed**
  before this phase ships.

## Preconditions

backend phase 1.1 is merged **and deployed**. Both sides validate with
`extra="forbid"`, so a scraper emitting fields a running backend does not know
makes ingest reject the whole snapshot. Verify against the deployed API before
the first `sc-refresh` writes to R2.

## Research Summary

See [RESEARCH.md](./RESEARCH.md). The short version:

- Coverage measured 2026-08-17: `TEL`, `EMAIL` and `NAME_D` are non-empty for
  **all 95** source rows across the four receptions. `WEBSITE` is populated for
  the 12 `pg` rows and empty everywhere else.
- The values carry real formatting noise: slash- and tab-separated multiples in
  `TEL`, `\r\r\n` tails on `WEBSITE`.
- The scraper already calls `/lv/api/childhood` for all three DG receptions and
  `newkg.uslugi.io` for `jasla` — this phase adds no requests.
- `coalesce_institutions` merges the `garden` and `infant` rows for the same
  kindergarten. Contacts have to coalesce there the way `address` already does,
  or a kindergarten's phone depends on iteration order.

## Decisions

- **Normalise in the source clients, not the pipeline.** `_normalise_address`
  already sets this precedent in both `source.py` and `source_jasla.py`; the
  pipeline stays a pure assembler. It also means the noisy-input tests live next
  to the parsing code.
- **One shared normaliser per field shape, not one per field.** `phone`,
  `email` and `director` need whitespace collapsing only; `website` additionally
  needs its `\r\r\n` tail stripped. Two helpers, not four.
- **Phone normalisation is whitespace-only.** Tabs and runs of spaces collapse
  to one space; slashes, commas and every other separator in `TEL` stay
  verbatim. The epic's "strip the stray tab and slash-separated phone forms"
  means *handle* those forms, not remove the slashes — removing them would be
  exactly the canonical format the Out of Scope section rules out.
- **Empty becomes `None`, never `""`.** The backend contract rejects the empty
  string outright (backend phase 1.1), so emitting one would fail ingest. This mirrors
  what `_normalise_address` already does.
- **Coalesce contacts first-non-`None`-wins**, exactly like `address` in
  `coalesce_institutions`. The `garden` and `infant` rows for one kindergarten
  carry the same values in practice, so the rule only matters when one reception
  has a blank. On a genuine conflict the winner is deterministic, not
  iteration luck: `_run_dg_branch` emits rows in `PIPELINE_RECEPTIONS` order
  (`garden` before `infant`), so `garden` wins — the same rule `address`
  already lives under. Raising on conflict, as `district_code` does, would let
  a cosmetic source discrepancy abort the whole snapshot.
- **No `schema_version` bump** — matching backend phase 1.1's decision. The two schemas
  re-converge in this phase, and their only permitted difference stays the
  pre-existing `minItems`.

## Risks

- **Shipping before the backend is deployed breaks ingest entirely**, not
  partially — `extra="forbid"` rejects the whole snapshot. Mitigated by the
  Preconditions check above and by the ordering note in backend phase 1.1's PR.
- **The live `sc-refresh` acceptance check depends on the source portal.** If
  `dg.uslugi.io` is unreachable the acceptance criteria cannot be demonstrated;
  say so rather than ticking on unit tests alone.
- **Silent field loss in coalescing.** A kindergarten appears in two receptions;
  if `MergedInstitution` gains the fields but `coalesce_institutions` forgets to
  merge them, the tests still pass on single-reception fixtures. The task
  requires a two-reception fixture specifically for this.
- **`String(128)` on the backend's `phone` column.** A pathological multi-number
  `TEL` could overflow it. The live-refresh acceptance check records the longest
  observed value so this is a measured fact, not an assumption.
- **The validated local scrape and the published R2 scrape are different
  runs.** `sc-refresh` re-scrapes instead of uploading the checked file, and the
  Sunday crons (scraper 01:00 UTC, backend ingest 02:00 UTC) consume whatever
  `latest.json` holds. Mitigated in TASK-005: a deployed-revision check before
  anything is written, validation of the published `latest.json` before
  anything ingests it, a one-shot run of the deployed ingest cron, and a
  rollback path through the timestamped `snapshots/varna/<ts>.json` objects
  `put_snapshot` already keeps. A rejected snapshot leaves the database
  untouched (ingest is transactional and exits 3).
  A "promote a validated file" command is a deferred follow-up, not this phase.

## Acceptance Criteria

- [ ] A live `just sc-refresh` produces a snapshot where all 77 institutions
      carry a non-null `phone`, `email` and `director`, and the 12 preschools
      carry a non-null `website` (counts as measured 2026-08-17 and as
      `sc-snapshot-check` asserts; a different roster means the portal changed —
      stop and re-measure, do not tick)
- [ ] `schema_version` is still `2` and the committed schema artifact matches
      the models (`tests/test_schema_artifact.py` passes)
- [ ] None of the emitted `phone`, `email`, `director`, `website` or `address`
      values contains a leading/trailing space, a tab, or a `\r`; `street` and
      `number` keep their existing verbatim contract and are not asserted
- [ ] Institutions whose source row omits a field serialise it as `null` — the
      key is present with a null value, never `""` and never omitted
- [ ] The regenerated `schemas/snapshot.v2.schema.json` differs from the
      backend's `tests/snapshot_contract/fixtures/snapshot.v2.schema.json` only
      by `"minItems": 1`
- [ ] The longest observed `phone` value is recorded and fits the backend's
      `String(128)` column
- [ ] `just sc-test` and `just sc-lint` pass

## Tasks

Task state lives here. Tasks are appended by `scripts/add_task.py` and
`scripts/add_final_task.py`. Update the checkboxes as work progresses.

- [x] TASK-001: Carry contacts through the dg.uslugi.io metadata client
- [x] TASK-002: Carry contacts through the jasla nursery client
- [ ] TASK-003: Add contact fields to the snapshot models and pipeline (depends on TASK-001, TASK-002)
- [ ] TASK-004: Regenerate the v2 schema artifact and field table (depends on TASK-003)
- [ ] TASK-005: Final Validation
