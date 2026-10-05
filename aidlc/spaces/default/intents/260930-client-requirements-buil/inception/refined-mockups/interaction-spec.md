# Interaction Specification — AI Facial Analysis Platform

Component-level behaviour for the screens in `mockups.md`. Each component uses the format of `.claude/knowledge/aidlc-design-agent/component-spec-template.md`. Components are built on shadcn/ui (Radix primitives) with Tailwind CSS (Q2); where a shadcn/Radix primitive exists, it is named so its built-in keyboard and screen-reader behaviour is reused rather than rebuilt.

**Breakpoints (all components):** phone < 768 px · tablet 768–1023 px · desktop ≥ 1024 px, with content capped at 1200 px wide on large screens. Mobile-first. Touch targets are at least 44 × 44 px, and 48 px for primary actions on phones.

**Motion:** 150–250 ms ease-out on entry and ease-in on exit. Everything becomes an instant change under `prefers-reduced-motion`.

---

## 1. AppHeader

| Field | Value |
|---|---|
| Component | AppHeader |
| Description | Persistent top navigation for the Public, Onboarding and App shells (`FR-017`, US11.2) |
| Category | navigation |

### States
| State | Description | Trigger |
|---|---|---|
| default | Links for the current shell; current page marked | page load |
| focus | Visible 2 px focus ring on the link | Tab |
| menu-open (phone) | Sheet with Home / Report / AI Visuals / Chat | ☰ pressed |
| user-menu-open | Dropdown: Settings, Log out | name pressed |

### Props / Inputs
| Prop | Type | Required | Default | Description |
|---|---|---|---|---|
| shell | "public" \| "onboarding" \| "app" | yes | — | Which link set to show |
| currentPath | string | yes | — | Sets `aria-current="page"` |
| step | { index: number; total: number; label: string } | no | — | Onboarding step indicator |
| userName | string | no | — | Shown in the user menu (from the auth store) |

### Responsive Behaviour
| Breakpoint | Behaviour |
|---|---|
| mobile (<768px) | Wordmark + ☰ + user menu; ☰ opens a Radix `Sheet` from the right; every link is one tap away (AC11.2.2) |
| tablet (768–1024px) | All links inline; user name shortened to initials if space runs out |
| desktop (>1024px) | All links inline with the full name |

### Accessibility
| Requirement | Implementation |
|---|---|
| ARIA role | `<header>` landmark with a `<nav aria-label="Main">` |
| Keyboard interaction | Tab through links; Enter to follow; Escape closes the sheet or menu |
| Label / aria-label | ☰ button: `aria-label="Open menu"`, `aria-expanded` |
| Contrast ratio | WCAG AA |
| Screen reader | The current page is announced by `aria-current` |
| Focus management | The sheet traps focus and returns it to ☰ on close. A "Skip to content" link is the first focusable element |

---

## 2. Toast

| Field | Value |
|---|---|
| Component | Toast (shadcn `Sonner`/`Toast`) |
| Description | Feedback for every action with a success or failure outcome (`BR-009`, US11.7) |
| Category | feedback |

### States
| State | Description | Trigger |
|---|---|---|
| success | Check icon + text; auto-dismisses after 6 s; pauses on hover or focus | successful action |
| error | Warning icon + text; stays until dismissed | failed action |
| info | Neutral icon + text; auto-dismisses after 6 s | informational |

### Props / Inputs
| Prop | Type | Required | Default | Description |
|---|---|---|---|---|
| variant | "success" \| "error" \| "info" | yes | — | Icon, colour and dismissal rule |
| message | string | yes | — | Plain-language outcome, never an error code |
| action | { label: string; onClick } | no | — | For example "Retry" |

### Responsive Behaviour
| Breakpoint | Behaviour |
|---|---|
| mobile (<768px) | Full width, directly under the header; never covers the header or the triggering action (AC11.7.5) |
| tablet / desktop | Top-right stack of up to 3; the oldest is removed first |

