# Refined Mockups — AI Facial Analysis Platform

Mid-fidelity screen designs for every user-facing story. There were no rough mockups (this workflow starts at Inception), so each screen is designed directly from:
- `inception/user-stories/stories.md` (US IDs below)
- `inception/requirements-analysis/requirements.md`
- the working specifications in `aidlc/spaces/default/knowledge/`: [RD] `report_design_spec.md`, [RT] `report_template.md`, [QS] `onboarding_questionnaire_spec.md`, [PC] `photo_capture_spec.md`, [IV] `photo_identity_validation_spec.md`

**Design decisions** (`refined-mockups-questions.md`):
- One visual language across all screens, extended from [RD] §3 (Q1).
- Tailwind CSS + shadcn/ui (Q2).
- One question per screen (Q3).
- Light theme only (Q4).
- A single-scroll web report with a table of contents (Q5).

Component behaviour is in `interaction-spec.md`, tokens in `design-system-mapping.md`, and accessibility in `accessibility-checklist.md`.

**Reading the wireframes:**
- `[Button]` is a button; `(•)` is a radio; `[x]` is a checkbox; `▢` is an image slot; `…` means content continues.
- Wireframes are desktop unless marked **Phone** (360 px reference width).
- Copy in quotes is the intended wording. Wording marked **[Recommendation]** is ours, not the client's.

---

## 0. Global frame

### 0.1 App shells
| Shell | Used on | Header content |
|---|---|---|
| **Public** | Landing, sign-up, log-in, forgot password | Wordmark (left) · "Sign in" link (right; hidden on auth screens) |
| **Onboarding** | Consent → questionnaire → photos → payment → start → progress | Wordmark · step indicator "Step 2 of 5 · Questionnaire" · user menu |
| **App** | Home, Report, AI Visuals, Chat, Settings | Wordmark · Home · Report · AI Visuals · Chat · user menu (Settings, Log out) |

The Onboarding shell's step indicator uses the journey steps from US11.8: Consent, Questionnaire, Photos, Payment, Analysis.

```
Desktop App shell
┌──────────────────────────────────────────────────────────────────────────┐
│ ◆ Wordmark      Home   Report   AI Visuals   Chat           Maya ▾       │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   <main>                                              ┌───────────────┐  │
│                                                       │ Toast region  │  │
│                                                       └───────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘

Phone App shell (US11.2 AC11.2.2)
┌──────────────────────────────┐
│ ◆ Wordmark          ☰  Maya ▾│   ☰ opens a sheet: Home · Report ·
├──────────────────────────────┤     AI Visuals · Chat (one extra tap)
│ <main>                       │
│                              │   Toasts span full width under the
│ [toast, full width]          │   header and never cover it (AC11.7.5)
└──────────────────────────────┘
```

### 0.2 Session restore (US3.5 AC3.5.1)
While the refresh on app start is pending, protected pages show a centred brand loader with the text "Restoring your session…". Login is never flashed. The loader is skipped on public pages.

### 0.3 Error and not-found pages
- "Something went wrong on our side. Please try again." plus a request id in small text (US1.8 AC1.8.2) and a [Try again] button.
- 404: "We couldn't find that page." with a [Go to my next step] button (US11.8).

---

## 1. Landing (US2.1, US2.2)

```
┌──────────────────────────────────────────────────────────────────────────┐
│ ◆ Wordmark                                                   Sign in     │
├──────────────────────────────────────────────────────────────────────────┤
│  Your face, measured.                               ▢ hero illustration │
│  An AI facial analysis with a personal, non-surgical   (no real face)   │
│  report.                                                                 │
│  [ Get started ]                                                         │
├──────────────────────────────────────────────────────────────────────────┤
│  How it works                                                            │
│   ① Questionnaire  →  ② Photos  →  ③ Analysis  →  ④ Report               │
│   (each step fades/slides in on scroll; static if reduced motion)        │
├──────────────────────────────────────────────────────────────────────────┤
│  What you get · Privacy note (links: disclaimer, privacy)                │
│  Footer                                                                  │
└──────────────────────────────────────────────────────────────────────────┘
```
- Hero copy and every section below "How it works" are **[Recommendation]** (`FR-001`, `CON-003`).
- "Get started" goes to sign-up when signed out, or to the next unfinished step when signed in (AC2.1.3).
- **Phone:** everything stacks in one column, "How it works" becomes a vertical list, and "Get started" stays visible above the fold.
- **States:** static page only.

