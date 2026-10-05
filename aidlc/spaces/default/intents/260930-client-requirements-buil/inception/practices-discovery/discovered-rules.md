# Discovered Rules — AI Facial Analysis Platform

> Only hard constraints the human stated appear under `## Mandated` and
> `## Forbidden`: the constraints in `client_requirements.md` (the human-provided
> source of truth, each rule citing its requirement ID) and the interview answers
> that are hard constraints (cited as `Q<n>`). Each rule is one line because the
> promotion tool appends every line in these two sections to `project.md`.
> Delivery-team recommendations the human did not state are kept separately under
> "Candidate rules" and are not promoted.

## Mandated

- ALWAYS build the backend as a separate Python + FastAPI application using SQLAlchemy as the ORM, Alembic for migrations and PostgreSQL as the database (`NFR-001`, `NFR-002`, `NFR-003`, `NFR-004`).
- ALWAYS build the frontend as a separate Next.js + TypeScript application that talks to the backend over HTTP/CORS, with authentication state managed in Zustand (`NFR-005`, `NFR-006`, `FE-001`).
- ALWAYS keep authentication custom and backend-controlled: the backend alone issues, validates, refreshes, rotates and revokes JWT access/refresh tokens and OTPs (`AUTH-001`, `AUTH-002`, `AUTH-004`, `AUTH-005`, `CON-002`).
- ALWAYS preserve the layering UI → Zustand Auth Store → API Client → Backend Auth APIs → JWT/OTP Services in every design and in the code (`client_requirements.md` Section 5.3, `FE-003`, `FE-004`, `FE-007`).
- ALWAYS store the refresh token only as an httpOnly cookie set, rotated and cleared by the backend, and keep the access token and user profile in memory only (`FE-002`, `OQ-009`).
- ALWAYS enforce payment before analysis and report access on the server side, and start analysis only from an explicit user "Start Analysis" action, never from the Stripe webhook (`FR-015`, `BR-001`).
- ALWAYS enforce photo validation, including the cross-photo identity check, on the backend, and re-run the identity check at checkout and at analysis start (`FR-006`, `BR-005`).
- ALWAYS read the report price and currency, the OpenAI base URL, API key and model, the image-generation vendor, and every other environment-specific value or secret from configuration (`FR-016`, `NFR-008`, `NFR-013`, `OQ-002`, Q7).
- ALWAYS write clean, modular, well-documented code that the client's own team can continue with AI-assisted tools, with lint-enforced layering, docstrings on services and a README per app as its checkable form (`NFR-011`, `BC-005`, Q8).
- ALWAYS map every `FR-*`, `AUTH-*`, `BR-*` and `FE-*` requirement to at least one test case (`client_requirements.md` Section 12, Q5).
- ALWAYS keep at least 80% line coverage in each application, enforced by the coverage tool, without adding exclusions to make a check pass (Q5, `org.md` § Testing Posture).
- ALWAYS merge into `main` through a GitHub pull request, squash-merged, with the required GitHub Actions checks (lint, type check, tests, coverage) passing on the protected `main` branch (Q1, Q6).
- ALWAYS label anything not explicitly stated by the client as `[Recommendation]`, `[Assumption]` or `[Decided by delivery team]` in derived documents, and surface, never silently resolve, conflicts with `client_requirements.md` (`client_requirements.md` "How to use this document", items 2–3).

## Forbidden

- NEVER use Supabase Auth, Auth0, Firebase Auth or any other third-party authentication-as-a-service or identity provider for application authentication (`AUTH-001`, `AUTH-005`, `CON-002`).
- NEVER use Supabase in any role (`NFR-002`).
- NEVER store the refresh token, or any auth state, in `localStorage`, `sessionStorage` or a Zustand `persist` store (`FE-002`, `ASM-001`).
- NEVER let UI components call auth APIs or handle tokens directly (`FE-007`, Section 5.3).
- NEVER hardcode the report price or currency, the OpenAI base URL, API key or model, or any other secret or environment-specific value (`FR-016`, `NFR-008`, Q7).
- NEVER commit secrets, API keys, private keys or `.env` files; commit only `.env.example` files with placeholder values (Q9, `construction.md` § Security).
- NEVER call a paid third-party service (OpenAI, Stripe, the email provider) from the default automated test run; use fakes behind the configuration-selected abstractions (Q5, `BR-006`).
- NEVER assume Replit or any other hosting provider (`NFR-010`, `CON-007`).
- NEVER build the out-of-scope items — admin panel and report review workflow, email notifications (SendGrid), Meta Pixel / Google Tag Manager, a formal data-retention policy, or a working PayPal integration — without an explicit client scope change (`BC-006`, `client_requirements.md` Section 2.2).
- NEVER run analysis or generate or expose a report before a successful payment, or from a photo set that failed validation (`FR-015`, `BR-001`, `BR-004`).
- NEVER reference medical, medication or allergy answers in cosmetic commentary, and never answer medical/medication questions in the AI Beauty Assistant (`FR-008`(f), `FR-019`).
- NEVER invent requirements that `client_requirements.md` does not support (`client_requirements.md` "How to use this document", item 2).

## Candidate rules (not mandated)

These came from the support reviews or engineering judgment. The human did not
state them as hard constraints, so they are not promoted. Each can become a rule
later through the design stage that owns it or the learnings ritual.

- Candidate: ALWAYS inject the clock and the random source into the OTP and JWT services, so the `AUTH-011`/`AUTH-012` time boundaries are testable exactly (quality).
- Candidate: NEVER use real user, client or team-member face photos as test fixtures; use synthetic or licensed images only (quality, devsecops).
- Candidate: NEVER log photo data, questionnaire answers, chat content, OTPs, passwords, tokens, `reset_token`, or `Authorization`/`Cookie` headers (devsecops).
- Candidate: ALWAYS verify the Stripe webhook signature on the raw request body and process each event ID idempotently before changing payment status (devsecops).
- Candidate: ALWAYS enforce object-level ownership checks on every endpoint that returns a user's photos, report, PDF, generated images or chat (devsecops).
- Candidate: NEVER serve photos, generated images or report PDFs from public or guessable URLs (devsecops).
- Candidate: ALWAYS strip EXIF metadata and re-encode uploaded images server-side, with size and pixel-dimension limits (devsecops).
- Candidate: NEVER render AI-generated text (narratives, chat) as raw HTML in the frontend (devsecops).
- Candidate: ALWAYS install dependencies from the committed lockfile and block merge on High/Critical known vulnerabilities that have a fix, unless a dated waiver is recorded (devsecops).
- Candidate: ALWAYS return API errors in one envelope `{"error": {"code", "message", "details", "request_id"}}` and branch on `code` in the frontend (developer).
- Candidate: NEVER read environment variables outside the backend `Settings` class or the frontend `env.ts` module (developer).
- Candidate: ALWAYS represent money as integer minor units plus an ISO-4217 currency code, never as floats (developer).
- Candidate: ALWAYS keep the required photo-angle set and the photo-validation and identity thresholds as configuration values (`ASM-005`, `ASM-002`, `ASM-010`; lead, developer).
- Candidate: ALWAYS ship database schema changes as forward-only, backward-compatible Alembic migrations (lead).
