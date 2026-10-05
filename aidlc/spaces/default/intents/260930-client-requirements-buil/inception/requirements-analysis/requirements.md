# Requirements — AI Facial Analysis Platform

**Source of truth:** `client_requirements.md` (v1.0, 2026-09-29). Every requirement below cites the client IDs it comes from (`FR-*`, `AUTH-*`, `FE-*`, `NFR-*`, `BR-*`, `WF-*`, `DATA-*`, `CON-*`, `ASM-*`, `OQ-*`). Anything the client did not state is labelled **[Decided by delivery team]**, **[Recommendation]** or **[Assumption]**, and cites the answer in `requirements-analysis-questions.md` (`Q1`–`Q8`) or the affirmed team practices (`inception/practices-discovery/team-practices.md`) that it came from.

Requirement IDs in this document (`FR{n}`, `FR{n}.{m}`, `NFR{n}`) are permanent traceability keys for every later stage. They are separate from, and mapped to, the client's IDs (see the Traceability section).

---

## 1. Intent Analysis

**What the client is trying to achieve.** Qoves-style facial aesthetics reports are produced by human experts, which makes them slow and expensive (`BC-001`, `BC-002`). The client wants a consumer product that automates the report with computer vision and AI, and sells it one report at a time behind a paywall (`BC-003`).

**Primary user:** the End User, the only functional role in current scope (Section 3 of the client document). Journey: sign up → questionnaire → three photos → pay → start analysis → read the report, AI visuals and chat (`WF-001`).

**Business goals behind the features.**
- Replace manual expert work with an automated pipeline that still reads as expert, personal and careful (`BC-002`, `FR-008`).
- Collect payment before any analysis cost is incurred (`FR-015`, `BR-001`).
- Publish reports with no human review, which makes enforced photo validation and safe AI behaviour harder requirements (`BR-002`, `BR-004`, `CON-006`).
- Hand over a codebase the client's own team can keep extending with AI-assisted tools (`BC-005`, `NFR-011`).

**Request type and size.** Greenfield, from-scratch build (`CON-001`) of two separate applications (Next.js frontend, FastAPI backend) over PostgreSQL. System-wide scope; complex domain (computer vision, LLM and image-generation integrations, payments, custom authentication). Depth: Standard.

---

## 2. Functional Requirements

Each requirement group ends with acceptance criteria in Given/When/Then form. The user stories stage will expand these; the criteria here are the pass/fail test of the requirement itself.

### FR1 — Landing page
Source: `FR-001`, `CON-003`.

- **FR1.1** The system shall show a public landing page with a primary "Get started" call to action that begins sign-up and onboarding.
- **FR1.2** The landing page header shall show a "Sign in" link for returning visitors, separate from "Get started".
- **FR1.3** The landing page shall include an animated, scroll-triggered "How it works" section showing the flow questionnaire → photos → analysis → report.
- **FR1.4** All other landing-page structure and copy is **[Recommendation]**, using the delivery team's own branding (`CON-003`).

Acceptance criteria:
- Given a visitor who is not signed in, when they open the site root, then they see "Get started", a header "Sign in" link, and a "How it works" section with the four steps in order.
- Given a visitor, when they click "Sign in", then they reach the login screen, not the sign-up screen.
- Given a signed-in user with a session, when they open the site root, then "Get started" leads them to the step they have reached rather than a new sign-up (`BR-005` rule 7 routing).

### FR2 — Authentication (backend)
Source: `FR-002`, `AUTH-001`–`AUTH-016`, `WF-002`, `DATA-001`–`DATA-003`, `CON-002`.