### Accessibility
| Requirement | Implementation |
|---|---|
| ARIA role | Success/info in a `role="status"` region (polite); errors in a `role="alert"` region |
| Keyboard interaction | F6 (or the "Notifications" skip link) moves to the region; Escape dismisses the focused toast |
| Label / aria-label | Close button `aria-label="Dismiss notification"` |
| Contrast ratio | 4.5:1 text; the icon adds meaning beyond colour |
| Screen reader | Announced once on appearance; toasts never take focus (AC11.7.2) |
| Focus management | Focus stays where it was |

**Exception:** the forgot-password request never shows a toast that reveals the outcome (AC11.7.1).

---

## 3. ConfirmDialog

| Field | Value |
|---|---|
| Component | ConfirmDialog (shadcn `AlertDialog`) |
| Description | The one shared confirmation for destructive or irreversible actions (`BR-010`) |
| Category | feedback |

### States
| State | Description | Trigger |
|---|---|---|
| closed | Not rendered | default |
| open | Title, consequence sentence, [Cancel] and a named confirm button | destructive action pressed |
| confirming | Confirm button spinner; both buttons disabled | confirm pressed |

### Props / Inputs
| Prop | Type | Required | Default | Description |
|---|---|---|---|---|
| title | string | yes | — | For example "Log out?" |
| description | string | yes | — | What will happen |
| confirmLabel | string | yes | — | Names the action ("Log out"), never "OK" |
| destructive | boolean | no | true | Destructive button style |
| onConfirm | () => Promise<void> | yes | — | Runs the action |

### Responsive Behaviour
| Breakpoint | Behaviour |
|---|---|
| mobile (<768px) | Bottom sheet, buttons stacked full width, confirm last |
| desktop | Centred dialog, max 440 px |

### Accessibility
| Requirement | Implementation |
|---|---|
| ARIA role | `alertdialog` with `aria-labelledby` (title) and `aria-describedby` (description) |
| Keyboard interaction | Focus trapped; Escape = Cancel; Enter on a focused button activates it |
| Contrast ratio | WCAG AA |
| Screen reader | The title and description are read when the dialog opens |
| Focus management | Focus starts on **Cancel** (the safe choice) and returns to the opener on close (AC11.7.3) |

---

## 4. FormField

| Field | Value |
|---|---|
| Component | FormField (shadcn `Form` + react-hook-form + zod) |
| Description | Labelled input with a hint, rule list and inline error (AC11.7.4) |
| Category | input |

### States
| State | Description | Trigger |
|---|---|---|
| default | Label above the input, hint below | load |
| focus | Focus ring | Tab / click |
| error | Error text below the field with an icon; input border and icon | validation on blur or submit, or a server error mapped to the field |
| valid | Optional ✓ for rule lists (password) | rule met |
| disabled | Greyed out, not focusable if the whole form is locked | lockout, submitting |

### Props / Inputs
| Prop | Type | Required | Default | Description |
|---|---|---|---|---|
| name | string | yes | — | Field key |
| label | string | yes | — | Visible label (never placeholder-only) |
| type | "text" \| "email" \| "password" \| "otp" \| "textarea" | yes | — | Input kind |
| hint | string | no | — | Shown before input |
| rules | { text: string; met: boolean }[] | no | — | Password rule list |
| autoComplete | string | no | per type | `one-time-code` for OTP, `new-password` / `current-password` |

### Responsive Behaviour
| Breakpoint | Behaviour |
|---|---|
| mobile | Full width; OTP uses `inputmode="numeric"` for the number pad |
| desktop | Max 480 px in single-column auth forms |

### Accessibility
| Requirement | Implementation |
|---|---|
| ARIA role | Native input |
| Keyboard interaction | Standard; password show/hide is a real button |
| Label / aria-label | `<label for>`; `aria-describedby` → hint, rules and error |
| Contrast ratio | 4.5:1 text; 3:1 input border |
| Screen reader | Error announced through `aria-invalid="true"` + the described-by text; on submit with errors, focus moves to the first invalid field |
| Focus management | See above |

---

## 5. OtpEntry

| Field | Value |
|---|---|
| Component | OtpEntry |
| Description | Code entry with masked address, resend countdown, expiry and lockout states (US3.2, US3.3, US3.9) |
| Category | input |

