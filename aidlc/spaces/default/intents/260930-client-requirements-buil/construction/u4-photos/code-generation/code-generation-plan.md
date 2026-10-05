# Code Generation Plan — U4 Photos and the same-person check (`u4-photos`)

## Scope
Stories US1.10, US1.11, US5.1, US5.2, US5.3, US5.5, US5.10, US5.6, US5.11, US5.8, US5.9
(`unit-of-work.md` U4; `stories.md`). Requirements FR-005, FR-006, BR-004, BR-005, NFR3/NFR11.
Design stages were skipped for this unit, so open design points are settled here and labelled
`[Decided by delivery team]` in `code-summary.md`. Out of scope: measurement (U6), journey routing (U10).

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

- [x] **Step 1 — Structure and configuration** (US1.10, US1.11, US5.9). Add backend modules `app/media/` (MediaStore), `app/face/` (FaceGeometry) and `app/photos/` (PhotoIntake) following the U1–U3 module layout and import-linter contracts. Typed settings: `MEDIA_BACKEND` (local disk, path from config), `PHOTO_ANGLES` (default `front,left_34,right_34`), upload limits (10 MB; JPEG/PNG/HEIC), per-photo thresholds (min resolution, brightness range, face-to-frame proportion, pose yaw ranges per angle, occlusion) and `IDENTITY_THRESHOLD=0.6`, all in `.env.example`. Pin the MediaPipe Face Landmarker model version and SHA-256; a script fetches it into a git-ignored path. Add dependencies (`mediapipe`, `pillow`, `pillow-heif`) to the lockfile.
- [x] **Step 2 — Test runner readiness.** Create `backend/tests/photos/` with conftest (real PostgreSQL, fixture images) and confirm the unit-scoped commands in `unit-test-instructions.md` run before Step 3.
- [x] **Step 3 — Same-person decision, test first** (US5.6, BR-005). Write failing tests first for the pure decision function: the 8-case table (AC5.6.1), the threshold boundary `≤ 0.6` (AC5.6.2), the [IV] §4 worked examples (AC5.6.3), "two angles only → not run, not blocking" (AC5.6.4). Hub-case tie-break `[Decided by delivery team]`: flag the side (left or right) whose distance to front is larger; equal → right. Then implement the 5-ratio landmark signature (ASM-010) and the shared `evaluate_identity(user)` function recomputed from current photos every call, no cache (AC5.6.5), exposed in the public port for checkout (U5) and start-analysis (U6).
- [x] **Step 4 — MediaStore** (US1.10, US5.8). Local-disk adapter behind an interface; re-encode on write (strip EXIF/GPS/device data, convert HEIC to JPEG); replacing a photo deletes the old file; files served only through an owner-checked authenticated endpoint with `Cache-Control: no-store` (404 for other users). Tests after.
- [x] **Step 5 — FaceGeometry** (US1.11). One Face Landmarker loaded once per process, returning 478 landmarks or typed `NoFace` / `MultipleFaces`; deterministic for the same image; results never cached. Tests after, using real face fixture images.
- [x] **Step 6 — Per-photo checks** (US5.5, US5.10). Readable image, minimum resolution, brightness, exactly one face, face-to-frame proportion, pose matches the angle (yaw from landmarks, turn direction explained), covered eyes/mouth heuristic. Each failure maps to a photo-focused reason and fix hint, never about appearance. Thresholds read from config. Tests after.
- [x] **Step 7 — Data model and API** (contract C-photos). Alembic migration `0004_u4_photos` (photos table: user, angle, storage key, status, check result, landmark signature; one current photo per user and angle) with clean downgrade. Endpoints: `GET /photos/requirements` (rules + configured angles), `GET /photos` (set status, "N of M", identity result with flagged angles), `PUT /photos/{angle}` (upload/replace, checks run, result returned), `GET /photos/{angle}/image` (owner-only). All protected, `no-store`; requires a submitted questionnaire (U3 public port). Regenerate OpenAPI types. API and integration tests after.
- [x] **Step 8 — Frontend screens** (US5.1, US5.2, US5.3, US5.11). `/photos`: requirements screen with the 7 rules and example images; one step per configured angle with turn instruction and guidance; file upload always available; camera capture with angle guide overlay, preview, retake/use, graceful fallback when denied or absent; checking state announced via `aria-live`; progress "N of 3"; review screen with flagged photo highlighted by text + icon, Continue disabled with reason while flagged or pending, no auto-navigation. All HTTP via the single API client; toasts on outcomes; `data-testid` on interactive elements; phone-portrait layout. Home links to photos once the questionnaire is submitted (temporary link until U10). Vitest + RTL tests after.
- [x] **Step 9 — Browser journey (Playwright).** `e2e/photos.spec.ts`: sign up → onboarding → upload three valid same-person photos → review shows consistent → Continue; plus a rejection case (wrong file type or no face) and a mismatched-set case showing the flagged angle. Tag the main journey `@checkpoint`. Keep `scripts/verify-skeleton.sh` under its 110 s budget by running only the skeleton journey plus one `@checkpoint` journey per unit (session and branch scenarios stay in `verify.sh`). Axe checks on each new screen.
- [x] **Step 10 — Wiring and docs.** CI, `verify.sh`, `verify-skeleton.sh`, size-check for `/photos`, CORS methods, backend/frontend READMEs (new env keys, model download). Keep both apps at ≥ 80% line coverage; ruff, mypy, import-linter, ESLint, Prettier and tsc clean.
