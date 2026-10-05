# CI/CD Pipeline — U1 Walking Skeleton

**Sources:** `nfr-design/logical-components.md` §5 (quality gates), `nfr-design/security-design.md` §7, team practices (GitHub pull requests with squash-merge to a protected `main`, GitHub Actions, Dependabot), and infrastructure answers Q1 and Q2.

There is **no deployment stage** in this workflow; no host is chosen. The pipeline is continuous integration only: every pull request into `main` and every push to `main` runs it, and all jobs are required checks on the protected `main` branch.

## 1. Workflow layout (`.github/workflows/ci.yml`)

Triggers:
- `pull_request` targeting `main`;
- `push` to `main`;
- `workflow_dispatch` (manual run).

Concurrency group `ci-${{ github.ref }}` with `cancel-in-progress: true` for pull requests.

Permissions: `contents: read` only. The workflow never needs write tokens.

| Job | Runs on | Needs | Purpose |
|---|---|---|---|
| `backend` | `ubuntu-24.04`, Python 3.12 via `astral-sh/setup-uv`, service container `postgres:16` | — | Lint, types, layering, unit and integration tests, coverage |
| `frontend` | `ubuntu-24.04`, Node 22 via `actions/setup-node` with the pnpm cache | — | Lint, format, types, unit tests, coverage, build, bundle size |
| `e2e` | `ubuntu-24.04`; Compose `postgres` + `mailpit`; API and web as processes (answer Q1) | `backend`, `frontend` | Migration round-trip, then the Playwright skeleton journey |
| `security` | `ubuntu-24.04` | — | Secret scan, dependency audit, deny-list |

All third-party actions are pinned by full commit SHA. Dependabot (`.github/dependabot.yml`) updates the `pip`/`uv`, `npm` and `github-actions` ecosystems weekly.

## 2. Job steps

**`backend`** (working directory `backend/`):
1. `uv sync --frozen`
2. `uv run ruff check .`, then `uv run ruff format --check .`
3. `uv run mypy --strict app`
4. `uv run lint-imports`
5. `uv run pytest --cov=app --cov-fail-under=80 -m "not perf"`, against the service container. `pytest-socket` allows only localhost (NFR8.2).
6. `uv run pytest -m perf`, reporting p95 per endpoint (NFR9.1–NFR9.3). It is kept out of the coverage step so timing noise cannot hide a coverage failure.

**`frontend`** (working directory `frontend/`):
1. `pnpm install --frozen-lockfile`
2. `pnpm lint` (ESLint, including the security plugin and `no-restricted-imports`), then `pnpm format:check` (Prettier)
3. `pnpm typecheck` (`tsc --noEmit`)
4. `pnpm test -- --coverage` (Vitest; the 80% threshold is set in config)
5. `pnpm build`, then `pnpm size-check` (auth routes at most 200 KB gzipped, NFR9.5)

**`e2e`:**
1. `docker compose up -d --wait postgres mailpit`
2. Backend: `uv sync --frozen`, then `alembic upgrade head && alembic downgrade base && alembic upgrade head` (NFR1.2)
3. Start the API in the background with `APP_ENV=test`, `EMAIL_BACKEND=smtp`, `SMTP_PORT=1025`; wait for `GET /health/ready` to return 200 (timeout 60 s)
4. `pnpm build && pnpm start` in the background with `API_ORIGIN=http://localhost:8000`; wait for `/login` to return 200
5. `pnpm exec playwright install --with-deps chromium`, then `pnpm e2e`: the journey at two viewports, with axe checks and codes read from the Mailpit API (NFR8.4, NFR9.6, NFR9.7)
6. On failure, upload the Playwright report and traces plus the API log as artifacts kept for 7 days
7. Always run `docker compose down -v`

**`security`:**
1. `gitleaks/gitleaks-action` over the full history on push and over the diff on pull requests
2. `uv run pip-audit` (backend) and `pnpm audit --prod --audit-level high` (frontend)
3. `scripts/check-denylist.sh`: fails if `supabase`, `@supabase/*`, `next-auth`, `@clerk/*`, `@auth0/*`, `firebase` or any `*-auth-sdk` package appears in either lockfile (NFR1.3, NFR2.1)

## 3. Stage-to-gate mapping

| Gate | Job / step | Blocks merge when | Requirement |
|---|---|---|---|
| Lint and format | backend 2, frontend 2 | Any violation | NFR7.1 |
| Types | backend 3, frontend 3 | Any error | NFR7.1 |
| Layering | backend 4, frontend 2 | Any forbidden import | NFR7.2 |
| Coverage ≥ 80% per app | backend 5, frontend 4 | Below the floor | NFR8.1 |
| No outside network in tests | backend 5 (`pytest-socket`) | Any attempted outside connection | NFR8.2 |
| Latency targets | backend 6 | p95 over target | NFR9.1–NFR9.3 |
| Bundle size | frontend 5 | Over 200 KB | NFR9.5 |
| Migration round-trip | e2e 2 | Any migration error | NFR1.2 |
| Skeleton journey and accessibility | e2e 5 | Any failed step or axe violation | NFR8.4, NFR9.6, NFR9.7 |
| Secrets | security 1 (also a pre-commit hook) | Any finding | NFR6.1 |
| Vulnerable dependencies | security 2 | High or critical advisory | Supply chain (security design §7) |
| Banned auth/BaaS packages | security 3 | Any match | NFR1.3, NFR2.1 |

## 4. Secrets in CI (answer Q2)

The repository holds **no secrets** for U1. Each job that starts the API creates throwaway values at the start of the job and appends them to `$GITHUB_ENV`. Gitleaks never sees them, and they die with the runner.
- `JWT_SIGNING_KEYS={"ci":"<openssl rand -base64 48>"}` and `JWT_ACTIVE_KID=ci`
- `CODE_HMAC_KEY=<openssl rand -base64 48>`

Database credentials are fixed, non-secret CI values (`app`/`app`) that are reachable only inside the runner. Each value is passed to `::add-mask::` so it cannot appear in logs. Later units that call real paid services in an opt-in job (for example the real-vendor check before handover) will use GitHub environment secrets, scoped to that job only.

## 5. Merging, rollback and promotion
- **Merging:** a pull request merges into the protected `main` only with all four jobs green and one approving review, as a squash merge named by the Bolt slug (team Way of Working).
- **Rollback:** with no deployment, rollback means `git revert` of the squash commit through a new pull request, which re-runs the full pipeline. Every migration has a working `downgrade` (proven by the round-trip), so a revert can also step the schema back.
- **Promotion:** none in this workflow. The recorded target for when a host exists is a `deploy-staging` job on push to `main` after all checks pass, and a `deploy-production` job behind a GitHub environment with required reviewers (tech lead and product owner), followed by a smoke test of `/health/ready` and a sign-in journey.

## 6. Local parity
`make verify` runs the same steps in the same order: backend, frontend, e2e (using the developer's Compose), then security (Gitleaks and audits). It is the command proposed for the skeleton checkpoint, so a green local `make verify` predicts a green pipeline.
