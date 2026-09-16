# Plan: Snapshot check command

Status: draft
Branch: feature/yas-16-snapshot-check-command
Risk: medium
Epic: none
Phase: none
Linear: YAS-16
Created: 2026-09-15

## Goal

`sc-snapshot-check` proves a snapshot is publishable — roster shape (per-kind
counts, unique ids, the infant-group marker) *and* contact coverage — from
one versioned, tested command in the scraper instead of an unversioned jq
block in the parent justfile. It does not prove *which* institutions are in
the file: identity substitution under novel ids is a deliberate non-goal (see
Out of Scope).

## Scope

- `src/yasli_scraper/check.py`: a pure `check_snapshot(raw, expected_city)`
  that validates the file against the `Snapshot` contract, asserts the four
  contact keys are present on every raw row, checks the per-city roster (12
  nurseries, 53 kindergartens, 12 preschools, no null `address`, no duplicate
  `(kind, external_id)`, the `Палечко` infant-group marker present and
  flagged), contact coverage (no null `phone`/`email`/`director`; no
  `preschool` with a null `website`) and whitespace noise (no leading/trailing
  whitespace, tab or `\r` in `phone`/`email`/`director`/`website`/`address`),
  runs those semantic checks on the raw rows independently of contract
  validation so every failure is reported together, tolerates unparseable
  bytes (invalid UTF-8 or JSON) and structurally malformed input (non-object
  root, non-list `institutions`, non-object rows) by reporting a failure
  rather than raising, and returns a summary plus a list of failures.
- `src/yasli_scraper/__main__.py`: a `check FILE [--city CITY]` subcommand that
  prints the summary as JSON on stdout, one `check failed: …` line per failure
  on stderr, and exits 0/1; `--city` asserts the file's declared city, it does
  not override it.
- `README.md`: document the command and the justfile recipe body that
  delegates to it.
- The parent `yasli/justfile` (unversioned): `sc-snapshot-check` becomes
  `cd scraper && uv run python -m yasli_scraper check --city varna "{{ FILE }}"`
  (the `--city varna` mirrors the sibling `sc-refresh` recipe).

## Out of Scope

- Uploading a validated file to R2 — that is YAS-17 (`promote`).
- Warning on conflicting `garden`/`infant` contact values — YAS-18.
- Asserting that non-preschool rows have a null `website`. Today 0/65 carry
  one, but that is a coincidence of the portal, not a contract; a kindergarten
  publishing a website must not fail the gate.
- Any change to the `run` command's floor (`MIN_EXPECTED_INSTITUTIONS`), which
  is a deliberately loose sanity check, not the roster.
- Detecting substitution of one institution by another under a novel id (an
  expected-id manifest or anchor ids). Ids are derived from the portal's URLs
  in `pipeline._external_id_from_url`, so a wholesale extraction change could
  shift them while counts stay 12/53/12 and this gate would pass. Known
  limitation, filed as YAS-20 for a follow-up; this plan's gate proves shape,
  counts and coverage, not identity.

## Research Summary

See [RESEARCH.md](./RESEARCH.md). The short version:

- The parent `yasli/` directory is **not a git repository**; the justfile is
  tracked by nothing, which is why YAS-16 was deferred and why the assertions
  must live in the scraper to be reviewed and tested.
- The scraper CLI (`__main__.py`) is argparse with a single `run` subcommand
  and eight CLI tests that call `main([...])` directly with `capsys`.
- The current recipe asserts `schema_version == 2`, 12 nurseries, 12
  preschools, 0 null addresses, nursery `district_code` non-null and the
  `Палечко` infant marker, and prints a summary object first. The archived
  contact-metadata plan's jq noise/coverage/key-presence assertions are the
  ready-made contact half.
- The `Snapshot` model already enforces `schema_version == 2`, `extra="forbid"`,
  non-empty optional strings and nursery district codes, so contract
  validation covers those for free. It does **not** prove key presence:
  missing keys default to `None`, so presence must be checked on the raw JSON.

## Decisions

