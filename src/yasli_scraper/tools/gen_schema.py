"""Regenerate ``schemas/snapshot.v2.schema.json`` from the Pydantic models.

Run as ``python -m yasli_scraper.tools.gen_schema``. The committed schema
file MUST match this generator's output byte-for-byte — a unit test enforces
the invariant.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from yasli_scraper.models import Snapshot

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_FILE = REPO_ROOT / "schemas" / "snapshot.v2.schema.json"


def render_schema() -> str:
    """Return the canonical JSON Schema text for the v2 snapshot."""
    schema = Snapshot.model_json_schema()
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    SCHEMA_FILE.parent.mkdir(parents=True, exist_ok=True)
    SCHEMA_FILE.write_text(render_schema(), encoding="utf-8")
    print(f"wrote {SCHEMA_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
