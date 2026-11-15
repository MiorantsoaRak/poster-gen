**Verdict: REJECT.**

1. **P1 — An old tab ignores an unresolved `restyle` request.**  
   The new kind is emitted at [reads.py:420](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/reads.py:420). In HEAD, `chat.ts:153` excludes it from `paid()`, so `ChatView.vue:59` also excludes it from `openCard()`. After takeover of a spent card with a saved request but no known job, the old tab can obtain and pay another change card while the first remains unresolved. This violates ADR-097/098.  
   **Fix:** block incompatible clients from creating further paid work, while preserving the unresolved request. Test actual HEAD takeover; the new smoke’s invented unknown kind checks only button visibility.

2. **P1 — An identity recap is still payable by the old bundle, which ignores identity.**  
   [reads.py:464](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/reads.py:464) returns the existing `recap` kind with `identity: true`. HEAD recognises that kind as paid, but its `ChatView.vue:295` and `App.vue:1384` do not apply identity. With the form’s default ticks, “avec le logo et le contact” therefore produces a paid poster without either.  
   **Fix:** extend compatibility protection to identity recaps, including stored answers.

3. **P2 — Explicitly asking to leave identity off can keep it on.**  
   [reads.py:453](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/reads.py:453) removes explicit `false`, making it indistinguishable from no request. [App.vue:1394](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:1394) then preserves existing form ticks. Tick logo/contact in Pas à pas, return to chat and ask “sans logo ni contact”: both remain selected.  
   **Fix:** preserve an explicit off instruction separately from absence and clear those two ticks. Keep absent-field hashes unchanged.

The other inspected paths answer the earlier P1 concerns: the four words reach the editor’s fields; same-message scene requests are deferred visibly; ownership is checked after the palette wait; `keptFrom`/`keptAlign` are cleared by the existing `finally`. Plan reuse includes style, direction, palette and revision in its signature. `commercial` retains its previous scope.

Deviations **1–5 and 7–9 are acceptable**. **6 needs the explicit-off fix above**. Format wins over identity, and identity over style; combinations involving either return one `steps` sentence without generation.

**Simplification:** a restyle still fetches an unavailable old saved look through `restoreHeadline`, although `pickLook(style)` immediately discards it. Skip that lookup while retaining the drawn settings.

Memory-only probes confirmed all three defects, the legacy hash and required reader fields. Creation-failure restoration/retry lacks a dedicated new regression check; real-reader evaluation remains T-CHAT-REST-002.

Not checked: full suites, build, browser, devices, network, production or paid behaviour. No files changed; `backend/.env` was not read.  
Risk: mixed bundles can bypass the unresolved-card guard or silently omit requested identity.