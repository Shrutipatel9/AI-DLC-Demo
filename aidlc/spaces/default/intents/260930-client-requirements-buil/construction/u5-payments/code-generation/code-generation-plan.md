# Code Generation Plan — U5 Payment (`u5-payments`)

## Scope
Stories US6.1–US6.5 (`unit-of-work.md` U5; `stories.md`). Requirements FR-015, FR-016, BR-001, FR7.x.
Design stages were skipped for this unit; open points are settled here and labelled
`[Decided by delivery team]` in `code-summary.md`. Out of scope: billing history (U10), Start Analysis itself (U6).

## Testing Contract

```json
{
  "version": 1,
  "methodology": "custom",
  "source": "team",
  "ordering": "For the backend JWT and OTP (token and one-time-code) services, the frontend token-refresh and single-flight logic, and the three-photo same-person identity check (`BR-005`), we write failing tests from the acceptance criteria first and then implement; every other layer is implemented first and then its tests are written and run before the Bolt is done.",
  "scope": "classic",
  "test_strategy": "standard",
  "project_type": "greenfield",
  "applicable_notes": [
    {
      "layer": "org",
      "text": "We treat tests as a first-class deliverable in every Bolt. The specific\nmethodology (TDD, BDD, ATDD, or classic test-after) is affirmed at\npractices-discovery and recorded in `team.md` under this heading with explicit\n`Methodology` and `Ordering` fields; Code Generation resolves those fields\nindependently from coverage, tooling, and scope notes.\n\nWhen no posture has been affirmed, our default per scope is:\n- **Methodology**: test-after\n- **Ordering**: implement each applicable testable layer, then write and run\n  that layer's tests.\n- `mvp`, `enterprise`, `feature`, `infra`, `classic` add an 80% line-coverage\n  floor and CI execution before merge.\n- `bugfix`, `security-patch` add a targeted regression for the specific\n  bug/vulnerability and require the existing suite to remain green.\n- `express` uses the Minimal strategy: requirement-driven unit tests (one per\n  requirement, with a happy-path floor per component); existing tests remain\n  green.\n- `poc`, `refactor`, `workshop` add no extra new-test floor and require the\n  existing suite to remain green.\n\nThe active `Test Strategy` still applies in every scope and determines test\nvolume/types. Scope floors are additive; they never reduce or replace the\nselected strategy.\n\nBuild and Test verifies defined coverage floors and affirmed quality targets;\nthey may not be weakened to make a step pass.\n\nAffirm a stricter posture in `team.md` if the team commits to one."
    },
    {
      "layer": "team",
      "text": "Tests are a first-class deliverable in every Bolt. We write tests **after** the code\nin general and **first** for the riskiest logic (interview Q4).\n\n- **Methodology**: custom\n- **Ordering**: For the backend JWT and OTP (token and one-time-code) services, the frontend token-refresh and single-flight logic, and the three-photo same-person identity check (`BR-005`), we write failing tests from the acceptance criteria first and then implement; every other layer is implemented first and then its tests are written and run before the Bolt is done.\n- **Test-first modules (exact list)**: backend JWT service and OTP service\n  (`AUTH-010`–`AUTH-016`); frontend API-client proactive refresh, 401 → refresh →\n  retry, and single-flight logic (`FE-005`, `FE-006`); the identity-check decision\n  logic over the three photos (`BR-005`). Any other module is test-after.\n- **Coverage floor**: each application (backend and frontend) keeps **at least 80%\n  line coverage**, measured over the whole application at every merge and enforced\n  by the tool (`pytest-cov` with `--cov-fail-under=80`; Vitest coverage thresholds\n  `lines: 80`). Coverage exclusions are declared in committed configuration and are\n  never added to make a check pass; the floor may not be weakened (`org.md`).\n- **Requirement coverage**: every `FR-*`, `AUTH-*`, `BR-*` and `FE-*` requirement\n  maps to at least one test (client Section 12 for `FR`/`AUTH`/`BR`; `FE` added by\n  interview Q5). How business-only or blocked IDs are recorded is\n  **[Open — confirm]** (see `evidence.md`).\n- **Backend tooling**: `pytest` + `pytest-cov`; API tests through FastAPI's test\n  client; integration tests against a **real PostgreSQL** database with Alembic\n  migrations applied, never SQLite (`NFR-002`, `NFR-003`).\n- **Frontend tooling**: Vitest + React Testing Library for units and components,\n  including the Zustand auth store and the API client (`FE-001`–`FE-007`).\n- **End-to-end**: a small Playwright set for the main journeys: sign-up/login, and\n  photos → payment → report. It is additive to the Standard test strategy and does\n  not count toward the 80% line floor.\n- **Paid services are faked**: OpenAI, Stripe and the email/OTP provider are\n  replaced by fakes behind their configuration-selected abstractions (`NFR-008`,\n  `NFR-013`). The default test run never calls a paid third-party API.\n- **Test strategy**: the workflow's Standard strategy sets test volume and types;\n  the floors above are additive to it.\n- **CI before merge**: a small **GitHub Actions** workflow is delivered in the first\n  piece of work (the walking skeleton). On every pull request to `main` it runs, for\n  each app: lint (including security rules), format check, type check, tests and\n  the coverage floor. `main` is protected so the workflow must pass before merge\n  (interview Q6). This meets the `org.md` \"CI execution before merge\" floor for\n  `classic`."
    }
  ],
  "obligations": {
    "strategy": "standard",
    "strategy_volume": [
      "Five to eight tests per component.",
      "Unit tests plus integration tests for key boundaries.",
      "Add E2E, performance, or security tests when requirements demand them."
    ],
    "scope_floor": [
      "Keep the existing test suite green.",
      "This scope adds no extra new-test floor beyond the selected test strategy."
    ],
    "combination_rule": "Apply every selected-strategy obligation and every scope-floor obligation; neither replaces the other, and a targeted scope regression may add the narrowest necessary test type beyond the strategy default."
  },
  "plan_profile": {
    "methodology": "custom",
    "runner_step": "Bootstrap the minimal test runner/configuration and record the exact unit-scoped command.",
    "runner_ready_before_first_test": true,
    "testable_layers": [
      "Data model / database behavior",
      "Repository / data access",
      "Business logic",
      "API / endpoint",
      "Frontend behavior"
    ],
    "steps": [
      "Project structure and production configuration skeleton.",
      "Bootstrap the minimal test runner/configuration and record the exact unit-scoped command.",
      "Custom ordering - For the backend JWT and OTP (token and one-time-code) services, the frontend token-refresh and single-flight logic, and the three-photo same-person identity check (`BR-005`), we write failing tests from the acceptance criteria first and then implement; every other layer is implemented first and then its tests are written and run before the Bolt is done.",
      "Implementation and tests - preserve that exact ordering; do not convert it to layer-local TDD.",
      "Environment/build configuration.",
      "Documentation and traceability."
    ]
  },
  "input_sha256": "sha256:03fb16fc47ef3da40c51217a3dc1655e4655b606e6041af3e826578db6a2b701",
  "contract_sha256": "sha256:c547d86232e1807f6acac4300e6efb06c9bafa5748fa79380bf964ac87c3d5db"
}
```

