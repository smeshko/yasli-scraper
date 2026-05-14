from __future__ import annotations

import json

import httpx
import pytest
import respx

from yasli_scraper.source_jasla import (
    BASE_URL,
    CHILDHOOD_PATH,
    JaslaPayloadError,
    fetch_jasla,
    parse_jasla_payload,
)


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _instant(_seconds: float) -> None:
        return None

    monkeypatch.setattr("yasli_scraper.http.asyncio.sleep", _instant)


def _payload(**overrides: object) -> bytes:
    record = {
        "DZ_ID": "9001",
        "DZ_NAME": "  ДЯ №1 „ Щастливо детство “ ",
        "ADDRESS": " ул.  \"Славянска\"   21 ",
        "RAJON_ID": "1",
        "RAJON": "01",
    } | overrides
    return json.dumps({"childhood": [record]}).encode()


def test_parse_jasla_payload_normalises_contract_fields() -> None:
    records = parse_jasla_payload(_payload())

    assert len(records) == 1
    record = records[0]
    assert record.external_id == "9001"
    assert record.name == 'ДЯ №1 "Щастливо детство"'
    assert record.address == 'ул. "Славянска" 21'
    assert record.district_code == "01"
    assert record.source_url == "https://newkg.uslugi.io/jasla/childhood?reception=jasla"


def test_parse_jasla_payload_maps_rajon_id_when_code_absent() -> None:
    records = parse_jasla_payload(_payload(RAJON=None, RAJON_ID="10"))

    assert records[0].district_code == "05"


def test_parse_jasla_payload_rejects_unknown_district() -> None:
    with pytest.raises(JaslaPayloadError, match="RAJON_ID"):
        parse_jasla_payload(_payload(RAJON=None, RAJON_ID="99"))


def test_parse_jasla_payload_rejects_conflicting_districts() -> None:
    with pytest.raises(JaslaPayloadError, match="conflicting"):
        parse_jasla_payload(_payload(RAJON="02", RAJON_ID="1"))


@respx.mock
async def test_fetch_jasla_posts_expected_request() -> None:
    route = respx.post(f"{BASE_URL}{CHILDHOOD_PATH}", json={"reception": "jasla"}).mock(
        return_value=httpx.Response(200, content=_payload())
    )

    async with httpx.AsyncClient() as client:
        records = await fetch_jasla(client)

    assert route.call_count == 1
    assert records[0].external_id == "9001"
