**Collaborator:** aidlc-design-agent

## Contribution

Scope of this review: user experience and persona fidelity. It covers the emotional states behind each persona, missing or out-of-order journey steps, whether UI behaviour is written as testable criteria (including accessibility and phone use), and stories that prescribe UI instead of stating a need. Each proposal says where its authority comes from: a client ID, a `requirements.md` ID, or **[Recommendation]** (my own proposal, not client-stated, which must keep that label if integrated). Proposed new AC IDs continue each story's existing sequence. The lead can renumber them.

---

### A. Journey gaps (missing steps and states)

**A1. No story owns "pick up where I left off" routing.** AC2.1.3 ("taken to the step I have reached") and the `requirements.md` FR1 acceptance criterion both depend on routing that no story delivers. US5.7 covers only the inconsistent-photo case, and AC11.1.1 covers only the report-exists case. P2's stated pain point is "fear ... of losing progress". Proposed new story:

> **US11.8 — Pick up where I left off.** As **P2 Sam**, I want to land on the next step I haven't finished whenever I sign in or come back, so that I never lose progress or have to find my own way back.
> Priority: Must · Deps: US3.5, US4.1, US5.7, US6.3, US7.2, US11.1 · Traces: FR1 (AC 3), FR6.7, FR8.2, FR11.1, `WF-001`, `BR-005` rule 7
> - AC11.8.1 Given I haven't consented, when I sign in, then I land on the consent step.
> - AC11.8.2 Given I've consented but not submitted the questionnaire, when I sign in, then I land on the questionnaire.
> - AC11.8.3 Given my photo set is incomplete or inconsistent, when I sign in, then I land on the photo screen (the inconsistent case is AC5.7.1).
> - AC11.8.4 Given a consistent set and no successful payment, when I sign in, then I land on the payment screen.
> - AC11.8.5 Given I've paid but not started analysis, when I sign in, then I land on the screen with "Start Analysis".
> - AC11.8.6 Given analysis is running, when I sign in, then I land on the progress screen for that run (AC7.2.2).
> - AC11.8.7 Given my report exists, when I sign in, then I land on Home Overview (AC11.1.1).
> - AC11.8.8 Given I open a later step's URL directly before finishing an earlier step, then I'm sent to the earliest step I haven't finished.

AC2.1.3 then depends on US11.8. Under the INVEST note it becomes testable on its own once its Deps exist.

**A2. Coming back from Stripe before the webhook arrives.** FR7.4 lets only the webhook update payment status, so a user can return from Checkout before their payment is confirmed. No story covers what the user sees in that gap. P2 fears "paying and getting nothing", and this is the exact moment that fear peaks. Proposed ACs for US6.3 (or a new US6.5 if the lead prefers to keep US6.3 backend-only):
- AC6.3.4 Given I return from Stripe Checkout before the payment is confirmed, then I see a "confirming your payment" state, not the payment screen and not an error. **[Recommendation]**
- AC6.3.5 Given confirmation arrives while I'm on that screen, then the screen updates by itself (no reload) and "Start Analysis" becomes available. A screen reader announces the change. **[Recommendation]**
- AC6.3.6 Given confirmation hasn't arrived after a configured wait, then I see a plain-language message saying my payment is still being confirmed, that I won't be charged twice, and that I can safely leave and come back. **[Recommendation]** The wait value is a configuration item for Domain Design.

**A3. What the user sees when analysis fails.** US1.7 (AC1.7.2, AC1.7.3) makes a job end as "failed with reason" for developers. No story says what the paying user sees. US9.5 covers image failures only; it does not cover a narrative or measurement failure. Proposed ACs for US7.2:
- AC7.2.4 Given the analysis run fails, then the progress screen explains in plain language that something went wrong on our side (never a raw error or stack trace), and confirms my payment is kept for this report. Basis: `FR-015`/`BR-001`, one paid report per user. The "payment kept" wording is **[Recommendation]**.
- AC7.2.5 Given a failed run, then I'm offered a way to start it again without paying again. **[Recommendation — the remedy (self-retry vs. contact support) is a judgment call for the human; see Positions]**

