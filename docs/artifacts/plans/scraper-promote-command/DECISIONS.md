# Decisions — Promote a validated local snapshot to R2

Date: 2026-09-19

---

## 1. What `promote` publishes

### Options Considered

1. **The file's exact bytes** — upload the checked `bytes` verbatim through a
   new bytes-level R2 function.
2. **Re-serialise the model** — parse to `Snapshot`, then
   `model_dump_json(indent=2)` exactly as `run` does.

### Dependencies

`r2.put_snapshot` currently takes a `Snapshot` and serialises it itself, so
today no caller can put unmodified bytes into R2. `check_snapshot` operates on
bytes and reports on those bytes.

### Selected Option

Option 1 — the file's exact bytes, via `r2.put_snapshot_bytes`, with
`put_snapshot` delegating to it after serialising.

### Rationale

YAS-17 exists because the artifact validated locally is never the artifact
published. Re-serialising re-opens exactly that gap in miniature: key order,
indentation or datetime rendering could differ from the file that passed the
checks, so the checked bytes and the published bytes would again be two
different things. Byte identity is also directly testable — the moto test
compares `path.read_bytes()` against each object body.

### Rejected Options

- Option 2 — guarantees canonical form but breaks the one property the command
  exists to provide. It also leaves `r2.py` untouched only by accident: the
  moment a promoted file's formatting matters, the function would need
  splitting anyway.

---

## 2. What gates the upload

### Options Considered

1. **Full `check_snapshot`, no escape hatch** — contract, key presence, roster,
   coverage and noise; any failure refuses.
2. **Full checks plus `--force`** — same gate with a documented bypass.
3. **Model contract only** — what YAS-17 literally proposes.

### Dependencies

`check.check_snapshot` is already pure and returns every failure in one pass;
`EXPECTED_ROSTER` lives in the same module and is updated when the portal
roster changes.

### Selected Option

Option 1 — full checks, no bypass.

### Rationale

Makes `promote` exactly `check` + upload, so "it passed `sc-snapshot-check`" and
"it is publishable" become the same statement. The roster check also
subsumes `run`'s crude `MIN_EXPECTED_INSTITUTIONS` floor on this path.

### Rejected Options

- Option 2 — a bypass would be reached for precisely the case it is most
  dangerous in: a roster that legitimately changed. The correct response there
  is a one-line edit to `EXPECTED_ROSTER` plus a commit that records it, not an
  unreviewed publish.
- Option 3 — a three-institution file with null contacts would validate against
  the model and publish. That is weaker than the manual ritual this command
  replaces.

---

## 3. How the object-key city is chosen

### Options Considered

1. **Required `--city`, asserted against the file** — publishing names its
   target prefix out loud.
2. **Optional `--city`, like `check`** — the key comes from the file's own
   `city`; the flag only asserts when given.

### Dependencies

`check` already defines `--city` as an assertion that never overrides the file.
`check_snapshot` fails any city with no `EXPECTED_ROSTER` entry, so a file that
passes the gate always carries a known, string-typed `city`.

### Selected Option

Option 2 — optional `--city`, identical in meaning to `check`'s.

### Rationale

One CLI surface with one meaning for one flag. The gate already guarantees the
city is known and the file is internally consistent, so a bare
`promote file.json` cannot publish under an unexpected prefix — the worst case
is publishing a valid Varna snapshot to `snapshots/varna/`. A recipe or script
that wants the stronger assertion passes `--city varna`, as `sc-promote` will.

### Rejected Options

