**REJECT.** The normal single-tab flow has useful guards, but cross-tab recovery can create two paid scenes for one wish. Read retries can also lose their idempotency key, and several reload paths lose data or cannot resume.

**Rulings on the eight divergences**

| # | Ruling |
|---|---|
| 1 | **Accept.** The recap can confirm the displayed product/photos/price. The separate fidelity review remains required. |
| 2 | **Accept the glue.** Restoring the reference and waiting for/falling back from the palette are necessary. Reset the low-resolution agreement between products; see finding 11. |
| 3 | **Accept.** An emitted navigation event is sufficient; an adapter method adds no value. |
| 4 | **Accept for T-CHAT-003**, except first-request failures that already created a draft: those still need correction and recovery. See finding 9. |
| 5 | **Accept.** Local handling avoids an invalid, unnecessary paid read. |
| 6 | **Accept.** Reusing the existing final and review dialogs preserves their checks. |
| 7 | **Reject.** The approved requirement says the switch remains available at any time. Hiding its only location on phones breaks that requirement. |
| 8 | **Reject as implemented.** A new paid recap is appropriate after a known terminal failure. “No job and no new version observed” does not establish that outcome. Changed replay payloads need recovery, rather than a new key. |

**Money-path assessment**

| Path | What stops it |
|---|---|
| Double tap in one tab | `spend()` and synchronous `starting`/`busy` locking stop the second action. |
| Paid button during a known job | Client `locked` disables it; server `image_job_running` also protects the same creation. |
| Same card, identical scene request | `store.mutate` replays the original response, including after completion. |
| Same card, changed plan/body/revision | Server returns `idempotency_reused`; no second charge, but recovery stalls. |
| Reload before creation ID exists | No second scene automatically, but the card becomes unrecoverable. |
| Reload after the job is known | Existing job following generally works. |
| New card ID or another creation | No per-wish protection. Job and scene-limit guards are per creation; the cap only limits total spending. |
| Two tabs during thread migration | **Unsafe:** the second tab can manufacture a new card and creation, bypassing all same-card guards. |

The optional key plumbing leaves the step editor’s existing mutation behavior intact. I found no concrete regression in `route()`, `here()`, the `adopt()` hash change, or automatic review opening **when chat is unused or unavailable**.

**P0:** none found.

**P1**

1. **Thread migration can create a second paid wish in another tab.**  
   [ChatView.vue:203](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:203), also 66–70 and 214–217.  
   Tab A moves `affiche.chat.new` to its creation ID and removes the source. Tab B receives that removal, calls `load(null)`, and rebuilds a complete recap from its retained form fields—with a **new UUID**. B can create another poster while A generates. Different creation IDs and card keys defeat replay, `image_job_running`, and the scene limit.  
   **Smallest fix:** persist the `new → creation` handover and make other tabs follow it; never recreate a paid card merely because its source key disappeared. I reproduced the new-card reconstruction in memory.

2. **Typing the next message destroys the current paid read’s replay key.**  
   [ChatView.vue:150](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:150), also 54–56 and 127–143.  
   While read A is pending, typing B replaces the sole `UNSENT_KEY` record. If A’s answer is lost, retrying A sends a new key and can pay again. If A succeeds, `keepUnsent(null)` instead deletes B’s saved draft. Storage failures likewise leave no in-memory replay record. `invalid_response` also discards a key even though the server may have completed the read.  
   **Smallest fix:** keep the immutable pending read separately from the editable composer, with an in-memory fallback; retain it for ambiguous outcomes. The `read()` helper itself correctly preserves the exact body and rejects text-based key reuse. The consumer loses that protection. Reproduced the changed-key retry.

3. **Scene recovery is incomplete both before creation and after reload.**  
   [ChatView.vue:175](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:175); [App.vue:1067](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:1067).  
   Reload after saving `spent`, before obtaining a creation ID: reconciliation exits forever, leaving no result, error or retry. Conversely, a persisted error card retried after reload rebuilds its plan, so an already accepted scene request gets a different body under the old card key and returns 409 indefinitely.  
   **Smallest fix:** retain enough operation state to resume creation and replay the original scene body/revision/key. Offer a new paid card only after establishing a terminal failure. Reproduced the pre-creation dead end.

