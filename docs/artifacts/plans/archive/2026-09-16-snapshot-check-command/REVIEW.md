# Review Summary — snapshot-check-command

**Rounds:** 3
**Fix commits:** e111c09..bd25036 (11 commits on top of the plan's task commits)
**Reviewer:** clean `general-purpose` subagent in every round, per the shared protocol's Codex-unavailable rule. Codex was attempted for round 1 but its job failed on a usage limit after one minute, and the companion rendered a false `Verdict: approve / No material findings` for the failed turn; that output is recorded but not treated as a review (see `reviews/round-1.md`).

## Rounds

| Round | Findings | Fixed | Deferred | Rejected |
|-------|----------|-------|----------|----------|
| 1     | 8 (6 findings + 2 from the assumptions section) | 6 | 0 | 2 |
| 2     | 3 | 3 | 0 | 0 |
| 3     | 2 | 2 | 0 | 0 |

Round 3's verdict was **approve**; its two findings are one-line residue of this review's own round-2 commits, not of the original implementation. The three-round rule calls for consulting the user at that point; the user was not available mid-task, so the protocol's most conservative option was taken (**act-and-stop**: both fixed as their own commits, verified by targeted runs, no fourth round). Revert `fb3e52e` and `bd25036` to undo that call.

## Fixes

### Round 1
- `e111c09` — `json.loads` can raise `RecursionError` and plain `ValueError` (deep nesting, >4300-digit ints), and `NaN`/`Infinity` were echoed into the stdout summary; every load failure is now a `parse:` line and non-finite constants are rejected (round-1 #1)
- `083d24c` — a `"\ud800"` escape in the file made the CLI's stdout `print` raise `UnicodeEncodeError`, losing the summary and every failure line; escaped before printing, pinned by a subprocess test because `capsys` never encodes (round-1 #2)
- `01a2a59` — `json.loads(bytes)` auto-detected UTF-16/UTF-32 and swallowed a UTF-8 BOM, so such files passed with exit 0 although `run`/R2 only write plain UTF-8; the bytes are now decoded as strict UTF-8 first (round-1 #3)
- `431980c` — the contract ran in lax mode and accepted `"true"`/`1` for `has_infant_group` and `"2"` for `schema_version`; it now validates in strict JSON mode, verified against the live published snapshot (round-1 #4)
- `0e1263f` — a newline in `external_id` split one failure across two stderr lines; labels, the duplicate-identity pair and contract locs now escape non-printable characters. Also pins the `row[i]` label fallback and `(+N more)` truncation, which had no tests (round-1 #5)
- `dc49346` — coverage and null-address lines said "null phone" for a key that was absent; worded "null or absent", summary keys unchanged (round-1 #6)

### Round 2
- `847c373` — the summary echoed raw `schema_version`/`city`: a ≥1000-deep list tracebacked the CLI's `json.dumps` and `1e400` printed `Infinity`; only JSON scalars are echoed now (round-2 #1)
- `7b9706a` — `print(summary)` still tracebacked on a non-UTF-8 console for a Cyrillic `city`; escaping now targets the console's own encoding, pinned by a subprocess test under `PYTHONIOENCODING=ascii` (round-2 #2)
- `3078371` — README now states the plain-UTF-8-without-BOM and strict-typing rules the round-1 fixes introduced, and the BOM failure no longer quotes Python's `utf-8-sig` hint (round-2 #3)

### Round 3
- `fb3e52e` — `backslashreplace` wrote `\UXXXXXXXX` for astral characters, which is not a JSON escape; the CLI now tries the console encoding and falls back to `ensure_ascii=True` so the escapes are JSON's own (round-3 #1)
- `bd25036` — two test fixtures added in round 2 wrote Cyrillic without `encoding="utf-8"` and errored under a non-UTF-8 locale (round-3 #2)

## Deferred

- none

## Rejected

- (round-1 #7) Infant-marker match is a bare substring on any kind while `RosterExpectation.infant_marker` is documented as a kindergarten — speculative: no nursery or preschool carries the name, the pipeline hard-codes `has_infant_group=False` for those kinds so a hypothetical match would fail the gate loudly rather than pass silently, and the plan pins the marker by name only. Round-2 and round-3 reviewers agreed.
- (round-1 #8) `main()` calls `_load_repo_env()` before dispatching to `check`, which needs no env — harmless no-op (the finding itself calls it harmless); README's "no env vars required" is accurate and it is `run`'s pre-existing behaviour. Round-2 and round-3 reviewers agreed.

## Evidence at HEAD

- `uv run ruff check .` clean; `uv run pytest` 216 passed (193 at the start of the review); `LC_ALL=en_US.ISO8859-1 uv run pytest tests/test_cli.py` 30 passed.
- Currently published `snapshots/varna/latest.json` (24 MB, downloaded read-only): `check --city varna` exits 0 with empty stderr, 12 / 53 / 12, total 77, zero null address/phone/email/director, zero preschools without a website, zero noisy values — so strict-mode validation accepts real portal data. `just sc-snapshot-check` on it exits 0; on a copy with one phone nulled exits 1 with a single `coverage:` line; on a BOM-prefixed copy exits 1 with `parse: invalid JSON: leading UTF-8 BOM (run writes plain UTF-8 without one)`.
- Round-3 reviewer's independent matrix at `3078371`: 32 CLI cases and a 12-field × 16-depth fuzz with no traceback, valid-JSON stdout and single-line `check failed:` stderr in every case.

## Known residuals (not findings)

- `"schema_version": 2.0` passes strict `Literal[2]` (pydantic semantics); `run` never writes it and the previous jq `== 2` accepted it too.
- `REPO_ENV_PATH` resolves to the parent `yasli/.env`, pre-existing and unrelated to this branch.
