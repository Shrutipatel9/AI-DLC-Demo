# Units of Work — AI Facial Analysis Platform

The implementation is split into 10 **units** (phases). Each is a vertical slice that delivers its backend module(s) and its screens, so each can be demonstrated in the browser (`units-generation-questions.md` Q1). Units are built from the components in `inception/domain-design/components.md`, and every one of the 80 stories in `inception/user-stories/stories.md` belongs to exactly one unit (`unit-of-work-story-map.md`).

This document says **what** each unit is. `unit-of-work-dependency.md` says what depends on what. The order units are built in, and why, is decided in Delivery Planning.

## Deployment model (Q3, Q4)

- **Two applications**, as the client requires (`NFR-001`, `NFR-005`):
  - `frontend/`: Next.js + TypeScript, containing WebApp and WebAuthClient.
  - `backend/`: FastAPI **modular monolith**, with the 13 backend components as modules. It runs as a **web process** plus a **background worker process** (analysis runs, image generation) from the same codebase.
- **Inside the backend**, modules call each other only through each module's public Python interface: in-process, with no internal HTTP and no message broker. Module import rules are lint-enforced (team practices, Code Style).
- **Between the apps:** HTTP/JSON only (and owner-checked media URLs).
- **Hosting:** none assumed (`NFR-010`). Units run locally with Docker Compose (PostgreSQL and the mail catcher).

Every unit is deployed as part of these two applications. "Standalone" deployment of a single unit doesn't apply.

## Unit summary

| Unit ID | Directory | Name | Kind | Complexity | Components (primary) | Stories |
|---|---|---|---|---|---|---|
| U1 | `u1-walking-skeleton` | Walking skeleton and project groundwork | service | L | Identity (sign-up, code, login, who-am-I), WebAuthClient, WebApp shell | 12 |
| U2 | `u2-session-security` | Full sign-in and session security | service | L | Identity (sessions, reset, change), WebAuthClient (refresh, tabs), WebApp (toast, dialog) | 9 |
| U3 | `u3-onboarding` | Consent and questionnaire | service | M | Onboarding | 4 |
| U4 | `u4-photos` | Photos and the same-person check | service | XL | MediaStore, FaceGeometry, PhotoIntake | 11 |
| U5 | `u5-payments` | Payment | service | M | Payments | 5 |
| U6 | `u6-analysis-core` | Analysis core | service | XL | AnalysisPipeline, FaceMeasurement, ReportWriting | 13 |
| U7 | `u7-ai-images` | AI images | service | M | ImageGeneration | 5 |
| U8 | `u8-report-home` | Report, Home dashboard and PDF | service | L | Report | 11 |
| U9 | `u9-beauty-assistant` | AI Beauty Assistant | service | M | BeautyAssistant | 3 |
| U10 | `u10-journey-settings` | Journey routing, landing, settings and end-to-end checks | service | M | Journey, WebApp (landing, settings), Payments (billing view) | 7 |

**Kind:** every unit is `service`, meaning it adds deployed backend behaviour plus its screens, so each gets the full Construction design set. No unit is spec-only, UI-only, packaging or library.

**Complexity:** S < 3 stories / low risk · M 3–6 stories · L 7–12 stories or security-critical · XL computer vision or AI with calibration risk.

---

## U1 — Walking skeleton and project groundwork (`u1-walking-skeleton`)
- **Description:** the thinnest slice that runs the whole way through: sign up → emailed code → verify → log in → "who am I", across Next.js, FastAPI and PostgreSQL, checked in CI. It also carries the groundwork every later unit relies on (team practices, Walking Skeleton).
- **Boundaries:**
  - *In:* the two-app repo and READMEs; Docker Compose with PostgreSQL and the mail catcher; Alembic baseline; GitHub Actions with lint, types, tests, 80% coverage and layering rules; Gitleaks, security lint and audits; typed configuration; the email adapter and fake; shared error format, ownership check and safe logging; the in-memory auth store and single API client; sign-up, code verification, login and "who am I".
  - *Out:* session restore, refresh, logout, reset (U2).
- **Responsibilities:** prove the pieces connect end to end; establish the conventions (module boundaries, error format, config, tests) that every other unit copies.
- **Implementation notes:**
  - The verification command must run the Playwright journey sign-up → code (read from the mail catcher) → login → "who am I".
  - The OTP and JWT services are test-first (team practices).
  - Rename the trunk to `main` before the first commit.
  - Fix `.gitignore` before the first commit.

## U2 — Full sign-in and session security (`u2-session-security`)
- **Description:** everything that makes the session safe and pleasant: resend and lockout, staying signed in across reloads, silent refresh, reuse detection, CSRF checks, logout, password reset, change password, two-tab coordination, and the app-wide toast and confirmation dialog.
- **Boundaries:**
  - *In:* the rest of Identity; refresh, retry and cross-tab coordination in WebAuthClient; the toast and dialog components.
  - *Out:* account info and billing screens (U10).
- **Responsibilities:** meet `AUTH-010`–`AUTH-016` and `FE-002`–`FE-007` exactly.
- **Implementation notes:**
  - Refresh single-flight and cross-tab coordination are test-first (ADR-006).
  - Server reuse detection stays strict (no grace window).
  - The injectable clock is used for every timing test.

## U3 — Consent and questionnaire (`u3-onboarding`)
- **Description:** versioned consent, the configurable one-question-per-screen questionnaire with branching and follow-ups, the disclaimer gate with its supportive message, and loading the 23 questions from the working specification ([QS]).
- **Boundaries:**
  - *In:* Onboarding and its screens.
  - *Out:* how answers are used by AI (U6, U9).
