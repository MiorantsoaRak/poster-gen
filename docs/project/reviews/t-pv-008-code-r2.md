**Verdict: APPROVE.**

- **R1 P2: CLOSED.** [review.py:101](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/review.py:101>) now blocks abandonment for any running request in exactly `(variant_ref, run_label, cycle_no)`, matching design line 357. The unused mapping and import are removed.
- **Tests:** cover both request purposes against both treatments, successful abandonment after interruption, and isolation from requests in another run, cycle or variant.
- **New actionable defects introduced by r2:** none found.

Both local files match the supplied artifact. Static review only: the launcher failed before execution (`helper_unknown_error: setup refresh had errors`), so I did not independently rerun pytest or mutations. No files modified; no network used.