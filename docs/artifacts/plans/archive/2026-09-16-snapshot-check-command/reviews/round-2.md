# Adversarial Review — Round 2

**Run:** 2026-09-16 04:58 UTC
**Branch:** feature/yas-16-snapshot-check-command
**Base:** staging
**Commits reviewed:** 397b076..dc49346 (round-1 fixes e111c09..dc49346)
**Prior rounds in scope:** reviews/round-1.md
**Reviewer:** subagent (clean `general-purpose` agent with the round-2 focus text; Codex still usage-limited until 11:41 local).

## Codex output

<!-- Paste /codex:adversarial-review stdout verbatim below this line. Do not edit. -->

# Adversarial Review — Round 2 (subagent)

Target: branch feature/yas-16-snapshot-check-command vs staging (397b076..dc49346), round-1 fixes e111c09..dc49346
Verdict: request-changes

## Summary
Five of the six round-1 fixes close their finding fully; #1.1 and #1.2 close the reproduced case but not the class. The one material leftover is that `_summary` echoes the file's raw `schema_version`/`city` values into the stdout JSON, so a value `json.loads` accepts but `json.dumps(indent=2)` cannot serialise (a list nested ≥1000 deep) still tracebacks through the real CLI with no summary and no `check failed:` lines, and `1e400` prints `Infinity` — both contradict the "reported as a failure, not a traceback" / "stdout always valid JSON" intent the triage itself states. One small sanitiser in `_summary` fixes both. Everything else is low. Verified by running the full suite (211 passed) and ruff, a `model_dump_json` round-trip under strict mode with an IDN/unicode URL and `Z`/`+00:00`/microsecond timestamps, a json.loads-vs-jiter disagreement table (dup keys, big ints, `2.0`, NUL escapes, depth 100–9500), CLI subprocess runs on 15 scratchpad files (BOM, UTF-16, overlong, surrogate bytes, empty, deep, `1e400`), and three non-UTF-8 stdout encodings. Not re-verified this round: the live `latest.json` under strict mode (no local copy; the strict-mode commit 431980c postdates the final-validation run at dcc005c) — type analysis says nothing `run` writes is affected, but one `just sc-snapshot-check` on the live object before merge would close that gap.

## Round-1 fix verification
| # | Finding | Fix commit | Sufficient? | Notes |
|---|---------|------------|-------------|-------|
| 1 | json.loads raises beyond JSONDecodeError; NaN/Infinity reach stdout | e111c09 | partial | `check_snapshot` now never raises (verified at depth 9500, 5000-digit ints, NaN/-Infinity). But `1e400` bypasses `parse_constant` (it goes through `float()` → `inf`) and prints `"schema_version": Infinity`; and a ≥1000-deep `city`/`schema_version` passes `json.loads` (C limit ~10k) yet `json.dumps(indent=2)` (pure Python) recurses in `_run_check`. See finding 1. |
| 2 | Lone surrogate makes stdout `print` raise | 083d24c | partial | Surrogate case closed on any encoding (subprocess test is good). The general form — `print` raising `UnicodeEncodeError` on a non-UTF-8 stdout — remains for a non-ASCII `city` (`PYTHONIOENCODING=ascii`/`latin-1` → traceback). Pre-existing, not a regression. See finding 2. |
| 3 | UTF-16/UTF-32/BOM accepted | 01a2a59 | yes | Strict `decode("utf-8")` rejects UTF-16 (BOM bytes), overlong `\xc0\xaf`, surrogate bytes `\xed\xa0\x80`; UTF-8 BOM → `Unexpected UTF-8 BOM`. `utf-8-sig` not used anywhere. |
| 4 | Lax contract accepts `"true"`/`1` bools | 431980c | yes | Strict JSON mode accepts everything `run` writes: verified `model_dump_json` round-trip with IDN host + Cyrillic path/query/fragment, nursery `district_code`, `Z`, `+00:00`, microseconds. Rejects `"2"`, `"true"`, `1`, naive datetime. Residual: `2.0` for `Literal[2]` is still accepted (exit 0, summary echoes `2.0`) — pydantic literal semantics, `run` never writes it and the old jq accepted it too; not a finding. json.loads and jiter agree on duplicate keys (both last-wins) and NUL escapes; big ints (>u64) and >255-deep nesting become `contract:` lines, not crashes. |
| 5 | Multi-line failure lines | 0e1263f | yes | `_printable` applied at every point a file value reaches a line (`_label`, duplicate pair, contract loc/msg); `city:` lines use `!r`. Escapes NUL, DEL, ZWSP, NBSP, U+2028, BOM, bidi controls; keeps emoji/combining marks. Only cosmetic residuals: `"a\nb"` and `"a\\nb"` render identically, and `ch == " "` is redundant (`" ".isprintable()` is True). |
| 6 | "null" wording for absent keys | dc49346 | yes | All three messages (address, contacts, preschool website) say "null or absent"; summary keys unchanged as triaged; README wording ("no null …") does not quote messages so nothing is stale. |

