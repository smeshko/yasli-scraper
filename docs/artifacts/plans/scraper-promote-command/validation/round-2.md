# Adversarial Validation — Round 2

**Run:** 2026-09-19 05:05 UTC
**Plan:** scraper-promote-command
**Status at start:** draft
**Prior rounds in scope:** validation/round-1.md
**Reviewer:** subagent (Codex still usage-limited — the limit announced in
round 1 resets at 12:04 local, after this round)

## Reviewer output

<!-- Pasted verbatim below this line. Do not edit. -->

## Findings

### Finding 1: The byte-identity test cannot obtain the keys it is told to assert on
**Severity:** med
**Evidence:** TASK-002 RED step 2 — "call `main(["promote", str(path)])`, then for **both** returned keys assert `s3.get_object(Bucket=…, Key=key)["Body"].read() == path.read_bytes()`". `__main__.main()` returns `int` (`src/yasli_scraper/__main__.py:105,157`); the keys are returned by `r2.put_snapshot_bytes`, which TASK-002 GREEN step 6 calls *inside* `_run_promote` with no `now=` injection. The timestamped key is therefore real-clock and unknowable to the test. Same problem in `test_promote_success_prints_both_keys` and in TASK-004 map row 1.
**Why it matters:** Round-1 finding 1 replaced "assert on the mock's recorded args" with "read the object bodies back", but never said how the test discovers the timestamped key — so the plan's central test is still unwritable as specified.
**Proposed verdict:** apply — say explicitly: `list_objects_v2(Prefix="snapshots/varna/")`, assert exactly two keys, or `monkeypatch.setattr(r2_module, "_utc_iso_filename", lambda now=None: "2026-09-15T13:05:33Z")` for an exact key.
**Would change:** TASK-002 RED steps 2 and 9; TASK-004 map row 1.

### Finding 2: The boto3 subprocess test offers two mutually exclusive forms, and the primary one asserts nothing
**Severity:** med
**Evidence:** TASK-002 RED step 4 — "run `[sys.executable, "-m", "yasli_scraper", "promote", str(bad_path)]` via `subprocess.run` with a tiny `-c` wrapper (or a `PYTHONSTARTUP`-free `python -c` that imports `main`, calls it, and prints `"boto3" in sys.modules`)". You cannot run `-m yasli_scraper` *and* a `-c` wrapper; the `-m` form exits before anything can inspect `sys.modules`. Only the parenthetical works — verified: `uv run python -c "import sys; from yasli_scraper.__main__ import main; rc=main(['check','/nonexistent.json']); print('boto3' in sys.modules)"` → `False`, rc `1`.
**Why it matters:** An implementer following the bolded first form ships a test that proves nothing about boto3, which is the entire point of round-1 finding 6.
**Proposed verdict:** apply — delete the `-m` variant and pin the `-c` form (plus `capture_output=True`, `timeout=60`, `env={**os.environ}`, matching `tests/test_cli.py:436`).
**Would change:** TASK-002 RED step 4.

### Finding 3: TASK-004's import-position claim over-reaches the single test it names as proof
**Severity:** med
**Evidence:** TASK-004:18-21 — "the `from yasli_scraper import r2` inside `_run_promote` still sits after the check, city/`scraped_at` and `validate_env` guards — proven by `test_promote_failing_file_never_imports_boto3`, not by reading the code". That test uses a *failing* file, so it returns at GREEN step 2 and exercises only the check guard. An implementation that put the `r2` import between step 2 and step 4 would pass the test while breaking the `validate_env` and `--dry-run` guards (GREEN steps 4-5, DECISIONS §5).
**Why it matters:** Round-1 finding 6 objected to an unfalsifiable claim; the edit narrowed the claim's *evidence* but widened the claim itself.
**Proposed verdict:** apply — either add two subprocess cases (missing `R2_BUCKET` → `False`; `--dry-run` on a valid file → `False`) or scope the TASK-004 bullet to the check guard alone.
**Would change:** TASK-004 step 4; TASK-002 RED step 4 (parametrise).

### Finding 4: The negative proof diffs against a baseline the successful promote already invalidated
**Severity:** med
**Evidence:** TASK-004:52-53 — "Record the pre-promote listing of `snapshots/varna/` for the negative proof below". TASK-004:79-81 — "confirm it exits `1` and that `snapshots/varna/` gained no new object (diff the prefix listing against the pre-promote one)". Between those two steps, TASK-004:61 runs the real promote, which adds one timestamped object (`r2.py:60,64`). The diff will always show one added key.
**Why it matters:** The negative proof — the evidence for criterion 3 — is guaranteed to look like a failure, so it will either be waved through or mis-debugged.
**Proposed verdict:** apply — take the baseline listing immediately before the corrupted run, not before the real promote.
**Would change:** TASK-004 Live verification bullet 2 and the Negative proof section.

