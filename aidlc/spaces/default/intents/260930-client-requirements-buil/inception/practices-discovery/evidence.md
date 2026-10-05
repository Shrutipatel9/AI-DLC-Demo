# Practices Discovery — Evidence

> Final evidence after lead integration (Step 5). It records what each participant
> inspected or inferred, the interview decisions, how the support objections were
> resolved, and what remains uncertain.

## Project context

- **Project type**: Greenfield (`aidlc-state.md` → `Project Type: Greenfield`).
- **Scope**: `classic`: Standard depth, Standard test strategy, `skeleton: off`.
  The CI Pipeline stage (3.7) and all Operation stages (4.1–4.7) are skipped.
- **Re-run baseline**: none. `aidlc/spaces/default/memory/team.md` and
  `project.md` had empty practice sections only.
- **Source of truth**: `client_requirements.md` (v1.0, 2026-09-29).

## What each participant inspected or inferred

### Lead — aidlc-pipeline-deploy-agent

| Source | What was found | Used for |
|---|---|---|
| `aidlc/spaces/default/memory/org.md`, the five practice sections | Trunk-based development with squash-merge to `main`; skeleton chosen by scope; test-after with an 80% line floor and CI before merge for `classic`; deploy on merge to staging with a manual production gate; defer to project linter/formatter config | Suggested defaults for all five sections |
| `aidlc/spaces/default/memory/team.md`, `project.md` | All practice sections empty | No re-run baseline |
| `.claude/scopes/aidlc-classic.md` | `skeleton: off`; CI Pipeline and Operation stages skipped | Walking Skeleton default; CI and Deployment tensions |
| `client_requirements.md` | Mandated stack `NFR-001`–`NFR-013`; auth layering Section 5.3; `AUTH-*` and `FE-*` constraints; hosting undecided `NFR-010` / `CON-007`; maintainability `NFR-011` / `BC-005`; out-of-scope list Section 2.2; UI conventions `BR-009` / `BR-010`; Section 12 Testing row | Hard constraints in `discovered-rules.md`; Deployment stance |
| Git repository at `D:\AIDLC-Demo` | Remote `origin` = `https://github.com/Shrutipatel9/AI-DLC-Demo.git`; unborn **`master`** branch; **no commits** (re-checked at integration) | Trunk rename; `commit none` in the timestamp |
| CI configuration | None (`.github/` absent) | CI-before-merge decision |
| `.gitignore` (re-checked at integration) | Only the AI-DLC block plus Node/editor entries; no `.env`, `.env.*`, `*.pem`, `*.key`, Python cache/venv, `.next/` or upload-folder entries | Confirms the devsecops finding; `.gitignore` fix before the first commit |
| `.claude/tools/aidlc-state.ts` (`practices-promote`) | Every non-blank line in `## Mandated` / `## Forbidden` is appended to `project.md` as a rule | Rules kept to one line each; candidates kept in a separate, non-promoted section |

### Quality — aidlc-quality-agent (`contributions/aidlc-quality-agent.md`)

- Laid out four methodology options (test-after, custom test-first for risky
  modules, TDD, ATDD) with explicit `Methodology`/`Ordering` fields, and named the
  modules that benefit from test-first: JWT/OTP services, the frontend refresh and
  single-flight logic, and the `BR-005` identity decision.
- Proposed precise coverage wording (whole application, enforced by
  `--cov-fail-under` and Vitest thresholds, exclusions declared in config).
- Found that the traceability rule cannot be satisfied literally for `BR-006` /
  `BR-007`, and is blocked for `FR-003` / `FR-004` until the questionnaire
  specification exists; recommended including `FE-*`.
- Argued that a local-only pre-merge run does not meet the `org.md` CI-before-merge
  floor; recommended a minimal GitHub Actions workflow in the first Bolt.
- Described fake-based test patterns for OpenAI, Stripe, email OTP, MediaPipe /
  OpenCV and PDF export, and a minimum security test set for the auth flows.
- Surfaced the multi-tab refresh race against `AUTH-012` reuse detection.

### Developer — aidlc-developer-agent (`contributions/aidlc-developer-agent.md`)

- Agreed with one repository holding separate `backend/` and `frontend/` apps.
- Proposed a feature-folder backend layout with fixed layers, lint-enforced import
  boundaries in both apps, a single API client, and one typed settings object.
- Proposed an API error envelope, a status-code table, naming conventions, a single
  formatter (Ruff format), mypy as a required gate, and OpenAPI-generated frontend
  types.
