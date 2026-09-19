# Adversarial Validation — Round 1

**Run:** 2026-09-19 04:42 UTC
**Plan:** scraper-promote-command
**Status at start:** draft
**Reviewer:** subagent (Codex unavailable — the `adversarial-review` job
`review-mu7wicpk-8z9426` failed after 6s with `You've hit your usage limit …
try again at 12:04 PM`; confirmed via `codex-companion.mjs status`, phase
`failed`. Per the shared protocol, the round ran with a clean
`general-purpose` subagent given the same adversarial framing and focus text.)

## Reviewer output

<!-- Pasted verbatim below this line. Do not edit. -->

## Findings

### Finding 1: AC-1 (byte identity of both R2 objects) cannot be produced by the test TASK-002 actually specifies
**Severity:** high
**Evidence:** PLAN.md:93 — "Both R2 objects written by `promote` are byte-identical to the local file (moto test compares `path.read_bytes()` against each object body)". But TASK-002 RED step 1 says "a helper that patches `r2.put_snapshot_bytes` to record `(city, body)` and return fixed keys", and step 2 asserts "the recorded body `== path.read_bytes()`". A recorded call argument is not an object body; with `put_snapshot_bytes` patched out, the moto bucket in the same fixture is never written to. Worse, TASK-002 GREEN specifies `r2.put_snapshot_bytes(city, raw)` with no `client=`/`bucket=`, so the real path calls `make_client()` → `boto3.client(endpoint_url="https://<acct>.r2.cloudflarestorage.com", …)` (r2.py:25-31). The repo's own precedent for making that reach moto is `tests/test_run_e2e.py:117` — `monkeypatch.setattr(r2_module, "make_client", lambda env=None: client)`. No task step mentions patching `make_client`.
**Why it matters:** The plan's single reason for existing — published bytes == checked bytes, end to end — would ship with only a mock-argument assertion behind it at the CLI level.
**Proposed verdict:** apply — either add the `make_client` patch and assert on `get_object(...)["Body"].read()`, or downgrade AC-1's parenthetical to match the double.
**Would change:** TASK-002 "Files" + RED steps 1-2; PLAN.md:93.