### Finding 5: No behaviour is specified for an upload that raises — and that is the exact state rollback exists for
**Severity:** med
**Evidence:** TASK-002 GREEN step 6 — "`timestamped, latest = r2.put_snapshot_bytes(city, raw)` and print the receipt". No try/except anywhere in the task. `r2.put_snapshot_bytes` propagates (`tests/test_r2.py:108` pins `pytest.raises(RuntimeError)` on the equivalent path). TASK-003 step 1 enumerates exit codes as "`0` published, `1` any check or env failure, `2` argparse usage" — no upload-failure case. So a failed *second* write gives the operator a raw boto3 traceback and **no receipt**, i.e. no record of the timestamped key that did land.
**Why it matters:** DECISIONS §4 justifies the receipt as "what a rollback needs", and PLAN Risks 3-4 build the whole rollback story on the partial-failure mode — which is precisely the case where the receipt is never printed.
**Proposed verdict:** apply — wrap the put, print `error: upload failed: …` on stderr naming which key was reached, return `1`; add a RED test and the exit code to TASK-003's list.
**Would change:** TASK-002 GREEN step 6 + Acceptance + a RED test; TASK-003 step 1.

### Finding 6: The drafted rollback command will not authenticate against R2
**Severity:** med
**Evidence:** TASK-003:64-67 — "`aws s3 cp --endpoint-url "https://$R2_ACCOUNT_ID.r2.cloudflarestorage.com" "s3://$R2_BUCKET/snapshots/varna/latest.json" /tmp/yasli-rollback.json`". The AWS CLI reads `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`; this repo's vars are `R2_ACCESS_KEY_ID`/`R2_SECRET_ACCESS_KEY` (`__main__.py:15-20`, `r2.py:26-30`). Nothing maps them, so the command fails with "Unable to locate credentials" (and R2 also needs `--region auto`, which `make_client` supplies and this does not). `grep -rn "aws s3\|awscli" README.md docs/` returns nothing outside this plan — the AWS CLI is not a documented tool of this project.
**Why it matters:** TASK-003's acceptance requires a **runnable** rollback command (round-1 finding 3's fix) and TASK-004:72-75 executes it under failure pressure. A command that errors on credentials at that moment is worse than none.
**Proposed verdict:** apply — either export the mapping inline (`AWS_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID" AWS_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY" AWS_DEFAULT_REGION=auto aws s3 cp …`) or, better, use the repo's own stack: `uv run python -c` over `r2.make_client()`, which already reads the right vars and needs no new tooling.
**Would change:** TASK-003 step 5 and the README block it produces.

### Finding 7: The stale-file mitigation prints `scraped_at` *after* the object is already live (pushback on triage #7)
**Severity:** med
**Evidence:** TASK-002 GREEN step 6 — "`r2.put_snapshot_bytes(city, raw)` **and print** the receipt: `scraped_at`, then the timestamped key, then the latest key". PLAN.md:80-82 claims the opposite effect: "the operator sees the age of what they are publishing **before the command reports success**". DECISIONS §7 rationale: "makes the hazard visible **at the moment of publishing**". On the real path the publish has already happened when the line appears.
**Why it matters:** I accept the user's call (receipt-only, no guard, no `check` summary change) — but as sequenced it is a post-mortem aid, not a mitigation, and the plan's Risks text overstates it. Printing the `scraped_at` line *before* the two `put_object` calls costs nothing, is strictly better, and makes the Risks wording true.
**Proposed verdict:** apply — move the `scraped_at` print above the `put_snapshot_bytes` call in step 6 (keys still printed after), or soften PLAN Risks bullet 1.
**Would change:** TASK-002 GREEN step 6; PLAN.md:80-83.

### Minor findings (6)

