---
name: Doka Studio
description: "Vos produits au premier plan."
colors:
  # The Signal kit (docs/project/brand/doka-studio-signal/palette.json). --signal is signal-yellow and --on-signal is
  # charcoal, in both themes and in both interfaces.
  signal-yellow: "#f2c744"
  charcoal: "#20201d"
  warm-paper: "#f5f1e8"
  # --signal-hover: the yellow mixed 86 % toward charcoal, written as a value (style.css).
  signal-hover: "#d5b03f"
  # Hard-coded behind an owner's original photo and behind the poster canvas (style.css: #fff).
  photo-mat: "#ffffff"
  # Light theme: :root[data-theme=clair] in frontend/src/style.css; the first value of each light-dark() in admin.css.
  light-ground: "#f5f1e8"
  light-surface: "#fffdf8"
  light-raised: "#ece6d8"
  light-line: "rgb(32 32 29 / .10)"
  light-control: "#7d786d"
  light-edge: "rgb(32 32 29 / .20)"
  light-active: "rgb(32 32 29 / .08)"
  light-side-bg: "rgb(32 32 29 / .045)"
  light-text: "#20201d"
  light-muted: "#4d4940"
  light-faint: "#5f5a50"
  light-signal-edge: "#d9b032"
  light-hue: "#8f6b00"
  light-accent-soft: "#fcf1d0"
  light-accent-ink: "#7a5c00"
  light-ok: "#145c37"
  light-ok-bg: "#e2f2e8"
  light-warn: "#6b4600"
  light-warn-bg: "#fdf0cf"
  light-bad: "#a3271f"
  light-bad-bg: "#fbeae8"
  light-invert: "#20201d"
  light-invert-ink: "#ffffff"
  light-scrim: "#15130f99"
  light-glass-strong: "rgb(255 253 248 / .86)"
  light-patch-1: "rgb(242 199 68 / .28)"
  light-patch-2: "rgb(222 204 168 / .55)"
  light-patch-3: "rgb(255 255 255 / .7)"
  light-bubble: "#e4dfd7"
  # Dark theme: :root in frontend/src/style.css; the second value of each light-dark() in admin.css.
  dark-ground: "#20201d"
  dark-surface: "#2b2b27"
  dark-raised: "#36362f"
  dark-line: "rgb(245 241 232 / .10)"
  dark-control: "#8f8b80"
  dark-edge: "rgb(245 241 232 / .22)"
  dark-active: "rgb(245 241 232 / .10)"
  dark-side-bg: "rgb(0 0 0 / .22)"
  dark-text: "#f5f1e8"
  dark-muted: "#d6d0c3"
  dark-faint: "#c2bcaf"
  dark-signal-edge: "#f2c744"
  dark-hue: "#f2c744"
  dark-accent-soft: "#3b3113"
  dark-accent-ink: "#f8d97a"
  dark-ok: "#8fddb0"
  dark-ok-bg: "#1d3327"
  dark-warn: "#f0c26a"
  dark-warn-bg: "#3a2f14"
  dark-bad: "#ff9a8f"
  dark-bad-bg: "#3d2320"
  dark-invert: "#f5f1e8"
  dark-invert-ink: "#100f0e"
  dark-scrim: "#000000cc"
  dark-glass-strong: "rgb(43 43 39 / .88)"
  dark-patch-1: "rgb(242 199 68 / .16)"
  dark-patch-2: "rgb(110 98 70 / .34)"
  dark-patch-3: "rgb(255 255 255 / .04)"
  dark-bubble: "#34312d"
  # Console only (admin.css): the drawer's scrim and the dialog's backdrop, both themes.
  console-scrim: "rgb(21 19 15 / .55)"
typography:
  page-title:
    fontFamily: "Figtree, system-ui, sans-serif"
    fontSize: "26px"
    fontWeight: 800
    lineHeight: "32px"
  heading-1:
    fontFamily: "Figtree, system-ui, sans-serif"
    fontSize: "22px"
    fontWeight: 800
    lineHeight: "28px"
    letterSpacing: "-0.01em"
  heading-2:
    fontFamily: "Figtree, system-ui, sans-serif"
    fontSize: "18px"
    fontWeight: 800
    lineHeight: "24px"
    letterSpacing: "-0.01em"
  heading-3:
    fontFamily: "Figtree, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 700
    lineHeight: "20px"
  top-title:
    fontFamily: "Figtree, system-ui, sans-serif"
    fontSize: "17px"
    fontWeight: 750
    lineHeight: "24px"
  chat-question:
    fontFamily: "Figtree, system-ui, sans-serif"
    fontSize: "clamp(26px, 3.4vw, 32px)"
    fontWeight: 750
    lineHeight: 1.15
    letterSpacing: "-0.02em"
  body:
    fontFamily: "Figtree, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: "20px"
  body-chat:
    fontFamily: "Figtree, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: "22px"
  field:
    fontFamily: "Figtree, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 550
    lineHeight: "20px"
  button:
    fontFamily: "Figtree, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 700
    lineHeight: 1.2
  button-main:
    fontFamily: "Figtree, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 700
    lineHeight: 1.2
  label:
    fontFamily: "Figtree, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 650
    lineHeight: "20px"
  help:
    fontFamily: "Figtree, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: "19px"
  badge:
    fontFamily: "Figtree, system-ui, sans-serif"
    fontSize: "12.5px"
    fontWeight: 700
  nav-label-phone:
    fontFamily: "Figtree, system-ui, sans-serif"
    fontSize: "12.5px"
    fontWeight: 650
    lineHeight: "16px"
  console-body:
    fontFamily: "Figtree, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.5
  console-heading-1:
    fontFamily: "Figtree, system-ui, sans-serif"
    fontSize: "26px"
    fontWeight: 800
    lineHeight: "32px"
    letterSpacing: "-0.015em"
  console-heading-2:
    fontFamily: "Figtree, system-ui, sans-serif"
    fontSize: "17px"
    fontWeight: 750
    lineHeight: "24px"
  console-figure:
    fontFamily: "Figtree, system-ui, sans-serif"
    fontSize: "28px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.01em"
rounded:
  text-button: "4px"
  poster: "5px"
  version-mark: "9px"
  thumb: "10px"
  chip: "12px"
  nav-row: "12px"
  chat-poster: "14px"
  recent-row: "14px"
  field: "16px"
  tile: "18px"
  group: "20px"
  console-card: "20px"
  card: "24px"
  composer: "24px"
  console-dialog: "24px"
  dialog: "28px"
  frame: "28px"
  pill: "999px"
spacing:
  gutter: "20px"
  gutter-phone-frame: "16px"
  gutter-phone: "12px"
  stack-gap: "14px"
  page: "860px"
  main-max: "1480px"
  sidebar: "288px"
  rail: "76px"
  frame-gap: "12px"
  drawer: "min(320px, 86vw)"
  console-column: "860px"
  console-column-wide: "1240px"
