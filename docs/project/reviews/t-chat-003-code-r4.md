**REJECT.** Two sequences can still produce two paid scene jobs for one wish. I found no additional unintended double-read sequence; retrying a settled `read_failed` deliberately pays for another read.

| Round-3 finding | Ruling | Reason |
|---|---|---|
| 1 — Ambiguous scene outcome permits replacement | **PARTIAL** | Exact replay fixes the 404 lookup race, but transient 4xx responses still permit unsafe replacement. |
| 2 — Ownership checked too early | **PARTIAL** | The final check is synchronous, but an old operation becomes valid again when its tab regains ownership. |
| 3 — Unmounted chat deletes newer pending read | **CLOSED** | Unmount invalidates ownership first; continuations and storage clearing are guarded. |
| 4 — Missing Web Locks permits concurrent reads | **CLOSED** | The fallback sends nothing and offers Pas à pas. |
| 5 — Duplicate `watchSticky()` | **CLOSED** | The redundant call is removed. |

1. **P1 — Regaining the lock revives an obsolete scene operation.**  
   [ChatView.vue:219](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:219), ownership reassigned at line 322.

   A taps card X and waits for plan preparation. B takes ownership, finds no stored scene request, offers replacement Y, and generates it. A then takes ownership back before its original preparation returns. `mine()` becomes true again, so X also sends.

   I reproduced two distinct scene keys using the compiled component in memory. On a poster already containing a rejected version, Y’s completion need not advance the revision; the server can admit X afterwards. Its active-job guard only prevents overlap. X’s request is also written onto an old card object absent from the reloaded thread.

   **Smallest fix:** capture an ownership token at operation start. Each lock acquisition must have a different token; check that exact token before sending and processing continuations. Regaining ownership must never revive earlier work.

2. **P1 — A transient refusal does not settle an earlier delayed delivery.**  
   [chat.ts:98](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/chat.ts:98), [ChatView.vue:246](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:246).

   X’s initial delivery remains delayed after an ambiguous failure. Another tab’s step editor starts an image job. Replaying X receives `409 image_job_running`, so chat retires X and offers Y. After the other job finishes, delayed X can arrive and succeed; Y can subsequently succeed too.

   Refusals do not reserve the key: [store.py:53](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/store.py:53) records it only after successful admission. Thus this 409 refuses one delivery, without preventing a later delivery of X.

   **Smallest fix:** retain the same request/key after transient refusals such as `image_job_running` or authentication failure. Restrict replacement to refusals that also make any outstanding identical delivery impossible. Update the test currently treating every listed 4xx as settled.

3. **P1 — Returning from steps can automatically buy a scene with discarded settings.**  
   [ChatView.vue:278](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:278), [App.vue:303](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:303).

   Let `/scenes` fail before reaching the server. Switch to steps, change the subtitle or ambiance, then return. These settings live outside the saved poster document, so its revision can remain unchanged. Chat automatically replays the old request and old plan.

   **The stale-request protection is confirmed for saved document changes such as title or price. It is not sufficient for all generation settings.** `plan_stale` reconstructs context using the stored plan’s direction; it cannot detect the owner’s newly typed ambiance. The old subtitle remains in the replayed body.

   **Smallest fix:** detect changes to generation settings before automatic replay. Preserve the original key, but require explicit confirmation of the old request when those settings changed.

The duplicate observer setup is gone. No further code removal warrants a separate finding; retain the adapter.

Verified: complete frontend diff, connected server admission paths, `vue-tsc --noEmit`, `git diff --check`, and in-memory reproductions with mocked boundaries. Files were unchanged.

Not rerun: Vitest, build, browser smokes, or the small-photo refusal path. No servers, network, paid calls, persistent-store writes, device checks, or `backend/.env` access.  
Remaining risk: duplicate scene spending and automatic generation using settings the owner changed.