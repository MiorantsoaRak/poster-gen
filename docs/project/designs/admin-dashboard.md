# DESIGN — Administration dashboard (admin-dashboard)

## System overview

**Status:** v3, 2026-11-17, approved under the autonomy grant (ADR-110); the round-2 fixes were not reviewed again. Reviewed twice by Codex: [round 1](../reviews/admin-dashboard-design-r1-2026-11-17.md) on v1 and [round 2](../reviews/admin-dashboard-design-r2-2026-11-17.md) on v2, both APPROVE WITH FIXES. A devil's advocate read v1; its points reached v2 through the lead's decisions (no report file). v3 applies round 2 and has not been reviewed again.
**Requirements file:** [../requirements/admin-dashboard.md](../requirements/admin-dashboard.md), Draft v4 (R-ADMIN-001 to 006), amended with this design.
**Depends on:** [multi-shop](multi-shop.md) v4 and [prepaid-balance](prepaid-balance.md) v4 as built (T-MULTI-SHOP-001 to 006, T-SHOP-REPLACE, T-BALANCE-001 to 006), and the seams they left: D-MULTI-SHOP-003 (functions on a connection), D-MULTI-SHOP-004 (`operator()`), D-BALANCE-005 ("The operator") and "Seams for the two dashboards".
**Release:** third feature of Release 1 « Invitation » (ROADMAP.md, ADR-105). Nothing is deployed until the whole release is ready.

The dashboard is a thin layer over what the operator's command line already does. One operator. Their password is set by the command line only, and its hash is kept in the database. An operator session lives in its own table under its own cookie; it has no shop and is never a shop session. Every write route calls the functions that `python -m affiche.shops` calls, in one write transaction that first checks the session again. Money keeps the rules of migration 0014: a request sent twice is refused by its reference, and the answer names the line that holds it. Money is recorded in the ledger with its actor; every other dashboard action is one journal line, best effort. The page lives at `/admin/` and is built by its own Vite pass, so no byte of it reaches the shops' page.

The parts: one migration (0016, the operator's sessions), one new backend module, one new command, one new page. No provider call. One new frontend dependency, on trial and last: Reka UI.

```
operator's phone or laptop ──HTTPS──▶ Caddy (Maizina's) ──▶ affiche-ia:8000
  /admin/                 a public page (dist/admin/), its own build pass; it imports nothing of the shops' code
  POST /api/admin/session {password} ─▶ auth.operator_login: limits under "#operator" → Argon2 against meta.operator_password_hash
                                          └─▶ operator_sessions (token_hash, created_at, expires_at 12 h, address, agent)
  /api/admin/…            AccessBoundary: Origin → operator session (cookie affiche_operator, Path=/api/admin) → bundle
                          the shop rules (cookie affiche_session, X-Affiche-Shop) never apply here; request.state.shop stays None
                          ─▶ admin.py ─▶ one write_tx: session still live? ─▶ shops.* / credits.* (the command line's own functions)
                                        money: a credit line with actor dashboard:<8 hex>   other writes: one log line after the commit
shop's page               /api/… as today; the operator cookie is never sent there (Path) and never read there
SSH, break-glass          python -m affiche.shops …: the same functions; operator-password sets the operator's password
                          GET /api/status from inside the container: unchanged (D-MULTI-SHOP-004)
```

## What changed from v2, and why

| v2 | v3 | Source |
|---|---|---|
| `log.info` lines, with no handler: Uvicorn leaves `affiche.*` at WARNING | the launcher gives the `affiche` logger its own INFO handler; emission tested under the real launcher; logging after the commit is best effort | round 2 P2-1 |
| A frozen request survived a 401 only; "any other refusal" was definite | 5xx (503 included), a network failure and a timeout are **uncertain** and keep the request; it is kept in memory across views and in `localStorage` across reloads; the shop's money forms reopen on it and start nothing new until it is resolved or discarded; the limit of deduplication stated | round 2 P2-2 |
| A repeated move returned the source's correction only | it also returns the destination grant when it can be established; the page says "already moved to <shop>, line N" and compares the destination; an amount fix stays distinct | round 2 P2-3 |
| Ending operator sessions was the whole answer to a stolen session | a "suspected compromise" procedure; the lifetime of what a session can create, apart from its own 12 hours | round 2 P2-4 |
| The operator's session got 401 on "every shop route" | 401 on protected shop routes only; the public shop session operations listed apart | round 2 P2-5 |
| References to the second; `repay-<8>`; `<ref>-geste` unbounded | a random suffix; the full job id; a concession reference bounded at 100 characters; pure-function tests | round 2 P3-6 |
| `operator-password`: 12 characters (about 59 bits); "whoever can read the backups can write the live file" | 26 characters from the same alphabet (about 129 bits); the sentence corrected | round 2 P3-7 |
| T-ADMIN-001 held schema, CLI and HTTP | split into 001 (schema and command line) and 002 (HTTP and boundary); ten tasks, 8 to 10 deferrable | round 2 P3-8 |
| After a restore, "run `operator-password`" | run it **before** starting the service again, in restore.sh's closing list | round 2, rulings |
| verify.sh warned on an unset password at every release | first deploy: routing check, then the password, then a readiness run of verify.sh by hand; from then on an unset password fails | round 2, rulings |
| "A REPLACE on `operator_sessions` only signs the operator out" | corrected: a REPLACE could extend an expiry and an UPDATE could rekey a session; no application path does either; a database writer can insert a session anyway | round 2, rulings |
| The re-check inside `write_tx` | reads the time after the lock is taken; a lock not obtained in 5 s is 503 and the request is kept | round 2, rulings |
| Requirements v3 | v4: R-ADMIN-001 "logged, best effort"; R-ADMIN-003 a reload and the limit of deduplication; the public shop session operations | round 2 P2-1, P2-2, P2-5 |

## What changed from v1, and why

| v1 | v2 | Source |
|---|---|---|
| An `operator_actions` table, `shops.record` inside the shops.py functions, an `actor` keyword on each, an actions route and view | none of them. Money stays in the ledger with its actor; every other dashboard write logs one line; sessions keep their address and browser and are listed. Round 1 P2-4 (nested recording) disappears with it | lead's decision A (devil's advocate) |
| The hash in `OPERATOR_PASSWORD_HASH`, a fingerprint per session, an "off" and an "invalid" state, a recreate to rotate | the hash in `meta`, set by `python -m affiche.shops operator-password`, which ends every operator session in its own transaction; unset, sign-in answers 409 `operator_not_set` | lead's decision B |
| 0016: two tables, four guards, eighteen guard lines | `operator_sessions` only; no guard; the rehearsal stays at fourteen lines | lead's decision A |
| Six tasks | nine, in the lead's order, the last three deferrable (v3: ten) | lead's decision C; round 1 P2-8 |
| Reka UI kept unless a check fails | kept only if it beats the native baseline on a measured point; a tie removes it; Tabs offered as the alternative (+6.4 KB gzip measured) | lead's decision D (devil's advocate) |
| References by date or by minute; "sending again is safe" for every write | a reference per form opening; the request frozen to a definite answer; one in flight per form; 409 `already_recorded` with the existing line; the retry sentence narrowed | round 1 P2-1; devil's advocate 3 and 5 |
| Images in the report counted by `takes_credit` | counted by kind; tested with jobs from both sides of 0014 | round 1 P2-2 |
| The session checked at the boundary only | every write checks it again inside its `write_tx` | round 1 P2-3 |
| `DELETE /api/admin/sessions` with no control on the page | a confirmed « End all operator sessions » on the Service screen | round 1 P2-5 |
| `ErrorDetail.detail` added to the model only | `store.Refused` carries `detail` and `existing`; `error_response` writes them; the mapping's order fixed; the HTTP body tested | round 1 P2-6 |
| One security matrix, every admin route 401 | public session operations apart from protected routes; the explicit checks | round 1 P2-7 |
| `move`'s refusal named no line | it names the correction line | round 1 P3-9 |
| 360 px checks with ordinary values | worst-case values; Cancel focused first | round 1 P3-10 |
| Verify commands on `data-probe` | generated fixtures only | round 1 P2-8 |
| An inclusive end date | an exclusive bound at the next day's start | round 1, rulings |
| — | a test that the server serves `/admin/`; the bound on a stolen session; the same-origin residual in the reviewer's words; payments by period in the core; "cancel a payment that never arrived" as an open decision | round 1, rulings; devil's advocate |
| D-MULTI-SHOP-004 said the dashboard would replace the body of `operator()` | `/api/status` unchanged; its read function shared. This design supersedes that sentence | round 1, rulings |

### What the code already gives (read 2026-11-17; backend suite 1437 passed, 3 deselected, per HANDOFF)

| Property | Where |
|---|---|
| Every operator action exists as a function on a connection that never commits; the caller holds `write_tx` | shops.py:1-3; `create_shop` :70-79, `set_password` :82-87, `end_sessions` :90-94, `suspend` :104-117, `enable` :120-125, `pause` :128-132, `resume` :135-137, `set_purchase_text` :140-147, `headroom` :156-168 |
| Grants, moves and corrections, with every money rule checked inside the caller's transaction; refusals are `ValueError`, one line, nothing written | credits.py:107-128, :131-159, :162-199 |
| A shop's creation and its welcome grant in one transaction | shops.py:356-363 (`_create`) |
| Passwords from an alphabet of 31 characters, hashed outside the transaction | shops.py:51-55, :354-355 |
| Migration 0014's rules refuse a duplicate line by `(shop_id, kind, ref)` and a repayment twice by `job_id`, whatever writes the line | prepaid-balance D-001; `credit_grants_never_replaced` (rehearse.GUARDS) |
| A credit line carries `actor`, `note`, `created_at`; it is never changed or removed | 0014, `credit_grants_never_changed`, `_never_removed` |
| The balance, the purchase text, the pause, the headroom | `credits.balance` :19-22, `credits.purchase_text` :32-35, `jobs.paused` jobs.py:58-60, `shops.headroom` |
| What a job's credit is doing, from its row alone | `jobs.CREDIT` jobs.py:142, `get_job` :145-152 |
| Jobs from before 0014 read `takes_credit = 0` | 0014 (`ADD COLUMN … DEFAULT 0`) |
| An unknown outcome is `interrupted` with `error_code='outcome_unknown'`; it gives its credit back at once | jobs.py:335-339; prepaid-balance owner decision 3 |
| The operator's status, loopback only | api.py:503-517; `operator()` :414-423; `_backup_state` :430-440 |
| Refusals are built by hand: `{"error": {code, message_fr, retryable, field?, current_revision?}, "request_id"}`; every code needs a sentence (a test) | `error_response` api.py:161-173; `store.Refused` store.py:23-26; `MESSAGES` api.py:45-154 |
| A constraint failure inside a request is answered 503 `storage_unavailable` | api.py:279-284 |
| Sign-in limits per address and per identifier; Argon2 outside the write transaction, two at a time; the hash read again in the write transaction | auth.py:25, :28, :119-124, :127-174 |
| A shop session lasts 90 days from sign-in | auth.py:26 |
| Every state-changing request carries Origin and `X-Affiche-Bundle` | api.py:226-247 |
| The container runs `python -m affiche.api` (Dockerfile:39), which calls `uvicorn.run` and configures no application logging (api.py:903-906). The `affiche.*` loggers have no handler: their warnings reach stderr only through Python's last-resort handler, and INFO is dropped (round 2's probe). The one `log.info` today is runtime.py:114 | api.py, Dockerfile |
| The shops' client keeps a request's key after a 5xx and drops it after a 4xx | frontend/src/api.ts:251-256 |
| `meta` is a key-value table (`key` PRIMARY KEY, `value`) | 0001_initial.py:20 |
| The rehearsal checks 13 objects and 1 column of `GUARDS` on every release | rehearse.py:34-104 |
| The tenancy test fails when a route of the schema is in no list | test_two_shops.py:26-34, :414-428 |
| The static mount is tested with a temporary build folder | test_api.py:441-442 |
| The shop's request function refuses every path but `/api/session` until the shop's identity gate opened | frontend/src/api.ts:154 |
| The shops' app has hand-made dialogs (`v-modal`, App.vue:632-635, :1872-1903) and a hand-made tablist with a roving tabindex (`tabKey` App.vue:473, the tablist :1740) | App.vue |
| restore.sh leaves the service stopped, ends every session (`end-sessions --all`) and prints the changes to redo before the start | deploy/restore.sh:62-75 |

