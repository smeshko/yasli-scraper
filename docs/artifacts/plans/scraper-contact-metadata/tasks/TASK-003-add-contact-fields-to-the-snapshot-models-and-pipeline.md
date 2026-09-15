# TASK-003: Add contact fields to the snapshot models and pipeline

Depends on: TASK-001, TASK-002
Suggested commit: `feat(models): emit contact fields in snapshot v2`

## Goal

The four fields reach the serialised snapshot for both branches of the
pipeline, and survive the `garden`/`infant` coalescing intact.

## Files

- `src/yasli_scraper/models.py` — `phone`, `email`, `director`, `website` as
  `str | None = None` on `Institution`; widen `_address_non_empty` to cover all
  five nullable strings. **Must match the backend's phase-1.1 model exactly** —
  mirror `_optional_strings_non_empty(cls, value, info: ValidationInfo)` from
  `../backend/src/yasli/snapshot_contract/models.py`, whose message is
  `f"{info.field_name} must be non-empty or null"`, so the existing
  `match="address"` test in `tests/test_models.py` keeps passing
- `src/yasli_scraper/pipeline.py` — five edits: the `Institution(...)`
  construction in `_run_dg_branch`; the one in `_institutions_from_jasla`; the
  `MergedInstitution` dataclass; and all three sites in `coalesce_institutions`
  — the seed `MergedInstitution(...)`, the merge block, and the final
  `Institution(...)` rebuild in the return comprehension. That last one lists
  every field by name, so forgetting it silently resets every contact to `None`
- `tests/test_models.py` — contract-level validation cases
- `tests/test_pipeline.py` — the coalescing and end-to-end cases below

## Acceptance

- [ ] An `Institution` built without contacts validates with all four `None`
- [ ] `Institution(phone="")` raises `ValidationError`; same for `email`,
      `director`, `website` and the pre-existing `address`
- [ ] A DG institution's contacts reach the built `Institution` from its
      metadata row
- [ ] A jasla nursery's contacts reach the built `Institution`
- [ ] **A kindergarten present in both `garden` and `infant` keeps its contacts
      after coalescing**, and when one reception has a blank field and the other
      does not, the non-`None` value wins regardless of input order
- [ ] The full pipeline test produces a snapshot whose institutions carry the
      fields, with `schema_version` still `2`
- [ ] `json.loads(snapshot.model_dump_json())` for an institution with no
      contacts contains all four keys with the value `null` — present, not
      omitted (this is the serialisation the CLI and `r2.put_snapshot` use, and
      it guards against a future `exclude_none`)

Evidence: `uv run pytest tests/test_models.py tests/test_pipeline.py -v`,
including the two-reception coalescing test run in both input orders.

## Steps

### RED
- [ ] Add the model validation tests
- [ ] Add a `coalesce_institutions` test with the same `(external_id, kind)`
      appearing twice, one row blank per field, asserted in both orders
- [ ] Extend the existing end-to-end pipeline test's fixtures with contact keys
- [ ] Add a serialisation test: a `Snapshot` with one contact-less institution,
      round-tripped through `model_dump_json()`, has the four keys present and
      `None`

### GREEN
- [ ] Add the fields to `Institution`, ordered after `address` so the generated
      schema key order matches the backend's
- [ ] Replace `_address_non_empty` with the backend's `_optional_strings_non_empty`
      — `@field_validator("address", "phone", "email", "director", "website")`
      taking `info: ValidationInfo`
- [ ] Thread the fields through both construction sites
- [ ] Add the fields to `MergedInstitution` and merge them first-non-`None`-wins,
      alongside the existing `if bucket.address is None and ...` line
- [ ] Copy the four fields into the final `Institution(...)` rebuild at the end
      of `coalesce_institutions` — the comprehension names every field, so a
      missing one falls back to the model default

### REFACTOR
- [ ] The merge block is now five near-identical `if bucket.X is None` lines —
      collapse to a loop over the field names if that reads better than the
      explicit form. Judgement call; keep whichever is clearer in context

## Notes

The coalescing test is the one that matters. A single-reception fixture passes
even if `coalesce_institutions` drops the fields entirely, because the seed half
of the function copies them and the merge half is never exercised. Assert in
both input orders so a "last wins" bug cannot hide behind fixture ordering.

Field order in the model is not cosmetic: `sort_keys=True` in `gen_schema.py`
sorts the JSON Schema properties, so key order does not affect the artifact —
but keeping the two repos' model files visually aligned makes the next contract
change diffable by eye.

Do not add `Field(min_length=1)` to the new fields. The backend deliberately
avoided it in backend phase 1.1; adding it here would emit `"minLength": 1` and break
the schema convergence check in TASK-004.
