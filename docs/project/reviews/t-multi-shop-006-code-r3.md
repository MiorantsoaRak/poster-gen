**Verdict: REJECT.**

1. **P1 — Failed restoration can still lose the paid request.** [chat.ts:256](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/chat.ts:256), [ChatView.vue:385](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:385). If restoration’s thread write fails, startup continues with the stale spent card lacking its request. The chat marks it concluded and saves that copy. On the next restoration, “concluded” wins and `kept` is deleted. **Reproduced using actual ChatView startup in memory.** This violates ADR-097/098 and the amended invariant. Keep the richer card available to the chat when persistence fails; do not conclude from the stale copy.

2. **P2 — Cleanup retry can erase a newly signed-in session’s data.** [App.vue:1606](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:1606). Hold the retry’s session answer after it reports nobody; sign the same shop into another tab and write new drafts; then deliver that answer. The retry deletes the newly written keys. The existing test signs in *before* requesting the check, missing this race. Serialize the session recheck and cleanup with `affiche-identity`.

3. **P2 — Canvas and palette decode failures omit the required session check.** [PosterCanvas.vue:48](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/PosterCanvas.vue:48), [palette.ts:47](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/palette.ts:47). Undecodable successful responses fail without calling `verify()`. The global handler cannot cover the detached canvas image’s `blob:` URL or `createImageBitmap()`. Both branches produced zero session checks in memory. Add the recheck on decode failure, as the round-2 amendment requires.

Previous findings:

| Review | Rulings |
|---|---|
| R1 | #1 **CLOSED**; #2 **CLOSED**; #3 **PARTIAL** (finding 1); #4 **CLOSED**; #5 **CLOSED**; #6 **CLOSED**; #7 **PARTIAL** (finding 2) |
| R2 | #1 **CLOSED**; #2 **PARTIAL** (finding 1); #3 **PARTIAL** (finding 3); #4 **CLOSED**; #5 **PARTIAL** (finding 2) |

The live-thread snapshot precedes unmounting. All inspected session GETs reach `settle()`. Cookie tests exercise controlled cookie changes and desktop Chromium lock serialization; their documented runtime limits remain appropriate.

No files changed. `git diff --check -- frontend backend` passed.  
Not checked: full suites, build or browser smokes under these read-only constraints; reported passes remain unverified.