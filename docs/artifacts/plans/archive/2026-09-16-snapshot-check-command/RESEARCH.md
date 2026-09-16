# Research: Snapshot check command

Curated findings only — no raw conversation transcripts.

## Key Files & Directories

- `../justfile` (parent `yasli/`, **not under git**) — `sc-snapshot-check FILE`
  at ~line 125: a bash recipe that prints a jq summary object, then a `jq -e`
  boolean over schema version, nursery/preschool counts, null addresses,
  nursery district codes and the `Палечко` infant marker. `set dotenv-load`
  at the top of the file; every `sc-*` recipe does `cd scraper && …`.
- `src/yasli_scraper/__main__.py` — argparse CLI, `build_parser()` with one
  `run` subparser; `main(argv)` returns an int and prints `error: …` lines to
  stderr with exit 1. `_load_repo_env()` runs for every command and is a
  harmless no-op without a `.env`.
- `src/yasli_scraper/models.py` — `Snapshot` / `Institution` (`extra="forbid"`,
  `frozen=True`); `_optional_strings_non_empty` rejects `""` on `address`,
  `phone`, `email`, `director`, `website`; nurseries require `district_code`;
  `Snapshot.institutions` has `min_length=1`.
- `tests/test_cli.py` — calls `main([...])` directly, uses `capsys` for
  stdout/stderr and `tmp_path` for files; `conftest.py` points
  `REPO_ENV_PATH` at a nonexistent file so the real `.env` never bleeds in.
- `tests/test_models.py` — `_valid_institution_kwargs()` /
  `_valid_snapshot_kwargs()` helpers worth mirroring for building fixtures.
- `docs/artifacts/plans/archive/2026-09-15-scraper-contact-metadata/RESEARCH.md`
  — the jq coverage, noise and key-presence assertions this command replaces.

## Architecture Facts

- The CLI's `run` floor (`MIN_EXPECTED_INSTITUTIONS = 50`) is intentionally
  loose; the exact roster (12/12) lives only in the justfile today.
- `Snapshot.model_validate(payload)` on a parsed dict gives contract
  validation; `model_dump_json()` in tests gives a round-trippable fixture.
  Missing optional keys default to `None`, so presence needs the raw dict.
- Published snapshot as observed on 2026-09-15 (`scraped_at`
  2026-09-15T13:05:33Z): 77 institutions (53 kindergarten, 12 nursery,
  12 preschool), 20 with `has_infant_group`, 0 null addresses, 0 null
  contacts, 12/12 preschool websites, longest phone 24 chars. Only `pg` rows
  carry a website. **Reference values** — `latest.json` is overwritten by
  every scrape; `max_phone_length` is reported, not asserted. The 12/53/12
  per-kind counts (so `total` 77), zero-null and 12-website figures are the
  roster contract pinned in `EXPECTED_ROSTER`. The `run` floor comment in
  `__main__.py` says "~52 kindergartens"; the table follows the observed 53.
- `json.loads` on `bytes` decodes first, so invalid UTF-8 raises
  `UnicodeDecodeError` (a `ValueError`), not `JSONDecodeError`; both must be
  caught for arbitrary file bytes to become a failure rather than a traceback.
- `Snapshot.city` is only `str` with `min_length=1`; nothing in the model ties
  it to a roster, so a `--city` that *overrode* the file's value could bless
  a wrongly-labelled file. It is an assertion instead.
- `pipeline.coalesce_institutions` merges scraped rows by
  `(external_id, kind)`; that pair is the institution identity. The `Snapshot`
  model does not enforce uniqueness, so a duplicate pair in a file is a
  corruption signal the checker must catch itself.
- `tests/fixtures/` holds HTML pages only — there is no JSON snapshot fixture.
  Exact summary assertions therefore run on the synthetic builders in
  `tests/test_check.py`; a committed real snapshot is not introduced.
- `json.loads` happily returns a list, a string or `None` for valid JSON, and
  `institutions` can be missing, `null` or a scalar; the raw key scan has to
  guard for that before indexing.
- The noise assertion that produced the plan's evidence:
  `[.institutions[] | {phone, email, director, website, address}[] | select(. != null) | select(test("^\\s|\\s$|\\t|\\r"))] | length == 0`.

## Constraints

- The justfile change cannot be committed anywhere; it is a hand edit on this
  machine. The README must carry the recipe body so it is reproducible.
- `just` runs recipes from `yasli/`; the delegation must `cd scraper` like the
  other `sc-*` recipes and quote `"{{ FILE }}"`.
- Ruff line length 100; tests are `asyncio_mode = "auto"` but this work is
  synchronous.
- Keep `run` untouched — the check must not require R2 env vars.

## Useful Commands

```bash
# Download the published artifact read-only (from scraper/, no secrets printed)
uv run python - <<'EOF'
import importlib, os, dotenv
m = importlib.import_module("yasli_scraper.__main__"); dotenv.load_dotenv(m.REPO_ENV_PATH)
from yasli_scraper.r2 import make_client
make_client().download_file(os.environ["R2_BUCKET"], "snapshots/varna/latest.json", "/tmp/yasli-latest.json")
EOF

# The command under test
uv run python -m yasli_scraper check --city varna /tmp/yasli-latest.json; echo exit=$?

# A deliberately broken copy for the fail path
jq '.institutions[0].phone = null' /tmp/yasli-latest.json > /tmp/yasli-broken.json
uv run python -m yasli_scraper check /tmp/yasli-broken.json; echo exit=$?

# Through the justfile (after the hand edit)
just sc-snapshot-check /tmp/yasli-latest.json; echo exit=$?

uv run pytest tests/test_check.py tests/test_cli.py -v
```

## Uncertainty

- **Whether non-preschool rows may ever carry a website.** Unknown; treated as
  allowed (not asserted) so real data cannot be blocked by a coincidence.
- **Whether the parent folder will become a git repo.** If it does, the
  delegation line can be committed there; nothing in this plan depends on it.

## References

- Linear YAS-16 — the deferred finding (validation round-1 #10 of the
  contact-metadata plan)
- `docs/artifacts/plans/archive/2026-09-15-scraper-contact-metadata/` — the
  plan whose ad-hoc checks this command preserves
