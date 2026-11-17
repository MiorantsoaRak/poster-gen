**T-ADMIN-003: APPROVE WITH FIXES.**  
**T-ADMIN-004: APPROVE WITH FIXES.**

No P1 finding. I found no double-write path, shop-session bypass, alternative balance calculation, or password logging in the reviewed diff.

1. **P2 — T-ADMIN-003, shared with T-ADMIN-004: narrow the `LookupError` mapping.** [admin.py:89](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/admin.py:89)

   `LookupError` includes `KeyError` and `IndexError`. Consequently, programming defects become 409 `operator_refused`, including their exception text, instead of the sanitized 500 response. A memory-only probe confirmed both cases; rollback happens first, so this does **not** preserve partial writes.

   Map only deliberate domain refusals. Unknown shops already pass through `find()` and receive 404. Add a regression proving unexpected lookup exceptions roll back and produce sanitized 500 responses. This also needs a small correction to the design’s mapping table.

2. **P3 — T-ADMIN-004: the maximum accepted end date crashes payments.** [credits.py:265](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/credits.py:265)

   `GET /api/admin/payments?start=2026-01-01&end=9999-12-31` accepts the date, then `end + timedelta(days=1)` raises `OverflowError`. It becomes 500 `internal_error`.

   Either reject this boundary with 422 or support it without constructing an out-of-range date. I reproduced the overflow by invoking the actual endpoint with a fake read connection.

**Rulings on the deviations**

| # | Ruling |
|---|---|
| 1 | Accept `reads.today()`: admission and dashboard retain the same query. |
| 2 | Accept the additional `LINES` columns: existing consumers use named fields. |
| 3 | Accept the sixth `Recorded` site: repeated amount fixes need the duplicate response; CLI text remains unchanged. |
| 4 | Accept shared `left`/`warning`: preserves the CLI calculation and comparison. |
| 5 | Keep `if welcome`: preserves refusal of CLI `--welcome -1`. |
| 6 | Accept logging `sessions_ended` only above zero: zero deletes change nothing. |
| 7 | Accept line ordering, 422 for reversed periods, and default history limit 50. Fix the maximum-date boundary above. |
| 8 | Narrow it as finding 1 recommends. |

Other conclusions from the review:

- Writes call the shared functions within `operator_tx`; session validity and its time check occur after `BEGIN IMMEDIATE`. Hashing happens before the transaction; non-money journaling happens after commit.
- Duplicate handling covers folded references, repayments under another reference, conflicting move destinations, amount-fix-then-move, and move chains. Cross-shop `existing` lines are intentional and operator-only.
- List and mutation balances use `credits.balance`. History uses a composite cursor with deterministic tie ordering; the added tests cross timestamp ties.
- Payment bounds correctly include an ordinary end day and exclude the following midnight. Move entries preserve the total received.
- All new routes appear in the security inventory. A source-wide check found only three `Refused` construction sites supplying `detail`/`existing`, all in `admin.py`.
- With the configured standard `StreamHandler`, a stream-write failure is swallowed by logging: the committed action still returns successfully. A memory-only broken-stream probe confirmed this.
- I found no weakened existing assertion or additional CLI behavior change beyond the move-refusal message.

The design explicitly exempts money actions from journal logging because their ledger lines carry the actor. The implementation follows that exception; the acceptance bullet saying every changed write journals should be qualified accordingly.

No files changed. I did not rerun pytest or mutation tests because they write temporary stores; reported counts remain unverified.  
No production, device, deployment, `.env`, or `data-probe` access; small-box performance and deployment SQLite compatibility remain unmeasured.