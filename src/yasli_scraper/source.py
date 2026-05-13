"""dg.uslugi.io endpoint client.

Wraps the two source-portal endpoints we depend on:

* ``POST /lv/api/childhood-rajon`` returns the per-reception institution
  listing as JSON.
* ``POST /lv/api/childhood`` returns per-reception institution metadata,
  including the physical address.
* ``GET <RAJON URL>`` returns the per-institution windows-1251 HTML.

Both calls go through :func:`yasli_scraper.http.fetch` so they inherit the
retry policy, Content-Length verification, and User-Agent header.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import httpx

from yasli_scraper.http import fetch

BASE_URL = "https://dg.uslugi.io"
REGIONS_PATH = "/lv/api/childhood-rajon"
CHILDHOOD_PATH = "/lv/api/childhood"
RECEPTIONS: tuple[str, ...] = ("infant", "garden", "pg")


@dataclass(frozen=True)
class InstitutionStub:
    """One row from the regions listing — minimum we need to fetch the HTML."""

    name: str
    source_url: str


@dataclass(frozen=True)
class InstitutionMetadata:
    """Metadata from `/lv/api/childhood` keyed by source institution id."""

    external_id: str
    address: str | None


async def fetch_regions(
    client: httpx.AsyncClient, reception: str
) -> list[InstitutionStub]:
    """POST to the regions endpoint for one reception; return parsed stubs."""
    body = await fetch(
        client,
        "POST",
        f"{BASE_URL}{REGIONS_PATH}",
        json={"reception": reception},
    )
    payload = json.loads(body)
    entries = payload.get("childhoodRajon", [])
    return [
        InstitutionStub(
            name=entry["DZ_NAME"].strip(),
            source_url=entry["RAJON"],
        )
        for entry in entries
    ]


async def fetch_institution_metadata(
    client: httpx.AsyncClient, reception: str
) -> dict[str, InstitutionMetadata]:
    """POST to the metadata endpoint for one reception; return rows by DZ_ID."""
    body = await fetch(
        client,
        "POST",
        f"{BASE_URL}{CHILDHOOD_PATH}",
        json={"reception": reception},
    )
    payload = json.loads(body)
    entries = payload.get("childhood", [])
    return {
        external_id: InstitutionMetadata(
            external_id=external_id,
            address=_normalise_address(entry.get("ADDRESS")),
        )
        for entry in entries
        if (external_id := str(entry.get("DZ_ID", "")).strip())
    }


async def fetch_html(client: httpx.AsyncClient, url: str) -> bytes:
    """GET a per-institution HTML page; return raw bytes."""
    return await fetch(client, "GET", url)


def _normalise_address(value: object) -> str | None:
    if value is None:
        return None
    address = " ".join(str(value).split())
    return address or None
