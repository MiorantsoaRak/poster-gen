**Verdict: REJECT.** Two P1 gaps block approval. The migration approach itself looks sound from source inspection.

**Actionable defects**

1. **P1 — Changing shops can retain the previous shop’s editor state.** The design reloads after explicit sign-out, but does not specify teardown after expiry, suspension or another shop signing in. Currently, `signedOut` only clears a boolean; `loadShop` leaves the document and intake intact; routing skips reopening an already loaded creation. B can therefore inherit A’s visible state after signing in. Require a fresh application state on every identity transition, and discard responses from the previous identity. Test expiry → B sign-in and cross-tab switching. Evidence: [multi-shop.md:397](docs/project/designs/multi-shop.md#L397), [App.vue:846](frontend/src/App.vue#L846), [App.vue:597](frontend/src/App.vue#L597), [App.vue:1459](frontend/src/App.vue#L1459).

2. **P1 — Suspension does not prevent every subsequent provider call.** A retry can reserve call 2, sleep, then be suspended before dispatch. `dispatch` checks job/call status, not shop state. Restart also requeues running jobs whose calls remain reserved, including suspended shops. Define dispatch as the cutoff: atomically refuse undispatched calls for suspended shops, release them, and make recovery respect suspension. Already dispatched calls may finish. Evidence: [multi-shop.md:370](docs/project/designs/multi-shop.md#L370), [worker.py:65](backend/src/affiche/posters/worker.py#L65), [jobs.py:145](backend/src/affiche/posters/jobs.py#L145), [jobs.py:262](backend/src/affiche/posters/jobs.py#L262).

3. **P2 — Password adoption discards an existing revocation safeguard.** Deleting `password_fingerprint` before adoption preserves sessions even when the environment password changed since the previous start—precisely when today’s code revokes them. Compare the fingerprint during adoption before removing it. Also distinguish intentional fresh setup from an upgraded pilot missing its password setting; otherwise it can start with no usable password. Once adopted, the conditional update correctly prevents a stale environment hash overriding an operator reset. Evidence: [multi-shop.md:97](docs/project/designs/multi-shop.md#L97), [multi-shop.md:103](docs/project/designs/multi-shop.md#L103), [auth.py:77](backend/src/affiche/posters/auth.py#L77).

4. **P2 — Chat reads do not fully follow the promised admission rules.** Replacing only the cap check leaves `read_limit` ahead of suspension/service-cap checks. Reads also call the provider directly, outside queue fairness and concurrency limits; one shop can admit many simultaneous reads from several devices. Specify their concurrency bound and make the stated refusal precedence consistent. Evidence: [multi-shop.md:310](docs/project/designs/multi-shop.md#L310), [reads.py:569](backend/src/affiche/posters/reads.py#L569), [reads.py:634](backend/src/affiche/posters/reads.py#L634).

5. **P2 — The sign-in timing and limit guarantees are overstated.** An adopted environment hash need not use the dummy hash’s Argon2 parameters: validation accepts any valid Argon2 hash. Also, requests count failures before waiting for `VERIFYING`, so a burst can pass the limit together and continue verifying after exhaustion. Define the imported-hash policy, recheck limits after acquiring verification capacity, and test concurrent failures. An address-wide limit necessarily still lets one caller temporarily block other shops behind that address; state this residual limitation plainly. Evidence: [multi-shop.md:155](docs/project/designs/multi-shop.md#L155), [multi-shop.md:170](docs/project/designs/multi-shop.md#L170), [auth.py:43](backend/src/affiche/posters/auth.py#L43).

6. **P2 — Global chat idempotency keys violate the isolation criterion.** Knowing A’s key makes B receive `idempotency_reused`, whereas a fresh key follows a different path. UUID unpredictability does not satisfy “same answer as nonexistent.” Scope the key and lookup to the shop through a forward migration, preserving every ledger row. Evidence: [multi-shop.md:291](docs/project/designs/multi-shop.md#L291), [reads.py:550](backend/src/affiche/posters/reads.py#L550), [multi-shop requirements:29](docs/project/requirements/multi-shop.md#L29).

7. **P2 — The prepaid seam is at the wrong unit of work.** `admit_spend` runs for reads, plans and retry calls. A customer credit belongs to one logical image job, not each provider reservation. Keep provider guards shared; specify atomic credit debit at image-job admission, keyed settlement/release, and no second debit for retries. Likewise, shop creation, welcome grant and administration audit need one transaction; functions that commit internally cannot simply be wrapped by the dashboard. Evidence: [multi-shop.md:310](docs/project/designs/multi-shop.md#L310), [multi-shop.md:233](docs/project/designs/multi-shop.md#L233), [multi-shop.md:439](docs/project/designs/multi-shop.md#L439).

8. **P2 — Autosave must not indefinitely prevent sign-out.** The proposed prerequisite can trap someone in a signed-in shop after a permanent save conflict, not merely a disconnected network. Offer an explicit discard-and-sign-out path while retaining unresolved paid-request records. Evidence: [multi-shop.md:397](docs/project/designs/multi-shop.md#L397), [autosave.ts:29](frontend/src/autosave.ts#L29).

**Migration and boundary checks**

- Turning foreign keys off through the raw connection **before** the explicit transaction, rebuilding, checking references before commit, then restoring enforcement is compatible with the existing transaction wrapper. Earlier migrations contain no competing commit. A failure *inside that transaction* should roll back schema, data and Alembic version together.
- I found eleven direct child tables referencing `shop_profile`. The rebuild preserves their target name and shop 1. `keep_shop` is the only existing trigger on the parent; no explicit parent index is omitted. `looks` has a shop column without a foreign key and also needs preservation assertions.
- **P2:** distinguish migration rollback from failure **after migration commit**, such as password adoption. Deployment does not automatically redeploy the previous commit; it exits with recovery instructions. Correct [multi-shop.md:115](docs/project/designs/multi-shop.md#L115) against [deploy.py:271](deploy/deploy.py#L271). Preservation checks must also allow the intentional fingerprint-row removal rather than demand identical counts everywhere.
- `X-Affiche-Shop` is a useful stale-tab guard, not authentication; forging it grants no ownership. Token rotation addresses fixation. Check mismatches on logout too, so an old A tab cannot terminate B’s current session.
- The status check is consistent with the documented Caddy route preserving the public Host. Forwarded client identity alone is insufficient; retain both checks and test spoofed forwarding/Host combinations. “Inside the container only” overstates it: local development browsers are deliberately allowed.

**Rulings on requirement wording**

- **R-003:** Accept a provider-spend ceiling if explicitly approved. Prepaid balance is **not** a daily generation limit.
- **R-004:** Accept UI-level separation with explicit disclosure of retained local data and cached images. Keeping the paid request preserves safe replay; deleting it does not itself debit twice. The lifecycle defect above must still be fixed.
- **R-005:** Keep unchanged. `data-probe` rehearsal does not replace rehearsal on a copy of the hosted pilot; make that a mandatory release gate.
- **R-006:** Accept already dispatched generations finishing. Reservation release is an intermediate implementation detail; the complete release must still release customer credits.

**Tasks, simplification and missing checks**

The early two-shop test is appropriate, but T-003’s route-set equality already includes the password route introduced only in T-005. Make each intermediate suite runnable. Split T-005’s password API from suspension/operator work.

Avoid building temporary dollar-usage fields that prepaid immediately replaces. Keep SQLite, opaque sessions and the existing ownership helpers.

Add failure cases for interrupted legacy-storage copying, failed foreign-key restoration, delayed responses after a shop switch, and backup restoration reviving old passwords or sessions. These are currently under-specified.

Source review only; no files changed, tests run, network access or `backend/.env` read. Runtime migration and browser behavior remain unverified.