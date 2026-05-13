from __future__ import annotations

import json

import httpx
import pytest
import respx

from yasli_scraper.source import (
    BASE_URL,
    CHILDHOOD_PATH,
    RECEPTIONS,
    REGIONS_PATH,
    InstitutionMetadata,
    InstitutionStub,
    fetch_html,
    fetch_institution_metadata,
    fetch_regions,
)


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _instant(_seconds: float) -> None:
        return None

    monkeypatch.setattr("yasli_scraper.http.asyncio.sleep", _instant)


def _regions_payload(name: str, url: str) -> bytes:
    return json.dumps(
        {"childhoodRajon": [{"DZ_NAME": name, "RAJON": url}]}
    ).encode()


def _metadata_payload(external_id: str, address: str) -> bytes:
    return json.dumps(
        {"childhood": [{"DZ_ID": external_id, "ADDRESS": address}]}
    ).encode()


@respx.mock
async def test_fetch_regions_parses_entries() -> None:
    body = _regions_payload(
        "ДГ№6 \"Палечко\"",
        "https://dg.uslugi.io/lv/documents/infant/varna/rajon/39.html",
    )
    route = respx.post(f"{BASE_URL}{REGIONS_PATH}").mock(
        return_value=httpx.Response(200, content=body)
    )
    async with httpx.AsyncClient() as client:
        stubs = await fetch_regions(client, "infant")
    sent = route.calls.last.request
    assert sent.method == "POST"
    assert json.loads(sent.content) == {"reception": "infant"}
    assert stubs == [
        InstitutionStub(
            name="ДГ№6 \"Палечко\"",
            source_url="https://dg.uslugi.io/lv/documents/infant/varna/rajon/39.html",
        )
    ]


@respx.mock
async def test_fetch_institution_metadata_parses_addresses() -> None:
    route = respx.post(f"{BASE_URL}{CHILDHOOD_PATH}").mock(
        return_value=httpx.Response(
            200,
            content=_metadata_payload("39", " гр. Варна,\r\n ул. \"Тодор Влайков\"  №71 "),
        )
    )

    async with httpx.AsyncClient() as client:
        metadata = await fetch_institution_metadata(client, "garden")

    sent = route.calls.last.request
    assert sent.method == "POST"
    assert json.loads(sent.content) == {"reception": "garden"}
    assert metadata == {
        "39": InstitutionMetadata(
            external_id="39",
            address='гр. Варна, ул. "Тодор Влайков" №71',
        )
    }


@respx.mock
async def test_fetch_regions_handles_all_three_receptions() -> None:
    routes = {}
    for rec in RECEPTIONS:
        routes[rec] = respx.post(f"{BASE_URL}{REGIONS_PATH}", json={"reception": rec}).mock(
            return_value=httpx.Response(
                200,
                content=_regions_payload(
                    f"name-{rec}",
                    f"https://dg.uslugi.io/lv/documents/{rec}/varna/rajon/1.html",
                ),
            )
        )
    async with httpx.AsyncClient() as client:
        results = {rec: await fetch_regions(client, rec) for rec in RECEPTIONS}
    for rec in RECEPTIONS:
        assert routes[rec].call_count == 1
        assert results[rec][0].name == f"name-{rec}"


@respx.mock
async def test_fetch_regions_strips_dz_name_whitespace() -> None:
    body = _regions_payload(
        "  ДГ№9   ",
        "https://dg.uslugi.io/lv/documents/garden/varna/rajon/41.html",
    )
    respx.post(f"{BASE_URL}{REGIONS_PATH}").mock(
        return_value=httpx.Response(200, content=body)
    )
    async with httpx.AsyncClient() as client:
        stubs = await fetch_regions(client, "garden")
    assert stubs[0].name == "ДГ№9"


@respx.mock
async def test_fetch_html_returns_bytes() -> None:
    target = "https://dg.uslugi.io/lv/documents/garden/varna/rajon/34.html"
    respx.get(target).mock(
        return_value=httpx.Response(200, content=b"<html>raw</html>")
    )
    async with httpx.AsyncClient() as client:
        body = await fetch_html(client, target)
    assert body == b"<html>raw</html>"
