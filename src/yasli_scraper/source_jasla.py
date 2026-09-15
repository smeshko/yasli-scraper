"""Client and parser for standalone nursery records from newkg.uslugi.io."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, cast

import httpx

from yasli_scraper.http import fetch
from yasli_scraper.models import DistrictCode

BASE_URL = "https://newkg.uslugi.io"
CHILDHOOD_PATH = "/lv/api/childhood"
JASLA_LISTING_URL = f"{BASE_URL}/jasla/childhood?reception=jasla"

DISTRICT_CODE_BY_RAJON_ID: dict[str, DistrictCode] = {
    "1": "01",  # Одесос
    "4": "02",  # Приморски
    "5": "03",  # Младост
    "6": "04",  # Владислав Варненчик
    "10": "05",  # Аспарухово
}
DISTRICT_CODE_BY_NAME: dict[str, DistrictCode] = {
    "одесос": "01",
    "приморски": "02",
    "младост": "03",
    "владислав варненчик": "04",
    "аспарухово": "05",
}
VALID_DISTRICT_CODES = {"01", "02", "03", "04", "05"}
_WHITESPACE = re.compile(r"\s+")
_SMART_QUOTES = str.maketrans({"„": '"', "“": '"', "”": '"', "‟": '"'})


class JaslaPayloadError(ValueError):
    """Raised when the standalone nursery payload is not understood."""


@dataclass(frozen=True)
class JaslaRecord:
    """One standalone nursery from the ``jasla`` reception.

    ``address`` and the four contact fields are whitespace-collapsed only
    (see :func:`_normalise_optional_text`); a blank source value is ``None``.
    Contacts deliberately skip :func:`_normalise_name`'s smart-quote
    translation, which exists for institution titles alone.
    """

    external_id: str
    name: str
    source_url: str
    address: str | None
    district_code: DistrictCode
    phone: str | None = None
    email: str | None = None
    director: str | None = None
    website: str | None = None


async def fetch_jasla(client: httpx.AsyncClient) -> list[JaslaRecord]:
    """Fetch and parse the standalone nursery payload."""

    body = await fetch(
        client,
        "POST",
        f"{BASE_URL}{CHILDHOOD_PATH}",
        json={"reception": "jasla"},
    )
    return parse_jasla_payload(body)


def parse_jasla_payload(raw: bytes) -> list[JaslaRecord]:
    """Parse standalone nursery JSON records from newkg.uslugi.io."""

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise JaslaPayloadError("standalone nursery payload is not valid JSON") from exc

    parsed: list[JaslaRecord] = []
    for index, record in enumerate(_extract_records(payload)):
        if not isinstance(record, dict):
            raise JaslaPayloadError(f"standalone nursery record {index} is not an object")

        external_id = _required_text(record, "DZ_ID")
        parsed.append(
            JaslaRecord(
                external_id=external_id,
                name=_normalise_name(_required_text(record, "DZ_NAME")),
                source_url=JASLA_LISTING_URL,
                address=_normalise_optional_text(record.get("ADDRESS")),
                district_code=_district_code(record),
                phone=_normalise_optional_text(record.get("TEL")),
                email=_normalise_optional_text(record.get("EMAIL")),
                director=_normalise_optional_text(record.get("NAME_D")),
                website=_normalise_optional_text(record.get("WEBSITE")),
            )
        )

    return parsed


def _extract_records(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("childhood", "childhoods", "data", "records", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        if {"DZ_ID", "DZ_NAME"}.issubset(payload):
            return [payload]
    raise JaslaPayloadError("standalone nursery payload did not contain a record list")


def _required_text(record: dict[str, Any], field: str) -> str:
    value = record.get(field)
    if value is None:
        raise JaslaPayloadError(f"standalone nursery record missing {field}")
    text = _collapse_ws(str(value))
    if text == "":
        raise JaslaPayloadError(f"standalone nursery record has empty {field}")
    return text


def _normalise_name(value: str) -> str:
    name = _collapse_ws(value.translate(_SMART_QUOTES))
    name = re.sub(r'"\s+', '"', name)
    return re.sub(r'\s+"(?=\s|$)', '"', name)


def _normalise_optional_text(value: Any) -> str | None:
    """Collapse whitespace; ``None`` or blank becomes ``None``, never ``""``.

    Unlike :func:`_required_text` this never raises — contacts and the address
    are optional. The ``None`` guard precedes ``str()`` because ``str(None)``
    is the non-empty string ``"None"``.
    """
    if value is None:
        return None
    text = _collapse_ws(str(value))
    return text or None


def _district_code(record: dict[str, Any]) -> DistrictCode:
    codes: list[DistrictCode] = []

    rajon = record.get("RAJON")
    if rajon is not None and _collapse_ws(str(rajon)) != "":
        code = _district_code_from_rajon(str(rajon))
        if code is None:
            raise JaslaPayloadError(f"unknown RAJON value {rajon!r}")
        codes.append(code)

    rajon_id = record.get("RAJON_ID")
    if rajon_id is not None and _collapse_ws(str(rajon_id)) != "":
        code = DISTRICT_CODE_BY_RAJON_ID.get(_collapse_ws(str(rajon_id)))
        if code is None:
            raise JaslaPayloadError(f"unknown RAJON_ID value {rajon_id!r}")
        codes.append(code)

    if not codes:
        raise JaslaPayloadError("standalone nursery record missing RAJON/RAJON_ID")
    if len(set(codes)) > 1:
        raise JaslaPayloadError(f"conflicting district values {codes!r}")
    return codes[0]


def _district_code_from_rajon(value: str) -> DistrictCode | None:
    rajon = _collapse_ws(value)
    if rajon in VALID_DISTRICT_CODES:
        return cast(DistrictCode, rajon)
    return DISTRICT_CODE_BY_NAME.get(rajon.lower())


def _collapse_ws(value: str) -> str:
    return _WHITESPACE.sub(" ", value).strip()
