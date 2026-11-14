**REJECT.**

| Round-4 finding | Ruling | Reason |
|---|---|---|
| 1 — Regaining ownership revives obsolete work | **CLOSED** | Each acquisition changes the token; captured tokens guard continuations and the final scene send. |
| 2 — Transient refusal permits unsafe replacement | **PARTIAL** | Busy/authentication refusals retain the request, but some “final” refusals are reversible. |
| 3 — Returning from steps automatically buys a scene | **CLOSED** | Recovery sends nothing automatically; it clears the earlier refusal and offers explicit « Reprendre », preserving the card’s words and showing cost. |

**P1 — `creation_abandoned` does not permanently prevent a delayed delivery.**  
[frontend/src/chat.ts:97](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/chat.ts:97), [frontend/src/ChatView.vue:253](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:253).

X remains delayed after an ambiguous failure. Another tab removes the poster; replaying X receives `creation_abandoned`, so chat retires X and offers Y. Restoring the poster leaves its revision unchanged ([store.py:344](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/store.py:344)). Delayed X can then succeed. On a poster already containing a rejected version, completion need not advance the revision, allowing Y to succeed afterwards too.

Smallest fix: retain the exact request/key on `creation_abandoned`. Also exclude `format_unavailable` from permanent refusals: reenabling a format does not change the poster revision. Replace the `format_*` wildcard with explicit permanent codes, and cover recovery without offering a replacement.

For the specific question: **`idempotency_reused` and application-level `not_found` do not present this same race under current server semantics.** An exact stored replay cannot ordinarily produce `idempotency_reused`: matching method, path, body and revision returns the recorded response. If another payload already owns that key, every identical delayed delivery remains blocked. Missing referenced resources use server-generated IDs that are not subsequently recreated under those IDs.

Verified: TypeScript, `git diff --check`, and in-memory component checks for token invalidation, transient retention, explicit recovery, and abandonment retirement. Files unchanged.

Not rerun: Vitest, build, browser smokes, or device checks; no servers, network, real-store writes, paid calls, or `backend/.env` access.  
Remaining risk: two paid scene jobs after a reversible refusal retires an unresolved card.