4. **Reconciliation guesses success from an unrelated newest visual.**  
   [ChatView.vue:178](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:178).  
   A spent recap is considered successful whenever the newest visual lacks a result bubble. For example, generate a version in steps, return to chat, then let a recap’s new job fail: the earlier, unrepresented version can be attributed to the failed request. Thread trimming can produce the same ambiguity.  
   **Smallest fix:** associate the card with its returned job ID and use that job’s `result_ref` or failure. Do not infer causality from visual order or missing bubbles.

**P2**

5. **Photos already sent are lost when reloading during the read.**  
   [ChatView.vue:116](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:116).  
   Sending moves photos into `draft`, revokes their URLs and empties the tray, but saves the thread only after the read finishes. Reload during that interval restores only the read body’s photo **count**, not asset IDs. This exceeds the stated “unsent images” gap.  
   **Smallest fix:** save the owner bubble and asset-backed draft before starting the read. Reproduced.

6. **Returning from steps restores stale product facts.**  
   [ChatView.vue:64](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:64).  
   Create a chat recap, switch to steps, correct the name/price/photos, then return. The existing stored thread wins; form fields are imported only when no raw thread exists. A later `run()` calls `sync()` and restores those old facts into the generation input.  
   **Smallest fix:** explicitly transfer current form values and asset references on the mode switch, then refresh the recap. Distinguish this transfer from reload restoration. Reproduced stale-name restoration.

7. **A new chat displays the previous poster’s image.**  
   [ChatView.vue:27](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:27); [App.vue:989](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:989).  
   `fresh()` clears the creation/document but retains `visuals`. The chat unconditionally uses `visuals[0]`, so clicking “Créer” after opening a poster leaves that poster in the new conversation’s sidebar.  
   **Smallest fix:** clear visuals on `fresh()` and require a matching creation before displaying them. Reproduced the stale display state.

8. **A result’s download action can export another selected version.**  
   [ChatView.vue:254](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:254); [App.vue:1347](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:1347).  
   Approve chat version A, select approved version B in steps, then return. A’s result still offers “Télécharger”, but `adapter.download()` renders the current document containing B. The sidebar’s newest visual can also differ from the selected version.  
   **Smallest fix:** make download target the card’s visual explicitly, or restrict it to the selected visual and state that selection clearly.

9. **A first-request title refusal cannot be corrected through chat.**  
   [ChatView.vue:122](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:122).  
   Scene-time validation can refuse a title after `createPoster()` succeeded. The next corrective message now encounters `state.creation` and receives only the local steps response; retry retains the invalid title. This is first-request recovery required by the failure table, not deferred polish.  
   **Smallest fix:** keep name correction available until the first scene succeeds, updating the existing draft before retrying.

10. **The mobile editor removes the only mode switch.**  
    [App.vue:1422](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:1422); [style.css:570](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/style.css:570).  
    Opening a poster in steps at phone width hides the entire header and switch.  
    **Smallest fix:** expose the same switch through the existing mobile editor bar/menu.

11. **Low-resolution consent carries into another product.**  
    [ChatView.vue:18](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:18), also 58 and 247.  
    Accept reduced quality, complete the poster, then start another conversation without unmounting chat. `load()` never resets `smallAccepted`, so the next product’s agreement starts checked and the adapter grants it to the new creation.  
    **Smallest fix:** reset consent on thread/product changes and when the applicable photos change.

**P3:** no separate maintainability finding warrants blocking this round. Keep the existing adapter; stable operation identities and explicit state transitions address the substantive problems without a broader refactor.

Static inspection found no new dependency, forbidden backend import, chat canvas/font loading, or new fixed-position ancestry violation. `git diff --check` passed. The targeted reproductions used the actual transpiled chat code with Vue reactivity and mocked boundaries, entirely in memory.

Not rerun: Vitest, build, browser smokes, or physical-device/accessibility checks. Files were untouched; no server, network, paid call, store write or `.env` access occurred.  
Remaining material risk: duplicate spending across tabs and incorrect recovery/version attribution.