### States
| State | Description | Trigger |
|---|---|---|
| default | One 6-digit field (single input, not six boxes, so paste and autofill work) | load |
| cooldown | "Resend code in Ns"; the resend control is disabled | code just sent |
| resend-ready | [Resend code] enabled | cooldown ended |
| wrong | Inline "That code isn't right. N tries left." | wrong code |
| expired | Inline "This code has expired." + [Send a new code] | server says expired |
| locked | Inline "Too many tries. You can try again at HH:MM." Verify and Resend disabled, reason next to them | server says locked |
| submitting | Verify button spinner | submit |

### Props / Inputs
| Prop | Type | Required | Default | Description |
|---|---|---|---|---|
| purpose | "signup" \| "login" \| "reset" | yes | — | Endpoint and next step |
| maskedEmail | string | yes | — | For example "m•••@example.com" |
| cooldownSeconds | number | yes | — | From the server response |

### Responsive Behaviour
| Breakpoint | Behaviour |
|---|---|
| mobile | Number pad; the field is large (24 px digits) |
| desktop | Same, centred |

### Accessibility
| Requirement | Implementation |
|---|---|
| ARIA role | Native input with `autocomplete="one-time-code"` |
| Keyboard interaction | Enter submits |
| Label / aria-label | "6-digit code" |
| Contrast ratio | WCAG AA |
| Screen reader | Countdown announced at start and when resend becomes available, not every second (polite region) |
| Focus management | Focus on the field at load and after an error |

---

## 6. QuestionStep

| Field | Value |
|---|---|
| Component | QuestionStep |
| Description | One questionnaire question per screen (Q3) driven by the configured definition ([QS]) |
| Category | input |

### States
| State | Description | Trigger |
|---|---|---|
| loading | Skeleton of question + options | definition loading |
| unanswered | Next shows "Please choose an answer" on press | load |
| answered | Next enabled | selection made |
| follow-up-open | Follow-up text area revealed under "Yes" | follow-up answer chosen |
| saving | Next spinner | Next pressed |
| save-error | Error toast; answer stays on screen | save failed |

### Props / Inputs
| Prop | Type | Required | Default | Description |
|---|---|---|---|---|
| question | { id; text; type: "text" \| "single" \| "multi" \| "yesno"; options?; followUp?; medical: boolean } | yes | — | From seed data |
| position | { index: number; total: number } | yes | — | Total reflects branching |
| answer | unknown | no | — | Saved answer, if any |

### Responsive Behaviour
| Breakpoint | Behaviour |
|---|---|
| mobile | Back / Next pinned at the bottom, full width |
| desktop | Card max 640 px, buttons at card bottom |

### Accessibility
| Requirement | Implementation |
|---|---|
| ARIA role | `fieldset` + `legend` = question text; radio group / checkbox group |
| Keyboard interaction | Arrow keys within a radio group; Space toggles checkboxes; Enter = Next |
| Label / aria-label | Progress: `role="progressbar"` with `aria-valuenow`/`aria-valuemax` and text "Question 5 of 22" |
| Contrast ratio | WCAG AA |
| Screen reader | A revealed follow-up is announced; the question legend is read on arrival |
| Focus management | On a new question, focus moves to the legend (the heading) |

**DisclaimerGate** (last screen) adds a checkbox using the exact [QS] §4 wording, Submit disabled with the reason visible, and the "I can't confirm this statement" link that opens the supportive panel (AC4.3.4) in place (not a dialog), with focus moved to its heading.

---

## 7. PhotoCapture

| Field | Value |
|---|---|
| Component | PhotoCapture |
| Description | Per-angle upload or camera capture with preview and validation result (US5.2, US5.3, US5.5, US5.10) |
| Category | input |

### States
| State | Description | Trigger |
|---|---|---|
| idle | Instruction, example image, [Take a photo] [Upload a photo] | step entry |
| camera | Live view with angle guide overlay, [Capture] [Cancel] | Take pressed + permission granted |
| camera-unavailable | Message + upload only | permission denied or no camera |
| preview | Image + [Retake] [Use this photo] | captured or file chosen |
| checking | Dimmed image + "Checking your photo…" | submitted |
| accepted | ✓ "Looks good" | server accept |
| rejected | ⚠ reason + fix + [Retake] | server reject |
| invalid-file | "Please use a JPEG, PNG or HEIC photo under 10 MB." | client-side type/size check |

