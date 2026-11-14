**REJECT**

| Round-2 finding | Ruling |
|---|---|
| 1. Partial amounts | **PARTIAL** — original examples fixed; further bypasses remain. |
| 2. Malformed text blocks | **CLOSED** — missing/null/non-string text produces `interrupted`, 503 `read_failed`, retaining cost 3900. |

1. **P1 — Invalid numeric spans still become prices.**  
   Confirmed through `build()`, supplying the accepted value as the model output:

   | Exact message | Accepted draft/recap price | Cause |
   |---|---:|---|
   | `JBL A55..123 Ar` | 123 | Model-prefix removal consumes both dots, salvaging malformed grouping. |
   | `JBL 七700 123 Ar` | 123 | `七` is both alphabetic and numeric; token dropping runs before numeric rejection. |
   | `JBL ⁻700 000 Ar` | 700000 | Superscript minus U+207B bypasses the sign list. |
   | `JBL 700٫123 456 Ar` | 123456 | Arabic decimal separator U+066B allows extraction to restart inside the amount. |

   These also reach existing-poster price-change cards. They exceed the accepted `13 700 000 Ar` suffix ambiguity.

   **Locations:** [reads.py:91](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/reads.py:91), [reads.py:95](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/reads.py:95).

   **Smallest fix:** reject numeric prefixes before the alphabetic branch; require whitespace when removing an attached model token, without consuming dots; reject the demonstrated Unicode sign/decimal boundaries. Add these exact cases through `build()`, expecting `ask_price` and no existing-poster change card.

2. **P3 — Removable defensive code.**
   
   - [reads.py:290](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/reads.py:290): the constructor’s `ValueError` fallback is unreachable through validated `Settings` and `_spec()`: the model is pinned and the key is present and printable. Remove that wrapper and the `read_unsent` alternative at line 317.
   - [reads.py:165](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/reads.py:165): `ValidationError` subclasses `ValueError`; remove the redundant exception entry and import.

No other P0/P1 defect found in the complete backend diff. Passed 47 existing pure parser/build cases, 20 provider cases with storage/thread dispatch mocked, and `git diff --check`.

Not verified: claimed full-suite, migration or mutation results; no files changed, prohibited commands run, or `backend/.env` accessed.  
Remaining risk: the price guard still accepts amounts the owner did not write as complete amounts.