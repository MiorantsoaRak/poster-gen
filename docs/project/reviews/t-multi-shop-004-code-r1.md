**APPROVE — no P1/P2 defects found.** T-004 matches the approved design; no unmet requirement within this task’s scope.

- **P3 — add focused concurrency tests.** The existing race test covers two admissions from one shop against the service cap ([test_poster_jobs.py:98](backend/tests/test_poster_jobs.py#L98)). It does not directly test the new daily ceiling or two different shops racing against the service cap. The implementation is correctly serialized: `mutate`, `_admit` and retry reservation all use `write_tx`, which issues `BEGIN IMMEDIATE` ([db.py:39](backend/src/affiche/db.py#L39)).

**Guard and ledger:** refusal order is suspension → service cap → shop ceiling. Exceptions roll back the job, mode marker and reservation. Scene, refinement, plan, look, text proposal, text effect, chat read and the 429 retry reach the guard. There is no paid cutout path currently. Evaluation calls retain their separate admission path and still count toward the service cap. Ownership, idempotency, ADR-095 and reservation/release behavior are unchanged.

The day is **UTC**, resetting at **03:00 in Madagascar**, explicitly documented in the design. Calls remain attributed to their reservation’s `created_at` after completion across midnight. This is an admission-day budget, not a local-calendar-day budget.

**Queue:** ordering matches the approved SQL ([jobs.py:146](backend/src/affiche/posters/jobs.py#L146)). A continuously queuing shop cannot keep an otherwise waiting shop behind its entire backlog. Never-served shops sort first; ties use creation time and ID. Recovery clears that job’s start time but retains history from other jobs. Free jobs count as turns as designed; this means fairness is across all jobs, with no separate guarantee for paid jobs while the same shop keeps starting free work.

**Reads:** guard → daily read count → two-running-read limit is correct. Refusal reserves nothing. Two crashed rows can block reads until they become older than 60 seconds; the next admission sweeps them. This behavior is documented, although the user-facing “quelques secondes” can mean nearly a minute ([reads.py:512](backend/src/affiche/posters/reads.py#L512)).

**Password route:** one verification, shared login limits checked twice, Argon2 outside the write transaction, and a conditional update against the verified hash. Other sessions of that shop end; the caller’s remains; other shops are untouched. Suspended shops are refused by the session boundary. Origin, bundle and `X-Affiche-Shop` checks apply. Minimum length **10** and no cookie change are explicitly designed ([auth.py:177](backend/src/affiche/posters/auth.py#L177)).

**Declared deviations:** 1 is conservative race accounting; 2 and 5 are explicitly designed; 3 matches the approved queue; 4 correctly isolates the scene-count test. Deferring the documents in 6 to T-005 is acceptable, provided they are corrected before release.

**The smoke’s two 422s are expected:**

- Injected `contact_unsupported` response ([browser_smoke.py:1474](frontend/tests/browser_smoke.py#L1474)).
- Real `acknowledgement_required` after reopening a low-resolution photo ([browser_smoke.py:2026](frontend/tests/browser_smoke.py#L2026)).

Stub reservations and final costs are zero; the daily ceiling cannot cause those responses. Its refusal would also be **429**, not 422.

**Operating notes:** USD 2 is a reasonable initial safety bound, not a promised image allowance. Using the supplied costs and USD 0.40 reservation, expect roughly 40–55 sequential images/adjustments, or eight older-model images, before other costs. Five outstanding image reservations alone consume the allowance. Unknown outcomes retain estimates. These constraints deserve observation during the invitation pilot.

No later-task implementation, `queue_full` or credit mechanism leaked in. No worthwhile simplification or removable production code identified.

Tests were not run: they write databases/files, prohibited in this read-only review. Reported passes remain implementer evidence; no files changed, network accessed, or protected data read.