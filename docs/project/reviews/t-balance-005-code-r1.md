**REJECT.** One P1 reconciliation bug can erase a payment’s credits and ariary from the effective ledger.

1. **P1 — Divergent move histories can cancel the entire payment.** [shops.py:239](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/shops.py:239), [shops.py:254](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/shops.py:254).

   Start with a backup containing A’s bought grant: 10 credits, 10,000 Ar. The kept database subsequently records **A→B→C**. After restoring, the operator records **A→C→B**. Both histories are valid through ordinary `move-payment` commands.

   Reconciliation considers four kept rows “here already” and selects only **B’s reversal**. Applying it leaves A, B and C at zero: the payment’s 10 credits and 10,000 Ar disappear. No negative-balance warning appears.

   Migration 0014 permits that insertion: B’s reversal brings its payment total exactly to zero, and the other-shop trigger only tests positive amounts. The Python holder check likewise sees no other positive holder.

   **Fix:** detect conflicting payment histories and refuse the entire copy before committing. Add an integration regression for these two movement orders. The runbook’s “move it … then run again” advice can lead directly into this case.

2. **P2 — The negative-balance explanation promises recovery without establishing the cause.** [shops.py:285](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/shops.py:285), [README.md:498](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/deploy/README.md:498).

   Example: backup has 10 credits; kept history withdraws 10. After restoring, one new generation succeeds before reconciliation. Copying the withdrawal leaves **−1 available, zero pending**, yet the report says a waiting generation holds the credit and its failure resolves the deficit. Even with pending jobs, their release may cover only part of a deficit.

   **Fix:** report the deficit and pending count without asserting causation or guaranteed recovery. Update the runbook and cover zero pending and insufficient pending credits.

3. **P3 — A schema-valid empty timestamp is silently replaced.** [credits.py:95](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/credits.py:95).

   `at or utc_now()` changes `created_at=''` into today’s timestamp. Migration 0014 permits that value, so this violates exact field preservation for such a kept row. Ordinary application writers produce nonempty timestamps.

   **Fix:** use `utc_now() if at is None else at`.

4. **P3 — Filesystem errors can escape the required loss-policy refusal.** [shops.py:184](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/shops.py:184).

   On the supported Python 3.12, an inaccessible parent directory can make `is_file()` raise `PermissionError`. Filesystem errors from `resolve()` also escape: only `sqlite3.Error` is caught. The CLI then produces a traceback without the required loss-policy sentence.

   **Fix:** handle filesystem errors around the path inspection and connection opening, retaining that sentence.

The other implementation choices are reasonable:

- Taking a caller-owned connection plus `Path` preserves transaction ownership. Report mode gets a consistent live snapshot through the engine’s `BEGIN`; apply uses `BEGIN IMMEDIATE`.
- Identifier mapping, global insertion order, missing-shop blocking, repayment filtering and rollback on insertion failure look correct. I found no separate duplicate-insert, wrong-shop mapping or partial-commit path.
- Explicit refusals without printing an accumulated report are acceptable. Listing all missing shops while blocking only required shops is also acceptable.
- Reusing `_key`, `LINES` and `_line` is smaller than adding another abstraction. Keep the plain inserts and trigger enforcement; fix history reconciliation above them.

`mode=ro` protects the kept database from writes and checkpointing, but **does not mean lock-free or sidecar-free**: SQLite may create/update `-shm` and use normal reader locks. The configured writable `/data` mount and UID 10001 are consistent with that requirement. SQLite documents this support from 3.22 onward. [SQLite WAL documentation](https://www.sqlite.org/wal.html#read_only_databases). `resolve().as_uri()` correctly escapes spaces, `%`, `?`, `#` and Unicode, preventing filename text from becoming URI options. [SQLite URI documentation](https://www.sqlite.org/uri.html).

The restore-script report failure is contained by `|| echo`; it does not change `STATE`, invoke `fail`, or start the service. The fake remains strict: unexpected Docker/Python calls are logged, rejected, and asserted absent. The new tests are substantive, but miss divergent movement histories; exact output assertions currently reinforce the misleading deficit explanation.

I confirmed findings 1–3 using extracted source functions and synthetic objects, without database connections; Python AST parsing and `sh -n deploy/restore.sh` passed. No files were modified.

Not checked: pytest/mutations, real SQLite replay, Docker/UID filesystem behavior, devices or production. The reported passing suite does not cover the P1 history merge.