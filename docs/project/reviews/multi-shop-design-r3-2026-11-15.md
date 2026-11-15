**Verdict: REJECT.** The read cutoff and task-order fixes are sound at design level. Two browser identity gaps still block approval.

**Actionable defects**

1. **P1 — A late login can silently restore the previous shop.** Without Web Locks, v3 explicitly permits A’s delayed login cookie to replace B’s, then reloads into A. Reconciliation confirms the cookie; it does not establish that the person now using the device intended A. This preserves round 2’s concurrent-login problem. Define a safe fallback: refuse concurrent identity changes, or keep the application hidden on an unexpected identity and require explicit authentication rather than automatically displaying that shop. Cover abandoned/timed-out login → B login → late A response. **T-006.** Evidence: [design:487–490](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/multi-shop.md:487).

2. **P1 — History restoration can paint A before identity validation.** “Every start” does not explicitly cover a page restored from the back-forward cache. The visibility check reloads *after* discovering a mismatch; it does not require hiding the restored screen while that request waits. Specify hiding shop content before suspension/navigation, then gating `pageshow` restoration and visibility return on session reconciliation. Failed reconciliation must leave content hidden. Test A → navigate away → B signs in elsewhere → Back, with the session answer delayed. This remains a gap in R-004’s application-level separation. **T-006.** Evidence: [design:480](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/multi-shop.md:480), [design:488](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/multi-shop.md:488).

3. **P2 — Sign-out can miss an unresolved card held only in memory.** Step 1 says the thread is saved, then detection searches stored threads. Existing `save()` catches storage failure and continues; the exact paid request can therefore exist only in memory. No stored unresolved card means no `kept` write—and sign-out loses it. Build the kept snapshot from the live thread plus stored threads, and require successful persistence before logout. Test stale/absent stored content when the current-thread save fails. **T-006.** Evidence: [design:497–502](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/multi-shop.md:497), [ChatView.vue:96](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:96), [ChatView.vue:293](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:293).

4. **P2 — The rehearsal’s equality rule rejects intentional migration changes.** Hashing every table before and after changes `alembic_version` by definition. `login_failures` also gains a column, but only the two rebuilt tables receive an explicit original-column projection. Define preservation hashes over the original data columns, with separate assertions for the expected schema version and added fields. State how later Release 1 migrations extend this contract. **T-001; integration checked in T-005.** Evidence: [design:145](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/multi-shop.md:145), [design:554–559](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/multi-shop.md:554).

**Previous findings**

| Finding | Ruling |
|---|---|
| R2 #1: read suspension cutoff | **CLOSED** — the new-read path crosses `_send`; known-key replay sends nothing, reads have no provider retry, and the stub belongs behind the same cutoff |
| R2 #2: late cookies | **PARTIAL** — normal locked operations addressed; fallback still permits identity reversal |
| R2 #3: verification-slot lifetime | **CLOSED** — held through commit, with blocked-writer coverage |
| R2 #4: kept paid-card lifecycle | **PARTIAL** — predicate, eviction and kept-write failure fixed; memory-only case remains |
| R2 #5: task dependency | **CLOSED** — `spent_micros` moved to T-003 |
| R2 P3: migration faults and preservation | **PARTIAL** — fault injection specified; hash contract needs finding 4 |
| R2 daily-ceiling note | **CLOSED** — explicitly an admission-day budget |
| R1: previous shop’s browser state | **PARTIAL** — findings 1–2 |
| R1: suspension at dispatch/recovery | **CLOSED** |
| R1: sign-in timing/limits | **CLOSED** at design level, with the stated timing and shared-address limitations |

**Requirement wording**

- **R-003: accept.** Provider-spend admission budget and removal of the queue cap remain coherent.
- **R-004: accept subject to findings 1–3.** The cache disclosure does not excuse application screens showing the previous shop.
- **R-005: accept subject to finding 4.** Intentional schema metadata changes must be distinguished from lost or modified pilot data.
- **R-006: accept.** The transactional dispatch cutoff is clear; customer-credit release remains mandatory before Release 1 ships.
- The additional **R-001 identifier wording is acceptable**; it promises normalization, not telephone-number equivalence.

**The two deviations**

Extracting `release.sh` and testing it with fake Docker is appropriate. The user’s command remains pyinfra. **T-005’s code review** must verify committed-script staging, quoting, the existing release lock, and fail-closed ordering.

The cookie-injection fallback is acceptable as a deterministic test of application recovery. It does **not** prove Chromium’s actual cookie-delivery behavior. **T-006** must distinguish those claims and check whether `route.fetch()` applies cookies before fulfillment.

**Tasks, simplification and remaining seams**

The six tasks now have a workable dependency order and can be committed independently. Keep one identity gate for startup, reconciliation and restoration; remove automatic adoption of an unexpected shop. Keep the connection-taking operator functions and existing paid-card predicate.

The remaining failure cases are browser restoration while offline, storage failure before the kept snapshot, and intentional migration transformations. Later reviews must cover credit settlement on every cancellation/recovery path and separate operator-session isolation for new administration routes. No wallet or administration implementation belongs in this change.

Read-only review: no files changed, tests or runtime operations run, network access, or `backend/.env` access. Browser, Docker and migration behavior remain unverified at runtime.