- **FR2.1 Sign-up.** The system shall accept full name, email and password; reject an email that is already registered; store only a password hash; create an unverified user; then send an email one-time code (OTP). No tokens are issued at this step (`AUTH-003`, `WF-002` step 1).
- **FR2.2 Login.** The system shall accept email and password, check them against the stored hash, and on success send an email OTP. No tokens are issued at this step (`AUTH-003`).
- **FR2.3 OTP verification.** The system shall verify the OTP against its stored hash, expiry and attempt limits. On success, sign-up marks the account verified and login confirms the session; in both cases an access token is returned and the refresh cookie is set (`AUTH-003`, `WF-002` step 2).
- **FR2.4 OTP rules.** OTPs expire after 10 minutes; resend has a 60-second cooldown; 5 failed attempts trigger a 15-minute lockout; OTPs are stored hashed, never in plaintext (`AUTH-011`).
- **FR2.5 Tokens.** Access tokens are JWTs valid for 15 minutes. Refresh tokens are valid for 7 days, rotated on every use, and tracked server-side by a token identifier (not the raw token) so they can be revoked (`AUTH-002`, `AUTH-010`, `AUTH-012`).
- **FR2.6 Reuse detection.** If a refresh token that was already rotated is presented again, the whole token family is revoked and the user must sign in again (`AUTH-012`).
- **FR2.7 Refresh.** `POST /auth/refresh` exchanges a valid refresh cookie for a new access token and a rotated cookie (`WF-002` step 4).
- **FR2.8 Logout.** `POST /auth/logout` revokes the refresh session and clears the cookie (`AUTH-006`, `WF-002` step 5).
- **FR2.9 Current user.** `GET /auth/me` returns the authenticated user's profile (`AUTH-014`).
- **FR2.10 Protected endpoints.** Every protected endpoint validates the access token before doing anything else (`AUTH-007`).
- **FR2.11 CSRF.** The cookie-authenticated endpoints (`/auth/refresh`, `/auth/logout`) require an `X-Requested-With` header and an Origin/Referer on the allow-list (`AUTH-013`).
- **FR2.12 Forgot password.** Three steps: request by email → verify a 6-digit emailed code (same rules as FR2.4) → set a new password with a short-lived (~10 minutes), single-use `reset_token` issued only after the code is verified. The reset token is rejected if reused, expired, or presented as a Bearer access token. On success, every session of that account on every device is revoked. The request step does not reveal whether the email exists (`AUTH-015`, `BR-009` exception).
- **FR2.13 Change password.** A signed-in user can change their password with current and new password (`POST /auth/change-password`); the session stays active (`AUTH-016`).
- **FR2.14 Roles.** Each user record carries a `role` field, currently always `"user"`, so an `"admin"` role can be added later without schema rework (`AUTH-008`, `AUTH-009`).
- **FR2.15 No third-party auth.** Authentication is custom and backend-controlled; no Supabase Auth, Auth0, Firebase Auth or other identity provider is used (`AUTH-001`, `AUTH-005`, `CON-002`).

Acceptance criteria:
- Given a new email, when the user submits full name, email and a valid password, then an unverified account is created, an OTP email is sent, and no token or cookie is returned.
- Given a registered email, when someone tries to sign up with it, then sign-up is refused and no OTP is sent.
- Given a pending OTP, when the correct code is submitted within 10 minutes, then the account is verified (sign-up) or the session confirmed (login), an access token is returned, and an httpOnly refresh cookie is set.
- Given 5 wrong OTP submissions, when a 6th is submitted, then it is refused for 15 minutes even if correct.
- Given an OTP was sent less than 60 seconds ago, when the user asks to resend, then the resend is refused with the remaining wait.
- Given a refresh token that has already been rotated, when it is presented to `/auth/refresh`, then every token in its family is revoked and the response is 401.
- Given a request to `/auth/refresh` without `X-Requested-With` or from an origin not on the allow-list, then it is refused.
- Given a completed password reset, when any old refresh cookie of that account is used, then it is refused with 401.
- Given a signed-in user who changes their password with the correct current password, then the change succeeds and their current session keeps working.

### FR3 — Session handling in the frontend
Source: `FE-001`–`FE-007`, Section 5.3, `ASM-001`.

- **FR3.1** Auth state (user profile, access token, initializing flag) lives only in memory in a single Zustand auth store; the store never uses `persist` and never holds the refresh token (`FE-001`, `FE-002`, `FE-003`).
- **FR3.2** A single API client attaches the access token to authenticated requests and sends cookies (`credentials: "include"`) (`FE-004`).
- **FR3.3** On app start, the client calls `POST /auth/refresh` to restore the session; protected routes wait until this restore finishes (`FE-002`).
- **FR3.4** The client refreshes the access token about 1 minute before it expires, and on a 401 it refreshes and retries once. Concurrent refreshes share one in-flight request (`FE-005`).
- **FR3.5** Auth state is cleared and the user redirected to login only when refresh returns 401 or the user logs out — never because of access-token expiry, page reload, closing a tab or browser, a network error, or a 5xx response (`FE-006`).
- **FR3.6** UI components never call auth APIs or touch tokens directly; the layering is UI → Zustand Auth Store → API Client → Backend Auth APIs → JWT/OTP Services (`FE-007`, Section 5.3).

Acceptance criteria:
- Given a signed-in user, when they reload the page or reopen the browser within 7 days, then they are still signed in without re-entering credentials.
- Given an access token about to expire, when the user keeps using the app, then requests continue without the user noticing a refresh.
- Given three requests that all get 401 at once, then exactly one refresh call is made and all three are retried after it.
- Given the backend returns 503 or the network drops, then the user stays signed in and sees an error toast rather than being sent to login.
- Given the refresh call returns 401, then the auth store is cleared and the user lands on the login screen.

### FR4 — Consent and onboarding questionnaire
Source: `FR-003`, `FR-004`, `BR-003`, `DATA-004`; `Q2`, `Q4`.

