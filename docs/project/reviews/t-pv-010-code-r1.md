**Verdict: APPROVE WITH FIXES.** Three findings, ranked:

1. **P2 — Abandon omits a prevalidation guard.** [evaluate.py:522](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/evaluate.py:522>)  
   `_check_abandon` never checks for a running request, although `review.abandon` does. With an API-owned request running, a file containing `confirm_cutout` followed by `abandon` passes validation: the confirmation commits, then abandonment fails. CLI startup only recovers CLI-owned requests, so it does not remove this condition.  
   **Fix:** after recognizing abandonment replays, check for **any running request in the scope**, regardless of treatment. Test that an unrelated valid decision remains unapplied.

2. **P2 — An unexpected admission error strands earlier reservations and stops unrelated rows.** [evaluate.py:613](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/evaluate.py:613>)  
   Only `Refused` is caught. If request A is admitted and admission B raises an `OperationalError`, `apply` exits before executing A or writing results. Recovery later marks A interrupted and retains its estimated cost, despite no provider call. Remaining products are skipped.  
   **Fix:** contain unexpected exceptions per row, record the failure, continue independent rows, and execute requests already admitted. Apply the same boundary to the decision loop. Test an injected failure on the second admission.

3. **P2 — Closed-scope filtering hides candidates that remain reviewable.** [sheet.py:79](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/sheet.py:79>)  
   Abandon a scope containing a pending candidate, then regenerate the sheet: the candidate disappears from both HTML and CSV. ADR-020 explicitly permits approving that candidate afterward; D-PV-008 promises every pending candidate.  
   **Fix:** enumerate pending candidates independently of the open-scope filter. Retain that filter for generation suggestions and scope-action rows. The existing test asserting the candidate disappears should change.

**Encoding:** the failure at [evaluate.py:424](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/evaluate.py:424>) warrants your planned fix. Decode the complete file strictly before parsing: UTF-8 with BOM support first, cp1252 fallback for BOM-less input. A UTF-8 BOM should commit the file to UTF-8; refuse malformed bytes rather than reinterpret them. Never use replacement decoding. Test accented notes in both encodings and replay equivalence.

The other choices are reasonable: protect existing decisions, omit exhausted revisions, reject unused columns, leave generation scope/budget refusals to admission, and keep abandonment notes unscreened. `not_started` is useful; document it in the result contract. The running-request omission above concerns **decision prevalidation**, not generation admission.

For terseness, prioritize these reductions:

- Share canonical rejection-payload validation between `review.reject` and `_payload`.
- Return the outcome already loaded by `_scene`; remove `apply`’s second request-query loop.
- Share the CSV column definition. Keep the two-pass validation and deterministic request-ID walk.

Static inspection found the replay-before-transition order, failed/interrupted retry selection, crop coordinates, composite placement, HTML escaping, and CLI `--paid` guard correct. Add the interrupted-request regression you identified.

The launcher failed, so tests were **not run**. Inspected files match the supplied diff. No files were modified, no network was used, and `backend/.env` was never opened.