### Props / Inputs
| Prop | Type | Required | Default | Description |
|---|---|---|---|---|
| angle | string (from `REQUIRED_ANGLES`) | yes | — | Configured angle |
| instruction | string | yes | — | Wording in the user's own terms |
| exampleImageSrc | string | yes | — | Example for this angle |
| maxBytes | number | yes | 10 MB | From configuration |

### Responsive Behaviour
| Breakpoint | Behaviour |
|---|---|
| mobile | Camera uses the front camera; the view, guide and shutter fit portrait without scrolling (AC5.3.4). The preview is mirrored in the live view only; the submitted image is not mirrored |
| desktop | Camera view max 640 px wide beside the instructions |

### Accessibility
| Requirement | Implementation |
|---|---|
| ARIA role | Buttons; the file input is a real `<input type="file" accept="image/jpeg,image/png,image/heic">` behind a labelled button |
| Keyboard interaction | All actions are buttons; Space/Enter captures |
| Label / aria-label | Capture button `aria-label="Take photo of your left side"` |
| Contrast ratio | Guide overlay 3:1 against a typical background |
| Screen reader | Checking / accepted / rejected are announced politely (AC5.2.5) |
| Focus management | After a result, focus moves to the result message; on rejection, to [Retake] |

Upload is always offered next to the camera (AC5.3.3), which is also the accessible route for users who can't frame a live shot.

---

## 8. PhotoReview

| Field | Value |
|---|---|
| Component | PhotoReview |
| Description | Shows all angles with the same-person result; gates Continue (US5.11, `BR-005` rule 6, [IV] §6) |
| Category | display |

### States
| State | Description | Trigger |
|---|---|---|
| checking | "Checking your photos…"; Continue disabled | on entry with a complete set, after any retake |
| consistent | "All three photos match."; Continue enabled; **no automatic navigation** | result has no flagged angles |
| flagged | Flagged photos marked with text + icon + border; [Retake …] per flagged photo; Continue disabled + reason | result lists flagged angles |
| error | "We couldn't check your photos. Try again." + [Try again] | request failed |

### Props / Inputs
| Prop | Type | Required | Default | Description |
|---|---|---|---|---|
| photos | { angle; src; status }[] | yes | — | Current set |
| identityResult | { consistent: boolean; mismatchedAngles: string[] } \| null | yes | — | `null` = pending, **never** treated as consistent |
| skipIfConsistentOnLoad | boolean | yes | — | Decided once from the first fetch ([IV] §6) |

### Responsive Behaviour
| Breakpoint | Behaviour |
|---|---|
| mobile | One column; each photo with its status and retake; Continue fixed at the bottom with its reason above |
| desktop | Three columns |

### Accessibility
| Requirement | Implementation |
|---|---|
| ARIA role | List of figures; each flag message tied to its photo with `aria-describedby` |
| Keyboard interaction | Tab reaches each retake button and Continue |
| Label / aria-label | Photo alt: "Your left side photo" |
| Contrast ratio | Flag border 3:1; text 4.5:1 |
| Screen reader | Result changes announced politely ("Right side photo doesn't match the others") |
| Focus management | Focus stays on the user's last control; nothing moves focus automatically |

---

## 9. PaymentStatus

| Field | Value |
|---|---|
| Component | PaymentStatus |
| Description | Pay → confirming → confirmed → Start Analysis (US6.1, US6.5, US7.1) |
| Category | feedback |

### States
| State | Description | Trigger |
|---|---|---|
| unpaid | Price, list of what's included, [Pay securely with Stripe] | no payment |
| redirecting | Button spinner "Opening secure checkout…" | Pay pressed |
| cancelled | Notice "Payment cancelled — you haven't been charged." | return from cancel URL |
| confirming | Spinner + "Confirming your payment…"; polls status | return from success URL, webhook not yet processed |
| slow-confirm | "Still confirming… you won't be charged twice. You can close this page." + [Check again] | configured wait passed |
| confirmed | "Payment confirmed ✓" + [Start Analysis] | payment succeeded |
| starting | Start button disabled + spinner | Start pressed |

