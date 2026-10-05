**Collaborator:** aidlc-quality-agent

## Contribution

Quality-engineering review of the lead draft (`team-practices.md`, `discovered-rules.md`,
`evidence.md`) against `client_requirements.md` and `org.md` § Testing Posture. This is a
greenfield project, so everything below is a **suggestion to confirm in the interview**
unless it cites a client requirement ID or an org rule. Tool names are
**[Suggested — confirm]**.

### 1. Testing Posture — methodology and ordering options for the interview

The org default (`test-after`, implement a layer then test it) is a valid choice.
It is also the posture recorded when nothing is affirmed. The interview should offer
these options, each stated with explicit `Methodology` and `Ordering` fields so
Code Generation can resolve them (`org.md` § Testing Posture):

| Option | Methodology | Ordering | Fit for this project |
|---|---|---|---|
| A (org default) | `test-after` | Implement each testable layer (repository → service → route; store → API client → component), then write and run that layer's tests before the Bolt is done. | Simplest. Weakest protection for the security-critical auth rules, where most defects are boundary and state bugs. |
| B (recommended) | `custom`: test-after in general, **test-first for designated security-critical and pure-logic modules** | For JWT/OTP services (`AUTH-010`–`AUTH-016`), the refresh/single-flight logic in the API client (`FE-005`, `FE-006`), and the identity-check vote (`BR-005` rules 2–5), write the failing tests from the acceptance criteria first, then implement. Every other layer uses test-after. | These modules have exact numeric rules (10 min, 60 s, 5 attempts, 15 min, 15 min / 7 days) and state machines (rotation, reuse detection, single-flight). Writing the tests first catches off-by-one and ordering defects cheaply. |
| C | `tdd` everywhere | Red → green → refactor per behaviour. | Heavy for UI, CV and LLM prompt work, where outputs are exploratory. |
| D | `atdd` (acceptance tests drive work) | Given/When/Then acceptance criteria from User Stories become executable tests, tagged with requirement IDs, before implementation. | Fits the client's rule that every requirement has a test (Section 12) and the inception guardrail that acceptance criteria use Given/When/Then. More upfront work per Bolt. |

If B or D is chosen, the designated module list must be recorded in `team.md` so
the rule is testable ("which modules are test-first?" must have a yes/no answer).

### 2. Coverage floor and tooling

- **Floor definition (clarification needed)**: the draft says "80% line coverage for
  each application … measured per Bolt". Suggested precise wording: *each
  application's cumulative line coverage is at least 80% at every Bolt merge,
  measured over the whole application (not only the Bolt diff)*. It is enforced by
  the tool so it cannot drift:
  - Backend: `pytest-cov` (coverage.py) with `--cov-fail-under=80` and
    `branch = true` in `[tool.coverage.run]`. Branch coverage is advisory unless
    the team affirms a branch floor.
  - Frontend: Vitest with `@vitest/coverage-v8` and
    `coverage.thresholds.lines: 80`.
- **Exclusions must be declared up front.** For example: Alembic `versions/`,
  generated OpenAPI/TS types, `next.config.*`, and `__init__.py` files with no logic.
  Exclusions go in committed config and must never be added to make a step pass.
  Adding an exclusion to pass would weaken the floor, which `org.md` forbids.
- **Candidate stricter floor**: 90–95% line **and** branch coverage for the auth
  modules (backend `auth`/`jwt`/`otp` services, frontend auth store and API
  client). This is additive to the 80% floor, not a replacement.
- **Frontend measurement limit**: Vitest with React Testing Library cannot render async
  Next.js App Router Server Components. Coverage of those comes only from E2E, and
  Playwright coverage should **not** count toward the 80% line floor. The team should
  expect that client-side logic (store, API client, hooks, client components) carries
  the frontend floor. Keeping logic out of server components helps.
- **Type checks as a gate**: `tsc --noEmit` (TS `strict`) and optionally `mypy` on
  the backend. These are cheap and catch a class of defects that tests miss.

