**REJECT.** The reported move-order bug is fixed, but the replacement check still permits incorrect financial copies.

What this change does: restores missing credit lines in order, preserves their original fields, and skips payment histories that conflict with the restored database.

1. **P1 — Matching shop/kind sequences can still duplicate a payment.** [shops.py:240](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/shops.py:240), [shops.py:251](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/shops.py:251).

   Concrete case, using ordinary operator operations:

   - Kept: A receives **10 credits / 10,000 Ar**, reference `MV-1`, then moves that payment to B.
   - After restoring a backup from before that payment: retype A’s grant as `mv-1`, then make an **amount fix of +1,000 Ar**, with zero credits.
   - Both histories begin `(A, grant), (A, correction)`. The prefix passes, and both A rows count as already present—even though one correction reverses a payment and the other increases its amount.
   - Reconciliation copies B’s grant. A retains **10 credits / 11,000 Ar**; B gains **10 credits / 10,000 Ar**.

   The spelling check only checks B’s own lines. The holder trigger compares stored references exactly, so A’s lowercase reference does not block B’s uppercase grant.

   This also fails without spelling differences: kept grant **10,000 Ar**, followed by **+1,000 Ar** correction; retyped grant already **11,000 Ar**. Copying the correction produces **12,000 Ar**.

   **Fix:** compare financial contents and repayment identity alongside shop/kind before accepting the prefix or treating its rows as present. On mismatch, skip that payment and continue unrelated lines. Add both regressions. Restoring the holder check alone would not fix the second case.

2. **P2 — A deferred repayment can remain permanently skipped after its job succeeds.** [shops.py:245](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/shops.py:245), [shops.py:262](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/shops.py:262).

   Backup contains A’s payment and B’s running charged job. Subsequently, the kept history records B’s repayment **under that payment’s reference**, then moves A’s payment to C.

   First reconciliation skips B’s pending repayment and copies A→C. After B’s job succeeds, rerunning sees:

   - Kept: A grant, **B repayment**, A reversal, C grant.
   - Here: A grant, A reversal, C grant.

   The tool now calls its own earlier copy divergent and skips B’s eligible repayment. “Run again after it ends” never delivers the credit.

   **Fix:** permit the specific history gaps created by repayment filtering while still validating the contents of present lines and the ordering of payment movements. Add this pending→succeeded regression.

3. **P3 — The new permission test fails on Windows.** [test_shops.py:791](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_shops.py:791).

   `os.geteuid()` is unavailable on Windows, a documented development platform. This test raises `AttributeError` before reaching its remaining assertions.

   **Fix:** guard the permission-specific block with `os.name == "posix" and os.geteuid()`.

**Round-1 dispositions:**

| Finding | Status |
|---|---|
| P1: divergent A→B→C / A→C→B moves | **CLOSED** for that reported case; new P1 above |
| P2: misleading below-zero explanation | **CLOSED** |
| P3: empty timestamp replaced | **CLOSED** |
| P3: filesystem errors escape loss-policy handling | **CLOSED** |

**Your policy questions:** skip-not-refuse is appropriate. It preserves the current payment history and allows unrelated recovery without requiring deletion of immutable rows. Removing the holder check is **unsafe with the present prefix check**, as finding 1 demonstrates.

The runbook broadly matches the implementation. Its promised repayment rerun at [README.md:492](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/deploy/README.md:492) fails in finding 2; its “typed otherwise” handling needs to cover differing financial contents.

For removable code, newly appended `held` entries never use their `kind` or `amount` fields. Those can go; no broader abstraction is needed.

Checks passed: five Python files parsed, restore shell syntax, diff whitespace, timestamp preservation, and three extracted-function counterexamples using synthetic objects.

Not checked: pytest/mutations, real SQLite replay, Docker, Windows execution, devices or production. No files modified; `.env` and `data-probe` untouched.