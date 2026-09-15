# Research: Emit contact metadata in the snapshot

Curated findings only — no raw conversation transcripts.

## Key Files & Directories

- `src/yasli_scraper/source.py` — `InstitutionMetadata` is a frozen dataclass
  holding only `external_id` and `address`. `fetch_institution_metadata` builds
  it from `/lv/api/childhood` rows keyed by `DZ_ID`, and `_normalise_address`
  is the existing collapse-whitespace-or-`None` helper.
- `src/yasli_scraper/source_jasla.py` — the `newkg.uslugi.io` client.
  `JaslaRecord` mirrors the same shape; `_collapse_ws` and `_normalise_address`
  already exist here as separate copies.
- `src/yasli_scraper/models.py` — the authoritative Pydantic contract.
  `Institution` is `extra="forbid"`, `frozen=True`, with `_address_non_empty`.
  Note `Snapshot.institutions` carries `Field(min_length=1)` here but **not** in
  the backend's vendored copy.
- `src/yasli_scraper/pipeline.py` — `_run_dg_branch` (~line 137) builds DG
  institutions and reads `metadata.address`; `_institutions_from_jasla`
  (~line 193) builds nurseries; `MergedInstitution` (~line 57) and
  `coalesce_institutions` (~line 215) merge the `garden`/`infant` duplicates.
- `src/yasli_scraper/tools/gen_schema.py` — writes
  `schemas/snapshot.v2.schema.json` with `indent=2, sort_keys=True,
  ensure_ascii=False` plus a trailing newline.
- `tests/test_schema_artifact.py` — fails when the committed schema drifts from
  the models.

## Architecture Facts

- `RECEPTIONS = ("infant", "garden", "pg")` drives the metadata fetch;
  `PIPELINE_RECEPTIONS = ("garden", "infant", "pg")` drives the region listings.
  Both are fetched today — this phase adds **no new HTTP requests**.
- A kindergarten with an infant group appears in *both* the `garden` and
  `infant` receptions and is merged by `coalesce_institutions` on
  `(external_id, kind)`. `address` merges first-non-`None`-wins; `district_code`
  goes through `_compatible_district_code`, which raises on conflict.
- `_run_dg_branch` falls back to `parse_institution_address_html(html)` when the
  metadata row has no address. There is no equivalent HTML fallback for
  contacts — the catchment page does not carry them — so a missing contact is
  simply `None`.
- The jasla branch has no HTML step at all; every field comes from the JSON.
- `source_jasla.py` normalises names through `_SMART_QUOTES` and `_collapse_ws`.
  Contacts need collapsing but **not** quote translation.

## Measured Source Facts (2026-08-17)

From `INSTITUTION_DETAIL_MAP_RESEARCH.md` §1, non-empty rows / total rows:

| Field | garden (53) | infant (18) | pg (12) | jasla (12) |
| --- | --- | --- | --- | --- |
| `TEL` | 53/53 | 18/18 | 12/12 | 12/12 |
| `EMAIL` | 53/53 | 18/18 | 12/12 | 12/12 |
| `NAME_D` | 53/53 | 18/18 | 12/12 | 12/12 |
| `WEBSITE` | 0/53 | 0/18 | **12/12** | 0/12 |

77 unique institutions after coalescing (`garden` 53 + `pg` 12 + `jasla` 12;
the 18 `infant` rows are the kindergartens-with-infant-group subset).

Known formatting noise:

- `TEL` is free-form — space-, slash- and **tab**-separated multiples.
- `WEBSITE` values carry `\r\r\n` tails.
- `NAME_D` and `EMAIL` need whitespace collapsing only.

## Constraints

- The backend deploys first. `extra="forbid"` on the backend's vendored
  `Institution` rejects the entire snapshot — not the unknown field — if the
  scraper is ahead.
- `schema_version` stays `2`. Optional-with-default fields keep every existing
  snapshot valid.
- The committed schema must match `gen_schema.py`'s output byte-for-byte;
  `tests/test_schema_artifact.py` enforces it.
- The scraper does not canonicalise `street`/`number`. Contacts are different —
  they are presentation data, and the noise above would otherwise reach the UI —
  but the cleaning stays limited to whitespace and line-ending removal.
- `just sc-refresh` writes to real R2. Use `just sc-snapshot-local <file>` for
  every check that does not specifically need to prove the R2 path.

## Useful Commands

Every `just` recipe below lives in the parent `yasli/justfile`, not in this
repo. `just` walks up from `scraper/` to find it and runs each recipe from
`yasli/` (`sc-*` recipes do `cd scraper && …`; `be-ingest` does
`cd backend && uv run python -m yasli.ingest`).

```bash
# Inspect what the source actually returns, per reception
for r in garden infant pg; do
  curl -sS -X POST 'https://dg.uslugi.io/lv/api/childhood' \
    -H 'Content-Type: application/json' -d "{\"reception\":\"$r\"}" -o "dg_$r.json"
done
curl -sS -X POST 'https://newkg.uslugi.io/lv/api/childhood' \
  -H 'Content-Type: application/json' -d '{"reception":"jasla"}' -o dg_jasla.json

# Local snapshot without touching R2
just sc-snapshot-local /tmp/yasli-contacts.json
just sc-snapshot-check /tmp/yasli-contacts.json

# Coverage + noise check on a local snapshot
jq '[.institutions[] | select(.phone == null)] | length' /tmp/yasli-contacts.json
jq '[.institutions[] | select(.kind=="preschool" and .website != null)] | length' /tmp/yasli-contacts.json
jq -e '[.institutions[] | has("phone") and has("email") and has("director") and has("website")] | all' \
  /tmp/yasli-contacts.json   # keys present even when null
jq -r '[.institutions[].phone | select(. != null) | length] | max' /tmp/yasli-contacts.json
# Noise assertion — exits 0 when clean, 1 when any contact/address value has
# leading/trailing whitespace, a tab or a \r (portable: no grep -P needed)
jq -e '[.institutions[] | {phone, email, director, website, address}[]
        | select(. != null) | select(test("^\\s|\\s$|\\t|\\r"))] | length == 0' \
  /tmp/yasli-contacts.json
# …and to list the offenders when it fails
jq -c '[.institutions[] | {phone, email, director, website, address}[]
        | select(. != null) | select(test("^\\s|\\s$|\\t|\\r"))]' /tmp/yasli-contacts.json

# Regenerate the artifact and confirm convergence with the backend fixture
uv run python -m yasli_scraper.tools.gen_schema
diff schemas/snapshot.v2.schema.json \
     ../backend/tests/snapshot_contract/fixtures/snapshot.v2.schema.json
```

## Uncertainty

- **Whether `TEL` ever exceeds the backend's `String(128)`.** Not measurable
  without a live run; the final validation records the observed maximum, which
  turns it from an assumption into a fact before production ingest sees it.
- **Whether to split multi-number `TEL` into a list.** Resolved: no. The epic
  says keep them as the source gives them, and a list would change the field's
  JSON type — a breaking contract change, not an additive one.
- **Whether jasla rows carry a `WEBSITE` key at all.** Measured 0/12 non-empty.
  Handled by reading with `.get()` and normalising to `None`, so a key that is
  absent and a key that is blank behave identically.

## References

- `openspec/docs/INSTITUTION_DETAIL_MAP_RESEARCH.md` §1 (field coverage and the
  formatting quirks), §8 (deploy-order constraint)
- `openspec/docs/NURSERY_RESEARCH.md` — the `jasla` source shape
- `docs/artifacts/epics/01-contact-metadata.md` — phase 1.1
- `schemas/README.md` — the field table this phase updates
