**Collaborator:** aidlc-developer-agent

## Contribution

Focus: implementability, story size (about 1–3 days each, Q3), dependency correctness, the walking-skeleton slice, whether the acceptance criteria can be built with the mandated stack, and technical work the draft leaves out. Every proposal below cites story IDs so it can be merged directly. Labels follow the project's Mandated rule: anything not stated by the client is marked `[Recommendation]` or `[Assumption]`.

### A. Walking skeleton: the listed set does not form a closed slice

The skeleton set (US1.1, US1.2, US1.3, US1.5, US3.1, US3.2, US3.4, US3.8) includes stories whose `Deps` point outside the set, and it leaves out work that `team.md` § Walking Skeleton requires.

1. **US3.8 depends on US3.5, which is not in the skeleton.** US3.5 brings session restore through the refresh cookie on reload. The skeleton does not need that: "who am I" works with the in-memory access token straight after login. **Proposal:** change US3.8 `Deps` from US3.5 to **US3.4**. Keep AC3.8.1's "any page loads" wording for after US3.5 by rewording it to "Given I have just signed in, then my full name appears in the greeting and user menu". Reloads are already covered by AC3.5.1.
2. **US3.1 depends on US1.6, which is not in the skeleton.** US1.6 bundles four adapters (OpenAI text, image, email, Stripe). The skeleton only needs email. **Proposal:** split US1.6 (see B.1). Only the email-adapter half joins the skeleton.
3. **US1.4 (security tooling) is missing, but `team.md` requires it in the skeleton.** `team.md` § Walking Skeleton says: "The skeleton also carries … the hardened `.gitignore`, pre-commit secret scanning and the GitHub Actions workflow." AC1.1.3 covers `.gitignore`. Gitleaks (AC1.4.1) is not covered by anything in the set. **Proposal:** add US1.4 to the skeleton. It is small, about 1 day.
4. **There is no story for the frontend auth store or the single API client, but the skeleton has to run through Next.js.** The skeleton ACs read as backend behaviour. Nothing builds the Zustand auth store (FE-001, in memory only, never `persist`), the single API client (FE-004), or the lint rule that enforces the layering (FE-007, Section 5.3). US3.6 assumes the client already exists. **Proposal:** add a new enabler, **US1.9 — Frontend auth store and single API client** (P4 Dev, Must, Deps: US1.1). Suggested ACs:
   - Given the auth store, then it holds the access token and user profile in memory only, and it uses no `persist` middleware and no Web Storage.
   - Given any UI component, when lint runs, then importing an auth API function or reading a token from a component fails the lint check.
   - Given any HTTP call in the frontend, then it goes through the one API client, which attaches the access token and sends `credentials: 'include'` and `X-Requested-With`.
   - Put US1.9 in the skeleton. US3.4 and US3.8 then gain a frontend half that runs on top of it.
5. **The end-to-end check needs a way to read the emailed code locally.** The verification command has to demonstrate sign-up → code → login → `/auth/me` with no paid email provider (Forbidden: paid services in the default test run). **Proposal:** add this AC to the new email-adapter story (B.1): "Given local development configuration, then codes are delivered to a local mail catcher (for example Mailpit in Docker Compose) or a file sink that the Playwright test can read, and no production endpoint exposes a code." `[Recommendation]`

Revised skeleton: **US1.1, US1.2, US1.3, US1.4, US1.5, US1.6a (email only), US1.9, US3.1, US3.2, US3.4, US3.8.** It is still one thin slice, and every story in it has all of its `Deps` inside the set.

### B. Hidden technical stories to add

1. **Split US1.6 so each vendor adapter arrives with its first real consumer.** Building all four adapters up front means building interfaces before anything uses them, and it pulls Stripe and OpenAI into the skeleton's dependency chain.
   - **US1.6a — Email delivery adapter with fake and local sink.** Must. Deps: US1.5. In the skeleton.
   - **US1.6b — OpenAI text and image adapters with fakes.** Must. Deps: US1.5. Needed before US7.4 and US9.1.
   - **Stripe adapter:** fold it into US6.2 as an AC, because Stripe Checkout and its webhook are the only consumers.
   - Keep AC1.6.1–AC1.6.3 on US1.6a/b. Each AC applies to the adapters that story delivers.