- Option 1 — buys deliberateness at the cost of divergence from `check`, and
  the failure it protects against (a valid file for city A published under city
  B's prefix) is already impossible once the key is derived from the file.

---

## 4. What ceremony guards production `latest.json`

### Options Considered

1. **`--dry-run` plus a printed receipt** — rehearse, then publish and record
   both keys.
2. **Interactive confirmation unless `--yes`** — prompt before writing.
3. **No ceremony** — checks pass, upload, like `run`.

### Dependencies

The command is operator-run, sometimes through Docker and potentially from a
non-TTY. An operator needs a durable record of what was published where — the
rollback *source* is the pre-promote copy of `latest.json` (see PLAN's Risks),
but the keys name what has to be undone.

### Selected Option

Option 1.

### Rationale

`--dry-run` answers "what would this write" without a network call; the receipt
puts both exact keys in scrollback, so the operator can see what landed and
verify it afterwards. Both work identically under a TTY and a pipe.

### Rejected Options

- Option 2 — a prompt breaks `docker run` and any scripted use unless `--yes` is
  threaded everywhere, and an operator who typed `promote` on a file that just
  passed every check has already expressed intent.
- Option 3 — cheap, but leaves no record of what was published.

---

## 5. Whether `--dry-run` requires the R2 environment

### Options Considered

1. **Require the four `R2_*` vars** — dry-run rehearses the full precondition.
2. **Skip env validation** — dry-run is credential-free, like `check`.

### Dependencies

`validate_env()` returns the first missing variable name; `check` already
provides a completely credential-free path over the same file.

### Selected Option

Option 1 — `--dry-run` validates the environment, builds no client and makes no
S3 call.

### Rationale

The point of a rehearsal is to fail on everything the real run would fail on
except the write itself. A dry-run that passes with no credentials would
tell the operator nothing they did not already learn from `check`.

### Rejected Options

- Option 2 — collapses `promote --dry-run` into a slightly wordier `check`.

---

## 6. Where the receipt is printed

### Options Considered

1. **stdout, after the summary** — accepting that `promote`'s stdout is not one
   JSON document.
2. **stderr** — keeps stdout a single JSON object, as `check` guarantees.
3. **Suppress the summary on `promote`** — receipt only on stdout.

### Dependencies

`check`'s contract is "exactly one JSON object on stdout, `check failed:` lines
on stderr". `promote` is a separate subcommand and can define its own.

### Selected Option

Option 1.

### Rationale

The summary is the evidence that the checks ran on the bytes being published,
so it belongs in the same output as the keys they were published to. Nothing
pipes `promote`; `check` stays the machine-readable command, and README states
the difference explicitly.

### Rejected Options

- Option 2 — stderr is where failures live in this CLI; a success receipt there
  would be misread, and it splits the record of one action across two streams.
- Option 3 — loses the "these checks, these bytes, these keys" record that makes
  the receipt worth printing.

---

## 7. How the stale-file risk is mitigated

*Added during validation (round-1 #7).*

### Options Considered

1. **Print `scraped_at` in the receipt** — display only, no refusal.
2. **Add `scraped_at` to `check.CheckReport.summary`** — both `check` and
   `promote` would show it.
3. **A freshness guard** — refuse when `scraped_at` is older than a threshold.
4. **Nothing** — document the hazard in README and rely on the operator.

### Dependencies

`check.py`'s `_summary()` does not carry `scraped_at` today, and `check`'s
stdout contract (exactly one JSON object, with a pinned field set) is covered by
`tests/test_check.py` and `tests/test_cli.py`. `models.Snapshot.scraped_at` is
an `AwareDatetime` serialised to a Z-suffixed ISO string, and the contract check
has already validated it by the time `promote` reaches the receipt.

### Selected Option

Option 1 — `promote` prints the payload's `scraped_at` **before** it uploads,
with a rendered age alongside the exact ISO stamp
(`scraped_at: 2026-09-15T13:05:33Z (4d 2h old)`), and the two keys following on
success.

### Rationale

The original mitigation for this risk was a restatement of the risk: printing
the *destination* keys says nothing about the age of the *source*. One line of
output makes the hazard visible, costs nothing, and refuses nothing. The age is
rendered rather than left as a bare ISO stamp (validation round-3 #9): the risk
is phrased as "a week-old snapshot", and an operator should not have to do date
subtraction in their head at the moment they are least likely to. The exact ISO
string stays in the line so tests can assert on it verbatim. It is
printed before the two `put_object` calls, not with the keys afterwards
(validation round-2 #7): a line that appears only once the object is already
live is a post-mortem aid, not a mitigation.

### Rejected Options

- Option 2 — widens the blast radius to `check`'s output contract and its tests
  for a field only `promote` needs.
- Option 3 — a threshold would be arbitrary, and a legitimate re-publish of a
  known-good older snapshot (the rollback case) is exactly when it would fire.
- Option 4 — leaves the plan's own top risk with no real mitigation.
