**Collaborator:** aidlc-developer-agent

## Contribution

Blind support review of the lead draft (`team-practices.md`, `discovered-rules.md`, `evidence.md`) from the implementation side: naming, layer boundaries, error handling, configuration, repository/folder layout, sync vs async SQLAlchemy, typing and code style. The project is greenfield, so nothing below is observed team practice. Each item is either **client-stated** (it cites a requirement ID in `client_requirements.md`) or a **[Recommendation]** for the human to affirm, change or drop in the Step 4 interview. Per `org.md` § Code Style, anything a committed linter or formatter config enforces is left to that config. The conventions below cover only what the linters cannot decide.

### 1. Repository and folder layout (two apps, one repo)

I agree with the lead's suggested layout: one repository with `backend/` and `frontend/` as two independent applications (`NFR-001`, `NFR-005`). Each app has its own dependency manifest, lint/format/type config, test suite and README. There is no shared root `package.json` or `pyproject.toml`, and neither app imports the other's source. The HTTP API is their only contract.

Suggested top level **[Recommendation]**:

```text
/
├── backend/            # FastAPI app (own pyproject.toml, alembic.ini, tests/)
├── frontend/           # Next.js app (own package.json, tsconfig.json, eslint/prettier config)
├── docs/               # optional: cross-app docs (e.g. API contract notes, ADRs)
├── .gitignore          # ignores .env*, except .env.example
└── README.md           # how the two apps fit together; links to each app README
```

#### Backend layout: organize by feature, with fixed layers inside each feature [Recommendation]

```text
backend/
├── pyproject.toml
├── alembic.ini
├── alembic/                    # env.py + versions/ (Alembic only, NFR-003)
├── app/
│   ├── main.py                 # app factory: routers, middleware, exception handlers, CORS
│   ├── core/                   # config (Settings), db session/engine, security primitives, logging, errors
│   ├── modules/
│   │   ├── auth/               # router.py, service.py, repository.py, models.py, schemas.py,
│   │   │                       # jwt_service.py, otp_service.py   (Section 5.3: JWT/OTP services decoupled from routes)
│   │   ├── users/
│   │   ├── questionnaire/
│   │   ├── photos/             # upload, per-photo validation, identity check (BR-005)
│   │   ├── payments/           # Stripe checkout + webhook (FR-015)
│   │   ├── analysis/           # pipeline orchestration
│   │   ├── reports/            # report assembly, PDF (FR-013)
│   │   ├── visuals/            # AI Visual Features (FR-020, FR-022)
│   │   └── chat/               # AI Beauty Assistant (FR-019)
│   ├── cv/                     # MediaPipe/OpenCV measurement engine: pure functions, no DB, no HTTP (NFR-007)
│   └── integrations/           # adapters behind interfaces: openai_text, image_generation (NFR-013),
│                               # stripe_client, email_sender (NFR-012)
└── tests/                      # unit/ and integration/, mirroring app/ (tooling is the quality agent's area)
```

Feature folders keep related code together, so a later developer (or an AI assistant, `BC-005`) can change one feature in one folder. Inside each feature, the layers are fixed.

#### Backend layer rules [Recommendation, lint-enforceable]

| Layer | Owns | May import | Must not |
|---|---|---|---|
| `router.py` | HTTP: path, method, status code, request/response schemas, auth dependencies, cookie set/clear | its own `service`, `schemas`, `core` dependencies | contain business rules, touch the DB session or ORM queries, call integrations directly |
| `service.py` (incl. `jwt_service`, `otp_service`) | business rules and orchestration (payment gate, identity re-check, OTP limits, token rotation) | repositories, integrations (via interfaces), `cv`, `core` | import `fastapi`, `Request`/`Response`, or raise `HTTPException` |
| `repository.py` | SQLAlchemy queries for one aggregate | `models`, `core.db` | contain business rules, commit transactions it doesn't own |
| `models.py` | SQLAlchemy 2.0 mapped classes | `core.db` base | import Pydantic schemas |
| `schemas.py` | Pydantic v2 request/response models (the API boundary) | nothing from models except via explicit mapping | leak ORM objects into responses without a response model |
| `integrations/*` | third-party calls behind a small interface; the implementation is chosen by config | `core.config` | be imported by routers |

