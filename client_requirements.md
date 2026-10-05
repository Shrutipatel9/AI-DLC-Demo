# Client Requirements — AI Facial Analysis Platform

## Document Control

| Field | Value |
|---|---|
| Document name | `client_requirements` |
| Role | **Single source of truth** for the entire project. Every other project document (PRD, BRD, architecture, technical design, API specification, database design, UI/UX, authentication, security, testing, deployment, and the detailed specifications listed below) must be derived from and validated against this document, not the other way around. |
| Version | 1.0 — initial baseline |
| Status | Draft — active project, expected to evolve |
| Last updated | 2026-09-29 |
| Source materials | Original requirement materials: `Discussion.docx`, `AI Facial Analysis_Proposal.docx`, `AI Facial Analysis Proposal.docx.pdf`, `Estimation.xlsx`, `protocol_report (3).pdf`, `Qoves Onboarding.mp4`, `Screenshot 2026-06-12 at 10.51.25.png`. Reference-product materials: `MyFace - Complete User Flow after report approval.mp4`, `MyFace-Protocol-test-1 (3).pdf`. Plus direct client decisions given in conversation. |

### How to use this document
1. Read and understand this document fully before creating any derived document.
2. Do not invent requirements not supported here — anything not explicitly stated by the client is labeled **[Recommendation]**, **[Assumption]**, or **[Decided by delivery team]**, and must stay labeled that way in any derived document.
3. Derived documents must stay consistent with this source. If a derived document would conflict with something here, surface the conflict — do not silently resolve it.
4. When this document changes, re-check every derived document that references the changed requirement ID(s) (see the Traceability Map, Section 12).
5. Keep business, product, technical, architecture, security, and implementation concerns in separate derived documents — this file mixes them only because it is the intentionally comprehensive source.

### Requirement ID legend
`BC-*` Business Context · `FR-*` Functional Requirement · `AUTH-*` Authentication/Authorization · `FE-*` Frontend requirement · `NFR-*` Non-functional/Technical · `BR-*` Business Rule · `WF-*` Workflow · `DATA-*` Data entity · `CON-*` Constraint · `ASM-*` Assumption/Recommendation (not client-stated) · `OQ-*` Open question

### Detailed specifications to be provided separately
The following detailed specifications do not exist yet. They will be supplied later and must be derived from, and consistent with, the requirements in this document. Until then, this document is the only reference.

| Specification | Expands on |
|---|---|
| Onboarding Questionnaire Specification — the literal 23 questions, answer options, branching logic, and exact disclaimer wording | `FR-003`, `FR-004`, `BR-003` |
| Photo Capture Specification — angle set, requirements screen, per-angle upload / camera capture flow | `FR-005`, `ASM-005` |
| Photo Validation Specification — per-photo check thresholds and the cross-photo identity-check algorithm and state contract | `FR-006`, `BR-005`, `ASM-002`, `ASM-010` |
| Report & UI Specification — report structure, Home Overview, interactive report, AI Visuals, Chat, Settings screens, and app-wide UI conventions | `FR-009`–`FR-022`, `BR-009`–`BR-012` |

---

## 1. Business Context (`BC-*`)

- **BC-001** [Client-stated] The product is an AI-driven facial aesthetics analysis platform, conceptually similar to Qoves.com — an existing real-world service that produces expert, cephalometric-based "aesthetic protocol" reports for clients.
- **BC-002** [Client-stated] The business problem: Qoves-style services depend on human experts manually producing each report, which is slow and expensive. This platform automates that process with computer vision + AI so a similar product can be sold at consumer scale and price point.
- **BC-003** [Client-stated] The commercial model is a paywalled report: a user completes onboarding and photo upload, pays, and an AI-generated report is then produced and made available to them.
- **BC-004** [Client-stated] Project Sponsor: Jay Michaels (paying client). Delivery team: Crest Infosystems (Tejash Patel — PM, Jainesh Bhatt — Business Manager).
- **BC-005** [Client-stated] The client wants to keep extending this codebase with their own team after delivery, using AI-assisted ("vibe coding") development tools — this drives a preference for clean, modular, well-documented code over clever/opaque implementations.
- **BC-006** [Client-stated] Scope is defined by the feature list in Section 2.1. Items in Section 2.2 are deliberately deferred and must not be built without an explicit client scope change.
- **BC-007** [Client-stated] The post-payment experience (Home Overview, interactive report, AI Visuals, AI Beauty Assistant chat, Settings/Billing) is benchmarked against a reference product, "MyFace" (screen recording + exported PDF report supplied by the client). The onboarding and photo-capture experience is benchmarked against Qoves.

---

## 2. Project Scope

