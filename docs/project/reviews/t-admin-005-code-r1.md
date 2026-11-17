**APPROVE WITH FIXES.** Four P2 findings; no P1 found. The changes are bounded, but session cleanup and asynchronous responses need fixing before acceptance.

1. **P2 — A generated password survives a 401 in memory and the DOM.**  
   [Admin.vue:37](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/admin/Admin.vue:37), [Admin.vue:187](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/admin/Admin.vue:187)  
   `failure()` changes the session but retains `shown`; `v-show` merely hides its containing element. The password is not visible or keyboard-accessible on the sign-in screen, but remains readable in the DOM and reappears after sign-in. Reproduced with an in-memory check. Preserve unfinished non-secret inputs if required, but clear the generated password on authentication loss. Also dismiss an open confirmation, which currently sits outside the hidden view. Add a 401 test while a password is shown.

2. **P2 — Responses arriving after sign-out restore cleared secrets and shop data.**  
   [Admin.vue:89](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/admin/Admin.vue:89), [Admin.vue:121](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/admin/Admin.vue:121)  
   Start creation, sign out while its response is delayed, then release the response: `show()` restores the generated password and `loadShops()` repopulates data despite `authenticated: false`. Reproduced in memory. Pending reads can likewise restore cleared data. Invalidate callbacks from an earlier authentication state; checking only the current boolean is insufficient if another sign-in has occurred meanwhile. Test delayed creation and reads across sign-out.

3. **P2 — A lost sign-out response is presented as a definite failure.**  
   [Admin.vue:83](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/admin/Admin.vue:83)  
   A timeout, network failure or 5xx produces **“Not signed out”**, leaves the dashboard visible and performs no session re-read. The server may already have revoked the session. Show an uncertain outcome, conceal sensitive content locally and re-read session status. Test a committed sign-out whose answer is lost.

4. **P2 — An action’s result can appear under the wrong shop.**  
   [Admin.vue:133](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/admin/Admin.vue:133)  
   Confirm suspension for A, navigate to B while it is pending, then receive A’s answer: B displays “Suspended…” through the shared `accessResult`. Refusals and uncertain-outcome messages have the same problem. Reproduced in memory. Associate completion messages with their shop/request and display them only in that context. Add a delayed-response navigation test.

Your seven deviations:

| # | Ruling |
|---|---|
| 1 | Accept. Answering through buttons and `cancel`, with the guarded `close` fallback, handles the queued-event problem reasonably. |
| 2 | Accept for sign-in, creation and access actions: each has a real code guard against ordinary repeated activation. Sign-out has no busy guard. |
| 3 | Keeping unfinished inputs matches the design; keeping secrets behind `v-show` needs fixing as above. |
| 4 | Surviving view changes is consistent with the panel’s lifetime. Surviving authentication loss should change. |
| 5 | Accept: operator-only dollar limits are explicitly designed. |
| 6 | “En attente” matches the specified screens. `AbortSignal.timeout` compatibility still needs checking against the intended phone/browser baseline. |
| 7 | Accept for this task. `no-cache` permits caching with revalidation; immutable caching would be a performance improvement, not a correctness fix. |

Static review found no HTML injection sink, secret storage/logging, new dependency or cross-import between the two applications. Crafted hashes resolve to a bounded numeric shop route or the list. The build configuration follows the approved separate-pass layout. Production Vue devtools are disabled by the installed plugin’s default.

`vue-tsc --noEmit` passed. The smoke covers substantial normal behavior, but misses the session races above. Copy intentionally leaves the password on the clipboard after Close/sign-out; browser or OS clipboard history is outside the panel’s cleanup.

Not checked: suite counts, builds/hash identity, browser smokes, real phone/password-manager/autofill behavior, screen reader or back/forward cache. No files changed; no device, production, deployment, store-writing commands, `.env` or `data-probe` access.