"""Validation regression tests for the v1 snapshot Pydantic models."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from yasli_scraper.models import AddressEntry, Institution, Snapshot


def _valid_institution_kwargs() -> dict[str, Any]:
    return {
        "external_id": "39",
        "name": 'ДГ №7 "Изгрев"',
        "kind": "kindergarten",
        "source_url": "https://example.com/dz/39",
        "address_entries": [AddressEntry(street="ул.Орех", number="12")],
    }


def _valid_snapshot_kwargs() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "scraped_at": datetime(2026, 5, 6, 12, 30, 45, tzinfo=timezone.utc),
        "city": "varna",
        "institutions": [Institution(**_valid_institution_kwargs())],
    }


def test_valid_snapshot_constructs() -> None:
    Snapshot(**_valid_snapshot_kwargs())


# --- 4.1 missing required field ---

def test_missing_schema_version_raises() -> None:
    kwargs = _valid_snapshot_kwargs()
    del kwargs["schema_version"]
    with pytest.raises(ValidationError, match="schema_version"):
        Snapshot(**kwargs)


def test_missing_scraped_at_raises() -> None:
    kwargs = _valid_snapshot_kwargs()
    del kwargs["scraped_at"]
    with pytest.raises(ValidationError, match="scraped_at"):
        Snapshot(**kwargs)


def test_missing_city_raises() -> None:
    kwargs = _valid_snapshot_kwargs()
    del kwargs["city"]
    with pytest.raises(ValidationError, match="city"):
        Snapshot(**kwargs)


def test_missing_institutions_raises() -> None:
    kwargs = _valid_snapshot_kwargs()
    del kwargs["institutions"]
    with pytest.raises(ValidationError, match="institutions"):
        Snapshot(**kwargs)


def test_missing_institution_field_raises() -> None:
    kwargs = _valid_institution_kwargs()
    del kwargs["external_id"]
    with pytest.raises(ValidationError, match="external_id"):
        Institution(**kwargs)


def test_missing_address_entry_field_raises() -> None:
    with pytest.raises(ValidationError, match="number"):
        AddressEntry(street="ул.Орех")  # type: ignore[call-arg]


# --- 4.2 extra field (strict mode) ---

def test_extra_field_on_snapshot_raises() -> None:
    kwargs = _valid_snapshot_kwargs() | {"unexpected": "value"}
    with pytest.raises(ValidationError, match="unexpected"):
        Snapshot(**kwargs)


def test_extra_field_on_institution_raises() -> None:
    kwargs = _valid_institution_kwargs() | {"priority_class": "E"}
    with pytest.raises(ValidationError, match="priority_class"):
        Institution(**kwargs)


def test_extra_field_on_address_entry_raises() -> None:
    with pytest.raises(ValidationError, match="city"):
        AddressEntry(street="ул.Орех", number="12", city="varna")  # type: ignore[call-arg]


# --- 4.3 unknown kind ---

def test_unknown_kind_raises() -> None:
    kwargs = _valid_institution_kwargs() | {"kind": "school"}
    with pytest.raises(ValidationError, match="kind"):
        Institution(**kwargs)


# --- 4.4 malformed datetime ---

def test_malformed_datetime_raises() -> None:
    kwargs = _valid_snapshot_kwargs() | {"scraped_at": "not-a-date"}
    with pytest.raises(ValidationError, match="scraped_at"):
        Snapshot(**kwargs)


def test_naive_datetime_raises() -> None:
    """AwareDatetime requires a tzinfo — a naive datetime must be rejected."""
    kwargs = _valid_snapshot_kwargs() | {"scraped_at": datetime(2026, 5, 6, 12, 30, 45)}
    with pytest.raises(ValidationError, match="scraped_at"):
        Snapshot(**kwargs)


# --- 4.5 non-HTTPS source_url ---

def test_http_source_url_raises() -> None:
    kwargs = _valid_institution_kwargs() | {"source_url": "http://example.com/dz/39"}
    with pytest.raises(ValidationError, match="source_url"):
        Institution(**kwargs)


def test_non_url_source_url_raises() -> None:
    kwargs = _valid_institution_kwargs() | {"source_url": "not a url"}
    with pytest.raises(ValidationError, match="source_url"):
        Institution(**kwargs)


# --- 4.6 schema_version other than 1 ---

def test_schema_version_two_raises() -> None:
    kwargs = _valid_snapshot_kwargs() | {"schema_version": 2}
    with pytest.raises(ValidationError, match="schema_version"):
        Snapshot(**kwargs)


def test_schema_version_string_raises() -> None:
    kwargs = _valid_snapshot_kwargs() | {"schema_version": "1"}
    with pytest.raises(ValidationError, match="schema_version"):
        Snapshot(**kwargs)
