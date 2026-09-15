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


def _metadata_payload(*rows: dict[str, object]) -> bytes:
    return json.dumps({"childhood": list(rows)}).encode()


async def _fetch_metadata(
    *rows: dict[str, object], reception: str = "garden"
) -> dict[str, InstitutionMetadata]:
    with respx.mock:
        respx.post(f"{BASE_URL}{CHILDHOOD_PATH}").mock(
            return_value=httpx.Response(200, content=_metadata_payload(*rows))
        )
        async with httpx.AsyncClient() as client:
            return await fetch_institution_metadata(client, reception)


# Verbatim row from the live `garden` reception (DZ_ID 34), captured 2026-09-15.
LIVE_GARDEN_ROW: dict[str, object] = {
    "DZ_ID": "34",
    "DZ_ID_VI": "10",
    "OBSHTINA_CODE": "0306",
    "VID": "3",
    "DZ_NUMBER": "33",
    "DZ_NAME": 'ДГ№1 "Светулка"',
    "NASME": None,
    "ADDRESS": 'гр. Варна, ул."Парижка комуна" №25\r\n',
    "NAME_D": "Катя Григорова ",
    "NAME_S": None,
    "NAME_K": None,
    "TEL": "052/613039",
    "EMAIL": "info-400240@edu.mon.bg\r\n",
    "DZ_ID_KIDS": "34",
    "RAJON": None,
    "DZ_ID_ADMIN": None,
    "DATE_ZAPIS_ADMIN": None,
    "DZ_NAME_ADMIN": None,
    "RAJON_ID": "1",
    "HAVE_INFANT_GROUP": False,
    "WEBSITE": None,
    "IS_ACTIVE": "1",
}


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
            content=_metadata_payload(
                {"DZ_ID": "39", "ADDRESS": " гр. Варна,\r\n ул. \"Тодор Влайков\"  №71 "}
            ),
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


async def test_fetch_institution_metadata_keeps_contacts_from_live_garden_row() -> None:
    metadata = await _fetch_metadata(LIVE_GARDEN_ROW)

    assert metadata == {
        "34": InstitutionMetadata(
            external_id="34",
            address='гр. Варна, ул."Парижка комуна" №25',
            phone="052/613039",
            email="info-400240@edu.mon.bg",
            director="Катя Григорова",
            website=None,
        )
    }


async def test_fetch_institution_metadata_collapses_whitespace_in_all_contacts() -> None:
    metadata = await _fetch_metadata(
        {
            "DZ_ID": "7",
            "ADDRESS": '9009, бул."Вл.Варненчик"№225',
            "TEL": " 052/740   659 ",
            "EMAIL": "\tinfo@example.bg\r\n",
            "NAME_D": "Димитър\t\tДимитров ",
            "WEBSITE": " https://ou-ivanrilski.com/ ",
        },
        reception="pg",
    )

    assert metadata["7"] == InstitutionMetadata(
        external_id="7",
        address='9009, бул."Вл.Варненчик"№225',
        phone="052/740 659",
        email="info@example.bg",
        director="Димитър Димитров",
        website="https://ou-ivanrilski.com/",
    )


async def test_fetch_institution_metadata_strips_website_line_ending_tail() -> None:
    # Verbatim WEBSITE value from the live `pg` reception (DZ_ID 7).
    metadata = await _fetch_metadata(
        {"DZ_ID": "7", "WEBSITE": "https://ou-ivanrilski.com/\r\r\n"}, reception="pg"
    )

    website = metadata["7"].website
    assert website == "https://ou-ivanrilski.com/"
    assert website == website.strip()
    assert "\r" not in website


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("052/613039", "052/613039"),
        ("052/613039\t0885 123 456", "052/613039 0885 123 456"),
        ("0885/665-940  052/820-764", "0885/665-940 052/820-764"),
        ("052/613039 / 052/613040", "052/613039 / 052/613040"),
        ("\t052 820758 0885665404", "052 820758 0885665404"),
    ],
    ids=["single", "tab-separated", "double-space", "slash-separated", "leading-tab"],
)
async def test_fetch_institution_metadata_keeps_phone_separators(raw: str, expected: str) -> None:
    metadata = await _fetch_metadata({"DZ_ID": "1", "TEL": raw})

    assert metadata["1"].phone == expected


@pytest.mark.parametrize(
    "row",
    [
        {"DZ_ID": "1"},
        {"DZ_ID": "1", "TEL": None, "EMAIL": None, "NAME_D": None, "WEBSITE": None},
        {"DZ_ID": "1", "TEL": "  ", "EMAIL": "\t", "NAME_D": "\r\n", "WEBSITE": ""},
    ],
    ids=["keys-absent", "explicit-null", "whitespace-only"],
)
async def test_fetch_institution_metadata_empty_contacts_are_none(
    row: dict[str, object],
) -> None:
    metadata = await _fetch_metadata(row)

    entry = metadata["1"]
    assert entry.phone is None
    assert entry.email is None
    assert entry.director is None
    assert entry.website is None


async def test_fetch_institution_metadata_skips_rows_without_dz_id() -> None:
    metadata = await _fetch_metadata(
        {"ADDRESS": "no id", "TEL": "052/000000"},
        {"DZ_ID": "  ", "TEL": "052/000000"},
        {"DZ_ID": "39", "TEL": "052/613130"},
    )

    assert list(metadata) == ["39"]
