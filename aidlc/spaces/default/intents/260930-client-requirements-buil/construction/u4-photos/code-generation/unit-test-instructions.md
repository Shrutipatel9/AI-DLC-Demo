# Unit Test Instructions — U4 Photos (`u4-photos`)

## Setup
- Prerequisites as in U1–U3: Docker (PostgreSQL + Mailpit via `docker compose up -d --wait postgres mailpit`), `uv`, `pnpm` (Node 22).
- Download the pinned Face Landmarker model once with the script added in Step 1 (path from configuration, git-ignored).
- Backend tests run against real PostgreSQL with Alembic migrations applied; never SQLite.

## Commands (this unit only)
- Backend: `cd backend && uv run pytest tests/photos tests/media tests/face -q`
- Frontend: `cd frontend && pnpm exec vitest run src/components/photos src/lib/photos src/app/photos`
- Browser: `cd frontend && pnpm exec playwright test e2e/photos.spec.ts --project=desktop`

## Volume and coverage
- Standard strategy: 5–8 tests per component (MediaStore, FaceGeometry, per-photo checks, identity decision, photos API, photo screens).
- The identity decision is written test first: 8-case table, the 0.6 boundary, the [IV] §4 worked examples, and the two-angle case.
- Whole-app line coverage stays ≥ 80% in each app (`--cov-fail-under=80`, Vitest `lines: 80`); no new exclusions.

## Mocking and test data
- Face images: small committed fixture images (real faces with suitable licence, or generated) for the same person at three angles, a different person, two faces, no face, too dark, too small.
- FaceGeometry is real MediaPipe in backend tests; pure decision logic is tested on signature values without images.
- The frontend camera is mocked (`getUserMedia` granted / denied / absent).
- No paid service is called.
