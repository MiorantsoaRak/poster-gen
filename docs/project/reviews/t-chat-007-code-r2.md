**REJECT**

- **P1 — Ownership checks still miss continuations inside plan helpers.** [App.vue:1042](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:1042) awaits `flush()` without checking ownership before `/plans`, then applies its response without checking again. [App.vue:1083](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:1083) likewise applies a plan revision after an unchecked await. A delayed-response probe reproduced `acceptPlan()` and `planSignature` changing after takeover, before the outer guard throws. Pass `owned` into `prepareScene`, check inside these continuations, and update `planSignature` only after the check. **The missing save/plan takeover regression tests block this round:** this is an active defect.

- **P2 — Strict selection can block the chat indefinitely.** [ChatView.vue:403](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:403) treats `GONE` like a temporary selection failure. A succeeded job whose result remains unlisted retries every ten seconds forever; its open card disables sending and offers no recovery action. Reproduced with mocked reconciliation. Handle the known succeeded job’s unavailable result explicitly, offering « Pas à pas » while retaining its key/request. Listing absence must not trigger a replacement paid attempt.

- **P2 — The dynamic canvas import claim is false (pre-existing constraint gap).** [App.vue:3](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:3) statically imports `PosterCanvas`, which imports [fonts.ts through PosterCanvas.vue:6](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/PosterCanvas.vue:6). The existing app bundle also statically imports the separate canvas chunk. Chat avoids mounting the canvas, but eagerly loads its modules. Only `ChatView` is dynamically imported.

Round 1: **P1 PARTIAL; P2 CLOSED; P3 CLOSED.** Missing selection now rejects; `conclude(GONE)` offers steps without another change card.

Exact request replay, card-key usage, spent-before-send, old layer-price handling and server-supplied words look consistent. Optional `owned` preserves editor callers’ behavior; no broader refactor is needed.

Verified: isolated in-memory probes and `git diff --check`; no files changed.  
Not rerun in this read-only sandbox: Vitest, build or browsers. The lead’s results remain reported evidence; takeover safety remains unresolved.