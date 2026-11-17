**Verdict: APPROVE WITH FIXES.** No established P1 blocker. The database-held hash and separate operator sessions fit this codebase. The remaining P2 issues concern the logging promise, uncertain money requests, duplicate-move comparison and compromise recovery.

References below point to [design v2](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/admin-dashboard.md) and [requirements v3](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/requirements/admin-dashboard.md). “Closed” means resolved in the design, pending implementation verification.

| Round-1 finding | Ruling against v2 |
|---|---|
| 1. Stable request identity | **PARTIAL** — frozen requests are specified; reopen/reload and 5xx handling remain incomplete. |
| 2. Images before migration 0014 | **CLOSED** — counted by kind, with explicit regression coverage. |
| 3. Revocation versus money writes | **CLOSED** — session rechecked inside `write_tx`, with a race test. |
| 4. Nested audit recording | **CLOSED — removed**, not fixed. The table and recording hooks no longer exist. |
| 5. End-all control absent | **CLOSED** — confirmed control, matching cookie deletion and second-device test. |
| 6. Error serialization incomplete | **CLOSED** — exception, serializer, model and HTTP-body tests are covered. |
| 7. Public-session security matrix | **PARTIAL** — admin exceptions fixed; public **shop** session operations still incorrectly receive blanket 401 expectations. |
| 8. Task size | **PARTIAL** — substantial improvement; task 001 still combines several independently verifiable changes. |
| 9. Repeated move names no line | **CLOSED** — correction-line ID explicitly required. |
| 10. Worst-case mobile content | **CLOSED** — concrete maximum-length fixtures and initial Cancel focus specified. |

**P2 findings**

1. **The proposed action logs will be dropped by the current logging configuration.**  
   [D-ADMIN-002, line 209](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/admin-dashboard.md:209).

   The launcher calls Uvicorn without configuring application logging ([api.py:903](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/api.py:903)). Installed Uvicorn configures handlers for its own loggers, leaving `affiche.admin` at effective **WARNING**, with no root handler. A read-only logging probe confirmed `INFO enabled: False`.

   Configure an application INFO handler explicitly. Verify emission under the real launcher configuration; `caplog.set_level(INFO)` could conceal this problem.

   Also state the post-commit loss policy: a process killed between commit and `log.info` leaves a successful action without its journal line. Best-effort logging is compatible with decision A, but requirements line 23 currently promises every action is logged. Narrow that promise explicitly. The proposed field allowlist itself is sound: it includes neither payment references nor passwords.

2. **An uncertain money request can lose its identity when the form is reopened.**  
   [D-ADMIN-005, lines 448–451](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/admin-dashboard.md:448), state machine lines 584–590.

   Example: an offered grant commits, its answer disappears, the operator reloads or returns to the shop later, and the form generates another timestamp reference. Submitting it credits again. The document preserves requests through reauthentication, but defines no recovery across navigation/reopening or reload.

   Define that lifecycle explicitly: retain unresolved requests when navigating; after reload, either recover the frozen request or require reconciliation before creating another offered grant/correction. Keep the existing warned **Discard** escape.

   **5xx responses also need an explicit transition.** They are absent from the state machine, while “any other refusal” is called definite. Preserve the frozen request after an uncertain 5xx; HTTP failure alone does not establish rollback. The existing shop client already retains request keys after 5xx ([api.ts:251](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/api.ts:251)).

   The database guarantees deduplication for the same normalized reference. It cannot recognize the same real payment entered as `MV-123` and `MV123`, or an offered grant recreated under a new reference. State that limit beside the two-tab guarantee.

3. **A source correction line cannot establish whether a repeated move matches the request.**  
   [D-ADMIN-003, lines 236–239](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/admin-dashboard.md:236), comparison at lines 452–455.

   A move request contains `from_shop` and `to_shop`. Its duplicate response carries the source correction, which contains no destination. After A→B, a request for A→C encounters the same correction. The promised comparison cannot distinguish those outcomes from that line alone.

   Specify action-specific comparison. Return the associated destination grant/destination when it can be established, or report **“source already corrected; inspect the payment history”** without claiming “as sent.” An amount correction must also remain distinguishable from a completed move.

   Add cases for repeated A→B, conflicting A→C, and a payment whose source correction was an amount fix.

4. **Ending operator sessions does not end access obtained through shop credentials.**  
   [Security, lines 655–659](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/admin-dashboard.md:655), lost-phone runbook at line 565.

   A stolen operator session can reset a shop password, read the replacement, and sign in as that shop. Ending operator sessions or running `operator-password` leaves that password and its shop sessions usable; shop sessions currently last 90 days. Grants and attacker-created shops also survive operator-session expiry.

   Keep ordinary operator revocation scoped as designed, but add a **suspected-compromise recovery procedure**: pause new spending, revoke shop sessions, reset affected shop passwords, suspend unauthorized shops, and reconcile grants. Operator revocation alone is sufficient only when the stolen session was not used.

   Distinguish the operator session’s 12-hour lifetime from the lifetime of access and changes it can create.