### 3. Requirement-to-test traceability (client Section 12, Testing row)

- **Mechanism [Suggested — confirm]**: tag tests with requirement IDs so the mapping can
  be checked by a tool rather than reviewed by hand:
  - pytest: a registered marker `@pytest.mark.req("AUTH-011")` (multiple allowed).
  - Vitest / Playwright: the ID in the test title, e.g.
    `describe("[FE-005] proactive refresh", …)`.
  - A small script lists all `FR-*`, `AUTH-*`, `BR-*` IDs from
    `client_requirements.md` and reports any ID with no tagged test. That report
    is part of the Bolt "done" evidence, and Build and Test uses it.
- **Gap the interview must resolve**: read literally, "every `FR-*`, `AUTH-*` and
  `BR-*` maps to at least one test case" includes rules that no software test can
  check:
  - `BR-006`: third-party costs are the client's.
  - `BR-007`: no timeline or estimate.
  - `FR-003` / `FR-004` literal content: blocked until the Onboarding Questionnaire
    Specification arrives.
  - `FR-006` / `BR-005` thresholds: set during development (`ASM-002`).

  Per the client's instruction to surface conflicts rather than resolve them
  silently, the human should confirm the following. A test may be marked `N/A`
  with a written justification for business-only rules, or `Deferred` with a
  pointer to the missing specification. The ID is still listed in the matrix, so
  nothing is dropped silently.
- **`FE-*` coverage**: Section 12 names only `FR-*`, `AUTH-*` and `BR-*`. `FE-001`
  to `FE-007` are client-stated and security-relevant, so I recommend including
  them in the same rule **[Recommendation]**.

### 4. CI quality gates when the CI Pipeline stage is skipped

- `org.md` sets two conditions for `classic`: CI execution before merge, and
  floors that "may not be weakened". A local-only pre-merge run is therefore **not
  an equivalent substitute**. A narrower team or project rule that replaces CI with
  a local run contradicts a broader rule and would be rejected under the
  strict-additive model. The honest options for the interview are:
  1. **(recommended)** Add a minimal GitHub Actions workflow as an ordinary Code
     Generation deliverable in the first Bolt. The remote is already GitHub. The
     workflow runs on pull requests to `main`:
     - **backend**: `ruff check`, `ruff format --check`, `pytest` with coverage
       against a PostgreSQL service container, and `alembic upgrade head` plus
       `alembic check` for model/migration drift.
     - **frontend**: `eslint`, `prettier --check`, `tsc --noEmit`, and
       `vitest run --coverage`.
     - **both**: the requirement-traceability report.

     Branch protection on `main` requires these checks. This does not need the
     skipped CI Pipeline stage. It is a small file set, and the stage's
     infrastructure-as-code or deployment wiring stays out of scope.
  2. The team explicitly records that the org `classic` floor is not met for this
     workflow. This is a human decision, recorded as a known deviation at the
     gate. It is not affirmed as a team rule.
- In either case, keep **one verification entry point** per app, such as
  `scripts/verify` or a `make check` target. Developers, the Bolt gate and CI all run
  the same command, so "passed locally" and "passed in CI" mean the same thing.
- **Suggested Bolt "done" gate**: lint and format clean; type check clean; unit and
  integration suites green; coverage floor met; no new untagged requirement IDs for
  the Bolt's scope; no tests skipped without a linked reason. **Flaky-test policy**:
  no automatic retries that hide failures, and quarantining a test needs a recorded
  reason and owner.

### 5. Test and code patterns for external services

The shared pattern: every third-party integration sits behind a small interface
owned by the project (a port or adapter), selected by configuration (`NFR-008`,
`NFR-013`). Tests use an in-repo fake of that interface. The test suite never mocks the
vendor SDK directly. By default, no automated test calls a paid API (`BR-006`).
Opt-in live checks run under a separate marker (e.g. `@pytest.mark.live`), are
excluded from the default run and the coverage gate, and read keys only from the
environment.