components:
  # Values resolve to the light theme; in the dark theme read each light- key as its dark- twin.
  button-primary:
    backgroundColor: "{colors.signal-yellow}"
    textColor: "{colors.charcoal}"
    typography: "{typography.button-main}"
    rounded: "{rounded.pill}"
    padding: "0 20px"
    height: "48px"
  button-primary-hover:
    backgroundColor: "{colors.signal-hover}"
  button-primary-disabled:
    backgroundColor: "{colors.light-raised}"
    textColor: "{colors.light-faint}"
  button-secondary:
    textColor: "{colors.light-text}"
    typography: "{typography.button-main}"
    rounded: "{rounded.pill}"
    padding: "0 20px"
    height: "48px"
  button-default:
    textColor: "{colors.light-text}"
    typography: "{typography.button}"
    rounded: "{rounded.pill}"
    padding: "0 20px"
    height: "40px"
  button-default-hover:
    backgroundColor: "{colors.light-active}"
  button-ghost:
    textColor: "{colors.light-text}"
    rounded: "{rounded.pill}"
    padding: "0 12px"
    height: "40px"
  button-text:
    textColor: "{colors.light-muted}"
    rounded: "{rounded.text-button}"
    padding: "0 4px"
    height: "32px"
  button-icon:
    rounded: "{rounded.pill}"
    size: "44px"
  button-send:
    backgroundColor: "{colors.signal-yellow}"
    textColor: "{colors.charcoal}"
    rounded: "{rounded.pill}"
    size: "44px"
  field:
    backgroundColor: "{colors.light-surface}"
    textColor: "{colors.light-text}"
    typography: "{typography.field}"
    rounded: "{rounded.field}"
    padding: "10px 16px"
    height: "48px"
  chip:
    backgroundColor: "{colors.light-surface}"
    textColor: "{colors.light-muted}"
    rounded: "{rounded.chip}"
    padding: "0 15px"
    height: "40px"
  chip-selected:
    backgroundColor: "{colors.light-accent-soft}"
    textColor: "{colors.light-accent-ink}"
    rounded: "{rounded.pill}"
  badge:
    backgroundColor: "{colors.light-raised}"
    textColor: "{colors.light-muted}"
    typography: "{typography.badge}"
    rounded: "{rounded.pill}"
    padding: "0 10px"
    height: "24px"
  badge-ok:
    backgroundColor: "{colors.light-ok-bg}"
    textColor: "{colors.light-ok}"
  badge-warn:
    backgroundColor: "{colors.light-warn-bg}"
    textColor: "{colors.light-warn}"
  badge-bad:
    backgroundColor: "{colors.light-bad-bg}"
    textColor: "{colors.light-bad}"
  segment-selected:
    backgroundColor: "{colors.light-invert}"
    textColor: "{colors.light-invert-ink}"
    rounded: "{rounded.pill}"
    height: "38px"
  side-link:
    textColor: "{colors.light-muted}"
    rounded: "{rounded.nav-row}"
    padding: "0 12px"
    height: "40px"
  side-link-current:
    backgroundColor: "{colors.light-active}"
    textColor: "{colors.light-text}"
  credits-pill:
    textColor: "{colors.light-text}"
    rounded: "{rounded.pill}"
    padding: "0 14px"
    height: "44px"
  phone-bar-item:
    textColor: "{colors.light-muted}"
    typography: "{typography.nav-label-phone}"
    rounded: "{rounded.field}"
    padding: "0 2px"
    height: "58px"
  phone-bar-icon-current:
    backgroundColor: "{colors.light-accent-soft}"
    textColor: "{colors.light-accent-ink}"
    rounded: "{rounded.pill}"
    width: "58px"
    height: "32px"
  phone-bar-make:
    backgroundColor: "{colors.signal-yellow}"
    textColor: "{colors.charcoal}"
    rounded: "{rounded.pill}"
    size: "56px"
  card:
    backgroundColor: "{colors.light-surface}"
    rounded: "{rounded.card}"
    padding: "20px 22px"
  dialog-confirm:
    backgroundColor: "{colors.light-glass-strong}"
    rounded: "{rounded.dialog}"
    padding: "24px"
    width: "440px"
  toast:
    backgroundColor: "{colors.light-glass-strong}"
    textColor: "{colors.light-text}"
    rounded: "{rounded.card}"
    padding: "10px 10px 10px 18px"
  bubble-owner:
    backgroundColor: "{colors.light-invert}"
    textColor: "{colors.light-invert-ink}"
    typography: "{typography.body-chat}"
    rounded: "{rounded.tile}"
    padding: "10px 14px"
  composer:
    backgroundColor: "{colors.light-surface}"
    rounded: "{rounded.composer}"
    padding: "8px 8px 8px 10px"
  console-button:
    textColor: "{colors.light-text}"
    rounded: "{rounded.pill}"
    padding: "0 18px"
    height: "44px"
  console-button-primary:
    backgroundColor: "{colors.signal-yellow}"
    textColor: "{colors.charcoal}"
  console-field:
    backgroundColor: "{colors.light-surface}"
    textColor: "{colors.light-text}"
    rounded: "{rounded.field}"
    padding: "10px 14px"
    height: "48px"
  console-card:
    backgroundColor: "{colors.light-surface}"
    rounded: "{rounded.console-card}"
    padding: "16px 20px"
---

# Design System: Doka Studio

As built on 2026-11-21 on the branch `redesign` after T-REDESIGN-001 to 006 (ADR-123; design: docs/project/designs/app-redesign.md v2), on the local stub build. Every value below is read from `frontend/src/style.css`, `frontend/src/admin/admin.css` and the components named. The screens are captured again with `uv run python ../frontend/tests/design_capture.py <label>` from `backend/`.

## Overview

