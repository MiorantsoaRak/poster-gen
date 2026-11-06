**APPROVE — static review.** No actionable defect found in the supplied diff under the documented startup, ownership and cancellation contracts.

The retry limit, budget refusal, atomic success transaction, recovery guard, billed-cost preservation, semaphore and metadata stripping are consistent with the design. The listed implementation choices are reasonable.

Two non-blocking points:

- **T-PV-009:** share one `Semaphore(2)`, use `assets.extension(mime)` for writers, and persist `cutout_asset` plus `[x, y, w, h]`.
- **Test tightening:** parameterize [test_execution.py:137](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_execution.py:137>) with a positive usage-based cost and `cost_micros=None`; assert exact cost, estimate flag and usage persistence. Current successes exercise only the stub’s zero cost.

No abstraction or test deletion offers a clear simplification worth changing here.

Tests could not start: the launcher failed with `helper_unknown_error: setup refresh had errors`. Reported test results were not independently reproduced. No files modified; no network used.