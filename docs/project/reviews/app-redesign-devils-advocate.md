# App redesign — devil's advocate (Opus subagent, 2026-11-20)

Challenged: `designs/app-redesign.md` v1. What v2 took and refused is in the design's « What the reviews changed ».

I found eight points that would change a decision in the design or its task plan. The most decision-changing come first. Line numbers are as of today's working tree. Nothing was run except reading files and read-only git commands; where a number is my own arithmetic rather than a measurement, I say so.

**1. There is no release unit, and every task merges into `main`.**
- **Decision challenged:** each task is merged into `main` (design :309, :311). The design never says what ships, or when.
- **Against it:**
  - The deploy ships whatever is checked out, as long as it is already on `origin/main` (`deploy.py`:9, :118-119). `main` is 12 commits ahead of `origin/main` and holds the interface polish, which is not deployed. If the redesign lands on `main`, one push carries both.
  - The owner has no Android phone at hand (ADR-121, `HANDOFF.md`:48). So the first real-phone look will be the pilot shop using the live site.
  - The phone checks are left to the owner (requirements :123). The yellow button seen in daylight is still the open check from ADR-122 (`reviews/interface-polish-devils-advocate.md`:10).
- **Instead:**
  - Merge into an integration branch; `redesign-app` and `redesign-console` already exist at `944192d`. Keep `main` on the polish until the owner deploys it.
  - Cut releases that can each be reverted, with a tag for each:
    - R1 = T-001 (and 004's badges) on today's shell. It is visual only, and it is the biggest speed gain on a cheap phone (point 7).
    - R2 = the phone shell and the chat.
    - R3 = the wide frame and rail, and the console. The console is used by the owner only, so it can go out at any time.
  - Before R1, check on a real phone: the yellow main button and the yellow send button side by side, in daylight at low brightness; the dark cards `#2b2b27` on `#20201d` with a 10% hairline on a cheap LCD screen; a dark poster on the new dark ground.
  - Before R2, check: the drawer with Android's Back gesture (point 2), the 360 px top bar with the phone's text-size setting raised, the floating bottom bar over Chrome's toolbar and the gesture bar, and the chat with the keyboard open.
- **Cost:** branch and tag discipline, and one owner look per release. No code.

**2. The phone top bar at 360 px does not fit, and the chat on a phone loses one-tap « new poster ».**
- **Decision challenged:** the phone top bar holds menu, D, title, « Message / Pas à pas » switch, credits pill and theme switch (D-002 :97-102; R-003); there is no bottom bar in the chat (owner default 5).
- **Against it:**
  - Today's 360 px creator row is already at its limit: logo with the typed name, sign-out, the two switch buttons, theme (`shop_dashboard_browser.py`:52-60; `style.css`:793-798). It already grew to two rows once (`HANDOFF.md`:69; `chat_browser.py`:1167).
  - The design swaps the logo-plus-name (about 86 px) and sign-out (44 px) for menu (44) + D (32) + a pill showing « 12 345 » (about 70 or more). That is roughly 20 px more on a row with no slack. This is my estimate: Figtree could not be measured here, because the font file needs a decoder that is not installed.
  - The mockup's phone bar has no « Message / Pas à pas » switch, and it was checked at 390 px, not 360 (mockup `README.md`:67).
  - Today, « Créer » in the phone chat starts a new poster in one tap (`App.vue`:2136, :723). Under the design it takes two (menu, then the drawer). That is the main loop: success is measured by "whether the shop returns for its next offer" (`PRODUCT.md`).
  - Today the credits panel pushes a history entry, so Back closes it (`App.vue`:684-689). The drawer is "in memory only" (design :129), so Android Back leaves the screen. In the chat with unsent photos, that raises the discard prompt (`App.vue`:717-720).
- **Instead:**
  - At ≤720 px, move the theme switch into the drawer; it is set once per device.
  - In the creator, hide the D and put a « Nouvelle affiche » plus button in the freed slot: menu, switch, plus, pill.
  - Decide what Back does with the drawer open: either a history entry that is replaced when a destination is chosen, or a stated "Back leaves the screen".
- **Cost:** R-003's third bullet changes, about 3 CSS rules and one link. The 360 px header tests are being rewritten anyway.

**3. The shell structure: right idea (the window keeps scrolling), wrong wrapper.**
- **Decision challenged:** a `div.shell` wrapper holding the sidebar, header and main, a frame as tall as the page, a sticky sidebar inside it, and a drawer that slides by `inset-inline-start` (design :86-117).
- **Against it:**
  - The tree puts `header.app-header` and `main` side by side directly under `.shell`. If `.shell` is a CSS grid, as in the mockup, the top bar stops sticking. The code's own note says "a grid item can only stick inside its own row" (`style.css`:514-515). The design does not say whether `.shell` is a grid.
  - The frame differs from the mockup on every screen that scrolls. Its top corners scroll away, and after any scroll the top bar sits at y = 0 while the sidebar sticks at y = 12.
  - Sliding the drawer by `inset-inline-start` forces a re-layout and a re-blur on every frame. A transform is safe here: the drawer holds nothing `position: fixed`; the no-transform rule only matters for ancestors of `main`.
- **Instead:**
  - No wrapper. `aside.side` is `position: fixed` at every width; sidebar and drawer then use one positioning mode.
  - `header` and `main` stay where they are in the DOM, with `margin-inline-start: var(--side-w)` over 1080 px. `main` gets no new ancestor, so the no-blur rule needs no policing.
  - `measureSticky`, ChatView's `measure()`, `scroll-padding` and the toasts at 64 px keep working unchanged.
  - The frame becomes one fixed layer behind the content, like `html::before` (`style.css`:51). It then looks like the mockup at any scroll position. Its one visual cost is content passing the frame's bottom edge; check that in a capture.
  - Keep the forced rail in the editor and the 1080/720 breakpoints. By my arithmetic from `style.css`:303 and :777, at 1366 px the editor's stage is about 682 px with the rail, against about 782 today and about 470 with the full sidebar. The chat's thread is about 610-650 px, close to today's 680 px maximum.
- **Cost:** about the same CSS, a smaller `App.vue` diff, and one class of layout bug removed.

**4. Console: defer Overview and `terms_current` (T-006).**
- **Against it:**
  - There is one pilot shop and no invitations yet, so Overview repeats Shops, Service and Money.
  - It adds a backend field and its tests to a redesign meant to be presentation only (design :8-9).
  - It needs a three-read page with partial-failure handling and seven "Needs you" causes to test.
  - It rewrites the smoke's sign-in landing and keyboard walk (`admin_browser.py`:161, :993-994, :1089-1092). It also reverses D-ADMIN-005's "Shops (the home)" (`admin-dashboard.md`:526).
  - D-005, which is T-005 in wave 1, already routes `''` to Overview and expects its walk to land there (design :221-223, :242). But `Overview.vue` arrives in T-006, wave 2, so T-005 cannot pass its own walk.
  - The one-shop two-column grid (design :236-237) shows History to the right of forms that come after it in the DOM. Review r1 finding 9 flagged exactly that mismatch (`interface-polish-design-r1.md`:31).
- **Instead:**
  - T-005 restyles the console's shell, tokens and table only. Shops stays the home, the routes are unchanged, and one shop stays one column.
  - Bring Overview back when a second shop is invited.
  - If the theme switch stays, write the console's tokens once with `light-dark()` and `color-scheme` (the console only runs in the owner's modern browser), not in three blocks (design :228-230).
  - Copy the Figtree licence file along with the 20 KB font.
