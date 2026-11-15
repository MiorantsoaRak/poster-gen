**Verdict: APPROVE.** No P1/P2 defects or unmet backend requirements found.

All previous findings are **CLOSED**:

| Finding | Result |
|---|---|
| Word-guard bypass | Both sides use `name_words`; unknown words are reported normalized. |
| Corrupted brackets | Ambiguous rewrites are refused. |
| Retained brand disappearing | The final title/brand pair is separated; `brand_in_title` metadata correctly means no separate drawn brand. |
| Carried title bypassing validation | Carried document text is checked before offering a scene. |
| Redundant dictionary union | Simplified to `document \| image`. |

Independent probes confirmed:

- Price-only changes preserve the title and brand, both with a separate brand and with `brand_in_title`.
- A requested title containing the retained brand is separated correctly.
- Unknown digits, a changed model number and `bluetooth` assembled from known `blue tooth` are refused.
- New-poster provider inputs match `HEAD`; canonical bodies without `visual_id` and the legacy hash remain unchanged.
- No weakening found in ADR-095, admission/replay ordering or version eligibility.

**P3 — Persist the additional regressions.** [test_reads.py:705](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_reads.py:705) lacks the price-only preservation cases through [poster_words](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/reads.py:467), and the digit/model/joined-word cases above. They passed independent probes but currently have no lasting coverage.

No further simplification warrants changing the implementation.

Verified: **126 tests passed**, plus isolated probes; no files modified.  
Not run: 48 tests requiring store writes, the full suite, devices, production or paid calls. Their results remain independently unverified; `backend/.env` was never read.