### 2.1 In scope
- Landing page (marketing entry point).
- Custom backend-controlled user authentication: email + password + OTP for both signup and login; forgot-password; in-app change-password (Section 5).
- Onboarding questionnaire (23 questions, branching logic, ends in a mandatory disclaimer).
- Photo upload with a guideline checklist UI **and** enforced backend validation, including a cross-photo "same person" identity check.
- Payment (Stripe, one-time payment per report), required **before** analysis starts. Exact price still open (`OQ-002`).
- AI facial analysis engine (MediaPipe + OpenCV for measurement, OpenAI for narrative), built from scratch.
- Report generation (11-feature structured report, PDF export), auto-published.
- Enriched interactive report — Facial Assessments (dimorphism, prototypicality, proportions, symmetry, face shape) and deeper per-feature metrics.
- Per-feature AI-generated before/after image for each of the 11 report features.
- AI Visual Features — AI-generated hairstyle variations, outfit variations, and a healthy-aging preview.
- AI Beauty Assistant — a chat where the user asks questions about their own report.
- Home Overview (post-analysis landing screen) with header navigation to Report / AI Visuals / Chat.
- Settings area (Account Info / Password / Billing).

### 2.2 Out of scope — deferred, do not build without a client scope change
- Admin panel and the full report status workflow: Draft → Pending Review → Approved → Published.
- Email notifications (SendGrid).
- Meta Pixel + Google Tag Manager tracking.
- Formal data-retention/privacy policy definition.
- A working PayPal integration (PayPal is shown visible-but-disabled only — see `BR-012`).

---

## 3. Actors & Roles

- **End User** — signs up/logs in, completes onboarding, uploads photos, pays, starts analysis, views/downloads their own report, uses AI Visuals and the AI Beauty Assistant, manages their account. The only functional role in current scope.
- **Admin** — future role (deferred, §2.2). Will review, edit, verify, and publish AI-generated reports, and manage recommendation content. Not built now, but the data model must not preclude adding it later (`AUTH-009`).
- **Project Sponsor** — Jay Michaels; the business decision-maker for scope and requirements.
- **Delivery team** — Crest Infosystems.
- **System/third-party actors** — OpenAI (`gpt-4o` for Vision/GPT narrative; `gpt-image-1` for image generation), MediaPipe/OpenCV (local CV libraries, not third-party services), Stripe (payments), a PostgreSQL database (hosting provider not yet decided, `NFR-010`; never used for authentication), and an email-based OTP delivery provider (channel confirmed as email; specific provider to be chosen during development).

---

## 4. Functional Requirements (`FR-*`)

### 4.1 Entry, onboarding and photos
| ID | Requirement | Source |
|---|---|---|
| FR-001 | Landing page with a clear call-to-action ("Get started") to begin onboarding, a header "Sign in" link for returning visitors (distinct from "Get started"), and an animated, scroll-triggered "How it works" section showing the product flow: questionnaire → photos → analysis → report. Other structure/copy is a `[Recommendation]`; no client content exists for this page (`CON-003`). | Client-stated |
| FR-002 | User account creation and login (full spec in Section 5). Signup requires the user's **full name**, email, and password. The full name is used for the in-app greeting and user menu. | Client-stated |
| FR-003 | 23-question onboarding questionnaire with branching logic, covering medical conditions/medications, allergies, self-perceived best feature, liked/disliked features, goals and motivation, comfort with specific recommendation types (e.g. weight loss), frequency of appearance-related thoughts, and similar lifestyle/self-perception questions. Content is sourced from the client's Qoves onboarding reference recording (`Qoves Onboarding.mp4`), not invented by the delivery team. Literal questions and branching logic: to be provided in the Onboarding Questionnaire Specification. | Client-stated (Qoves onboarding reference) |
| FR-004 | The questionnaire must end with a mandatory, checkbox-gated disclaimer: the user confirms no Body Dysmorphic Disorder–related concerns and understands recommendations are informational only, not medical guidance. The questionnaire cannot be submitted without it being checked. Exact wording: to be provided in the Onboarding Questionnaire Specification. | Client-stated (Qoves onboarding reference) |
| FR-005 | Photo upload of three angles — **front, left 3/4, right 3/4** (`ASM-005`) — via file upload or camera capture, preceded by a Photo Requirements screen showing a 7-point guideline checklist: remove glasses/hat; use natural, even lighting; use a plain white background; tie back long hair; remove makeup; avoid neck-covering clothing; do not use filters. | Client-stated (Qoves onboarding reference) |
| FR-006 | Photo validation must be **enforced** by the backend, not just displayed as a checklist. Per-photo checks: file readability, minimum resolution, brightness/exposure, exactly one face, face-to-frame proportion, occlusion of eyes/mouth, and pose match (the photo matches the requested angle). Set-level check: all three photos must be the same person. Rules in `BR-005`; thresholds in `ASM-002` / `ASM-010`. | Client-stated |

