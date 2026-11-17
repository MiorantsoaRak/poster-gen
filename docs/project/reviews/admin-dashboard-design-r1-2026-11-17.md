**Verdict: APPROVE WITH FIXES.** The core approach fits Release 1: separate operator sessions, existing credit functions, one transaction per write, and an isolated frontend build. I found no established P1 blocker, but the P2 contracts below need fixing before implementation.

References below use [the design’s line numbers](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/admin-dashboard.md).

**P2 findings**

1. **“Sending again is safe” needs an explicit, stable request identity.**  
   **Design:311–338, 444–456, 572.** The backend correctly rejects repeated offered grants and credit-only corrections with the **same normalized reference**, just as it rejects bought grants. A new reference creates another line. The design does not explicitly freeze the reference, destination shop and payload through confirmation, sending, timeout and reauthentication.

   Generate an offered/correction reference once per new action; retain the complete request for retries; disable repeated submission while sending. Test a lost response followed by retry, including a correction across a minute boundary. The date-only offered reference also blocks a second legitimate offered grant that day; the minute-only correction reference has the same problem.

   Keep the existing ledger checks; a new operator idempotency table is unnecessary. Also narrow the universal retry sentence: resetting a password again creates another password, while purchase-text retries can overwrite a CLI change made meanwhile.

2. **The usage report drops the pilot’s existing images.**  
   **Design:383–395.** It counts images using `takes_credit = 1`, but [migration 0014:17](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/migrations/versions/0014_credits.py:17) deliberately gives all existing jobs `takes_credit = 0`. Their provider costs still appear in the report. The opening month can therefore show costs and confirmed posters while omitting the images that produced them.

   Count successful images by image kind, independently of billing. Retain `takes_credit` for returned-credit figures and credit history. Add a report test containing successful image jobs from both sides of migration 0014.

3. **Session revocation and a money write do not currently share a transaction.**  
   **Design:113–134, 245, 555.** The sentence claiming “the check and the write” use one transaction conflicts with the proposed boundary arrangement. The existing boundary authenticates through a separate connection; handlers open their write transaction later.

   A grant can pass authentication, wait, then execute after another device ends all operator sessions. Either explicitly allow already-authenticated requests to finish, or—my preference for these money routes—recheck the operator session inside their `write_tx`, before changing anything. Test revocation between boundary authentication and handler execution.

4. **Automatic audit recording conflicts with nested calls and refused restore attempts.**  
   **Design:218–229, 249, 625, 647.** [shops.py:82–94](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/shops.py:82) shows `set_password()` calling `end_sessions()`. Adding recording and a default actor to both produces two action rows; without explicit propagation, the inner row incorrectly says `operator`. Similarly, recording both `create_shop()` and `open_shop()` duplicates creation.

   Define one recording owner per operator action. The smallest fix is for password reset to perform its session deletion directly, while `open_shop()` owns creation recording. Record `restore_copied` only when lines actually copy: `after_restore(..., apply=True)` can return blocked without copying, and its CLI caller refuses **after** the transaction exits.

   Add rollback tests where the audit INSERT fails, plus tests proving reads, refusals and no-ops leave no misleading action rows. Preserve copied credit lines’ original actors.

5. **The required “end all operator sessions” control is missing from the page.**  
   **Design:146, 450; requirements R-ADMIN-001.** The route exists, but the Service screen lists sessions and Refresh without a revocation button.

   Add a confirmed “End all operator sessions” action, state that it includes this device, clear the cookie with the matching `/api/admin` path, and return to sign-in. Cover another live device in its test.

6. **Adding `ErrorDetail.detail` alone will not produce the promised error responses.**  
   **Design:253–270, 646.** [api.py:161–173](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/api.py:161) constructs error JSON manually; `store.Refused` also has no `detail` field. The response model is documentation, not the serializer.

   Explicitly include the exception/serialization change in the task. Keep details conditional on admin refusals, handle `ValidationError` before its parent `ValueError`, and test the actual HTTP body. The proposed rollback-before-mapping and driver-message-only handling are sound.

7. **The security matrix contradicts the public session endpoints.**  
   **Design:603–616, 625.** “Every other admin route → 401” includes public `POST` and `DELETE /api/admin/session`. Likewise, an operator-only browser gets `200 {authenticated:false}` from the shop’s public session GET, rather than 401. Blindly asserting 401 for every admin-prefix route will fail legitimate behavior.

   Separate public session operations from protected data/actions in both requirements and tests. Add explicit checks for:
   
   - Missing/wrong Origin on admin login, logout and writes.
   - HTTPS `Secure` flags and matching cookie deletion.
   - Replacement of the previous session after successful login.
   - Both cookies present together, without crossing identities.
   - Audit failure rolling back the action.