### Finding 2: TASK-004 drops the repo's acceptance-evidence map, and three PLAN criteria have no covering step
**Severity:** high
**Evidence:** The archived precedent `docs/artifacts/plans/archive/2026-09-16-snapshot-check-command/tasks/TASK-004-final-validation.md` carries an `### Acceptance evidence map` table, one row per PLAN criterion. The new TASK-004 replaces it with one catch-all bullet (line 20): "`PLAN.md` acceptance criteria all met, each with its Evidence produced". Mapping one to one against PLAN.md:93-112: AC-5 (`--city` mismatch fails before upload; bare invocation publishes under the file's own city) — **no step**; AC-6 (missing R2 env var prints the `required environment variable …` line after the checks) — **no step**; AC-8 (README documents `promote` + carries the `sc-promote` recipe) — **no step**. AC-3 is only partly covered: TASK-004:33-35 checks the `latest.json` key and exit 0, never the `<UTC-ISO-timestamp>` placeholder. AC-2's "prints the same `check failed:` lines as `check`" is not compared in the negative proof (TASK-004:52-54).
**Why it matters:** A catch-all bullet is exactly the "ticked because the code looks right" the same bullet forbids; three criteria would be signed off with no named evidence.
**Proposed verdict:** apply — restore the evidence-map table with a row per criterion.
**Would change:** TASK-004, new `### Acceptance evidence map` section.

### Finding 3: The recorded rollback target is the wrong object in the exact failure mode this repo documents
**Severity:** high
**Evidence:** TASK-004:28-30 — "list `snapshots/varna/` and record the newest timestamped key **before** promoting, plus the current `latest.json` ETag". But `docs/DEPLOYMENT.md:258-266` documents a live mode titled "Manual run wrote a timestamped object but `latest.json` is stale" — the timestamped write succeeded and the `latest.json` write failed, which `tests/test_r2.py:88` pins as an invariant. In that state the newest timestamped key is a payload that was **never live**, and TASK-004:46 ("copy the pre-promote timestamped object over `latest.json`") would publish it. The ETag is recorded but no step says to match it against the timestamped objects to pick the correct source. Separately, no task writes a runnable rollback command anywhere: PLAN.md:77-79 says "with any S3 client against the R2 endpoint", TASK-003's acceptance only requires README to "name the rollback path".
**Why it matters:** The one step that exists to make rollback safe can itself publish data that was never served.
**Proposed verdict:** apply — record the rollback target by matching `latest.json`'s ETag to a timestamped object (or by downloading `latest.json` to a local file pre-promote), and put a concrete rollback command in README.
**Would change:** TASK-004 live-verification first bullet and the failure bullet; TASK-003 acceptance.

### Finding 4: `just sc-snapshot-local` takes a required argument — the step as written errors out
**Severity:** med
**Evidence:** `yasli/justfile:120` — `sc-snapshot-local FILE:` (no default, unlike `sc-snapshot-check FILE="/tmp/yasli-v2-snapshot.json"` on line 125). Verified: `just -n sc-snapshot-local` → `error: recipe 'sc-snapshot-local' got 0 positional arguments but takes 1`. RESEARCH.md:78 lists it bare as "`just sc-snapshot-local   # scrape to /tmp/yasli-v2-snapshot.json`" and TASK-004:31 invokes it bare.
**Why it matters:** The first step of the live verification does not run, and RESEARCH.md misstates a default that does not exist.
**Proposed verdict:** apply — write `just sc-snapshot-local /tmp/yasli-v2-snapshot.json` in both places.
**Would change:** RESEARCH.md:78; TASK-004:31.

### Finding 5: The drafted `sc-promote` recipe cannot pass `--dry-run`, yet TASK-003 requires confirming it does
**Severity:** med
**Evidence:** TASK-003:47-51 drafts `sc-promote FILE="/tmp/yasli-v2-snapshot.json":` → `… promote --city varna "{{ FILE }}"`. TASK-003 step 4 then asks to "confirm `just sc-promote --dry-run`-equivalent usage works from the parent directory". With that recipe, `just sc-promote --dry-run` binds `--dry-run` to `FILE`, producing `promote --city varna "--dry-run"` — argparse consumes it as the flag and then fails on the missing positional. The parent justfile already has the right pattern: `be-load-locations *ARGS:` (line 90).
**Why it matters:** The ceremony DECISIONS #4 selected (`--dry-run` before publishing) is unreachable through the only recipe operators are told to use.
**Proposed verdict:** apply — draft the recipe as `sc-promote FILE="/tmp/yasli-v2-snapshot.json" *ARGS:` (or `*ARGS` alone) and pass `{{ ARGS }}` through.
**Would change:** TASK-003 recipe block and step 4; the same block in README per TASK-003 acceptance.

### Finding 6: "A refused `promote` never touches boto3" is asserted with no step that can show it
**Severity:** med
**Evidence:** TASK-004:17-19 — "boto3 is still imported lazily so `check` and a refused `promote` never touch it". `src/yasli_scraper/r2.py:8` imports boto3 at module top, so the property depends entirely on *where* `from yasli_scraper import r2` sits inside `_run_promote`. TASK-002 GREEN lists that import as an unordered bullet ("Import `r2` lazily inside `_run_promote`") separate from the step that spells out the control flow, so a function-top import satisfies the step and breaks the claim. The failure-path test ("an `r2` double that raises if `put_snapshot_bytes` or `make_client` is called", TASK-002:25-26) cannot detect an import — neither symbol is called.
**Why it matters:** An unfalsifiable criterion in the final-validation task; the only way to check it is a `sys.modules` assertion or a subprocess, and no step calls for one.
**Proposed verdict:** apply — pin the import *after* the `report.ok` and `validate_env()` guards, and add an assertion (`"boto3" not in sys.modules` in a subprocess run) or delete the claim from TASK-004.
**Would change:** TASK-002 GREEN step ordering + a RED test; TASK-004:17-19.

### Finding 7: The stale-file "mitigation" is a restatement, and the summary the receipt sits under has no `scraped_at`
**Severity:** med
**Evidence:** PLAN.md:71-75 — "*Mitigation:* the receipt prints both keys, and README states plainly that `promote` publishes the file you name, with no freshness check." Printing the destination keys tells the operator nothing about the source file's age. Grounding the gap: `check.py:252-269` `_summary()` emits `schema_version, city, total, kinds, infant_group, null_*, preschool_null_website, noisy_values, max_phone_length` — **no `scraped_at`**, even though `models.py:82` carries it and serialises it to a Z-suffixed ISO string. So neither the summary nor the receipt shows the age of what is being published.
**Why it matters:** This is the plan's own top risk (publishing a week-old file) and nothing in the output would let an operator notice it.
**Proposed verdict:** apply — have the receipt print the file's `scraped_at` (parsed from the already-validated payload, or added to `CheckReport.summary`); that is a real mitigation at near-zero cost.
**Would change:** PLAN.md Risks bullet 1 and Scope; TASK-002 `_run_promote` receipt step + a RED test.

### Finding 8: The Goal overclaims against the plan's own Out of Scope
**Severity:** med
**Evidence:** PLAN.md:12-14 — "so publication stops being a second, unchecked scrape". PLAN.md:34-36 — "Out of Scope: Changing `run`. It keeps re-scraping … gating the weekly cron on `check_snapshot` is a separate decision". RESEARCH.md:45-47 confirms production is a Railway cron running `python -m yasli_scraper run --city varna` every Sunday 01:00 UTC. The cron overwrites `snapshots/varna/latest.json` with an unchecked re-scrape within days of TASK-004's live proof.
**Why it matters:** After this plan lands, *operator* publication is checked but *production* publication is still an unchecked scrape — a reader of the Goal (or of AC-9's live proof) would conclude otherwise, and the durability of the live evidence is a few days at most.
**Proposed verdict:** apply — restate the Goal as "operator publication stops being a second, unchecked scrape" and note in Risks that the cron re-publishes unchecked until a follow-up issue gates it.
**Would change:** PLAN.md:12-14, plus a Risks bullet (and ideally a Linear follow-up ref alongside YAS-20).

### Finding 9: `_print_report`'s stream contract is unspecified
**Severity:** low
**Evidence:** TASK-002 GREEN — "`_print_report(report) -> None` (the summary with its console-encoding fallback, then one `check failed:` line per failure)". `__main__.py:99-101` prints the summary to stdout and each failure to **stderr** (`file=sys.stderr`). TASK-002 acceptance:24 requires "prints the same `check failed:` lines as `check`", and DECISIONS #6 is explicitly about stream placement — yet the extraction step never names the stream.
**Why it matters:** A refactor that "prints" failures could land them on stdout, quietly breaking the `check` regression tests and DECISIONS #6's stated contract.
**Proposed verdict:** apply — one clause: failures go to stderr, summary to stdout.
**Would change:** TASK-002 GREEN step 1.

### Finding 10: PLAN.md is missing the `Branch:` header both archived plans carry
**Severity:** low
**Evidence:** `archive/2026-09-16-snapshot-check-command/PLAN.md:4` — `Branch: feature/yas-16-snapshot-check-command`; `archive/2026-09-15-scraper-contact-metadata/PLAN.md:4` — `Branch: feature/yas-10-scraper-contact-metadata`. The new PLAN.md:3-8 has `Status / Risk / Epic / Phase / Linear / Created` and no `Branch`.
**Why it matters:** Convention drift in the header the downstream `create-pr` / `archive-plan` flows read.
**Proposed verdict:** apply — add `Branch: feature/yas-17-scraper-promote-command`.
**Would change:** PLAN.md header.

Not findings, checked and clean: every referenced symbol and helper is real and current (`_run_check`, `validate_env`, `check_snapshot(raw, expected_city) -> CheckReport`, `EXPECTED_ROSTER`, `put_snapshot`'s `client`/`bucket`/`now` injection points, `_utc_iso_filename`, `_varna_snapshot`/`_snapshot_dict`/`_write_json`/`_write_mutated`/`_file_*`, conftest's `REPO_ENV_PATH` fixture). The claim that `put_snapshot` serialises with `indent=2` holds (r2.py:59). The claim that a passing report guarantees a known, string-typed `city` holds — `_resolve_roster` (check.py:161-165) appends a failure unless `isinstance(city, str) and city in EXPECTED_ROSTER`, so `report.ok` implies both. Task dependencies (001→002→003→004) are acyclic and sane; DECISIONS 1-6 are mutually consistent and consistent with Scope/Out-of-Scope.

## Verdict
Material findings: three high (AC-1's evidence is unproducible as specified, TASK-004 has no criterion-to-evidence map and leaves AC-5/AC-6/AC-8 uncovered, and the recorded rollback target is wrong in the documented partial-failure mode) plus five medium — the plan should not go to implementation unedited.

## Triage

All ten findings were independently re-grounded before triage: the parent
`yasli/justfile` (`sc-snapshot-local FILE:` with no default at line 120,
`be-load-locations *ARGS:` at line 90), `tests/test_run_e2e.py:117`'s
`make_client` monkeypatch, `r2.py:8`'s module-level boto3 import, `check.py`'s
`_summary()` field list, and the `Branch:` header in both archived plans. Every
claim held, so nothing was rejected as ungrounded.

Findings 7 and 8 were referred to the user under the "vs. the request" rule —
both touch choices made in the authoring interview (a freshness guard was
explicitly declined; gating `run` was explicitly put out of scope). User
decisions: print `scraped_at` in the receipt only (**not** in `check`'s summary
dict, which would change the `check` contract); reword the Goal and add a Risks
bullet for the cron gap, **without** filing a Linear follow-up.

| # | Finding | Severity | Verdict | Rationale | Applied to |
|---|---------|----------|---------|-----------|------------|
| 1 | AC-1's byte-identity evidence is unproducible: the specified test patches out `put_snapshot_bytes`, so no object body is ever compared | high | apply | Correct and load-bearing — the plan's whole purpose would rest on a mock-argument assertion; `test_run_e2e.py:117` already shows the `make_client` patch that makes moto reachable | TASK-002:Files, TASK-002:RED, PLAN.md:Acceptance Criteria |
| 2 | TASK-004 has no acceptance-evidence map; AC-5, AC-6 and AC-8 have no covering step and AC-3 is half-covered | high | apply | Verified against the archived `snapshot-check-command` TASK-004, which carries the map; the catch-all bullet contradicts itself | TASK-004:Acceptance evidence map, TASK-004:Steps |
| 3 | The pre-promote rollback target is wrong in the documented "timestamped written, latest stale" mode; no runnable rollback command exists | high | apply | `docs/DEPLOYMENT.md` documents that exact state and `tests/test_r2.py` pins it as an invariant — the newest timestamped object can be a payload that was never live | TASK-004:Live verification, TASK-003:Acceptance, PLAN.md:Risks |
| 4 | `just sc-snapshot-local` takes a required FILE argument; the plan invokes it bare | med | apply | Confirmed at `yasli/justfile:120` — the first live-verification step would error out | RESEARCH.md:Useful Commands, TASK-004:Live verification |
| 5 | The drafted `sc-promote` recipe cannot forward `--dry-run`, making DECISIONS #4's rehearsal unreachable through the documented recipe | med | apply | Confirmed; `be-load-locations *ARGS:` at `yasli/justfile:90` is the in-repo pattern for forwarding flags | TASK-003:Steps, TASK-003:Acceptance |
| 6 | "A refused promote never touches boto3" is unfalsifiable as specified — the import position is unpinned and no test can detect it | med | apply | `r2.py:8` imports boto3 at module top, so the property is purely about import placement; the existing subprocess-test pattern in `test_cli.py` makes the assertion cheap | TASK-002:GREEN, TASK-002:RED, TASK-004:Steps |
| 7 | The stale-file risk's mitigation is a restatement; neither the summary nor the receipt shows the payload's age | med | apply | Confirmed — `check.py`'s `_summary()` has no `scraped_at`. User chose the receipt-only fix, so `check`'s summary contract is untouched; `_run_promote` reads `city` and `scraped_at` from one `json.loads` of the already-validated text | PLAN.md:Goal, PLAN.md:Scope, PLAN.md:Risks, TASK-002:GREEN, TASK-002:RED, RESEARCH.md:Uncertainty |
| 8 | The Goal overclaims: the weekly cron keeps publishing unchecked re-scrapes, so the live proof's durability is days | med | apply | Accurate against the plan's own Out-of-Scope and the Railway cron schedule. User chose reword + Risks bullet, no Linear follow-up | PLAN.md:Goal, PLAN.md:Risks |
| 9 | `_print_report`'s stream contract (summary→stdout, failures→stderr) is never stated in the extraction step | low | apply | `__main__.py:99-101` splits the streams today and DECISIONS #6 depends on it; a one-clause fix removes the ambiguity | TASK-002:GREEN |
| 10 | `PLAN.md` lacks the `Branch:` header both archived plans carry | low | apply | Verified in both archived plans; downstream `create-pr`/`archive-plan` read the header block | PLAN.md:header |
