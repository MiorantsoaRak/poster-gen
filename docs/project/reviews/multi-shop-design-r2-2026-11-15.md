**Verdict: REJECT.** V2 closes several round-one findings, but two P1 gaps remain.

**Actionable defects**

1. **P1 — Chat reads bypass the suspension cutoff.** D-006 guards `jobs.dispatch`, but reads reserve in `_admit` and later call `_ask` directly. Suspension between those steps can still be followed by a provider call. Add a dispatch transition for reads that checks suspension and releases an unsent reservation at zero cost. Test suspension between admission and dispatch. This fails R-006’s proposed “no further provider call” criterion. Evidence: [design:421](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/multi-shop.md:421), [reads.py:627](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/reads.py:627), [reads.py:634](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/reads.py:634).

2. **P1 — Dropping late response bodies does not stop late cookies.** `epoch` cannot prevent the browser applying `Set-Cookie`. An A logout accepted before B signs in can deliver its cookie deletion after B’s successful login. Concurrent sign-ins can similarly leave the cookie belonging to the earlier identity whose response arrives last. The header guard only checks requests; it cannot repair response ordering. Define serialization of cookie-changing operations across tabs through response completion, with session reconciliation before showing the application. Test reversed login/logout response delivery. R-004’s identity boundary remains incomplete. Evidence: [design:451](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/multi-shop.md:451), [api.py:621](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/api.py:621), [api.py:629](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/api.py:629).

3. **P2 — The login overshoot guarantee still does not follow from the pseudocode.** The verification slot ends before the failure-recording transaction. While that transaction waits for SQLite’s writer, further requests can acquire slots, see the unchanged counter and verify. Keep the slot until the failure/session transaction finishes; Argon2 can still run outside the write transaction. Test with a deliberately blocked writer. Evidence: [design:201](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/multi-shop.md:201), [design:223](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/multi-shop.md:223).

4. **P2 — The retained paid card needs a complete storage lifecycle.** `nextStep(item) === 'replay'` also matches retired cards whose request remains attached. Use the existing unresolved-card predicate: paid, spent, unfinished, and awaiting replay. Also exempt retained unresolved records from ordinary thread eviction, and specify what happens if rewriting the record fails before reload. Currently chat cleanup removes old threads without considering unresolved payment records. Shop prefixes and server ownership prevent B replaying A’s request, but preservation for A is not yet guaranteed. Evidence: [design:465](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/multi-shop.md:465), [ChatView.vue:59](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:59), [ChatView.vue:101](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:101).

5. **P2 — T-003 depends on code assigned to T-004.** T-003 scopes `/api/usage` using `spent_micros(shop=…)`; that helper is introduced in T-004. Move the helper and its tests into T-003. The route-set/password-route dependency from round one is fixed. Evidence: [design:321](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/multi-shop.md:321), [design:546](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/multi-shop.md:546).

**Round-one findings**

| Finding | Ruling |
|---|---|
| 1. Previous shop’s browser state | **PARTIAL** — reload and epoch rules added; cookie-response ordering remains |
| 2. Suspension at dispatch/recovery | **PARTIAL** — job paths covered; reads omitted |
| 3. Password adoption/revocation | **CLOSED** |
| 4. Read precedence/concurrency | **CLOSED** |
| 5. Sign-in timing/limits | **PARTIAL** — timing caveat correct; concurrency guarantee still overstated |
| 6. Global read keys | **CLOSED** |
| 7. Prepaid/admin transaction seams | **CLOSED** |
| 8. Autosave trapping sign-out | **CLOSED** |

**Migration and boundary notes**

The two rebuilds are sound in the stated order: foreign keys disabled before `BEGIN IMMEDIATE`, parent rebuilt under its original name, read ledger copied with `UNIQUE(shop_id,key)`, references checked before commit. A failure between rebuilds should roll back both rebuilds and the Alembic version together.

The previous notes are **CLOSED at design level**: `looks` preservation, post-commit startup failure, fingerprint removal during adoption, logout’s shop-header check, and the two-part status boundary.

**P3:** add fault injection between the rebuilds and after the read-ledger swap. Strengthen rehearsal comparisons with preserved row contents: equal counts and ledger sums alone cannot detect changed version payloads. Evidence: [design:509](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/multi-shop.md:509), [design:529](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/multi-shop.md:529).

**Requirement wording and the three deviations**

- **R-003: accept.** Provider-spend ceiling is explicit; removing the queue cap follows the lead’s ruling.
- **R-004: accept subject to finding 4.** The exception and cache disclosure are clear. “Visible to no other shop” describes application access, not protection from browser tools.
- **R-005: accept.** An automatic rehearsal before stopping the old service satisfies the ruling. Docker being unavailable is an unresolved verification gap, not a reason to reject this approach. Require release-image evidence and a failed-rehearsal test proving the stop/start sequence is never reached.
- **R-006: accept subject to finding 1.** Retained but unusable sessions are coherent. Customer-credit release remains mandatory before the complete release ships.
- **Additional R-001 amendment: accept.** Local and international phone forms may remain distinct **operator-chosen identifiers**. Do not describe this as telephone-number equivalence.
- **`/api/usage`: acceptable.** The cap and start date are configuration, not another shop’s totals. Keeping the existing fields avoids temporary contract churn; replace them with credits in the prepaid feature.

Keep SQLite, the rebuilds, connection-taking shop functions and the daily provider ceiling. The temporary loopback status-access mechanism can be removed once administration owns the route.

Still outside the current failure analysis: reservations queued before midnight can dispatch on a later day while counting against their admission day. Clarify whether this is a daily admission budget or a dispatch-day spending ceiling.

Read-only source review; no files changed, commands executed against stores, tests, network, device, production or paid operations, and no `backend/.env` access. Migration, browser and Docker behavior remain unverified by this review.