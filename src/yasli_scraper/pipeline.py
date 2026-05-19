"""End-to-end scraping pipeline.

Steps (atomic — any exception aborts before any output is written):

1. Fetch DG RAJON listings and standalone nursery records.
2. Fetch each per-institution DG HTML page (cap = 4).
3. Parse DG catchment rows and optional physical addresses.
4. Build and coalesce v2 :class:`Snapshot` data via Pydantic.

The CLI handles destination (R2 vs ``--out`` file). The pipeline only
returns the validated :class:`Snapshot`.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import re

import httpx

from yasli_scraper.models import AddressEntry, DistrictCode, Institution, Kind, Snapshot
from yasli_scraper.parser import parse_address_html, parse_institution_address_html
from yasli_scraper.source import (
    RECEPTIONS,
    InstitutionStub,
    InstitutionMetadata,
    fetch_html,
    fetch_institution_metadata,
    fetch_regions,
)
from yasli_scraper.source_jasla import JaslaRecord, fetch_jasla

CONCURRENCY = 4
SCHEMA_VERSION = 2
SUPPORTED_CITIES: tuple[str, ...] = ("varna",)
PIPELINE_RECEPTIONS: tuple[str, ...] = ("garden", "infant", "pg")

KIND_BY_RECEPTION: dict[str, Kind] = {
    "infant": "kindergarten",
    "garden": "kindergarten",
    "pg": "preschool",
}
INFANT_GROUP_MARKER = re.compile(r"/\s*с\s+яслена\s+група\s*/", re.IGNORECASE)
_WHITESPACE = re.compile(r"\s+")
log = logging.getLogger(__name__)


@dataclass(frozen=True)
class DgBranchResult:
    institutions: list[Institution]
    address_failures: int


@dataclass
class MergedInstitution:
    external_id: str
    name: str
    kind: Kind
    source_url: str
    address_entries: list[AddressEntry]
    address_entry_keys: set[tuple[str, str]]
    address: str | None
    district_code: DistrictCode | None
    has_infant_group: bool


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
    (regions + institution HTMLs + standalone nursery listing). If ``client``
    is supplied (tests), it is not closed by this function.
    """
    if city not in SUPPORTED_CITIES:
        raise UnsupportedCityError(
            f"city {city!r} is not supported in v2 (supported: {SUPPORTED_CITIES})"
        )

    if client is None:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
        ) as owned:
            return await _run_with_client(city, owned, now=now)
    return await _run_with_client(city, client, now=now)


async def _run_with_client(
    city: str,
    client: httpx.AsyncClient,
    *,
    now: datetime | None,
) -> Snapshot:
    dg_result, jasla_records = await asyncio.gather(_run_dg_branch(client), fetch_jasla(client))

    if dg_result.address_failures:
        log.warning("scrape_summary address_extraction_failed=%s", dg_result.address_failures)
    else:
        log.info("scrape_summary address_extraction_failed=0")

    moment = now if now is not None else datetime.now(timezone.utc)
    return Snapshot(
        schema_version=SCHEMA_VERSION,
        scraped_at=moment,
        city=city,
        institutions=coalesce_institutions(
            dg_result.institutions + _institutions_from_jasla(jasla_records)
        ),
    )