**A4. Moving from the progress screen to the result.** No story says what happens when a run finishes while the user is watching. Proposed AC7.2.6: Given I'm on the progress screen when the report is ready, then I'm moved to Home Overview (or shown a clear "View my report" action), and a screen reader announces the change. **[Recommendation]** — the lead picks one.

**A5. The progress screen must say you can leave.** FR8.2 lets users leave and return, but a user can't benefit from that unless the screen says so. Proposed AC7.2.7: Given analysis is running, then the screen says I can close the page and come back, and gives the expected wait (a configured figure consistent with NFR4's 10-minute target). **[Recommendation]**

**A6. Disclaimer dead-end.** `FR-004`/`BR-003` requires the user to confirm they have "no Body Dysmorphic Disorder–related concerns". P3 is described as someone who "thinks about their appearance often and may show elevated appearance-related distress". That is exactly the user who may be unable to tick the box truthfully. AC4.3.1 only says "submission is blocked with a visible reason", which leaves that user stuck on a blocked screen with no way forward and no explanation. The gate itself is client-stated and must stay. What the blocked user sees is not specified anywhere. Proposal:
- AC4.3.4 Given I haven't ticked the disclaimer, then the screen explains in neutral, non-judgemental language why confirmation is needed, and lets me leave without losing my answers. **[Recommendation]**
- Raise as an open question for the client: *what should a user who cannot confirm the disclaimer see?* Examples: a neutral exit message, or pointers to support resources. I'm not proposing specific support resources because that would be inventing content. Note that payment comes after this gate, so nobody pays and then gets blocked here. That ordering is correct and should stay.

