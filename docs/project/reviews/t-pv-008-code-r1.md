**Verdict: APPROVE WITH FIXES.** One P2 contract mismatch.

1. **P2 — Abandon’s running-request guard is too narrow.** [review.py:103](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/review.py:103>) filters by purpose. D-PV-003 defines scope as `(variant, cycle, run)`; D-PV-005:357 refuses abandonment while **any request in that scope** runs.
   - **Scenario:** a scene request is running; abandoning `photo_preserved` in the same scope returns `applied` instead of `request_running`.
   - **Fix:** remove `purpose = :purpose`. Remove the now-unused `_PURPOSES` mapping and `TREATMENTS` import. Update [test_review.py:247](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_review.py:247>) to expect refusal. The killed purpose-filter mutation currently reinforces this mismatch.

Interpretations **1–6 are acceptable** under the typed caller contract. **7** matches the required transition rules, but T-PV-010 must recognize matching replays before calling `next_status`; otherwise replayed approvals/rejections fail prevalidation. Cutout prevalidation also remains necessary.

For **8**, keep the current behavior under the written design: abandonment blocks new generation in that treatment’s scope; approving an existing candidate neither generates nor reopens it. `approved > abandoned` resolves reporting, and a subsequent explicit cycle requires the approval. Neither additional refusal is presently specified.

No other actionable defect found in the conditional writes, rejection screening, cycle gate, or reuse query.

Static review only: the requested pytest command failed before Python started (`helper_unknown_error: setup refresh had errors`). Both reviewed files match the supplied diff. No files modified; no network used.