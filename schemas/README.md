# Snapshot contract

This directory holds the canonical, language-agnostic spec for the JSON
snapshots the scraper writes to R2. The Pydantic models in
`src/yasli_scraper/models.py` are the single source of truth; the committed
schema file is generated from them via:

```sh
python -m yasli_scraper.tools.gen_schema
```

A unit test (`tests/test_schema_artifact.py`) fails if the committed file
drifts from what the models emit.

## Files

- `snapshot.v1.schema.json` — JSON Schema (draft 2020-12, via Pydantic) for
  the v1 envelope. Vendor this into any non-Python consumer.
- `examples/varna-stub.json` — a minimal valid snapshot, used as a
  reference and as a fixture for cross-language consumers.

## Envelope (v1)

| Field            | Type                                        | Notes |
| ---------------- | ------------------------------------------- | ----- |
| `schema_version` | integer (literal `1`)                       | Bumping always indicates a breaking change. |
| `scraped_at`     | ISO 8601 UTC datetime ending in `Z`         | Wall-clock instant the scrape completed. |
| `city`           | non-empty string slug (e.g. `"varna"`)      | One snapshot per city per run. |
| `institutions`   | array of `Institution` (possibly empty)     | One entry per municipal institution. |

## `Institution`

| Field             | Type                                                | Notes |
| ----------------- | --------------------------------------------------- | ----- |
| `external_id`     | non-empty string                                    | The source-system ID (e.g. `"39"`); `external_` prefix disambiguates from any internal DB primary key the backend assigns at ingest. |
| `name`            | non-empty string                                    | Raw `DZ_NAME` from the source — preserved verbatim, including quotes / mixed punctuation. |
| `kind`            | one of `"nursery"`, `"kindergarten"`, `"preschool"` | Translated from source jargon at the scraper boundary (`infant` → `nursery`, `garden` → `kindergarten`, `pg` → `preschool`). |
| `source_url`      | HTTPS URL                                           | Page on the source portal that originated this institution. |
| `address_entries` | array of `AddressEntry` (possibly empty)            | One entry per street/number row. |

## `AddressEntry`

| Field    | Type             | Notes |
| -------- | ---------------- | ----- |
| `street` | non-empty string | Raw form, e.g. `"ГР.ВАРНА БУЛ.ВЛАДИСЛАВ ВАРНЕНЧИК"` — preserved verbatim, **no normalisation**. |
| `number` | non-empty string | Raw form, e.g. `"041 вх.А"` — preserved verbatim. |

## Invariants

- All three models forbid extra fields (`extra='forbid'`). Drift in the
  source portal that adds a field surfaces as a validation error rather
  than silently passing through.
- All three models are frozen — instances cannot be mutated between
  construction and serialisation.
- Validation is implicit: constructing `Snapshot(...)` enforces every
  constraint above. There is no separate `validate_snapshot()` step.
- The scraper does not normalise street / number. Any canonicalisation is
  the backend's job during ingest.

## Versioning policy

- `schema_version` is a single integer; bumping it is **always** a breaking
  change.
- Consumers MUST reject snapshots whose `schema_version` is not one they
  support, without attempting to interpret the rest of the document.
- Future versions ship as **sibling files** (`snapshot.v2.schema.json`,
  `models.py` gains a `SnapshotV2`). v1 is never edited in place once
  published.
- Examples of changes that require a version bump: adding/removing a
  required field, changing a field's type, changing the `kind` value
  vocabulary, changing the meaning of an existing field.

## For non-Python consumers

Vendor `snapshot.v1.schema.json` into your repo and add a test that
asserts byte-for-byte equality with the upstream copy. A small duplication
beats the friction of a single-file submodule.