- **FR4.1 Consent [Decided by delivery team — Q2].** Before the questionnaire starts, the user must tick an explicit consent to processing of their facial images, facial measurements and health-related questionnaire answers for producing their report. The consent is stored with a timestamp and the consent text version. Without it, the user cannot continue.
- **FR4.2 Data-driven questionnaire [Decided by delivery team — Q4].** The questionnaire's questions, answer options and branching rules come from configuration or seed data, not code. Until the Onboarding Questionnaire Specification arrives, clearly marked placeholder content is used. Loading the real 23 questions must need no code change (`FR-003`).
- **FR4.3 Branching.** The questionnaire shows or skips questions according to the configured branching rules based on earlier answers (`FR-003`).
- **FR4.4 Disclaimer gate.** The questionnaire ends with a mandatory checkbox disclaimer (no Body Dysmorphic Disorder–related concerns; recommendations are informational, not medical). It cannot be submitted unless the box is ticked. The wording is configurable and comes from the specification (`FR-004`, `BR-003`).
- **FR4.5 Stored answers.** Submitted answers are stored per user, each linked to its question so the real question text can be sent to OpenAI later (`DATA-004`, `FR-008`(a)).
- **FR4.6 Sensitive-question flag [Decided by delivery team — Q1].** Each configured question carries a flag marking it as medical, medication or allergy related, so those answers can be excluded from AI requests (see FR8.6).

Acceptance criteria:
- Given a verified user who has not consented, when they try to open the questionnaire, then they see the consent step and cannot skip it.
- Given a questionnaire configuration that includes a branching rule, when the triggering answer is chosen, then the dependent question appears (or is skipped) accordingly.
- Given the final disclaimer is unticked, when the user tries to submit, then submission is blocked with a visible reason and nothing is saved as submitted.
- Given a new questionnaire definition is loaded as seed data, when a user starts onboarding, then they see the new questions with no code change.

### FR5 — Photo capture
Source: `FR-005`, `ASM-005`, `OQ-010`.

- **FR5.1** Before upload, the system shows a Photo Requirements screen with the 7-point checklist: remove glasses and hat; natural, even lighting; plain white background; tie back long hair; remove makeup; avoid neck-covering clothing; no filters.
- **FR5.2** The user provides three photos — front, left 3/4, right 3/4 — each by file upload or by device camera.
- **FR5.3** The set of required angles is a single configuration value, so moving to the 7-pose set later is a configuration change (`ASM-005`).
- **FR5.4** A retake replaces the existing photo for that angle; there is never more than one photo record per angle per user (`BR-005`, `DATA-005`).
- **FR5.5 [Recommendation — security review in practices discovery]** Uploaded images have location and other identifying metadata (EXIF) removed before storage.

Acceptance criteria:
- Given the requirements screen, when the user proceeds, then they are asked for exactly the configured angles, in order.
- Given a device with a camera, when the user chooses camera capture, then they can take the photo in the browser without uploading a file.
- Given an existing front photo, when the user retakes it, then the old front photo is replaced and only one front photo exists.

### FR6 — Photo validation (enforced by the backend)
Source: `FR-006`, `BR-004`, `BR-005`, `CON-006`, `ASM-002`, `ASM-010`; `Q4`.

- **FR6.1 Per-photo checks.** Each photo is checked on upload for: readable image file, minimum resolution, acceptable brightness/exposure, exactly one face, face-to-frame proportion within range, eyes and mouth not covered, and pose matching the requested angle. A failing photo is rejected with a clear reason naming the failed check (`FR-006`, `BR-005`).
- **FR6.2 Configurable thresholds [Decided by delivery team — Q4].** All thresholds come from configuration, with initial values set during development and recorded in the Photo Validation Specification (`ASM-002`, `OQ-008`).
- **FR6.3 Identity check.** Once all three angles have individually passed, the system checks they show the same person, using the MediaPipe-landmark signature and initial threshold 0.6 described in `ASM-010`. It never blocks a single upload.
- **FR6.4 Which photo is flagged.** Each photo counts how many of the other two it matches within the threshold; the photo(s) with the fewest matches are flagged. When the vote is ambiguous, front is the reference. If all three differ, both non-front photos are flagged. The result is a list of mismatched angles, empty when consistent (`BR-005` rules 2–4).
- **FR6.5 Recompute on retake.** The identity result is recomputed from scratch from the current three photos after every retake; nothing carries over (`BR-005` rule 5).
- **FR6.6 Review screen behaviour.** The review screen highlights every flagged photo and disables Continue while any is flagged. A retake never moves the user forward automatically. Skipping the review screen for an already-complete set is decided only on the initial page load (`BR-005` rule 6).
- **FR6.7 Routing.** Every entry point (after login, direct dashboard visit, end of questionnaire, and so on) treats an identity-inconsistent set as incomplete and sends the user to the photo screen with the error shown (`BR-005` rule 7).
- **FR6.8 Server-side re-check.** The identity check runs again on the server at payment checkout and at analysis start; a mismatch returns HTTP 409 with the mismatched angles (`BR-005` rule 8).
- **FR6.9** No analysis runs and no report is generated from a photo set that failed validation (`BR-004`).

