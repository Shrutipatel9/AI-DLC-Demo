# User Stories — Plan and Questions

## Story plan (draft)

- **Source:** `inception/requirements-analysis/requirements.md` (FR1–FR14, NFR1–NFR12), itself traced to `client_requirements.md`.
- **Format:** "As a [persona], I want [goal], so that [benefit]"; stable IDs `US{group}.{seq}`; acceptance criteria `AC{group}.{seq}.{n}` in Given/When/Then; each story checked against INVEST (Independent, Negotiable, Valuable, Estimable, Small, Testable).
- **Priority:** MoSCoW per story. The MVP line itself is decided later in Delivery Planning.
- **Collaboration:** after I draft, the designer (experience and persona fit), developer (can it be built, is it small enough) and quality engineer (can each criterion be tested) each review the draft independently. Anything they disagree on that is a judgment call comes back to you.

Pick one letter per question (or X and describe your own answer).

---

### Question 1 — Personas
The client document names one functional role, the End User; the Admin is a future, out-of-scope role. How should users be described?

A. One End User role, split into 2–3 personas by motivation and emotional state (for example a self-improver with clear goals, a curious first-timer, and a user with higher appearance-related anxiety), because tone and safety rules depend on this (FR8.5, FR12.2) (Recommended)
B. A single End User persona
C. End User personas plus the future Admin as a "Won't Have" persona
X. Other (please specify)

[Answer]: A

### Question 2 — How stories are grouped
A. By the user's journey: Account & sign-in, Consent & questionnaire, Photos, Payment, Analysis, Report, AI Visuals, Chat, Home & Settings (Recommended)
B. By persona
C. By technical area (auth, media, payments, AI)
X. Other (please specify)

[Answer]: A

### Question 3 — Story size
A. Small: each story about 1–3 days of work, which gives roughly 50–70 stories (Recommended)
B. Medium: about 3–5 days each, roughly 30–40 stories
X. Other (please specify)

[Answer]: A

### Question 4 — Groundwork that isn't a user feature
The team agreed to build a thin end-to-end slice first and to deliver the GitHub Actions checks, Docker Compose and security tooling in the first piece of work. These are not user features.

A. Write them as clearly marked "enabler" stories (from the developer's or client team's point of view) so they can be planned and traced like the rest (Recommended)
B. Keep stories purely user-facing; leave groundwork to the unit and delivery plans
X. Other (please specify)

[Answer]: A

### Question 5 — Priorities
A. Every client in-scope feature (client §2.1) is Must Have; delivery-team additions are ranked individually (consent step: Must; chat daily limit and image-metadata removal: Should) (Recommended)
B. Everything, including delivery-team additions, is Must Have
X. Other (please specify)

[Answer]: A

### Question 6 — Content that waits on separate specifications
The questionnaire's 23 questions, the photo-validation thresholds and some report views (Face Shape, Skin, Protocol) wait on specifications the client will send later.

A. Stories for the configurable engine now (working with marked placeholder content), plus separate "load the real content" stories marked blocked until the specification arrives (Recommended)
B. Only the engine stories; loading real content is not a story
X. Other (please specify)

[Answer]: A

---

## Follow-up questions from the designer, developer and quality engineer

### Question 7 — Specification drafts found in the team knowledge folder
`aidlc/spaces/default/knowledge/` already holds `onboarding_questionnaire_spec.md` (the 23 questions, branching, exact disclaimer wording; Draft with 2 open items), `photo_capture_spec.md` (3-angle flow; Draft), `photo_identity_validation_spec.md` (the same-person algorithm, including the "hub" case; Active), `report_design_spec.md` and `report_template.md` (report structure copied from the MyFace reference; Active). `client_requirements.md` v1.0 says these specifications "do not exist yet", and some drafts describe an earlier implementation.

A. Use them as the working specifications: fold their content into the stories, unblock the matching stories, and keep their open items (and the fact they are unconfirmed by the client) clearly labelled (Recommended)
B. Use them only as reference; keep those stories blocked until the client confirms the specifications
C. Ignore them
X. Other (please specify)

[Answer]: A

### Question 8 — A paid analysis run that fails
If analysis fails after the user has paid (after the automatic image retries), what should the user be able to do?

A. Failed steps retry automatically; if the run still fails, the user sees a clear message and can re-run once for free from the progress screen; after that, a "contact support" message (Recommended)
B. The user can re-run for free as many times as needed
C. Show a "contact support" message only
X. Other (please specify)

[Answer]: A

### Question 9 — Story size after the developer's review
The developer found about 10 stories bigger than 1–3 days (for example measurements, narratives, token refresh, the identity check) and a few missing technical stories (photo storage, a shared face-landmark service, pipeline orchestration, journey routing). Splitting them takes the total to about 75–77 stories, above the 50–70 estimate.

A. Split them and add the missing stories, keeping every story at 1–3 days (Recommended)
B. Keep the current story sizes; only add the missing stories
X. Other (please specify)

[Answer]: A

### Question 10 — Limits that need exact values
The chat daily limit and image retries need exact rules before their tests can be written.

A. A "day" is the UTC calendar day; failed chat calls don't count toward the limit; manual retries are capped at 3 per image (Recommended)
B. A "day" is a rolling 24 hours; failed calls count; manual retries are unlimited
X. Other (please specify)

[Answer]: A

### Question 11 — Protecting anxious users on report screens
Today the anxious persona is protected only in the AI text. The designer proposes that the "Understanding Your Results" preamble comes before any score, that every AI image carries a visible "AI-generated illustration" label, and that rejection and mismatch messages describe the photo, not the person.

A. Adopt these as acceptance criteria (Recommended)
B. Keep protection to the AI text only
X. Other (please specify)

[Answer]: A

### Question 12 — Accessibility and phone criteria
A. Add specific accessibility and phone-layout criteria to the high-risk screens (camera, photo review, progress, report charts, OTP entry, chat, dialogs), on top of the app-wide WCAG 2.1 AA rule (Recommended)
B. Rely on the app-wide WCAG 2.1 AA rule only
X. Other (please specify)

[Answer]: A

### Question 13 — A user who can't tick the disclaimer
The disclaimer asks the user to confirm they have no Body Dysmorphic Disorder–related concerns. A user who honestly can't tick it is currently just blocked.

A. Show a calm, supportive message explaining why the analysis isn't offered, with a pointer to professional help; they can't proceed (labelled for client confirmation) (Recommended)
B. Just keep the Submit button disabled with no extra message
X. Other (please specify)

[Answer]: A

### Question 14 — Password rule and photo formats
Neither is defined in the client document.

A. Password: at least 8 characters with at least one letter and one number, common passwords rejected. Photos: JPEG, PNG and iPhone HEIC (converted on upload), up to 10 MB each (Recommended)
B. Password: at least 12 characters, no other rules. Photos: JPEG and PNG only, up to 10 MB
X. Other (please specify)

[Answer]: A
