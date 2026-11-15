# Devil's advocate: multi-shop design, draft v1 (2026-11-15)

**Scope:** [designs/multi-shop.md](../designs/multi-shop.md) draft v1, its agreed choices included. I read the code it cites, and I ran throwaway scripts on scratch copies only. I did not change any file in the repository except this report. I made no paid call, used no network, started no server and did not read `backend/.env`.

**Result:** the migration holds. I could not break it. The design's largest cost is in four mechanisms built for a state that is never deployed. One defect class is missing: a different shop signs in on a page whose session ended, and sees the previous shop's poster.

## Points that would change a decision

### 1. Four mechanisms serve a state that is never deployed (High)

**What is wrong.** ADR-105 and ROADMAP.md:7 say that nothing is deployed until all of Release 1 is complete. The prepaid balance, both dashboards and the shop's Account screen ship together with multi-shop. Four parts of the design exist only "until the next feature":

| Part of the design | What replaces it in the same release | Evidence |
|---|---|---|
| Per-shop daily spend ceiling: `SHOP_DAILY_SPEND_USD`, check 3 of `admit_spend`, `shop_daily_limit` and its sentence, the worker's `SPEND_REFUSALS`, the chat's text-back (D-005) | The balance, which bounds a shop by its credits (prepaid-balance.md:21, :48), and the per-shop read limit (reads.py:33; R-BALANCE-007, prepaid-balance.md:59) | design lines 308-356 |
| `/api/status` answered only for loopback client plus loopback `Host` (`operator(request)`, the `TestClient(client=…)` test) | The administration dashboard's own sign-in (admin-dashboard.md:49) | design line 277 |
| `/api/usage` gains `today_micros` and `daily_cap_micros` in dollars | Credits; R-BALANCE-001 shows no dollars to a shop | design lines 270-275. No frontend code reads `/api/usage` or `/api/status`: only the smokes and test_api.py do (grep of `frontend/src`) |
| The header `<details>` menu with the password dialog | The shop's Account screen: "Change the password; « Se déconnecter »" (shop-dashboard.md:33). The design itself says the dashboard "may move it" (line 396) | design lines 395-397 |

**Smaller alternative.**
- `admit_spend` keeps two checks: suspended, then the service cap. The balance design adds its own check after them.
- Do not build the dollar ceiling. In the requirement, "generations" in R-003's daily limits is met by the balance, and "messages read" by the existing count.
- `/api/status`: refuse it to every shop now (404), or delete the route. The dashboard adds its own route. There is nothing to read from a browser before the release in any case.
- `/api/usage`: keep `recorded_micros` per shop (what the smokes read) and remove `cap_micros`. Nothing more.
- Frontend: a plain « Se déconnecter » button (R-001 and the two-shop walk need it). Build `POST /api/session/password` and its tests now. Build its dialog once, in the Account screen.

**What the balance design must take over.** `PROVIDER_KINDS` is `scene, refine, text_texture, background, plan, text_patch` (jobs.py:18-19). R-BALANCE-001 charges a credit only for "a first poster, a whole new image, or an adjustment". Textures (USD 0.30 estimate), plans, looks and text patches are paid calls that are not charged. The balance design must give each paid kind a credit or a daily count per shop. Without that, a shop at zero credits can still spend. That is where a per-shop money bound belongs, if one is needed.

**The smallest thing that stops one shop from emptying the service's cap,** today and at the release: the service cap (exists), the per-shop read count (exists), one image job per poster (`poster_one_image`, 0006), and the balance. In the period between this feature and the balance, nothing is deployed, so nothing is needed.

`queue_full` (4) protects nobody that the fair queue does not already protect: other shops' first jobs go first whatever the length of one shop's queue. Also, the design says that "4 means four posters at once". That is not exact, because plan, look and text_patch jobs count too (they are in `PROVIDER_KINDS`). Keep it only if the user wants R-003's last criterion as written.

### 2. A different shop signs in on a page whose session ended and sees the previous shop's poster (High)

**What is wrong.** The design clears memory on « Se déconnecter » (`location.replace`, D-007). There is a second way to reach the sign-in form, and the design does not clear memory on it:
- A 401 while a job is followed (App.vue:1250), and the chat's `signedOut` (App.vue:1459), only set `authenticated = false`. The poster, the document, the history and the style that was read at setup stay in memory.
- `signIn()` (App.vue:854-857) then calls `loadShop()` and `route()`. `route()` returns without fetching when `creation.value?.id === id` (App.vue:597). The hash still names the previous shop's poster, so the editor shows that poster under the new shop's session. Then the autosave sends it to the previous shop's id (404).
- This is the case that R-004 exists for: the operator suspends shop A, or A changes its password on another device. A's phone shows the sign-in form, and somebody signs in as B. The `X-Affiche-Shop` header does not catch it, because `useShop(B)` runs at sign-in.

