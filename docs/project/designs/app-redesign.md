# App redesign — design

**Status:** v2, 2026-11-20. Covers [requirements/app-redesign.md](../requirements/app-redesign.md) v2,
R-REDESIGN-001 … 007. Target: the mockup [mockups/doka-console/](../mockups/doka-console/README.md)
(`client.html`, `admin.html`, `doka.css`; published at https://claude.ai/artifact/TLAJXwcJihPh6Tp8R2pa5F).
v1 was rejected by its first review ([r1](../reviews/app-redesign-design-r1.md), 17 findings) and challenged once
([devil's advocate](../reviews/app-redesign-devils-advocate.md), 8 points); « What the reviews changed » is at the
end. v2 was **approved with fixes** by its second review ([r2](../reviews/app-redesign-design-r2.md)); its eight
findings are applied here.

**Shape of the change.** Presentation and navigation of the two interfaces. No migration, no job, no money rule,
no route, no server answer; nothing in `backend/`, `render.ts`, `canvas.ts`, `PosterCanvas.vue`, `document.ts`,
`composition.ts` or the poster fonts. The data model and the state machines are unchanged, so this design has no
section for them.

**How the mockup is used.** It fixes the look and the arrangement. Its sample sentences, its sample numbers, its
fixed-height window with an inner scroll and its single 900 px breakpoint are not the product: where the
application has an approved sentence, a rule or a breakpoint, the application's wins, and the requirements' table
« Not built, on purpose » says where they part.

**Where the work lives.** Branch `redesign` (shops' app, then everything), branch `redesign-console` (the console
until it merges into `redesign`), in git worktrees under `../affiche-ia-worktrees/`. `main` keeps the interface
polish as it is, so the owner can release it alone. Nothing merges into `main`, is pushed or deployed without his
word. Each task leaves `redesign` in a state that could be released.

## Three rules that hold everywhere

1. **Nothing between a fixed element and the window.** No `backdrop-filter`, `filter`, `transform`, `perspective`,
   `contain`, `container-type` or `will-change` naming one of them, on any ancestor of a `position: fixed` element:
   `main`, the editor, the review and final panels (their approval buttons are fixed to the screen on a phone,
   `style.css` 306, 468, 635), and anything new. A blur is painted by the fixed or sticky element itself or by its
   pseudo-element, as today.
2. **The window is the page's scroller.** No wrapper around `header` and `main`, no `overflow` on an ancestor of a
   sticky element. `measureSticky()` (`App.vue` 530–543) and the chat's `measure()` keep measuring real boxes.
3. **One thing is exposed at a time.** What is not shown is `hidden` or `inert`: a closed drawer, the page behind
   an open drawer or a dialog, the shop's parts while the gate is closed.

## D-REDESIGN-001 — Tokens and primitives (R-REDESIGN-001)

**The shops' app** (`frontend/src/style.css`; `:root` is the dark theme, `:root[data-theme=clair]` the light one).
Values of the mockup's `doka.css`, role for role:

| Role | Token | Light | Dark |
| --- | --- | --- | --- |
| Ground | `--ground` | `#f5f1e8` | `#20201d` (was `#100f0e`) |
| Card, field | `--surface` | `#fffdf8` | `#2b2b27` |
| Hover, track, a segment's trough | `--raised` | `#ece6d8` | `#36362f` |
| Text | `--text` | `#20201d` | `#f5f1e8` |
| Secondary, tertiary text | `--muted`, `--faint` | `#4d4940`, `#5f5a50` | `#d6d0c3`, `#c2bcaf` |
| Hairline of a card or a row | `--line` | `rgb(32 32 29 / .10)` | `rgb(245 241 232 / .10)` |
| A field's boundary (3:1) | `--control` | `#7d786d` | `#8f8b80` |
| A button's edge (new) | `--edge` | `rgb(32 32 29 / .20)` | `rgb(245 241 232 / .22)` |
| Hover and current item (new) | `--active` | `rgb(32 32 29 / .08)` | `rgb(245 241 232 / .10)` |
| The sidebar's column (new) | `--side-bg` | `rgb(32 32 29 / .045)` | `rgb(0 0 0 / .22)` |
| The main action's fill, its text | `--signal`, `--on-signal` | `#f2c744`, `#20201d` | the same |
| The main action's edge (new) | `--signal-edge` | `#d9b032` | `#f2c744` |
| Rings, chosen borders, progress (3:1) | `--hue` | `#8f6b00` (unchanged) | `#f2c744` (unchanged) |
| States | `--ok`/`-bg`, `--warn`/`-bg`, `--bad`/`-bg` | `#145c37`/`#e2f2e8`, `#6b4600`/`#fdf0cf`, `#a3271f`/`#fbeae8` | `#8fddb0`/`#1d3327`, `#f0c26a`/`#3a2f14`, `#ff9a8f`/`#3d2320` |
| The field behind the window | `--ambient` from three lights | yellow `.28`, sand `.55`, white `.7` on the ground | yellow `.16`, sand `.34`, white `.04` |
| Glass of a bar | `--glass` | `rgb(255 253 248 / .66)` | `rgb(43 43 39 / .62)` |
| Glass of a dialog, the drawer | `--glass-strong` | `rgb(255 253 248 / .86)` | `rgb(43 43 39 / .88)` |
| What floats | `--lift` | the mockup's | the mockup's |

Where `style.css` has a token of the same role under another name, the name stays and the value changes; a new
name is added only for a role marked (new).

- **The main action.** `button.primary`, `a.primary` and `.download-button`: `--signal` fill, `--on-signal` text,
  a 1.5 px `--signal-edge` border; hover mixes the yellow toward charcoal (`color-mix`, 86 %), never an opacity;
  the busy and disabled rules keep their shape. `.download-button.secondary` and the final panel's ranking of
  « Partager » over the file stay as they are (share-poster.md).
- **Secondary button**: transparent, `--edge` border, `--active` on hover. **Field**: `--surface`, `--control`
  border. **Chip**: `--surface`, `--edge`. **Badge** (`.badge` with `.ok`, `.warn`, `.bad` or none): the state's pale
  ground and its dark text, a pill, one dot.
- **Resting surfaces lose their glass, here and once.** `.sign-in`, `.intake`, `.empty`, `.look-card`, `.rows`,
  `.card`, `.group`, `.comparison figure`, `.shot`, `.facts`, `.job-state` (the shared list, `style.css` 227–228),
  and every field, chip and secondary button that uses `--glass-field`, become `--surface` with a `--line` hairline:
  no `backdrop-filter`, no shadow. The chat's composer and bubbles take the same swap (their restructure is
  D-REDESIGN-003).
- **What keeps blur and shadow, with its present structure and only new values:** the top bar's `::before`, the
  phone's bottom bar, dialogs and sheets, toasts, the editor's sticky and fixed bars, the review and final panels'
  action bars. The review and final panels themselves keep their opaque ground and their scrim shadow exactly: no
  blur is added to them (rule 1).
- The glass tokens nothing uses any more are deleted, and the « one blur » and « solid fallback » blocks
  (`style.css` 813–828) shrink to what is left. `--invert` keeps its other uses after each is read: only the main
  action leaves it.
- Type sizes, weights, line heights and radii are not touched. `index.html`: the dark `theme-color` and the inline
  script's dark value become `#20201d`. `donnees.html` stays without script; its inline style takes the values.

**The operator's page**: see D-REDESIGN-005 (same table, its own file).

**Tests (T-REDESIGN-001).**
- `tokens.test.ts` pins the whole table above in `style.css`, per theme. Where a check proves a colour it reads
  the computed paint of the rendered element, not the token's text.
- `browser_smoke.py`: `MARKS` gains the main action; a new `check_primary(page, where)` asserts on an enabled
  `button.primary` that the computed fill is `rgb(242, 199, 68)` and the text `rgb(32, 32, 29)`, in both themes, on
  the sign-in, the intake and the final panel (where the secondary file action must not be yellow). A field's
  boundary is measured on an empty field of the sign-in and the intake, focused by the keyboard and not, and the
  check fails when the selector is absent. `GROUNDS` and the literal grounds in `terms_browser.py` take the new
  values.
- No resting surface has a blur or a shadow: on Accueil, Mes affiches, Styles and the intake, the computed
  `backdrop-filter` and `box-shadow` of each selector of the list above are `none`; in the step editor at 1440 px
  the same for `.rail` and its `::before` (`style.css` 309: the rail is a card, its blur goes).
- The review panel on a phone (360 × 640), with a poster long enough to scroll, after a scroll to the end: both
  approval buttons are inside the visible viewport and `elementFromPoint` at their centres returns them. The same
  for the final panel's actions.
- The poster guard of T-POLISH-002 and the confirmed file's bytes: unchanged, and they pass.

## D-REDESIGN-002 — The shops' shell (R-REDESIGN-002, 003)

**Three widths.** Over 1180 px: sidebar or rail, and the frame. 1180 px and under: the drawer. 720 px and under:
the bottom bar as well. Why 1180 and not 1080: with the rail (76 px) and the frame's gaps (24 px) the content is
then never narrower than 1081 px, the editor's present threshold for two columns (`style.css` 513). The chat's
side panel still comes from the 880 px query (`style.css` 775): at 1181 px beside the full sidebar its thread is
465 px, 11 px under today's narrowest (476 px at 880 px). That is accepted and tested, so no media query of the
editor or the chat changes.

**Structure** (`App.vue`; the template keeps several roots, no wrapper):

```
div.load-line, button.skip     as today
aside.side                     new. v-if="shown". position: fixed at every width
├─ button.side-close           « Fermer le menu », drawer only
├─ a.brand                     « Doka Studio — Accueil »: the horizontal logo of the theme; the D on the rail
├─ a.primary.new               « Nouvelle affiche », to #creer
├─ nav.nav                     aria-label « Navigation »: Accueil, Mes affiches + count, Styles + count
├─ section.recent              « Affiches récentes »: up to five links
└─ div.side-foot               a.credit-card, a.account, button.sign-out, button.theme-toggle (≤ 720 only)
div.scrim                      behind an open drawer
header.app-header              the top bar; still the sticky element with ref="appHeader"
├─ button.menu                 « Ouvrir le menu », ≤ 1180 │ button.rail-toggle, > 1180, not while editing
├─ a.mark                      the D, « Doka Studio — Accueil », ≤ 1180; not in the chat at ≤ 720
├─ p.top-title                 aria-hidden: the creator's poster name or « Nouvelle affiche »; > 720
├─ div.seg                     « Façon de créer », as today
├─ a.new-poster                « Nouvelle affiche », a plus: ≤ 720, in the chat only
├─ a.credits-pill              the balance
└─ button.theme-toggle         > 720, and at every width while signed out
main.gate / main               unchanged children; main.gate gains the horizontal logo above its content
nav.phone-bar                  new, ≤ 720: v-if="shown && !chatting && !editing"
```

**Layout.**
- `<html>` carries `data-shell` while `shown`, and `data-rail` when the rail applies: the kept choice, or `editing`
  (`doc && !chatting`) in every state of the editor, before and after a visual exists. CSS keys on them: `--side-w` is `0px`; over 1180 px with `data-shell` it is `288px`, with `data-rail`
  `76px`; `--gap` is `12px` over 1180 px with `data-shell`, else `0px`.
- Over 1180 px: `aside.side` is fixed at `inset-block: 12px; inset-inline-start: 12px; width: var(--side-w)` and
  scrolls inside itself on a short screen. `header.app-header` and `main` take `margin-inline: calc(var(--gap) +
  var(--side-w)) var(--gap)`; `body` takes `padding-block: var(--gap)`, `position: relative` and a minimum height of
  the window.
- **The frame** is `body::before`: absolute, `inset: var(--gap)`, as tall as the page, 28 px corners, a `--line`
  border, behind everything (`z-index: -1`, after the ambient field), no blur. Its background paints the sidebar's
  column (`--side-bg` from the left edge to `--side-w`, then a hairline, then nothing). It scrolls with the page:
  at rest the window looks like the mockup's; on a long page its top edge leaves and the top bar sticks at
  `top: 0`, as today. Nothing is clipped by it.
- The top bar stays `position: sticky; top: 0` in the page's flow, 64 px high plus the safe-area inset, its glass
  on its `::before` with the frame's top-right corner radius. `scroll-padding` and the stage's sticky offsets are
  untouched; the measured heights stay the truth once stuck. A notice sits under the bar wherever the bar is:
  `top: calc(64px + var(--gap) + env(safe-area-inset-top, 0px))`. Toasts are centred on the content column
  (`left: calc(50% + var(--side-w) / 2)`: the gaps are symmetric); the load line runs between the content column's
  edges.
- 1180 px and under: `aside.side` is the drawer: fixed, the window's height, `min(320px, 86vw)` wide,
  `--glass-strong`, blur and `--lift` on itself (it holds nothing fixed), moved off screen and `visibility: hidden`
  when closed. Motion on `transform`, none under `prefers-reduced-motion`.
- `nav.phone-bar` takes the rules the phone `.nav` has today (`style.css` 596–687: fixed to the bottom, safe-area
  padding, five columns); `.nav` keeps only the sidebar's list. The class is not `.tabs`: the editor's tab row owns
  it (`style.css` 314, 544, 569, 582, 817). `body:has(.chat.typing) .nav` (790) goes: the bar is not in the chat.
- The chat's `measure()` (`ChatView.vue` 428–430) stops looking for a fixed `.nav` and subtracts `body`'s bottom
  padding; its `- 12` and the visual-viewport sizing stay.

**The sidebar's content.**
- Counts keep today's guards: Mes affiches when `listKnown` (`activeTotal`), else the recent answer's `total` once
  it is read; Styles when `caps`. The account row shows `profile.name || 'Votre boutique'`. A cold Accueil
  therefore makes no new request (shop-dashboard.md's deferred reads and its smoke stay).
- `aria-current="page"`: Accueil, Mes affiches and Styles as today; never « Nouvelle affiche »; in « Affiches
  récentes », the row of the poster that is open.
- **« Affiches récentes »**: one reader, owned by `App.vue`: `sectionRead<Listing>('/api/creations?limit=5')`,
  passed to `ShopHome` as a prop (which no longer creates or clears its own, and keeps its « Réessayer » and its
  refresh). `App` reads it, and the balance, **once, after the first route has resolved**, each only when the
  screen that route opened does not read it itself (Accueil reads both): no watcher on `shown` or `loaded`, which
  fire before Accueil mounts and would send the request twice. It reads again after a poster is created, copied,
  confirmed, removed or restored. It is cleared where `funds.clear()` is (identity lost, `App.vue` 2013), and its
  answer is dropped by `sectionRead`'s turn counter when it arrives late. A failed or empty read leaves the
  section out.
- **A recent row is a real link**: `<a href="#…">` with the poster's own address (the one `openFromList` ends on
  for it), the thumbnail (`loading="lazy"`, 32 × 40, empty `alt`), the title, the state's French name. Nothing
  intercepts its click: `accountLink` sees it unprevented, then the hash change goes through `route()` and its
  questions (unsent photos, unsaved account), exactly as a typed address does. It never calls `openFromList`
  directly. Choosing the poster that is already open changes no address: the drawer closes and, at 1180 px and
  under, the focus returns to the menu button.
- **The rail**: labels are visually hidden and each link has a `title`; « Affiches récentes » is `display: none`;
  the credit card shows the number alone. The choice is `localStorage['affiche.rail']` (`'1'` or absent; nothing
  of a shop, ADR-108), read inside try/catch, set on `<html>` by `index.html`'s inline script before the first
  paint as the theme is. `api.test.ts`'s list of `App.vue`'s plain keys (469–471) gains exactly this key.
- **The gate**, three things kept apart. (a) *The shell*: everything of a shop in it is rendered with
  `v-if="shown"`, not only hidden: the recent links with their addresses and thumbnails, the account's name, the
  counts, the pill's number, the top title; `aside.side` and `nav.phone-bar` are absent while the gate is closed.
  (b) *A verification in progress* (the page shown again, another tab's sign-in): the hidden `main` keeps the
  shop's unsaved work as today (D-MULTI-SHOP-007); nothing of it is exposed, and it returns when the same shop is
  confirmed. (c) *After a sign-out or another shop's sign-in*: the present erasure, and the recent reader cleared
  with it. Signed out, the top bar holds the theme switch only and `main.gate` shows the horizontal logo (the file
  of the theme, 220 px, empty `alt`) above whatever it says.
- **Under a dialog.** `aside.side` and `nav.phone-bar` take the header's present predicate,
  `:inert="modalOpen || peeking"`: a keyboard cannot reach the sidebar or sign out behind the review, the final
  panel or the editor's full-screen look. The scrim is above the sticky top bar.

**The drawer's contract.**
- The menu button has `aria-expanded` and `aria-controls`. Opening moves the focus to « Fermer le menu ».
- Open: `button.skip`, the top bar, both `main` and the phone bar are `inert`; the scrim covers them.
- Escape, the scrim or « Fermer le menu »: closed, the focus back on the menu button.
- A destination: `accountLink` (`App.vue` 672) is bound on `aside.side` and `nav.phone-bar` as it is on the header
  today, and runs first. Then the drawer closes and nothing moves the focus to the menu button: the route gives it
  to the destination's `h1` (737), or to the question the departure raised (unsaved account, unsent photos), or to
  the dialog the destination opens.
- It also closes when `shown` turns false, when the window becomes wider than 1180 px, and when a dialog opens.
- Its state is in memory. No history entry: Back acts on the page (owner decision 7).

**The credits.**
- One handler for the pill, the sidebar's and the drawer's credit card and the editor rail's button. In the creator
  it remembers the element it came from (`event.currentTarget`, taken before the drawer closes) and calls
  `openCredits()` (the history-backed panel, `App.vue` 684);
  elsewhere the link goes to `#credits`. The two `ref="creditButton"` become that remembered element.
- Closing the panel (`App.vue` 774–780) focuses the front dialog if one is open, else the opener when it is still
  rendered and visible, else the menu button (the opener was in the drawer), else the pill.
- The pill's accessible name is `balanceLabel`; its text is the number, « Crédits » while unread. The balance is
  read once the gate opens when no screen has read it.

**Amendments recorded in ADR-123**: R-SHOP-DASH-008 (the product is named by the kit's logo: horizontal in the
sidebar, the drawer and the signed-out screens, the D in the top bar; the name is no longer typed beside it);
D-POLISH-003's phone bar; poster-editor.md 156–185 (one `.nav` in the header, glass on resting surfaces).

**Tests (T-REDESIGN-002).** A shared helper `go(page, name)` in `browser_smoke.py` uses the visible control at the
current width (sidebar, drawer, or phone bar); every direct `.nav a` click and « Créer » lookup is moved to it:

| Existing check | What it becomes |
| --- | --- |
| `browser_smoke.py` 812, 845, 919, 3034, 3055, 3305–3339 | `go()`; counts and `aria-current` read in the sidebar; the header geometry replaced by the checks below |
| `chat_browser.py` 159, 1105–1183 | navigation through `go()`; the composer-against-nav geometry becomes: no `.phone-bar` in the chat, the composer's bottom inside the visible viewport with the keyboard open and after blur |
| `terms_browser.py` 123, 214, 571; `share_browser.py` 717 | `go()`; the same assertions after it |
| `editor_refinements_browser.py` 71, 77, 82 | the draft-versus-saved shop name read in the sidebar's account row at 1440 px |
| `shop_dashboard_browser.py` 24–63, 84, 107–153, 196, 244–251, 465 | the logo, bar and title checks below; the shop's name read in the account row; the five content edges, the 860 px frame, the 16 px gutter and the title's focus are asserted as they are |

New checks, all in `shop_dashboard_browser.py` unless said:
- **Sticky after a document scroll** (Mes affiches with enough posters to scroll): at 1440 px, after
  `window.scrollTo(0, 600)` the top bar's `top` is 0, the sidebar's box has not moved, and the frame's left and
  right edges are 12 px inside the window; at 1024 px there is no frame and the top bar's `top` is 0. The bar's
  height is 64 px plus the safe-area inset. A notice shown at scroll 0 and after the scroll does not overlap the
  bar; a toast's centre is the content column's centre with the sidebar and with the rail. In the editor at
  1440 px: `editor_refinements_browser.py` unchanged, plus `--sticky-top` equal to the measured bars after a scroll.
- **Widths**: at 1181 px the sidebar shows; the editor, before and after a visual exists, has the rail, its columns
  of today and no sideways scroll; a chat with a poster has its side panel, a thread of 460 px or more and no
  sideways scroll; at 1180 px the menu button shows and the sidebar is not in the accessibility tree; at 721 px no
  phone bar; at 720 px the bar.
- **The logo and the font**: at 1181 and 1440 px the sidebar's logo is at least 220 px wide, `naturalWidth > 0`,
  the file of the theme, in both themes; no text « Doka Studio » beside it; a `FontFace` of the family Figtree has
  `status === 'loaded'` and a sidebar link's computed `font-family` starts with it.
- **The sidebar's tint**: the frame is a pseudo-element of `body`, which the contrast helper does not see:
  `tokens.test.ts` computes `--muted` and `--faint` on `--side-bg` over `--ground` from the pinned values, 4.5:1 in
  both themes.
- **The rail**: the toggle gives a 76 px sidebar, every link keeps its accessible name, a reload keeps it; forced
  in the editor; with `localStorage` throwing, the toggle works for the page. `tokens.test.ts` reads
  `index.html`: its inline script sets `data-rail` from `affiche.rail` inside a try, before the app's script.
- **The drawer** (1024 and 360 px): Tab and Shift+Tab stay inside; Escape, the scrim and the close button return
  the focus to the menu button; a destination puts the focus on its `h1`; with unsaved account edits a destination
  raises the present question and the drawer is closed; resizing to 1300 px closes it; the accessibility snapshot
  has one navigation landmark when open, none at 1024 px when closed.
- **Recent posters and departures**: in a chat with photos chosen and not sent, a recent row of another poster
  raises the present question, and « Annuler » leaves the chat and its photos as they were; from Mon compte with
  unsaved edits, a recent row raises the account's question; the row of the poster already open closes the drawer
  and changes nothing.
- **Under a dialog** (1440 px, the review panel, the final panel and the editor's full-screen look): Tab never
  reaches the sidebar; « Se déconnecter » cannot be activated.
- **The phone bar** (360 px): five items by accessible name in order; `BAR_JS` on the four labelled items; the
  centre action checked apart (a plus is painted, 44 × 44 px or more, name « Nouvelle affiche »); absent in the
  chat and the editor; inert under a dialog and under the drawer.
- **The top bar** (360 px, balance 12 345, long poster title): one row, 64 px or less, nothing cut, on Accueil and
  in the chat (menu, switch, plus, pill); at 800 px with the title.
- **The gate**, each case apart, with markers that differ per shop (name, poster title, balance): (a) signed out,
  and when a late answer arrives after a sign-out: `aside.side` and `nav.phone-bar` are absent and `HOLDS` finds no
  marker in the page's markup; (b) a verification in progress (`pagehide` then the page shown again) with an
  unsaved account edit: the shell is absent, `GATE_CLOSED` holds, and the edit is back when the shop is confirmed;
  (c) shop A signs out and shop B signs in: no marker of A anywhere.
- **The credits**: from the pill, from the editor rail's button and from the drawer's card, in the creator: the
  panel opens with the draft kept, and closing returns the focus to the pill, the rail's button, the menu button.
- **Cold starts**: a cold Accueil makes the requests it makes today, each once, counted before the smoke clicks
  « Actualiser » (the present assertion, tightened to counts); a cold Mes affiches makes one read of the five
  recent posters and one of the balance.

## D-REDESIGN-003 — The chat (R-REDESIGN-004)

`ChatView.vue`'s template and the chat's rules in `style.css` (688–798); nothing in `chat.ts`, `generation.ts` or
the server's sentences. Built on the shell (after T-REDESIGN-002).

- **Empty conversation** (no message of the owner, no poster): the first assistant bubble becomes a centred block:
  the D (decorative), `p.hello-q` « Quelle affiche créons-nous ? », the present greeting as its second line. Over
  1180 px the block and the composer are centred vertically as one group; under, the composer stays at the bottom.
  The page's `h1` stays the hidden one of T-POLISH-003.
- **The composer** (`form.composer`): one `--surface` box, a `--control` border, 24 px corners, the soft shadow of
  the mockup (`0 1px 2px rgb(0 0 0 / .04), 0 10px 24px -18px rgb(0 0 0 / .22)`), no blur. Rows: `.tray`; the error
  lines; the textarea with no border of its own (the box is its boundary and takes the focus ring with
  `:focus-within`); a tool row with the attach button (« Ajouter des images », its icon and the word « Photo » over
  720 px), the style choices (`.style-pill` × 3 or the « comme votre inspiration » pill, in a strip that scrolls
  sideways, while no poster exists), and `.send` at the right. `.chat-elsewhere-read` keeps its place. Whether the
  styles hide while typing does not change.
- **Messages.** `.bubble.me`: `--invert` fill in the light theme, `--raised` in the dark, on the right.
  `.bubble.bot`: no fill, no border, the D at its left (decorative). The wait bubble keeps its spinner.
- **A card with a button** (`ChatView.vue` 528–550). Every predicate and sentence stays: `limitOf`, the stop
  sentence when `state.credit.stop`, the features warning, the small-photo acknowledgement, `free(item)`, retry
  and resume with « ONCE », the alternate main actions of a result (« Vérifier » or « Télécharger ou partager »).
  The order of the DOM stays. The recap's facts become cells in one `--surface` box split by hairlines (one row
  when they fit, two columns under 480 px); the `small` lines under the buttons are 13 px in `--muted`. The cost
  line gets an `id` and the button's `aria-describedby` names it, beside the warning's `id` where there is one.
- **The side panel** (`.chat-side`, from 880 px as today): a `--surface` card with a hairline; the thread has no
  surface.

**Tests (T-REDESIGN-003, `chat_browser.py`).** At 1440 px an empty conversation's question and composer are inside
the middle half of the content column's height, and the composer is at the bottom after the first message; at
360 px it is at the bottom in both states. The tool row is one line with `.send` at its right edge at 360 px. At
1440 px a recap's cells share one row (equal tops). On a recap at 360 px with a long title and price, the cost line and its button are both inside the visible viewport at
once, the line is in the same card as the button and is the button's description. The paid change card and the
free change card: the first shows the cost line, the second does not. The composer's border and its focus ring are
marks at 3:1, required present; `check_marks` on the send button, resting and pressed; `check_contrast` with the
composer's placeholder required, both themes. The side panel at 1241 px is a surface with a hairline. Every
existing sentence assertion passes unchanged.

## D-REDESIGN-004 — The other screens (R-REDESIGN-005)

T-REDESIGN-001 already restyles them through the primitives. This task is what the primitives cannot do:

- **Mes affiches and Accueil's recent posters**: the state leaves the details line and becomes a `.badge` after the
  title's line, with `stateNames`' word: Brouillon (plain), À vérifier (`.warn`), Approuvée and Confirmée (`.ok`);
  the details line then reads « 289 000 Ar · 20 nov. 2026 · Conforme à la photo ». « Retirée » keeps its form.
  Accueil's attention groups keep theirs, with the `--warn` and `--bad` tokens.
- **Signed out**: `.sign-in` under the logo of D-REDESIGN-002, 420 px wide at most.
- **« Vos données »**: its values, as D-REDESIGN-001 says.
- Each screen keeps its `h1`, its focus on arrival, its 860 px frame and its 16 px gutter.

**Tests (T-REDESIGN-004).** `check_contrast` on every screen each smoke visits, both themes, with the badge
required on Mes affiches; a row's reading order (title, badge, details) and the badge's word for each of the four
states in `shop_dashboard_browser.py`; the present title and frame assertions unchanged.

## D-REDESIGN-005 — The console's shell (R-REDESIGN-006)

`frontend/src/admin/`: `Admin.vue`, `admin.css`, `admin.ts`; new files `Figtree-Variable.woff2` (with the font's
licence text beside it), `doka-horizontal-charcoal.svg`, `doka-horizontal-paper.svg`, `doka-symbol.svg` (the
kit's files; `brand.test.ts` pins their digests). `admin.test.ts`'s list of the folder's source files gains what
is added; its import rule is unchanged (`./file` is allowed, the build emits it under `/admin/assets/`).

- **Tokens**: the table of D-REDESIGN-001, each written once with `light-dark(<light>, <dark>)`;
  `:root { color-scheme: light dark }`, `:root[data-theme=light] { color-scheme: light }`,
  `:root[data-theme=dark] { color-scheme: dark }`. `brand.test.ts` pins the same values as `tokens.test.ts` does.
  The logo's file follows the same three cases.
- **Structure**: the three rules above and the same parts, written again in this folder: `aside.side` (fixed; logo,
  `a.primary` « New shop », `nav` « Console » with Shops, Payments, Service, then the theme switch, the actor and
  « Sign out »), `div.scrim`, `header.bar` (sticky; menu button or rail toggle; « Filter shops » on the Shops
  list), `main`, the frame on `body::before`. Sidebar over 1180 px, drawer under, with the drawer's contract of
  D-REDESIGN-002; the scrim is above the sticky bar, and everything else at the page's root is the drawer's
  background: the banner and the one-time password's controls included (`Admin.vue` 423, 458). No bottom bar;
  nothing fixed to the bottom. The rail's choice is in memory. `light-dark()` is for colours only: a gradient or a
  shadow is composed from colour tokens.
- **Routes**: unchanged in this task (`''`, `#`, `#/shops` → the list). « Payments » replaces « Money » as the
  screen's name and its link; its route stays `#/money`. « New shop » goes to `#/shops`, opens the existing fold
  and, once the route and the fold have settled, focuses its first field, also when already on Shops; the smoke's
  selector tells the sidebar's link from the fold's summary.
- **Theme**: a switch in the sidebar sets `data-theme` on `<html>` and `localStorage['affiche.admin.theme']`;
  reading `localStorage` itself is inside the try (in `walk_no_storage` the getter throws). Nothing stored: the
  device decides.
- **Every target 44 px at every width** (`SMALL_TARGETS_JS` runs at 1280 px too).
- **Shops**: the mockup's table: 12.5 px plain headers with no band, rows of one height on a hairline; first cell
  the identifier (the link, its accessible name exactly as today) with the shop's name under it; one state badge
  (`suspended`, else « no password », else `active`) beside today's mark of an unanswered request; the present
  values; figures right-aligned from 600 px; cards under 600 px (D-POLISH-004). « Filter shops » filters the rows
  on the page by identifier or name, says « No shop matches » when none does, and is cleared by emptying it.
- **One shop, Payments, Service**: their present content and order in `--surface` cards, one column.
- D-ADMIN-005's « both themes through `prefers-color-scheme`, the system's fonts » and its header (« Shops ·
  Service · Money ») are replaced by this section.

**Tests (T-REDESIGN-005, `admin_browser.py`; `admin.test.ts`; `brand.test.ts`).** The walk signs in to Shops as
today. The sidebar's links by exact name with `aria-current`; the rail and the drawer as for the shops' app
(1280, 1024, 360 px), Tab never reaching the banner or the one-time password's controls behind an open drawer.
`check_layout` on every screen at 360 and 1280 px in both themes. The « own files » assertion unchanged and
passing; a loaded `FontFace` of Figtree and a button whose computed `font-family` starts with it; the logo's
`naturalWidth > 0` at 1181 and 1440 px; colours asserted as computed paint; the identifier's cell the widest of its
row; `brand.test.ts` computes the sidebar's text on its tint from the pinned values (4.5:1, both themes). The 18
`emulate_media` steps run with nothing stored and assert the computed ground after each change;
apart, the switch: choose the other theme, change the device's scheme, reload: the choice holds. `walk_no_storage`
exercises the switch and the rail and still finds an unanswered request after a navigation. The numeric columns
by position on the new table; the filter by identifier, by name, with no match, cleared; a long name on a 360 px
card; a suspended shop with no password shows `suspended`; the sign-out error is found where it is shown now.

## D-REDESIGN-006 — Overview (R-REDESIGN-006)

A new view `Overview.vue` (the folder's list gains it), the console's home. Three reads the page already makes,
together, on arrival, on « Refresh » and when the tab is shown again: `GET /api/admin/shops`,
`GET /api/admin/service`, `GET /api/admin/payments` (no parameter: the current UTC month). No server change.

| On the screen | Contract |
| --- | --- |
| Active shops: N of M | `state === 'active'` over all items; M is the number of items |
| Credits outstanding: N, « ≈ $X at $Y an image » | `headroom.outstanding` credits; `cost` and `unit` are micro-USD (`unit` may be fractional, `cost` is the server's rounding): the page's present dollar formatter, the server's `cost` |
| Received in <month> (UTC): N Ar | `payments.received_ar`, a signed integer; the month named from the answer's `start` |
| Provider spend: $X of $Y, since <date>, a meter | `headroom.spent`, `headroom.cap` (micro-USD), `service.spend.since`; the figure is the real spend even when the meter is full; « since » is the cap's own period, not the month |
| Shops: the first eight by last poster, « View all N » | a copy sorted by `last_poster_at` descending, none last, then by identifier |
| Payments this month: the five latest | the answer is in ascending ledger order: the last five, newest first; signs, kinds and amount corrections as the Payments screen shows them |
| Service | `paused_since`; `commit` and `migration`; `backup` (may be null); `limits.shop_daily_spend_micros`, `limits.reads_per_day`; `failed_jobs_24h` |
| Needs you | an unanswered request (the page's reactive `kept`, which also holds what storage refused); `has_password === false`; `purchase_text.stored == null`; `backup == null` or `backup.late`; `failed_jobs_24h > 0`; `headroom.warning`. Each line links to the screen where it is settled or read |

- The four figures are one card split by hairlines, a label over each value, no icon: four across over 1180 px, two
  by two from 600 px, one column under.
- **Partial failure, one rule per input.** Each block renders from its own read; a failed read shows « Could not be
  read » and « Try again » in its blocks. « Needs you » has three inputs: Shops gives the missing passwords;
  Service gives the purchase text, the backup, the failed jobs and the cap warning; the page's memory gives the
  unanswered requests. Payments gives it nothing. It says « Nothing needs you » only when Shops and Service were
  both read; otherwise it lists what it knows and adds « Shops not read: passwords not checked » or « Service not
  read: purchase text, backup, jobs and cap not checked ».
- **Order of answers.** Each refresh takes a number; an answer of an older refresh is dropped (`adminApi.ts`'s
  epoch only covers a change of session), except a 401 of the present session, which follows the page's present
  path whatever its number.
- **Routes** (`admin.ts` `route()`, `Admin.vue` `load()`): `''`, `#` and `#/overview` → `{view:'overview'}`;
  `#/shops` → the list; a malformed hash → Shops, as today. After a sign-in the focus goes to the `h1` « Overview »
  only on a home entry: a 401 on a shop with a kept request still returns to that shop. `load()` gets its Overview
  branch. The sidebar gains « Overview » first.
- D-ADMIN-005's « Shops (the home) » is replaced by this section.

**Tests (T-REDESIGN-006).** `admin.test.ts`: the router's cases apart (empty, `#`, `#/overview`, `#/shops`, deep
links, malformed). `admin_browser.py`, on a store seeded with more than five payment lines, a moved payment, a
signed amount correction, a line of the month before, an offered grant, a non-round dollar cost, and shops whose
identifiers do not sort as their last posters do: the four figures and both lists against that store; each of the
six causes of « Needs you » present and absent, and its empty sentence; a failed `service` read (routed to a 500)
leaves the shops usable and no « Nothing needs you », and the line names the purchase text; a failed `payments`
read alone leaves « Needs you » as it is; an older refresh that answers after a newer one changes nothing, in both
orders of success and failure, and an older refresh's 401 still opens the sign-in; an unanswered request held in memory only is listed; the figures'
positions at 1280 px (one row), 800 px (two by two) and 360 px (one column).

## D-REDESIGN-007 — The record and the proof (R-REDESIGN-007)

By the lead, on `redesign` after `redesign-console` is merged into it: the whole suite, one smoke at a time;
`design_capture.py` with the console's Overview and the drawer and rail states added; both checkers;
`reviews/app-redesign-after-<date>.md` sets each screen beside its mockup state and lists every difference with
its reason; `DESIGN.md` rewritten from the code (Impeccable's `document`), its sidecar regenerated.

## Errors, edge cases, failure modes

| Case | Handling |
| --- | --- |
| A fixed dialog, toast or bar lands inside a box | Rule 1; the phone's review and final actions are hit-tested after a scroll |
| The editor's sticky bars or the chat's height break | Rule 2; the sidebar starts at 1181 px; `editor_refinements_browser.py` unchanged; the sticky checks after a document scroll |
| The balance read fails | The pill says « Crédits » and still opens Mes crédits, which has its own failure state |
| The recent read fails, or is empty | No « Affiches récentes » in the sidebar; Accueil keeps its retry |
| An answer arrives after a sign-out | `sectionRead`'s turn counter drops it; the shell's shop parts are not rendered |
| `localStorage` refuses (rail, the console's theme) | try/catch around the getter too; the choice lasts the page |
| A long shop name, 12 345 credits, 120 posters | The sidebar's rows cut with an ellipsis and keep the full name as `title`; the top bar and the phone bar are checked at 360 px |
| A dialog opens while the drawer is open | The drawer closes first |
| The console's three reads answer at different times, or one fails | Each block has its own state; refreshes are numbered; no false « Nothing needs you » |
| Forced colours | Borders and outlines are real; a badge has its dot and its word |
| A machine that cannot run two smokes at once | Each worktree has its own ports; at most one smoke per worktree and two on the machine; a timeout under load is rerun alone before it is believed (T-SUITE-FLAKE) |

## Tasks

| Task | What | Branch, worktree | After |
| --- | --- | --- | --- |
| **T-REDESIGN-001** | Tokens and primitives of the shops' app (D-001) | `redesign`, `app` | — |
| **T-REDESIGN-002** | The shops' shell (D-002) | `redesign`, `app` | 001 |
| **T-REDESIGN-003** | The chat (D-003) | `redesign-chat`, `chat` | 002 |
| **T-REDESIGN-004** | The other screens (D-004) | `redesign`, `app` | 002, beside 003 |
| **T-REDESIGN-005** | The console's shell, tokens, table (D-005) | `redesign-console`, `console` | —, beside 001 |
| **T-REDESIGN-006** | Overview (D-006) | `redesign-console`, `console` | 005 |
| **T-REDESIGN-007** | The record and the proof (D-007), by the lead | `redesign` | all |

Ownership is by file: 003 owns `ChatView.vue`, `chat_browser.py` and the chat's block of `style.css` (688–798);
004 owns the rows' markup in `App.vue` and `ShopHome.vue` and `shop_dashboard_browser.py`, and in `style.css` only
the library rows' rules (near 262), a region that does not touch the chat's; the console's tasks own
`frontend/src/admin/`, `admin_browser.py`, `admin.test.ts` and `brand.test.ts`'s console cases. `redesign-chat` is
merged into `redesign` by the lead when 003 and 004 are both done, before 007. Each task: one Opus implementer, the lead's own run of its checks, one Codex
review of the diff, a local commit on its branch.

## Owner decisions on their defaults

1. Suggestion chips are not built; proposed as T-CHAT-STARTERS.
2. The cost sentence stays in the chat, small. The mockup's shorter form (« Créer l’affiche · 1 crédit » on the
   button, the sentence only when the balance is unknown, waiting, low or empty) is possible on his word.
3. One shop is a page in one column, not a sheet. « Conditions pending » is not shown; proposed as T-ADMIN-TERMS.
4. The name is no longer typed beside the mark (R-SHOP-DASH-008 amended).
5. The bottom bar is not shown in the chat on a phone; the top bar has « Nouvelle affiche » there.
6. On a phone the theme switch is in the drawer.
7. Back, with the drawer open, acts on the page and does not close the drawer.
8. The composer has a visible edge, stronger than the mockup's.
9. What ships when: `redesign` is cut so that tokens (001), then the shell and the chat (002–004), then the console
   (005–006) could each be released alone.

## What the reviews changed

From the review (r1): the fixed-ancestor rule now names the review and final panels and is tested by hit-testing
(1); the drawer's and the credits' focus contracts (2, 3); the sidebar's values keep today's guards, so a cold
Accueil reads nothing new (4); one owner and one lifetime for the recent reader, shop parts not rendered behind
the gate (5); « Needs you » from `kept`, never a false all-clear, numbered refreshes (6); no wrapper, the frame on
`body::before`, checks after a document scroll (7); the widths 720/721, 1180/1181 (8); `nav.phone-bar` and the
centre action checked apart (9); the cost line described by its button and seen with it (10); Overview's contract
per field (11); the router's cases and the figures' one column on a phone (13); the missing criteria and weak
tests (14); the list of smokes that change (15); ownership by file, the shell before the chat (16); the console's
rail in memory, the amendments and the new French listed (17). Finding 12 falls: no server field is added.

From the devil's advocate: the work stays off `main`, in releasable steps (1); the phone's top bar is spelled out
and keeps a one-tap « Nouvelle affiche » in the chat, the theme switch goes to the drawer (2); no wrapper and a
fixed sidebar (3); Shops stays the console's home until Overview exists, one shop stays one column, the tokens are
written once with `light-dark()`, `terms_current` is dropped (4); the task order and one smoke per worktree (5);
the composer loses its blur, the rail is set before the first paint, thumbnails load lazily (7); the phone bar's
class (8). Refused: dropping Overview (the owner asked for a console and approved this one); splitting the shell
in two tasks (the drawer and the sidebar are one element); a fixed frame (content would pass over its edges; the
page-height frame needs no mask); a history entry for the drawer (it would enter `route()`'s departure rules);
the shorter cost line (decision 2).

From the second review (r2, approve with fixes; it ruled 8 of r1's findings closed and 9 partial): a recent row is
a real link through `route()`, so no departure question is skipped (1); the sidebar and the phone bar are inert
under a dialog (2); the gate's three cases are stated and tested apart, and the requirement no longer promises
more than the gate does (3); the rail is forced on `editing` in every state, and the chat's 465 px thread at
1181 px is accepted and tested (4); the toast's centre, the notice's offset, the load line and the 1024 px
assertion follow the real geometry (5); the shell's first reads have one trigger and are counted (6); « Needs
you » has one failure rule per input and a 401 is never dropped (7); the font, the paint, the sidebar's tint, the
table's first cell and the recap's cells are proven, the editor rail's blur goes (8). « Atelier » as a label and
the first-paint assertion are removed.
