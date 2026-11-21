# Code review r1 — T-FB-002: connecting a shop's Facebook Page

Reviewer: Codex, read-only, 2026-11-21. Verdict: REJECT (one P1, three P2, one P3, all concrete; the lock, the replay guard and the isolation of a refusal's message were confirmed). Answered in the code the same day; see r2.

1. **P1 — A signed-out session can still bind a Page.** `AccessBoundary` checks the session before the handler acquires its write lock. If sign-out commits in between, `choose()` can still find the `choice` row by session hash and bind the Page. Sign-out deletes the session row, so the hash alone is insufficient. Check `auth.live_shop(conn, token) == shop` inside the choice transaction, as `_store()` already does. Apply the same check to `connect` and `disconnect` so an ended session cannot replace or delete a newer attempt. The existing sign-out test covers the Graph exchange, leaving this final choice race uncovered. [facebook_connect.py:157](backend/src/affiche/posters/facebook_connect.py#L157)

2. **P2 — A failed callback can disappear without a message.** If the code POST never reaches the handler, the server has no `last_error`. The return page catches the failure and redirects, so the owner sees the ordinary account card. A failed session lookup also skips the POST silently. After scrubbing the address, show a French failure message and a « Mon compte » link on the return page for these failures. Preserve the normal signed-out redirect. Add a browser case where the POST fails before delivery. [facebook-return.ts:12](frontend/src/facebook-return.ts#L12)

3. **P2 — A capabilities failure hides its own retry button.** `facebookOn` starts false. If `/api/capabilities` fails, the catch sets `facebookError`, but both the message and retry control are inside `v-if="facebookOn"`. Distinguish an unknown capability from a confirmed `false`, and show the read error and retry control for the former. A successful `false` should continue to hide the card. [ShopAccount.vue:97](frontend/src/ShopAccount.vue#L97)

4. **P2 — Provider `off` still exposes body validation.** For authenticated, same-origin requests, FastAPI validates `CodeRequest` and `Choice` before either handler calls `make_graph`. An invalid body therefore gets 422 where the design promises 404. Omit the Facebook routes when the provider is off, or gate them before body parsing. The off-mode test supplies only valid bodies. [api.py:660](backend/src/affiche/api.py#L660)

5. **P3 — The Page limit is invisible.** An owner whose desired Page falls beyond the first hundred gets no explanation. The smallest fix without changing the Graph client is a static French note explaining the 100-Page limit, including in the no-eligible-Page message. The single-Page wording also differs from the design, but the owner sees the name and must explicitly confirm it. [ShopAccount.vue:155](frontend/src/ShopAccount.vue#L155)

The exchange itself releases the write lock before all three Graph calls and rechecks the attempt before storing tokens. The callback scrubs the query before checking the session, skips submission without a code or error, and a replay cannot reclaim the attempt. `last_error` is isolated by session hash. It has no fixed size cap, but each new refusal sweeps expired entries, and the data-folder lock enforces one API process. The capabilities change is additive, and the two-shop test retains its existing checks.

Static review only. No test runs or production proxy checks were counted.

**REJECT**