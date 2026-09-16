"""Tests for the snapshot check module: contract, key presence, roster, coverage, noise.

Fixtures are plain dicts (not models) so keys can be deleted and leaves can
take any JSON type; ``_raw`` serialises them to the bytes ``check_snapshot``
reads. ``_varna_roster`` builds the 77 rows that match ``EXPECTED_ROSTER["varna"]``.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest

from yasli_scraper.check import CONTACT_FIELDS, EXPECTED_ROSTER, check_snapshot
from yasli_scraper.models import Snapshot

INFANT_MARKER_NAME = 'ДГ №6 "Палечко"'
LONG_PHONE = "052/613039, 0888123456"


def _institution(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "external_id": "39",
        "name": 'ДГ №7 "Изгрев"',
        "kind": "kindergarten",
        "source_url": "https://example.com/dz/39",
        "address_entries": [{"street": "ул.Орех", "number": "12"}],
        "address": "ул. Тестова 1",
        "phone": "052/613039",
        "email": "info-400240@edu.mon.bg",
        "director": "Катя Григорова",
        "website": None,
        "district_code": None,
        "has_infant_group": False,
    }
    return base | overrides


def _varna_roster() -> list[dict[str, Any]]:
    """77 rows matching EXPECTED_ROSTER["varna"] (12 / 53 / 12), marker included.

    Nursery and kindergarten ids deliberately overlap ("1".."12") — identity
    is (kind, external_id), and the same id under two kinds is legitimate.
    """
    roster = EXPECTED_ROSTER["varna"]
    rows: list[dict[str, Any]] = []
    for i in range(1, roster.nurseries + 1):
        rows.append(
            _institution(
                external_id=str(i),
                name=f"ДЯ №{i}",
                kind="nursery",
                source_url=f"https://example.com/dy/{i}",
                district_code=f"0{i % 5 + 1}",
                phone=LONG_PHONE if i == 1 else "052/613039",
            )
        )
    for i in range(1, roster.kindergartens + 1):
        rows.append(
            _institution(
                external_id=str(i),
                name=INFANT_MARKER_NAME if i == 6 else f'ДГ №{i} "Тест"',
                kind="kindergarten",
                source_url=f"https://example.com/dz/{i}",
                has_infant_group=i == 6 or i % 10 == 0,
            )
        )
    for i in range(1, roster.preschools + 1):
        rows.append(
            _institution(
                external_id=f"pg{i}",
                name=f"ОУ №{i}",
                kind="preschool",
                source_url=f"https://example.com/pg/{i}",
                website=f"https://school{i}.example.com/",
            )
        )
    return rows


def _snapshot(institutions: Any = None, **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": 2,
        "scraped_at": "2026-09-15T13:05:33Z",
        "city": "varna",
        "institutions": _varna_roster() if institutions is None else institutions,
    }
    return base | overrides


def _raw(snapshot: Any) -> bytes:
    return json.dumps(snapshot, ensure_ascii=False).encode("utf-8")


def _first(rows: list[dict[str, Any]], kind: str) -> dict[str, Any]:
    return next(r for r in rows if r["kind"] == kind)


def _with_prefix(failures: list[str], prefix: str) -> list[str]:
    return [f for f in failures if f.startswith(prefix)]


VALID_SUMMARY = {
    "schema_version": 2,
    "city": "varna",
    "total": 77,
    "kinds": {"nursery": 12, "kindergarten": 53, "preschool": 12},
    "infant_group": 6,
    "null_address": 0,
    "null_phone": 0,
    "null_email": 0,
    "null_director": 0,
    "preschool_null_website": 0,
    "noisy_values": 0,
    "max_phone_length": len(LONG_PHONE),
}


# --- valid fixture ---

def test_valid_fixture_satisfies_the_contract() -> None:
    Snapshot.model_validate(_snapshot())


def test_valid_snapshot_is_ok_with_exact_summary() -> None:
    report = check_snapshot(_raw(_snapshot()))
    assert report.failures == []
    assert report.ok
    assert report.summary == VALID_SUMMARY


# --- unparseable bytes ---

def test_invalid_json_is_one_failure() -> None:
    report = check_snapshot(b"{not json")
    assert len(report.failures) == 1
    assert "invalid JSON" in report.failures[0]
    assert not report.ok


def test_invalid_utf8_is_one_failure() -> None:
    report = check_snapshot(b"\xff{")
    assert len(report.failures) == 1
    assert "invalid UTF-8" in report.failures[0]
    assert not report.ok


def test_utf16_file_is_rejected_as_invalid_utf8() -> None:
    """run and R2 write plain UTF-8; json.loads(bytes) must not auto-detect UTF-16."""
    raw = json.dumps(_snapshot(), ensure_ascii=False).encode("utf-16")
    report = check_snapshot(raw)
    assert len(report.failures) == 1
    assert report.failures[0].startswith("parse: invalid UTF-8:")


def test_utf8_bom_is_rejected_as_invalid_json() -> None:
    report = check_snapshot(b"\xef\xbb\xbf" + _raw(_snapshot()))
    assert len(report.failures) == 1
    assert report.failures[0].startswith("parse: invalid JSON:")
    assert "BOM" in report.failures[0]


@pytest.mark.parametrize(
    ("raw", "fragment"),
    [
        pytest.param(b"[" * 100_000, "recursion", id="deeply-nested"),
        pytest.param(b'{"schema_version": ' + b"9" * 5000 + b"}", "4300 digits", id="huge-int"),
        pytest.param(b'{"schema_version": NaN}', "NaN", id="nan"),
        pytest.param(b'{"schema_version": -Infinity}', "Infinity", id="infinity"),
    ],
)
def test_unloadable_json_is_one_parse_failure_not_an_exception(
    raw: bytes, fragment: str
) -> None:
    """json.loads raises more than JSONDecodeError; every load failure is a parse: line."""
    report = check_snapshot(raw)
    assert len(report.failures) == 1
    assert report.failures[0].startswith("parse: unusable JSON:")
    assert fragment in report.failures[0]
    assert report.summary["total"] == 0


# --- structurally malformed input ---

def _without_institutions() -> dict[str, Any]:
    snapshot = _snapshot()
    del snapshot["institutions"]
    return snapshot


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param([], id="root-list"),
        pytest.param("snapshot", id="root-string"),
        pytest.param(None, id="root-null"),
        pytest.param(_snapshot(institutions=None) | {"institutions": None}, id="institutions-null"),
        pytest.param(_snapshot(institutions="rows"), id="institutions-string"),
        pytest.param(_without_institutions(), id="institutions-missing"),
    ],
)
def test_malformed_structure_is_a_contract_failure(payload: Any) -> None:
    report = check_snapshot(_raw(payload))
    assert _with_prefix(report.failures, "contract:")
    assert not report.ok
    assert report.summary["total"] == 0


def test_non_object_row_is_a_contract_failure_and_summary_still_counts() -> None:
    rows = _varna_roster()
    rows.append("not a row")
    report = check_snapshot(_raw(_snapshot(rows)))
    assert any("institutions.77" in f for f in _with_prefix(report.failures, "contract:"))
    assert report.summary["total"] == 77


def test_lone_surrogate_escape_is_a_contract_failure_and_rows_are_still_checked() -> None:
    """json.loads accepts a lone "\\ud800" escape; the contract parser rejects it."""
    raw = json.dumps(_snapshot(city="\ud800")).encode("utf-8")  # ensure_ascii keeps the escape
    report = check_snapshot(raw)
    assert any("Invalid JSON" in f for f in _with_prefix(report.failures, "contract:"))
    assert _with_prefix(report.failures, "city:")
    assert report.summary["total"] == 77


# --- non-string leaves that would otherwise become keys ---

def test_non_string_city_is_reported_unknown() -> None:
    report = check_snapshot(_raw(_snapshot(city=[])))
    assert any("[]" in f for f in _with_prefix(report.failures, "city:"))
    assert any("city" in f for f in _with_prefix(report.failures, "contract:"))


def test_non_string_kind_is_left_out_of_the_count() -> None:
    rows = _varna_roster()
    _first(rows, "nursery")["kind"] = []
    report = check_snapshot(_raw(_snapshot(rows)))
    assert any("kind" in f for f in _with_prefix(report.failures, "contract:"))
    assert any("11 nursery" in f for f in _with_prefix(report.failures, "roster:"))


def test_non_string_external_id_is_left_out_of_identity() -> None:
    rows = _varna_roster()
    _first(rows, "nursery")["external_id"] = []
    report = check_snapshot(_raw(_snapshot(rows)))
    assert any("external_id" in f for f in _with_prefix(report.failures, "contract:"))
    assert not any("duplicate" in f for f in report.failures)


# --- labels ---

def test_control_characters_in_identity_keep_each_failure_on_one_line() -> None:
    rows = _varna_roster()
    row = _first(rows, "kindergarten")
    row["external_id"] = "a\nb"
    del row["phone"]
    report = check_snapshot(_raw(_snapshot(rows)))
    assert report.failures
    assert all("\n" not in f and "\r" not in f for f in report.failures)
    assert any("kindergarten/a\\nb" in f for f in _with_prefix(report.failures, "keys:"))


def test_row_without_string_identity_is_labelled_by_index() -> None:
    rows = _varna_roster()
    rows[3]["external_id"] = 7
    del rows[3]["phone"]
    report = check_snapshot(_raw(_snapshot(rows)))
    assert any("row[3]" in f for f in _with_prefix(report.failures, "keys:"))


def test_listed_offenders_are_truncated_after_five() -> None:
    rows = _varna_roster()
    for row in rows[:7]:  # nurseries 1..7
        del row["phone"]
    report = check_snapshot(_raw(_snapshot(rows)))
    line = next(f for f in _with_prefix(report.failures, "keys:") if "phone" in f)
    assert "7 institution(s)" in line
    assert "nursery/5" in line and "nursery/6" not in line
    assert line.endswith("(+2 more)")


# --- key presence on the raw rows ---

@pytest.mark.parametrize("key", CONTACT_FIELDS)
def test_missing_contact_key_is_reported_even_though_the_model_defaults_it(key: str) -> None:
    rows = _varna_roster()
    del _first(rows, "kindergarten")[key]
    report = check_snapshot(_raw(_snapshot(rows)))
    assert not _with_prefix(report.failures, "contract:")
    assert any(key in f for f in _with_prefix(report.failures, "keys:"))


# --- contract ---

def _empty_phone(snapshot: dict[str, Any]) -> None:
    snapshot["institutions"][0]["phone"] = ""


def _extra_key(snapshot: dict[str, Any]) -> None:
    snapshot["institutions"][0]["bogus"] = 1


def _schema_version_3(snapshot: dict[str, Any]) -> None:
    snapshot["schema_version"] = 3


def _schema_version_string(snapshot: dict[str, Any]) -> None:
    snapshot["schema_version"] = "2"


def _string_infant_flag(snapshot: dict[str, Any]) -> None:
    snapshot["institutions"][0]["has_infant_group"] = "true"


def _int_infant_flag(snapshot: dict[str, Any]) -> None:
    snapshot["institutions"][0]["has_infant_group"] = 1


@pytest.mark.parametrize(
    ("mutate", "field"),
    [
        pytest.param(_empty_phone, "phone", id="empty-phone"),
        pytest.param(_extra_key, "bogus", id="extra-key"),
        pytest.param(_schema_version_3, "schema_version", id="schema-3"),
        # Lax coercions run never writes: the contract is the model's declared types.
        pytest.param(_schema_version_string, "schema_version", id="schema-string"),
        pytest.param(_string_infant_flag, "has_infant_group", id="string-bool"),
        pytest.param(_int_infant_flag, "has_infant_group", id="int-bool"),
    ],
)
def test_contract_violation_is_prefixed(
    mutate: Callable[[dict[str, Any]], None], field: str
) -> None:
    snapshot = _snapshot()
    mutate(snapshot)
    report = check_snapshot(_raw(snapshot))
    assert any(field in f for f in _with_prefix(report.failures, "contract:"))


# --- roster ---

@pytest.mark.parametrize(
    ("kind", "expected"), [("nursery", 12), ("kindergarten", 53), ("preschool", 12)]
)
def test_wrong_kind_count_names_seen_vs_expected(kind: str, expected: int) -> None:
    rows = _varna_roster()
    last = max(i for i, r in enumerate(rows) if r["kind"] == kind)  # never the marker
    del rows[last]
    report = check_snapshot(_raw(_snapshot(rows)))
    roster = _with_prefix(report.failures, "roster:")
    assert any(f"{expected - 1} {kind}" in f and f"expected {expected}" in f for f in roster)


def test_null_address_names_seen_vs_expected() -> None:
    rows = _varna_roster()
    _first(rows, "kindergarten")["address"] = None
    report = check_snapshot(_raw(_snapshot(rows)))
    roster = _with_prefix(report.failures, "roster:")
    assert any(
        "1 institution" in f and "null or absent address" in f and "expected 0" in f
        for f in roster
    )
    assert report.summary["null_address"] == 1


def test_marker_without_infant_flag_is_reported() -> None:
    rows = _varna_roster()
    marker = next(r for r in rows if r["name"] == INFANT_MARKER_NAME)
    marker["has_infant_group"] = False
    report = check_snapshot(_raw(_snapshot(rows)))
    roster = _with_prefix(report.failures, "roster:")
    assert any("Палечко" in f and "has_infant_group" in f and "expected True" in f for f in roster)


def test_missing_marker_is_reported() -> None:
    rows = _varna_roster()
    marker = next(r for r in rows if r["name"] == INFANT_MARKER_NAME)
    marker["name"] = 'ДГ №6 "Друга"'
    report = check_snapshot(_raw(_snapshot(rows)))
    assert any("Палечко" in f for f in _with_prefix(report.failures, "roster:"))


def test_duplicate_identity_names_the_pair() -> None:
    rows = _varna_roster()
    kindergartens = [r for r in rows if r["kind"] == "kindergarten"]
    kindergartens[1]["external_id"] = kindergartens[2]["external_id"]
    report = check_snapshot(_raw(_snapshot(rows)))
    pair = f"kindergarten/{kindergartens[2]['external_id']}"
    assert any("duplicate" in f and pair in f for f in _with_prefix(report.failures, "roster:"))


def test_same_external_id_across_kinds_is_allowed() -> None:
    rows = _varna_roster()
    nursery_ids = {r["external_id"] for r in rows if r["kind"] == "nursery"}
    kindergarten_ids = {r["external_id"] for r in rows if r["kind"] == "kindergarten"}
    assert nursery_ids & kindergarten_ids, "fixture must overlap ids across kinds"
    report = check_snapshot(_raw(_snapshot(rows)))
    assert not any("duplicate" in f for f in report.failures)


# --- contact coverage ---

@pytest.mark.parametrize("key", ["phone", "email", "director"])
def test_null_contact_reports_the_count(key: str) -> None:
    rows = _varna_roster()
    rows[0][key] = None
    rows[1][key] = None
    report = check_snapshot(_raw(_snapshot(rows)))
    coverage = _with_prefix(report.failures, "coverage:")
    assert any(f"null or absent {key}" in f and "2 institution" in f for f in coverage)
    assert report.summary[f"null_{key}"] == 2


def test_absent_contact_key_is_worded_null_or_absent_in_coverage() -> None:
    """Absent counts as missing (deliberate); the line must not call it null."""
    rows = _varna_roster()
    del _first(rows, "nursery")["email"]
    report = check_snapshot(_raw(_snapshot(rows)))
    coverage = _with_prefix(report.failures, "coverage:")
    assert any("null or absent email" in f and "nursery/1" in f for f in coverage)
    assert not any(" with null email" in f for f in coverage)


def test_preschool_null_website_reports_the_count() -> None:
    rows = _varna_roster()
    _first(rows, "preschool")["website"] = None
    report = check_snapshot(_raw(_snapshot(rows)))
    coverage = _with_prefix(report.failures, "coverage:")
    assert any("null or absent website" in f and "1 preschool" in f for f in coverage)
    assert report.summary["preschool_null_website"] == 1


def test_non_preschool_null_website_is_allowed() -> None:
    """A kindergarten without a website is not a gate failure (Out of Scope)."""
    rows = _varna_roster()
    assert _first(rows, "kindergarten")["website"] is None
    assert check_snapshot(_raw(_snapshot(rows))).ok


# --- whitespace noise ---

@pytest.mark.parametrize("field", ["phone", "email", "director", "website", "address"])
@pytest.mark.parametrize(
    "noisy",
    [" leading", "trailing ", "tab\tinside", "cr\rinside"],
    ids=["leading-space", "trailing-space", "tab", "cr"],
)
def test_noise_names_external_id_and_field(field: str, noisy: str) -> None:
    rows = _varna_roster()
    row = _first(rows, "preschool")  # the one kind that carries every noise field
    row[field] = noisy
    report = check_snapshot(_raw(_snapshot(rows)))
    noise = _with_prefix(report.failures, "noise:")
    assert any(f"preschool/{row['external_id']}.{field}" in f for f in noise)
    assert report.summary["noisy_values"] == 1


def test_internal_spaces_and_slashes_are_not_noise() -> None:
    rows = _varna_roster()
    rows[0]["phone"] = "052/613 039"
    rows[0]["address"] = "ул. Тестова 1 / бл. 2"
    report = check_snapshot(_raw(_snapshot(rows)))
    assert not _with_prefix(report.failures, "noise:")
    assert report.summary["noisy_values"] == 0


# --- city ---

def test_unknown_city_is_reported() -> None:
    report = check_snapshot(_raw(_snapshot(city="sofia")))
    assert any("sofia" in f for f in _with_prefix(report.failures, "city:"))


def test_expected_city_mismatch_names_both() -> None:
    report = check_snapshot(_raw(_snapshot()), expected_city="sofia")
    assert any("varna" in f and "sofia" in f for f in _with_prefix(report.failures, "city:"))


def test_matching_expected_city_adds_nothing() -> None:
    report = check_snapshot(_raw(_snapshot()), expected_city="varna")
    assert report.ok
    assert report.summary == VALID_SUMMARY


# --- everything is reported together ---

def test_several_problems_are_all_reported_in_one_call() -> None:
    snapshot = _snapshot(schema_version=3)
    rows = snapshot["institutions"]
    del rows[0]  # a nursery: 11 instead of 12
    rows[-1]["director"] = None
    report = check_snapshot(_raw(snapshot))
    assert any("schema_version" in f for f in _with_prefix(report.failures, "contract:"))
    assert any("11 nursery" in f for f in _with_prefix(report.failures, "roster:"))
    assert any("null or absent director" in f for f in _with_prefix(report.failures, "coverage:"))
    assert report.summary["total"] == 76