- **Transaction ownership** **[Recommendation]**: the service layer owns the unit of work (one commit per use case). Repositories never commit on their own.
- **Enforcement** **[Recommendation]**: an `import-linter` contract (or an equivalent Ruff `flake8-tidy-imports` banned-API rule) makes "services must not import fastapi" and "routers must not import repositories" fail the pre-merge lint. Without it, `NFR-011` has no pass/fail check (inception guardrail: requirements must be testable).

#### Frontend layout and layer rules [Recommendation]

```text
frontend/src/
├── app/                        # Next.js routes: thin; compose feature components
├── features/<feature>/         # components/, hooks/, api.ts (typed endpoint calls), types.ts
├── components/ui/              # shared presentational: Toast host (BR-009), ConfirmDialog (BR-010), buttons, forms
├── stores/authStore.ts         # Zustand auth store: user, accessToken, status/initializing; no persist (FE-001, FE-002)
├── lib/api/                    # apiClient (attach token, credentials: "include", proactive refresh,
│                               # 401→refresh→retry single-flight), ApiError, auth endpoint calls (FE-004, FE-005)
└── lib/config/env.ts           # typed, validated public env (API base URL only)
```

This maps onto the client's layering exactly: UI (`app/`, `components/`, `features/*/components`) → Zustand Auth Store (`stores/authStore.ts`) → API Client (`lib/api/`) → Backend Auth APIs (Section 5.3).

- **Boundary rule (enforces `FE-007` and Section 5.3)**: files under `components/`, `features/*/components/` and `app/` must not import `lib/api/auth*` or read `accessToken`. They use the auth store's actions and selectors only. **[Recommendation]** Enforce this with ESLint `no-restricted-imports` path patterns, so the client's layering fails lint instead of depending on code review.
- **One API client**: every HTTP call goes through `lib/api/apiClient`. No direct `fetch`/`axios` anywhere else (`FE-004`). Lint-enforceable with `no-restricted-globals`/`no-restricted-imports`.
- **Rendering model gap**: the access token lives only in browser memory (`FE-002`), and the refresh cookie is set by the backend, which may be a different origin from Next.js. So Server Components, Route Handlers and Next.js `middleware.ts` cannot see the user's auth state. Protected screens therefore fetch data client-side through the API client, and route protection is a client-side guard that waits for the initial restore (`FE-002`). The interview or Application Design needs to affirm this (see gap G3). It is also where Next.js defaults and the client's auth model diverge most.

### 2. Error-handling conventions

#### Backend error envelope [Recommendation; replaces FastAPI's default `{"detail": ...}`]

```json
{
  "error": {
    "code": "PAYMENT_REQUIRED",
    "message": "Payment is required before analysis can start.",
    "details": [],
    "request_id": "7f3c…"
  }
}
```

- **Services raise typed domain exceptions**, e.g. `AppError` subclasses `PaymentRequiredError`, `IdentityMismatchError(mismatched_angles=[…])`, `OtpLockedError`, `InvalidCredentialsError`. A single exception-handler module in `core/errors.py` maps them to HTTP statuses and the envelope. Handlers also cover `RequestValidationError` (422 with field `details`), `HTTPException`, and a catch-all 500 that logs the stack trace and returns a generic message with the `request_id`.
- **The error `code` is a stable, documented UPPER_SNAKE catalogue** (a single `ErrorCode` enum). The frontend branches on `code`, never on `message` text.

Status-code conventions derived from the client document:

| Situation | Status | Code (suggested) | Source |
|---|---|---|---|
| Analysis/report requested before successful payment | 402 | `PAYMENT_REQUIRED` | `FR-015`, `BR-001` (client-stated status) |
| Identity check fails at checkout or analysis start | 409 | `PHOTO_IDENTITY_MISMATCH`, `details` = list of mismatched angles | `BR-005` item 8 (client-stated status); item 4 (list result) |
| Duplicate email at signup | 409 | `EMAIL_ALREADY_REGISTERED` | `WF-002` step 1; **[Recommendation]** see gap G6 on enumeration |
| Missing/invalid/expired access token | 401 | `ACCESS_TOKEN_INVALID` / `ACCESS_TOKEN_EXPIRED` | `AUTH-007`; the frontend refreshes on 401 (`FE-005`) |
| Refresh cookie expired, revoked, missing or reused | 401 | `REFRESH_SESSION_INVALID` | `FE-006`: only this error clears auth and redirects |
| CSRF header or Origin check failure on cookie endpoints | 403 | `CSRF_REJECTED` | `AUTH-013` |
| OTP resend inside the 60 s cooldown / OTP lockout after 5 failures | 429 + `Retry-After` | `OTP_COOLDOWN` / `OTP_LOCKED` | `AUTH-011` (status is **[Recommendation]**; the client doc names no status) |
| Photo fails a per-photo check | 422 | `PHOTO_VALIDATION_FAILED`, `details` = failed checks with reasons | `BR-005` ("rejected with a clear reason"); status **[Recommendation]** |
| Upstream vendor failure (OpenAI, Stripe, email) | 502/503 | `UPSTREAM_UNAVAILABLE` | **[Recommendation]**; never 401, so the frontend never clears auth on it (`FE-006`) |