8. **Two tasks exceed the stated “one session, independently verifiable” size.**  
   **Design:644–670.** T-ADMIN-001 combines migration, permanent guards, authentication, the shared boundary, every CLI audit hook, restore behavior and runbooks. T-ADMIN-004 combines most operator workflows and their browser coverage.

   Split schema/auditing from operator authentication, and split the initial page/access workflows from money forms/history. Keep every money route with its transaction and refusal tests—the proposed ordering already gets that right. Routine verification should use generated fixtures; the task currently names `data-probe` directly.

**P3 findings**

9. **Repeated moves do not provide the promised line identifier.**  
   **Design:316–317; requirements R-ADMIN-003.** [credits.move():146–147](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/credits.py:146) says the payment was already moved or corrected but does not name the correction line. Either add that existing line’s ID to the message or narrow the requirement. Adding the ID is the smaller, more useful change.

10. **The mobile/browser checks need realistic worst-case content.**  
    **Design:464, 517–525, 628.** A 360 px test using ordinary short values will not establish the promised layout. Include an unbroken 100-character reference, long method/name, and a long refusal. Make the native confirmation focus Cancel initially and require the trial to preserve that behavior.

**Rulings on the departures**

| Departure | Ruling |
|---|---|
| Keep `/api/status` unchanged | **Accept.** Its address-and-Host loopback check supports existing operations. Share its read function with the authenticated admin route. Correct the earlier design’s replacement promise. |
| Actor `dashboard:<8 hex>`; CLI `operator` | **Accept.** Sufficient channel/session attribution for one operator. It identifies a session, not the person using a stolen session. |
| Welcome credits entered at creation | **Accept.** Reuses the atomic creation/welcome flow and avoids an unnecessary setting. |
| No individually configurable shop daily limits | **Accept.** Each shop retains its own daily accounting under the common configured ceiling. No new schema is needed. |
| Credit lines serve as their own audit record | **Accept.** Avoid duplicating money events in `operator_actions`. |

The amended requirements should explicitly preserve these decisions before implementation approval.

The authentication design is otherwise coherent: fresh random tokens prevent fixation; distinct tables prevent token interchange; Origin checking protects writes; cookie security follows configured HTTPS rather than proxy scheme detection. The secrets file already reaches the container through Compose’s `env_file`; single quoting preserves Argon2’s `$` characters. Missing/invalid hashes disable only administration at startup, and rotation takes effect on **recreate**, not immediately when the file is edited.

The same-origin exposure is accurately disclosed and remains material: injected shop-page JavaScript in the operator’s browser could read admin data and perform writes using the operator cookie. HttpOnly, Path and SameSite do not prevent that. Keeping this Release 1 default is a conscious tradeoff; a separate build is not an origin security boundary.

Migration 0016’s proposed append-only guards match the existing REPLACE defense. Four permanent guard objects are appropriate; no existing `ADDED` check appears to need `SUPERSEDES`, because existing tables/triggers remain unchanged. Keeping post-backup action records only in the retained database is a reasonable documented loss policy.

The report’s UTC convention and inclusive end date are clear; implement the latter as an exclusive next-day boundary. For the invited-shop workload, a few aggregate scans are reasonable. Keep aggregation in SQL and bound detail lists; no cache, reporting service or speculative indexes are justified yet.

The separate Vite pass is justified by the byte-identical shop-bundle constraint. FastAPI’s existing final `StaticFiles(..., html=True)` mount can serve `/admin/`; no new frontend server is required. Preserve the hash comparison and add an actual static-serving test.

The Reka trial is narrow, measurable and reversible. Its focus/keyboard scope matches the [official AlertDialog behavior](https://reka-ui.com/docs/components/alert-dialog). Keep the native baseline and the exit rule; automated ARIA checks do not establish real screen-reader usability. No Combobox, router library, settings table or additional operator framework is needed.

**Not checked:** no tests, builds, installs, migration executions, device, production, deployment or store-writing commands; no files modified. Neither `backend/.env` nor `backend/data-probe/` was accessed.  
**Remaining uncertainty:** bundle identity, probe measurements, real proxy behavior, SQLite 3.40.1 and phone accessibility remain unverified; same-origin script compromise retains operator-level impact.