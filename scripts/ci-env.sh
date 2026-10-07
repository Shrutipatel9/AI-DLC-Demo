#!/usr/bin/env bash
# Single source of the test environment (plan decision D8; infra review R-01, R-02, R-09).
#
#   source scripts/ci-env.sh
#
# Used by CI (every job that needs it) and by scripts/verify.sh. It sets:
#   - database URLs for the throwaway test databases `app_test` and `app_e2e`;
#   - throwaway signing, code and email-hash keys from `openssl rand` (never committed or logged);
#   - origins, email and limiter settings for APP_ENV=test.
# Keys that are already set in the environment are kept, so sourcing twice is safe.
# In GitHub Actions each generated key is masked with ::add-mask::. The values stay in the
# step that sourced this file (keys scoped to the steps that need them). Set
# CI_ENV_EXPORT_TO_GITHUB_ENV=1 to also export them to later steps via $GITHUB_ENV.

if [ -n "${BASH_SOURCE[0]:-}" ] && [ "${BASH_SOURCE[0]}" = "$0" ]; then
  echo "ci-env.sh must be sourced: source scripts/ci-env.sh" >&2
  exit 1
fi

_ci_env_export() {
  # $1 = name, $2 = value, $3 = "secret" to mask in GitHub Actions
  export "$1=$2"
  if [ -n "${GITHUB_ACTIONS:-}" ]; then
    if [ "${3:-}" = "secret" ]; then
      echo "::add-mask::$2"
    fi
    if [ "${CI_ENV_EXPORT_TO_GITHUB_ENV:-0}" = "1" ] && [ -n "${GITHUB_ENV:-}" ]; then
      printf '%s=%s\n' "$1" "$2" >>"$GITHUB_ENV"
    fi
  fi
}

_ci_env_random_key() {
  if ! command -v openssl >/dev/null 2>&1; then
    echo "ci-env.sh: openssl is required to generate throwaway keys" >&2
    return 1
  fi
  openssl rand -base64 48 | tr -d '\r\n'
}

# --- PostgreSQL (docker-compose.yml defaults; local-only, not secret) -----------------
_ci_env_export POSTGRES_USER "${POSTGRES_USER:-app}"
_ci_env_export POSTGRES_PASSWORD "${POSTGRES_PASSWORD:-app}"
_ci_env_export POSTGRES_HOST "${POSTGRES_HOST:-127.0.0.1}"
_ci_env_export POSTGRES_PORT "${POSTGRES_PORT:-5432}"
_ci_db_base="postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}"
_ci_env_export TEST_DATABASE_URL "${_ci_db_base}/app_test"
_ci_env_export E2E_DATABASE_URL "${_ci_db_base}/app_e2e"
_ci_env_export DATABASE_URL "${TEST_DATABASE_URL}"

# --- Throwaway keys -------------------------------------------------------------------
if [ -z "${CODE_HMAC_KEY:-}" ]; then
  _ci_env_export CODE_HMAC_KEY "$(_ci_env_random_key)" secret
fi
if [ -z "${JWT_SIGNING_KEYS:-}" ]; then
  _ci_jwt_key="$(_ci_env_random_key)"
  [ -n "${GITHUB_ACTIONS:-}" ] && echo "::add-mask::${_ci_jwt_key}"
  _ci_env_export JWT_SIGNING_KEYS "{\"ci\":\"${_ci_jwt_key}\"}" secret
  _ci_env_export JWT_ACTIVE_KID "ci"
  unset _ci_jwt_key
fi

if [ -z "${EMAIL_HASH_KEY:-}" ]; then
  _ci_env_export EMAIL_HASH_KEY "$(_ci_env_random_key)" secret
fi

# --- Application settings for APP_ENV=test --------------------------------------------
_ci_env_export APP_ENV "test"
_ci_env_export LOG_LEVEL "${LOG_LEVEL:-INFO}"
_ci_env_export FRONTEND_ORIGIN "${FRONTEND_ORIGIN:-http://localhost:3000}"
_ci_env_export REFRESH_COOKIE_SECURE "false"
_ci_env_export EMAIL_BACKEND "${EMAIL_BACKEND:-fake}"
_ci_env_export EMAIL_FROM "no-reply@example.test"
_ci_env_export SMTP_HOST "${SMTP_HOST:-127.0.0.1}"
_ci_env_export SMTP_PORT "${SMTP_PORT:-1025}"
_ci_env_export SMTP_STARTTLS "false"
# The local mail catcher needs no login; blank any real-provider credentials a developer
# keeps in backend/.env so they are never sent to Mailpit (plaintext AUTH is refused).
_ci_env_export SMTP_USERNAME ""
_ci_env_export SMTP_PASSWORD ""
_ci_env_export RATE_LIMIT_BACKEND "postgres"
# Test environments only (U2 infrastructure post-review R-02): the e2e journeys make many
# auth calls from one address. Production defaults stay 20 and 60; the limiter's own tests
# set the low limits explicitly. Values already set are kept.
_ci_env_export AUTH_RATE_LIMIT_PER_MINUTE "${AUTH_RATE_LIMIT_PER_MINUTE:-1000}"
_ci_env_export REFRESH_RATE_LIMIT_PER_MINUTE "${REFRESH_RATE_LIMIT_PER_MINUTE:-1000}"
_ci_env_export METRICS_ENABLED "false"
# Payments (U5): a test price and the fake provider (never Stripe in tests, NFR-008). The fake
# signs its webhooks with a throwaway secret and posts them back to the API after a short
# delay, so the browser journeys see "confirming your payment" before the confirmation.
_ci_env_export REPORT_PRICE_AMOUNT "${REPORT_PRICE_AMOUNT:-2900}"
_ci_env_export REPORT_PRICE_CURRENCY "${REPORT_PRICE_CURRENCY:-USD}"
_ci_env_export PAYMENT_PROVIDER "fake"
_ci_env_export FAKE_PAYMENT_BASE_URL "${FAKE_PAYMENT_BASE_URL:-http://localhost:8000}"
_ci_env_export FAKE_PAYMENT_WEBHOOK_DELAY_SECONDS "${FAKE_PAYMENT_WEBHOOK_DELAY_SECONDS:-3}"
_ci_env_export PAYMENT_CONFIRM_WAIT_SECONDS "${PAYMENT_CONFIRM_WAIT_SECONDS:-30}"
if [ -z "${STRIPE_WEBHOOK_SECRET:-}" ]; then
  _ci_env_export STRIPE_WEBHOOK_SECRET "whsec_test_$(openssl rand -hex 24)" secret
fi

# --- Frontend and end-to-end ------------------------------------------------------------
_ci_env_export API_ORIGIN "${API_ORIGIN:-http://localhost:8000}"
_ci_env_export WEB_BASE_URL "${WEB_BASE_URL:-http://localhost:3000}"
_ci_env_export MAILPIT_URL "${MAILPIT_URL:-http://127.0.0.1:8025}"

unset _ci_db_base
unset -f _ci_env_export _ci_env_random_key
