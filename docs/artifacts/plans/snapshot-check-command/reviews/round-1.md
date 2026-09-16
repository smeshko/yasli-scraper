# Adversarial Review — Round 1

**Run:** 2026-09-16 04:35 UTC
**Branch:** feature/yas-16-snapshot-check-command
**Base:** staging
**Commits reviewed:** 397b076..dcc005c
**Reviewer:** subagent (clean `general-purpose` agent with the adversarial framing, per the shared protocol's Codex-unavailable rule).
Codex was attempted first at 04:31 UTC (`--wait --scope branch --base staging`); the job failed after 1m 2s on a usage limit (`Codex error: You've hit your usage limit … try again at 11:41 AM`, job `review-mu3lsl4f-u57qhf`) and the companion rendered a false `Verdict: approve / No material findings` for the failed turn. That output is not a review and is not recorded here.

## Codex output

<!-- Paste /codex:adversarial-review stdout verbatim below this line. Do not edit. -->

# Adversarial Review — Round 1 (subagent)

Target: branch feature/yas-16-snapshot-check-command vs staging (397b076..dcc005c)
Verdict: request-changes

## Summary
The design is sound and the failure-reporting model (raw-row checks independent of the contract, every failure in one run) behaves as the plan says; the suite is green (193 passed, ruff clean) and the README recipe is byte-identical to the parent justfile. The biggest risk is that the "never raises / never tracebacks on bad input" guarantee — the one thing three validation rounds pushed hardest on — only holds for the two exception types that were named: `json.loads` also raises `RecursionError` and a plain `ValueError`, and the CLI's stdout print can raise `UnicodeEncodeError`, all reproduced through the real `python -m yasli_scraper check`. Secondary: `json.loads(bytes)` auto-detects encoding, so UTF-16/UTF-32/BOM-prefixed files pass with exit 0 even though `run` and R2 only ever write plain UTF-8. All fixes are small. I verified by running pytest/ruff, a 40-case fuzz of `check_snapshot`, subprocess runs of the CLI, and a jq-1.7.1 vs Python comparison of the noise regex.

## Findings
1. [med] [CONFIRMED] `check_snapshot` and the CLI traceback on JSON that `json.loads` rejects with something other than `JSONDecodeError`/`UnicodeDecodeError`
   - Where: /Users/A1E6E98/Developer/Projects/yasli/scraper/src/yasli_scraper/check.py:90-95
   - What: Only two exception classes are caught. `b"[" * 100000` raises `RecursionError`; a 5000-digit integer anywhere in the file (`{"schema_version": 999…}` or a row's `phone`) raises `ValueError: Exceeds the limit (4300 digits)…`. Both escape `check_snapshot`, contradicting its docstring ("never raises on bad input"), the plan's Scope/Decisions, and the README ("reported as a failure, not a traceback"). Through the CLI the summary is never printed and stderr is a traceback instead of `check failed:`.
   - Evidence: `uv run python -m yasli_scraper check deep.json` → `RecursionError: maximum recursion depth exceeded while decoding a JSON array`; `check bigint.json` → `ValueError: Exceeds the limit (4300 digits) for integer string conversion`. Both exit 1 only because Python's uncaught-exception exit is 1.
   - Suggested fix: catch `(ValueError, RecursionError)` around `json.loads` (`JSONDecodeError` and `UnicodeDecodeError` are both `ValueError` subclasses, so keep the two specific branches for the nicer prefixes and add a generic `parse:` fallback); add one regression test per case.

2. [med] [CONFIRMED] CLI tracebacks when a summary field contains a lone surrogate
   - Where: /Users/A1E6E98/Developer/Projects/yasli/scraper/src/yasli_scraper/__main__.py:89
   - What: `city`/`schema_version` are echoed raw into the summary. A JSON escape `"\ud800"` (or the raw bytes `\xed\xa0\x80`, which `json.loads(bytes)` accepts via `surrogatepass`) yields a lone surrogate; `check_snapshot` handles it (the `city:` failure uses `!r`), but `print(json.dumps(..., ensure_ascii=False))` then raises `UnicodeEncodeError` on a UTF-8 stdout. The summary and every `check failed:` line are lost.
   - Evidence: `check surrogate.json` → `File "…/__main__.py", line 89, in _run_check … UnicodeEncodeError: 'utf-8' codec can't encode character '\ud800' in position 36: surrogates not allowed`. Not caught by the pytest suite because `capsys` buffers are `StringIO` and never encode.
   - Suggested fix: write the summary via `sys.stdout.buffer.write(text.encode("utf-8", "backslashreplace"))` (or reject the file in `check_snapshot` by decoding explicitly with `raw.decode("utf-8")`, which is strict about surrogates — see finding 3, which fixes this for free).

3. [med] [CONFIRMED] UTF-16, UTF-32 and BOM-prefixed files are accepted as publishable
   - Where: /Users/A1E6E98/Developer/Projects/yasli/scraper/src/yasli_scraper/check.py:91
   - What: `json.loads(bytes)` runs `json.detect_encoding` first, so a UTF-16/UTF-32 file or a UTF-8 file with a BOM (what Windows editors write on a hand edit — the plan explicitly contemplates hand-edited files) parses and passes with exit 0. `run` and `r2.put_snapshot` (r2.py:59) only ever write plain UTF-8 with `ContentType="application/json"`; a consumer reading the promoted bytes as UTF-8 will fail. The plan's "invalid UTF-8 is a failure" decision implies the gate asserts UTF-8, but it does not.
   - Evidence: `check --city varna valid_utf16.json` → exit 0, empty stderr; `check_snapshot(b"\xef\xbb\xbf" + valid)` → `ok=True`. Verified the fix: `json.loads(raw.decode("utf-8"))` rejects UTF-16 (`UnicodeDecodeError`) and the BOM (`JSONDecodeError: Unexpected UTF-8 BOM`).
   - Suggested fix: decode explicitly (`text = raw.decode("utf-8")`) before `json.loads`, so the gate asserts the same encoding `run` writes; add BOM and UTF-16 regression cases.

4. [low] [CONFIRMED] The contract is lax about booleans while the roster/summary are strict, so string/int `has_infant_group` values pass the gate and the summary under-reports
   - Where: /Users/A1E6E98/Developer/Projects/yasli/scraper/src/yasli_scraper/check.py:118, 187, 228
   - What: `Snapshot.model_validate` runs in lax mode, so `"has_infant_group": "true"` (or `1`) on every kindergarten is accepted by the contract. The marker row is caught only because `flag is not True`; the other 52 rows sail through and `summary["infant_group"]` reports 1. A file with non-boolean flags is not what `run` writes and is not JSON the backend should ingest, yet the gate says publishable.
   - Evidence: valid fixture with `"true"` on all non-marker kindergartens → `report.ok == True`, `summary["infant_group"] == 1`; with `"true"` on all 53 → only the one marker failure, `infant_group == 0`. `Snapshot.model_validate_json(raw, strict=True)` rejects it (`('institutions', 0, 'has_infant_group')`) while still accepting the valid fixture; `model_validate(payload, strict=True)` is not an option (it rejects the ISO `scraped_at` string).
   - Suggested fix: run the contract with `Snapshot.model_validate_json(raw, strict=True)` (JSON-mode strict keeps ISO datetimes/URLs working) and keep the separate `json.loads` for the raw-row checks; or add a raw-row `isinstance(flag, bool)` assertion.

5. [low] [CONFIRMED] A failure can span multiple stderr lines, breaking "exactly one `check failed:` line per failure"
   - Where: /Users/A1E6E98/Developer/Projects/yasli/scraper/src/yasli_scraper/check.py:268-272 (`_label`), __main__.py:91
   - What: labels interpolate raw `kind`/`external_id`; the contract only requires `external_id` to be non-empty, so `"a\nb"` is contract-clean and every `keys:`/`coverage:`/`noise:`/`roster:` message naming that row contains a newline. `_label` also emits a raw `kind` even when the contract has already rejected it (`"nursery\n"`).
   - Evidence: `check newline_id.json 2>&1 | cat -A` → `check failed: keys: phone absent on 1 institution(s): kindergarten/a$` / `b$` (two lines for one failure), same for the coverage line.
   - Suggested fix: build labels with `repr()` (or strip `\r\n\t` from the interpolated identity) so a label is always a single line.

6. [low] [CONFIRMED] `coverage:` reports an absent key as "null", double-counting the `keys:` failure with a wrong label
   - Where: /Users/A1E6E98/Developer/Projects/yasli/scraper/src/yasli_scraper/check.py:194-202, 248-251
   - What: `_missing` treats absent and `null` identically (deliberate per round-3 #1), but the message says `N institution(s) with null phone` when the key is missing, and the same row is already listed under `keys: phone absent`. The same wording applies to `roster: … null address` for an absent `address` key (which the contract does not flag at all).
   - Evidence: delete `phone` from one row → `keys: phone absent on 1 institution(s): nursery/1` and `coverage: 1 institution(s) with null phone, expected 0: nursery/1`; `summary["null_phone"] == 1` for a key that is absent, not null.
   - Suggested fix: word the coverage/roster messages and summary keys as "null or absent", or exclude rows already reported under `keys:` from the coverage line.

## Assumptions challenged
- "Noise regex is the jq one verbatim, in effect": compared 14 cases against jq 1.7.1. Identical for NBSP, `\x85`, ` `, `　`, leading/trailing newline, `a \nb`, `a\n b`, ZWSP and `﻿` (neither flags the last two). Only divergence: Python's `\s` also matches `\x1c`–`\x1f` (stricter, harmless). Claim holds.
- "Every failure is reported together": holds — contract + roster + coverage all appear in one report; unknown city correctly skips only counts/marker while still running null-address and duplicate checks. But `json.loads` also accepts `NaN`/`Infinity` literals; the contract flags them, yet the stdout summary then echoes `"schema_version": NaN`, which is not valid JSON for a strict consumer (low; folds into finding 1/3's "decode and parse exactly what `run` writes").
- Infant marker is a bare substring on any kind: a nursery or preschool whose name contains `Палечко` would fail unconditionally, because the pipeline hard-codes `has_infant_group=False` for those kinds. Not a live risk (nurseries are `ДЯ …`, preschools are `ОУ/СУ …`), but `RosterExpectation.infant_marker` documents itself as "the kindergarten that must carry…" while the code does not filter `kind == "kindergarten"`. One-line tightening if you want the code to match the comment.
- `--city` as assertion: exact, case-sensitive, `--city ""` fails as `expected ''`; an unknown file city plus a mismatched `--city` yields two distinct `city:` lines. Behaves as decided.
- README "no env vars": true that none are required, but `main()` still calls `_load_repo_env()` before dispatching to `check` (and the parent justfile's `set dotenv-load` loads it anyway). Harmless; the `_run_check` comment ("no validate_env()") is accurate.
- Tests: the CLI fixture built from `Snapshot.model_dump_json()` does pin that `run`'s serialisation (all four contact keys present, `Z`-suffixed timestamp) passes the gate — a valuable pin. Gaps: no test for the `row[i]` label fallback, the `(+N more)` truncation, or any of findings 1–5 (all of which pass the current suite, and finding 2 is invisible under `capsys`).

## Verified OK
- `uv run pytest` (193 passed) and `uv run ruff check .` clean at head.
- Structural fuzz: root list/string/null, `institutions` null/string/dict/empty, non-object rows, `city` null/int/list/2000-deep nested list, `name` null, `kind` outside enum, `external_id` int, `phone` list, `scraped_at` 1e308/-1e308/10^30, 100k-char `source_url`, duplicate JSON keys — none raise; each yields the expected `contract:`/`city:`/`roster:` lines and a computable summary (`total` counts only object rows, as documented).
- Roster: `(kind, external_id)` uniqueness allows the same id across kinds and names the duplicated pair; per-kind counts name seen vs expected; a second name matching the marker is flagged too; `(+N more)` truncation counts correctly (5 shown, `+2 more` for 7).
- CLI: missing path and directory path give one `error: cannot read …` line, no traceback; valid file with and without `--city varna` exits 0 with empty stderr; summary printed before failures and even when checks fail; stderr with `PYTHONIOENCODING=ascii` degrades to `\uXXXX` escapes rather than crashing.
- README recipe body is byte-identical to `../justfile` lines 122–126, and the documented exit-code and stdout/stderr split match observed behaviour (modulo findings 1, 2, 5).

## Triage

<!--
Verdict values:
  fix    — real bug; address now in this branch
  defer  — has merit but out of scope; capture as a follow-up
  reject — contradicts an explicit Decision in PLAN.md, or is taste/speculation

One row per finding. Number them so subsequent rounds can reference them
(e.g. "round-1 #3 is unaddressed"). Severity is one of: high, med, low.
Commit is the fix SHA when verdict is `fix`; empty otherwise.
-->

| # | Finding | Severity | Verdict | Rationale | Commit |
|---|---------|----------|---------|-----------|--------|
| 1 | `json.loads` can raise `RecursionError` / plain `ValueError` (deep nesting, >4300-digit ints) and `NaN`/`Infinity` are echoed into the stdout summary; the "never raises" claim in the docstring, Scope and README is false | med | fix | Contradicts the plan's own Decision that unparseable input is reported, not raised; catch every load failure as `parse:` and reject non-finite constants so stdout is always valid JSON | e111c09 |
| 2 | A lone-surrogate escape (`"\ud800"`) in the file makes the CLI's stdout `print` raise `UnicodeEncodeError`, losing the summary and every failure line | med | fix | Real traceback path reproduced through `python -m`; invisible under `capsys`. Escape unencodable characters when printing the summary; a subprocess test pins it | 083d24c |
| 3 | `json.loads(bytes)` auto-detects encoding, so UTF-16/UTF-32 and BOM-prefixed files pass with exit 0 although `run`/R2 only ever write plain UTF-8 | med | fix | The plan's "invalid UTF-8 is a failure" Decision implies the gate asserts UTF-8; decode explicitly before parsing | 01a2a59 |
| 4 | Lax-mode contract accepts `"true"`/`1` for `has_infant_group` (and other coercions), so a file `run` would never write passes and the summary under-counts | low | fix | The Decision is "the check follows the model"; strict JSON-mode validation is the model's declared types, verified to still accept the valid fixture. Small change, closes a class of holes | 431980c |
| 5 | Labels interpolate raw `kind`/`external_id`, so a newline in an id yields a multi-line failure and breaks "one `check failed:` line per failure" | low | fix | Acceptance criterion is one line per failure; escape non-printable characters in labels and contract locs. Add the missing `row[i]` / `(+N more)` tests while here | 0e1263f |
| 6 | `coverage:`/`roster:` say "null phone"/"null address" for a key that is absent, not null | low | fix | Absent-counts-as-missing is deliberate (validation round-3 #1) but the message must name the problem accurately; reword to "null or absent", summary keys unchanged | dc49346 |
| 7 | Infant marker matches by substring on any kind while `RosterExpectation.infant_marker` is documented as a kindergarten | low | reject | Speculative: no nursery or preschool carries the name, and if one ever did the gate would fail loudly rather than silently pass; the plan pins the marker by name only | |
| 8 | `main()` calls `_load_repo_env()` before dispatching to `check`, which needs no env | low | reject | Harmless no-op the finding itself calls harmless; README's "no env vars required" is accurate. Taste | |
