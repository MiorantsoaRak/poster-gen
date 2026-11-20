---
name: Doka Studio
description: "Vos produits au premier plan."
colors:
  # The Signal kit (docs/project/brand/doka-studio-signal/palette.json). In the shops' app --signal is signal-yellow
  # and --on-signal is charcoal, in both themes.
  signal-yellow: "#f2c744"
  charcoal: "#20201d"
  warm-paper: "#f5f1e8"
  # Hard-coded behind an owner's original photo and behind the poster canvas (style.css: #fff).
  photo-mat: "#ffffff"
  # Shops' app, light theme: :root[data-theme=clair] in frontend/src/style.css
  light-ground: "#f5f1e8"
  light-surface: "#ffffff"
  light-raised: "#ebe5dc"
  light-line: "#e2dacf"
  light-control: "#c9c0b4"
  light-text: "#20201d"
  light-muted: "#5c554d"
  light-faint: "#67605a"
  light-hue: "#8f6b00"
  light-accent-soft: "#fcf1d0"
  light-accent-ink: "#7a5c00"
  light-ok: "#145c37"
  light-ok-bg: "#e2f2e8"
  light-warn: "#6b4600"
  light-warn-bg: "#fff1d6"
  light-bad: "#a3271f"
  light-bad-bg: "#fbeae8"
  light-invert: "#20201d"
  light-invert-ink: "#ffffff"
  light-scrim: "#15130f99"
  light-glass: "rgb(255 255 255 / .86)"
  light-glass-panel: "rgb(255 255 255 / .74)"
  light-glass-field: "rgb(255 255 255 / .62)"
  light-glass-strong: "rgb(255 255 255 / .92)"
  light-glass-line: "rgb(255 255 255 / .75)"
  light-glass-hi: "rgb(255 255 255 / .96)"
  light-warn-glass: "rgb(255 241 214 / .8)"
  light-bubble: "#e4dfd7"
  light-patch-1: "#f7f5f1"
  light-patch-2: "#f2efe9"
  light-patch-3: "#eae6df"
  # Shops' app, dark theme: :root in frontend/src/style.css
  dark-ground: "#100f0e"
  dark-surface: "#1b1a18"
  dark-raised: "#2a2825"
  dark-line: "#302d2a"
  dark-control: "#57524c"
  dark-text: "#f5f1e8"
  dark-muted: "#bdb6ad"
  dark-faint: "#a39b91"
  dark-hue: "#f2c744"
  dark-accent-soft: "#3b3113"
  dark-accent-ink: "#f8d97a"
  dark-ok: "#8fddb0"
  dark-ok-bg: "#16261d"
  dark-warn: "#e9b458"
  dark-warn-bg: "#2a2212"
  dark-bad: "#ef7d74"
  dark-bad-bg: "#331a18"
  dark-invert: "#f5f1e8"
  dark-invert-ink: "#100f0e"
  dark-scrim: "#000000cc"
  dark-glass: "rgb(27 26 24 / .86)"
  dark-glass-panel: "rgb(30 28 26 / .58)"
  dark-glass-field: "rgb(255 255 255 / .07)"
  dark-glass-strong: "rgb(70 66 62 / .7)"
  dark-glass-line: "rgb(255 255 255 / .1)"
  dark-glass-hi: "rgb(74 70 65 / .72)"
  dark-warn-glass: "rgb(42 34 18 / .8)"
  dark-bubble: "#34312d"
  dark-patch-1: "#191816"
  dark-patch-2: "#121110"
  dark-patch-3: "#0d0c0b"
  # Operator's page: frontend/src/admin/admin.css (ground and text are warm-paper / charcoal, swapped in dark)
  operator-light-surface: "#fffdf8"
  operator-light-muted: "#57534a"
  operator-light-line: "#cfc7b6"
  operator-light-bad: "#a3271f"
  operator-dark-surface: "#2b2b27"
  operator-dark-muted: "#c9c3b6"
  operator-dark-line: "#55534c"
  operator-dark-bad: "#ff9a8f"
  operator-backdrop: "rgb(0 0 0 / .55)"
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
  figure:
    fontFamily: "Figtree, system-ui, sans-serif"
    fontSize: "2rem"
    fontWeight: 700
    lineHeight: 1.2
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
  nav-label-phone:
    fontFamily: "Figtree, system-ui, sans-serif"
    fontSize: "12.5px"
    fontWeight: 650
    lineHeight: "16px"
  operator-body:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.5
  operator-heading-1:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "24px"
    lineHeight: "32px"
  operator-heading-2:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "18px"
    lineHeight: "24px"
rounded:
  text-button: "4px"
  poster: "5px"
  operator: "8px"
  thumb: "10px"
  version-mark: "9px"
  chip: "12px"
  chat-poster: "14px"
  operator-dialog: "12px"
  field: "16px"
  tile: "18px"
  group: "20px"
  composer: "22px"
  card: "24px"
  dialog: "28px"
  pill: "999px"
spacing:
  gutter: "20px"
  gutter-phone-frame: "16px"
  gutter-phone: "12px"
  stack-gap: "14px"
  page: "860px"
  main-max: "1480px"
  operator-page: "960px"
components:
  # Values resolve to the light theme; in the dark theme read each light- key as its dark- twin.
  button-primary:
    backgroundColor: "{colors.light-invert}"
    textColor: "{colors.light-invert-ink}"
    typography: "{typography.button-main}"
    rounded: "{rounded.pill}"
    padding: "0 20px"
    height: "48px"
  button-primary-disabled:
    backgroundColor: "{colors.light-raised}"
    textColor: "{colors.light-faint}"
  button-secondary:
    backgroundColor: "{colors.light-glass-field}"
    textColor: "{colors.light-text}"
    typography: "{typography.button-main}"
    rounded: "{rounded.pill}"
    padding: "0 20px"
    height: "48px"
  button-default:
    backgroundColor: "{colors.light-glass-field}"
    textColor: "{colors.light-text}"
    typography: "{typography.button}"
    rounded: "{rounded.pill}"
    padding: "0 20px"
    height: "40px"
  button-default-hover:
    backgroundColor: "{colors.light-raised}"
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
    backgroundColor: "{colors.light-glass-field}"
    textColor: "{colors.light-text}"
    typography: "{typography.field}"
    rounded: "{rounded.field}"
    padding: "10px 16px"
    height: "48px"
  chip:
    backgroundColor: "{colors.light-glass-field}"
    textColor: "{colors.light-muted}"
    rounded: "{rounded.chip}"
    padding: "0 15px"
    height: "40px"
  chip-selected:
    backgroundColor: "{colors.light-accent-soft}"
    textColor: "{colors.light-accent-ink}"
    rounded: "{rounded.pill}"
  segment-selected:
    backgroundColor: "{colors.light-invert}"
    textColor: "{colors.light-invert-ink}"
    rounded: "{rounded.pill}"
    height: "38px"
  nav-link:
    textColor: "{colors.light-muted}"
    rounded: "{rounded.pill}"
    padding: "0 14px"
    height: "40px"
  nav-link-current:
    backgroundColor: "{colors.light-glass-field}"
    textColor: "{colors.light-text}"
  nav-item-phone:
    textColor: "{colors.light-muted}"
    typography: "{typography.nav-label-phone}"
    rounded: "{rounded.field}"
    padding: "0 4px"
    height: "58px"
  nav-icon-phone-current:
    backgroundColor: "{colors.light-accent-soft}"
    textColor: "{colors.light-accent-ink}"
    rounded: "{rounded.pill}"
    width: "58px"
    height: "32px"
  card-glass:
    backgroundColor: "{colors.light-glass-panel}"
    rounded: "{rounded.card}"
    padding: "20px 22px"
  card-solid:
    backgroundColor: "{colors.light-surface}"
    rounded: "{rounded.card}"
  dialog-confirm:
    backgroundColor: "{colors.light-glass}"
    rounded: "{rounded.dialog}"
    padding: "24px"
    width: "440px"
  toast:
    backgroundColor: "{colors.light-glass}"
    textColor: "{colors.light-text}"
    rounded: "{rounded.card}"
    padding: "10px 10px 10px 18px"
  bubble-owner:
    backgroundColor: "{colors.light-bubble}"
    textColor: "{colors.light-text}"
    typography: "{typography.body-chat}"
    rounded: "{rounded.tile}"
    padding: "10px 14px"
  operator-button:
    backgroundColor: "{colors.operator-light-surface}"
    textColor: "{colors.charcoal}"
    rounded: "{rounded.operator}"
    padding: "0 16px"
    height: "44px"
  operator-button-primary:
    backgroundColor: "{colors.signal-yellow}"
    textColor: "{colors.charcoal}"
  operator-field:
    backgroundColor: "{colors.operator-light-surface}"
    textColor: "{colors.charcoal}"
    rounded: "{rounded.operator}"
    padding: "8px 12px"
    height: "44px"
