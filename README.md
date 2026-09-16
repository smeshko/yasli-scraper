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

### Checking a snapshot

`check` proves a local snapshot file is publishable. It reads the file only — no R2 access, no env vars:

```bash
python -m yasli_scraper check --city varna ./snap.json
```

It prints a summary object on stdout, then one `check failed: …` line per failure on stderr, and exits `0` when every check passes or `1` otherwise (argparse keeps `2` for usage errors). Every failure is reported in one run, and the summary is printed even when checks fail.

What is asserted:

- **Contract** — the file validates against the `Snapshot` v2 model (`schema_version` 2, no extra keys, non-empty strings, nursery `district_code`). Unparseable or structurally malformed input is reported as a failure, not a traceback.
- **Key presence** — every institution carries all four contact keys (`phone`, `email`, `director`, `website`), even when null.
- **Roster** — the per-city table `EXPECTED_ROSTER` in `src/yasli_scraper/check.py`: for Varna 12 nurseries, 53 kindergartens, 12 preschools, no null `address`, no duplicate `(kind, external_id)`, and the `Палечко` infant-group marker present with `has_infant_group: true`. The table is selected by the file's own `city`; an unknown city fails. When the portal roster changes, update that table.
- **Contact coverage** — no null `phone`, `email` or `director` on any institution, and no preschool without a `website`.
- **Noise** — no leading/trailing whitespace, tab or `\r` in `phone`, `email`, `director`, `website` or `address`.

`--city` asserts the file's declared `city` — it does not override it — so a recipe can refuse a file labelled for another city.

The parent `yasli/justfile` (not under version control) delegates its `sc-snapshot-check` recipe to this command. If the recipe is ever lost, restore it as:

```just
# Validate a local snapshot has the expected v2 nursery-ingest shape.
[group('scraper')]
sc-snapshot-check FILE="/tmp/yasli-v2-snapshot.json":
    cd scraper && uv run python -m yasli_scraper check --city varna "{{ FILE }}"
```

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
