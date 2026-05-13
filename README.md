# yasli-scraper

Scraper that produces canonical JSON snapshots of Bulgarian municipal services
and writes them to Cloudflare R2. The backend ingests those snapshots on its
own schedule.

This repo is the scraper half of the `yasli` system. Specs live in the
sibling [`yasli/spec`](https://github.com/smeshko/yasli-spec) repo.

## Status

`v0.3.0` — snapshot v2 pipeline. The CLI scrapes DG catchments from
`dg.uslugi.io`, standalone nurseries from `newkg.uslugi.io`, and writes a
~76-institution snapshot to R2 (or to a local file with `--out`). The
expected weekly cron runtime on Railway is ~15–30s.

## Quickstart (local, Python)

Requires Python 3.12+.

```bash
# Install in editable mode with dev deps
pip install -e ".[dev]"

# Run tests
pytest

# Local end-to-end against the live source — no R2 setup needed
python -m yasli_scraper run --city varna --out ./snap.json

# Production-style invocation: writes the snapshot to R2 instead.
# Needs the four R2 env vars (see docs/DEPLOYMENT.md).
export R2_ACCOUNT_ID=...
export R2_ACCESS_KEY_ID=...
export R2_SECRET_ACCESS_KEY=...
export R2_BUCKET=yasli-snapshots
python -m yasli_scraper run --city varna
```

The `--out PATH` flag bypasses R2 entirely: the snapshot JSON lands at
`PATH` and the four `R2_*` env vars are not consulted. Default invocation
(no `--out`) uploads to R2 and requires those env vars.

## Quickstart (local, Docker)

Mirrors what Railway runs in production.

```bash
# Build the image (note the trailing '.', the build context)
docker build -t yasli-scraper:local .

# Put your R2 creds in a local .env (gitignored), values UNQUOTED:
#   R2_ACCOUNT_ID=...
#   R2_ACCESS_KEY_ID=...
#   R2_SECRET_ACCESS_KEY=...
#   R2_BUCKET=yasli-snapshots
# Docker's --env-file takes values literally — surrounding "..." would
# become part of the value and break the R2 endpoint URL.

# Run (the trailing args go to the python -m yasli_scraper entrypoint)
docker run --rm --env-file .env yasli-scraper:local run --city varna
```

See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for full troubleshooting.

## Required environment variables

| Variable                | Purpose                                          |
| ----------------------- | ------------------------------------------------ |
| `R2_ACCOUNT_ID`         | Cloudflare account ID (sets the R2 endpoint URL) |
| `R2_ACCESS_KEY_ID`      | R2 API token access key                          |
| `R2_SECRET_ACCESS_KEY`  | R2 API token secret                              |
| `R2_BUCKET`             | Bucket name (e.g. `yasli-snapshots`)             |

All four are validated at startup before any network call. A missing or
empty value causes a non-zero exit with the variable name on stderr.

## Object layout in R2

Each successful run writes two objects:

```
snapshots/<city>/<UTC-ISO-timestamp>.json   # immutable audit trail
snapshots/<city>/latest.json                # mutable pointer the backend reads
```

The timestamped object is written first; `latest.json` is overwritten only
on success. A partial failure leaves `latest.json` pointing at the previous
good snapshot.

## Cloud setup (Cloudflare R2 + Railway)

See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for the step-by-step operator
guide covering R2 bucket and API token creation, Railway cron service
configuration, one-off verification, local Docker runs against real R2, and
troubleshooting.

## Source endpoints and retry policy

The scraper hits two municipal source portals:

* `POST /lv/api/childhood-rajon` with `{"reception": "<infant|garden|pg>"}`
  on `dg.uslugi.io` returns the per-reception institution listing. `infant`
  and `garden` both map to `kind="kindergarten"`; the infant-group marker in
  `DZ_NAME` sets `has_infant_group`.
* `GET <RAJON URL>` returns the per-institution windows-1251 HTML
  (street/number blocks).
* `POST /lv/api/childhood` with `{"reception": "jasla"}` on
  `newkg.uslugi.io` returns the 12 standalone nurseries. These records carry
  `address` and `district_code`, but no catchment `address_entries`.

Every request retries up to **3 attempts** with exponential backoff
(1s, 2s, 4s) and a `Content-Length` check on each response. If any URL is
still failing after 3 attempts, the whole run aborts with a non-zero exit
and **no R2 write** — atomic semantics protect snapshot consumers from
silent data loss. See `openspec/docs/CONTEXT.md` in the spec repo for the
full reverse-engineering history of these endpoints.

## Layout

```
src/yasli_scraper/
  __init__.py        # __version__
  __main__.py        # CLI entry point (argparse)
  http.py            # async fetch with retries + UA + Content-Length check
  source.py          # dg.uslugi.io endpoint client
  source_jasla.py    # newkg.uslugi.io standalone nursery client
  parser.py          # windows-1251 HTML → address + (street, number) pairs
  pipeline.py        # orchestrates fetch → parse → Snapshot
  r2.py              # boto3 wrapper for R2 (S3-compatible)
  snapshot.py        # SCHEMA_VERSION constant + (legacy) stub builder
tests/               # pytest suite
tests/fixtures/      # real captured HTMLs — see fixtures/README.md
docs/DEPLOYMENT.md   # operator setup guide
Dockerfile           # python:3.12-slim image
pyproject.toml
```