| Service | Deterministic tests (default suite) | What cannot be unit-asserted and needs a different check |
|---|---|---|
| **OpenAI narrative** (`FR-008`) | Test the **prompt builder** as a pure function: questions sent with real question text, not IDs (a); measurement values present (b); goal/motivation context (d); distress flag switches the tone instruction (e); **medical, medication and allergy answers are excluded from the payload** (f), asserted structurally. Validate the response schema with a fake client returning canned JSON: all 11 features (`FR-009`, `BR-008`), 3–5 sentences per feature (c). Test timeout, retry and malformed-response handling. | Whether the model actually *writes* in the right tone. This needs a small opt-in evaluation set, reviewed by a person or scored by rubric, with an agreed pass threshold (open item). |
| **AI Beauty Assistant** (`FR-019`) | The system-prompt and guardrail layer is deterministic: medical-decline instructions are always present and grounding context is scoped to the current user's report (no data from other users — an authorization test). | Model compliance on medical questions varies from run to run. Suggested: an opt-in evaluation set of medical and medication questions with a required decline rate (the target is an interview item; 100% on a fixed set is a reasonable default). |
| **Image generation** (`NFR-013`, `FR-020`, `FR-022`) | A fake generator returns a fixture PNG. Assert: the vendor is chosen from configuration; exactly 24 images per report (13 + 11); per-image failure and retry behaviour; what happens on partial failure (open design question — surface it to Functional Design). | Identity preservation and quality (`ASM-011`). This is a manual acceptance check on sample outputs, not an automated gate. |
| **Stripe** (`FR-015`, `FR-016`, `NFR-009`) | Stub Checkout Session creation (respx/`stripe-mock`). Test webhooks with a signature generated from a test signing secret: a valid signature is accepted, a bad or missing signature is rejected, duplicate event delivery is idempotent, and **a webhook never starts analysis** (assert no pipeline enqueued). Test HTTP 402 on analysis and report routes before payment (`BR-001`). Price and currency come from configuration, and there is a test that the value is not hardcoded (`FR-016`). | End-to-end with real Stripe test mode through `stripe listen` is a manual or opt-in check only. Live keys never appear in tests. |
| **Email OTP** (`NFR-012`) | An `EmailSender` interface with an in-memory outbox fake, so tests read the sent code. OTP generation takes an injected random source; all expiry, cooldown and lockout logic takes an **injected clock** (e.g. `time-machine`/`freezegun`) so time-boundary tests are exact and instant. | Deliverability through the chosen provider. For local E2E, a local SMTP catcher (e.g. Mailpit) is suggested. |
| **MediaPipe / OpenCV** (`FR-006`, `FR-007`, `BR-005`, `ASM-010`) | Keep the **identity vote** (`BR-005` rules 2–5) as a pure function over a 3×3 distance matrix. Test it with a truth table (all match; one outlier per angle; the ambiguous "front matches both" case; all different → both non-front photos flagged). A property-based test (Hypothesis) checks that output is recomputed with no carry-over (rule 5). Configure the threshold (0.6) and assert it is read from config. Landmark and measurement code uses golden-fixture photos with **tolerance-based** assertions, pinned `mediapipe` / `opencv-python-headless` versions, and a pinned model-file checksum. Run under a separate `cv` marker because these tests are slow. | Threshold accuracy across a diverse population (`ASM-010` states it is unvalidated). This needs a labelled evaluation set and a tuning pass, tracked as a known quality risk rather than a unit test. |
| **PDF export** (`FR-013`) | Generated on the first download, served from cache afterwards (assert one generation); all 11 feature headings present in the extracted text. | Visual layout. Manual review, or optional snapshot comparison. |

