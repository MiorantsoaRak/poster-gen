# Code review r2 — T-FB-008: migration 0019, the Graph client's two calls, the operator's limit

Reviewer: Codex, read-only, 2026-11-21. Verdict: REJECT (three of five closed, two partial on numbers past Python's digit limit; one new P1 in the stand-in). Answered in the code the same day; see r3.

1. **P1 CLOSED** — `classify` selects both the response field and the log label from fixed literals. [facebook.py:168](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/facebook.py:168)
2. **P1 PARTIAL** — The stub rejects the reported malformed arguments, but `position=10**5000` passes validation and raises `ValueError` during marker formatting under Python’s default digit limit. The traceback retains `page_token`. Bound `position` by `sys.maxsize` before formatting. [facebook.py:403](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/facebook.py:403)
3. **P2 CLOSED** — An upload response with `post_id` returns `failed/published` only for a credential-free post ID of the requested Page. Every other value returns `failed/unexpected`. [facebook.py:197](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/facebook.py:197)
4. **P2 PARTIAL** — The ledger ceiling is gone, but 4,300 leading zeros followed by `1` is a valid spelling of one that `int(typed)` rejects under Python’s default digit limit. Strip leading zeros after validating ASCII digits, then reject more than 19 significant digits before conversion. [shops.py:653](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/shops.py:653)
5. **P3 CLOSED** — The cheat sheet gives `post-limit <identifier> [N|none]`. [AGENTS.md:53](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/AGENTS.md:53)

**New P1 — `StubGraph.create_post` can return the Page token in `post_id`, `link`, and `repr(Outcome)`.** For a 19-digit Page ID, `page_id + "_"` passes `credential()` and prefixes every generated post ID. Apply `_kept(post_id, POST_ID, (page_token,))` before constructing the outcome and return `unknown` when it fails. [facebook.py:414](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/facebook.py:414)

Migration 0019 is additive, and `publish_photo` retains its request and classification behavior. Review was read-only. The 518 focused passes are user-reported. The running full suite is excluded.

**REJECT**