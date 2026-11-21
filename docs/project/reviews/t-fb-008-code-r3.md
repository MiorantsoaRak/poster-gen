# Code review r3 — T-FB-008: migration 0019, the Graph client's two calls, the operator's limit

Reviewer: Codex, read-only, 2026-11-21. Verdict: APPROVE (the three open findings closed; no new finding).

- **Finding 2 (P1) — CLOSED.** The stub converts only the marker’s one to three digits. It compares `position + 1` numerically, including for `position=10**5000`. [facebook.py:404](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/facebook.py:404)
- **Finding 4 (P2) — CLOSED.** `post-limit` validates ASCII digits, strips leading zeros, converts at most 19 digits and enforces `1..2**63-1`. The regression test covers 5,000 leading zeros followed by `7`. [shops.py:653](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/shops.py:653) · [test_shops.py:608](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_shops.py:608)
- **Round-2 new finding (P1) — CLOSED.** `StubGraph.create_post` checks the generated ID with `_kept` before building the link. A token match returns `Outcome("unknown")` with both ID and link unset. [facebook.py:416](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/facebook.py:416)

No new findings in scope. Migration 0019 is additive, and `publish_photo` retains its request and classification behavior. This was a read-only review. The 518 focused passes are user-reported.

**APPROVE**