### Props / Inputs
| Prop | Type | Required | Default | Description |
|---|---|---|---|---|
| price | { amount: number; currency: string } | yes | — | From configuration via API |
| paymentState | enum above | yes | — | From the API |
| confirmWaitSeconds | number | yes | — | Configured |

### Responsive Behaviour
| Breakpoint | Behaviour |
|---|---|
| mobile | Primary action fixed at the bottom |
| desktop | Centred card, max 560 px |

### Accessibility
| Requirement | Implementation |
|---|---|
| ARIA role | Status text in `role="status"` |
| Keyboard interaction | Standard buttons |
| Screen reader | The change to "confirmed" is announced (AC6.5.2) |
| Focus management | On confirmed, focus moves to [Start Analysis] |

---

## 10. ProgressSteps

| Field | Value |
|---|---|
| Component | ProgressSteps |
| Description | Analysis run progress with failure and re-run handling (US7.2, US7.11) |
| Category | feedback |

### States
| State | Description | Trigger |
|---|---|---|
| running | Steps with Done / In progress / Waiting text + icons; "you can close this page" note | job running |
| ready | "Your report is ready." + [View my report] | job completed |
| failed-first | Plain-language failure, payment still covers it, [Try again] | first failure |
| failed-final | Failure + "Please contact support" + contact; no retry | re-run failed |

### Props / Inputs
| Prop | Type | Required | Default | Description |
|---|---|---|---|---|
| steps | { key; label; state: "done" \| "current" \| "waiting" }[] | yes | — | From job status |
| status | "running" \| "ready" \| "failed" | yes | — | — |
| rerunAvailable | boolean | yes | — | False after the free re-run is used |

### Responsive Behaviour
| Breakpoint | Behaviour |
|---|---|
| all | Single vertical list; the page polls every few seconds and never auto-navigates |

### Accessibility
| Requirement | Implementation |
|---|---|
| ARIA role | `<ol>` of steps; status changes in a polite live region |
| Screen reader | Step changes announced without moving focus (AC7.2.1) |
| Focus management | On ready, focus is **not** moved; the "View my report" button is announced |

---

## 11. ImageSlot

| Field | Value |
|---|---|
| Component | ImageSlot |
| Description | Any photo or AI image with badge chip, AI caption and failure/retry state (US8.7, US9.x) |
| Category | display |

### States
| State | Description | Trigger |
|---|---|---|
| loading | Skeleton at the final aspect ratio | fetching |
| pending | Skeleton + "Creating image…" | generation in progress |
| ready | Image + badge chip (BEFORE / AFTER / POTENTIAL) + caption "AI-generated illustration" for generated images | image available |
| unavailable | "Image not available yet" + [Try again] + "2 of 3 retries left" | generation failed |
| retry-exhausted | "You've used all retries for this image" | 3 manual retries used |
| enlarged | Dialog with the full-size image | image pressed |

### Props / Inputs
| Prop | Type | Required | Default | Description |
|---|---|---|---|---|
| kind | "photo" \| "generated" | yes | — | Controls the AI caption |
| chip | string | no | — | Badge text ([RD] §3.4) |
| alt | string | yes | — | For example "AI-generated illustration — Nose" |
| retriesLeft | number | no | — | For generated images |

### Responsive Behaviour
| Breakpoint | Behaviour |
|---|---|
| all | Fixed aspect ratio so the layout doesn't shift; lazy-loaded below the fold |

### Accessibility
| Requirement | Implementation |
|---|---|
| ARIA role | `<figure>` + `<figcaption>` for the AI caption |
| Keyboard interaction | The enlarge button and the retry button are separate controls |
| Label / aria-label | Alt names the image (never just the chip text) |
| Contrast ratio | Chip text on its dark chip ≥ 4.5:1 |
| Screen reader | Retry result announced |
| Focus management | Enlarge dialog traps focus and returns it on close |

---

## 12. RadarChart, SymmetryPanel, ThirdsBars, DimorphismScale

| Field | Value |
|---|---|
| Component | Data visualisations |
| Description | Home Harmony Profile (6 axes, [RD] §12.1) and report assessments (US8.3, US8.8) |
| Category | display |

### States
| State | Description | Trigger |
|---|---|---|
| ready | Chart with value labels on every point | data loaded |
| partial | An axis without a score is not plotted and is labelled "Not scored" ([RD] §12.3) | null value |
| table | The same data as a table | "Show as table" toggle |
| loading | Skeleton | fetching |

