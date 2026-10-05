# Project-Level Rules

> Project-specific specialisation and corrections. Loaded after `org.md` and
> `team.md` as strict-additive guidance; contradictions with broader policy
> are rejected. Populated by practices-discovery and the self-learning loop.
>
> Use sparingly: most teams don't need a project layer. Reach for it
> only when this specific project needs stable, durable guidance beyond the
> team practice (for example, package-specific release checks or an additional
> regression suite for a legacy component).

## Way of Working

<!-- Project-specific specialisation. Example: -->
<!-- This monorepo requires package-scoped branch names and a package owner -->
<!-- review in addition to the team's normal merge policy. -->

## Walking Skeleton

<!-- Project-specific specialisation. Example: -->
<!-- The walking skeleton must exercise the legacy service adapter as well -->
<!-- as the new service boundary. -->

## Testing Posture

<!-- Project-specific specialisation. -->

## Guard Policy

<!-- Project-specific. Mode: strict, relaxed, or off. Strict here holds for every intent and cannot be changed from chat. A section under the retired Change Control heading, written by an earlier release, is still read. -->

## Deployment

<!-- Project-specific specialisation. -->

## Code Style

<!-- Project-specific specialisation. -->

## Tech Stack

<!-- Technology choices locked for this project. -->

## Decided

<!-- Decisions made in earlier stages that should not be re-asked. -->
<!-- Format: DECIDED: [decision] (Stage [slug], [date]) -->

## Scope Overrides

<!-- Custom scope rules for this project. -->

## Forbidden

<!-- Populated by practices-discovery affirmation gate. -->
<!-- Format: NEVER [behavior] (affirmed [date]) -->
<!-- Example: NEVER throw exceptions across service layer boundaries (affirmed 2026-05-17) -->

- NEVER use Supabase Auth, Auth0, Firebase Auth or any other third-party authentication-as-a-service or identity provider for application authentication (`AUTH-001`, `AUTH-005`, `CON-002`). (affirmed 2026-09-30)

- NEVER use Supabase in any role (`NFR-002`). (affirmed 2026-09-30)

- NEVER store the refresh token, or any auth state, in `localStorage`, `sessionStorage` or a Zustand `persist` store (`FE-002`, `ASM-001`). (affirmed 2026-09-30)

- NEVER let UI components call auth APIs or handle tokens directly (`FE-007`, Section 5.3). (affirmed 2026-09-30)

- NEVER hardcode the report price or currency, the OpenAI base URL, API key or model, or any other secret or environment-specific value (`FR-016`, `NFR-008`, Q7). (affirmed 2026-09-30)

- NEVER commit secrets, API keys, private keys or `.env` files; commit only `.env.example` files with placeholder values (Q9, `construction.md` § Security). (affirmed 2026-09-30)

- NEVER call a paid third-party service (OpenAI, Stripe, the email provider) from the default automated test run; use fakes behind the configuration-selected abstractions (Q5, `BR-006`). (affirmed 2026-09-30)

- NEVER assume Replit or any other hosting provider (`NFR-010`, `CON-007`). (affirmed 2026-09-30)

- NEVER build the out-of-scope items — admin panel and report review workflow, email notifications (SendGrid), Meta Pixel / Google Tag Manager, a formal data-retention policy, or a working PayPal integration — without an explicit client scope change (`BC-006`, `client_requirements.md` Section 2.2). (affirmed 2026-09-30)

- NEVER run analysis or generate or expose a report before a successful payment, or from a photo set that failed validation (`FR-015`, `BR-001`, `BR-004`). (affirmed 2026-09-30)

- NEVER reference medical, medication or allergy answers in cosmetic commentary, and never answer medical/medication questions in the AI Beauty Assistant (`FR-008`(f), `FR-019`). (affirmed 2026-09-30)

- NEVER invent requirements that `client_requirements.md` does not support (`client_requirements.md` "How to use this document", item 2). (affirmed 2026-09-30)

## Mandated

<!-- Populated by practices-discovery affirmation gate. -->
<!-- Format: ALWAYS [behavior] (affirmed [date]) -->
<!-- Example: ALWAYS use Result<T,E> for fallible operations in service layer (affirmed 2026-05-17) -->

- ALWAYS build the backend as a separate Python + FastAPI application using SQLAlchemy as the ORM, Alembic for migrations and PostgreSQL as the database (`NFR-001`, `NFR-002`, `NFR-003`, `NFR-004`). (affirmed 2026-09-30)

- ALWAYS build the frontend as a separate Next.js + TypeScript application that talks to the backend over HTTP/CORS, with authentication state managed in Zustand (`NFR-005`, `NFR-006`, `FE-001`). (affirmed 2026-09-30)

- ALWAYS keep authentication custom and backend-controlled: the backend alone issues, validates, refreshes, rotates and revokes JWT access/refresh tokens and OTPs (`AUTH-001`, `AUTH-002`, `AUTH-004`, `AUTH-005`, `CON-002`). (affirmed 2026-09-30)

- ALWAYS preserve the layering UI → Zustand Auth Store → API Client → Backend Auth APIs → JWT/OTP Services in every design and in the code (`client_requirements.md` Section 5.3, `FE-003`, `FE-004`, `FE-007`). (affirmed 2026-09-30)

- ALWAYS store the refresh token only as an httpOnly cookie set, rotated and cleared by the backend, and keep the access token and user profile in memory only (`FE-002`, `OQ-009`). (affirmed 2026-09-30)

- ALWAYS enforce payment before analysis and report access on the server side, and start analysis only from an explicit user "Start Analysis" action, never from the Stripe webhook (`FR-015`, `BR-001`). (affirmed 2026-09-30)

- ALWAYS enforce photo validation, including the cross-photo identity check, on the backend, and re-run the identity check at checkout and at analysis start (`FR-006`, `BR-005`). (affirmed 2026-09-30)

- ALWAYS read the report price and currency, the OpenAI base URL, API key and model, the image-generation vendor, and every other environment-specific value or secret from configuration (`FR-016`, `NFR-008`, `NFR-013`, `OQ-002`, Q7). (affirmed 2026-09-30)

- ALWAYS write clean, modular, well-documented code that the client's own team can continue with AI-assisted tools, with lint-enforced layering, docstrings on services and a README per app as its checkable form (`NFR-011`, `BC-005`, Q8). (affirmed 2026-09-30)

- ALWAYS map every `FR-*`, `AUTH-*`, `BR-*` and `FE-*` requirement to at least one test case (`client_requirements.md` Section 12, Q5). (affirmed 2026-09-30)

- ALWAYS keep at least 80% line coverage in each application, enforced by the coverage tool, without adding exclusions to make a check pass (Q5, `org.md` § Testing Posture). (affirmed 2026-09-30)

- ALWAYS merge into `main` through a GitHub pull request, squash-merged, with the required GitHub Actions checks (lint, type check, tests, coverage) passing on the protected `main` branch (Q1, Q6). (affirmed 2026-09-30)

- ALWAYS label anything not explicitly stated by the client as `[Recommendation]`, `[Assumption]` or `[Decided by delivery team]` in derived documents, and surface, never silently resolve, conflicts with `client_requirements.md` (`client_requirements.md` "How to use this document", items 2–3). (affirmed 2026-09-30)

## Corrections

<!-- Project-specific corrections from human feedback. -->
<!-- Format: NEVER/ALWAYS [behavior] (learned [date]) -->
