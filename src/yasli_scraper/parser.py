"""HTML address-page parser.

Per s02 Decision 8, the CSS class letter (A–E) on each number ``<div>`` is
extracted but discarded — the snapshot keeps only ``(street, number)``.
Per s03 Decision 4, decoding is strict windows-1251. Any decode failure or
fully empty parse aborts the run.
"""
from __future__ import annotations

from html import unescape
import re
from collections.abc import Iterator

# A street block is `<p>STREET</p>` followed by everything up to the next
# `<p>` opener or the closing `</body>`. The trailing assertion is a
# look-ahead so the next iteration can match the same `<p>` again.
_STREET_BLOCK = re.compile(r"<p>([^<]+)</p>(.*?)(?=<p>|</body>)", re.DOTALL)
_NUMBER_DIV = re.compile(r"<div class='([A-E])'>([^<]+)</div>")
_WHITESPACE = re.compile(r"\s+")
_TAG = re.compile(r"<[^>]+>")
_HEADER_ADDRESS = re.compile(
    r"<(?P<tag>div|p|span)[^>]*(?:class|id)=['\"][^'\"]*(?:address|addr|adres|institution-address|dz-address)[^'\"]*['\"][^>]*>"
    r"(?P<value>.*?)</(?P=tag)>",
    re.IGNORECASE | re.DOTALL,
)
_HEADER_LABEL_ADDRESS = re.compile(
    r"(?:Адрес|Aдрес)\s*:?\s*(?P<value>[^<]+)",
    re.IGNORECASE,
)


class ParseError(RuntimeError):
    """Raised when the HTML cannot be parsed into ``(street, number)`` rows."""


def parse_address_html(raw: bytes) -> Iterator[tuple[str, str]]:
    """Yield ``(street, number)`` pairs from one institution's HTML.

    Decodes strictly as windows-1251 — any decode failure raises
    :class:`ParseError`. If the document contains no recognisable street
    blocks at all, also raises :class:`ParseError` (the source has likely
    changed shape).
    """
    content = _decode_html(raw)

    rows = list(_iter_rows(content))
    if not rows:
        raise ParseError("no recognisable street blocks in HTML")
    yield from rows


def parse_institution_address_html(raw: bytes) -> str | None:
    """Extract the physical institution address from the page header."""
    content = _decode_html(raw)
    header = re.split(r"<hr\b", content, maxsplit=1, flags=re.IGNORECASE)[0]

    for pattern in (_HEADER_ADDRESS, _HEADER_LABEL_ADDRESS):
        match = pattern.search(header)
        if match is None:
            continue
        address = _clean_text(match.group("value"))
        if address:
            return address

    return None


def _decode_html(raw: bytes) -> str:
    if not raw:
        raise ParseError("empty HTML body")
    try:
        return raw.decode("windows-1251", errors="strict")
    except UnicodeDecodeError as exc:
        raise ParseError(f"windows-1251 decode failed: {exc}") from exc


def _iter_rows(content: str) -> Iterator[tuple[str, str]]:
    for block in _STREET_BLOCK.finditer(content):
        street = _clean_text(block.group(1))
        for _cls, number in _NUMBER_DIV.findall(block.group(2)):
            yield street, _clean_text(number)


def _clean_text(value: str) -> str:
    text = _TAG.sub("", value)
    text = unescape(text)
    return _WHITESPACE.sub(" ", text).strip()
