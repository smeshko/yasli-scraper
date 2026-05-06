from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
import pytest
import respx

from yasli_scraper.pipeline import (
    KIND_BY_RECEPTION,
    SUPPORTED_CITIES,
    UnsupportedCityError,
    run,
)
from yasli_scraper.source import BASE_URL, REGIONS_PATH

from .fixtures import load_html

# (reception, external_id, fixture_filename, dz_name)
PIPELINE_INSTITUTIONS = [
    ("infant", "39", "infant_39.html", 'ДГ№6 "Палечко"'),
    ("garden", "34", "garden_34.html", 'ДГ№1 "Светулка"'),
    ("pg", "10", "pg_10.html", 'ОУ "Капитан Петко войвода"'),
]

EXPECTED_ROW_TOTAL = 4503 + 4497 + 8222


def _rajon_url(reception: str, ext_id: str) -> str:
    return f"{BASE_URL}/lv/documents/{reception}/varna/rajon/{ext_id}.html"


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _instant(_seconds: float) -> None:
        return None

    monkeypatch.setattr("yasli_scraper.http.asyncio.sleep", _instant)


def _mock_endpoints() -> None:
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


@respx.mock
async def test_run_builds_full_snapshot() -> None:
    _mock_endpoints()
    fixed = datetime(2026, 5, 6, 12, 0, 0, tzinfo=timezone.utc)

    snapshot = await run("varna", now=fixed)

    assert snapshot.schema_version == 1
    assert snapshot.city == "varna"
    assert snapshot.scraped_at == fixed
    assert len(snapshot.institutions) == len(PIPELINE_INSTITUTIONS)

    by_id = {inst.external_id: inst for inst in snapshot.institutions}
    for reception, ext_id, _, name in PIPELINE_INSTITUTIONS:
        inst = by_id[ext_id]
        assert inst.kind == KIND_BY_RECEPTION[reception]
        assert inst.name == name
        assert str(inst.source_url) == _rajon_url(reception, ext_id)

    total_rows = sum(len(i.address_entries) for i in snapshot.institutions)
    assert total_rows == EXPECTED_ROW_TOTAL


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

    with pytest.raises(Exception):
        await run("varna")


def test_supported_cities_v1() -> None:
    assert SUPPORTED_CITIES == ("varna",)