Acceptance criteria:
- Given a photo with two faces, when it is uploaded, then it is rejected with a reason saying exactly one face is required.
- Given a left 3/4 upload that is actually a front-facing photo, then it is rejected for pose mismatch.
- Given front and left match but right is a different person, then only right is flagged and Continue is disabled.
- Given front matches left and front matches right but left and right do not match, then the vote is ambiguous, front is the reference, and no photo is flagged.
- Given all three photos are different people, then left and right are both flagged and front is not.
- Given a flagged right photo, when the user retakes it with a matching photo, then no photo is flagged, Continue becomes enabled, and the user stays on the screen.
- Given a set that became inconsistent, when the user calls checkout or start-analysis directly, then the server returns 409 with the mismatched angles.

### FR7 — Payment
Source: `FR-015`, `FR-016`, `BR-001`, `NFR-009`, `DATA-008`, `ASM-003`, `ASM-008`, `OQ-002`.

- **FR7.1** The payment screen appears as soon as a valid, identity-consistent photo set exists; no teaser or partial result is shown before payment (`FR-015`).
- **FR7.2** Payment uses Stripe hosted Checkout, one-time payment per report, no subscription (`FR-016`, `NFR-009`).
- **FR7.3** Price and currency are configuration values, never hardcoded; the price itself is still open (`FR-016`, `OQ-002`).
- **FR7.4** Payment status is updated only by the verified Stripe webhook. The webhook never starts analysis (`FR-015`).
- **FR7.5 [Recommendation — security review in practices discovery]** The webhook verifies Stripe's signature and handles repeated delivery of the same event without double-processing.
- **FR7.6** Any attempt to start analysis or access a report without a successful payment returns HTTP 402 (`FR-015`, `BR-001`).

Acceptance criteria:
- Given a consistent photo set and no payment, when the user continues, then they see the payment screen and nothing of the analysis.
- Given the user completes Stripe Checkout, when Stripe sends the success webhook, then the payment is marked succeeded and analysis has not started.
- Given the same webhook event is delivered twice, then the payment is recorded once.
- Given a webhook with an invalid signature, then it is rejected and nothing changes.
- Given no successful payment, when the client calls start-analysis or the report endpoint, then the response is 402.
- Given the configured price changes, when a new checkout starts, then the new price is charged with no code change.

### FR8 — Analysis pipeline
Source: `FR-007`, `FR-008`, `FR-015`, `NFR-007`, `NFR-008`, `DATA-006`, `ASM-010`; `Q1`, `Q5`.

- **FR8.1 Explicit start.** Analysis starts only when the paid user clicks "Start Analysis"; it re-runs the payment check (402) and identity check (409) before starting (`FR-015`, `BR-005` rule 8).
- **FR8.2 Background run with progress [Decided by delivery team — Q5].** Analysis runs as a background job, not inside the web request. The user sees a progress screen with the current step, can leave and come back, and sees the same progress on return.
- **FR8.3 Measurement.** Facial landmarks are detected with MediaPipe Face Landmarker (478 points) and measured with OpenCV. Seven of the 11 features get real geometric measurements; Hair, Skin and Neck use simpler heuristics or none. Mesh-based features use the front photo; each ear uses its own side's 3/4 photo, falling back to the front photo if that side is missing (`FR-007`, `NFR-007`).
- **FR8.4 Narrative.** For each of the 11 features, OpenAI (`gpt-4o`, multimodal — photos plus measurements plus questionnaire context) writes a 3–5 sentence narrative that cites an actual measurement value when one exists (`FR-008`(b), (c)).
- **FR8.5 Prompt content.** Each questionnaire answer sent to OpenAI is sent with its real question text, never as an opaque ID (`FR-008`(a)). The tone is personalised to the user's stated goal, motivation and liked/disliked features, and is especially measured and reassuring when answers indicate elevated appearance-related distress (`FR-008`(d), (e)).
- **FR8.6 Medical answers excluded [Decided by delivery team — Q1].** Answers to questions flagged as medical, medication or allergy related (FR4.6) are never sent to OpenAI. This enforces `FR-008`(f) by not sharing the data at all, and narrows `FR-008`'s "questionnaire answers as context" to non-medical answers.
- **FR8.7 One result per user.** Measurements and narratives are stored as one analysis result per user, linked to the photo set (`DATA-006`).

Acceptance criteria:
- Given a paid user with a consistent photo set, when they click "Start Analysis", then a background job starts and the progress screen shows its first step.
- Given the user closes the tab during analysis, when they sign in again, then they see the progress screen (or the finished report) for the same run.
- Given a completed analysis, then every one of the 11 features has a narrative of 3–5 sentences, and the 7 measured features each cite at least one measurement value.
- Given the OpenAI request payload for a user who answered medical questions, then no medical, medication or allergy answer appears in it.
- Given a missing right 3/4 photo record at measurement time, then the right ear is measured from the front photo.

