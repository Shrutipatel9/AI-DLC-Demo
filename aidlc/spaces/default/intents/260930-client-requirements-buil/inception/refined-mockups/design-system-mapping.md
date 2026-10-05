# Design System Mapping — AI Facial Analysis Platform

**Decisions:**
- One visual language for every screen, extended from [RD] `report_design_spec.md` §3 (Q1).
- Tailwind CSS + shadcn/ui (Q2).
- Light theme only (Q4).

No client branding exists (`CON-003`), and [RD] marks every colour as "visually approximated, not sampled". The values below are therefore **[Decided by delivery team]** starting points. Where an [RD] value fails WCAG 2.1 AA, a corrected value is given and the change is flagged.

---

## 1. Colour tokens

Contrast is measured against `#FFFFFF` unless stated otherwise (relative-luminance calculation; WCAG thresholds are 4.5:1 for normal text and 3:1 for large text and UI parts).

| Token (CSS variable) | [RD] value | Value to use | Contrast | Use |
|---|---|---|---|---|
| `--ink-heading` | `#1A2230` | `#1A2230` | ≈ 16:1 ✓ | Headings, wordmark |
| `--ink-subheading` | `#9FB4C7` | **`#5A7690`** | [RD] ≈ 2.1:1 ✗ → ≈ 4.7:1 ✓ | Second line of two-line titles. **Changed:** the [RD] value fails even the large-text threshold. `#9FB4C7` may be kept only as a decorative, non-text colour |
| `--ink-body` | `#2A2D31` | `#2A2D31` | ≈ 14:1 ✓ | Body text |
| `--ink-muted` | `#6B7280` | `#6B7280` on white; **`#5F6673`** on `--surface-page` | ≈ 4.8:1 ✓ / ≈ 4.4:1 ✗ → ≈ 5.3:1 ✓ | Captions, footnotes. **Changed on the grey page background** |
| `--accent` | `#2E8B7D` | `#2E8B7D` for fills, lines, borders and large numerals; **`#25756A`** for accent text under 24 px | ≈ 4.1:1 (UI ✓, small text ✗) → ≈ 5.5:1 ✓ | Score numerals, chart lines, focus ring, top rule |
| `--surface-page` | `#FFFFFF` (PDF) / `#F5F6F7` (dashboard) | Same | — | Page backgrounds |
| `--surface-card` | `#FFFFFF` + `#E5E7EB` border | Same | Border decorative | Cards, tiles, tables |
| `--surface-summary` | `#DCEEE8` | Same, with `--ink-body` text | ≈ 12:1 ✓ | Per-feature Summary callout |
| `--chip-bg` | `#333436` at 50% opacity | **`#333436` at 85% opacity** | White text ≥ 4.5:1 on any photo | Badge chips (BEFORE / AFTER / POTENTIAL …). **Changed:** 50% opacity can't guarantee contrast over light photos |
| `--danger` | — (not in [RD]) | `#B42318` | ≈ 6.5:1 ✓ | Errors, destructive buttons, flag borders (always with an icon and text) |
| `--success` | — | `#1E7B4F` | ≈ 5.3:1 ✓ | "Looks good", confirmations (with icon) |
| `--warning` | — | `#8A5A00` text on `#FFF4DB` | ≈ 5.9:1 ✓ | Notices such as "still confirming" |
| `--focus-ring` | — | `--accent` 2 px + 2 px white offset | ≥ 3:1 against both | Every focusable element |

All pairs are rechecked with an automated contrast test in CI (US1.13) once the tokens are in code.

## 2. Typography

[RD] §3.2 fixes the roles, not the typefaces.

| Role | Tailwind class | Size / weight / line height | Typeface **[Recommendation]** |
|---|---|---|---|
| `display` (two-line title) | `text-display` | 32/40 desktop, 28/36 phone; line 1 bold `--ink-heading`, line 2 regular `--ink-subheading` | Inter (self-hosted via `next/font`) |
| `heading` | `text-heading` | 20/28 semibold | Inter |
| `body` | `text-body` | 16/24 regular (never below 16 px for inputs, to stop iOS zoom) | Inter |
| `caption` | `text-caption` | 14/20 regular `--ink-muted` | Inter |
| `numeral` | `text-numeral tabular-nums` | 40/44 bold `--accent` for scores; tabular figures in tables | Inter |

Text must reflow to 200% zoom with no horizontal page scroll (the only exception is the metric tables, which scroll inside their own area).

## 3. Shape, spacing, elevation

