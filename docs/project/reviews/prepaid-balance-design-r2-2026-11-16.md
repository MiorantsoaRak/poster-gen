**Verdict: REJECT.** The derived balance is sound against the current job lifecycle. Payment moves and restore reconciliation still need correction.

1. **P1 — A payment can still fund two shops.**  
   D-005 permits `correct A 0 --amount-ar -1000`, then a bought grant to B with `--move-from A`. A keeps all its unspent credits; B receives more. The destination amount also need not equal the reversed amount, so the receipt total can change. See [design:421](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/prepaid-balance.md:421) and its money-only example at line 489.  
   **Fix:** require a matching credit reversal and payment amount, and perform the move atomically. If spent credits prevent reversal, refuse the move or record the owner’s concession separately as offered credits. Check all shops holding that reference.

2. **P2 — Restore replay checks job existence, but needs its restored state.**  
   A backup can contain a `running` job that subsequently succeeded and received a repayment. After restore, the job still exists, so D-005 prints its repayment command—but `correct` requires `succeeded`. Recovery can later interrupt it and return the credit automatically. See [design:470](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/prepaid-balance.md:470), [jobs.py:285](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/jobs.py:285).  
   **Fix:** classify repayments by restored state: replay for charged successes, skip terminal failures, explicitly defer unresolved jobs. Also recreate missing shops with `--welcome 0` before replaying their original grants; otherwise the default welcome grant can replace a different original amount.

3. **P2 — A scene-based `blocked` flag wrongly disables text textures.**  
   D-003 checks a scene’s estimate; D-006 applies that answer to every image button. With USD 0.35 remaining, a USD 0.30 texture is admissible, but the USD 0.40 scene check disables it. See [design:338](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/prepaid-balance.md:338), [jobs.py:52](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/jobs.py:52).  
   **Fix:** return blocking reasons per charged operation, using its actual estimate.

4. **P2 — The proposed history omits returned credits.**  
   The dashboard seam unions grants with **counted jobs**, excluding failed, interrupted and cancelled jobs—the records needed to explain returns under R-SHOP-DASH-002. See [design:540](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/prepaid-balance.md:540).  
   **Fix:** history includes every `takes_credit = 1` job, with admission and terminal timestamps. Only the balance query filters to counted statuses. The amended R-BALANCE-003 is otherwise honest about losing immutable debit/release lines.

5. **P2 — Cached cancellation answers retain dollar fields.**  
   Removing `usage` from `get_job` leaves historical cancellation responses in `mutation_keys`. Replaying their keys returns the stored body unchanged, including `usage.recorded_micros`. See [jobs.py:139](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/jobs.py:139), [store.py:52](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/store.py:52).  
   **Fix:** define response compatibility for these replays and test a pre-0014 cancellation key after migration. Checking the browser document for `$`/`USD` cannot prove the API contract.

**Round-1 disposition**

| Finding | Status |
|---|---|
| P1-1 Lost trigger undetected | CLOSED |
| P1-2 Restore reconciliation | PARTIAL — finding 2 |
| P2-3 Payment reassignment | PARTIAL — finding 1 |
| P2-4 Double repayment | CLOSED |
| P2-5 Pause/retry semantics | CLOSED |
| P2-6 Buying shown before service blockage | CLOSED |
| P2-7 Consumers/task boundaries | CLOSED |
| P3 Constraint-error status | CLOSED |

`BEGIN IMMEDIATE` serialises admission against negative corrections across processes. Current writers neither delete/reassign jobs nor revive terminal states; the proposed trigger permits same-status updates and recovery’s requeue. Permanent guards fit the rehearsal if checked after migration on every run; legitimate schema changes must update their expected SQL. Exact SQL comparison may reject harmless formatting changes, but fails closed.

Keep the derived model, admission-only pause and flat read limit. The pilot grant in a forward-only migration is acceptable with an explicitly approved amount and its conditional rehearsal assertion. Task order is sensible; split T-BALANCE-004 into operator commands and restore reconciliation.

No files changed or tests run; no network, device, production, paid or store-writing commands used. SQLite 3.40.1 execution remains unverified.