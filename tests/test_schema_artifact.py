"""The committed JSON Schema must match what the Pydantic models generate."""
from __future__ import annotations

from yasli_scraper.tools.gen_schema import SCHEMA_FILE, render_schema


def test_committed_schema_matches_generator() -> None:
    """Drift between models and committed schema is a build failure.

    Regenerate via ``python -m yasli_scraper.tools.gen_schema`` if this fails.
    """
    on_disk = SCHEMA_FILE.read_text(encoding="utf-8")
    assert on_disk == render_schema(), (
        "schemas/snapshot.v1.schema.json is out of date — "
        "run `python -m yasli_scraper.tools.gen_schema`"
    )
