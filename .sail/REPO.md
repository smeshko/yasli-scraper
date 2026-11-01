# yasli-scraper

The weekly job that scrapes Varna's nursery and kindergarten portals (`dg.uslugi.io`, `newkg.uslugi.io`) into a validated JSON
snapshot on Cloudflare R2. `docs/ARCHITECTURE.md` has the layout. The backend is a separate repository that ingests the
snapshot, so the snapshot format is a contract with it.

## Commands

- Lint: `uv run ruff check .`. One test file: `uv run pytest <file>`. There is no type checker in CI.
- `uv` is the package manager; a new dependency is `uv add <package>`.

## Tests

pytest under `tests/`, one `test_<module>.py` per module, parsing against saved pages in `tests/fixtures/` (see its
README). Tests never reach a portal or R2.

## Contracts and generated files

- `schemas/snapshot.v2.schema.json` is generated from `src/yasli_scraper/models.py`, and `tests/test_schema_artifact.py`
  fails when they disagree. Change both together. A snapshot change must stay readable by the backend's ingest: add
  fields; a breaking change ends the step **blocked**.
- `EXPECTED_ROSTER` in `src/yasli_scraper/check.py` changes only when the portal's roster does.

## Demonstration

The surface is `cli`: `uv run python -m yasli_scraper` (`run`, `check`, `promote`).

Run every scenario through `.sail/lib/demo.sh <command> [args…]`, which strips the R2 credentials. Build the input from
`tests/fixtures/` and the code under `tests/`, and write output under `$STAGE_OUT/demo/`. `check` works on any local file.
`promote --dry-run` is the only form of `promote` a run uses, and a run never scrapes the live portals: `run` belongs to
the weekly job. A criterion only a live scrape could show is reported not shown, saying so.

```
.sail/lib/demo.sh uv run python -m yasli_scraper check --city varna "$STAGE_OUT/demo/snapshot.json"
```
