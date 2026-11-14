**Verdict: APPROVE WITH NITS for the implementation.** The four r1 code findings are closed. Regression verification remains incomplete; I found no additional P1/P2 defect in the reviewed code.

**Remaining actionable issue**

- **P3 — Missing navigation to logo recovery.** In [App.vue:633](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:633), `mainFix` omits `staleLogo`. Changing framing in Réglages disables export and requests restoration, but provides no shortcut to Boutique, where restoration lives. **Minimal fix:** include `staleLogo.value` in the Boutique branch. For palette failures, prefer directing recovery to Style, where retry and the failure explanation are available.

**R1 code findings**

| Finding | Ruling | Evidence |
|---|---|---|
| #1 Saved boutique details opt themselves in | **CLOSED** | `loadShop()` resets all three flags; populated-profile reload coverage added. |
| #2 Automatic corner-logo conversion to seal | **CLOSED** | Automatic circle assignment removed; smoke explicitly selects seal mode. |
| #3 Returning to a footer version leaves corner placement | **CLOSED** | `logo_footer_box` restores historical geometry separately from strict corner reservations; transition scenario added. |
| #4 Expanded preview blocks short-screen editing | **CLOSED** | Short visual viewport hides proof/layers, retains fullscreen access, and cleans up its listener. Latest code also reveals focused fields; the test no longer scrolls them into place itself. |

These closures assess implementation, **not independently observed browser passes**.

**Earlier findings carried forward by r1**

| Finding | Ruling | Evidence / outstanding work |
|---|---|---|
| Requirements #1 — seal/legacy compatibility | **CLOSED** | Footer restoration and explicit seal-to-corner copy preserve the source. |
| Requirements #2 — stale-scene rules | **CLOSED** | Shared pre-export/pre-refinement guards retain text and revision checks. |
| Requirements #3 — actual composite review | **PARTIAL** | Review wording exists; actual original-logo rendering/collision coverage across both corners and all formats remains incomplete. Geometry tests alone do not establish it. |
| Requirements #4 — free preparation versus paid actions | **CLOSED** | Preparation remains free; generation retains explicit confirmation. |
| Requirements #5 — palette precedence/persistence | **CLOSED** | Displayed palette feeds generation; manual choices persist and invalidate pending sampling. |
| Requirements #6 — recovery/accessibility | **PARTIAL** | Missing-only import and mobile recovery implemented; focused profile-save/conflict failure coverage remains missing. |
| Design #1 — brand behavior marker | **CLOSED** | Server-owned marker persists through two-generation new/legacy refinement tests. |
| Design #2 — crop-aware logo guard | **CLOSED** | Client/server framing checks and restoration agree. |
| Design #3 — seal transitions | **PARTIAL** | Copy preservation is covered; explicit historical-disc reselection coverage remains missing. |
| Design #4 — shared normalization | **CLOSED** | Matching algorithms and shared Unicode vectors. |
| Design #5 — sampling races | **CLOSED** | Epoch invalidation plus delayed-decoder/manual-override coverage. |

A small simplification: remove the redundant `paletteBlocked` check from `mainAction.disabled`; `whyNoHeadline` already includes it. The latest API README now documents `logo_footer_box`, resolving the omission noticed during review.

The scoped `git diff --check` passed. Files changed concurrently during review; I inspected the late focus-handling, browser-test and README updates.

No files modified, delegation, browser/device/production commands, or store writes. Tests were not rerun; pending browser/full-suite results and the coverage gaps above remain the verification limits.
Implementation resolution: P3 fixed by routing stale-logo recovery to Boutique and palette recovery to Style; redundant paletteBlocked predicate removed. Expanded render and browser regression results are recorded in the final verification report/HANDOFF rather than attributed to this independent reviewer.
