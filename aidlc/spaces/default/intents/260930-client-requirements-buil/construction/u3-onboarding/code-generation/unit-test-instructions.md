# Unit Test Instructions — U3 Onboarding

## Setup
Same runners and fixtures as U1 and U2: pytest against real PostgreSQL (`app_test`), Vitest with RTL, and Playwright with axe. Before running anything:
1. `docker compose up -d --wait postgres mailpit`
2. `source scripts/ci-env.sh`

## How to run THIS UNIT's tests
- **Backend** (from `backend/`): `uv run pytest tests/onboarding -m "not perf" -q`
- **Backend whole-app coverage gate:** `uv run pytest tests -m "not perf" --cov=app --cov-fail-under=80 -q`
- **Frontend** (from `frontend/`): `pnpm vitest run src/components/onboarding src/app/onboarding`
- **Frontend whole-app coverage gate:** `pnpm vitest run --coverage`
- **E2E** (from `frontend/`, with the API and the production build running): `pnpm exec playwright test e2e/onboarding.spec.ts`

## Test-first modules
None in U3. Every layer is test-after.

## Coverage targets
- At least 80% line coverage per app.
- About 40 backend tests and 25 frontend tests (Standard: 5–8 per component).

## Mocking and data
- **Questionnaire:** load the real seed definition in tests.
- **Users:** create them with the U1 factories.
- **Frontend:** stub `fetch` per test.
- **Network:** no outside network calls.