2. **Media storage is missing entirely.** Photos (3 per user), 24 generated images per report, and the cached PDF (US8.5) all need to be stored somewhere. No host has been chosen (`NFR-010`), so this has to be an abstraction. **Proposal:** add **US1.10 — Private media storage** (Enabler, Must, Deps: US1.5, US1.8). Suggested ACs:
   - Given a stored file, then the configured backend saves it: local disk in development, with an object-store adapter possible later.
   - Given a stored file, then it is never served from a public static path and is readable only through an authenticated endpoint that checks ownership.
   - Given a photo retake, then the old file is deleted, not orphaned.
   - Given local development, then the upload folder is git-ignored (already covered by AC1.1.3).
   - US5.2 and US9.1 should depend on US1.10. `[Recommendation]`
   - **US5.8 (EXIF removal) becomes almost free** if US1.10 re-encodes every photo on write with Pillow or OpenCV. Consider folding it into US1.10's write path. The story can stay Should, but its cost is well under a day.
3. **Face landmark service shared by three features.** MediaPipe Face Landmarker is used by the per-photo checks (face count and pose, US5.5), the identity signature (US5.6, `ASM-010`) and the measurements (US7.3). As drafted, US5.5 would build it and US7.3 would quietly rebuild or reuse it. **Proposal:** add **US1.11 — Face landmark service** (Enabler, Must, Deps: US1.1). Suggested ACs:
   - Given an image, then the service returns the 478 landmarks, or a typed "no face" or "multiple faces" result.
   - Given the model file, then it is pinned to a version and loaded once per process (cached instance). Only the model object is cached, never results (see `knowledge/photo_identity_validation_spec.md` §5).
   - Given the same image twice, then identical landmarks are returned. This determinism underpins AC7.5.2.
   - US5.5, US5.6 and US7.3 should depend on US1.11.
4. **Orchestrating the analysis pipeline.** US1.7 is a generic job runner. Nothing owns the actual pipeline: measure → write narratives → generate 24 images → assemble report, where each step persists its output, a retried job resumes rather than repeats, and one payment allows exactly one analysis (NFR10, AC7.1.3). **Proposal:** add **US7.6 — Analysis pipeline orchestration** (P4 Dev enabler, Must, Deps: US1.7, US7.1). Suggested ACs:
   - Given a run, then its status moves through the named steps, and those steps are what US7.2 shows.
   - Given a step has already completed, when the job resumes after a restart, then that step is not repeated and no second paid OpenAI call is made for it.
   - Given a payment, then at most one analysis run exists for it.
   - Given narratives are done but some images failed, then the report is assembled and published (FR10.5).
   - Move AC9.4.2 (24 images in total) here, because it spans US9.1–US9.4.
5. **Journey progress resolver.** AC2.1.3 ("taken to the step I have reached"), AC5.7.1 (every entry point sends an inconsistent set back to photos), AC11.1.1 (land on Home when a report exists) and AC7.2.2 (return to progress) all need one server-side answer to "where is this user in the journey?". None of their `Deps` build it. US2.1 lists only US1.1, yet AC2.1.3 needs auth plus progress. **Proposal:** add **US11.8 — Resume at the right step** (P1, Must, Deps: US3.5). Suggested ACs:
   - Given my progress, when I call the progress endpoint, then I get exactly one next step: consent, questionnaire, photos, payment, start analysis, analysing or report.
   - Given the frontend route guard, then it uses that endpoint.
   - Given an identity-inconsistent set, then the next step is "photos".
   - Then US2.1 AC2.1.3 and US5.7 depend on US11.8. Alternatively, move AC2.1.3 out of US2.1 so US2.1 stays a pure landing-page story.
