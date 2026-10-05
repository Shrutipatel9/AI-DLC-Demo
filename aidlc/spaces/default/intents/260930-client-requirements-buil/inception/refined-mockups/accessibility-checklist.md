# Accessibility Checklist — WCAG 2.1 AA

**Target:** WCAG 2.1 Level AA on every screen (requirements NFR9, `requirements-analysis-questions.md` Q7). High-risk screens also carry the per-screen criteria from the stories (stories Q12).

**Verification:**
- automated axe on the main screens in CI (US1.13, AC1.13.3);
- Playwright journeys on a 360 px phone viewport and a desktop viewport in Chromium, WebKit and Firefox (AC1.13.2);
- the manual checks in §3 before handover.

Legend: ☐ = to be verified in Build and Test. Each line names where it is designed (`mockups.md` section / `interaction-spec.md` component).

---

## 1. Checklist by WCAG principle

### Perceivable
- ☐ **1.1.1 Non-text content.**
  - Every photo and AI image has alt text naming what it shows ("AI-generated illustration — Nose"), never just the chip text (ImageSlot).
  - Charts have a summary label and a data table (RadarChart etc., AC8.3.3, AC11.1.4).
  - Decorative icons are hidden with `aria-hidden`.
- ☐ **1.3.1 Info and relationships.**
  - One `h1` per page, and headings in order.
  - Questionnaire options use `fieldset`/`legend` (QuestionStep).
  - Tables use `<th scope>`.
  - Landmarks: header, nav, main, footer.
- ☐ **1.3.2 Meaningful sequence.** The DOM order matches the visual order, including the phone single-column order of the Home dashboard (`mockups.md` §6).
- ☐ **1.3.4 Orientation.** Every screen works in portrait and landscape; the camera step is designed for portrait but doesn't lock orientation.
- ☐ **1.3.5 Identify input purpose.** `autocomplete` is set: `name`, `email`, `new-password`, `current-password`, `one-time-code` (FormField, OtpEntry).
- ☐ **1.4.1 Use of colour.**
  - Photo flags, step states, statuses and errors always use text + icon, never colour alone (PhotoReview, ProgressSteps).
  - Chart series have labels.
- ☐ **1.4.3 Contrast (minimum).**
  - All text pairs are ≥ 4.5:1 (≥ 3:1 large), using the corrected tokens in `design-system-mapping.md` §1: subheading `#5A7690`, small accent text `#25756A`, muted text on the grey page `#5F6673`, chips at 85%.
- ☐ **1.4.4 Resize text / 1.4.10 Reflow.**
  - At 200% zoom and at 320 px width, nothing is cut off and there's no two-dimensional scrolling.
  - Metric tables scroll inside their own region (AC8.4.3).
- ☐ **1.4.11 Non-text contrast.** Input borders (`#8A919C`), the focus ring, chart lines and flag borders are ≥ 3:1.
- ☐ **1.4.12 Text spacing.** No clipping when line height is 1.5, paragraph spacing 2×, and letter or word spacing is increased.
- ☐ **1.4.13 Content on hover or focus.** Tooltips can be dismissed with Escape, can be hovered, and stay visible while hovered.

### Operable
- ☐ **2.1.1 Keyboard.**
  - Every action is reachable by keyboard: camera capture, upload, retake, contents drawer, chart table toggle, chat send, image enlarge.
  - Swipe carousels have previous/next buttons (`mockups.md` §8).
- ☐ **2.1.2 No keyboard trap.** Dialogs and sheets trap focus only while open, and Escape closes them (ConfirmDialog, AppHeader, ReportToc).
- ☐ **2.2.1 Timing adjustable.**
  - The code expiry (10 min) and resend cooldown are security limits. The user can always request a new code, and the remaining time is shown as text.
  - The code screen never auto-submits.
- ☐ **2.2.2 Pause, stop, hide.** Progress and confirming screens update status text only; nothing moves continuously except a spinner, and reduced motion replaces it with static text.
- ☐ **2.3.1 Three flashes.** No flashing content.
- ☐ **2.4.1 Bypass blocks.** A "Skip to content" link is first on every page.
- ☐ **2.4.2 Page titled.** Each route has a unique `<title>`, for example "Photos — Step 3 of 5".
- ☐ **2.4.3 Focus order.**
  - A new question moves focus to its legend.
  - A photo result moves focus to its message.
  - Choosing a table-of-contents entry moves focus to the section heading.
  - A dialog returns focus to its opener.
