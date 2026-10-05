# Practices Discovery — Questions

These questions set how the team will build the AI Facial Analysis platform. The suggested answers come from the organisation defaults and from `client_requirements.md`; the release engineer, quality engineer, developer and security engineer reviewed them first. Pick one letter per question (or X and describe your own answer).

Design choices such as sync vs async database access, the API error format and the Next.js rendering approach are left for the later design stages, not asked here.

---

## Way of Working

### Question 1 — Branching and merging
The new repository is currently on a `master` branch with no commits, while the default practice assumes a `main` trunk with short-lived feature branches that are squash-merged (one commit per piece of work). How should changes reach the trunk?

A. Rename to `main`; each piece of work on a short-lived branch, squash-merged into `main` through a GitHub pull request (Recommended)
B. Rename to `main`; squash-merge locally after I approve each piece of work, no pull requests
C. Keep `master` as the trunk, otherwise as in A
X. Other (please specify)

[Answer]: A

### Question 2 — Repository layout
The client requires two separate applications (FastAPI backend, Next.js frontend) that talk over HTTP (NFR-001, NFR-005), but does not say whether they share a repository.

A. One repository with `backend/` and `frontend/` folders, each with its own dependencies, config, tests and README (Recommended)
B. Two separate repositories
X. Other (please specify)

[Answer]: A

---

## Walking Skeleton

### Question 3 — Build a thin end-to-end slice first?
A walking skeleton is a minimal version that runs the whole way through, built first to prove the pieces connect before the real features go in. Here that would be sign-up → emailed code → login → "who am I" across the Next.js app, the FastAPI app and PostgreSQL.

A. Yes — build and verify that thin slice first, then the real features
B. No — go straight into the planned pieces of work in order (default for this workflow)
X. Other (please specify)

[Answer]: A

---

## Testing Posture

### Question 4 — When tests are written
Tests are a deliverable in every piece of work. The question is whether they are written before or after the code.

A. After the code, everywhere: build each layer, then write and run its tests (organisation default)
B. Mixed: after the code in general, but tests first for the riskiest logic — the token/one-time-code services, the frontend token-refresh logic, and the "same person in all three photos" check (Recommended by the quality engineer)
C. Tests first everywhere (TDD)
D. Behaviour scenarios (Given/When/Then) first, then code
X. Other (please specify)

[Answer]: B

### Question 5 — Test types and tools
Every requirement (FR, AUTH, BR, and the frontend FE rules) maps to at least one test (client Section 12), and each app needs at least 80% line coverage. Paid services (OpenAI, Stripe, email) are replaced by fakes in tests. Suggested tools: pytest + pytest-cov with a real PostgreSQL database for the backend; Vitest + React Testing Library for the frontend.

A. Unit and integration tests only (standard level), with those tools
B. As A, plus a small set of Playwright end-to-end tests for the main journeys (sign-up/login, photos → payment → report) (Recommended)
C. As A, but with Jest instead of Vitest
X. Other (please specify)

[Answer]: B

### Question 6 — Where checks run before merging
The default practice requires tests and linting to run in CI before anything merges, but this workflow has no CI stage and no CI exists yet.

A. Add a small GitHub Actions workflow (lint, type check, tests, coverage) as part of the first piece of work, and protect `main` so it must pass (Recommended)
B. Run the checks locally before each merge and record the result at each approval — note: this does not meet the organisation's "CI before merge" rule, so it would be recorded as a known gap
X. Other (please specify)

[Answer]: A

---

## Deployment

### Question 7 — Deployment and local setup
The client says hosting is undecided and not needed now (NFR-010, CON-007), so this workflow ships no deployment. Both apps will read every environment-specific value (database URL, keys, price, model names) from configuration.

A. No deployment now; provide a Docker Compose file to run PostgreSQL locally, plus `.env.example` files (Recommended)
B. No deployment now; no Docker — developers install PostgreSQL themselves; `.env.example` files only
C. Choose a hosting target now (please name it)
X. Other (please specify)

[Answer]: A

---

## Code Style

### Question 8 — Linting, formatting and type checking
The client wants clean, modular, well-documented code that their own team can extend with AI tools (NFR-011, BC-005).

A. Python: Ruff for linting and formatting, plus mypy as a required check. TypeScript: ESLint + Prettier with strict mode. Import rules enforce the layering (e.g. UI never calls auth APIs directly, Section 5.3). Docstrings on services, a README per app (Recommended)
B. As A, but without mypy and without lint-enforced layering (review only)
C. Black for Python formatting with Ruff for linting, otherwise as A
X. Other (please specify)

[Answer]: A

### Question 9 — Security checks
The app stores face photos and medical questionnaire answers. The current `.gitignore` does not ignore `.env` files, key files or local upload folders, so secrets could be committed by accident.

A. Fix `.gitignore` before the first commit; add a secret scanner as a pre-commit hook (Gitleaks); enable security lint rules (Ruff `S`, ESLint security plugins); run `pip-audit` / `npm audit` and turn on Dependabot (Recommended)
B. Fix `.gitignore` and turn on Dependabot only
X. Other (please specify)

[Answer]: A
