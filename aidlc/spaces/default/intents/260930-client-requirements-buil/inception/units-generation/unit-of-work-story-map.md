# Unit ↔ Story Map — AI Facial Analysis Platform

Every story in `inception/user-stories/stories.md` is mapped to exactly one unit (`unit-of-work.md`). Within each unit, stories are listed in implementation order: each story comes after the stories it depends on (its `Deps`). Every story dependency points to the same unit, earlier in this order, or to a unit this unit depends on (`unit-of-work-dependency.md`). This was checked by script. There is one known exception, explained below.

## Story → unit

| Story | Title | Priority | Unit ID | Directory | Order in unit |
|---|---|---|---|---|---|
| US1.1 | Two-app repository with documentation | Must | U1 | `u1-walking-skeleton` | 1 |
| US1.2 | Local environment with PostgreSQL and a mail catcher | Must | U1 | `u1-walking-skeleton` | 2 |
| US1.5 | Configuration instead of hardcoded values | Must | U1 | `u1-walking-skeleton` | 3 |
| US1.8 | Safe handling of personal data across the API | Must | U1 | `u1-walking-skeleton` | 4 |
| US1.3 | Pull-request checks in GitHub Actions | Must | U1 | `u1-walking-skeleton` | 5 |
| US1.4 | Security tooling | Must | U1 | `u1-walking-skeleton` | 6 |
| US1.6 | Email delivery with a fake and a local sink | Must | U1 | `u1-walking-skeleton` | 7 |
| US1.9 | Frontend auth store and single API client | Must | U1 | `u1-walking-skeleton` | 8 |
| US3.1 | Sign up with name, email and password | Must | U1 | `u1-walking-skeleton` | 9 |
| US3.2 | Verify my email code to finish signing up | Must | U1 | `u1-walking-skeleton` | 10 |
| US3.4 | Log in with password and emailed code | Must | U1 | `u1-walking-skeleton` | 11 |
| US3.8 | See who I'm signed in as | Must | U1 | `u1-walking-skeleton` | 12 |
| US11.7 | Feedback, confirmations and form errors everywhere | Must | U2 | `u2-session-security` | 1 |
| US3.3 | Resend a code and lockout after wrong attempts | Must | U2 | `u2-session-security` | 2 |
| US3.5 | Stay signed in across reloads and restarts | Must | U2 | `u2-session-security` | 3 |
| US3.6 | Refresh-token reuse detection and CSRF checks | Must | U2 | `u2-session-security` | 4 |
| US3.7 | Log out | Must | U2 | `u2-session-security` | 5 |
| US3.9 | Reset a forgotten password | Must | U2 | `u2-session-security` | 6 |
| US3.10 | Session renews itself quietly | Must | U2 | `u2-session-security` | 7 |
| US3.11 | Two tabs don't log each other out | Must | U2 | `u2-session-security` | 8 |
| US11.5 | Change my password | Must | U2 | `u2-session-security` | 9 |
| US4.1 | Consent to facial analysis before starting | Must (delivery-team decision, Q5) | U3 | `u3-onboarding` | 1 |
| US4.2 | Answer the questionnaire with branching | Must | U3 | `u3-onboarding` | 2 |
| US4.3 | Disclaimer before submitting | Must | U3 | `u3-onboarding` | 3 |
| US4.4 | Load the real 23 questions | Must | U3 | `u3-onboarding` | 4 |
| US1.10 | Private media storage | Must | U4 | `u4-photos` | 1 |
| US1.11 | Face landmark service | Must | U4 | `u4-photos` | 2 |
| US5.1 | See the photo requirements first | Must | U4 | `u4-photos` | 3 |
| US5.2 | Upload a photo for each angle | Must | U4 | `u4-photos` | 4 |
| US5.3 | Take a photo with my camera | Must | U4 | `u4-photos` | 5 |
| US5.5 | Clear reasons for basic photo checks | Must | U4 | `u4-photos` | 6 |
| US5.10 | Pose and covered-face checks | Must | U4 | `u4-photos` | 7 |
| US5.6 | Same-person decision across my three photos | Must | U4 | `u4-photos` | 8 |
| US5.11 | Review screen for the same-person check | Must | U4 | `u4-photos` | 9 |
| US5.8 | Location data removed from my photos | Should (delivery-team recommendation, Q5) | U4 | `u4-photos` | 10 |
| US5.9 | Validation thresholds from the specification | Must | U4 | `u4-photos` | 11 |
| US6.1 | Payment screen once my photos are ready | Must | U5 | `u5-payments` | 1 |
| US6.2 | Pay with Stripe Checkout | Must | U5 | `u5-payments` | 2 |
| US6.3 | Payment confirmed by Stripe | Must | U5 | `u5-payments` | 3 |
| US6.4 | No analysis or report without payment | Must | U5 | `u5-payments` | 4 |
| US6.5 | Confirming my payment | Must | U5 | `u5-payments` | 5 |
| US1.7 | Background jobs with progress | Must | U6 | `u6-analysis-core` | 1 |
| US1.12 | OpenAI text and image adapters with fakes | Must | U6 | `u6-analysis-core` | 2 |
| US7.1 | Start my analysis | Must | U6 | `u6-analysis-core` | 3 |
| US7.6 | Analysis pipeline that resumes safely | Must | U6 | `u6-analysis-core` | 4 |
| US7.2 | Watch progress and come back later | Must | U6 | `u6-analysis-core` | 5 |
| US7.3 | Measurements from my front photo | Must | U6 | `u6-analysis-core` | 6 |
| US7.7 | Ear measurements | Must | U6 | `u6-analysis-core` | 7 |
| US7.8 | Hair, Skin and Neck assessments | Must | U6 | `u6-analysis-core` | 8 |
| US7.5 | Symmetry and facial thirds | Must | U6 | `u6-analysis-core` | 9 |
| US7.10 | Dimorphism, prototypicality and face shape | Must | U6 | `u6-analysis-core` | 10 |
| US7.4 | Safe, personal AI requests | Must | U6 | `u6-analysis-core` | 11 |
| US7.9 | Write my report text | Must | U6 | `u6-analysis-core` | 12 |
| US7.11 | A failed paid run can be re-run once | Must (delivery-team decision, Q8) | U6 | `u6-analysis-core` | 13 |
| US9.1 | Before/after image for each feature | Must | U7 | `u7-ai-images` | 1 |
| US9.2 | Hairstyle variations | Must | U7 | `u7-ai-images` | 2 |
| US9.3 | Outfit variations | Must | U7 | `u7-ai-images` | 3 |
| US9.4 | Healthy-aging preview | Must | U7 | `u7-ai-images` | 4 |
| US9.5 | Retry an image that failed | Must | U7 | `u7-ai-images` | 5 |
| US8.1 | Report data I own | Must | U8 | `u8-report-home` | 1 |
| US8.7 | Read my 11-feature report | Must | U8 | `u8-report-home` | 2 |
| US8.2 | Recommendations in three tiers | Must | U8 | `u8-report-home` | 3 |
| US8.3 | Explore my assessments and jump around my report | Must | U8 | `u8-report-home` | 4 |
| US8.8 | Dimorphism, prototypicality and face-shape views | Must | U8 | `u8-report-home` | 5 |
| US8.4 | Per-feature metric tables | Must | U8 | `u8-report-home` | 6 |
| US8.6 | Face Shape and Skin views | Must | U8 | `u8-report-home` | 7 |
| US8.5 | Download my report as a PDF | Must | U8 | `u8-report-home` | 8 |
| US11.1 | Home Overview | Must | U8 | `u8-report-home` | 9 |
| US11.2 | Move around easily | Must | U8 | `u8-report-home` | 10 |
| US11.3 | Protocol section | Must | U8 | `u8-report-home` | 11 |
| US10.1 | Ask questions about my report | Must | U9 | `u9-beauty-assistant` | 1 |
| US10.2 | Medical questions are declined | Must | U9 | `u9-beauty-assistant` | 2 |
| US10.3 | Daily chat limit | Should (delivery-team decision, Q5) | U9 | `u9-beauty-assistant` | 3 |
| US11.8 | Pick up where I left off | Must | U10 | `u10-journey-settings` | 1 |
| US2.1 | Landing page with clear entry points | Must | U10 | `u10-journey-settings` | 2 |
| US2.2 | See how it works before starting | Must | U10 | `u10-journey-settings` | 3 |
| US5.7 | Sent back to fix inconsistent photos | Must | U10 | `u10-journey-settings` | 4 |
| US11.4 | Account info | Must | U10 | `u10-journey-settings` | 5 |
| US11.6 | Billing | Must | U10 | `u10-journey-settings` | 6 |
| US1.13 | Requirement-to-test map, journeys and accessibility checks | Must | U10 | `u10-journey-settings` | 7 |

