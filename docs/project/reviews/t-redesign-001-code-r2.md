# T-REDESIGN-001 — code review, round 2 (Codex, 2026-11-20)

Reviewed: the uncommitted diff of the worktree `app` (branch `redesign`) after round 1's fixes. Verdict: APPROVE WITH FIXES. Its three points (the phone review panel's bottom clearance, the light theme's ambient field in the token test, one chat button's edge) were fixed by the lead; the clearance check was proven by switching the fix off.

**APPROVE WITH FIXES**

The glass and composer fixes address both high-severity findings. I’d fix the phone review panel’s bottom clearance before committing. The stronger action bar makes an existing layout defect more consequential: the buttons stay reachable while the final checklist items can remain underneath them.

### Round 1 rulings

| # | Ruling | Evidence |
|---|---|---|
| 1. Floating text contrast | **CLOSED** | The floating bars use `--glass-strong`, with alpha `.86` in light and `.88` in dark. Both poster pills use opaque `--surface`. The token test checks all three text roles over black and white in both themes. I found no remaining reference to a deleted glass or blur token, or a weaker text-bearing floating surface. `frontend/src/style.css:27,48,400,407,653,684` · `frontend/tests/tokens.test.ts:90` |
| 2. Composer boundary | **CLOSED** | The enclosing form gets `--control` at rest and `--text` on `:focus-within`. The desktop chat smoke requires that specific border to reach 3:1 against its surroundings in both themes, and verifies keyboard focus on the textarea. `frontend/src/style.css:775` · `frontend/tests/chat_browser.py:67,75,82,182` |
| 3. Token coverage | **PARTIAL** | The table, light sources, lift, hover and solid fallback are pinned. One override still escapes: only `dark.ambient` is asserted. A first `--ambient` declaration in the light selector passes both the duplicate check and the allowed-selector check, even if it replaces all three lights. Assert `light.ambient === dark.ambient` as well. `frontend/tests/tokens.test.ts:29,36,62,67,72` |
| 4. Colour parser | **CLOSED for the current palette** | Hover now uses a literal sRGB colour. Both checkers reject `color(srgb …)` and `color(srgb-linear …)` before extracting numbers. I found no ordinary computed value on these paths that should spuriously throw: transparent backgrounds resolve to RGBA, `currentColor` resolves on the measured colour properties, and gradients are scanned for stops. A `none` background image yields no stops. A missing required shadow or stroke correctly fails as unpainted. The smokes exercise the two app themes; forced-colour palette behaviour remains unverified. `frontend/src/style.css:31,112` · `frontend/tests/browser_smoke.py:97,105,198,210` |
| 5. Browser assertions | **CLOSED for the named checks** | The helpers now inspect the intended action, verify the painted theme, scroll the field into view, require the resting selectors, and compare action rectangles across a real panel scroll. The sharing smoke measures the named download separately. `frontend/tests/browser_smoke.py:419,435,463,480,493` · `frontend/tests/share_browser.py:1230` |
| 6. Chat button edges | **CLOSED for the three cited controls** | `.pic-role`, `.mods-toggle` and `.style-pill` use `--edge` and retain their state overrides. One adjacent omission remains: “Reprendre cette photo” is an action button whose border still uses `--line`. Use `--edge` there too. `frontend/src/style.css:740,759,781` · `frontend/src/ChatView.vue:524` |

### Commit and regression checks

**Fix the phone panel clearance.** The `padding` shorthand resets the `176px` bottom allowance declared twelve lines earlier. At maximum scroll, the fixed bar can cover the last verification point or the rejection form. Preserve the allowance on panels with an action bar and extend the smoke to verify the last in-flow item clears the bar. `check_reach` currently hit-tests only the buttons. Its `> 100` scroll requirement can also reject a correct panel with 1–100 px of genuine overflow. `frontend/src/style.css:651,663` · `frontend/src/App.vue:2366,2396` · `frontend/tests/browser_smoke.py:498`

I found no current `check_resting` false failure. It does inspect off-screen and inert cards, and it reads pseudo-element effects even when `content: none` prevents painting. Those are potential false failures if styles change. `frontend/tests/browser_smoke.py:278,285,488`

**The poster and sharing rulings hold.** The pills cover portions of the thumbnail or generation preview, but both are DOM siblings of `PosterCanvas`. Their opaque fills cannot enter the canvas or exported PNG. The large-view rule hides the ordinary preview badge. The canvas guard and confirmed-byte comparison remain intact. Phone header blur stays on `::before`, and the review panel retains its opaque ground without a new fixed-position containing block. Share remains primary while ready or preparing, with download promoted on fallback. `frontend/src/App.vue:2294,2370` · `frontend/src/style.css:484,609,614` · `frontend/tests/browser_smoke.py:3133,3648`

Read-only review. Builds, tests and browser smokes remain for the lead. No files changed, and no device, production, store-writing or paid commands ran.