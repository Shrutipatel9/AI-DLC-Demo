# Requirements Analysis — Questions

`client_requirements.md` is the single source of truth and already covers most of what the requirements need. These questions only cover gaps and conflicts it leaves open. Where an answer adds something the client did not state, the requirement will be labelled `[Decided by delivery team]` or `[Recommendation]`, as the document itself asks.

Pick one letter per question (or X and describe your own answer).

---

### Question 1 — Medical answers and OpenAI
FR-008 says the questionnaire answers are sent to OpenAI as context for the narrative, but FR-008(f) says the narrative must never mention the medical, medication or allergy answers. If those answers are sent anyway, sensitive health data leaves the platform with no benefit.

A. Leave medical, medication and allergy answers out of every OpenAI request; send only the other answers (Recommended)
B. Send all answers as FR-008 says, and rely on the prompt to stop the model from mentioning the medical ones
X. Other (please specify)

[Answer]: A

### Question 2 — Where users are and consent to face analysis
The client document doesn't say which countries the product is sold in. Face geometry and health answers count as specially protected data in many places (for example the EU/UK under GDPR, and some US states such as Illinois). The formal retention policy is out of scope (Section 2.2), but the basics affect what gets built now.

A. Treat it as possibly global: add an explicit consent checkbox for facial analysis and health data before the questionnaire, and keep the data model ready for later deletion; flag the jurisdiction question to the client (Recommended)
B. US only, no extra consent step beyond the existing disclaimer (FR-004)
C. Leave it for now and record it as an open question for the client
X. Other (please specify)

[Answer]: A

### Question 3 — Sorting recommendations into the three tiers
The report sorts recommendations into at-home, over-the-counter and in-clinic tiers (FR-012). The document suggests keyword rules (ASM-007) but marks this as not confirmed by the client (OQ-012).

A. Keyword rules as the document describes (ASM-007), with the keyword lists kept in configuration so they can be tuned
B. Ask OpenAI to return each recommendation already labelled with its tier (structured output), with keyword rules only as a fallback (Recommended)
X. Other (please specify)

[Answer]: B

### Question 4 — Specifications that don't exist yet
The 23 questionnaire questions, the photo-validation thresholds and the report/UI details will come later in separate specifications. How should those parts be built in the meantime?

A. Build them data-driven: questions, branching, thresholds and copy come from configuration or seed data, filled with clearly marked placeholder content until the specs arrive, so the real content drops in without code changes (Recommended)
B. Build the rest now and leave these features until the specifications arrive
X. Other (please specify)

[Answer]: A

### Question 5 — How long analysis may take
After "Start Analysis", the system measures the face, writes 11 narratives and generates 24 AI images. The document sets no time target.

A. Run it in the background with a visible progress screen; the user can leave and come back; target: report ready within 10 minutes in normal conditions (Recommended)
B. Same, with a stricter target of 5 minutes
C. No time target; just show progress until it's done
X. Other (please specify)

[Answer]: A

### Question 6 — When some AI images fail
With 24 generated images per report, some calls to the image service will occasionally fail.

A. Retry each failed image automatically (up to 3 times); if it still fails, publish the report with that image marked "not available yet" and let the user retry it later (Recommended)
B. Don't publish the report until all 24 images succeed, retrying in the background
C. Publish without the missing images and don't offer a retry
X. Other (please specify)

[Answer]: A

### Question 7 — Devices, browsers and accessibility
Photo capture by camera suggests many users will be on phones. The document doesn't state device, browser or accessibility targets.

A. Responsive web for phone and desktop; latest two versions of Chrome, Safari, Edge and Firefox; WCAG 2.1 AA accessibility (Recommended)
B. Same devices and browsers, but no formal accessibility target
C. Desktop-first; phones supported on a best-effort basis
X. Other (please specify)

[Answer]: A

### Question 8 — Limits on the AI Beauty Assistant chat
Every chat message costs money on OpenAI (BR-006), and the document sets no limit.

A. A configurable daily message limit per user (for example 50), with a clear message when it is reached (Recommended)
B. No limit
X. Other (please specify)

[Answer]: A
