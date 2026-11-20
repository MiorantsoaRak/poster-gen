# App redesign — design review, round 2 (Codex, 2026-11-20)

Reviewed: `designs/app-redesign.md` v2. Verdict: APPROVE WITH FIXES. Its findings are applied in the design (« What the reviews changed »).

**APPROVE WITH FIXES.** The wrapper-free shell is viable, and all six « Needs you » causes are available without a backend change. The main remaining risks are losing the shop’s departure guard through a recent-poster link, exposing shell controls behind a dialog, and applying viewport breakpoints to a materially narrower content column. T-REDESIGN-001 and 005 can proceed independently once their shared token and drawer contracts are corrected. Neither needs to wait for Overview.

### Round 1 rulings

`D` and `R` refer to lines in [design v2](docs/project/designs/app-redesign.md) and [requirements v2](docs/project/requirements/app-redesign.md).

| # | Ruling | Evidence |
|---|---|---|
| 1 | CLOSED | D27–31, 78–81, 101–103 preserve the panel scrim, prohibit containing-block effects on fixed ancestors, and hit-test actions after scrolling. |
| 2 | PARTIAL | D187–196 specifies dismissal and focus, but binding the account guard to a bubbling ancestor does not guarantee it runs before a recent link’s handler. |
| 3 | CLOSED | D198–205, 246–247 replace both refs with the actual opener, retain the history-backed panel, and specify visible fallbacks. This matches `App.vue:684,774,2136,2206`. Capture `event.currentTarget` before closing the drawer. |
| 4 | PARTIAL | D165–167 preserves deferred profile and Styles reads. It nevertheless hides the poster count until `listKnown`, even after the five-recent answer supplies `total`. `dashboard.ts:5`, `App.vue:1242`. |
| 5 | PARTIAL | D170–185 gives `App.vue` ownership, invalidation and shell removal. Initial request deduplication and the distinction between temporary concealment and sign-out still need precise checks. |
| 6 | PARTIAL | D361–382 covers reactive `kept`, partial failure and numbered refreshes. The failure copy omits one Service check and leaves a Payments-only failure unspecified. |
| 7 | PARTIAL | D138–154 preserves the sticky containing block. Its toast centre, initial notice offset and 1024 px frame assertion disagree with its geometry. |
| 8 | PARTIAL | D108–112, 161–162 fixes drawer subtraction and preserves visual-viewport sizing. The full-sidebar chat still enters wide mode below its previous available-width threshold. |
| 9 | CLOSED | D158–160, 234–240 gives the phone bar its own class and checks the accessibility tree, focus traversal, plus glyph, name and target separately. |
| 10 | CLOSED | D268–285 preserves the paid/free predicates and requires the same card’s cost and button to be visible together and programmatically associated. `ChatView.vue:530,535,547`. |
| 11 | CLOSED | D352–360, 376–383 specifies units, UTC period, ordering, signed corrections and discriminating fixtures. `admin.py:122,294,305,314`, `admin.ts:41,281`. |
| 12 | CLOSED | D348–350 and R135 drop pending conditions. No change to the list, detail or create response is necessary. |
| 13 | CLOSED | D319–322, 363–383 preserves deep links and malformed-hash fallback, handles New shop focus and asserts actual KPI positions. |
| 14 | PARTIAL | R84,95 and D268–301 settle the thread and badge questions. The proposed checks can still miss fallback fonts, a blurred pseudo-element, an incorrect identity-column width and wrapped desktop recap cells. |
| 15 | PARTIAL | D211–220 inventories most navigation changes, but the old header `.shop-label` assertion survives outside the cited ranges. `shop_dashboard_browser.py:84`. |
| 16 | PARTIAL | D412–423 orders shell before chat correctly, but 003 and 004 still share `style.css` unless row styling is assigned elsewhere. |
| 17 | CLOSED | D177–180, 207–209, 318 and R145–148 settle rail persistence, editor amendments and new control labels. |

### High severity

**1. A recent link can bypass a departure decision.** Home’s `openFromList()` directly loads and adopts a poster. The unsent-photo check lives in `route()`. `accountLink()` ignores an already-prevented event, so calling `openFromList()` or preventing the default in a child before the sidebar’s bubbling handler defeats D191’s ordering. Use a real poster hash appropriate to the destination mode, run the account guard before consuming the link, and pass poster changes through the unsent-photo decision. Test recent A→B with staged photos, dirty Account→recent, cancellation, and selecting the already-current destination, which generates no hash change to restore focus. `App.vue:672,717,729,747,1229`; D174–176,191–195.

**2. Closing the drawer does not make the persistent sidebar inert.** Today the header explicitly becomes inert during a custom modal or editor peek. Moving its controls into an earlier sibling removes that protection. A desktop keyboard user could navigate or sign out behind review or final confirmation. Apply the background-inert predicate to the sidebar and phone bar for every foreground custom dialog and peek, and layer the scrim above the sticky header. In the console include the root-level banner and one-time-password controls in the drawer’s background. Test keyboard traversal with those controls present. `App.vue:888,2130,2284,2358`; `admin/Admin.vue:423,458`; D118–135,187–195.

