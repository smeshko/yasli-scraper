"""dg.uslugi.io endpoint client.

Wraps the two source-portal endpoints we depend on:

* ``POST /lv/api/childhood-rajon`` returns the per-reception institution
  listing as JSON.
* ``POST /lv/api/childhood`` returns per-reception institution metadata:
  the physical address plus the contact details (phone, e-mail, director,
  website).
* ``GET <RAJON URL>`` returns the per-institution windows-1251 HTML.

All calls go through :func:`yasli_scraper.http.fetch` so they inherit the
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
    """Metadata from `/lv/api/childhood` keyed by source institution id.

    Every optional field is whitespace-normalised on the way in (see
    :func:`_normalise_text`); a blank source value becomes ``None``. ``phone``
    keeps every separator the source packs into ``TEL`` — slashes included —
    so multiple numbers survive as the portal gives them.
    """

    external_id: str
    address: str | None
    phone: str | None = None
    email: str | None = None
    director: str | None = None
    website: str | None = None


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
            address=_normalise_text(entry.get("ADDRESS")),
            phone=_normalise_text(entry.get("TEL")),
            email=_normalise_text(entry.get("EMAIL")),
            director=_normalise_text(entry.get("NAME_D")),
            website=_normalise_text(entry.get("WEBSITE")),
        )
        for entry in entries
        if (external_id := str(entry.get("DZ_ID", "")).strip())
    }


async def fetch_html(client: httpx.AsyncClient, url: str) -> bytes:
    """GET a per-institution HTML page; return raw bytes."""
    return await fetch(client, "GET", url)


def _normalise_text(value: object) -> str | None:
    """Collapse whitespace to single spaces; ``None`` or blank becomes ``None``.

    Bare ``str.split()`` splits on every whitespace character, so tabs, runs
    of spaces and the ``\\r\\r\\n`` tails the source appends to ``WEBSITE`` all
    collapse in one step. The ``None`` guard matters: ``str(None)`` is the
    non-empty string ``"None"``, which would otherwise ship as a value.
    """
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None