**Smaller alternative.** In `signIn()`: if a shop was already loaded and the answer's `shop_id` is different, call `location.reload()`. This is one line. Add it to the browser walk: suspend A while its page follows a job, sign in as B on the form that appears, and B sees nothing of A.

### 3. Normalise the identifier by removing spaces and punctuation (Medium)

**What is wrong.** D-002 normalises with `strip().lower()` only. Anything else is "an unknown identifier", and it counts as a failure (design line 151). The pilot shop is called « Original Phone Mada ». The owner will type « Original Phone » with a space. This is refused, and it counts toward his limit of 5.

**The phone number.** It is not better as the only identity. The pilot's profile in `data-probe` lists two numbers. An owner who types his other number gets « Identifiant ou mot de passe incorrect » and spends his five attempts. An operator-chosen identifier, when forgotten, costs one call to the operator, who runs `list`. A password forgotten at night costs the same with either choice.

**Smaller alternative.** Normalise with NFKD, lower case, then remove every character that is not a-z or 0-9, at creation and at sign-in. Then `Original Phone`, `original-phone` and `ORIGINALPHONE` all open the same shop. The operator can also choose a shop's phone number as its identifier when the shop prefers it (`034 12 345 67` becomes `0341234567`), with no code change. The decision "identifier or phone number" then disappears.

### 4. The sign-in form does not say how to get help (Medium)

**What is wrong.** Password recovery is "the operator resets it" (R-001, out of scope). The only place that says how to reach the operator is the Account screen (shop-dashboard.md:34), and a shop that is signed out cannot open it. The 429 refusal locks for 15 minutes and does not say whom to call.

**Smaller alternative.** Add one line under the sign-in form and in the `rate_limited` sentence: « Mot de passe oublié : contactez … ». The text is a setting that the operator writes (a new setting, or the buying text of R-ADMIN-006 when that exists).

### 5. The seam for the dashboard: functions take a connection, and the command does not migrate (Medium)

**What is wrong.**
- The `affiche.shops` functions take an `engine` and open their own transaction (design lines 231-237).
- The dashboard must record every change "with its time and what changed" (admin-dashboard.md:21). It must also create a shop with welcome credits (admin-dashboard.md:28, prepaid-balance.md:53).
- With an engine, the audit row and the welcome grant cannot be in the same transaction as the change. The dashboard will have to rewrite these functions.
- The command also "runs `migrate`" (line 229). If it is run from a newer image against the live volume, it migrates under the running API. The `deploy.py` release uses `docker compose run` with the new image before the new container starts, so this pattern is close at hand.

**Smaller alternative.**
- Use `create_shop(conn, identifier, name, password_hash) -> id`, `set_password(conn, shop_id, hash)`, `suspend(conn, shop_id)` and so on. The caller hashes the password outside the transaction. The command line wraps each call in `write_tx`, and the dashboard later wraps the same call with its audit row.
- The command checks that the schema is at head and refuses otherwise ("start the API first"). It never migrates.

### 6. Suspension: do not delete the sessions (Medium)

**What is wrong.** `suspend` deletes the shop's sessions (D-006). The session read already requires `state='active'` (D-002, design line 180), so the deletion adds nothing to the suspension. It only makes a mistake permanent. An operator who suspends the wrong shop and enables it again signs that owner out of every device. If the owner does not remember his password, the operator must set a new one.

**Smaller alternative.** `suspend` changes `state` and cancels the queued jobs. `enable` then reverses everything except the cancelled jobs. When the reason is a leaked password, the operator also runs `set-password`, which deletes the sessions. R-006 "its open sessions end" is still met: they stop working at once. Also print the shop's name and require `--yes` before `suspend` acts.

### 7. Storage at sign-out: both privacy and no double payment are possible (Low to Medium)

**What is wrong.** The design keeps the shop's keys at sign-out, and asks to reword the R-004 story. Its reason is that deleting them "can make a waiting paid card be paid twice". The risk is smaller than that:
- While the first image job runs, the server refuses a second one on the same poster (`poster_one_image`, 0006:22).
- When the first job has finished, its version is on the poster.
- When the request never arrived, nothing was paid.

The only real case is a card that keeps a request with no job (`nextStep(item) === 'replay'`, chat.ts:135).

**Smaller alternative.** Keep the per-shop prefixes, because they handle two tabs well. At sign-out, delete the shop's prefix. Refuse sign-out while a kept card has `nextStep === 'replay'`, with a sentence like the one for unsaved edits. R-004 then stays as written.