## Stories per unit (implementation order)

- **U1 `u1-walking-skeleton`** (12): US1.1 → US1.2 → US1.5 → US1.8 → US1.3 → US1.4 → US1.6 → US1.9 → US3.1 → US3.2 → US3.4 → US3.8
- **U2 `u2-session-security`** (9): US11.7 → US3.3 → US3.5 → US3.6 → US3.7 → US3.9 → US3.10 → US3.11 → US11.5
- **U3 `u3-onboarding`** (4): US4.1 → US4.2 → US4.3 → US4.4
- **U4 `u4-photos`** (11): US1.10 → US1.11 → US5.1 → US5.2 → US5.3 → US5.5 → US5.10 → US5.6 → US5.11 → US5.8 → US5.9
- **U5 `u5-payments`** (5): US6.1 → US6.2 → US6.3 → US6.4 → US6.5
- **U6 `u6-analysis-core`** (13): US1.7 → US1.12 → US7.1 → US7.6 → US7.2 → US7.3 → US7.7 → US7.8 → US7.5 → US7.10 → US7.4 → US7.9 → US7.11
- **U7 `u7-ai-images`** (5): US9.1 → US9.2 → US9.3 → US9.4 → US9.5
- **U8 `u8-report-home`** (11): US8.1 → US8.7 → US8.2 → US8.3 → US8.8 → US8.4 → US8.6 → US8.5 → US11.1 → US11.2 → US11.3
- **U9 `u9-beauty-assistant`** (3): US10.1 → US10.2 → US10.3
- **U10 `u10-journey-settings`** (7): US11.8 → US2.1 → US2.2 → US5.7 → US11.4 → US11.6 → US1.13

