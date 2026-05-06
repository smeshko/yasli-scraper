"""End-to-end scraping pipeline.

Steps (atomic — any exception aborts before any output is written):

1. Fetch the regions listing for each of the three receptions.
2. Concurrently fetch each per-institution HTML page (cap = 4).
3. Parse each HTML into ``(street, number)`` rows.
4. Build :class:`Snapshot` via Pydantic.

The CLI handles destination (R2 vs ``--out`` file). The pipeline only
returns the validated :class:`Snapshot`.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import httpx

from yasli_scraper.models import AddressEntry, Institution, Snapshot
from yasli_scraper.parser import parse_address_html
from yasli_scraper.snapshot import SCHEMA_VERSION
from yasli_scraper.source import (
    RECEPTIONS,
    InstitutionStub,
    fetch_html,
    fetch_regions,
)

CONCURRENCY = 4
SUPPORTED_CITIES: tuple[str, ...] = ("varna",)

KIND_BY_RECEPTION: dict[str, str] = {
    "infant": "nursery",
    "garden": "kindergarten",
    "pg": "preschool",
}


class UnsupportedCityError(ValueError):
    """Raised when ``city`` is not one of :data:`SUPPORTED_CITIES`."""


def _external_id_from_url(url: str) -> str:
    """Extract the institution ID from a RAJON URL (``.../<id>.html``)."""
    return url.rsplit("/", 1)[-1].removesuffix(".html")


async def _fetch_with_limit(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    url: str,
) -> bytes:
    async with semaphore:
        return await fetch_html(client, url)


async def run(
    city: str,
    *,
    client: httpx.AsyncClient | None = None,
    now: datetime | None = None,
) -> Snapshot:
    """Run the full fetch → parse → build pipeline for ``city``.

    A single :class:`httpx.AsyncClient` is reused across all requests
    (regions + institution HTMLs). If ``client`` is supplied (tests), it is
    not closed by this function.
    """
    if city not in SUPPORTED_CITIES:
        raise UnsupportedCityError(
            f"city {city!r} is not supported in v1 (supported: {SUPPORTED_CITIES})"
        )

    if client is None:
        async with httpx.AsyncClient() as owned:
            return await _run_with_client(city, owned, now=now)
    return await _run_with_client(city, client, now=now)


async def _run_with_client(
    city: str,
    client: httpx.AsyncClient,
    *,
    now: datetime | None,
) -> Snapshot:
    # Step 1: regions for every reception, in parallel.
    region_lists = await asyncio.gather(
        *(fetch_regions(client, rec) for rec in RECEPTIONS)
    )
    pairs: list[tuple[str, InstitutionStub]] = [
        (reception, stub)
        for reception, stubs in zip(RECEPTIONS, region_lists, strict=True)
        for stub in stubs
    ]

    # Step 2: per-institution HTMLs, concurrency-capped.
    semaphore = asyncio.Semaphore(CONCURRENCY)
    htmls = await asyncio.gather(
        *(_fetch_with_limit(client, semaphore, stub.source_url) for _, stub in pairs)
    )

    # Steps 3–4: parse each HTML, build Institution + Snapshot.
    institutions: list[Institution] = []
    for (reception, stub), html in zip(pairs, htmls, strict=True):
        rows = list(parse_address_html(html))
        institutions.append(
            Institution(
                external_id=_external_id_from_url(stub.source_url),
                name=stub.name,
                kind=KIND_BY_RECEPTION[reception],  # type: ignore[arg-type]
                source_url=stub.source_url,  # type: ignore[arg-type]
                address_entries=[
                    AddressEntry(street=street, number=number) for street, number in rows
                ],
            )
        )

    moment = now if now is not None else datetime.now(timezone.utc)
    return Snapshot(
        schema_version=SCHEMA_VERSION,
        scraped_at=moment,
        city=city,
        institutions=institutions,
    )
