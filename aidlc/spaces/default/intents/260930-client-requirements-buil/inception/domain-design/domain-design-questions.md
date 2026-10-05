# Domain Design — Questions

This stage decides the **logical building blocks** of the code — what each part owns and which part calls which. It does not decide how they are deployed (that's the next stage, Units Generation) or the database schema (Functional Design).

Inputs: `requirements.md`, `stories.md` (80 stories), `mockups.md` and `interaction-spec.md`, the team practices, and the working specifications in `aidlc/spaces/default/knowledge/`. The client already fixes the auth layering (UI → Zustand Auth Store → API Client → Backend Auth APIs → JWT/OTP Services, client §5.3) and the stack, so those aren't asked here.

Pick one letter per question (or X and describe your own answer).

---

### Question 1 — How the analysis work is split
After "Start Analysis", four different kinds of work happen: face measurement (MediaPipe/OpenCV), AI text (narratives, recommendations), AI images (24 per report), and assembling the report and PDF. They change for different reasons (CV tuning vs prompt changes vs image vendor swaps).

A. Separate building blocks — Face Measurement, Report Writing (AI text), Image Generation, Report — coordinated by an Analysis Pipeline that owns the run and its steps (Recommended)
B. One "Analysis" block containing all of it
X. Other (please specify)

[Answer]: A

### Question 2 — The shared face-landmark service
The same MediaPipe landmark detection is used by photo checks, the same-person check, and measurements (stories US1.11).

A. Its own small building block ("Face Geometry"): landmarks, identity signature and pose — used by both Photo Intake and Face Measurement (Recommended)
B. Part of Photo Intake; Face Measurement calls Photo Intake for landmarks
X. Other (please specify)

[Answer]: A

### Question 3 — Who decides the user's next step
Routing needs one answer to "where is this user in the journey?" (consent → questionnaire → photos → payment → analysis → report; story US11.8).

A. A read-only "Journey" block that asks each owning block for its state and computes the next step; it owns no data of its own (Recommended)
B. A stored progress record, owned by the account block, that every other block updates as the user moves forward
X. Other (please specify)

[Answer]: A

### Question 4 — How payment unlocks analysis
Payment status is set only by the Stripe webhook, and analysis starts only on the user's click (client `FR-015`).

A. Payments owns the payment records and answers "has this user paid for a report?"; the Analysis Pipeline and Report ask it directly when needed (Recommended)
B. The payment webhook creates a "ready to analyse" record in the Analysis Pipeline, so the pipeline never calls Payments
X. Other (please specify)

[Answer]: A

### Question 5 — Frontend structure
A. Feature folders that mirror the backend blocks (auth, onboarding, photos, payment, analysis, report, visuals, chat, settings, journey), plus a shared UI kit and the single auth store and API client (Recommended)
B. Organised only by page/route, with shared code in a common folder
X. Other (please specify)

[Answer]: A

### Question 6 — Two tabs refreshing at once (open from the stories, US3.11)
The client requires that re-using an already-rotated refresh token signs out every session (`AUTH-012`). Two tabs refreshing at the same moment can look exactly like that and log the user out — which the client also forbids (`FE-006`). The product lead asked that you choose the approach.

A. The browser tabs coordinate so only one tab refreshes at a time and shares the result with the others; the server's reuse detection stays fully strict (Recommended)
B. The server accepts the previous refresh token for a short grace window (for example 10 seconds) after rotation; simpler, but slightly weakens reuse detection
C. Both: tab coordination first, plus a very short grace window (for example 3 seconds) as a safety net
X. Other (please specify)

[Answer]: A
