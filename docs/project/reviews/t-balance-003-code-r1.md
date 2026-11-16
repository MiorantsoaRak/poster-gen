**Verdict: APPROVE.** No P1 or P2 defect found.

What this change does: pauses new AI admissions, exposes each shop’s credits and operation-specific blockers, replaces `/api/usage`, and limits chat reads to 100 per UTC day.

Verified by inspection:

- [jobs.py:63](backend/src/affiche/posters/jobs.py:63): suspension → pause → cap → shop’s day. New requests default to `admission=True`; call 2 bypasses only the pause. Queued jobs continue.
- [jobs.py:83](backend/src/affiche/posters/jobs.py:83): `blocked` only reads and reuses the admission guard with each operation’s estimate. No duplicated budget arithmetic or reservation.
- [api.py:488](backend/src/affiche/api.py:488): balance uses the session’s shop, matches the response contract, exposes no dollar figure, and propagates unexpected refusals. Database errors become 503 through existing middleware. Negative availability remains a signed integer, as designed; admission still refuses it.
- Provider-mode mismatch stops application startup. The preview’s omission of that check creates no normal-running admission gap.
- The pause sentence covers images, styles, texts and reads. Chat preserves retry requests. No remaining `/api/usage` consumer exists in the requested directories; the sole occurrence asserts its removal.
- The smoke replacements preserve the zero-spend check: the whole service’s nonnegative ledger must now equal zero in isolated stub data.
- Both task-002 coverage gaps are addressed. The rollback test compares the five relevant tables, rather than literally every table; its assertions cover admission’s writes.
- No task 004–006 implementation, migration, dependency or screen change leaked in. No unmet task-scope design point or worthwhile production-code simplification found.

`git diff --check` passed. All 12 changed Python files parsed successfully without writes.

Not run: tests, mutations, build or browser checks; those require writes forbidden by this review. Reported pass counts remain unverified. No files changed.