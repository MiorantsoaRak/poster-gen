**REJECT**

- **P1 — Work continues after ownership is lost.** [App.vue:1387](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:1387) resumes after `pickVersion()` and changes `refinement` without another `owned()`. `revise()` also enters a scene pipeline whose awaits lack ownership checks: after `flush()`, [App.vue:1073](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:1073) can call `prepareScene()` and POST `/plans` under the lost token. In-memory probes reproduced both paths. `sending` blocks the later image request, but does not satisfy ADR-097’s requirement to stop before further changes or sends. Carry the guard through these continuations; test takeover during saves and plan preparation.

- **P2 — Missing selection is reported as success.** [App.vue:1402](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:1402) discards `choose()`’s `false` result. Consequently, [ChatView.vue:401](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:401) can close a successful paid card while the previous image remains selected. A probe confirmed that `select()` resolves without selecting anything or invoking `owned()`. Reuse the strict `pickVersion()` path so reconciliation retains the card and reports the failure.

- **P3 — Permanently missing versions produce endless replacement cards.** [ChatView.vue:351](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:351) calls `again()` for the adapter’s “version gone” refusal. Offer the steps route instead of another identical card that can only refuse.

Declared deviations: **1, 2, 5, 6 and 7 are acceptable**. Restoration requires an explicit new tap; it creates no automatic loop. **3 is acceptable for texts switched off**, but has the permanent-refusal issue above. **4 needs the selection fix**.

The old-card conversion, saved-before-read path and exact kept-request replay look consistent. The smokes genuinely assert no `/scenes` request with texts off, and the old request’s body and key. Their takeover test covers listing refresh only.

One pre-existing constraint gap: `App.vue` statically imports `PosterCanvas`, which imports `fonts.ts`. The smoke checks font downloads, not module loading; the literal “never loads `fonts.ts`” claim is unproven.

Verification: three isolated, mocked probes reproduced the findings; `git diff --check` was clean.  
Not run: Vitest, build or browser suites, including the greeting rerun. No files changed; runtime integration remains unverified.