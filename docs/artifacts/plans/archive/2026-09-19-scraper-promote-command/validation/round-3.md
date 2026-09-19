# Adversarial Validation — Round 3

**Run:** 2026-09-19 05:35 UTC
**Plan:** scraper-promote-command
**Status at start:** draft
**Prior rounds in scope:** validation/round-1.md, validation/round-2.md
**Reviewer:** subagent (Codex usage-limited for the whole validation — see
round-1's header)

## Reviewer output

<!-- Pasted verbatim below this line. Do not edit. -->

## Findings

### Finding 1: `test_promote_early_return_never_imports_boto3` case 2 does not return at `validate_env` — it performs a real upload to production R2
**Severity:** high
**Evidence:** `tasks/TASK-002-...md:88-89` — "2. a valid file with `R2_BUCKET` deleted from the child env (returns at `validate_env`)". But `__main__.py:70-72`, `validate_env()` calls `_load_repo_env()` → `dotenv.load_dotenv(REPO_ENV_PATH)`, and `REPO_ENV_PATH` (`__main__.py:29`) is `parents[3]/.env` = `/Users/A1E6E98/Developer/Projects/yasli/.env`, which exists (350 B) and supplies all four vars. `tests/conftest.py:8-16` neutralises it **only in-process**; a `python -c` child gets the real file. Verified in a child process: after popping all four `R2_*` vars, `REPO_ENV_PATH … exists: True` / `validate_env() -> None` / all four vars repopulated. So case 2 falls through GREEN steps 4-5 to step 7, imports `r2`, and calls `put_snapshot_bytes("varna", raw)` with the operator's real credentials — publishing the 77-institution `example.com` test fixture over production `snapshots/varna/latest.json` on every `pytest` run. (The assertion then fails, loudly — after the damage.)
**Why it matters:** The test round 2 added to prove `promote` is safe is the single most dangerous thing in the plan: a unit test that overwrites the object the backend ingests.
**Proposed verdict:** apply — set `R2_BUCKET=""` in the child env instead of deleting it (verified: empty string → `validate_env()` returns `"R2_BUCKET"`, because `load_dotenv(override=False)` skips a key already present and `__main__.py:75` treats empty as missing). Additionally have the `-c` snippet neutralise `REPO_ENV_PATH` (`import yasli_scraper.__main__ as m; m.REPO_ENV_PATH = Path("/nonexistent")`) before calling `main`, so no case silently depends on the developer's `.env` — case 3's "full env" currently does too.
**Would change:** TASK-002 RED step 4 (cases 2 and 3, plus the `-c` snippet text).

### Finding 2: Both drafted rollback commands fail as written — no `cd scraper`, and no `.env` load
**Severity:** high
**Evidence:** `TASK-003:76-88` drafts `uv run python -c "from yasli_scraper import r2; …"`. Verified from the repo root: `uv run python -c "import yasli_scraper"` → `ModuleNotFoundError: No module named 'yasli_scraper'` (there is no root `pyproject.toml`; every justfile recipe does `cd scraper && uv run …`). And from `scraper/`, with the vars not exported: `r2.make_client()` → `KeyError: 'R2_ACCOUNT_ID'` — `make_client` reads `os.environ` directly (`r2.py:24-31`) and, unlike the CLI, nothing calls `_load_repo_env()`. `os.environ['R2_BUCKET']` in both snippets has the same problem.
**Why it matters:** Round-2 #6 swapped an AWS-CLI credentials failure for a Python `KeyError` — the same defect in a new costume. TASK-004:73-76 runs this command under failure pressure, immediately after production `latest.json` has been overwritten.
**Proposed verdict:** apply — prefix with `cd scraper &&` and load the repo env explicitly (`from yasli_scraper.__main__ import _load_repo_env; _load_repo_env()` as the first statement, or `set -a; source ../.env; set +a` in the README block). Then run both once for real before the README text is transcribed.
**Would change:** TASK-003 step 5 (both code blocks) and the README block it produces.

### Finding 3: "naming how far the two-phase write got" is not producible by the specified design
**Severity:** med
**Evidence:** PLAN.md:123-124 and TASK-002:32-33 both require "one `error: upload failed: …` line naming how far the two-phase write got". But GREEN step 7 calls `r2.put_snapshot_bytes(city, raw)` and catches `Exception as exc`; `put_snapshot_bytes` computes both keys internally (`r2.py:60-61`) and returns them only on success, so on failure `_run_promote` holds neither key nor any indication of which `put_object` raised. GREEN step 7 itself concedes this — it specifies "noting that the timestamped object **may already have landed** and `latest.json` **may or may not** have been replaced" (TASK-002:155-157) — which is the opposite of naming how far it got. The RED test (TASK-002:102-106) and TASK-004 row 3 assert only "one `error: upload failed:` line" and "no `Traceback`", so the criterion would be ticked on the code looking right.
**Why it matters:** Round-2 #5's stated purpose was preserving "the only record of the timestamped key that did land". As applied, that record still does not exist, and a PLAN criterion is unfalsifiable.
**Proposed verdict:** apply — either (a) have `_run_promote` pass an explicit `now=datetime.now(timezone.utc)` and print the two candidate keys alongside the error (needs a key-building helper exposed from `r2`, e.g. `snapshot_keys(city, now)`), or (b) reword PLAN AC-3 and TASK-002 acceptance to match GREEN's honest "may or may not" wording. (b) is cheap and closes the gap; (a) is the real fix.
**Would change:** PLAN.md AC-3; TASK-002 Acceptance bullet 4 (and GREEN step 7 / TASK-001 if (a)).

### Finding 4: PLAN.md and RESEARCH.md still carry the pre-round-1 rollback model, contradicting PLAN's own Risks
**Severity:** med
**Evidence:** PLAN.md:50-51 — "Deleting or rewriting R2 objects (rollback stays a manual copy of **a timestamped object** over `latest.json`)". PLAN.md:100-102 — "the rollback source is the **pre-promote download of `latest.json` itself, not a key chosen by timestamp**". RESEARCH.md:51-53 — "Rollback for a bad `latest.json` is copying a previous `snapshots/varna/<ts>.json` over it". TASK-003:33-37 and TASK-004:49-54 use the download model.
**Why it matters:** Round-1 #3 was a high finding about exactly this hazard. Two of the five plan files still state the unsafe rule, and Out of Scope is the section an implementer reads to decide what the command must not do.
**Proposed verdict:** apply — rewrite PLAN.md:50-51 as "rollback stays a manual re-upload of the pre-promote copy of `latest.json`" and fix RESEARCH.md:51-53 the same way.
**Would change:** PLAN.md Out of Scope; RESEARCH.md Architecture Facts.

### Finding 5: TASK-004 needs four R2 operations; TASK-003 documents two
**Severity:** low
**Evidence:** TASK-004 requires listing the prefix (`:61`, `:84`, `:87`), downloading `latest.json` (`:49`, `:64`) and downloading the timestamped object from the receipt (`:68`). TASK-003:70-88 documents only get-`latest.json` and put-`latest.json`.
**Why it matters:** Three live-verification steps and the whole negative proof have no runnable command, on a machine where `aws` is not a documented tool (round-2 #6).
**Proposed verdict:** apply — add a `list_objects_v2` one-liner and parametrise the get one-liner on `Key`, in the same block.
**Would change:** TASK-003 step 5; TASK-004 live-verification and negative-proof bullets.

### Finding 6: The restore command is never executed on the happy path, yet TASK-003 claims it was transcribed from a real run
**Severity:** low
**Evidence:** TASK-003:89-90 — "Run both once during TASK-004 so the README text is transcribed from a command that actually ran, not drafted." TASK-004:73 gates the restore on "**If anything above fails**". A clean live verification therefore ships a README rollback command that has never run.
**Why it matters:** The plan's own demonstrated-not-compiled standard, applied to the command that only ever runs in an emergency.
**Proposed verdict:** apply — drill the restore against a throwaway key (`snapshots/varna/rollback-drill.json`) as an unconditional TASK-004 step, or state plainly that the restore half is unverified.
**Would change:** TASK-004 live verification; TASK-003 step 5's last clause.

### Finding 7: The pinned fake clock is the same instant as the fixture's `scraped_at`, blurring the two values the ordering test must distinguish
**Severity:** low
**Evidence:** TASK-002:61-62 pins `_utc_iso_filename` to `"2026-09-15T13:05:33Z"`; `tests/test_cli.py:239` sets `_varna_snapshot()`'s `scraped_at` to `datetime(2026, 9, 15, 13, 5, 33, tzinfo=timezone.utc)` — the identical string, as TASK-002:98-100 itself notes. The timestamped key is then `snapshots/varna/2026-09-15T13:05:33Z.json`, so the string appears on both the `scraped_at` line and the key line.
**Why it matters:** `test_promote_prints_scraped_at_before_the_keys` (round-2 #7's proof) and the dry-run "placeholder, not a real stamp" assertion both become substring-ambiguous for no reason.
**Proposed verdict:** apply — pin the fake clock to a distinct later stamp, e.g. `"2026-09-19T09:00:00Z"`.
**Would change:** TASK-002 RED steps 1, 2 and 5; TASK-004 map row 1.

### Finding 8: TASK-001's Notes now contradict TASK-002's test approach
**Severity:** low
**Evidence:** TASK-001:71-72 — "The `now` parameter must stay on both functions — the existing tests pin exact timestamped keys with it, and **TASK-002's promote tests will do the same**." TASK-002 RED step 1 pins `r2._utc_iso_filename` instead, because GREEN step 7 calls `put_snapshot_bytes(city, raw)` with no `now=` (round-2 #9's applied signature).
**Why it matters:** Stale cross-reference left by the round-2 edits; an implementer reading TASK-001 first will thread `now=` through `_run_promote`.
**Proposed verdict:** apply — keep the first half (existing `test_r2.py` tests need `now`), drop the TASK-002 clause.
**Would change:** TASK-001 Notes.

### Finding 9: Pushback on triage #7 — a bare ISO timestamp is not a legible freshness signal
**Severity:** low
**Evidence:** DECISIONS.md:240-245 — "One line of output makes the hazard visible, costs nothing, and refuses nothing." The line prints `2026-09-15T13:05:33Z`. The risk it mitigates (PLAN.md:78-79) is "a **week-old** snapshot". An operator must do the subtraction in their head, at the exact moment they are least likely to.
**Why it matters:** I accept the user's calls (no guard, no `check`-summary change) and round-2's re-sequencing; this is about the applied mitigation's legibility, not its shape. Rendering the age alongside the stamp costs one f-string and makes the mitigation actually work.
**Proposed verdict:** apply — print `scraped_at: 2026-09-15T13:05:33Z (4d 2h old)`; keep the exact ISO string in the line so tests can assert on it verbatim.
**Would change:** TASK-002 GREEN step 5 and the RED receipt test; DECISIONS §7 Selected Option.

### Finding 10: TASK-003's `docs/ARCHITECTURE.md` edit has no PLAN criterion and no evidence-map row
**Severity:** low
**Evidence:** TASK-003:17-18 and `:41` require an ARCHITECTURE.md change (both target sections are real — `docs/ARCHITECTURE.md:80` code-layout line, `:98` "Two-phase R2 write"). PLAN.md Scope:31-32 names only README, AC-10 (PLAN.md:137-138) names only README, and TASK-004 map row 10 lists only "the README diff".
**Why it matters:** A task deliverable that the final-validation gate cannot tick.
**Proposed verdict:** apply — one word in AC-10 and in map row 10.
**Would change:** PLAN.md Scope + AC-10; TASK-004 map row 10.

**Clean, checked, no finding:** the `_utc_iso_filename` monkeypatch mechanism itself (module-global lookup inside `put_snapshot_bytes`; `lambda now=None` matches the positional call; no conflict with `put_snapshot`'s `now=` tests, which inject explicitly); the `list_objects_v2` key discovery; the `sc-promote FILE="…" *ARGS:` signature (re-verified on just 1.51.0: bare → default + empty ARGS, `/tmp/x.json --dry-run` → `FILE=[/tmp/x.json] ARGS=[--dry-run]`); the negative-proof resequencing; the `_print_report` stream split against `__main__.py:99-101`; the 12 map rows against PLAN's 12 criteria (one-to-one, numbering correct after renumbering, every row's evidence producible except row 3 — Finding 3); GREEN steps 1-6 as a control flow (guards precede the import, `scraped_at` precedes both the dry-run return and the upload, `json.loads` is safe because `report.ok` implies strict-model validation passed).

## Round-2 sufficiency
1. Closed — `_utc_iso_filename` pinned + `list_objects_v2`; map row 1 updated (nit: Finding 7).
2. Closed — the `-m` variant is gone, the `-c` form is pinned with `capture_output`/`env`/`timeout`.
3. Still open — three cases added, but case 2 never reaches `validate_env` and uploads to production instead (Finding 1).
4. Closed — the baseline is now taken inside the negative-proof section, after the real promote.
5. Still open (partially) — try/except, exit code and RED test all landed, but the "naming how far the write got" half is unimplementable and GREEN contradicts it (Finding 3).
6. Still open — `aws s3 cp` replaced, but the replacement doesn't import (no `cd scraper`) and doesn't authenticate (no `.env` load) (Finding 2).
7. Closed — `scraped_at` now printed at GREEN step 5, before both branches; PLAN Risks and DECISIONS §7 match (legibility pushback: Finding 9).
8. Closed — `R2_BUCKET` explicitly set to the created bucket, with the reason stated.
9. Closed — TASK-001 Files and GREEN now both read `client=None, bucket=None, now=None` (stale Notes: Finding 8).
10. Closed in TASK-003, but the old rollback model survives in PLAN Out of Scope and RESEARCH.md (Finding 4).
11. Closed — the orphaned `Option 3` is gone; §6 and §7 Rejected Options lists are each intact.
12. Closed — map row 9 names all three test files.
13. Closed — PLAN.md:90-91 reads "**no follow-up issue is filed**".

Round-1 carry-overs: #1 **closed** (real upload path + object read-back + deterministic keys); #6 **still open** (import position is correctly pinned, but its proving test is broken — Finding 1); #7 **closed**.

## Verdict
Not ready — two high findings (a test that publishes fixture data to production R2, and rollback commands that cannot run), plus a PLAN criterion nothing can produce and a self-contradictory rollback rule; fix Findings 1-4 and the rest are cheap edits.

## Triage

Findings 1 and 2 were re-verified directly against this machine before triage,
since both are high and both concern commands that touch production R2:

- **Finding 1 confirmed.** In a child process with all four `R2_*` vars popped,
  `m.REPO_ENV_PATH.exists()` is `True` and `m.validate_env()` returns `None` —
  the repo-root `.env` repopulates every variable, because `conftest.py`'s
  neutralising fixture is in-process only. The proposed fix was verified too:
  with `R2_BUCKET` set to `""`, `validate_env()` returns `'R2_BUCKET'`
  (`load_dotenv(override=False)` will not replace a key already present), and
  with `REPO_ENV_PATH` pointed at a nonexistent file it returns
  `'R2_ACCOUNT_ID'`. Both belts are applied, not just one.
- **Finding 2 confirmed.** `uv run python -c "import yasli_scraper"` from the
  repo root gives `ModuleNotFoundError`; from `scraper/` with the vars unset,
  `r2.make_client()` gives `KeyError: 'R2_ACCOUNT_ID'`; and with
  `_load_repo_env()` called first, the client builds. The corrected form is the
  one now in the plan.

Finding 9 is the third pushback in this validation on the freshness display.
It was put to the user rather than decided here, because it touches a choice
made in the authoring interview; the user accepted the rendered age, with the
exact ISO string kept in the line so tests can assert on it verbatim.

Finding 3 offered two fixes. Option (a) — exposing a key-building helper from
`r2` so the error line can name both candidate keys — was chosen over the cheap
reword: the whole justification for the receipt (DECISIONS §4) is that it is
what a rollback needs, and the partial-write case is the one where a rollback is
actually required. A criterion reworded down to "may or may not" would leave
that case with no record at all.

This was the third round, and it again produced only `apply` rows. Per the
shared protocol the situation was put to the user rather than auto-running a
fourth round: the plan's *design* — the `r2` split, the promote control flow,
the gates and all seven decisions — has gone unchallenged for three rounds,
while the recurring defects are in the patches themselves. The user chose
apply-all-then-stop, with the applied edits re-verified against the code here
rather than by a fourth reviewer.

| # | Finding | Severity | Verdict | Rationale | Applied to |
|---|---------|----------|---------|-----------|------------|
| 1 | The boto3 early-return test's case 2 never reaches `validate_env` and would upload the test fixture to production R2 on every `pytest` run | high | apply | Verified on this machine — the repo `.env` repopulates the popped vars in a child process; fixed with both belts (`R2_BUCKET=""` **and** a neutralised `REPO_ENV_PATH`), each verified to return the expected missing-var name | TASK-002:RED |
| 2 | Both rollback commands fail as written — `ModuleNotFoundError` without `cd scraper`, `KeyError` without `_load_repo_env()` | high | apply | Verified all three states; round-2 #6 replaced an AWS-CLI credential failure with a Python one, and TASK-004 runs this command right after production `latest.json` was overwritten | TASK-003:Steps |
| 3 | PLAN AC-3's "naming how far the two-phase write got" cannot be produced — `put_snapshot_bytes` returns the keys only on success | med | apply | Fixed properly rather than reworded down: `r2` exposes `snapshot_keys(city, now)`, `_run_promote` computes the keys itself and passes `now=`, so the error line names both candidates — which is what DECISIONS §4 says the receipt is for | TASK-001:Files, TASK-001:Steps, TASK-002:GREEN, TASK-002:RED, PLAN.md:Scope |
| 4 | `PLAN.md` Out of Scope and `RESEARCH.md` still state the unsafe "roll back to a timestamped object" rule that round-1 #3 fixed everywhere else | med | apply | Confirmed both locations contradict PLAN's own Risks; Out of Scope is exactly where an implementer looks for the rule | PLAN.md:Out of Scope, RESEARCH.md:Architecture Facts |
| 5 | TASK-004 performs four distinct R2 operations; TASK-003 documents two | low | apply | The prefix listing and the timestamped-object download had no runnable command, and `aws` is not a documented tool here | TASK-003:Steps |
| 6 | The restore command only runs if something fails, yet TASK-003 claims the README text is transcribed from a real run | low | apply | Resolved with an unconditional drill against a throwaway key, so the emergency command is exercised on the happy path | TASK-004:Live verification, TASK-003:Steps |
| 7 | The pinned fake clock equals the fixture's `scraped_at`, making the ordering assertions substring-ambiguous | low | apply | Free fix — pin the clock to a distinct later stamp so the two values cannot be confused | TASK-002:RED, TASK-004:map row 1 |
| 8 | TASK-001's Notes still say TASK-002's tests will pin keys via `now=`, which round-2 #9 changed | low | apply | Stale cross-reference that would send an implementer down the wrong path | TASK-001:Notes |
| 9 | A bare ISO `scraped_at` is not a legible freshness signal for a risk phrased as "a week-old snapshot" | low | apply | Third pushback on this area, so it went to the user; they accepted the rendered age with the ISO string kept verbatim for assertions | TASK-002:GREEN, TASK-002:RED, DECISIONS.md, PLAN.md:Acceptance Criteria |
| 10 | TASK-003's `docs/ARCHITECTURE.md` deliverable has no PLAN criterion and no evidence-map row | low | apply | A task output the final-validation gate could not tick | PLAN.md:Scope, PLAN.md:Acceptance Criteria, TASK-004:map row 10 |