### 8. A restore now rolls back every shop (Low)

The restore runbook (deploy/README.md:186-208) assumes one shop. It also tells the operator to compare `/api/status`. With several shops, restoring for one shop's problem loses every other shop's work, and later every credit grant made since the backup. T-007 should rewrite that section: never restore for one shop; tell all shops; enter again the grants made since the backup. It should also stop pointing to `/api/status` if point 1 is taken.

## Tried to break, and could not

**The migration (D-001).** Script: `scratchpad/da-multishop/rehearse.py`. It runs the design's 0013 through Alembic with the design's `migrate()`.

| Run | Result |
|---|---|
| Fresh 0012 database made by the real migrations | 0013 applied. `integrity_check` ok. `foreign_key_check` empty. Keys back to 1 on the pooled connection. Shop 2 can be inserted. Shop 9 is refused (FK). Upper case, a duplicate identifier and a plaintext hash are refused. `keep_shop` holds |
| Consistent copy of `data-probe` (2.5 MB, through the backup API) | No foreign-key violation existed before. The three ledger sums are identical (7,269,000 / 513,948 / 512,881 µ$). Only `meta` changed: the fingerprint row was removed. Shop 1 is `originalphone`, `active` |
| Empty database to 0013, with keys off for every migration | ok |
| `kill -9` after `DROP TABLE shop_profile`, before COMMIT | On reopen: version 0012, `integrity_check` ok, the old table with `CHECK (id = 1)` and `keep_shop` are present, no `shop_profile_new` |
| Same SQL on the system SQLite 3.46.1 (the main runs use 3.53.1) | ok |
| Cost | `foreign_key_check` takes 0.8 ms on the probe copy. A `migrate` at head takes 2 ms |

**No rebuild.** A separate `shops` table cannot work. Every child table references `shop_profile(id)`, and `CHECK (id = 1)` refuses row 2. The only route without a rebuild is SQLite's documented `writable_schema` edit for removing a CHECK, followed by `ADD COLUMN`s. I ran it too: it passes the same checks, and `migrate()` stays unchanged with keys on. It is not safer: it rewrites schema text with a string replacement. Keep the design's rebuild.

**Not tested:** Debian bookworm's SQLite 3.40.1 (the release image), and the real database on mx1. The rehearsal of the release step in T-007 is still needed.

**Moving the password into the database (D-001).** The alternative is to have no adoption: the operator runs `set-password originalphone` at the release and tells the owner the identifier and a new password. It removes the "present but ignored" setting, and the lost-phone procedure that would then do nothing in silence. But it sends a password over a messaging channel and signs the phone out. I found no option that is clearly safer. Keep the adoption. Make "remove `SHOP_PASSWORD_HASH`" and the new lost-phone line steps of the release checklist, not only documentation.

**`/api/status` as a boundary.** With today's configuration I found no path to it from outside:
- In production, Caddy rewrites `X-Forwarded-For`, uvicorn takes the right-most untrusted address, and Caddy routes by `Host`.
- Through `phone_session.py`, Vite keeps the tunnel's `Host` (`changeOrigin: false`).

The boundary depends on two configurations that this route does not own (Maizina's Caddy, and Vite's proxy option). Because the route is never deployed in this form, point 1 removes the question.

**Others.**
- Sign-in enumeration and timing (dummy hash, one answer): no gap found.
- Two people of one shop on two phones: sessions are per device, and one image job per poster is enforced on the server. Nothing new.
- The pilot's open tab: an old bundle gets `bundle_outdated`, and the frontend shows the server's `message_fr` (api.ts:44).

## The seven tasks

- **Cut:** the dollar ceiling, `today_micros` and `daily_cap_micros`, `operator(request)`, and the password dialog (point 1).
- **Merge:** T-004 and T-005. What is left of T-004 is `admit_spend` (suspended, then cap), the fair `claim` and `shop_suspended` in the worker's refusals. Suspension needs exactly that.
- **Result:** six tasks, with T-006 smaller.
- **Most hidden risk:** T-006, not T-001. T-001 is the data risk, but it is now rehearsed. T-006 changes about fifteen storage sites in App.vue, ChatView.vue, chat.ts and words.ts. It also moves the style read after the session and moves the legacy keys, and it misses the stale-memory path of point 2.
- **Second risk:** T-002. `BUNDLE` 3 and the new sign-in body change every harness: browser_smoke.py:808, :1269, :2233; chat_browser.py:33, :1011; editor_refinements_browser.py:47. Lesson of the day: run both smokes before calling it done.