5. **The security matrix still contradicts public shop-session behavior.**  
   [Security, line 647](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/admin-dashboard.md:647); requirements line 20.

   With only an operator cookie:

   - `GET /api/session` returns **200, authenticated:false**.
   - Valid shop credentials can still sign in through `POST /api/session`.
   - `DELETE /api/session` remains a public operation.

   Narrow the 401 expectation to **protected shop routes**, then list these public operations separately. This is the remaining part of round-1 finding 7.

**P3 findings**

6. **Generated references need collision and length rules.**  
   [D-ADMIN-005, line 448](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/admin-dashboard.md:448).

   Two forms opened within one second can receive identical offered/correction references, blocking independent actions. Eight UUID characters can likewise collide between repayment references. Separately, appending `-geste` to an accepted 100-character payment reference produces an invalid 106-character reference.

   Use a collision-resistant suffix/full job ID and define a bounded concession reference. Include these boundary cases in the pure-function tests.

7. **Generate a longer operator password.**  
   [D-ADMIN-001, line 103](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/admin-dashboard.md:103).

   Uniform random 59-bit passwords behind Argon2 are not an established practical cracking weakness here. Nevertheless, this credential controls every shop, has no MFA, and is destined for a password manager. Generate 24–26 characters from the existing alphabet—roughly 119–129 bits—without changing shop-password defaults. This costs essentially nothing. OWASP’s current guidance also recommends longer passwords when MFA is absent. [Authentication guidance](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html#implement-proper-password-strength-controls).

   Correct line 108 as well: permission to **read a backup** does not imply permission to **write the live database**.

8. **Task 001 remains the scheduling outlier.**  
   [Tasks, line 689](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/admin-dashboard.md:689).

   It combines migration, password management, authentication, the shared boundary, session operations, CLI changes, deployment checks, restore documentation and mutation checks. Split schema/password CLI work from HTTP authentication/boundary work, each with its own verification. Tasks 2–6 are substantially more cohesive.

**Other rulings**

- **Database-held hash: accept.** Existing `meta` writers use fixed keys or internally selected provider-mode keys, with bound values. I found no shop route accepting an arbitrary key and no SQL-injection path in the inspected SQL construction. The proposed source scan is a useful regression check, not proof by itself.
- **Restore: the stopped-service sequence is sound.** `restore.sh` already leaves the service stopped. Require `operator-password` **before restarting**, rather than merely “after restore.” Ending sessions alone does not invalidate the restored password.
- **First deployment: warning is reasonable during infrastructure verification.** A cleaner operational sequence is routing verification → interactive password bootstrap → explicit readiness check/sign-in. Later releases should treat an unset password as unexpected. There is no need to add another migration/startup mechanism solely for this.
- **`operator_not_set`: acceptable disclosure.** It exposes configuration state, not a password or an account-enumeration opportunity. With no hash, there is no credential to guess.
- **No operator-session guards: accept, with corrected reasoning.** There is no shop identity to reassign, unlike `sessions`. However, REPLACE could extend an existing session’s expiry, and UPDATE could rekey it; “only signs the operator out” is inaccurate. No proposed application path performs either operation. Arbitrary database-write access already permits inserting an operator session.
- **Transaction recheck: correct.** `BEGIN IMMEDIATE` serializes revocation and writes. Check expiry using the current time after acquiring the lock. If acquisition remains busy for approximately five seconds, the operator receives **503 `storage_unavailable`**, not 401; preserve the request for retry. This matches the existing database and exception handling. [SQLite transaction semantics](https://www.sqlite.org/lang_transaction.html).
- **Existing-line disclosure: operator-only under the proposed boundary.** Returning another shop’s payment line is appropriate there. Keep it out of shop refusals.
- **Core coverage/order:** job IDs and repayments remain in tasks 003/005; purchase text is in 006; the pilot’s opening grant remains an explicit CLI release step. Routes and their tenancy tests must land together. Tasks 7–9 remain release requirements until the owner explicitly defers them.
- **Removable work:** audit-table hooks and audit-insert rollback tests are obsolete. No operator idempotency table, permanent session guards, reporting cache or additional frontend framework is justified by these findings.

No files modified. Only source/document inspection and an in-memory logging-configuration probe were performed; `backend/.env` and `backend/data-probe/` were not accessed.  
Not checked: tests/builds, migration execution, Reka measurements, devices, production or deployment. Same-origin script compromise retains operator-level impact.