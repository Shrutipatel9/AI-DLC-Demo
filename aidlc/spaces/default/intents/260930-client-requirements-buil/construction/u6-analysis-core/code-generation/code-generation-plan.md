# Code Generation Plan — U6 Analysis core (`u6-analysis-core`)

## Scope
Stories US1.7, US1.12, US7.1–US7.11 (`unit-of-work.md` U6; `stories.md`). Requirements FR-007, FR-008, FR-009, FR-015, BR-001, NFR4/NFR5/NFR10.
Design stages were skipped for this unit; formulas, label bands and trigger levels are settled here and labelled
`[Decided by delivery team]` in `code-summary.md`. Out of scope: real image generation (U7), showing the report (U8).

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

- [x] **Step 1 — Structure and configuration.** Backend modules `app/jobs/` (job mechanism + worker entry point), `app/ai/` (text and image adapters), `app/measurement/` (FaceMeasurement), `app/report_writing/` (ReportWriting) and `app/analysis/` (AnalysisPipeline), with import-linter contracts. Typed settings: `AI_TEXT_PROVIDER`, `AI_IMAGE_PROVIDER` (`openai` | `fake`), `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_TEXT_MODEL`, `OPENAI_IMAGE_MODEL`, timeouts, retry counts, image concurrency, expected-wait minutes, distress trigger levels, symmetry label bands; placeholders only in `.env.example`. A `worker` command (and Docker Compose / verify scripts start it).
- [x] **Step 2 — Test runner readiness.** `backend/tests/{jobs,ai,analysis}/` with conftest (real PostgreSQL, AI fakes, in-process queue drain); confirm the unit-scoped commands run.
- [x] **Step 3 — Job mechanism** (US1.7). PostgreSQL-backed jobs table (status, current step, result, failure reason, heartbeat) claimed with `FOR UPDATE SKIP LOCKED`; a worker process; jobs left running by a dead worker are resumed or failed on restart, never stuck; failures logged without photo data or answer text. Tests after.
- [x] **Step 4 — AI adapters and fakes** (US1.12). Text and image interfaces chosen by configuration; OpenAI adapters with timeouts and typed errors (including rate limit); fakes that record calls and can succeed, fail, return malformed output or be slow, plus a committed "realistic latency" profile. Tests after.
- [x] **Step 5 — Measurements and assessments** (US7.3, US7.5, US7.7, US7.8, US7.10). From U4 FaceGeometry landmarks: geometric measurements for Eyebrows, Eyes, Nose, Cheeks, Jaw, Lips, Chin (front photo); Ears from each side's 3/4 photo, falling back to front when missing; Hair, Skin, Neck as documented heuristics or an explicit "no measurement" marker; symmetry 0–100 with configured label bands and Regional Balance; facial thirds; dimorphism, prototypicality and face-shape classification as first-pass heuristics. All deterministic. Tests after, including identical results for the same photos and band boundaries.
- [x] **Step 6 — Privacy-safe AI request and report text** (US7.4, US7.9). Request builder sends photos, measurements and the non-medical answers (with question text) from the U3 public port — never a medical-flagged question or follow-up — plus the reassuring-tone instruction when Q20/Q21 are at or above the configured level. Text output schema per feature for all 11 features: 3–5-sentence narrative citing at least one stored value, projected-potential ideas, summary callout, recommendations sorted into the three tiers by the ASM-007 keyword rules. Invalid or malformed output is retried up to the configured count, then the run fails with a reason; nothing half-valid is stored. Tests after, including the canary privacy test.
- [x] **Step 7 — Pipeline, start and re-run** (US7.1, US7.2, US7.6, US7.11). Migration `0006_u6_analysis` with clean downgrade: analysis runs (one per payment, plus one free re-run), steps and their saved outputs, the photo files recorded at start (R-02), the stored analysis result, and 24 image slots. Steps: measuring → writing → generating images (U6 records 24 slots as "not available yet"; U7 fills them) → assembling. Completed steps are never repeated on resume. `POST /analysis/start` uses the U5 `paid_photo_snapshot` port (402 before 409), is idempotent under concurrent requests (database constraint), and never starts a second run after completion. `GET /analysis/current` returns steps with done/current/waiting, expected wait, failure explanation and re-run availability; `POST /analysis/rerun` allows one free re-run after a failure. Regenerate OpenAPI types. API and integration tests after.
- [x] **Step 8 — Frontend progress screen** (US7.1, US7.2, US7.11). "Start Analysis" on the payment success screen now calls start and goes to `/analysis`. `/analysis`: step list with text states, `aria-live` announcements without moving focus, "you can close this page" with the expected wait, resume on revisit, "View my report" (to `/home` until U8) when ready, plain-language failure with the free re-run button, then "contact support" after a second failure. 409 sends the user to `/photos`. All HTTP via the single API client; toasts; `data-testid`. Vitest + RTL tests after.
- [x] **Step 9 — Browser journey (Playwright).** `e2e/analysis.spec.ts`: paid user with consistent photos → Start Analysis → progress steps advance → ready → "View my report", tagged `@checkpoint`; plus failure → free re-run → completes (fake told to fail once). The worker runs as a real process in `verify-skeleton.sh` and `verify.sh`, with the fast fake profile. Axe on the new screen. `verify-skeleton.sh` stays well under its 110 s budget.
- [x] **Step 10 — Wiring and docs.** CI, verify scripts, Docker Compose worker service, size-check, READMEs (worker, AI settings, the opt-in AI evaluation suite placeholder for `(eval)` ACs). Keep ≥ 80% line coverage in both apps; ruff, mypy, import-linter, ESLint, Prettier, tsc clean.
