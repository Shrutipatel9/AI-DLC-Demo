# User Stories — AI Facial Analysis Platform

**Sources.**
- Requirements: `inception/requirements-analysis/requirements.md` (FR1–FR14, NFR1–NFR12), traced to `client_requirements.md`.
- Personas: `personas.md` (P1 Maya, P2 Sam, P3 Jordan, P4 Dev) plus the **Project Sponsor**, a named actor in client Section 3.
- Plan decisions: `user-stories-questions.md` Q1–Q14.
- Team practices: `inception/practices-discovery/team-practices.md`.
- Working specifications (Q7): the documents in `aidlc/spaces/default/knowledge/`, cited below as:
  - **[QS]** `onboarding_questionnaire_spec.md`
  - **[PC]** `photo_capture_spec.md`
  - **[IV]** `photo_identity_validation_spec.md`
  - **[RD]** `report_design_spec.md`
  - **[RT]** `report_template.md`

  They are drafts not yet confirmed by the client (client document v1.0 says the specifications "do not exist yet"). Their own open items stay open.

**Conventions.**
- **IDs:** stories `US{group}.{seq}`; acceptance criteria `AC{group}.{seq}.{n}` in Given/When/Then.
- **Priority** is MoSCoW. Every client in-scope feature is **Must**; delivery-team additions are ranked individually (Q5).
- **Markers:**
  - **Enabler:** groundwork for P4 (Q4).
  - **Spec:** content that comes from a working specification (Q7).
  - **[Recommendation]:** not stated by the client.
  - **[Open — Functional Design]:** a rule the design stage must fix before the criterion can be tested.
- **Size:** each story is about 1–3 days (Q3, Q9). `Deps` lists stories that must exist first; "Independent" in INVEST means a story can be built and tested alone once its `Deps` exist.
- **"Refused"** means an error response in the shared error format (US1.8) with a named machine-readable `code`. The code names and HTTP statuses not fixed by the client are decided in Contract Design.
- **Test clock:** timing criteria (codes, tokens, limits) are tested with an injectable clock, never by sleeping.
- **AI output:** criteria marked *(eval)* check real AI output. They run in an opt-in evaluation suite before handover, never in the default test run (Forbidden: paid calls in default tests). Every *(eval)* criterion has a deterministic companion that uses fakes.
- **Inherited rules:** every story also inherits the app-wide rules in US11.7 (toasts, dialogs, inline form errors), US1.8 (ownership, safe logging) and NFR9 (responsive, WCAG 2.1 AA). High-risk screens also carry their own accessibility and phone criteria (Q12).

---

## Story map (journey order)

| Group | Epic | Stories |
|---|---|---|
| 1 | Groundwork (enablers) | US1.1–US1.13 |
| 2 | Landing | US2.1–US2.2 |
| 3 | Account & sign-in | US3.1–US3.11 |
| 4 | Consent & questionnaire | US4.1–US4.4 |
| 5 | Photos | US5.1–US5.3, US5.5–US5.11 (US5.4 merged into US5.2) |
| 6 | Payment | US6.1–US6.5 |
| 7 | Analysis | US7.1–US7.11 |
| 8 | Report | US8.1–US8.8 |
| 9 | AI images & visuals | US9.1–US9.5 |
| 10 | AI Beauty Assistant | US10.1–US10.3 |
| 11 | Home, settings & app-wide | US11.1–US11.8 |

**Walking skeleton (team practice).** The skeleton is US1.1, US1.2, US1.3, US1.4, US1.5, US1.6, US1.9, US3.1, US3.2, US3.4 and US3.8. Every dependency of these stories is also in the set. Together they give sign-up → emailed code → login → "who am I" across Next.js, FastAPI and PostgreSQL. The emailed code is read from the local mail catcher, and the whole path is checked in CI and by a Playwright journey.

---

## Group 1 — Groundwork (enablers)

### US1.1 — Two-app repository with documentation
**Enabler.** As **P4 Dev**, I want one repository with separate `backend/` (FastAPI) and `frontend/` (Next.js + TypeScript) applications, each with its own README, dependencies and lockfile, so that I can understand, run and extend either app on its own.
- Priority: Must · Deps: none · Traces: NFR1, NFR7, NFR11
- AC1.1.1 Given a fresh clone, when I follow the root README, then it points me to each app's README and states that the two apps talk only over HTTP.
- AC1.1.2 Given the repository, when the backend is searched for frontend imports (or the reverse), then none exist.
- AC1.1.3 Given the repository, then `.gitignore` excludes `.env` files (except `.env.example`), key files, Python caches and virtual environments, `.next/` and local media folders.

### US1.2 — Local environment with PostgreSQL and a mail catcher
**Enabler.** As **P4 Dev**, I want Docker Compose for PostgreSQL and a local mail catcher, Alembic with a baseline migration, and `.env.example` files, so that I can run both apps locally without any hosting account or paid service.
- Priority: Must · Deps: US1.1 · Traces: NFR1, NFR11, NFR12
- AC1.2.1 Given Docker is installed, when I run the documented compose command, then PostgreSQL and the mail catcher start, and the backend connects using only values copied from `.env.example`.
- AC1.2.2 Given an empty database, when I run the Alembic upgrade, then the schema is created; a downgrade followed by an upgrade also succeeds, and CI runs this check.
- AC1.2.3 Given the codebase, then no hosting-provider SDK or host-specific configuration exists.
- AC1.2.4 Given any story that changes the schema, then it ships its own Alembic migration. **[Recommendation]**

### US1.3 — Pull-request checks in GitHub Actions
**Enabler.** As **P4 Dev**, I want every pull request to `main` to run lint, format, type, test, coverage and layering checks for both apps, with `main` protected, so that nothing merges unchecked.
- Priority: Must · Deps: US1.1 · Traces: NFR7, NFR8, FR3.6
- AC1.3.1 Given a pull request, then the workflow runs:
  - backend: Ruff, mypy, and pytest with `--cov-fail-under=80`;
  - frontend: ESLint, Prettier check, `tsc --noEmit`, and Vitest with an 80% line threshold.
- AC1.3.2 Given any of those checks fails, then the pull request cannot be merged into `main`.
- AC1.3.3 Given the default test run, then outbound network access is blocked for backend tests and unhandled requests fail frontend tests, so no call can reach OpenAI, Stripe or an email provider.
- AC1.3.4 Given a UI component that imports the auth API module or reads a token, then the ESLint layering rule fails the check (Section 5.3, FE-007).
- AC1.3.5 Given a backend route handler that imports the JWT or OTP internals directly instead of going through the auth service, then the backend import rule fails the check.

### US1.4 — Security tooling
**Enabler.** As **P4 Dev**, I want secret scanning before commit, security lint rules and dependency audits, so that secrets and known-vulnerable or forbidden packages never reach the repository.
- Priority: Must · Deps: US1.1, US1.3 · Traces: NFR3, NFR7, FR2.15
- AC1.4.1 Given a staged file containing an API-key pattern, when I commit, then the Gitleaks pre-commit hook blocks the commit.
- AC1.4.2 Given the CI workflow, then Ruff `S` rules and the ESLint security plugins run, and `pip-audit` and `npm audit` run against the committed lockfiles.
- AC1.4.3 Given the repository settings, then Dependabot is enabled for both apps.
- AC1.4.4 Given either lockfile gains an authentication-as-a-service SDK (Supabase, Auth0, Firebase Auth), then the check fails (FR2.15, `CON-002`).

### US1.5 — Configuration instead of hardcoded values
**Enabler.** As **P4 Dev**, I want every secret and tunable value read from typed configuration, so that I can change a price, model, vendor, threshold or limit without editing code.
- Priority: Must · Deps: US1.1 · Traces: NFR6, FR7.3, FR5.3
- AC1.5.1 Given the configuration module, then each value introduced by a story is a typed setting with a documented default or a required marker. The full list grows story by story (see NFR6).
- AC1.5.2 Given a vendor adapter that needs a secret is selected, when that secret is missing at start-up, then the backend refuses to start and names the missing setting without printing any secret value.
- AC1.5.3 Given the fakes are selected (the default for tests and local development), then no real vendor secret is required.
- AC1.5.4 Given the application source is scanned for literal API keys, prices or model names, then none are found.

