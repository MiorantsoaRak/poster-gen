**Verdict: APPROVE WITH FIXES — two P2 defects.**

1. **P2 — Identity is lost after an old-tab refusal and reload.**  
   Reproduced using HEAD’s recovery functions in memory: the old tab loads an `identity: true` recap, receives `reload_required`, retires it and builds another recap without identity. It also saves a draft without identity. After reload, [readThread](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/chat.ts:113) accepts that as `null`; [start](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:1398) then leaves the default ticks off. The new bundle can therefore pay without the requested logo/contact. The original identity-bearing card remains in history.  
   **Fix:** recover that preserved choice during legacy-thread restoration. Add a HEAD → 409 → reload regression case; stripping the header from the new bundle does not exercise this failure.

2. **P2 — The reload instruction discards unsaved editor changes without saying so.**  
   The new [gate](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/api.py:215) permanently refuses the old editor’s autosave, then says [“Rechargez la page pour continuer.”](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/api.py:139). [DraftSaver](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/autosave.ts:45) retains the failed document only in memory. Reloading loses it. The existing unload prompt helps, but retrying cannot save these edits.  
   **Fix:** make the server’s refusal explicitly say that changes are unsaved and must be copied before reloading. Keep the compatibility gate closed.

Previous review:

- Old tab beside unresolved `restyle`: **CLOSED**.
- Old identity recap: **PARTIAL** — payment is blocked, but recovery loses identity as above.
- Explicit `identity: false`: **CLOSED**.
- Skip discarded saved-look lookup: **CLOSED**.

The four rejected design P1 concerns are otherwise addressed: incompatible requests are stopped; the card’s words reach the request; same-message scene adjustments are visibly deferred; ownership is checked immediately after the palette wait.

The middleware’s in-memory probe passed for **28 mutation routes**. No paid route or upload bypass was found; no mutation route exists outside `/api/`. Session operations remain exempt, status is GET, and an unauthenticated data mutation with the correct Origin gets **401 before the bundle check**. The older deployed bundle cannot start new paid work through these routes. The shared gate is simpler than per-card compatibility patches.

Not checked: suites, build, browser, devices, network, production or paid execution; implementer results remain unverified. No files changed; `backend/.env` was not read.  
Risk: legacy recovery can lose identity, and reloading an old editor can lose unsaved edits. D-006’s real-reader evaluation remains T-CHAT-REST-002.