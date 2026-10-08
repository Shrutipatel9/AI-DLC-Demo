# Unit Test Instructions — U9 AI Beauty Assistant (`u9-beauty-assistant`)

## Setup
Same as U6–U10 (Docker PostgreSQL + Mailpit, `uv`, `pnpm`, face model); `AI_TEXT_PROVIDER=fake`, so tests never call OpenAI.

## Commands (this unit only)
- Backend: `cd backend && uv run pytest tests/chat -q`
- Frontend: `cd frontend && pnpm exec vitest run src/components/chat src/lib/chat src/app/chat`
- Browser: `cd frontend && pnpm exec playwright test e2e/chat.spec.ts --project=desktop`

## Volume and coverage
Standard strategy: 5–8 tests per component (grounding context builder, medical-decline instruction, conversation store, daily limit incl. concurrency, chat API, chat screen). Whole-app line coverage stays ≥ 80% in each app.

## Mocking
The text fake records the system instructions and grounding context and can be told to fail; the medical-decline evaluation set is an opt-in `(eval)` suite that is not part of the default run.