### FR9 — Report
Source: `FR-009`–`FR-014`, `FR-018`, `BR-002`, `BR-008`, `BR-011`, `DATA-007`, `ASM-007`, `OQ-012`; `Q3`.

- **FR9.1 Eleven features.** Every report covers exactly Hair, Eyebrows, Eyes, Nose, Cheeks, Jaw, Lips, Chin, Skin, Neck, Ears. Smile-related content belongs to Lips; there is no 12th feature (`FR-009`, `BR-008`, `BR-011`).
- **FR9.2 Feature section.** Each feature section contains a narrative, a before/after pair (the user's photo and the AI "after" image from FR10.2) with textual "projected potential" ideas, and a short summary callout (`FR-010`).
- **FR9.3 Static and AI sections.** The introduction, "Understanding Your Results" preamble and limitations/disclaimer are static branded template copy; the closing recommendations section is AI-synthesised (`FR-011`).
- **FR9.4 Three recommendation tiers [Decided by delivery team — Q3].** Recommendations are grouped as at-home/lifestyle, OTC/skincare-active, and optional in-clinic. OpenAI returns each recommendation already labelled with its tier (structured output); configurable keyword rules (`ASM-007`) are used only when a label is missing or invalid. All recommendations are informational, never prescriptive, and include "consult a qualified professional" language (`FR-012`).
- **FR9.5 Interactive report.** An interactive report screen with a table of contents shows Facial Assessments — masculine/feminine dimorphism sliders with an overall summary, a prototypicality score, facial-thirds proportions, symmetry (score out of 100, descriptive label such as "Quite Symmetric", and a Regional Balance breakdown), and a face-shape wireframe — plus per-feature metric tables for the 11 features. Assessment scores are first-pass heuristics subject to later calibration (`FR-018`).
- **FR9.6 Unconfirmed content.** The exact content of the Face Shape view and the Skin feature-analysis view is not assumed; it waits for the Report & UI Specification and is built data-driven in the meantime (`FR-018`, `Q4`).
- **FR9.7 PDF.** The report can be downloaded as a PDF in the delivery team's own branding. The PDF is generated on first download and cached (`FR-013`).
- **FR9.8 Auto-publish.** The report is published and available as soon as it is generated — no review step. One report per user, 1:1 with that user's analysis result (`FR-014`, `BR-002`).

Acceptance criteria:
- Given a generated report, then it contains exactly the 11 named features in order and no Smile section.
- Given a recommendation whose tier label from OpenAI is missing, then the keyword rules assign a tier and the recommendation still appears in exactly one tier.
- Given a report, then the introduction, preamble and limitations text match the configured template copy exactly.
- Given a user downloads the PDF twice, then the second download returns the cached file without regenerating it.
- Given analysis finishes, then the report is visible to the user immediately with no approval step.

### FR10 — AI-generated images
Source: `FR-020`, `FR-022`, `NFR-013`, `DATA-009`, `DATA-010`, `ASM-011`; `Q6`.

- **FR10.1 Vendor abstraction.** Images are generated with OpenAI `gpt-image-1` image editing at high input fidelity, so the user's identity is preserved while one attribute changes. The vendor sits behind an image-generation interface selected by configuration, so another vendor can be swapped in without code changes elsewhere (`NFR-013`).
- **FR10.2 Per-feature "after" images.** Each of the 11 features gets its own AI-generated "after"/potential image — 11 per report (`FR-022`, `DATA-009`).
- **FR10.3 AI Visuals.** Five hairstyle variations, five outfit variations, and a healthy-aging stack of four cards at current (the user's own photo, not generated), +3 years, +5 years and +10 years — 13 generated images per report (`FR-020`, `DATA-010`).
- **FR10.4 Volume.** Each report produces 24 generated images (`FR-020` + `FR-022`).
- **FR10.5 Failure handling [Decided by delivery team — Q6].** A failed image generation is retried automatically up to 3 times. If it still fails, the report is published with that image slot marked "not available yet", and the user can retry that image later from the report or AI Visuals screen. The report text never waits on images.

Acceptance criteria:
- Given a finished report, then 11 per-feature images and 13 AI Visual images are stored and linked to the report, and the "current" healthy-aging card is the user's own front photo.
- Given the image vendor is switched in configuration, when a report is generated, then the new vendor is used with no code change outside the vendor adapter.
- Given one image fails 4 times in a row (first try plus 3 retries), then the report is still published, that slot shows "not available yet", and a retry action is offered.
- Given the user retries a failed image and generation succeeds, then the slot shows the new image.

### FR11 — Home Overview
Source: `FR-017`.

- **FR11.1** Once a report exists, the user's landing screen is the Home Overview: key stats, the before/potential image, a "Priority Features to Improve" list, a protocol summary, and a facial-harmony radar chart with six axes including Symmetry.
- **FR11.2** A persistent header gives access to Home, Report, AI Visuals and Chat; account and billing are under Settings.
- **FR11.3** Report status and the PDF download are reachable from Home.
- **FR11.4** The exact content of the Protocol section is not assumed; it waits for the Report & UI Specification and is built data-driven meanwhile (`FR-017`, `Q4`).

Acceptance criteria:
- Given a user whose report exists, when they sign in, then they land on Home Overview, not the questionnaire or photo screens.
- Given the Home Overview, then the radar chart shows exactly six axes, one of which is Symmetry.
- Given the header, then Home, Report, AI Visuals and Chat links are present on every post-analysis screen.

### FR12 — AI Beauty Assistant (chat)
Source: `FR-019`, `DATA-011`, `BR-006`; `Q1`, `Q8`.

- **FR12.1** The user can chat about their own report. Answers are grounded in their measurements, narratives and non-medical questionnaire answers (`FR-019`, narrowed by `Q1`).
- **FR12.2** The assistant declines medical and medication questions and directs the user to a qualified professional (`FR-019`).
- **FR12.3** Conversations and messages are stored per user and report (`DATA-011`).
- **FR12.4 Daily limit [Decided by delivery team — Q8].** Each user has a configurable daily message limit (initial value 50). When it is reached, the user sees a clear message saying when they can chat again, and no request is sent to OpenAI.

Acceptance criteria:
- Given a user asks "What is my symmetry score?", then the answer uses the value from their own report.
- Given a user asks whether they should change a medication, then the assistant declines and suggests a qualified professional.
- Given a user has sent the configured daily maximum, when they send another message, then it is refused with the reset time and no OpenAI call is made.
- Given a user returns later, then their earlier conversation is shown.

### FR13 — Settings
Source: `FR-021`, `AUTH-016`, `BR-012`, `ASM-009`.

- **FR13.1 Account Info** shows full name, email, verification status and member-since date. Full name is set at sign-up and cannot be edited.
- **FR13.2 Password** lets a signed-in user change their password with current, new and confirm-new fields, without being signed out (FR2.13).
- **FR13.3 Billing** shows payment history, a working Stripe option, and PayPal shown but disabled (muted button with a "not available"-style status label). There is no real PayPal integration (`BR-012`).

Acceptance criteria:
- Given Account Info, then full name has no edit control.
- Given new and confirm-new passwords that differ, then the change is refused on the client before any request is sent.
- Given Billing, then the PayPal option is visible, disabled and labelled as not available, and clicking it does nothing.

### FR14 — App-wide interface conventions
Source: `BR-009`, `BR-010`.

- **FR14.1** Every user action with a real success or failure outcome shows a toast (top-right). Exception: outcomes that must stay hidden for anti-enumeration reasons, such as the forgot-password request (`BR-009`).
- **FR14.2** Every destructive or irreversible action (delete, logout, revoke, and so on) asks for confirmation in a shared confirmation dialog before it runs (`BR-010`).

Acceptance criteria:
- Given the user saves any change successfully or unsuccessfully, then a toast states the outcome.
- Given the user clicks Logout, then a confirmation dialog appears, and cancelling keeps them signed in.
- Given a forgot-password request for an unknown email, then the screen shows the same message as for a known email.

---

## 3. Non-Functional Requirements

- **NFR1 — Technology stack.** Backend: Python + FastAPI, SQLAlchemy, Alembic migrations, PostgreSQL (vendor-neutral; no Supabase in any role). Frontend: Next.js + TypeScript with Zustand for auth state. Two separate applications talking over HTTP/CORS. Pass: both apps build and run independently; all schema changes are Alembic migrations (`NFR-001`–`NFR-006`, `CON-001`).
- **NFR2 — Authentication security.** The token, OTP, CSRF and reset rules in FR2 are met exactly: 15-minute access token, 7-day rotating refresh token with family revocation on reuse, hashed OTPs with 10-minute expiry / 60-second resend / 5-attempt 15-minute lockout, refresh token only in an httpOnly cookie. Passwords are stored only as hashes from a slow password-hashing algorithm **[Recommendation]**. Pass: each rule has an automated test (`AUTH-010`–`AUTH-016`, `FE-002`, `ASM-001`).
- **NFR3 — Protection of sensitive data.** Facial photos, landmark signatures and questionnaire answers are treated as sensitive personal data **[Decided by delivery team — Q1, Q2; practices discovery security review]**:
  - medical, medication and allergy answers never leave the platform (FR8.6);
  - photos and answers never appear in logs, error messages or test fixtures; tests use synthetic or licensed images only;
  - every photo, report, visual and chat endpoint checks that the resource belongs to the requesting user;
  - consent is recorded before processing (FR4.1).
  Pass: an automated test proves one user cannot read another user's photo, report, visual or chat; log output from the test suite contains no answer text or image data.
- **NFR4 — Analysis time [Decided by delivery team — Q5].** Under normal conditions (vendors responding normally), a report is ready — all narratives written and all 24 images either generated or marked failed — within 10 minutes of "Start Analysis". Pass: measured in an end-to-end run with the vendor fakes set to realistic latencies, and verified once against the real vendors before handover.
- **NFR5 — Reliability of external calls.** Every call to OpenAI, Stripe and the email provider has a timeout, and errors are surfaced or logged, never swallowed (construction phase guardrail). Image generation retries per FR10.5. The Stripe webhook is idempotent (FR7.5). Pass: tests simulate vendor timeouts and errors and show the documented behaviour.
- **NFR6 — Configuration over code.** These are configuration values and never hardcoded: report price and currency; OpenAI base URL, API key and models; image-generation vendor; required photo angles; photo-validation and identity thresholds; questionnaire content and branching; recommendation keyword rules; chat daily limit; consent and disclaimer text; every secret and environment-specific value (`FR-016`, `NFR-008`, `NFR-013`, `ASM-005`, `ASM-002`, `ASM-010`, `Q3`, `Q4`, `Q8`). Pass: a repository scan finds no literal keys, prices or model names in application code.
- **NFR7 — Maintainability.** Clean, modular, documented code for the client's own AI-assisted team: lint-enforced layering (including Section 5.3), docstrings on services, a README per app, Ruff + mypy for Python, ESLint + Prettier + strict TypeScript for the frontend (`NFR-011`, `BC-005`, team practices Code Style). Pass: all these checks pass in CI on every pull request.
- **NFR8 — Testability.** Every `FR-*`, `AUTH-*`, `BR-*` and `FE-*` client requirement maps to at least one test; each app keeps at least 80% line coverage; paid services are faked in the default test run; a small set of Playwright end-to-end tests covers sign-up/login and photos → payment → report (client Section 12, team practices Testing Posture). Pass: CI enforces the coverage floor and the traceability list has no untested requirement except those recorded as N/A or Deferred with a reason.
- **NFR9 — Devices, browsers and accessibility [Decided by delivery team — Q7].** Responsive web for phones and desktops; the latest two versions of Chrome, Safari, Edge and Firefox; WCAG 2.1 AA. Pass: automated accessibility checks (for example axe) report no WCAG 2.1 AA violations on the main screens, and the Playwright journeys pass on a phone-sized and a desktop viewport.
- **NFR10 — Cost control [Decided by delivery team — Q8].** Paid AI usage is bounded: one analysis per paid report, the chat daily limit (FR12.4), and a cap on image retries (FR10.5). Third-party costs are billed to the client (`BR-006`, `CON-004`). Pass: tests show no OpenAI call is made past each limit.
- **NFR11 — Hosting neutrality.** No hosting provider is assumed; nothing in the code depends on a specific host. Local development uses Docker Compose for PostgreSQL (`NFR-010`, `CON-007`, team practices Deployment). Pass: both apps start locally from their README instructions with only the `.env.example` values filled in.
- **NFR12 — Email delivery.** OTP and password-reset codes are sent by email through a provider chosen during development, behind an interface so the provider can be swapped (`NFR-012`). Pass: tests use a fake provider; switching providers changes configuration and one adapter only.

---

## 4. Constraints

- Custom, backend-controlled authentication only; no third-party auth service (`AUTH-001`, `CON-002`).
- Stack fixed by the client: FastAPI, SQLAlchemy, Alembic, PostgreSQL, Next.js + TypeScript, Zustand, MediaPipe + OpenCV, OpenAI `gpt-4o` and `gpt-image-1`, Stripe (`NFR-001`–`NFR-009`, `NFR-013`).
- No client branding assets; the delivery team owns UI and branding (`CON-003`).
- Third-party costs belong to the client and are not in any estimate; no committed timeline or dollar estimate (`BR-006`, `BR-007`, `CON-004`, `CON-005`).
- Hosting undecided and not needed now (`NFR-010`, `CON-007`).
- Reports auto-publish with no human review, so validation and safe AI behaviour must be enforced by the system (`BR-002`, `CON-006`).
- Team practices (affirmed): one repo with `backend/` and `frontend/`; pull requests into protected `main` with GitHub Actions checks; walking skeleton first (sign-up → OTP → login → `/auth/me`); 80% coverage per app (`inception/practices-discovery/team-practices.md`).

## 5. Assumptions

- **A1 — Three photo angles.** The build uses front, left 3/4 and right 3/4, configurable, although this is not yet confirmed by the client (`ASM-005`, `OQ-010`). Owner: client sponsor.
- **A2 — Identity check and ear formula are first-pass heuristics** needing a tuning pass on a larger, diverse photo set (`ASM-010`). Owner: delivery team.
- **A3 — Image quality and cost of `gpt-image-1` at 24 images per report are not yet validated** (`ASM-011`). Owner: delivery team, with a check before handover.
- **A4 — Assessment scores (dimorphism, prototypicality, symmetry) are first-pass heuristics**, client-confirmed as subject to calibration (`FR-018`).
- **A5 — Placeholder content** is used for the questionnaire, photo-validation thresholds, Face Shape, Skin view and Protocol section until the separate specifications arrive (`Q4`). Owner: client to supply specifications.
- **A6 — The consent step (FR4.1) and the exclusion of medical answers from OpenAI (FR8.6)** are delivery-team decisions and must be shown to the client for confirmation (`Q1`, `Q2`).
- **A7 — AI tier labelling (FR9.4)** replaces the keyword heuristic as the primary method; the client has not yet decided `OQ-012` (`Q3`).

## 6. Out of Scope

Deferred by the client; not built without an explicit scope change (Section 2.2, `BC-006`):
- Admin panel and the Draft → Pending Review → Approved → Published workflow (the `role` field only keeps the door open, FR2.14).
- Email notifications (SendGrid) — OTP and reset emails are in scope, marketing or status notifications are not.
- Meta Pixel and Google Tag Manager tracking.
- A formal data-retention and privacy policy (FR4.1 records consent and the data model allows later deletion, but no retention rules or deletion feature are built).
- A working PayPal integration (shown disabled only).
- Deployment to any host (hosting undecided).

## 7. Open Questions (for later stages or the client)

- **OQ-002 — Report price.** Kept open by the client; price and currency stay configurable (FR7.3).
- **OQ-010 — 3 angles vs the 7-pose Qoves set.** Not yet put to the client (A1).
- **OQ-012 — Tiering method.** Resolved for the build as AI labelling with keyword fallback (`Q3`), still to be confirmed by the client.
- **Jurisdiction.** Which countries users are in, and therefore which biometric and health-data rules apply (`Q2`). To raise with the client.
- **Concurrent tabs vs refresh-token reuse detection.** Two tabs refreshing at the same moment could present an already-rotated token and trigger family revocation (FR2.6), logging the user out against FE-006 (FR3.5). Needs a design decision in Domain Design (for example cross-tab coordination of the single-flight refresh, or a short grace window).
- **Status codes not fixed by the client.** 402 and 409 are client-stated; codes for OTP lockout/cooldown and photo-validation failure are decided in Contract Design.
- **Traceability for business-only and blocked IDs.** `BR-006`/`BR-007` have no testable behaviour and `FR-003`/`FR-004` content is blocked on the questionnaire specification; the test traceability list records them as N/A or Deferred with a reason (team practices, open item).
- **Face Shape, Skin view and Protocol content** await the Report & UI Specification (FR9.6, FR11.4).

---

## 8. Traceability

| Client IDs | Requirements here |
|---|---|
| `BC-001`–`BC-007` | Intent Analysis; NFR7 |
| `FR-001` | FR1 |
| `FR-002`, `AUTH-001`–`AUTH-016`, `WF-002` | FR2, NFR2 |
| `FE-001`–`FE-007`, Section 5.3, `ASM-001` | FR3, NFR2 |
| `FR-003`, `FR-004`, `BR-003` | FR4 |
| `FR-005`, `ASM-005` | FR5 |
| `FR-006`, `BR-004`, `BR-005`, `ASM-002`, `ASM-010` | FR6 |
| `FR-015`, `FR-016`, `BR-001`, `NFR-009`, `ASM-003`, `ASM-008` | FR7 |
| `FR-007`, `FR-008`, `NFR-007`, `NFR-008` | FR8 |
| `FR-009`–`FR-014`, `FR-018`, `BR-002`, `BR-008`, `BR-011`, `ASM-007` | FR9 |
| `FR-020`, `FR-022`, `NFR-013`, `ASM-011` | FR10 |
| `FR-017` | FR11 |
| `FR-019` | FR12 |
| `FR-021`, `BR-012`, `ASM-009` | FR13 |
| `BR-009`, `BR-010` | FR14 |
| `NFR-001`–`NFR-006`, `CON-001` | NFR1 |
| `NFR-010`, `CON-007` | NFR11 |
| `NFR-011` | NFR7 |
| `NFR-012` | NFR12 |
| `BR-006`, `BR-007`, `CON-004`, `CON-005` | Constraints; NFR10 |
| `DATA-001`–`DATA-011` | FR2, FR4, FR5, FR7, FR8, FR9, FR10, FR12 (data model detail in Domain Design) |
| Section 2.2 | Out of Scope |
| `Q1`–`Q8` (this stage) | FR4.1, FR4.2, FR4.6, FR6.2, FR8.2, FR8.6, FR9.4, FR10.5, FR12.4, NFR3, NFR4, NFR9, NFR10 |
| Team practices (practices discovery) | Constraints; NFR7, NFR8, NFR11; FR5.5, FR7.5 |
