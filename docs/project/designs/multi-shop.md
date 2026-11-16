# DESIGN — Several shops, each with its own sign-in (multi-shop)

## System overview

**Status:** v4, 2026-11-15. Approved under the user's autonomy grant (ADR-107) after three review rounds and a devil's advocate; round 3 rejected v3 on four points, answered in v4 and not reviewed again as a design: the code reviews of T-001, T-005 and T-006 check them.
**Requirements file:** [../requirements/multi-shop.md](../requirements/multi-shop.md) (R-MULTI-SHOP-001 to 006, approved with their working defaults, ADR-106). This design asks for wording changes, listed at the end.
**Reviews:** [round 1, Codex, REJECT](../reviews/multi-shop-design-r1-2026-11-15.md); [devil's advocate](../reviews/multi-shop-design-devils-advocate-2026-11-15.md); [round 2, Codex, REJECT](../reviews/multi-shop-design-r2-2026-11-15.md); [round 3, Codex, REJECT](../reviews/multi-shop-design-r3-2026-11-15.md). The lead's rulings on all four are applied.
**Release:** first feature of Release 1 « Invitation » (ROADMAP.md, ADR-105). Nothing is deployed until the whole release is ready.

The shop already is the unit of every data query. This feature makes the shop row plural, moves the password from the environment into that row, adds the identifier to the sign-in, scopes the chat ledger's keys and the two service-wide reads to the shop, gives each shop a provider-spend ceiling and a fair turn in the queue, makes suspension stop provider calls where they are sent, and makes every change of identity in the browser start from a fresh page. One process, one SQLite file, no new dependency, no new table.

```
phone ──POST /api/session {identifier,password}──▶ auth.login ──▶ shop_profile (identifier, password_hash, state)
                                                        └─▶ sessions (token_hash, shop_id)   one row per device
every /api/ request ─▶ AccessBoundary: session → shop 'active' → X-Affiche-Shop = that shop (stale-tab guard) → bundle ≥ 3
provider reservation (jobs._reserve, reads._admit) ─▶ jobs.provider_guard: suspended? service cap? shop's daily ceiling?
provider call sent (jobs.dispatch for a job, reads._send for a chat read) ─▶ shop suspended? then released at 0, never sent
worker ─▶ jobs.claim: the least recently served shop first; two provider slots as today
browser ─▶ the identity gate: a page is bound to one shop for its life and shows it only while the session says that shop;
           any other identity is the signed-out screen; sign-in and sign-out run under one cross-tab lock
operator ─▶ python -m affiche.shops …  (functions on a connection; refuses unless the schema is at head)
release ─▶ deploy.py rehearses migration 0013 on a fresh copy of the live database, in the release image, before stopping anything
```

### What the code already gives (read 2026-11-15; backend suite 1019 passed, 3 deselected, on this Linux machine)

| Property | Where |
|---|---|
| Every owned row is read by `id` **and** `shop_id`; a miss is 404 `not_found` | `store._owned` store.py:60-66; `get_creation` store.py:229-230; `jobs.get_job` jobs.py:98-99 |
| Assets are reachable only through the shop's grant, its visuals or its effects | `store._asset` store.py:76-87; `GET /api/assets/{sha}` api.py:664-669; thumbnails api.py:648-653 |
| Lists filter by shop | `GET /api/creations` api.py:747,750; `looks.list_looks`; `reads.suggestions` reads.py:480-488 |
| Idempotency keys of mutations are per shop | `mutation_keys` PRIMARY KEY (shop_id,key), 0004; `store.mutate` store.py:42-57 |
| The worker uses the job's own shop | `PosterService.prepare` service.py:36-53, `finalise` service.py:117,134,148 |
| Daily read limit is per shop | `reads.DAILY_LIMIT` reads.py:33, counted per shop reads.py:569-572 |
| Every request carries `X-Affiche-Bundle`; older bundles change nothing | `BUNDLE` api.py:163, frontend/src/api.ts:27; guard api.py:214-219 (ADR-103) |
| The audit's two-shop test: 67 cross-shop attempts refused, and it fails when the shop filter is removed | outputs/saas-review-2026-11-15/test_tenancy_audit.py:92-278, mutant_check.py |

### What assumes one shop, and where this design changes it

| Today | Where | Changed in |
|---|---|---|
| `shop_profile.id INTEGER PRIMARY KEY CHECK (id = 1)`, trigger `keep_shop` | 0004_poster_drafts.py:15, :44 | D-001 |
| `chat_reads.key` unique for the whole service | 0012_chat_reads.py:17; lookup by key alone reads.py:550 | D-001 |
| One password hash in settings, required at start; a changed hash ends every session (`meta.password_fingerprint`) | config.py:52; auth.py:43-49; auth.py:77-84, called api.py:405 | D-001 |
| Sign-in takes a password and writes a session for shop 1; the limit counts the address only | `Login` api.py:259-260; auth.py:87-116 (shop 1 at :108, count at :91-95) | D-002 |
| `GET /api/usage` gives the service's total to any shop; `GET /api/status` is open to any shop | api.py:435-439; api.py:441-454 | D-004 |
| One spend cap for everyone; one FIFO queue; nothing checks the shop when a call is sent | admission.py:295-302, jobs.py:56, reads.py:573; jobs.py:129; `dispatch` jobs.py:145-153; `recover` jobs.py:250-272 | D-005, D-006 |
| Sign-in form asks for a password only; no sign-out; a 401 only hides the screens and keeps the previous shop's poster in memory | App.vue:1544, :854-857; App.vue:1250, :1459; `route()` reuses a loaded poster App.vue:597 | D-007 |
| Browser storage keys are not separated by shop | chat.ts:98-99, words.ts:3, App.vue:51, :231, :246-250 | D-007 |

## Amended on 2026-11-16, after the code review of T-MULTI-SHOP-006

Round 1 of that review ([report](../reviews/t-multi-shop-006-code-r1.md)) showed four ways the code, and in two places this design, could lose a waiting paid card or show the wrong shop. Amended under the autonomy grant; where the text of D-MULTI-SHOP-007 below still differs, this section wins.

- **No request before the gate.** No data request leaves before the gate has opened on the bound shop, and an answer counts only under the binding its request left with. Routing waits for the same moment.
- **A 401 is acted on at its status**, before the body is read. A 409 whose body cannot be read is not taken for another shop: the session is asked again and the shop stays hidden until it answers (rule 2).
- **The kept record at sign-out** is built from the live thread, every stored thread of the shop and a `kept` record not restored yet, merged by card id; for one card the live copy wins, then the stored thread's, then the record's.
- **A failed sign-out** puts `kept` back exactly as it was before (removed if there was none): a record whose restoration failed may be the only copy.
- **Restoration** adds each card of `kept` by its id to its thread (created when absent; a card already there is left as it is, never doubled), in time order, and removes `kept` only after every thread was written. The earlier rule "written back when that thread key does not exist" lost the card when a thread existed.
- **« Se déconnecter » on a phone:** the poster editor hides the header there, so its bar carries the same button.
- **The support line** comes with every `GET /api/session` answer when it is configured (it is public text), so every sign-in form can show it.
- **Keys the browser refuses to delete at sign-out:** the session still ends; the page says « Vous êtes déconnecté, mais ce navigateur a gardé des données de la boutique : elles n’ont pas pu être effacées. » with « Réessayer l’effacement », and loads fresh once every key is gone.

**After round 2 of the same review** ([report](../reviews/t-multi-shop-006-code-r2.md)); these replace the bullets above where they differ:

- **Every session answer goes to the gate**, whoever asked for it, also the one asked inside a sign-in or sign-out and also when that operation failed. A late answer can close the gate, never open it. After a sign-out whose own answer was lost, that answer decides: nobody or another shop means the sign-out happened and `kept` stays; the same shop means `kept` is put back and the failure is said.
- **One invariant for a waiting paid card:** no writer of a thread drops it, replaces it by a poorer copy or trims it; the 100-item trim keeps it wherever it is. When two copies of one card exist, the one that has gone furthest wins (concluded, followed by its job, request kept, tapped, not tapped); on a tie the live copy, then the stored thread's, then the record's. Each card appears once.
- **Images of the shop** drawn by the canvas and read for the colours go through the same request function as data (header, gate). An `<img>` under `/api/` that fails, or an image that fails to decode, asks the session again.
- **After a sign-out nothing writes the shop's keys:** the shop's part of the page is unmounted before the cleanup, and shop keys are written through one function that refuses unless that shop is open on the page.
- **The cleanup** lists the shop's keys again from storage each time; a stored paid card the kept record lacks is spared; shop 1's keys from before the shops are deleted too; a key not listed, refused or spared leaves the cleanup unfinished and said. The retry asks the session first and deletes nothing if that shop has signed in again.

**After round 3** ([report](../reviews/t-multi-shop-006-code-r3.md)):

- **Until the kept record is removed, the chat also takes the record's cards for the thread it opens, in memory, by the same rule as restoration**, so a refused restoration write never leaves it with the poorer copy.
- **A copy concluded with neither its request nor its job ranks as tapped.** Only a conclusion from the server's answer to the card's key outranks a copy carrying the request: a refusal for good, kept with its request, or the end of its job.
- **« Réessayer l’effacement »** asks the session and deletes inside the `affiche-identity` lock, the check limited to 30 s. Without Web Locks, a change of `affiche.identity` between the question and the deletion has the session asked again; a sign-in whose `affiche.identity` write fails, and a write landing during the deletion itself, stay unprotected there.
- **An image of the shop that is answered but cannot be decoded** (the canvas's, the colour reader's) asks the session again, as a failed `<img>` does.

**After round 4: the kept card is removed (user decision 2026-11-16, ADR-108).** Round 4 ([report](../reviews/t-multi-shop-006-code-r4.md)) rejected again: each round had found a new way to lose or overwrite a waiting paid request where two of its three copies met (the chat's memory, the stored thread, the `kept` record) or where browser storage failed. The user asked for another solution instead of more patches. **Every bullet above about `kept`, the ranking of copies, restoration and the spared card is void; so are steps 2 to 5 of « Se déconnecter » in D-MULTI-SHOP-007 where they speak of it.**

- **The server is the authority for a paid request.** The key, the job and the spend reservation are written in one transaction (`store.py`, `jobs.py`): if the server has the key it has the job; if not, nothing was paid. Every `/api/` request has its session checked before its handler, and sign-out deletes the session row: after `DELETE /api/session` a paid request not yet admitted gets 401 and creates no job and no charge.
- **Sign-out keeps nothing on the device.** Order, which must hold: save unsaved edits; if a paid image waits, one confirmation sentence; inside the `affiche-identity` lock `DELETE /api/session` (with the existing check after a lost answer); bind the page to nobody; unmount the shop's part; delete every key of the shop and shop 1's keys from before the shops; « Réessayer l’effacement » as before. The session ends first, the keys go after. Sign-out is no longer refused because the chat is open in another tab.
- **After signing in again**, an image the server received is the poster's running job or a version « À vérifier » in « Mes affiches », as on any other device. The card itself does not come back; a changed version is chosen by the owner.
- **Strict send:** a paid card's request leaves only after the thread holding the request and its key was written to storage. When the write fails the request is not sent, the card says « Ce navigateur ne peut pas garder la demande : rien n’a été envoyé. Utilisez Pas à pas. » and a new card can be made. This also closes the gap that was on `main` before this task (the save's failure did not stop the send).
- **At the tap too:** when the tapped card itself cannot be stored, nothing leaves at all, not even the free poster or plan.
- **After a sign-out made in another tab:** a tab told of the identity change writes no key of the shop while its gate is out, so a late answer does not write a thread back after the cleanup. A session that only ended (a 401) still lets the chat keep its « Connectez-vous pour continuer. » card.
- **"Admitted" means the request passed the session check.** One that passed just before the sign-out committed still makes its job; it lives on the server and shows on the poster.
- **After round 5** ([report](../reviews/t-multi-shop-006-code-r5.md), APPROVE WITH FIXES): from another tab's identity event on, a page writes nothing of its shop until an answer asked after that event names its shop (this replaces "while its gate is out" above); the thread cap never takes the thread just written nor one whose paid card waits, and a thread counts as stored only when it is there as written; when this tab does not hold the chat, « Se déconnecter » reads the stored threads, read only, to know whether an image waits, and storage it cannot read shows the confirmation; « Mes affiches » reads the list again each time it opens.
- **Accepted:** a request the server never received is forgotten at sign-out (nothing paid); a pending chat read is lost at sign-out (one more read, about USD 0.003); asking again for a change whose image already finished pays again (the server only refuses two at once on one poster); no lookup of a request by its key is added (not needed for correctness).
- **Tests:** backend: a `/scenes` request with an ended session's cookie gets 401, no `poster_jobs` row, no `mutation_keys` row. Vitest: a refused write at sending keeps the request from leaving; with storage working the thread holds the request before the send; sign-out and cleanup with no exception. Browser: an answer lost, sign-out, no key of the shop left, after sign-in the poster shows the one job; a `/scenes` request held across the sign-out and released after it gets 401 and makes no job; sign-out from a tab that does not hold the chat.

## What changed from v3, and why

Three rounds found new gaps in the same place, the browser's handling of a change of identity, each time by adding a path to a list. v4 replaces the list by one rule.

| v3 | v4 | Finding (round 3) |
|---|---|---|
| A table of paths (401, 409, sign-in, another tab), each with its own reaction; a mismatch reloaded into the shop the session named | **The identity gate** (D-007): a page is bound to one shop for its life (`sessionStorage` `affiche.bound`); shop content is shown only while the last session answer names it; any other identity is the signed-out screen; showing a shop takes an explicit sign-in on the page; `epoch` and the per-path list deleted | P1-1 and P1-2; the reviewer's "keep one identity gate…; remove automatic adoption of an unexpected shop" |
| Without Web Locks, a late sign-in answer of A could reload B's page into A | The same rule holds; the cost is a signed-out screen for B, never A's data (rule 6) | P1-1, a late sign-in restoring the previous shop |
| The back-forward cache and the return to visibility were not gated; content could paint before the answer | `pagehide` hides shop content; `pageshow` `persisted` reloads at once; visibility re-asks the session with content hidden; a missing or failed answer keeps it hidden with « Réessayer » (rule 2, rule 5) | P1-2, history restoration |
| Sign-out searched the stored threads for an unresolved card | The snapshot comes from the live thread plus the stored threads; its write must succeed before `DELETE /api/session`; refused while another tab holds the chat (D-007) | P2-3, a card held only in memory |
| The rehearsal hashed every table, so the expected changes of `alembic_version` and of `login_failures` would fail it | Preservation hashes over explicit projections of the original columns (`shop_profile`, `chat_reads`, `login_failures`); the version and the added columns asserted apart; each later migration states its own `PRESERVED` and `ADDED` (Release gate) | P2-4, the rehearsal's equality rule |
| — | "What the code reviews check" under Tasks: T-001's projections; T-005's `release.sh` (committed and staged, quoted, the existing lock, fail-closed, the pyinfra command unchanged); T-006's gate and the cookie claims its tests prove and do not prove, with the `route.fetch()` check | Round 3 "The two deviations" |

## What changed from v2, and why

| v2 | v3 | Finding (round 2) |
|---|---|---|
| A chat read was admitted, then sent with no check of the shop in between | `reads._send`: one transition between admission and the call; a suspended shop's read is closed `failed` at cost 0 and answered `shop_suspended` (D-006) | P1-1, reads and suspension |
| Late answers were dropped by `epoch`, but a late `Set-Cookie` still applies | Sign-in and sign-out run under one Web Lock `affiche-identity` until their response is complete; `GET /api/session` is asked after each and at every start, and nothing of a shop is shown until it matches; what a late sign-out can still do is stated and tested with reversed delivery (D-007) | P1-2, cookies arriving late |
| The verification slot ended before the transaction that records the failure | The slot is held until that transaction has finished; Argon2 stays outside the write transaction; a test with a blocked writer (D-002) | P2-3, sign-in overshoot |
| The kept card chosen by `nextStep(item) === 'replay'`; old threads evicted regardless; the record rewritten after the session ended | The chat's own predicate for a paid card waiting for its answer (`paid(item.card) && item.spent && !item.done`, ChatView.vue:59), exported as `unresolved`; such threads are never evicted; the record is written first, and sign-out stops if it cannot be (D-007) | P2-4, the kept paid card |
| `spent_micros(shop=…)` arrived in T-004 while T-003's `/api/usage` needed it | Moved, with its tests, into T-003 (Tasks) | P2-5, task order |
| Migration tests without faults between the rebuilds; the rehearsal compared counts and sums | Faults injected between the rebuilds and after the read-ledger swap; the rehearsal compares a hash of each preserved table's rows; the gate requires evidence from the release image and a test that a failed rehearsal never reaches the stop and start (Release gate, Tests) | P3 |
| The daily ceiling's day was not said | A budget of the admission day (D-005) | Note on the daily ceiling |
| — | `/api/usage` keeps its fields until the prepaid feature replaces dollars by credits there (D-004); the identifier "may be a phone number in one written form" (D-002, wording) | Requirement wording notes |

## What changed from v1, and why

| v1 | v2 | Finding |
|---|---|---|
| Memory cleared only by « Se déconnecter » | Every change of identity ends in a full reload; responses of an ended identity are dropped (D-007) | Codex P1-1; devil's advocate 2 |
| Suspension deleted the sessions; a call reserved before the suspension could still be sent; recovery requeued it | The session check requires an active shop and sessions are kept, so « enable » reverses a mistake; `dispatch` is the cutoff; recovery cancels a suspended shop's unsent calls (D-006) | Codex P1-2; devil's advocate 6 |
| 0013 deleted `password_fingerprint`; adoption ignored it; a failure after the migration "redeploys the previous commit" | Adoption compares the fingerprint first and ends the sessions when the environment password changed, then removes the row; an upgraded pilot with no password anywhere refuses to start; the deploy's real behaviour stated (D-001) | Codex P2-3; Codex "Migration and boundary checks" |
| Reads: only the cap line replaced; no bound on reads in progress | Reads follow suspended, cap, shop ceiling, then the daily read limit; at most two reads in progress per shop (D-005) | Codex P2-4 |
| "Timing identical"; limits counted once before waiting for a verification slot | Limits counted again inside the slot; a test with concurrent failures; the timing claim and the address-wide residual stated as they are; an adopted hash is upgraded at its first sign-in (D-002) | Codex P2-5 |
| Global `chat_reads.key` accepted as a known leak | 0013 rebuilds `chat_reads` with `UNIQUE (shop_id, key)`; lookup by shop and key (D-001) | Codex P2-6 |
| `admit_spend` named as the prepaid balance's seam; `affiche.shops` functions took an engine and migrated | The provider guard is not that seam (a note for the next feature, D-005); the functions take a connection; the command refuses unless the schema is at head and never migrates (D-003) | Codex P2-7; devil's advocate 5 |
| `queue_full`; new dollar fields in `/api/usage`; `operator(request)` described as "inside the container"; a password dialog | `queue_full` cut; `/api/usage` scoped to the shop with its fields unchanged; `/api/status` keeps both checks, tested against spoofed forwarding and Host, worded honestly; the password route only, its screen is R-SHOP-DASH-003 | Devil's advocate 1; Codex R-003 ruling |
| Sign-out kept the shop's keys; unsaved edits blocked sign-out | Sign-out deletes the shop's keys and reloads, with one exception (a paid card waiting on an unknown outcome); a failed or conflicting autosave can be discarded; cached images disclosed (D-007) | Codex P2-8 and R-004 ruling; devil's advocate 7 |
| Identifier: `strip().lower()` | Accents, case, spaces and punctuation removed before lookup; the operator's chosen identifier may be a phone number in one written form; « Mot de passe oublié ? Contactez … » from a setting (D-002) | Devil's advocate 3, 4 |
| `X-Affiche-Shop` exempt on the whole `/api/session` | Described as a stale-tab guard, not authentication; checked on sign-out too (D-002) | Codex "Migration and boundary checks" |
| Rehearsal on `data-probe` plus the operator's own steps | A release gate: `deploy.py` runs `python -m affiche.rehearse` on a fresh copy of the live database in the release image before stopping anything, and the user's steps around it (Release gate) | Codex R-005 ruling |
| Seven tasks; T-003's route test needed T-005's route | Six tasks, each leaving a runnable suite; the password route apart from suspension; the riskiest task named with its de-risking (Tasks) | Codex "Tasks"; devil's advocate "The seven tasks" |
| — | Failure cases added: interrupted copy of legacy keys (D-007), failed restoration of foreign keys (D-001), delayed response after a change of shop (D-007), backup restore reviving passwords or sessions (D-001, D-003); restore rolls back every shop (T-005 runbook); `looks` preserved although it has no foreign key (Tests) | Codex "Tasks" and "Migration and boundary checks"; devil's advocate 8 |

---

## D-MULTI-SHOP-001 — The schema: several shops; the pilot keeps everything (covers R-MULTI-SHOP-005, the data of 001, 002 and 006)

**Approach:** rebuild `shop_profile` in migration 0013 without its CHECK and with the shop's identity columns, keeping the pilot's row as shop 1 and every row of every table; rebuild `chat_reads` in the same migration with its key unique per shop. The password moves from the environment into shop 1's row at the first start, with today's revocation rule applied once more. No separate credentials table: `store.get_profile` returns named columns only (store.py:125-129), so the hash never reaches a profile answer.

**Why `affiche.db.migrate` changes** (scratch database built by the real migrations 0001–0012; the devil's advocate repeated it on a copy of `data-probe`, with `kill -9` before COMMIT, and on SQLite 3.46.1): `migrate` runs every migration in one `BEGIN IMMEDIATE` with `foreign_keys = ON` (db.py:56-61). `PRAGMA foreign_keys = OFF` is ignored inside a transaction, and dropping the referenced `shop_profile` then fails (`FOREIGN KEY constraint failed`, also at COMMIT with `defer_foreign_keys`). SQLite's own procedure turns the keys off **before** BEGIN and checks them before COMMIT:
```python
# db.py migrate(), replacing lines 58-61
with engine.connect() as conn:
    raw = conn.connection.dbapi_connection          # before any BEGIN: the pragma is a no-op inside a transaction
    raw.execute("PRAGMA foreign_keys = OFF")
    try:
        with conn.execution_options(**{_WRITE_OPTION: True}).begin():   # BEGIN IMMEDIATE, as before
            config.attributes["connection"] = conn
            command.upgrade(config, "head")
            if conn.exec_driver_sql("PRAGMA foreign_key_check").first() is not None:
                raise RuntimeError("a migration left a reference to a missing row; nothing was applied")
    finally:
        try:
            raw.execute("PRAGMA foreign_keys = ON")
            restored = raw.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        except sqlite3.Error:
            restored = False
        if not restored:                            # never back to the pool with keys off
            conn.invalidate()
            raise RuntimeError("foreign keys could not be turned on again; the connection was discarded")
```
Every migration, old ones included, now runs with keys off and is checked whole before commit. Measured by the devil's advocate on the `data-probe` copy: `foreign_key_check` 0.8 ms, `migrate` at head 2 ms.

**Migration `0013_shops.py`** (forward-only, hand-written SQL, in this order):
```sql
DROP TRIGGER keep_shop;
CREATE TABLE shop_profile_new (
  id INTEGER PRIMARY KEY,                                    -- no CHECK (id = 1) any more
  revision INTEGER NOT NULL CHECK (revision >= 1),           -- the profile's own revision (PUT /api/shop-profile), unchanged
  name TEXT, contact TEXT, logo_asset TEXT REFERENCES assets(sha256), updated_at TEXT NOT NULL,
  identifier TEXT NOT NULL UNIQUE                            -- the normalised form only (D-002), so UNIQUE ignores case and spacing
    CHECK (length(identifier) BETWEEN 3 AND 32 AND identifier NOT GLOB '*[^a-z0-9]*'),
  password_hash TEXT CHECK (password_hash IS NULL OR password_hash LIKE '$argon2%'),  -- NULL: nobody can sign in
  state TEXT NOT NULL CHECK (state IN ('active','suspended')),
  created_at TEXT NOT NULL
);
INSERT INTO shop_profile_new (id,revision,name,contact,logo_asset,updated_at,identifier,password_hash,state,created_at)
  SELECT id,revision,name,contact,logo_asset,updated_at,'originalphone',NULL,'active',
         COALESCE((SELECT min(created_at) FROM creations),updated_at) FROM shop_profile;
DROP TABLE shop_profile;
ALTER TABLE shop_profile_new RENAME TO shop_profile;       -- the eleven child tables keep REFERENCES shop_profile(id)
CREATE TRIGGER keep_shop BEFORE DELETE ON shop_profile BEGIN SELECT RAISE(ABORT,'shop cannot be deleted'); END;
CREATE TABLE chat_reads_new (                              -- 0012's columns, with the key unique per shop
  id TEXT PRIMARY KEY, shop_id INTEGER NOT NULL REFERENCES shop_profile(id), creation_id TEXT REFERENCES creations(id),
  key TEXT NOT NULL, payload_sha TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('running','succeeded','failed','interrupted')),
  provider TEXT NOT NULL, model TEXT NOT NULL, rate_card_json TEXT NOT NULL,
  cost_micros INTEGER NOT NULL, cost_is_estimate INTEGER NOT NULL,
  usage_json TEXT, provider_request_id TEXT, response_json TEXT, created_at TEXT NOT NULL, finished_at TEXT,
  UNIQUE (shop_id, key)
);
INSERT INTO chat_reads_new (<the sixteen columns>) SELECT <the sixteen columns> FROM chat_reads;
DROP TABLE chat_reads;
ALTER TABLE chat_reads_new RENAME TO chat_reads;
CREATE INDEX chat_reads_created ON chat_reads (created_at);
ALTER TABLE login_failures ADD COLUMN identifier TEXT;     -- NULL on older rows: they count for the address only
CREATE INDEX login_failures_identifier ON login_failures(identifier,ip,attempted_at);
CREATE INDEX poster_jobs_shop_started ON poster_jobs(shop_id,started_at);   -- the fair queue (D-005)
```
- **One migration, not 0013 and 0014:** both rebuilds need the keys off, the same release gate checks them, and one backup point covers both. Nothing references `chat_reads`, so its rebuild is the simple case. Tried on a copy of `data-probe` (2026-11-15): row counts of every table identical, the three ledger sums identical (512,881 / 7,269,000 / 513,948 µ$), `integrity_check` ok, `foreign_key_check` empty; afterwards shop 2 may reuse shop 1's key, shop 1 may not reuse its own.
- The lookup changes with it: `SELECT … FROM chat_reads WHERE shop_id=:shop AND key=:key` (reads.py:550), and the replay check compares the payload only (reads.py:584). Another shop's key is then a fresh key: the same path and answer as any new key.
- 0013 removes no row: `meta.password_fingerprint` stays for the adoption below. The file states its preservation contract for the rehearsal (Release gate): `PRESERVED` = `shop_profile`, `chat_reads` and `login_failures` with their 0012 columns; `ADDED` = the expected values of the new columns, the per-shop key and the three indexes.
- Password and state changes do not touch `revision` or `updated_at`: those belong to the profile form's optimistic check.
- **The pilot's identifier is the constant `originalphone`**, the user's to confirm before T-MULTI-SHOP-001 is committed; afterwards a different one is a forward migration `UPDATE shop_profile SET identifier=… WHERE id=1`, never an edit of 0013.
- Every other table is untouched and keeps `shop_id = 1`, so the ledger (`poster_calls` through `poster_jobs.shop_id`, `chat_reads.shop_id`) is shop 1's. `provider_calls` (the evaluation CLI's ledger) has no shop and counts for the service only; the hosted pilot's data folder started empty (D-HOSTED-PILOT-003), so its ledger is wholly shop 1's.

**Adoption of `SHOP_PASSWORD_HASH`** (`auth.adopt_password_setting(engine, settings)`, at start in place of `end_sessions_on_new_password`, api.py:405; one write transaction). `S` is the setting, `H` shop 1's stored hash, `F` the fingerprint row, "data" means `F` exists or shop 1 has a product input:

| S | H | Case | At start |
|---|---|---|---|
| present | NULL | first start after 0013 (or a new installation given the setting) | **today's rule first:** if `F` is missing or differs from SHA-256 of `S`, `DELETE FROM sessions` (all are shop 1's); then `UPDATE shop_profile SET password_hash=:S WHERE id=1 AND password_hash IS NULL`; then `DELETE FROM meta WHERE key='password_fingerprint'` |
| present | set | adopted earlier | not read; warning in the log: "SHOP_PASSWORD_HASH is no longer read: shop 1 has its own password since migration 0013 (python -m affiche.shops set-password). Remove the setting." |
| absent | set | normal after adoption | nothing |
| absent | NULL, with data | an upgraded pilot with no password anywhere | **refuse to start** (`ConfigError`): "Shop 1 has data but no password and SHOP_PASSWORD_HASH is not set: set it to the pilot's hash for this start, or run python -m affiche.shops set-password originalphone." |
| absent | NULL, no data | a new installation | start; log "shop 1 has no password: python -m affiche.shops set-password originalphone"; nobody can sign in to it until then |

