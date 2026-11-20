# Interface polish — design

**Status:** Approved v2, 2026-11-20, by the lead under the autonomy grant (ADR-122). Covers
[requirements/interface-polish.md](../requirements/interface-polish.md) v2, R-POLISH-001 … 005. Evidence:
[reviews/design-baseline-2026-11-20.md](../reviews/design-baseline-2026-11-20.md) (finding numbers A1 … D16 are that
report's). v1 was rejected by [Codex r1](../reviews/interface-polish-design-r1.md) and narrowed by the
[devil's advocate](../reviews/interface-polish-devils-advocate.md); the table at the end says what each changed. v2
was not reviewed again: each task's code gets its own review.

**Shape of the change.** Presentation only: the HTML entry pages, `frontend/public/` (manifest, icons,
`donnees.html`), `frontend/src/style.css`, the `<template>` and `<style>` parts of the Vue files,
`frontend/src/admin/admin.css`, and tests. No route, table, migration, job or money rule; nothing in `render.ts`,
`canvas.ts`, `PosterCanvas.vue`, `document.ts`, `composition.ts`, the poster fonts or the backend. The data model,
the API contracts and the state machines are unchanged, so this design has no section for them.

**The three skills, each in one role.** Impeccable: its craft floor is read before any UI edit, `detect --changed`
runs after each task, `document` writes `DESIGN.md` at the end. design-taste: its app-screen rules
(`references/app-screens.md`) are the second read, `inspect.mjs --app` judges the after captures. ui-ux-pro-max: one
lookup per precise question, never its design-system generator. When they disagree: the Signal guide, PRODUCT.md,
the approved designs, this design, then a skill.

## D-POLISH-001 — The name and the mark (R-POLISH-001; A1, A2, A3) — built

| File | Change |
| --- | --- |
| `frontend/index.html` | `<title>Doka Studio</title>`; `favicon.ico`, `favicon.svg`, the Apple touch icon |
| `frontend/public/manifest.webmanifest` | `name` « Doka Studio », `short_name` « Doka », `theme_color` `#F2C744`, `background_color` `#F5F1E8`; the rest and the three icon paths unchanged |
| `frontend/public/icons/`, `frontend/public/favicon.*` | the kit's files, byte for byte (the kit's `maskable-512.png` keeps today's path `icon-maskable-512.png`) |
| `frontend/public/donnees.html` | the same two icon links; title « Vos données · Doka Studio » |
| `frontend/src/admin/Admin.vue`, `admin.css` | the mark before « Doka Studio · Operator » in its three places: a `::before` whose background is the kit's `favicon.svg`, percent-encoded inside `admin.css` |

The operator's page asks the server for nothing but its own files and routes (D-ADMIN-005; `admin_browser.py`
asserts it, `admin.test.ts` asserts that it imports nothing of the shops'). So its mark is neither an import of
`src/assets` nor a request for `/favicon.svg`: it is in its own stylesheet, and `admin/index.html` gets no icon link
(a browser asks the origin for `/favicon.ico` by itself, which that smoke already allows). `brand.test.ts` pins the
SHA-256 of the six shipped files (the kit folder is not committed: a comparison with it would vanish on a fresh
clone), checks the names, the links and that the operator's mark is the kit's drawing. `vite.config.ts` gains
`test: { css: true }`: without it Vitest hands every stylesheet to a test as an empty string, and `admin.test.ts`'s
isolation rule never saw `admin.css`.

The manifest's colours are the installed app's splash and task switcher, which have no theme: the kit's values. The
page's own `theme-color` metas keep following the page's ground. An installed app keeps its old name and icon until
the browser reads the manifest again; nothing to do.

## D-POLISH-002 — The Signal accent and the text (R-POLISH-002; B4, C9, C12)

**Tokens** (`style.css`; `:root` is the dark theme, `:root[data-theme=clair]` the light one).

| Token | Light | Dark |
| --- | --- | --- |
| `--ground` | `#f4f1ec` → `#f5f1e8` | unchanged |
| `--text`, `--invert` | `#1b1815` → `#20201d` | `#f5f2ee` → `#f5f1e8` |
| `--signal` (new): a fill, always under `--on-signal` | `#f2c744` | `#f2c744` |
| `--on-signal` (new) | `#20201d` | `#20201d` |
| `--hue`: every ring, border and progress mark | `#e58e1a` → a dark ochre of the yellow's hue, at least 3:1 on `--ground`, `--surface` and `--raised` | `#f2a33d` → `#f2c744` |
| `--accent-soft`, `--accent-ink` | rederived in the yellow's hue, ink at least 4.5:1 on soft | the same |

The two `theme-color` metas and the inline script of `index.html`, and those of `donnees.html`, take the new light
ground. Every other token stays, the dark greys included (ADR-091).

**Each present use of `--hue` gets one of the two roles**, decided once, by this rule: a shape that holds a glyph or
a label is a fill (`--signal`, its content `--on-signal`); anything that must be seen against the page is a line
(`--hue`). The uses today (`style.css`): the top loading line (93), the border of a chosen chip, format or element
(151, 162, 338), the dot of the generation pill (378), the moving part of the wait bar (395–396), the ring of the
current step (404), the chat's spinner (702), the send button (756), the press ring of the main button under
reduced motion (790). Of these only the send button is a fill; its glyph takes `--on-signal` in place of its
hard-coded ink. The implementer greps the Vue files' styles for any other use and classifies it the same way.

**The main button is not touched**, in either theme, nor is the final panel's order of main and secondary actions
(share-poster.md).

**Placeholders** (C9): `input::placeholder, textarea::placeholder` lose `opacity: .8`, and their colour is at least
4.5:1 on every field they sit in, in both themes, with less emphasis than typed text.

**Text finish** (C12): the second line of a poster row gets a line height of at least 1.3. The detector's three
« cramped padding » blocks are read in the after captures and changed only if content really touches a border.
C13 needs nothing: both endless animations already stop under `prefers-reduced-motion` (`style.css` 782–791).

**Tests.**
- `browser_smoke.py`'s `check_contrast` already measures every visible text over the darkest and the lightest point
  of its real backdrop (glass over the patches). It is extended to placeholders (colour and opacity together, 4.5:1
  whatever the size) and called on the screens it does not visit yet in both themes: Accueil, Mes crédits, Mon
  compte, the chat with and without a poster, the final panel.
- A walk reads the computed colour of each `--hue` and `--signal` use listed above against what is behind it: 3:1
  for a line, 4.5:1 for the send button's glyph on its fill, in both themes; the wait bar's moving part against its
  track at no less than today's ratio.
- `frontend/tests/tokens.test.ts`: the exact kit values of `--ground`, `--text`, `--invert`, `--signal`,
  `--on-signal` in each theme, so a later edit cannot drift from the kit.
- The poster: the existing check of the confirmed file's bytes stays. New: with one fixed document, the editor's
  poster canvas gives the same `toDataURL()` in the light and the dark theme, and neither the canvas nor an ancestor
  up to the stage has an opacity under 1, a filter or a blend mode when nothing is running. A page token cannot
  reach a poster; this proves it on the rendered page.

## D-POLISH-003 — One frame for every screen of the shop (R-POLISH-003; B5, B6, C10, C11)

**Titles.** The `h1` of Accueil, Mes affiches, Mes crédits, Mon compte and Styles share one class: 26 px / 32 px,
weight 800 (`ShopHome.vue`'s `clamp(2rem, 5vw, 3rem)` goes; the sign-in, the step editor's own titles and the
mobile step bar are not touched). On that class only: `:focus { outline: none }`, and `:focus-visible` shows a 2 px
underline 6 px under the text, so a keyboard user still sees where the focus went and nobody sees a box. Titles
that have no `tabindex` today get `tabindex="-1"` and the same focus as the others on arrival. « Ma boutique »
(`ShopAccount.vue`, the focus's return after a cancelled departure) and every other `h2` keep the ordinary ring.

**The chat's title.** One `h1` for the chat route, rendered by `App.vue` outside the conversation's live region and
shared by every branch (the conversation, the retry of an import, an unsupported browser, another tab's ownership,
ownership pending), with the existing visually-hidden class: « Créer une affiche » while there is no creation, the
creation's offer title when it has one, else « Votre affiche ». A dialog's heading is not the page's: the page
behind is inert while it is open.

**Width and gutter.** `--page: 860px` is the content width of the five screens: `ShopAccount.vue`'s
`width: min(100%, 660px)` is replaced (a `max-width` beside it would change nothing), `ShopCredits.vue`'s 680 px
too as a page, while the credits **panel** in the creator keeps its 680 px. At 720 px and below, those five screens
alone get a 16 px gutter; `main`'s 12 px, which the editor's sticky bars use in their negative margins, stays for
the chat and the editor.

**The bottom bar on a phone (≤ 720 px).** Items and order unchanged: four on the dashboard screens, five in the
creator, where the balance stays shown and linked (D-SHOP-DASH-001). At that width:
- every label is on one line at 11 px or more;
- the counts of « Mes affiches » and « Styles » leave the eye and stay in the accessible name (visually hidden, not
  `display: none`). This amends item 10 of poster-editor.md, which showed them;
- the credits item shows the number alone, written exactly as in its name (« 117 », « -2 », « 12345 »); the name
  stays « 117 crédits ». An unread balance shows « Crédits », named « Mes crédits »;
- if « Mes affiches » does not fit one line in the five-item bar at 360 px and 11 px, both bars show « Affiches »,
  named « Mes affiches ».
The editor rail's separate credits button and the desktop navigation do not change.

**Not changed, on purpose.** The compact creator header (B8): the product name may wrap inside its control, the
header stays one row (T-SHOP-DASH-010, `chat_browser.py` checks the height). An empty conversation on a wide screen
(D14): the composer stays at the bottom; moving it at the first message costs more than the empty space.

**Tests** (`shop_dashboard_browser.py` for the five screens and the bar, `chat_browser.py` for the chat):
- per screen and state (fresh, with a poster titled and untitled, each recovery branch): exactly one level-one
  heading in the accessibility tree, with the expected name;
- the five titles: computed 26 px / 32 px / 800; after arriving by the navigation the title is `activeElement`, has
  no outline, the next Tab goes to the screen's first control; « Ma boutique » still shows its ring after a
  cancelled departure; closing the credits panel returns the focus to its opener;
- at 1440 px the five contents are 860 px wide with the same left and right edges; at 360 px no text of those
  screens starts closer than 16 px to an edge; `editor_refinements_browser.py` and the chat's 360 px geometry checks
  pass unchanged;
- the bar at 360 px, four and five items, balances −2, 0, 117, 12 345 and a failed read, 0, 3 and 120 posters: each
  label's text range is inside its link on one line; each link is at least 44 × 44 px; the accessible name contains
  the visible text and equals the full French name.

## D-POLISH-004 — The operator's numbers (R-POLISH-004; D15)

One class on the numeric headers and cells of the Shops table (Available, En attente, Posters, Sessions):
right-aligned, tabular figures, from 600 px (the cards below 600 px label each value and stay as they are).
`admin_browser.py` checks headers and cells at 1280 px and the cards at 360 px.

Not done here: the two-column shop page (T-ADMIN-008 adds sections to that screen; laid out once, then) and the
session fold (24 sessions were this run's; the live service has one to four).

## D-POLISH-005 — The record and the proof (R-POLISH-005)

- The capture script moves from the session's scratchpad to `frontend/tests/design_capture.py` (seed through the
  real screens with the smokes' helpers, 17 screens × 3 widths × 2 themes, the static snapshots), with its command
  in AGENTS.md.
- It runs again on the final build; Impeccable's detector and design-taste's inspector run on the new snapshots;
  `reviews/design-after-<date>.md` goes through the 16 findings one by one: closed (with the capture's name), left
  (with the reason), or new.
- `DESIGN.md` at the root, by Impeccable's `document` playbook, from the code as built.

## Errors, edge cases, failure modes

Nothing here touches money, sign-in or a provider. What can go wrong is visual:

| Case | Handling |
| --- | --- |
| A text or placeholder falls under 4.5:1 after a token moves | `check_contrast` fails the smoke, on the real backdrop |
| The amber's replacement makes a running generation hard to see | The walk compares each line with what is behind it, and the wait bar with today's ratio |
| A smoke asserts an old colour, title size or width | Updated in the same task, only for what a criterion changes; any other failing assertion is a regression |
| A balance of five digits, a negative one, an unread one; 120 posters | The bottom-bar walk |
| A phone keeps the old manifest and icon | Expected for some days; no code |
| Forced colours | The focus ring and borders stay real outlines and borders; the title's underline is a text decoration |

## Tasks

1. **T-POLISH-001** — D-POLISH-001. Built by the lead (a small, mechanical change).
2. **T-POLISH-002** — D-POLISH-002. One Opus implementer, the lead's run of the checks, one Codex review.
3. **T-POLISH-003** — D-POLISH-003. The same.
4. **T-POLISH-004** — D-POLISH-004. Built by the lead.
5. **T-POLISH-005** — D-POLISH-005.

## What the two reviews changed

| v1 | v2 | Why |
| --- | --- | --- |
| The main button turns Signal Yellow | Unchanged | 1.43:1 against the paper; up to two main buttons on a screen; not seen on a phone in daylight (devil's advocate 3) |
| The dark theme rebuilt on charcoal `#20201D` | The dark greys stay | About 25 tuned values, state grounds that would merge with the page, nothing a shop would notice (devil's advocate 4; Codex 2) |
| `--hue` becomes the yellow everywhere | Two tokens: a fill and a line | Ten uses of `--hue`; a yellow line on paper is 1.43:1 and the wait bar nearly disappears (Codex 3; devil's advocate 2) |
| A token table composed over the ground and the surface | The existing rendered measure, extended to placeholders | The page's real backdrop is the patches' gradient under glass; one required pair could never pass (Codex 1, 2; devil's advocate 5) |
| « pixel for pixel » proved by a list of files | The canvas's pixels in both themes | The stylesheet controls what is around the canvas (Codex 11) |
| No outline on any focused `h1` or `h2` | Route titles only, with an underline for a keyboard focus | « Ma boutique » is a deliberate focus target (Codex 4) |
| A hidden `h1` inside the conversation | One for the route, every branch | Three branches sit outside the conversation (Codex 5) |
| `max-width` on the five screens; no 12 px gutter anywhere | Account's width replaced; 16 px on the five screens only | Account would have stayed 660 px; the editor uses the 12 px (Codex 7; devil's advocate 6) |
| An empty conversation centred on a wide screen | Dropped | Phones first; the composer would jump at the first message (devil's advocate 1) |
| The operator's shop page in two columns, sessions folded | Numbers aligned only | One user; T-ADMIN-008 changes that screen; the long list was the test's (devil's advocate 8; Codex 9) |
| The mark imported from the shops' assets | In `admin.css` | The operator's page takes and asks nothing of the shops' (Codex 10) |

## Owner decisions on their defaults

1. The interface typeface stays Figtree (ADR-122).
2. The accent goes from amber to Signal Yellow; the main button stays charcoal until the owner has seen a yellow one
   on a phone in daylight.
3. The dark theme keeps its near-black ground rather than the kit's charcoal.
4. On a phone the bottom bar shows the credits as a number alone and hides the counts.
5. Two titles for screen readers are new French words: « Créer une affiche », « Votre affiche ».