---

## 2. Account screens

### 2.1 Sign up (US3.1)
```
┌─────────────────────── Create your account ───────────────────────┐
│ Full name        [______________________]                         │
│ Email            [______________________]                         │
│ Password         [______________________] [Show]                  │
│   • At least 8 characters  • A letter and a number  (live ticks)  │
│ [ Create account ]                                                │
│ Already have an account? Sign in                                  │
└───────────────────────────────────────────────────────────────────┘
```
- The rule list shows before typing (WCAG 3.3.2), and each rule ticks as it is met. A common password gets the inline error "This password is too common — try another." (AC3.1.4).
- Errors appear inline under the field (AC11.7.4). An already-registered verified email shows "An account with this email already exists. Sign in instead?" (AC3.1.2).
- **States:** default · submitting (button spinner, fields read-only) · field errors · server error toast.

### 2.2 Enter your code (US3.2, US3.3; also used after login and for reset)
```
┌───────────────────── Check your email ─────────────────────┐
│ We sent a 6-digit code to m•••@example.com.                │
│ Code  [ _ _ _ _ _ _ ]   (one field, numeric keypad,        │
│                          paste and OTP autofill allowed)   │
│ [ Verify ]                                                 │
│ Didn't get it?  Resend code in 42s   → becomes [Resend]    │
│ Wrong email? Go back                                       │
└────────────────────────────────────────────────────────────┘
```
| State | Display |
|---|---|
| Expired (AC3.2.2) | Inline: "This code has expired." + [Send a new code] |
| Wrong code | Inline: "That code isn't right. 3 tries left." **[Recommendation: show remaining tries]** |
| Locked (AC3.3.3) | Inline: "Too many tries. You can try again at 14:32." Verify and Resend disabled, with the reason shown next to them |
| Resend cooldown (AC3.3.1) | The countdown text is announced once at start and once when resend becomes available (not every second) |
| Success | Sign-up: goes to Consent. Login: goes to the next unfinished step (US11.8) |

### 2.3 Log in (US3.4)
Email and password, then **Enter your code**. A wrong password shows "Email or password is incorrect." (AC3.4.2). There's also a "Forgot password?" link.
If the session was revoked for security, a banner above the form reads "You were signed out to keep your account safe. Please sign in again." (AC3.6.4).

### 2.4 Forgot password (US3.9)
1. **Request:** email field → [Send code] → always shows "If an account exists for that email, we've sent a code." (AC3.9.1). No toast reveals the outcome.
2. **Code:** the same component as 2.2.
3. **New password:** new + confirm fields, with the rule list from 2.1 → success → login screen with the banner "Password changed. Please sign in." A reset token that has expired or been reused shows "This reset has expired. Start again." with a link back to step 1.

---

## 3. Consent and questionnaire

### 3.1 Consent (US4.1)
```
┌──────────────── Before we start ────────────────┐
│ How we use your photos and answers               │
│ • Your photos and facial measurements are used   │
│   only to create your report.                    │
│ • Health-related answers never leave the         │
│   platform or go to the AI service.              │
│ • …configured consent text (versioned)           │
│ [x] I agree to the processing of my facial       │
│     images, measurements and answers for my      │
│     report.                                      │
│ [ Continue ]  (disabled until ticked, reason     │
│               shown: "Tick the box to continue") │
└──────────────────────────────────────────────────┘
```
The consent text comes from configuration and is **[Decided by delivery team — requirements Q2]**. The client must confirm the wording.

### 3.2 Question screen (US4.2, Q3)
```
Onboarding shell · Step 2 of 5 · Questionnaire
┌───────────────────────────────────────────────────────────┐
│ Question 5 of 22        ▓▓▓▓▓░░░░░░░░░░░░░░ (progress)     │
│                                                           │
│ Have you had any non-surgical aesthetic treatments        │
│ before?                                                   │
│   (•) Yes                                                 │
│   ( ) No                                                  │
│                                                           │
│ [ Back ]                                   [ Next ]       │
└───────────────────────────────────────────────────────────┘
```
- The "N of M" count reflects branching; M updates if a branching answer changes (AC4.2.1, AC4.2.5).
- **Input types** ([QS] §2):
  - **Free text:** single-line or multiline, with a character count.
  - **Single select:** radio group.
  - **Multi-select:** checkbox group. Q7's options are grouped under the four treatment-type headings.
  - **Yes/No with follow-up:** "Yes" reveals a text area inline, which is announced to screen readers (AC4.2.4).