async def _run_dg_branch(client: httpx.AsyncClient) -> DgBranchResult:
    region_lists, metadata_lists = await asyncio.gather(
        asyncio.gather(*(fetch_regions(client, rec) for rec in PIPELINE_RECEPTIONS)),
        asyncio.gather(*(fetch_institution_metadata(client, rec) for rec in RECEPTIONS)),
    )
    metadata_by_reception: dict[str, dict[str, InstitutionMetadata]] = dict(
        zip(RECEPTIONS, metadata_lists, strict=True)
    )
    pairs: list[tuple[str, InstitutionStub]] = [
        (reception, stub)
        for reception, stubs in zip(PIPELINE_RECEPTIONS, region_lists, strict=True)
        for stub in stubs
    ]

    semaphore = asyncio.Semaphore(CONCURRENCY)
    htmls = await asyncio.gather(
        *(_fetch_with_limit(client, semaphore, stub.source_url) for _, stub in pairs)
    )

    institutions: list[Institution] = []
    address_failures = 0
    for (reception, stub), html in zip(pairs, htmls, strict=True):
        external_id = _external_id_from_url(stub.source_url)
        metadata = metadata_by_reception.get(reception, {}).get(external_id)
        address = metadata.address if metadata is not None else None
        if address is None:
            address = parse_institution_address_html(html)
        if address is None:
            address_failures += 1
            log.warning(
                "address_extraction_failed external_id=%s source_url=%s",
                external_id,
                stub.source_url,
            )

        kind = KIND_BY_RECEPTION[reception]
        has_marker, name = normalise_reception_name(stub.name)
        rows = list(parse_address_html(html))
        institutions.append(
            Institution(
                external_id=external_id,
                name=name,
                kind=kind,
                source_url=stub.source_url,  # type: ignore[arg-type]
                address_entries=[
                    AddressEntry(street=street, number=number) for street, number in rows
                ],
                address=address,
                district_code=None,
                has_infant_group=kind == "kindergarten" and has_marker,
            )
        )

    return DgBranchResult(institutions=institutions, address_failures=address_failures)


def _institutions_from_jasla(records: list[JaslaRecord]) -> list[Institution]:
    return [
        Institution(
            external_id=record.external_id,
            name=record.name,
            kind="nursery",
            source_url=record.source_url,  # type: ignore[arg-type]
            address_entries=[],
            address=record.address,
            district_code=record.district_code,
            has_infant_group=False,
        )
        for record in records
    ]


def normalise_reception_name(name: str) -> tuple[bool, str]:
    has_marker = INFANT_GROUP_MARKER.search(name) is not None
    cleaned = INFANT_GROUP_MARKER.sub(" ", name)
    return has_marker, _WHITESPACE.sub(" ", cleaned).strip()


def coalesce_institutions(institutions: list[Institution]) -> list[Institution]:
    merged: dict[tuple[str, Kind], MergedInstitution] = {}

    for institution in institutions:
        key = (institution.external_id, institution.kind)
        bucket = merged.get(key)
        if bucket is None:
            entries = list(institution.address_entries)
            merged[key] = MergedInstitution(
                external_id=institution.external_id,
                name=institution.name,
                kind=institution.kind,
                source_url=str(institution.source_url),
                address_entries=entries,
                address_entry_keys={(entry.street, entry.number) for entry in entries},
                address=institution.address,
                district_code=institution.district_code,
                has_infant_group=institution.has_infant_group,
            )
            continue

        if bucket.address is None and institution.address is not None:
            bucket.address = institution.address
        bucket.has_infant_group = bucket.has_infant_group or institution.has_infant_group
        bucket.district_code = _compatible_district_code(
            bucket.district_code,
            institution.district_code,
            institution.external_id,
            institution.kind,
        )

        for entry in institution.address_entries:
            entry_key = (entry.street, entry.number)
            if entry_key in bucket.address_entry_keys:
                continue
            bucket.address_entry_keys.add(entry_key)
            bucket.address_entries.append(entry)

    return [
        Institution(
            external_id=bucket.external_id,
            name=bucket.name,
            kind=bucket.kind,
            source_url=bucket.source_url,  # type: ignore[arg-type]
            address_entries=bucket.address_entries,
            address=bucket.address,
            district_code=bucket.district_code,
            has_infant_group=bucket.has_infant_group,
        )
        for bucket in merged.values()
    ]


def _compatible_district_code(
    existing: DistrictCode | None,
    incoming: DistrictCode | None,
    external_id: str,
    kind: Kind,
) -> DistrictCode | None:
    if existing is None:
        return incoming
    if incoming is None or incoming == existing:
        return existing
    raise ValueError(f"conflicting district_code for {kind} {external_id}: {existing!r} vs {incoming!r}")
