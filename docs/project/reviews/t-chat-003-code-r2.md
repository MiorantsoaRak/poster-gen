**REJECT.** Two tabs can still pay twice for one wish. Recovery also relies on job attribution that the server has not established.

| R1 # | Ruling | Current code |
|---|---|---|
| 1 | **PARTIAL** | The migration pointer works normally; the 30-second replacement path still permits duplicate spending. |
| 2 | **PARTIAL** | Typing preserves the pending read. Another tab can still replace or clear its record. |
| 3 | **PARTIAL** | Spent cards no longer replay old scene keys. An unresolved operation can still become a fresh paid card. |
| 4 | **PARTIAL** | Recorded job IDs work; the timestamp fallback can attribute another operation’s result or miss its own. |
| 5 | **CLOSED** | Uploaded asset IDs and the owner bubble are saved before the read leaves. |
| 6 | **PARTIAL** | Pre-creation form corrections transfer back. Corrections to an existing poster leave unpaid recaps stale. |
| 7 | **CLOSED** | `fresh()` clears visuals; a new chat requires a creation before showing them. |
| 8 | **CLOSED** | Download is offered only for the selected approved visual. |
| 9 | **CLOSED** | Scene-time validation offers the agreed « Corriger dans Pas à pas ». |
| 10 | **CLOSED** | The phone editor bar contains « Continuer par message ». |
| 11 | **CLOSED** | Small-photo consent resets on thread, product-name and product-photo changes. |

Remaining and new findings, by severity:

1. **P1 — Thirty seconds without a job does not establish that nothing will be sent.**  
   [frontend/src/ChatView.vue:236](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:236), also 244–246.

   A starts creation and remains awaiting its response for over 30 seconds. B loads the spent card, finds no creation or migration pointer, and offers a new recap with a new UUID. B starts its poster; A then resumes. Both can submit scenes under different keys and creation IDs.

   I reproduced both scene starts using the compiled component in memory. Server idempotency and `image_job_running` do **not** close this case: the keys and posters differ.

   **Smallest safe fix:** serialize the operation across tabs and keep replacement blocked while its owner remains unresolved. Elapsed time must not authorize another paid card. Also, `reconcile(true)` currently bypasses the grace period for ambiguous exceptions; those are not proof of refusal.

2. **P1 — `cardFate` still guesses causality from timestamps.**  
   [frontend/src/chat.ts:97](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/chat.ts:97), [frontend/src/ChatView.vue:189](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:189).

   The Date-header adjustment helps ordinary clock skew, but it does not establish job ownership. A clock correction after the last response can leave `tapped` ahead of the actual job. Once that job has completed, recovery reports `none` and offers another paid scene; the active-job guard then finds nothing.

   Conversely, an unrelated step-editor job after the tap—or even up to two seconds before it—can become this card’s result. The active-job shortcut also adopts a job without checking existing card ownership. `taken` is ignored for explicit `item.job` matches, so it does not enforce exclusive ownership.

   **Smallest safe fix:** retain an unknown outcome until the job can be matched to the original request identity. Expose that identity in the server job list and preserve it through the small-photo dialog. Increasing the timestamp tolerance cannot fix attribution.

   The claimed job-list read occurs **before** `adapter.start()`, poster creation, palette work and plan preparation—not immediately before `/scenes`.

3. **P1 — Cross-tab read retries can create two paid keys and lose pending recovery.**  
   [frontend/src/ChatView.vue:174](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:174), [frontend/src/ChatView.vue:270](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:270).

   Two tabs retrying the same failed read before receiving each other’s storage events both create a fresh key. The server admits distinct keys independently. I reproduced two requests for the same retry with different keys.

   Additionally, storage events unconditionally replace `pending`, including while that tab is reading. Another tab’s deletion can erase an unresolved record; a subsequent network failure then produces a card without « Réessayer ». This was also reproduced in memory.

   **Smallest fix:** serialize retry admission across tabs, re-read the shared operation under that lock, and preserve each active `{key, body}` locally. Clear shared pending state only when its key matches the completed request.

4. **P2 — Returning from chat remounts the editor without reconnecting canvas measurement.**  
   [frontend/src/App.vue:1475](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:1475), [frontend/src/App.vue:925](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:925).

   Chat now unmounts the editor. Its canvas observer is installed only by `adopt()`, but switching modes for the same poster returns without calling `adopt()`. A poster opened in chat therefore reaches steps without a canvas observer; an editor reopened after chat retains an observer on the detached host.

   `canvasWidth` consequently remains stale. In particular, the phone’s enlarged preview can use the default 540-pixel width and clip the poster.

   **Smallest fix:** bind and disconnect the observer through a post-render watch of `canvasHost`, including every remount.

5. **P2 — An existing poster’s unpaid recap can contradict the generation input.**  
   [frontend/src/ChatView.vue:98](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:98), [frontend/src/App.vue:1332](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:1332).

   After a failed first attempt leaves a draft and replacement recap, correct its title or price in steps and return. `importForm()` exits because a creation exists. The recap retains the old values, while generation uses the edited document.

   **Smallest fix:** expose the current document’s offer through the adapter and refresh unpaid recaps on explicit mode return. Preserve spent-card history.

For the reported **360×282 failure**, I found no direct height increase caused by the new icon: it shares the existing no-wrap, 56-pixel bar and reduces title width. The viewport assertion remains intact. Its isolated failure is unverified; two later passes do not establish its cause. Finding 4 is a separate concrete regression introduced by mode switching.

Keep the adapter. Remove the elapsed-time authorization and timestamp ownership heuristic when fixing recovery; no broader refactor is needed.

Verified: `vue-tsc --noEmit`, `git diff --check`, and targeted in-memory reproductions. Files remained untouched; no `.env`, server, network, paid or application-store access occurred.  
Not rerun: Vitest, build, browser smokes or device checks. Remaining material risk: duplicate charges and incorrect result attribution.