- **Anti-enumeration**: the forgot-password request returns the same success response whether or not the email exists, and shows no outcome toast (`BR-009` exception).
- **Never in a response or a log**: tokens, OTPs, reset tokens, password hashes, raw photos, Stripe secrets (`AUTH-011`, org construction guardrail).

#### Frontend error flow [Recommendation]

- `apiClient` converts every non-2xx response into a typed `ApiError { status, code, message, details, requestId }` and network failures into a distinct `NetworkError`. The API client itself never shows toasts or navigates, except for the `FE-006` clear-and-redirect on `REFRESH_SESSION_INVALID`.
- The feature hook or UI layer catches errors and calls one shared `notify.success` / `notify.error` helper, which renders the top-right toast (`BR-009`). A `code → user message` map lives in one place. Components do not write ad-hoc error strings.
- Destructive actions go through the shared `ConfirmDialog` before the call is made (`BR-010`, including logout per `WF-002` step 5).
- 5xx and network errors produce a toast only. They never clear auth (`FE-006`).

### 3. Configuration handling (no hardcoded price, model, keys)

- **Backend** **[Recommendation]**:
  - One typed `Settings` class (`pydantic-settings`) in `app/core/config.py` is the only place that reads environment variables. Other modules receive settings through dependency injection or import the settings object, never `os.environ`.
  - The app validates settings at startup and fails fast on missing required values.
  - It loads settings from environment variables, with an optional local `.env` that is git-ignored. A committed `backend/.env.example` lists every key with a safe placeholder.
- Values that must be configuration:
  - **client-stated**:
    - `REPORT_PRICE_AMOUNT`, `REPORT_CURRENCY` (`FR-016`, `OQ-002`)
    - `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL` (`NFR-008`)
    - `IMAGE_GENERATION_PROVIDER` plus its model and key (`NFR-013`)
  - **[Recommendation]**:
    - `DATABASE_URL`
    - JWT signing secret or keys
    - `CORS_ALLOWED_ORIGINS`, `CSRF_ALLOWED_ORIGINS` (`AUTH-013`)
    - cookie `domain`/`secure`/`samesite`
    - Stripe secret key and webhook signing secret
    - email provider selection and credentials (`NFR-012`)
    - `REQUIRED_PHOTO_ANGLES` (`ASM-005`)
    - photo-validation thresholds and the identity threshold, default `0.6` (`ASM-002`, `ASM-010`)
    - token and OTP lifetimes and limits, defaulting to the `AUTH-011`/`AUTH-012` values
- **Money** **[Recommendation]**: store and transmit amounts as integer minor units (cents) with an ISO-4217 currency code, never floats. This fits Stripe's API and `DATA-008`.
- **Frontend** **[Recommendation]**: the only public variable is `NEXT_PUBLIC_API_BASE_URL`, validated in `lib/config/env.ts`. No secret ever goes in a `NEXT_PUBLIC_*` variable. The frontend shows the price by fetching it from the backend, never from its own config or code, so `FR-016` has exactly one source.

### 4. Sync vs async SQLAlchemy (needs a human decision)

The client mandates SQLAlchemy and PostgreSQL (`NFR-002`, `NFR-004`) but not the I/O model. There are two alternatives (inception guardrail: at least two options with trade-offs):

| | A. Sync SQLAlchemy 2.0 + `psycopg` 3; `def` endpoints (FastAPI runs them in its threadpool) | B. Async SQLAlchemy 2.0 (`AsyncSession`) + `asyncpg`; `async def` endpoints |
|---|---|---|
| Readability for the client's team (`BC-005`, `NFR-011`) | Simplest; the most common pattern in docs and AI-assistant training data | More ceremony: `await` everywhere, eager-loading rules, async Alembic `env.py` |
| Common pitfalls | Threadpool size caps concurrent DB-bound requests | Implicit lazy loads raise `MissingGreenlet`; accidentally calling blocking CV/OpenCV code inside `async def` stalls the whole event loop |
| Fit with this workload | CPU-bound MediaPipe/OpenCV work and long OpenAI calls must leave the request path either way | Better concurrency for many simultaneous I/O-bound requests (chat, polling) |
| Testing | Straightforward pytest | Needs `pytest-asyncio`/`anyio` and async fixtures |