- **8 (low-med) — the moto promote fixture will hit `NoSuchBucket` if it copies the existing env fixture.** TASK-002 RED step 1 says "`monkeypatch.setenv` for the four `R2_*` vars"; `tests/test_cli.py:22-25`'s `all_env` sets every var to `f"test-{name.lower()}"`, so `R2_BUCKET="test-r2_bucket"`, while `put_snapshot_bytes` with no `bucket=` resolves `os.environ["R2_BUCKET"]` (`r2.py:57`). `tests/test_run_e2e.py:100` sets `R2_BUCKET` to the created `BUCKET` explicitly. *apply* — state that `R2_BUCKET` must equal the created bucket. → TASK-002 RED step 1.
- **9 (low) — TASK-001 states two incompatible signatures.** Files: `put_snapshot_bytes(city, body, *, client, bucket, now)` (required kwargs); GREEN: `*, client=None, bucket=None, now=None`. TASK-002 GREEN step 6 calls `put_snapshot_bytes(city, raw)` with neither. *apply* — make Files match GREEN. → TASK-001 Files.
- **10 (low) — after a rollback, the newest timestamped object is *again* a payload that was never served.** TASK-003:30-33 frames the "not the newest timestamped object" rule as the `docs/DEPLOYMENT.md` partial-failure special case; PLAN Out of Scope:50-51 confirms rollback never deletes the bad timestamped object, so the hazard is permanent, not exceptional. *apply* — one clause in README stating the rule holds after every rollback too. → TASK-003 acceptance bullet 5.
- **11 (low) — DECISIONS §7 carries a stray duplicated rejection.** Lines 246 and 249 both start "Option 3"; the second ("loses the 'these checks, these bytes, these keys' record") is pasted from §6's Option 3 and is not about a freshness guard. *apply* — delete it. → DECISIONS.md §7.
- **12 (low) — evidence map row 8 omits a named test file.** PLAN criterion 8 names `tests/test_r2.py`, `tests/test_run_e2e.py` **and** `tests/test_cli.py`; TASK-004:36 lists only the first two. *apply*. → TASK-004 map row 8.
- **13 (low) — pushback on triage #8's "no Linear follow-up".** PLAN.md:90 reads "Gating `run` on `check_snapshot` is the obvious follow-up", which a later reader will take to mean a ticket exists (RESEARCH.md:118 files exactly this kind of gap as YAS-20). The user's no-ticket call can stand, but the line should say so: "no follow-up issue is filed". *apply* — wording only. → PLAN.md Risks bullet 2.

## Round-1 sufficiency

1. **Still open (partial).** The `make_client` patch and object-body read-back landed, but the test cannot name the timestamped key — see Finding 1.
2. **Closed.** Map restored with 11 rows; numbering matches PLAN.md's 11 criteria exactly (verified one-to-one); AC-5/6/7/9 now covered; criterion 3's stderr comparison added. Two nits: Findings 4 and 12.
3. **Closed.** PLAN Risks 3-4, TASK-003 acceptance and TASK-004:46-51 all now use the pre-promote download of `latest.json`. But the "runnable command" it demands is not runnable — Finding 6 — and the residual orphan is under-stated — Finding 10.
4. **Closed.** `RESEARCH.md:78-80` carries the note and the explicit path; `TASK-004:54` passes it.
5. **Closed and verified empirically.** `just 1.51.0` accepts `FILE="…" *ARGS:`; tested: bare → default + empty ARGS; `/tmp/x.json --dry-run` → `FILE=[/tmp/x.json] ARGS=[--dry-run]`; `just -n` prints the interpolated command. The signature and the acceptance bullet are correct.
6. **Still open.** Import position is now pinned in GREEN steps 1-6 and called out at TASK-002:122-125 — good — but the proving test is unwritable as specified (Finding 2) and the claim it is said to prove is wider than it (Finding 3).
7. **Still open (sequencing).** Receipt-only was implemented everywhere consistently (PLAN Scope/Risks/AC-2, DECISIONS §7, TASK-002), but printed after the write — Finding 7.
8. **Closed.** Goal reworded to "**operator** publication", cron Risks bullet added. Wording nit in Finding 13.
9. **Closed.** TASK-002 GREEN step 1 now names both streams and forbids collapsing them; matches `__main__.py:99-101`.
10. **Closed.** `Branch: feature/yas-17-scraper-promote-command` at PLAN.md:4.

Re-checked clean from round 1: `_resolve_roster` (`check.py:161-168`) still guarantees a passing report implies a string `city` in `EXPECTED_ROSTER`; `Snapshot.scraped_at` is required with no default (`models.py:82`) and JSON-strict mode accepts only a string, so GREEN step 3's `json.loads` + `isinstance` guards are safe; `_file_missing_phone_key`/`_file_null_phone`/`_file_wrong_nursery_count`/`_file_invalid_utf8` all exist (`test_cli.py:287-307`); `_write_json` uses compact `json.dumps` so the fixture bytes genuinely differ from `model_dump_json(indent=2)` — a real byte-identity test; `_varna_snapshot()`'s `scraped_at` is fixed at `2026-09-15T13:05:33Z`, so the receipt test is deterministic; task DAG and DECISIONS 1-6 remain consistent.

## Verdict
Yes — 7 material new findings (5 med with real implementation consequences), of which 4 were introduced or left half-closed by the round-1 edits themselves; round-1 findings 1, 6 and 7 are not yet closed.

