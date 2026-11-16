**Verdict: APPROVE.** No P1 or P2 defect found.

This change makes image admission hold one credit atomically and adds the 402 purchase guidance. The implementation matches T-BALANCE-002 by inspection.

Two P3 coverage notes:

1. **“Nothing left” does not check every table.** [test_poster_jobs.py:132](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_poster_jobs.py:132) compares three table counts and the balance. Admission also writes `meta.provider_mode`, already seeded before these refusals. Add a refusal with that key initially absent and compare `meta` and credit-ledger rows. The current transaction correctly rolls these writes back; the test does not prove it.

2. **Funded second shops leave admission isolation unchallenged.** [test_api.py:416](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_api.py:416) funds every second shop, while the new admission balance assertions exercise shop 1. Checking shop 1’s balance accidentally during shop 2’s admission could escape these tests. Add the asymmetric case: A funded, B empty; B receives 402 and A stays unchanged. This is already planned for T-BALANCE-003.

Verified by inspection:

- Every application enqueue caller uses `mutate`; job, reservation, balance check and key share its transaction. Suspension, cap and day precede credit refusal.
- One remaining credit succeeds; zero or negative availability refuses. Replay returns the stored answer before admission, satisfying the round-3 point.
- Recovery and 429 retries reuse the job. Terminal failures release its credit through the balance query; success retains it.
- Purchase guidance is read after rollback. Storage failure logs a warning and preserves the 402 sentence; other refusals retain their behavior.
- Chat preserves the request for « Réessayer » and « Reprendre », despite `retryable: false`.
- No task 003–006 implementation, weakened assertion, migration or dependency leaked into the diff. No worthwhile production-code simplification found.

`git diff --check -- backend frontend` passed.

Not run: tests, mutations, build or browser checks; they require writes forbidden by this review. Reported pass counts remain unverified. No files changed.