#!/usr/bin/env bash
# Fail if an authentication-as-a-service or Supabase package appears in either lockfile
# (BR8.10, AC1.4.4, NFR1.3, NFR2.1; CON-001, CON-002). Authentication stays custom and
# backend-controlled.
#
#   bash scripts/check-denylist.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PNPM_LOCK="$ROOT/frontend/pnpm-lock.yaml"
UV_LOCK="$ROOT/backend/uv.lock"

# npm package names: exact names, or a scope/prefix ending in '*'.
NPM_DENY=(
  "supabase" "@supabase/*" "next-auth" "@auth/*" "@clerk/*" "@auth0/*" "auth0"
  "firebase" "firebase-admin" "@firebase/*" "@okta/*" "@kinde-oss/*" "@stytch/*" "supertokens-*"
)
# Python distribution names (normalised, lower-case).
PY_DENY=(
  "supabase" "supabase-*" "gotrue" "auth0-python" "firebase-admin" "pyrebase*"
  "supertokens-*" "okta*" "stytch" "clerk-*" "kinde-*"
)

for lock in "$PNPM_LOCK" "$UV_LOCK"; do
  if [ ! -f "$lock" ]; then
    echo "deny-list: missing lockfile $lock" >&2
    exit 1
  fi
done

matches() {
  # $1 = candidate name, $2 = pattern (exact, or prefix ending in '*')
  case "$2" in
    *"*") [[ "$1" == "${2%\*}"* ]] ;;
    *) [[ "$1" == "$2" ]] ;;
  esac
}

found=0

# pnpm-lock.yaml: package keys look like `  '@scope/name@1.2.3':` or `  name@1.2.3:`.
while IFS= read -r name; do
  for pattern in "${NPM_DENY[@]}"; do
    if matches "$name" "$pattern"; then
      echo "deny-list: forbidden npm package '$name' in frontend/pnpm-lock.yaml" >&2
      found=1
    fi
  done
done < <(sed -n -E "s/^  '?(@?[^@' ]+)@[^:]*'?:.*$/\1/p" "$PNPM_LOCK" | sort -u)

# uv.lock: `name = "package"` lines.
while IFS= read -r name; do
  lowered="$(printf '%s' "$name" | tr '[:upper:]_' '[:lower:]-')"
  for pattern in "${PY_DENY[@]}"; do
    if matches "$lowered" "$pattern"; then
      echo "deny-list: forbidden Python package '$name' in backend/uv.lock" >&2
      found=1
    fi
  done
done < <(sed -n -E 's/^name = "([^"]+)"$/\1/p' "$UV_LOCK" | sort -u)

if [ "$found" -ne 0 ]; then
  echo "deny-list: FAILED (authentication must stay custom and backend-controlled)" >&2
  exit 1
fi
echo "deny-list: OK (no auth-as-a-service or Supabase packages in either lockfile)"
