# Team-Level Rules

> This team's affirmed practices and corrections. Loaded after `org.md` as
> strict-additive guidance; contradictions with broader policy are rejected.
> Populated by the practices-discovery affirmation gate. Edit at the gate,
> not directly.

## Way of Working

We use **trunk-based development on `main`**. Every change reaches `main` through
a short-lived branch (resolved within 1–2 days) and a **GitHub pull request**, and
we **squash-merge** it so each piece of work (each Bolt) becomes one commit on
`main`, named by its Bolt slug. The full branch history stays on the source branch
until the worktree is discarded. We do not keep long-lived branches. (Interview Q1;
`org.md` § Way of Working.)

- **Trunk**: `main`. The repository was initialised on an unborn `master` branch; we
  rename it to `main` before the first commit.
- **Construction worktrees**: base branch `main`, merge target `main`, strategy
  `squash`.
- **Merge path**: a pull request into `main`; `main` is branch-protected and the
  required GitHub Actions checks (see Testing Posture) must pass before merge.
- **Repository layout**: one repository (`github.com/Shrutipatel9/AI-DLC-Demo`)
  holding two independent applications, `backend/` (Python + FastAPI) and
  `frontend/` (Next.js + TypeScript). Each has its own dependency manifest and
  lockfile, lint/format/type configuration, tests and README. Neither app imports
  the other's source; the HTTP API is their only contract (`NFR-001`, `NFR-005`;
  interview Q2).
- **Traceability**: pull-request descriptions cite the requirement IDs they
  implement (`FR-*`, `AUTH-*`, `BR-*`, `FE-*`), following the client's
  traceability map (`client_requirements.md` Section 12).

## Walking Skeleton

We **always build a walking skeleton first** for greenfield work on this project,
even though the `classic` scope's default is `skeleton: off` (interview Q3). A
walking skeleton is a minimal version that runs the whole way through, built first
to prove the pieces connect before the real features go in.

- **The slice**: sign-up → emailed one-time code (OTP) → login → `GET /auth/me`,
  running across the Next.js app, the FastAPI app and PostgreSQL (with Alembic
  migrations applied).
- **Order**: the skeleton is the first Unit of Construction. It runs through every
  applicable per-unit stage, including Code Generation, before any later Unit
  starts.
- **Done means verified**: the skeleton is demonstrated with the intent's
  human-approved Construction Verification Command, and then needs the human's
  skeleton checkpoint approval. A design-stage review alone does not count as a
  working skeleton.
- **Autonomy choice**: the "continue automatically / review each checkpoint" choice
  is offered only after the skeleton is verified and approved.
- The skeleton also carries the project scaffolding the later Units depend on: both
  app skeletons, Docker Compose for local PostgreSQL, `.env.example` files, the
  hardened `.gitignore`, pre-commit secret scanning and the GitHub Actions workflow.

## Testing Posture

Tests are a first-class deliverable in every Bolt. We write tests **after** the code
in general and **first** for the riskiest logic (interview Q4).

- **Methodology**: custom
- **Ordering**: For the backend JWT and OTP (token and one-time-code) services, the frontend token-refresh and single-flight logic, and the three-photo same-person identity check (`BR-005`), we write failing tests from the acceptance criteria first and then implement; every other layer is implemented first and then its tests are written and run before the Bolt is done.
- **Test-first modules (exact list)**: backend JWT service and OTP service
  (`AUTH-010`–`AUTH-016`); frontend API-client proactive refresh, 401 → refresh →
  retry, and single-flight logic (`FE-005`, `FE-006`); the identity-check decision
  logic over the three photos (`BR-005`). Any other module is test-after.
- **Coverage floor**: each application (backend and frontend) keeps **at least 80%
  line coverage**, measured over the whole application at every merge and enforced
  by the tool (`pytest-cov` with `--cov-fail-under=80`; Vitest coverage thresholds
  `lines: 80`). Coverage exclusions are declared in committed configuration and are
  never added to make a check pass; the floor may not be weakened (`org.md`).
- **Requirement coverage**: every `FR-*`, `AUTH-*`, `BR-*` and `FE-*` requirement
  maps to at least one test (client Section 12 for `FR`/`AUTH`/`BR`; `FE` added by
  interview Q5). How business-only or blocked IDs are recorded is
  **[Open — confirm]** (see `evidence.md`).
- **Backend tooling**: `pytest` + `pytest-cov`; API tests through FastAPI's test
  client; integration tests against a **real PostgreSQL** database with Alembic
  migrations applied, never SQLite (`NFR-002`, `NFR-003`).