`validate_config` (auth.py:43-49) no longer requires the setting; when present it must still be a valid Argon2 hash. **Not chosen:** refusing to start when the setting differs from a stored hash (after an operator reset the setting is stale by design, and an unattended restart after an out-of-memory kill would take the service down); the setting overriding the row at each start (it would undo the owner's own change). Sessions survive 0013 when the password did not change, so the pilot's phone stays signed in across the release.

**What the deploy does when the start fails** (deploy.py:271-276): the migration and the adoption run in the new container, after the old one is stopped and the pre-release backup is taken. A failure **inside** the migration rolls everything back (version stays 0012). A failure **after** the migration's commit (the adoption refusal, or any later start error) leaves the database at 0013. In both cases the new container does not become healthy and `deploy.py` prints "THE SERVICE IS DOWN", the container's last lines and the recovery text ("Code-only release: git checkout <previous commit> … Release with a migration: fix forward, or restore the backup taken just before"), and exits 1. It never redeploys by itself. Fix forward for the adoption refusal: put the hash in `app.env` and recreate, or run `set-password` in a one-off container of the new image (the schema is at head).

**Failure modes & handling:**
| Failure | Detection | Behavior |
|---|---|---|
| Migration fails half way (disk, lock, constraint), or the process is killed | exception, or the journal at reopen | rollback; version 0012, old table and trigger intact (devil's advocate's `kill -9` run); start fails |
| A migration leaves a broken reference | `foreign_key_check` before commit | RuntimeError, rollback, nothing applied |
| `foreign_keys` cannot be turned on again | the pragma raises or reads 0 | the connection is invalidated (never returns to the pool) and start fails; a new connection gets the pragmas from `_on_connect` |
| Upgraded pilot started without the setting | adoption table | refuses to start with the sentence above; database at 0013, fix forward |
| Adoption write fails | exception at start | start fails; nothing half done (one transaction) |
| The environment password was changed while the old version ran, then the release starts | fingerprint differs | every session ends at that start, as today |
| Operator forgets to remove the setting | warning at each start | no effect; removal is a step of the release gate |
| **A backup is restored** | the operator restores (deploy/README.md, Restore) | passwords, states and sessions return to the backup's moment: a reset after a lost phone is undone and its session lives again. The restore runbook (T-005) ends every session after a restore (`python -m affiche.shops end-sessions --all`), and the operator redoes the resets and suspensions made since the backup; shops are told that a password changed after that time must be changed again |
| Fresh database without the setting | adoption table | starts; shop 1 unusable until `set-password` |

**Edge cases:** shop 1 with no creation: `created_at` = its `updated_at`. Login failures from before 0013 count for the address only and are purged after 15 minutes. `meta.provider_mode` and `planner_mode` are service-wide and untouched. `looks.shop_id` has no foreign key (0010): the rebuild leaves it alone; the migration test asserts its rows keep shop 1.

**Security / data notes:** the hash column accepts only Argon2 text, so a plaintext pasted by mistake is refused. The migration reads no environment.

---

## D-MULTI-SHOP-002 — Sign-in, sign-out on the server, password change (covers R-MULTI-SHOP-001; 006 at sign-in)

**Identifier:** one function `auth.identifier_key(text)`: `unicodedata.normalize("NFKD", text[:64]).lower()`, then every character outside `a-z0-9` removed. The same function makes the stored identifier at creation and the lookup key at sign-in. « Original Phone », « original-phone » and « ORIGINALPHONE » open the same shop. The identifier is one the operator chooses, which may be a phone number in one written form: « 034 12 345 67 » gives `0341234567`, while « +261 34 12 345 67 » gives `261341234567`, a different identifier; the operator tells the owner the form he chose. A result outside 3–32 characters is simply unknown (no 422: the same answer as a wrong one).

**API contract:**
```
POST /api/session                body { identifier: str 1–64, password: str 1–1024 }   no session; Origin; bundle ≥ 3
  200 { authenticated: true, shop_id: int }   Set-Cookie as today (HttpOnly, SameSite=Strict, Secure on HTTPS, 90 days)
  401 wrong_credentials    unknown identifier, wrong password, shop without password: one answer, equal except request_id
  403 shop_suspended       only after a correct password
  429 rate_limited         Retry-After: 900
  409 bundle_outdated      an older tab (its body has no identifier)
GET /api/session                 200 { authenticated: false, support_fr?: str } | { authenticated: true, shop_id: int }
DELETE /api/session              200 { authenticated: false }   (auth.logout auth.py:119-122); X-Affiche-Shop checked, bundle not
POST /api/session/password       session, Origin, bundle, X-Affiche-Shop; no Idempotency-Key (security notes)
  body { current_password: str 1–1024, new_password: str 1–1024 }
  200 { changed: true }    this session kept; the shop's other sessions ended; no other shop's
  403 wrong_password · 422 password_too_short (< 10 characters) · 429 rate_limited
```
`support_fr` is the new optional setting `SUPPORT_CONTACT_FR` (≤ 200 characters, e.g. « Miorantsoa au 034 … »), shown under the sign-in form as « Mot de passe oublié ? Contactez {support_fr}. »; absent when not set. `verify.sh` compares the signed-out body exactly (verify.sh:61-62); it checks `"authenticated":false` instead (T-002). The password change's screen is the shop's dashboard (R-SHOP-DASH-003); this feature builds the route and its tests only.

**`auth.login(engine, identifier, password, ip, previous=None) -> (token, shop_id)`:**
```
key = limit_key(ip) (existing: IPv4 as is, IPv6 by /64);  name = identifier_key(identifier)
count(): pair = failures since 15 min WHERE ip=key AND identifier=name; address = failures since 15 min WHERE ip=key
count() over a limit → 429 rate_limited (no slot taken, nothing written)
with VERIFYING (the existing 2-at-a-time semaphore, auth.py:21), held until the write transaction below has committed:
    count() again → over a limit → 429 rate_limited           # requests that queued for the slot are stopped here
    shop = SELECT id,password_hash,state FROM shop_profile WHERE identifier=name
    stored = shop.password_hash if shop else None
    ok, upgraded = PASSWORDS.verify_and_update(password, stored or DUMMY_HASH)   # Argon2: no write transaction open
    valid = ok and stored is not None
    write_tx:  purge old failures and expired sessions (as today)
               valid → re-read the row; still valid only if password_hash is still `stored`
               valid, 'active'    → store `upgraded` if any; delete `previous`'s session row; insert a session for shop.id
               valid, 'suspended' → nothing written
               not valid          → INSERT login_failures (ip, identifier, attempted_at) with `name`, known or not
slot released; then: not valid → 401 wrong_credentials; suspended → 403 shop_suspended; else the token
```
`DUMMY_HASH = PASSWORDS.hash(secrets.token_hex(16))` once at module import. `verify_and_update` (pwdlib 0.3.1, signature `(password, hash) -> tuple[bool, str | None]`, read in the installed package) returns a new hash when the stored one uses other parameters than `PasswordHash.recommended()`; it is stored only for an active shop and only if the row's hash is still the verified one.

**Limits:**
| Counter | Key | Limit per 15 min | Why |
|---|---|---|---|
| Identifier from an address | (`identifier`, address or /64) | 5 failures | the requirement's limit; one owner's mistakes lock only his shop from that address |
| Address alone | address or /64 | 20 failures | bounds guessing many identifiers from one place |
| Identifier from everywhere | — | none, on purpose | anyone could lock a shop out from anywhere; guessing is bounded by Argon2, the two limits and the password lengths (D-003) |

**Guarantees, stated as they are:**
- **Limits:** they are counted before a verification slot is taken and again once it is held, and the slot is held until the failure (or the session) is committed. A request that gets a slot therefore sees every failure recorded by the requests that held it before; only the two that hold the slots at the same moment can count the same number. A burst of concurrent wrong attempts records at most one failure beyond each limit, whatever the database's writer is doing; the rest are refused without verification. Holding the slot over the write costs at most `busy_timeout` (5 s) of waiting for two sign-ins when another writer holds SQLite's lock; Argon2 still runs with no write transaction open. Tested with concurrent failures and with a deliberately blocked writer.
- **Timing:** one Argon2 verification in every case that passes the limits: unknown identifier, wrong password, shop without password, suspended shop. Caveat: the dummy uses `PasswordHash.recommended()` parameters; an adopted environment hash may have been made with others (`validate_config` accepts any valid Argon2 hash), and until its first successful sign-in upgrades it, signing in to `originalphone` may take a different time than an unknown identifier. That tells only that `originalphone` exists, which is not a secret. Hashes made by the command and the password route use the dummy's parameters.
- **Residual, not solved:** the address-wide limit lets one caller behind a shared address (a carrier's NAT, many phones on one public address) block sign-in for **every** shop behind that address for fifteen minutes, with 20 wrong attempts. The per-identifier limit does not prevent it. The support line on the form says whom to call.

**Sessions:**
- Reading a session joins the shop: `SELECT s.shop_id FROM sessions s JOIN shop_profile p ON p.id=s.shop_id WHERE s.token_hash=:h AND s.expires_at>:now AND p.state='active'` (auth.py:56-61). A suspended shop's sessions stop working at once and work again when it is enabled (D-006).
- Ending one shop's sessions is `DELETE FROM sessions WHERE shop_id=:shop [AND token_hash<>:mine]` (password set or changed). No credential-version column: session rows are already server-side, and the race with a sign-in verified on the old hash is closed by re-reading the hash in the write transaction.
- Signing in on a device that holds another session deletes that session (existing `previous`, auth.py:106-107): shop B signing in on shop A's phone ends A's session on that phone.

**Password change (`auth.change_password(engine, shop, token, current, new, ip)`):** it keeps the current session's token, so it sets no cookie and is not one of the cookie-changing operations of D-007. The same two limits, keyed by the shop's own identifier, counted again inside the slot, and the slot held until its transaction has committed; `len(new) < 10` → 422 before any verification; `current` verified and `new` hashed under `VERIFYING`, outside the transaction; in the write transaction the stored hash must still be the verified one, else 403 `wrong_password`. A wrong `current` is recorded in `login_failures` (a stolen session cannot guess the password here). Success: `UPDATE password_hash`, `DELETE FROM sessions WHERE shop_id=:shop AND token_hash<>:mine`. The status is 403, not 401, because the editor treats any 401 as the end of the session (App.vue:1250, ChatView.vue:37).

**Boundary rules (`AccessBoundary`, api.py:166-256), in order:**
| Rule | Change |
|---|---|
| Origin on every state-changing request | unchanged |
| Session required under `/api/` except `/api/session` | also except `/api/status`, which checks its own caller (D-004) |
| **`X-Affiche-Shop`**: present and not the session's shop → 409 `shop_changed`, nothing done | new. A **stale-tab guard, not authentication**: it never grants anything, a forged value only gets the request refused, and an absent header passes (images loaded by `<img>`, older bundles). Exempt: `GET` and `POST /api/session`. **Checked on `DELETE /api/session`**, so an old tab of shop A cannot end shop B's session |
| Bundle ≥ `BUNDLE` on state-changing requests | `POST /api/session` is no longer exempt (an older tab's sign-in has no identifier and must get the « rechargez » sentence); `DELETE /api/session` stays exempt. `BUNDLE` 2 → 3, both sides |

**New sentences (`MESSAGES`, api.py:42; the existing test makes every code have one):**
| Code | Status | Sentence |
|---|---|---|
| `wrong_credentials` | 401 | « Identifiant ou mot de passe incorrect. » |
| `shop_suspended` | 403 | « Cette boutique est suspendue. Contactez l’administrateur. » |
| `shop_changed` | 409 | « Une autre boutique est connectée dans ce navigateur. Connectez-vous pour continuer. » (the page then shows the signed-out screen, D-007 rule 3) |
| `wrong_password` | 403 | « Le mot de passe actuel n’est pas le bon. » |
| `password_too_short` | 422 | « Le nouveau mot de passe doit avoir au moins 10 caractères. » |

**Failure modes & handling:**
| Failure | Detection | Behavior |
|---|---|---|
| Database busy during the sign-in transaction | busy_timeout 5 s | 503 `storage_unavailable` (existing); the failure may be unrecorded; the client may retry |
| Crash between verification and the transaction | — | nothing written; the client retries |
| Password changed (owner or operator) during a sign-in's verification | hash re-read in the transaction | 401, recorded as a failure |
| Shop suspended during a sign-in's verification | state re-read | 403, no session |
| Stored hash unparsable | pwdlib raises | 500 `internal_error`, nothing written; unreachable in practice (the CHECK, `PASSWORDS.hash`) |
| Burst of wrong attempts | counts inside the slot, slot held through the write | at most one failure past each limit; two verifications at a time, never inside a write transaction |
| Another writer holds SQLite's lock during a sign-in | busy_timeout 5 s, slot held | the two slots wait; later sign-ins wait for a slot, then count what was committed; past 5 s: 503 `storage_unavailable`, nothing recorded |
| Password change answer lost | client error | the new password is in force; a resend with the old `current` gets `wrong_password` |
| Strangers behind the owner's carrier address fail 20 times | address counter | every shop behind that address waits 15 minutes (residual above) |

**Edge cases:** an identifier with only punctuation normalises to nothing and is unknown. Two shops may share a display name. A new password equal to the old one is accepted. The owner changing his password on his phone ends his desktop session.

**Security notes:**
- **Enumeration:** one status, code and sentence for an unknown identifier, a wrong password and a shop without password; failures are recorded for unknown identifiers too, so the 429 threshold behaves the same; the suspension is told only to someone who gave the right password.
- **Session fixation:** tokens are made by the server at sign-in only (`secrets.token_urlsafe(32)`, stored as SHA-256); the device's previous token is deleted; HttpOnly, SameSite=Strict; a session never changes shop.
- **No Idempotency-Key on the password change:** `mutation_keys.payload_sha` would hold an unsalted SHA-256 of both passwords.
- The numeric `shop_id` is visible to its shop (session answer, storage prefix, header): it tells roughly how many shops were created before. Accepted.

---

## D-MULTI-SHOP-003 — The operator's command until the dashboard (covers R-MULTI-SHOP-001 operator reset, 006; the seam for R-ADMIN-002)

**Approach:** one module `backend/src/affiche/shops.py`, run as `python -m affiche.shops`, in the style of `backup.py` and `visuals/evaluate.py` (argparse subcommands, `main(argv, env_file=ENV_FILE) -> int`). **Its functions take a connection** and never commit by themselves: the command wraps each call in `write_tx`; the administration dashboard will put the shop's creation, its welcome grant and its audit row in one transaction around the same call. Passwords are hashed by the caller, outside the transaction.

| Function (conn first) | Does | Returns |
|---|---|---|
| `find_shop(conn, identifier)` | lookup by `identifier_key` | row or None |
| `create_shop(conn, identifier, name, password_hash)` | `identifier_key` checked (3–32); `name` checked by `Profile` (models.py:65); `INSERT INTO shop_profile (revision,name,updated_at,identifier,password_hash,state,created_at) VALUES (1,…,'active',…) RETURNING id` | shop id |
| `set_password(conn, shop_id, password_hash)` | `UPDATE password_hash`; `DELETE FROM sessions WHERE shop_id` | — |
| `end_sessions(conn, shop_id=None)` | `DELETE FROM sessions` for one shop or all (after a restore) | count |
| `suspend(conn, shop_id)` / `enable(conn, shop_id)` | D-006 | counts |
| `list_shops(conn)` | id, identifier, name, state, created_at | rows |

`new_password()`: 12 characters from `abcdefghjkmnpqrstuvwxyz23456789` (no 0/o, 1/l/i; about 59 bits), easy to type on a phone. A password given by a caller must have 10 characters or more.

**The command never migrates.** It opens `make_engine(settings.data_dir)` and compares `alembic_version` with the code's head (`ScriptDirectory.from_config(Config(BACKEND_DIR / "alembic.ini")).get_current_head()`, alembic 1.20.1, returns `0012` today); when they differ: exit 1, "the database is at <x>, this code expects <head>: start the application of this version once; this command never migrates". It does not take the `api` or `cli` lock, so it runs beside the API and during an evaluation run.
```
uv run python -m affiche.shops list
uv run python -m affiche.shops create <identifier> [--name "Nom affiché"]   # prints the password once
uv run python -m affiche.shops set-password <identifier>                      # prints the new password once; ends that shop's sessions
uv run python -m affiche.shops end-sessions (<identifier> | --all)
uv run python -m affiche.shops suspend <identifier> --yes                     # prints the shop's name; without --yes it only shows it
uv run python -m affiche.shops enable <identifier>
on mx1: sudo docker exec -it affiche-ia-affiche-ia-1 python -m affiche.shops …
exit 0 done · 1 refused (one line on stderr, nothing written) · 2 usage
```
The password is printed to the operator's terminal only; `docker exec` output is not in the container's log.

**Other callers that change:** `deploy/phone_session.py` (phone_session.py:79-84) passed a one-off password as `shop_password_hash`; after 0013 it would be adopted once and then ignored. It runs `migrate(make_engine(data-probe))` itself (it is the application's start for that folder), then `set_password` in a `write_tx`, starts the API without the setting, and prints the identifier with the address. `deploy.py`'s first-deploy `AFFICHE_SHOP_PASSWORD_HASH` (deploy.py:90-105) stays: on a new box it becomes shop 1's password through the adoption.

**Failure modes & handling:**
| Failure | Detection | Behavior |
|---|---|---|
| Schema not at head (a newer or older image than the database) | version compare | exit 1, nothing done |
| Identifier taken (any case or spacing) | UNIQUE on the normalised column | exit 1, nothing written |
| Database locked by the API | busy_timeout 5 s | exit 1 with the error; run again |
| The terminal output is lost after `create` | — | `set-password` makes a new one |
| Wrong shop about to be suspended | name printed, `--yes` required | nothing until confirmed; `enable` reverses (D-006) |
| A backup restored | operator | `end-sessions --all`, then redo resets and suspensions made since the backup (D-001) |

**Edge cases:** `suspend` on a suspended shop and `enable` on an active one change nothing and say so. Shop 1 can be suspended like any other.

**Security / data notes:** no network surface. Every operator action of this feature goes through these functions on one connection, so the dashboard's record of actions (R-ADMIN-001) is in the same transaction as the action.

---

## D-MULTI-SHOP-004 — Isolation as a tested property; usage and status (covers R-MULTI-SHOP-002)

**`GET /api/usage`:** the same fields as today (api.py:435-439), `recorded_micros` now the shop's own spend since `SPEND_CAP_SINCE` (`spent_micros(conn, settings, shop=shop)`, D-005); `cap_micros` and `since` are the service's configuration, not its totals (accepted in round 2). The fields stay as they are; the prepaid feature replaces the dollars by credits there (R-BALANCE-001 shows no dollars to a shop). Only the smokes read it (browser_smoke.py:1570, :1708, :1800, :1969).

**`GET /api/status`, operator only, until the administration has its own sign-in:** answered only when **both** `request.client.host` (after uvicorn's forwarded-header handling) is a loopback address **and** the `Host` header names a loopback host (`127.0.0.1`, `localhost`, `[::1]`, any port). Any other caller, signed in or not, gets 404 `not_found`. One function, `operator(request)`; the dashboard replaces its body with its session check (R-ADMIN-001). **Who that admits, honestly:** any caller on the machine that runs the API: on mx1, a process inside the container (`sudo docker exec affiche-ia-affiche-ia-1 python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/api/status').read().decode())"`, the pattern of verify.sh:34); in development, the developer's own browser through Vite (`changeOrigin: false` keeps `127.0.0.1:5173` as Host), **on purpose**. It relies on two configurations this route does not own: Caddy rewriting `X-Forwarded-For` and routing by the public Host (D-HOSTED-PILOT-001), and Vite keeping the tunnel's Host in `phone_session.py`; the spoofing tests below pin what the application itself does. The answer is unchanged (service totals, commit, migration, backup, failures).

| Caller (as the test builds it) | Host | Expected |
|---|---|---|
| TestClient `client=("127.0.0.1", 50000)` (Starlette 1.10 `TestClient(client=…)`, checked) | `127.0.0.1:8000` | 200 |
| same | `shop.example` | 404 |
| `client=("203.0.113.9", 50000)` | `127.0.0.1` | 404 |
| a shop's session, public client | `shop.example` | 404 |
| real uvicorn (extends `test_actual_uvicorn_http_session`), peer loopback, `X-Forwarded-For: 203.0.113.9` | `127.0.0.1:<port>` | 404 (client becomes 203.0.113.9) |
| real uvicorn, peer loopback, `X-Forwarded-For: 127.0.0.1` | `affiches.miorantsoa.app` | 404 (Host) |
| real uvicorn, peer loopback, no forwarding | `127.0.0.1:<port>` | 200 |

**The two-shop test, `backend/tests/test_two_shops.py`** (from the audit's test, with a real second shop):
- Shop B made by `shops.create_shop`; both shops signed in through `POST /api/session` with their identifiers; stub image and planner providers, workers running (TestClient lifespan), as in the audit.
- Shop A builds one object of every kind through the real routes: logo, original, style asset, input, creation, plan, scene, approved visual, look, text proposal (applied), text effect, render, confirmation, chat read (test_tenancy_audit.py:101-150).
- **Coverage:** the test reads A's `/api/openapi.json` and asserts `set(schema routes) == set(ATTEMPTS) | EXEMPT`. `ATTEMPTS` maps each (method, path template) to requests built with A's ids. At T-MULTI-SHOP-003 `EXEMPT` = `GET/POST/DELETE /api/session`, `GET /api/capabilities` (modes and estimates, no shop data), `GET /api/status` (asserted 404 for shops above). T-MULTI-SHOP-004 adds `POST /api/session/password` to `EXEMPT` with its own tests, in the same task that adds the route. A new route in neither set fails the test.
- **Same answer as for nothing:** every attempt is sent twice by B, with A's ids and with fresh ids (`uuid4`, a random SHA-256) in the same places; the (status, error code) pairs must be equal and a refusal. Ids in the path (poster, version, visual, plan, job, look, proposal, effect, render, confirmation, input, asset, thumbnail) and in bodies (B's poster pointing at A's visual, effect, logo, input, plan, look, style asset; A's photo in B's input; A's logo in B's profile; a read naming A's poster). **A read sent by B with the Idempotency-Key A used** gets the same answer as with a fresh key (201, a new read of B's), now that keys are per shop.
- **Lists:** `GET /api/creations`, `GET /api/looks`, B's `/api/creations/{own}/jobs` and `/visuals` hold none of A's ids.
- **Usage:** B's `recorded_micros` equals B's own ledger (A's spend inserted on the ledger is absent).
- **Same bytes:** B uploads A's original, and A's generated scene as a style: the answers have the same keys and warnings as for new bytes; B can read the asset it uploaded, never A's visual nor its thumbnail.
- **Worker:** B's scene lands in B's shop (`poster_visuals.shop_id`); A gets 404 on it.
- **Stale tab:** B's cookie with `X-Affiche-Shop: <A>` → 409 on a change and on `DELETE /api/session`; B's session still works.
- **Mutation check (in the task's verify, not in the suite):** a scratchpad script replaces `store._owned` by an id-only lookup (as outputs/saas-review-2026-11-15/mutant_check.py) and the test must fail.

`/api/openapi.json` shows every shop the fixed application version "0.2.0", not the commit. Accepted.

**Failure modes & handling:**
| Failure | Detection | Behavior |
|---|---|---|
| A new route without a shop check | coverage or same-answer assertion | the suite fails |
| A route reveals existence (409 for A's id, 404 for a random one) | same-answer assertion | the suite fails |
| `/api/status` reachable through a proxy | the spoofing matrix | the suite fails |

**Edge cases:** an id existing in both shops cannot happen (UUIDs; SHA-addressed files shared only through grants). A shop with no data lists zero items.

**Security / data notes:** the test never reads `backend/.env` (`env_file=None`, test_api.py:41-45).

---

## D-MULTI-SHOP-005 — What all shops share: provider spend, queue, reads (covers R-MULTI-SHOP-003)

**Approach:** every provider reservation passes one guard with the checks in the order a shop must be told; each shop has a daily provider-spend ceiling; the queue serves shops in turn. No cap on queued generations: the fair queue already keeps one shop's long queue from delaying another shop's first job.

**`jobs.provider_guard(conn, settings, shop, estimate_micros)`**, inside the existing admission transactions, called by `jobs._reserve` (call 1 from `enqueue`, call 2 from `reserve_rate_limit_retry`, jobs.py:55-62, :177-192) and by `reads._admit` (reads.py:544-574):
```
1. shop_profile.state != 'active'                                              → 403 shop_suspended
2. spent_micros(conn, settings) + estimate > SPEND_CAP_USD                      → 429 budget_exhausted  (the service is paused)
3. spent_micros(conn, settings, shop=shop, since=<today UTC>) + estimate > SHOP_DAILY_SPEND_USD → 429 shop_daily_limit
```
The service check comes before the shop's own, so that when the service's cap is reached every shop is told the service is paused. A refusal raises inside the transaction: nothing reserved, nothing written (existing rule).

**Reads, in this order** (reads.py:562-574 today: mode lock, daily limit, cap): mode lock (unchanged, a configuration error), `provider_guard`, then the daily read limit (200 per shop, reads.py:33, unchanged), then **reads in progress**: `SELECT COUNT(*) FROM chat_reads WHERE shop_id=:shop AND status='running'` ≥ 2 → 429 `reads_busy`. One device already sends one read at a time (ADR-098, one chat tab per device by Web Lock, ADR-097); two lets two phones of one shop read at once, and bounds what several can start. The existing sweep (reads.py:511-515) closes a `running` row after 60 s, so a crashed read frees its place. After admission, a read passes the same cutoff as a job before its call is sent (`reads._send`, D-006).

**`spent_micros(conn, settings, *, shop=None, since=None)`** (admission.py:295-302): without `shop`, unchanged. With `shop`: `poster_calls` joined to `poster_jobs` on `job_id` where `shop_id = :shop`, plus `chat_reads` where `shop_id = :shop`; `provider_calls` is never a shop's. `since` defaults to `SPEND_CAP_SINCE`; the day is `utc_now()[:10]`, the same text comparison as today.

**Setting `SHOP_DAILY_SPEND_USD`** (config.py, `PositiveUsd`, default 2.00; added to `test_config.NAMES`). It is a budget of the admission day: a reservation counts on the UTC day it was admitted (its `created_at`), also when its call is sent after midnight. It is the only bound on the paid operations that will cost no customer credit (plans, looks, textures, text patches, reads). A reservation counts until its real cost replaces it (scene 0.40, plan 0.10, texture 0.30, read 0.02 by default); 2.00 is about fifty images a day at the measured USD 0.028 to 0.040 each. An interrupted call keeps its reservation as its cost (existing rule) and so counts in the shop's day.

**Fair queue** (`jobs.claim`, jobs.py:129): queued rows ordered by the time their shop last had a job started, oldest (or never) first, then as today:
```sql
SELECT j.* FROM poster_jobs j WHERE j.status='queued' AND j.kind IN :kinds
ORDER BY (SELECT MAX(s.started_at) FROM poster_jobs s WHERE s.shop_id=j.shop_id), j.created_at, j.id
```
SQLite sorts NULL first in ascending order, so a shop's first job goes before a busy shop's next one. The slot loop (jobs.py:131-136) and the scheduler's two tasks (service.py:213-219) are unchanged. Index `poster_jobs_shop_started` (0013) serves the subquery.

**Worker** (worker.py:63-72): a 429 retry's reservation may now be refused by any of the three checks; `if refused.code != "budget_exhausted": raise` becomes `if refused.code not in jobs.SPEND_REFUSALS` (`budget_exhausted`, `shop_daily_limit`, `shop_suspended`). The job then fails with the provider's code at cost 0, instead of escaping to `reconciliation_required`. The cutoff at dispatch is D-006.

**Sentences:**
| Code | Status | Sentence |
|---|---|---|
| `budget_exhausted` (changed, api.py:105) | 429 | « La création d’images est en pause pour tout le service. Vous pouvez encore modifier et télécharger vos affiches. Réessayez plus tard. » |
| `shop_daily_limit` | 429 | « La boutique a atteint sa limite d’images pour aujourd’hui. Vous pouvez encore modifier et télécharger vos affiches. Réessayez demain. » |
| `reads_busy` | 429 | « Deux messages de la boutique sont déjà en cours de lecture. Patientez quelques secondes, puis renvoyez le vôtre. » |

In the chat, `shop_daily_limit` and `reads_busy` on a read put the text back in the field like `budget_exhausted` (ChatView.vue:257). None of the new codes goes into the chat's final list (chat.ts:142-146): a paid card refused by a limit stored nothing and keeps its request and « Réessayer » (ADR-097).

**Note for the prepaid balance, and nothing more:** a customer credit is debited once, at the admission of one image job, never per provider call or retry. Plans, textures, looks and text patches cost the provider and no credit; that is exactly why this feature keeps a provider-spend ceiling per shop. `provider_guard` is a provider guard and stays one; it is not the credit's seam.

**Failure modes & handling:**
| Failure | Detection | Behavior |
|---|---|---|
| Service cap reached (by any shop or by the evaluation CLI) | check 2 | every shop: 429 `budget_exhausted`, nothing reserved; editing and downloads work |
| A shop's day reached | check 3 | that shop only: 429 `shop_daily_limit`; the others go on |
| Two tabs or phones of one shop admit at once | `BEGIN IMMEDIATE` | serialised: the second sees the first's reservation and the first's `running` read |
| A 429 retry refused by a guard | worker.py:67 | job `failed` with the provider code, call 2 never reserved, cost 0 |
| Reservations of running jobs fill a shop's day | check 3 | new requests refused until real costs (lower) replace them |
| Clock of the day | UTC text comparison | the day turns at 03:00 in Madagascar, as the read limit |

**Edge cases:** with the stub providers every estimate is 0, so only the read counts apply (tests that need a ceiling insert ledger rows, as the audit did). A shop that never ran a job is served first. Recovered jobs (`started_at` NULL, jobs.py:263) keep their shop's history from its other jobs.

**Security / data notes:** one place decides whether a provider call may be reserved, and one place (D-006) whether it may be sent.

---

## D-MULTI-SHOP-006 — Suspension (covers R-MULTI-SHOP-006)

**`shops.suspend(conn, shop_id)`:** `UPDATE shop_profile SET state='suspended'`, then `jobs.cancel_queued(conn, job_id, now)` for each of the shop's `queued` jobs. `cancel_queued` is the body of today's owner cancellation (jobs.py:114-117: the job `cancelled`, its `reserved` call `cancelled` at cost 0), shared by `jobs.cancel` and `suspend`; the prepaid balance adds its credit release beside it. **Sessions are not deleted:** the session read requires an active shop (D-002), so they stop working at once, and `enable` brings them back. When the reason is a leaked password, the operator also runs `set-password`, which deletes them.

**Where the provider call is sent is the cutoff:**
- `jobs.dispatch` (jobs.py:145-153), in its write transaction, reads the job's shop. Suspended: the job becomes `cancelled` with `error_code='shop_suspended'`, its `reserved` call `cancelled` at cost 0, committed, and `dispatch` returns None. `run_job` (worker.py:57) sends nothing when `dispatch` returns None and returns. This covers a 429 retry whose call 2 was reserved before the suspension and waits its 2 s (worker.py:70-72).
- `jobs.recover` (jobs.py:250-272): a running job of a suspended shop whose call is absent or `reserved` is cancelled the same way instead of being requeued. A job whose call was dispatched (`running`) is `interrupted` as today (its outcome is unknown); a spooled result is finalised as today.
- **A chat read gets the same cutoff.** Today `reads.read` (reads.py:624-655) admits in `_admit` (reads.py:627, the `running` row and its reservation, transaction 1) and then calls `_ask` (reads.py:634, the provider call) with nothing in between. A new transition `reads._send(engine, read_id) -> bool` runs between them, in one write transaction:
  ```
  SELECT r.status, p.state FROM chat_reads r JOIN shop_profile p ON p.id=r.shop_id WHERE r.id=:id
  status 'running' and state 'active'  → True: the call may be sent
  status 'running' and state not active → UPDATE chat_reads SET status='failed', cost_micros=0, cost_is_estimate=0,
                                          finished_at=:now WHERE id=:id AND status='running'   → False
  status no longer 'running' (the 60 s sweep closed it) → False
  ```
  `read` answers False with 403 `shop_suspended` (or `read_failed` when the sweep closed it) and never calls `_ask`. `failed` at cost 0 is the existing rule for a call never sent (ADR-094, `_finish` reads.py:593-602). A replay of the same key later finds `failed` and answers `read_failed` (reads.py:588-589), by which time the shop's session is refused anyway. The commit of `_send` is the moment the call counts as sent: a suspension that commits after it lets that one call finish, as for a dispatched job.
- **A call already sent finishes.** It is in flight or paid; stopping it cannot recover the money and would leave an unknown outcome. Its result is stored in the shop and is there when the shop is enabled. A chat read past `_send` finishes within its 20 s bound (D-TEXT-FIRST-002).
- **Races, closed:** a request authenticated just before the suspension commits and admitted after it is refused by `provider_guard` in its own transaction; a call reserved before it is cut at `dispatch` (jobs) or `_send` (reads); a sign-in verified before it gets no session (state re-read, D-002). A render admitted in that window runs: it costs nothing.

**`shops.enable(conn, shop_id)`:** `state='active'`. Data, versions, styles, the ledger, the profile and the sessions were never touched. Cancelled jobs stay cancelled; the owner asks again.

**What an open tab of the shop sees:** its next request gets 401 (the session read requires `active`), which is evidence of another identity: shop content is hidden and the signed-out screen shows (D-007, rule 3). Signing in shows « Cette boutique est suspendue. Contactez l’administrateur. ». After `enable`, the tab, still bound to that shop, is signed in again at its next start (its session row was kept); signing in on the form also works, and the page reloads fresh.

**Failure modes & handling:**
| Failure | Detection | Behavior |
|---|---|---|
| Suspension transaction fails | exception | exit 1, nothing changed |
| Suspended while a 429 retry waits to send call 2 | `dispatch` | cancelled at cost 0, nothing sent |
| Suspended between a read's admission and its call | `reads._send` | the read `failed` at cost 0, 403 `shop_suspended`, nothing sent |
| Suspended, then the process restarts | `recover` | unsent calls cancelled, not requeued |
| A job finishes after the suspension | normal finalisation | its version is stored in the shop; seen after enable |
| The wrong shop suspended | operator | `enable` restores everything but the cancelled jobs |

**Edge cases:** suspending every shop leaves the service running for nobody; the operator's `/api/status` still answers. Free jobs (renders) of a suspended shop are not sent to a provider and need no cutoff.

**Security / data notes:** suspension holds even if a session row survives, because the session read requires `active`.

---

## D-MULTI-SHOP-007 — The browser: the identity gate, sign-out, storage per shop (covers R-MULTI-SHOP-001, 004)

### The identity gate: one rule, stated once, used everywhere

`bound` is the tab's shop: kept in `sessionStorage` under `affiche.bound` (per tab; kept across reloads and Back) and in api.ts. The gate is open only while the last `GET /api/session` answer names `bound`.

1. **A page is bound to at most one shop for its whole life:** the shop of the first session answer it accepted. A tab with no binding accepts the answer of its first start (the device's own session, as when the application is opened). A reload, a Back or a restore keeps the binding. The page never adopts another shop.
2. **Shop content is shown only while the last session answer says that same shop.** Before the first answer, while an answer is awaited after the page becomes visible again, and whenever an answer is missing or failed, shop content is hidden: the shop's part of the document (the header's shop name and navigation, `<main>`) carries the `hidden` attribute, so nothing of the shop is displayed or in the accessibility tree; nothing is merely laid over it. The components stay mounted, so a hidden editor keeps its unsaved state. A missing or failed answer shows « Connexion au serveur impossible. » and « Réessayer ».
3. **Any evidence of another identity ends in the signed-out screen, shop content hidden first:** a session answer naming another shop or nobody; a 409 `shop_changed` on any request; a 401 on any request but the sign-in (expiry, a password changed elsewhere, a suspension). The address's hash, which may name a poster, is cleared. When the reason is another shop, the screen says « Une autre boutique est connectée dans ce navigateur. Connectez-vous pour continuer. ». The page never reloads into whatever shop the cookie now holds.
4. **Showing a shop always takes an explicit sign-in on this page, which then loads fresh:** its answer sets `bound` to the shop signed in and a full reload follows; the reloaded page must find that same shop in `GET /api/session`, else rule 3. When the shop signed in is the one already bound and the page holds unsaved edits, the autosave sends them before the reload (if it cannot: « Recharger sans ces modifications »). « Se déconnecter » binds the page to nobody: it shows no shop until an explicit sign-in on it.
5. **Leaving and coming back:** `pagehide` hides shop content, so a back-forward cache snapshot holds none. `pageshow` with `persisted` reloads at once, and the reloaded page shows nothing of a shop before its session answer. Returning to visibility (`visibilitychange`) closes the gate and asks the session again before anything of the shop is visible or interactive; a `storage` event on the device key `affiche.identity` (written at every sign-in and sign-out) asks it again too.
6. **Without the Web Locks API the same rule holds**; only the serialisation of the cookie-changing operations below is lost. The cost, plainly: a late sign-in answer of shop A while B is using the device can leave the cookie on A; B's page then reaches the signed-out screen at its next request or session check, never A's data, and showing A takes A's explicit sign-in on a page.

**Why one rule is enough.** Every data request carries `X-Affiche-Shop: <bound>`, and the server answers it only when the cookie's session is that shop (else 409, D-002) and the row is that shop's (D-004). So a page's memory can only ever hold its bound shop's data, and the gate alone decides when that data is visible. There is no list of paths to keep complete and no `epoch`: an answer for another identity cannot reach the memory, and answers of the bound shop that arrive while the gate is closed only update hidden memory. Loading fresh stays a reload, never a hand reset of App.vue's twenty refs (round 1 P1-1: `signedOut` only flips a boolean, App.vue:1459; `route()` keeps a loaded poster, App.vue:597). Where `sessionStorage` is refused (some private modes), the binding lives in memory only, and a reload is a new page life that accepts the device's session, as a new tab would.

### Cookie-changing operations

Dropping a late answer's body does not stop the browser applying its `Set-Cookie` (round 2 P1-2). Two operations change the cookie: sign-in (`POST /api/session` sets it, api.py:621) and sign-out (`DELETE /api/session` deletes it, api.py:629). The password change keeps the session's token and sets none (D-002).
- Both run inside `navigator.locks.request('affiche-identity', { mode: 'exclusive' }, …)`, held until the response is complete (status and headers, where the browser applies `Set-Cookie`, then the body read) and then until `GET /api/session` has answered. Another tab's sign-in or sign-out waits for it. The chat already requires this API: it holds `navigator.locks.request('affiche-chat', …)` (ChatView.vue:448-453), and `lockless = !navigator.locks` (ChatView.vue:28) turns the chat off (ADR-097). `api()` has no time limit unless asked (api.ts:30-32); inside the lock the request gets 30 s and is aborted after, so a lost answer cannot hold the lock for ever.
- What a late answer can still do once the lock was given up (an aborted request) or without Web Locks: a late sign-out can delete a newer cookie (the server keeps that session's row; only this device has lost it): a 401, then the signed-out screen. A late sign-in can put an earlier shop's cookie back: rule 6. Neither shows another shop's data.

### Sign-in form

App.vue:1544: « Identifiant de la boutique » (`name="username"`, `autocomplete="username"`, `autocapitalize="none"`, `spellcheck="false"`, required) above « Mot de passe »; the line under the title becomes « Connectez-vous avec l’identifiant et le mot de passe de la boutique. »; under the button « Mot de passe oublié ? Contactez {support_fr}. » when the server gives it. The identifier is not remembered by the application (password managers fill it).

### « Se déconnecter »

A button in the header beside the shop's name (App.vue:1534), on every signed-in screen.

**The unresolved paid card** is the chat's own predicate, not a new one: `paid(item.card) && item.spent && !item.done` (ChatView.vue:59, `openCard`, under the rule « A paid card that still waits for its answer comes first », ChatView.vue:66-67). It is moved to chat.ts as `unresolved(item)` and used by `openCard`, by sign-out and by the eviction below. It holds for a card whose job is followed (`item.job`) and for one whose request is kept for « Reprendre » (`item.request`); a card retired by a final refusal is `done` (`conclude`, ChatView.vue:345) and is not kept, even with its request still attached.

1. `await flush()` (the autosave).
2. **The snapshot** of unresolved cards is built from the chat's **live thread in memory** plus every stored thread of the shop; for the live thread's own key the live items win. The chat's own `save()` catches a storage failure and goes on (ChatView.vue:96-106), so the stored copy of the current thread may be stale or absent while the exact paid request exists only in memory. ChatView hands its live items to App.vue through its adapter. If another tab holds the chat (`navigator.locks.query()` lists `affiche-chat` as held and this tab is not its owner), sign-out is refused with « Le chat est ouvert dans un autre onglet : déconnectez-vous depuis cet onglet. », because only that tab holds its live thread.
3. Two things may stop it, shown together in one confirmation with « Se déconnecter quand même » and « Annuler »:
   - the autosave could not save (offline, failed or `revision_conflict`, autosave.ts:27-51): « Des modifications de l’affiche n’ont pas pu être enregistrées : elles seront perdues. »
   - the snapshot holds an `unresolved` card: « Une image payée attend encore sa réponse. Elle restera sur cet appareil, visible seulement par cette boutique, pour la reprendre à sa prochaine connexion. »
4. Inside the `affiche-identity` lock:
   1. **The kept record first.** When the snapshot holds unresolved cards, write `affiche.shop<id>.kept` = `{ <thread key>: [its unresolved items] }`. This write must succeed before the server is asked to sign out. If it fails: stop, nothing else is changed, and say « La demande payée en attente n’a pas pu être gardée sur cet appareil : vous restez connecté. Attendez la réponse de l’image, ou libérez de la place dans le navigateur, puis réessayez. »
   2. `DELETE /api/session` (with `X-Affiche-Shop`). Network failure or timeout: put `kept` back exactly as it was before step 4.1 (removed if there was none: a record whose restoration failed may be the only copy), « Déconnexion impossible : la connexion au serveur est interrompue. Réessayez. », still signed in, nothing else touched. 409 `shop_changed` (another tab already changed shop): this shop's session on the device is already gone; continue.
   3. `GET /api/session` (the lock's rule); whatever it answers, the page goes on: it is about to be bound to nobody.
   4. Bind the page to nobody (`affiche.bound` = signed out); delete every `affiche.shop<id>.` key except `kept`; write `affiche.identity`; remove the `beforeunload` warning; `location.replace(location.pathname)` (a reload without the hash).
5. **At that shop's next start**, before the chat reads anything: each card of `kept` is added by its id to its thread (the thread is created when it does not exist; a card already in the thread is left as it is and never doubled), in time order, and `kept` is removed only after every thread was written (copy, then remove, as for the legacy keys). The card then shows as after any reload: followed, or « Reprendre » with its kept request (ADR-097).

A failed or conflicting autosave never traps anyone in a shop: step 3 always offers to discard and sign out. Only a kept record that cannot be written (or a chat held by another tab) stops sign-out, because losing it could lose a paid image's request.

### Storage per shop

| Key | Today | After |
|---|---|---|
| chat threads, unsent text, pending read | `affiche.chat.*` (chat.ts:98-99) | `affiche.shop<id>.chat.*` |
| words before a first version | `affiche.words.*` (words.ts:3) | `affiche.shop<id>.words.*` |
| palette per poster | `affiche.palette.*` (App.vue:51) | `affiche.shop<id>.palette.*` |
| remembered style | `affiche.style` (App.vue:231) | `affiche.shop<id>.style` |
| theme, start view, `affiche.identity` | `affiche.theme`, `affiche.start` | device keys, unchanged |
| the tab's binding | — | `sessionStorage` `affiche.bound` |
| Web Lock `affiche-chat` | one per device | unchanged |
- One function in api.ts, `shopKey(name)`, builds every shop key from `bound` and **throws** while `bound` is not a shop whose gate has opened once; every storage access is already in a `try` ("convenience only"), so a read before the session finds nothing instead of another shop's data. The constants become functions (`threadKey`, `unsentKey()`, `pendingKey()`, the word and palette prefixes); the cleanups that list keys (ChatView.vue:101, App.vue:63, :902) list by the shop's prefix. The style reads done at setup (App.vue:232-238, :246-250) move into `loadShop()`.
- **Old threads and unresolved cards:** `save()` keeps the 30 newest threads (ChatView.vue:100-102 through `staleWords`, words.ts:22-25). A thread holding an `unresolved` card is taken out of the list before the cut, so it is never evicted; `affiche.shop<id>.kept` is not a thread key and is never listed. One device has at most one unresolved card at a time (ADR-098), so the exemption keeps at most one thread beyond the 30.
- **Keys already on the pilot's phone:** at start, before anything reads, each legacy key (`affiche.chat.*`, `affiche.words.*`, `affiche.palette.*`, `affiche.style`) is copied to `affiche.shop1.…` when that key does not exist yet, and removed **only after its copy succeeded**. They can only be shop 1's: no other shop existed. An interruption (tab closed, `setItem` refused for quota) leaves the rest legacy; the next start resumes, never overwrites, and never removes a key whose copy failed. An older tab still open may write legacy keys for a while; where a shop-1 key already exists they are dropped at the next start (that tab can save nothing to the server anyway).
- **What the browser may still hold after sign-out:** images under `/api/assets` and `/api/thumbnails` are cached `private, max-age=31536000, immutable` (api.py:324, ADR-087), and the history holds addresses with poster ids. The application never requests another shop's addresses, but someone with the browser's own tools can find them. The conditions of use (service-terms) will say so, and that a shared phone should be cleared with the browser's own settings. Not built: `Clear-Site-Data: "cache"` on sign-out (support per mobile browser not verified here).

**`X-Affiche-Shop`:** `api()` (api.ts:36) sends it with every request once `bound` is a shop.

**Bundle:** `BUNDLE` 2 → 3 in api.ts:27 and api.py:163 (T-MULTI-SHOP-002): an older tab's sign-in has no identifier and its storage is not per shop. The deployed pilot is on 2; later features of Release 1 may raise it again before the deploy.

**What the pilot's phone sees at the release:** an open tab of the old bundle can read and is refused on every change with « rechargez »; after a reload the new bundle moves the old keys to shop 1; the tab has no binding yet, so its first `GET /api/session` (still `shop_id: 1`, the session survived 0013 unless the environment password changed) binds it to shop 1, and his threads and style are there. At his next sign-in he types `originalphone` and his current password.

**Failure modes & handling** (each behaviour is rule 2 or rule 3 of the gate unless said):
| Failure | Detection | Behavior |
|---|---|---|
| `localStorage` unavailable | exception | as today: nothing kept, nothing breaks |
| `sessionStorage` unavailable | exception | the binding lives in memory; a reload is a new page life |
| A shop key read before the gate opened | `shopKey` throws | caught, nothing found |
| Interrupted copy of the legacy keys | some keys still legacy | the next start resumes; nothing overwritten, nothing lost |
| A delayed answer after a change of shop | the server's 409 on any request sent with the old header | rule 3; nothing of another shop reaches memory |
| Another shop signs in in a second tab | `storage` event, visibility, or the next request's 409 | rule 3: the signed-out screen; never that shop's content |
| The page comes back from the back-forward cache | `pageshow` `persisted` | reload; nothing shown before the session answer (rule 5) |
| The session answer is late or fails on return (offline) | pending or failed `GET /api/session` | rule 2: hidden, « Réessayer »; the hidden editor keeps its edits |
| A late `Set-Cookie` (sign-out or sign-in) after the lock was given up, or without Web Locks | 401, 409, or the next session answer | rule 3 or rule 6; never another shop's data |
| The identity lock's request hangs | 30 s limit | aborted, then `GET /api/session` |
| Sign-out with unsaved edits or an unresolved card | step 3 | the confirmation; never blocked by the autosave |
| The current thread's own save had failed | the snapshot uses the live thread | the card is in `kept`; nothing lost |
| The kept record cannot be written | `setItem` throws at step 4.1 | sign-out does not happen, the sentence says why; nothing changed |
| The chat is held by another tab | `navigator.locks.query()` | sign-out refused with its sentence |
| The kept record's restoration is interrupted | `kept` still present at the next start | resumed; nothing overwritten; `kept` removed only after every write |
| Sign-out offline | `DELETE` fails or times out | the sentence; signed in; nothing touched |
| An older open tab after the release | `bundle_outdated` | the existing sentence |

**Edge cases:** shop B signs in first on the admin's desktop where shop 1's legacy keys are: they still go to `affiche.shop1.`, never to B. Two shops alternate on one phone: each finds nothing of the other; the waiting card of A comes back only to A. The session expires on A's phone and B signs in on the form that appears: B's explicit sign-in binds the tab to B and reloads fresh; B sees nothing of A. A tab opened later on that device shows the device's current session, as a new tab always did.

**Security / data notes:** after « Se déconnecter » only a waiting paid card's record stays, under the shop's prefix. Cached images and history are disclosed above; device protection is out of the requirement's scope.

---

## Release gate (mandatory for Release 1; covers R-MULTI-SHOP-005)

**The rehearsal command** `python -m affiche.rehearse <database file>` (new module, T-MULTI-SHOP-001; no settings, no `.env`): copies the file with `sqlite3.Connection.backup` into a new temporary folder (the source is only read); records, before and after `migrate(make_engine(folder))`:
- the row count of every data table, `foreign_key_check`, and after it `integrity_check`;
- **preservation hashes over the original data columns:** SHA-256 over each data table's rows read in a stable order (`ORDER BY` its primary key columns from `PRAGMA table_info`, else `rowid`), each row serialised as canonical JSON (blobs as hex), through an explicit projection. For the tables 0013 rebuilds or widens, the projection is the columns they had at 0012: `shop_profile` (`id, revision, name, contact, logo_asset, updated_at`), `chat_reads` (its sixteen columns of 0012), `login_failures` (`id, ip, attempted_at`). Every other data table is hashed over all its columns. `alembic_version` is schema metadata, not a preserved table. Equal counts and ledger sums cannot see a changed document or plan payload; equal hashes can;
- **separate assertions for what 0013 changes on purpose:** the version is `0012` before and `0013` after; the added columns hold exactly their expected values (`shop_profile`: `identifier` `originalphone` for shop 1, `password_hash` NULL, `state` `active`, `created_at` not NULL; `login_failures.identifier` NULL on every row of before); `chat_reads` has `UNIQUE (shop_id, key)` and no service-wide key; the three new indexes exist; `meta` is unchanged (the fingerprint row is removed later, at the first start, D-001);
- the three ledger sums (`provider_calls`, `poster_calls`, `chat_reads` `cost_micros`), printed for the release record although the hashes already cover them;
- **its own environment:** `sqlite3.sqlite_version`, the Python version and `REVISION` (the image's revision, D-HOSTED-PILOT-005), so that the report is evidence of where it ran.
It prints both columns and `REHEARSAL OK` or `REHEARSAL FAILED: <what differs>`, exits 0 or 1, and deletes its copy. Every count, preservation hash and sum must be identical, and every assertion must hold.

**The contract for the later migrations of Release 1:** each migration file states its own projection and its expected additions as two constants (`PRESERVED`: the tables it rebuilds or widens, with their columns before it; `ADDED`: the checks of what it adds), 0013 first; the rehearsal loads the pending migrations' files by path (as tests/test_phone_session.py:7-10 loads a script), applies to each table the projection of the earliest pending migration that names it, and fails on a pending migration that states none.

**In the deploy** (T-MULTI-SHOP-005): the release step's shell text, today one f-string inside `deploy.py` (deploy.py:237-279), moves to `deploy/release.sh`, uploaded and run like `daily.sh` and `verify.sh`, with the revision, the archive name and the remote folder as arguments, so that it can be tested. After the image is built and its configuration checked (deploy.py:254), **before the old container is stopped** (deploy.py:258-259): when `/data/affiche.db` exists, `docker compose -f app.new/deploy/compose.yml run --rm --no-deps affiche-ia python -m affiche.rehearse /data/affiche.db`. It runs in the release image, whose SQLite is 3.40.1, while the tests ran on 3.53.1 (this machine) and 3.46.1 (the devil's advocate's system SQLite). Failure: "Rehearsal FAILED: nothing was changed, the service still runs", exit 1, before any `docker stop`, backup or `up`. The copy goes to the container's `/tmp` (tmpfs, inside its 1 GB; the pilot's database is a few MB).

**The gate's own test** (`backend/tests/test_release_script.py`, loading a file of `deploy/` as tests/test_phone_session.py:7-10 does): `deploy/release.sh` is run with `sh` in a temporary folder, with a fake `docker` first on `PATH` that records its arguments and answers each call. When the rehearsal call fails, the record holds no `stop`, no backup, no `up`, and the exit code is 1; when it passes, the order is rehearsal, stop, backup, up. Docker itself is not available to Claude on this machine, so the step is proven against the fake and, for the real image, only by the evidence the gate requires below.

**The user's steps:**
1. **Backup:** on mx1, `sudo sh /opt/affiche-ia/daily.sh`, then check that `/opt/affiche-ia/backups/last-backup.json` has today's time.
2. **Optional, the day before:** copy that backup's `db/affiche-<stamp>.db` to the development machine and run `uv run python -m affiche.rehearse <copy>` from `backend/` (development SQLite; it shows the counts early).
3. **Copy and run in the release image:** run `deploy.py` as usual. Its rehearsal step makes a fresh copy of the live database and runs migration 0013 on it in the release image, before anything is stopped.
4. **Evidence from the release image:** the report's environment lines must show SQLite 3.40.1 and the release's revision. A report without them, or from another SQLite, is not the gate: stop.
5. **Preservation checks:** every data table's count and preservation hash identical before and after; the version `0012` then `0013`; the added columns as expected (shop 1 `originalphone` `active`); `integrity_check` ok, `foreign_key_check` empty.
6. **Ledger sums:** the three sums identical before and after. Save the whole report as `docs/project/reviews/release-1-rehearsal-<date>.md`.
7. If the report says FAILED, the deploy has stopped before stopping anything (tested, above) and the old version still serves: nothing to undo.
8. After the release: the new container migrated and adopted the password (the deploy's own backup was taken just before, deploy.py:260-266). Sign in on the pilot's phone with `originalphone` and the current password; « Mes affiches » shows the same number of posters as before.
9. Remove `SHOP_PASSWORD_HASH` from `/opt/affiche-ia/secrets/app.env`, recreate, and replace the lost-phone procedure with `python -m affiche.shops set-password originalphone` (deploy/README.md:164-169).

A rehearsal on a copy of `data-probe` is the development check of T-MULTI-SHOP-001, not this gate.

---

## Tests

- **Migration (test_db.py):** `migrate` leaves `foreign_keys = 1` on the same pooled connection; a migration that breaks a reference raises and leaves the version as it was (`command.upgrade` patched as test_db.py:55 does, or a throwaway revision under `tmp_path`); a failure to turn the keys on again invalidates the connection (the pragma patched to fail); 0013 on a 0012 database filled with shop-1 rows in every child table and `looks`, a session, login failures, chat reads and the fingerprint row: identical counts per table, identical ledger sums, `foreign_key_check` empty, shop 1 `originalphone`/`active`/NULL hash, a shop 2 insertable, `keep_shop` refuses a delete, the CHECKs refuse a non-normalised identifier and a plaintext hash, a chat-read key reusable by another shop and not by the same one. **Faults injected** with an SQLAlchemy `before_cursor_execute` listener that raises on one statement: on `CREATE TABLE chat_reads_new` (between the two rebuilds) and on `CREATE INDEX chat_reads_created` (right after the read-ledger swap): each time the version stays 0012, `shop_profile` still has `CHECK (id = 1)` and `keep_shop`, `chat_reads` still has its service-wide key, and every content hash is the one before. `python -m affiche.rehearse` on the filled database: OK, with its environment lines, although `alembic_version` changed and three tables gained columns (the projections and the separate assertions); on copies damaged on purpose by a patched `migrate` (a row deleted; one `creation_versions.document_json` changed with counts and sums intact; one `login_failures.ip` changed; an added column with an unexpected value): FAILED, exit 1, naming the table; a pending migration without `PRESERVED`: FAILED.
- **Adoption (test_api.py):** each row of the adoption table: first start with the fingerprint equal (sessions kept), different (sessions ended), missing (sessions ended); the setting stale (warning, no effect); upgraded pilot without the setting (start refused, message); new installation without it (starts, nobody signs in).
- **Sign-in (test_api.py, test_shops.py):** the `login()` helper sends the identifier; `identifier_key` (case, spaces, punctuation, accents, a phone number, an empty result); unknown identifier and wrong password give equal answers and call verification exactly once each (patched, as test_api.py:195-211); the pair limit (5) and the address limit (20), another identifier from the same address, another address, an IPv6 /64; **ten concurrent wrong attempts** with a slow patched verification: at most one failure recorded past the pair limit, the rest 429 without verification; **the same with a deliberately blocked writer** (another connection holds `BEGIN IMMEDIATE` for 2 s, under the 5 s busy_timeout, as tests/tx_worker.py does): verifications counted while the writer is blocked, then failures recorded once it is released: still at most one past the limit; verification outside the write transaction (existing test, adapted); an adopted hash with other Argon2 parameters is upgraded at its first sign-in; a suspended shop: right password 403, wrong 401; hash changed during verification → refused; session of a suspended shop → unauthenticated, of the same shop enabled again → authenticated; `previous` deleted; `support_fr` present only when set; `POST /api/session` from bundle 2 → 409, `DELETE` from bundle 2 → 200; `X-Affiche-Shop` mismatch → 409 on a change and on `DELETE`, absent → passes.
- **Password route (test_shops.py):** too short; wrong current (recorded, limited); success keeps this session, ends the shop's others, leaves shop B's.
- **Operator (test_shops.py):** functions on a connection inside a caller's transaction (a rollback undoes them); `create` normalises and refuses a taken identifier in another spelling; `set-password` ends that shop's sessions only; `end-sessions --all`; `suspend` (state, queued jobs and their reserved calls at 0, a running job untouched, sessions kept) and `enable`; `main()` with `env_file=None`: refuses a database not at head, prints a password once, `suspend` without `--yes` changes nothing, exit codes 0, 1, 2.
- **Spend per shop (test_admission.py, with T-MULTI-SHOP-003):** `spent_micros` without a shop unchanged; with a shop, only its `poster_calls` (through `poster_jobs.shop_id`) and `chat_reads`, never `provider_calls`; with `since`, a day's sum.
- **Limits and suspension (test_poster_jobs.py, test_reads.py):** `provider_guard` order; the day's ceiling for jobs and reads; reads: suspended, cap, ceiling, then `read_limit`, then `reads_busy` at two running; fair claim (A queues three, B one, B's is claimed second; the audit's FIFO test inverted, test_tenancy_audit.py:329-339); a 429 retry refused by `shop_daily_limit` or `shop_suspended` fails the job at cost 0; `dispatch` of a suspended shop's reserved call: job cancelled, call at 0, nothing sent (a stub provider that fails the test if called); `recover` cancels a suspended shop's unsent call and requeues an active shop's; **a read whose shop is suspended between `_admit` and `_send`** (the suspension committed from the test between the two, the transport a mock that fails the test if called): 403 `shop_suspended`, the row `failed` at cost 0, `spent_micros` unchanged, nothing sent; a read past `_send` when the suspension commits finishes and records its cost; the daily ceiling counts a reservation on its admission day (one admitted at 23:59 UTC and finished after midnight stays in the first day's sum); every new code has its sentence (existing test).
- **Isolation:** test_two_shops.py and the `/api/status` spoofing matrix (D-004).
- **Vitest:** api.test.ts: `BUNDLE` 3; `X-Affiche-Shop` sent once `bound` is a shop; `shopKey` throws before; **the gate as a pure function** of (binding, last answer, answer pending, answer failed) giving shown, hidden or signed-out, with a tab without binding, a page bound to nobody after sign-out, an answer naming another shop, a 401 and a 409; the binding read from and written to `sessionStorage`, and held in memory when it throws; the legacy move (moves, never overwrites, keeps a key whose copy failed, leaves `affiche.theme` and `affiche.start`); **a source check** that no file of `src/` but api.ts contains `'affiche.chat.`, `'affiche.words.`, `'affiche.palette.` or `'affiche.style`; chat.test.ts: keys per shop (chat.test.ts:29-32 today); `unresolved` (a followed card and a card with a kept request are unresolved; a `done` card with its request still attached is not; an unspent card is not); the eviction keeps a thread with an unresolved card past the 30 newest; the sign-out plan as a pure function (unsaved edits, unresolved cards, the kept record, the keys to delete) **built from the live thread, the stored threads and a kept record not restored yet, merged by card id, the live copy winning**, including a live unresolved card whose stored thread is stale or absent; a `setItem` that throws on the kept record leaves every key in place and the session untouched; the restoration of `kept` (adds each missing card by id to its thread, made when absent; never overwrites or doubles a card; removes `kept` last); sign-in and sign-out call `navigator.locks.request('affiche-identity', …)` and release only after the body and `GET /api/session` have answered, and run without it when `navigator.locks` is absent.
- **Browser smoke (stub, zero spend), `walk_two_shops` in browser_smoke.py: the cases of the identity gate.** A second shop made with `shops.create_shop` on the smoke's data folder; at 360 px, both themes; in each case the test asserts that the document holds no element of a shop other than the one the page is bound to, and none at all while the gate is not open. Basics: wrong identifier and wrong password show the same sentence; the support line shows; A signs in with « Original Phone » (spaced), makes a poster, types an unsent chat message, signs out: the sign-in form shows nothing of A and A's keys are gone.
  1. **An abandoned or timed-out sign-in for A, then B signs in, then A's answer arrives:** tab 1's sign-in for A is held past the 30 s limit (and, in a second run, tab 1 is closed); B signs in in tab 2 and sees B; A's cookie change is then delivered: tab 2 reaches the signed-out screen with « Une autre boutique est connectée… » at its next request or session check, and never shows A.
  2. **A, navigate away, B signs in elsewhere, Back:** tab 1 bound to A goes to another page; B signs in in tab 2; Back in tab 1 (a back-forward cache restore reloads at once): with the session answer delayed, the document holds nothing of A or B while it waits, then the signed-out screen (the tab is bound to A, the answer names B); with the answer failing, shop content stays hidden with « Réessayer ».
  3. **Offline restoration:** A edits with an unsaved change, the network is cut, the page is hidden then shown: shop content hidden, « Réessayer »; network back, « Réessayer »: A's editor comes back with its unsaved change, which then saves.
  4. **Two tabs:** A in tab 1, B signs in in tab 2: tab 1 reaches the signed-out screen (`storage` event), never B's content; a request held from tab 1 across the switch is refused (409) and changes nothing; A's explicit sign-in in tab 1 loads A fresh, and tab 2 in turn reaches the signed-out screen.
  5. **Expiry, then another shop:** A's session row deleted while its editor shows a poster and follows a job; the next poll gives the signed-out screen; B signs in there: the page binds to B and reloads fresh, B sees no poster of A, and the autosave sends nothing to A's poster.
  6. **Suspension:** A suspended with `shops.suspend` while its page is open: the next action gives the signed-out screen, signing in shows the suspension sentence; `enable`, reload: A again (same binding, same session).
  7. **Sign-out with an unresolved card:** a recap card's request held by a routed failure; the confirmation, « Se déconnecter quand même »; only that card's thread comes back at A's next sign-in, with « Reprendre ». The same **with the current thread's own save failed** (`setItem` made to throw for that thread's key only): the kept record comes from the live thread and the card still comes back. With the kept write failing too: sign-out refused with its sentence, still signed in.
  8. **Sign-out with a conflicting autosave** offers to discard; **with the chat held by another tab** it is refused with its sentence.
  Contrast checked with the existing helper. The existing smokes and chat smoke sign in with `originalphone` (browser_smoke.py:808, :1269, :2233; chat_browser.py:33, :1011; editor_refinements_browser.py:47).
- **Browser smoke, cookies:** with the lock, tab 1's held sign-out keeps tab 2's sign-in from being sent until it completes; without the lock (`navigator.locks` removed by an init script), case 1 above and a late sign-out answer after B's sign-in (the next screen is the signed-out one). **What these tests prove:** the application's reaction to any change of the cookie at any moment (the gate's outcome is only ever the bound shop, hidden, or the signed-out screen), and that the lock serialises sign-in and sign-out across two tabs of desktop Chromium. **What they do not prove:** whether a real browser applies or drops the `Set-Cookie` of an aborted or late request, and in which order; the lock's behaviour in mobile browsers. **Checked first in T-MULTI-SHOP-006:** whether Playwright's `route.fetch()` already applies the response's cookies to the context before `route.fulfill` (if it does, a held `route.fetch()` cannot hold a cookie, and the test changes the cookie itself with `context.add_cookies` or `context.clear_cookies` at the moment of delivery, or delays the request with `route.continue_()`); the result is written in the task's notes.
- **Release script (test_release_script.py):** a failed rehearsal never reaches `stop`, the backup or `up`; a passing one runs them in order (Release gate).
- **Not proven here:** the deploy's rehearsal step against real Docker and the migration under SQLite 3.40.1 (the gate's evidence lines prove them at the release); the pilot's real database (the release gate); a real phone.

## Tasks

Six tasks, each one session, each leaving the whole suite runnable at its end. From `backend/` unless said; frontend commands on Linux are `corepack npm@10 …` (AGENTS.md).

1. **T-MULTI-SHOP-001 — Schema, per-shop read keys, the password in the database, the rehearsal command.** `migrate` with keys off, checked and restored; 0013; the reads lookup by shop and key; `adopt_password_setting` with the fingerprint and the two start cases; `validate_config` without the requirement; `auth.login` verifies shop 1's stored hash (still a password-only body, so the frontend and the smokes are untouched); `shops.set_password` and `end_sessions` (connection functions); `phone_session.py`; `affiche.rehearse` with its preservation projections, the separate assertions, 0013's `PRESERVED` and `ADDED`, and its environment lines; the migration's fault-injection tests. Verify: `uv run pytest tests/test_db.py tests/test_api.py tests/test_reads.py -q` → all passed; `uv run python -m affiche.rehearse data-probe/affiche.db` → `REHEARSAL OK`, identical counts and hashes, sums 512,881 / 7,269,000 / 513,948 µ$ on both sides (as measured 2026-11-15, if `data-probe` has not changed).
2. **T-MULTI-SHOP-002 — Sign-in by identifier, end to end.** `identifier_key`; `Login` body; `auth.login` with both limits counted again in the slot, the slot held until the write has committed, the dummy hash and `verify_and_update` (with the concurrent and blocked-writer tests); `wrong_credentials`; `shop_suspended` at sign-in; the session read joined to `active`; `shop_id` and `support_fr` in the session answers; `SUPPORT_CONTACT_FR`; `POST /api/session` under the bundle rule; `BUNDLE` 3 both sides; `shops.create_shop`; the form's identifier field and support line; the harnesses' sign-in; verify.sh's signed-out check. Verify: `uv run pytest tests/test_api.py tests/test_shops.py -q`; `cd ../frontend && corepack npm@10 test`; `uv run python ../frontend/tests/browser_smoke.py` and `uv run python ../frontend/tests/chat_browser.py` → pass.
3. **T-MULTI-SHOP-003 — Isolation under test.** test_two_shops.py over the routes that exist then; `spent_micros(conn, settings, *, shop=None, since=None)` and its tests; `/api/usage` per shop through it; `/api/status` through `operator(request)` and its spoofing matrix; the `X-Affiche-Shop` guard on the server, `DELETE` included (the frontend does not send it yet: an absent header passes). Verify: `uv run pytest tests/test_two_shops.py tests/test_admission.py tests/test_api.py -q` → pass; the mutation script in the scratchpad → test_two_shops fails; `uv run pytest -q` → all passed.
4. **T-MULTI-SHOP-004 — Shared provider limits, and the password route.** `provider_guard` (on T-003's `spent_micros`), `SHOP_DAILY_SPEND_USD` as an admission-day budget, the reads' order and `reads_busy`, fair `claim`, `SPEND_REFUSALS`, the sentences, ChatView's text-back for the two codes; `POST /api/session/password` with its tests, added to `EXEMPT` of test_two_shops. Verify: `uv run pytest tests/test_poster_jobs.py tests/test_reads.py tests/test_config.py tests/test_api.py tests/test_shops.py tests/test_two_shops.py -q` → pass; `cd ../frontend && corepack npm@10 test` → pass.
5. **T-MULTI-SHOP-005 — Suspension, the operator command, the runbooks and the deploy gate.** `jobs.cancel_queued`; the cutoff in `dispatch` and `run_job`; `reads._send` between `_admit` and `_ask`; `recover` respecting suspension; `shops.suspend`, `enable`, `find_shop`, `list_shops`, `main` (head check, `--yes`); the release step moved to `deploy/release.sh` with its rehearsal, and test_release_script.py; deploy/README.md (operator commands, `/api/status` from the container, the release gate's steps, a restore rolls back every shop and is followed by `end-sessions --all` and the resets made since, the lost-phone line), backend/api/README.md:20, .env.example:39-40 (and the two new settings), AGENTS.md's API command. Verify: `uv run pytest tests/test_shops.py tests/test_poster_jobs.py tests/test_reads.py tests/test_two_shops.py tests/test_release_script.py -q` → pass; `python3 -m py_compile ../deploy/deploy.py` and `sh -n ../deploy/*.sh` → no output; `uv run pytest -q` → all passed.
6. **T-MULTI-SHOP-006 — The browser: the identity gate, sign-out, storage per shop; two shops in the browser.** The gate (the binding in `sessionStorage`, shop content `hidden` until the session answer names the bound shop, the signed-out screen on any other identity, the reload after an explicit sign-in, `pagehide`/`pageshow`/visibility/`storage` re-asks); the `affiche-identity` lock around sign-in and sign-out and the `GET /api/session` after each; `unresolved` moved to chat.ts and its eviction exemption; the sign-out button, its confirmation, the snapshot from the live thread plus the stored threads, the kept record written before the server is asked, restored at the next start; `shopKey`, the legacy move, `X-Affiche-Shop` sent; the style read after the session; the Vitest cases; `walk_two_shops` with the gate's cases and the cookie cases. Verify: `cd ../frontend && corepack npm@10 test && corepack npm@10 run build` → pass; `uv run python ../frontend/tests/browser_smoke.py` (with the two-shop walk) and `uv run python ../frontend/tests/chat_browser.py` → pass; `uv run pytest -q` → all passed.

**What the code reviews check** (there is no further design round; round 3's four points are checked here):
- **T-MULTI-SHOP-001:** the rehearsal's projections and separate assertions (round 3 P2-4): `shop_profile`, `chat_reads` and `login_failures` over their 0012 columns, the version and the added columns asserted apart, 0013's `PRESERVED`/`ADDED`, a pending migration without them refused.
- **T-MULTI-SHOP-005:** the extracted `deploy/release.sh`: the script run on the box is the committed one that `deploy.py` stages (`deploy/` is already in `GUARD_PATHS`, deploy.py:53, so an uncommitted change stops the deploy at deploy.py:114, and the file is uploaded from the commit through `committed()`, deploy.py:76, like `daily.sh` and `verify.sh`); every variable quoted; the existing release lock kept (`LOCK`, `flock -w 600 9` on `/opt/affiche-ia/.lock`, deploy.py:55, shared with `daily.sh`); the order fails closed (no `docker stop`, backup or `up` after a failed rehearsal or check, proven by test_release_script.py); and the user's command stays the pyinfra one (`pyinfra 89.167.56.26 deploy.py --user deploy -y`, deploy/README.md), with nothing new to type.
- **T-MULTI-SHOP-006:** that the browser follows the one gate and has no other path to showing a shop (round 3 P1-1, P1-2); the sign-out snapshot from the live thread (P2-3); and which cookie claims its tests prove and which they do not (Tests, "Browser smoke, cookies"), with the result of the `route.fetch()` check written down.

**The most hidden risk is T-MULTI-SHOP-006** (devil's advocate's reading, kept): about fifteen storage sites in App.vue, ChatView.vue, chat.ts and words.ts change, the style read moves, the legacy keys move, the identity gate replaces every path to showing a shop, and sign-in and sign-out move under a cross-tab lock with the kept record of an unresolved card. De-risked by: one rule (the gate) instead of a list of paths, and one mechanism (a reload) instead of resetting refs; `shopKey` throwing before the session, so a missed site finds nothing rather than another shop's data; the Vitest source check that no literal legacy key remains outside api.ts; the gate as a pure function under Vitest; the browser walk of the gate's eight cases; both smokes run before the task is called done. Second risk: T-MULTI-SHOP-002 (`BUNDLE` 3 and the new body change every harness; both smokes run). T-MULTI-SHOP-001 carries the data risk, rehearsed on `data-probe` and gated at the release.

## Wording of the requirements this design asks for

Sentences of [requirements/multi-shop.md](../requirements/multi-shop.md) to change, with their new text:

**R-MULTI-SHOP-003**
- Replace « Each shop has its own daily limits (generations, messages read). The service keeps one ceiling above them all. » with « Each shop has its own daily ceiling of provider spend and its own daily limit of messages read. The service keeps one ceiling above them all. »
- Keep « Jobs are taken in turn between shops; a shop with many queued jobs does not delay another shop's first job behind all of them. »
- Delete « A shop cannot queue more than a set number of generations at once. » (no cap on queued generations; the fair queue serves every shop in turn).

**R-MULTI-SHOP-004**
- Replace « After « Se déconnecter », the next shop to sign in on that device sees none of it. » with « « Se déconnecter » deletes what the application kept on the device for this shop, and the next shop to sign in sees none of it. One exception: when an image the shop paid for still waits for its outcome, the owner is told and may sign out anyway; that card alone is kept, under the shop's own key, visible to no other shop, so that it can be resumed. Images the browser keeps in its own cache are not deleted; the conditions of use say so. »

**R-MULTI-SHOP-005**
- Replace « The change of the database is forward-only, is tried first on a copy of the pilot's database, and a backup is taken before it runs on the real one. » with « The change of the database is forward-only. The release is gated by a rehearsal on a fresh copy of the hosted pilot's database, run in the release image: every table keeps all its rows and the three ledgers keep their sums, or the release stops before anything changes. A backup is taken before the change runs on the real database. »

**R-MULTI-SHOP-006**
- Replace « A suspended shop cannot sign in; its open sessions end; its queued generations are cancelled and their credits released. » with « A suspended shop cannot sign in, and its sessions stop working at once; they work again when the shop is enabled. Its queued generations are cancelled and no further provider call is sent for it; a call already sent finishes and its result is kept. Credits are released by the prepaid-balance feature. »

**R-MULTI-SHOP-001** (follows ruling 10; apply with the others)
- Replace « The sign-in form asks for an identifier and a password. **Default:** the identifier is chosen by the operator when he creates the shop (letters and digits, not case-sensitive); the alternative is the shop's phone number. » with « The sign-in form asks for an identifier and a password, and says whom to contact when the password is forgotten. The identifier is one the operator chooses when he creates the shop, which may be a phone number in one written form; case, accents, spaces and punctuation are ignored. »

## Not built, on purpose

A credential-version column (session rows are deleted by shop; the race is closed by re-reading the hash); a separate shops or credentials table; a cap on queued generations; dollar fields in `/api/usage`; the password change screen (R-SHOP-DASH-003); renaming identifiers (a forward migration if ever needed); a per-identifier limit from all addresses; remembering the identifier on the device; `Clear-Site-Data` on sign-out; an operator account and a record of operator actions (administration dashboard); per-shop settings for limits (R-ADMIN-006); password rules beyond length; any other sign-in method, public sign-up, the balance, the dashboards, payments.

## Traceability

| Requirement | Design |
|---|---|
| R-MULTI-SHOP-001 | D-002 (routes, identifier, limits, sessions, support line), D-003 (operator reset), D-007 (form, sign-out); the password screen is R-SHOP-DASH-003 |
| R-MULTI-SHOP-002 | D-004 (usage, status, two-shop test), D-001 (read keys per shop), D-002 (`X-Affiche-Shop`) |
| R-MULTI-SHOP-003 | D-005 |
| R-MULTI-SHOP-004 | D-007 (identity rule, sign-out, storage per shop, legacy keys) |
| R-MULTI-SHOP-005 | D-001, Release gate |
| R-MULTI-SHOP-006 | D-006, D-002 (sign-in and session read), D-003 (command) |