6. **Report content schema and generation of all per-feature text.** AC8.1.2 needs "projected-potential ideas" and a "summary callout" per feature, and US8.2 needs tiered recommendations. US7.4 only generates the narrative. Nothing generates the other text. **Proposal:** widen US7.4b (see C.2) so one structured-output call per feature, or one per report, returns narrative, projected-potential ideas, summary callout and recommendations with tier labels, all validated against a JSON schema. State in US8.2 that it depends on that output.

### C. Stories that are too big for 1–3 days: proposed splits

1. **US3.6 Seamless token refresh (6 ACs, backend and frontend, with test-first modules).** This is about 5–7 days. There is also a dependency problem: US3.5 (restore on reload and restart) cannot work without the backend `POST /auth/refresh`, yet the draft puts the refresh endpoint's behaviour in US3.6, which depends on US3.5. Proposed split:
   - **US3.5** also owns the basic backend refresh endpoint: it issues a new access token and rotates the cookie (AUTH-010–AUTH-016 test-first).
   - **US3.6a — Refresh-token reuse detection and CSRF checks** (backend, test-first): AC3.6.4 and AC3.6.5.
   - **US3.6b — Proactive refresh and single-flight 401 retry** (frontend API client, test-first per FE-005/FE-006): AC3.6.1, AC3.6.2 and AC3.6.3. Deps: US1.9, US3.5.
   - **US3.6c — Two tabs refreshing at once** (AC3.6.6). Keep it as its own story marked `[Open — mechanism decided in Domain Design]` so the open question does not block US3.6a/b. `[Recommendation]` Likely mechanisms are a Web Locks or BroadcastChannel leader, or a short server-side grace window for the previous refresh token.
2. **US7.4 Narratives (prompt assembly, a multimodal gpt-4o call, the tone rule, the medical filter, output validation, persistence).** About 4–6 days. Split:
   - **US7.4a — Prompt assembly** (pure logic, no vendor): AC7.4.2 (question text included, medical/medication/allergy answers excluded) and AC7.4.3 (tone instruction). This is the P3 safety core and can be fully unit-tested.
   - **US7.4b — Generate, validate and store report text**: AC7.4.1 and AC7.4.4, plus the schema from B.6.
   - Make AC7.4.1's "cites at least one of my measurement values" checkable. Suggested wording: "…then a validator confirms the narrative contains at least one stored value for that feature (formatted to the configured precision). If it does not, the text is regenerated once, and if it still fails, the failure is recorded." Without a stated rule, the fake always passes and the real vendor is never checked.
   - Add an AC to US7.4b: "Given gpt-4o returns malformed or schema-invalid output, then it is retried within the NFR5 limits and the run fails with a reason instead of storing partial text."
3. **US7.3 Measurements (landmarker, 7 front-mesh features, ears from the 3/4 photos with fallback, and heuristics for Hair, Skin and Neck).** About 4–6 days even with US1.11 in place. Split:
   - **US7.3a — Front-photo measurements for the 7 mesh features** (AC7.3.1).
   - **US7.3b — Ear measurement from each side's 3/4 photo, falling back to front** (AC7.3.2, `ASM-010` first-pass formula).
   - **US7.3c — Hair, Skin and Neck heuristics, or an explicit "no measurement" marker** (AC7.3.3).
   - Add a determinism AC to US7.3a: "Given the same photo twice, then identical values". AC7.5.2 relies on this.
4. **US8.1 Read my 11-feature report (backend report API with the 402 and ownership checks, template text, 11 sections, and the frontend page).** About 4–5 days. It also depends on US9.1, which puts image generation on the report's critical path. Split:
   - **US8.1a — Report read API**: assembles the analysis result, image slots and template sections, and returns 402 or 404 correctly.
   - **US8.1b — Report page**: renders the sections. Each image slot renders an "image not available yet" state.
   - With that slot state, **drop the US9.1 dependency from US8.1**. Images fill in once US9.1 lands, and US9.5 already defines the slot state. The text report can then be demonstrated earlier.
