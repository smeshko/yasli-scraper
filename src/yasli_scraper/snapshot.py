"""Snapshot envelope construction.

The envelope shape is fixed across all changes in this capability. Real
scraping logic (population of ``institutions``) lands in ``scraper-pipeline``.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

SCHEMA_VERSION = 1


def _utc_iso_now(now: datetime | None = None) -> str:
    moment = now if now is not None else datetime.now(timezone.utc)
    return moment.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_stub(city: str, *, now: datetime | None = None) -> dict[str, Any]:
    """Return the stub snapshot envelope for ``city``.

    The envelope conforms to the ``Snapshot envelope`` requirement in the
    ``scraper-runtime`` spec: ``schema_version``, ``scraped_at``, ``city``,
    and an empty ``institutions`` array.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "scraped_at": _utc_iso_now(now),
        "city": city,
        "institutions": [],
    }
