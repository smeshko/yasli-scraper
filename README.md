# yasli-scraper

Scrapes Varna's nurseries, kindergartens, and preschools from `dg.uslugi.io` and `newkg.uslugi.io`, validates against the snapshot v2 contract, and uploads canonical JSON to Cloudflare R2. [`yasli-backend`](https://github.com/smeshko/yasli-backend) ingests those snapshots on its own schedule.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for how the pieces fit together.

## Quickstart

Requires Python 3.12+.

```bash
pip install -e ".[dev]"

# Run against the live source, write to a local file (no R2 needed)
python -m yasli_scraper run --city varna --out ./snap.json

# Run tests
pytest

# Production-style run: uploads to R2 (needs the four R2 env vars)
export R2_ACCOUNT_ID=… R2_ACCESS_KEY_ID=… R2_SECRET_ACCESS_KEY=… R2_BUCKET=yasli-snapshots
python -m yasli_scraper run --city varna
```

The `--out PATH` flag bypasses R2 entirely.

## Docker

Mirrors what Railway runs:

```bash
docker build -t yasli-scraper:local .
docker run --rm --env-file .env yasli-scraper:local run --city varna
```

`.env` values must be **unquoted** — Docker's `--env-file` takes them literally.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `R2_ACCOUNT_ID` | Cloudflare account id (sets the R2 endpoint). |
| `R2_ACCESS_KEY_ID` | R2 API token access key. |
| `R2_SECRET_ACCESS_KEY` | R2 API token secret. |
| `R2_BUCKET` | Snapshot bucket, e.g. `yasli-snapshots`. |

All four are validated at startup. With `--out`, none are required.

## Output layout in R2

```
snapshots/<city>/<UTC-ISO-timestamp>.json   # immutable audit trail (written first)
snapshots/<city>/latest.json                # backend reads this (written second)
```

A partial failure leaves `latest.json` pointing at the previous good snapshot.

## Deployment

Deployed on Railway as a weekly cron service. See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).
