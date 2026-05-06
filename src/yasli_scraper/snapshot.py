"""Snapshot envelope construction.

Construction goes through ``Snapshot`` so the v1 contract is enforced
implicitly — invalid envelopes raise ``pydantic.ValidationError`` and never
reach R2. Real scraping logic (population of ``institutions``) lands in
``scraper-pipeline``.
"""
from __future__ import annotations

from datetime import datetime, timezone

from yasli_scraper.models import Snapshot

SCHEMA_VERSION = 1


def build_stub(city: str, *, now: datetime | None = None) -> Snapshot:
    """Return the stub snapshot envelope for ``city``."""
    moment = now if now is not None else datetime.now(timezone.utc)
    return Snapshot(
        schema_version=SCHEMA_VERSION,
        scraped_at=moment,
        city=city,
        institutions=[],
    )
