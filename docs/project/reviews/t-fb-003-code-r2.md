# Code review r2 — T-FB-003: publishing a confirmed poster on the shop's Facebook Page

Reviewer: Codex, read-only, 2026-11-21. Verdict: APPROVE WITH FIXES (both P1 and three P2 of round 1 closed, one partial; two new P2). The three fixes are in the code; not reviewed again. The four restore checks listed OPEN belong to T-FB-004.

Five round‑1 findings are closed. The lost-answer message still claims a publication line exists when the history refresh fails or another tab created the newest line.

### Round‑1 findings

| Finding | Ruling | Evidence |
|---|---|---|
| P1 · Backward clock | **CLOSED** | Admission and history both use `rowid DESC`, so backdating B cannot make A the latest publication. `facebook_publish.py:86,155` |
| P1 · Shutdown | **CLOSED** | The lifespan awaits `drain()` before closing the service, disposing the engine and releasing the data-folder lock. `facebook_publish.py:215`, `api.py:586` |
| P2 · Stale poster | **CLOSED** | On `facebook_stale`, a changed revision or confirmation render closes the sheet and invokes `openFinal`. The browser walk covers an edit from another tab. `App.vue:1871`, `share_browser.py:1487` |
| P2 · File error and lost answer | **PARTIAL** | `export_missing` keeps its own sentence. If the POST and history GET both lose their answers, the sheet still promises a line. A newer row from another tab can trigger the same claim. Use neutral wording such as « La réponse n’est pas arrivée. Vérifiez l’historique avant de réessayer. » `App.vue:1863,1883,1894` |
| P2 · Earlier-version history | **CLOSED** | Earlier previews retain history and the two `unknown` controls. The browser walk checks seven rows and no publish button. `App.vue:2648–2652`, `share_browser.py:1501` |
| P2 · Image before publishing | **CLOSED** | Both the button and its handler require a successful image load. A failed load offers « Réessayer ». `App.vue:1856,2621–2627` |

### Round‑1 test gaps

| Gap | Ruling | Evidence |
|---|---|---|
| Suspended shop with session intact | **CLOSED** | Exercises admission and the route, asserting zero rows and zero sends. `test_facebook_publish.py:275` |
| Missing PNG | **CLOSED** | Unlinks the file and checks `503 export_missing` with no write or send. `test_facebook_publish.py:223` |
| Backward clock | **CLOSED** | Backdates B, rejects a sheet that saw A, and asserts list order `[B, A]`. `test_facebook_publish.py:289` |
| Shutdown with a detached send | **CLOSED** | Cancels the caller during the send, awaits `drain()`, then verifies settlement and an empty task set. `test_facebook_publish.py:421` |
| Restore clears connections | **OPEN** | Deferred to T‑FB‑004. `TODO.md:167` |
| Restore copies a missing publication | **OPEN** | Deferred to T‑FB‑004. `TODO.md:167` |
| Restore takes the kept database’s settlement | **OPEN** | Deferred to T‑FB‑004. `TODO.md:167` |
| Restore carries the Facebook mode | **OPEN** | Deferred to T‑FB‑004. `TODO.md:167` |

### New findings

- **P2 · The 30-second send deadline still uses wall time.** If the handler stalls for 45 seconds and the clock moves back one minute, the computed age is negative and the photo is sent. Capture a monotonic timestamp at admission and use it for the elapsed-time check. [facebook_publish.py:205](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/facebook_publish.py:205)
- **P2 · « Annuler » stays active after the owner taps « Publier ».** It dismisses the sheet while the send continues, and the sheet-identity check then discards the response handling. Keep the sheet open during submission and label the pending action « Publication en cours… ». Apply the same guard to Escape. [App.vue:2619](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:2619) · [App.vue:2627](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:2627)

Read-only review. No suite or smoke results counted.

**APPROVE WITH FIXES**