- Asked for design choices: sync vs async SQLAlchemy, JSON casing, `/api/v1`
  prefix, the Next.js rendering model under in-memory tokens, signup enumeration
  behaviour, and toolchain pins.
- Flagged that the analysis pipeline is long-running and must not run inside an
  HTTP request.

### Security — aidlc-devsecops-agent (`contributions/aidlc-devsecops-agent.md`)

- Classified face photos, the derived identity signature and medical questionnaire
  answers as restricted (possible biometric and health data), and noted that the
  user jurisdiction is not stated anywhere.
- Found the `.gitignore` gap and proposed the entries to add before the first
  commit.
- Proposed Ruff `S` + ESLint security plugins, Gitleaks pre-commit, `pip-audit` /
  `npm audit`, Dependabot, and Semgrep or CodeQL as a SAST layer.
- Proposed candidate rules for logging redaction, Stripe webhook signature
  verification, object-level ownership checks, upload hardening and fixture-photo
  sourcing.
- Surfaced the `FR-008` vs `FR-008`(f) question: whether medical, medication and
  allergy answers should be sent to OpenAI at all.

## Interview decisions

Answers are from `practices-discovery-questions.md` and are authoritative.

| # | Area | Answer | Recorded as |
|---|---|---|---|
| Q1 | Branching and merging | **A**: rename to `main`; short-lived branches squash-merged into `main` through a GitHub pull request | Way of Working; Mandated rule |
| Q2 | Repository layout | **A**: one repository, `backend/` + `frontend/`, each with its own dependencies, config, tests and README | Way of Working |
| Q3 | Thin end-to-end slice first | **A**: yes; build and verify sign-up → emailed OTP → login → `/auth/me` across Next.js, FastAPI and PostgreSQL first | Walking Skeleton (on, overriding the scope default) |
| Q4 | When tests are written | **B**: mixed; test-after in general, test-first for JWT/OTP services, frontend token refresh / single-flight, and the `BR-005` same-person check | `Methodology: custom` plus an explicit `Ordering` |
| Q5 | Test types and tools | **B**: pytest + pytest-cov on real PostgreSQL; Vitest + React Testing Library; a small Playwright E2E set; paid services faked; every `FR`/`AUTH`/`BR`/`FE` requirement maps to a test; ≥80% line coverage per app | Testing Posture; Mandated and Forbidden rules |
| Q6 | Where checks run before merge | **A**: a small GitHub Actions workflow (lint, type check, tests, coverage) in the first piece of work; `main` protected | Testing Posture; Mandated rule |
| Q7 | Deployment and local setup | **A**: no deployment now; Docker Compose for local PostgreSQL; `.env.example` files; all environment-specific values from configuration | Deployment; Mandated and Forbidden rules |
| Q8 | Linting, formatting, type checking | **A**: Ruff lint + format and mypy (required); ESLint + Prettier with TS strict; import rules enforce Section 5.3 layering; docstrings on services; README per app | Code Style; Mandated rule |
| Q9 | Security checks | **A**: fix `.gitignore` before the first commit; Gitleaks pre-commit; Ruff `S` + ESLint security plugins; `pip-audit` / `npm audit`; Dependabot | Code Style; Forbidden rule on committing secrets |

## Support objections and how they were resolved

| Raised by | Objection | Resolution |
|---|---|---|
| Quality | A local-only run is not equivalent to CI before merge | Resolved by Q6: GitHub Actions in the first piece of work, `main` protected |
| Quality | "80% … measured per Bolt" is ambiguous; no exclusion policy | Resolved: whole-application floor per app at every merge, tool-enforced, exclusions declared in config and never added to pass |
| Quality | Traceability rule is unsatisfiable for `BR-006`/`BR-007` and blocked for `FR-003`/`FR-004` | **Carried forward, not resolved**: the interview did not ask about `N/A` / `Deferred` statuses (see Unresolved) |
| Quality | Playwright was implied as a default | Resolved by Q5: E2E is an explicit, additive choice |
| Quality | Add candidates for clock/randomness injection and fixture photos | Added as candidate rules (not mandated) |
| Developer | Layer boundaries too vague for `NFR-011` to be checkable | Partly resolved by Q8: import rules enforce the Section 5.3 layering; the full backend feature-folder layout is deferred to design |
| Developer | Type checking optional | Resolved by Q8: mypy is required |
| Developer | "Ruff format or Black" | Resolved by Q8: Ruff for lint and format |
| Developer | Missing implementation conventions (sync/async, error envelope, casing, prefix, rendering model) | Deferred to design stages; the question file said so to the human |
| Developer | "Clean, modular, well-documented" not verifiable | Resolved: the Mandated rule now names its checkable form (lint-enforced layering, service docstrings, README per app) |
| Devsecops | Committing secrets was only a candidate | Resolved: promoted to Forbidden (Q9, `construction.md` § Security) |
| Devsecops | The config rule covered only OpenAI and pricing | Resolved: widened to every secret and environment-specific value (Q7) |
| Devsecops | `.gitignore` gap not recorded | Resolved: recorded above and in Code Style (Q9) |
| Devsecops | No security lint rules | Resolved by Q9: Ruff `S` + ESLint security plugins |
| Devsecops | No practices for webhook signatures, logging, fixture photos, object-level authorization | Kept as candidate rules (not mandated); for the design stages |

