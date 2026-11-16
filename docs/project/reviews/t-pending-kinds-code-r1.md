**Verdict: APPROVE.** No P1/P2 defects found in this diff.

- **P3 — Persistent failures still produce repeated warnings.** [worker.py:36](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/worker.py:36) logs both failed attempts; [service.py:222](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/service.py:222) repeats the sweep every second. That is roughly two warnings/second/job indefinitely. There is no tight loop, but the “no log flood” claim is overstated. This policy predates the diff; consider throttling duplicate warnings separately.

Verified by inspection:

- All six claimed kinds have finalisers. No application path enqueues `cutout` or `background`, and no remaining code reads `pending_finalisations`.
- Spool recovery returns before provider dispatch ([worker.py:46](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/worker.py:46)).
- Successful finalisation cannot commit twice: `BEGIN IMMEDIATE` serialises writers, and [jobs.py:258](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/jobs.py:258) returns the existing result before invoking the finaliser.
- The three new cases exercise the service loop and assert success plus zero recovery sends. Restoring the old filter would leave these jobs running and fail their assertions. This was established by inspection, not mutation execution.

`git diff --check -- backend` passed.

Not checked: runtime tests or mutation runs under the read-only restrictions; **152 passed** and **1134 passed, 3 deselected** remain implementer-reported. Production, devices, network, paid operations and broader prepaid-balance work were outside this review.