# Bolt Plan — AI Facial Analysis Platform

A **Bolt** is one build pass over a piece of the work that ends in something that runs and can be demonstrated. Here each Bolt builds exactly one unit of work (`inception/units-generation/unit-of-work.md`; delivery Q3). Bolts run one after another: each is designed, built, verified and approved before the next starts (delivery Q4).

**How work reaches `main`** (team practices, Way of Working): each Bolt is built on a short-lived branch and merged into the protected `main` through a GitHub pull request, squash-merged, with the GitHub Actions checks green.

**Verification:** every finished unit is verified by one project command. The command is created in Bolt 1 and approved by you at the first checkpoint (delivery Q7). The expected shape is `make verify`, running lint, type checks, all tests with the 80% coverage floor, and the Playwright journeys that exist so far.

**Sequencing:** walking skeleton first, then risk-first within the dependency order (delivery Q1). The reasons are in `risk-and-sequencing-rationale.md`.

---

## Bolt 1 — Walking skeleton (U1 `u1-walking-skeleton`) · WALKING SKELETON
- **Unit:** U1. **Stories (12):** US1.1, US1.2, US1.5, US1.8, US1.3, US1.4, US1.6, US1.9, US3.1, US3.2, US3.4, US3.8.
- **Walking skeleton:** yes. A walking skeleton is a minimal version that runs the whole way through, built first to prove the pieces connect. It proves:
  - the Next.js ↔ FastAPI HTTP boundary with CORS and credentials;
  - PostgreSQL with Alembic;
  - the single auth store and API client (client §5.3 layering);
  - JWT issue and validation;
  - the email-code flow through the email adapter and mail catcher;
  - the shared error format;
  - the GitHub Actions gates.
- **Prerequisites:**
  - rename the trunk to `main`;
  - harden `.gitignore` before the first commit;
  - Docker installed locally;
  - GitHub repository access for branch protection.
- **Definition of Done:**
  - Sign up → code (read from the mail catcher) → verify → log in → "who am I" works in the browser.
  - The Playwright skeleton journey passes, and `make verify` passes locally and in CI.
  - `main` is protected, and Gitleaks blocks a planted secret.
  - The OTP and JWT services were built test-first.
  - Coverage is ≥ 80% for both apps.
  - You approve the verification command and the skeleton checkpoint.
- **Confidence hypothesis:** the two-app architecture, the auth layering and the CI gates work together end to end, so later Bolts can add features without rework to the foundations.
- **Expected demo:** register a new account in the browser, enter the emailed code, log in, see "Hi, {name}", then show the green pipeline and a pull request blocked by a failing check.

## Bolt 2 — Session security (U2 `u2-session-security`)
- **Unit:** U2. **Stories (9):** US11.7, US3.3, US3.5, US3.6, US3.7, US3.9, US3.10, US3.11, US11.5.
- **Definition of Done:**
  - Every `AUTH-010`–`AUTH-016` and `FE-002`–`FE-007` rule has a passing automated test with exact time boundaries.
  - Refresh single-flight and cross-tab coordination were built test-first.
  - Reuse of a rotated refresh token revokes the family.
  - Two tabs stay signed in.
  - Logout, reset and change-password work.
  - Toasts and dialogs pass the axe check.
- **Confidence hypothesis:** the session stays both secure (strict reuse detection) and invisible to the user (no spurious logouts across reloads, tabs or network blips). This addresses the worry about sign-in security.
- **Expected demo:**
  - reload and restart the browser and stay signed in;
  - open two tabs and let tokens expire with no logout;
  - replay an old refresh cookie and get signed out everywhere;
  - reset a password and see other devices signed out.

## Bolt 3 — Consent and questionnaire (U3 `u3-onboarding`)
- **Unit:** U3. **Stories (4):** US4.1, US4.2, US4.3, US4.4.
- **Definition of Done:**
  - Consent is required and versioned.
  - The 23 questions load from seed data ([QS]), and branching works: Q19 is shown or skipped by Q4.
  - The disclaimer is enforced by the server, and the supportive message appears when it can't be confirmed.
  - The medical flags are set on Q8–Q12 and their follow-ups, and a test proves `answers_for_ai` never returns them.