## Rejections reviewed
- #7 infant-marker kind filter — agree. Verified the failure direction: a nursery/preschool named like `Палечко` gets `has_infant_group=False` from the pipeline and the gate fails loudly ("expected True"); a filter would change nothing about false negatives. Only the comment at `src/yasli_scraper/check.py:45` ("of the kindergarten") is slightly inaccurate; cosmetic.
- #8 `_load_repo_env()` before `check` — agree. `load_dotenv` is a no-op without the file, `check` neither reads nor requires env, README's "no env vars" is accurate, and it is `run`'s pre-existing behaviour.

## Findings
1. [med] [CONFIRMED] [INCOMPLETE-FIX round-1 #1] The stdout summary echoes raw `schema_version`/`city`, so a deep value still tracebacks the CLI and `1e400` prints invalid JSON
   - Where: `src/yasli_scraper/check.py:249-250` (`_summary` echoes `payload.get(...)` unsanitised); `src/yasli_scraper/__main__.py:89-93` (`json.dumps(..., indent=2)` uses the pure-Python encoder, whose recursion limit is Python's ~1000, while `json.loads`' C scanner accepts ~10 000)
   - What: `check_snapshot` is now genuinely raise-free (verified in-process up to depth 9500 for `city`, `has_infant_group`, `schema_version`), but `_run_check` is not: a `city` (or `schema_version`) that is a list nested 1000–~10 000 deep parses fine, is correctly reported (3 failures), and then `json.dumps(report.summary, indent=2)` raises `RecursionError`, losing the summary and every `check failed:` line. Separately, `1e400`/`-1e400` are not `parse_constant` literals (they go through `float()` → `±inf`), so stdout carries `"schema_version": Infinity` / `"city": -Infinity` — the triage rationale for #1 was "so stdout is always valid JSON".
   - Evidence: `uv run python -m yasli_scraper check --city varna deep_city_1200.json` → `rc=1`, stdout 0 bytes, 0 `check failed` lines, `RecursionError: maximum recursion depth exceeded`; `deep_city_990.json` → rc=1 with summary and 3 lines (window starts at ≈1000). `check --city varna inf_schema.json` → stdout `"schema_version": Infinity` (rc=1, `contract: schema_version: Input should be 2`). Neither is caught by the suite (`b"[" * 100_000` only exercises the far side of the window).
   - Suggested fix: in `_summary`, echo `schema_version`/`city` only when they are JSON scalars (`str`, `bool`, `int`, finite `float`, `None`) and otherwise `None` — that covers both symptoms in one place and keeps `json.dumps` trivially safe; add a 1500-deep `city` CLI case and a `1e400` case (`json.loads(out)` must succeed) to the tests.

2. [low] [CONFIRMED] [INCOMPLETE-FIX round-1 #2] `print(summary)` still tracebacks on a non-UTF-8 stdout when the file's `city` is non-ASCII
   - Where: `src/yasli_scraper/__main__.py:93`
   - What: the fix pre-escapes only what UTF-8 cannot encode (lone surrogates). `sys.stdout.errors` is `strict` (stderr is `backslashreplace`, which is why stderr is safe), so with a non-UTF-8 stdout any non-ASCII summary value raises. Only a non-ASCII `city` can put non-ASCII in the summary, and that file already fails (unknown city), so impact is "traceback instead of failure lines" on a non-UTF-8 console (explicit `PYTHONIOENCODING`, legacy Windows console; `LC_ALL=C` on 3.12 is coerced to UTF-8 and is fine). Pre-existing in the original commit, not a regression.
   - Evidence: `PYTHONIOENCODING=ascii uv run python -m yasli_scraper check --city varna cyrillic_city.json` → stdout 0 bytes, 0 `check failed` lines, `Traceback … UnicodeEncodeError`; same with `latin-1`; `cp1251` and default UTF-8 are fine.
   - Suggested fix: generalise the existing line to the real stream encoding: `enc = sys.stdout.encoding or "utf-8"; print(summary.encode(enc, "backslashreplace").decode(enc))`.

3. [low] [CONFIRMED] [NEW] README does not describe the two behaviours the fixes introduced (plain-UTF-8-only input, strict types)
   - Where: `README.md:39` (Contract bullet); no README change in e111c09..dc49346 (`git diff dcc005c..dc49346 --stat` touches only `src/` and `tests/`)
   - What: a hand-edited file saved with a BOM — exactly the scenario #1.3 cited — now fails with `parse: invalid JSON: Unexpected UTF-8 BOM (decode using utf-8-sig)`, whose Python-supplied hint suggests the wrong remedy, and nothing in the README says the gate requires BOM-less UTF-8 or that types are checked without coercion (`"2"`/`"true"` fail). Nothing in the README is *false*.
   - Evidence: `check bom.json` output above; README section read end-to-end.
   - Suggested fix: one clause in the Contract bullet ("the file must be plain UTF-8 without a BOM; field types are checked strictly, `"2"` is not `2`"), and optionally replace the BOM message with a fixed `parse: invalid JSON: UTF-8 BOM present; run writes plain UTF-8`.

## Verified OK
- `uv run pytest` 211 passed, `uv run ruff check .` clean at dc49346; every new test from the six fix commits exercises the thing it names (BOM, UTF-16, deep, huge-int, NaN, -Infinity, lone surrogate contract + subprocess stdout, strict `"2"`/`"true"`/`1`, `row[i]`, `(+N more)`, newline id through the CLI, "null or absent").
- `check_snapshot` never raises: fuzzed in-process with depth 100–9500 in `city`/`has_infant_group`/`schema_version`, 4000-digit and 2^64+1 ints, `1e400`, duplicate keys at root and in a row, ` ` in `external_id`, empty file, whitespace-only file, overlong and surrogate byte sequences, BOM — every case is a `parse:`/`contract:` line plus a computable summary.
- Strict JSON mode vs `run`'s output: `Snapshot.model_dump_json(indent=2)` of an institution with `https://община-варна.бг/дг/39?q=дя#фр` (serialised as punycode + percent-encoding), nursery `district_code="01"`, `Z`/`+00:00`/`.123456Z` timestamps all pass strict validation; the CLI fixture path (`json.loads(model_dump_json())` → file) exits 0 with and without `--city varna`.
- json.loads and pydantic's parser agree where it matters: duplicate keys are last-wins in both (row `phone: null, phone: ""` → both see `""` and the contract flags it); disagreements (lone surrogate, >255 depth, >u64 ints) all surface as `contract: … Invalid JSON …` lines, never as inconsistent pass/fail.
- Encoding edges: strict decode rejects overlong sequences and encoded surrogates; `utf-8-sig` is not used; stderr with `PYTHONIOENCODING=ascii` degrades to `\uXXXX` escapes.
- `_printable`: escapes every control/format/separator character tested (NUL, DEL, `\x1c`, ZWSP, NBSP, U+2028, BOM, U+2066), keeps emoji and combining marks; `--city $'var\nna'` yields one line (`expected 'var\nna'`); a 990-deep `city` yields three very long but single lines.
- Parent `yasli/justfile` lines 122–126 are still byte-identical to the README recipe.

## Triage

<!--
Verdict values:
  fix    — real bug; address now in this branch
  defer  — has merit but out of scope; capture as a follow-up
  reject — contradicts an explicit Decision in PLAN.md, or is taste/speculation
-->

Triager note: the "not re-verified" gap in the Summary was closed before this round ran — the fixed command at dc49346 was run on the currently published `latest.json` (24 MB, downloaded read-only): exit 0, empty stderr, 12 / 53 / 12, total 77, zero nulls, zero noisy values; `just sc-snapshot-check` on the same file exits 0 and on a copy with one phone nulled exits 1 with a single `coverage:` line.

| # | Finding | Severity | Verdict | Rationale | Commit |
|---|---------|----------|---------|-----------|--------|
| 1 | `_summary` echoes raw `schema_version`/`city`: a ≥1000-deep list tracebacks `json.dumps` in the CLI and `1e400` prints `Infinity` on stdout | med | fix | Same class as round-1 #1 and that fix only covered the parse side; echo only JSON scalars into the summary so stdout is always serialisable and valid | 847c373 |
| 2 | `print(summary)` still tracebacks on a non-UTF-8 console for a non-ASCII `city` | low | fix | Pre-existing, but the round-1 #2 line already exists and generalising it to the stream's encoding is one line | 7b9706a |
| 3 | README omits the plain-UTF-8-without-BOM requirement and strict typing; the BOM message's Python hint suggests `utf-8-sig`, the wrong remedy | low | fix | Behaviour introduced by round-1 #3/#4 must be documented; own the BOM message instead of Python's | 3078371 |
