**Verdict: REJECT.**

1. **P1 — Requests before binding can put B’s poster in A’s page.** [App.vue:616](frontend/src/App.vue#L616), [api.ts:90](frontend/src/api.ts#L90), [App.vue:929](frontend/src/App.vue#L929). A hash change before the first session answer starts requests without `X-Affiche-Shop`. If B’s visuals answer arrives after the session confirms A, `adopt()` installs B’s document while A’s gate is open. Reproduced in a mocked App setup. Block routing and shop requests until the initial binding is confirmed.

2. **P1 — Failed sign-out can delete the only kept paid request.** [api.ts:140](frontend/src/api.ts#L140). When restoration previously failed, `kept` may be the sole copy. `endSession()` rewrites it, then deletes it on network failure, incorrectly assuming another copy survives. Reproduced. Preserve the previous record on failure; remove only a newly created duplicate.

3. **P1 — An existing thread makes restoration discard paid cards.** [chat.ts:216](frontend/src/chat.ts#L216), [chat.ts:197](frontend/src/chat.ts#L197). Restoration skips any existing thread, then deletes `kept`, even if that thread lacks the waiting card. `signOutPlan()` likewise replaces kept cards with the incomplete thread. Reproduced; [the test explicitly accepts this loss](frontend/tests/chat.test.ts#L349). Merge missing cards by id and remove `kept` only after preservation succeeds. The design’s collision rule needs correction too.

4. **P1 — A 401 does not always close the gate.** [api.ts:98](frontend/src/api.ts#L98). The identity-loss hook runs only after JSON parsing. A 401 with an unreadable body leaves shop content visible; a delayed body delays hiding it. Reproduced with an unreadable response. Handle the 401 status before reading its body, retaining the sign-in exception.

5. **P2 — Sign-out is absent from the phone editor.** [App.vue:1632](frontend/src/App.vue#L1632), [style.css:576](frontend/src/style.css#L576). Its only button sits inside the header that mobile editing hides. This breaks R-MULTI-SHOP-001’s “every screen” requirement. Add it to the editor’s visible menu/bar.

6. **P2 — The recovery contact disappears from sign-in screens.** [App.vue:1533](frontend/src/App.vue#L1533), [App.vue:1642](frontend/src/App.vue#L1642). An authenticated session answer clears `support`; another-shop and expiry screens can therefore omit the contact despite configuration. This breaks R-MULTI-SHOP-001. Make the configured contact available whenever the form is displayed.

7. **P2 — Failed storage cleanup silently reports successful sign-out.** [App.vue:1606](frontend/src/App.vue#L1606). A throwing `removeItem()` leaves threads, words and style behind, followed by an unconditional redirect. Isolation remains, but R-MULTI-SHOP-004’s deletion promise and the visible-failure constraint are unmet. Surface incomplete cleanup and provide recovery.

The live-thread snapshot is wired in. The cookie tests establish controlled cookie-change reactions and desktop Chromium lock serialization; they do **not** establish real late/aborted `Set-Cookie` ordering, mobile lock behavior or an actual back-forward-cache restore.

Focused in-memory checks reproduced findings 1–4; `git diff --check` passed. No files changed.  
Full suites, build and browser walks were not run under the read-only/no-store-write constraints; the implementer’s reported passes remain unverified.