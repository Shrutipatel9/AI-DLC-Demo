# Refined Mockups — Questions

There are no rough mockups for this workflow (it starts at Inception), so the screens are designed from the stories (`inception/user-stories/stories.md`), the requirements, and the working report specifications in `aidlc/spaces/default/knowledge/` (`report_design_spec.md` — [RD], `report_template.md` — [RT]).

Several design questions are already settled and are not asked again:
- WCAG 2.1 AA, with per-screen accessibility and phone criteria (requirements Q7, stories Q12)
- Responsive phone and desktop layouts
- The loading, empty, error and partial states each screen must handle (stories)
- A persistent header for Home / Report / AI Visuals / Chat (client `FR-017`)
- Toasts top-right and a shared confirmation dialog (`BR-009`, `BR-010`)
- Gentle framing for anxious users (stories Q11)

Pick one letter per question (or X and describe your own answer).

---

### Question 1 — One look for the whole product
[RD] §3 defines colours and type for the report and Home dashboard, taken from the MyFace reference (navy headings, muted slate subheadings, a teal-green accent, a sage summary box). No client branding exists (`CON-003`), and the other screens (landing, sign-in, questionnaire, photos, payment, settings) have no visual spec.

A. Extend the [RD] colours, type roles and card style to every screen so the product feels like one thing; the exact values get a contrast check before use (Recommended)
B. A separate neutral style for the app screens; the [RD] style only for the report and Home
X. Other (please specify)

[Answer]: A

### Question 2 — UI component library
The client fixes Next.js + TypeScript but not a component library. The choice affects accessibility effort and how easily the client's team can extend the UI.

A. Tailwind CSS with shadcn/ui components (built on Radix, which handles keyboard and screen-reader behaviour for dialogs, menus and tabs; the code lives in the repo so it's easy to change) (Recommended)
B. Material UI (MUI) — a complete, opinionated library
C. Chakra UI
X. Other (please specify)

[Answer]: A

### Question 3 — How the questionnaire is presented
The reference onboarding shows an "N / 23" counter on every question screen.

A. One question per screen with a progress bar and "N of M" count, Back and Next buttons (matches the reference; works well on phones) (Recommended)
B. A few related questions per page (fewer screens, more scrolling)
X. Other (please specify)

[Answer]: A

### Question 4 — Light and dark appearance
A. Light only, matching the reference (Recommended)
B. Light and dark, following the device setting
X. Other (please specify)

[Answer]: A

### Question 5 — The web report layout
[RD] describes two report surfaces: the Home dashboard (the web "Protocol Summary") and the 16-page PDF. The interactive report screen (client `FR-018`) needs its own web layout.

A. A single scrolling web report that follows the PDF's section order, with a sticky table of contents on desktop and a contents drawer on phones; the Facial Assessments sit at the top, after the preamble (Recommended)
B. A tabbed report (Overview / Assessments / Features / Recommendations)
X. Other (please specify)

[Answer]: A