- **Responsibilities:** own the only health data; expose non-medical answers (with question text) to other modules, and nothing else (ADR-007).
- **Implementation notes:** medical flags on [QS] Q8–Q12 and their follow-ups; the Q19 branch condition and the Q9/Q11 follow-up shape stay open for the client.

## U4 — Photos and the same-person check (`u4-photos`)
- **Description:** private media storage, the shared face-landmark service, the photo requirements screen, upload and camera capture per configured angle, per-photo checks with photo-focused reasons, the same-person vote and the review screen.
- **Boundaries:**
  - *In:* MediaStore, FaceGeometry, PhotoIntake and their screens.
  - *Out:* measurement (U6).
- **Responsibilities:** only valid, same-person photo sets can move on (`BR-004`, `BR-005`); face images are never public (ADR-009).
- **Implementation notes:**
  - The same-person decision is test-first, using the 8-case table and the [IV] worked examples.
  - MediaPipe model version is pinned.
  - HEIC conversion and metadata stripping happen on write.
  - Per-photo thresholds are initial values set in configuration (`ASM-002`).
  - The hub-case tie-break is decided in Functional Design.

## U5 — Payment (`u5-payments`)
- **Description:** the payment screen with the configured price, Stripe hosted Checkout behind an adapter, the verified idempotent webhook, the "confirming your payment" state, and the 402 paywall.
- **Boundaries:**
  - *In:* Payments and its screens, including the Stripe adapter and its fake.
  - *Out:* billing history screen (U10).
- **Responsibilities:** payment status changes only through the verified webhook; the webhook never starts analysis (`FR-015`, ADR-004).
- **Implementation notes:** local testing uses Stripe CLI forwarding; the default test run uses the Stripe fake only.

## U6 — Analysis core (`u6-analysis-core`)
- **Description:** the background worker and job mechanism, the OpenAI text and image adapters with fakes, "Start Analysis", the progress screen, the resumable pipeline, measurements (seven front-mesh features, ears, Hair/Skin/Neck), assessments (symmetry, thirds, dimorphism, prototypicality, face shape), the privacy-safe AI request and validated report text with tiers, and the one free re-run.
- **Boundaries:**
  - *In:* AnalysisPipeline, FaceMeasurement, ReportWriting, the job mechanism and the progress screens.
  - *Out:* image generation (U7); showing the report (U8).
- **Responsibilities:** one analysis per payment plus one free re-run; nothing half-valid is published; no medical answer is ever sent (ADR-001, ADR-007, ADR-010).
- **Implementation notes:**
  - The pipeline must record which photo files a run uses at start, so resumes and later retries use the same photos (architecture review finding R-02).
  - Formulas, label bands and distress thresholds are fixed in Functional Design.
  - AI-quality checks go in the opt-in evaluation suite.

## U7 — AI images (`u7-ai-images`)
- **Description:** the 24 images per report (11 per-feature "after" images, 5 hairstyles, 5 outfits, 3 aging cards), with 3 automatic retries, a "not available yet" state, and up to 3 manual retries per image.
- **Boundaries:**
  - *In:* ImageGeneration and the image step of the pipeline.
  - *Out:* laying out the images in the report and AI Visuals screens (U8).
- **Responsibilities:** vendor-swappable image editing (`NFR-013`); bounded cost (NFR10).
- **Implementation notes:** configurable concurrency and back-off on rate limits (NFR4's 10-minute target); image quality is checked manually before handover (`ASM-011`).

## U8 — Report, Home dashboard and PDF (`u8-report-home`)
- **Description:** report assembly and auto-publish; the single-scroll report with table of contents, assessments, the 11 feature sections and tiered recommendations; AI Visuals; the Home dashboard ([RD] §4) with the radar chart and Protocol card; header navigation; and the cached PDF.
- **Boundaries:**
  - *In:* the Report module and the report, Home and AI Visuals screens.
  - *Out:* chat (U9).
- **Responsibilities:** exactly 11 features, preamble first, AI images labelled, 402/404 enforced, PDF regenerated when an image changes.
- **Implementation notes:** the PDF layout must be owned by the backend (a template Report owns), not rendered from a frontend page (architecture review finding R-01). Face Shape, Skin and Protocol content come from [RD]/[RT], and TBD items stay out.

## U9 — AI Beauty Assistant (`u9-beauty-assistant`)
- **Description:** chat grounded in the user's report, the always-on medical-decline rule, conversation history, and the daily limit (50 per UTC day, failed calls not counted).
- **Boundaries:**
  - *In:* BeautyAssistant and the chat screen.
- **Responsibilities:** safe, grounded answers with bounded cost (`FR-019`, NFR10).
- **Implementation notes:** the medical-decline evaluation set runs before handover *(eval)*.

## U10 — Journey routing, landing, settings and end-to-end checks (`u10-journey-settings`)
- **Description:**
  - the read-only next-step rule and route guard;
  - the landing page with "How it works";
  - re-routing to photos when the set becomes inconsistent;
  - Settings (account info and billing, with PayPal disabled);
  - the requirement-to-test map, the full Playwright journeys and accessibility checks across every screen.
- **Boundaries:**
  - *In:* Journey, landing, Settings screens, US1.13 checks.
  - *Out:* password change (U2).
- **Responsibilities:** every entry point lands on the right step (`BR-005` rule 7); quality gates cover the whole product (NFR8, NFR9).
- **Implementation notes:** Journey needs every stateful module, so it closes the build. Earlier units route with simple temporary links that U10 replaces.