- **Suggested default** **[Recommendation]**: **A (sync)**. The main reasons are maintainability for the client's AI-assisted team and a lower risk of event-loop blocking from CV code. Revisit if load testing shows the threadpool is a bottleneck.
- **Either way** **[Recommendation]**:
  - Use the SQLAlchemy 2.0 typed style (`DeclarativeBase`, `Mapped[...]`, `mapped_column`, `select()`) and never the legacy `Query` API.
  - Use one session per request through a dependency.
  - Never mix sync and async sessions in one code path.
- **Out of scope here**: the analysis pipeline (CV + 24 AI images per report, `FR-020`/`FR-022`) is long-running and must not run inside an HTTP request. Whether it uses FastAPI `BackgroundTasks`, a worker process or a job queue is an Application Design decision. I flag it here only because it constrains the sync/async choice.

### 5. Naming conventions (what the linters won't decide) [Recommendation unless cited]

- **Python**: `snake_case` modules, functions and variables; `PascalCase` classes; `UPPER_SNAKE_CASE` constants.
  - Functions are named verb + noun (`issue_token_pair`, `verify_otp`).
  - Booleans start with `is_`/`has_`.
- **Database**:
  - Tables are plural `snake_case` (`users`, `otp_records`, `refresh_tokens`, `payments`); ORM classes are singular `PascalCase` (`User`, `RefreshToken`).
  - Timestamp columns are `created_at`/`updated_at` (UTC, `timestamptz`).
  - Set a SQLAlchemy `MetaData(naming_convention=...)` for pk/fk/ix/uq/ck so Alembic autogenerate produces deterministic constraint names.
  - Alembic `file_template` is date-prefixed with a slug (e.g. `20261001_1200_create_users.py`).
- **Pydantic schemas**: suffix by role (`RegisterRequest`, `UserResponse`, `CheckoutSessionResponse`), never bare entity names that clash with ORM models.
- **URLs**: plural nouns, kebab-case segments, verbs only for action endpoints. The client document already fixes `/auth/refresh`, `/auth/logout`, `/auth/me`, `/auth/change-password` (`AUTH-013`, `AUTH-014`, `AUTH-016`). Keep them verbatim; see gap G4 on prefix and versioning.
- **TypeScript/React**: `camelCase` variables and functions; `PascalCase` components and types, with no `I` prefix; hooks are named `useX`; the Zustand store is `useAuthStore`. One convention for file names, suggested **kebab-case files** (`confirm-dialog.tsx`) exporting `PascalCase` components.
- **`data-testid`**: kebab-case `{component}-{element-role}` on interactive elements (e.g. `login-form-submit-button`), to support the E2E tests the quality agent may propose.

### 6. Typing and code style

- **Python**:
  - Type hints on all function signatures, not only public ones.
  - Pydantic v2 at the boundary.
  - **[Recommendation]**: make a type checker (mypy, or pyright) part of the pre-merge check for `backend/app/`, not "optional". For code the client will extend with AI tools, type errors are the cheapest regression signal.
- **One formatter** **[Recommendation]**: Ruff format (drop the "or Black" alternative so there is one tool and one config in `pyproject.toml`). Ruff lint rule sets suggested: `E, F, I, B, UP, N, S` (bandit subset; the devsecops agent may refine), plus `ANN` if the team wants annotation enforcement.
- **TypeScript**:
  - `strict: true`.
  - ESLint `@typescript-eslint/no-explicit-any` as an error.
  - Prettier for formatting, with ESLint's formatting rules disabled (`eslint-config-prettier`).
- **Contract drift** **[Recommendation]**: generate the frontend's API types from the backend's OpenAPI schema (e.g. `openapi-typescript`) rather than hand-writing them. A mismatch then becomes a type error, and the API contract has one source.
- **Documentation (`NFR-011`, `BC-005`)**, with checkable forms **[Recommendation]**:
  - a module docstring on every `app/modules/*/service.py` and integration adapter
  - docstrings on public service functions (Google style)
  - a README per app covering setup, env keys, commands and the layer map
  - a short "architecture and conventions" section, so the client's AI-assisted team reads the same rules this workflow affirms
  - Ruff's `D` rules, scoped to services, can enforce the docstring part.
