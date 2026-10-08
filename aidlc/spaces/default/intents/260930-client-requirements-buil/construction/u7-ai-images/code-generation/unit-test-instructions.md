# Unit Test Instructions — U7 AI images (`u7-ai-images`)

## Setup
Same as U6 (Docker PostgreSQL + Mailpit, `uv`, `pnpm`, face model); `AI_IMAGE_PROVIDER=fake`, so tests never call OpenAI.

## Commands (this unit only)
- Backend: `cd backend && uv run pytest tests/images -q`
- Frontend: `cd frontend && pnpm exec vitest run src/components/visuals src/lib/visuals src/app/visuals`
- Browser: `cd frontend && pnpm exec playwright test e2e/visuals.spec.ts --project=desktop`

## Volume and coverage
Standard strategy: 5–8 tests per component (prompt catalog, generation step with retries/back-off, manual retry limits, images API, AI Visuals screen). Whole-app line coverage stays ≥ 80% in each app.

## Mocking
The image fake is scripted per test (fail N times, then succeed; rate-limit responses) and records every call.