- Answers save when the user presses Next (AC4.2.6). Back keeps earlier answers (AC4.2.5).
- **Phone:** Back and Next are fixed to the bottom, full width, 48 px tall.
- **States:** loading question set (skeleton) · validation ("Please choose an answer") · save failed (toast, answer kept on screen).

### 3.3 Final screen with disclaimer (US4.3, [QS] Q23 + §4)
```
│ Question 22 of 22                                         │
│ Anything else you think we should know?                   │
│ [__________________________________________]              │
│ ───────────────────────────────────────────────────────── │
│ [ ] I hereby confirm that I do not have any concerns      │
│     related to Body Dysmorphic Disorder … at my own       │
│     discretion.   ([QS] §4 wording, exact)                │
│ [ Submit ]  disabled · "Please confirm the statement      │
│             above to submit."                             │
│ I can't confirm this statement  (text link)               │
```
- **"I can't confirm this statement"** opens the supportive message (AC4.3.4) below.
- The message wording is **[Recommendation]** and needs client confirmation. The support resource is configurable, and none is invented here.
```
┌──────────────────────────────────────────────────────────┐
│ Thank you for being honest with us.                      │
│ This analysis focuses on appearance, so it isn't the     │
│ right fit when appearance concerns feel difficult. If    │
│ you'd like support, a qualified professional can help.   │
│ [configured support link]                                │
│ Your answers are saved. [ Back to the questionnaire ]    │
└──────────────────────────────────────────────────────────┘
```

---

## 4. Photos

### 4.1 Photo requirements (US5.1, [PC] §2)
Seven rule cards, each with an example image (a good-versus-bad pair with visible text labels):
- no glasses or hat;
- natural, even light;
- plain white background;
- hair tied back;
- no makeup;
- no neck-covering clothing;
- no filters.

