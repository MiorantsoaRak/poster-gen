**Verdict: APPROVE.** No P1 or P2 defect found in T-002. Two P3 notes remain.

- **P3 — The deployment check accepts malformed responses.** [verify.sh:63](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/deploy/verify.sh:63) accepts both `{"authenticated":false,` and `{"authenticated":false}garbage`, confirmed with a read-only shell probe. The change is explicitly in scope, but should require a complete object.
- **P3 — Add regression coverage for the declared hash-upgrade race.** [auth.py:154](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/auth.py:154) safely refuses a concurrent sign-in verified against the pre-upgrade hash, recording a failure despite the correct password. This is a tolerable one-time retry consequence of the required hash recheck. The [upgrade test:463](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_api.py:463) currently exercises sequential sign-ins only.

The substantive checks look correct from source:

- **Credentials:** every well-formed attempt passing both limit checks performs one Argon2 verification. Unknown identifiers, missing passwords and wrong passwords produce the same 401 and normalized failure record. Suspension returns 403 only after successful password verification.
- **Concurrency:** limits are counted before and inside the semaphore; its scope includes transaction commit. Argon2 runs outside the write transaction. Concurrent-failure and blocked-writer tests cover the previous findings.
- **Recheck:** the transactional hash/state lookup prevents sessions after a concurrent reset or suspension. `BEGIN IMMEDIATE` also prevents an upgrade overwriting a newer hash.
- **Identifiers:** normalization matches the design, including truncation before NFKD expansion. Empty, short and expanded overlong keys cannot match stored identifiers; raw API inputs over 64 characters get validation errors. Canonical storage plus `UNIQUE` prevents duplicate normalized identifiers.
- **Sessions:** every protected API route passes through `session_shop`. Suspended sessions become unauthenticated, remain stored and work again after enabling. Legacy failures with NULL identifiers count toward the address limit only.
- **Bundle/browser:** both constants are 3; old sign-ins receive the reload sentence before body validation; old sign-outs remain allowed. Smokes import the bundle number. Identifier autocomplete, capitalization and spellcheck settings suit phone entry. Other browser behavior remains unchanged.
- **Shop creation:** uses the caller’s connection, validates identifier/name and never commits. It preserves the transaction seam needed by later operator/dashboard work.

**Declared deviations:** 1, 5 and 6 are acceptable as implemented. 2 and 3 are acceptable staged omissions, but support after session expiry and the stale documentation must close in T-006/T-005 before release. Deviation 4 is the P3 above; 7 is in scope with the response-validation weakness noted above. No migration or excluded later-task implementation appeared.

No additional abstraction or substantial deletion is warranted. Remaining regression gaps include legacy NULL failure rows and the upgrade/reset combination. The identity gate remains a release prerequisite.

**Verification:** diff whitespace, Python syntax, shell syntax and isolated normalization/pattern probes passed. No files changed or secrets read.

Tests, builds and browsers were not run in this read-only sandbox; the implementer’s pass counts and mutation results remain unverified. No network, device, production, paid or store-writing commands were run.