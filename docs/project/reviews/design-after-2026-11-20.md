# Design after the polish — client and operator interfaces (2026-11-20)

The proof for T-POLISH-001 to 005 (ADR-122), against the 16 findings of
[design-baseline-2026-11-20.md](design-baseline-2026-11-20.md). Same method: the local build of `main`, stub
providers, the same seeded data, the same 17 screens at 360, 768 and 1440 px in both themes
(`uv run python ../frontend/tests/design_capture.py after` from `backend/`; output in
`outputs/design-capture/after/`, git-ignored). Not the live site, not a real phone, not a screen reader. Nothing is
deployed.

## The two checkers, before and after

| Checker | Before | After | What moved |
| --- | --- | --- | --- |
| Impeccable detector on the 51 snapshots | 167 findings, 13 distinct | 108, 5 distinct | Gone: the five faint placeholders (14), the tight line height (3), the fading dot (36). Left: the cream ground (24: the brand's paper), the two moving progress lines (72: a wait, stopped under reduced motion), three « cramped padding » blocks (12: read below) |
| design-taste inspector, 13 screens | 14 rules fired | 11 | `edge-text` 8 screens → 0, `no-title` 3 → 0, `app-title-size` 1 → 0. Unchanged: `palette-cream` (brand), `font-fallback` and `broken-image` (artefacts of a snapshot), `button-fx`, `heavy-shadow`, `gradient`, `micro-label` (the glass look, ADR-077), `hero-void`, `unused-canvas`, `headline-lines`, `numeric-align` (at 390 px only: the operator's cards, which label each value) |

The detector first reported 126 after the code changes: 18 of them were two corner sizes of the chat (14 px, 9 px)
missing from the new `DESIGN.md`'s scale. The record was completed, not the code.

## The 16 findings

| # | Baseline finding | State | Evidence |
| --- | --- | --- | --- |
| A1 | The tab and the installed app said « Affiche Gen » | **Closed** (T-POLISH-001) | `brand.test.ts`: the three titles, the manifest, no shipped file with the old name |
| A2 | The operator's page had no mark | **Closed** (T-POLISH-001) | `sheets/admin-shops.png`, both themes; the mark is in the page's own stylesheet |
| A3 | The app icon was not the Signal one | **Closed** (T-POLISH-001) | six files, SHA-256 pinned in `brand.test.ts` |
| B4 | Three type systems; the kit names two other families | **Decided, not changed** | Figtree stays (ADR-122); the operator's page keeps the system font. An owner decision on its default |
| B5 | Titles of 42 px, small, or missing | **Closed** (T-POLISH-003) | one `.page-title` on five screens; one accessible title for the chat in seven states (`chat_browser.py`) |
| B6 | The navigation changed between screen families; « 117 cré… », « Mes affiches » on two lines | **Closed for the labels** (T-POLISH-003) | `sheets/client-chat-new.png`: « Accueil, Créer, Affiches, Styles, 117 ». Four items on the dashboard screens and five in the creator stay: the creator shows the balance (D-SHOP-DASH-001) |
| B7 | The main button is charcoal on the client and yellow on the operator's page | **Left, on purpose** | A yellow main button on paper is 1.43:1; it waits for the owner's look at a phone in daylight |
| B8 | The creator's phone header wraps the name | **Left, on purpose** | An approved choice (T-SHOP-DASH-010): the name stays visible, the header stays one row |
| C9 | Placeholders at 3.6 to 3.9:1 | **Closed** (T-POLISH-002) | 5.7:1 at worst; measured on the rendered screens, a named field that was not measured fails the smoke |
| C10 | A box around the page title on a direct load | **Closed, in two steps** | T-POLISH-003 replaced the box by an underline, which then showed on every page opened (found by reading the after captures: `sheets/client-home.png` of the first after run). Now the underline needs a key press first (`:root[data-keys]`); `shop_dashboard_browser.py` reloads a page and checks that nothing shows |
| C11 | Text 12 px from the phone's edge | **Closed** (T-POLISH-003) | 16 px on the five screens, checked as `main`'s computed padding |
| C12 | Line height 1.2 on the poster rows; three « cramped » blocks | **Closed for the line height; the blocks left** | The three blocks were read in the captures: `.home-bal` has its padding, the poster `.rows` and the steps' `details` are full-width rows with a separator, by design |
| C13 | Two endless animations to check under reduced motion | **Closed, and more** (T-POLISH-002) | They already stopped; the review found them dimmed to about 2:1 when still, and the dot fading to 1.5:1: now opaque, the dot pulses in size |
| D14 | Desktop leaves half of the first screen empty | **Left, on purpose** | Centring an empty conversation was dropped (phones first; the composer would jump at the first message). « Mes affiches » is a short list on little data |
| D15 | Operator tables: numbers left-aligned; one shop's page narrow | **Half** (T-POLISH-004) | Numbers right-aligned from 600 px. The two-column shop page goes with T-ADMIN-008 |
| D16 | The Service screen lists every session | **Left, on purpose** | 24 sessions were the capture run's own; the live service has one to four |

## Found during the work, and fixed

- Under reduced motion the pressed send button lost its fill: a charcoal arrow on dark grey, 1.11:1 (Codex, T-POLISH-002).
- On a slow opening of a poster's chat from « Mes affiches » two page titles were exposed for a moment; the chat's
  title stayed readable behind « Quitter le message ? » (Codex, T-POLISH-003).
- The 860 px frame cut a poster row's details sooner on a desktop (« … · 20 nov. … »): they now sit under the title
  at every width, as they did on a phone (found by reading the after captures).
- Vitest handed every stylesheet to a test as an empty string: `admin.test.ts`'s rule that the operator's page takes
  nothing of the shops' had never seen `admin.css` (`vite.config.ts`, `test: { css: true }`).

## Still open

Proposed as follow-up tasks in TODO.md, none started:

| What | Why it matters | Source |
| --- | --- | --- |
| The plain borders of fields, buttons and chips are about 1.2:1 in the light theme and 1.4:1 in the dark one, and no test measures them | A control's boundary should be 3:1 (WCAG 1.4.11); a calculation from the tokens, not a measurement | the `DESIGN.md` pass |
| Under reduced motion the switch knob and the disclosure arrow still move, the busy and thumbnail spinners keep turning, the chat's spinners only slow down; the still wait bar is a full solid bar that can read as « finished » | The reset reaches `*`, not pseudo-elements | the `DESIGN.md` pass; Codex, T-POLISH-002 r2 |
| No forced-colours fallback for the pressed ring and the progress fills | They are shadows and backgrounds, which that mode drops | Codex, T-POLISH-002 r1 |
| The generation pill is measured against its panel, not against the poster under it | A light or dark poster changes what is behind the glass | Codex, T-POLISH-002 r1 |
| Three blocks of the operator's page have yellow borders on the light ground (about 1.5:1) | The shops' rule is the ochre for any line | the `DESIGN.md` pass |

For the owner:

| Decision | Default in force |
| --- | --- |
| The interface typeface | Figtree |
| The main button's colour | Charcoal; a yellow one after he has seen it on a phone in daylight |
| The dark theme's ground | The near black of ADR-091, not the kit's charcoal |
| The phone bar shows « Affiches » and the credits as a number alone | Yes; the full names stay for screen readers. A voice-control user who says « Mes affiches » to a link that shows « Affiches » is untested |
| Two new titles for screen readers, « Créer une affiche » and « Votre affiche » | Drafts until he reads them |
| The name typed beside the mark, in the shops' header under 1440 px and on the operator's page | Kept. The Signal guide says not to retype the logo with a font nor to assemble its elements; the mark alone, or the kit's horizontal logo, would follow it |

## What this proof does not cover

A real phone, a screen reader, forced colours, the live site, long shop names, a shop with many posters in the
860 px frame, the editor's canvas. The poster is covered by the guard of T-POLISH-002 (the canvas gives the same
pixels in both themes, nothing veils it) and by the unchanged check of a confirmed file's bytes, not by a pixel
baseline: a clipped canvas would pass.
