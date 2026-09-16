# Adversarial Review — Round 3

**Run:** 2026-09-16 05:20 UTC
**Branch:** feature/yas-16-snapshot-check-command
**Base:** staging
**Commits reviewed:** 397b076..3078371 (round-2 fixes 847c373..3078371)
**Prior rounds in scope:** reviews/round-1.md, reviews/round-2.md
**Reviewer:** subagent (clean `general-purpose` agent with the round-3 focus text; Codex still usage-limited until 11:41 local).

## Codex output

<!-- Paste /codex:adversarial-review stdout verbatim below this line. Do not edit. -->

# Adversarial Review — Round 3 (subagent)

Target: branch feature/yas-16-snapshot-check-command vs staging (397b076..3078371), round-2 fixes 847c373..3078371
Verdict: approve

## Summary
All three round-2 fixes do what they claim and none regressed a round-1 fix: at HEAD the suite is green (216 passed, ruff clean), the live Varna `latest.json` exits 0 with 12/53/12, and a 32-case CLI matrix (deep nesting, 4300/4301/5000-digit ints, NaN/±1e400, bool/str/null/dict/deep `schema_version` and `city`, UTF-16 with and without BOM, UTF-8 BOM, lone surrogate, newline id, `"true"`/`1`/`1.0` flags, empty/whitespace files) gives valid-JSON stdout, single-line `check failed:` stderr and no traceback in every case. A depth fuzz over 12 fields at depths 500–20 000 never makes `check_snapshot` raise. Two low residuals remain, both one-line fixes and neither a defect on the platforms this runs on (macOS dev, ubuntu CI, Railway): the console-encoding escape emits `\U0001f642` for astral characters, which is not a JSON escape, so on a non-UTF-8 console with an emoji in `city` the stdout summary is not JSON (rc and stderr still correct); and two tests added by 847c373 write Cyrillic fixtures without `encoding="utf-8"` and fail under a non-UTF-8 locale. I would not stop the author for either; they can be folded in or deferred at triage.

## Round-2 fix verification
| # | Finding | Fix commit | Sufficient? | Notes |
|---|---------|------------|-------------|-------|
| 1 | `_summary` echoed raw `schema_version`/`city`; deep list tracebacked `json.dumps`, `1e400` printed `Infinity` | 847c373 | yes | Deep list/dict `city` (1500, 5000) → `null`; `-1e400` city and `1e400` schema → `null`; `true` echoes as `true` (bool is in the isinstance tuple, a JSON scalar, sensible); `null` → `null`; a 4300-digit int echoes and dumps fine because `int()` and `int.__repr__` share the 4300-digit limit (4301 digits fails at the parse, so nothing loadable is undumpable); `2`/`"varna"` still shown for the valid file and the live file. No other summary field carries a file value (all counts/lengths). Only test-side nit: see finding 2. |
| 2 | `print(summary)` tracebacked on a non-UTF-8 stdout for a non-ASCII `city` | 7b9706a | partial | No traceback on 11 encodings (`utf-8`, `utf-8:strict`, `ascii`, `ascii:strict`, `latin-1`, `cp1251`, `cp1252`, `utf-16`, `utf-32`, `cp037`, unset) × 4 files; `sys.stdout.encoding is None` (StringIO) path works via the `or "utf-8"` fallback; the escape round-trip is identity on UTF-8 for everything and on cp1251 for BMP Cyrillic; pytest's `CaptureIO` reports `"UTF-8"` so capsys tests are unaffected; `sys.stderr.errors` stays `backslashreplace` even under `ascii:strict`. But `backslashreplace` writes `\U0001f642` for non-BMP characters, which JSON does not accept — finding 1. |
| 3 | README silent on UTF-8/BOM and strict types; BOM message suggested `utf-8-sig` | 3078371 | yes | BOM branch sits after the strict decode and before `json.loads`, returns the same `_summary(None, [])` as other parse failures, message is owned. README Contract bullet verified through the CLI: `"2"` → `contract: schema_version: Input should be 2`; `"true"` → `Input should be a valid boolean`; UTF-8 BOM → the owned message; UTF-16 (BOM) → `parse: invalid UTF-8`; UTF-16-LE without BOM → `parse: invalid JSON`. Recipe block still byte-identical to `../justfile:123-126`; `docs/DEPLOYMENT.md`/`ARCHITECTURE.md` only cite `run` as the start command, not stale. Residual (already judged not-a-finding in round 2): `"schema_version": 2.0` passes strict `Literal[2]`, rc 0, summary echoes `2.0` — the README's "types are not coerced" is slightly broader than pydantic's semantics; `run` never writes it. |

