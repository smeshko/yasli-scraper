# TASK-001: Upload snapshot bytes verbatim from r2.put_snapshot_bytes

Depends on: None
Suggested commit: `feat(r2): add put_snapshot_bytes for verbatim two-phase uploads`

## Goal

Let a caller put exactly the bytes it holds into both R2 objects, without
`run`'s behaviour changing in any way.

## Files

- `src/yasli_scraper/r2.py` — new `snapshot_keys(city, now=None) ->
  tuple[str, str]` returning `(timestamped_key, latest_key)` for a given
  instant, and new `put_snapshot_bytes(city, body: bytes, *, client=None,
  bucket=None, now=None) -> tuple[str, str]` doing the ordered two writes over
  those keys; every keyword defaults to `None` so `promote` can call
  `put_snapshot_bytes(city, raw)` bare. `put_snapshot` keeps its signature and
  becomes a delegate that serialises the `Snapshot` first.

  `snapshot_keys` is split out so a caller can know the two keys *before* the
  writes begin: `promote` needs them to name both candidates if the upload
  raises mid-way (TASK-002), which is precisely when nothing is returned.
- `tests/test_r2.py` — tests for the new function plus a test pinning
  `put_snapshot`'s serialisation.

## Acceptance

- [ ] `put_snapshot_bytes("varna", body, …)` writes `body` unchanged to both
      `snapshots/varna/<ts>.json` and `snapshots/varna/latest.json`, and returns
      both keys
- [ ] `snapshot_keys("varna", now)` returns exactly the pair
      `put_snapshot_bytes` writes to for that same `now`
- [ ] Write order is still timestamped-first — asserted on the new function
- [ ] A failure on the first write still leaves `latest.json` untouched —
      asserted on the new function
- [ ] `put_snapshot` writes exactly
      `payload.model_dump_json(indent=2).encode("utf-8")`, so `run`'s published
      bytes are provably unchanged
- [ ] The three existing `test_r2.py` tests pass unmodified

Evidence: `pytest tests/test_r2.py -v` output showing the existing three tests
plus the new ones passing, pasted into the commit's task notes.

## Steps

### RED
- [ ] Add `test_put_snapshot_bytes_writes_the_given_bytes_to_both_keys` — build
      a body that is *not* what the model would serialise (e.g. compact
      separators, or a trailing newline) and assert both object bodies equal it
      exactly, via `read()` on the moto objects, comparing `bytes`, not parsed
      JSON
- [ ] Add `test_put_snapshot_bytes_writes_timestamped_before_latest` and
      `test_put_snapshot_bytes_failure_on_first_write_does_not_touch_latest`,
      mirroring the existing `put_snapshot` tests
- [ ] Add `test_put_snapshot_serialises_with_indent_two` asserting the object
      body equals `payload.model_dump_json(indent=2).encode("utf-8")`
- [ ] Add `test_snapshot_keys_matches_what_put_snapshot_bytes_writes` — call
      `snapshot_keys("varna", fixed_now)` and assert the pair equals the keys
      `put_snapshot_bytes(..., now=fixed_now)` returns, so the two can never
      drift
- [ ] Run `pytest tests/test_r2.py` and see the new tests fail on the missing
      attribute

### GREEN
- [ ] Add `snapshot_keys(city, now=None) -> tuple[str, str]` holding the key
      construction (`f"snapshots/{city}/{_utc_iso_filename(now)}.json"` and
      `f"snapshots/{city}/latest.json"`)
- [ ] Move the body of `put_snapshot` into `put_snapshot_bytes(city, body: bytes,
      *, client=None, bucket=None, now=None)`, keeping the same client/bucket
      resolution, `ContentType="application/json"` and the comment explaining
      why the order is load-bearing, and taking its two keys from
      `snapshot_keys(city, now)` so there is one definition of the layout
- [ ] Reduce `put_snapshot` to `return put_snapshot_bytes(city,
      payload.model_dump_json(indent=2).encode("utf-8"), client=client,
      bucket=bucket, now=now)`, keeping its docstring and pointing it at the new
      function
- [ ] `pytest tests/test_r2.py tests/test_run_e2e.py`

### REFACTOR
- [ ] Give `put_snapshot_bytes` a docstring stating that the body is written
      unmodified and that the caller owns validation
- [ ] `ruff check src tests` (or `just sc-lint`)

## Notes

The `now` parameter must stay on `put_snapshot` and `put_snapshot_bytes` — the
existing `tests/test_r2.py` tests pin exact timestamped keys with it.
TASK-002's promote tests do **not** use it: `_run_promote` calls
`put_snapshot_bytes(city, raw, now=now)` with an instant it computed itself,
and the tests pin `r2._utc_iso_filename` instead.
