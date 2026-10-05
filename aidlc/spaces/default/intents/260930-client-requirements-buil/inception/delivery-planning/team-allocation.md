# Team Allocation — AI Facial Analysis Platform

A **Bolt** is one build pass over a piece of the work that ends in something that runs and can be demonstrated (see `bolt-plan.md`). A **mob** is the group that builds a Bolt together.

## Staffing decision
The Team Formation stage did not run in this workflow (it starts at Inception), and you chose to have every Bolt built from this session, one unit at a time, with your approval at each checkpoint (delivery Q8). There is therefore one mob:
- **Builder:** the AI developer (aidlc-developer-agent).
- **Reviewers:** the quality engineer and security engineer at each Bolt's Build-and-Test step.
- **Decision-maker:** you, at every plan approval and checkpoint.

| Bolt | Unit | Builds | Reviews and checks | Approves |
|---|---|---|---|---|
| 1 | U1 walking skeleton | AI developer | Quality engineer; security engineer (auth, secrets, CI gates) | You (skeleton checkpoint + verification command) |
| 2 | U2 session security | AI developer | Security engineer (token and session rules); quality engineer (boundary tests) | You |
| 3 | U3 onboarding | AI developer | Quality engineer; security engineer (health-data isolation) | You |
| 4 | U4 photos | AI developer | Quality engineer (8-case table, calibration); security engineer (private media) | You |
| 5 | U5 payments | AI developer | Security engineer (webhook signature, idempotency); quality engineer | You |
| 6 | U6 analysis core | AI developer | Quality engineer (evaluation suite, resume tests); security engineer (no medical data to AI) | You |
| 7 | U7 AI images | AI developer | Quality engineer (timed real-vendor run, cost record) | You |
| 8 | U8 report and home | AI developer | Quality engineer (axe, PDF); designer check against the mockups | You |
| 9 | U9 beauty assistant | AI developer | Quality engineer (medical-decline evaluation set) | You |
| 10 | U10 journey and settings | AI developer | Quality engineer (full journeys, traceability report) | You |

## Settings recorded for the build
- **Unit ownership:** solo — one session builds every unit.
- **Iteration:** unit by unit. Each unit's design stages and code are finished and verified before the next unit starts. The walking skeleton (U1) is completed and approved first.
- **Execution:** serial (no parallel builds).
- **Checkpoints:** enabled. Each finished unit is verified with the project command created in Bolt 1 and approved by you.
- **Verification command:** not chosen yet. It will be proposed at the first checkpoint, once Bolt 1 has created it (delivery Q7).

## Handover note
The client's own team will continue development with AI-assisted tools (`BC-005`). Each Bolt's pull request cites the requirement IDs it implements (team practices). The client team can read the plan, stories and contracts alongside the code to pick up any unit.
