"""Snapshot publishability checks.

``check_snapshot`` turns a snapshot file's bytes into a :class:`CheckReport`:
a summary of what the file contains plus every failure found, so a bad
snapshot lists everything wrong with it in one run. It proves *shape*
(contract, key presence, per-city roster counts, unique identity) and
*coverage* (contacts, preschool websites, whitespace noise) — not identity:
a file whose institutions were swapped under novel ids passes (YAS-20).

The semantic checks run on the raw JSON rows, not on the validated model:
the model defaults an omitted ``phone`` to ``None`` and would hide the
key-presence violation, and one contract error must not hide an independent
roster or coverage defect. The module does no I/O.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from yasli_scraper.models import Snapshot

CONTACT_FIELDS: tuple[str, ...] = ("phone", "email", "director", "website")
# Contacts every institution must carry; ``website`` is only required on preschools.
REQUIRED_CONTACTS: tuple[str, ...] = ("phone", "email", "director")
NOISE_FIELDS: tuple[str, ...] = (*CONTACT_FIELDS, "address")
# Verbatim from the archived contact-metadata plan's jq assertion.
NOISE = re.compile(r"^\s|\s$|\t|\r")
KINDS: tuple[str, ...] = ("nursery", "kindergarten", "preschool")
# How many offending institutions a failure line names before truncating.
_MAX_LISTED = 5


@dataclass(frozen=True)
class RosterExpectation:
    """The per-city roster a publishable snapshot must match exactly."""

    nurseries: int
    kindergartens: int
    preschools: int
    # Name fragment of the kindergarten that must carry ``has_infant_group``.
    infant_marker: str

    @property
    def by_kind(self) -> dict[str, int]:
        return {
            "nursery": self.nurseries,
            "kindergarten": self.kindergartens,
            "preschool": self.preschools,
        }

    @property
    def total(self) -> int:
        return sum(self.by_kind.values())


# Selected by the file's own ``city``; an unknown city is a failure, not a skip.
EXPECTED_ROSTER: dict[str, RosterExpectation] = {
    "varna": RosterExpectation(
        nurseries=12, kindergartens=53, preschools=12, infant_marker="Палечко"
    ),
}


@dataclass
class CheckReport:
    summary: dict[str, Any]
    failures: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures


# (index in ``institutions``, the raw object row) — the index labels rows
# whose identity is not string-typed.
Row = tuple[int, dict[str, Any]]


def check_snapshot(raw: bytes, expected_city: str | None = None) -> CheckReport:
    """Check a snapshot file's bytes; never raises on bad input.

    ``expected_city`` asserts the file's declared ``city``; it does not
    override it. The roster is always selected by the file's own value.
    """
    # Decode explicitly: json.loads(bytes) would auto-detect UTF-16/32 and
    # swallow a UTF-8 BOM, but ``run`` and R2 only ever write plain UTF-8, so
    # anything else is not publishable.
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return CheckReport(_summary(None, []), [f"parse: invalid UTF-8: {exc}"])
    if text.startswith("\ufeff"):
        # Python's own message suggests decoding with utf-8-sig, the wrong remedy.
        return CheckReport(
            _summary(None, []),
            ["parse: invalid JSON: leading UTF-8 BOM (run writes plain UTF-8 without one)"],
        )
    try:
        payload = json.loads(text, parse_constant=_reject_non_finite)
    except json.JSONDecodeError as exc:
        return CheckReport(_summary(None, []), [f"parse: invalid JSON: {exc}"])
    except (ValueError, RecursionError) as exc:
        # json.loads also raises a plain ValueError (an int beyond the 4300-digit
        # conversion limit, a NaN/Infinity constant) and RecursionError (nesting
        # deeper than the interpreter allows). None of those is a snapshot.
        return CheckReport(_summary(None, []), [f"parse: unusable JSON: {exc}"])

    # Shape guard: the row checks need an object root holding a list of rows.
    # Anything else is left to the model to describe as a contract failure.
    if not isinstance(payload, dict):
        return CheckReport(_summary(None, []), _contract_failures(text))
    institutions = payload.get("institutions")
    if not isinstance(institutions, list):
        return CheckReport(_summary(payload, []), _contract_failures(text))

    # Only object rows feed the checks; the model names the others.
    rows: list[Row] = [(i, r) for i, r in enumerate(institutions) if isinstance(r, dict)]
    failures = _contract_failures(text)
    roster = _resolve_roster(payload.get("city"), expected_city, failures)
    _check_key_presence(rows, failures)
    _check_roster(rows, roster, failures)
    _check_coverage(rows, failures)
    _check_noise(rows, failures)
    return CheckReport(_summary(payload, rows), failures)


def _reject_non_finite(name: str) -> Any:
    # NaN/Infinity are not JSON (RFC 8259); ``run`` never writes them and the
    # stdout summary must stay valid JSON, so they fail the parse instead.
    raise ValueError(f"non-finite number {name} is not valid JSON")


def _contract_failures(text: str) -> list[str]:
    # JSON-mode strict validation: the model's declared types with none of the
    # lax coercions ("true" -> bool, "2" -> 2) that ``run`` never writes.
    # Python-mode strict would reject the ISO ``scraped_at`` string; JSON mode
    # accepts it.
    try:
        Snapshot.model_validate_json(text, strict=True)
    except ValidationError as exc:
        return [
            _printable(
                f"contract: {'.'.join(str(p) for p in err['loc']) or 'root'}: {err['msg']}"
            )
            for err in exc.errors()
        ]
    return []


def _resolve_roster(
    city: Any, expected_city: str | None, failures: list[str]
) -> RosterExpectation | None:
    if expected_city is not None and city != expected_city:
        failures.append(f"city: file declares city {city!r}, expected {expected_city!r}")
    if isinstance(city, str) and city in EXPECTED_ROSTER:
        return EXPECTED_ROSTER[city]
    known = ", ".join(sorted(EXPECTED_ROSTER))
    failures.append(f"city: no roster expectation for city {city!r} (known: {known})")
    return None


def _check_key_presence(rows: list[Row], failures: list[str]) -> None:
    # On the raw rows: the model defaults an omitted contact to None and would hide this.
    for key in CONTACT_FIELDS:
        absent = [r for r in rows if key not in r[1]]
        if absent:
            failures.append(
                f"keys: {key} absent on {len(absent)} institution(s): {_listed(absent)}"
            )


def _check_roster(
    rows: list[Row], roster: RosterExpectation | None, failures: list[str]
) -> None:
    null_address = _missing(rows, "address")
    if null_address:
        failures.append(
            f"roster: {len(null_address)} institution(s) with null or absent address, "
            f"expected 0: "
            f"{_listed(null_address)}"
        )

    # Identity is (kind, external_id): pipeline.coalesce_institutions merges by it,
    # so a duplicate can only come from a corrupted or hand-edited file.
    identities = Counter(
        (r[1]["kind"], r[1]["external_id"]) for r in rows if _has_string_identity(r)
    )
    for (kind, external_id), count in sorted(identities.items()):
        if count > 1:
            failures.append(
                f"roster: duplicate (kind, external_id) {_printable(f'{kind}/{external_id}')} "
                f"appears {count} times"
            )

    if roster is None:
        return  # unknown city: nothing to compare the counts or the marker against

    counts = _kind_counts(rows)
    for kind, expected in roster.by_kind.items():
        if counts[kind] != expected:
            failures.append(
                f"roster: {counts[kind]} {kind} institution(s), expected {expected}"
            )

    marker = roster.infant_marker
    marked = [r for r in rows if isinstance(r[1].get("name"), str) and marker in r[1]["name"]]
    if not marked:
        failures.append(f"roster: no institution named like {marker!r} (the infant-group marker)")
    for r in marked:
        flag = r[1].get("has_infant_group")
        if flag is not True:
            failures.append(
                f"roster: {_label(r)} matches infant marker {marker!r} "
                f"but has_infant_group is {flag!r}, expected True"
            )


def _check_coverage(rows: list[Row], failures: list[str]) -> None:
    # Absent or null both count as missing; a non-null non-string is the contract's problem.
    for key in REQUIRED_CONTACTS:
        missing = _missing(rows, key)
        if missing:
            failures.append(
                f"coverage: {len(missing)} institution(s) with null or absent {key}, "
                f"expected 0: "
                f"{_listed(missing)}"
            )
    missing_website = _missing(rows, "website", kind="preschool")
    if missing_website:
        failures.append(
            f"coverage: {len(missing_website)} preschool(s) with null or absent website, "
            f"expected 0: "
            f"{_listed(missing_website)}"
        )


def _check_noise(rows: list[Row], failures: list[str]) -> None:
    noisy = _noisy_values(rows)
    if noisy:
        failures.append(
            f"noise: {len(noisy)} value(s) with leading/trailing whitespace, tab or CR: "
            + _truncated([f"{_label(r)}.{key}" for r, key in noisy])
        )


def _summary(payload: dict[str, Any] | None, rows: list[Row]) -> dict[str, Any]:
    """Counts over the object rows; always computable, even when the contract fails."""
    envelope = payload or {}
    phones = [r[1]["phone"] for r in rows if isinstance(r[1].get("phone"), str)]
    return {
        "schema_version": _json_scalar(envelope.get("schema_version")),
        "city": _json_scalar(envelope.get("city")),
        "total": len(rows),
        "kinds": _kind_counts(rows),
        "infant_group": sum(1 for r in rows if r[1].get("has_infant_group") is True),
        "null_address": len(_missing(rows, "address")),
        "null_phone": len(_missing(rows, "phone")),
        "null_email": len(_missing(rows, "email")),
        "null_director": len(_missing(rows, "director")),
        "preschool_null_website": len(_missing(rows, "website", kind="preschool")),
        "noisy_values": len(_noisy_values(rows)),
        "max_phone_length": max((len(p) for p in phones), default=0),
    }


def _json_scalar(value: Any) -> Any:
    """Echo a file value into the summary only if json.dumps can always emit it.

    A list nested a thousand deep parses but overflows the encoder in the CLI,
    and ``1e400`` would print as ``Infinity``; the failure lines name them.
    """
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    return None


def _kind_counts(rows: list[Row]) -> dict[str, int]:
    counts = dict.fromkeys(KINDS, 0)
    for _, data in rows:
        kind = data.get("kind")
        if isinstance(kind, str) and kind in counts:
            counts[kind] += 1
    return counts


def _missing(rows: list[Row], key: str, kind: str | None = None) -> list[Row]:
    return [
        r for r in rows if (kind is None or r[1].get("kind") == kind) and r[1].get(key) is None
    ]


def _noisy_values(rows: list[Row]) -> list[tuple[Row, str]]:
    return [
        (r, key)
        for r in rows
        for key in NOISE_FIELDS
        if isinstance(r[1].get(key), str) and NOISE.search(r[1][key])
    ]


def _has_string_identity(row: Row) -> bool:
    data = row[1]
    return isinstance(data.get("kind"), str) and isinstance(data.get("external_id"), str)


def _label(row: Row) -> str:
    index, data = row
    if _has_string_identity(row):
        return _printable(f"{data['kind']}/{data['external_id']}")
    return f"row[{index}]"


def _printable(text: str) -> str:
    """Escape control and other non-printable characters so a failure stays one line.

    The contract only requires ``external_id`` to be non-empty, so a newline in
    it would otherwise split one ``check failed:`` line into two.
    """
    return "".join(ch if ch == " " or ch.isprintable() else repr(ch)[1:-1] for ch in text)


def _listed(rows: list[Row]) -> str:
    return _truncated([_label(r) for r in rows])


def _truncated(labels: list[str]) -> str:
    shown = labels[:_MAX_LISTED]
    extra = len(labels) - len(shown)
    return ", ".join(shown) + (f" (+{extra} more)" if extra else "")
