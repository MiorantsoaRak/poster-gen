**Verdict: APPROVE WITH FIXES.** The server-authority shape is sound, but this diff needs fixes before shipping to invited shops.

1. **P2 — Another tab can recreate deleted shop data.** [api.ts:69](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/api.ts:69) refuses writes only when the gate is `out`. After the identity event, the session check leaves it `hidden`, so a late successful answer can rewrite a deleted thread. When the check subsequently answers “signed out,” that thread remains. **Reproduced in memory.** A failed check extends this beyond the stated one-round-trip window, indefinitely. Coordinate cleanup with writers; receiving the identity event must immediately prevent these writes. The browser test misses this because it [waits for the sign-in screen before releasing the response](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/tests/chat_browser.py:1653). Breaks R-MULTI-SHOP-004’s deletion promise.

2. **P2 — Strict send can delete its own persisted request.** [ChatView.vue:105](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:105) runs the thread cap after writing, then returns `true` even if that cap removed the current thread. With 30 stored threads dated ahead of the corrected device clock, `keepRequest()` permits sending with no stored request/key left. **Reproduced using the actual `save()` body.** Exclude the current thread from eviction and protect unresolved requests. Add a clock-correction regression check. This defeats strict send and same-session ADR-097 recovery.

3. **P2 — The required pending-image warning is missing outside the owning chat.** [App.vue:1569](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:1569) consults only this tab’s mounted chat. Another tab signs out immediately, even while an image waits; the [new browser case explicitly expects this](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/tests/chat_browser.py:1651). Leaving the chat for the editor also removes that warning source. Provide the confirmation on these paths without restoring the removed card mechanism. R-MULTI-SHOP-004 and the amendment require the warning.

**Server assessment:** the inspected paid routes share the session boundary; no paid exemption was found. Jobs, mutation keys and reservations commit together. Reads use their own atomic keyed reservation. The worker’s bounded 429 retry belongs to the existing job and releases the refused call’s cost. A request passing authentication before logout may continue afterward, as explicitly accepted.

The new pytest is a useful sequential revoked-cookie test with a positive control. It does not independently prove transaction atomicity or concurrent admission; those conclusions come from source inspection.

**Previous findings**

| Round | Ruling by finding number |
|---|---|
| R1 | #1 CLOSED; #2 VOID; #3 VOID; #4 CLOSED; #5 CLOSED; #6 CLOSED; #7 CLOSED |
| R2 | #1 CLOSED; #2 VOID; #3 CLOSED; #4 PARTIAL — own-tab case fixed, cross-tab writes remain; #5 CLOSED |
| R3 | #1 VOID; #2 CLOSED; #3 CLOSED |
| R4 | #1 VOID; #2 VOID |

**Stated weaknesses**

| Item | Ruling |
|---|---|
| a | **BLOCKS** — finding 1; failed reconciliation makes the window unbounded. |
| b | **ACCEPTABLE WITH A NOTE** — explicitly accepted in ADR-108. |
| c | **ACCEPTABLE WITH A NOTE** — stale listing, but opening the draft retrieves its current job/versions. |
| d | **BLOCKS** — finding 3. |
| e | **ACCEPTABLE WITH A NOTE** — a free empty draft can remain; no image request leaves. |
| f | **NOT A DEFECT in the current reachable flow** — `plannerMode` stays `fixed`; editor buttons are outside the chat strict-send contract. Extend protection before enabling paid planning there. |

No remaining kept-record implementation was found. **P3:** the [chat smoke’s success summary](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/tests/chat_browser.py:1961) still claims preservation and refusal of sign-out when preservation fails; update that obsolete wording.

No files or persistent stores changed. In-memory probes reproduced findings 1–2; diff whitespace checks passed.  
Full suites, build, browser smokes and mutation claims remain unverified under the read-only/no-store-writing constraints.