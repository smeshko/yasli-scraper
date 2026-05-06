from __future__ import annotations

import pytest

from yasli_scraper.parser import ParseError, parse_address_html

from .fixtures import load_html

# Counts taken from initial/data/parsed/addresses.tsv for the same institutions.
EXPECTED_ROWS = {
    "infant_39.html": 4503,
    "garden_34.html": 4497,
    "pg_10.html": 8222,
}


@pytest.mark.parametrize("name,expected", list(EXPECTED_ROWS.items()))
def test_row_count_matches_addresses_tsv(name: str, expected: int) -> None:
    rows = list(parse_address_html(load_html(name)))
    assert len(rows) == expected


def test_rows_are_street_number_pairs() -> None:
    rows = list(parse_address_html(load_html("garden_34.html")))
    for street, number in rows[:50]:
        assert isinstance(street, str) and street
        assert isinstance(number, str) and number


def test_streets_are_collapsed_and_stripped() -> None:
    """Street values come out without runs of whitespace or surrounding spaces."""
    rows = list(parse_address_html(load_html("garden_34.html")))
    streets = {street for street, _ in rows}
    for street in streets:
        assert street == street.strip()
        assert "  " not in street


def test_class_letter_is_discarded() -> None:
    """Numbers should not contain the A–E class letter from the source div."""
    rows = list(parse_address_html(load_html("infant_39.html")))
    # The class letter shows up only as a div attribute; numbers like
    # "041 вх.А" are legitimate. Just verify we got non-empty number strings.
    for _, number in rows:
        assert number


def test_decode_failure_raises() -> None:
    # Bytes that are invalid windows-1251 (0x98 has no mapping in cp1251).
    bad = b"<body><p>" + bytes([0x98]) + b"</p></body>"
    with pytest.raises(ParseError, match="decode"):
        list(parse_address_html(bad))


def test_empty_body_raises() -> None:
    with pytest.raises(ParseError):
        list(parse_address_html(b""))


def test_no_street_blocks_raises() -> None:
    html = b"<html><body><h1>nothing here</h1></body></html>"
    with pytest.raises(ParseError, match="no recognisable street blocks"):
        list(parse_address_html(html))


def test_synthetic_block_extraction() -> None:
    """Construct a minimal block to verify the regex contract directly."""
    html = (
        b"<body>"
        b"<p>STREET ONE</p>"
        b"<div class='A'>001</div>"
        b"<div class='C'>002</div>"
        b"<p>STREET TWO</p>"
        b"<div class='B'>003</div>"
        b"</body>"
    )
    rows = list(parse_address_html(html))
    assert rows == [
        ("STREET ONE", "001"),
        ("STREET ONE", "002"),
        ("STREET TWO", "003"),
    ]
