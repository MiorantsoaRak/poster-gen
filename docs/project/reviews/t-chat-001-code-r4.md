**APPROVE WITH FIXES**

| Round-3 finding | Ruling |
|---|---|
| P1 price guard | **CLOSED** — all four bypasses are rejected through `build()`, including existing-poster changes. |
| P3 removable code | **CLOSED** — constructor fallback, `read_unsent`, and redundant `ValidationError` handling removed. |

1. **P2 — Leading-zero rejection exceeds the specification.** [reads.py:94](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/reads.py:94)

   Exact inputs `0700000 Ar` and `0700000`, with model output `price_ar=700000`, produce no candidate and `ask_price`. Both are valid single pure tokens under rules 2, 6 and 8. Rule 7’s leading-zero exclusion applies to space-grouped suffixes.

   **Smallest fix:** apply that exclusion only when `suffixes and len(span) > 1`; separately reject numerical zero. Add candidate and `build()` tests for both inputs.

2. **P3 — Redundant numeric predicates.** [reads.py:112](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/reads.py:112)

   `isnumeric()` already includes every character matched by `isdigit()` or `isdecimal()`. Verified across all Unicode code points.

   **Smallest fix:** use `any(c.isnumeric() for c in before)`. No failing input; behavior is equivalent.

No remaining P0/P1 found. No unexpected accepted amount surfaced in 20,000 independent parser comparisons. Passed 82 existing parser/build cases and 20 provider cases with storage and thread dispatch mocked. `git diff --check` passed.

The previous misleading timeout test is fixed: its delayed coroutine returns a valid result, and removing the timeout now produces a recap instead of the asserted failure. No other misleading named test confirmed.

Not verified: full-suite completion, migrations, or claimed mutation results. No files changed or `backend/.env` accessed.  
Remaining risk: valid leading-zero prices are rejected; real-model extraction accuracy remains unverified.