---

# Design System: Doka Studio

As built on 2026-11-20 at the end of the interface polish (T-POLISH-001 to 005, ADR-122), on the local stub build. The proof is in docs/project/reviews/design-after-2026-11-20.md; the screens are captured again with `uv run python ../frontend/tests/design_capture.py <label>` from `backend/`.

## Overview

**Creative North Star: "The poster is the one lifted thing"** (the words of `style.css`'s header and of its `.stage` rule).

Doka Studio has two interfaces. **The shops' app** (`frontend/index.html`, `frontend/src/style.css` and the scoped styles of `ShopHome.vue`, `ShopCredits.vue`, `ShopAccount.vue`) is a French, phone-first workspace for an owner on an Android phone in Chrome. It has a light theme (« clair », a warm paper ground) and a dark one (« sombre », a warm near-black ground). The theme follows the device until the owner picks one; the pick is stored under `affiche.theme` and applied by an inline script before the first paint. Every surface is frosted glass over a fixed, nearly flat neutral backdrop. Type is Figtree. The main button is ink (charcoal in light, paper in dark), and Signal Yellow is the one accent.

**The operator's page** (`frontend/admin/index.html`, `frontend/src/admin/admin.css`) is for one operator. It is flat: system font, the kit's exact paper, charcoal and yellow, both themes from the device only, 2 px borders, no glass, no shadows, no transitions. It imports nothing from the shops' app and requests nothing from it (D-ADMIN-005; `admin.test.ts` and `admin_browser.py` assert this). Both interfaces share the name « Doka Studio », the Signal D mark and the three kit colours. A third page, « Vos données » (`frontend/public/donnees.html`), is static. It has its own copy of five of the app's tokens, Figtree, solid sections and the device's theme.

The shop's poster is outside this system. The canvas draws it with the poster's own fonts and colours, and no page token reaches it. D-POLISH-002 has a test for this: the same `toDataURL()` in both themes. The poster never carries the Doka identity.

**Key Characteristics:**
- Two themes of equal standing in the shops' app; the operator's page and « Vos données » follow `prefers-color-scheme` only.
- Glass on every surface (ADR-077) over a neutral backdrop (ADR-091), with a solid fallback.
- An ink main button; Signal Yellow only as a fill under charcoal; a separate line colour for rings and progress marks.
- Pills for actions and chosen states; rounded squares for choices not yet made.
- Contrast measured on the rendered screens, over the darkest and the lightest point of the real backdrop.
- 44 px touch targets, 52 px main buttons and fields on touch screens.

## Colors

Warm paper and charcoal carry the page; Signal Yellow marks an action or a state; red, green and amber carry state only.

### Primary
- **Signal Yellow** (`--signal`, #f2c744, the same in both themes): a **fill** only, and always with **Charcoal** (`--on-signal`, #20201d) on it. In the shops' app it fills two things: the tile behind the header's D (`.signal-symbol`) and the chat's send button (`.chat .send`). On the operator's page it fills the primary button and the banner. It is also used there as a line: the 2px border of `.shown` and `.kept`, the 4px left border of `.note`, and the focus ring in the dark theme.
- **Signal line** (`--hue`): every ring, border and progress mark that has to read against the page: the border of a chosen chip, format or poster element, the loading line, the moving part of the wait bar, the current step's ring, the generation dot, the chat spinner's arc, and the press ring under reduced motion. It is a **dark ochre** (#8f6b00) in the light theme and the **yellow** (#f2c744) in the dark one. A yellow line on paper is 1.4:1. The ochre is 3.9:1 on `--raised`, 4.4:1 on `--ground` and 4.9:1 on `--surface` (`style.css` comment).
- **Accent soft / accent ink** (`--accent-soft`, `--accent-ink`): the pale fill of a chosen chip, poster element or format, of the active tool icon, of the phone bar's current icon and of the chat's « inspiration » role, with its ink on top. Light: #fcf1d0 / #7a5c00; dark: #3b3113 / #f8d97a.

### Neutral
- **Warm Paper** (#f5f1e8): the light `--ground`, the dark `--text` and `--invert`, and the operator's light ground and dark text.
- **Charcoal** (#20201d): the light `--text` and `--invert`, `--on-signal`, and the operator's light text and dark ground.
- **Near-black** (#100f0e): the shops' dark `--ground` and `--invert-ink`. This is not the kit's Charcoal (owner decision 3 of interface-polish).
- **White** (#ffffff): the light `--surface` and `--invert-ink`, and the hard-coded mat behind an owner's photo and the poster canvas (`.photo-strip img`, `.proof .photo img`, `.comparison figure:first-child img`, `.poster-canvas`). The chat's poster frame is hard-coded #14110e.

### Shops' app: light theme (`:root[data-theme=clair]`)

`--signal` and `--on-signal`, `--radius` (24px), `--field` (16px), the blurs, `--press` and `--ambient` are defined once in `:root` and hold in both themes.

| Token | Key | Value | Role |
| --- | --- | --- | --- |
| `--ground` | light-ground | #f5f1e8 | Page ground (`html`), the review panel's and credits dialog's ground, the sticky step row on a phone |
| `--surface` | light-surface | #ffffff | Solid cards of Accueil, Mes crédits, Mon compte; the solid-glass fallback; swatch and spinner gaps |
| `--raised` | light-raised | #ebe5dc | Hover and press fill of buttons and rows, disabled main button, switch track when off |
| `--line` | light-line | #e2dacf | 1 to 1.5 px borders of controls, separators of lists, the wait bar's track |
| `--control` | light-control | #c9c0b4 | Field border on hover, dashed drop zones, swatch ring, spinner track, disabled send button |
| `--text` | light-text | #20201d | Text, focus ring, focused field border, chosen-swatch and chosen-style ring |
| `--muted` | light-muted | #5c554d | Secondary text, labels, placeholders, unchosen chips, tabs and links, the off switch's ring and knob |
| `--faint` | light-faint | #67605a | Help and small text, meta lines, disabled control text, chevrons, the « Ar » unit |
| `--hue` | light-hue | #8f6b00 | The line accent (see Primary) |
| `--accent-soft` | light-accent-soft | #fcf1d0 | Fill of a chosen chip, element, format, tool, phone-bar icon |
| `--accent-ink` | light-accent-ink | #7a5c00 | Text and icon on `--accent-soft`; current step's number |
| `--ok` / `--ok-bg` | light-ok / light-ok-bg | #145c37 / #e2f2e8 | Success: notice dot, approved state, « done » banner, finished step |
| `--warn` / `--warn-bg` | light-warn / light-warn-bg | #6b4600 / #fff1d6 | Caution: `.why` reasons, demo notice, recovery and issue blocks, draft state dot, offline note, demo badge |
| `--bad` / `--bad-bg` | light-bad / light-bad-bg | #a3271f / #fbeae8 | Failure: error toast dot, rejected state dot, blocking issue link. `--bad-bg` is defined but no rule uses it |
| `--invert` / `--invert-ink` | light-invert / light-invert-ink | #20201d / #ffffff | The main button, the download link, the chosen segment, a switch when on, « Retirer de l'affiche », the chosen style's tick, the chat's remove-photo button |
| `--scrim` | light-scrim | #15130f99 | Behind dialogs and the review panel |
| `--glass` | light-glass | rgb(255 255 255 / .86) | Bars and sheets over content |
| `--glass-panel` | light-glass-panel | rgb(255 255 255 / .74) | Panels and tiles |
| `--glass-field` | light-glass-field | rgb(255 255 255 / .62) | Fields, chips, default and secondary buttons, tab tracks |
| `--glass-strong` | light-glass-strong | rgb(255 255 255 / .92) | A chosen tab or segment, the French file-pick button |
| `--glass-line` | light-glass-line | rgb(255 255 255 / .75) | The edge of a glass bar, toast, dialog, chat surface |
| `--glass-hi` | light-glass-hi | rgb(255 255 255 / .96) | The sheen at one corner of the chat's surfaces |
| `--warn-glass` | light-warn-glass | rgb(255 241 214 / .8) | Glass caution blocks |
| `--bubble` | light-bubble | #e4dfd7 | The owner's chat bubble; the current modification row |
| `--patch-1…3` | light-patch-1…3 | #f7f5f1, #f2efe9, #eae6df | Backdrop gradient stops |

### Shops' app: dark theme (`:root`)

| Token | Key | Value | Role |
| --- | --- | --- | --- |
| `--ground` | dark-ground | #100f0e | As light |
| `--surface` | dark-surface | #1b1a18 | As light |
| `--raised` | dark-raised | #2a2825 | As light |
| `--line` | dark-line | #302d2a | As light |
| `--control` | dark-control | #57524c | As light |
| `--text` | dark-text | #f5f1e8 | As light |
| `--muted` | dark-muted | #bdb6ad | As light; it is also the placeholder colour, because `--faint` is 4.19:1 on a dark field over `--raised` |
| `--faint` | dark-faint | #a39b91 | As light |
| `--hue` | dark-hue | #f2c744 | The line accent, the yellow itself |
| `--accent-soft` | dark-accent-soft | #3b3113 | As light |
| `--accent-ink` | dark-accent-ink | #f8d97a | As light |
| `--ok` / `--ok-bg` | dark-ok / dark-ok-bg | #8fddb0 / #16261d | As light |
| `--warn` / `--warn-bg` | dark-warn / dark-warn-bg | #e9b458 / #2a2212 | As light |
| `--bad` / `--bad-bg` | dark-bad / dark-bad-bg | #ef7d74 / #331a18 | As light. On a dark bubble `--bad` is 4.29:1, so the word « Refusée » in the chat keeps `--text` |
| `--invert` / `--invert-ink` | dark-invert / dark-invert-ink | #f5f1e8 / #100f0e | As light |
| `--scrim` | dark-scrim | #000000cc | As light |
| `--glass` | dark-glass | rgb(27 26 24 / .86) | As light |
| `--glass-panel` | dark-glass-panel | rgb(30 28 26 / .58) | As light |
| `--glass-field` | dark-glass-field | rgb(255 255 255 / .07) | As light |
| `--glass-strong` | dark-glass-strong | rgb(70 66 62 / .7) | As light |
| `--glass-line` | dark-glass-line | rgb(255 255 255 / .1) | As light |
| `--glass-hi` | dark-glass-hi | rgb(74 70 65 / .72) | As light |
| `--warn-glass` | dark-warn-glass | rgb(42 34 18 / .8) | As light |
| `--bubble` | dark-bubble | #34312d | As light |
| `--patch-1…3` | dark-patch-1…3 | #191816, #121110, #0d0c0b | As light |

### Operator's page (`admin.css`)

| Token | Light | Dark (`prefers-color-scheme: dark`) | Role |
| --- | --- | --- | --- |
| `--paper`, `--charcoal`, `--signal` | #f5f1e8, #20201d, #f2c744 | same | The kit's three colours |
| `--ground` | warm-paper | charcoal | Page ground |
| `--surface` | #fffdf8 | #2b2b27 | Buttons, fields, cards, dialogs |
| `--text` | charcoal | warm-paper | Text |
| `--muted` | #57534a | #c9c3b6 | Secondary text, table headers, and the 2 px border of buttons and fields |
| `--line` | #cfc7b6 | #55534c | Separators, the top bar's rule, the phone cards' border |
| `--bad` | #a3271f | #ff9a8f | A refusal (`.refusal`, bold) |
| `--focus` | charcoal | signal-yellow | The 3 px focus outline |
| dialog backdrop | rgb(0 0 0 / .55) | same | `dialog::backdrop` |

### Contrast

The smokes test these rules on rendered screens, in both themes, over the darkest and the lightest point of the real backdrop (the ground, each patch, glass and its `saturate()` folded in). The tests are `check_contrast` and `check_marks` in `frontend/tests/browser_smoke.py`, which `shop_dashboard_browser.py` and `chat_browser.py` also call.
- **Text:** 4.5:1; 3:1 from 24 px, or from 18.66 px at weight 700 or more (WCAG AA). Disabled controls and text over an image are not measured.
- **Placeholders:** 4.5:1 at any size, colour and opacity together, and lower than the typed value's ratio.
- **Accent lines (`check_marks`):** 3:1 against what is behind them. This covers the loading line, the border of a chosen chip, format or element, the generation dot at the smallest point of its pulse, the current step's ring and the chat spinner. The wait bar's moving part must reach 3:1 in light and at least 6.57:1 in dark. The send button's glyph must reach 4.5:1 on its yellow.
- **Not measured:** the `--line` borders of fields and buttons. The comment on the switch rule says the switch's off track is outlined in `--muted` for 3:1.
- **Kit pairs** (USAGE.md): charcoal on paper 14.49:1, charcoal on yellow 10.13:1, paper on charcoal 14.49:1.

**The Fill-and-Line Rule.** In the shops' app, `--signal` is a fill and nothing else, and its content is always `--on-signal`. A shape that holds a glyph or a label is a fill. Anything that must be seen against the page is a line, and a line uses `--hue` (D-POLISH-002).

**The Ink Button Rule.** The shops' main action is `--invert`: charcoal with white ink in light, paper with near-black ink in dark. It is not yellow (owner decision 2 of interface-polish).

**The Mark-and-Place Rule.** A state colour is a dot, a ground or a word's colour, and it always comes with words. A toast's kind is its dot and its place (errors at the bottom, notices at the top), never its text colour.

## Typography

**Body and display font (shops' app):** Figtree, with `system-ui, sans-serif` as fallback. It ships as one variable file, `frontend/public/fonts/Figtree-Variable.woff2` (weights 300 to 900, `font-display: swap`, preloaded by `index.html`, with `Figtree-OFL.txt`). Nothing is fetched from another site.
**Operator's page:** `system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif`; code in `ui-monospace, monospace`.
**« Vos données »:** Figtree, `15px/22px`.

**Character:** a single humanist sans for everything. The weight carries the hierarchy (400 to 800). Size changes little.

**Why Figtree, not the kit's fonts.** The Signal guide names Space Grotesk Bold for large titles and Noto Sans Regular/Bold for text and controls. For an interface without those fonts loaded, it accepts a system sans as a fallback. The app does not load Space Grotesk or Noto Sans for its text. Figtree was chosen with the approved mockup (ADR-077). The owner did not answer the typeface question in the polish, so the lead's recommendation stands (ADR-122; owner decision 1). He may overturn it. Space Grotesk survives only as outlines inside the logo files.

**The narrow no-break space.** Figtree has no U+202F, the French thousands separator in « 90 000 ». A second `@font-face` named Figtree maps `NotoSans-Regular.ttf` to `unicode-range: U+202F` only, so a price has the same spacing on every phone. The other font files in `public/fonts/` (Noto Sans Bold, Noto Serif, Montserrat Black Italic, and the same Noto Sans Regular as « Affiche Noto Sans ») are the poster's, listed in `font-manifest.json`.

### Hierarchy (shops' app)
- **Page title** (800, 26px, 32px): `.page-title`, the `h1` of Accueil, Mes affiches, Styles, Mes crédits and Mon compte. It takes the focus on arrival for a screen reader and shows no box; a 2px underline 6px under it appears only after a key was pressed (`:root[data-keys]`, set in `main.ts` on `keydown` and cleared on `pointerdown`): until the first tap a browser counts a script's focus as the keyboard's, and the title of every page opened would be underlined. The sign-in and intake titles use the same size (`.sign-in h1, .intake h1`).
- **Heading 1** (800, 22px, 28px, -0.01em, `text-wrap: balance`): every other `h1`. In the phone editor's bar (`.bar h1`) the title is 16px/22px at 700.
- **Heading 2** (800, 18px, 24px, -0.01em): `h2`. A review section's heading is 21px/27px. The versions column heading is 13px/700 in `--muted`.
- **Heading 3** (700, 14px): `h3`, with an icon gap of 8px.
- **Figures** (700): Accueil's counts at 2rem/1.2 and the credit figures at 1.8rem/1.3. `:root` sets 14px, so 1rem is 14px here. Also the chat recap price (800, 24px/30px) and the wait block's title (800, 16px/22px).
- **Body** (400, 14px, 20px): the `:root` default. The chat is 15px/22px. Intro text is limited to 52ch and a review lede to 62ch.
- **Field** (550, 15px): typed values. At 720px wide and below, fields are 16px, because iOS zooms the page on a field under 16px.
- **Button** (700, 14px, line-height 1.2). Main and secondary buttons are 15px. The phone bottom bars use 15.5px.
- **Label** (650, 13px, `--muted`): a field's label, a choice's heading, chips at 14px.
- **Help** (400, 13px, 19px, `--faint`): `small`, `.help`, `.meta` (500).
- **Phone bar label** (650, 12.5px, 16px). The tool tabs use the same size.

### Hierarchy (operator's page)
- **Heading 1** (24px/32px), **Heading 2** (18px/24px), **Body** (16px/1.5), **Small** (14px, `--muted`). Labels, buttons and summaries are 700. The brand line is 800.

**The One Family Rule.** The shops' interface uses Figtree for every word. The poster keeps its own fonts. Never load a second interface family or fetch a font from another origin.

**The Tabular Rule.** `:root` sets `font-variant-numeric: tabular-nums` and `font-synthesis: none`, so every figure in the shops' app is tabular. The operator's page applies tabular figures only to the Shops table's numeric columns from 600px (`.shops .num`, right-aligned).

## Layout

**The frame.** `main` is centred, at most 1480px wide. Its gutters are `--gutter-l` and `--gutter-r`: 20px on wider screens, or the safe area if larger. At 720px and below the gutter is 12px for the chat and the editor, whose sticky bars use it in their negative margins. It is 16px for the five frame screens (`main:has(> :is(.shop-home, .shop-account, .gallery, div.credits-container))`). The bottom padding is 64px (56px at 720px and below), or 88px plus the safe area above the phone bar.

**The One Frame Rule.** Accueil, Mes affiches, Styles, Mes crédits and Mon compte share one content width, `--page: 860px`, and one title, `.page-title` (D-POLISH-003). As a panel inside the creator, Mes crédits keeps its dialog's 680px.

**Other widths:** sign-in 420px; new-poster intake 640px; chat 680px, or 1080px with a 340px poster column from 880px wide (24px column gap); confirmation 440px; conditions of use 560px; credits dialog `min(680px, 100% - 24px)`; review panel `inset: 3vh max(3vw, calc(50vw - 580px))`; toast `max-width: min(94vw, 680px)`; « Vos données » 680px; operator page 960px with 16px side padding.

**The editor.** At more than 1080px wide it is three columns: a 360px rail, the stage, and a 156px versions column, with a 14px gap. The stage is sticky 64px from the top. At 1080px and below it is one column (a flex column, so that the poster can stick). The main action becomes a fixed glass bar at the bottom of the screen, and 150px is reserved below the content.

**Rhythm.** There is no spacing token scale. Gaps run 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24 and 28px. 14px is the most frequent: the gap between stacked blocks, a field's bottom margin, the wall and grid gaps. Card padding runs from 18 to 28px.

**Breakpoints:**

| Query | What changes |
| --- | --- |
| `min-width: 1440px` | The header shows the kit's horizontal logo at 220px in place of the D and the typed name |
| `max-width: 1080px` | Editor in one column; the main action is a fixed bottom bar; large view of the poster; tools as an icon row |
| `min-width: 880px` | Chat with a poster: two columns |
| `max-width: 720px` | Phone: bottom navigation bar, compact header, 12/16px gutters, 16px fields, editor's own top bar, full-screen review panel |
| `max-width: 420px` | Header with the « Message / Pas à pas » switch packs tighter |
| `min-width: 600px` / `max-width: 599px` (operator) | Shops table with right-aligned numbers, or one card per shop |
| `hover: hover` | Hover looks exist only here (on touch screens they stick to the next control) |
| `pointer: coarse` | 44px minimum targets; 52px main buttons and fields |
| `forced-colors: active` | The switch goes back to a native checkbox |
| `prefers-reduced-transparency` / `prefers-reduced-motion` | Solid glass, no blur (see Elevation) |

**Safe areas.** `viewport-fit=cover` and `interactive-widget=resizes-content` are set in the viewport meta. Every fixed or sticky bar pads with `max(…, env(safe-area-inset-*))`. `scroll-padding` is 64px at the top and 80px at the bottom (150px at the bottom at 1080px and below).

## Elevation & Depth

The system is a hybrid. Depth comes from translucent glass layered over a fixed backdrop, plus a small vocabulary of soft shadows. The backdrop is `html::before`, fixed, with `--ambient: linear-gradient(155deg, var(--patch-1), var(--patch-2) 50%, var(--patch-3))`. It is neutral and almost flat (ADR-091), never a blurred copy of the poster (ADR-077). `body` stays transparent. The operator's page and « Vos données » are flat: solid surfaces, borders, no shadows.

### Glass by surface

| Token | Blur | Used on |
| --- | --- | --- |
| `--glass` | `--blur-panel`: blur(26px) saturate(1.5) | Header, phone navigation bar, editor top bar, fixed bottom action bars, step navigation, toasts, confirmation dialogs, large poster view; with `--blur-field` for the badge and generation pill over the poster |
| `--glass-panel` | `--blur-panel` | Sign-in, intake, empty states, poster list, style tiles and cards, editor rail, review groups, comparison figures, final shot, facts, job state, switch groups, tool row |
| `--glass-field` | `--blur-field`: blur(16px) saturate(1.4) | Fields, default and secondary buttons, chips, upload zone, tab tracks, segmented controls, current desktop nav link |
| `--glass-strong` | none of its own | A chosen tab or segment, the file-pick button |
| `--glass-hi` → `--glass-panel` | `--blur-panel` | The chat's bot bubbles, composer and poster side, as `linear-gradient(140deg, var(--glass-hi), var(--glass-panel) 60%)` |
| `--warn-glass` | `--blur-field` | Demo notice, issues, save recovery, polish preview, refusal |

### Shadow Vocabulary
- **Glass edge** (`--glass-shadow`; light `inset 0 1px 0 rgb(255 255 255 / .7), 0 12px 32px -14px rgb(40 28 14 / .3)`; dark `inset 0 1px 0 rgb(255 255 255 / .07), 0 12px 32px -14px rgb(0 0 0 / .65)`): every glass panel, the chat surfaces and the confirmation dialog.
- **Lift** (`--lift`; light `0 1px 2px rgb(40 28 14 / .06), 0 10px 28px -10px rgb(40 28 14 / .18)`; dark `0 1px 2px rgb(0 0 0 / .5), 0 10px 28px -10px rgb(0 0 0 / .7)`): what floats over content. That is a toast, the chosen tab or review segment, the badge and generation pill over the poster, and « Retirer de l'affiche ».
- **Poster shadow** (`--poster-shadow`; light `0 1px 2px rgb(40 28 14 / .08), 0 6px 16px -6px rgb(40 28 14 / .16)`; dark `0 8px 20px -8px rgb(0 0 0 / .6)`): the poster canvas, version thumbnails, the final check's image.
- **Message shadow** (`--msg-shadow`; light `inset 0 1px 0 rgb(255 255 255 / .7), 0 4px 18px -10px rgb(40 28 14 / .12)`; dark `inset 0 1px 0 rgb(255 255 255 / .07), 0 4px 18px -10px rgb(0 0 0 / .3)`): a bot bubble.
- **Selection ring** (`0 0 0 2px var(--ground), 0 0 0 5px var(--text)`): a chosen style tile. It is a shadow so that the focus outline still shows outside it (focus offset 6px).
- **Scrim**: `.confirm-sheet` lays `--scrim` with `blur(6px)` behind its dialog. The review panel casts `0 0 0 100vmax var(--scrim)`.

### Stacking order
Header 5 · editor top bar 6 · bottom action bar and phone navigation 20 · large poster view 25 · review panel 30 · toasts 40 · conditions of use 45 · confirmation 50 · skip link 60 · loading line 70.

**The One Lifted Thing Rule.** The stage has no surface of its own. The poster sits directly on the backdrop and is the one lifted object on the screen. `--lift` is only for things that float over content.

**The Blur Once Rule.** A control or tile on a surface that already blurs keeps its translucent fill but gets no blur of its own (the selector list at the end of `style.css`). A blurred element becomes the containing block of its fixed descendants. So the header on a phone and the editor rail carry their blur on a `::before` layer, and their fixed bars still sit on the screen.

**The Solid Fallback Rule.** Where `backdrop-filter` is unsupported, or under `prefers-reduced-transparency: reduce` or `prefers-reduced-motion: reduce`, the glass tokens become opaque. `--glass`, `--glass-panel`, `--glass-hi` and `--glass-strong` become `--surface`; `--glass-field` becomes `--ground`; `--warn-glass` becomes `--warn-bg`; `--glass-line` becomes `--line`. Under the two preferences `--blur-panel` and `--blur-field` become `none`, and the confirmation sheet loses its blur.

## Shapes

Actions and chosen states are pills (999px). A choice not yet made is a rounded square. Containers have large, soft corners. Fields: 16px (`--field`). In the chat, a poster and a reused picture: 14px; the version mark of a change (« V1 »): 9px. Cards, lists, toasts and the credits dialog: 24px (`--radius`). Confirmation and review dialogs, the phone tool row and the sticky step row: 28px. Groups, facts, switch groups, the wait block and the « done » banner: 20px. Style tiles and chat bubbles: 18px; a bubble's corner toward its speaker is 6px. Composer: 22px. Unchosen chips and poster elements: 12px. Version thumbnails: 10px. The poster and its small previews: 5px. Photos: 12 to 16px. Text buttons: 4px. Status dots, swatches and step numbers are circles.

Strokes: 1.5px for control borders and inner rings, 1px for separators and glass edges, 2px dashed for drop zones and the « new » tile. Icons are one outline set: 16px viewBox, stroke 1.5, round caps and joins, `currentColor`, inline paths in `App.vue` with no icon dependency (ADR-050). In the chat they are 20px at stroke 2.

The kit's cut corners and the arcs of the D are not used in either interface. The operator's page uses 8px corners, 2px borders, and 12px for its dialog.

**The Pill Means Chosen Rule.** A chip, a poster element or a format is a 12px rounded square until it is chosen. Then it becomes a pill with the accent fill and the `--hue` border. Shape marks the choice as well as colour, and the change of corner animates over 200ms.

## Components

### Buttons
Every `button` starts from one zero-specificity reset (`:where(button)`), so one class overrides it.
- **Shape:** pill (999px), 1.5px border, 8px gap between icon and label, line-height 1.2, weight 700.
- **Default** (40px, padding 0 20px): `--glass-field` with `--blur-field`, `--line` border, `--text`. Hover, only where a pointer hovers: `--raised`.
- **Primary** (`button.primary`, 48px, 15px): `--invert` fill and border, `--invert-ink` label, no blur. Hover: opacity .86. Disabled: `--raised` fill, `--faint` label. While busy it keeps its own colours. `.download-button` is the same look for a link (48px, padding 0 22px). « Retirer de l'affiche » (`.selection .remove`) is the one dark pill near the poster, with `--lift`.
- **Secondary** (`button.secondary`, 48px, 15px): the default glass pill at main size. `.download-button.secondary` matches it when « Partager » is the main action.
- **Ghost** (`button.ghost`): no border, no fill, `--text`, weight 500, padding 0 12px. Used for sign-out and the theme switch.
- **Icon** (`button.icon`): 44 × 44px.
- **Text** (`button.text-button`, 32px): no border or fill, `--muted`, 600, underlined 2px below. Hover: `--text`.
- **Send** (`.chat .send`): a 44px yellow circle, `--signal`, with a 24-unit up arrow in `--on-signal` (stroke 2). Disabled: `--control` at opacity .6.
- **Focus:** `outline: 2px solid var(--text); outline-offset: 2px` on buttons, links, fields, summaries and the poster.
- **Press:** `scale(.97)` at once and back on `--press`. Full-width rows and switch rows take a `--raised` background instead.
- **Busy:** after 120ms a 14px spinner in `currentColor` takes the place of the last icon, or sits at the label's end. The control keeps its size.
- **Touch:** with `pointer: coarse` every button is at least 44px high, and main and secondary buttons and download links at least 52px. The phone bottom bars use 52px, 15.5px, padding 0 16px; the primary takes the free width.

### Inputs / Fields
- **Style:** 48px high (52px on touch), padding 10px 16px, 16px radius, 1.5px `--line` border, `--glass-field` with `--blur-field`, `--text` at 15px/550 (16px at 720px and below).
- **Label:** above the field, gap 6px, 13px/650 `--muted`, 14px below.
- **Placeholder:** `--muted` at weight 400, lighter and thinner than a typed value, 4.5:1.
- **Hover / Focus:** border `--control` on hover (hover devices); `--text` on focus, plus the 2px focus outline for a keyboard.
- **Price:** `.unit` writes « Ar » in `--faint` 600, 16px from the right edge.
- **Files:** `.upload-zone` is a 2px dashed `--control` area with 22px padding. `.file-pick` lays a transparent native input over the whole area and shows a French pill button (`--glass-strong`, 44px).
- **Checkbox:** 22px, `accent-color: var(--text)`, in a `label.check` row at least 40px high.
- **Switch** (`label.switch`), for a choice that changes the poster at once: the label is on the left and a 52 × 32 track on the right. Off: `--raised` with a 2px `--muted` ring and a 20px `--muted` knob. On: `--invert` with a 24px `--invert-ink` knob. Switches are grouped in a 20px glass list with `--line` between rows. It is still a checkbox for the keyboard and screen readers.
- **Disclosure** (`summary`): 44px, 700, `--muted` (`--text` when open), with a 7px chevron in `--faint` that turns.
- **Errors:** fields carry no error colour. A reason goes in a `.why` line (`--warn`, 13px/550), a block of issues, or an error toast.

### Chips and choices
- **Chip** (`.chip`): 40px (44px on touch), at least 44px wide, padding 0 15px, 12px corners, `--line` border, `--muted` at 14px/650. Chosen (`aria-pressed=true`): a pill, `--accent-soft`, `--hue` border, `--accent-ink`. Poster elements (`.layer-list button`, 36px) and format radios (`.format-choice label.chip`, with the radio transparent over the label) behave the same way.
- **Colour swatch** (`.sw`): 36px circle (44px on touch), 3px `--surface` border, 1.5px `--control` ring. Chosen: 2.5px `--text` ring.
- **Segmented control** (`.seg`, « Message / Pas à pas » in the header): a pill track with 3px padding, `--glass-field`, 1px `--line` ring. Segments are 38px at 13px/600 `--muted`; the chosen one is `--invert`.
- **Tabs and steps** (`.tabs`): a pill track with 4px padding and a 1.5px `--line` ring. Tabs are 36px at 13.5px/600 `--muted`. The chosen tab is `--glass-strong`, `--text` 700, with `--lift`. A step number is a 16px disc in `--line`, or `--text` when chosen. In the editor's tools at 1080px and below, the tabs become a 28px-corner glass row of icons with labels. The active icon sits in a 54 × 32 pill of `--accent-soft`.
- **Style tile** (`.look`): an 18px glass tile with a 13px-corner square image and 12.5px/600 text. Chosen: the selection ring and a 24px `--invert` disc with an `--invert-ink` tick.

### Cards / Containers
- **Glass panels:** `--glass-panel` with `--glass-shadow` and `--blur-panel`. Editor rail `.card`: 24px corners, padding 20px 22px (18px 16px on a phone). `.group`: 20px corners, padding 18px 20px. `.sign-in` (420px) and `.intake`: 24px corners, padding 28px (20px on a phone). `.empty`: padding 28px, `--muted`.
- **Solid dashboard cards:** on Accueil (`.home-bal`, padding `clamp(16px, 3vw, 32px)`), Mes crédits (`.credit-balance`, 16px) and Mon compte (forms and sections, 18px, 12px gap). These are `--surface`, with a 1px `--line` border and `--radius` corners. They are not glass.
- **Facts** (`.facts`): a three-column glass strip with `--line` between cells. The label is 13px `--faint` and the value 16px/700. On a phone only the price row stays.

### List rows
- **Poster list** (`.rows` > `.library-row` > `.library-item`): one 24px glass panel. Rows are at least 76px high and separated by 1px `--line`. Columns: a 48 × 60 thumbnail (8px corners, `object-fit: contain`), title (ellipsis) with the meta under it in `--faint` 500, whole at every width (state · price · date · variant), and a 16px chevron. Hover: `--glass-field`. Press: `--raised`, no scale. Rows off screen use `content-visibility: auto`.
- **Accueil's recent posters** (`.home-recent`): transparent rows with a bottom `--line`, padding 10px 2px, a 44 × 55 thumbnail on `--raised`.
- **Credit history** (`ShopCredits.vue li`): padding 10px 0, a bottom `--line`, time and note in `--muted`, tabular figures.

### Dialogs and sheets
- **Confirmation** (`.confirm-sheet` > `.confirm`), for a paid action, the fidelity check, the final check and sign-out. The sheet is fixed and centred, with `--scrim` and `blur(6px)` behind it. The dialog is `min(100%, 440px)` wide, `--glass` with a 1px `--glass-line` edge, 28px corners, padding 24px, gap 10px and `--glass-shadow`. Text is `--muted`; the cost is `--text` 700.
- **Conditions of use** (`.terms-sheet`): the same, 560px, starting from the top and scrolling.
- **Review panel** (`.review-panel`): fixed, with its own ground (`--ambient` over `--ground`) and 28px corners. On a phone it fills the screen with 0 corners. Its decision bar is fixed at the bottom, one full-width 52px button per row, with the forward decision on top.
- **Credits dialog** (`dialog.credits-container`): `--ground`, 1px `--line`, `--radius` corners, `--scrim` backdrop.
- **Large poster view** (`.stage.peek`, 1080px and below): fixed full screen on `--glass`.

### Navigation
- **Header** (`.app-header`): sticky, at least 56px, `--glass` with `--blur-panel`, a 1px `--glass-line` bottom edge. The brand link is at least 44px high, named « Doka Studio — Accueil », with `translate="no"`. Then the shop's name (13px/600 `--muted`, at most 28ch, hidden on a phone), the navigation, the segmented control in the creator, the theme switch (ghost icon) and sign-out (ghost).
- **Desktop navigation** (`.nav a`): 40px pills, padding 0 14px, `--muted` 650. Hover: `--glass-field` and `--text`. Current (`aria-current`): `--text` 700 on `--glass-field` with a 1.5px `--line` inner ring. Counts are `--muted` in the header.
- **Phone bar** (at 720px and below, outside the editor): the same `nav` becomes a fixed bar at the bottom. It is `--glass` with `--blur-panel`, a 1px `--line` top, a padding of 6px 8px plus the safe area, and a grid of 4 equal columns (5 in the creator). Each item is 58px high, with an icon in a 58 × 32 pill over a one-line label at 12.5px/16px. The current item's icon pill is `--accent-soft` with `--accent-ink`. The bar shows « Accueil », « Créer », « Affiches », « Styles » and, in the creator, the bare balance number (« Crédits » when the balance failed to load). The counts and the long words (« Mes affiches 3 », « Styles 12 », « 117 crédits ») are visually hidden but stay in the accessible name. The short labels are `aria-hidden`. While a chat message is being typed, the bar is hidden.
- **Phone editor bar** (`.titlerow.bar`): replaces the header while a poster is open. It is sticky, 56px plus the safe area, with back, the poster's name (16px/700) and its save state (12.5px `--muted`), then undo and redo. `--muted` keeps 4.5:1 over the content blurred behind it.

### Chat
- **Frame** (`.chat`): a grid of the poster side, the thread and the composer, 680px wide, 15px/22px text, thin `--control` scrollbars. From 880px with a poster, the thread and the composer are on the left and a 340px poster column is on the right. The chat's height follows the visible screen, and the page itself does not scroll.
- **Bubbles:** at most `min(86%, 460px)`, padding 10px 14px, 18px corners. The owner's bubble is on the right, `--bubble`, with a 6px bottom-right corner. The bot's is on the left, glass with the corner sheen, a 1px `--glass-line` edge, `--msg-shadow` and a 6px bottom-left corner. While a reply is awaited, a 16px spinner shows (`--control` track, `--hue` arc).
- **Composer** (`.composer`): glass with the sheen, 22px corners, padding 8px. Its edge turns `--text` while focused. It holds the photo tray (68px images, 12px corners), the style pills (34px, `--glass-field`, chosen with a `--text` border) and a borderless 16px/22px textarea of 44 to 120px beside the send button.
- **Poster side** (`.chat-side`): glass, 20px corners. It holds a 60px poster thumbnail (full width in the wide column) and the list of modifications, with 44px rows and the current row on `--bubble`.

### Status blocks
- **Toast** (`.message`): fixed and centred, `--glass`, 24px corners, `--lift`, 700 text, and an 8px dot: `--ok`, or `--bad` for an error. Errors sit at the bottom, notices at the top (64px). At 1080px and below an error rises 130px, above the bottom bar, and in the editor a notice moves there too.
- **Caution:** `.demo-notice`, `.issues`, `.save-recovery`, `.polish-preview` and `.refusal` are `--warn-glass` with 16px corners. Their text is `--warn` at 13px; a blocking issue's link is `--bad` 700.
- **Done** (`p.done`): `--ok-bg` with `--ok` text at 650, 20px corners.
- **Version state** (`.state`): a 7px dot, `--warn` for draft, `--ok` for approved, `--bad` for rejected, always beside its word.
- **Wait block** (`.job-state.wait`): a 20px glass block with a padding of 16px 18px. It has a 16px/22px/800 heading, the elapsed time in the top right corner (13px/700 `--muted`), a 2px rail, and three steps in 24px circles. A finished step is `--ok-bg` with `--ok`; the current step has a 2px `--hue` ring and `--accent-ink`. An offline note is `--warn-bg` with `--warn`.

### Progress marks
- **Loading line** (`.load-line`, `role=progressbar`): fixed at the top of the screen, 3px high, above everything. A 30% segment of `--hue` travels across.
- **Wait bar** (`.wait-rail`): a 2px `--line` track. A 30% segment of `--hue` travels while the job runs (`.moving`).
- **Generation pill** (`.gen-pill`): a 28px glass pill at the bottom centre of the poster, 12.5px/18px/700, with a 7px `--hue` dot that pulses in size. While a scene is made, the poster dims to opacity .55 and the version badge shows.
- **Spinners:** the busy control's 14px spinner, a 22px spinner on a version thumbnail (over `--surface`), the chat's 16px spinner, and a 16px `--text` spinner on a photo while it uploads.

### The Signal mark
- **Kit files** (`docs/project/brand/doka-studio-signal/`, untracked in git at this commit): `masters/`, `digital/` (charcoal, black, paper and white versions of horizontal, stacked, wordmark and symbol, SVG and PNG), `web/` (favicons, Apple and PWA icons, maskable icon, app icon), `fonts/`, `palette.json`, `USAGE.md`.
- **In the app, byte for byte:** `frontend/src/assets/doka-symbol-small.svg`, `doka-horizontal.svg` and `doka-horizontal-reverse.svg` (from `masters/`); `frontend/public/favicon.svg`, `favicon.ico` and `icons/{apple-touch-icon,icon-192,icon-512,icon-maskable-512}.png` (from `web/`, the kit's `maskable-512.png` renamed). `tests/brand.test.ts` pins their SHA-256. The manifest uses `theme_color` #F2C744 and `background_color` #F5F1E8, the kit's values. The page's `theme-color` metas follow the ground (#f5f1e8 / #100f0e).
- **Header, below 1440px:** the charcoal small D (`doka-symbol-small.svg`) at 32px with 6px of padding on a square `--signal` tile (`.signal-symbol`), followed by the name « Doka Studio » set in Figtree at 16px/800.
- **Header, from 1440px:** the horizontal logo at 220px, the guide's screen minimum. It is the charcoal file in light and the reverse paper file in dark.
- **Operator's page:** the kit's `favicon.svg` (a D on a yellow tile with corners of radius 40.96/256), percent-encoded inside `admin.css` as `.marked::before`. It is 24px (28px beside the `h1`), with a quarter of its height kept clear (`margin: 6px 0`, `7px 0` beside the `h1`, and an 8px gap), before « Doka Studio · Operator ». The page asks the server for no image.
- **Clear space** (USAGE.md): x = a quarter of the visible height of the D, at the scale in use. For the wordmark alone, a quarter of the height of the « d ». Measure from the drawing, not the file's edge. The space stays free of text, edges and other marks. The supplied icons have their own framing.
- **Minimum screen widths** (USAGE.md): horizontal 220px; stacked 160px; wordmark 160px; D alone 16px (prefer the favicon file at that size).
- **Yellow** (USAGE.md): paper and charcoal structure the page, and yellow draws attention to an action or an announcement. Charcoal goes on yellow, never white. Yellow is a ground or an accent, never a text colour on a light ground. Icons are the charcoal D on yellow.
- **Integrity** (USAGE.md): keep the files' proportions, orientation, spacing and colours. Do not stretch, rotate, outline, shadow or add a gradient, and do not assemble the elements improvisationally. On a dark ground use the paper or white files. Do not retype the logo with a font.

### Operator's page
- **Top bar** (`.bar`): 960px wide, a 2px `--line` rule below, the brand in 800 with the mark, then the navigation and the `.actor` line (14px `--muted`).
- **Buttons:** 44px, padding 0 16px, 2px `--muted` border, 8px corners, `--surface`, 700. **Primary:** `--signal` fill and border with charcoal text, in both themes.
- **Fields:** 44px (a textarea 88px), padding 8px 12px, 2px `--muted` border, 8px corners, `--surface`.
- **Focus:** `outline: 3px solid var(--focus); outline-offset: 2px`.
- **Shops table:** a 1px `--line` under each row, headers 14px `--muted`. From 600px, the numeric columns are right-aligned with tabular figures. Below 600px each shop is a card (2px `--line`, 8px corners) and each value carries its column's name.
- **Notices:** `.banner` is a yellow band with charcoal 700 text. `.note` has a 4px yellow left border. A shown secret or kept record (`.shown`, `.kept`) is a 2px yellow-bordered card. `.refusal` is `--bad` 700.
- **Dialog:** `min(32rem, 100vw - 32px)`, 2px `--text` border, 12px corners, `--surface`, backdrop rgb(0 0 0 / .55).

### Motion

| What moves | Property | Duration | Easing |
| --- | --- | --- | --- |
| Colour changes on controls, fields, nav, tabs, switch track | `background-color`, `border-color`, `color`, `opacity` | 150ms | ease-out |
| Press (`--press`) | `transform: scale(.97)` | 160ms | `cubic-bezier(.23, 1, .32, 1)` |
| A chip or element becoming a pill | `border-radius` | 200ms | ease-out |
| Switch knob | `inset`, `width`, `height` | 150ms | ease-out |
| Disclosure chevron | `transform` (45° → 225°) | 150ms | ease-out |
| Busy spinner | `rotate` 1 turn, shown after 120ms | 700ms, infinite | linear |
| Loading line | `translateX(-100%)` → `translateX(435%)` | 1.2s, infinite | `cubic-bezier(.4, 0, .2, 1)` |
| Wait bar segment | same keyframes | 2.4s, infinite | linear |
| Generation dot | `scale` 1 → .6 → 1 | 1.6s, infinite | ease-in-out |
| Chat reply spinner | `rotate` | 800ms, infinite | linear |
| A new version appearing (`App.vue`, `canvasDrawn`) | `opacity` 0 → 1 (Web Animations) | 200ms | ease-out |
| Page scroll | `scroll-behavior: smooth` | | |

Transitions name their property, never `all`. The generation dot pulses in size, not opacity, because a fainter dot fell under 3:1.

**`prefers-reduced-motion: reduce` does exactly this:** it sets `scroll-behavior: auto` and `transition: none` on every element (`*`, `!important`). Pseudo-elements are not matched, so the switch knob and the disclosure chevron keep their 150ms transition. It stops the generation dot. It stops the wait bar segment and the loading line and draws each at full width, still and not dimmed. It replaces the press scale: buttons (except the primary, a thumbnail, the « new version » tile and send), links (except the download link) and format chips take a `--raised` background, and those exceptions take a 3px `--hue` ring. It slows the chat spinner and the photo spinner to 2.4s per turn. It makes every glass surface solid with no blur (see Elevation) and removes the confirmation sheet's blur. `App.vue` skips the new version's fade. The busy-control spinner and the thumbnail spinner keep turning at 700ms. The operator's page and « Vos données » define no motion.

## Do's and Don'ts

### Do:
- **Do** put the shops' main action on `--invert` (charcoal #20201d with #ffffff ink in light, paper #f5f1e8 with #100f0e ink in dark).
- **Do** use `--signal` only as a fill with `--on-signal` on it, and `--hue` for every ring, border and progress mark.
- **Do** keep text at 4.5:1 (3:1 from 24px, or 18.66px bold), placeholders at 4.5:1 at any size and lighter than typed text, and accent lines at 3:1, measured with `check_contrast` and `check_marks` in both themes.
- **Do** mark a choice by its shape as well as its colour: a pill among rounded squares, a ring, a tick.
- **Do** keep targets at 44px on touch screens, and main buttons and fields at 52px.
- **Do** keep each phone-bar label on one line and keep the full French name in the accessible name.
- **Do** give the five frame screens `--page` (860px) and `.page-title` (26px/32px/800).
- **Do** put hover looks inside `@media (hover: hover)`.
- **Do** use the kit's files byte for byte, the charcoal files on light grounds and the paper or white files on dark ones.

### Don't:
- **Don't** make the shops' main button yellow until the owner has seen a yellow one on a phone in daylight (owner decision 2; Signal Yellow on paper is 1.43:1).
- **Don't** use Signal Yellow as a line or as text on a light ground; never put white on yellow.
- **Don't** add the Doka logo or any Doka identity to a shop's poster, and don't let a page token reach the poster canvas.
- **Don't** load Space Grotesk or Noto Sans for the interface text, and don't fetch a font from another site (ADR-122).
- **Don't** rebuild the shops' dark theme on the kit's Charcoal; it keeps its near-black ground and greys (owner decision 3).
- **Don't** let the operator's page import or request anything of the shops' app (D-ADMIN-005).
- **Don't** blur a copy of the poster as a backdrop, and don't blur a control again on a surface that already blurs.
- **Don't** put a blur on an ancestor of a fixed bar; move the blur to a `::before` layer.
- **Don't** fade a progress mark with opacity; it falls under 3:1.
- **Don't** transition `all`.