- **Frontend tooling**: Vitest + React Testing Library for units and components,
  including the Zustand auth store and the API client (`FE-001`–`FE-007`).
- **End-to-end**: a small Playwright set for the main journeys: sign-up/login, and
  photos → payment → report. It is additive to the Standard test strategy and does
  not count toward the 80% line floor.
- **Paid services are faked**: OpenAI, Stripe and the email/OTP provider are
  replaced by fakes behind their configuration-selected abstractions (`NFR-008`,
  `NFR-013`). The default test run never calls a paid third-party API.
- **Test strategy**: the workflow's Standard strategy sets test volume and types;
  the floors above are additive to it.
- **CI before merge**: a small **GitHub Actions** workflow is delivered in the first
  piece of work (the walking skeleton). On every pull request to `main` it runs, for
  each app: lint (including security rules), format check, type check, tests and
  the coverage floor. `main` is protected so the workflow must pass before merge
  (interview Q6). This meets the `org.md` "CI execution before merge" floor for
  `classic`.

## Guard Policy

<!-- Affirmed by the team. Mode: strict, relaxed, or off. Strict here holds for every intent and cannot be changed from chat. A section under the retired Change Control heading, written by an earlier release, is still read. -->

## Deployment

**This workflow ships no deployment.** The client confirmed hosting is undecided
and not needed now, and we assume no host (`NFR-010`, `CON-007`; interview Q7).

- **Local run**: a **Docker Compose** file runs PostgreSQL locally for development
  and for the integration tests. Each app ships a committed `.env.example` with
  placeholder values only.
- **Configuration**: every environment-specific value — database URL, CORS and
  cookie settings, JWT signing key, OpenAI base URL/key/model, image-generation
  provider, Stripe keys, report price and currency, email provider settings — comes
  from configuration or environment variables, never from code (`NFR-008`,
  `NFR-013`, `FR-016`).
- **Database changes**: schema changes ship only as Alembic migrations (`NFR-003`).
- **Future target**: once a host is chosen, we adopt the organisation default:
  deploy on merge to a staging environment, with production gated by a separate
  manual approval (tech lead + product owner). This is recorded as the target, not
  something this workflow builds.

## Code Style

We defer to the linter, formatter and type-checker configuration committed in each
app; every check runs in the GitHub Actions workflow and a failure blocks the merge
(`org.md` § Code Style; interview Q8).

- **Python (backend)**: **Ruff** for linting and formatting (one tool, configured in
  `backend/pyproject.toml`); **mypy** is a required check. Type hints on function
  signatures.
- **TypeScript (frontend)**: **ESLint** + **Prettier**, with TypeScript `strict`
  mode; `tsc --noEmit` runs as the type check.
- **Layering enforced by import rules**: lint rules enforce the client's
  authentication layering, UI → Zustand Auth Store → API Client → Backend Auth APIs
  → JWT/OTP Services (`client_requirements.md` Section 5.3). In the frontend, UI
  components never import auth API functions or read tokens (`FE-007`), and all HTTP
  calls go through the single API client (`FE-004`). In the backend, the JWT and OTP
  services stay decoupled from the route handlers.
- **Security lint rules** (interview Q9): Ruff `S` rules (flake8-bandit) in the
  backend, with `S101` allowed only under `tests/`; ESLint security plugins in the
  frontend. Suppressions are inline, one rule at a time, with a one-line reason.
- **Secrets and supply chain** (interview Q9):
  - `.gitignore` is fixed **before the first commit** to ignore `.env` and `.env.*`
    (keeping `.env.example`), private keys (`*.pem`, `*.key`), Python caches and
    virtual environments, `.next/`, coverage output and local upload folders.
  - **Gitleaks** runs as a pre-commit hook.
  - `pip-audit` and `npm audit` run against the committed lockfiles.
  - **Dependabot** is enabled for the Python and npm dependencies.
- **Naming**: language-idiomatic — `snake_case` in Python; `camelCase` for
  TypeScript variables and functions; `PascalCase` for classes, React components
  and types.
- **Documentation** (`NFR-011`, `BC-005`): docstrings on services, and a README per
  app covering setup, environment keys, commands and the layer map, so the client's
  team can continue the code with AI-assisted tools.
- **App-wide UI conventions** (client document, delivery-team decided): a toast for
  every action with a real success/failure outcome (`BR-009`), and a shared
  confirmation dialog for every destructive action (`BR-010`).
## Forbidden

<!-- Team-specific forbidden patterns -->

## Mandated

<!-- Team-specific mandates -->

## Corrections

<!-- Self-learning loop appends here. -->