### Where the requirements and the code pull against each other

1. **Recording every action against credit lines that record themselves.** Resolution (decision A): money is recorded by the ledger with its actor; every other dashboard action is a journal line, best effort. No table is added for it.
2. **D-MULTI-SHOP-004 planned to replace the body of `operator()` with the dashboard's session check.** That would close the in-container check of deploy/README.md "Operate" and the smoke's spend read (editor_refinements_browser.py:244). Resolution: `/api/status` stays as it is; the service route reads the same function. This supersedes that sentence of D-MULTI-SHOP-004.
3. **D-BALANCE-005 "the dashboard will write its operator's name" in `actor`.** There is one operator and no name. Resolution: `dashboard:<first 8 hex of the session's token hash>`; the command line keeps `operator`. It identifies a session, not the person using it.
4. **"Its limits", "daily limits per shop".** No per-shop limit exists: `SHOP_DAILY_SPEND_USD` (config.py:40) and `reads.DAILY_LIMIT` (reads.py:32) hold for every shop, each with its own count. Resolution: shown read-only.
5. **"One switch per shop … in one sentence".** Suspension also stops sign-in and editing (prepaid-balance decision 6). Resolution: suspension is the switch; the shop reads the existing sentences.
6. **"Unknown outcome … what the credit is doing".** An `interrupted` job has already given its credit back (ADR-109). Resolution: the problems list also shows image jobs running for more than ten minutes, which still hold one.
7. **The history seam was "built with the shop dashboard"** (prepaid-balance, Seams). The admin dashboard comes first. Resolution: this design builds `credits.history` as the seam specifies.
8. **Idempotency for operator writes.** `mutation_keys` is keyed by shop (0004); an operator write is not a shop's request. Resolution: the reference is the idempotency key for money, as 0014 enforces; the page keeps an uncertain request until it is resolved (D-ADMIN-005).

---

## D-ADMIN-001 — The operator: password, sign-in, session, boundary (covers R-ADMIN-001)

**Approach:** the smallest safe operator. One password, set by the command line, its Argon2 hash in the database. A sign-in route with the shops' limits. Server-side sessions in their own table, under their own cookie scoped to `/api/admin`. The boundary branches on the path before any shop rule. Not chosen:
- **Loopback only, through an SSH tunnel:** the container publishes no port, and the operator must grant credits from a phone (R-ADMIN-003).
- **A flag on a shop row:** every shop session check would become a privilege check, and one bug would make a shop the operator. A table without `shop_id` makes "an operator session is not a shop session" a property of the schema.
- **The hash in the environment (v1):** every change needed a container recreate, and it brought an "invalid hash" state. In the database it changes at once, in one transaction with the end of every session, like a shop's password.

### The password

- **Where:** `meta`, key `operator_password_hash` (the constant `auth.OPERATOR_KEY`). The value is an Argon2 hash.
- **Set only by the command line:** `python -m affiche.shops operator-password`.
  - Its function, `shops.set_operator_password(conn, password_hash) -> int`, writes the key (`INSERT … ON CONFLICT(key) DO UPDATE`, as `set_purchase_text`) and runs `DELETE FROM operator_sessions` in the same transaction. It returns how many sessions ended.
  - The handler makes the password with `new_password(26)`: 26 characters from the existing alphabet, about 129 bits (`new_password` gains a length, default 12; shop passwords are unchanged). This credential controls every shop and has no second factor; a password manager holds it.
  - It hashes outside the transaction and prints the password once: "operator password (shown once; keep it in your password manager): … — N operator sessions ended".
  - It runs inside the container with `docker exec -it`, or through the `operator` compose service while the service is stopped; either way the output goes to the terminal and not to the journal (deploy/README.md, "Where a printed password goes"). It never migrates and refuses an old schema, like the other commands.
