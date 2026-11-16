What this change does: adds the credit ledger, balance functions and permanent schema checks without enabling charging. **Verdict: REJECT — two P1 database bypasses.**

1. **P1 — `REPLACE` can rewrite the permanent ledger.**  
   [0014_credits.py:44](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/migrations/versions/0014_credits.py:44), [db.py:24](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/db.py:24)

   The DELETE trigger does not protect implicit replacement deletes when `recursive_triggers=0`, the connection default left unchanged by the app. `INSERT OR REPLACE` using an existing `(shop_id, kind, ref)` successfully replaces its credits, amount and date.

   This also breaks the payment floor: grant **1,000 Ar**, correct **−400 Ar**, then replace the original grant with **100 Ar** → total **−300 Ar**. Both payment triggers allow it; the schema guards still pass.

   **Fix:** protect replacement collisions, including primary key, reference and repayment keys. Add direct SQL regression tests; an unconditional DELETE trigger alone is insufficient with recursion disabled.

2. **P1 — A finished debit can be replaced or deleted. Deletion classification: BLOCKS.**  
   [0014_credits.py:59](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/migrations/versions/0014_credits.py:59)

   `poster_jobs_final` guards UPDATE only. Replacing the same job ID successfully changes `succeeded, takes_credit=1` into `queued, takes_credit=0`. I reproduced this with an existing `poster_calls` child: foreign keys remain valid, the credit returns, and every schema guard passes.

   Plain DELETE also succeeds when no child prevents it. The absence of a current deletion caller does not satisfy R-BALANCE-003’s permanent preservation rule.

   **Fix:** add a permanent deletion guard and replacement protection, cover both in `GUARDS`, and test direct SQL deletion/replacement with and without child rows.

The remaining reviewed behavior looks consistent with this task:

- The per-shop `HAVING` form and exact monetary reversal checks match v4. Ordinary multi-row INSERTs see earlier rows; `RAISE(ABORT)` rolls back the statement. `OR IGNORE` does not suppress these trigger refusals.
- Existing job writers respect the new status rule. `BEGIN IMMEDIATE` serializes operator balance checks against another writer when callers follow the documented transaction contract.
- Guards run with nothing pending. Exact SQL comparison detects retargeted or weakened triggers, though it cannot establish that the matched SQL prevents the bypasses above.
- The 0013/0014 preservation contracts fit together. No charging integration from tasks 002–006 leaked in. The French sentence, head assertions and named-column browser seed are justified.
- The single correction slot intentionally prevents moving an amount-corrected payment. That is an approved limitation.
- **Lean:** after fixing the invariants, `credits.move`’s other-shop query at [credits.py:101](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/credits.py:101) is redundant unless deliberate corruption detection is wanted.

**Verification:** 76 `test_credits.py` cases passed using an adapted in-memory fixture on SQLite 3.53.1. Both bypasses reproduced against the actual migrated schema; additional SQL probes ran on 3.46.1. Collection-error mutation kills do not prove behavioral coverage.

Not checked: normal filesystem/WAL suites, reported mutation results, or SQLite 3.40.1. No files changed, network/device/production commands run, or `.env`/`data-probe` accessed; the release-image rehearsal remains required.