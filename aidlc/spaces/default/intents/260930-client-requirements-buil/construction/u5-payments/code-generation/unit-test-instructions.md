# Unit Test Instructions — U5 Payment (`u5-payments`)

## Setup
- Same prerequisites as U1–U4: Docker (PostgreSQL + Mailpit), `uv`, `pnpm` (Node 22), the pinned face model fetched for U4.
- `PAYMENT_PROVIDER=fake` in tests and E2E; the real Stripe adapter is never called by the default test run.

## Commands (this unit only)
- Backend: `cd backend && uv run pytest tests/payments -q`
- Frontend: `cd frontend && pnpm exec vitest run src/components/payments src/lib/payments src/app/payment`
- Browser: `cd frontend && pnpm exec playwright test e2e/payments.spec.ts --project=desktop`

## Volume and coverage
- Standard strategy: 5–8 tests per component (provider fake/adapter, webhook verification, payment service and idempotency, payments API, payment screens).
- Whole-app line coverage stays ≥ 80% in each app; no new exclusions.

## Mocking and test data
- Stripe: the fake provider records checkout sessions and signs webhooks with the test webhook secret; the Stripe adapter is unit-tested with the SDK's HTTP layer stubbed.
- Concurrency: duplicate webhook delivery is tested with two concurrent requests against real PostgreSQL.
- Photo sets come from the U4 fixtures and helpers.