**Test data and privacy [Suggested — confirm]**: use only synthetic, licensed or
explicitly consented face images as fixtures. Never commit real user or client photos
to the repository. Use factories (e.g. `factory_boy`/`polyfactory`, `@faker-js/faker`)
and per-test transaction rollback against real PostgreSQL, run through a Docker
service or testcontainers, with Alembic migrations applied at session start.

### 6. Security-critical auth flows — minimum test set

Backend (`pytest`, FastAPI test client, real PostgreSQL, injected clock):

- **AUTH-007 route guard**: a structural test that walks `app.routes` and asserts
  every route not on an explicit public allow-list returns 401 without a token. A
  newly added unprotected route then fails the build instead of shipping.
- **JWT validation**: reject an expired token, a wrong signature, `alg: none`, a
  refresh token presented as an access token, and a `reset_token` presented as a
  Bearer token (`AUTH-015`).
- **AUTH-011 boundaries**:
  - OTP accepted at 9:59 and rejected at 10:00 and later.
  - Resend blocked at 59 s and allowed at 60 s.
  - Failures 1–4 are allowed; the 5th triggers the lockout; a correct code during
    the lockout is still rejected; the lockout lifts at 15 min.
  - The stored OTP is not the plaintext value (assert on the database column).
- **AUTH-010 / AUTH-012**:
  - Access token expires at 15 min; refresh token at 7 days.
  - Each refresh rotates the token, so the old token becomes invalid.
  - **Reuse detection**: presenting a rotated token revokes the whole family, so
    the sibling and successor tokens fail too.
  - Logout revokes the session server-side (the old cookie fails after logout).
  - The revocation store holds a token identifier or hash, never the raw token.
- **Cookie attributes**: the refresh cookie is `HttpOnly`, `Secure`, has the
  agreed `SameSite` and `Path`, and is cleared on logout and on an invalid refresh.
- **AUTH-013 CSRF**: `/auth/refresh` and `/auth/logout` are rejected without
  `X-Requested-With` and rejected with an Origin or Referer outside the allow-list.
- **AUTH-015**:
  - The `reset_token` is single-use and expires at about 10 min.
  - It is issued only after successful OTP verification.
  - A successful reset revokes all sessions on all devices.
  - Anti-enumeration: the response to an unknown email is the same as for a known
    one (`BR-009` exception).
- **AUTH-016**: a wrong current password is rejected. A successful change keeps
  the current session valid; this is the opposite of AUTH-015, so test both side
  by side.

Frontend (Vitest, Mock Service Worker, fake timers):

- **FE-005**:
  - Proactive refresh fires about 1 min before expiry.
  - On a 401, the client refreshes and retries **once**, with no retry loop.
  - **Single-flight**: N concurrent 401s produce exactly one `/auth/refresh`
    call, and all N requests are retried with the new token.
  - Access-token expiry alone never clears auth.
- **FE-006**: auth is cleared and the user is redirected only when refresh returns
  401 or on explicit logout. It is **not** cleared on network errors, 5xx
  responses or a page reload.
- **FE-002 / FE-003 / FE-007 as static guards**: add ESLint `no-restricted-syntax`
  or `no-restricted-imports` rules, which catch violations at lint time rather than
  test time:
  - ban `localStorage`/`sessionStorage` in auth code;
  - ban `zustand/middleware` `persist` in the auth store;
  - ban UI components from importing auth API functions or reading tokens.

  Add a unit test that spies on storage APIs during a full login → refresh →
  logout sequence and asserts no writes.
- **Rehydration** (`FE-002`, `AUTH-014`): on app start the client calls
  `/auth/refresh` and then `/auth/me`, and protected routes wait while the
  store's initializing flag is set.

E2E (Playwright, small set, **only if affirmed**; see Positions):

- signup → OTP (read from the local SMTP catcher) → login → reload, still signed in;
- logout through the confirmation dialog (`BR-010`) → redirect to login;
- pay-before-analysis gate.

### 7. Testing risk to pass downstream (not a practice; flag for Functional/NFR Design)

The refresh logic has a real tension that the tests will expose:

