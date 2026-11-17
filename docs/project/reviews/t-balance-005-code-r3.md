**REJECT. One P1 remains.**

**P1 — A repayment can hide a missing move reversal and duplicate the payment.** [shops.py:247](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/shops.py:247), [shops.py:254](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/shops.py:254).

An ordinary operator history:

1. The backup contains A’s succeeded, charged job `made`, with sufficient existing credits.
2. Kept history: grant A **10 credits / 10,000 Ar**, reference `MV-1`, then move that payment **A→B**.
3. After restoring: retype A’s grant with identical figures as `mv-1`, then `correct A +1 --ref mv-1 --job made --note …`.
4. Reconciliation excludes that repayment from `mine`, so the payment prefix matches. But “here already” treats it as the kept **A reversal**, because both are corrections under the same key. Only **B’s grant** is selected.

A retains its payment; B receives another **10 credits / 10,000 Ar**. The database’s exact-reference trigger does not connect A’s lowercase `mv-1` with B’s uppercase `MV-1`.

I reproduced the selection using the extracted reconciliation function and synthetic objects. The insertion’s acceptance follows from the trigger conditions; I did not execute database writes.

**Fix:** detect mismatched financial contents **and `job_id`** between corresponding present rows before accepting the payment history. Skip and name that payment’s missing lines. Keep repayments excluded from sequence comparison so the deferred-repayment fix survives. Add this regression.

Round-2 dispositions:

| Finding | Status |
|---|---|
| P1: matching shop/kind sequences with different contents | **PARTIAL** — both reported cases fixed; repayment substitution above still permits duplication |
| P2: deferred repayment permanently skipped after movement | **CLOSED** — the reported pending→succeeded case now selects the repayment |
| P3: Windows `os.geteuid()` failure | **CLOSED** — [test_shops.py:791](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_shops.py:791) short-circuits on Windows |

No additional P2 or P3 finding.

For **non-payment keys**, retaining the current figures is acceptable under D-BALANCE-005’s explicit identity rule. A “figures differ; current line retained” diagnostic would help, but I would not block approval solely on its absence. Automatically adding the kept figures would be wrong.

For simplification, I found no further meaningful deletion. `held` still protects reference spelling; `job_id` in `LINES` is needed. Fix the identity interaction without introducing another abstraction.

Passed: scoped whitespace check, restore shell syntax, five Python AST parses, and extracted-function assertions for the original round-2 financial cases and deferred repayment. No files modified.

Not checked: pytest/mutations, real SQLite replay, Docker/container behavior, Windows execution, devices or production; `.env` and `data-probe` untouched. The remaining P1 can duplicate credits and recorded receipts.