**A7. Questionnaire progress and editing.** The questionnaire is 23 questions with branching (`FR-003`), completed on a phone by P1/P2. Proposed ACs for US4.2, all **[Recommendation]**:
- AC4.2.4 Given I'm answering, then I see my position in the questionnaire, and the count reflects questions skipped by branching.
- AC4.2.5 Given I haven't submitted, when I go back, then my earlier answers are kept and editable, and changing a branching answer updates which questions follow.
- AC4.2.6 Given I leave mid-questionnaire and sign in again, then my answers so far are kept. (This supports US11.8 and P2's "losing progress" pain point. Saving partial answers is a design decision; the developer should confirm the cost.)

---

### B. Persona fidelity and emotional states

**B1. P3's safety bar stops at AI text, but the UI carries tone too.** P3's section ("What it means for the product") and the stories cover tone only in the narrative (AC7.4.3) and the assistant (US10.2). Several client-stated screens are just as likely to upset P3: symmetry "score out of 100", "Priority Features to Improve", the aging preview (+10 years), and before/after "potential" images. I'm not proposing to change any client-stated content. I'm proposing to frame it. All **[Recommendation]**:
- AC8.1.5 (US8.1) Given the web report, then the "Understanding Your Results" preamble (`FR-011`) comes before the first score or feature, in both the web view and the PDF.
- AC8.1.6 (US8.1) and AC9.4.3 (US9.4) Given any AI-generated image (per-feature "after", hairstyle, outfit, aging card), then it is visibly labelled as an AI-generated illustration, not a prediction or medical outcome. The label is text, not only an icon.
- AC5.5.5 (US5.5) Given a rejected photo, then the reason describes the photo and how to fix it (for example "Move closer so your face fills more of the frame"), never the person's appearance.
- AC5.6.6 (US5.6) Given a flagged photo, then the message says the photos don't appear to match and suggests retaking that angle in the same lighting and position. It does not accuse the user of using someone else's photo. (A same-person mismatch can come from lighting or pose, not only a different person; see `ASM-010`, which is a first-pass heuristic.)
- Add these points to P3's "What it means for the product" in `personas.md`, marked **[Recommendation]**.

**B2. P2's "shareable" goal implies a feature nobody specified.** P2's goal "See fun, shareable AI visuals" suggests a share feature. The client never states one, and no story builds one. Proposed rewording: "See fun AI visuals of themselves — hairstyles, outfits, aging (FR10.3)". This avoids implying an unscoped requirement (project rule: NEVER invent requirements).

**B3. No persona reflects accessibility needs.** The product commits to WCAG 2.1 AA (NFR9), but no persona uses assistive technology, keyboard-only input or magnification. I'm not proposing a fifth persona. Proposed one-line addition under "Relationships" in `personas.md`: "Any persona may use a screen reader, keyboard-only input, screen magnification or reduced motion; accessibility criteria come from NFR9 and apply to every persona." **[Recommendation]** This makes the a11y ACs below trace to a user, not only to an NFR.

**B4. P1 "often on a phone" is not reflected in any criterion.** See section D.

---

### C. Testable UI behaviour (per screen)

**C1. Camera and upload (US5.2, US5.3).** P1 is "often on a phone, and uses camera capture". Proposed ACs:
- AC5.3.3 Given I take a photo with the camera, then I see a preview and can retake it or use it before it's submitted for validation. **[Recommendation]**
- AC5.3.4 Given my device has no camera, then only the upload option is offered, with no broken or empty camera view. **[Recommendation]**
- AC5.3.5 Given any angle step, then file upload is always offered next to the camera. This is also the accessible route for users who can't frame a live camera shot. Basis: FR5.2, "file upload or camera".
- AC5.2.4 Given each angle step, then the instruction says which way to turn in the user's own terms (for example "Turn your head so your left cheek faces the camera"), and an example image shows it. **[Recommendation]** "Left 3/4" is ambiguous from the user's own point of view versus the camera's, and front cameras show a mirrored preview. Getting this wrong produces pose-mismatch rejections (AC5.5.2), which is P2's main pain point.
- AC5.2.5 Given I've submitted a photo, then I see a checking state for that photo until its result arrives, and the result (accepted or the reason) is announced to screen readers. **[Recommendation]**
- AC5.2.6 Given I'm on the photo step, then I can see how many of the required angles are done (for example "2 of 3"), counted from the configured angle set (FR5.3). **[Recommendation]**
- **Open question: phone file formats.** Photos from iPhones are HEIC by default. The requirements don't say whether HEIC is accepted, converted or rejected. AC5.2.3 ("isn't a readable image") would reject iPhone photos unless someone makes a decision. This is a knowledge gap for the developer and client, not something to decide here.

**C2. Identity-check review screen (US5.6).**
- AC5.6.7 Given a flagged photo, then the flag is shown by text and an icon, not colour alone (WCAG 1.4.1), and the reason is programmatically tied to that photo so a screen reader reads it with the photo.
- AC5.6.8 Given Continue is disabled, then the screen says why next to the button (for example "Retake the highlighted photo to continue"). A disabled button alone is invisible to keyboard and screen-reader users. **[Recommendation]**
- AC5.6.4 already captures "stays on the screen until I click it" (`BR-005` rule 6). Keep it exactly as written.

**C3. Progress screen (US7.2).**
- AC7.2.8 Given analysis is running, then each step's state (done, current, waiting) is shown in text, not only by colour or a spinner, and step changes are announced politely to screen readers without moving focus.

**C4. Report navigation, charts and images (US8.1, US8.3, US8.4, US11.1).**
- AC8.3.3 Given the table of contents, when I choose an entry by mouse, touch or keyboard, then the page moves to that section and keyboard focus moves to its heading.
- AC8.3.4 Given the dimorphism sliders, then they are display-only (not inputs I can drag), and each one's value and meaning are available as text. **[Recommendation]** "Sliders" in `FR-018` describes the visual; I'm reading it as display, not input. The lead should confirm that reading, or raise it with the client.
- AC11.1.4 (US11.1) and AC8.3.5 (US8.3) Given any chart (the six-axis radar, facial thirds, the symmetry breakdown), then its values are also available as text or a table (WCAG 1.1.1).
- AC8.1.7 Given each before/after pair, then each image has alt text naming it (for example "Your photo — Nose" / "AI-generated illustration — Nose").
- AC8.4.3 Given a metric table on a phone-width screen, then the table scrolls within its own area and the page itself does not scroll sideways.

**C5. Toasts, dialogs and form errors (US11.7).** AC11.7.3 says "no violations and they work by keyboard". That is necessary but doesn't cover the behaviour that matters most. Proposed ACs:
- AC11.7.4 Given a toast appears, then screen readers announce it, it doesn't take focus, and an error toast stays until dismissed. A success toast stays at least long enough to read, and can be dismissed. **[Recommendation — durations for Domain Design or the design system]**
- AC11.7.5 Given the confirmation dialog opens, then focus moves into it and stays there. Escape cancels. When it closes, focus returns to the control that opened it. The confirming button names the action (for example "Log out"), not "OK".
- AC11.7.6 Given a form input is invalid (sign-up, OTP, reset, change password), then the error appears as text next to the field and is linked to it. A toast may add to this but never replaces it (WCAG 3.3.1, 3.3.3). This also clarifies AC11.5.2 and AC11.5.3: a wrong current password is an inline field error plus a toast, not a toast alone.

**C6. OTP entry (US3.2, US3.3, US3.4).** None of these stories has an entry-experience criterion, and OTP entry is where phone users abandon. All **[Recommendation]**:
- AC3.2.4 Given the code screen, then it shows a partly hidden version of the address the code was sent to (for example "m•••@example.com").
- AC3.2.5 Given I'm on a phone, then the code field opens a numeric keypad and accepts pasting or the operating system's one-time-code autofill.
- AC3.3.4 Given the resend cooldown is active, then the resend control shows the remaining seconds and becomes available by itself when the cooldown ends (extends AC3.3.1).
- AC3.2.6 Given my code has expired, then the message offers to send a new one right there.

**C7. Chat (US10.1, US10.3).**
- AC10.1.4 Given I send a message, then I see that a reply is on its way, and when it arrives screen readers announce it without moving focus.
- AC10.1.5 Given the assistant request fails, then my message stays in the input or conversation so I don't have to retype it, and I see an error toast. **[Recommendation]**
- AC10.1.6 Given I open the chat for the first time, then I see an empty state explaining what I can ask about (my own report). **[Recommendation]**

**C8. Session wording.**
- AC3.5.1 says "a loading state shows briefly". "Briefly" is not a pass/fail criterion (inception rule: avoid ambiguous language). Proposed rewording: "then a loading indicator shows until the session is restored, and the login screen is never shown in between" (this merges with AC3.5.4).
- AC3.6.4 Given my session family is revoked, then the login screen tells me in plain language that I was signed out for security and should sign in again. **[Recommendation]** This matters for P3's worry about their data.

**C9. Billing (US11.6).** AC11.6.2: the disabled PayPal option must be announced as unavailable, with its "not available" label read out. It must not be a silent, unlabelled control.

**C10. Payment screen promise (US6.1).** P2's section in `personas.md` asks for "a clear promise", but no AC delivers one. Proposed AC6.1.3: Given the payment screen, then it lists what the payment unlocks (the 11-feature report with PDF, AI visuals, the Beauty Assistant) and says that analysis begins only when I click "Start Analysis". None of my results or any partial content is shown. Basis: `FR-015` (no teaser) and FR8.1. The list itself is **[Recommendation]** copy.

---

### D. Phone use (NFR9)

The draft inherits NFR9 in every story without repeating it. I agree with that for simple screens. For the screens where phone layout is a real risk, NFR9's "Playwright journeys pass on a phone-sized viewport" won't catch the problems unless the criterion names the risk. Proposed phone-specific ACs (viewport per NFR9; a minimum reference width such as 360 px is **[Recommendation]**):
- US5.3: AC5.3.6 Given a phone in portrait, then the camera view, angle guide and capture control are all visible without scrolling.
- US5.6: AC5.6.9 Given a phone-width screen, then all three photos, their flags and the Continue control are reachable, and flagged photos are not cut off.
- US11.2: AC11.2.2 Given a phone-width screen, then Home, Report, AI Visuals and Chat are reachable from the header (for example through a menu button), each in no more than one extra tap. **[Recommendation]**
- US10.1: AC10.1.7 Given a phone with the on-screen keyboard open, then the message input and the latest reply stay visible.
- US11.7: AC11.7.7 Given a phone-width screen, then a toast doesn't cover the header navigation or the main action it reports on. **[Recommendation]** "Top-right" (`BR-009`) stays, but it may need to span the width on phones. The team should confirm, because `BR-009` fixes the position.

---

### E. Stories that prescribe UI instead of the need

The client-named labels ("Get started", "Sign in", "Start Analysis", Home/Report/AI Visuals/Chat) should stay in the ACs, because they are client-stated. The "I want" clause should state the need:
- **US2.2**: "I want an animated 'How it works' section..." → "I want to see the steps of the process before I start, so that I know what I'm signing up for." The animation and scroll trigger (`FR-001`) move into the ACs, which already cover them.
- **US8.3**: "I want an interactive report screen with a table of contents..." → "I want to explore my facial assessments and jump straight to any part of my report, so that I can find what matters to me."
- **US11.2**: "I want a header with Home, Report, AI Visuals and Chat..." → "I want to move between my results, visuals and chat from any screen, so that I never get lost." The header and its four links stay in AC11.2.1.

**Actor and value problems** (inception rule: each story must name the actor, action and business value):
- **US6.4**: "As P1 Maya (and the client), I want analysis and reports locked until payment succeeds". Maya doesn't want a paywall, so the value is the client's. Proposed actor: **the Project Sponsor** (a named actor in client §3): "As the Project Sponsor, I want analysis and reports locked until payment succeeds, so that no analysis cost is incurred and no report is given away without payment (`BC-003`, `BR-001`)."
- **US10.3**: "As the client (through P4 Dev's configuration)". Split the user-facing part from the business part. Either (a) actor **Project Sponsor**, value "chat costs stay bounded (NFR10)", with a user-facing AC kept in; or (b) actor **P1 Maya**: "I want to know when I've reached today's chat limit and when I can chat again, so that I'm not left guessing" (AC10.3.1 already covers this), and the cost value noted as the business reason. Option (a) is closer to the requirement's intent.

---

### F. Specification tracking

**F1. The Photo Capture Specification is missing from the blocked list.** Client "Detailed specifications to be provided separately" lists four specifications. The draft marks three as "Blocked: spec" (questionnaire, photo validation, report & UI) but not the **Photo Capture Specification** ("angle set, requirements screen, per-angle upload / camera capture flow", expanding `FR-005`, `ASM-005`). US5.1–US5.3 build that flow now. Proposed new story, consistent with the Q6 pattern:

> **US5.10 — Align the capture flow with the client's specification.** **Blocked: spec (Photo Capture Specification).** As **P2 Sam**, I want the photo requirements screen and per-angle capture steps to match the client's specification, so that capturing photos feels like the reference experience.
> Priority: Must · Deps: US5.1, US5.2, US5.3 · Traces: FR5.1, FR5.2, FR5.3
> - AC5.10.1 Given the specification, when its angle set, guidance content and capture steps are applied, then the photo step follows it with configuration or content changes only, wherever the specification stays within the configurable angle set (FR5.3).

The coverage summary and totals change to 5 blocked stories.

**F2. Flag for the lead or conductor, not a decision here.** The space's team-knowledge folder (`aidlc/spaces/default/knowledge/`) already contains draft documents titled `onboarding_questionnaire_spec.md`, `photo_capture_spec.md`, `photo_identity_validation_spec.md`, `report_design_spec.md` and `report_template.md`. They are dated 2026-09-08 to 2026-09-15 and cite other documents that are not in this workspace. `client_requirements.md` v1.0 (2026-09-29) says these specifications "do not exist yet". I have treated them as **not** client-supplied, and none of my proposals depends on them. Whether they are the incoming specifications (which would unblock US4.4 / US5.9 / US8.6 / US11.3 / US5.10) or out-of-date internal drafts is a conflict to surface to the human, not resolve silently (`client_requirements.md` "How to use this document", item 3).

**F3. Small corrections.**
- AC3.9.2 says "reusing the same reset link or token fails". The flow is code-based (FR2.12, `AUTH-015`) and there is no reset link, so a tester or copywriter could be misled. Proposed: "reusing the same reset token fails".
- US3.1 has no password-rule criterion, and neither `requirements.md` nor the client document defines a password policy. The user needs to see the rules before typing (WCAG 3.3.2). Raise this as an open question for the developer or security. Don't invent a rule in stories.

## Positions

- AGREE: Journey-ordered story map (Groups 2–11) follows `WF-001` step for step. It is the right spine for UX review and planning.
- AGREE: Splitting the End User into P1/P2/P3 by motivation and emotional state, with P3 setting the safety bar for every AI-facing story. Tone and safety rules really do differ between them.
- AGREE: AC5.6.1–AC5.6.5 and AC5.7.1–AC5.7.2 capture `BR-005` rules 1–7 accurately, including "retake never auto-navigates" and "skip decided only on initial load".
- AGREE: Keeping client-named UI labels ("Get started", "Sign in", "Start Analysis", header items) in the acceptance criteria, because they are client-stated.
- OBJECT: No story owns "resume at the next unfinished step" routing (proposed US11.8). AC2.1.3 depends on behaviour nothing delivers, so it can't be tested independently. **Knowledge dispute.**
- OBJECT: No user-facing state for returning from Stripe before the webhook confirms payment (AC6.3.4–6.3.6), or for a failed analysis run (AC7.2.4). With a webhook-only status (FR7.4) and a background job (FR8.2), these states will happen. **Knowledge dispute.** The remedy offered after a failed run (self-retry vs. contact support) is a **judgment call** for the human.
- OBJECT: The Photo Capture Specification is missing from the "Blocked: spec" set even though the client lists it as pending (proposed US5.10). **Knowledge dispute.**
- OBJECT: US6.4 and US10.3 have no genuine user actor or value as written. They should name the Project Sponsor, or be split, per the inception rule on actor/action/value. **Knowledge dispute.**
- OBJECT: P2's "shareable AI visuals" implies a sharing feature the client never stated. Remove "shareable". **Knowledge dispute.**
- OBJECT: A toast is the only feedback specified for form errors. WCAG 3.3.1/3.3.3 need errors identified in text next to the field (AC11.7.6). **Knowledge dispute.**
- OBJECT: AC3.5.1's "briefly" is not a pass/fail criterion, and AC3.9.2 refers to a reset "link" that doesn't exist. **Knowledge dispute.**
- OBJECT: Relying only on the blanket NFR9 inheritance leaves the highest-risk screens (camera, review screen, progress, charts, toasts/dialogs, OTP, chat on phones) without testable accessibility or phone criteria. I propose per-screen ACs only for those screens (sections C and D). **Judgment call** (story-volume vs. testability trade-off).
- OBJECT: P3's safety bar covers AI text only. Client-stated scores, "priority features" and AI images need UI framing: preamble first, images labelled as AI illustrations, rejection copy that describes the photo rather than the person. **Judgment call** (these are [Recommendation] additions).
- OBJECT: A user who cannot truthfully tick the BDD disclaimer hits a dead-end, and nothing defines what they see. **Judgment call** that needs the client's input; propose AC4.3.4 plus an open question for the client.
- OBJECT: US2.2, US8.3 and US11.2 put UI mechanics in the "I want" clause instead of the need. **Judgment call** (wording only; ACs unchanged).