### US1.6 — Email delivery with a fake and a local sink
**Enabler.** As **P4 Dev**, I want email sending behind an interface, with a test fake and a local mail catcher, so that sign-in codes can be tested end to end without a real provider.
- Priority: Must · Deps: US1.5 · Traces: NFR12, NFR5
- AC1.6.1 Given the email provider setting names a different adapter, when an email is sent, then that adapter is used, and no code outside the adapter changes.
- AC1.6.2 Given any send, then it has a timeout, and a failure is raised as a typed error, never swallowed.
- AC1.6.3 Given test configuration, then the fake records sent codes where the test harness can read them. This capability cannot be enabled by production configuration, and sent codes never appear in logs.
- AC1.6.4 Given local configuration, then emails go to the mail catcher from US1.2.

### US1.7 — Background jobs with progress
**Enabler.** As **P4 Dev**, I want a background job mechanism that stores each job's current step and result, so that long AI work runs outside web requests and the UI can show progress.
- Priority: Must · Deps: US1.2 · Traces: FR8.2, NFR4, NFR5
- AC1.7.1 Given a job is enqueued, when the web request returns, then the job keeps running, and its status and current step can be read by id.
- AC1.7.2 Given the backend process restarts during a job, then the job ends in either "completed" or "failed with reason". It is never left "running" forever.
- AC1.7.3 Given a job step fails, then the failure and reason are recorded and logged without any photo data or questionnaire answer text.

### US1.8 — Safe handling of personal data across the API
**Enabler.** As **P4 Dev**, I want one shared error format, a reusable ownership check and logs that never contain sensitive data, so that one user's face, answers or report can never leak to another user or into logs.
- Priority: Must · Deps: US1.1 · Traces: NFR3, NFR5, FR2.10
- AC1.8.1 Given the reusable ownership check, when user A requests a record owned by user B, then the response is 404 and no data is returned. Each resource story (US5.2, US8.1, US9.1, US10.1) repeats this check for its own resource. **[Recommendation: 404 over 403, to hide existence]**
- AC1.8.2 Given an unhandled error, then the client receives the shared error format with a request id and no stack trace.
- AC1.8.3 Given fixtures seeded with canary answer text and canary image bytes, when the full test suite runs, then the captured logs contain no canary value and no token.

### US1.9 — Frontend auth store and single API client
**Enabler.** As **P4 Dev**, I want one in-memory auth store and one API client that every frontend request goes through, so that token handling lives in exactly one place (Section 5.3).
- Priority: Must · Deps: US1.1 · Traces: FR3.1, FR3.2, FR3.6
- AC1.9.1 Given the auth store, then it holds the access token, user profile and initializing flag in memory only. It uses no `persist` middleware and no Web Storage, and it never holds the refresh token.
- AC1.9.2 Given any HTTP call in the frontend, then it goes through the one API client, which attaches the access token and sends `credentials: "include"` and `X-Requested-With`.
- AC1.9.3 Given a UI component, then it reads auth state only through the store's public selectors and never calls an auth endpoint directly (enforced by AC1.3.4).

### US1.10 — Private media storage
**Enabler.** As **P4 Dev**, I want photos, generated images and PDFs kept in private storage behind an interface, so that no face image is ever public, and a host can be chosen later.
- Priority: Must · Deps: US1.5, US1.8 · Traces: NFR3, NFR11, FR5.4
- AC1.10.1 Given a stored file, then it is saved by the configured backend: local disk in development, with room for an object-store adapter later.
- AC1.10.2 Given a stored file, then it is never served from a public static path. It is readable only through an authenticated endpoint that checks ownership.
- AC1.10.3 Given a file is replaced (for example by a retake), then the old file is deleted, not orphaned.

### US1.11 — Face landmark service
**Enabler.** As **P4 Dev**, I want one MediaPipe Face Landmarker service shared by photo checks, the same-person check and measurements, so that all three agree and the model is loaded once.
- Priority: Must · Deps: US1.1 · Traces: FR6.1, FR6.3, FR8.3
- AC1.11.1 Given an image, then the service returns the 478 landmarks, or a typed "no face" or "multiple faces" result.
- AC1.11.2 Given the model file, then it is pinned to a version and loaded once per process. Only the model is cached; results never are ([IV] §5).
- AC1.11.3 Given the same image twice, then identical landmarks are returned.

### US1.12 — OpenAI text and image adapters with fakes
**Enabler.** As **P4 Dev**, I want the OpenAI text and image-generation vendors behind interfaces with fakes, so that vendors can be swapped by configuration and tests never spend money.
- Priority: Must · Deps: US1.5 · Traces: FR10.1, NFR5, NFR6, NFR10
- AC1.12.1 Given the image vendor setting names a different adapter, when an image is requested, then that adapter is used, and no code outside the adapter changes.
- AC1.12.2 Given any adapter call, then it has a timeout, and a vendor error (including rate limiting) is raised as a typed error, never swallowed.
- AC1.12.3 Given test configuration, then both adapters resolve to fakes that record their calls and can be told to succeed, fail, return malformed output or be slow.

### US1.13 — Requirement-to-test map, journeys and accessibility checks
**Enabler.** As **P4 Dev**, I want CI to prove every client requirement has a test, the main journeys pass end to end, and the main screens pass accessibility checks, so that quality is visible and enforced.
- Priority: Must · Deps: US1.3 · Traces: NFR8, NFR9
- AC1.13.1 Given the requirement-to-test map, then every `FR-*`, `AUTH-*`, `BR-*` and `FE-*` client ID maps to at least one test, or to N/A or Deferred with a reason, and CI fails on an unmapped ID.
- AC1.13.2 Given the Playwright journeys (sign-up/login; photos → payment → report), then they pass on a phone-sized viewport (360 px wide **[Recommendation]**) and a desktop viewport, in Chromium, WebKit and Firefox.
- AC1.13.3 Given axe runs against landing, auth, questionnaire, photos, payment, progress, report, Home, chat and settings, then it reports no WCAG 2.1 AA violations.

---

## Group 2 — Landing

### US2.1 — Landing page with clear entry points
As **P2 Sam**, I want a landing page with a "Get started" button and a separate "Sign in" link, so that I can start a new analysis or get back to mine without confusion.
- Priority: Must · Deps: US1.1 · Traces: FR1.1, FR1.2, FR1.4
- AC2.1.1 Given I'm not signed in, when I open the site root, then I see "Get started" and a header "Sign in" link.
- AC2.1.2 Given I click "Sign in", then I reach the login screen, not sign-up.
- AC2.1.3 Given I'm already signed in, when I click "Get started", then I'm taken to my next unfinished step as decided by US11.8.

### US2.2 — See how it works before starting
As **P2 Sam**, I want to see the steps of the process before I start, so that I know what I'm signing up for.
- Priority: Must · Deps: US2.1 · Traces: FR1.3
- AC2.2.1 Given I scroll to the "How it works" section, then questionnaire → photos → analysis → report appear in that order, with a scroll-triggered animation.
- AC2.2.2 Given my system requests reduced motion, then the steps appear without animation.

---

## Group 3 — Account & sign-in

