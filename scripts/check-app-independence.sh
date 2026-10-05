#!/usr/bin/env bash
# Fail if one app imports the other's source (BR8.1, AC1.1.2, NFR1.1). The HTTP API is the
# only contract; the frontend's API types are GENERATED from the backend's OpenAPI document
# by scripts/export-openapi.sh, never imported from backend source.
#
#   bash scripts/check-app-independence.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
status=0

# Frontend source may not import or require anything from ../backend.
if grep -rnE "(from|import|require)\s*\(?\s*['\"](\.\./)+backend/" \
  "$ROOT/frontend/src" "$ROOT/frontend/e2e" "$ROOT/frontend/scripts" 2>/dev/null; then
  echo "app-independence: the frontend imports backend source (above)." >&2
  status=1
fi

# Backend Python may not import or read anything from the frontend tree.
if grep -rnE "^\s*(from|import)\s+frontend\b|['\"](\.\./)+frontend/" \
  --include='*.py' "$ROOT/backend/app" "$ROOT/backend/tests" "$ROOT/backend/tools" 2>/dev/null; then
  echo "app-independence: the backend references frontend source (above)." >&2
  status=1
fi

if [ "$status" -ne 0 ]; then
  exit 1
fi
echo "app-independence: OK (backend and frontend share no source; HTTP is the only contract)"