- **Logging** **[Recommendation]**: structured logs with a request-ID middleware; the same ID is echoed in the error envelope. Never log secrets, tokens, OTPs or photo bytes.

### 7. Gaps the interview must resolve (developer view)

These are additions to the lead's open items. Each is a team choice, not an evidence question.

- **G1 Backend organization**: feature folders with fixed layers inside each (suggested), or a layer-first layout (`routers/`, `services/`, `repositories/`)? Should layer rules be lint-enforced (import-linter / ESLint `no-restricted-imports`)?
- **G2 Sync vs async SQLAlchemy**: A (sync, suggested) or B (async)? See §4.
- **G3 Next.js rendering model**: App Router with client-side data fetching and a client-side route guard for protected screens (suggested; forced by `FE-002`), or something else?
- **G4 API paths**: keep the client's `/auth/*` paths at the root, or mount everything under a prefix such as `/api/v1`? The client document names bare paths. A prefix would be a delivery-team addition that must be labeled, not silently applied (client doc "How to use", item 3).
- **G5 JSON field casing on the wire**: `snake_case` end to end (simplest with generated TS types), or camelCase via Pydantic alias generators?
- **G6 Signup enumeration**: return 409 `EMAIL_ALREADY_REGISTERED` (explicit UX, per `WF-002`), or a generic response like forgot-password? This is also a devsecops question.
- **G7 Toolchain pins**: Python version (e.g. 3.12) and dependency manager (uv / Poetry / pip-tools); Node LTS version and package manager (npm / pnpm).
- **G8 Type checking gate**: is mypy/pyright a required pre-merge check (suggested) or advisory?
- **G9 Error envelope and code catalogue**: affirm the envelope shape and the status-code table in §2 as the team convention (the API contract stage then fills in exact codes).

### Suggested additions to `discovered-rules.md` candidates (not mandated unless affirmed)

- Candidate: ALWAYS return API errors in the single `{"error": {"code", "message", "details", "request_id"}}` envelope, and branch on `code` in the frontend.
- Candidate: NEVER import `fastapi` in service, repository or integration modules. HTTP concerns stay in routers.
- Candidate: NEVER call `fetch` or axios outside the frontend's central API client (`FE-004`), and never import auth API functions or read the access token in UI components (`FE-007`, enforced by lint).
- Candidate: NEVER read environment variables outside the backend `Settings` class or the frontend `env.ts` module.
- Candidate: ALWAYS represent money as integer minor units plus a currency code, never as floats.

## Positions

- AGREE: one repository with separate `backend/` and `frontend/` applications. It satisfies `NFR-001`/`NFR-005`, and nothing in the client document requires two repositories.
- AGREE: deferring to committed linter/formatter config (Ruff; ESLint + Prettier; TypeScript `strict`) with language-idiomatic naming. This matches `org.md` § Code Style.
- AGREE: the Mandated/Forbidden rules on the stack, the Section 5.3 layering, token storage and config-driven price/model/keys. Each cites a client-stated requirement ID.
- AGREE: the candidates "NEVER commit secrets; ship `.env.example`" and "ALWAYS keep the photo-angle set as one configuration value". I suggest extending the second to the photo-validation and identity thresholds (`ASM-002`, `ASM-010`).
- OBJECT: the Code Style section reduces layer boundaries to "route handlers separated from services". Without concrete backend layer rules, a frontend import boundary and an error-envelope convention (§1–§2 above), `NFR-011` has no pass/fail check, and Section 5.3 is enforced only by review.
- OBJECT: "type hints on public functions, optionally checked with mypy". Since `BC-005` expects AI-assisted continuation, a type checker should be a proposed pre-merge gate. This is a judgment call for the human (G8).
- OBJECT: "Ruff format or Black". Pick one formatter so there is a single config. I suggest Ruff format.
- OBJECT: the draft omits several implementation conventions the team must choose before Construction: sync vs async SQLAlchemy, the API error envelope and status-code usage (402/409 are client-stated), JSON casing, API path prefix, and the Next.js rendering model under in-memory tokens. These are gaps G1–G9 above.
- OBJECT: the Mandated rule "ALWAYS write clean, modular, well-documented code" is client-stated (`NFR-011`) but not verifiable as written. Keep it, and pair it in Code Style with checkable forms (lint-enforced layer rules, required docstrings on services, a README per app), so the rule has a pass/fail criterion (inception guardrail).
