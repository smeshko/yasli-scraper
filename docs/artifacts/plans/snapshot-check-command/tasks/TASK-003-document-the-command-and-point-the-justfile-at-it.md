# TASK-003: Document the command and point the justfile at it

Depends on: TASK-002
Suggested commit: `docs(readme): document the snapshot check command`

## Goal

The README explains `check` and carries the exact justfile recipe body, and
the parent `yasli/justfile`'s `sc-snapshot-check` delegates to the command.

## Files

- `README.md` — a "Checking a snapshot" subsection under Quickstart: usage,
  what is asserted, exit codes, and the recipe body for `sc-snapshot-check`
- `../justfile` (parent `yasli/`, **not under git** — hand edit, not part of
  the commit) — replace the bash/jq body of `sc-snapshot-check` with
  `cd scraper && uv run python -m yasli_scraper check --city varna "{{ FILE }}"`
  (the `--city varna` mirrors `sc-refresh` and makes the recipe refuse a file
  labelled for another city), keeping the `FILE` default and the
  `[group('scraper')]` attribute

## Acceptance

- [ ] README documents the command, its checks, exit codes and the recipe body
- [ ] `just sc-snapshot-check <published latest.json>` exits 0 and prints the
      summary
- [ ] `just sc-snapshot-check <broken copy>` exits 1 and prints the failure
      line(s)
- [ ] `just --list` still shows `sc-snapshot-check` in the scraper group

Evidence: the README diff, `sed -n '/^sc-snapshot-check/,/^$/p' ../justfile`
showing the new body, and the two `just` invocations with their exit codes.

## Steps

- [ ] Write the README subsection (usage first, then the recipe body in a
      fenced block so it can be pasted back into a fresh justfile)
- [ ] Edit the parent justfile recipe by hand; keep the comment line above it
- [ ] Download the published `latest.json` read-only (RESEARCH.md → Useful
      Commands) and run the pass case through `just`
- [ ] Create the broken copy with `jq '.institutions[0].phone = null'` and run
      the fail case through `just`
- [ ] Stage `README.md` only; the justfile lives outside the repo

## Notes

`git add` must not be run from the parent directory; the justfile is not in
any repo and there is nothing to stage for it. The README is the durable
record of what the recipe should say.
