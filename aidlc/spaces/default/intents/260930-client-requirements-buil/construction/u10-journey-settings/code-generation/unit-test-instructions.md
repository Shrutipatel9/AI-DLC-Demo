# Unit Test Instructions — U10 Journey, landing, settings and end-to-end checks (`u10-journey-settings`)

## Setup
Same as U6–U8 (Docker PostgreSQL + Mailpit, `uv`, `pnpm`, face model); all paid services are fakes.

## Commands (this unit only)
- Backend: `cd backend && uv run pytest tests/journey tests/settings tests/traceability -q`
- Frontend: `cd frontend && pnpm exec vitest run src/components/landing src/components/settings src/lib/journey src/app/settings`
- Browser: `cd frontend && pnpm exec playwright test e2e/journey.spec.ts e2e/settings.spec.ts --project=desktop`

## Volume and coverage
Standard strategy: 5–8 tests per component (next-step rule over every state row, route guard, landing, account info, billing, requirement-to-test map check). Whole-app line coverage stays ≥ 80% in each app.

## Mocking
States are built with the existing helpers for each earlier unit (consent, questionnaire, photo fixtures, Stripe fake, analysis fakes).
