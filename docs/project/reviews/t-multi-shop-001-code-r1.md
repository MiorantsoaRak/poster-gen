**Verdict: APPROVE WITH FIXES.**

- **P2 — Phone-session startup changes the database before checking the process lock.** [phone_session.py:89](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/deploy/phone_session.py:89) migrates and commits a password reset before application startup acquires `api.lock`. If another API owns `data-probe`, the second launch revokes its sessions and replaces its password, then fails with `AlreadyRunning`. Perform initialization under the existing guarded startup lifecycle. Add a stubbed regression proving a held lock leaves the schema version, password and sessions unchanged. This change is explicitly within T-001’s scope.

- **P3 — The declared password-reset race remains.** [auth.py:125](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/auth.py:125) verifies outside the transaction without rechecking the stored hash before creating a session. Deferral to T-002 matches the task split; its planned transactional recheck must land before release.

The core migration looks consistent with the approved design:

- Migrations **0001–0012 are byte-for-byte unchanged against HEAD**. The rebuilds preserve the original columns, references, trigger and required indexes.
- `migrate` retains `BEGIN IMMEDIATE`, checks references before commit, restores foreign-key enforcement and invalidates the connection if restoration fails. Tests cover both requested fault boundaries.
- Read admission and replay use `(shop_id, key)`. Password adoption implements the five cases and fingerprint rule without logging hashes or allowing a stale environment hash to overwrite the stored password.
- **Round 3 finding 4 is addressed:** original-column hashes cover all three changed tables; version and additions are checked separately. Content-damage tests include unchanged counts and ledger sums.

Declared deviations **1–4 are reasonable**: callers match the reduced login signature, unknown shops fail explicitly, migration-local contracts avoid another registry, and Alembic’s loaded modules simplify discovery. **5 is acceptable** as a no-pending-migration check, though it proves no upgrade occurred. **6 needs the fix above; 7 remains a tracked T-002 obligation.**

No later-task implementation leaked in. No SQL requiring SQLite newer than 3.40.1 was identified. Reusing guarded startup should also remove the phone script’s duplicate migration; hash its password outside the write transaction.

**Verification:** Python syntax parsing and diff whitespace checks passed. No files changed or secrets read.

Tests were not run because they require filesystem writes; the implementer’s pass counts and mutation claims remain unverified. Browser, paid, production and release-image behavior were not exercised.