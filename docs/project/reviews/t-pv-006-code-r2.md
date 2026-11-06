**APPROVE.** No new actionable defects found in the r2 changes.

| R1 item | Ruling | Evidence |
|---|---|---|
| 1. Durable subject | **CLOSED** | [admission.py:257](</C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/admission.py:257>) reads subject and arm from `run_products` for every entry point. Background admission needs no catalogue. Tests deliberately seed different candidate subjects. |
| 2. Latest fallback | **CLOSED** | [admission.py:124](</C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/admission.py:124>) orders by descending attempt number; [test_admission.py:356](</C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_admission.py:356>) exercises reversed timestamps with realistic numbering. |
| 3. Stale targets | **CLOSED** | [admission.py:163](</C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/admission.py:163>) checks both targets before scope rules and cutout confirmation. [test_admission.py:392](</C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_admission.py:392>) covers full and abandoned current scopes. Idempotent replay still comes first; allowance still precedes same-parent revision checks. |
| 4. Payload tests | **CLOSED** | [test_admission.py:238](</C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_admission.py:238>) preserves warnings for direction/photo changes and adds a warnings-only case. |
| 5. Two-process assertion | **CLOSED** | [test_admission.py:296](</C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_admission.py:296>) requires exactly `["admitted 3", "refused attempt_limit_reached"]`. |

[Migration 0002:23](</C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/migrations/versions/0002_run_products_subject.py:23>) is sound for the stated SQLite version and empty-table deployment. It leaves 0001 untouched, refuses downgrade, and runs within [the explicit migration transaction](</C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/db.py:56>). Its failure on populated tables is the documented precondition, not a new defect under the supplied deployment facts.

**T-PV-009 integration:** explicitly supply validated `name` and `variant` in the snapshot INSERT. Omitting them intentionally fails the CHECK; inserting first and filling them later will fail too. No existing production insert was found to break.

The requested pytest command could not start: launcher error `helper_unknown_error: setup refresh had errors`. This verdict is static; supplied test results were not independently reproduced. No files modified; no network used.