### 4.2 Payment and analysis
| ID | Requirement | Source |
|---|---|---|
| FR-015 | Nothing is analysed and no report is accessible until the user completes a successful Stripe payment (hosted Checkout + webhook). The payment screen appears immediately after a valid, identity-consistent photo set is uploaded; no teaser or partial content is shown before payment. After payment, analysis starts only when the user clicks an explicit **"Start Analysis"** button, so the "analyzing" step is visible; the Stripe webhook only updates payment status and never starts the pipeline itself. Enforced server-side (payment-required error, HTTP 402). | Client-stated |
| FR-016 | One-time payment per report (no subscription). Price and currency are configuration values, never hardcoded. | Recommendation — price point still open, `OQ-002` |
| FR-007 | Facial landmark detection and mathematical measurement via MediaPipe (Face Landmarker, 478-point mesh) + OpenCV, built new. Seven of the 11 report features get real geometric measurements; Hair, Skin and Neck use simpler heuristics or none. Mesh-based features are measured from the **front** photo, since they are mostly left/right symmetry comparisons and a 3/4-turned photo foreshortens the turned-away side. **Ears** are the exception: each ear is measured from its own side's 3/4 photo, falling back to the front photo only if that side photo is missing. | Client-stated |
| FR-008 | AI-generated narrative explanations and personalized recommendations via **OpenAI** (`gpt-4o`, Vision + GPT). The call is multimodal (photos are sent, not only measurements) and uses both the CV measurements **and** the questionnaire answers as context. Prompt requirements: (a) each questionnaire answer is sent with its real question text, never as opaque IDs; (b) narratives cite an actual measurement value in prose when one is available; (c) 3–5 sentences per feature; (d) tone personalized to the user's stated goal, motivation and liked/disliked features; (e) an especially measured, reassuring tone when answers indicate elevated appearance-related distress (linked to `FR-004`); (f) never reference medical, medication or allergy answers in cosmetic commentary. | Client-stated |

### 4.3 Report
| ID | Requirement | Source |
|---|---|---|
| FR-009 | The report covers exactly 11 facial features: Hair, Eyebrows, Eyes, Nose, Cheeks, Jaw, Lips, Chin, Skin, Neck, Ears — always all 11. Smile-related content is part of Lips (`BR-011`). | Client-stated (Qoves sample report; confirmed by MyFace PDF) |
| FR-010 | Each feature section includes: a narrative analysis; a before/after — the user's photo plus an **AI-generated "after"/potential image** (`FR-022`) with textual "projected potential" ideas; and a short summary callout. | Client-stated (Qoves sample report; MyFace PDF) |
| FR-011 | The report includes an introduction, an "Understanding Your Results" preamble, an explicit limitations/disclaimer section, and a closing recommendations section synthesizing all findings. Introduction, preamble and limitations are static branded template copy (not AI-generated); the closing recommendations are AI-synthesized. | Client-stated (Qoves sample report) |
| FR-012 | Recommendations span three tiers — at-home/lifestyle, OTC/skincare-active, and optional in-clinic — always informational, never prescriptive, with "consult a qualified professional" language. Tiering approach: `ASM-007`. | Client-stated (Qoves sample report) |
| FR-013 | The report is downloadable as a PDF, branded with the delivery team's own in-house design (no client branding assets exist, `CON-003`). [Decided by delivery team] Generated on first download and cached. | Client-stated |
| FR-014 | The report auto-publishes and is immediately available once generated — no manual review/approval step (`BR-002`). One report per user, 1:1 with that user's analysis result. | Client-stated |
| FR-018 | Enriched interactive report screen (with a table of contents): **Facial Assessments** — masculine/feminine dimorphism sliders with an overall summary page, a prototypicality score, facial-thirds proportions, symmetry (score out of 100, a descriptive label such as "Quite Symmetric", and a Regional Balance breakdown), and a face-shape wireframe — plus deeper per-feature metric tables for the 11 features. Assessment scores are first-pass heuristics (client-confirmed) subject to later calibration. Face Shape and the Skin feature-analysis view are never opened in the reference video, so their exact content is **unconfirmed** and must not be assumed. | Client-stated (MyFace reference video) |
| FR-022 | **Per-feature AI before/after image** — each of the 11 features gets its own AI-generated "after"/potential image (every feature page of the MyFace PDF has a BEFORE/AFTER slot). 11 images per report, generated with the `NFR-013` vendor. | Client-stated (MyFace reference PDF) |

