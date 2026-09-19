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

- **Contract** — the file must be plain UTF-8 without a BOM (what `run` writes; UTF-16 or a BOM fails the parse) and validates against the `Snapshot` v2 model in strict mode (`schema_version` 2, no extra keys, non-empty strings, nursery `district_code`; types are not coerced, so `"2"` is not `2` and `"true"` is not `true`). Unparseable or structurally malformed input is reported as a failure, not a traceback.
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

### Promoting a snapshot

`promote` publishes a local snapshot **you have already checked** — and publishes its exact bytes, so the file validated on your machine and the objects serving from R2 are the same artifact. This is the difference between `promote` and `sc-refresh`, which re-scrapes and uploads a *second*, unchecked snapshot.

```bash
python -m yasli_scraper promote --city varna /tmp/yasli-v2-snapshot.json
```

The full workflow is three steps: `sc-snapshot-local` → `sc-snapshot-check` → `sc-promote`.

**It runs the full `check` suite first and refuses on any failure — there is no bypass.** `promote` is exactly `check` + upload, so "it passed `sc-snapshot-check`" and "it is publishable" are the same statement. When the portal roster legitimately changes, update `EXPECTED_ROSTER` in `src/yasli_scraper/check.py` and commit that change; do not look for a `--force` flag, there isn't one.

Flags:

- `--city CITY` — asserts the file's declared `city`, exactly as `check`'s flag does. It never overrides it: the object-key prefix always comes from the file itself. Omitting it publishes under the file's own city.
- `--dry-run` — runs every check, validates the environment and prints the target keys, but makes no R2 write and never even imports boto3. The four `R2_*` vars are required **even for a dry run**: a rehearsal should fail on everything the real run would fail on except the write itself. (Use `check` if you want a credential-free pass.)

Exit codes: `0` published, `1` any check failure, a missing env var, an unreadable file **or a failed upload**, `2` argparse usage. A failed upload prints a single `error: upload failed: …` line naming both object keys and how far the two-phase write got — never a traceback.

A real `--dry-run` run (the rendered age advances with the clock; the rest is verbatim):

```
$ python -m yasli_scraper promote --city varna --dry-run /tmp/yasli-v2-snapshot.json
{
  "schema_version": 2,
  "city": "varna",
  "total": 77,
  "kinds": {
    "nursery": 12,
    "kindergarten": 53,
    "preschool": 12
  },
  "infant_group": 20,
  "null_address": 0,
  "null_phone": 0,
  "null_email": 0,
  "null_director": 0,
  "preschool_null_website": 0,
  "noisy_values": 0,
  "max_phone_length": 24
}
scraped_at: 2026-09-19T07:01:51Z (14s old)
would write: snapshots/varna/<UTC-ISO-timestamp>.json
would write: snapshots/varna/latest.json
```

The timestamped key is a `<UTC-ISO-timestamp>` placeholder on purpose — the real stamp is taken at write time, so printing an exact key here would be a lie by the time the real promote runs. On a real promote the two lines read `published: snapshots/varna/<the actual stamp>.json` and `published: snapshots/varna/latest.json`, in write order.

Two things to know about the output:

- **`promote`'s stdout is not a single JSON document.** It is the summary object *followed by* the `scraped_at` line and the receipt lines. `check` remains the pipe-friendly command; `promote`'s stdout is an operator's record, not a machine interface.
- **`promote` publishes the file you name, and never refuses on age.** A week-old snapshot that still passes every check will publish happily under a fresh timestamped key. The `scraped_at` line is printed *before* the upload, with the age rendered next to the exact stamp, so the age of what you are about to publish is on screen ahead of the write. Read it.

#### Rolling back a bad `latest.json`

**The rollback source is a copy of `latest.json` taken before the write — never "the newest timestamped object".** This is a permanent rule, not a precaution for one incident. Because the timestamped object is written *first*, a partial failure can leave a timestamped key newer than the `latest.json` that was actually being served; and a rollback supersedes but never deletes the object it replaces, so after any rollback the newest timestamped key is again a payload that was never served.

So: **download `latest.json` before you promote.** These commands use this repo's own credentials — `r2.make_client()` reads `R2_ACCOUNT_ID` / `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY`, which the AWS CLI does not pick up under those names, so `aws s3 cp` is not an option here. Each one must run from `scraper/` (there is no root `pyproject.toml`) and must load the repo `.env` itself (`make_client` reads `os.environ` directly):

```bash
# prelude — every command below starts with this
cd scraper && uv run python -c "
import os
from yasli_scraper.__main__ import _load_repo_env; _load_repo_env()
from yasli_scraper import r2
s3, bucket = r2.make_client(), os.environ['R2_BUCKET']
...
"
```

1. **List** the prefix:
   ```python
   print([o['Key'] for o in s3.list_objects_v2(Bucket=bucket, Prefix='snapshots/varna/').get('Contents', [])])
   ```
2. **Download** any key — use it for `latest.json` before promoting, and for the timestamped object named in the receipt afterwards:
   ```python
   open('/tmp/yasli-rollback.json','wb').write(s3.get_object(Bucket=bucket, Key='snapshots/varna/latest.json')['Body'].read())
   ```
3. **Restore** — the rollback itself:
   ```python
   s3.put_object(Bucket=bucket, Key='snapshots/varna/latest.json', Body=open('/tmp/yasli-rollback.json','rb').read(), ContentType='application/json')
   ```

Afterwards, download `latest.json` again and `cmp` it against your rollback file to confirm the restore landed.

#### Restoring the `sc-promote` recipe

The parent `yasli/justfile` is not under version control, so this block is the only durable copy:

```just
# Publish an already-validated local snapshot to R2, byte for byte.
[group('scraper')]
sc-promote FILE="/tmp/yasli-v2-snapshot.json" *ARGS:
    cd scraper && uv run python -m yasli_scraper promote --city varna "{{ FILE }}" {{ ARGS }}
```

`*ARGS` is load-bearing: it forwards trailing flags, so `just sc-promote /tmp/yasli-v2-snapshot.json --dry-run` reaches the CLI as `--dry-run` rather than binding to `FILE`.

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
