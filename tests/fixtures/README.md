# Test fixtures

`infant_39.html`, `garden_34.html`, `pg_10.html` are verbatim captures of
real per-institution HTML pages from `dg.uslugi.io`. They're used by the
parser and pipeline tests — both as parser inputs and as the bodies that
`respx`-mocked endpoints serve in the pipeline test.

The encoding is `windows-1251`. Do **not** re-encode these files; the
parser must round-trip raw bytes.

## Refresh procedure

The fixtures are stable (the source's `Last-Modified` header has been
unchanged for months), but if the source changes shape and the parser
starts failing, refresh from the spec repo:

```bash
cp ../../../initial/data/raw/infant/39.html  infant_39.html
cp ../../../initial/data/raw/garden/34.html  garden_34.html
cp ../../../initial/data/raw/pg/10.html      pg_10.html
```

(Path is relative to this directory; adjust if the spec repo is elsewhere.)

If the source HTMLs themselves are stale, refresh them first by running the
research scripts in `initial/scripts/`:

```bash
cd /path/to/yasli/initial
./scripts/01_fetch_regions.sh
./scripts/02_fetch_rajon_html.py
```

then copy as above.

## Why these three

One per reception type (`infant`, `garden`, `pg`) is enough to catch the
small variance between source pages while keeping the fixture set tiny.
`pg_10.html` is the largest (~225 KB) and exercises bigger streets blocks.
