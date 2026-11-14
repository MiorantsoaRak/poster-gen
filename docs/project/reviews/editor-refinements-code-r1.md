**Verdict: REQUEST CHANGES.** Four actionable findings remain.

1. **P1 — Saved boutique details still opt themselves in.** [App.vue:741](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:741)  
   `loadShop()` sets contact/logo inclusion from saved profile values. Sign-in, reload and `fresh()` therefore override the new off defaults whenever those details exist. The empty-profile scenario misses this.  
   **Minimal fix:** reset all three inclusion flags to false in this path; preserve the profile values. Cover a populated profile on reload and “Nouvelle affiche”.

2. **P2 — Intake still silently converts the corner logo into a seal.** [App.vue:782](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:782)  
   `createPoster()` first places the logo top-right, then assigns `shape = 'circle'` when logo/contact are selected without shop name. That defeats the approved corner default and can crop a rectangular original logo without an explicit seal choice.  
   **Minimal fix:** remove this automatic circle assignment for new posters; retain explicit seal selection and existing seal documents.

3. **P2 — Returning to a legacy footer version leaves the corner logo behind.** [App.vue:1218](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:1218), [visuals.py:328](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/visuals.py:328)  
   After moving a plain footer logo to a corner, selecting the older footer version restores neither its logo position nor size: it has neither `logo_box` nor `logo_disc`. The new guard then rejects export/refinement because the logo remains at the top without a reservation. The restore button is also unavailable for that version.  
   **Minimal fix:** expose and restore the historical plan’s footer logo geometry on selection, distinguished from a corner reservation. Cover footer → corner → footer.

4. **P2 — The expanded sticky stack exceeds short-screen space even while typing.** [style.css:498](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/style.css:498), [App.vue:1436](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:1436)  
   Static geometry gives approximately **299 px**: 56 px header + 165 px preview/toggle stack + 78 px sticky tabs. At a 282 px viewport, the focused field cannot fit below it. Typing hides the layer list but retains both preview buttons and the 96 px image. This is a code-derived finding, not a browser measurement.  
   **Minimal fix:** collapse the preview further when available height is insufficient; test focused-field visibility with the preview initially expanded.

Prior-review disposition follows. **CLOSED describes the implementation assessment, not an independently observed test pass.**

| Prior finding | Status | Evidence / remaining work |
|---|---|---|
| Requirements r1 #1 — seal/legacy compatibility | **PARTIAL** | Explicit seal copy exists; legacy footer restoration fails as above. |
| Requirements r1 #2 — stale-scene rules | **CLOSED** | Shared logo guard runs before render/refinement; baked-text and revision safeguards remain. |
| Requirements r1 #3 — actual composite review | **PARTIAL** | Composite-review wording added; all-format original-logo rendering/collision coverage remains incomplete. |
| Requirements r1 #4 — free preparation versus paid actions | **CLOSED** | New preparation paths do not enqueue paid work; confirmation remains explicit. |
| Requirements r1 #5 — palette precedence/persistence | **CLOSED** | Displayed palette feeds the plan/accent; overrides persist and sampling failures block generation. |
| Requirements r1 #6 — recovery and accessibility | **PARTIAL** | Missing-only import and copy improvements exist; short-screen regression and recovery-test gaps remain. |
| Design r1 #1 — brand behavior marker | **CLOSED** | Server-owned marker is inherited; latest diff includes legacy/new refinement-chain tests. |
| Design r1 #2 — crop-aware logo guard | **CLOSED** | Client/server require original framing; restoration and all-format guard tests exist. |
| Design r1 #3 — seal transitions | **PARTIAL** | Copy, historical-disc restoration and refinement coverage guard exist; transition regression tests remain missing. |
| Design r1 #4 — shared normalization | **CLOSED** | Matching normalization rules and shared vectors, including Straße cases. |
| Design r1 #5 — sampling races | **PARTIAL** | Epoch invalidation covers manual choices/retries; delayed-response regression coverage is missing. |

The scoped `git diff --check` passed. Your reported 103 backend tests, 150 frontend tests and build are prior verification; I did not independently reproduce them or treat the underway full backend/Chromium runs as passing.

No files changed, delegation, device/production commands or store writes. Tests/browser checks were not run; the findings above and pending regression evidence prevent approval.