5. **US5.6 Same-person check (a test-first backend decision, a server re-check reused at checkout and analysis start, and frontend review-screen state).** About 3–5 days. Split:
   - **US5.6a — Identity decision and photo-status endpoint** (backend, test-first per `team.md`): AC5.6.1, AC5.6.2, AC5.6.3 and AC5.6.5. Expose one `check_photo_set_identity` function that US6.2 and US7.1 call for their 409 check.
   - **US5.6b — Review screen**: AC5.6.4, plus the regression documented in `knowledge/photo_identity_validation_spec.md` §6. Suggested AC: "Given a retake has just uploaded and the fresh identity result is still pending, then Continue stays disabled and no automatic navigation happens (a pending result is not a consistent one)." That is exactly the bug the spec records, and the draft has no AC for it.
6. **US5.5 Clear rejection reasons (seven checks).** Readability, resolution, brightness, face count and proportion are simple OpenCV and landmarker work. Pose match (head yaw from the landmark transformation matrix) and eye/mouth occlusion (glasses, hat) are harder and heuristic. Split:
   - **US5.5a** — the five simple checks.
   - **US5.5b** — pose match and occlusion. Mark occlusion as `[Assumption]` first-pass, tuned with US5.9.
7. **US8.3 Interactive Facial Assessments together with US7.5 scores.**
   - AC7.5.1 asks for dimorphism and prototypicality values. Both normally need reference data: a sex-typical landmark average for dimorphism and a mean face for prototypicality. Neither the client document nor the knowledge folder defines them. `FR-018` only says they are "first-pass heuristics (client-confirmed)".
   - **Proposal:** split US7.5 into **US7.5a — symmetry, Regional Balance and facial thirds** (purely geometric, well defined) and **US7.5b — dimorphism, prototypicality and face-shape classification**. Mark US7.5b `[Assumption] formula and reference data defined in Functional Design`. Otherwise AC7.5.1 can be met with any number and still pass.
   - US8.3 (dimorphism sliders, prototypicality, thirds, symmetry, face-shape wireframe, table of contents) is also about 4 days of frontend work. Split it the same way: **US8.3a** covers the table of contents, symmetry and thirds; **US8.3b** covers dimorphism, prototypicality and the wireframe.

### D. Stories that are too thin, or ACs in the wrong place

- **US5.4 (retake replaces)** is a single AC and falls out of how US5.2 is built: upsert per `(user, angle)`, plus old-file deletion in US1.10. **Proposal:** merge it into US5.2 as AC5.2.4. `[Recommendation]`
- **US1.8 AC1.8.1** tests ownership on photo, report, visual and chat, but none of those exist when US1.8 is built (Deps: US1.1 only), so the story cannot be tested on its own. **Proposal:** US1.8 delivers the reusable ownership dependency and tests it against the user's own record. Each resource story (US5.2, US8.1a, US9.1, US10.1) then carries its own "another user's id returns 404" AC.
- **US1.5 AC1.5.2** ("backend refuses to start if a required secret is missing") would force every developer to set real OpenAI and Stripe keys from the skeleton onward. **Proposal:** "a secret is required only when the adapter that needs it is selected. With the fakes selected (the default for tests and local development), those keys are not required." AC1.5.1's list of settings should grow story by story, not be complete up front.
- **US9.2, US9.3 and US9.4** are about a day each. That is acceptable as they are. Do not merge them; they are independently demonstrable.

### E. Gaps in feasibility and acceptance criteria against the mandated stack