- **Confidence hypothesis:** questionnaire content can change without code, and health data is structurally isolated (ADR-007).
- **Expected demo:** consent → answer the questionnaire on a phone-sized screen → change Q4 and watch Q19 appear or disappear → submit, and see the disclaimer gate and the "I can't confirm" message.

## Bolt 4 — Photos and the same-person check (U4 `u4-photos`)
- **Unit:** U4. **Stories (11):** US1.10, US1.11, US5.1, US5.2, US5.3, US5.5, US5.10, US5.6, US5.11, US5.8, US5.9.
- **Definition of Done:**
  - Upload and camera capture work for the three angles, and HEIC is converted.
  - Per-photo checks return photo-focused reasons.
  - The same-person decision was built test-first and passes the 8-case table and the [IV] worked examples.
  - The review screen never auto-advances.
  - Media is private (another user gets 404), and metadata is stripped.
  - A calibration check runs the per-photo thresholds and the identity threshold against a small, consented, diverse photo set, and the results are recorded (`ASM-002`, `ASM-010`).
- **Confidence hypothesis:** only valid, same-person photo sets can move forward, and the thresholds work on real photos without frequent false rejections. This addresses the worry about photo-check accuracy.
- **Expected demo:** take the three photos on a phone; try two faces, a wrong angle and sunglasses and see each reason; swap in a different person's side photo and see only that photo flagged; retake it and see Continue enable without jumping ahead.

## Bolt 5 — Payment (U5 `u5-payments`)
- **Unit:** U5. **Stories (5):** US6.1, US6.2, US6.3, US6.4, US6.5.
- **Prerequisite:** Stripe test-mode keys and Stripe CLI for local webhooks (`external-dependency-map.md`).
- **Definition of Done:**
  - Checkout works in Stripe test mode at the configured price.
  - The webhook verifies signatures and is idempotent, including under concurrent duplicates.
  - The confirming state works, and cancel returns to the payment screen.
  - 402 is enforced, and the 409 re-check happens at checkout.
  - The Stripe adapter has a fake for the default test run.
- **Confidence hypothesis:** the paywall can't be bypassed, and a paying user never sees an error in the gap before the webhook arrives.
- **Expected demo:** pay with a Stripe test card and watch "Confirming your payment…" turn into "Start Analysis"; cancel and see nothing charged; call the analysis API directly without paying and get 402.

## Bolt 6 — Analysis core (U6 `u6-analysis-core`)
- **Unit:** U6. **Stories (13):** US1.7, US1.12, US7.1, US7.6, US7.2, US7.3, US7.7, US7.8, US7.5, US7.10, US7.4, US7.9, US7.11.
- **Prerequisite:** OpenAI API key and a budget limit set on the account.
- **Definition of Done:**
  - Start is idempotent, and the run captures its photo snapshot.
  - Steps resume after a worker restart without repeating paid calls.
  - The measurements are deterministic, and the assessments use the Functional Design formulas.
  - The privacy test proves no medical answer reaches the AI (canaries).
  - Report text is schema-validated with retries; a failed run offers one free re-run.
  - The opt-in evaluation suite runs once against the real model on consented fixtures, and narrative quality, tone and timing are recorded.
- **Confidence hypothesis:** a real analysis produces trustworthy, safe text within budget, and recovers from failures without double-charging AI cost. This addresses the worries about AI quality and cost.
- **Expected demo:** click Start Analysis and watch the steps progress; kill the worker mid-run and see it resume; show the stored measurements and the 11 narratives; force a failure and use the free re-run.

## Bolt 7 — AI images (U7 `u7-ai-images`)
- **Unit:** U7. **Stories (5):** US9.1, US9.2, US9.3, US9.4, US9.5.
- **Definition of Done:**
  - 24 image slots are produced per run, registered through the step hook.
  - There are 3 automatic retries, then "not available yet", and at most 3 manual retries.
  - Concurrency and back-off are configurable.
  - The vendor can be swapped by configuration.
  - A timed real-vendor run on consented fixtures records the end-to-end analysis time against the 10-minute target, the cost per report, and image likeness (`ASM-011`).
