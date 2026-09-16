# TASK-001: Add the snapshot check module

Depends on: None
Suggested commit: `feat(check): add snapshot roster and contact checks`

## Goal

`check_snapshot(raw, expected_city)` in a new `src/yasli_scraper/check.py`
turns a snapshot file's bytes into a `CheckReport` with a summary dict and a
list of human-readable failures, covering contract, key presence, roster,
contact coverage and whitespace noise.

## Files

- `src/yasli_scraper/check.py` — new: `CONTACT_FIELDS`, `NOISE` regex
  (`^\s|\s$|\t|\r`), `RosterExpectation` dataclass, `EXPECTED_ROSTER`
  (`"varna"`: 12 nurseries, 53 kindergartens, 12 preschools, infant marker
  name `"Палечко"`), `CheckReport` (`summary`, `failures`, `ok` property),
  `check_snapshot(raw: bytes, expected_city: str | None = None) ->
  CheckReport`; the raw scan guards the JSON shape (object root, list
  `institutions`, object rows) before touching any key
- `tests/test_check.py` — new: fixture builders and one test per failure mode

## Acceptance

- [ ] A valid Varna-shaped snapshot (12 nurseries, 53 kindergartens including
      `ДГ№6 "Палечко"` with `has_infant_group=True`, 12 preschools, full
      contacts, preschool websites — 77 rows matching
      `EXPECTED_ROSTER["varna"]`) yields `ok` and a summary whose exact values are
      asserted for `total`, per-kind counts, `infant_group`, `null_address`,
      `null_phone`, `null_email`, `null_director`, `preschool_null_website`,
      `noisy_values`, `max_phone_length`
- [ ] Invalid JSON and invalid UTF-8 (`b"\xff{"`) each yield exactly one
      failure and no crash
- [ ] A structurally malformed file — a JSON root that is not an object,
      `institutions` that is not a list (missing, `null`, a string), or a row
      that is not an object — yields a `contract:` failure and no traceback,
      and the summary is still returned
- [ ] A non-string leaf where a key is needed — `city: []`, `kind: []`,
      `external_id: []` — yields no traceback: the city is reported as
      unknown, the row is left out of the count and identity checks, and the
      `contract:` failure names the field
- [ ] A row missing any of the four contact keys yields a failure naming the
      key, even though the model would default it to `None`
- [ ] A contract violation (empty-string `phone`, an extra key,
      `schema_version` 3) yields a failure prefixed `contract:`
- [ ] Wrong nursery, kindergarten or preschool count, a null `address`, and
      the marker kindergarten without `has_infant_group` each yield a failure
      that names the seen vs expected value; a snapshot with no marker
      kindergarten at all yields a failure naming the marker
- [ ] Two rows sharing `(kind, external_id)` yield a failure naming the pair;
      the same `external_id` under two different kinds does not
- [ ] Null `phone`/`email`/`director` on any row and null `website` on a
      preschool each yield a failure with the count of offending rows
- [ ] A leading/trailing space, a tab or a `\r` in `phone`, `email`,
      `director`, `website` or `address` yields a failure listing the
      offending `external_id` and field; internal spaces and slashes do not
- [ ] An unknown file `city` yields a failure naming it; an `expected_city`
      that differs from the file's `city` yields a failure naming both; a
      matching `expected_city` adds nothing
- [ ] A snapshot with several problems reports all of them in one call —
      including a contract error (`schema_version` 3) alongside a roster
      error (wrong nursery count) and a null contact

Evidence: `uv run pytest tests/test_check.py -v` output, one test per bullet.

## Steps

### RED
- [ ] Add `tests/test_check.py` with `_institution(**overrides)` /
      `_snapshot(institutions)` builders (mirror `tests/test_models.py`), a
      `_varna_roster()` builder that generates the 12/53/12 rows (unique ids
      per kind, the marker kindergarten included) so the valid fixture matches
      `EXPECTED_ROSTER["varna"]`, a `_raw(snapshot_dict) -> bytes` helper that
      serialises a plain dict so keys can be deleted, and the tests above; run
      them and confirm they fail on the missing module

### GREEN
- [ ] Implement `check_snapshot`: decode and parse (catch
      `UnicodeDecodeError` and `json.JSONDecodeError`, one failure, return) →
      shape guard (root is a dict and `institutions` is a list, else one
      `contract:` failure and return; only dict rows feed the checks below,
      non-dict rows are left for the model to reject) → summary from the dict
      rows → `Snapshot.model_validate` (collect `ValidationError` messages
      under `contract:`, do **not** return) → resolve city (the raw `city`
      value; a non-string or unknown city is an unknown-city failure, an
      `expected_city` mismatch is a failure) and `EXPECTED_ROSTER` → raw key
      presence, roster (per-kind counts, null `address`, unique
      `(kind, external_id)`, marker present and flagged — only rows whose
      `kind` and `external_id` are strings take part; others are already
      contract failures), coverage (absent or `null` counts as missing) and
      noise/length scans (string values only), all over the raw dict rows
- [ ] Build the summary from the raw dict rows (string-typed values only for
      length and noise counts), not from the model, so it is returned even
      when the contract fails; counts are zero when no dict rows exist
- [ ] Keep every check independent so all failures accumulate; the only
      early returns are unparseable bytes and an unusable structure

### REFACTOR
- [ ] Extract the per-field noise scan and the per-kind counts into small
      helpers if `check_snapshot` grows past a screen; keep the module free of
      I/O and of `argparse`

## Notes

Check key presence on the raw dicts *before* `model_validate`: the model's
defaults hide omitted keys, and that is exactly the contract violation the
archived plan's key-presence assertion exists to catch.

`Snapshot.institutions` has `min_length=1`, so an empty file is already a
contract failure; do not special-case it.

Guard the shape before the raw scan: `json.loads` returns a list, a string or
`None` for perfectly valid JSON, and `institutions` can be missing, `null` or
a scalar. Those must fall through to `model_validate`, which reports them as
`contract:` failures — the raw scan must never raise `TypeError`/`KeyError`.

Identity is `(kind, external_id)` because `pipeline.coalesce_institutions`
merges by that pair; nursery and kindergarten ids come from different portals
and may legitimately collide across kinds.

`json.loads` on bytes raises `UnicodeDecodeError`, not `JSONDecodeError`, for
invalid UTF-8; catch both so arbitrary file bytes become a failure, never a
traceback.

Semantic checks run on the raw dict rows, not on the validated model, so a
leaf contract error (`schema_version` 3, an empty-string `phone`) does not
hide an independent roster or coverage defect. Coverage counts a contact as
missing when the key is absent **or the value is `null`**; only the noise and
length scans are restricted to string values. A non-string, non-null value
(`phone: 5`) is the contract's problem and is left to it.

Guard the leaves that become keys: `city`, `kind` and `external_id` can be
any JSON value in a contract-invalid file. A non-string `city` is reported as
an unknown city; a row whose `kind` or `external_id` is not a string is left
out of the count and identity checks (the contract failure already names the
field). Never use a raw value as a dict or set key without an `isinstance`
check.