| Token | Value | Source |
|---|---|---|
| `--radius` | 12 px, used for every card, image tile, chip and button | [RD] §3.3, "one corner radius" |
| Spacing scale | 4 · 8 · 12 · 16 · 24 · 32 · 48 px (Tailwind 1, 2, 3, 4, 6, 8, 12) | Wireframing guide |
| Top rule | 4 px `--accent` bar at the top of report pages and the PDF; 1 px divider under page titles | [RD] §3.3 |
| Elevation | Cards: border only, no shadow. Dialogs and sheets: `shadow-lg` | [RD] ("thin border") |
| Content width | Max 1200 px; auth and forms 480 px; questionnaire card 640 px; chat 760 px | — |

## 4. Tailwind theme and shadcn variables

shadcn/ui components read CSS variables. The mapping is:

| shadcn variable | Our token |
|---|---|
| `--background` | `--surface-page` |
| `--foreground` | `--ink-body` |
| `--card` / `--card-foreground` | `--surface-card` / `--ink-body` |
| `--primary` / `--primary-foreground` | `--accent` / `#FFFFFF` (white on `#2E8B7D` ≈ 4.1:1, so primary buttons use 16 px semibold text, and the hover state darkens to `#25756A` ≈ 5.5:1) **[Recommendation: buttons use `#25756A` as the base colour for full normal-text contrast]** |
| `--secondary` | `#EEF2F5` with `--ink-heading` text |
| `--muted` / `--muted-foreground` | `#F5F6F7` / `#5F6673` |
| `--destructive` | `--danger` |
| `--border` / `--input` | `#E5E7EB` / `#9CA3AF` (input borders need 3:1 → `#9CA3AF` ≈ 2.5:1 ✗ → **use `#8A919C`** ≈ 3.2:1 ✓) |
| `--ring` | `--accent` |
| `--radius` | 12 px |

The tokens live in one file (`frontend/src/styles/tokens.css`) and in `tailwind.config.ts`, so the client's team can rebrand in one place (`NFR-011`).

## 5. Component mapping

| Our component (interaction-spec) | shadcn/ui / library base | Notes |
|---|---|---|
| AppHeader | `NavigationMenu`, `Sheet`, `DropdownMenu` | Sheet for the phone menu |
| Toast | `Sonner` | Polite / assertive regions |
| ConfirmDialog | `AlertDialog` | Focus starts on Cancel |
| FormField | `Form` (react-hook-form + zod), `Input`, `Label`, `Textarea` | zod schemas mirror the backend rules |
| OtpEntry | `Input` (single field) | Not `InputOTP`'s six boxes, so paste and autofill stay reliable |
| QuestionStep | `RadioGroup`, `Checkbox`, `Textarea`, `Progress` | `fieldset` / `legend` wrapper |
| PhotoCapture | Custom + `Button`; camera via `getUserMedia` | HEIC converted on the backend |
| PhotoReview | Custom + `Card`, `Badge` | — |
| PaymentStatus, ProgressSteps | Custom + `Card`, `Button` | — |
| ImageSlot | Custom `figure` + `Dialog` for enlarge | Aspect-ratio boxes |
| Charts | Recharts **[Recommendation]** with custom accessible table | SVG `role="img"` + `<table>` |
| ReportToc | Custom + `Sheet` | Scroll spy via `IntersectionObserver` |
| ChatPanel | Custom + `ScrollArea`, `Textarea` | `role="log"` |
| Settings | `Tabs` (desktop) / list (phone), `Table` | — |
| Skeletons | `Skeleton` | Same shape as final content |

## 6. Iconography and imagery

- **Icons:** lucide-react (shadcn default). Status icons are always paired with text: ✓ `CircleCheck`, ⚠ `TriangleAlert`, • `Loader`.
- **Photos:** a fixed 3:4 portrait ratio for face photos, and 1:1 for thumbnails.
- **AI images:** always a `POTENTIAL`/`AFTER` chip plus the visible caption "AI-generated illustration" (Q11). [RD] §20 item 2 asks for this disclosure, and it is confirmed here.
- **Landing illustration:** abstract or illustrated only — no real person's face (no client assets, and a stock face could be mistaken for a result).

## 7. PDF

The PDF is rendered from the report's own HTML (print stylesheet) with headless Chromium **[Recommendation, from the developer's user-stories review]**. It uses the same tokens with print overrides: white page, the 4 px accent top rule, a page break before each feature, and the [RD] §5–§10 page order.
