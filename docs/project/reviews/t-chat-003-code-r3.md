**REJECT.** Job attribution is fixed, but operation admission still permits duplicate spending and loss of read recovery.

| Round-2 finding | Ruling | Reason |
|---|---|---|
| 1 — Replacement while an operation remains unresolved | **PARTIAL** | The timeout is gone; a transient 404 can still authorize replacement. |
| 2 — Timestamp-based job attribution | **CLOSED** | Recorded job IDs and request-key lookup establish ownership. |
| 3 — Cross-tab read retries | **PARTIAL** | Ordinary locked tabs are serialized; unmounting and the no-lock fallback remain unsafe. |
| 4 — Canvas measurement after remount | **CLOSED** | Post-render host watches reconnect both observers. |
| 5 — Existing poster’s stale unpaid recap | **CLOSED** | Returning imports the document’s title and price; spent cards remain unchanged. |

1. **P1 — A 404 cannot authorize a new paid operation.**  
   [ChatView.vue:256](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:256), also `clear()` at line 221.

   Reload while `/scenes` is still in transit or uncommitted. Lookup returns 404, so reconciliation offers another card with another key. Its preflight can also return 404 immediately before the original request commits.

   The server’s active-job guard prevents overlapping jobs on the same poster, but does not establish per-wish uniqueness. On a poster already containing a rejected version, the original job can complete during the replacement’s remaining preparation. Subsequent scenes do not automatically advance the document revision, so the replacement can then pass both revision and active-job checks and pay again.

   **Smallest fix:** treat 404 as unresolved after an ambiguous send. Preserve and replay the original scene’s key, body and revision; offer a new key only after a definite refusal or terminal job outcome. Another lookup cannot close this race.

2. **P1 — Ownership is checked before asynchronous work, not immediately before sending.**  
   [ChatView.vue:222](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:222), [App.vue:1086](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:1086).

   `clear()` checks ownership, then awaits earlier-key lookups without checking again. Afterwards, `generateScene()` awaits `savePlan()`, which can perform HTTP requests. Stealing the lock during either interval does not prevent the old tab from submitting `/scenes`.

   I reproduced a send after ownership became false during an earlier-key lookup. Losing ownership during poster creation **before entering `clear()`** is correctly stopped.

   **Smallest fix:** finish plan saving and asynchronous lookups first, then perform a synchronous ownership check immediately before the scene mutation.

3. **P1 — An unmounted chat can delete the new owner’s pending read.**  
   [ChatView.vue:312](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:312), also line 169.

   Switching to steps during a read releases the lock without clearing `owner`. Return to chat, recover that read, and start another message while the original response remains delayed. When the unmounted component receives its old answer, its local key comparison succeeds: it removes the newer shared pending record and overwrites the thread with its stale copy.

   I reproduced the newer pending key disappearing. Reload then loses the newer read’s replay identity, allowing another paid reading.

   **Smallest fix:** invalidate ownership before releasing the lock; ignore asynchronous continuations after ownership/lifecycle loss. Clear shared pending state only when its stored key matches the completed request. Apply the ownership guard to the unsent-text watcher too.

4. **P1 — Missing Web Locks restores the double-read race.**  
   [ChatView.vue:299](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:299).

   Both tabs grant themselves ownership. Retrying the same settled `read_failed` card simultaneously creates two fresh keys. I reproduced two requests with distinct keys. Their separate answers can subsequently produce separate scene cards and posters.

   **Smallest fix:** fall back to Pas à pas when Web Locks are unavailable, or supply real serialization. Unconditional ownership is unsafe.

5. **P3, optional — Redundant observer setup.**  
   [App.vue:931](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:931).

   The explicit `watchSticky()` call in `adopt()` duplicates setup now handled by the rendered-host watcher. Remove that call; retain the adapter.

The new route’s authorization looks sound: middleware requires a session, SQL filters by that session’s shop, keys are validated, and responses are `no-store`. It returns stored bodies from **all mutation kinds**, including historical profile, creation, style and confirmation responses. Sign-in/sign-out do not use `mutate`; passwords and session tokens are not exposed through this table. Cross-shop isolation lacks a dedicated new test.

The `availableHeight` watch can change editor scrolling on **any visible-height change**, including keyboard closing, browser chrome, rotation or window resizing, when a focused panel field is clipped. It aligns that field beneath the sticky area. Ordinary typing does not trigger it, and scrolling does not directly change either watched dependency: I found no direct reactive loop. The reported passing runs support the keyboard fix but do not prove behavior on physical keyboards/browser chrome.

Verified: complete diff inspection, `vue-tsc --noEmit`, `git diff --check`, and targeted in-memory reproductions using the transpiled component.

Not rerun: Vitest, pytest, build, browser smokes or device checks; no files, stores, servers, network, production or `.env` were touched.  
Remaining risk: duplicate paid operations and lost pending-read recovery.