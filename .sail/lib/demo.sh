#!/usr/bin/env bash
# Runs one command with no R2 credentials in its environment, so nothing it does can reach the bucket.
# Usage: .sail/lib/demo.sh <command> [args…]
set -euo pipefail
[ $# -gt 0 ] || { echo 'usage: demo.sh <command> [args…]' >&2; exit 2; }
exec env -u R2_ACCOUNT_ID -u R2_ACCESS_KEY_ID -u R2_SECRET_ACCESS_KEY -u R2_BUCKET "$@"