### 4.4 Post-analysis experience
| ID | Requirement | Source |
|---|---|---|
| FR-017 | **Home Overview** — the user's landing screen once their report exists: key stats, before/potential image, a "Priority Features to Improve" list, a protocol summary, and a facial-harmony radar chart with **six axes** (including Symmetry). A persistent header navigation gives access to Home, Report, AI Visuals and Chat; account and billing are in Settings (`FR-021`). Report status and PDF download are reachable from here. The Protocol section is never opened in the reference video, so its exact content is **unconfirmed** and must not be assumed. | Client-stated (MyFace reference video) |
| FR-019 | **AI Beauty Assistant** — a chat where the user asks questions about their own report, grounded in their measurements, narrative and questionnaire answers. Hard rule: decline medical/medication questions and redirect the user to a qualified professional. | Client-stated (MyFace reference video) |
| FR-020 | **AI Visual Features** — 5 AI-generated hairstyle variations; 5 AI-generated outfit variations; and a healthy-aging preview as a **4-card stack at non-uniform steps: current (age 28 in the reference — the user's own photo, not generated), +3 years, +5 years, +10 years**, matching the MyFace reference exactly. 13 generated images per report, using the `NFR-013` vendor. | Client-stated (MyFace reference video) |
| FR-021 | **Settings**, three sections: **Account Info** — full name, email, verification status, member-since date (full name is set at signup and not editable afterward); **Password** — in-app change password with current / new / confirm-new fields that does **not** sign the user out (`AUTH-016`); **Billing** — payment history, a working Stripe option, and PayPal visible but disabled (`BR-012`). | Client-stated (MyFace reference video + direct client instruction) |

**Image volume:** `FR-020` (13) + `FR-022` (11) = **24 AI-generated images per report**.

---

## 5. Authentication & Authorization Requirements (`AUTH-*` / `FE-*`)

Authentication is custom and backend-controlled; no third-party auth-as-a-service is used in any role (client decision).

### 5.1 Backend authentication requirements
| ID | Requirement | Source |
|---|---|---|
| AUTH-001 | Authentication must be a custom, backend-controlled flow. Do **not** use Supabase Auth, Auth0, Firebase Auth, or any third-party auth-as-a-service as the application's authentication mechanism. | Client-stated |
| AUTH-002 | JWT-based authentication using an access token + refresh token pair. | Client-stated |
| AUTH-003 | Signup and login follow the same two-step shape: (1) email + password submitted first (plus full name at signup); (2) once that succeeds, an OTP is emailed and must be verified; only then does signup/login complete and tokens get issued. OTP is a mandatory second step, not an alternative to the password. See `WF-002`. | Client-stated |
| AUTH-004 | Secure token generation, validation, refresh, and expiration handling, fully owned by the backend. | Client-stated |
| AUTH-005 | Backend APIs are solely responsible for authentication and authorization — no delegation to a third-party identity provider. | Client-stated |
| AUTH-006 | Login, OTP verification, logout, token refresh, and session expiry must each be distinct, well-defined flows. | Client-stated |
| AUTH-007 | Protected API endpoints must validate the JWT access token before allowing access. | Client-stated |
| AUTH-008 | Role/permission handling must exist where required. | Client-stated |
| AUTH-009 | The user record carries a `role` field (currently only `"user"`) so an `"admin"` role can be added later without schema rework. | Recommendation (supports deferred admin panel) |
| AUTH-010 | Refresh tokens must be revocable server-side (a store of issued/rotated refresh tokens keyed by a token identifier, not the raw token), so logout and expiry truly invalidate a session. | Decided by delivery team (client: "decide by yourself considering security") |
| AUTH-011 | OTP parameters: **10-minute expiry**, **60-second resend cooldown**, **5 failed attempts** then a **15-minute lockout**; OTP stored **hashed**, never in plaintext. | Decided by delivery team (client: "decide by yourself considering security") |
| AUTH-012 | Token lifetimes: **access token 15 minutes**; **refresh token 7 days**, rotated on every use, with reuse detection — if an already-rotated refresh token is presented again, the whole token family is revoked and the user must re-authenticate. | Decided by delivery team (client: "decide by yourself considering security") |
| AUTH-013 | Cookie-authenticated endpoints (`/auth/refresh`, `/auth/logout`) require CSRF defenses: an `X-Requested-With` header plus an Origin/Referer allow-list. | Decided by delivery team |
| AUTH-014 | `GET /auth/me` returns the current authenticated user, used to rehydrate the frontend after a page reload once the refresh cookie has been exchanged for a new access token. | Decided by delivery team |
| AUTH-015 | Forgot password, three screens: request email → verify a 6-digit emailed code (reusing `AUTH-011`'s OTP rules) → set new password. Verification and password-setting are linked by a short-lived (~10-minute), single-use `reset_token` — never the raw OTP or email — issued only after successful OTP verification and rejected if reused, expired, or presented as a Bearer access token. On success, all of the account's sessions on all devices are revoked. | Decided by delivery team |
| AUTH-016 | Change password (signed in): `POST /auth/change-password` with current password and new password (the UI also asks to confirm the new password). Because the user proves identity with the current password, their session is **not** revoked afterwards. | Client-stated (direct instruction) |

### 5.2 Frontend token management requirements
| ID | Requirement | Source |
|---|---|---|
| FE-001 | Authentication state is managed with **Zustand**. | Client-stated |
| FE-002 | The **access token** and user profile live only in memory in the Zustand auth store. The **refresh token** is only an **httpOnly cookie** set, rotated and cleared by the backend — never in Zustand, `localStorage` or `sessionStorage`. The auth store must never use Zustand `persist`. Sessions survive page refresh, tab close and browser restart via the refresh cookie and a `POST /auth/refresh` call on app start; protected routes wait while this initial restore is in progress. See `ASM-001`. | Client-stated / delivery team |
| FE-003 | Auth state and token handling are centralized in a single auth store/service, never duplicated across components. | Client-stated |
| FE-004 | The access token is attached automatically to authenticated API requests by a centralized API client. | Client-stated |
| FE-005 | Token expiry is handled automatically: proactive refresh ~1 minute before access-token expiry, plus 401 → refresh → retry as fallback, transparent to the UI. Concurrent refresh attempts share one in-flight refresh (single-flight). Access-token expiry alone must never clear auth or redirect. | Client-stated |
| FE-006 | Auth state is cleared and the user redirected to login **only** when the refresh session is invalid (refresh returns 401: expired, revoked, missing or reused) or the user explicitly logs out. Never for access-token expiry, page refresh, tab/browser close, network errors, or 5xx responses. | Client-stated |
| FE-007 | Authentication logic is separate from UI components — UI components never call auth APIs or handle tokens directly. | Client-stated |

### 5.3 Required architectural separation
The client specified this exact layering; it must be preserved in every derived architecture/design document:

```
UI → Zustand Auth Store → API Client → Backend Auth APIs → JWT/OTP Services
```

- **UI** — presentational components; no direct API or token access.
- **Zustand Auth Store** — single frontend source of truth for auth state (user, access token, auth status / initializing flag). Does not hold the refresh token.
- **API Client** — centralized HTTP client: attaches the access token, sends cookies (`credentials: "include"`), handles proactive refresh and refresh-on-401 (single-flight).
- **Backend Auth APIs** — FastAPI endpoints for register (full name + email + password → OTP), login (email + password → OTP), OTP verify, refresh, logout, `/auth/me`, forgot/reset password, change password, and protected-route JWT validation. Sets/rotates/clears the httpOnly refresh cookie. The Next.js frontend calls these directly from the browser over HTTP.
- **JWT/OTP Services** — backend-internal services for token issuance/validation and OTP generation/verification/email delivery, decoupled from route handlers.

---

## 6. Non-Functional / Technical Expectations (`NFR-*`)

| ID | Requirement | Source |
|---|---|---|
| NFR-001 | Backend: **Python + FastAPI**, a separate application from the frontend. | Client-stated |
| NFR-002 | Database: **PostgreSQL**, vendor-neutral. Supabase is not used in any role. Hosting provider undecided (`NFR-010`). | Client-stated |
| NFR-003 | Database migrations: **Alembic**. | Client-stated |
| NFR-004 | ORM: **SQLAlchemy**. | Client-stated |
| NFR-005 | Frontend: **Next.js + TypeScript**, a separate application from the backend; the two communicate over HTTP/CORS. | Client-stated |
| NFR-006 | Frontend state management: **Zustand**, at minimum for authentication (Section 5.2). | Client-stated |
| NFR-007 | Facial analysis engine: MediaPipe + OpenCV, built from scratch. | Client-stated |
| NFR-008 | AI narrative/recommendation generation: **OpenAI** (Vision + GPT, `gpt-4o`). Base URL, API key and model must be configuration values so the vendor/model can be swapped without code changes. | Client-stated |
| NFR-009 | Payments: **Stripe**. PayPal appears only as a visible-but-disabled option (`BR-012`). | Client-stated |
| NFR-010 | Hosting: **not decided** — the client confirmed no hosting decision is needed now. Do not assume Replit or any other host. | Client-confirmed |
| NFR-011 | Code must be clean, modular, and well-documented so the client's own team can continue development after handoff. | Client-stated |
| NFR-012 | OTP delivery channel: **email**. Specific provider (e.g. SendGrid, AWS SES, Postmark) chosen during development — not blocking. | Client-confirmed |
| NFR-013 | AI image generation (`FR-020`, `FR-022`): **OpenAI `gpt-image-1`**, using image editing with high input fidelity so the user's face/identity is preserved while one attribute changes. Must sit behind a swappable image-generation abstraction selected by configuration, so another vendor (e.g. Google Gemini 2.5 Flash Image) can be used without code changes elsewhere. | Client-stated |

---

## 7. Business Rules (`BR-*`)

- **BR-001** [Client-stated] No analysis runs and no report is accessible until payment succeeds (`FR-015`). Enforced server-side.
- **BR-002** [Client-stated] Reports auto-publish immediately — no Draft/Pending Review/Approved gate. That workflow only arrives with the deferred Admin panel (§2.2).
- **BR-003** [Client-stated] The BDD/informational-only disclaimer checkbox is a hard, non-optional gate before questionnaire submission.
- **BR-004** [Recommendation] Because there is no admin review before publishing, the AI pipeline must not run — and no report may be generated — from photos that fail validation (`BR-005`).
- **BR-005** [Client-stated + delegated mechanism] Photo validation is enforced by the backend, not a self-attestation checklist.
  - **Per-photo checks:** exactly one face; face occupies a reasonable proportion of the frame; no occlusion of eyes/mouth (glasses/hat); minimum resolution; acceptable brightness/exposure; pose matches the requested angle. A failing photo is rejected with a clear reason. Thresholds: `ASM-002`.
  - **Set-level identity check — all three photos must be the same person:**
    1. Runs once all three angles have individually passed; it never blocks a single upload.
    2. The photo to flag is chosen by a deterministic match-count vote: each photo counts how many of the other two it matches within the identity threshold; the one with the fewest matches is flagged. Whenever the vote is ambiguous (e.g. one photo matches both others but those two don't match each other), **front** is treated as the reference.
    3. If all three photos are different people, **both non-front photos** are flagged (front is kept as the reference).
    4. The result is a list of mismatched angles (empty when consistent), so more than one photo can be flagged at once.
    5. The result is fully recomputed from the current three photos after every retake. A retake replaces the previous result — nothing is carried over — and errors appear only on the photo(s) currently mismatched.
    6. UI: the review screen highlights every flagged photo and blocks **Continue** while any photo is flagged. A retake never auto-navigates the user forward; once the set is consistent the user stays on the screen with Continue enabled until they click it. Skipping the review screen for an already-complete set is decided only from the initial page load, never from retake results.
    7. Routing: every entry point (after login, direct dashboard visit, end of questionnaire, etc.) treats an identity-inconsistent set as incomplete and returns the user to the photo screen with the error shown.
    8. The identity check is re-run server-side at both payment checkout and analysis start (conflict error, HTTP 409), so the UI gate cannot be bypassed.
  - **Retakes** replace the existing photo for that angle — no duplicate photo records.
- **BR-006** [Client-stated] Third-party usage costs (OpenAI text and image generation, Stripe, PostgreSQL hosting once chosen, email/OTP provider) are the client's responsibility and not part of any development estimate.
- **BR-007** [Client-stated] No committed timeline or re-estimate is produced at this stage; scope is defined by feature list (Sections 2 and 4), not hours or dollars, until the client asks otherwise.
- **BR-008** [Client-stated] The report always has exactly 11 features (`FR-009`) — a fixed structural rule from the Qoves sample report, confirmed by the MyFace PDF.
- **BR-009** [Decided by delivery team] Every user action with a real success/failure outcome shows feedback via a toast notification (top-right) — never silent success or failure. Applies app-wide. Exception: flows that must not reveal the outcome for anti-enumeration reasons (e.g. forgot-password request).
- **BR-010** [Decided by delivery team] Every destructive or irreversible action (delete, logout, revoke, etc.) requires confirmation via a shared confirmation dialog before it runs. Applies app-wide.
- **BR-011** [Decided by delivery team, confirmed by client] "Smile" (shown in the MyFace interactive report) is **not** a 12th feature. Smile-related content (mouth width, smile-arc curvature) is covered under **Lips**. The MyFace PDF itself lists exactly 11 features with no Smile section.
- **BR-012** [Decided by delivery team, confirmed by client] The Billing screen shows PayPal as a **visible but disabled** option (muted button with a "not available"-style status pill) next to a working Stripe option, matching the MyFace reference. No real PayPal integration unless the client separately requests it.

---

## 8. Workflows (`WF-*`)

### WF-001 — End-to-end user journey
1. Landing page → sign up (full name + email + password → OTP) or log in (email + password → OTP).
2. Onboarding: 23-question branching questionnaire → BDD / informational-only disclaimer checkbox → submit.
3. Photo Requirements screen (7-point checklist).
4. Photo upload / capture for front, left 3/4, right 3/4 → per-photo validation → set-level identity check; any flagged photo must be retaken before continuing (`BR-005`).
5. Payment screen → Stripe hosted Checkout → payment succeeds. No teaser or partial content before this point.
6. User clicks **Start Analysis** → MediaPipe/OpenCV measurement → OpenAI narrative (measurements + questionnaire context) → facial assessments → AI image generation (per-feature before/after and AI Visuals).
7. Report assembled and auto-published (`BR-002`).
8. Home Overview → Report (with PDF download), AI Visuals, AI Beauty Assistant chat, Settings (Account Info / Password / Billing).

### WF-002 — Authentication flow
1. **Step 1 — Email + password.**
   - *Signup:* user submits full name, email and password → backend checks the email isn't registered, hashes the password, creates an unverified user.
   - *Login:* user submits email and password → backend checks them against the stored hash.
   - No tokens are issued yet; proceed to Step 2.
2. **Step 2 — OTP.** Backend generates an OTP, stores it hashed with an expiry (`AUTH-011`), and emails it (`NFR-012`). The user submits it.
   - Backend checks it against the hash, expiry, and attempt/lockout limits.
   - On success: signup marks the account verified; login confirms the session. The backend issues the access token and sets the refresh cookie (`AUTH-002`, `AUTH-012`).
   - On failure: attempt counter increments; after 5 failures a 15-minute lockout applies.
3. **Authenticated requests:** the API client attaches the access token (`FE-004`); the backend validates it on protected routes (`AUTH-007`).
4. **Token refresh:** near access-token expiry, or on a 401, the frontend calls `POST /auth/refresh` with the refresh cookie → backend validates against its revocation store (`AUTH-010`), issues a new access token and rotates the cookie → frontend updates the store transparently (`FE-005`). Reuse of an already-rotated token revokes the whole token family.
5. **Logout:** user confirms (`BR-010`) → backend revokes the refresh session and clears the cookie → frontend clears the auth store and redirects to login (`FE-006`). Never triggered by page unload, visibility or route changes.
6. **Invalid refresh session:** refresh returns 401 (expired, revoked, missing, reused) → frontend clears the auth store and redirects to login. Network errors and 5xx never clear auth.
7. **Forgot password:** request email → verify 6-digit code → set new password via single-use `reset_token`; all sessions revoked on success (`AUTH-015`).
8. **Change password (signed in):** current + new + confirm → `POST /auth/change-password`; session stays active (`AUTH-016`).

---

## 9. Data Entities (`DATA-*`, high-level — full schema belongs in the database design document)

- **DATA-001 User** — full name, email, hashed password, verification status, `role` (`AUTH-009`), timestamps.
- **DATA-002 OTP Record** — linked to a user or pending signup; hashed OTP; purpose (signup / login / password_reset); expiry; attempt count; consumed flag.
- **DATA-003 Refresh Token / Session Record** — token identifier (not the raw token), user reference, issued/expiry timestamps, revoked flag, rotation lineage (reuse detection, `AUTH-012`).
- **DATA-004 Questionnaire Response** — the 23 branching answers, linked to a user.
- **DATA-005 Photo** — one per angle per user (replaced on retake), validation status and results (`BR-005`).
- **DATA-006 Facial Analysis Result** — per-feature measurements and the AI narrative, linked to the user's photo set; one per user.
- **DATA-007 Report** — the 11 feature sections, facial assessments (`FR-018`), PDF artifact reference, publish state (published on generation, `BR-002`); linked to the user, questionnaire response and analysis result; one per user.
- **DATA-008 Payment** — Stripe session/payment identifier, status, amount, currency; linked to the user (created before any report exists, since payment gates analysis).
- **DATA-009 Report Feature Visual** — the AI-generated before/after image for each of the 11 features (`FR-022`), linked to the report.
- **DATA-010 AI Visual Asset** — generated hairstyle, outfit and healthy-aging images (`FR-020`), linked to the user/report.
- **DATA-011 Chat Conversation** — AI Beauty Assistant conversations and messages (`FR-019`), linked to the user/report.
- **Deferred (§2.2):** admin/reviewer accounts, report review history.

---

## 10. Constraints (`CON-*`)

- **CON-001** [Client-stated] No existing codebase — this is a from-scratch build; no "existing MVP" claims from pre-negotiation materials apply.
- **CON-002** [Client-stated] No third-party authentication-as-a-service (Supabase Auth, Auth0, Firebase Auth, etc.) may be used for authentication.
- **CON-003** [Client-stated] No client-supplied branding/design assets exist — the delivery team owns UI/branding decisions for now.
- **CON-004** [Client-stated] Third-party service costs are billed to and owned by the client, not bundled into any dev estimate.
- **CON-005** [Client-stated] No committed delivery timeline or dollar estimate exists, and none has been requested.
- **CON-006** [Recommendation] Because reports auto-publish with no human review, enforced photo validation (`BR-005`) is a harder requirement than it would be with downstream review.
- **CON-007** [Client-stated] Hosting platform is undecided and not currently needed — do not assume any specific host.

---

## 11. Assumptions & Recommendations Not Yet Confirmed by the Client (`ASM-*`)

These must stay visibly labeled as non-client-stated in derived documents until confirmed.

- **ASM-001 — Token storage and residual XSS risk.** The refresh token is an httpOnly cookie (not readable by JavaScript); only the short-lived access token is held in memory. Residual XSS exposure is limited to that in-memory access token for at most 15 minutes. Mitigate with standard XSS hardening (CSP, output encoding, dependency hygiene). Forbidden for auth: `localStorage`, `sessionStorage`, Zustand `persist`.
- **ASM-002 — Photo validation thresholds.** The per-photo checks in `BR-005` are a delivery-team recommendation; the client confirmed exact thresholds are set during development. They will be recorded in the Photo Validation Specification.
- **ASM-003 — Payment model.** One-time payment per report (`FR-016`) is a recommendation; price remains open (`OQ-002`).
- **ASM-005 — Three photo angles — NOT YET CONFIRMED by the client.** The build uses 3 angles (front, left 3/4, right 3/4) instead of the 7-pose set in the Qoves reference. This is enough for the required measurements and reduces upload friction, but is a reduction from the reference product. The required-angle set must be a single configurable value so moving to 7 angles later is a config change, not a redesign. See `OQ-010`.
- **ASM-007 — Recommendation tiering by keyword heuristic — NOT YET CONFIRMED by the client.** The AI returns a flat recommendation list per feature; these are sorted into `FR-012`'s three tiers by keyword rules (e.g. "serum"/"cream" → OTC; "consider seeing a dermatologist"/"laser" → in-clinic; everything else → at-home). A first-pass judgment call, not a clinical classification — expect some misclassification and a later tuning pass. See `OQ-012`.
- **ASM-008 — Pay-before-analysis gate.** `FR-015`/`BR-001` allow a model with no pre-payment content; per direct client instruction, payment gates the start of analysis itself and analysis is started by an explicit user click. Recorded for traceability; no further sign-off needed.
- **ASM-009 — Profile scope.** Full name is collected at signup and shown in Account Info and greetings but is not editable afterwards; password is changed in-app (`AUTH-016`). Recorded for traceability; no further sign-off needed.
- **ASM-010 — Identity check and ear measurement are first-pass heuristics.** No separate face-recognition model is used (avoids a heavier dependency). Instead, a signature of 5 facial-landmark distance ratios (eye, nose, mouth, jaw and face width, each normalized by the distance between the eyes) is computed with the same MediaPipe Face Landmarker used for measurement. Initial mismatch threshold: **0.6** (same-person pairs measured roughly 0.08–0.33; different-person pairs roughly 0.71–0.93). The Ears measurement from 3/4 photos (`FR-007`) is likewise a first-pass formula. Neither has been validated on a large, diverse photo set — expect a tuning pass.
- **ASM-011 — Image-generation quality and cost not yet validated.** Output quality of `NFR-013`'s model on real user photos, and real cost at 24 images per report, still need to be validated.

---

## 12. Traceability Map — how this document feeds derived documents

| Derived document | Primary requirement IDs |
|---|---|
| PRD | `FR-*`, `WF-001`, Section 2 |
| BRD | `BC-*`, `BR-*`, Section 2, `CON-*` |
| Architecture | `NFR-*`, Section 5.3, `WF-002` |
| Technical Design | `NFR-*`, `AUTH-*`, `FE-*`, `ASM-*` |
| API Specification | `AUTH-001`–`AUTH-016`, `WF-002`, endpoints implied by each `FR-*` |
| Database Design | `DATA-*` |
| UI/UX Requirements | `FR-001`–`FR-005`, `FR-017`–`FR-022`, `FE-*`, `BR-009`–`BR-012` |
| Authentication | `AUTH-*`, `FE-*`, `WF-002`, `ASM-001` |
| Security | `AUTH-010`–`AUTH-016`, `ASM-001`, `BR-005`, `CON-006` |
| Testing | Every `FR-*`, `AUTH-*` and `BR-*` maps to at least one test case |
| Deployment | `NFR-010`, `CON-007`, `CON-002`, `NFR-001`–`NFR-003` |
| Onboarding Questionnaire Specification | `FR-003`, `FR-004`, `BR-003` |
| Photo Capture Specification | `FR-005`, `ASM-005` |
| Photo Validation Specification | `FR-006`, `BR-004`, `BR-005`, `ASM-002`, `ASM-010` |
| Report & UI Specification | `FR-009`–`FR-022`, `BR-008`–`BR-012` |

Every derived document should cite requirement IDs from this table so a later change here can be traced to what it affects.

---

## 13. Decisions & Open Questions (`OQ-*`)

### Decided
| ID | Question | Decision |
|---|---|---|
| OQ-001 | Login mechanism | Email + password, then mandatory OTP, for both signup and login (`AUTH-003`, `WF-002`). |
| OQ-003 | Token/OTP lifetimes and limits | Delegated to delivery team "considering security" — see `AUTH-010`–`AUTH-012`. |
| OQ-004 | OTP delivery channel | Email; provider chosen during development (`NFR-012`). |
| OQ-005 | ORM | SQLAlchemy (`NFR-004`). |
| OQ-006 | Frontend framework | Next.js, separate from the FastAPI backend (`NFR-005`). |
| OQ-007 | Hosting | Deferred — not needed now (`NFR-010`, `CON-007`). |
| OQ-008 | Photo-validation thresholds | Set during development (`ASM-002`); recorded in the Photo Validation Specification. |
| OQ-009 | Refresh token storage | httpOnly cookie; access token in memory only (`FE-002`, `ASM-001`). |
| OQ-011 | AI vendors | OpenAI `gpt-4o` for narrative, OpenAI `gpt-image-1` for images (`NFR-008`, `NFR-013`). |

### Still open
| ID | Question | Status |
|---|---|---|
| OQ-002 | Report price / pricing specifics | **Kept open by the client.** One-time payment per report is the working model; price stays configurable, never hardcoded. |
| OQ-010 | Photo angle count — 3 angles vs. the 7-pose Qoves reference | Not yet put to the client (`ASM-005`). |
| OQ-012 | Recommendation tiering — keyword heuristic vs. AI-based classification | Not yet put to the client (`ASM-007`). |

---

### Summary
This document is the single source of truth for the AI Facial Analysis platform: a from-scratch build on two separate applications — a Next.js/TypeScript frontend and a Python/FastAPI + SQLAlchemy/Alembic backend — over a vendor-neutral PostgreSQL database. It covers custom authentication (password + mandatory email OTP, JWT with rotating httpOnly refresh cookie, forgot and change password, strict UI → Zustand Auth Store → API Client → Backend Auth APIs → JWT/OTP Services layering); a 23-question onboarding questionnaire with a mandatory disclaimer; enforced 3-angle photo validation with a cross-photo identity check; Stripe payment before analysis; a MediaPipe/OpenCV + OpenAI analysis pipeline; an auto-published 11-feature report with PDF export, interactive Facial Assessments and a per-feature AI before/after image; AI Visual Features (5 hairstyles, 5 outfits, 4-card healthy-aging stack; 24 AI images per report in total); an AI Beauty Assistant that declines medical questions; a Home Overview; and Settings (Account Info / Password / Billing, with PayPal visible but disabled). Admin panel and review workflow, email notifications, Meta Pixel/GTM, a formal data-retention policy and a working PayPal integration are out of scope. Open items: pricing (`OQ-002`), photo angle count (`OQ-010`) and recommendation tiering (`OQ-012`). Detailed specifications for the questionnaire, photo capture, photo validation and report/UI will be provided separately and derived from this document.
