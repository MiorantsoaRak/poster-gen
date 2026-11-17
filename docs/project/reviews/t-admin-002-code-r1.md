**APPROVE WITH FIXES.** No P1 or authentication bypass found. Two P2 fixes and one P3 verification issue remain.

1. **P2 — The missing marker permits later releases with no operator password.**  
   [deploy/verify.sh:78](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/deploy/verify.sh:78)

   “Marker absent” means both “first deployment” and “readiness check skipped or marker lost.” If the first deployment warns and the manual readiness run never happens, every subsequent deployment can keep passing with `configured:false`. Losing the marker similarly reopens this exception.

   **Fix:** default to failing when unconfigured. Permit it only through an explicit bootstrap argument supplied for the first Release 1 invocation; the subsequent readiness run must use the strict default. Do not hardcode that argument into every future deployment.

2. **P2 — Existing shop failures override `operator_not_set`.**  
   [backend/src/affiche/posters/auth.py:260](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/auth.py:260)

   `limited()` runs before checking whether the operator password exists. With no password and 20 shop failures from the same address, operator sign-in answers **429**, contrary to the acceptance criterion requiring **409 `operator_not_set`**.

   I reproduced this with a fake connection, without writing a store. The existing unset-password test starts with an empty failure table and misses it.

   **Fix:** check the stored password first, then apply limiting when configured. Add the case with an already exhausted address limit. The approved pseudocode also needs its ordering corrected.

3. **P3 — The 401 check cannot establish that protected routes exist.**  
   [deploy/verify.sh:71](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/deploy/verify.sh:71)

   This task registers no `/api/admin/shops` route, yet this check passes: the boundary returns 401 before routing. An omitted protected router would produce the same result while the public session routes continued working. The runbook’s claim that missing dashboard routes produce 404 is therefore inaccurate.

   **Fix:** use an existing protected operation and describe this check as proving anonymous access is closed. If deployment verification must establish route registration too, add a separate route-inventory check. A pre-routing 401 cannot prove both properties.

**Rulings on the deviations**

| # | Ruling |
|---|---|
| 1 | **Accept.** Returning expiry supports the response contract without another lookup. |
| 2 | **Accept.** Expiry-or-None works correctly; `operator_tx` owns the HTTP refusal and reads time after acquiring the lock. |
| 3 | **Accept for this artifact.** Unsupported methods on `/api/admin/session` reach 405 and execute no operation. HEAD/OPTIONS probes confirmed this. |
| 4 | **Accept; not a weakened shop assertion.** All shop mutations remain covered. Admin protected mutations receive their bundle checks with an operator session in `test_admin`; the coverage assertion requires new admin routes to be classified. |
| 5 | **Accept.** Changing the subprocess’s port preserves `serve(None)` and Uvicorn’s logging setup while avoiding the application port. |
| 6 | **Prefer the explicit bootstrap argument**, with strict behavior by default and no persistent bypass. It removes the marker’s ambiguous lifecycle. |

The security checks otherwise look sound:

- **Routing:** no bypass found through decoded slashes, repeated slashes, dot segments, case changes, trailing slashes or unsupported methods. Boundary and router use the decoded ASGI path. Bare `/api/admin` currently takes the shop branch, but reaches no admin handler. Static-file normalization serves public build files; it does not dispatch API handlers. The existing route-inventory test also checks registrations outside OpenAPI.
- **CSRF and cookies:** Origin precedes every state-changing operation, including sign-out and “end all.” Cookie creation and deletion match. A cross-site session GET without the Strict cookie reveals only the deliberately public configuration bit; no cross-origin read permission is added.
- **Limiting:** the address comes from `request.client`, with forwarding handled by Uvicorn. Production trusts Docker private ranges, rather than only loopback, and depends on Caddy being the only exposed entry point. Operator failures alone stop around five; shared-NAT users can still interfere through the shared address limit. The semaphore bounds Argon2 concurrency, but sustained distributed requests can occupy worker threads waiting for it—an existing availability limitation.
- **Lifecycle:** fresh random tokens prevent fixation; only hashes are stored. Password replacement and session creation serialize correctly, with the password hash rechecked under the write lock. Protected writes likewise recheck revocation and expiry under that lock. Concurrent sign-ins carrying the same previous cookie can create two new sessions; neither reveals a token to another caller.
- **Logging:** the new lines contain actor, action, address and counts. Error handling suppresses exception text and validation inputs. Installed Uvicorn configuration preserves the application handler; ordinary single-launch behavior introduces no duplicate handler. The newly emitted application INFO messages are intentional.

**Verification limits:** `sh -n deploy/verify.sh` passed; I ran memory-only probes. I did not rerun the store-writing suite, launcher, browser or deployment checks, so the reported counts remain unverified. No files changed; `backend/.env` and `backend/data-probe/` were untouched.

Residual risks remain same-origin shop-page XSS and distributed sign-in resource exhaustion; this diff does not eliminate either.