**APPROVE WITH FIXES.** Round-3 finding: **CLOSED**. The payment-copy rule now protects credits and ariary for ordinary histories under the same normalized reference key. One **P2** remains in repayment recovery.

**P2 — A different correction can masquerade as an already-restored repayment.** [shops.py:260](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/shops.py:260)

A reproducible sequence:

1. Backup: A has **10 credits / 10,000 Ar**, reference `MV-1`, a running charged job `made`, and sufficient other credits.
2. Kept database: `made` succeeds; the operator records `correct A +1 --ref MV-1 --job made`.
3. After restoring, reconciliation defers that repayment because `made` still runs. The operator then moves the payment **A→B**.
4. `made` succeeds here. Reconciliation now treats A’s **−10 credits / −10,000 Ar reversal** as the kept **+1 job repayment**, because both occupy `(A, correction, MV-1)`.

The output says **“2 here already, 0 to copy, 0 skipped”**, although `made` has never been repaid. Rerunning cannot deliver its credit.

The new slot check detects the mismatch, but `differs` only governs missing non-repayment rows. The earlier `same` branch consumes the repayment before job-specific handling.

Another ordinary variant produces the same result: kept history repays job J1; current history repays J2 under the same payment reference. J1 is incorrectly counted as present.

**Fix:** establish repayment presence using `job_id`. If its original correction slot contains another operation, explicitly name the conflict and require manual repayment using an unused reference; preserve the original-reference policy rather than silently rewriting it. Cover both variants. The runbook’s promised deferred-repayment rerun at [README.md:492](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/deploy/README.md:492) needs that qualification.

For the payment rule itself, the reasoning now holds:

- If both checks pass, current non-repayment rows form an exact prefix; an existing repayment cannot impersonate a missing financial row. Copying completes the kept sequence.
- If either fails, no missing non-repayment row for that key is selected. Current payment history stands.
- Insert refusal rolls the whole transaction back.

Against kept grants, move chains, amount fixes, and histories containing shared-reference corrections or repayments:

| Action after restore | Result |
|---|---|
| Retype identical grant, same spelling | Grant counts as present; matching remaining moves/fix can arrive. |
| Retype with different shop or figures | Current history stands; missing financial rows are skipped. |
| Retype with case/space differences | Identity matches. A remaining row requiring another spelling in that same shop explicitly refuses the whole copy. |
| Move payment | Matching prefix completes; divergent or extended history stands. |
| Fix amount | Matching contents are accepted; differing contents prevent financial completion. |
| Credit-only correction under payment reference | Included in prefix comparison; cannot impersonate an amount fix or reversal. |
| Job repayment under payment reference | Excluded from prefix order; slot comparison prevents the round-3 duplication. Existing-slot repayment collisions remain the P2 above. |
| Required shop missing | Entire copy blocked until creation. |
| Rerun between actions | Successful copies are idempotent; subsequent actions undergo the same checks. Deferred repayments work unless their slot becomes occupied. |

References differing beyond case and whitespace remain separate keys. The tool cannot recognize an external payment retyped under an unrelated reference.

I would **retain the prefix-plus-slot approach**. Blanket exclusion of every touched payment would discard legitimate prefix completions and would not resolve repayment misidentification.

For simplification, store complete current rows in the slot dictionary and reuse it for `same`, replacing the repeated linear search. Keep the spelling guard. The runbook should also say **divergent history**, since an exact replayed prefix remains eligible for completion.

Verification: **294 kept shapes × 4,297 current histories = 1,263,318 synthetic pairs**, with no non-repayment invariant failure; targeted repayment counterexamples, round-3 regression, prior deferred-repayment case and missing-shop blocking checked using extracted functions. Python AST parsing, shell syntax and scoped whitespace checks passed.

Not checked: pytest, actual SQLite replay/triggers, containers, Windows, devices or production. No files changed; `.env` and `data-probe` untouched.  
Remaining risk: an eligible job repayment can stay missing while reconciliation reports it already present.