## Proposals deferred to the design stages (not affirmed)

The human did not decide these, so they are not in `team-practices.md` or the
Mandated/Forbidden rules.

- Sync vs async SQLAlchemy (developer suggested sync) → Application / NFR Design.
- API error envelope, error-code catalogue and status codes not stated by the
  client (e.g. 429 for OTP cooldown/lockout, 422 for photo validation, 502/503
  for upstream failures) → Contract / Functional Design. The client-stated 402 and
  409 already stand in the requirements.
- JSON field casing on the wire, and an `/api/v1` path prefix → Contract Design.
- Next.js rendering model and route protection under in-memory tokens → Application
  / Functional Design.
- Signup email-enumeration behaviour (409 vs generic response) → Requirements
  Analysis / design.
- A stricter coverage floor (90–95% line and branch) for auth modules → not
  affirmed; the floor stays at 80% per app.
- Backend feature-folder layout, import-linter contracts, OpenAPI-generated
  frontend types, `data-testid` naming → Code Generation planning.
- Semgrep or CodeQL SAST, GitHub secret scanning and push protection, the
  vulnerability gate threshold (High/Critical proposed), SBOM → CI setup in the
  first piece of work, or a later decision.
- Python version, dependency manager (uv vs pip-tools), Node version and package
  manager → Code Generation planning.
- Photo and generated-asset storage location and access pattern → Application /
  Infrastructure Design.
- Opt-in evaluation sets for `FR-008` tone and `FR-019` medical decline, and their
  pass thresholds → NFR Design / Build and Test.

## Unresolved uncertainty (carry forward)

1. **`FR-008` vs `FR-008`(f)**: whether medical, medication and allergy answers are
   sent to OpenAI at all. `FR-008` says the questionnaire answers are used as
   context; `FR-008`(f) forbids referencing medical answers; data minimisation
   favours excluding them from the payload. → **Requirements Analysis** (surface
   to the client; do not resolve silently).
2. **User jurisdictions for biometric and health data**: unknown. This decides
   whether GDPR Art. 9 or US state biometric laws (e.g. BIPA) apply, and so the
   consent, encryption and deletion obligations. → **Requirements Analysis** (and
   compliance).
3. **Concurrent multi-tab refresh vs `AUTH-012` reuse detection**: two tabs
   refreshing at once can present an already-rotated token, revoke the family and
   log the user out, contradicting `FE-006`. Needs cross-tab coordination or a
   server-side grace window, recorded traceably. → **design** (Functional / NFR
   Design).
4. **The analysis pipeline must run as a background job**: CV work plus 24
   generated images per report (`FR-020`, `FR-022`) cannot run inside an HTTP
   request. `BackgroundTasks`, a worker process or a job queue is still open.
   → **design** (Application Design).
5. **Traceability statuses**: `BR-006` / `BR-007` (business-only) cannot be tested
   by software, and `FR-003` / `FR-004` are blocked until the Onboarding
   Questionnaire Specification arrives. Proposed: `N/A` with a written
   justification and `Deferred` with a pointer to the missing specification, so no
   ID is dropped silently. Pending the questionnaire specification and a human
   confirmation. → **Requirements Analysis** / Build and Test.
6. **Walking skeleton vs scope default**: the team affirmed "always build a walking
   skeleton first" (Q3) while the `classic` scope declares `skeleton: off`. The
   orchestrator should apply the affirmed team stance at Construction entry
   (a `PRACTICES_OVERRIDE` with `Reason: bolt-plan-marker-conflict` is the recorded
   path if a plan marker disagrees).
7. **Trunk rename**: the repository is still on an unborn `master`; it must be
   renamed to `main` before the first commit and before the first Construction
   worktree is created.