## Known exception: US6.2 → US1.12

`stories.md` lists US1.12 (OpenAI text and image adapters, in U6) as a dependency of US6.2 (Stripe Checkout, in U5). The dependency is really on *a Stripe adapter with a fake*. No story owns that adapter — the product lead raised this at the user-stories gate (finding R-01), and it was accepted open. **Resolution in this plan:** U5 builds the Stripe adapter and its fake as part of US6.2 (see `unit-of-work.md` U5), following the adapter pattern established in U1 (US1.6, the email adapter). So U5 does not need U6, and the DAG stays as recorded. Contract Design should name the Stripe port explicitly.

## Cross-cutting stories

Some stories are built in one unit but their rules apply everywhere after it:

| Story | Built in | Applies to |
|---|---|---|
| US1.3 PR checks, US1.4 security tooling, US1.5 configuration | U1 | Every unit: each adds its settings, tests and lint rules to the same gates |
| US1.8 safe personal data (ownership, logging, errors) | U1 | Every unit with user data; each resource story repeats its own ownership check |
| US1.9 auth store and API client | U1 | Every frontend call in every unit |
| US11.7 toasts, dialogs, inline form errors | U2 | Every screen from U2 on |
| US1.10 private media storage | U4 | U6 (photos for measurement), U7 (generated images), U8 (PDF) |
| US1.11 face landmark service | U4 | U6 (measurements) |
| US1.12 OpenAI adapters | U6 | U7 (images), U9 (chat) |
| US1.13 requirement-to-test map, journeys, accessibility | U10 | The whole product; earlier units already keep their own tests and axe checks green |
| US11.8 journey routing | U10 | Replaces the temporary step links used by U1–U9 |

## Coverage check

- Stories assigned: **80 of 80**; no story is assigned twice.
- Every unit has stories: U1 12 · U2 9 · U3 4 · U4 11 · U5 5 · U6 13 · U7 5 · U8 11 · U9 3 · U10 7.
- `traceability.json` maps every story to its unit ID.