## Round-1 fixes re-checked at HEAD
- #1.1 (e111c09) still holds: `[`×100 000, 5000-digit int, `NaN`, `-Infinity` each give one `parse: unusable JSON:` line with the summary printed, rc 1, no traceback.
- #1.2 (083d24c) still holds: `"\ud800"` city via subprocess with `PYTHONIOENCODING=utf-8:strict` → rc 1, stdout parses with `city == '\ud800'`, no traceback.
- #1.3 (01a2a59) still holds: UTF-16 → `parse: invalid UTF-8`; BOM → owned message; both single line, summary printed.
- #1.4 (431980c) still holds: `"true"`, `1`, `1.0` for `has_infant_group` and `"2"`, `true`, `null` for `schema_version` are `contract:` lines; the live 24 MB file still passes strict mode.
- #1.5 (0e1263f) still holds: `a\nb` id → one line `keys: phone absent … kindergarten/a\nb`; in all 32 matrix cases every stderr line starts with `check failed:` (line count == failure count).
- #1.6 (dc49346) still holds: absent `phone` → `keys: phone absent on 1 …` plus `coverage: 1 institution(s) with null or absent phone …`; null `email` → `null or absent email`.

## Rejections reviewed
- round-1 #7 infant-marker kind filter — agree. `pipeline.py:202` hard-codes `has_infant_group=kind == "kindergarten" and has_marker`, so a nursery/preschool named like `Палечко` would fail the gate loudly (`expected True`), never pass silently; the plan pins the marker by name only and a filter would only trade a loud false positive for silence. The comment at `check.py:46` ("of the kindergarten") is cosmetic.
- round-1 #8 `_load_repo_env()` before `check` — agree. `load_dotenv` on a missing file is a no-op, `check` reads no env, the README's "no env vars" is accurate, and it is `run`'s pre-existing behaviour. (Unrelated pre-existing note: `REPO_ENV_PATH` resolves to the parent `yasli/.env`, not the scraper root — not this branch's change.)

## Findings
1. [low] [CONFIRMED] [INCOMPLETE-FIX round-2 #2] `backslashreplace` emits `\UXXXXXXXX` for astral characters, which is not a JSON escape, so the stdout summary is invalid JSON on a non-UTF-8 console
   - Where: /Users/A1E6E98/Developer/Projects/yasli/scraper/src/yasli_scraper/__main__.py:93-94
   - What: BMP characters happen to escape as `\uXXXX`, which JSON also accepts, so the round-2 test (`варна` on ASCII) passes by coincidence. A non-BMP character (emoji, rare CJK) escapes as `\U0001f642`, which `json.loads` rejects (`Invalid \escape`). Reachable only when `sys.stdout.encoding` cannot encode the character (ascii, latin-1, cp1251, cp1252, cp037 — not UTF-8/16/32) and the file's `city`/`schema_version` carries such a character, which already fails the city check; rc and every stderr line are correct and there is no traceback. The triage rationale for #1.1 and #2.1 was "stdout always valid JSON", which this does not deliver on that console.
   - Evidence: `PYTHONIOENCODING=cp1251 uv run python -m yasli_scraper check enc_emoji.json` → stdout line 3 is `"city": "варна\U0001f642",` (bytes `\xE2\xE0\xF0\xED\xE0\U0001f642`); piping the same stdout under `ascii` into `json.loads` → `INVALID JSON: Invalid \escape: line 3 column 42`. Same for latin-1, cp1252, cp037. UTF-8/16/32 and all BMP-only files are fine.
   - Suggested fix: instead of `backslashreplace`, fall back to a JSON-native escape when the console cannot encode the text: `try: summary.encode(encoding) except UnicodeEncodeError: summary = json.dumps(report.summary, ensure_ascii=True, indent=2)` then `print(summary)`. Verified: `ensure_ascii=True` yields `🙂` for the emoji and `\ud800` for the lone surrogate, encodes on ascii/latin-1/cp1251/cp037/utf-16, and parses back identical; the two existing subprocess tests keep passing under it (they assert on `json.loads(stdout)["city"]`).

2. [low] [CONFIRMED] [NEW] Two tests added by 847c373 write a Cyrillic fixture with `write_text` and no `encoding`, so the suite depends on a UTF-8 locale
   - Where: /Users/A1E6E98/Developer/Projects/yasli/scraper/tests/test_cli.py:329 (`_file_deep_city`) and :415 (`test_check_summary_stays_valid_json_for_a_non_finite_schema_version`)
   - What: every other writer in the file passes `encoding="utf-8"` (lines 100, 251, 432, 450); these two use the locale default, and the payload contains `ДГ №7 "Изгрев"` etc. On Windows (default cp1252, no UTF-8 mode) or any non-UTF-8 POSIX locale both tests error inside `write_text` before the code under test runs. CI is `ubuntu-latest` (UTF-8), so it does not bite there.
   - Evidence: `LC_ALL=en_US.ISO8859-1 uv run pytest "tests/test_cli.py::…[deep-city]" "tests/test_cli.py::test_check_summary_stays_valid_json_for_a_non_finite_schema_version" "…[utf16]"` → `2 failed, 1 passed`, both with `UnicodeEncodeError: 'latin-1' codec can't encode characters in position 128-129` at `pathlib.py:1048`; `locale.getencoding()` under that locale is `ISO8859-1`, `utf8_mode=0`.
   - Suggested fix: add `encoding="utf-8"` to both `write_text` calls (or route them through the existing `_write_json` helper).

## Verified OK
- `uv run pytest` 216 passed and `uv run ruff check .` clean at 3078371; live `yasli-latest.json` with `--city varna` → rc 0, empty stderr, 12/53/12, total 77, zero null/noisy, infant_group 20, max_phone_length 24.
- 32-case CLI matrix (files under the scratchpad `r3/`): every case has the expected rc, a `json.loads`-able stdout, stderr consisting solely of single `check failed:` lines, no `Traceback`. Includes 4300-digit ints in `schema_version`, `city` and the marker's `has_infant_group` (echoed/repr'd without error; 4301 digits fails at the parse), `-1e400` city, `true`/`"2"`/`null` schema, a dict city, 1500- and 5000-deep city, 3000-deep marker flag, BOM after a leading space and UTF-16-LE without BOM (both still `parse:` failures), empty and whitespace-only files.
- `check_snapshot` never raises: 12 fields (`city` list/dict, `schema_version`, marker `has_infant_group`, row `kind`/`external_id`/`name`/`phone`/`address_entries`, deep `institutions` element, deep root dict, deep extra key) × 16 depths from 500 to 20 000, each also passing `json.dumps(summary, indent=2, allow_nan=False)` and single-line failures; `json.loads` itself gives up at depth 10 000 and `repr` still works at 9 990, so there is no window where a loadable value is un-repr-able.
- Encoding: 44 subprocess runs (11 `PYTHONIOENCODING` values × valid/Cyrillic/surrogate/emoji files) — no traceback, correct rc, stdout decodes in the declared codec; `io.StringIO` stdout (`encoding is None`) prints the Cyrillic and surrogate summaries; the escape round-trip is identity on UTF-8 for all inputs and on cp1251 for BMP Cyrillic; `sys.stderr.errors` is `backslashreplace` even under `ascii:strict`.
- Missing path and directory path: rc 1, empty stdout, exactly one `error: cannot read …` line naming the path.
- README `just` block is byte-identical to `../justfile:123-126`; no other doc references the CLI beyond `run` as the deployment start command; `models.py`, `pipeline.py`, `r2.py` unchanged on the branch and no line was removed from the `run` path in `__main__.py`.
- Known, accepted residual re-confirmed: `"schema_version": 2.0` → rc 0 with the summary echoing `2.0` (pydantic strict `Literal[2]` semantics, `run` never writes it, the old jq `== 2` accepted it too).

