"""Test fixture loader.

The HTML fixtures are real captures of dg.uslugi.io per-institution pages,
copied verbatim from the spec repo's ``initial/data/raw/`` (see README.md
for refresh procedure). They're served as bytes — the parser is responsible
for windows-1251 decoding.
"""
from __future__ import annotations

from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent


def load_html(name: str) -> bytes:
    """Return the raw bytes of ``tests/fixtures/<name>``."""
    return (FIXTURES_DIR / name).read_bytes()
