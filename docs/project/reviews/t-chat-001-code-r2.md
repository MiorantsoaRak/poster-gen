**REJECT**

| Previous finding | Ruling |
|---|---|
| 1. Partial amounts | **PARTIAL** — original examples pass; nonzero suffixes still bypass the guard. |
| 2. Envelope/schema split | **PARTIAL** — truncation and unexpected models fixed; malformed text blocks still succeed. |
| 3. Timeout test | **CLOSED** — the delayed coroutine now returns a valid result. |
| 4. Combined ledger test | **CLOSED** — covers all three ledgers and the date cutoff. |
| 5. Invalid UUID keys | **CLOSED** — shared validation runs before admission. |

1. **P1 — Invalid amounts still produce accepted prices.** [reads.py:90](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/reads.py:90)  
   Confirmed through `candidate_amounts()` **and `build()`**:

   | Message fragment | Accepted recap price |
   |---|---:|
   | `-700 123 Ar` | 123 |
   | `700,123 456 Ar` | 456 |
   | `−700 000 Ar` (Unicode minus) | 700000 |
   | `٧700 123 Ar` (mixed Unicode digits) | 123 |

   Dropping the first numeric token salvages malformed amounts; the ASCII sign check misses Unicode minus. **Smallest fix:** reject the entire malformed/signed numeric span; restrict token dropping to actual product/model prefixes. Add these nonzero cases through `build()`.

2. **P2 — Missing or non-string text is classified as a completed answer.** [planner.py:108](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/planner.py:108)  
   With the pinned model and `end_turn`, `content=[{"type":"text"}]` produces `succeeded` plus `unclear`. `text: null` and `text: 7` do likewise. Confirmed using mocked transport: readable cost remains 3900, but the required result is `interrupted` and 503 `read_failed`. **Smallest fix:** require a string `text` before setting `complete=True`, preserving parsed usage.

Failure-cost probes otherwise matched the intended rules. Twenty-one existing adapter/usage checks passed directly in memory; no behavior change found for plan/look/text_patch. `Armani`, `arrivage` and internal-newline grouping were rejected. A 500-character backtracking probe took approximately **0.19 seconds** locally.

No files changed or prohibited commands ran; `backend/.env` was untouched. Full-suite, migration and mutation claims remain unverified.  
Remaining risk: the server still accepts prices the owner did not write as amounts.