- **Cost:** the console's home differs from the approved mockup for now; the owner must hear that as a choice.

**5. The task plan collides in places the design does not name.**
- **Against it:**
  - The style.css regions overlap: T-002 owns 785–835 and T-003 owns 688–798 (design :312-313).
  - T-002 is given the chat's height code in `ChatView.vue` (design :143-144) and `chat_browser.py` 1105–1169 (design :149). T-003 edits the same `walk_phone` test (design :185-188).
  - The cross-stylesheet test that compares `style.css` and `admin.css` is in T-001 (design :70-71). It fails until T-005 merges.
  - The plan implies smokes running side by side, but `HANDOFF.md`:58 says one smoke at a time on this 6 GB machine. The suite's fixed 10 s waits already fail under load (T-SUITE-FLAKE, `TODO.md`:115).
- **Real order:** T-001 comes first, then everything else. T-003 depends only on T-001: `measure()` takes the first `.nav` in the DOM, which becomes the sidebar's non-fixed nav, so the chat still sizes itself correctly. T-004 is mostly carried by T-001's primitives.
- **Instead:**
  - Run T-001, then run T-003 and a phone-first T-002a in parallel. T-002a is the top bar, the drawer at every width and the bottom bar; a drawer at every width is a valid state to ship.
  - T-003 owns `ChatView.vue`, `chat_browser.py` and style.css 688–798.
  - Then T-004, then T-002b (wide sidebar, rail and frame) in parallel with T-005.
  - Move the cross-stylesheet test to T-005.
  - Implementers run smokes one at a time across the machine, for example behind a lock.
- **Cost:** one more task row, and some waiting time.