- **Versioned Python command, not jq** (author's call): the parent folder has
  no git repo, so jq there is untestable and unreviewable. The justfile keeps a
  one-line delegation.
- **The command owns the roster checks too** (author's call): one checker, one
  place to update when the portal roster changes; the justfile carries no logic.
- **Key presence is checked on the raw JSON, before model validation.** The
  model would silently default an omitted `phone` to `None` and the coverage
  check would then pass on a file that violates the "keys always present"
  contract.
- **Report every failure, don't fail fast.** A bad snapshot lists everything
  wrong with it in one run; the summary is printed even when checks fail. The
  semantic checks (key presence, roster, coverage, noise) run on the raw rows
  independently of contract validation, so a file with `schema_version` 3
  *and* a wrong nursery count reports both. The only early exits are
  unparseable bytes (invalid UTF-8 or JSON) and an unusable structure
  (non-object root, non-list `institutions`), where the row checks have
  nothing to run on.
- **Exit code 1 on failure**, matching `run`'s existing error convention;
  argparse keeps 2 for usage errors.
- **Roster expectations are a per-city table** (`EXPECTED_ROSTER["varna"]`)
  pinning all three kinds — 12 nurseries, 53 kindergartens, 12 preschools —
  so `total` 77 is derived from the table, not observed, and losing a batch
  of kindergartens fails the gate the same way a 13th nursery does. The table
  is always selected by the file's own `city` field; unknown city is a
  failure, not a skip.
- **`--city` asserts the file's city, it does not override it.** An override
  would let `--city varna` bless a file whose `city` says `sofia`; as an
  assertion it lets the justfile pin which file it expects. Fixtures simply
  carry `city: "varna"`.
- **The noise regex is the jq one verbatim** (`^\s|\s$|\t|\r`) so the
  command asserts exactly what the archived plan's evidence asserted.
- **No R2 access in `check`.** It reads a local file only; fetching and
  promoting are YAS-17's concern.
- **Institution identity is `(kind, external_id)` and must be unique; there
  is no expected-id list.** `pipeline.coalesce_institutions` already merges
  scraped rows by that pair, so a duplicate in a snapshot can only come from a
  corrupted or hand-edited file and is cheap to assert. A hardcoded set of
  expected ids was considered and rejected: it fails on every legitimate
  roster change and turns the one-line table edit in Risks into a 77-line one,
  and the only thing it adds over per-kind counts plus uniqueness is
  substitution detection, which is out of scope (see Out of Scope).
- **Structurally malformed input is a contract failure, not a crash.** The raw
  key-presence scan and the summary iterate only rows that are JSON objects
  inside a list; any other shape is left to `Snapshot.model_validate` to
  report under `contract:`. The summary is always returned (counts over
  whatever object-shaped rows exist, zero when there are none) so the CLI can
  always print it.
- **Exact summary values are asserted on the synthetic fixture, not on
  `latest.json`.** The live object is overwritten by every scrape, so pinning
  `max_phone_length` 24 to it makes the evidence depend on when it is run
  (`total` 77 is different: it follows from the per-kind table and *is*
  asserted). The live smoke asserts only the roster invariants; exact values
  for the remaining summary fields live in `tests/test_check.py`.

## Risks

- **The justfile edit is unversioned and can be lost** (fresh clone, another
  machine). Mitigated by documenting the exact recipe body in the README so it
  can be restored by hand, and by the final-validation step that runs the
  recipe end to end.
- **Roster constants drift when the portal changes** (a 13th nursery or a
  54th kindergarten fails the gate). Same brittleness as today's jq, extended
  to kindergartens because the alternative — no kindergarten expectation at
  all — let a file that lost 52 of them pass; the failure message names the
  count seen vs expected so the fix is a one-line table edit.
- **Contract validation makes the check follow the model.** A future model
  change changes what the gate accepts — intended, but it means the check is
  only as strict as `models.py`.
- **A too-strict noise rule blocks legitimate data.** The rule is limited to
  leading/trailing whitespace, tabs and `\r`, which the normalisers already
  strip; internal spaces and slashes are untouched.

## Acceptance Criteria

- [ ] `uv run python -m yasli_scraper check --city varna <latest.json>` on the
      currently published snapshot exits 0, prints nothing on stderr, and
      prints a summary whose roster invariants hold: 12 nurseries, 53
      kindergartens, 12 preschools (`total` 77 follows from the table), zero
      null `address`/`phone`/`email`/`director`, 12 preschools with a
      `website`, zero noisy values. `max_phone_length` is reported, not
      asserted (the live object is overwritten by every scrape; the value
      observed on 2026-09-15 is in RESEARCH.md for reference)
- [ ] `check_snapshot` reports a failure naming the problem for each of these
      mutations of a valid snapshot (`tests/test_check.py`, one test per
      mutation): a missing contact key; a null `phone`, `email` or `director`;
      a `preschool` with null `website`; a tab, `\r` or leading/trailing space
      in a contact or `address`; a wrong nursery, kindergarten or preschool
      count; a duplicate `(kind, external_id)`; a null `address`; the
      infant-marker kindergarten absent, or present without
      `has_infant_group`; an empty-string contact (contract); an extra key
      (contract); invalid JSON; invalid UTF-8; a structurally malformed file
      (non-object root, non-list `institutions`, non-object row); a
      non-string `city`, `kind` or `external_id`; an unknown city; an
      `expected_city` that differs from the file's city — plus a
      contract error combined with a roster error reports both, and the exact
      summary values of the synthetic valid fixture are asserted there too
- [ ] The CLI exits 1 and prints one `check failed: …` line per failure,
      naming the problem, for a parametrised sample of those mutations
      (`tests/test_cli.py`: missing contact key, null `phone`, wrong nursery
      count, malformed shape, invalid UTF-8, `--city sofia` on a Varna file),
      and exits 0 with an empty stderr for the valid fixture with and without
      `--city varna`
- [ ] The CLI exits 1 with a single `error: …` line naming the path, and no
      traceback, for a missing path and for an unreadable path (a directory)
- [ ] `just sc-snapshot-check <file>` in the parent justfile delegates to the
      command and reproduces the pass and one fail case above
- [ ] The scraper README documents the command and the recipe body
- [ ] `just sc-test` and `just sc-lint` pass, with `check.py` covered by
      `tests/test_check.py` and the subcommand by `tests/test_cli.py`

## Tasks

Task state lives here. Tasks are appended by `scripts/add_task.py` and
`scripts/add_final_task.py`. Update the checkboxes as work progresses.

- [ ] TASK-001: Add the snapshot check module
- [ ] TASK-002: Wire the check subcommand into the CLI (depends on TASK-001)
- [ ] TASK-003: Document the command and point the justfile at it (depends on TASK-002)
- [ ] TASK-004: Final Validation