- ☐ **2.4.6 Headings and labels.** Labels are visible above inputs, never placeholder-only.
- ☐ **2.4.7 Focus visible.** A 2 px accent ring with a 2 px offset on every focusable element; `outline: none` is never used without a replacement.
- ☐ **2.5.3 Label in name.** Accessible names contain the visible text ("Take photo of your left side" contains "Take photo").
- ☐ **2.5.5 (AAA, adopted as guidance) Target size.** Touch targets are ≥ 44 × 44 px, and 48 px for primary actions on phones.

### Understandable
- ☐ **3.1.1 Language of page.** `<html lang="en">`.
- ☐ **3.2.1 / 3.2.2 On focus and on input.**
  - Nothing navigates on focus or selection.
  - The photo review never auto-advances; the user always presses Continue (AC5.11.4).
  - Payment confirmation updates in place but doesn't navigate.
- ☐ **3.2.3 / 3.2.4 Consistent navigation and identification.** The same header in each shell; the same labels for the same actions ("Retake", "Try again").
- ☐ **3.3.1 Error identification.** Errors are text next to the field, linked with `aria-describedby`, and `aria-invalid` is set (FormField, AC11.7.4).
- ☐ **3.3.2 Labels or instructions.** Password rules are shown before typing; file type and size limits are shown before upload; photo guidance is shown before capture.
- ☐ **3.3.3 Error suggestion.** Every error says how to fix it ("Move closer…", "Please use a JPEG, PNG or HEIC photo under 10 MB").
- ☐ **3.3.4 Error prevention (legal/financial).** Payment goes through Stripe Checkout, which shows a review step. Consent and the disclaimer are explicit checkboxes. Log out is confirmed.

### Robust
- ☐ **4.1.2 Name, role, value.** Native elements first; Radix primitives for dialogs, menus, tabs and sheets. Display-only dimorphism "sliders" are not given a slider role (AC8.8.1).
- ☐ **4.1.3 Status messages.** Status changes are announced without moving focus:
  - toasts (polite; errors assertive);
  - photo checking and results;
  - identity result;
  - payment confirming and confirmed;
  - analysis steps;
  - chat replies (`role="log"`);
  - OTP resend availability.

---

## 2. Per-screen checks (high-risk screens, stories Q12)

| Screen | Specific checks | Stories |
|---|---|---|
| Camera and upload | Upload always offered beside the camera; camera denied → clear message; capture and retake by keyboard; phone portrait fits without scrolling; result announced | AC5.3.2–AC5.3.4, AC5.2.5 |
| Photo review | Flags by text + icon + border; reason next to the disabled Continue; pending ≠ consistent; nothing moves focus automatically; phone: nothing cut off | AC5.11.1–AC5.11.5 |
| Code entry | Masked email shown; numeric keypad; paste and autofill work; countdown not announced every second; lockout end time shown as text | AC3.2.6, AC3.3.1, AC3.3.3 |
| Questionnaire | One question per screen with `fieldset`/`legend`; "N of M" as text and progress bar; revealed follow-up announced; Back keeps answers | AC4.2.1–AC4.2.6 |
| Disclaimer | Exact wording; reason next to the disabled Submit; supportive panel reachable and announced | AC4.3.1, AC4.3.4 |
| Progress | Step states in text; changes announced politely; "you can leave" note | AC7.2.1, AC7.2.2 |
| Report and charts | Preamble first; table of contents moves focus; every chart has a table; AI images captioned; tables scroll in place on phones | AC8.3.1, AC8.3.3, AC8.7.2, AC8.7.4, AC8.4.3 |
| Chat | `role="log"`; replies announced; input stays visible above the phone keyboard; failed message kept | AC10.1.3–AC10.1.6 |
| Dialogs and toasts | Focus trap, Escape, focus return; named confirm button; toasts announced, no focus steal, errors persist; phone toasts don't cover the header | AC11.7.2, AC11.7.3, AC11.7.5 |
| Billing | Disabled PayPal announced as "not available" | AC11.6.2 |

## 3. Manual checks before handover

- ☐ **Keyboard only:** sign up → report → chat → log out with no mouse.
- ☐ **Screen readers:** NVDA + Firefox (Windows), VoiceOver + Safari (macOS and iOS) and TalkBack + Chrome (Android) across the same journey, including camera capture and photo review.
- ☐ **Zoom and reflow:** 200% and 400% zoom; 320 px width.
- ☐ **Colour-blindness:** simulate protanopia, deuteranopia and tritanopia on photo review, charts and status screens.
- ☐ **Reduced motion:** turn it on and confirm there are no animations (landing "How it works", transitions, spinners replaced by text).
- ☐ **Browsers:** latest two versions of Chrome, Edge, Safari and Firefox (NVDA/Edge spot check included). The automated matrix covers the Chromium/WebKit/Firefox engines; Edge and "two versions" are covered manually.