**Creative North Star: "The poster is the one lifted thing"** (the words of `style.css`'s header and of its `.stage` rule).

Doka Studio has two interfaces on one system. **The shops' app** (`frontend/index.html`, `frontend/src/style.css`, `App.vue`, `ChatView.vue` and the scoped styles of `ShopHome.vue`, `ShopCredits.vue`, `ShopAccount.vue`) is a French, phone-first workspace for an owner on an Android phone in Chrome. **The operator's console** (`frontend/admin/index.html`, `frontend/src/admin/`) is an English workspace for one operator. Both use the kit's Warm Paper, Charcoal and Signal Yellow, Figtree, the same token table, the same shell (sidebar, rail, drawer) and the same frame.

Each has a light theme and a dark one. The theme follows the device until the person picks one. The shops' app stores the pick under `affiche.theme` and applies it before the first paint (inline script in `index.html`). The console stores it under `affiche.admin.theme` (`Admin.vue`). The console imports nothing from the shops' app and requests nothing from it (`admin.test.ts`). A third page, « Vos données » (`frontend/public/donnees.html`), is static: Figtree, five of the tokens copied inline, solid sections, the device's theme.

The shop's poster is outside this system. The canvas draws it with the poster's own fonts and colours, and no page token reaches it. The poster never carries the Doka identity.

**Key Characteristics:**
- Warm Paper (light) or Charcoal (dark) under three soft lights.
- The main action is charcoal on Signal Yellow, in both themes.
- Resting surfaces (cards, lists, fields, chips) are opaque with a hairline. No blur, no shadow.
- One glass, `--glass-strong`, only on what floats: bars, the drawer, sheets, dialogs, toasts.
- A sidebar over 1180 px, reduced to a rail on demand; a drawer at 1180 px and under; a bottom bar at 720 px and under (shops only).
- Contrast is tested: from the pinned tokens where the browser cannot see the pixels, on the rendered screens elsewhere.
- 44 px touch targets; 52 px main buttons and fields on touch screens.

## Colors

Warm paper and charcoal carry the page. Signal Yellow fills the main action. A dark ochre line (light) or the yellow (dark) marks rings and progress. Red, green and amber carry state only.

### Primary
- **Signal Yellow** (`--signal`, #f2c744, both themes): a **fill**, always with **Charcoal** (`--on-signal`, #20201d) on it. It fills the main action (`button.primary`, `a.primary`, `.download-button`), the chat's send button, the phone bar's centre « Nouvelle affiche », the tile behind the D (`.signal-symbol`), and in the console the primary button and the banner.
- **Signal edge** (`--signal-edge`): the 1.5 px border of a yellow fill. #d9b032 in light, #f2c744 in dark. The console also uses it for the 4 px left border of `.note`.
- **Signal hover** (`--signal-hover`, #d5b03f, both themes): the main action under a hovering pointer. It is the yellow mixed 86 % toward charcoal, written as a value because the contrast checks read `rgb()` only. A main action never changes its opacity.
- **Signal line** (`--hue`): every ring, chosen border and progress mark: the border of a chosen chip, format or poster element, the loading line, the wait bar's moving part, the current step's ring, the generation dot, the chat spinner's arc, the press ring under reduced motion. It is a dark ochre (#8f6b00) in light and the yellow (#f2c744) in dark, because a yellow line on paper is 1.4:1. In the console it is also the focus ring and the 2 px border of `.kept` and `.shown`.
- **Accent soft / accent ink** (`--accent-soft`, `--accent-ink`): the pale fill of a chosen chip, poster element or format, the active editor tool, the phone bar's current icon and the chat's « inspiration » role, with its ink on top. Light #fcf1d0 / #7a5c00; dark #3b3113 / #f8d97a. Shops only.

### Neutral
- **Warm Paper** (#f5f1e8): the light `--ground`, the dark `--text` and `--invert`.
- **Charcoal** (#20201d): the dark `--ground` (the kit's Charcoal, ADR-123), the light `--text` and `--invert`, `--on-signal`.
- **Near-black** (#100f0e): only the dark `--invert-ink`.
- **White** (#ffffff): the light `--invert-ink`, and the hard-coded mat behind an owner's photo and the poster canvas (`.photo-strip img`, `.proof .photo img`, `.comparison figure:first-child img`, `.poster-canvas`). The chat's poster frame is hard-coded #14110e.

### Token table

`:root` is the dark theme and `:root[data-theme=clair]` the light one in `style.css`. In `admin.css` each colour is written once as `light-dark(<light>, <dark>)`. `tokens.test.ts` pins the shops' values and `brand.test.ts` pins the console's, from one table (D-REDESIGN-001).

| Token | Light | Dark | Role |
| --- | --- | --- | --- |
| `--ground` | #f5f1e8 | #20201d | Page ground (`:root`, the console's `body`); the review panel's and the credits dialog's ground |
| `--surface` | #fffdf8 | #2b2b27 | Cards, lists, fields, chips, the composer, the pills over the poster; the solid fallback of the glass |
| `--raised` | #ece6d8 | #36362f | Tracks and troughs (tabs, segmented control, switch off), the disabled main button, the owner's bubble in dark, a neutral badge, a press under reduced motion |
| `--line` | rgb(32 32 29 / .10) | rgb(245 241 232 / .10) | The hairline of a card, a row, a bar's edge, the frame |
| `--control` | #7d786d | #8f8b80 | A field's and the composer's boundary (3:1), drop zones, spinner tracks, the disabled send button |
| `--edge` | rgb(32 32 29 / .20) | rgb(245 241 232 / .22) | The border of a default or secondary button, a chip, the credits pill |
| `--active` | rgb(32 32 29 / .08) | rgb(245 241 232 / .10) | Hover, and the current sidebar row |
| `--side-bg` | rgb(32 32 29 / .045) | rgb(0 0 0 / .22) | The sidebar's column, painted by the frame |
| `--text` | #20201d | #f5f1e8 | Text; the shops' focus ring; a focused field's border |
| `--muted` | #4d4940 | #d6d0c3 | Secondary text, labels, placeholders (shops) |
| `--faint` | #5f5a50 | #c2bcaf | Help, meta lines, counts, section headings in the sidebar; placeholders (console) |
| `--signal` / `--on-signal` | #f2c744 / #20201d | same | The main action |
| `--signal-edge` | #d9b032 | #f2c744 | The main action's border |
| `--signal-hover` | #d5b03f | same | The main action, hovered (shops only) |
| `--hue` | #8f6b00 | #f2c744 | The line accent |
| `--accent-soft` / `--accent-ink` | #fcf1d0 / #7a5c00 | #3b3113 / #f8d97a | A chosen choice's fill and ink (shops only) |
| `--ok` / `--ok-bg` | #145c37 / #e2f2e8 | #8fddb0 / #1d3327 | Success |
| `--warn` / `--warn-bg` | #6b4600 / #fdf0cf | #f0c26a / #3a2f14 | Caution |
| `--bad` / `--bad-bg` | #a3271f / #fbeae8 | #ff9a8f / #3d2320 | Failure |
| `--invert` / `--invert-ink` | #20201d / #ffffff | #f5f1e8 / #100f0e | The chosen segment, a switch when on, « Retirer de l'affiche », the chosen style's tick, the account avatar, the owner's bubble in light, the chat's remove-photo button (shops only) |
| `--scrim` | #15130f99 | #000000cc | Behind the drawer, dialogs and the review panel (shops). The console uses rgb(21 19 15 / .55) in both themes |
| `--glass-strong` | rgb(255 253 248 / .86) | rgb(43 43 39 / .88) | The one glass |
| `--patch-1…3` | rgb(242 199 68 / .28), rgb(222 204 168 / .55), rgb(255 255 255 / .7) | rgb(242 199 68 / .16), rgb(110 98 70 / .34), rgb(255 255 255 / .04) | The three soft lights: yellow, sand, white. The console calls them `--yellow-light`, `--sand-light`, `--white-light` |
| `--bubble` | #e4dfd7 | #34312d | The current row of the chat's list of modifications (shops only) |

### Contrast

What the tests prove:
- **Text on the glass, whatever scrolls under it.** `--text`, `--muted` and `--faint` on `--glass-strong` composited over pure black and over pure white are at least 4.5:1, in both themes. Shops: `tokens.test.ts`, « keeps the text of what floats at 4.5:1 whatever is behind it, black or white ». Console: `brand.test.ts`, « keeps the texts at 4.5:1 on the one glass, whatever scrolls under it ». The browser checks cannot see what scrolls under a sibling, so this is computed from the pinned values. The mockup's lighter glass (.62) fell to 2.74:1 over a white poster.
- **The sidebar's tint.** `--muted` and `--faint` on `--side-bg` over `--ground` are at least 4.5:1 in both themes (`tokens.test.ts`, « keeps the sidebar's secondary text at 4.5:1 on its tint over the ground »). The console's test also proves `--text` on `--active` over that column (`brand.test.ts`, « keeps the sidebar's texts at 4.5:1 on the frame's tint »). On a hovered or current sidebar row a count and a recent poster's state switch from `--faint` to `--muted` (`style.css`: 4.37:1 light otherwise, where the yellow light is under the sidebar).
- **Rendered screens** (`frontend/tests/browser_smoke.py`, also called by `shop_dashboard_browser.py` and `chat_browser.py`), in both themes over the real backdrop: `check_contrast` (text 4.5:1, or 3:1 from 24 px or from 18.66 px at 700; placeholders 4.5:1 and lighter than typed text) and `check_marks` (the `MARKS` list: each line accent 3:1 against what is behind it; the wait bar's moving part 3:1 in light and 6.57:1 in dark; the send button's glyph 4.5:1 on its yellow; the main action's label 4.5:1 on its yellow).
- **The main action's paint.** `check_primary` asserts on an enabled main action a fill of rgb(242, 199, 68), text rgb(32, 32, 29) and the theme's `--signal-edge`, and that the named secondary action is clear with `--text` and `--edge`.
- **Fields.** `check_field` asserts an empty field's boundary is `--control` at rest and `--text` when focused by the keyboard, 3:1 both times. `composer_edge` in `chat_browser.py` does the same for the composer.

Computed from the tokens, not a test: charcoal on Signal Yellow 10.13:1; charcoal on `--signal-hover` 7.86:1; the ochre `--hue` 3.95:1 on `--raised`, 4.36:1 on `--ground`, 4.84:1 on `--surface`; Signal Yellow on paper 1.43:1.

**The Fill-and-Line Rule.** `--signal` is a fill, and its content is always `--on-signal`. Anything that must be seen against the page is a line, and a line uses `--hue`.

**The Yellow Action Rule.** The main action is charcoal on Signal Yellow with a 1.5 px `--signal-edge`, in both themes (ADR-123 reverses ADR-122's ink button). Hovered, it is `--signal-hover`. Disabled, it is `--raised` with `--faint`. Busy, it keeps its yellow. Where « Partager » is the main action, the download link is the secondary (`.download-button.secondary`).

**The Mark-and-Place Rule.** A state colour is a dot, a ground or a word's colour, and it always comes with words. A toast's kind is its dot and its place (errors at the bottom, notices at the top), never its text colour.

## Typography

**Font:** Figtree, with `system-ui, sans-serif` as fallback, in both interfaces. The shops' app ships `frontend/public/fonts/Figtree-Variable.woff2` (weights 300 to 900, `font-display: swap`). The console has its own copy, `frontend/src/admin/Figtree-Variable.woff2`, with `Figtree-OFL.txt`, loaded as `url('./Figtree-Variable.woff2')`. Nothing is fetched from another site. `admin_browser.py` and `shop_dashboard_browser.py` check that a Figtree face has `status === 'loaded'`.

**Character:** one humanist sans for everything. The weight carries the hierarchy (400 to 800). Size changes little.

**Why Figtree, not the kit's fonts.** The Signal guide names Space Grotesk Bold for titles and Noto Sans for text, and accepts a system sans for an interface without them. Figtree was chosen with the approved mockup (ADR-077) and kept by ADR-122. Space Grotesk survives only as outlines inside the logo files.

**The narrow no-break space.** Figtree has no U+202F, the French thousands separator in « 90 000 ». A second `@font-face` named Figtree maps `NotoSans-Regular.ttf` to `unicode-range: U+202F` only. The other font files in `public/fonts/` are the poster's.

### Hierarchy (shops' app)
- **Page title** (800, 26px/32px): `.page-title`, the `h1` of Accueil, Mes affiches, Styles, Mes crédits and Mon compte, and the sign-in and intake titles. It takes the focus on arrival and shows no box; a 2 px underline 6 px under it appears only after a key was pressed (`:root[data-keys]`).
- **Top bar title** (750, 17px/24px): `.top-title`, the poster's name in the chat, over 720 px, cut with an ellipsis.
- **Chat question** (750, `clamp(26px, 3.4vw, 32px)`/1.15, -0.02em): « Quelle affiche créons-nous ? » in an empty conversation; its greeting under it is 16px/24px `--muted`.
- **Heading 1** (800, 22px/28px, -0.01em, `text-wrap: balance`): other `h1`. The phone editor bar's title is 16px/22px at 700.
- **Heading 2** (800, 18px/24px, -0.01em). A review section's heading is 21px/27px. The sidebar's « Affiches récentes » is 13px/18px at 600 in `--faint`.
- **Heading 3** (700, 14px).
- **Body** (400, 14px/20px). The chat is 15px/22px.
- **Field** (550, 15px). At 720 px and below, fields are 16px (iOS zooms under 16px). The composer's textarea is 16px/22px.
- **Button** (700, 14px, 1.2). Main and secondary buttons are 15px; the editor's phone bottom bar uses 15.5px.
- **Label** (650, 13px, `--muted`). **Help** (400, 13px/19px, `--faint`).
- **Badge** (700, 12.5px). **Phone bar label** (650, 12.5px/16px).
- **Figures**: the recap price in the chat (800, 24px/30px).

### Hierarchy (console)
- **Body** 16px/1.5. **Heading 1** 800, 26px/32px, -0.015em. **Heading 2** 750, 17px/24px. **Small** 14px `--faint`. **Label** 650, 14px `--muted`.
- **Overview figure** (`.kpi .value`) 700, 28px/1.2, -0.01em; its label 13px `--muted`; its detail 14px `--faint`.
- **Shops table**: 14px; headers 12.5px at 500 in `--faint`, no band.
- Fields are 16px at every width where a phone would zoom (the filter).

**The One Family Rule.** Both interfaces use Figtree for every word. The poster keeps its own fonts. Never fetch a font from another origin.

**The Tabular Rule.** The shops' `:root` sets `font-variant-numeric: tabular-nums` and `font-synthesis: none`. The console applies tabular figures to the Shops table's numeric columns from 600 px (`.shops .num`, right-aligned) and to payment amounts.

## Layout

### The shell

Both interfaces share one shell (D-REDESIGN-002, D-REDESIGN-005). `<html>` carries `data-shell` while the person is signed in, and `data-rail` when the rail applies. CSS reads two variables: `--side-w` and `--gap`, both `0px` by default.

| Width | What shows |
| --- | --- |
| Over 1180 px (`width > 1180px`) | The sidebar, fixed, `--side-w: 288px`, `--gap: 12px`. With `data-rail`, `--side-w: 76px`. The frame is painted |
| 1180 px and under (`width <= 1180px`) | No sidebar. The same `aside.side` is a drawer, opened by the menu button |
| 720 px and under (`width <= 720px`) | Shops only: the bottom bar as well, outside the chat and the editor |

Each width is split by complementary conditions (`>` and `<=`), in CSS and in `matchMedia`, so that a fractional width under zoom is always on one side.

**The sidebar** (over 1180 px): fixed at `inset-block: var(--gap)`, `inset-inline-start: var(--gap)`, `width: var(--side-w)`, padding 18px 14px 14px. It scrolls inside itself. It has no fill of its own: the frame paints its column. Shops: the horizontal logo (220px), « Nouvelle affiche » (`a.primary`), the navigation (Accueil, Mes affiches with its count, Styles with its count), « Affiches récentes » (up to five links with a 32 × 40 thumbnail), then at the foot the credit card, the account row, « Se déconnecter ». Console: the logo, « New shop », the navigation (Overview, Shops, Payments, Service), then the theme switch, the actor and « Sign out ».

**The rail**: icons only, 76px wide, padding 14px 8px (console 12px 8px). Labels are visually hidden and each link keeps a `title`. The D (40px on its yellow tile) replaces the logo. « Affiches récentes » is hidden. The credit card shows the number alone. The shops' rail toggle stores `affiche.rail` (`'1'` or absent), applied by `index.html` before the first paint; the step editor always has the rail. The console's rail is in memory only.

**The drawer** (1180 px and under): fixed, the window's height, `min(320px, 86vw)` wide, `--glass-strong` with its own blur, a `--line` edge on its right, corners `0 24px 24px 0` (shops), `--lift`. Closed, it is `translateX(-105%)` and `visibility: hidden`, and `inert` at once. It opens in 280ms on `transform` with `cubic-bezier(.2, .8, .2, 1)`. A scrim covers the page behind it. Shops: drawer 42, scrim 41, above the toasts (40) and under the dialogs (45, 50). Console: drawer 50, scrim 40.

**The drawer's contract.** The menu button has `aria-expanded` and `aria-controls`. Opening moves the focus to « Fermer le menu ». Open, the skip link, the top bar, `main` and the phone bar are `inert`. Escape, the scrim or the close button close it and return the focus to the menu button. A destination closes it and the route owns the focus. It also closes when the window becomes wider than 1180 px, when a dialog opens, and on every route change. It makes no history entry: Back acts on the page.

**The frame** (over 1180 px): `body::before`, absolute, `inset: var(--gap)`, as tall as the page, a 1px `--line` border and 28px corners, behind everything (`z-index: -1`). Its background paints the sidebar's column: `--side-bg` up to `--side-w`, a 1px `--line`, then nothing. It scrolls with the page. Nothing is clipped by it. In the shops' step editor (`data-editing`) the gap is `0px` and the frame has no border or corners: the editor is a work surface.

**The top bar**: sticky at `top: 0` in the page's flow, after the sidebar's margin (`margin-inline: calc(var(--gap) + var(--side-w)) var(--gap)`). Its glass is on its own `::before`, with a `--line` bottom edge and the frame's top-right corner (28px shops, 27px console) over 1180 px. Shops: at least 64px plus the top safe area. It holds the menu button (≤ 1180) or the rail toggle (> 1180, not while editing), the D on its tile (≤ 1180, not in the chat at ≤ 720), the title in the chat (> 720), the « Message / Pas à pas » switch in the creator, « Nouvelle affiche » as a plus (≤ 720, in the chat), the credits pill, and the theme switch (> 720, and at every width while signed out). Console: at least 64px, the menu or rail toggle and « Filter shops » on the Shops list.

**The phone bar** (shops, 720 px and under, not in the chat and not in the editor): fixed at the bottom, `--glass-strong` with blur, a `--line` top, padding 6px plus the safe area. Five equal columns: Accueil, Affiches, the centre « Nouvelle affiche », Styles, Compte. The centre action is a 56px yellow circle with `--signal-edge` and `--lift`. Each other item is 58px high, an icon in a 58 × 32 pill over a one-line label; the current item's pill is `--accent-soft`. Counts and the long words (« Mes affiches 3 », « Mon compte ») are visually hidden but stay in the accessible name. The console has no bottom bar and nothing fixed to the bottom.

**The three rules** (they hold in both interfaces):
1. **Nothing between a fixed element and the window.** No `backdrop-filter`, `filter`, `transform`, `perspective`, `contain` or `container-type` on an ancestor of a `position: fixed` element. A blur is painted by the fixed or sticky element itself, or by its `::before`. The top bar's glass is on its `::before`. The drawer blurs and moves itself because it holds nothing fixed. The review panel has its own opaque ground and never blurs, because its decision bar is fixed on a phone.
2. **The window scrolls.** No wrapper around the top bar and `main`, no `overflow` on an ancestor of a sticky element. The frame is painted behind, not wrapped around.
3. **One thing is exposed at a time.** What is not shown is `hidden` or `inert`: a closed drawer, the page behind an open drawer or a dialog, the sidebar and the phone bar under a dialog (`:inert="modalOpen || peeking"`), the shop's parts while the identity gate is closed (`v-if="shown"`).

`check_reach` in `browser_smoke.py` scrolls the review and final panels to their end on a phone and checks that each decision stays fixed, inside the viewport, and is what a tap at its centre reaches.

### The content

`main` takes the same margins as the top bar. Its gutters are `--gutter-l` and `--gutter-r`: 20px, or the safe area if larger; 12px at 720 px and below for the chat and the editor; 16px for the five frame screens (`main:has(> :is(.shop-home, .shop-account, .gallery, div.credits-container))`). Over 1180 px `main` has no max width and the editor is at most 1440px, centred. Otherwise `main` is at most 1480px. Toasts are centred on the content column (`left: calc(50% + var(--side-w) / 2)`); a notice sits at `top: calc(64px + var(--gap) + env(safe-area-inset-top, 0px))`; the loading line runs from `calc(var(--gap) + var(--side-w))` to `var(--gap)`.

**The One Frame Rule.** Accueil, Mes affiches, Styles, Mes crédits and Mon compte share one content width, `--page: 860px`, and one title, `.page-title`. As a panel inside the creator, Mes crédits keeps its dialog's 680px.

**Other widths (shops):** sign-in 420px; intake 640px; chat 680px, or 1080px with a 340px poster column from 880 px (24px column gap); confirmation 440px; conditions of use 560px; credits dialog `min(680px, 100% - 24px)`; review panel `inset: 3vh max(3vw, calc(50vw - 580px))`; toast `max-width: min(94vw, 680px)`.

**The console's column:** `main` centres its own column in the space right of the sidebar: `--column: 860px`, 1240px on wide screens (`main.wide`), 420px signed out (`main.out`). Its gutter is 20px, 16px under 600 px. The banner and the one-time secret (`.banner`, `.shown`) take the same inset.

**The editor.** Over 1080 px: three columns, a 360px rail, the stage, a 156px versions column, 14px gap; the stage sticks 64px from the top. At 1080 px and under: one flex column; the main action becomes a fixed glass bar at the bottom; 150px is reserved below.

**Rhythm.** There is no spacing scale. 14px is the most frequent gap. Card padding runs from 16 to 28px.

**Breakpoints:**

| Query | What changes |
| --- | --- |
| `width > 1180px` / `width <= 1180px` | Sidebar or rail and the frame / the drawer (both interfaces). Over 1180 px an empty chat centres its question and composer as one group; the console shows four figures across and two columns |
| `max-width: 1080px` | Editor in one column; the main action is a fixed bottom bar; large view of the poster; tools as an icon row |
| `min-width: 880px` | Chat with a poster: two columns |
| `width <= 720px` / `max-width: 720px` | Phone: bottom bar, compact top bar, theme switch in the drawer, 12/16px gutters, 16px fields, the editor's own top bar, full-screen review panel |
| `max-width: 480px` | The chat's recap goes to two columns |
| `max-width: 420px` | The top bar with the « Message / Pas à pas » switch packs tighter |
| `width >= 600px` / `width < 600px` (console) | Two figures per row, right-aligned numbers / one figure per row, one card per shop, 16px gutter |
| `hover: hover` | Hover looks exist only here |
| `pointer: coarse` | 44px minimum targets; 52px main buttons and fields |
| `forced-colors: active` | The switch goes back to a native checkbox |
| `prefers-reduced-transparency` / `prefers-reduced-motion` | The glass becomes `--surface` and nothing blurs |

**Safe areas.** `viewport-fit=cover` and `interactive-widget=resizes-content` are set. Every fixed or sticky bar and the drawer pad with `max(…, env(safe-area-inset-*))`. `scroll-padding` is 64px at the top and 80px at the bottom (150px at the bottom at 1080 px and below).

## Elevation & Depth

Depth comes from three things only: the soft lights behind the window, one glass on what floats, and a short list of shadows. The backdrop is `html::before`, fixed, with `--ambient`: three radial gradients of `--patch-1` (yellow, top left), `--patch-2` (sand, bottom right) and `--patch-3` (white, centre right) on the ground. It is never a blurred copy of the poster. `tokens.test.ts` pins `--ambient` and checks that the light theme changes the lights, not the gradient.

### One glass

`--glass-strong` with `--blur-panel` (`blur(26px) saturate(1.5)`; the console's `--blur` is `blur(22px) saturate(1.35)`). It is used on:
- the top bar's `::before` (both interfaces);
- the drawer (both);
- the phone bar, the editor's phone bar (`.titlerow.bar`), the step navigation (`.main-action.step-nav`), the editor's fixed bottom bar at 1080 px and under, the sticky poster strip (`.pin`), the review panel's decision bar on a phone;
- toasts (`.message`), the confirmation and conditions dialogs (`.confirm`, no blur of its own: its sheet blurs the page with `blur(6px)`), the large poster view (`.stage.peek`);
- the console's dialog.

The old tokens `--glass`, `--glass-panel`, `--glass-field`, `--glass-line`, `--glass-hi`, `--warn-glass`, `--glass-shadow`, `--msg-shadow` and `--blur-field` are gone.

**Resting surfaces are opaque.** `.sign-in`, `.intake`, `.empty`, `.look-card`, `.rows`, `.card`, `.group`, `.comparison figure`, `.shot`, `.facts`, `.job-state` are `--surface` with a 1px `--line` border: no blur, no shadow. So are fields, chips, style tiles, the switch group, the composer and the chat's side panel, and the console's cards. `check_resting` in `browser_smoke.py` asserts this on every such element on screen, including `.rail` and their `::before` and `::after`, in both themes. The pills over the poster (`.frame .badge`, `.gen-pill`) are `--surface`: any poster is behind them.

### Shadow vocabulary
- **Lift** (`--lift`; light `0 2px 4px rgb(60 44 16 / .08), 0 28px 60px -28px rgb(60 44 16 / .45)`; dark `0 2px 4px rgb(0 0 0 / .45), 0 28px 60px -28px rgb(0 0 0 / .9)`): what floats. The drawer, toasts, the confirmation dialog, the chosen tab, the badge and generation pill over the poster, « Retirer de l'affiche », the phone bar's centre action, the console's drawer and dialog.
- **Poster shadow** (`--poster-shadow`; light `0 1px 2px rgb(40 28 14 / .08), 0 6px 16px -6px rgb(40 28 14 / .16)`; dark `0 8px 20px -8px rgb(0 0 0 / .6)`): the poster canvas, version thumbnails, the final check's image.
- **Composer shadow** (`0 1px 2px rgb(0 0 0 / .04), 0 10px 24px -18px rgb(0 0 0 / .22)`): the one resting surface with a shadow, from the mockup (R-REDESIGN-001).
- **Selection ring** (`0 0 0 2px var(--ground), 0 0 0 5px var(--text)`): a chosen style tile. It is a shadow so that the focus outline still shows outside it.
- **Scrim**: `.confirm-sheet` lays `--scrim` with `blur(6px)`. The review panel casts `0 0 0 100vmax var(--scrim)`.

### Stacking order (shops)
Editor rail tabs 2 · top bar 5 · sidebar over 1180 px 6 · editor phone bar 6 · bottom bars and phone bar 20 · large poster view 25 · review panel 30 · toasts 40 · drawer scrim 41 · drawer 42 · conditions of use 45 · confirmation 50 · skip link 60 · loading line 70.

Console: top bar 20 · sidebar 30 · scrim 40 · drawer 50.

**The One Lifted Thing Rule.** The stage has no surface of its own. The poster sits on the backdrop and is the one lifted object on the screen.

**The Blur Once Rule.** Only what floats blurs, and nothing inside it blurs again.

**The Solid Fallback Rule.** Where `backdrop-filter` is unsupported, `--glass-strong` becomes `--surface`. Under `prefers-reduced-transparency: reduce` or `prefers-reduced-motion: reduce`, `--glass-strong` becomes `--surface`, `--blur-panel` becomes `none`, and the confirmation sheet loses its blur (`tokens.test.ts` pins both blocks).

## Shapes

Actions and chosen states are pills (999px). A choice not yet made is a rounded square. Containers have large, soft corners.

Shops: the frame and dialogs 28px; cards, lists, toasts, the credits dialog 24px (`--radius`); the composer 24px; groups, facts, the wait block, the switch group, the chat's side panel 20px; style tiles and chat bubbles 18px (a bubble's corner toward its speaker 6px); fields, the recap, the credit card 16px (`--field`); recent rows and the chat's poster 14px; chips, sidebar rows and the D's tile in the header 12px; version thumbnails 10px; the version mark 9px; the poster 5px; text buttons 4px. Console: cards 20px, fields 16px, shop cards under 600 px 16px, the banner 16px, the dialog 24px, sidebar rows 12px, buttons pills.

Strokes: 1.5px for control and button borders, 1px for hairlines and glass edges, 2px dashed for drop zones and the « new » tile. Shops' icons are one outline set: 16px, stroke 1.5, round caps, `currentColor`, inline in `App.vue` (ADR-050). In the chat and the console they are 20px at stroke 2 and 1.6.

**The Pill Means Chosen Rule.** A chip, a poster element or a format is a 12px rounded square until it is chosen. Then it becomes a pill with the accent fill and the `--hue` border. The change of corner animates over 200ms.

## Components

### Buttons
Every `button` starts from one zero-specificity reset (`:where(button)`), so one class overrides it.
- **Shape:** pill, 1.5px `--edge` border, transparent, `--text`, 700, 8px icon gap.
- **Default** (40px, padding 0 20px). Hover, only where a pointer hovers: `--active`.
- **Primary** (`button.primary`, `a.primary`, `.download-button`; 48px, 15px): `--signal`, `--signal-edge`, `--on-signal`. Hover: `--signal-hover`. Disabled: `--raised` fill and border, `--faint` label.
- **Secondary** (`button.secondary`, 48px, 15px): the default at main size. `.download-button.secondary` matches it.
- **Ghost** (`button.ghost`): no border, no fill, 500, padding 0 12px.
- **Icon** (`button.icon`): 44 × 44px.
- **Text** (`button.text-button`, 32px): `--muted`, 600, underlined. Hover: `--text`.
- **Send** (`.chat .send`): a 44px yellow circle with an up arrow in `--on-signal`. Disabled: `--control` at opacity .6.
- **Focus:** shops `outline: 2px solid var(--text); outline-offset: 2px`; console `outline: 2px solid var(--hue)`.
- **Press:** `scale(.97)` on `--press`. Full-width rows and switch rows take `--raised` instead.
- **Busy:** after 120ms a 14px spinner takes the place of the last icon. The control keeps its size and colours.
- **Touch:** with `pointer: coarse` every button is at least 44px; main and secondary buttons, download links and fields 52px.
- **Console:** 44px at every width, padding 0 18px, 1px `--edge`, 650; primary 1.5px `--signal-edge`, 750; hover `--active`, primary hover `color-mix(in srgb, var(--signal) 86%, var(--on-signal))`.

### Fields
- 48px (52px on touch), padding 10px 16px, 16px radius, 1.5px `--control` border, `--surface`, `--text` at 15px/550 (16px at 720 px and below). Focused: `--text` border.
- Label above, gap 6px, 13px/650 `--muted`. Placeholder `--muted` at 400.
- `.upload-zone`: `--surface`, 2px dashed `--control`. `.file-pick` shows a French pill with an `--edge` border over a transparent native input.
- **Switch** (`label.switch`): a 52 × 32 track. Off: `--raised` with a 2px `--muted` ring and knob. On: `--invert` with an `--invert-ink` knob. Grouped in a 20px `--surface` list with `--line` between rows.
- A form fills its card (the owner's rule): where its fields would be too wide, the card or the page's column is made narrower, never the form inside it. « Se déconnecter » is the last thing on Mon compte, outside every card.
- In the sign-in card each button takes the card's width, with 14px before the help line.
- Fields carry no error colour. A reason goes in a `.why` line (`--warn`), a block of issues, or an error toast.
- **Console:** 48px, padding 10px 14px, 1.5px `--control`, 16px corners, `--surface`; textarea 96px; the filter is a 44px pill at 16px with a search icon.

### Chips and choices
- **Chip** (`.chip`): 40px (44px on touch), 12px corners, `--edge`, `--surface`, `--muted` at 14px/650. Hover: `--raised`. Chosen: pill, `--accent-soft`, `--hue` border, `--accent-ink`. Poster elements and format radios behave the same way.
- **Segmented control** (`.seg`): a pill track, `--raised` with a 1px `--line` ring; segments 38px at 13px/600; the chosen one `--invert`.
- **Tabs and steps** (`.tabs`): a pill track, `--raised` with a 1.5px `--line` ring; the chosen tab `--surface`, 700, `--lift`. In the editor's tools at 1080 px and under: a 28px-corner `--surface` row of icons; the active icon in a 54 × 32 `--accent-soft` pill.
- **Style tile** (`.look`): `--surface`, 1px `--line`, 18px. Chosen: the selection ring and a 24px `--invert` disc with a tick.

### Badge
`.badge` names a state in words (D-REDESIGN-004): a pill, at least 24px, padding 0 10px, 12.5px/700, `nowrap`. Plain: `--raised` with `--muted`. `.ok`: `--ok-bg` / `--ok`. `.warn`: `--warn-bg` / `--warn`. `.bad`: `--bad-bg` / `--bad`. One dot, in `currentColor`: in the shops' app a 3px border on a zero box, so that forced colours keep it; in the console a 6px filled circle. Mes affiches and Accueil's recent posters put it on its own line between the title and the details: Brouillon (plain), À vérifier (`.warn`), Approuvée and Confirmée (`.ok`). The console's Shops table shows `suspended`, « no password » or `active`. The pill over the poster (`.frame .badge`) is a different look: `--surface`, `--lift`, `--text`, 28px.

### Cards and lists
- **Cards** (`.card`, `.group`, `.sign-in`, `.intake`, `.empty`, `.rows`): `--surface`, 1px `--line`. Editor rail `.card` 24px, padding 20px 22px (18px 16px on a phone). `.group` 20px, padding 18px 20px.
- **Dashboard cards** (Mon compte's forms and sections): `--surface`, `--line`, `--radius`, padding 20px.
- **Balance card** (`.balance-card`: Accueil's « Mes crédits » and the « Solde » of Mes crédits, one form for one fact): always the dark card, charcoal `#20201d` in the light theme (where everything inside reads the dark theme's roles again: the one place besides the two themes that writes the table's tokens, pinned by `tokens.test.ts`) and `--surface` in the dark one. Flat: `--line`, `--radius`, padding `clamp(20px, 3vw, 32px)`, no gradient. Its title is a 15px/650 `--muted` label. `.balance-figures`: each figure has its label above (13px/600 `--muted`) and its unit after (« crédit » or « crédits », `--muted`); the available credits lead at 36px/40px 700, the pending ones are second at 20px behind a `--line` divider. On Accueil the check time and « Voir mes crédits » share one line and « Créer une affiche » is under them, full width at 720 px and under, at the right above. On Mes crédits « Obtenir des crédits » is the card's second part under a hairline.
- **Poster list** (`.rows` > `.library-row` > `.library-item`): rows at least 96px, separated by `--line`. A 64 × 80 thumbnail with 4px corners (a poster is known by its look), the title (one line; two at 720 px and under), the badge, the details in `--faint`, a chevron. Hover: `--active`. Press: `--raised`. The row's second actions (`.row-actions`: « Dupliquer », « Retirer de la liste ») are underlined `--muted` words with no outline, at the right of the row, and under the text's edge at 720 px and under.
- **A list's title row** (`.gallery .titlerow`): the title and its sentence on the left, the action on the right; the filter (« Afficher les affiches retirées ») has its own line, directly on the list it filters.
- **Accueil's recent posters**: transparent rows on a bottom `--line`, a 48 × 60 thumbnail with 4px corners, the badge under the title, a drawn chevron at the end. « Mon compte » is a 56px row of its own under the list, between two hairlines, with the same chevron.
- **The way back** (`a.back`, Mes crédits and Mon compte): « Retour à l’accueil » before the title, on its own line, `--muted`, with a drawn chevron.
- **Styles** (`.look-wall`): square pictures at every width, two across on a phone.

### Navigation (shops)
- **Sidebar rows** (`.nav a`, `.sign-out`, `.theme-toggle`): 40px (44px on touch), padding 0 12px, 12px corners, `--muted` 600. Hover: `--active` and `--text`. Current (`aria-current`): `--active`, `--text`, 700. Counts: `--faint` 13px at the row's end.
- **Recent rows** (`.recent a`): at least 52px, a 32 × 40 thumbnail with 6px corners, the title (650, ellipsis), the state in `--faint`. The open poster's row is current.
- **Credit card** (`.credit-card`): 48px, `--surface`, 1px `--line`, 16px corners, 700.
- **Account row** (`.account`): 48px, a 36px `--invert` avatar with 12px corners, the shop's name.
- **Credits pill** (`.credits-pill`): 44px, 1.5px `--edge`, the balance; « Crédits » while unread; its accessible name is the full balance label.
- **Phone editor bar** (`.titlerow.bar`): replaces the top bar while a poster is open at 720 px and under. Sticky, 56px plus the safe area, `--glass-strong`: back, the name (16px/700), the save state (12.5px `--muted`), undo, redo.

### Chat
- **Frame** (`.chat`): a grid of the side panel, the thread and the composer, 680px, 15px/22px. Its height is set by `ChatView.vue` from the visible screen, minus `body`'s bottom padding (the frame's gap) and 12px; the page itself does not scroll (`main.chatting` has no bottom padding). From 880 px with a poster: 1080px, the thread and the composer on the left, a 340px side column on the right.
- **Empty conversation** (`.hello`): the D (56px, decorative), the question, the greeting, centred. Over 1180 px the welcome and the composer are centred as one group (`.chat.welcome`); under, the composer stays at the bottom.
- **Messages:** the owner's bubble (`.bubble.me`) on the right, at most `min(86%, 460px)`, 18px corners with a 6px bottom-right corner: `--invert` with `--invert-ink` in light, `--raised` with `--text` in dark. The assistant's (`.bubble.bot`) has no fill and no border: it speaks on the ground, the full width, with the D (28px, a painted `::before`) at its left. The wait line has a 16px spinner (`--control` track, `--hue` arc).
- **Recap** (`.recap`): the facts as cells of one `--surface` box split by 1px `--line` gaps, 16px corners; the price 800, 24px/30px. Under 480 px: two columns, the name and the price each on their own line.
- **Composer** (`form.composer`): `--surface`, a 1px `--control` border (`--text` while focused), 24px corners, the composer shadow, padding 8px 8px 8px 10px. Rows: the photo tray (68px images), the error lines, a borderless 16px/22px textarea (44 to 120px), and the tool row: the attach button (« Images » beside its icon over 720 px), the style pills (34px, `--edge`, `--surface`; chosen with a `--text` border) in a strip that scrolls sideways, and `.send` at the right. With the keyboard open on a phone the style row hides.
- **Side panel** (`.chat-side`): `--surface`, `--line`, 20px. A 60px poster thumbnail and « Modifications » folded behind a button; from 880 px the poster is full width and the list is open. Rows 44px; the current one is `--bubble`.

### Dialogs and sheets
- **Confirmation** (`.confirm-sheet` > `.confirm`): the sheet is fixed, `--scrim` and `blur(6px)`. The dialog is `min(100%, 440px)`, `--glass-strong`, 1px `--line`, 28px, padding 24px, `--lift`.
- **Conditions of use** (`.terms-sheet`): the same at 560px, from the top.
- **Review panel** (`.review-panel`): fixed, `--ambient` over `--ground`, 28px. On a phone it fills the screen and its decision bar is fixed at the bottom.
- **Credits dialog** (`dialog.credits-container`): `--ground`, `--line`, `--radius`, `--scrim` backdrop.
- **Console dialog**: `min(32rem, 100vw - 32px)`, `--glass-strong` with blur, 1px `--line`, 24px, `--lift`; backdrop rgb(21 19 15 / .55).

### Status blocks
- **Toast** (`.message`): fixed, centred on the content column, `--glass-strong` with blur, 1px `--line`, 24px, `--lift`, 700, an 8px dot (`--ok`, or `--bad` for an error). Errors at the bottom, notices under the top bar. At 1080 px and below an error rises 130px.
- **Caution:** `.demo-notice`, `.issues`, `.save-recovery`, `.polish-preview`, `.refusal` are `--warn-bg` with 16px corners, `--warn` text.
- **Done** (`p.done`): `--ok-bg` with `--ok`, 20px.
- **Version state** (`.state`): a 7px dot beside its word.
- **Wait block** (`.job-state.wait`): `--surface`, 20px, a 2px rail, three steps in 24px circles; the current step a 2px `--hue` ring.

### Progress marks
- **Loading line** (`.load-line`): fixed at the top of the content column, 3px; a 30% `--hue` segment travels.
- **Wait bar** (`.wait-rail`): a 2px `--line` track; a 30% `--hue` segment while the job runs.
- **Generation pill** (`.gen-pill`): a 28px `--surface` pill on the poster with a 7px `--hue` dot that pulses in size; the poster dims to .55.

### The Signal mark
- **Kit files** (`docs/project/brand/doka-studio-signal/`): masters, digital, web, fonts, `palette.json`, `USAGE.md`.
- **Shops' app, byte for byte:** `src/assets/doka-symbol-small.svg`, `doka-horizontal.svg`, `doka-horizontal-reverse.svg`; `public/favicon.svg`, `favicon.ico`, `icons/*.png`. `tests/brand.test.ts` pins their SHA-256.
- **Sidebar, drawer and signed-out screen:** the horizontal logo at 220px, the guide's screen minimum: the charcoal file in light, the reverse paper file in dark. The product's name is not typed beside it (R-SHOP-DASH-008 amended).
- **Rail:** the charcoal D on its yellow tile, 40px with 8px padding. **Top bar at 1180 px and under:** the same at 32px with 6px padding, in a 44px link.
- **Chat:** `favicon.svg` at 56px over the empty conversation and at 28px beside each assistant message.
- **Console, its own files:** `src/admin/doka-horizontal-charcoal.svg`, `doka-horizontal-paper.svg` (`.on-light`, `.on-dark`, shown by `data-theme` or by `prefers-color-scheme`) and `doka-symbol.svg` (the rail). `brand.test.ts` pins their digests. The build emits them under `/admin/assets/`.
- **Clear space and integrity** (USAGE.md): a quarter of the D's visible height around it; keep proportions, orientation and colours; charcoal on yellow, never white; paper or white files on a dark ground; do not retype the logo.

### Console (Overview and Shops)
- **Overview** (`Overview.vue`, the console's home): four figures in one card (Active shops, Credits outstanding, Received in the month, Provider spend with a 6px meter in `--text` on `--raised`). The 1px gaps over `--line` are the hairlines between them: one column, two by two from 600 px, four across over 1180 px. « Needs you » follows, the full width, its lines as 44px links on a hairline in as many columns as fit. Below: Shops (the first eight) and Service on the left, the month's payments in a 340px column on the right, over 1180 px.
- **Shops table:** rows 60px on a `--line` hairline; the first cell the identifier (a 44px link) and the name under it; numbers right-aligned and tabular from 600 px; under 600 px one `--surface` card per shop, each value with its column's name on the left and the value on the right edge.
- **Payments:** the period is one row that fills its card (two date fields sharing the width, then « Show » at their height; stacked under 600 px). The payments are a table with the shops table's styles (`.shops.payments`): When (and who wrote the line), Shop, Entry, Method, Reference (and the note), Credits, Amount; the shop and the amount in `--text` 650, the two numbers right-aligned. Under 600 px each payment is a block of labelled values between hairlines.
- **A page's action** (`.title-action`: « Refresh » on Overview and Service, « New shop » on Shops) sits on the title's line, at its right.
- **« New shop »** is a window: the native modal `dialog.new-shop` (the console's dialog surface, 32rem), opened by the sidebar's link (over the Shops list) and by the Shops page's button. Its first field is focused; « Cancel » and « Create the shop » are at its bottom right; Esc closes it and what was typed stays.
- **Forms** (`.stack`) fill their card. **One shop** (`main.single`) is a 600px column. Its head (`.shop-head`): the name (18px/650), the state as a badge with the live sessions after it, and at the right the two balances as figures (22px/700, label above, a `--line` divider), under them below 600 px.
- **Notices:** `.banner` a 16px-corner yellow band with charcoal 700. `.note` a 4px `--signal-edge` left border. `.kept` and `.shown` a 2px `--hue` border. `.refusal` `--bad` 700.

### Motion

| What moves | Property | Duration | Easing |
| --- | --- | --- | --- |
| Colour changes on controls, fields, rows, tabs, the switch track | `background-color`, `border-color`, `color`, `opacity` | 150ms | ease-out |
| Press (`--press`) | `transform: scale(.97)` | 160ms | `cubic-bezier(.23, 1, .32, 1)` |
| A chip or element becoming a pill | `border-radius` | 200ms | ease-out |
| The drawer (both interfaces) | `transform`, then `visibility` | 280ms | `cubic-bezier(.2, .8, .2, 1)` |
| The drawer's scrim (shops) | `opacity` | 200ms | ease-out |
| Switch knob | `inset`, `width`, `height` | 150ms | ease-out |
| Disclosure chevron | `transform` | 150ms | ease-out |
| Busy spinner | `rotate`, shown after 120ms | 700ms, infinite | linear |
| Loading line | `translateX(-100%)` → `translateX(435%)` | 1.2s, infinite | `cubic-bezier(.4, 0, .2, 1)` |
| Wait bar segment | same keyframes | 2.4s, infinite | linear |
| Generation dot | `scale` 1 → .6 → 1 | 1.6s, infinite | ease-in-out |
| Chat wait spinner | `rotate` | 800ms, infinite | linear |
| A new version appearing (`App.vue`) | `opacity` 0 → 1 | 200ms | ease-out |

Transitions name their property, never `all`. The generation dot pulses in size, not opacity, because a fainter dot fell under 3:1.

**`prefers-reduced-motion: reduce`** sets `scroll-behavior: auto` and `transition: none` on every element (the drawer included; the console removes its drawer transition itself), stops the generation dot, draws the wait bar and the loading line still at full width, replaces the press scale with a `--raised` background (or a 3px `--hue` ring on the yellow and picture controls), slows the chat and photo spinners to 2.4s, and makes the glass solid with no blur.

## Do's and Don'ts

### Do:
- **Do** make the main action charcoal on Signal Yellow with its `--signal-edge`, and `--signal-hover` under a hovering pointer.
- **Do** keep resting surfaces `--surface` with a 1px `--line`, and keep glass and `--lift` for what floats.
- **Do** use `--glass-strong` for every floating surface that carries text; it is the one glass that keeps 4.5:1 over black and white.
- **Do** use `--hue` for every ring, chosen border and progress mark.
- **Do** keep text at 4.5:1 (3:1 from 24px, or 18.66px bold), placeholders at 4.5:1, accent lines and field boundaries at 3:1, measured in both themes.
- **Do** paint a blur on the fixed or sticky element itself or on its `::before`.
- **Do** split every width condition into complementary halves (`>` and `<=`).
- **Do** make what is not shown `hidden` or `inert`.
- **Do** mark a choice by shape as well as colour, and a state by a word as well as a dot.
- **Do** keep targets at 44px on touch screens (at every width in the console), and main buttons and fields at 52px on touch.
- **Do** give the five frame screens `--page` (860px) and `.page-title`.
- **Do** put hover looks inside `@media (hover: hover)`.
- **Do** use the kit's files byte for byte: charcoal on light grounds, paper on dark ones.

### Don't:
- **Don't** put white on yellow, or use Signal Yellow as a line or as text on a light ground.
- **Don't** change a main action's opacity on hover.
- **Don't** blur or shadow a card, a list, a field or a chip.
- **Don't** put a `backdrop-filter`, `filter`, `transform` or containment on an ancestor of a fixed element.
- **Don't** wrap the top bar and `main` in a scrolling box; the window scrolls.
- **Don't** add the Doka logo or any Doka identity to a shop's poster, and don't let a page token reach the poster canvas.
- **Don't** fetch a font from another site.
- **Don't** let the console import or request anything of the shops' app.
- **Don't** blur a copy of the poster as a backdrop.
- **Don't** fade a progress mark with opacity; it falls under 3:1.
- **Don't** transition `all`.