## Triage

<!--
Verdict values:
  fix    — real bug; address now in this branch
  defer  — has merit but out of scope; capture as a follow-up
  reject — contradicts an explicit Decision in PLAN.md, or is taste/speculation
-->

Triager note — three-round rule: round 3 still produced two `fix` rows, which the protocol says is the point to stop and ask the user. The user was not available mid-task (autonomous session), the round's verdict is **approve**, and both rows are one-line residue of this review's own round-2 commits (847c373, 7b9706a), not of the original implementation — no structural signal. The protocol's most conservative option was taken: **act-and-stop** — both rows fixed as their own commits, verified by targeted RED/GREEN runs (below), and **no fourth round**. The user can revert `fb3e52e` and `bd25036` if they disagree with acting.

Verification after the two commits (not a review round): `uv run pytest` 216 passed, ruff clean; `PYTHONIOENCODING=ascii … check emoji.json | json.loads` → `'варна🙂'` (was `Invalid \escape` before fb3e52e); `LC_ALL=en_US.ISO8859-1 uv run pytest tests/test_cli.py` → 30 passed (the two tests failed before bd25036).

| # | Finding | Severity | Verdict | Rationale | Commit |
|---|---------|----------|---------|-----------|--------|
| 1 | `backslashreplace` writes `\UXXXXXXXX` for astral characters, so on a non-UTF-8 console an emoji in `city` leaves the stdout summary unparseable | low | fix | Residue of round-2 #2; try the console encoding first and fall back to `ensure_ascii=True`, whose escapes are JSON's own. Existing subprocess test extended with an emoji | fb3e52e |
| 2 | Two tests from 847c373 write Cyrillic fixtures without `encoding="utf-8"` and error under a non-UTF-8 locale | low | fix | Regression introduced by this review's own commit; every other writer in the file already passes the encoding | bd25036 |
