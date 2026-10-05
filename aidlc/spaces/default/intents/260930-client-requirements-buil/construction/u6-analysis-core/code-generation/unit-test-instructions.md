# Unit Test Instructions — U6 Analysis core (`u6-analysis-core`)

## Setup
- Same prerequisites as U1–U5: Docker (PostgreSQL + Mailpit), `uv`, `pnpm` (Node 22), the pinned face model.
- `AI_TEXT_PROVIDER=fake` and `AI_IMAGE_PROVIDER=fake` in tests and E2E; the default test run never calls OpenAI.
- The worker runs in-process in tests (a test helper drains the job queue); E2E starts the real worker process next to the API.

## Commands (this unit only)
- Backend: `cd backend && uv run pytest tests/jobs tests/ai tests/analysis -q`
- Frontend: `cd frontend && pnpm exec vitest run src/components/analysis src/lib/analysis src/app/analysis`
- Browser: `cd frontend && pnpm exec playwright test e2e/analysis.spec.ts --project=desktop`

## Volume and coverage
- Standard strategy: 5–8 tests per component (job mechanism, AI adapters and fakes, measurements, assessments, privacy-safe request builder, report-text validation, pipeline and resume, start/progress API, progress screen).
- Determinism tests: the same photos give identical measurements and assessments.
- Whole-app line coverage stays ≥ 80% in each app; no new exclusions.

## Mocking and test data
- AI fakes record calls and can be told to succeed, fail, return malformed output or be slow.
- Privacy test: fixture questionnaire answers seeded with canary strings; the captured AI request must not contain any medical-flagged question or answer.
- Photos come from the U4 fixtures; paid users from the U5 fake.
