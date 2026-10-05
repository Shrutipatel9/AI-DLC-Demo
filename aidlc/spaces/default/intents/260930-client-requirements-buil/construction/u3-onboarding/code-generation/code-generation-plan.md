# Code Generation Plan — U3 Onboarding (Consent and Questionnaire)

## Overview
**Stories:** US4.1 (consent), US4.2 (branching questionnaire), US4.3 (disclaimer), US4.4 (load the 23 questions).

**Sources:** the per-unit design stages were skipped for this run, so design comes directly from these inception artifacts:
- `inception/user-stories/stories.md` (US4.1–US4.4 and their ACs)
- `inception/contract-design/contract-summary.md` (C1 `/onboarding/*` endpoints, C11 error codes `CONSENT_REQUIRED`, `DISCLAIMER_REQUIRED`, `QUESTIONNAIRE_NOT_SUBMITTED`)
- `inception/domain-design/components.md` (Onboarding component, ADR-007: medical answers never leave Onboarding)
- `inception/refined-mockups/` (screens)
- `aidlc/spaces/default/knowledge/onboarding_questionnaire_spec.md` ([QS]: the 23 questions, Q19 conditional on Q4, follow-ups, disclaimer wording, medical flags on Q8–Q12)
- `inception/units-generation/unit-of-work.md` §U3

**Build on:** U1 and U2 conventions — Identity `current_user`, the error envelope, the API client, the auth store, the toast service, `confirm()`, `FieldError`, and the test fixtures.

## Decisions carried into the code
| # | Decision |
|---|---|
| D1 | The questionnaire definition is versioned data loaded from a seed file (`backend/app/onboarding/data/questionnaire_v1.json`), built from [QS]. It is not hardcoded in the logic, and branching conditions are part of the data. |
| D2 | Consent is versioned. The consent text comes from configuration/seed data. A `ConsentRecord` stores the user, the version and the time. Every questionnaire endpoint requires the current consent, or returns 403 `CONSENT_REQUIRED`. |
| D3 | Answers are saved one per request (`PUT /onboarding/response/answers/{questionId}`), so the user can resume. Submitting validates that every required visible question is answered, then requires the disclaimer; otherwise it returns 422 `DISCLAIMER_REQUIRED` or `VALIDATION_FAILED`. |
| D4 | Medical answers are tagged in the definition. A public read port `get_non_medical_answers(user_id)` returns only non-medical answers with their question text (ADR-007). Nothing else exposes answers. |
| D5 | Open client questions stay labelled `[Open — client]` in the seed data, without inventing requirements: the Q19 branch condition and the Q9/Q11 follow-up shape. |
| D6 | The frontend shows one question per screen, with Back/Next, a progress bar, the conditional Q19, follow-ups, then a disclaimer checkbox and a supportive message, then submit. The flow resumes from the saved answers. |
| D7 | Nothing is committed or pushed. |

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

U3 contains no test-first modules, so every layer is test-after.

## Steps
- [x] **Step 1 — Model and migration** `0003_u3_onboarding` (US4.1, US4.2, US4.4). Tables: `consent_records`, `questionnaire_definitions` (version, JSON), `questionnaire_responses` (user, definition version, status, answers JSON, `disclaimer_accepted_at`, `submitted_at`). The migration includes a clean downgrade. The seed loader loads `questionnaire_v1.json`, built from [QS] (D1, D5).
- [x] **Step 2 — Backend Onboarding module** `app/onboarding/`. Contents:
  - services: consent, definition, branching and visibility, answer save with validation, submit;
  - repositories;
  - routes for `/onboarding/consent`, `/onboarding/questionnaire`, `/onboarding/response`, `/onboarding/response/answers/{questionId}` and `/onboarding/response/submit`;
  - the public port `get_non_medical_answers` (D2–D4);
  - import-linter contracts extended for the new module.
- [x] **Step 3 — Backend tests.** Consent gate (5), definition and branching including Q19 and follow-ups (7), answer validation per type (7), submit with the disclaimer and required checks (6), the medical filter port (4), API ownership 404 and auth (4), and the migration round-trip.
- [x] **Step 4 — Frontend** `/onboarding`:
  - the consent screen;
  - a one-question-per-screen wizard (types from the definition: single and multi choice, text, scale), with Back/Next, a progress bar, resume, the conditional Q19 and follow-ups;
  - a disclaimer step with the supportive message, then submit;
  - toasts, `FieldError`, `data-testid`;
  - the home page links to onboarding until it is submitted;
  - OpenAPI types regenerated.
- [x] **Step 5 — Frontend tests.** Consent (4), wizard navigation and branching (7), question types (6), disclaimer and submit (5), resume (3).
- [ ] **Step 6 — E2E.** `e2e/onboarding.spec.ts`: sign in, then consent, answer every question (Q19 shown when Q4 is set), disclaimer, submit. One scenario is tagged `@checkpoint`. CI, `verify.sh` and `verify-skeleton.sh` run it; the checkpoint run stays within 110 s.
- [ ] **Step 7 — Verify and record.** Run `bash scripts/verify.sh` and `bash scripts/verify-skeleton.sh` until green, never lowering a target. Update the READMEs. Write `code-summary.md`, `source-manifest.json` (exact schema `{stage, unit, version: 1, writes: [{path}]}`) and `traceability.json` (US4.1–US4.4 ACs pointing to files).

## Quality targets (never relaxed)
- At least 80% line coverage per app.
- Zero axe WCAG 2.1 AA violations.
- Bundle at most 200 KB per route; the onboarding route is code-split.
- No outside network calls in tests.
- The checkpoint command finishes in 110 s or less.
