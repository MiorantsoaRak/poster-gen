# T-REDESIGN-001 — code review, round 1 (Codex, 2026-11-20)

Reviewed: the uncommitted diff of the worktree `app` (branch `redesign`). Verdict: REJECT, with fixes inside the task.

**REJECT** — The new glass makes phone navigation and approval text unreadable over some posters. The composer also misses the explicit 3:1 field-boundary requirement. Both can be fixed within the CSS-only scope of this task.

### High severity

1. **Text on floating surfaces fails contrast over real content.** `frontend/src/style.css:397`, `:539`, `:649`, `:680`. The poster badge sits directly over the image. Scrolling can also put a poster or product photo behind the fixed bars. Over white, dark-theme `.62` glass gives **3.73:1** for `--text`, **2.74:1** for `--muted`, and **2.23:1** for `--faint`. Over black, light-theme `.66` glass gives **6.79**, **3.73**, and **2.85** respectively. The final panel’s instruction uses muted text, as do inactive phone navigation labels. Blur cannot improve a uniform white or black backdrop. `frontend/tests/browser_smoke.py:106` walks DOM ancestors, so it misses a poster painted underneath a sibling bar. **Fix:** keep the specified `--glass` token, use `--glass-strong` or an opaque backing where text can overlap arbitrary content, and check black and white backdrops in both themes. **Departure 8 is a defect.**

2. **The chat input has no 3:1 boundary at rest.** `frontend/src/style.css:707`, `:770`, `:781`. The textarea has no border of its own. Its enclosing composer gets the same 10% hairline as a card. D-REDESIGN-003 includes a later composer test, but R-REDESIGN-001 explicitly includes this field, and each task is intended to be releasable. **Fix:** give `.composer` `border-color: var(--control)` now, retain its focus rule, and measure the enclosing form at rest and on keyboard focus. **Departure 9 is a defect.**

### Medium severity

3. **The token test misses four rows of the design table.** `frontend/tests/tokens.test.ts:8`, `:14`. The actual CSS matches both theme columns, including the mockup’s gradient stops and lift shadows. The test omits the three ambient lights and their composition, `--glass`, `--glass-strong`, and `--lift`. Its regex reads only the first matching rule, so a later base-theme override can silently win. **Fix:** assert the missing values and resolve all applicable base declarations in cascade order, using CSSOM or a CSS parser. Keep the reduced-transparency override as a separate case.

4. **The colour parser can manufacture a passing ratio.** `frontend/tests/browser_smoke.py:96`, `:194`. Ordinary Chromium `color(srgb r g b / a)` with decimal channels works, including fractional alpha. The regex drops minus signs, splits exponents, reads percentage alpha as a number out of 100, and leaves channels above 1 unbounded. Its prefix also accepts `srgb-linear` as gamma-encoded sRGB, while `display-p3` contributes a spurious `3`. Separately, `MARKS_JS` still extracts only `rgb()`/`rgba()`. **Fix:** recognize the supported serializations exactly, parse signed numbers and alpha, and explicitly convert or reject unsupported spaces and out-of-range values. Use the same parser for marks. Add small cases for fractional alpha, negative channels and `srgb-linear`. **Departure 2 is a defect in the checker.** The reported hover contrast itself is correct.

5. **The new browser assertions can pass against the wrong element or state.**

   - `frontend/tests/browser_smoke.py:256`, `:414`. `check_primary` accepts any matching main action in the document. An inert editor action behind the final panel can satisfy it if the intended button loses `.primary`. `checkVisibility()` also accepts off-screen boxes. **Fix:** pass the expected action locator within the active form or dialog and assert its paint directly. For sharing, assert the named download’s paint independently.
   - `frontend/tests/browser_smoke.py:260`, `:452`. `check_resting` misses `::before` shadows, opacity of the fill, and the visible hairline. A transparent, borderless card passes. It runs in the current theme only, and the calls omit required surfaces such as `.shot`, `.facts`, `.comparison figure` and `.job-state` where those surfaces appear. **Fix:** require the expected selectors on their respective screens, check computed fill, border, element and pseudo-element effects, and repeat in both themes.
   - `frontend/tests/browser_smoke.py:400`, `:430`, `:460`. `check_field` correctly fails on an absent selector and verifies actual keyboard focus. Its rest measurement can still inspect an off-screen box. `both_themes` changes the attribute without verifying the painted ground. `check_reach` correctly fails for missing, off-screen or covered controls **at scroll end**, but an ordinary button in document flow can pass there too. **Fix:** verify the theme’s computed ground, bring the named field into view before measuring, and compare action coordinates before and after scrolling for the fixed-panel contract.

### Lower severity

6. **Some chat controls still use the card hairline as a button edge.** `frontend/src/style.css:736`, `:755`, `:776`. The interactive photo-role button, modifications toggle and style chips retain `--line`; the design assigns `--edge` to these roles. Use `--edge` on the buttons and preserve their selected-state styling. **Departure 4 is acceptable for the listed replacements**; these remaining consumers need the same role audit.

### Calculated contrast

Ratios use sRGB compositing. Each value is against the named background.

| Foreground and background | Light | Dark |
|---|---:|---:|
| Warn / ok / bad ink on matching state fill | 7.41 / 6.92 / 6.29 | 7.91 / 8.45 / 7.04 |
| Default text on warn / ok / bad fill | 14.42 / 14.08 / 14.03 | 11.67 / 11.98 / 12.76 |
| Text / muted / faint on active over ground | 12.43 / 6.82 / 5.21 | 10.92 / 8.02 / 6.51 |
| Text / muted / faint on active over surface | 13.75 / 7.54 / 5.77 | 9.40 / 6.90 / 5.61 |
| Muted / faint on raised | 7.20 / 5.51 | 7.92 / 6.44 |
| Disabled primary label on raised | 5.51 | 6.44 |
| Charcoal on hovered Signal | 7.83 | 7.83 |

**Departure 10 is acceptable.** The dark wait bar calculates to **6.58:1** against its composited track. The existing 6.57 floor is intact.

### Remaining rulings and scope

- **1 and 3 are acceptable.** The explicit secondary-button primitive specifies transparent fill and `--edge`. Its use on the secondary download preserves the share hierarchy. Flipping the intake blur assertion enforces the approved change. I found no lowered contrast threshold or removed poster guard.
- **5 and 6 are acceptable.** The bot bubble loses its shadow, the composer retains the soft shadow, and the send button uses the signal edge. The new badge dot excludes the frame and uses a border that survives forced colours. The existing poster state dot remains separate.
- **7 is acceptable.** Dark `--invert-ink` remains readable in its remaining uses. I found no absolutely positioned control relying on `.rail` as its containing block. No blur moved from a pseudo-element onto an ancestor of a **displayed** fixed control. `.stage.peek` already blurred and hides its descendant `.main-action`; `.confirm` adds no filter; the review and final panels retain their opaque ground and scrim. The phone header still puts blur on `::before`. `main` gains no containing block.
- I found no dangling deleted glass token, new light-ground yellow text or yellow carrying white text. The reduced-transparency and reduced-motion fallbacks still make both glass roles opaque and disable blur. Share remains first while ready or preparing; the download remains available on failure, unsupported browsers and earlier confirmations. Both HTML files use the intended grounds, and `donnees.html` remains script-free. The diff stays within the seven named files.

Read-only review. I calculated contrast independently and did not run builds, tests, browser smokes, device commands or paid calls.