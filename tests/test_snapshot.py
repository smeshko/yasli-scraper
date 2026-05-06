from __future__ import annotations

import re
from datetime import datetime, timezone

from yasli_scraper.snapshot import SCHEMA_VERSION, build_stub

ISO_Z_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def test_stub_has_required_keys() -> None:
    stub = build_stub("varna")
    assert set(stub.keys()) == {"schema_version", "scraped_at", "city", "institutions"}


def test_stub_schema_version_is_one() -> None:
    stub = build_stub("varna")
    assert stub["schema_version"] == SCHEMA_VERSION == 1


def test_stub_city_matches_argument() -> None:
    assert build_stub("varna")["city"] == "varna"
    assert build_stub("sofia")["city"] == "sofia"


def test_stub_institutions_is_empty_list() -> None:
    stub = build_stub("varna")
    assert stub["institutions"] == []
    assert isinstance(stub["institutions"], list)


def test_stub_scraped_at_is_iso_z() -> None:
    stub = build_stub("varna")
    assert ISO_Z_RE.match(stub["scraped_at"]) is not None


def test_stub_scraped_at_uses_supplied_time() -> None:
    fixed = datetime(2026, 5, 6, 12, 30, 45, tzinfo=timezone.utc)
    stub = build_stub("varna", now=fixed)
    assert stub["scraped_at"] == "2026-05-06T12:30:45Z"


def test_stub_field_types() -> None:
    stub = build_stub("varna")
    assert isinstance(stub["schema_version"], int)
    assert isinstance(stub["scraped_at"], str)
    assert isinstance(stub["city"], str)
    assert isinstance(stub["institutions"], list)
