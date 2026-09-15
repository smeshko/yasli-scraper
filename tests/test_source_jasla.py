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


CONTACT_KEYS = ("TEL", "EMAIL", "NAME_D", "WEBSITE")

# Verbatim row from the live `jasla` reception (DZ_ID 4), captured 2026-09-15.
LIVE_JASLA_ROW: dict[str, object] = {
    "DZ_ID": "4",
    "DZ_ID_VI": "40",
    "OBSHTINA_CODE": "0306",
    "VID": "1",
    "DZ_NUMBER": "4",
    "DZ_NAME": "ДЯ № 4 “Приказен свят” ",
    "NASME": None,
    "ADDRESS": "бул. \"Чаталджа\" 111",
    "NAME_D": "Маргарита Георгиева",
    "NAME_S": None,
    "NAME_K": None,
    "TEL": "\t052 820758 0885665404",
    "EMAIL": "prikazen4@mail.bg",
    "DZ_ID_KIDS": "4",
    "RAJON": "02",
    "DZ_ID_ADMIN": "0",
    "DATE_ZAPIS_ADMIN": None,
    "DZ_NAME_ADMIN": None,
    "RAJON_ID": "4",
    "HAVE_INFANT_GROUP": False,
    "WEBSITE": "",
    "IS_ACTIVE": "1",
}


def _record(**overrides: object) -> dict[str, object]:
    return {
        "DZ_ID": "9001",
        "DZ_NAME": "  ДЯ №1 „ Щастливо детство “ ",
        "ADDRESS": " ул.  \"Славянска\"   21 ",
        "RAJON_ID": "1",
        "RAJON": "01",
        "TEL": "\t052 820758\t0885665404 ",
        "EMAIL": " prikazen4@mail.bg\r\n",
        "NAME_D": " Маргарита  Георгиева ",
        "WEBSITE": "",
    } | overrides


def _encode(*records: dict[str, object]) -> bytes:
    return json.dumps({"childhood": list(records)}).encode()


def _payload(**overrides: object) -> bytes:
    return _encode(_record(**overrides))


def test_parse_jasla_payload_normalises_contract_fields() -> None:
    records = parse_jasla_payload(_payload())

    assert len(records) == 1
    record = records[0]
    assert record.external_id == "9001"
    assert record.name == 'ДЯ №1 "Щастливо детство"'
    assert record.address == 'ул. "Славянска" 21'
    assert record.district_code == "01"
    assert record.source_url == "https://newkg.uslugi.io/jasla/childhood?reception=jasla"
    assert record.phone == "052 820758 0885665404"
    assert record.email == "prikazen4@mail.bg"
    assert record.director == "Маргарита Георгиева"
    assert record.website is None


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


def test_parse_jasla_payload_keeps_contacts_from_live_row() -> None:
    record = parse_jasla_payload(_encode(LIVE_JASLA_ROW))[0]

    assert record.external_id == "4"
    assert record.name == 'ДЯ № 4 "Приказен свят"'
    assert record.address == 'бул. "Чаталджа" 111'
    assert record.district_code == "02"
    assert record.phone == "052 820758 0885665404"
    assert record.email == "prikazen4@mail.bg"
    assert record.director == "Маргарита Георгиева"
    assert record.website is None


def test_parse_jasla_payload_keeps_phone_separators() -> None:
    # Verbatim TEL from the live `jasla` reception (DZ_ID 11): slashes and
    # hyphens stay, the double space collapses.
    record = parse_jasla_payload(_payload(TEL="0885/665-940  052/820-764"))[0]

    assert record.phone == "0885/665-940 052/820-764"


def _contacts_absent() -> dict[str, object]:
    record = _record()
    for key in CONTACT_KEYS:
        del record[key]
    return record


@pytest.mark.parametrize(
    "record",
    [
        _contacts_absent(),
        _record(TEL=None, EMAIL=None, NAME_D=None, WEBSITE=None),
        _record(TEL="  ", EMAIL="\t", NAME_D="\r\n", WEBSITE=""),
    ],
    ids=["keys-absent", "explicit-null", "whitespace-only"],
)
def test_parse_jasla_payload_empty_contacts_are_none(record: dict[str, object]) -> None:
    parsed = parse_jasla_payload(_encode(record))[0]

    assert parsed.external_id == "9001"
    assert parsed.phone is None
    assert parsed.email is None
    assert parsed.director is None
    assert parsed.website is None


def test_parse_jasla_payload_contacts_bypass_smart_quote_translation() -> None:
    record = parse_jasla_payload(
        _payload(DZ_NAME="ДЯ №2 „Мечо Пух“", NAME_D="Мария „Мими“ Иванова")
    )[0]

    assert record.name == 'ДЯ №2 "Мечо Пух"'
    assert record.director == "Мария „Мими“ Иванова"


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"DZ_ID": None}, "DZ_ID"),
        ({"DZ_NAME": "  "}, "DZ_NAME"),
        ({"RAJON": None, "RAJON_ID": None}, "RAJON"),
    ],
    ids=["missing-dz-id", "empty-dz-name", "missing-district"],
)
def test_parse_jasla_payload_required_fields_still_raise(
    overrides: dict[str, object], match: str
) -> None:
    record = _contacts_absent() | overrides

    with pytest.raises(JaslaPayloadError, match=match):
        parse_jasla_payload(_encode(record))