## Steps

- [x] **Step 1 — Structure and configuration.** Backend module `app/payments/` in the U1–U4 layout with import-linter contracts. Typed settings: `REPORT_PRICE_AMOUNT`, `REPORT_PRICE_CURRENCY`, `PAYMENT_PROVIDER` (`stripe` | `fake`), `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, success/cancel URLs, `PAYMENT_CONFIRM_WAIT_SECONDS`, all in `.env.example` with placeholders only. Add the `stripe` SDK to the lockfile.
- [x] **Step 2 — Test runner readiness.** `backend/tests/payments/` with conftest (real PostgreSQL, Stripe fake); confirm the unit-scoped commands in `unit-test-instructions.md` run.
- [x] **Step 3 — Stripe adapter and fake** (US6.2, US6.3). `PaymentProvider` interface: create hosted Checkout session (one-time, configured price) and verify/parse a webhook from the raw body. The Stripe adapter uses the SDK; the fake records sessions, serves a dev/test-only hosted page with "Pay" / "Cancel" that redirects back and posts a correctly signed webhook. The fake is refused outside development and test. Tests after.
- [x] **Step 4 — Data model and service** (US6.3, US6.4). Migration `0005_u5_payments` with clean downgrade: `payments` (user, provider session id, amount, currency, status `pending|succeeded|cancelled`, timestamps) and `payment_events` with a unique provider event id (idempotency enforced by the database, safe under concurrent delivery). Checkout requires a consistent photo set: it calls the U4 `evaluate_identity` port and returns 409 with the same mismatched angles (AC6.2.2). Webhook marks the payment succeeded and never starts analysis. Public port `require_paid(user)` raising 402 for U6/U8, checked before photo consistency (AC6.4.2). Tests after.
- [x] **Step 5 — API** (contract C-payments). `GET /payments/offer` (price, currency, what is unlocked), `POST /payments/checkout` (returns the hosted Checkout URL), `GET /payments/status` (none / pending / succeeded, for polling), `POST /payments/webhook` (raw-body signature check, no auth, CSRF-exempt). All user routes protected and `no-store`. Regenerate OpenAPI types. API and integration tests after, including duplicate and concurrent webhook delivery and a bad signature.
- [x] **Step 6 — Frontend screens** (US6.1, US6.5). `/payment`: configured price and currency, what payment unlocks, "analysis starts only when you click Start Analysis", Pay button, no results or partial content. `/payment/success`: "confirming your payment" with polling, live update and `aria-live` announcement when confirmed, "Start Analysis" shown disabled until confirmed (it links to the U6 step later), and the still-confirming message after the configured wait. `/payment/cancel` returns to the payment screen. Photo review Continue now goes to `/payment`. All HTTP via the single API client; toasts; `data-testid`. Vitest + RTL tests after.
- [x] **Step 7 — Browser journey (Playwright).** `e2e/payments.spec.ts`: sign up → onboarding (API) → photos (fixtures) → payment screen shows configured price → Pay → fake hosted page → Pay → success page shows confirming then confirmed and "Start Analysis" enabled, tagged `@checkpoint`; plus cancel returns to payment with nothing charged. Axe on each new screen. `scripts/verify-skeleton.sh` stays under its 110 s budget.
- [x] **Step 8 — Wiring and docs.** CI, `verify.sh`, `verify-skeleton.sh`, size-check, READMEs (Stripe CLI forwarding for local real-Stripe testing). Keep ≥ 80% line coverage in both apps; ruff, mypy, import-linter, ESLint, Prettier, tsc clean.
