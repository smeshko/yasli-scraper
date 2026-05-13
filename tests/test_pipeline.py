from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import httpx
import pytest
import respx

from yasli_scraper.models import AddressEntry, Institution
from yasli_scraper.pipeline import (
    KIND_BY_RECEPTION,
    SUPPORTED_CITIES,
    UnsupportedCityError,
    coalesce_institutions,
    normalise_reception_name,
    run,
)
from yasli_scraper.source import BASE_URL, CHILDHOOD_PATH as DG_CHILDHOOD_PATH
from yasli_scraper.source import REGIONS_PATH
from yasli_scraper.source_jasla import BASE_URL as JASLA_BASE_URL
from yasli_scraper.source_jasla import CHILDHOOD_PATH as JASLA_CHILDHOOD_PATH

from .fixtures import load_html

# (reception, external_id, fixture_filename, dz_name)
PIPELINE_INSTITUTIONS = [
    ("infant", "39", "infant_39.html", 'ДГ№6 "Палечко"'),
    ("garden", "34", "garden_34.html", 'ДГ№1 "Светулка"'),
    ("pg", "10", "pg_10.html", 'ОУ "Капитан Петко войвода"'),
]

EXPECTED_ROW_TOTAL = 4503 + 4497 + 8222
JASLA_RECORD = {
    "DZ_ID": "9001",
    "DZ_NAME": " ДЯ №1 „Щастливо детство“ ",
    "ADDRESS": " ул.  \"Славянска\"   21 ",
    "RAJON_ID": "1",
    "RAJON": "01",
}
DG_ADDRESSES = {
    "39": 'гр. Варна, ул. "Тодор Влайков" №65 А',
    "34": 'гр. Варна, ул. "Парижка комуна" №25',
    "10": 'гр. Варна, бул. "Владислав Варненчик" №36',
}


def _rajon_url(reception: str, ext_id: str) -> str:
    return f"{BASE_URL}/lv/documents/{reception}/varna/rajon/{ext_id}.html"


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _instant(_seconds: float) -> None:
        return None

    monkeypatch.setattr("yasli_scraper.http.asyncio.sleep", _instant)


def _mock_endpoints(*, include_jasla: bool = True, include_metadata: bool = True) -> None:
    by_reception: dict[str, list[dict[str, str]]] = {
        rec: [] for rec in KIND_BY_RECEPTION
    }
    for reception, ext_id, fixture, name in PIPELINE_INSTITUTIONS:
        url = _rajon_url(reception, ext_id)
        by_reception[reception].append({"DZ_NAME": name, "RAJON": url})
        respx.get(url).mock(
            return_value=httpx.Response(200, content=load_html(fixture))
        )

    for reception, entries in by_reception.items():
        respx.post(
            f"{BASE_URL}{REGIONS_PATH}", json={"reception": reception}
        ).mock(
            return_value=httpx.Response(
                200,
                content=json.dumps({"childhoodRajon": entries}).encode(),
            )
        )
        records = []
        if include_metadata:
            for entry in entries:
                external_id = entry["RAJON"].rsplit("/", 1)[-1].removesuffix(".html")
                records.append({"DZ_ID": external_id, "ADDRESS": DG_ADDRESSES[external_id]})
        respx.post(f"{BASE_URL}{DG_CHILDHOOD_PATH}", json={"reception": reception}).mock(
            return_value=httpx.Response(200, content=json.dumps({"childhood": records}).encode())
        )
    if include_jasla:
        _mock_jasla()


def _mock_jasla() -> None:
    respx.post(f"{JASLA_BASE_URL}{JASLA_CHILDHOOD_PATH}", json={"reception": "jasla"}).mock(
        return_value=httpx.Response(
            200,
            content=json.dumps({"childhood": [JASLA_RECORD]}).encode(),
        )
    )


def _mock_empty_dg_metadata() -> None:
    for reception in KIND_BY_RECEPTION:
        respx.post(f"{BASE_URL}{DG_CHILDHOOD_PATH}", json={"reception": reception}).mock(
            return_value=httpx.Response(200, content=json.dumps({"childhood": []}).encode())
        )


@respx.mock
async def test_run_builds_full_snapshot(caplog: pytest.LogCaptureFixture) -> None:
    _mock_endpoints()
    caplog.set_level(logging.WARNING, logger="yasli_scraper.pipeline")
    fixed = datetime(2026, 5, 6, 12, 0, 0, tzinfo=timezone.utc)

    snapshot = await run("varna", now=fixed)

    assert snapshot.schema_version == 2
    assert snapshot.city == "varna"
    assert snapshot.scraped_at == fixed
    assert len(snapshot.institutions) == len(PIPELINE_INSTITUTIONS) + 1

    by_id = {inst.external_id: inst for inst in snapshot.institutions}
    for reception, ext_id, _, name in PIPELINE_INSTITUTIONS:
        inst = by_id[ext_id]
        assert inst.kind == KIND_BY_RECEPTION[reception]
        assert inst.name == name
        assert str(inst.source_url) == _rajon_url(reception, ext_id)
        assert inst.address == DG_ADDRESSES[ext_id]
        assert inst.district_code is None
        assert inst.has_infant_group is False

    nursery = by_id["9001"]
    assert nursery.kind == "nursery"
    assert nursery.name == 'ДЯ №1 "Щастливо детство"'
    assert nursery.address == 'ул. "Славянска" 21'
    assert nursery.district_code == "01"
    assert nursery.address_entries == []
    assert nursery.has_infant_group is False

    total_rows = sum(len(i.address_entries) for i in snapshot.institutions)
    assert total_rows == EXPECTED_ROW_TOTAL
    assert "address_extraction_failed" not in caplog.text


