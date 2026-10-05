#!/usr/bin/env bash
# Regenerate the frontend API types from the backend's OpenAPI document (contract Q6, D11).
#
#   bash scripts/export-openapi.sh            # regenerate frontend/src/lib/api/types.gen.ts
#   bash scripts/export-openapi.sh --check    # regenerate, then fail on drift
#
# The document comes from `app.openapi()` in-process (no server, no database). The drift
# check compares the regenerated file with a copy taken before regenerating, so it works
# before the first commit as well as in CI (where `git diff --exit-code` is equivalent).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TYPES_REL="src/lib/api/types.gen.ts"
TYPES="$ROOT/frontend/$TYPES_REL"
TMP_DIR="$(mktemp -d)"
# Native Windows tools need a native path (Git Bash may not convert it, e.g. under
# MSYS_NO_PATHCONV=1).
if command -v cygpath >/dev/null 2>&1; then
  TMP_DIR="$(cygpath -m "$TMP_DIR")"
fi
trap 'rm -rf "$TMP_DIR"' EXIT

CHECK=0
[ "${1:-}" = "--check" ] && CHECK=1
if [ "$CHECK" -eq 1 ] && [ -f "$TYPES" ]; then
  cp "$TYPES" "$TMP_DIR/before.ts"
fi

(cd "$ROOT/backend" && uv run --frozen python -m tools.export_openapi "$TMP_DIR/openapi.json")
(cd "$ROOT/frontend" && pnpm exec openapi-typescript "$TMP_DIR/openapi.json" --output "$TYPES_REL" >/dev/null)
echo "Generated frontend/$TYPES_REL"

if [ "$CHECK" -eq 1 ]; then
  if [ ! -f "$TMP_DIR/before.ts" ] || ! cmp -s "$TMP_DIR/before.ts" "$TYPES"; then
    echo "OpenAPI drift: frontend/$TYPES_REL was out of date with the backend." >&2
    echo "It has been regenerated; review and commit it." >&2
    exit 1
  fi
  echo "OpenAPI types are up to date."
fi