**6. Keeping the cost sentence: R-BALANCE-001 is used as an excuse.**
- **Decision challenged:** the « Not built » row on the mockup's « Créer l'affiche · 1 crédit » (requirements :115; owner default 2).
- **Against it:**
  - R-BALANCE-001 reads: "Every button that makes an image says « 1 crédit » and shows what is left" (`prepaid-balance.md`:23).
  - The mockup's button says it on the button itself, which is closer to the letter than today's small line under it (`ChatView.vue`:547).
  - In the normal state, the always-visible pill carries what is left.
  - But the pill shows only what is available (`App.vue`:41). The unknown, pending, three-or-fewer and zero states carry more than the pill (`generation.ts`:64-71). Product principle 2 requires telling waiting credits from spent ones.
- **Instead:** label the button « Créer l'affiche · 1 crédit » (and the change buttons the same way, `ChatView.vue`:535). Show the small line only when `credit()` returns anything other than the plain normal sentence.
- **Cost:** about 6 cost-line assertions in `chat_browser.py` (:191, :537, :609, :694, :795, :1972). The button-name checks are not exact matches, so they survive the new label.
- **The other refusals:**
  - Suggestion chips: the refusal is right, but the real reason is accuracy, not "a paid call to check it". « Une promotion » invites discounts the app must not invent, and « Prix plus grand » needs a new paid scene when the price is drawn (ADR-044).
  - One shop as a sheet: right.
  - « Money » kept over « Payments »: an excuse, since the operator is the owner who approved « Payments ». Either way it costs 2 lines (`Admin.vue`:450, :500) plus 3 test lines; follow the mockup or ask him.

**7. Performance and other gaps the design does not see.**
- **The blur count is the strongest argument for shipping T-001 first.** Today every button and every field blurs (`style.css`:68-69, :119-120), plus ten resting surfaces (:227-228) and every style tile (:338). After T-001, only the bars, the drawer, sheets and toasts blur.
- **The composer:** D-003 makes it an opaque surface (design :170) while D-001 keeps its blur (:51-52). The blur paints nothing; drop it.
- **The rail on load:** `data-rail` must be set by the inline script in `index.html` (:9-14), as the theme is. Otherwise every page load jumps the sidebar from 288 px to 76 px for someone who chose the rail.
- **Recent posters in the drawer:** their thumbnails need `loading="lazy"`, so phones on mobile data don't fetch five images on every page load.
- **No change needed:** the installed app's colour (the manifest's yellow `theme_color`), right-to-left (French and Malagasy are both left-to-right), and the keyboard order (the skip link at `App.vue`:2129 covers the sidebar's tab stops).
- **Not verified:** Android Chrome's text scaling at 360 px.

**8. Test churn: the design already keeps the cheap selectors; one new name collides.**
- **Mostly unavoidable:** keeping `nav.nav` for the sidebar keeps 11 desktop `.nav a` lookups alive (`browser_smoke.py`:812–3229). No structure keeps both the desktop and phone lookups, and the geometry tests must be rewritten under any sidebar shell.
- **The collision:** `nav.tabs` reuses the editor's `.tabs` class (`style.css`:314, :544, :569, :582, :817). The bar would inherit `overflow-x: auto`, a background and a 16 px bottom margin. The overflow would clip the raised centre button, and `BAR_JS` counts the bar as clipping its labels. Use another name, such as `nav.phone-bar`.
- **« Créer » → « Nouvelle affiche » is not gratuitous:** it is in the approved mockup, and the link really starts a fresh poster (`App.vue`:723). It costs about 14 one-line test edits. But today « Créer » is marked as the current page whenever any poster is open (`App.vue`:2136). « Nouvelle affiche » must not be; say which item is current then, presumably Mes affiches.

**Tasks**
- **T-REDESIGN-001:** keep. Goes first, ships alone as R1 after a phone look. Its cross-stylesheet test moves to T-005.
- **T-REDESIGN-002:** change. Split into 002a (phone top bar without the theme switch, drawer at every width sliding by transform, phone bar not named `.tabs`, recent posters) and 002b (fixed sidebar and rail, fixed frame, forced rail in the editor). No `.shell` wrapper. Hand `ChatView.vue` and `chat_browser.py` to T-003.
- **T-REDESIGN-003:** keep. Runs beside 002a once 001 lands. Owns `ChatView.vue` (including `measure()`), `chat_browser.py` and style.css 688–798. Adopt the shorter cost line if the owner agrees.
- **T-REDESIGN-004:** keep. Small: badges and the sign-in card. Can run beside 003 after 001.
- **T-REDESIGN-005:** change. Console shell, tokens and table only. Shops stays the home, routes unchanged, one column for one shop. Theme switch through `light-dark()` or dropped. Takes the cross-stylesheet test.
- **T-REDESIGN-006:** drop for now. Defer Overview and `terms_current` until a second shop is invited.
- **T-REDESIGN-007:** change. Capture and report per release unit, on the integration branch rather than `main`.
