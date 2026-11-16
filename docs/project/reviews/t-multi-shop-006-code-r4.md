**Verdict: REJECT.** The kept-card mechanism is not sound enough to ship to invited shops.

1. **P1 — A failed kept-record read still permits another paid card.** [ChatView.vue:120](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:120), [ChatView.vue:387](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:387). With a stale tapped card in the thread and its exact request only in `kept`, refuse the kept-record read. Startup silently continues, concludes “nothing sent” and offers a new paid card. **Reproduced through the real ChatView startup in memory.** An unreadable recovery record must leave recovery visibly blocked, rather than establish that no request exists.

2. **P1 — Restoration can overwrite a newer paid request.** [chat.ts:261](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/chat.ts:261), [chat.ts:266](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/chat.ts:266), [App.vue:1535](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:1535).
   - If reading the existing thread throws, restoration treats it as absent, overwrites it with the older kept cards, then deletes `kept`. A newer paid request already in that thread disappears.
   - Restoration also runs outside `affiche-chat`. Another tab can save a newer paid request between restoration’s read and write; restoration overwrites that save.

   **Both reproduced with in-memory storage probes.** Failed reads must prevent replacement; restoration and chat writes need the same serialization or an authoritative record they cannot overwrite.

These violate the amended paid-card preservation invariant and ADR-097/098. The ranking only protects copies that a writer successfully reads.

**Previous findings**

| Review | Rulings |
|---|---|
| R1 | #1 **CLOSED**; #2 **CLOSED**; #3 **PARTIAL**; #4 **CLOSED**; #5 **CLOSED**; #6 **CLOSED**; #7 **CLOSED** |
| R2 | #1 **CLOSED**; #2 **PARTIAL**; #3 **CLOSED**; #4 **CLOSED**; #5 **CLOSED** |
| R3 | #1 **PARTIAL**; #2 **CLOSED**; #3 **CLOSED** |

The specific round-3 refused-write case is addressed; findings 1–2 leave recovery unsafe. Cleanup retry now holds the identity lock, and both decode failures call `verify()`.

**Fragility list**

| Claim | Ruling and scope |
|---|---|
| **a. Failed save does not stop sending** | **ACCEPTABLE WITH A NOTE for this diff.** Confirmed already on HEAD: `sending()` calls a save that catches failure. Existing risk, not introduced here; the redesign should fix it. |
| **b. Unreadable or malformed kept record** | **BLOCKS.** Finding 1 is new. Also confirmed that malformed `kept` is silently deleted as “restored” ([chat.ts:232](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/chat.ts:232), [chat.ts:269](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/chat.ts:269)). |
| **c. Conclusion convention** | **NOT A DEFECT demonstrated.** Current server-derived paid-card conclusions retain request or job. The ranking is new; current writers satisfy its assumption. |
| **d. Whole-thread writes versus restoration** | **BLOCKS.** Finding 2. Whole-thread saving predates this task; the competing restoration writer does not. |
| **e. Lockless cleanup gaps** | **ACCEPTABLE WITH A NOTE.** New, explicitly accepted by the latest design amendment. Same-shop drafts can be erased under those schedules; no cross-shop disclosure was demonstrated. |

**Redesign choice**

Choose **one authoritative record per shop/card id**, with threads displaying it. Three copies are not inherently wrong, but this implementation lacks one durable authority and consistent ownership of writes.

Guarantee that the exact request and idempotency key are durably written **before sending**; failed persistence stops sending; unreadable records block another paid card; sign-out cleanup preserves them; only a final refusal or terminal job outcome resolves them. A transient response must not remove them.

Refusing sign-out while a card waits would change approved R-MULTI-SHOP-004 and would not fix the pre-existing send-after-save-failure problem.

The inspected visibility paths use the one gate, and sign-out takes its snapshot from the live thread. Cookie tests cover controlled cookie changes and desktop Chromium lock serialization; the `route.fetch()` observation is documented, but I did not independently rerun it.

No files or persistent stores changed. In-memory probes reproduced the findings; `git diff --check -- frontend backend` passed.  
Full suites, build and browser smokes were not run under the read-only constraints; the lead’s reported results remain unverified.