Then [ I'm ready ]. **Phone:** the cards stack, and the button stays at the bottom.

### 4.2 Capture step, per angle (US5.2, US5.3, US5.5, US5.10)
```
Onboarding shell · Step 3 of 5 · Photos             Photo 2 of 3
┌────────────────────────────────────────────────────────────────┐
│ Left side (3/4 view)                                            │
│ Turn your head so your left cheek faces the camera, about 45°.  │
│ ▢ example image          Tips: arm's length · neutral face ·    │
│                          head and neck in frame  ([PC] §3)      │
│                                                                 │
│ [ Take a photo ]   [ Upload a photo ]                           │
│ JPEG, PNG or HEIC · up to 10 MB                                 │
└────────────────────────────────────────────────────────────────┘
```
| State | What the user sees |
|---|---|
| Camera open | Live view with a face-outline guide for this angle, [Capture], [Cancel]. **Phone portrait:** the view, guide and capture button fit without scrolling (AC5.3.4) |
| Camera denied / none | "We couldn't use your camera. You can upload a photo instead." Only upload is shown (AC5.3.2) |
| Preview | The photo + [Retake] [Use this photo] |
| Checking | The photo dimmed + "Checking your photo…", announced politely (AC5.2.5) |
| Accepted | ✓ "Looks good" (text + icon), then the next angle |
| Rejected | ⚠ plus a photo-focused reason and fix, for example "Move closer so your face fills more of the frame." or "We could see more than one face — please make sure only you are in the photo." Then [Retake] (AC5.5.4) |
| Wrong type/size | "Please use a JPEG, PNG or HEIC photo under 10 MB." |

A thumbnail strip shows all angles with a status for each (✓ done, • current, ○ waiting), and "2 of 3" is also given as text (AC5.2.6).

### 4.3 Review — same-person check (US5.11, US5.6)
```
┌──────────────────────── Check your photos ────────────────────────┐
│  ▢ Front            ▢ Left side           ▢ Right side              │
│  ✓ Looks good       ✓ Looks good          ⚠ Doesn't match           │
│                                           [ Retake right side ]     │
│  ⚠ This photo doesn't seem to match the others. Try retaking it     │
│    in the same light and position.                                  │
│                                                                     │
│  Retake the highlighted photo to continue.   [ Continue ] (disabled)│
└─────────────────────────────────────────────────────────────────────┘
```
- Flags use a text label, an icon and a 3 px border, never colour alone (AC5.11.1). Each flag message is tied to its photo with `aria-describedby`.
- After a retake: "Checking your photos…"; Continue stays disabled while the result is pending, and nothing navigates automatically (AC5.11.3).
- When consistent: "All three photos match." Continue is enabled, and the user stays on this screen until they press it (AC5.11.4).
- **Phone:** photos stack in one column, each with its status and retake button, and Continue is fixed to the bottom with its reason above it (AC5.11.5).

---

## 5. Payment and start

### 5.1 Payment (US6.1, US6.2)
```
┌──────────────────── Unlock your analysis ────────────────────┐
│ One-time payment                         {price} {currency}   │
│ You'll get:                                                   │
│  • Your full 11-feature report, with PDF download             │
│  • AI visuals: hairstyles, outfits and a healthy-aging preview│
│  • The AI Beauty Assistant for questions about your report    │
│ Your analysis starts only when you press "Start Analysis".    │
│ [ Pay securely with Stripe ]                                  │
│ Payments are processed by Stripe.                             │
└───────────────────────────────────────────────────────────────┘
```
- The price and currency come from configuration; the list copy is **[Recommendation]** (AC6.1.2). No results or partial content appear here (`FR-015`).
- If the photo set became inconsistent, the user is returned to 4.3 with the flags shown (409, AC6.2.2).
- If the user cancels on Stripe, they come back here with the notice "Payment cancelled — you haven't been charged." (AC6.2.3).

### 5.2 Confirming payment (US6.5)
- A spinner + "Confirming your payment…" (live region).
- On confirmation, the screen switches in place to 5.3 without a reload, and the change is announced.
- After the configured wait: "Your payment is still being confirmed. You won't be charged twice. You can close this page and come back." + [Check again].

### 5.3 Start analysis (US7.1)
```
│ Payment confirmed ✓                                         │
│ Ready when you are. The analysis takes up to about 10       │
│ minutes and runs even if you leave.                         │
│ [ Start Analysis ]                                          │
```
The button disables on click so it can't be pressed twice, and a double click still creates only one job (AC7.1.3).

### 5.4 Analysis progress (US7.2, US7.11)
```
┌────────────────────── Analysing your photos ──────────────────────┐
│ ✓ Measuring your features             Done                          │
│ ● Writing your personal report        In progress                   │
│ ○ Creating your AI images             Waiting                       │
│ ○ Putting your report together        Waiting                       │
│                                                                     │
│ This usually takes up to 10 minutes. You can close this page —      │
│ we'll keep going and your results will be here when you return.     │
└─────────────────────────────────────────────────────────────────────┘
```
- Step states are text (Done / In progress / Waiting) plus an icon. Changes are announced politely without moving focus (AC7.2.1).
- **Ready:** "Your report is ready." + [View my report] → Home (AC7.2.4).
- **Failed (first time):** "Something went wrong on our side while creating your report. Your payment still covers it." + [Try again]. The re-run is free and doesn't repeat finished steps (AC7.11.1, AC7.11.2).
- **Failed twice:** the same message, then "Please contact support and we'll sort it out." + the support contact from configuration. No retry button is shown (AC7.11.3).

---

## 6. Home Overview — the "Protocol Summary" dashboard (US11.1, US11.3; [RD] §4)

```
Desktop (≥1024 px) — three columns per [RD] §4
┌──────────────────────────────────────────────────────────────────────────┐
│ PROTOCOL | Maya #A1B2C3 · 30 Sep 2026                ◆ Wordmark          │
├──────────────┬──────────────┬─────────────────────────────────────────────┤
│ Overall 72/100│ Evaluated 170+│ Analysis time 8 min                        │  ← stat tiles
├──────────────┴──────────────┴──────────────┬──────────────────────────────┤
│ LEFT                  │ MIDDLE              │ RIGHT                        │
│ Identity card         │ ▢ BEFORE ▢ POTENTIAL│ Treatment Protocol           │
│ "Your Facial          │  (AI illustration   │  PHASE 01 · title · timing   │
│  Analysis" (3 steps)  │   label on POTENTIAL)│  • driving findings          │
│ Priority Features to  │ Facial Age  28      │  closing paragraph           │
│ Improve (table)       │  5 ──●────── 65     │ [Download PDF]               │
│  Skin 54/100 Needs    │ Harmony Profile     │ Report status: Ready         │
│  attention            │  (6-axis radar) +   │                              │
│   Evenness — …        │  [Show as table]    │                              │
│                       │ Overview paragraph  │                              │
├───────────────────────┴─────────────────────┴──────────────────────────────┤
│ Feature Evaluation (Zone | Finding | Reference)                           │
└──────────────────────────────────────────────────────────────────────────┘
```
- **Tablet (768–1023 px):** two columns (left + middle), with the right column below. **Phone:** a single column in this order: stat tiles → Before/Potential → Priority features → Protocol → Harmony (with its table) → Facial Age → Overview → Feature Evaluation (as stacked cards).
- **Radar chart:** the six axes follow [RD] §12.1 and include Symmetry. There's a visible "Show as table" toggle, and value labels appear at each point (AC11.1.4). An axis with no score is not plotted and is shown as "Not scored".
- **Open items, not invented:**
  - which features qualify as Priority features ([RD] §13.1, Functional Design);
  - one or several Protocol phases ([RD] §14 / §20.3);
  - whether Facial Age is shown at all — it isn't in the client's `FR-017` list; [RD] §15 adds it, so it's included as working-spec content.
- **States:**
  - loading skeleton;
  - image slot pending ("Creating image…");
  - image slot not available: "Image not available yet" + [Try again], with the retry count shown (AC9.5.2–AC9.5.4).

---

## 7. Report — single scroll with table of contents (US8.1–US8.8; Q5)

```
Desktop
┌──────────────┬───────────────────────────────────────────────────────────┐
│ Contents     │ Understanding Your Results   (preamble first — AC8.7.2)   │
│ (sticky)     │ Introduction · Limitations & disclaimer (template copy)    │
│ • Understanding│ ──────────────────────────────────────────────────────── │
│ • Assessments │ Facial Assessments                                        │
│   – Symmetry  │   Symmetry  81/100 · "Quite Symmetric" · Regional Balance  │
│   – Thirds    │   Facial thirds  upper · middle · lower (bars + values)    │
│   – Dimorphism│   Dimorphism  (display-only sliders, values in text)       │
│   – Prototyp. │   Prototypicality · Face shape wireframe                   │
│ • Features    │ ──────────────────────────────────────────────────────────  │
│   – Hair …    │ Hair                                                       │
│   – Ears      │  ▢ BEFORE        ▢ AFTER · AI-generated illustration       │
│ • Recommend-  │  Narrative (3–5 sentences) · Projected potential ideas      │
│   ations      │  Metrics table (scrolls sideways on its own on phones)      │
│              │  ┌ Summary ─────────────── (sage box) ┐                     │
│ [Download PDF]│ … Eyebrows … Ears (fixed order, 11 features)               │
│              │ Closing recommendations                                    │
│              │  At home · Over the counter · In clinic (tier captions)     │
│              │  "Consult a qualified professional…" (static copy)          │
└──────────────┴───────────────────────────────────────────────────────────┘
Phone: a "Contents" button opens a drawer; picking an entry closes the drawer,
scrolls to the section and moves focus to its heading (AC8.3.1).
```
- **Section order:**
  1. Understanding Your Results
  2. Introduction
  3. Limitations
  4. Facial Assessments
  5. the 11 features, in the fixed order
  6. Closing recommendations

  The preamble always comes before any score (Q11). The PDF keeps the [RD] §5–§10 page order.
- **Images:** each carries a badge chip (BEFORE / AFTER / POTENTIAL, [RD] §3.4) plus a visible text caption "AI-generated illustration" on generated images. Alt text names the photo and the feature (AC8.7.4).
- **Hair page:** the Hair Loss scale ([RD] §13.3), with the current stage marked by a border and a text label.
- **Face Shape and Skin views:** content per [RD] §9.2 / [RT] §10. 🔴 TBD items stay out (US8.6).
- **States:**
  - loading skeleton per section;
  - image pending or not available (as on Home);
  - PDF generating: the button shows "Preparing PDF…" and is disabled, then the download starts and a success toast appears;
  - PDF failed: an error toast + retry.

---

## 8. AI Visuals (US9.2–US9.5)
```
┌────────────────────────────── AI Visuals ─────────────────────────────┐
│ All images are AI-generated illustrations, not predictions.            │
│ Hairstyles        ▢ ▢ ▢ ▢ ▢     (grid; tap to enlarge in a dialog)       │
│ Outfits           ▢ ▢ ▢ ▢ ▢                                              │
│ Healthy aging     [You now] → [+3 years] → [+5 years] → [+10 years]      │
│                   (first card is your own photo, labelled "Your photo")  │
└────────────────────────────────────────────────────────────────────────┘
```
- **Phone:** each row becomes a horizontal carousel with visible previous/next buttons and "2 of 5" text. It can be swiped, but swiping is never the only way to move.
- **States:** image pending / not available / retry cap reached ("You've used all retries for this image").

## 9. AI Beauty Assistant (US10.1–US10.3)
```
┌──────────────────────────── Ask about your report ───────────────────────┐
│ (empty state) You can ask about your scores, features and                │
│ recommendations. For medical questions, please see a professional.       │
│   Suggested: "What is my symmetry score?"  "Which features should I …"   │
│ ─────────────────────────────────────────────────────────────────────── │
│ You: …                                                                   │
│ Assistant: …                                                             │
│ Assistant is typing…  (announced once)                                   │
│ [ Type your question… ]                                    [ Send ]      │
│ 12 of 50 messages left today (resets at 00:00 UTC)                        │
└──────────────────────────────────────────────────────────────────────────┘
```
- **Limit reached:** input disabled + "You've reached today's limit. You can chat again at 00:00 UTC (in 4 h 12 min)." (AC10.3.1).
- **Send failed:** the message stays in the input, an error toast appears, and [Retry] is offered (AC10.1.4).
- **Phone:** the input is pinned above the keyboard, and the conversation scrolls so the latest reply stays visible (AC10.1.6).

## 10. Settings (US11.4–US11.6)
Tabs: **Account** · **Password** · **Billing** (on phones, a list that opens each section).
- **Account:** name (read-only, with the helper "Your name can't be changed"), email, verification badge (text + icon), member since.
- **Password:** current / new / confirm, with the rule list. Errors appear inline per field. Success gives a toast "Password changed" and the user stays signed in.
- **Billing:**
  - a payment history table (Date | Amount | Currency | Status); on phones, rows become cards; empty state: "No payments yet";
  - payment options: Stripe card ✓ Available · PayPal (muted, disabled) with the "Not available" pill; screen readers announce "PayPal, not available" (AC11.6.2).

---

## 11. Screen-state matrix

| Screen | Loading | Empty | Error | Partial / edge |
|---|---|---|---|---|
| Sign up / log in / code | Button spinner | — | Inline field + toast | Locked, cooldown, expired |
| Consent | Skeleton | — | Toast | Consent text version changed |
| Questionnaire | Skeleton | — | Inline "Please choose an answer"; save-failed toast | Branch changes count; long free text |
| Capture | Checking overlay | No photos yet ("0 of 3") | Rejection reason; type/size | Camera denied / absent; HEIC conversion |
| Review | "Checking your photos…" | — | Flag messages | Pending after retake; 2 flagged |
| Payment | — | — | 409 → review; cancelled notice | Price change |
| Confirming | Spinner | — | Long wait message | Arrives while viewing |
| Progress | Step list | — | Failed / failed twice | User leaves and returns |
| Home | Skeleton | — | Section error + retry | Image pending / unavailable; axis not scored |
| Report | Section skeletons | — | PDF failed | Missing images; Hair/Skin/Neck "no measurement" |
| AI Visuals | Image skeletons | — | Per-image failure | Retry cap reached |
| Chat | Typing indicator | First-time empty state | Send failed | Daily limit reached |
| Settings | Skeleton | "No payments yet" | Inline + toast | PayPal disabled |

## 12. Story → screen map

| Stories | Screen |
|---|---|
| US2.1, US2.2 | §1 |
| US3.1–US3.11 | §2, §0.2 (US3.10–US3.11 have no screen of their own; they are session behaviour) |
| US4.1–US4.4 | §3 |
| US5.1–US5.3, US5.5–US5.11 | §4 |
| US6.1–US6.5, US7.1, US7.2, US7.11 | §5 |
| US11.1, US11.3 | §6 |
| US8.1–US8.8 | §7 |
| US9.1–US9.5 | §6, §7, §8 |
| US10.1–US10.3 | §9 |
| US11.4–US11.6 | §10 |
| US11.2, US11.7, US11.8 | §0 and every screen |

Enabler stories (US1.x, US7.6) have no screens.
