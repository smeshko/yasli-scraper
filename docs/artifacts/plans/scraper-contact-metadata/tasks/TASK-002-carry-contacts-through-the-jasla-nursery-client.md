# TASK-002: Carry contacts through the jasla nursery client

Depends on: None
Suggested commit: `feat(jasla): keep contact fields from the nursery payload`

## Goal

`JaslaRecord` carries normalised `phone`, `email`, `director` and `website`
from the `newkg.uslugi.io` payload.

## Files

- `src/yasli_scraper/source_jasla.py` — four fields on `JaslaRecord`, populated
  in `parse_jasla_payload` via the existing `_collapse_ws`
- `tests/test_source_jasla.py` — the cases below

## Acceptance

- [ ] A jasla record with `TEL`, `EMAIL` and `NAME_D` produces a `JaslaRecord`
      carrying each, whitespace-collapsed
- [ ] `WEBSITE` is blank or absent in every measured jasla row (0/12 non-empty;
      key presence unverified) — an absent key and a blank value both yield
      `None` and neither raises
- [ ] A whitespace-only, empty or explicit-`null` value yields `None`, never `""`
- [ ] The existing `DZ_ID` / `DZ_NAME` / `RAJON` failure modes are unchanged —
      contacts are optional and never make a record invalid
- [ ] Name normalisation still applies to `DZ_NAME` only; contact values are not
      passed through `_SMART_QUOTES`

Evidence: `uv run pytest tests/test_source_jasla.py -v` output, with a fixture
captured verbatim from the live `jasla` reception.

## Steps

### RED
- [ ] Extend the payload fixtures with contact keys; add a record missing every
      contact key; add one with an explicit JSON `null` in every contact key;
      add one with whitespace-only values

### GREEN
- [ ] Add the four fields to `JaslaRecord`
- [ ] Populate them in `parse_jasla_payload` using a `_normalise_optional_text`
      helper built on the existing `_collapse_ws`, with `_normalise_address`'s
      `if value is None: return None` guard in front of the `str()` call — do
      **not** use `_required_text`, which raises on empty

### REFACTOR
- [ ] Check whether `_normalise_address` and the new optional-text helper are
      now the same function; collapse them if so

## Notes

This file already has its own `_collapse_ws` and `_normalise_address`, separate
from `source.py`'s copies. Do not try to unify them across the two modules in
this task — they are deliberately independent clients, and the shared-helper
question is bigger than this plan.

Contacts must not go through `_normalise_name` / `_SMART_QUOTES`. That
transform exists to tidy the quoting in institution titles like
`ДГ№4 „Теменужка“`; applying it to an e-mail or a phone number would be a
silent corruption.
