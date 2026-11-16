**Verdict: APPROVE for T-BALANCE-001.** No new P1/P2 defect or unmet task requirement found.

Round-1 findings:

- **Ledger replacement — CLOSED.** [0014_credits.py:66](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/migrations/versions/0014_credits.py:66) covers collisions on id, repayment job, and shop/kind/reference. NULL job references behave correctly.
- **Job replacement/deletion — CLOSED.** [0014_credits.py:70](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/migrations/versions/0014_credits.py:70) protects deletion, id/rowid replacement, the partial image index, and immutable job identity.
- **Redundant `move` query — CLOSED.** Removed; the payment triggers establish its precondition.

The per-shop `HAVING`, positive corrected payment total, and exact monetary reversal match v4. All eleven guards match the migrated schema. Existing enqueue, cancellation and recovery writes remain compatible, including `running → queued`. Nothing in application code calls the credit module or charges existing jobs.

The [unique-key regression test](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_credits.py:245) pins the partial index’s predicate. Future index changes must update the replacement trigger and its guard together. No further removable logic identified.

**Known P1 — SEPARATE TASK: shop identity replacement.**  
[0013_shops.py:32](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/migrations/versions/0013_shops.py:32) still permits `REPLACE` when recursive triggers are off. I reproduced replacement at the same numeric shop id: the new identifier inherited the existing balance **with foreign keys enabled**, while balance guards passed. T-SHOP-REPLACE should close this before release and also cover ordinary id/rowid updates with foreign keys off, through a forward migration.

Other stated limits:

| Limit | Ruling |
|---|---|
| Dropping triggers, rebuilding schema, `writable_schema` | **ACCEPTABLE** privileged-writer boundary; rehearsal detects guarded schema changes, without a startup check. |
| `ignore_check_constraints` | **ACCEPTABLE** deliberate disabling of integrity enforcement. |
| Incremental BLOB writes to unindexed text metadata | **ACCEPTABLE** native-writer boundary; immutability claims need that qualification. |
| Hand-written id −1 | **ACCEPTABLE** documented failure closed; the same caveat applies to job rowid −1. |
| Reference case/spacing | **SEPARATE TASK**, T-BALANCE-004’s input policy. |

Refusing **every** job deletion is intentional and stated in amended R-BALANCE-003. Future poster/shop deletion needs a retention design. Changing or deleting a creation did not erase its job debit.

**Verification:** SQLite 3.53.1; **134 adapted in-memory credit cases passed**, including all **57 bypass statements refused with unchanged database contents**. Fourteen guard/rebuild cases passed at the guard layer. The populated migration fixture preserved existing rows and provider ledgers, granted nothing, and left old jobs uncharged.

Not checked: normal filesystem/WAL suites, full rehearsal, 45 mutation runs, browser smokes, or SQLite 3.40.1; reported results are not counted as independently passed. No files changed or restricted resources accessed.  
Release risk: T-SHOP-REPLACE and the release-image rehearsal remain outstanding.