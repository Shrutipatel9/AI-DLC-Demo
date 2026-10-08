# Code Generation Plan — U8 Report, Home dashboard and PDF (`u8-report-home`)

## Scope
Stories US8.1–US8.8, US11.1–US11.3 (`unit-of-work.md` U8). Requirements FR-009, FR-011, FR-015, BR-001. Code-first; decisions labelled `[Decided by delivery team]` in `code-summary.md`. Out of scope: chat (U9), journey routing and settings (U10). Items marked TBD in [RD]/[RT] stay out.

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

- [x] **Step 1 — Module, config and checkpoint speed.** Backend module `app/report/` with import-linter contracts; configured template text (introduction, "Understanding Your Results" preamble, limitations, "consult a qualified professional" copy, tier captions) as versioned seed data; a server-side PDF library added to the lockfile; `backend/tests/report/` ready. Speed up `scripts/verify-skeleton.sh` (currently ~99 s of a 110 s budget) without dropping any checkpoint journey — e.g. skip reinstall/build steps whose inputs are unchanged, reuse the Playwright browser install, run migrations once — so it runs well under 90 s.
- [x] **Step 2 — Report assembly and API** (US8.1, US8.2, US8.7). Assemble and auto-publish the report when a run completes (no approval step): exactly 11 features in the order Hair, Eyebrows, Eyes, Nose, Cheeks, Jaw, Lips, Chin, Skin, Neck, Ears; each with narrative, own photo + AI "after" image slot state (ready / pending / not available yet), projected-potential ideas, summary callout, recommendations in exactly one of three tiers (keyword rules fill missing tiers); assessments (symmetry, Regional Balance, thirds, dimorphism, prototypicality, face shape); metric tables with units or a "no measurement" note. `GET /report` uses the U5 `require_paid` port (402) and is owner-only (404). Tests after.
- [x] **Step 3 — PDF** (US8.5). Backend-owned template following the [RD] §5–§10 page order, preamble before any score; generated on first download, cached privately via MediaStore, regenerated when any report image changes. `GET /report/pdf` with the same paywall and ownership. Tests after.
- [x] **Step 4 — Home API** (US11.1, US11.3). `GET /home`: key stats, before/potential image, "Priority Features to Improve" (`[Decided by delivery team]`: the three features with the lowest scores), protocol summary from the recommendations per [RD] §14 / [RT] §3.7 (TBD items left out), six-axis radar values including Symmetry, report status and PDF link. Regenerate OpenAPI types. Tests after.
- [x] **Step 5 — Report page** (US8.3, US8.4, US8.6, US8.7, US8.8). `/report`: single scroll with table of contents (focus moves to the section heading), preamble first, assessments views (symmetry score/label/Regional Balance, thirds, display-only dimorphism sliders, prototypicality, face-shape wireframe) each with a text/table alternative, Skin and Face Shape content per [RD] §9.2 / [RT] §10, 11 feature sections with photo vs AI "after" image (visible AI label and alt text), metric tables scrolling inside their own area on phones, tiered recommendations, Download PDF. Vitest + RTL tests after.
- [x] **Step 6 — Home and header navigation** (US11.1, US11.2). `/home` becomes Home Overview once a report exists (key stats, before/potential image, priorities, protocol card, radar chart with text alternative, status, PDF); header with Home, Report, AI Visuals, Chat (placeholder link until U9) and Settings in the user menu, reachable within one extra tap on phones. "View my report" now goes to `/home`. Vitest + RTL tests after.
- [x] **Step 7 — Browser test and wiring.** Extend the analysis `@checkpoint` journey (no new `@checkpoint` test) to land on Home Overview, open the report, see 11 feature sections and download the PDF; axe on `/home` and `/report`. CI, verify scripts, size-check, READMEs. ≥ 80% coverage in both apps; all linters clean; `verify-skeleton.sh` well under 110 s.
