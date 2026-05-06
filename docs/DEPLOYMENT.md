# Deployment guide

This is the operator's step-by-step guide for getting `yasli-scraper` from a
fresh GitHub repo to a working weekly cron on Railway, writing snapshots into
Cloudflare R2.

The implementer of `s01-bootstrap-scraper-repo` does **not** log in to
Cloudflare or Railway. Every web-UI step below is for you, the operator, to
run once.

---

## Cloudflare R2 setup

R2 is Cloudflare's S3-compatible object storage. We treat it as S3 (via
`boto3`) pointed at an account-specific endpoint URL.

1. **Sign in** to <https://dash.cloudflare.com>. If you're new to R2 you'll
   be prompted to enable it on your account — accept the terms (R2 has a
   free tier sufficient for this project).
2. **Note your Account ID.** It's visible in the right sidebar of the
   dashboard ("Account ID") and as a path component of dashboard URLs. Save
   it; this is the `R2_ACCOUNT_ID` env var. It also determines the S3
   endpoint URL: `https://<account-id>.r2.cloudflarestorage.com`.
3. **Create the bucket.** Sidebar → **R2 Object Storage** → **Create bucket**.
   Name it `yasli-snapshots`. Location: leave as automatic. Click **Create
   bucket**. This is the `R2_BUCKET` env var.
4. **Create a scoped API token.** From R2 Object Storage → **Manage R2 API
   Tokens** → **Create API token**.
   - **Token name:** `yasli-scraper`
   - **Permissions:** **Object Read & Write**
   - **Specify bucket(s):** select **`yasli-snapshots` only** (do **not**
     grant access to all buckets).
   - **TTL:** leave at default (no expiry) unless your security policy
     requires rotation.
   - Click **Create API Token**.
5. **Copy the credentials immediately.** Cloudflare shows the
   **Access Key ID** and **Secret Access Key** **once**. They are the
   `R2_ACCESS_KEY_ID` and `R2_SECRET_ACCESS_KEY` env vars. If you lose
   them you have to recreate the token.

You should now have all four values:

| Env var                | Source                                              |
| ---------------------- | --------------------------------------------------- |
| `R2_ACCOUNT_ID`        | dashboard right sidebar / URL                       |
| `R2_ACCESS_KEY_ID`     | shown once on token creation                        |
| `R2_SECRET_ACCESS_KEY` | shown once on token creation                        |
| `R2_BUCKET`            | `yasli-snapshots`                                   |

Keep them somewhere safe (a password manager, not a sticky note).

---

## Railway setup

Railway runs the scraper as a Docker container on a cron schedule.

1. **Sign in** to <https://railway.app>.
2. **New Project** → **Deploy from GitHub repo**. Authorise Railway against
   GitHub if you haven't already, and select the `smeshko/yasli-scraper`
   repo. Railway will detect the `Dockerfile` and use it for builds — no
   buildpack involvement.
3. **Add the four R2 environment variables** to the service. In the service
   view → **Variables** → **+ New Variable**, paste each name and value
   from the table above. There are four; `R2_BUCKET=yasli-snapshots` is a
   plain literal, the other three came from R2.
4. **Convert the service to a Cron service.** In the service settings:
   - **Service type:** Cron
   - **Schedule:** `0 1 * * 0` (every Sunday at 01:00 UTC)
   - **Start command:** `python -m yasli_scraper run --city varna`
   Confirm the dashboard shows "Cron" rather than "Web". Web services run
   continuously and would crash-loop here; cron runs the start command on
   the schedule and expects a clean exit.
5. **Trigger the first build.** Railway should auto-build on the push that
   set up the service; if not, hit **Deploy**. Wait for the build to go
   green.

---

## One-off verification

Before relying on the cron, verify the pipeline by triggering a run yourself.

1. In the Railway service view, click **Deploy** → **Run now** (or whichever
   button currently triggers a one-shot run for cron services).
2. Open **Deployments** → latest deployment → **View logs**. You should see:
   - The container starts.
   - No "missing environment variable" errors.
   - A clean exit. Railway shows "Exited with code 0" for cron services on
     success. Expected runtime is **~15–30s** (83 institution HTMLs fetched
     four-at-a-time, each ~120–230 KB). A run that exits in <1s usually
     means env-var validation failed before any network call.
3. In Cloudflare R2 → bucket `yasli-snapshots` → **Objects**, navigate to
   `snapshots/varna/`. You should see two objects:
   - `latest.json` — the mutable pointer
   - `<UTC-ISO-timestamp>.json` — e.g. `2026-05-06T12:00:00Z.json`
4. Click `latest.json` → **Download** (or open the preview). Confirm the
   shape:
   ```json
   {
     "schema_version": 1,
     "scraped_at": "2026-05-06T12:00:00Z",
     "city": "varna",
     "institutions": [ /* ~83 entries with kind/name/address_entries */ ]
   }
   ```
   Total `address_entries` rows across all institutions should be on the
   order of **~236k** for Varna.

If everything matches, the pipeline is working end-to-end and the cron will
keep producing fresh snapshots weekly.

---

## Local dev quickstart (no R2 needed)

Use this for everyday iteration when you just want to inspect the JSON.

```bash
pip install -e ".[dev]"
python -m yasli_scraper run --city varna --out ./snap.json
```

