#!/usr/bin/env bash
# Wait until a URL answers with HTTP 2xx, or fail after a timeout.
#
#   bash scripts/wait-for.sh http://127.0.0.1:8000/health/ready 60
set -euo pipefail

URL="${1:?usage: wait-for.sh URL [TIMEOUT_SECONDS]}"
TIMEOUT="${2:-60}"
deadline=$(( $(date +%s) + TIMEOUT ))

until curl --silent --fail --max-time 5 "$URL" >/dev/null 2>&1; do
  if [ "$(date +%s)" -ge "$deadline" ]; then
    echo "wait-for: $URL did not answer within ${TIMEOUT}s" >&2
    exit 1
  fi
  sleep 1
done
echo "wait-for: $URL is up"