## Triage

Each finding was re-grounded before triage. Confirmed independently: the
orphaned `Option 3` bullet at `DECISIONS.md:71` (a real structural defect the
round-1 §7 insertion introduced — the anchor split §6's Rejected Options list);
the `put_snapshot_bytes` signature mismatch between TASK-001's Files and GREEN
sections; `all_env` at `tests/test_cli.py:22-25` setting `R2_BUCKET` to
`test-r2_bucket` while `test_run_e2e.py:100` overrides it with the created
bucket; the existing subprocess idiom at `tests/test_cli.py:436` using
`-m yasli_scraper` with no way to inspect the child's `sys.modules`; and that
`aws` exists on this machine but appears nowhere in the repo's docs, with
`R2_*` names that the AWS CLI does not read.

No finding was escalated to the user this round: none contradicts an
interview decision. Finding 7 is an explicit pushback on round-1 #7's
*sequencing*, not on the user's receipt-only choice, and accepting it makes the
user's chosen mitigation actually work. Finding 13 records the user's
no-follow-up decision in the plan text rather than reversing it. Finding 5 adds
error handling the command needs but no task owned — in scope for "a promote
command that publishes safely", not a scope widening.

| # | Finding | Severity | Verdict | Rationale | Applied to |
|---|---------|----------|---------|-----------|------------|
| 1 | The byte-identity test has no way to learn the real-clock timestamped key it must assert on | med | apply | Round-1 #1 fixed the assertion target but not key discovery; pinning `_utc_iso_filename` makes both keys exact and the test deterministic | TASK-002:RED, TASK-004:map row 1 |
| 2 | The boto3 subprocess test names two mutually exclusive forms and bolds the one that proves nothing | med | apply | Confirmed — `-m yasli_scraper` exits before `sys.modules` can be read; only the `-c` form works | TASK-002:RED |
| 3 | TASK-004's import-position claim is wider than the single failing-file test named as its proof | med | apply | An import between the check guard and `validate_env` would pass that test and still break DECISIONS §5; parametrising over three cases closes it | TASK-002:RED, TASK-004:Steps |
| 4 | The negative proof's baseline listing is taken before the real promote, so the diff always shows one added key | med | apply | Correct sequencing bug in my round-1 edit — the baseline must be taken immediately before the corrupted run | TASK-004:Live verification, TASK-004:Negative proof |
| 5 | No behaviour specified when the upload raises — exactly the partial-failure state the rollback story is built on | med | apply | `put_snapshot_bytes` propagates; without a handler the operator gets a traceback and no record of the timestamped key that landed | TASK-002:GREEN, TASK-002:RED, TASK-002:Acceptance, TASK-003:Steps |
| 6 | The drafted `aws s3 cp` rollback command cannot authenticate — wrong env var names, undocumented tool | med | apply | `R2_ACCESS_KEY_ID` ≠ `AWS_ACCESS_KEY_ID`; using `r2.make_client()` reuses the repo's own credentials path and adds no tooling | TASK-003:Steps, TASK-003:Acceptance |
| 7 | `scraped_at` is printed after the object is already live, so the "mitigation" is a post-mortem | med | apply | Pushback on round-1 #7's sequencing, not on the user's receipt-only choice; printing before the put costs nothing and makes PLAN's Risks text true | TASK-002:GREEN, PLAN.md:Risks |
| 8 | Reusing the `all_env` fixture gives `R2_BUCKET=test-r2_bucket`, so the moto promote test would hit `NoSuchBucket` | low | apply | Confirmed against both fixtures; `test_run_e2e.py:100` is the precedent | TASK-002:RED |
| 9 | TASK-001's Files and GREEN sections state incompatible `put_snapshot_bytes` signatures | low | apply | Files shows required kwargs, GREEN defaults them, and TASK-002 calls with neither | TASK-001:Files |
| 10 | The "never roll back to the newest timestamped object" rule is framed as a special case when it is permanent | low | apply | Rollback never deletes the superseded object, so the hazard survives every rollback | TASK-003:Acceptance |
| 11 | `DECISIONS.md` §7 ends with an orphaned `Option 3` bullet belonging to §6 | low | apply | Structural defect introduced by the round-1 insertion anchor; verified at `DECISIONS.md:71` | DECISIONS.md |
| 12 | Evidence map row 8 omits `tests/test_cli.py`, which PLAN criterion 8 names | low | apply | One-word completeness fix to the map restored in round 1 | TASK-004:map row 8 |
| 13 | "the obvious follow-up" implies a ticket exists; the user decided not to file one | low | apply | Records the decision honestly instead of leaving a later reader hunting for an issue | PLAN.md:Risks |
