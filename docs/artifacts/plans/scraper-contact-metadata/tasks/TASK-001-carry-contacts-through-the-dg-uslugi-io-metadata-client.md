# TASK-001: Carry contacts through the dg.uslugi.io metadata client

Depends on: None
Suggested commit: `feat(source): keep contact fields from /lv/api/childhood`

## Goal

`InstitutionMetadata` carries normalised `phone`, `email`, `director` and
`website` from the `/lv/api/childhood` response instead of discarding them.

## Files

- `src/yasli_scraper/source.py` — four fields on `InstitutionMetadata`; read
  `TEL`, `EMAIL`, `NAME_D`, `WEBSITE` in `fetch_institution_metadata`; add a
  `_normalise_text` helper and a `_normalise_website` that also strips `\r`/`\n`
- `tests/test_source.py` — the parsing and normalisation cases below

## Acceptance

- [ ] A metadata row with all four fields produces an `InstitutionMetadata`
      carrying each verbatim after whitespace collapsing
- [ ] A row whose `WEBSITE` ends in `\r\r\n` yields a value with no trailing
      whitespace and no `\r`
- [ ] A `TEL` holding tab- or slash-separated numbers keeps every number and
      every slash, with tabs collapsed to single spaces
- [ ] A missing key, an explicit `null`, and a whitespace-only value all yield
      `None` — never `""`
- [ ] Rows with no usable `DZ_ID` are still skipped, as today

Evidence: `uv run pytest tests/test_source.py -v` output, including a test whose
fixture is a verbatim row captured from the live `garden` reception.

## Steps

### RED
- [ ] Add fixture rows to `tests/test_source.py` covering: all fields present;
      `WEBSITE` with a `\r\r\n` tail; `TEL` with tabs and slashes; a row with
      every contact key absent; a row with an explicit JSON `null` in every
      contact key; a row with whitespace-only values

### GREEN
- [ ] Add `phone`, `email`, `director`, `website` to `InstitutionMetadata`
- [ ] Add `_normalise_text(value: object) -> str | None` — `_normalise_address`'s
      exact body, guard included: `if value is None: return None`, then
      `" ".join(str(value).split())`, then empty-to-`None`. Without the guard
      `str(None)` is the non-empty string `"None"`, which passes every
      downstream validator and ships as a director's name
- [ ] Add `_normalise_website(value: object) -> str | None` — the same, since
      `str.split()` on no argument already splits on `\r` and `\n`; keep it as a
      named alias only if it earns its name, otherwise reuse `_normalise_text`
- [ ] Populate the four fields in `fetch_institution_metadata`

### REFACTOR
- [ ] Fold `_normalise_address` into `_normalise_text` — same behaviour, one
      helper — and update the module docstring's endpoint description to mention
      contacts

## Notes

`" ".join(str(value).split())` handles tabs, `\r`, `\n` and runs of spaces in
one step, because bare `str.split()` splits on any whitespace. That is why the
existing `_normalise_address` already produces clean output and why a separate
website helper probably does not earn its keep — verify with a test before
adding one.

Do not touch `parse_institution_address_html`. The HTML fallback exists only for
`address`; the catchment pages carry no contact data, so a metadata row without
contacts simply yields `None`.