- **Confidence hypothesis:** the 24 images fit inside the 10-minute target at an acceptable cost and still look like the user. This addresses the worries about the 10-minute target and cost.
- **Expected demo:** a full run produces the hairstyle, outfit and aging images; force one image to fail and see "not available yet" and a working retry; show the recorded time and cost.

## Bolt 8 — Report, Home dashboard and PDF (U8 `u8-report-home`)
- **Unit:** U8. **Stories (11):** US8.1, US8.7, US8.2, US8.3, US8.8, US8.4, US8.6, US8.5, US11.1, US11.2, US11.3.
- **Definition of Done:**
  - The report auto-publishes with exactly 11 features and the preamble first.
  - AI images are labelled, and tiered recommendations show the static professional-advice text.
  - The interactive report has a table of contents and chart tables.
  - The Home dashboard matches [RD] §4, with TBD items omitted.
  - The PDF renders from a backend-owned template, is cached, and regenerates when an image changes.
  - axe finds no WCAG 2.1 AA violations on the report and Home.
- **Confidence hypothesis:** the delivered report reads as a coherent, careful, branded product on a phone and in the PDF.
- **Expected demo:** land on Home after analysis; open the report and jump through the table of contents; switch a chart to its table view; download the PDF; retry an image and download again to show the updated PDF.

## Bolt 9 — AI Beauty Assistant (U9 `u9-beauty-assistant`)
- **Unit:** U9. **Stories (3):** US10.1, US10.2, US10.3.
- **Definition of Done:**
  - Chat answers are grounded in the user's report (proved with the fake), and history persists.
  - The medical-decline instruction is always present, and the opt-in evaluation set declines 100% of the medical prompts.
  - The daily limit of 50 per UTC day holds, including under concurrent sends, and failed calls don't count.
- **Confidence hypothesis:** the assistant is useful about the user's own results and never gives medical advice.
- **Expected demo:** ask about the symmetry score; ask a medication question and see the polite decline; hit a lowered test limit and see the reset time.

## Bolt 10 — Journey routing, landing, settings and final checks (U10 `u10-journey-settings`)
- **Unit:** U10. **Stories (7):** US11.8, US2.1, US2.2, US5.7, US11.4, US11.6, US1.13.
- **Definition of Done:**
  - Every entry point lands on the next unfinished step, from one parametrised test over the Journey table; temporary links from earlier Bolts are removed.
  - The landing page includes "How it works", with reduced motion respected.
  - Account info and billing work, with PayPal disabled.
  - The requirement-to-test map has no unmapped client ID.
  - The full Playwright journeys pass on phone and desktop in Chromium, WebKit and Firefox.
  - axe is clean on every main screen.
- **Confidence hypothesis:** the whole product works as one journey, and every client requirement is demonstrably tested. This is the handover-readiness check.
- **Expected demo:** a brand-new user goes from the landing page to the report on a phone; a returning user lands on Home; a user with an inconsistent photo set is sent back to photos; show the traceability report and the green test matrix.

---

## Plan at a glance

| Bolt | Unit | Stories | Walking skeleton | Main risk addressed |
|---|---|---|---|---|
| 1 | U1 walking skeleton | 12 | ✅ | Integration of the two apps, auth layering, CI |
| 2 | U2 session security | 9 | | Auth security (worry C) |
| 3 | U3 onboarding | 4 | | Health-data isolation |
| 4 | U4 photos | 11 | | Photo-check accuracy (worry B) |
| 5 | U5 payments | 5 | | Paywall integrity |
| 6 | U6 analysis core | 13 | | AI quality and cost (worries A, D) |
| 7 | U7 AI images | 5 | | 10-minute target, image cost and likeness (worries A, D) |
| 8 | U8 report and home | 11 | | Product coherence, PDF |
| 9 | U9 beauty assistant | 3 | | Medical safety in chat |
| 10 | U10 journey and settings | 7 | | Whole-journey readiness, full test traceability |

All 80 stories are covered, and each is in exactly one Bolt.