### Props / Inputs
| Prop | Type | Required | Default | Description |
|---|---|---|---|---|
| series | { axis: string; value: number \| null }[] | yes | — | Never fills a null with 0 |
| max | number | yes | 100 | Scale |
| label | string | yes | — | Chart title |

### Responsive Behaviour
| Breakpoint | Behaviour |
|---|---|
| mobile | Chart scales to width (min 280 px); labels abbreviated per [RD] §12.1 with full names in the table |
| desktop | Fixed size in its card |

### Accessibility
| Requirement | Implementation |
|---|---|
| ARIA role | SVG with `role="img"` and an `aria-label` summary; the table is a real `<table>` (AC8.3.3, AC11.1.4) |
| Keyboard interaction | The table toggle is a button; dimorphism sliders are **display-only** (no input role, AC8.8.1) |
| Contrast ratio | 3:1 for lines and fills against the background |
| Screen reader | Summary label, for example "Harmony profile: Symmetry 81, Jaw 70, …" |
| Focus management | None beyond the toggle |

---

## 13. ReportToc

| Field | Value |
|---|---|
| Component | ReportToc |
| Description | Sticky contents on desktop, drawer on phones (Q5, US8.3) |
| Category | navigation |

### States
| State | Description | Trigger |
|---|---|---|
| default | Section list, current section highlighted (scroll spy) | scroll |
| drawer-open (phone) | Radix `Sheet` with the list | "Contents" pressed |

### Responsive Behaviour
| Breakpoint | Behaviour |
|---|---|
| mobile | "Contents" button in a sticky bar under the header; drawer from the left |
| desktop | Sticky left column, 240 px |

### Accessibility
| Requirement | Implementation |
|---|---|
| ARIA role | `<nav aria-label="Report contents">`; current item `aria-current="location"` |
| Keyboard interaction | Links; Escape closes the drawer |
| Focus management | Choosing an entry scrolls there and moves focus to the section heading (`tabindex="-1"`); the drawer closes and returns focus to the heading, not the button |

---

## 14. ChatPanel

| Field | Value |
|---|---|
| Component | ChatPanel |
| Description | AI Beauty Assistant conversation (US10.1–US10.3) |
| Category | input |

### States
| State | Description | Trigger |
|---|---|---|
| empty | Explanation + suggested questions | no messages yet |
| idle | Conversation + input + "N of 50 left today" | messages exist |
| sending | Message shown as sending; "Assistant is typing…" | Send pressed |
| send-failed | Message kept in the input; error toast; [Retry] | request failed |
| limit-reached | Input disabled + reset time (00:00 UTC) and time left | daily limit hit |

### Props / Inputs
| Prop | Type | Required | Default | Description |
|---|---|---|---|---|
| messages | { role; text; time }[] | yes | — | History |
| remainingToday | number | yes | — | From the API |
| resetsAt | ISO time | yes | — | Next 00:00 UTC |

### Responsive Behaviour
| Breakpoint | Behaviour |
|---|---|
| mobile | Input pinned above the on-screen keyboard; conversation scrolls to the latest reply (AC10.1.6) |
| desktop | Max 760 px column |

### Accessibility
| Requirement | Implementation |
|---|---|
| ARIA role | Conversation in `role="log"` (polite) |
| Keyboard interaction | Enter sends; Shift+Enter new line |
| Label / aria-label | Input label "Your question" |
| Screen reader | New replies announced once, without moving focus (AC10.1.3) |
| Focus management | Focus stays in the input after sending |

---

## 15. Session and routing behaviour (no visible component)

- **SessionGate:** wraps protected routes. It shows the "Restoring your session…" loader until the start-up refresh resolves, then either renders the page or routes to login. It never flashes login (AC3.5.1).
- **NextStepGuard:** on protected onboarding routes, it asks the backend for the next step (US11.8) and redirects to it when the requested URL is later than the next unfinished step (AC11.8.2). The photo-review skip decision is taken only from the first page load ([IV] §6).
- **Silent refresh (US3.10):** lives in the API client only, never in a component. No component shows a spinner for it.
