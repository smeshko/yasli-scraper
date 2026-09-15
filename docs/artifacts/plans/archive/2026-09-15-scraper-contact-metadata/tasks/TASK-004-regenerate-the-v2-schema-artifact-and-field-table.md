# TASK-004: Regenerate the v2 schema artifact and field table

Depends on: TASK-003
Suggested commit: `chore(schemas): regenerate v2 artifact with contact fields`

## Goal

The committed schema artifact matches the models again, the field table
documents the four new fields, and the artifact re-converges with the backend's
vendored fixture.

## Files

- `schemas/snapshot.v2.schema.json` — regenerated, never hand-edited
- `schemas/README.md` — four rows added to the `Institution` field table
- `schemas/examples/varna-stub.json` — left alone unless the added rows make it
  misleading; the fields are optional, so a stub without them is still valid

## Acceptance

- [ ] `uv run python -m yasli_scraper.tools.gen_schema` produces no diff on a
      second run (idempotent) and `tests/test_schema_artifact.py` passes
- [ ] `schema_version` is still `2` in the artifact and the README envelope table
- [ ] The `Institution` table in `schemas/README.md` documents all four fields,
      including that `website` is populated only for `preschool` rows and that
      `phone` may hold several numbers verbatim
- [ ] `diff schemas/snapshot.v2.schema.json ../backend/tests/snapshot_contract/fixtures/snapshot.v2.schema.json`
      shows **only** the `"minItems": 1` line
- [ ] No `"minLength"` appears on any of the four new properties

Evidence: the `gen_schema` output, the `diff` against the backend fixture
showing the single expected line, and `uv run pytest tests/test_schema_artifact.py -v`.

## Steps

### RED
- [ ] Confirm `tests/test_schema_artifact.py` fails before regenerating — that
      failure is the proof the model change actually reached the schema

### GREEN
- [ ] Run `uv run python -m yasli_scraper.tools.gen_schema`
- [ ] Add the four README rows, matching the existing table's tone and the
      measured coverage from `RESEARCH.md`

### REFACTOR
- [ ] Re-read the README's "Invariants" section and add a line if the contact
      fields introduce one worth stating — specifically that they are
      normalised (whitespace collapsed) unlike `street`/`number`, which are
      explicitly preserved verbatim

## Notes

The `minItems` divergence is expected and load-bearing: the scraper refuses to
emit an empty snapshot (`Field(min_length=1)`), while the backend tolerates
ingesting one. Do not "fix" it in either direction — if the diff shows anything
else, the two models have genuinely drifted and that is the bug this check
exists to catch.

The README's `Institution` table is the human-facing contract for any
non-Python consumer. Say what the fields mean, not just their types: `director`
is a person's name (`NAME_D`), and `phone` is free-form because the source
packs multiple numbers into one cell.