**3. R52 promises more DOM erasure than D181 delivers.** Inserting the `aside` before the header is safe. The header already has preceding siblings, `measureSticky()` uses `appHeader`, and skip/focus query the visible `main`. `GATE_CLOSED` accepts an absent element, while `HOLDS` scans the entire markup. During temporary identity verification, the existing hidden `main` can retain the current shop’s unsaved editor or Account. Specify shell DOM absence, whole-page concealment during verification, and prior-identity erasure after sign-out separately. Preserve unsaved work. Test pagehide/reverification and A→B with distinct markers. `App.vue:530,737,2007,2109,2128,2147,2152`; `browser_smoke.py:1354,1357,1670`; D243–245.

### Medium severity

**4. The 1180 calculation works for the editor under a specific predicate.** At 1181 the rail leaves 1081 px before main gutters. Force it on `editing` (`doc && !chatting`), including after a visual exists, when `stepping` becomes false. The actual desktop `.work` has three tracks. With the full sidebar, chat gets 869 px before gutters, 829 after ordinary gutters, and a 465 px thread after its 340 px panel and 24 px gap. That is indeed 11 px below the old minimum thread, but the 880 px viewport query still selects wide mode. Either explicitly accept and test that narrower thread or select the panel from available width. Exercise editor states before and after generation, populated chat at 1181, and classic scrollbar widths. `App.vue:465,496,603,2193`; `style.css:209,303,513,775`; D108–112,227,284.

**5. Separate frame painting from viewport offsets.** With transparent `body`, relative positioning and default `z-index:auto`, the two `-1` pseudo-elements share the root stacking context. The later `body::before` paints above the ambient `html::before`. Neither Vue component depends on `body` as an `offsetParent`. Chat’s rectangle already includes the top padding; subtract the bottom padding once and retain its existing 12 px allowance. Main margins leave fixed sheets, panels and the native modal viewport-relative. The content midpoint is `50% + side-w/2` because the gaps are symmetric; the proposed toast is 6 px too far right. Give the load line content-column **edges**. Position notices below the actual header bottom, including initial padding and safe area. Keep measured sticky heights for the stuck state. Expect zero frame gap at 1024 and allow inset height above 64. `style.css:48,51,95,216,222,455,468,833`; `App.vue:530`; `ChatView.vue:428`; D139–162,223–226.

**6. Cold-read proof permits duplicates.** `openShop()` sets `loaded` before routing; `view` starts as `opening`. A shell watcher can start a five-recent or balance read before Home mounts and calls `refresh()`. `sectionRead` rejects obsolete answers but issues every request. Give initial reads one trigger after route resolution, retain explicit refresh/retry, and count cold requests **before** the smoke clicks Actualiser. Use the recent total when known. `App.vue:585,2025`; `ShopHome.vue:16`; `dashboard.ts:16`; `shop_dashboard_browser.py:261,277,287`.

**7. Overview needs one failure rule per input.** Password comes from Shops; purchase text, backup, failed/interrupted jobs and cap warning come from Service; unanswered requests come from reactive client memory, including storage refusal. Payments supplies no attention cause. Keep R107’s conservative all-clear gate, name Payments when it alone failed, include purchase text when Service failed, and process a current-session 401 before dropping an obsolete refresh result. `admin.py:129,135,305,314`; `api.py:482,489`; `admin/Admin.vue:51,99,223`; `admin/adminApi.ts:14`; D361–369.

**8. Theme and acceptance checks need stronger evidence.** `light-dark()` for colours fits the import allowlist and all 18 system-theme calls. Compose gradients and shadows from colour tokens. Assert computed **paint**, an actual loaded Figtree face and its use on a control. `fonts.check()` alone can succeed with fallback. Check the sidebar tint behind text: the contrast helper skips the transparent body’s pseudo-element. Require the full role table, the widest identity cell, desktop recap cell positions, and removal of `.rail::before` blur. Hide the D specifically in phone chat as R66 requires. `admin.test.ts:12,20`; `admin_browser.py:106,187,1216`; `browser_smoke.py:105`; `style.css:309`; D91–100,128,277–285,327–343.

### Delivery and cuts

**001 beside 005:** independent worktrees are sound. Settle the shared token expectations and drawer contract first. The working TODO already marks 001 in progress. **003 beside 004:** safe after 002 if 003 owns global chat CSS and 004 uses scoped row styles or styling landed in 001. Name the chat-branch merge before 007. `TODO.md:118,124`; D387,414–423.

Remove unused « Atelier », the unsupported “before `DOMContentLoaded` proves first paint” assertion, and duplicate frame measurements at drawer widths. Keep the sidebar, drawer and Overview. Real-device paint, enlarged text and screen-reader focus remain owner checks under R142–144.

Static working-tree review only. No files changed and no build, test, browser smoke, device, production, store-writing or paid operation ran.