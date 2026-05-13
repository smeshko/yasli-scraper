from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from yasli_scraper.models import Snapshot
from yasli_scraper.snapshot import SCHEMA_VERSION, build_stub

ISO_Z_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _stub_dict(city: str = "varna", now: datetime | None = None) -> dict:
    return json.loads(build_stub(city, now=now).model_dump_json())


def test_stub_returns_snapshot_instance() -> None:
    assert isinstance(build_stub("varna"), Snapshot)


def test_stub_has_required_keys() -> None:
    payload = _stub_dict()
    assert set(payload.keys()) == {"schema_version", "scraped_at", "city", "institutions"}


def test_stub_schema_version_is_two() -> None:
    payload = _stub_dict()
    assert payload["schema_version"] == SCHEMA_VERSION == 2


def test_stub_city_matches_argument() -> None:
    assert _stub_dict("varna")["city"] == "varna"
    assert _stub_dict("sofia")["city"] == "sofia"


def test_stub_institutions_is_empty_list() -> None:
    payload = _stub_dict()
    assert payload["institutions"] == []
    assert isinstance(payload["institutions"], list)


def test_stub_scraped_at_is_iso_z() -> None:
    payload = _stub_dict()
    assert ISO_Z_RE.match(payload["scraped_at"]) is not None


def test_stub_scraped_at_uses_supplied_time() -> None:
    fixed = datetime(2026, 5, 6, 12, 30, 45, tzinfo=timezone.utc)
    payload = _stub_dict("varna", now=fixed)
    assert payload["scraped_at"] == "2026-05-06T12:30:45Z"


def test_stub_field_types() -> None:
    payload = _stub_dict()
    assert isinstance(payload["schema_version"], int)
    assert isinstance(payload["scraped_at"], str)
    assert isinstance(payload["city"], str)
    assert isinstance(payload["institutions"], list)


def test_stub_round_trips_through_model_validate_json() -> None:
    fixed = datetime(2026, 5, 6, 12, 30, 45, tzinfo=timezone.utc)
    original = build_stub("varna", now=fixed)
    rehydrated = Snapshot.model_validate_json(original.model_dump_json())
    assert rehydrated == original