`--out` writes the snapshot JSON to the given path and **skips the R2
upload entirely**. The four `R2_*` env vars are not consulted, so you can
run this on a fresh clone with no setup. Inspect the result with:

```bash
python -c "import json; d=json.load(open('snap.json')); \
  print(len(d['institutions']), 'institutions,', \
  sum(len(i['address_entries']) for i in d['institutions']), 'rows')"
```

Expect ~83 institutions and ~236k rows.

## Local Docker run (against your real R2 bucket)

Use this to test the production code-path before pushing to Railway.

1. Create a local `.env` file (it's gitignored — never commit it):
   ```bash
   cat > .env <<'EOF'
   R2_ACCOUNT_ID=<your-account-id>
   R2_ACCESS_KEY_ID=<your-access-key>
   R2_SECRET_ACCESS_KEY=<your-secret>
   R2_BUCKET=yasli-snapshots
   EOF
   ```
2. Build the image:
   ```bash
   docker build -t scraper:local .
   ```
3. Run it. The container's entrypoint is `python -m yasli_scraper`, so the
   trailing `run --city varna` is the subcommand + args:
   ```bash
   docker run --rm --env-file .env scraper:local run --city varna
   ```
   To exercise the `--out` flag locally without touching R2 (useful when
   debugging the container build), mount a directory and pass `--out`:
   ```bash
   docker run --rm -v "$PWD/out:/out" scraper:local \
       run --city varna --out /out/snap.json
   ```
4. Verify a new timestamped object appears in R2 under `snapshots/varna/`,
   and `latest.json` matches.

## Refreshing test fixtures

The `tests/fixtures/*.html` files are real captures from `dg.uslugi.io`. If
the source changes shape and the parser starts failing, refresh from the
spec repo (`yasli/initial/data/raw/`) — see
`tests/fixtures/README.md` for the exact `cp` commands. To refresh the
upstream HTMLs themselves, run `initial/scripts/01_fetch_regions.sh` then
`initial/scripts/02_fetch_rajon_html.py` in the spec repo.

---

## Troubleshooting

### Missing or mistyped environment variable

**Symptom:** Container exits non-zero almost immediately. Logs:
```
error: required environment variable R2_BUCKET is not set
```

**Fix:** Check the Railway **Variables** tab for that exact name. The
scraper validates env vars at startup before any network call, so this
error is purely about the variable name and value. Watch for trailing
whitespace and mixed-case typos (`R2_AccessKey_ID` ≠ `R2_ACCESS_KEY_ID`).

### Wrong R2 endpoint URL

**Symptom:** boto3 errors like `EndpointConnectionError` or DNS resolution
failures during `put_object`.

**Fix:** The scraper builds the endpoint URL as
`https://<R2_ACCOUNT_ID>.r2.cloudflarestorage.com`. If `R2_ACCOUNT_ID` is
copied wrong (extra characters, only part of the ID), the host won't
resolve. Re-copy from the Cloudflare dashboard sidebar.

### `403 Forbidden` / `AccessDenied` from R2

**Symptom:** Logs show an `S3.Client.exceptions.ClientError` with
`AccessDenied` on `PutObject`.

**Fix:** The API token doesn't have write access to the bucket, or it's
scoped to a different bucket. Recreate the token in R2 → **Manage R2 API
Tokens**, ensuring **Object Read & Write** and **bucket: yasli-snapshots**
are selected. Update both Railway and any local `.env`.

### `404 NoSuchBucket`

**Symptom:** R2 returns `NoSuchBucket` on the first put.

**Fix:** `R2_BUCKET` is misspelled, or the bucket wasn't created in this
account. R2 buckets are scoped to a single Cloudflare account. Confirm the
bucket exists in the same account whose ID you're using.

### Railway service is a Web service, not a Cron service

**Symptom:** Container starts on every deploy, runs once, exits 0, then
Railway restarts it. Logs show repeated runs with `RestartLoopBackoff` or
similar.

**Fix:** In Railway service settings, **Service type** must be **Cron**.
Web services keep restarting any process that exits, which is the wrong
contract for a one-shot scraper.

### Cron didn't fire on schedule

**Symptom:** No new objects in `snapshots/varna/` after Sunday 01:00 UTC.

**Fix:**
- Confirm the schedule cron expression is `0 1 * * 0` (UTC). Railway uses
  UTC — local-timezone confusion is the most common cause.
- Check the **Deployments** tab — Railway shows skipped or failed runs.
- If the most recent build was after the cron tick, the next run is
  scheduled for the following week's tick; trigger a manual run to verify
  the harness works.

### Manual run wrote a timestamped object but `latest.json` is stale

**Symptom:** A new `<timestamp>.json` exists, but `latest.json` still has
older content.

**Fix:** This is the documented "partial failure" mode (see the
`R2 write order` requirement in `scraper-runtime`). The first write
succeeded; the second failed. The process should have exited non-zero —
inspect the failed deployment's logs for the underlying error (often
permissions or a transient R2 5xx). Re-run after fixing.

### Local Docker run says "permission denied" on `.env`

**Symptom:** `docker run --env-file .env` errors with permission denied.

**Fix:** Make sure the `.env` file is readable by your user
(`chmod 600 .env` is fine — Docker reads it as your UID), and that you're
running `docker run` from the directory containing `.env`.