- **Image volume against the 10-minute limit (AC7.2.3, NFR4).** `gpt-image-1` high-fidelity edits typically take tens of seconds each `[Assumption — to be measured]`. Twenty-four images one after another would likely exceed 10 minutes with the real vendor. **Proposal:** add an AC to US7.6 or US9.1: "Given image generation, then images are generated with a configurable concurrency limit, and rate-limit (429) responses back off and count toward the FR10.5 retry cap." Also keep NFR4's "verified once against the real vendors" as an explicit task in Build and Test.
- **Returning from Stripe before the webhook arrives (US6.3).** Stripe redirects the user to `success_url` before, or at the same time as, the webhook. Suggested AC: "Given I return from Checkout before the webhook is processed, then I see 'confirming payment', and 'Start Analysis' becomes available once the payment is recorded, without a manual reload." Also add to US6.3: "the webhook handler verifies the signature against the raw request body". Local development needs Stripe CLI forwarding, documented in the backend README.
- **User-triggered image retry against the cost cap (US9.5, NFR10).** AC9.5.3 lets the user retry with no limit. NFR10 requires "a cap on image retries". Suggested AC: "Given I've used the configured number of manual retries for a slot, then the retry button is disabled and no image call is made."
- **Branching in the questionnaire engine (US4.2).** The draft onboarding spec in team knowledge (`knowledge/onboarding_questionnaire_spec.md` §3 and §5) needs a conditional question (Q19 depends on Q4). It also probably needs a yes/no question that reveals a follow-up free-text field (Q9 medications, Q11 allergies). Suggested addition to AC4.2.2: "…including a follow-up field revealed by a specific answer, and the follow-up inherits the medical flag of its parent question." Otherwise medication details typed into a follow-up could reach OpenAI unflagged, which breaks FR8.6.
- **Unverified re-sign-up (US3.1).** AC3.1.2 refuses any registered email. It does not say what happens when the earlier account never verified, where the user simply lost the first code. Suggested AC: "Given an unverified account with that email, then sign-up resends a code (subject to US3.3's resend limits) rather than blocking the address forever."
- **PDF (US8.5).** This is feasible in about 2–3 days if the PDF is rendered from the report's own HTML with headless Chromium, since Playwright is already in the toolchain. A separate ReportLab layout would take longer. Branding to `knowledge/report_design_spec.md` v3.0 may be more than 3 days. Keep US8.5 functional and treat branded styling as a follow-up if it overruns. `[Recommendation]`
- **Home radar chart and "Priority Features" (US11.1).** The six radar axes and the rule for choosing priority features are not defined. `knowledge/report_design_spec.md` §13.1 marks the cutoff 🔴 TBD. Mark AC11.1.2's selection rule `[Open — Functional Design]` so the AC can be tested.
- **Convention to add:** every story that changes the schema ships its own Alembic migration, with the upgrade/downgrade check from AC1.2.2 in CI.

### F. The "Blocked: spec" stories: team knowledge already holds draft specifications

The team knowledge folder (`aidlc/spaces/default/knowledge/`) already contains:
- `onboarding_questionnaire_spec.md`: all 23 questions, the Q19 branch and the exact disclaimer wording. Status "Draft", with two items open for client confirmation.
- `photo_identity_validation_spec.md`: v1.1, "Active". It gives the identity algorithm, worked examples and the state contract.
- `report_design_spec.md` and `report_template.md`: v3.0, "ACTIVE". They include Protocol sections (§4, §8, §14).

The draft marks US4.4, US5.9 (only partly: the per-photo thresholds are still missing, but the identity threshold of 0.6 is in `ASM-010`), US8.6 and US11.3 as waiting on specifications that "arrive later". Whether these documents count as the client's specifications is not for me to decide. **Proposal:**
- The lead should check these files and surface the question to the human rather than silently resolving it, per the Mandated rule on surfacing conflicts.
- If the documents are accepted, US4.4 and US11.3 can move from "Blocked" to "Ready — client confirmation pending on listed open items".
- The US5.6a ACs should cite the identity spec's worked examples (Scene 1→2→3, Flip-flop A/B) as test cases.

### G. Knowledge dispute: AC5.6.2, the "hub" case

AC5.6.2 says: "Given front matches both others but left and right don't match each other, then front is the reference and **nothing is flagged**."

