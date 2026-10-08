# Unit Test Instructions — U8 Report, Home and PDF (`u8-report-home`)

## Setup
Same as U6/U7 (Docker PostgreSQL + Mailpit, `uv`, `pnpm`, face model); AI providers are fakes, so tests never call OpenAI. The PDF library runs locally with no network.

## Commands (this unit only)
- Backend: `cd backend && uv run pytest tests/report -q`
- Frontend: `cd frontend && pnpm exec vitest run src/components/report src/components/home src/lib/report src/app/report src/app/home`
- Browser: `cd frontend && pnpm exec playwright test e2e/analysis.spec.ts --project=desktop`

## Volume and coverage
Standard strategy: 5–8 tests per component (report assembly/publish, report API + paywall, PDF render/cache/invalidate, report page, assessments views, Home, header nav). Whole-app line coverage stays ≥ 80% in each app.

## Mocking
Completed runs are built with the U6/U7 fakes and helpers; PDF output is checked by page text and order, not pixels.
