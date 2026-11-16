**Verdict: REJECT.** Admission is sound in principle, but restore handling and protection of the release trigger need revision before implementation.

1. **P1 — The rehearsal can miss a lost release trigger.**  
   D-BALANCE-001 checks trigger names only through migration 0014’s `ADDED`. The rehearsal evaluates **pending migrations only** ([rehearse.py:90](backend/src/affiche/rehearse.py:90), [rehearse.py:107](backend/src/affiche/rehearse.py:107)); its preservation hashes cover table rows, not triggers. A later `poster_jobs` rebuild could drop `poster_jobs_credit_back` and still pass. Add a permanent check of the credit constraints and trigger definition, plus a regression where a later migration drops it. Keeping the trigger is reasonable once that safeguard exists.

2. **P1 — “Type the same references again” is insufficient after restore.**  
   D-BALANCE-004 says to replay grants **and corrections**, but a correction naming a post-backup job will fail: that job no longer exists. Replaying grants without reconciling lost debits also returns credits for images already downloaded; restoring the database cannot retract those files. The script preserves the replaced database ([restore.sh:40](deploy/restore.sh:40)), so specify reconciliation against it, while stopped, covering grants, debits and job-linked corrections together. Define the loss policy when that database is unavailable. R-BALANCE-003 is not satisfied by the proposed procedure alone.

3. **P2 — Payment reassignment duplicates the payment history.**  
   D-BALANCE-004 permits reversing credits in the wrong shop, then granting the same payment to the right one. The reversal has no `amount_ar`; both bought grants remain counted as receipts by the dashboard’s proposed query. One payment becomes two receipts—and can fund both shops if the first already spent its credits. Give a payment one service-wide identity, and distinguish reassignment from another payment. No separate payments table is necessarily required.

4. **P2 — `UNIQUE(job_id, kind)` does not prevent double repayment.**  
   D-BALANCE-001/004 claims it does, but a job can have both a `release +1` and a `correction +1`. The specified `correct` function checks ownership, not whether the credit was already returned. The schema also permits a release without a matching debit. Define and test the permitted job-linked correction: a charged job, no prior repayment, and the allowed amount. Keep unrelated courtesy grants separate.

5. **P2 — Pause does more than the stated default promises.**  
   Owner decision 7 says admitted jobs finish. However, `reserve_rate_limit_retry` calls `_reserve`, which calls `provider_guard` ([jobs.py:208](backend/src/affiche/posters/jobs.py:208)). Adding pause there makes an admitted job fail after a provider 429 ([worker.py:65](backend/src/affiche/posters/worker.py:65)). Either exempt retries from the manual admission pause or explicitly approve that exception and test its credit release. The pause also blocks chat reads, styles and text proposals; those need accurate wording beyond “image creation paused.”

6. **P2 — The zero-credit UI contradicts the refusal priority.**  
   D-BALANCE-002 intentionally prioritises service pause and daily limits over buying credits. D-BALANCE-005 instead shows purchase instructions at zero without sending anything, while `/api/balance` supplies neither pause nor daily-limit state. A paused shop is therefore told to buy when buying cannot help. Include the relevant blocking state in the balance response and apply the same priority in the dialog.

7. **P2 — API consumers and task boundaries are incomplete.**  
   `/api/usage` is also read by [test_typography.py:267](backend/tests/test_typography.py:267), not just the listed smokes. Job `usage` is asserted in [test_poster_jobs.py:440](backend/tests/test_poster_jobs.py:440) and [test_poster_visuals.py:574](backend/tests/test_poster_visuals.py:574); update these to inspect the provider ledger directly. Update `backend/api/README.md` too.  
   Image admissions appear in ten backend test modules; second-shop fixtures need explicit funding as well ([test_api.py:376](backend/tests/test_api.py:376)). One helper can be reused, but cannot eliminate those fixture changes. Split T-001 into smaller verified slices. Also fix T-002’s “no dollars left” review gate: estimates and job usage deliberately survive until T-004.

**Checks that passed on inspection**

- `mutate` replay and rollback semantics support atomic admission and debit ([store.py:42](backend/src/affiche/posters/store.py:42)); `BEGIN IMMEDIATE` serialises competing writers.
- Current terminal paths supply `finished_at`. The trigger operates within their transaction; repeated terminal updates are protected by `NOT EXISTS`. A first release with no timestamp aborts the update rather than losing the credit.
- The origin rule is internally consistent: with each origin nonnegative, the proposed debit cannot refuse a positive total because it chose the wrong origin. Negative corrections are deliberately limited to that origin’s available credits.
- The `_pending` finding is correct ([service.py:187](backend/src/affiche/posters/service.py:187)). Its missing kinds have finalisers already; removing the filter is a suitable fix. Test recovery for texture, text proposal and render, without another provider call.
- `/api/balance` needs the proposed two-shop coverage; retain the cross-shop job refusal checks.

**Owner defaults and remaining gaps**

Decision 3 needs explicit cost acceptance: the ceilings bound **recorded reservations and estimates**, not proven provider charges ([admission.py:295](backend/src/affiche/visuals/admission.py:295)). Unknown outcomes retain estimates, which helps, but does not establish a hard dollar bound.

Decision 1 should grant the pilot’s opening balance after migration **before public traffic resumes**, rather than expose a temporary zero balance. Decisions 2, 4 and 5 are reasonable working defaults. Decision 6 is workable only with acceptance that suspension also removes access to editing and downloads. Decision 7 needs the retry clarification above.

P3: D-BALANCE-001 promises `500 internal_error` for constraint failures, but the existing middleware maps `SQLAlchemyError` to `503 storage_unavailable` ([api.py:273](backend/src/affiche/api.py:273)). Align the contract and tests.

No files changed; no tests, network, device, production or paid commands run. Exact fixture failure counts and SQLite 3.40.1 behaviour remain unverified.