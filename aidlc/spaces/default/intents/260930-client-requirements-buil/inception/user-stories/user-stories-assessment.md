# User Stories — Assessment

## Decision
**Execute.**

## Rationale
The platform is almost entirely user-facing. One paying end user moves through a multi-step journey — sign-up with an emailed code, consent and questionnaire, three photos with enforced validation, payment, background analysis, report, AI visuals, chat and settings (`requirements.md` FR1–FR14, client `WF-001`). Each step has its own business rules, failure cases and screens. Stories turn those requirements into small pieces of user value with testable acceptance criteria, and they are what the human asked for ("write user stories, and plan the implementation as phases (units) mapped to stories").

## Factors considered
- **Project type:** greenfield, two applications (Next.js frontend, FastAPI backend) over PostgreSQL (`NFR1`).
- **User-facing scope:** 14 functional requirement groups, 12 of them with screens the user touches directly.
- **Complexity signals:** custom authentication with token rotation and reuse detection (FR2, FR3); backend-enforced photo validation with a same-person vote (FR6); a paywall that must be enforced on the server (FR7); a background AI pipeline with retries (FR8, FR10); auto-published reports with no human review (FR9.8).
- **Personas:** one functional role today (End User), whose motivation and emotional state change how the product must behave (FR8.5 tone; FR12.2 medical refusals). The future Admin role is out of scope.
- **Cross-cutting rules:** toasts, confirmation dialogs, consent, cost limits and sensitive-data rules touch many stories (FR14, NFR3, NFR10).

## Where stories add the most value
- Turning the auth and session rules into user-visible behaviour a tester can check (sign-in survives reload; never logged out by a network blip).
- Making the photo-validation and identity-check rules concrete from the user's point of view (what they see, when Continue is blocked).
- Pinning down the paid path end to end (pay → start → progress → report), including what the user sees when something fails.
- Giving Units Generation and Delivery Planning a story map to group into phases, starting with the walking skeleton (sign-up → code → login → "who am I").
