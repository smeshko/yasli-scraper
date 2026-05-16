# Scraper architecture

## Role in the yasli system

```
  Bulgarian municipal portals
  ┌──────────────────────┐  ┌──────────────────────┐
  │   dg.uslugi.io       │  │   newkg.uslugi.io    │
  │  kindergartens + pg  │  │  standalone nurseries │
  └──────────┬───────────┘  └──────────┬───────────┘
             │                          │
             └───────────┬──────────────┘
                         ▼
              ┌────────────────────┐
              │   yasli-scraper    │   weekly cron on Railway
              │  fetch → parse →   │   (Sun 01:00 UTC)
              │  validate → write  │
              └─────────┬──────────┘
                        │ S3 PUT (boto3)
                        ▼
              ┌────────────────────────────────────┐
              │  Cloudflare R2: yasli-snapshots/   │
              │   snapshots/varna/<ts>.json        │
              │   snapshots/varna/latest.json      │
              └─────────┬──────────────────────────┘
                        │ pulled by backend ingest
                        ▼
                  yasli-backend (Postgres)
                        │
                        ▼
                  yasli-frontend (browser)
```

The scraper is the **only** writer of `snapshots/varna/*.json`. It never talks to the backend, the frontend, or the database — the contract is purely the JSON file in R2.

## Stack

- Python 3.12, `httpx` (async), Pydantic v2.
- HTML: built-in `html.parser` + regex on windows-1251 byte strings (matches the source encoding).
- `boto3` for the R2 S3-compatible API.
- pytest + `pytest-asyncio`, `respx` for HTTP mocking, `moto[s3]` for R2 mocking.

## Sources

| Source | Endpoint | What it gives us | Kinds produced |
| --- | --- | --- | --- |
| `dg.uslugi.io` | `POST /lv/api/childhood-rajon` `{reception: infant\|garden\|pg}` | Per-reception institution listings (stubs). | `kindergarten`, `preschool` |
| `dg.uslugi.io` | `POST /lv/api/childhood` | Institution metadata (physical addresses). | (enriches above) |
| `dg.uslugi.io` | `GET /lv/documents/{reception}/varna/rajon/{id}.html` | windows-1251 HTML — catchment street/number rows. | (enriches above) |
| `newkg.uslugi.io` | `POST /lv/api/childhood` `{reception: jasla}` | 12 standalone Varna nurseries with district codes. | `nursery` |

Every request retries up to 3 attempts with exponential backoff (1s, 2s, 4s) and a `Content-Length` sanity check. If any URL is still failing after 3 attempts, the run aborts with a non-zero exit and **no R2 write** — atomic semantics protect the backend from partial snapshots.

## Snapshot contract (v2)

```
Snapshot
├── schema_version: 2
├── scraped_at: AwareDatetime    (UTC, Z-suffixed)
├── city: str
└── institutions: list[Institution]
    ├── external_id: str         (extracted from source URL)
    ├── name: str
    ├── kind: nursery | kindergarten | preschool
    ├── source_url: HttpsUrl
    ├── address: str | None      (normalised physical address)
    ├── district_code: 01..05 | None  (required for nurseries)
    ├── has_infant_group: bool
    └── address_entries: list[AddressEntry]
        ├── street: str          (verbatim from source)
        └── number: str
```

Defined in `src/yasli_scraper/models.py`. The backend vendors a copy at `src/yasli/snapshot_contract/models.py` — the two must agree at every schema version. JSON Schema is exported to `schemas/snapshot.v2.schema.json` for inspection.

## Code layout

```
src/yasli_scraper/
├── __main__.py        CLI entry (argparse, --city, --out)
├── http.py            async fetch + retries + Content-Length check
├── source.py          dg.uslugi.io client (kindergartens + preschools)
├── source_jasla.py    newkg.uslugi.io client (standalone nurseries)
├── parser.py          windows-1251 HTML → (street, number) pairs
├── pipeline.py        orchestrates fetch → parse → build Snapshot
├── snapshot.py        SCHEMA_VERSION constant
├── models.py          Pydantic Snapshot/Institution/AddressEntry
├── r2.py              boto3 S3 client, two-phase upload
└── tools/             one-offs (schema dump, fixture capture)

schemas/               snapshot.v1.schema.json, snapshot.v2.schema.json
tests/
├── fixtures/          real captured HTMLs (infant_39, garden_34, pg_10)
└── test_*.py          unit + e2e (mocked endpoints via respx + moto)
docs/                  ARCHITECTURE.md, DEPLOYMENT.md
```

## Two-phase R2 write

Each successful run writes two objects, in order:

1. `snapshots/<city>/<UTC-ISO-timestamp>.json` — immutable audit trail.
2. `snapshots/<city>/latest.json` — what the backend ingest reads.

If step 2 fails after step 1 succeeded, the run exits non-zero but the previous `latest.json` is still intact. The backend never sees a partial snapshot.

## Deployment

Railway cron service:

- Schedule: `0 1 * * 0` (Sunday 01:00 UTC).
- Start command: `python -m yasli_scraper run --city varna`.
- Runtime: ~15–30s per run.

Full operator guide in `docs/DEPLOYMENT.md`.

## Cross-repo contracts

- **Backend**: must vendor a matching copy of the Pydantic snapshot models at the same `schema_version`. Bumping the schema is a coordinated change across both repos plus a backend migration.
- **R2**: bucket name + object key layout (`snapshots/{city}/{ts}.json`, `snapshots/{city}/latest.json`) is the only wire-level contract.
- **Sources**: `dg.uslugi.io` and `newkg.uslugi.io` are external, undocumented, and could break. The retry policy + atomic write design assumes that.
