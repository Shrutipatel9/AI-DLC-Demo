# Personas — AI Facial Analysis Platform

The client document defines one functional role in scope: the **End User** (client Section 3). The Admin is a future role and is out of scope (client §2.2), so it has no persona here. The End User is split into three personas by motivation and emotional state, because the product must behave differently for them: narrative tone (`requirements.md` FR8.5), safety of chat answers (FR12.2), and the disclaimer and consent steps (FR4.1, FR4.4). One further persona stands for the people who will keep building the product after handover (client `BC-005`); it is used only for enabler stories.

These are **[Recommendation]** personas derived from the client document and the answers in `user-stories-questions.md` (Q1). They are not market research.

---

## P1 — Maya, the goal-driven self-improver
- **Role:** End User.
- **Context:** In their late 20s to 30s. Has already read about facial aesthetics and Qoves-style reports, and has specific features they want to work on.
- **Goals:**
  - Get an objective, measurement-based view of their face.
  - Get concrete, tiered actions they can take — at home, over the counter, in clinic (FR9.4).
  - Revisit the report and ask follow-up questions (FR12).
- **Pain points:**
  - Expert reports are expensive and slow (client `BC-002`).
  - Generic advice that ignores their stated goals.
- **Tech comfort:** High. Often on a phone, and uses camera capture.
- **Frequency:** One purchase, then several return visits to the report, visuals and chat.
- **What it means for the product:** Measurements must be cited in narratives (FR8.4). Priority features and the protocol summary on Home matter most (FR11.1).

## P2 — Sam, the curious first-timer
- **Role:** End User.
- **Context:** Found the product through the landing page and is not sure what a "facial analysis" involves. Price-sensitive and cautious about uploading photos.
- **Goals:**
  - Understand what they get before paying (FR1.3 "How it works").
  - Get through photos without repeated rejections.
  - See fun AI visuals of themselves — hairstyles, outfits, aging (FR10.3).
- **Pain points:**
  - Unclear photo rules and vague rejection messages.
  - Fear of paying and getting nothing, or of losing progress.
- **Tech comfort:** Medium. Mixed phone and desktop use.
- **Frequency:** One-off purchase. Likely to drop off at photos or payment if friction is high.
- **What it means for the product:**
  - Clear photo requirements (FR5.1) and specific rejection reasons (FR6.1).
  - A payment screen with no teaser but a clear promise (FR7.1).
  - Visible progress during analysis (FR8.2).

## P3 — Jordan, the anxious checker
- **Role:** End User.
- **Context:** Thinks about their appearance often and may show elevated appearance-related distress in the questionnaire. May also have medical or medication questions.
- **Goals:**
  - Reassurance and a balanced view, not a list of flaws.
  - Safe answers from the assistant.
- **Pain points:**
  - Harsh or clinical language.
  - Recommendations that feel like medical advice.
  - Worry about where their face data goes.
- **Tech comfort:** Medium.
- **Frequency:** One purchase. May re-read the report many times.
- **What it means for the product:**
  - A measured, reassuring tone when answers show distress (FR8.5).
  - The disclaimer gate (FR4.4).
  - An explicit consent step (FR4.1).
  - Medical answers never sent to AI (FR8.6).
  - The assistant refuses medical questions and points to a professional (FR12.2).
  - **[Recommendation — Q11]** The same care on screens, not only in AI text: the "Understanding Your Results" preamble comes before any score; every AI image is labelled as an AI-generated illustration; photo rejection and mismatch messages describe the photo, never the person.
  - **[Recommendation — Q13]** A user who cannot confirm the disclaimer sees a calm, supportive explanation with a pointer to professional help rather than a silent dead end.
- **Priority note:** P3 sets the safety bar for all AI-generated content. Stories must pass P3's acceptance criteria even when written for P1 or P2.

## P4 — Dev, the client's continuing developer (enabler persona)
- **Role:** A member of the client's own team who will extend the codebase after handover, often with AI-assisted tools (client `BC-005`, `NFR-011`). The delivery team works in the same shoes during the build.
- **Goals:**
  - Clone the repo, run both apps locally, and trust the checks.
  - Swap vendors and change prices or thresholds through configuration.
- **Pain points:**
  - Hidden coupling.
  - Hardcoded keys.
  - Tests that call paid APIs.
- **Tech comfort:** High.
- **Frequency:** Daily.
- **What it means for the product:**
  - Enabler stories for the repository, local setup, CI, security tooling, configuration, vendor adapters and background jobs (team practices; NFR1, NFR6, NFR7, NFR8, NFR11).

---

## Persona priority
1. **P1 Maya** — primary buyer; most stories are written for P1.
2. **P3 Jordan** — sets the safety and tone bar for every AI-facing story.
3. **P2 Sam** — sets the clarity bar for landing, photos and payment.
4. **P4 Dev** — enabler stories only.

## Relationships
P1, P2 and P3 are the same role at different points on the motivation and anxiety spectrum. A real user can move between them; for example, a P2 who answers the questionnaire in a way that shows distress is treated as P3 by FR8.5. P4 never uses the product as an end user.

**Accessibility [Recommendation — Q12]:** any persona may use a screen reader, keyboard-only input, screen magnification or reduced motion. Accessibility criteria come from NFR9 and apply to every persona.
