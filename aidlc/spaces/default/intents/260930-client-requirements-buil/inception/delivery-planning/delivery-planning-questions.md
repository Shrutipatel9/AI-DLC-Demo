# Delivery Planning — Questions

This stage turns the 10 units (`inception/units-generation/unit-of-work.md`) into a build plan. The plan is made of **Bolts** — a Bolt is one build pass over a piece of the work that ends in something that runs and can be demonstrated. Units Generation recorded what depends on what. The order the Bolts ship in, and why, is a value judgment, so it's your call.

Context that narrows the choices:
- The team always builds a **walking skeleton** first — a minimal version that runs the whole way through, built to prove the pieces connect before the real features go in. That is unit U1.
- The unit dependency map is almost a straight line, because each journey step needs the one before it: U1 → U2 → U3 → U4 → U5 → U6 → U7 → U8, then U9 and U10. Only U9 (chat) and U10 (routing, settings and final checks) are independent of each other.
- Construction currently builds one unit at a time, each unit's design and code finished and checked before the next.

Pick one letter per question (or X and describe your own answer).

---

### Question 1 — What to build first
A. The walking skeleton (U1), then follow the journey order. Within that order, get to the riskiest parts as early as the dependencies allow: the photo checks (U4) and the analysis and AI work (U6, U7) (Recommended)
B. The walking skeleton, then strictly the journey order with no special attention to risk
C. The walking skeleton, then the most valuable, demonstrable parts first (report and visuals), using fake data until the real pipeline exists
X. Other (please specify)

[Answer]: A

### Question 2 — Formal scoring
WSJF (Weighted Shortest Job First) ranks work by value, urgency and risk reduction divided by size.

A. No formal scoring: with an almost straight dependency chain there is very little order left to choose, so a written risk-first rationale is enough (Recommended)
B. Score every Bolt with WSJF anyway, for the record
X. Other (please specify)

[Answer]: A

### Question 3 — Bolt size
A. One unit per Bolt — 10 Bolts, each with its own demo and approval (Recommended)
B. Bundle the smaller units: U3 onboarding with U4 photos, and U9 chat with U10 — 8 Bolts
X. Other (please specify)

[Answer]: A

### Question 4 — Building Bolts at the same time
A. One after another, each finished and approved before the next starts (Recommended — it matches the current one-unit-at-a-time setting and keeps review simple)
B. Allow U9 and U10 to be built in parallel once U8 is approved
X. Other (please specify)

[Answer]: A

### Question 5 — Outside dependencies
Some things come from outside the build: an OpenAI API key and budget, a Stripe test account, an email provider, and the client's confirmations (the 23-question spec's open items, 3 photo angles vs 7, consent and disclaimer wording, which countries users are in).

A. Build against fakes until each is needed; get the Stripe test keys before the payment Bolt (U5) and the OpenAI key and budget before the analysis Bolt (U6); the email provider can wait (local mail catcher); client confirmations are chased in parallel and don't block Bolts (Recommended)
B. All keys and accounts are already available now
X. Other (please specify)

[Answer]: A

### Question 6 — What worries you most (select all that apply)
These get extra attention: earlier testing, earlier real-vendor checks, or spikes.

A. AI output quality and the 10-minute analysis target (24 images per report)
B. Photo validation and same-person accuracy on real photos
C. Sign-in and session security getting subtly wrong
D. AI cost per report
X. Other (please specify)

[Answer]: A, B, C, D

### Question 7 — The check that verifies each finished unit
Each finished unit is verified with one project command (for example, running all tests plus the end-to-end journey). The project has no code yet, so no such command exists.

A. Decide it at the first checkpoint: U1 creates the command (for example `make verify` running lint, types, tests and the Playwright skeleton journey), and I'll ask you to approve it then (Recommended)
B. Name the command now, before it exists
X. Other (please specify)

[Answer]: A

### Question 8 — Who builds
A. I build every Bolt from this session, one unit at a time, and you approve each one (Recommended)
B. Each of your teams owns a unit and approves its own work independently
X. Other (please specify)

[Answer]: A
