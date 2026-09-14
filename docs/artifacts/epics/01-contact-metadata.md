# Epic 01 — Snapshot contact metadata

Status: planned
Created: 2026-08-17
Depends on: backend epic 01, phase 1.1 (merged **and deployed**)
Project: none
Linear: none
Milestone: none

## Overview

The source portal's `/lv/api/childhood` response carries phone, e-mail, director
and website for all 95 rows, and the scraper already fetches it — but keeps only
`ADDRESS`. This epic carries those fields through to snapshot v2 so the backend
can store them and, later, a detail page can show them.

Cross-repo ordering is load-bearing: both the scraper and the backend validate
the snapshot with `extra="forbid"`, so the backend must accept the new fields
([backend epic 01](../../../../backend/docs/artifacts/epics/01-institution-data-foundation.md),
phase 1.1) **before** this epic's phase starts emitting them, or ingest rejects
the snapshot outright.

## Architecture references

- [INSTITUTION_DETAIL_MAP_RESEARCH.md](../../../../openspec/docs/INSTITUTION_DETAIL_MAP_RESEARCH.md) — field coverage per reception (§1) and the whitespace/tab/slash quirks the normaliser must handle
- [ARCHITECTURE.md](../../../../openspec/docs/ARCHITECTURE.md) — the scraper → R2 → ingest → API pipeline
- [NURSERY_RESEARCH.md](../../../../openspec/docs/NURSERY_RESEARCH.md) — the `jasla` source shape

## Dependencies

- **backend epic 01, phase 1.1** — merged and deployed (done).

## Out of scope

- Storing or exposing the fields — backend epic 01.
- Coordinates and branches — backend epic 01, phase 1.2.
- Bumping `schema_version`. The fields are additive and optional; the contract stays at v2.

## Phase 1.1 — Emit contact metadata in the snapshot

**Plan**: [scraper-contact-metadata](../plans/scraper-contact-metadata/PLAN.md) · status: planned

**Linear**: none

**Goal**: The scraper carries the contact fields it already fetches through to snapshot v2 instead of discarding them.

### What to build

- Extend `InstitutionMetadata` in `src/yasli_scraper/source.py` to keep `TEL`, `EMAIL`, `NAME_D`, `WEBSITE` alongside `ADDRESS`, and the equivalent in `source_jasla.py`.
- Add the four optional fields to `Institution` in `src/yasli_scraper/models.py` and thread them through `pipeline.py` (`_run_dg_branch` and `_institutions_from_jasla`).
- Normalise on the way in: collapse whitespace, strip the stray tab and slash-separated phone forms, strip the `\r\r\n` tails on `WEBSITE`. Keep multiple phone numbers as the source gives them — do not invent a canonical format.
- Regenerate `schemas/snapshot.v2.schema.json` via `python -m yasli_scraper.tools.gen_schema` (the artifact test fails otherwise). **No `schema_version` bump** — the fields are additive and optional.
- Update `schemas/README.md`'s field table.

### Acceptance criteria

- [ ] A live `just sc-refresh` produces a snapshot where all 77 institutions carry `phone`, `email` and `director`, and the 12 preschools carry `website`
- [ ] `schema_version` is still `2` and the committed schema artifact matches the models
- [ ] Whitespace, tab and slash quirks documented in research §1 are handled — no field contains a leading/trailing space or a `\r`
- [ ] Institutions whose source row omits a field serialise it as `null`, not `""`
- [ ] `just sc-test` and `just sc-lint` pass

### Validation

Run `just sc-refresh` and then `just be-ingest`, and show a query listing five institutions with their phone, e-mail, director and website. This is also the end-to-end proof for backend epic 01, phase 1.1.

---

<!-- PHASES -->

## Epic-level acceptance criteria

- [ ] Every phase merged and its acceptance criteria met
- [ ] The production snapshot carries contact metadata and the backend ingests it without error
- [ ] Status row in [EPICS.md](./EPICS.md) updated to `Done`
