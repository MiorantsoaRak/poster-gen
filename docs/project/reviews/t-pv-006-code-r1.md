**APPROVE WITH FIXES.** Static inspection found no admission path exceeding the cap or allowance, duplicating a live initial/revision, leaking arm-B corrections, or crossing scopes.

1. **P2 — Background admission needs a durable subject.** [admission.py:138](</C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/admission.py:138>)  
   The proposed CSV-only catalogue cannot support a later `apply decisions.csv`: that command receives no fixtures, and `run_products` stores only the arm/hash. After restarting, confirming a cutout and requesting its background still requires reconstructing its name/variant.  
   **Fix:** snapshot the subject when creating the cutout, using a forward migration; read it here and remove `catalogue` from `request_background`.

2. **P2 — “Latest fallback” depends on wall-clock order.** [admission.py:137](</C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/admission.py:137>)  
   If the clock moves backward between candidates 1 and 2, the query selects candidate 1. A background replacement then gets `revision_already_requested`, despite candidate 2 being rejected and eligible.  
   **Fix:** replace the ordering with `ORDER BY attempt_no DESC LIMIT 1`. The chain already supplies the sequence. Give seeded candidates realistic attempt numbers—the helper currently hardcodes `1`—and test reversed timestamps.

3. **P3 — Stale targets receive current-cycle errors.** [admission.py:177](</C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/admission.py:177>)  
   Revising a cycle-1 candidate when cycle 2 is full returns `attempt_limit_reached`, suggesting fallback, although this target requires `wrong_scope`. An abandonment similarly masks the stale target.  
   **Fix:** check parent/cutout scope identity before `_check_scope`; remove the duplicated identity checks below. This does **not** change the same-parent race: its loser still reaches the allowance guard first.

4. **P3 — Payload-change tests change warnings too.** [test_admission.py:232](</C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_admission.py:232>)  
   The original request acknowledges `["low_resolution", "x"]`; the changed-direction/default-photo calls omit them. Consequently, a regression normalizing explicit default photos to `None` still passes this purported distinction test.  
   **Fix:** preserve the original warnings in those two lambdas, changing exactly one field per case.

The **two-process test is useful but does not force contention**: either worker can finish before the other enters admission. The existing `test_db` lock-wait test supplies that proof. Tighten [test_admission.py:287](</C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_admission.py:287>) to require exactly `refused attempt_limit_reached`; the alternative unnecessarily tolerates changed rule ordering.

Deviation judgments: **1 and 3 are correct; 2 is reasonable** (`owner` is execution metadata), subject to fixing its test; **4 correctly resolves the conflicting background test wording; 5 is sensible** for an approved candidate, so update the specification; **6 is acceptable provided T-PV-009 validates cutout assets/style references; 7 has the diagnostic defect above.**

No current `Refused` follows an insertion. A propagated exception would roll back both rows. For T-PV-007, `reserve()` only calculates/checks: call it and insert call 2 inside the same `write_tx`; catch budget refusal **inside** that transaction when committing request failure.

Pytest could not start: `helper_unknown_error`. Review completed from the matching diff, code and SQL. No files modified; no network used.