- **No HTTP route writes the key.** Two tests: a source check (the key's constant appears only in `auth.py`, which reads it, and `shops.py`, which writes it), and the admin tests' fixture, which asserts the `meta` row unchanged after each test that runs an admin route. Round 2 checked that no shop route takes an arbitrary `meta` key.
- **Not set** (a new database, or before the command runs): `GET /api/admin/session` answers `configured: false`; `POST /api/admin/session` answers **409 `operator_not_set`**, with no Argon2 and no failure counted; every protected route answers 401, since no session can exist. The page shows the command to run.
- **Changing it:** run the command again. The new hash and the end of every operator session commit together and take effect at once; the hash is read at each sign-in.
- **After a restore:** the database holds the backup's hash, which may be one the operator replaced since. restore.sh leaves the service stopped; its closing list says to run `operator-password` **before** starting the service (D-ADMIN-007). Ending the sessions alone would not invalidate the restored password.
- **Cost of keeping it in the database:** the hash is in every backup copy, like the shops' hashes. Guessing about 129 bits offline against Argon2 is out of reach. A backup copy gives no session by itself: a session is a row in the live database.

### Sign-in

`auth.operator_login(engine, password, ip, agent, previous) -> (token, actor)`, in the shape of `auth.login` (auth.py:127-174):
```
key = limit_key(ip);  name = "#operator"       # "#" is never in a shop identifier ([a-z0-9]): the counters never mix
limited(conn, key, name) → 429 rate_limited
stored = SELECT value FROM meta WHERE key = OPERATOR_KEY;  None → 409 operator_not_set
with VERIFYING:                                  # the shops' two slots, held through the write
    limited(conn, key, name) again → 429 rate_limited
    ok = PASSWORDS.verify(password, stored)      # Argon2, no write transaction open
    write_tx:
        purge login_failures older than 15 min (as today); DELETE FROM operator_sessions WHERE expires_at <= :now
        ok and the key still holds `stored` (read again: a password set meanwhile gives no session)
           → DELETE the row of `previous` (this browser's operator cookie); INSERT the session
        else → INSERT INTO login_failures (ip, identifier, attempted_at) VALUES (:key, '#operator', :now)
not ok → 401 wrong_credentials;   ok → log line "sign_in" (D-ADMIN-002)
```
- `actor = "dashboard:" + token_hash(token)[:8]`. The first 8 hex of a SHA-256 of a 256-bit token tell nothing about the token.
- **Limits:** the shops' own, keyed by `#operator`: 5 failures per address (or IPv6 /64) per 15 minutes, and the address-wide 20, shared with the shops. **No limit over all addresses, on purpose** (owner decision 12): anyone could use it to lock the operator out. The limits bound the Argon2 work (tens of MiB each, two at a time, auth.py:23-25).
- `ip` is the client as uvicorn gives it after the forwarded headers it believes (Caddy), as for the shops.

### The session

- Cookie `affiche_operator`: HttpOnly; SameSite=Strict; Secure when `APP_ORIGIN` is HTTPS (as api.py:697); **Path=/api/admin**; Max-Age 43200. Its value is a server-made token (`secrets.token_urlsafe(32)`), stored as SHA-256. Sign-out and « End all » delete it with the same Path and Secure flag, or the browser keeps it.
- Read on every `/api/admin/` request, with no write on the read (ADR-065's rule for shops):
  ```sql
  SELECT created_at FROM operator_sessions WHERE token_hash = :hash AND expires_at > :now
  ```
- **Ends:** at sign-out (`DELETE /api/admin/session`); at 12 hours from sign-in (**Default**, owner decision 7); when `operator-password` runs; when every operator session is ended, from the page (`DELETE /api/admin/sessions`, D-ADMIN-005) or the command line (`end-sessions --operator`, or `--all`, D-ADMIN-007). Several may live at once (phone and laptop).
- **Every write checks it again** inside its own `write_tx`, before changing anything: `auth.operator_live(conn, token_hash)` runs the query above with `:now` taken **after** `BEGIN IMMEDIATE` holds the lock, so a session that expired while the write waited is refused. `BEGIN IMMEDIATE` also orders the check against the end of the sessions: a write either commits before the end, or finds no session and answers 401 with nothing written. A lock not obtained within busy_timeout (5 s) is 503 `storage_unavailable` before the check; nothing is written and the page keeps the request (D-ADMIN-005).
- An operator session holds no shop; a shop session is never read on these routes. The two tables, the two cookies and the two token spaces never meet.

### The boundary (`AccessBoundary`, api.py:182-284)

One branch, taken when the path starts with `/api/admin/`, before the shop rules (api.py:230):

| # | Rule on `/api/admin/…` | Refusal |
|---|---|---|
| 1 | Origin on every state-changing request: the existing line, api.py:226-227. It covers sign-in, sign-out and every write | 403 `forbidden_origin` |
| 2 | `request.state.operator` = (actor, token hash) of a live operator session, else None. `request.state.shop` = None, whatever cookie came: no admin handler can read a shop | — |
| 3 | A live operator session, except on the three public session operations: `GET`, `POST` and `DELETE /api/admin/session` | 401 `unauthenticated` |
| 4 | `X-Affiche-Shop`: not read on these paths | — |
| 5 | Bundle: the existing rule (api.py:243-247); `DELETE /api/admin/session` exempt, as the shops' sign-out is | 409 `bundle_outdated` |
| 6 | Size limits and body buffering: unchanged (128 KB) | 413 / 400 |

Every other path is unchanged. The shop session rule still reads `affiche_session` only, so an operator cookie authenticates nothing there. `/api/status` keeps `operator()`.

### API contract (the session)

```
GET    /api/admin/session           public
  200 { authenticated: false, configured: bool } | { authenticated: true, actor: "dashboard:3fa9c2d1", expires_at: str }
POST   /api/admin/session           public; body { password: str 1–1024 }; Origin; bundle
  200 { authenticated: true, actor, expires_at }    Set-Cookie affiche_operator (above); this browser's previous session deleted
  401 wrong_credentials · 409 operator_not_set · 429 rate_limited (Retry-After: 900) · 409 bundle_outdated · 403 forbidden_origin
DELETE /api/admin/session           public; Origin
  200 { authenticated: false }      the row deleted when there is one; the cookie deleted (same Path, same Secure); logged
DELETE /api/admin/sessions          protected
  200 { ended: int }                every operator session, this one included; this browser's cookie deleted; logged
```

**Failure modes & handling:**
| Failure | Detection | Behavior |
|---|---|---|
| Guessing the password | the two per-address limits | 429 after 5 failures from one address; Argon2 at most twice at a time; about 129 bits |
| Many addresses guessing | nothing global, on purpose | one Argon2 per try; each live session shows its address on the Service screen |
| A stolen session | the operator | the "suspected compromise" procedure (Security); ending operator sessions alone is never shown to be enough by the journal (T-ADMIN-001 review) |
| The database or a backup is read | — | offline Argon2 against about 129 bits; run `operator-password` to be sure |
| No password set | `meta` | 409 `operator_not_set`; the page names the command; verify.sh warns at the first deploy and fails afterwards (D-ADMIN-007) |
| A backup restored | the runbook | the backup's password and sessions return; restore.sh ends the sessions; `operator-password` runs before the start |
| A shop's session on a protected admin route | rule 3 | 401; tested for every route |
| An operator session on a protected shop route | the shop rule reads `affiche_session` only | 401; tested |
| A session ended or expired while a write waits | `operator_live`, time read after the lock | 401, nothing written |
| Database busy | busy_timeout 5 s | 503 `storage_unavailable`; nothing written; the page keeps a money request |
| The sign-in answer is lost | client error | `GET /api/admin/session` tells; signing in again is harmless (it replaces `previous`) |
| A cross-site request | SameSite=Strict, Origin | refused |

**Edge cases:** an operator and a shop signed in on the same browser keep both cookies, and neither changes the other. The device's clock plays no part. There is one password and no identifier to enumerate; every wrong password gets the same 401. `configured` tells anyone whether an operator password exists: without one, nothing can be guessed (round 2 accepted this disclosure).

---

## D-ADMIN-002 — Data and the journal: migration 0016 (covers R-ADMIN-001)

**Migration `0016_operator_sessions.py`** (forward-only, hand-written SQL, a `STATEMENTS` list as 0014 and 0015):
```sql
CREATE TABLE operator_sessions (
  token_hash TEXT PRIMARY KEY CHECK (length(token_hash) = 64),
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  address TEXT NOT NULL CHECK (length(address) BETWEEN 1 AND 64),       -- the client as uvicorn gives it
  agent TEXT CHECK (agent IS NULL OR length(agent) BETWEEN 1 AND 200)    -- the browser's User-Agent, cut at 200
)
```
- **No permanent guard.** There is no shop identity in the table to reassign, unlike `sessions`, and nothing in it is money or history. A guard would still not be empty of meaning: a REPLACE on an existing row could extend that session's expiry, and an UPDATE could rekey a session to another token. No application path does either: the code inserts with a fresh token's hash, reads, and deletes. And whoever can write the database file can insert a session outright, which no rule on this table prevents (prepaid-balance, "Outside what a database rule can hold").
- **The password's key** lives in `meta`, which exists since 0001; it needs no migration. Its only writer is the upsert of `operator-password`.
- **Rehearsal contract:** `PRESERVED = {}`; `ADDED = {"operator_sessions: empty": ("SELECT count(*) FROM operator_sessions", [(0,)])}`. `GUARDS` is unchanged: the rehearsal still prints fourteen guard lines.

### What is logged (lead's decision A)

- **A handler of the application's own.** The launcher becomes `serve(env_file=ENV_FILE)` in api.py; `python -m affiche.api` (the container's command) calls it. Before `uvicorn.run` it gives the `affiche` logger one `logging.StreamHandler()` (stderr, which the journald driver keeps), a plain format (`%(levelname)s %(name)s: %(message)s`) and level INFO. Every `affiche.*` logger inherits it. Today's warnings go through it too, on the same stream; the only existing `log.info` (runtime.py:114, after a crash) is wanted there.
- **Uvicorn's own configuration** is applied inside `uvicorn.run`. The task reads the installed version's default and confirms that it leaves the `affiche` logger in place. If it does not, the same handler goes into the `log_config` passed to `uvicorn.run`. The test below decides.
- **Proof under the real launcher, not with `caplog.set_level`:** a test starts `serve(None)` in a subprocess (the launcher's own code, without reading `backend/.env`), with a temporary data folder and stub providers. It sets the operator password in that folder with the command, signs in over HTTP, and finds the `sign_in` line in the subprocess's stderr.
- **The line,** after each committed write in `admin.py`:
  ```
  operator action=<name> shop=<identifier or -> actor=dashboard:<8 hex> [count=<n>]
  ```

| Write | `action` |
|---|---|
| sign-in, sign-out, every operator session ended | `sign_in` (with the address), `sign_out`, `operator_sessions_ended` (with the count) |
| a shop created; a new password; its sessions ended | `shop_created` (with the welcome credits), `password_set`, `sessions_ended` (with the count) |
| suspend; enable | `shop_suspended` (with the queued jobs cancelled), `shop_enabled`; only when it changed something |
| pause; resume; purchase text | `service_paused`, `service_resumed` (only when changed), `purchase_text_set` |
| grants, corrections, moves | none: the ledger holds them, with the same actor |

- **Best effort.** The line is written after the commit. A process killed between the two leaves a done action without its line; a full disk or a stopped journal can drop it too. The action is never undone for a missing line.
- **Never logged:** a password, a hash, a token, a payment reference, a request body. A test captures every record the admin tests emit and checks this.
- **Where it goes:** the container's journal (`journalctl -t affiche-ia`). deploy/README.md asks to check that it keeps at least 14 days; it is shared with the other projects on the box.
- **The cost, plainly:** beyond the journal's retention, or when a line was lost, there is no record that can be looked up of who suspended which shop and when, who reset a password, or when the service was paused. The command line's non-money actions are not logged at all: its output goes to the operator's terminal on purpose, so that printed passwords never reach the journal. Its money actions are ledger lines with actor `operator`. Owner decision 1.

---

## D-ADMIN-003 — Shops and credits (covers R-ADMIN-002, R-ADMIN-003)

**Approach:** one module, `backend/src/affiche/admin.py`, makes an `APIRouter` that `create_app` includes. Each handler calls the command line's functions in one `write_tx` and returns what the command line prints, as data. Each reads `request.state.operator`, never `request.state.shop`.

### No second implementation

- **`shops.open_shop(conn, identifier, name, password_hash, welcome, actor) -> (shop_id, welcome_line | None)`:** the body of `_create` (shops.py:356-363) moved into a function: `create_shop`, then `credits.grant(…, origin="offered", ref="welcome", actor=actor, note="Crédits de bienvenue")` when `welcome > 0`. A taken identifier's `IntegrityError` becomes `ValueError("the identifier … is already taken")`. `_create` calls it with `actor="operator"`. No other shops.py function gains a parameter.
- **`credits.history(conn, shop, *, before=None, limit=50)`:** as prepaid-balance "Seams" specifies. One `UNION ALL` of the shop's credit lines and **every** job of the shop with `takes_credit = 1`, whatever its end, newest first. Each job brings its id, kind, status, `credit` (`jobs.CREDIT`'s rule), `creation_id`, `result_ref`, `error_code`, `created_at`, `finished_at`, and `repaid_by` (the line whose `job_id` is this job, else null). The cursor is `"<created_at>|<line|job>|<id>"`, checked by a pattern as `GET /api/creations` checks its own (api.py:808-816).
- **`credits.Recorded(ValueError)`:** a refusal that carries `.line` (the line already holding the request's place) and `.moved_to` (below). `credits.LINES` gains `g.shop_id`, so a line names its shop by id and identifier. It is raised where `credits.py` already refuses a duplicate:
  - `grant`: "this shop already has a grant with the reference …", and "the payment … is already recorded in shop …";
  - `correct`: "this shop already has a correction with the reference …", and "this job was already repaid (line N)";
  - `move`: "the payment … was already moved or corrected in the source shop (line N)". Its message now names the correction line. `.moved_to` is the **destination grant when it can be established**: the first bought grant under the same reference key, in another shop, written after that correction, whose credits and ariary are the correction's negated (`move` writes both in one transaction, the grant right after). Otherwise `.moved_to` is None, and the correction is an amount fix (0 credits) or a correction whose destination cannot be established.
  Being a `ValueError`, it changes nothing for the command line except the move's message.
- Grants, corrections and moves otherwise call `credits.grant`, `credits.correct` and `credits.move` unchanged. Password hashes are made with `PASSWORDS.hash` under `VERIFYING`, outside the transaction.

### Every write: the same frame

```python
with refusals():                                   # maps after the rollback (below)
    with write_tx(engine) as conn:                 # BEGIN IMMEDIATE: the lock is held from here
        auth.operator_live(conn, token_hash)       # first; the time read now; else 401 unauthenticated, nothing written
        …the shops.* or credits.* call(s)…
log.info(…)                                         # non-money writes only, after the commit, best effort
```

### Refusals: the existing shape, two optional keys

- `store.Refused` gains two keyword arguments, `detail: str | None = None` and `existing: dict | None = None`. `error_response` (api.py:161-173) adds `"detail"` and `"existing"` to the body only when they are set. `ErrorDetail` (api.py:309-314) documents both. Only `admin.py` sets them, so every shop refusal's body stays as it is (tested), and no shop refusal ever carries another shop's line.
- New codes, with `MESSAGES` sentences that only the operator reads:
  - `operator_refused` (409): « Refusé : rien n’a été écrit. »
  - `already_recorded` (409): « Déjà enregistré : rien n’a été écrit de plus. »
  - `operator_not_set` (409): « Aucun mot de passe d’opérateur n’est défini : lancez python -m affiche.shops operator-password sur le serveur. »
- **Mapping, in this order, around the transaction** (so the rollback happens first):

| Raised inside | Answer |
|---|---|
| pydantic `ValidationError` (the shop's name, `Profile`). It is a `ValueError`, so it comes first | 422 `validation_error`, `field: "name"` |
| `credits.Recorded` | 409 `already_recorded`, `detail` = its message, `existing` = its line and `moved_to` |
| another `ValueError` | 409 `operator_refused`, `detail` = its message |
| a `LookupError` (amended after the code review: `KeyError` and `IndexError` are defects; an unknown shop is 404 before the write) | 500, sanitised, rolled back |
| `IntegrityError` (a rule of 0014 or 0015) | 409 `operator_refused`, `detail` = the driver's message only (`error.orig`), as shops.py:608-609 |
| an unknown shop id | 404 `not_found` |
| any other `SQLAlchemyError`, `OSError`; a lock not obtained | 503 `storage_unavailable` (existing, api.py:279-284) |

```
409 {"error": {"code": "already_recorded", "message_fr": "Déjà enregistré : rien n’a été écrit de plus.", "retryable": false,
               "detail": "the payment 'MV-123' was already moved or corrected in the source shop (line 42)",
               "existing": {"id": 42, "shop_id": 3, "identifier": "chezrado", "kind": "correction", "origin": null,
                            "credits": -10, "amount_ar": -20000, "method": null, "ref": "MV-123", "job_id": null,
                            "created_at": "2026-11-17T08:12:03.411902+00:00",
                            "moved_to": {"id": 43, "shop_id": 5, "identifier": "boutiquedeux"}}},
 "request_id": "…"}
```
For a grant or a correction, `moved_to` is null.

### API contract

All protected. Bodies are the project's `Model` (extra fields refused, strict types). Integers are bounded by `credits.MOST`. Times are the schema's UTC ISO text. No `Idempotency-Key`: the reference is the key for money.

```
GET  /api/admin/shops
  200 { items: [ { id, identifier, name, state, has_password, created_at, available, pending,
                   posters, last_poster_at, sessions } ] }                every shop, by identifier
POST /api/admin/shops               { identifier: str 1–64, name: str | null, welcome: int 0–MOST }
  201 { shop: <item>, password: str, welcome_line: int | null }           the password is in this answer only
  409 operator_refused (identifier taken or invalid) · 422 validation_error (name)
GET  /api/admin/shops/{id}
  200 { shop: <item>, limits: { day_spent_micros, day_limit_micros, reads_today, reads_limit } }   the UTC day
POST /api/admin/shops/{id}/password  200 { password: str, sessions_ended: int }
DELETE /api/admin/shops/{id}/sessions  200 { ended: int }
POST /api/admin/shops/{id}/suspend   200 { changed: bool, cancelled_jobs: int }
POST /api/admin/shops/{id}/enable    200 { changed: bool }

GET  /api/admin/shops/{id}/history?before=<cursor>&limit=1–50
  200 { items: [ { type: "line", id, kind, origin, credits, amount_ar, method, ref, job_id, note, actor, at }
               | { type: "job", id, kind, status, credit, creation_id, result_ref, error_code, at, finished_at, repaid_by } ],
        next_cursor: str | null }
POST /api/admin/shops/{id}/grants   { credits: int 1–MOST, origin: "offered" | "bought", ref: str 1–100, note: str 1–500 | null,
                                      amount_ar: int 1–MOST | null, method: str 1–40 | null }
  201 { line: int, balance: { available, pending },
        headroom: { cap, spent, left, outstanding, unit, cost, images, warning: bool } }    micro-USD, as shops.headroom
POST /api/admin/shops/{id}/corrections  { credits: int, ref: str 1–100, note: str 1–500,
                                          amount_ar: int | null, job_id: uuid | null }
  201 { line: int, balance: { available, pending } }
POST /api/admin/payments/move       { ref: str 1–100, from_shop: int, to_shop: int, note: str 1–500 }
  201 { lines: [reversal, grant], balances: { from: {…}, to: {…} } }
GET  /api/admin/payments?start=YYYY-MM-DD&end=YYYY-MM-DD        whole UTC days, end included; default the current UTC month
  200 { start, end, received_ar: int,
        items: [ { line, shop_id, identifier, kind, origin, credits, amount_ar, method, ref, note, actor, at } ] }
  422 validation_error (not a date; start after end)
every write: 401 · 403 forbidden_origin · 404 not_found · 409 already_recorded | operator_refused | bundle_outdated · 503
```
- `posters` counts the shop's active creations; `last_poster_at` is the latest `creations.created_at`; `sessions` counts its live shop sessions.
- `warning` is the command line's test, `cost > left` (shops.py:441).
- A suspension's answer counts the queued jobs it cancelled; their credits are back (ADR-109); a running job finishes (D-MULTI-SHOP-006).
- **Payments:** the lines with an amount whose `created_at` is in `[start 00:00, end + 1 day 00:00)`. `received_ar` is `SUM(amount_ar)`: a moved payment is +A, −A, +A, so it counts once.

### Sending again

| Write | The same request sent again | Safe? |
|---|---|---|
| Grant, correction, repayment | 409 `already_recorded` with the line | yes: the reference, `UNIQUE (shop_id, kind, ref)`, `job_id UNIQUE` |
| Move | 409 `already_recorded` with the source's correction and, when established, the destination grant | yes |
| Create a shop | 409 `operator_refused`: the identifier is taken. The first answer's password is lost with it: the page offers « Set a new password » | yes, no second shop |
| Suspend, enable, pause, resume | `changed: false` | yes, by state |
| End a shop's sessions, end every operator session | `ended: 0` | yes |
| **A new password** | another password; the earlier one, maybe never seen, stops working | harmless, but a second change |
| **The purchase text** | written again: it overwrites a text the command line set in between | not always: the page shows the stored text before the send |

**The limit of deduplication:** the database refuses a second line under one normalised reference (case and spacing ignored), per shop and kind. It cannot know that `MV-123` and `MV123` are one payment, nor that an offered grant discarded and made again under a new reference is the same gift. The page's kept request (D-ADMIN-005) covers a lost answer within one browser; the operator's payment records cover the rest.

**Failure modes & handling (money):**
| Failure | Detection | Behavior |
|---|---|---|
| A grant sent twice (two taps, two tabs, a lost answer) | the reference | one line; the second answer is 409 `already_recorded` with it |
| A correction that would take the balance below zero | `credits.correct` in the transaction | 409 `operator_refused`, "the balance would go below zero (available N)" |
| A move after part of the payment was spent | `credits.move`'s balance check | 409 `operator_refused`; the page offers the concession, confirmed apart |
| A move repeated, or sent to another destination after the first | the source's correction | 409 `already_recorded` with the correction and `moved_to`; the page compares the destination |
| A move of a payment whose amount was fixed in the source | the source's correction (0 credits) | 409 `already_recorded`, `moved_to` null; the page says "corrected, not moved" |
| A bought reference that another shop holds | `credits.grant` | 409 `already_recorded`, the other shop's line; the page points to « Move a payment » |
| A rule of the database refuses a line the module let through | `IntegrityError` | 409 with the driver's message; nothing written |
| The session ended or expired while the write waited | `auth.operator_live` inside `write_tx` | 401, nothing written |
| A crash, a lost connection, a 5xx | — | uncertain to the page: the request is kept and sent again as it was (D-ADMIN-005) |
| The database is busy | busy_timeout 5 s | 503 `storage_unavailable`, nothing written; the request is kept |
| The shop is suspended | — | grants and corrections are accepted; credits wait for the shop |

**Edge cases:** a shop without a password (a backup from before 0013 restored) shows `has_password: false` and « Set a new password ». References are compared by `credits._key` (case and inner spaces do not count) and stored as first typed. A reference whose folded form passes 100 characters (some letters, such as « ß », fold into two) is refused by the server and edited by hand.

**Security notes:** the password of a new shop, or a new shop password, travels once in an HTTPS answer marked `no-store`. It is never logged (`access_log` off, api.py:894; the log lines above hold none) and never stored by the page. No route changes or removes a credit line.

---

## D-ADMIN-004 — The service, usage, problems (covers R-ADMIN-004, R-ADMIN-005, R-ADMIN-006)

**Approach:** reads over the ledgers that exist, and three small writes that call shops.py. The body of `status()` (api.py:503-517) moves into `status_view(conn, settings, started_at)`; `/api/status` and the service route both call it, and `/api/status` answers exactly as before.

### The service (core, T-ADMIN-007)

```
GET  /api/admin/service
  200 { …status_view (commit, migration, started_at, backup, spend, failed_jobs_24h),
        paused_since: str | null,
        purchase_text: { stored: str | null, shown: str },                  shown = credits.purchase_text
        headroom: { … as for a grant },
        limits: { shop_daily_spend_micros, reads_per_day },
        operator_sessions: [ { actor, created_at, expires_at, address, agent, current: bool } ] }
POST /api/admin/service/pause        200 { changed: bool, paused_since }
POST /api/admin/service/resume       200 { changed: bool }
PUT  /api/admin/service/purchase-text  { text: str 1–500 }   200 { stored, shown }
```
Pause and resume call `shops.pause` and `shops.resume`. The purchase text calls `shops.set_purchase_text` and reads it back in the same transaction, as `_purchase_text` does (shops.py:487-495).

### Usage (deferrable, T-ADMIN-008)

```
GET  /api/admin/usage?start=YYYY-MM-DD&end=YYYY-MM-DD           the same period rule as payments
  200 { start, end, shops: [ <usage> ], service: <usage> & { evaluation_micros } }
```
`<usage>`, one per shop and one for the whole service. Every time column is compared with `>= start` and `< end + 1 day`:

| Field | From | Time column |
|---|---|---|
| `images: { scene, refine, text_texture }` | jobs of these kinds, `succeeded`, **whatever `takes_credit`**: jobs from before 0014 read 0 there and are still images | `finished_at` |
| `given_back` | jobs with `takes_credit = 1` ended `failed`, `interrupted` or `cancelled` | `finished_at` |
| `reads` | `chat_reads` `succeeded` | `created_at` |
| `image_micros`, `planner_micros` | `poster_calls` of the image kinds; of `plan` and `text_patch` | `created_at`, as `spent_micros` |
| `read_micros` | `chat_reads.cost_micros` | `created_at` |
| `estimated_micros` | the part of the three above with `cost_is_estimate = 1` | — |
| `granted: { offered, bought }`, `corrected` | `SUM(credits)` of grants by origin, of corrections | `created_at` |
| `received_ar` | `SUM(amount_ar)` of every line | `created_at` |
| `confirmed_posters` | distinct `creation_id` of `confirmations`, joined to the shop through `creations` | `confirmed_at` |
| `posters_with_scene` | distinct `creation_id` of `succeeded` scene jobs | `finished_at` |
| `evaluation_micros` (service only) | `provider_calls` | `started_at` |

The page divides; the server does not: cost per image = `image_micros / images`; images per confirmed poster = `images / confirmed_posters`; adjustments per poster = `refine / posters_with_scene`; « — » when the divisor is 0. Every field is 0 for an empty period, never absent.

### Problems and queue (deferrable, T-ADMIN-009)

```
GET  /api/admin/problems
  200 { queue: { queued, running, oldest_queued_at, by_shop: [ { shop_id, identifier, queued, running } ] },
        problems: [ { job_id, shop_id, identifier, creation_id, kind, status, error_code, created_at, started_at,
                      finished_at, credit } ],                               newest first, at most 100
        reads_failed_24h: int }
```
`problems` are the jobs, of every kind, that are `failed` or `interrupted` with `finished_at` in the last seven days, and the jobs `running` with `started_at` more than ten minutes ago. `credit` is `jobs.CREDIT`'s rule for a job with `takes_credit = 1`, else null. An unknown outcome reads `interrupted`, `outcome_unknown`, `given_back`; a stuck image reads `running`, `pending`.

**Failure modes & handling:**
| Failure | Detection | Behavior |
|---|---|---|
| The backup marker is missing or unreadable | `_backup_state` | `backup: null`, shown as "unknown", never "fresh" |
| The pause is set while images are queued | — | they run; only new requests are refused (D-BALANCE-003) |
| A purchase text that is blank or too long | `set_purchase_text` | 409 `operator_refused` "a purchase text has 1 to 500 characters" |
| A large period | — | a few aggregate scans over thousands of rows in Release 1; aggregation stays in SQL; lists are bounded |
| A recorded cost is an estimate | `cost_is_estimate` | counted in `estimated_micros` and shown as such |

**Edge cases:** the day is UTC (owner decision 11); it turns at 03:00 in Madagascar. A job admitted in one period and finished in the next counts where it finished.

---

## D-ADMIN-005 — The page (covers the screens of R-ADMIN-002 to R-ADMIN-006; R-ADMIN-003 at 360 px)

### Where it lives, and how it stays out of the shops' bundle

**A second entry page of the same frontend project, built by its own Vite pass; not a route inside App.vue.**
- `frontend/admin/index.html` (`lang="en"`, `<title>Doka Studio · Operator</title>`, `<meta name="robots" content="noindex">`) loads `src/admin/main.ts`.
- `frontend/vite.admin.config.ts`: the Vue plugin; `build.rolldownOptions.input: 'admin/index.html'`; `build.outDir: 'dist'` with `emptyOutDir: false`; `build.assetsDir: 'admin/assets'`; `publicDir: false`. Expected output: `dist/admin/index.html` and `dist/admin/assets/`.
- `package.json`: `"build": "vue-tsc --noEmit && vite build && vite build --config vite.admin.config.ts"`. The Dockerfile already runs `npm run build` and copies `dist`. `tsconfig.json` includes the new config file.
- Served at `/admin/` by the existing static mount (`SERVE_FRONTEND`); a test proves it. In development Vite serves `admin/index.html` at `http://127.0.0.1:5173/admin/`.
- **Why a second pass:** the shops' build does not change at all; its files stay byte-identical (checked by their hashes). Reka UI's size is read off the admin's own files. A route inside App.vue would put the operator behind the shops' identity gate (api.ts:154) and inside its bundle. A separate build is not an origin boundary (Security).
- **The admin code imports nothing of the shops' code**, only `vue`, `reka-ui` (the trial) and its own files; a Vitest test enforces it.
- **Bundle number:** `adminApi.ts` has its own `BUNDLE = 3` and sends `X-Affiche-Bundle`; a Vitest test fails when it differs from the shops'.

### Files

| File | Holds |
|---|---|
| `src/admin/main.ts` | `createApp(Admin).mount('#app')` |
| `src/admin/Admin.vue` | the views, chosen by the address's hash (`#/shops`, `#/shops/<id>`, `#/service`, `#/money`). No router library |
| `src/admin/adminApi.ts` | one `call()` over `fetch`: same-origin credentials, `X-Affiche-Bundle`, JSON, 30 s; an error carries `code`, `detail ?? message_fr`, `existing`, `status` |
| `src/admin/admin.ts` | pure functions, tested: the references, the kept requests, the comparisons with `existing`, ariary and dollar formats, the default period, the ratios |
| `src/admin/Confirm.vue` | the one confirmation dialog: native `<dialog>` and `showModal()`, `role="alertdialog"`, named and described, **Cancel focused first**, focus returned to the opener |
| `src/admin/admin.css` | its own styles; the shops' `style.css` is not loaded |

### References (round 2 P3-6)

| Request | Reference | Length |
|---|---|---|
| offered grant | `offered-<YYYYMMDD-HHMMSS>-<6>`: UTC to the second, then six characters drawn with `crypto.getRandomValues` from the shops' password alphabet (31 characters: about 887 million values) | 30 |
| correction | `correction-<YYYYMMDD-HHMMSS>-<6>` | 33 |
| repayment | `repay-<the full job id>` (a UUID): one per job, as `job_id UNIQUE` is | 42 |
| concession after a refused move | `<ref>-geste` when that holds at most 100 characters, else the first 94 characters of `<ref>` and `-geste`. Deterministic: the same payment's concession made twice is refused by its reference, never given twice | ≤ 100 |
| bought grant | typed: the payment's own | ≤ 100 |

Pure-function tests: two references made in the same second differ (a fixed random source); a repayment reference holds the whole job id and stays within 100; concessions for payment references of 94, 95 and 100 characters give 100, 100 and 100 characters; no generated reference passes 100.

### Requests kept until they are resolved (round 1 P2-1; round 2 P2-2)

- **Frozen.** When the operator presses « Grant… », « Correct… » or « Move… », the request (shop, path, values, reference) is frozen. The confirmation shows exactly it; sending sends exactly it; while it is in flight the button is disabled. « Cancel » at the confirmation returns to the form with the same reference: nothing was sent.
- **Kept before it leaves.** On confirmation, before the request is sent, the page records it as **unresolved**: in memory, and in `localStorage` under `affiche.admin.pending`, one entry per shop (`{shop, form, path, body, at}`).
  - **Why `localStorage`:** an uncertain answer matters most when the phone's browser drops the tab or the operator reopens the dashboard in a new tab. `sessionStorage` is lost in both cases and is not shared between tabs. `localStorage` survives a reload, a dropped tab and a restart, and is shared by every tab of this browser, which reads it on start and on its `storage` event.
  - **What it holds:** a shop id, a path, the reference and the figures. No secret, no token.
  - **What touches it:** a resolution or a discard clears it; nothing else does, sign-out included, because an unresolved request must survive a new sign-in. The shops' sign-out cleanup deletes only `affiche.shop<id>.` keys and the legacy ones (api.ts:126-127, :226-234), never this key.
  - **When storage is refused** (some private modes): the request lives in memory only, and the form says "This browser cannot keep an unanswered request across a reload."
- **Definite answers end it:** a 2xx; a 409 `already_recorded`; any other 4xx except 401 and `bundle_outdated`. These say the server decided, and nothing was written beyond what they report.
- **Kept for a resend:** a 401 (sign in again in place, then « Send again »); a 409 `bundle_outdated` (the page reloads, and the form reopens on the request).
- **Uncertain, and kept:** every 5xx, `503 storage_unavailable` included; a network failure; a timeout (30 s). An HTTP failure does not prove a rollback, so the shops' client keeps a request's key after a 5xx too (api.ts:251-256). The page reads the shop's history again.
- **One unresolved money request per shop.** While a shop has one, its Grant, Correction and Move forms start nothing new; they reopen on it, after navigation inside the page, a reload or a new tab, with « Send again » (the same request) and « Discard ». Discard warns: "If the first send was recorded, a new one writes a second line. Read the history first."
- **Resolved by the history.** When the shop's history holds a line under the request's reference (compared as the server compares), the request is resolved as recorded, compared as below, and cleared.
- **What it cannot cover:** another browser or device does not see the kept request; a request discarded and made again under a new reference is a second line. The limit of deduplication is the server's (D-ADMIN-003).

### Reading `already_recorded`

The comparison depends on the action (round 2 P2-3):

- **Grant, correction, repayment.** The page compares `existing` with the frozen request: shop, kind, credits, ariary, method, job.
  - The same → "Already recorded as line N, as sent. Nothing more to do."
  - Same shop, other values → "Line N already holds this reference with other values. To change them, write a correction (or fix the amount). Do not use another reference."
  - Another shop (a bought reference) → "This payment is recorded for <identifier>, line N. If it belongs here, move it."
- **Move.** The answer carries the source's correction and `moved_to`.
  - `moved_to` is the destination sent → "Already moved to <identifier>, line N, as sent."
  - `moved_to` is another shop → "Already moved to <identifier> (line N), not to <the destination sent>. See the payment's history."
  - `moved_to` null and the correction holds 0 credits → "The payment was corrected in <source> (an amount fix, line N), not moved. See the payment's history."
  - `moved_to` null otherwise → "The payment was already corrected in <source> (line N). See the payment's history."
  - A move never reads "as sent" without its destination.
- **The narrowed sentence after an uncertain answer**, for money only: "No answer from the server. It may have been recorded: the history is read again below. Sending the same request again is safe: it is written once." A new password and the purchase text never say "safe" (D-ADMIN-003, "Sending again").

### Screens

A header on every screen: « Doka Studio · Operator », the links (Shops · Service · Money), the session's actor and « Sign out ».

1. **Sign-in.** A hidden `username` field set to `operator` (for password managers), the password (`autocomplete="current-password"`), « Sign in ». With `configured: false` it says: "No operator password is set. On the server run: python -m affiche.shops operator-password (deploy/README.md, « Operator dashboard »)."
2. **Shops** (the home). « New shop » opens a form on the page: identifier, name, welcome credits (5). After it, a panel: "Password for <identifier>, shown once: <password>" with « Copy », and "Give it to the owner in person." The panel stays until closed or the page is left; the password is never stored. Below, every shop: identifier, name, state, « no password » when so, available and « en attente », posters, last poster, and a mark when the shop has an unresolved request. A table from 600 px; cards below.
3. **One shop.** In this order, so that a grant is first on a phone:
   - the shop's line: identifier, name, state, « available N · en attente M », live sessions;
   - an unresolved request, when there is one, above everything else, with « Send again » and « Discard »;
   - **Grant:** credits; « Offered » or « Bought »; when bought, the amount in ariary and the method (suggestions mvola, orange, airtel, cash); the reference; a note. The confirmation: "Grant 10 bought credits to <identifier>? 20 000 Ar by mvola, reference MV-123." The answer: the line, the balance after it, the headroom line, its warning in bold;
   - **Correction** (folded): « Add » or « Take back » and a whole number; the reference; the reason (required). « Fix a payment's amount » switches it to the payment's reference and a signed amount in ariary, with 0 credits;
   - **Move a payment** (folded): the payment's reference; the destination, a native `<select>` of the other shops; the reason. Refused because credits were spent, it fills the Grant form with « Offered » and the concession reference, no note, for the operator to read and confirm;
   - **History**, newest first, 50 at a time, « Older ». A line: date, kind and origin, ± credits, ariary, method, reference, note, actor. A job: date, kind, status, credit, its poster's id and its job id (copyable). « Repay » on a `succeeded` job not yet repaid fills the Correction form: +1, the job, `repay-<job id>`, the reason to type;
   - **Access** (folded): « Set a new password » (confirmed: "A new password for X. Its N sessions end.", then the shown-once panel); « End its sessions » (confirmed); « Suspend » (confirmed: "X cannot sign in. Its sessions stop working. Its queued images are cancelled and their credits come back. An image being made finishes.") or « Enable » (confirmed);
   - **Today's limits:** provider spend and messages read, against the limits, for the UTC day.
4. **Service.** Version, schema, start, the last backup's age ("late" in bold past 48 hours, "unknown" when unreadable); spend against the cap and the headroom; « Pause new requests… » or « Resume » (confirmed); the purchase text as shops read it (`lang="fr"`), a text area of 500 characters and « Save »; the daily limits, read-only; **the live operator sessions** (start, expiry, address, browser, "this device") and **« End all operator sessions »**, confirmed: "Every operator session ends, this device's too. You will sign in again." It deletes this browser's cookie (Path `/api/admin`) and returns to the sign-in form. From T-ADMIN-009: the queue and the problems. « Refresh ».
5. **Money.** Two `<input type="date">` (the current UTC month by default); the payments and their total. From T-ADMIN-008: the usage per shop and for the service, the ratios, the estimated part. An empty period shows its zeros.

### Behaviour

- **A refusal** shows `detail` (or `message_fr`) under the form, keeps what was typed, and reads the balance again.
- **A 401** shows the sign-in form over the view, keeping the view and the unresolved request.
- **Two tabs.** Each reads its own data; the server serialises writes (D-ADMIN-003); both see the unresolved request through `localStorage`. A sign-out in one tab is a 401 in the other at its next request.
- **Fresh data:** read when a view opens, after each write, and when the tab becomes visible again. No polling.

### At 360 px (R-ADMIN-003)

One column. Fields at 16 px or more. Targets 44 px high. `inputmode="numeric"` for credits and ariary; the sign of a correction is a choice, not a typed « − ». Nothing fixed to the bottom of the screen. The confirmation opens after the form is sent, when the keyboard has closed, with Cancel focused. Long values wrap (`overflow-wrap: anywhere`). **The test uses the worst values the fields accept:** an unbroken reference of 100 characters, a method of 40, a shop name of 160 (`Name`, models.py:11), a note of 500, and a refusal `detail` of 300 characters. At 360 × 640 in both themes, nothing scrolls sideways (`scrollWidth <= clientWidth`) and the confirmation's two buttons are visible.

### Language and brand

**English**, for the operator (owner decision 10). The module refusals that `detail` carries, the command line and the runbook are English and tested. The page is `lang="en"`. What a shop reads is shown as the shop reads it, in French, with `lang="fr"`: the purchase text. **The dashboard writes no sentence that a shop reads.** Notes the operator types may be shown to the shop by its future dashboard; that design decides.

Brand (T-BRAND-DOKA): the name « Doka Studio · Operator », the Signal kit's palette as CSS variables (charcoal on paper, Signal yellow as an accent, charcoal text on yellow, never white), both themes through `prefers-color-scheme`, the system's fonts.

---

## D-ADMIN-006 — The Reka UI trial (deferrable, T-ADMIN-010; the owner's agreement of 2026-11-16)

**The owner's terms:** no UI library in the shops' app; one trial of Reka UI, in this dashboard.

### Facts, checked on 2026-11-17

| Fact | Source |
|---|---|
| Package `reka-ui`, latest **2.11.0**, published 2026-10-05. Tag `alpha` = 3.0.0-alpha.0 (2026-11-05): not to be used | [npm registry metadata](https://registry.npmjs.org/reka-ui) (`dist-tags`, `time`); [npm page](https://www.npmjs.com/package/reka-ui) |
| Licence **MIT** | registry metadata, `license` |
| Vue: `peerDependencies` `vue >= 3.4.0`. The app pins 3.5.45 | registry metadata |
| Direct dependencies: `defu`, `ohash`, `aria-hidden`, `@vueuse/core`, `@vueuse/shared`, `@floating-ui/vue`, `@tanstack/vue-virtual`, `@internationalized/date`, `@internationalized/number`. With theirs, 17 packages arrive in `node_modules` beside `reka-ui` | registry metadata; an install in the scratchpad (`--ignore-scripts`) |
| Package size: tarball 1.65 MB, 9.18 MB unpacked. That is disk, not what reaches the browser | registry metadata; the tarball |
| "the new identity of Radix Vue in its v2 evolution"; unstyled; follows WAI-ARIA patterns; unused components are dropped by tree-shaking | [Introduction](https://reka-ui.com/docs/overview/introduction) |
| shadcn-vue credits Reka UI as "The headless components that power this project" | [shadcn-vue, About](https://next.shadcn-vue.com/docs/about) |
| Source repository `unovue/reka-ui` | [GitHub](https://github.com/unovue/reka-ui) |
| **AlertDialog**: "A modal dialog that interrupts the user with important content and expects a response". Parts: `AlertDialogRoot`, `AlertDialogTrigger`, `AlertDialogPortal`, `AlertDialogOverlay`, `AlertDialogContent`, `AlertDialogTitle`, `AlertDialogDescription`, `AlertDialogCancel`, `AlertDialogAction`. The WAI-ARIA "Alert and Message Dialogs" pattern; "Focus is automatically trapped"; Esc "closes the dialog and moves focus to `AlertDialogTrigger`". The page does not say which element gets focus at opening, nor where focus goes on other ways of closing | [AlertDialog](https://reka-ui.com/docs/components/alert-dialog); names also in 2.11.0's `index.d.ts` |
| **Tabs**: parts `TabsRoot`, `TabsList`, `TabsTrigger`, `TabsContent`, `TabsIndicator`. `TabsRootProps`: `modelValue`, `defaultValue`, `orientation`, `dir`, `activationMode` (`'automatic' \| 'manual'`), `unmountOnHide`; `TabsListProps`: `loop` | 2.11.0's type declarations (`dist/index3.d.ts`) and `dist/Tabs/`; the docs page was not read |
| **Dialog**: parts `DialogRoot`, `DialogTrigger`, `DialogPortal`, `DialogOverlay`, `DialogContent`, `DialogTitle`, `DialogDescription`, `DialogClose`; `DialogRootProps` `open`, `defaultOpen`, `modal`, `unmountOnHide`; event `update:open` | [Dialog](https://reka-ui.com/docs/components/dialog); 2.11.0's type declarations |
| **Combobox**: 15 parts (`ComboboxRoot` … `ComboboxArrow`); filtering built in (`ignore-filter`, `useFilter`) | [Combobox](https://reka-ui.com/docs/components/combobox) |

**Measured (scratchpad probe, 2026-11-17).** Vite 8.3.7, Vue 3.5.45, reka-ui 2.11.0, target es2022, the default minifier, gzip −9. Each probe page mounts every part of its primitive:

| Page | JS | gzip | Over Vue alone |
|---|---|---|---|
| Vue alone (baseline) | 62.5 KB | 24.1 KB | — |
| Tabs (four parts, five tabs) | 81.8 KB | 30.5 KB | +6.4 KB |
| Dialog | 98.3 KB | 35.2 KB | +11.1 KB |
| AlertDialog | 101.4 KB | 35.6 KB | +11.5 KB |
| Combobox | 155.7 KB | 54.2 KB | +30.1 KB |

These are probe pages, not the dashboard; the trial measures the dashboard's own build.

### The trial

- **Default (owner decision 4): AlertDialog**, in place of the inside of `Confirm.vue`. T-ADMIN-005 builds `Confirm.vue` on the native `<dialog>`: Esc and the inert page come from the browser; `role="alertdialog"`, the name, the description, Cancel focused first and focus returned to the opener are written by hand, as the shops' `v-modal` does (App.vue:632-635). The trial swaps only the inside of `Confirm.vue`, in one commit; every caller and every test stay as they are. If AlertDialog does not focus Cancel by itself, the trial sets it, and that code counts in the comparison.
- **Alternative: Tabs**, for the one-shop screen's sections (Grant, Correction, Move, History, Access). Its baseline is a hand-made tablist with a roving tabindex, as the shops' app has (`tabKey`, App.vue:473; the tablist, :1740). The same rule applies.
- **Not chosen: Combobox** (about 30 KB gzip for a picker a native `<select>` covers).
- **Install:** `npm install --save-exact reka-ui@<the latest 2.x that day>` (2.11.0 today), never the `alpha` tag. Imported by name from `reka-ui`.

### How it is judged

The same browser test runs on both versions of `Confirm.vue` (`admin_browser.py`, written against roles and keys):
1. **Keyboard:** opening focuses Cancel; Tab and Shift+Tab stay inside; Esc closes it without acting, and focus returns to the button that opened it; the action button acts once; Enter on Cancel does not act.
2. **Screen reader, automated:** role `alertdialog`, named by its title, described by its sentence; the page behind it out of reach while it is open.
3. **Pointer:** a tap outside does not act.
4. **360 px**, both themes, worst-case content: the dialog and its two buttons visible at 360 × 640; no sideways scroll.
5. **Size:** gzip of `dist/admin/assets/*.js` before and after the trial's commit.
6. **Code:** the lines of `Confirm.vue` before and after; every override of the library's focus, keyboard or styles written down.
7. **A real phone's screen reader** (TalkBack or VoiceOver): the owner's check, optional; the report says when it was not done.

**Exit rule (lead's decision D).** Reka UI is **kept only if it beats the native version on a measured point**, with checks 1 to 4 passing on its side and the size delta at most 15 KB gzip:
- a check of 1 to 4 that the native version fails and Reka UI passes; or
- `Confirm.vue` at least a third shorter, for the same passing checks, with no override of the library's focus or keyboard behaviour.

**A tie removes it:** the trial's commit is reverted, the 18 packages leave `node_modules`, and the native `<dialog>` stays. Either way the numbers go to `docs/project/reviews/reka-ui-trial-<date>.md`. Whether the shops' app ever uses Reka UI is a separate decision of the owner, taken on that report.

---

## D-ADMIN-007 — The command line stays the break-glass path (covers R-ADMIN-001)

- **It keeps working:** when nobody can sign in to the dashboard, while the service is stopped (the `operator` service of deploy/compose.yml), and beside the API (it takes no lock).
- **What changes in shops.py:**
  - a new command `operator-password` and its function `set_operator_password` (D-ADMIN-001); `new_password` gains a length;
  - `end-sessions --operator` ends every operator session and nothing else; `--all` also ends the operator's;
  - `_create` calls `open_shop`;
  - through `credits.Recorded`, the refusal of a move already made names its correction line.
  Every other command, message and exit code is unchanged.
- **restore.sh:** its closing list ("Before you start it, redo by hand …", restore.sh:71-75) gains, first: "the operator's password: `operator-password` (the restored database holds the backup's password; run it now, before the service starts)". Its `end-sessions --all` already runs and now ends the operator's sessions too.
- **verify.sh, and the order of the first deploy** (round 2, rulings):
  - **Every run:** `$PUBLIC/api/admin/shops` without a session must answer **401**. This proves that nobody enters without a session, not that a route exists: the refusal comes before routing.
  - **The password** (amended after the T-ADMIN-002 review, which found the marker file ambiguous: missing meant both "first deploy" and "check skipped or marker lost"): when `$PUBLIC/api/admin/session` answers `"configured":false`, verify.sh **fails**, unless it was given `--operator-bootstrap`, in which case it warns. deploy.py passes that argument only when the release is run with `OPERATOR_BOOTSTRAP=1` in its environment. No state is kept on the box.
  - **The first Release 1 deploy:** (1) the release, run once with `OPERATOR_BOOTSTRAP=1`: its verify.sh checks the 401 and warns; (2) `operator-password` in the running container; (3) the readiness check: `sudo sh /opt/affiche-ia/verify.sh <revision>` by hand, strict; (4) a sign-in at `/admin/` from the phone. Every later release fails when the password is unset. Sign-in checks that a password exists before the limits, so shop failures from the same address never hide `operator_not_set`.
- **Runbook (deploy/README.md):**
  - a new section « Operator dashboard »: where it is; setting and changing the password (`operator-password`, shown once, 26 characters, in the password manager); a lost phone with an unused session (`end-sessions --operator`, then `operator-password`); **a suspected compromise** (Security, the procedure, word for word); the live sessions on the Service screen; the journal lines (`journalctl -t affiche-ia | grep "operator action"`), best effort; the marker of verify.sh; that the command line remains;
  - "Shops" and "Credits": every command has its button, and the dashboard's money lines carry `dashboard:<8 hex>`;
  - "Restore": run `operator-password` before the start;
  - **Release 1 steps:** the four steps of the first deploy above; then the pilot's opening grant, which stays the command line's (prepaid-balance D-005), and a check that the pilot shows 30 credits on the dashboard.

---

## State machines

**The operator's password:** `unset` ──`operator-password`──▶ `set` ──`operator-password`──▶ `set` (new hash; every operator session ended in the same transaction). A restore returns it to the backup's state.

**Operator session:**
```
none ──sign-in (password set, right, under the limits)──▶ live ──sign-out | 12 h | operator-password | End all──▶ ended
```
A request with an ended or expired session gets 401, a waiting write included. Expired rows are deleted at the next sign-in. Live sessions survive a restart of the service.

**A money request from the page:**
```
form (reference made) ──Grant… / Correct… / Move…──▶ frozen ──▶ confirming (Cancel focused)
   ──Cancel / Esc──▶ form, same reference (nothing sent)
   ──confirm──▶ kept as unresolved (memory and localStorage) ──▶ sending (button disabled)
sending
   ──2xx──────────────────────────▶ done: answer shown; unresolved cleared; view read again; new reference
   ──409 already_recorded──────────▶ compared, per action; unresolved cleared; new reference
   ──other 4xx (not 401, not bundle_outdated)──▶ refused: detail shown; nothing written; unresolved cleared; form unlocked
   ──401──────────────────────────▶ kept: sign-in in place ──▶ « Send again »
   ──409 bundle_outdated───────────▶ kept: the page reloads ──▶ reopened on it
   ──5xx (503 storage_unavailable included), network failure, timeout──▶ uncertain: kept; history read again
kept (after navigation, reload, a new tab)
   ──the history holds its reference──▶ resolved as recorded; compared; cleared
   ──« Send again »──▶ sending (the same request)
   ──« Discard » (warned)──▶ cleared; the shop's money forms start new requests again
```

**Shops, the service, jobs and credits:** unchanged. Shop `active ⇄ suspended` (D-MULTI-SHOP-006); service `running ⇄ paused` (D-BALANCE-003); jobs and their credits one to one (D-BALANCE-002).

## Concurrency and edge cases

| Case | What happens |
|---|---|
| **Two operator tabs** grant at once | each is one `BEGIN IMMEDIATE`; SQLite serialises them. Same reference: one line, the other `already_recorded`. Different references: two lines. Both tabs see an unresolved request of the other through `localStorage`. **The limit:** one normalised reference is deduplicated; `MV-123` and `MV123`, or a gift discarded and made again under a new reference, are two lines |
| **A grant sent twice** | the second meets the reference: 409 `already_recorded`, compared on the page |
| **The command line and the dashboard write at once** | both use `write_tx` on the same file. The second waits up to busy_timeout (5 s), then fails whole (503 on the page, the request kept; exit 1 on the command line). The money rules run inside each transaction |
| **« End all » on one device while a grant waits on another** | the grant checks the session after taking the lock: it commits before the end, or answers 401 with nothing written |
| **`operator-password` while a sign-in is verifying** | the sign-in reads the key again in its write transaction: no session on the old password |
| **A move repeated, or retried to another shop** | `already_recorded` with the source's correction and `moved_to`; the page names the shop it went to |
| **A shop suspended while it generates** | its queued jobs are cancelled and their credits come back; a running job is cut at dispatch if its call was not sent, else it finishes (D-MULTI-SHOP-006) |
| **A correction that would take a balance below zero** | refused in its transaction. Images still running count as taken |
| **A payment moved after part of it was spent** | refused; the payment stays. The page offers the concession under its bounded reference, confirmed apart |
| **A payment that never arrived** | a negative correction removes its credits; its ariary stays counted in « received ». A whole reversal is owner decision 5, not built |
| **A sign-out in one tab** | the other tab's next request gets 401: sign-in in place, view and unresolved request kept |

## Failure modes for money, auth and external systems

**Money** (details in D-ADMIN-003 and D-ADMIN-005): duplicates refused by reference or job, with the line returned and compared per action; database rules answered 409 with nothing written; balances below zero refused in the transaction; a 5xx, a network failure or a timeout is uncertain, the request kept across navigation and reload and sent again as it was; a busy database or a crash writes nothing; a session ended during a write writes nothing; a restore copies credit lines back with `after-restore` (unchanged).

**Auth** (details in D-ADMIN-001): guessing (per-address limits, about 129 bits, Argon2); a stolen session (the suspected-compromise procedure below); a read database or backup (offline Argon2; `operator-password`); a shop on a protected admin route (401); the operator on a protected shop route (401); no password set (409 `operator_not_set`; verify.sh); a restore bringing back an older password (`operator-password` before the start); cross-site requests (SameSite=Strict, Origin); the same-origin residual (owner decision 6).

**External systems:** none new. The dashboard calls no provider and no outside service. The journal is best effort (D-ADMIN-002). Caddy is unchanged. Reka UI, if kept, is bundled at build time from the lockfile.

## Security and isolation

**Public admin session operations** (`GET`, `POST`, `DELETE /api/admin/session`):

| Check | Expected |
|---|---|
| `GET` with no cookie; with a shop's session; with a shop's token in `affiche_operator`; with an expired or ended session | 200 `authenticated: false`, `configured` as set |
| `GET` with a live operator session | 200 `authenticated: true`, its actor |
| `POST` with no or a wrong `Origin` | 403 `forbidden_origin` |
| `POST` with an older bundle | 409 `bundle_outdated` |
| `POST` with no password set | 409 `operator_not_set` |
| `POST` right: the cookie's attributes | HttpOnly, SameSite=Strict, Path=/api/admin, Max-Age 43200, and Secure when `APP_ORIGIN` is HTTPS (a test with an HTTPS origin and one with a loopback HTTP origin) |
| `POST` right from a browser that already holds an operator session | the previous row deleted, a new one written |
| `DELETE` with no or a wrong `Origin` | 403 |
| `DELETE`: the cookie's deletion | the same name, Path and Secure flag as when set |

**Public shop session operations, with only the operator's cookie** (round 2 P2-5):

| Check | Expected |
|---|---|
| `GET /api/session` | 200 `authenticated: false` (and `support_fr` when set), as with no cookie |
| `POST /api/session` with a shop's identifier and password | that shop signs in, as without the operator cookie; the operator cookie is untouched |
| `DELETE /api/session` | 200 `authenticated: false`; the operator cookie is untouched |

**Protected routes** (every other path under `/api/admin/`, read from `app.openapi()`; a new admin route in no list fails the test), and the protected shop routes:

| Caller | Expected |
|---|---|
| no cookie | 401 |
| a shop's session; with `X-Affiche-Shop` too | 401 |
| the operator's token in `affiche_session`; a shop's token in `affiche_operator` | 401 |
| an expired operator session; one ended by « End all », `end-sessions --operator` or `operator-password` | 401 |
| a loopback client and Host, no cookie | 401: loopback grants nothing here |
| the operator's session, a write with no or a wrong `Origin` | 403 `forbidden_origin` |
| the operator's session | the route's answer |
| the operator's session on every **protected** shop route (all but `/api/session` and `/api/status`) | 401 |
| a browser holding both a shop's and the operator's cookie | the shop routes answer as that shop, the admin routes as the operator; neither changes the other; a sign-out of one leaves the other |

- **test_two_shops.py:** a new set `OPERATOR` holds the admin routes by prefix; both shops get 401 on each protected one and `authenticated: false` on the session read. The coverage assertion (test_two_shops.py:428) then holds.
- **Dollars:** the operator sees micro-USD. No shop route changes.
- **At rest:** the operator's hash in `meta` (in every backup, like the shops' hashes); tokens as SHA-256; no secret in a log or an answer other than the one that shows a password once.
- **The page holds no data:** `dist/admin/` is public like the shops' page. Answers under `/api/` are `no-store`.

**What a stolen operator session can do** (devil's advocate; round 2 P2-4):
- **Credits:** it can grant any number to any shop, correct and move payments. Credits become money only through images, each bounded by its shop's daily provider ceiling (`SHOP_DAILY_SPEND_USD`, default 2.00 USD per shop per UTC day), and all spend by `SPEND_CAP_USD` counted from `SPEND_CAP_SINCE`. So the most it can make the service spend is what is left of the cap, at about 2.00 USD a day per shop it can drive. It can create shops, which adds shops to drive.
- **Shops:** it can set any shop's password and sign in as that shop: that shop's posters, photos and logo, and its credits to spend. It can lock owners out, end their sessions, suspend shops and pause the service.
- **The purchase text:** it can change it, so that shops pay another mobile money number.
- **Reading:** every shop's identifier, balance, payments (references, amounts, methods, notes), sessions and limits; the service's costs.
- **It cannot:** set or read the operator's password or its hash; read or change the secrets file, the provider keys or the cap; delete or edit a credit line or a job; run code on the box.
- **Two lifetimes.** The session itself lasts at most 12 hours, and less after « End all », `end-sessions --operator` or `operator-password`. What it made lasts longer, and none of these ends it:

  | What it made | Lasts until |
  |---|---|
  | a shop password it set | the next `set-password` |
  | shop sessions opened with it | 90 days (auth.py:26), or `end-sessions` / `set-password` |
  | grants, corrections, moves | forever, as lines; undone only by later corrections or moves |
  | shops it created | suspended |
  | a pause, a suspension | resumed, enabled |
  | the purchase text | set again |

- **Traces:** its credit lines carry `dashboard:<8 hex>`; its other writes are journal lines with the same actor (best effort, about 14 days); its session row shows its address and browser on the Service screen while it lives.

**Suspected compromise: the procedure** (a session you did not open, a line or a journal line you did not make). Over SSH, in this order (deploy/README.md « Operator dashboard »):
1. `pause --yes`: no new request reaches the AI.
2. `operator-password`: every operator session ends, the stolen one too; keep the new password.
3. `purchase-text`: read it; set it again if it is not yours.
4. `end-sessions --all`: every shop session and every operator session ends; the shops sign in again.
5. `set-password` for every shop whose password was set from the dashboard in that time (`journalctl -t affiche-ia | grep "action=password_set"`). The journal is best effort and keeps about 14 days: when in doubt, every shop. Give each new password to its owner in person.
6. `suspend --yes` every shop you did not create (`list` shows each creation day; the journal's `shop_created`).
7. Check every credit line with the suspect actor (`dashboard:<8 hex>`, in each shop's history) against your payment records. Take back unjustified credits with `correct -n`. Move a payment back with `move-payment` while its credits are unspent.
8. `resume`.

The journal cannot prove that a stolen session was never used: a line is missing when the process stopped after the action. Do the whole procedure unless you know the session was never out of your hands.

**Residual, same origin** (round 1, rulings): the dashboard and the shops' pages share an origin. Injected shop-page JavaScript in the operator's browser could read admin data and perform writes using the operator cookie; HttpOnly, Path and SameSite do not prevent that. A separate build is not an origin boundary. Today the shops' pages render shop text through Vue's escaping and use no `v-html` (checked: none in frontend/src). The full fix is a separate origin, owner decision 6.

## Tests

| Task | What must be proved |
|---|---|
| T-ADMIN-001 | **test_shops.py:** `operator-password` prints a 26-character password from the alphabet; `meta` holds its Argon2 hash; the operator sessions (rows the test inserts) are deleted in the same transaction; a second run replaces the hash. `end-sessions --operator` deletes the operator's and keeps the shops'; `--all` deletes both. `new_password()` still gives 12. **test_db.py:** 0016 on the 0012 pilot fixture (rehearsal OK, its `ADDED` line, fourteen guard lines). **test_restore_script.py:** the closing list names `operator-password` before the start |
| T-ADMIN-002 | **test_admin.py:** every row of the three matrices of Security for the routes that exist (the session routes, `DELETE /api/admin/sessions`); a burst of concurrent wrong sign-ins records at most one failure past the limit; 5 wrong from one address → 429; no password set → 409, no `login_failures` row; a sign-in verified on the old hash gets no session when `operator-password` commits in between; `DELETE /api/admin/sessions` ends a second live device's session too; expiry; **no route writes `operator_password_hash`** (the source check, and the fixture's `meta` check). **The launcher:** `serve(None)` in a subprocess emits the `sign_in` line on stderr; no record holds a password, a hash or a token. **test_two_shops.py:** the `OPERATOR` set |
| T-ADMIN-003 | **test_admin.py, shops:** list, one shop (limits on the UTC day); create (its password signs in at once; welcome 0 and 5; an identifier taken → `operator_refused`; a bad name → 422, `field: "name"`); a new password ends that shop's sessions only; end sessions; suspend (queued jobs cancelled and counted; its sessions refused; `enable` brings them back). Each answer's real HTTP body; a shop refusal's body keeps its keys. One log line per changed write, none for a no-op. **A session ended between the boundary and the handler** (a hook ends it after the boundary's read) → 401, nothing changed; **a session that expires while the write waits for the lock** → 401; **a lock not obtained** → 503 |
| T-ADMIN-004 | **test_admin.py, money:** a grant offered and bought (line, balance, headroom, warning). The same grant twice → one line, `already_recorded` with `existing` equal to it and `moved_to` null. A bought reference held by another shop → `already_recorded` with that shop's line. A correction below zero → `operator_refused`. A repayment, then again → `already_recorded`; of a `failed` job → `operator_refused`. An amount fix. A move with credits unspent (both balances; `SUM(amount_ar)` unchanged); after a spend → `operator_refused`. **Moves repeated:** A→B twice → `moved_to` = B's grant; A→B then A→C → `moved_to` = B's grant; a payment amount-fixed in A, then A→B → `existing.credits` 0 and `moved_to` null; a chain A→B→C, then A→B again → `moved_to` = B's grant. An `IntegrityError` → 409 with the driver's message (a monkeypatched `credits.grant`). Every refusal leaves the `credit_grants` count unchanged. The dashboard's lines carry `dashboard:<8 hex>`. A session ended between the boundary and the handler → 401, no line. **History:** merged newest first; the cursor; `repaid_by`. **Payments:** the end date included, the next day's 00:00 excluded; a moved payment once. **test_credits.py:** `credits.history`; `Recorded` with `line` and `moved_to`; `move`'s message names the line |
| T-ADMIN-005 | **test_api.py:** the static mount on a temporary build folder serves `admin/index.html` at `/admin/`. **Vitest:** no import leaves `src/admin/`; the two `BUNDLE` constants equal. **Build:** `dist/admin/index.html` exists; the shops' files byte-identical. **admin_browser.py** (stub, a data folder of its own, zero spend; 360 × 640 and 1280; both themes): sign in, and the `configured: false` text; create a shop and see its password once; a new password; end its sessions; suspend (Cancel focused; Esc closes without acting and returns focus; then confirm); enable; sign out; **the shops' page (`/`) requests nothing under `/admin/`** |
| T-ADMIN-006 | **Vitest:** the references (two in one second differ; `repay-<job id>`; concessions at 94, 95 and 100 characters; nothing over 100); the kept request: stored before it leaves, kept on 5xx, 503, network failure, timeout, 401 and `bundle_outdated`, cleared on 2xx, `already_recorded` and other 4xx; one per shop; resolved when the history holds its reference; the comparisons (grant: as sent, other values, other shop; move: as sent, another destination, amount fix, unknown); storage refused → memory only, with its sentence. **admin_browser.py:** a bought grant at 360 px; its answer dropped once (the route intercepted): « Send again » → "as sent"; an offered grant answered 503 once, then **the page reloaded**: the form reopens on the same request, no new offered grant can start, « Send again » → recorded once; « Discard » with its warning; a correction below zero refused; « Repay »; a move, a move refused after a spend with the concession filled in; the payments of a period; the worst-case content (no sideways scroll, both confirmation buttons visible) |
| T-ADMIN-007 | **test_admin.py:** the service answer holds `status_view`'s fields and `/api/status` answers the same body as before; pause and resume (a shop's next scene gets `budget_exhausted`); the purchase text (set, read back; blank → 409); the operator sessions with `current`. **admin_browser.py:** the Service screen; « End all operator sessions » confirmed with a second browser context signed in: both reach the sign-in form |
| T-ADMIN-008 | **test_admin.py, usage:** an empty period gives every field 0; image jobs from both sides of 0014 (`takes_credit` 0 and 1) both in `images`, only the second in credit figures; the period's last UTC day counted, the next day's 00:00 not; estimates apart; `evaluation_micros`. **Vitest:** the ratios with « — ». **admin_browser.py:** the usage table, empty and filled |
| T-ADMIN-009 | **test_admin.py:** `problems` lists a failed job, an `interrupted outcome_unknown` with `given_back`, a job running for 11 minutes with `pending`, and not one finished 8 days ago; the queue by shop. **admin_browser.py:** the list and its links |
| T-ADMIN-010 | **admin_browser.py**'s dialog checks 1 to 4 (D-ADMIN-006) pass with the native `<dialog>` before the trial's commit and with Reka UI after it; the size and the lines measured and written down |

**Mutation checks** (scratchpad scripts, run in each task's verify, never committed):
1. `set_operator_password` loses its `DELETE FROM operator_sessions` → test_shops.py fails (T-ADMIN-001).
2. `end-sessions --operator` also deletes the shops' sessions → test_shops.py fails (T-ADMIN-001).
3. The boundary accepts a shop session as the operator (rule 3 reads `request.state.shop`) → test_admin.py fails (T-ADMIN-002).
4. The session read loses `expires_at > :now` → the expiry test fails (T-ADMIN-002).
5. A write's `auth.operator_live` call removed → the "ended between the boundary and the handler" test fails (T-ADMIN-003; and for the grant in T-ADMIN-004).
6. The grant route writes through `credits._line` instead of `credits.grant` → the "bought reference held by another shop" test fails (T-ADMIN-004).

**Not proven by these tests:** a real phone; a real screen reader (D-ADMIN-006, check 7); 0016 on the release image's SQLite 3.40.1 (the release rehearsal is the gate); Caddy in front, and verify.sh's new lines (no test runs verify.sh: `sh -n` and the first deploy check them).

## Tasks

Ten tasks, each one session, each leaving the whole suite and the smokes runnable, in the lead's order (decision C). **Tasks 1 to 7 are the core. Tasks 8, 9 and 10 may move after Release 1 on the owner's word; until then they are part of it.** Verification uses generated fixtures only, never `data-probe`. Commands run from `backend/` unless said; on Linux the frontend's npm is `corepack npm@10 …` (AGENTS.md).

1. **T-ADMIN-001 — Schema and the command line.** 0016 with its contract; `auth.OPERATOR_KEY`; `set_operator_password`, `operator-password`, `new_password(length)`; `end-sessions --operator`, `--all`; restore.sh's closing list; deploy/README.md « Operator dashboard » (password, lost phone, suspected compromise, journal, marker), "Restore", the Release 1 steps; AGENTS.md's command table.
   Verify: `uv run pytest tests/test_db.py tests/test_shops.py tests/test_restore_script.py -q` → all passed; `sh -n ../deploy/restore.sh` → no output; mutation checks 1 and 2 → test_shops.py fails; `uv run pytest -q -rf` → all passed.
2. **T-ADMIN-002 — Sign-in and the boundary.** `auth.operator_login`, the session read; the boundary's branch; the three public session routes and `DELETE /api/admin/sessions`; `operator_not_set`; `serve()` and the `affiche` logger's handler; the log lines of sign-in, sign-out and « End all »; test_two_shops.py's `OPERATOR` set; verify.sh's 401 line and its marker.
   Verify: `uv run pytest tests/test_admin.py tests/test_api.py tests/test_two_shops.py -q` → all passed (the launcher test included); `sh -n ../deploy/verify.sh` → no output; mutation checks 3 and 4 → test_admin.py fails; `uv run pytest -q -rf` → all passed.
3. **T-ADMIN-003 — Shop routes.** `admin.py`'s write frame (`operator_live` first, log line after the commit); `store.Refused`'s `detail` and `existing`, `error_response`, `ErrorDetail`, `operator_refused`; the mapping; `shops.open_shop`; list, one shop, create, password, end sessions, suspend, enable.
   Verify: `uv run pytest tests/test_admin.py tests/test_shops.py tests/test_api.py tests/test_two_shops.py -q` → all passed; mutation check 5 → test_admin.py fails; `uv run pytest -q -rf` → all passed.
4. **T-ADMIN-004 — Money routes.** `credits.Recorded` with `line` and `moved_to`; `LINES` with `shop_id`; `move`'s message with its line; `already_recorded`; `credits.history`; grants, corrections, moves, history, payments.
   Verify: `uv run pytest tests/test_admin.py tests/test_credits.py tests/test_shops.py -q` → all passed; mutation checks 5 and 6 → the named tests fail; `uv run pytest -q -rf` → all passed.
5. **T-ADMIN-005 — The page: sign-in, shops, one shop's access.** `admin/index.html`, `vite.admin.config.ts`, the build script, `src/admin/*` with the native `Confirm.vue`; Sign-in, Shops, the one-shop header and Access; the static-mount test; Vitest; `frontend/tests/admin_browser.py`.
   Verify: before any change, `cd ../frontend && corepack npm@10 run build && sha256sum dist/index.html dist/render.html dist/assets/* > <scratchpad>/shop-build.txt`. After: `corepack npm@10 test && corepack npm@10 run build` → pass; `dist/admin/index.html` exists; `sha256sum -c <scratchpad>/shop-build.txt` → every line OK. Then `cd ../backend && uv run pytest tests/test_api.py -q` → pass; `uv run python ../frontend/tests/admin_browser.py` → pass; `browser_smoke.py`, `chat_browser.py`, `editor_refinements_browser.py` → pass.
6. **T-ADMIN-006 — The page: money forms, kept requests, history, payments.** The references; the kept requests (memory and `localStorage`); Grant, Correction, Move, Repay, the concession; the comparisons; History; the Money screen's payments; the worst-case 360 px test; deploy/README.md "Shops" and "Credits" point to the buttons.
   Verify: `cd ../frontend && corepack npm@10 test && corepack npm@10 run build` → pass; `sha256sum -c <scratchpad>/shop-build.txt` → OK; `cd ../backend && uv run python ../frontend/tests/admin_browser.py` → pass; the three shop smokes → pass.
7. **T-ADMIN-007 — Service.** `status_view` shared with `/api/status`; the service, pause, resume and purchase-text routes; the Service screen with the operator sessions and « End all operator sessions ».
   Verify: `uv run pytest tests/test_admin.py tests/test_api.py -q` → all passed; `cd ../frontend && corepack npm@10 test && corepack npm@10 run build` → pass; `cd ../backend && uv run python ../frontend/tests/admin_browser.py` → pass; `uv run pytest -q -rf` → all passed.
8. **T-ADMIN-008 — Usage (may move after Release 1 on the owner's word).** The usage route; the Money screen's usage table and ratios.
   Verify: `uv run pytest tests/test_admin.py -q` → all passed; `cd ../frontend && corepack npm@10 test && corepack npm@10 run build` → pass; `cd ../backend && uv run python ../frontend/tests/admin_browser.py` → pass.
9. **T-ADMIN-009 — Problems and queue (may move after Release 1 on the owner's word).** The problems route; its part of the Service screen.
   Verify: as T-ADMIN-008.
10. **T-ADMIN-010 — The Reka UI trial (may move after Release 1 on the owner's word).** Measure the admin bundle and `Confirm.vue`; install Reka UI (exact, the latest 2.x); replace the inside of `Confirm.vue` in one commit (or the one-shop sections with Tabs, if the owner chose decision 4's alternative); measure again; run the dialog checks; write `docs/project/reviews/reka-ui-trial-<date>.md`; apply the exit rule.
    Verify: `cd ../frontend && corepack npm@10 test && corepack npm@10 run build` → pass; `sha256sum -c <scratchpad>/shop-build.txt` → OK; `cd ../backend && uv run python ../frontend/tests/admin_browser.py` → pass on the version kept; the report holds both sizes, both line counts and the rule's outcome.

**The riskiest task is T-ADMIN-002:** it changes the boundary every request crosses. De-risked by the matrices over every route of the schema, by the shop suite (test_two_shops.py) passing unchanged apart from its new set, and by mutation checks 3 and 4.

**What the code reviews check:** T-001, that `operator-password` is the only writer of the key and ends the sessions in its transaction. T-002, that no admin path reads `request.state.shop`, that the shop rules are unchanged elsewhere, that the logger's handler is set by the launcher and proved under it. T-003 and T-004, that every write opens with `operator_live` inside its `write_tx`, that every money route calls `credits.grant`, `credits.correct` or `credits.move` and nothing below them, and that no log line holds a secret or a payment reference. T-005 and T-006, that nothing under `src/admin/` imports the shops' modules, that the shops' files are unchanged, and that a kept request never changes before a definite answer. T-010, that the numbers come from the build and the exit rule was applied as written.

## Not built, on purpose

- A table of non-money actions, and a route or view listing them (decision A; owner decision 1).
- The operator's hash in the environment; an "off" or "invalid" state (decision B).
- Several operators, roles, two-factor sign-in; a global sign-in limit.
- A separate origin for the dashboard (owner decision 6); a Content-Security-Policy.
- Replacing `/api/status`'s loopback rule.
- `mutation_keys` for operator writes (the reference does it); polling; a cross-tab lock.
- Per-shop limits; a settings table; welcome credits as a stored setting.
- Signing in as a shop; seeing a shop's images; deleting or renaming a shop.
- Cancelling a payment that never arrived (owner decision 5).
- Retrying a job; charts; exports; notifications when a shop reaches zero.
- A router library; the shops' `style.css`; Reka UI's Combobox; any UI library in the shops' app.

## Traceability

| Requirement | Decisions | Tasks |
|---|---|---|
| R-ADMIN-001 | D-ADMIN-001 (password, sign-in, session, boundary), D-ADMIN-002 (0016, the journal), D-ADMIN-004 (live sessions, « End all »), D-ADMIN-007 (the command line, verify.sh, restore) | T-ADMIN-001, 002, 003, 007 |
| R-ADMIN-002 | D-ADMIN-003 (shop routes, `open_shop`, `credits.history`), D-ADMIN-005 (Shops and Shop screens) | T-ADMIN-003, 004, 005 |
| R-ADMIN-003 | D-ADMIN-003 (grants, corrections, moves, `already_recorded`, payments), D-ADMIN-005 (references, kept requests, comparisons, 360 px), D-ADMIN-006 (the confirmation) | T-ADMIN-004, 005, 006, 010 |
| R-ADMIN-004 | D-ADMIN-004 (usage) | T-ADMIN-008 |
| R-ADMIN-005 | D-ADMIN-004 (service, pause, problems), D-ADMIN-001 (`/api/status` kept) | T-ADMIN-007, 009 |
| R-ADMIN-006 | D-ADMIN-004 (purchase text, limits read-only), D-ADMIN-003 (welcome at creation) | T-ADMIN-003, 007 |

## Decisions only the owner can take

Each is in force on its default; the owner can change it before the task named. Decisions 1 to 4 are the lead's calls of 2026-11-17, which the owner may overturn.

| # | Decision | Default in force | Changeable until |
|---|---|---|---|
| 1 | A queryable record of non-money actions | none in Release 1: money is in the ledger with its actor; other dashboard actions are journal lines, best effort, about 14 days. After that, or when a line was lost, who suspended which shop and when, who reset a password, or when the service was paused cannot be looked up. The command line's non-money actions leave no trace beyond their effect | T-ADMIN-003 |
| 2 | Where the operator's password lives | its hash in `meta`, set by `operator-password` (26 characters), which ends every operator session. Unset: sign-in 409. After a restore: run the command before the start. Alternative: the environment (v1), with a recreate for every change | T-ADMIN-001 |
| 3 | What Release 1 may leave out | nothing is cut. Usage (T-ADMIN-008), problems and queue (T-ADMIN-009) and the Reka UI trial (T-ADMIN-010) come last and may move after Release 1 on the owner's word | before T-ADMIN-008 |
| 4 | Which Reka UI primitive is tried | AlertDialog, kept only if it beats the native dialog on a measured point; a tie removes it. Alternative: Tabs for the one-shop sections (+6.4 KB gzip measured), judged the same way against a hand-made tablist | T-ADMIN-010 |
| 5 | Cancelling a payment that never arrived: a reversal alone, bringing its total to exactly zero, refused once its credits are spent | not in Release 1. Today a negative correction removes the credits; the ariary stays counted as received | — (its own task) |
| 6 | Where the dashboard lives | `/admin/` on the shops' address. A subdomain closes the same-origin residual and needs a DNS record and a change to Maizina's Caddy, which is not this project's | T-ADMIN-005 |
| 7 | Length of an operator session | 12 hours from sign-in, no extension on use | T-ADMIN-002 |
| 8 | Two-factor sign-in | none in Release 1 | — (its own requirement before Phase 2) |
| 9 | Per-shop daily limits | not built; one setting for every shop, shown read-only | — (its own task) |
| 10 | The dashboard's language | English; what a shop reads stays French | T-ADMIN-005 |
| 11 | The report's day | the UTC day, as the shop's daily limit | T-ADMIN-008 |
| 12 | Sign-in limits | per address only; a limit over all addresses would let anyone lock the operator out | T-ADMIN-002 |
