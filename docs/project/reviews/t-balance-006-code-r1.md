**Verdict: APPROVE WITH FIXES.** No P1 found.

What this change does: replaces shop-facing dollar estimates with credit messages and gates new image requests. The main gaps are recovery paths and tests that do not exercise the actual UI boundary.

1. **P2 — The step editor can block an already-admitted retry.** [App.vue:705](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:705)  
   Spend the last credit, lose the scene response, then reopen the generation dialog without changing anything. Its balance read returns zero and removes confirmation, although [mutation()](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/api.ts:243) retained the exact request’s key for replay. The same problem occurs if the service becomes blocked. Recover the job or replay the retained request before applying the new-request gate. Add a lost-answer test for the editor.

2. **P2 — Cancelling skips both the refund message and balance refresh.** [App.vue:1281](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:1281)  
   `cancelJob()` discards the response, clears the job and stops polling. Cancelling the last queued image can therefore leave the browser showing zero available and one pending, although the server returned the credit. Consume the terminal result, show the refund sentence when appropriate, and refresh the balance. An in-memory probe confirmed no message and no balance read.

3. **P2 — Reopening a failed chat job omits its refund.** [ChatView.vue:417](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:417)  
   If a job finishes while the page is closed, `reconcile()` handles its terminal state directly; it never reaches the new `ended()` call in `poll()`. With `credit: given_back`, it displays only “Aucune image n’a été ajoutée.” Reuse `ended(job)` here and carry `credit` in `JobRow`. In-memory probes reproduced this for failed, interrupted and cancelled jobs.

4. **P2 — The free-at-zero test bypasses the condition it must protect.** [chat.test.ts:201](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/tests/chat.test.ts:201)  
   The test manually passes `stop=false`; it never executes [ChatView.vue:76](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:76). Removing `!free(item) &&` therefore hides a free price-change button while every added assertion still passes. Render that card with zero credits and with blocking set; verify the edit works and sends no image request.

5. **P3 — The dollar-key walk is useful coverage, but not every route’s successful answer.** [test_two_shops.py:367](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_two_shops.py:367)  
   Several routes contribute only ownership refusals. For example, the successful `GET /api/plans/{id}` answer is not exercised; password changes are exempt and never called. Adding a dollar field to those successful route answers could escape this walk. Track successful-response coverage separately from the tenancy attempt matrix and explicitly name remaining exemptions. I found no current dollar leak in the inspected response builders.

6. **P3 — A chat replay’s 402 does not refresh the balance.** [ChatView.vue:332](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:332)  
   `replay()` calls `mutation()` directly, bypassing both refresh handlers in App.vue. A never-admitted request retried after another device spends the balance receives 402 but leaves the cached positive balance unchanged. Refresh on this refusal while keeping replay available.

The identity handling looks sound: balance reads use `api()`, including its shop header and binding-generation checks. An in-memory probe confirmed that an A response is rejected after binding changes to B. Explicit sign-in loads a fresh page. I found no path displaying A’s balance as B’s.

The job mapping is correct for the current states: queued/running → pending, succeeded → spent, other terminal states → given_back; `takes_credit=0` always yields null. Legacy cancellation replay removes `usage` as designed.

One remaining **design limitation**: a continuously visible chat can retain zero or a pause after an operator grants credits or resumes service. Conversely, spending on another device can leave a stale positive number. Visibility changes, reloads or editor dialogs refresh it; the server still protects admission. The reload in `walk_credits` does not test this situation.

Rulings on the stated departures:

- **1:** Acceptable copy variation; purchase instructions remain visible.
- **2:** Extra reads for non-image jobs are acceptable. The omitted 402 refresh needs finding 6.
- **3:** Acceptable punctuation.
- **4:** Acceptable isolated smoke setup; the reload leaves the freshness limitation untested.
- **5:** Needs the regression test in finding 4.

Not checked: full suites, build, browser/device runs, production or deployment; reported counts remain unverified. Only source inspection and in-memory probes ran; no files changed, and neither `backend/.env` nor `backend/data-probe/` was accessed.