- `knowledge/photo_identity_validation_spec.md` §3 rule 5 says the hub case is "resolved to a **single flagged angle**, with `front` protected from being the answer whenever an alternative exists".
- Client `BR-005` rule 2 flags "the one with the fewest matches". Front has 2 matches and left and right have 1 each, so a non-front photo is flagged. The "front is the reference" tie-break chooses which photo is kept, not whether any photo is flagged.
- Flagging nothing would let a set whose left and right photos show different people reach payment and analysis. That breaks `BR-004`/FR6.9 and the Forbidden rule against analysing a photo set that failed validation.

**Proposal:** "AC5.6.2 Given front matches both others but left and right don't match each other, then front is not flagged, exactly one of left and right is flagged (by a fixed, documented tie-break), and Continue is disabled." The tie-break is `[Open — Functional Design]`, or it can be taken from the identity spec if the human accepts it.

### H. Dependency check and totals

- After the changes above, the dependency graph I traced has no cycles. The one ordering problem in the draft is US3.5 needing the refresh endpoint that US3.6 describes; C.1 fixes it.
- Undeclared dependencies to add: US2.1 → US11.8 (via AC2.1.3), US5.2 → US1.10, US5.5/US5.6/US7.3 → US1.11, US6.2 and US7.1 → US5.6a (the shared re-check function), US10.1 → US1.6b, US9.1 → US1.6b and US1.10.
- Net effect: about +16 stories and −1 merge, which is roughly 75–77 stories. That is above Q3's "roughly 50–70" estimate. Q3 sets the size at 1–3 days, and that holds; the count estimate is what gives. If the human prefers to stay near 70, the lowest-risk splits to leave out are US8.3a/b and US5.5a/b.

## Positions

- AGREE: journey-order grouping, and enablers written as P4 stories (Q2, Q4) — these map cleanly onto Units and Bolts and keep groundwork traceable.
- AGREE: separating the configurable engine from "load real content" stories (Q6) — it keeps code changes and content changes apart, which fits `NFR-011`.
- AGREE: most stories are sized and scoped correctly (US3.1–US3.4, US3.7, US3.9, US4.1–US4.3, US6.1–US6.4, US9.2–US9.5, US10.1–US10.3, US11.2, US11.4–US11.7) — each is about 1–3 days with a clear backend and frontend boundary.
- OBJECT: the walking-skeleton set is not closed under its own `Deps` (US3.8 → US3.5, US3.1 → US1.6), leaves out US1.4 (Gitleaks), which `team.md` requires, and has no frontend auth store or API client story — knowledge dispute (checkable against `team.md` and the draft's own Deps column).
- OBJECT: hidden technical stories are missing — media storage (US1.10), the shared face landmark service (US1.11), frontend auth store and API client (US1.9), pipeline orchestration (US7.6), the journey progress resolver (US11.8) and the generation of per-feature summary, potential and recommendation text — knowledge dispute (without them, several ACs cannot be built or tested under the stated Deps).
- OBJECT: AC5.6.2 flags nothing in the hub case — knowledge dispute (it conflicts with `knowledge/photo_identity_validation_spec.md` §3 rule 5 and `BR-005` rule 2, and would let a mismatched set be analysed).
- OBJECT: US3.6, US7.3, US7.4, US8.1, US5.6, US5.5, US7.5 and US8.3 are larger than 1–3 days and should be split as in section C — judgment call (the split granularity trades story count against the Q3 size target; both positions are legitimate).
- OBJECT: US8.1 depends on US9.1 — judgment call (dropping the dependency by rendering an "image not available yet" slot shortens the critical path; keeping it is simpler but delays any demonstrable report).
- OBJECT: US4.4, US8.6 and US11.3 (and part of US5.9) are marked "Blocked: spec" although draft or active specifications exist in team knowledge — knowledge dispute to be settled by the human or client (whether those documents count as the client's specifications).
- OBJECT: AC7.4.1 (cites a measurement), AC7.5.1 (dimorphism and prototypicality) and AC11.1.2 (priority features) have no rule a test can check against — knowledge dispute (as written, any output passes against the fakes).
