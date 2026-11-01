#!/usr/bin/env bash
# The repository's gate, what CI runs: lint and tests. tests/test_schema_artifact.py fails when models.py and the
# committed schema disagree.
set -euo pipefail
uv run ruff check .
uv run pytest
