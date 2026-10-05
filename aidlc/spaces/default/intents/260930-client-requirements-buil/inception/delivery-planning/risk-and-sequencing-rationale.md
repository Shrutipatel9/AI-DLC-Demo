# Risk and Sequencing Rationale — AI Facial Analysis Platform

Why the Bolts are in the order they are. A **Bolt** is one build pass over a piece of the work that ends in something that runs (see `bolt-plan.md`). The order must respect the unit dependency map from Units Generation (`unit-of-work-dependency.md`). Within that, the order is a value judgment: yours, recorded in `delivery-planning-questions.md`.

## Heuristic used
**Walking skeleton first, then risk-first** (delivery Q1):
- The *walking skeleton* (Cockburn, *Crystal Clear*) is a minimal version that runs the whole way through, built first to prove the pieces connect.
- *Risk-first* (Boehm, spiral model) tackles the highest-uncertainty work as early as the dependencies allow, so later work is calibrated against reality.

No formal WSJF scoring was done (delivery Q2). WSJF, Weighted Shortest Job First (Reinertsen / SAFe), ranks work by value, urgency and risk reduction divided by size. It was skipped because the dependency map leaves almost no ordering freedom.

## How much freedom the dependency map leaves
The map is a near-linear chain: U1 → U2 → U3 → U4 → U5 → U6 → U7 → U8, then U9 and U10 (both after U8, independent of each other). Each step of the user journey genuinely needs the one before it:
- the photo screen follows the submitted questionnaire;
- payment needs a valid photo set;
- analysis needs payment and answers;
- images need the analysis run;
- the report needs text and images;
- chat and routing need the report.

**The only free choice is U9 before U10.** U9 (chat) comes first because it carries a safety risk (medical advice) that should be exercised before the final whole-journey checks in U10, and U10's end-to-end journeys and traceability report are most useful once every feature exists.

**This plan does not deviate from the topological order.**

## Where risk-first shows up
Since the order is mostly fixed, risk-first is applied *inside* Bolts, by pulling risk-reducing checks forward to the earliest Bolt that can run them. Each one answers one of your four worries (delivery Q6):

| Worry (Q6) | Risk | Earliest point it can be reduced | What is pulled forward |
|---|---|---|---|
| C. Sign-in security | Subtle token, OTP or session bugs; spurious logouts | Bolt 1 and Bolt 2 (first two Bolts) | OTP/JWT services and the refresh client built test-first, with exact time boundaries; security engineer review on both Bolts |
| B. Photo-check accuracy | Thresholds reject good photos or accept mismatched people; no human review after (`CON-006`) | Bolt 4 | Calibration on a small consented, diverse photo set before payment is built on top; 8-case identity table test-first |
| A. AI quality and 10-minute target | Narratives unsafe or generic; 24 images too slow | Bolt 6 (text), Bolt 7 (images) — the first Bolts where the vendors are wired | Opt-in evaluation suite on real models in Bolt 6; timed full real-vendor run in Bolt 7, before the report UI is built on top |
| D. AI cost per report | 24 `gpt-image-1` edits + text may cost too much per sale | Bolt 6/7 | Cost per report recorded in Bolt 7; image concurrency and retry caps configurable; account budget limit set before Bolt 6 |

**An option not taken:** a throwaway image-generation spike right after Bolt 1 would surface worries A and D a few weeks earlier. It needs the OpenAI key early and builds nothing reusable. If you want it, it can be added as a short experiment between Bolts 1 and 2 without changing the units. It is noted here so you can ask for it at the approval step.

## Risk register

| Risk | Likelihood | Impact | Mitigation | Bolt |
|---|---|---|---|---|
| Auth rules implemented subtly wrong (reuse detection, lockout timing) | Medium | High | Test-first with an injectable clock; security review; exact boundary criteria | 1, 2 |
| Multi-tab refresh causes logouts | Medium | Medium | Cross-tab coordination (ADR-006), test-first | 2 |
| Photo thresholds wrong for real users (lighting, skin tones, phones) | High | High | Configurable thresholds; calibration set with diversity; photo-focused reasons | 4 |
| Same-person heuristic false positives or negatives (`ASM-010`) | Medium | High | 8-case vote tested; threshold calibrated; flagged for tuning pass | 4 |
| Stripe webhook arrives late or twice | Medium | Medium | Confirming state; idempotency by event id with a database constraint | 5 |
| Medical answers leak to AI | Low | Critical | Structural isolation (ADR-007) + canary tests | 3, 6 |
| AI narrative tone harmful to anxious users | Medium | High | Tone instruction, schema validation, evaluation set, static disclaimers | 6 |
| 24 images exceed 10 minutes | High | Medium | Concurrency, back-off, image failures don't block publishing; timed run | 7 |
| Image cost per report too high (`ASM-011`) | Medium | High | Cost recorded in Bolt 7; vendor swappable (`NFR-013`); retry caps | 7 |
| AI images don't resemble the user | Medium | High | High-fidelity edit mode; manual likeness check; vendor swappable | 7 |
| PDF rendering coupled to the frontend | Medium | Medium | Backend-owned template (domain review R-01) | 8 |
| Client specifications change after build ([QS] open items, 3 vs 7 angles) | Medium | Medium | Data-driven questionnaire and angle set; content changes need no code | 3, 4 |
| Open contract gaps (image delivery to the browser, missing read interfaces, error codes) | High | Medium | Resolved in each unit's Functional Design before code (contract review R-01, R-03, R-04) | 6, 8, 10 |

## Deviations from the dependency order
None.