- `FE-005` single-flight is **per browser tab**.
- Two tabs of the same session each hold the same refresh cookie. If both refresh
  at about the same moment, the second request presents an already-rotated token.
- Under `AUTH-012` reuse detection, that revokes the whole family and logs the user
  out. That breaks `FE-006`'s promise not to clear auth on routine events.

This needs a design decision, such as cross-tab coordination (BroadcastChannel or
Web Locks) or a short server-side grace window. The decision must be traceable,
since `AUTH-012` is delivery-team-decided. It should not be silently resolved in
tests. I recommend the lead records it in the evidence as a surfaced risk.

### 8. Gaps the interview must resolve (quality view)

1. Methodology and ordering: option A, B, C or D above. If B or D, which modules
   are test-first or acceptance-first.
2. Coverage wording: whole-application cumulative 80% line at each merge; declared
   exclusion list; branch floor yes or no; stricter auth-module floor yes or no.
3. How the traceability rule treats business-only or blocked IDs (`N/A` with
   justification, `Deferred` with a spec pointer); whether `FE-*` is included; the
   ID-tagging convention.
4. CI: add a minimal GitHub Actions workflow in the first Bolt (recommended), or
   record the org floor as knowingly unmet. A local-only run cannot be affirmed as
   equal to CI.
5. E2E: Playwright in or out. The Standard strategy defines unit + integration;
   E2E is additive if chosen.
6. LLM behaviour checks: whether opt-in evaluation sets for `FR-008` tone and
   `FR-019` medical decline are part of acceptance, and their pass thresholds.
7. Fixture photos: source and consent policy for face images used in CV tests.
8. Local test database: Docker Compose or testcontainers for PostgreSQL. This links
   to the draft's open "local run" item: integration tests need a real PostgreSQL
   either way.

## Positions

- AGREE: Testing Posture records explicit `Methodology` and `Ordering` fields with test-after as the unaffirmed default — this matches `org.md` and is what Code Generation resolves.
- AGREE: Integration tests run against real PostgreSQL with Alembic migrations applied, not SQLite — the client mandates PostgreSQL/Alembic (`NFR-002`, `NFR-003`), and SQLite would hide dialect and migration defects.
- AGREE: Third-party services are faked behind configuration-selected abstractions, and paid APIs are never called by default — this is required for determinism and consistent with `BR-006`, `NFR-008` and `NFR-013`.
- AGREE: The mandated rule that every `FR-*`, `AUTH-*` and `BR-*` maps to at least one test — it is client-stated in Section 12, with the `N/A`/`Deferred` handling below.
- OBJECT: The draft's CI open item lists "a local test/lint run recorded at the Bolt gate" as an alternative to CI — `org.md` makes CI-before-merge a `classic` floor that "may not be weakened", so a local-only run can be recorded only as a knowingly unmet floor, not affirmed as an equivalent team practice.
- OBJECT: "80% line coverage … measured per Bolt" is ambiguous (Bolt diff vs. whole application) and states no exclusion policy — it should say whole-application cumulative coverage at each merge, enforced by `--cov-fail-under` / Vitest thresholds, with exclusions declared in config.
- OBJECT: The mandated traceability rule in `discovered-rules.md` is literally unsatisfiable for `BR-006`/`BR-007`, and blocked for `FR-003`/`FR-004` until their specification exists — the interview should confirm `N/A` (with justification) and `Deferred` (with a spec pointer) as allowed statuses, rather than leave the rule to be silently bent later.
- OBJECT: Playwright E2E appears in the draft tooling as a default, but the Standard strategy covers unit + integration — record E2E as an explicit interview choice (additive) rather than an implied default.
- OBJECT: The candidate rules omit two quality-critical items — "NEVER commit real user or client face photos as test fixtures" (privacy) and "ALWAYS inject clock and randomness into OTP/JWT services" (without it the `AUTH-011`/`AUTH-012` time boundaries cannot be tested deterministically); add both as candidates.
