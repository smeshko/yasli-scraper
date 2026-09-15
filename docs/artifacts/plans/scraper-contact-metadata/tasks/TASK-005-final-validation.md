# TASK-005: Final Validation

Depends on: all prior tasks
Suggested commit: `chore: final validation for scraper-contact-metadata`

## Goal

Confirm the plan is fully implemented and production-ready.

Every `just` recipe below lives in the parent `yasli/justfile`; `just` walks
up from `scraper/` to find it, so run them from anywhere under `yasli/`.
`be-ingest` runs `cd backend && uv run python -m yasli.ingest`.

## Steps

- [ ] All task checkboxes in `PLAN.md` are ticked
- [ ] `just sc-lint` passes with no issues
- [ ] `just sc-test` passes in full
- [ ] `uv run python -m yasli_scraper.tools.gen_schema` produces no diff on a
      second run and `uv run pytest tests/test_schema_artifact.py -v` passes —
      PLAN.md's schema-artifact criterion, re-checked here after every later edit
- [ ] `diff schemas/snapshot.v2.schema.json ../backend/tests/snapshot_contract/fixtures/snapshot.v2.schema.json`
      shows only the `"minItems": 1` line — PLAN.md's convergence criterion;
      paste the diff output as evidence
- [ ] **Precondition check** — executable, before anything is written to R2.
      Two facts, because `alembic upgrade head` is run by hand before deploys
      (backend `docs/DEPLOYMENT.md`), so the migration alone proves columns,
      not code: (1) in the Railway dashboard both `backend-api` and
      `backend-ingest` are deployed from a commit at or after backend phase
      1.1's merge (archived plan `2026-09-14-institution-contact-fields-contract`);
      (2) `SELECT version_num FROM alembic_version` on the Railway Postgres
      returns `0009` and `curl https://<backend-api>.up.railway.app/api/health`
      returns 200. The Sunday crons (scraper 01:00 UTC, backend ingest 02:00
      UTC) consume whatever `latest.json` holds, so this gate matters before
      merge as well as before a manual `sc-refresh`; run the live steps on a
      weekday so a rollback has days, not hours
- [ ] `just sc-snapshot-local /tmp/yasli-contacts.json`, then
      `just sc-snapshot-check /tmp/yasli-contacts.json` passes
- [ ] Coverage from that local snapshot: 77 institutions, 0 with `phone`,
      `email` or `director` null; 12 preschools, 0 with `website` null (the
      counts `sc-snapshot-check` already asserts). A different roster means the
      portal changed — stop and re-measure rather than tick
- [ ] Noise check: the `jq -e` noise assertion in RESEARCH.md → Useful Commands
      exits 0 — none of `phone`, `email`, `director`, `website` or `address`
      has a leading or trailing space, a tab, or a `\r`. It is an assertion,
      not an eyeball check: it exits 1 and lists the offenders when any value
      is dirty. `street`/`number` keep their verbatim contract and are not
      part of this check
- [ ] Key presence: `jq -e '[.institutions[] | has("phone") and has("email") and has("director") and has("website")] | all' /tmp/yasli-contacts.json`
      exits 0 — omitted fields serialise as `null`, they never vanish
- [ ] Record the longest observed `phone` value and confirm it fits the
      backend's `String(128)` column
- [ ] Rollback path noted **before** writing: `put_snapshot` keeps every run as
      `snapshots/varna/<ts>.json`, so if the new `latest.json` is rejected, copy
      the previous timestamped object over `latest.json` (any S3 client against
      the R2 endpoint) or re-run `just sc-refresh` from `staging`. A rejected
      snapshot leaves the database untouched — ingest is transactional and exits 3
- [ ] `just sc-refresh` writes the real snapshot to R2 — note the timestamped
      key it created
- [ ] Validate the artifact that was **actually published** before anything
      ingests it: download `snapshots/varna/latest.json` from the R2 dashboard
      (or any S3 client against the R2 endpoint) to `/tmp/yasli-latest.json`
      and re-run `just sc-snapshot-check /tmp/yasli-latest.json` plus the
      coverage, noise, key-presence and longest-`phone` checks above against
      it. This is the object the crons will read, so PLAN.md's coverage, noise
      and null criteria are ticked on *this* file, not on the local scrape
- [ ] `just be-ingest` succeeds — show the ingest summary
- [ ] Trigger a one-shot run of the Railway `backend-ingest` cron service from
      the dashboard and confirm it exits 0 with the same summary shape — the
      local `be-ingest` runs the checkout's code; this proves the *deployed*
      revision accepts the artifact
- [ ] Cross-check in the database, scoped to this snapshot's rows via the
      `last_seen_at` column ingest stamps:
      `SELECT count(*) FILTER (WHERE phone IS NULL) AS phone_null, count(*) FILTER (WHERE email IS NULL) AS email_null, count(*) FILTER (WHERE director IS NULL) AS director_null, count(*) FILTER (WHERE kind = 'preschool' AND website IS NULL) AS website_null, max(length(phone)) AS max_phone FROM institutions WHERE last_seen_at = (SELECT max(last_seen_at) FROM institutions);`
      — all four counts zero and `max_phone` ≤ 128
- [ ] Query five institutions with their phone, e-mail, director and website.
      **This is also the end-to-end proof for backend phase 1.1's second acceptance
      criterion** — link it from that plan's evidence
- [ ] `PLAN.md` acceptance criteria all met, each with its Evidence produced —
      no criterion ticked on "the code looks right"

### Epic update

The epics live in this repo (`docs/artifacts/epics/`, since 35e8b97), so
`link_plan.py` resolves both sides from the git toplevel.

- [ ] `python3 ~/.claude/skills/create-epic/scripts/link_plan.py 01 --phase 1.1 --plan scraper-contact-metadata --status done`
      — sets the phase's `**Plan**:` line to `status: done`
- [ ] Tick phase 1.1's `### Acceptance criteria` in
      `docs/artifacts/epics/01-contact-metadata.md`
- [ ] Backend phase 1.1's acceptance criteria are already all ticked in
      `../backend/docs/artifacts/epics/01-institution-data-foundation.md`; no
      backend commit is needed — the five-institution query above is simply the
      end-to-end evidence that plan promised
- [ ] This is Epic 01's only phase: tick its epic-level acceptance criteria and
      promote its row in `docs/artifacts/epics/EPICS.md` to `Done` — the tick
      rides this PR and becomes true when it merges, per the workflow in
      `EPICS.md`
