1. **P2 — Alembic CLI bypasses the configured database and transaction setup.** [env.py:23](</C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/migrations/env.py:23>), [alembic.ini:5](</C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/alembic.ini:5>).

   `alembic upgrade head` uses a separate engine targeting `data/affiche.db`. On this checkout, `data/` does not exist, so that command cannot open its database. With a custom `DATA_DIR`, it targets the wrong database. It also bypasses the WAL/FK hooks and explicit transaction control: a migration failure can leave partially applied DDL. The tests exercise only `migrate(engine)`, concealing this difference.

   **Fix:** replace the `engine_from_config` branch with `make_engine(load_settings().data_dir)` and run migrations inside `write_tx()`, disposing the engine afterward. Remove the hard-coded `sqlalchemy.url`. Test the CLI against an initially nonexistent temporary data directory.

2. **P2 — The concurrency test has an uncontrolled startup window and unbounded waits.** [test_db.py:69](</C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_db.py:69>), [tx_worker.py:22](</C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/tx_worker.py:22>).

   Starting the waiter first does not establish that it reached its stdin wait. Slow Windows startup can consume the holder’s 1.5-second sleep and fail a correct implementation. Conversely, suspension after recording `started`, but before entering `write_tx()`, can let a deferred-BEGIN mutation pass after the holder commits. The timestamp assertion proves when the timestamp was recorded, not when locking was attempted. Both holder `readline()` calls can also hang before either 15-second timeout applies.

   **Fix:** add a waiter-ready handshake after connection initialization; let the parent explicitly release the holder; bound every communication wait. Assert the actual emitted `BEGIN IMMEDIATE` alongside the blocking behavior, so scheduling cannot conceal the deferred-BEGIN mutation.

Verification:

- **19 configuration tests passed**, with bytecode, pytest caching and capture disabled.
- **Four database tests remain unverified here:** the full-suite attempt stopped before collection because the sandbox cannot create temporary files. I did not reproduce the reported 23-pass result.
- All **15 migration statements exactly match** the design after removing comments and whitespace.
- `git check-ignore` printed all four requested paths.
- Claims **1–6 are supported** by installed-source inspection and targeted checks; migration atomicity was checked by source inspection. Python documents the deferred transaction behavior of [`autocommit=False`](https://docs.python.org/3.12/library/sqlite3.html#transaction-control-via-the-autocommit-attribute).
- Claim **7 overstates the test’s guarantee**. Cross-process [`time.monotonic()`](https://docs.python.org/3.12/library/time.html#time.monotonic) comparability is valid; synchronization is the issue.

No files modified.

**Verdict: APPROVE WITH FIXES.**