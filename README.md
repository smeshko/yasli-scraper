# yasli-scraper

Scraper that produces canonical JSON snapshots of Bulgarian municipal services
and writes them to Cloudflare R2. The backend ingests those snapshots on its
own schedule.

This repo is the scraper half of the `yasli` system. Specs live in the
sibling [`yasli/spec`](https://github.com/smeshko/yasli-spec) repo.

## Status

`v0.1.0` — stub iteration. The CLI runs end-to-end and writes a well-formed
empty snapshot envelope to R2. Real scraping logic lands in a follow-up
change (`scraper-pipeline`).

## Quickstart (local, Python)

Requires Python 3.12+.

```bash
# Install in editable mode with dev deps
pip install -e ".[dev]"

# Run tests
pytest

# Run the scraper (needs real R2 credentials — see docs/DEPLOYMENT.md)
export R2_ACCOUNT_ID=...
export R2_ACCESS_KEY_ID=...
export R2_SECRET_ACCESS_KEY=...
export R2_BUCKET=yasli-snapshots
python -m yasli_scraper run --city varna
```

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

## Layout

```
src/yasli_scraper/
  __init__.py        # __version__
  __main__.py        # CLI entry point (argparse)
  r2.py              # boto3 wrapper for R2 (S3-compatible)
  snapshot.py        # snapshot envelope builder
tests/               # pytest suite
docs/DEPLOYMENT.md   # operator setup guide
Dockerfile           # python:3.12-slim image
pyproject.toml
```
