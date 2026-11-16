**Verdict: REJECT.**

1. **P1 — The post-operation session answer bypasses the gate.** [api.ts:137](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/api.ts:137). If DELETE succeeds server-side but its response is lost, the following GET can return `authenticated: false`; `identityChange()` discards it, and the failed sign-out leaves shop content shown. Another-shop answers and failed reconciliation are likewise ignored. Feed this check into the gate, including when the operation fails. Reproduced in memory. Breaks D-007’s single-gate rule.

2. **P1 — Restoration still discards paid requests.** [chat.ts:224](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/chat.ts:224). Two branches reproduced:
   - A stale thread contains the same spent card id without its request. Restoration skips it and deletes `kept`; recovery then treats it as “nothing sent.”
   - An older kept card merged into 100 newer messages is subsequently dropped by `readThread()`’s trimming, after `kept` has gone.

   Preserve the exact request when the existing card remains unresolved, and exempt unresolved cards from trimming. This also needs an amendment to the design’s “existing card left unchanged” rule to satisfy ADR-097/098.

3. **P1 — Protected-image requests bypass identity-loss handling.** [PosterCanvas.vue:35](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/PosterCanvas.vue:35), [palette.ts:43](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/palette.ts:43). These fetches omit `X-Affiche-Shop` and turn 401 into an ordinary image error. An uncached image failing after the session expires can leave the shop displayed despite that evidence. Route protected-image identity failures through the gate. The canvas branch was reproduced in memory.

4. **P2 — Late chat work can recreate deleted threads after sign-out.** [ChatView.vue:261](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:261), [ChatView.vue:96](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:96). `bind(null)` leaves the mounted chat owning its lock. A late read rejected with `gate_closed` still reaches `save()`, which writes the old thread before the key guard throws. With cleanup awaiting retry, that thread survives because the retry only removes recorded leftovers. Stop writes after successful sign-out while retaining state during ordinary visibility checks. Reproduced in memory.

5. **P2 — Some cleanup failures still become silent success.** [App.vue:1587](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:1587), [api.ts:75](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/api.ts:75). Storage enumeration/read failure becomes an empty cleanup plan, so no warning or retry appears. Separately, a failed legacy-key removal leaves a source that can repopulate shop-1 storage after sign-out deletes its scoped copy. Preserve incomplete-cleanup state and include unfinished legacy migration in cleanup. Both violate R-004’s deletion promise and visible-failure requirement.

**Previous findings**

| Round 1 finding | Ruling |
|---|---|
| #1 Requests before binding | **CLOSED** |
| #2 Failed sign-out loses previous kept record | **CLOSED** |
| #3 Restoration loses paid cards | **PARTIAL** — finding 2 |
| #4 `api()` delays/misses 401 handling | **CLOSED** — image bypass is finding 3 |
| #5 Phone editor lacks sign-out | **CLOSED** |
| #6 Support contact disappears | **CLOSED** |
| #7 Cleanup failure reported as success | **PARTIAL** — findings 4–5 |

The live-thread snapshot is wired in. Cookie tests cover controlled cookie-change schedules and desktop Chromium lock serialization. They do not prove real late/aborted cookie ordering, mobile locks or actual BFCache restoration; those accepted limits are not blockers. Losing the cleanup retry list after reload does not expose another shop’s keys, but does not excuse the additional deletion failures above.

Focused source probes reproduced findings 1–4; `git diff --check` passed. No files or persistent stores changed.  
Full suites, build and browser smokes were not run under the read-only constraints; reported passes remain unverified.