### US3.1 — Sign up with name, email and password
As **P1 Maya**, I want to create an account with my full name, email and password, so that my analysis and report belong to me.
- Priority: Must · Deps: US1.2, US1.6 · Traces: FR2.1, FR2.14, FR2.15, NFR2
- AC3.1.1 Given a new email, when I submit name, email and a valid password, then an unverified account is created, a code is emailed, and no token or cookie is returned.
- AC3.1.2 Given an email with a verified account, when I sign up with it, then sign-up is refused and no code is sent.
- AC3.1.3 Given an email whose earlier account was never verified, when I sign up again, then a new code is sent (subject to US3.3's limits) instead of blocking the address. **[Recommendation]**
- AC3.1.4 Given a password shorter than 8 characters, without both a letter and a number, or on the common-password list, then it is refused with the rule shown next to the field before submission. **[Decided by delivery team — Q14]**
- AC3.1.5 Given the stored user record, then the password is stored only as a slow hash and the role is "user".

### US3.2 — Verify my email code to finish signing up
As **P1 Maya**, I want to enter the code emailed to me to activate my account, so that only I can use it.
- Priority: Must · Deps: US3.1 · Traces: FR2.3, FR2.4, FR2.5, NFR2, NFR12
- AC3.2.1 Given a code issued at T, when the correct code is entered at T+9:59, then my account is verified, I receive an access token, and an httpOnly refresh cookie is set.
- AC3.2.2 Given a code issued at T, when it is entered at T+10:00, then it is refused as expired, and the message offers to send a new one.
- AC3.2.3 Given a code already used successfully, when it is entered again, then it is refused.
- AC3.2.4 Given a code issued for sign-up, when it is submitted to the login or password-reset step, then it is refused. **[Recommendation]**
- AC3.2.5 Given the stored code, then only its hash is kept.
- AC3.2.6 Given the code screen, then it shows a partly hidden address (for example "m•••@example.com"). On a phone, the field opens a numeric keypad and accepts pasting and one-time-code autofill. **[Recommendation]**

### US3.3 — Resend a code and lockout after wrong attempts
As **P2 Sam**, I want to request a new code if mine didn't arrive, with protection against guessing, so that I can finish signing in and my account stays safe.
- Priority: Must · Deps: US3.2 · Traces: FR2.4
- AC3.3.1 Given a code sent at T, when I ask to resend at T+59s, then it is refused and the remaining wait (1 s) is shown; at T+60s the resend succeeds. The resend control counts down and becomes available by itself.
- AC3.3.2 Given a successful resend, when the previous code is entered, then it is refused. **[Recommendation]**
- AC3.3.3 Given the 5th wrong code for an account and purpose at time L, then even a correct code is refused until L+15:00. The failure count is per account and purpose, resending does not reset it, and resend is refused during the lockout. **[Recommendation on counter scope]**
- AC3.3.4 Given the lockout ended at L+15:00, when I request and enter a new correct code, then it succeeds and the failure count resets.

### US3.4 — Log in with password and emailed code
As **P1 Maya**, I want to sign in with my email and password and then a code sent to my email, so that my face data is protected by two steps.
- Priority: Must · Deps: US3.2, US1.9 · Traces: FR2.2, FR2.3, FR2.4, NFR2
- AC3.4.1 Given correct email and password, when I submit them, then a code is emailed and no token is issued yet.
- AC3.4.2 Given a wrong password, then login fails with a message that doesn't say whether the email exists.
- AC3.4.3 Given I then enter the correct code, then I'm signed in with an access token held in the auth store and a refresh cookie.

### US3.5 — Stay signed in across reloads and restarts
As **P1 Maya**, I want to stay signed in when I reload the page or reopen my browser within 7 days, so that I don't have to log in every time I check my report.
- Priority: Must · Deps: US3.4 · Traces: FR2.5, FR2.7, FR3.1, FR3.3, FR3.5
- AC3.5.1 Given I'm signed in, when I reload, then a loading indicator shows until the session is restored and the login screen is never shown in between.
- AC3.5.2 Given a refresh cookie issued at T, when I reopen the browser before T+7 days, then I'm signed in. At T+7 days the refresh returns 401, the store is cleared and I land on login.
- AC3.5.3 Given a successful refresh, then the new cookie differs from the old one, the server stores only a token identifier, and no raw refresh-token value exists in the database.
- AC3.5.4 Given the refresh cookie, then it is `HttpOnly` with `Max-Age` equal to the configured 7 days. `Secure`, `SameSite` and `Path` come from configuration. **[Recommendation for the last three]**
- AC3.5.5 Given local and session storage, then no token or user profile is stored there.

### US3.6 — Refresh-token reuse detection and CSRF checks
As **P3 Jordan**, I want a stolen or replayed session token to shut the session down, so that nobody else can use my account.
- Priority: Must · Deps: US3.5 · Traces: FR2.5, FR2.6, FR2.11, NFR2
- AC3.6.1 Given a refresh token that has already been rotated, when it is presented again, then every session in its family is revoked, and the response is 401.
- AC3.6.2 Given a request to `/auth/refresh` or `/auth/logout` without `X-Requested-With`, or from an origin not on the allow-list, then it is refused, and the session stays valid.
- AC3.6.3 Given an access token issued at T, then a protected endpoint accepts it at T+14:59 and returns 401 at T+15:00.
- AC3.6.4 Given my session family was revoked, when I next see the login screen, then it tells me in plain language that I was signed out for security. **[Recommendation]**

### US3.7 — Log out
As **P3 Jordan**, I want to log out with a confirmation step, so that nobody else on this device can see my face data.
- Priority: Must · Deps: US3.5, US11.7 · Traces: FR2.8, FR3.5, FR14.2
- AC3.7.1 Given I click Log out, then the confirmation dialog appears; cancelling keeps me signed in.
- AC3.7.2 Given I confirm, then my refresh session is revoked, the cookie is cleared, the store is cleared, and I land on login.
- AC3.7.3 Given I'm logged out, when the old refresh cookie is replayed, then it is refused.
- AC3.7.4 Given a page unload, visibility change or route change, then no logout call is made and the store is not cleared.

### US3.8 — See who I'm signed in as
As **P1 Maya**, I want the app to greet me by name and show my account in the user menu, so that I know I'm in the right account.
- Priority: Must · Deps: US3.4 · Traces: FR2.9, FR2.10
- AC3.8.1 Given I have just signed in, then my full name appears in the greeting and user menu, loaded from "who am I".
- AC3.8.2 Given each protected route (listed from the router minus an explicit public allow-list), when it is called with no token, an expired token, a tampered signature, an `alg: none` token or a password-reset token, then it returns 401. **[Recommendation on test method]**

### US3.9 — Reset a forgotten password
As **P2 Sam**, I want to reset my password with a code emailed to me, so that I can get back into my paid report.
- Priority: Must · Deps: US3.2 · Traces: FR2.12, FR14.1
- AC3.9.1 Given I enter any email on the reset screen, then I see the same message whether or not the account exists.
- AC3.9.2 Given I enter the correct 6-digit code (same timing, single-use and 5-attempt/15-minute rules as US3.2 and US3.3), then I get a `reset_token` and can set a new password once; reusing that `reset_token` fails.
- AC3.9.3 Given a `reset_token` issued at T, when it is used at T+10:00, then it is refused. The window is a setting, initially 10 minutes (`AUTH-015` "~10 minutes").
- AC3.9.4 Given the reset succeeds, then every refresh cookie issued for my account before the reset returns 401 on every device.
- AC3.9.5 Given the new password, then the US3.1 password rule applies.

### US3.10 — Session renews itself quietly
As **P1 Maya**, I want my session to renew itself while I use the app, so that I'm never interrupted mid-task.
- Priority: Must · Deps: US3.5, US1.9 · Traces: FR3.2, FR3.4, FR3.5
- AC3.10.1 Given an access token whose expiry is T+15:00, with fake timers, then no refresh call has been made at T+13:59, and exactly one has been made by T+14:00. No request reaches the UI as a 401, and no navigation happens.
- AC3.10.2 Given three requests get 401 at once, or a request gets 401 while a proactive refresh is in flight, then exactly one refresh call is made and all waiting requests are retried once.
- AC3.10.3 Given a retried request gets 401 again, then it is not retried a second time; and a 401 from the refresh call itself never triggers another refresh.
- AC3.10.4 Given the shared refresh returns 401, then every waiting request rejects, the store is cleared exactly once, and the app goes to login exactly once.
- AC3.10.5 Given the shared refresh fails with a network error or 5xx, then waiting requests reject with an error toast, and I stay signed in.

### US3.11 — Two tabs don't log each other out
As **P1 Maya**, I want the app open in two tabs to keep working, so that I'm not signed out for using it normally.
- Priority: Must · Deps: US3.6, US3.10 · Traces: FR2.6, FR3.5
- AC3.11.1 Given two tabs share the same refresh cookie and both refresh within the same second, then both end with a valid session and the token family is not revoked. **[Open — mechanism decided in Domain Design, for example cross-tab single-flight or a short grace window]**

---

## Group 4 — Consent & questionnaire

### US4.1 — Consent to facial analysis before starting
As **P3 Jordan**, I want to be asked clearly for consent before my face and health answers are processed, so that I know what happens with my data.
- Priority: Must (delivery-team decision, Q5) · Deps: US3.4 · Traces: FR4.1, NFR3
- AC4.1.1 Given I haven't consented, when I try to open the questionnaire, then I see the consent step and cannot skip it; a direct questionnaire API call without stored consent is refused.
- AC4.1.2 Given I tick consent and continue, then the consent is stored with a timestamp and the consent text version.
- AC4.1.3 Given the consent text is changed in configuration, then new users see the new text and the new version is recorded.

### US4.2 — Answer the questionnaire with branching
As **P1 Maya**, I want to answer the onboarding questionnaire, seeing only the questions that apply to me, so that my report is personalised without wasting my time.
- Priority: Must · Deps: US4.1, US1.5 · Traces: FR4.2, FR4.3, FR4.5, FR4.6
- AC4.2.1 Given a questionnaire definition in seed data, when I start, then its questions are shown in order, with my position shown ("5 of 22"); the count reflects questions skipped by branching.
- AC4.2.2 Given a branching rule, when I choose its triggering answer, then the dependent question appears.
- AC4.2.3 Given a branching rule, when I choose a non-triggering answer, then the dependent question is skipped.
- AC4.2.4 Given a question with a follow-up field revealed by an answer (for example "Yes" → "please list"), then the follow-up appears, and it inherits its parent's medical flag.
- AC4.2.5 Given I go back before submitting, then my earlier answers are kept and editable, and changing a branching answer updates which questions follow. **[Recommendation]**
- AC4.2.6 Given I leave mid-questionnaire and sign in again, then my answers so far are kept. **[Recommendation]**
- AC4.2.7 Given I submit, then each answer is stored with its question id, question text and medical flag.

### US4.3 — Disclaimer before submitting
As **P3 Jordan**, I want to confirm the disclaimer before submitting, and to be treated kindly if I can't, so that it's clear the results are informational and not medical advice.
- Priority: Must · Deps: US4.2 · Traces: FR4.4
- AC4.3.1 Given the disclaimer box is unticked, then Submit is disabled and the reason is shown next to it.
- AC4.3.2 Given I tick it and submit, then the questionnaire is marked submitted and I move to the photo requirements screen.
- AC4.3.3 Given a direct API call to submit without the disclaimer confirmed, then the backend refuses it.
- AC4.3.4 Given I choose not to confirm the disclaimer, then I see a calm, supportive message explaining why the analysis isn't offered, with a pointer to professional help. My answers are kept, and I can't proceed. **[Decided by delivery team — Q13; wording to be confirmed by the client]**

### US4.4 — Load the real 23 questions
**Spec [QS].** As **P1 Maya**, I want the real questions, options, branching and disclaimer wording from the specification, so that my answers match the reference experience.
- Priority: Must · Deps: US4.2, US4.3 · Traces: FR4.2, FR4.4, FR4.6
- AC4.4.1 Given [QS] §2 is loaded as seed data, then all 23 questions appear with their types and options, with no code change.
- AC4.4.2 Given Q4 = Feminine, then Q19 is skipped; given Masculine or No Preference, then Q19 is shown ([QS] §3; exact condition open for client confirmation).
- AC4.4.3 Given Q8 (medical conditions), Q9 (medications, with its follow-up), Q10 (retinoids), Q11 (allergies, with its follow-up) and Q12 (skin conditions), then each carries the medical flag. **[Interpretation of FR-008(f); confirm with the client]**
- AC4.4.4 Given the disclaimer, then its text matches [QS] §4 exactly.
- AC4.4.5 Given the loaded content, then no placeholder text remains. The Q9/Q11 follow-up shape and the Q19 condition stay labelled as open items for the client ([QS] §5).

---

## Group 5 — Photos

### US5.1 — See the photo requirements first
As **P2 Sam**, I want to see the photo rules before I take photos, so that my photos pass the first time.
- Priority: Must · Deps: US4.3 · Traces: FR5.1
- AC5.1.1 Given I reach the photo step, then I see the 7 rules: no glasses or hat; natural, even light; plain white background; hair tied back; no makeup; no neck-covering clothing; no filters. Each rule is shown with its example image ([PC] §2).
- AC5.1.2 Given I continue, then I'm asked for the configured angles in order.

### US5.2 — Upload a photo for each angle
As **P1 Maya**, I want to upload a photo for each required angle, and replace one if I retake it, so that the system analyses my best photos.
- Priority: Must · Deps: US5.1, US1.10, US1.8 · Traces: FR5.2, FR5.3, FR5.4
- AC5.2.1 Given the configured angles are front, left 3/4 and right 3/4, then I'm asked for exactly those three; changing the setting changes the steps with no code change.
- AC5.2.2 Given each angle step, then the instruction says which way to turn in my own terms, with an example image, plus the per-photo guidance from [PC] §3.
- AC5.2.3 Given a JPEG, PNG or HEIC file up to 10 MB, then it is accepted (HEIC is converted on upload); any other type or size is refused with a reason. **[Decided by delivery team — Q14; [PC] also lists DNG, not adopted]**
- AC5.2.4 Given I have a front photo, when I retake it, then the old one is replaced and only one front photo exists for me.
- AC5.2.5 Given I've submitted a photo, then I see a checking state until its result arrives, and the result is announced to screen readers.
- AC5.2.6 Given the photo step, then I see how many angles are done ("2 of 3"), counted from the configured set.
- AC5.2.7 Given user B requests user A's photo by id, then the response is 404.

### US5.3 — Take a photo with my camera
As **P1 Maya**, I want to take each photo with my phone or laptop camera in the browser, so that I don't have to find and upload files.
- Priority: Must · Deps: US5.2 · Traces: FR5.2
- AC5.3.1 Given my device has a camera and I allow access, when I choose camera capture, then I see a guide overlay for the current angle, can take the photo, and can retake or use it from a preview.
- AC5.3.2 Given I deny camera access or have no camera, then file upload is offered and no broken camera view is shown.
- AC5.3.3 Given any angle step, then file upload is always offered next to the camera.
- AC5.3.4 Given a phone in portrait, then the camera view, angle guide and capture control are all visible without scrolling.

### US5.5 — Clear reasons for basic photo checks
As **P2 Sam**, I want to be told exactly why a photo was rejected and how to fix it, so that I can succeed on the next try.
- Priority: Must · Deps: US5.2, US1.11 · Traces: FR6.1, FR6.2, FR6.9
- AC5.5.1 Given a photo with two faces, then it's rejected with "exactly one face" as the reason.
- AC5.5.2 Given photos that each break only one check (readable image, minimum resolution, brightness, face-to-frame proportion), then each is rejected with that check's reason.
- AC5.5.3 Given the thresholds change in configuration, then the new values apply with no code change.
- AC5.5.4 Given any rejection, then the message describes the photo and how to fix it (for example "Move closer so your face fills more of the frame"), never the person's appearance. **[Decided by delivery team — Q11]**

### US5.6 — Same-person decision across my three photos
As **P1 Maya**, I want the system to check that all three photos show me and to point out exactly which one doesn't match, so that my report is based on one person.
- Priority: Must · Deps: US5.5, US1.11 · Traces: FR6.3, FR6.4, FR6.5, FR6.8
- AC5.6.1 Given the pairwise results front↔right, front↔left and right↔left (✓ = within the threshold), then the flagged angles are ([IV] §3, `BR-005` rule 2):

  | F↔R | F↔L | R↔L | Flagged |
  |---|---|---|---|
  | ✓ | ✓ | ✓ | none |
  | ✓ | ✗ | ✗ | left |
  | ✗ | ✓ | ✗ | right |
  | ✗ | ✗ | ✓ | front |
  | ✓ | ✓ | ✗ | exactly one of left or right, never front (hub case) **[tie-break: Open — Functional Design]** |
  | ✓ | ✗ | ✓ | left |
  | ✗ | ✓ | ✓ | right |
  | ✗ | ✗ | ✗ | left and right |
- AC5.6.2 Given a pair distance exactly equal to the threshold (0.6), then it counts as a match; at 0.6 + ε it doesn't. **[Assumption: "within" means ≤]**
- AC5.6.3 Given the [IV] §4 worked examples (Scene 1→2→3; Flip-flop A and B), then each step gives the documented result. For example, A/A/B then retake right as B → front flagged.
- AC5.6.4 Given only two angles have passed, then the check doesn't run and doesn't block uploads.
- AC5.6.5 Given the check, then one shared function computes it from the current three photos every time, with nothing cached; checkout (US6.2) and start-analysis (US7.1) call the same function.

### US5.7 — Sent back to fix inconsistent photos
As **P1 Maya**, I want to be taken back to the photo screen, with the problem shown, whenever my photo set doesn't match, so that I can't get stuck or skip the fix.
- Priority: Must · Deps: US5.11, US11.8 · Traces: FR6.7
- AC5.7.1 Given my set is inconsistent, when I sign in, open the dashboard directly or finish the questionnaire, then I land on the photo screen with the flagged photos shown.
- AC5.7.2 Given my set is complete and consistent on first page load, then the review screen is skipped. That decision is taken only from the first page load ([IV] §6).

### US5.8 — Location data removed from my photos
As **P3 Jordan**, I want location and device data removed from my photos when they're saved, so that my photos don't reveal where I live.
- Priority: Should (delivery-team recommendation, Q5) · Deps: US5.2 · Traces: FR5.5, NFR3
- AC5.8.1 Given I upload a photo with GPS data in its metadata, then the stored copy has no GPS or device metadata (re-encoded on write by US1.10).

### US5.9 — Validation thresholds from the specification
**Spec [PC], [IV] — partly open.** As **P2 Sam**, I want the validation limits tuned to the specifications, so that good photos pass and bad ones don't.
- Priority: Must · Deps: US5.5, US5.10, US5.6 · Traces: FR6.2
- AC5.9.1 Given the identity threshold (0.6, `ASM-010`, [IV] §7), then it is set in configuration and calibrated against real fixtures before handover.
- AC5.9.2 Given the per-photo thresholds (resolution, brightness, proportion, pose angle, occlusion), when the client's Photo Validation Specification supplies values, then they are loaded into configuration with no code change. **[Still open: no working specification gives these numbers; initial values set during development, `ASM-002`]**

### US5.10 — Pose and covered-face checks
As **P2 Sam**, I want to know when a photo is at the wrong angle or my eyes or mouth are covered, so that I can retake it correctly.
- Priority: Must · Deps: US5.5 · Traces: FR6.1, FR6.2
- AC5.10.1 Given a front-facing photo uploaded as left 3/4, then it's rejected for pose mismatch, with the turn direction explained.
- AC5.10.2 Given a photo with glasses or a hat covering the eyes, or a hand over the mouth, then it's rejected for covered features. **[Assumption: first-pass heuristic, tuned under US5.9]**

### US5.11 — Review screen for the same-person check
As **P1 Maya**, I want the review screen to show clearly which photo to retake, without jumping ahead on its own, so that I stay in control.
- Priority: Must · Deps: US5.6, US5.2 · Traces: FR6.6, FR6.5
- AC5.11.1 Given a flagged photo, then it's highlighted with text and an icon (not colour alone). Its message says the photos don't appear to match and suggests retaking in the same light and position, never accusing the user.
- AC5.11.2 Given any photo is flagged, then Continue is disabled and the reason is shown next to it.
- AC5.11.3 Given I retake a flagged photo and the fresh result is still pending, then Continue stays disabled and no automatic navigation happens (pending is not consistent, [IV] §6).
- AC5.11.4 Given the fresh result is consistent, then Continue becomes enabled, and I stay on the screen until I click it.
- AC5.11.5 Given a phone-width screen, then all three photos, their flags and Continue are reachable without any photo being cut off.

---

## Group 6 — Payment

### US6.1 — Payment screen once my photos are ready
As **P2 Sam**, I want to reach a payment screen as soon as my three photos are accepted, with a clear promise of what I get, so that I know exactly what I'm paying for.
- Priority: Must · Deps: US5.6, US1.5 · Traces: FR7.1, FR7.3
- AC6.1.1 Given a consistent set and no payment, when I continue, then I see the payment screen with the configured price and currency, and none of my results or any partial content.
- AC6.1.2 Given the payment screen, then it lists what payment unlocks (the 11-feature report with PDF, AI visuals, the Beauty Assistant) and says analysis starts only when I click "Start Analysis". **[Recommendation: copy]**
- AC6.1.3 Given the price is changed in configuration, then the screen and the next checkout session (as recorded by the Stripe fake) both use the new amount.

### US6.2 — Pay with Stripe Checkout
As **P1 Maya**, I want to pay once through Stripe's secure checkout, so that I can unlock my analysis.
- Priority: Must · Deps: US6.1, US1.12 · Traces: FR7.2, FR7.3, FR6.8
- AC6.2.1 Given I click Pay, then I'm sent to Stripe hosted Checkout for a one-time payment at the configured price, through the Stripe adapter.
- AC6.2.2 Given my photo set became inconsistent, when checkout is requested, then the server returns 409, and the mismatched angles in the body equal the US5.6 function's result for the same photos.
- AC6.2.3 Given I cancel on Stripe's page, then I return to the payment screen with nothing charged. **[Recommendation]**

### US6.3 — Payment confirmed by Stripe
As **P1 Maya**, I want my payment recorded as soon as Stripe confirms it, so that I can start my analysis.
- Priority: Must · Deps: US6.2 · Traces: FR7.4, FR7.5
- AC6.3.1 Given Stripe sends a valid success webhook, then my payment is marked succeeded, and analysis does not start by itself.
- AC6.3.2 Given the same event id arrives twice, including concurrently, then exactly one payment record exists, enforced by a database constraint.
- AC6.3.3 Given a webhook whose signature fails verification against the raw request body, then it's rejected and nothing changes.

### US6.4 — No analysis or report without payment
As the **Project Sponsor**, I want analysis and reports locked until payment succeeds, so that no analysis cost is incurred and no report is given away without payment.
- Priority: Must · Deps: US6.3 · Traces: FR7.6, FR6.9
- AC6.4.1 Given no successful payment, when start-analysis or the report endpoint is called directly, then the response is 402.
- AC6.4.2 Given no payment and an inconsistent set, then the response is 402 (payment is checked first). **[Recommendation]**
- AC6.4.3 Given a photo set that failed validation, when start-analysis is called, then analysis does not run.

### US6.5 — Confirming my payment
As **P2 Sam**, I want to see that my payment is being confirmed when I come back from Stripe, so that I'm not worried I paid for nothing.
- Priority: Must · Deps: US6.3 · Traces: FR7.1, FR7.4
- AC6.5.1 Given I return to the success page before the webhook arrives, then I see "confirming your payment", the payment is not yet marked succeeded, and "Start Analysis" is unavailable.
- AC6.5.2 Given the confirmation arrives while I'm on that screen, then it updates without a reload, "Start Analysis" becomes available, and the change is announced to screen readers. **[Recommendation]**
- AC6.5.3 Given confirmation hasn't arrived after a configured wait, then I see that my payment is still being confirmed, that I won't be charged twice, and that I can safely leave and come back. **[Recommendation]**

---

## Group 7 — Analysis

### US7.1 — Start my analysis
As **P1 Maya**, I want to start the analysis myself with a "Start Analysis" button, so that I choose when it runs and can watch it happen.
- Priority: Must · Deps: US6.4, US1.7, US5.6 · Traces: FR8.1
- AC7.1.1 Given I've paid and my set is consistent, when I click "Start Analysis", then a background job starts and I see the progress screen.
- AC7.1.2 Given my set became inconsistent after paying, when I click it, then I get the 409 message and am sent to the photo screen.
- AC7.1.3 Given two start requests arrive at the same time, then exactly one job exists and both requests return its id.
- AC7.1.4 Given a completed run, when start is called again, then no new job starts and no vendor call is made (one analysis per paid report, NFR10).

### US7.2 — Watch progress and come back later
As **P2 Sam**, I want to see which step the analysis is on, know I can leave, and be taken to my results when they're ready, so that I'm not stuck staring at a spinner.
- Priority: Must · Deps: US7.1, US7.6 · Traces: FR8.2, NFR4
- AC7.2.1 Given analysis is running, then each step (measuring, writing, generating images, assembling) shows its state in text (done, current, waiting). Step changes are announced to screen readers without moving focus.
- AC7.2.2 Given analysis is running, then the screen says I can close the page and come back, and gives the expected wait (configured, within NFR4's 10 minutes).
- AC7.2.3 Given I close the tab and sign in later, then I see the same run's progress, or my results.
- AC7.2.4 Given I'm on the progress screen when the report is ready, then I'm shown a "View my report" action that leads to Home Overview, and the change is announced. **[Recommendation]**
- AC7.2.5 Given the committed "realistic latency" fake profile, then all narratives are written and all 24 images are generated or marked failed within 10 minutes of starting.
- AC7.2.6 Given the real vendors, before handover, then one timed end-to-end run meets the same 10-minute target. *(eval)*

### US7.3 — Measurements from my front photo
As **P1 Maya**, I want my features measured from my own photo, so that the report is objective and specific to me.
- Priority: Must · Deps: US7.1, US1.11 · Traces: FR8.3
- AC7.3.1 Given a completed run, then Eyebrows, Eyes, Nose, Cheeks, Jaw, Lips and Chin each have geometric measurements taken from the front photo's landmark mesh. **[Interpretation of `FR-007`'s "seven": the seven front-mesh features, with Ears measured separately (US7.7); confirm with the client]**
- AC7.3.2 Given the same photo analysed twice, then the values are identical.

### US7.4 — Safe, personal AI requests
As **P3 Jordan**, I want the AI to get the context it needs about my goals and feelings but never my medical answers, so that my report is personal, careful and private.
- Priority: Must · Deps: US7.3, US4.2 · Traces: FR8.4, FR8.5, FR8.6, NFR3
- AC7.4.1 Given fixture answers seeded with canary strings, then the captured request contains the question text with each included answer. It contains neither the question text nor the answer of any medical-flagged question or follow-up.
- AC7.4.2 Given the captured request, then it contains the photos, the measurements, and my goal, motivation, liked-feature and disliked-feature answers.
- AC7.4.3 Given answers to the distress and appearance-frequency questions ([QS] Q20, Q21) at or above a configured level, then the request includes the reassuring-tone instruction. **[Trigger levels: Open — Functional Design]**

### US7.5 — Symmetry and facial thirds
As **P1 Maya**, I want my symmetry and facial proportions calculated, so that I get an objective picture of balance.
- Priority: Must · Deps: US7.3 · Traces: FR9.5
- AC7.5.1 Given a completed run, then a symmetry score from 0 to 100, its label, a Regional Balance breakdown and facial-thirds proportions are stored.
- AC7.5.2 Given the configured label bands, then a score on each band boundary gets the documented label. **[Band values: Open — Functional Design]**
- AC7.5.3 Given the same photos analysed twice, then the results are identical.

### US7.6 — Analysis pipeline that resumes safely
**Enabler.** As **P4 Dev**, I want the analysis steps chained so that each saves its output and a restart resumes instead of repeating, so that no paid call is wasted and one payment gives one analysis.
- Priority: Must · Deps: US1.7, US7.1 · Traces: FR8.2, FR10.4, NFR5, NFR10
- AC7.6.1 Given a run, then its status moves through the named steps shown in US7.2.
- AC7.6.2 Given a step already completed, when the job resumes after a restart, then that step isn't repeated and no second vendor call is made for it.
- AC7.6.3 Given a payment, then at most one analysis run exists for it, apart from the one free re-run in US7.11.
- AC7.6.4 Given image generation, then images are generated with a configurable concurrency limit, and rate-limit responses back off and count toward the retry cap.
- AC7.6.5 Given narratives are done but some images failed, then the report is still assembled and published (FR10.5), with 24 image slots in total.

### US7.7 — Ear measurements
As **P1 Maya**, I want my ears measured from the side photos, so that the Ears section is based on a real view of each ear.
- Priority: Must · Deps: US7.3 · Traces: FR8.3
- AC7.7.1 Given a completed run, then each ear is measured from its own side's 3/4 photo.
- AC7.7.2 Given a side photo record is missing at measurement time, then that ear is measured from the front photo.

### US7.8 — Hair, Skin and Neck assessments
As **P1 Maya**, I want Hair, Skin and Neck assessed honestly, so that I'm never shown made-up numbers.
- Priority: Must · Deps: US7.3 · Traces: FR8.3
- AC7.8.1 Given Hair, Skin and Neck, then each uses its documented heuristic or an explicit "no measurement" marker, never an invented number. **[Heuristics defined in Functional Design, drawing on [RT] §10]**

### US7.9 — Write my report text
As **P1 Maya**, I want every feature explained, with ideas for its potential, a short summary and tiered recommendations, so that I understand my results and what I could do.
- Priority: Must · Deps: US7.4, US1.12 · Traces: FR8.4, FR8.7, FR9.2, FR9.4
- AC7.9.1 Given a completed run, then the stored text passes validation for all 11 features: a narrative of 3–5 sentences, projected-potential ideas, a summary callout, and recommendations each labelled with one of the three tiers. Each measured feature's narrative contains at least one of its stored values at the configured precision.
- AC7.9.2 Given the text fake returns output that fails validation or is malformed, then the step is retried up to a configured count; after that, the run fails with a reason and nothing half-valid is published.
- AC7.9.3 Given the run completes, then one analysis result is stored for me.
- AC7.9.4 Given the real model and fixed test inputs, then the narratives are 3–5 sentences, cite measurements, and follow [RT] §8 and §13–§15 (no raw field names, no medical claims). *(eval)*

### US7.10 — Dimorphism, prototypicality and face shape
As **P1 Maya**, I want my masculine/feminine balance, how typical my features are, and my face shape assessed, so that I get the full set of Facial Assessments.
- Priority: Must · Deps: US7.3 · Traces: FR9.5
- AC7.10.1 Given a completed run, then dimorphism values, a prototypicality score and a face-shape classification are stored. **[Assumption: formulas and reference data defined in Functional Design; first-pass heuristics, client-confirmed as subject to calibration]**
- AC7.10.2 Given the same photos analysed twice, then the results are identical.

### US7.11 — A failed paid run can be re-run once
As **P2 Sam**, I want a clear explanation and a free re-run if my paid analysis fails, so that I never pay for nothing.
- Priority: Must (delivery-team decision, Q8) · Deps: US7.6, US7.2 · Traces: FR8.2, NFR5, NFR10
- AC7.11.1 Given a run fails after its automatic retries, then the progress screen explains in plain language that something went wrong on our side (never a raw error), and confirms my payment still covers this report.
- AC7.11.2 Given that first failure, then I can re-run once for free from the progress screen, and completed steps are not repeated.
- AC7.11.3 Given the free re-run also fails, then I see a "contact support" message, and no further re-run is offered.

---

## Group 8 — Report

### US8.1 — Report data I own
As **P1 Maya**, I want my report delivered to me alone, and only after payment, so that my results stay private.
- Priority: Must · Deps: US7.9, US6.4 · Traces: FR9.1, FR9.3, FR9.8
- AC8.1.1 Given my report, then it contains exactly Hair, Eyebrows, Eyes, Nose, Cheeks, Jaw, Lips, Chin, Skin, Neck and Ears, in that order, with no Smile section.
- AC8.1.2 Given analysis finishes, then the report is available immediately with no approval step.
- AC8.1.3 Given user B requests user A's report, then the response is 404; given no payment, then it's 402.
- AC8.1.4 Given each image slot, then its state is included (ready, pending, or not available yet).

### US8.2 — Recommendations in three tiers
As **P1 Maya**, I want recommendations grouped into at-home, over-the-counter and in-clinic, so that I can pick what fits my comfort and budget.
- Priority: Must · Deps: US7.9 · Traces: FR9.4
- AC8.2.1 Given the recommendations, then each appears in exactly one of the three tiers.
- AC8.2.2 Given a recommendation with a missing or invalid tier label from the AI, then the configured keyword rules assign one.
- AC8.2.3 Given the recommendations section, then it shows the static "consult a qualified professional" copy exactly as configured, and each tier caption follows [RT] §9.3.

### US8.3 — Explore my assessments and jump around my report
As **P1 Maya**, I want to explore my facial assessments and jump straight to any part of my report, so that I can find what matters to me.
- Priority: Must · Deps: US7.5, US8.7 · Traces: FR9.5
- AC8.3.1 Given the interactive report, then a table of contents links to each assessment and feature. Choosing an entry by mouse, touch or keyboard moves to that section, and focus moves to its heading.
- AC8.3.2 Given the symmetry view, then it shows the score out of 100, its label and the Regional Balance breakdown. Given the facial-thirds view, then it shows the three proportions.
- AC8.3.3 Given any chart, then its values are also available as text or a table.

### US8.4 — Per-feature metric tables
As **P1 Maya**, I want a table of measurements for each feature, so that I can see the numbers behind the narrative.
- Priority: Must · Deps: US7.3, US7.7, US8.3 · Traces: FR9.5
- AC8.4.1 Given each measured feature, then its table lists the stored measurements with units.
- AC8.4.2 Given Hair, Skin or Neck without a geometric measurement, then its table says so instead of showing empty numbers.
- AC8.4.3 Given a phone-width screen, then each table scrolls within its own area, and the page doesn't scroll sideways.

### US8.5 — Download my report as a PDF
As **P1 Maya**, I want to download my report as a branded PDF, so that I can keep it and read it offline.
- Priority: Must · Deps: US8.7 · Traces: FR9.7
- AC8.5.1 Given I click Download PDF for the first time, then a PDF of the full report, following the [RD] §5–§10 page order, is generated and downloaded.
- AC8.5.2 Given I download again, then the cached PDF is returned without regenerating.
- AC8.5.3 Given an image in my report changed after the PDF was cached (for example after a retry), then the next download regenerates the PDF. **[Recommendation]**

### US8.6 — Face Shape and Skin views
**Spec [RD], [RT].** As **P1 Maya**, I want the Face Shape and Skin views to show the content the specification describes, so that they match the reference product.
- Priority: Must · Deps: US8.8, US7.8 · Traces: FR9.6
- AC8.6.1 Given [RD] §9.2 and [RT] §10 for the Skin and face-shape content, then those views show it. Items marked 🔴 TBD in [RD] §20 or [RT] §19 stay open for the client and are not invented.

### US8.7 — Read my 11-feature report
As **P1 Maya**, I want a report page covering all 11 features with narrative, before/after and a summary, introduced gently, so that I understand my face feature by feature.
- Priority: Must · Deps: US8.1 · Traces: FR9.2, FR9.3
- AC8.7.1 Given each feature, then it shows the narrative, my photo next to its AI "after" image, the projected-potential ideas and a summary callout ([RT] §9).
- AC8.7.2 Given the report, then the "Understanding Your Results" preamble appears before the first score or feature, in the web view and the PDF. **[Decided by delivery team — Q11]**
- AC8.7.3 Given the introduction, preamble and limitations, then their text matches the configured template exactly ([RT] §4–§6).
- AC8.7.4 Given any AI-generated image, then it carries a visible text label saying it's an AI-generated illustration, and each image has alt text naming it (for example "AI-generated illustration — Nose"). **[Decided by delivery team — Q11]**
- AC8.7.5 Given an image slot that isn't ready, then it shows "not available yet" and the text still renders; the report doesn't wait on images.

### US8.8 — Dimorphism, prototypicality and face-shape views
As **P1 Maya**, I want to see my masculine/feminine balance, prototypicality and face shape, so that I get the complete Facial Assessments.
- Priority: Must · Deps: US7.10, US8.3 · Traces: FR9.5
- AC8.8.1 Given the dimorphism view, then display-only sliders (not inputs) show each value, with an overall summary, and the value and meaning are also available as text. **[Recommendation: display-only reading of "sliders"]**
- AC8.8.2 Given the prototypicality and face-shape views, then they show the stored score and a face-shape wireframe, with text alternatives.

---

## Group 9 — AI images & visuals

### US9.1 — Before/after image for each feature
As **P1 Maya**, I want an AI "after" image for each of the 11 features that still looks like me, so that I can picture the potential of each change.
- Priority: Must · Deps: US7.6, US1.12, US1.10 · Traces: FR10.1, FR10.2, FR10.4
- AC9.1.1 Given a completed run, then 11 per-feature images are stored and linked to my report, one per feature.
- AC9.1.2 Given each request, then the fake records an image-edit call using my own photo and the configured high-fidelity setting.
- AC9.1.3 Given user B requests user A's image, then the response is 404.
- AC9.1.4 Given the real vendor and fixture photos, then each image still resembles the person (manual check before handover, `ASM-011`). *(eval)*

### US9.2 — Hairstyle variations
As **P2 Sam**, I want to see myself with 5 different hairstyles, so that I can explore looks before changing anything.
- Priority: Must · Deps: US9.1 · Traces: FR10.3, FR10.4
- AC9.2.1 Given a completed run, then the AI Visuals screen shows 5 hairstyle images of me, each labelled as an AI-generated illustration.

### US9.3 — Outfit variations
As **P2 Sam**, I want to see myself in 5 different outfits, so that I can see what suits me.
- Priority: Must · Deps: US9.1 · Traces: FR10.3, FR10.4
- AC9.3.1 Given a completed run, then the AI Visuals screen shows 5 outfit images of me, each labelled as an AI-generated illustration.

### US9.4 — Healthy-aging preview
As **P1 Maya**, I want a four-card aging preview (now, +3, +5, +10 years), so that I can see how healthy habits might play out.
- Priority: Must · Deps: US9.1 · Traces: FR10.3, FR10.4
- AC9.4.1 Given a completed run, then the stack shows 4 cards in order: my own front photo (not generated), then generated +3, +5 and +10 years, with the generated cards labelled as AI illustrations.
- AC9.4.2 Given a completed run, then 13 AI Visual images exist (5 + 5 + 3).

### US9.5 — Retry an image that failed
As **P2 Sam**, I want my report on time even if an image fails, with a way to retry it, so that one glitch doesn't hold everything up.
- Priority: Must · Deps: US9.1 · Traces: FR10.5, NFR5, NFR10
- AC9.5.1 Given the image fake fails 3 times, then succeeds, then the image is stored after exactly 4 calls.
- AC9.5.2 Given the image fake fails 4 times, then the slot shows "not available yet" with a retry button after exactly 4 calls, and the report is published.
- AC9.5.3 Given I click retry and generation succeeds, then the slot shows the new image. If it fails, I see an error toast and the slot stays marked.
- AC9.5.4 Given I've used 3 manual retries for a slot, then its retry button is disabled and no image call is made. **[Decided by delivery team — Q10]**
- AC9.5.5 Given images are still being generated, then the narratives are already visible.

---

## Group 10 — AI Beauty Assistant

### US10.1 — Ask questions about my report
As **P1 Maya**, I want to chat with an assistant that knows my report, so that I can understand my results in my own words.
- Priority: Must · Deps: US8.1, US1.12 · Traces: FR12.1, FR12.3
- AC10.1.1 Given I ask about my symmetry score, then the grounding context sent to the fake contains my stored symmetry score. It contains no medical, medication or allergy answer.
- AC10.1.2 Given I return later, then my earlier conversation is shown; user B requesting my conversation gets 404.
- AC10.1.3 Given I send a message, then I see that a reply is on its way, and the reply is announced to screen readers without moving focus.
- AC10.1.4 Given the assistant request fails, then my message is kept (not lost), and I see an error toast.
- AC10.1.5 Given I open chat for the first time, then an empty state explains what I can ask about.
- AC10.1.6 Given a phone with the keyboard open, then the input and the latest reply stay visible.
- AC10.1.7 Given the real model and a fixed question about my report, then the answer uses my report's value. *(eval)*

### US10.2 — Medical questions are declined
As **P3 Jordan**, I want the assistant to decline medical and medication questions and point me to a professional, so that I don't mistake it for medical advice.
- Priority: Must · Deps: US10.1 · Traces: FR12.2
- AC10.2.1 Given any chat request, then the system instructions sent to the fake include the medical-decline instruction.
- AC10.2.2 Given a fixed set of medical and medication questions run against the real model, then every answer declines and suggests a qualified professional. *(eval)*

### US10.3 — Daily chat limit
As the **Project Sponsor**, I want each user limited to a daily number of chat messages, with a clear message when they reach it, so that chat costs stay bounded without confusing users.
- Priority: Should (delivery-team decision, Q5) · Deps: US10.1 · Traces: FR12.4, NFR10
- AC10.3.1 Given I've had the configured daily maximum (initially 50) of successful messages this UTC day, when I send another, then it's refused with the time I can chat again (next 00:00 UTC), and no AI call is made. **[Decided by delivery team — Q10]**
- AC10.3.2 Given a message whose AI call failed, then it doesn't count toward the limit.
- AC10.3.3 Given I've sent 49 and send 2 at the same time, then exactly one is accepted.
- AC10.3.4 Given the limit is changed in configuration, then the new limit applies with no code change.

---

## Group 11 — Home, settings & app-wide

### US11.1 — Home Overview
As **P1 Maya**, I want a home screen summarising my results, so that I see my priorities at a glance whenever I return.
- Priority: Must · Deps: US8.1, US7.5 · Traces: FR11.1, FR11.3
- AC11.1.1 Given my report exists, when I sign in, then I land on Home Overview.
- AC11.1.2 Given Home, then I see:
  - key stats;
  - my before/potential image;
  - "Priority Features to Improve" **[selection rule: Open — Functional Design, [RD] §13.1]**;
  - a protocol summary;
  - a six-axis radar chart that includes Symmetry ([RD] §4, §12.1).
- AC11.1.3 Given Home, then report status and PDF download are reachable from it.
- AC11.1.4 Given the radar chart, then its values are also available as text.

### US11.2 — Move around easily
As **P1 Maya**, I want to move between my results, visuals and chat from any screen, so that I never get lost.
- Priority: Must · Deps: US11.1 · Traces: FR11.2
- AC11.2.1 Given any post-analysis screen, then the header shows Home, Report, AI Visuals and Chat, with Settings in the user menu.
- AC11.2.2 Given a phone-width screen, then each of those is reachable from the header within one extra tap.

### US11.3 — Protocol section
**Spec [RD], [RT].** As **P1 Maya**, I want the Protocol section on Home to show my treatment protocol as the specification describes, so that I know what to do next.
- Priority: Must · Deps: US11.1, US8.2 · Traces: FR11.4
- AC11.3.1 Given [RD] §14 and [RT] §3.7, then the Treatment Protocol card shows the specified content from my recommendations. Items marked 🔴 TBD stay open for the client.

### US11.4 — Account info
As **P1 Maya**, I want to see my name, email, verification status and member-since date, so that I know my account details.
- Priority: Must · Deps: US3.8 · Traces: FR13.1
- AC11.4.1 Given Settings → Account Info, then name, email, verification status and member-since date are shown.
- AC11.4.2 Given Account Info, then full name has no edit control.

### US11.5 — Change my password
As **P3 Jordan**, I want to change my password while signed in without being logged out, so that I can secure my account easily.
- Priority: Must · Deps: US3.5 · Traces: FR13.2, FR2.13
- AC11.5.1 Given the correct current password and matching new and confirm fields that meet the US3.1 rule, then the password changes, and I stay signed in.
- AC11.5.2 Given new and confirm don't match, then an inline field error blocks submission before any request.
- AC11.5.3 Given a wrong current password, then the change is refused with an inline error on that field and a toast.

### US11.6 — Billing
As **P1 Maya**, I want to see my payment history and payment options, so that I can check what I paid.
- Priority: Must · Deps: US6.3 · Traces: FR13.3
- AC11.6.1 Given Settings → Billing, then my payments are listed with date, amount, currency and status.
- AC11.6.2 Given Billing, then Stripe is shown as available, and PayPal is visible but disabled with a "not available" label that screen readers announce. Activating PayPal does nothing.

### US11.7 — Feedback, confirmations and form errors everywhere
As **P2 Sam**, I want every action to tell me whether it worked, every irreversible action to ask first, and form mistakes shown where I made them, so that I'm never left guessing.
- Priority: Must · Deps: US1.1 · Traces: FR14.1, FR14.2, NFR9
- AC11.7.1 Given any action with a success or failure outcome, then a toast appears top-right, except the forgot-password request, which never reveals the outcome.
- AC11.7.2 Given a toast, then screen readers announce it and it doesn't take focus. An error toast stays until dismissed.
- AC11.7.3 Given any destructive or irreversible action, then the shared dialog appears first. Focus moves into it and stays there, Escape cancels, focus returns to the opener on close, and the confirm button names the action.
- AC11.7.4 Given an invalid form input, then the error appears as text next to the field and is linked to it. A toast may add to it but never replaces it.
- AC11.7.5 Given a phone-width screen, then a toast doesn't cover the header navigation or the action it reports on.

### US11.8 — Pick up where I left off
As **P2 Sam**, I want to land on the next step I haven't finished whenever I sign in or come back, so that I never lose progress or have to find my own way.
- Priority: Must · Deps: US3.5 · Traces: FR1.1, FR6.7, FR8.2, FR11.1
- AC11.8.1 Given my progress, then the backend returns exactly one next step, following this table, and the frontend route guard uses it:

  | State | Next step |
  |---|---|
  | No consent | Consent |
  | Consent, questionnaire not submitted | Questionnaire |
  | Photos incomplete or inconsistent | Photos |
  | Consistent photos, no successful payment | Payment |
  | Payment returned but not confirmed | Confirming payment |
  | Paid, not started | Start Analysis |
  | Running | Progress |
  | Report exists | Home |
- AC11.8.2 Given I open a later step's URL before finishing an earlier one, then I'm sent to my next unfinished step.

---

## Coverage summary

| Requirement | Stories |
|---|---|
| FR1 | US2.1, US2.2, US11.8 |
| FR2 | US3.1–US3.9, US3.11, US11.5 |
| FR3 | US1.9, US3.5, US3.7, US3.10, US3.11 |
| FR4 | US4.1–US4.4 |
| FR5 | US5.1–US5.3, US5.8 |
| FR6 | US5.5–US5.7, US5.9–US5.11, US6.2, US6.4 |
| FR7 | US6.1–US6.5 |
| FR8 | US7.1–US7.4, US7.6–US7.9, US7.11 |
| FR9 | US7.5, US7.10, US8.1–US8.8 |
| FR10 | US9.1–US9.5, US7.6 |
| FR11 | US11.1–US11.3, US11.8 |
| FR12 | US10.1–US10.3 |
| FR13 | US11.4–US11.6 |
| FR14 | US11.7, US3.7, US3.9 |
| NFR1–NFR12 | See `traceability.json` |

**Totals:** 80 stories. 13 are enablers (plus the US7.6 pipeline enabler), and 5 take their content from working specifications (US4.4, US5.9, US8.6, US11.3, and the [IV] rules in US5.6). By priority: 78 Must, 2 Should (US5.8, US10.3).

**Open for later stages or the client:**
- Hub-case tie-break (AC5.6.1).
- Threshold inclusivity (AC5.6.2).
- Symmetry label bands (AC7.5.2).
- Distress trigger levels (AC7.4.3).
- Dimorphism and prototypicality formulas (US7.10).
- Priority-feature rule (AC11.1.2).
- Two-tab refresh mechanism (US3.11).
- Per-photo thresholds (US5.9).
- Medical-flag list, Q9/Q11 follow-up shape and Q19 condition ([QS] §5).
- Client confirmation of the working specifications (Q7), the consent step (Q2), the disclaimer message (Q13), and the reading of "seven measured features" (AC7.3.1).