@respx.mock
async def test_run_logs_address_extraction_failure_when_metadata_missing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    _mock_endpoints(include_metadata=False)
    caplog.set_level(logging.WARNING, logger="yasli_scraper.pipeline")

    snapshot = await run("varna")

    assert all(inst.address is None for inst in snapshot.institutions if inst.kind != "nursery")
    assert "address_extraction_failed=3" in caplog.text
    assert "external_id=39" in caplog.text


@respx.mock
async def test_run_unknown_city_raises() -> None:
    with pytest.raises(UnsupportedCityError):
        await run("sofia")


@respx.mock
async def test_run_aborts_on_persistent_fetch_failure() -> None:
    """Atomic semantics: if any institution HTML fails after retries, raise."""
    by_reception: dict[str, list[dict[str, str]]] = {
        rec: [] for rec in KIND_BY_RECEPTION
    }
    # Two healthy entries, one broken.
    healthy = [
        ("infant", "39", "infant_39.html", 'ДГ№6 "Палечко"'),
        ("garden", "34", "garden_34.html", 'ДГ№1 "Светулка"'),
    ]
    for reception, ext_id, fixture, name in healthy:
        url = _rajon_url(reception, ext_id)
        by_reception[reception].append({"DZ_NAME": name, "RAJON": url})
        respx.get(url).mock(
            return_value=httpx.Response(200, content=load_html(fixture))
        )
    # Broken pg entry — every retry returns 500.
    bad_url = _rajon_url("pg", "999")
    by_reception["pg"].append({"DZ_NAME": "broken", "RAJON": bad_url})
    respx.get(bad_url).mock(return_value=httpx.Response(500, content=b""))

    for reception, entries in by_reception.items():
        respx.post(
            f"{BASE_URL}{REGIONS_PATH}", json={"reception": reception}
        ).mock(
            return_value=httpx.Response(
                200,
                content=json.dumps({"childhoodRajon": entries}).encode(),
            )
        )
    _mock_empty_dg_metadata()
    _mock_jasla()

    with pytest.raises(Exception) as exc_info:
        await run("varna")
    assert "999" in str(exc_info.value) or "pg" in str(exc_info.value)


@respx.mock
async def test_run_aborts_on_parse_failure() -> None:
    """Atomic semantics: a malformed HTML aborts the whole run."""
    by_reception: dict[str, list[dict[str, str]]] = {
        rec: [] for rec in KIND_BY_RECEPTION
    }
    healthy = [
        ("infant", "39", "infant_39.html", 'ДГ№6 "Палечко"'),
        ("pg", "10", "pg_10.html", 'ОУ "Капитан Петко войвода"'),
    ]
    for reception, ext_id, fixture, name in healthy:
        url = _rajon_url(reception, ext_id)
        by_reception[reception].append({"DZ_NAME": name, "RAJON": url})
        respx.get(url).mock(
            return_value=httpx.Response(200, content=load_html(fixture))
        )
    # Malformed garden HTML — no street blocks.
    bad_url = _rajon_url("garden", "999")
    by_reception["garden"].append({"DZ_NAME": "broken", "RAJON": bad_url})
    respx.get(bad_url).mock(
        return_value=httpx.Response(200, content=b"<html><body>nothing</body></html>")
    )

    for reception, entries in by_reception.items():
        respx.post(
            f"{BASE_URL}{REGIONS_PATH}", json={"reception": reception}
        ).mock(
            return_value=httpx.Response(
                200,
                content=json.dumps({"childhoodRajon": entries}).encode(),
            )
        )
    _mock_empty_dg_metadata()
    _mock_jasla()

    with pytest.raises(Exception):
        await run("varna")


@respx.mock
async def test_run_aborts_on_jasla_http_failure() -> None:
    _mock_endpoints(include_jasla=False)
    respx.post(f"{JASLA_BASE_URL}{JASLA_CHILDHOOD_PATH}", json={"reception": "jasla"}).mock(
        return_value=httpx.Response(500, content=b"")
    )

    with pytest.raises(Exception):
        await run("varna")


def test_supported_cities_v2() -> None:
    assert SUPPORTED_CITIES == ("varna",)


@pytest.mark.parametrize(
    ("raw", "expected_marker", "expected_name"),
    [
        ('ДГ№6 "Палечко"/с яслена група/', True, 'ДГ№6 "Палечко"'),
        ('ДГ№6 "Палечко" / с яслена група/', True, 'ДГ№6 "Палечко"'),
        ('ДГ№1 "Светулка"', False, 'ДГ№1 "Светулка"'),
    ],
)
def test_normalise_reception_name_marker_variants(
    raw: str, expected_marker: bool, expected_name: str
) -> None:
    assert normalise_reception_name(raw) == (expected_marker, expected_name)


def test_coalesce_merges_by_external_id_and_kind() -> None:
    first = Institution(
        external_id="39",
        name='ДГ№6 "Палечко"',
        kind="kindergarten",
        source_url="https://example.com/39",
        address_entries=[AddressEntry(street="ул. А", number="1")],
        address=None,
        district_code=None,
        has_infant_group=False,
    )
    second = Institution(
        external_id="39",
        name='ДГ№6 "Палечко"',
        kind="kindergarten",
        source_url="https://example.com/39",
        address_entries=[
            AddressEntry(street="ул. А", number="1"),
            AddressEntry(street="ул. Б", number="2"),
        ],
        address="ул. Извор 3",
        district_code=None,
        has_infant_group=True,
    )

    merged = coalesce_institutions([first, second])

    assert len(merged) == 1
    assert merged[0].address == "ул. Извор 3"
    assert merged[0].has_infant_group is True
    assert [(row.street, row.number) for row in merged[0].address_entries] == [
        ("ул. А", "1"),
        ("ул. Б", "2"),
    ]
