# REQUIREMENTS — Administration dashboard

**Status:** Draft v4, 2026-11-17 (Claude), with working defaults marked **Default**. v1 (2026-11-15) was written before the multi-shop feature and the prepaid balance were built; v2 stated what they built; v3 followed design v2 (review round 1 and the lead's decisions); v4 narrows three promises after review round 2 (design v3). The tables at the end list the changes. Part of Release 1 « Invitation » ([roadmap](../ROADMAP.md), ADR-105; the user asked for it as a condition of the next deploy). Depends on [multi-shop](multi-shop.md) and [prepaid-balance](prepaid-balance.md), both built. Design: [designs/admin-dashboard.md](../designs/admin-dashboard.md) v3.

**What exists (2026-11-17):** the operator's command `python -m affiche.shops` (list, create with welcome credits, set-password, end-sessions, suspend, enable, grant, move-payment, correct, pause, resume, purchase-text, after-restore), run over SSH on the box. `GET /api/status`, answered only to a caller on the API's own machine. `GET /api/balance`, a shop's own credits (`/api/usage` is removed). Credit lines (`credit_grants`) are never changed or removed and carry their time, actor, reference and note. No operator account, no operator screen.

## Index

| ID | Title | Priority | Status |
|---|---|---|---|
| R-ADMIN-001 | The operator's own access | P0 | Draft v4 |
| R-ADMIN-002 | Shops | P0 | Draft v4 |
| R-ADMIN-003 | Credits and payments received | P0 | Draft v4 |
| R-ADMIN-004 | Usage and costs | P1 | Draft v4 |
| R-ADMIN-005 | Health and the stop switches | P1 | Draft v4 |
| R-ADMIN-006 | The few settings | P2 | Draft v4 |

## R-ADMIN-001 — The operator's own access
- **Story:** As the operator, I reach the administration with my own sign-in, and no shop can.
- [ ] The dashboard has its own sign-in and its own session, apart from every shop's. Three session operations are public: reading whether the browser is signed in, signing in, signing out. Every other dashboard route refuses a shop's session and a browser with no session. An operator's session is refused on every protected shop route; the shops' own session operations (reading the session, signing in, signing out) stay public and answer as they do without it.
- [ ] Wrong passwords are limited as a shop's sign-in is. A session ends at sign-out, at its expiry, when the operator's password is set again, and when the operator ends every operator session: from the dashboard (a confirmed control that includes this device) or from the command line.
- [ ] The operator's password is set only by the command line (`python -m affiche.shops operator-password`), which prints a new one once and ends every operator session. No dashboard route can set it. **Default:** until it is set, the dashboard's sign-in is refused with a sentence that names the command.
- [ ] The ledger records every money action with its actor: `operator` for the command line, `dashboard:<8 hex>` for a dashboard session. Every other dashboard action is logged, best effort: one line with its action, shop and actor, written after the action is saved and kept by the journal. A process stopped between the two leaves the action without its line. No log line holds a password, a hash, a token or a payment reference.
- [ ] The dashboard lists the live operator sessions (start, expiry, address, browser).
- [ ] The command line keeps working for every action, also when nobody can sign in to the dashboard.
- [ ] `GET /api/status` stays as it is, answered on the API's own machine only.
- [ ] **Default:** one operator. **Default:** a session lasts 12 hours from sign-in.
- **Out of scope:** several operators with roles; two-factor sign-in (wanted before Phase 2); a queryable history of non-money actions (owner decision 1).

## R-ADMIN-002 — Shops
- **Story:** As the operator, I invite a shop in a minute and see all shops at a glance.
- [ ] A list of every shop: identifier, name, state (active, suspended), whether it has a password, credits available and « en attente », number of posters, date of the last poster.
- [ ] Create a shop: identifier, name, welcome credits (**Default:** 5, typed at each creation). Its first password is shown once. The shop can sign in at once.
- [ ] Set a new password for a shop (shown once; that shop's sessions end); end its sessions; suspend it; enable it again. Each is confirmed first.
- [ ] Open one shop: its credit history newest first (grants and corrections; each generation that took a credit, with its outcome, its poster and its job id), and its limits for today (provider spend against the daily ceiling, messages read against the daily limit).
- **Out of scope:** signing in as a shop; deleting a shop; seeing a shop's images (**Default:** the operator sees counts and outcomes, not pictures).

## R-ADMIN-003 — Credits and payments received
- **Story:** As the operator, when a shop pays me by mobile money I credit it and keep the trace.
- [ ] Grant credits to a shop: how many, offered or bought; for bought, the amount received in whole ariary and the method; a reference; a note. The answer shows the line written, the shop's balance after it, and the cap's headroom with its warning.
- [ ] Remove or correct credits only by a new line with a reason; a line is never edited or removed; a correction never takes a balance below zero. A generation is repaid (+1 credit) from its job in the shop's history, once.
- [ ] A payment credited to the wrong shop is moved whole while its credits are unspent. When some are spent the move is refused, and an offered grant is the way to serve the right shop.
- [ ] A grant, correction or move is one request from the moment it is confirmed: the same shop, values and reference through sending, a lost answer or a server error, a new sign-in, a reload of the page and a resend. While a shop has a request with no definite answer, no new grant, correction or move for that shop starts in that browser until the request is sent again or discarded (discarding warns). Sent again, it is written once: the answer says « already recorded as line N » and whether that line matches what was sent; for a move, which shop the payment went to. When it does not match, the way out is a correction or a move, never another reference.
- [ ] The limit, stated: one reference is written once (case and spacing ignored). The same payment typed under two references (`MV-123`, `MV123`), or a gift discarded and made again under a new reference, is two lines; the operator's payment records catch those.
- [ ] Granting credits is usable at 360 px on a phone with the keyboard open, with the longest values the fields accept (added 2026-11-16 from the prepaid-balance design: a shop out of credits on a Sunday must not wait for the operator's laptop).
- [ ] A list of payments received in a period, with their total in ariary. A moved payment counts once.
- **Out of scope:** payment providers, receipts sent to the shop, refunds in money, prices and packs in the application, cancelling a payment that never arrived (owner decision 5).

## R-ADMIN-004 — Usage and costs
- **Story:** As the operator, I know what each shop costs me and whether a price holds.
- [ ] For a period of whole UTC days (**Default:** the current month), for each shop and for the service: images made (first scenes, adjustments, text materials, counted by kind, also those made before credits existed), credits given back, messages read, what the providers charged (as recorded, with the part that is an estimate said), credits granted, ariary received, posters confirmed. The evaluation command's spend counts for the service, on its own line.
- [ ] The figures a price depends on: provider cost per image, images per confirmed poster, adjustments per poster. « — » when the period has nothing to divide by.
- [ ] Every figure is computed from the ledgers; an empty period shows zero, never an example.
- **Out of scope:** charts; accounting; taxes.

## R-ADMIN-005 — Health and the stop switches
- **Story:** As the operator, I see when something is stuck and can stop spending at once.
- [ ] For the operator only: version, schema version, start time, age of the last backup, spend against the cap and the cap's headroom.
- [ ] The queue (images waiting and running), and the generations that failed, ended with an unknown outcome in the last seven days or have run for more than ten minutes, each with its shop, its poster, its job id and what its credit is doing.
- [ ] The service's pause and its end, each confirmed. The pause stops new requests to the AI for every shop (images, styles, text proposals, reading messages); requests already admitted finish; nothing is taken from a shop.
- [ ] One shop is stopped by suspending it (R-ADMIN-002). **Default:** suspension is the only stop for one shop; it also stops its sign-in and editing (prepaid-balance, owner decision 6).
- [ ] The shop is told by the sentences that exist: the pause sentence at its next request, the suspension sentence at sign-in. The dashboard adds no sentence a shop reads.
- **Out of scope:** retrying a job from here; changing models or prompts.

## R-ADMIN-006 — The few settings
- **Story:** As the operator, I change the few numbers of the business without a release.
- [ ] The purchase text: shown as the shops read it (the fallback when none is set), changed from the dashboard. A change applies from then on and is logged (R-ADMIN-001).
- [ ] Welcome credits are typed at each creation (R-ADMIN-002); there is no stored setting for them.
- [ ] The daily limits are shown, read-only: provider spend per shop per UTC day (`SHOP_DAILY_SPEND_USD`) and messages read per shop per UTC day (100). **Default:** the same for every shop; each shop keeps its own count under them. They change in the box's secrets file (a recreate, not a release) or in code.
- **Out of scope:** secrets, provider keys, model choice, per-shop limits, anything that is a release today.

## What changed from v3, and why

| v3 | v4 | Source |
|---|---|---|
| "Every other dashboard action is logged" | logged, best effort: a line can be lost when the process stops after the action is saved | design v3; review round 2 P2-1 |
| One request kept "through sending, a lost answer, a new sign-in and a resend" | also through a server error and a reload; no new money request for that shop until it is resolved or discarded; the limit of deduplication stated; a repeated move names where the payment went | review round 2 P2-2, P2-3 |
| "An operator's session is refused on every shop route" | on every protected shop route; the shops' own session operations stay public | review round 2 P2-5 |

## What changed from v2, and why

| v2 | v3 | Source |
|---|---|---|
| An append-only record of every non-money action, listable | money in the ledger with its actor; other dashboard actions logged to the journal; live sessions listed | lead's decision A (design v2) |
| The hash in `OPERATOR_PASSWORD_HASH`; without it the dashboard is off | set by `operator-password` in the database; unset, sign-in is refused | lead's decision B |
| "A session ends … when the operator ends every operator session" | that control is on the page, confirmed, and includes this device | Codex r1 P2-5 |
| Every dashboard route refuses a shop's session | the three public session operations apart from the protected routes | Codex r1 P2-7 |
| "Sent twice … written once, names the line" | one frozen request; « already recorded as line N » and whether it matches; never another reference | Codex r1 P2-1, devil's advocate |
| 360 px | with the longest values the fields accept | Codex r1 P3-10 |
| Images in the usage report | counted by kind, those from before credits included | Codex r1 P2-2 |
| The decisions kept by the review stood only in the design | written here: `/api/status` unchanged, the actor's form, welcome at creation, one limit for every shop | Codex r1, rulings |

## What changed from v1, and why

| v1 | v2 | Why |
|---|---|---|
| "What exists: `/api/status` and `/api/usage`, readable by the shop session" | the command line, `/api/status` on the machine only, `/api/balance` | multi-shop and prepaid-balance as built |
| One record of every action | credit lines are their own record | `credit_grants` already holds time, actor, reference and note, and is never changed or removed |
| "Open one shop: its ledger, its recent generations with their outcome, its limits" | the credit history with each generation's job id; today's limits | a repayment needs the job id (`correct --job`); limits are service-wide settings |
| "Add credits … with the payment's reference" | the reference makes a second send harmless; moving a payment | migration 0014's rules; `move-payment` |
| "A switch … one per shop. Both say so to the shop in one sentence" | the pause, and suspension for one shop; the existing sentences | prepaid-balance owner decision 6; no new shop sentence |
| "Jobs whose outcome is unknown are listed with … what the shop's credit is doing" | failed, unknown outcome, and running over ten minutes; with the job id | an unknown outcome gives the credit back at once (prepaid-balance owner decision 3); a stuck job still holds one |
| "Welcome credits; daily limits per shop" as settings | welcome typed per shop; limits shown read-only | no per-shop limit exists; adding one is a schema change no shop has asked for |

## Decisions only the owner can take

Each is in force on its default until the owner says otherwise. Decisions 1 to 4 are the lead's calls of 2026-11-17, which the owner may overturn.

| # | Decision | Default in force |
|---|---|---|
| 1 | A queryable record of non-money actions | none in Release 1: the ledger holds money with its actor; the rest is in the journal, best effort (about 14 days). Who suspended which shop and when cannot be looked up after that, or when a line was lost |
| 2 | Where the operator's password lives | its hash in the database, set by `operator-password` (26 characters); a restore brings back the backup's password, so the command is run again before the service starts |
| 3 | What Release 1 may leave out | nothing is cut. The usage report, the problems list and the Reka UI trial come last and may move after Release 1 on the owner's word |
| 4 | Which Reka UI primitive is tried | AlertDialog, kept only if it beats the native dialog on a measured point. Alternative: Tabs |
| 5 | Cancelling a payment that never arrived (its whole reversal, refused once its credits are spent) | not in Release 1; today a correction removes the credits and the amount stays counted |
| 6 | Where the dashboard lives | `/admin/` on the shops' address. A subdomain would isolate it from the shops' pages fully, and needs a DNS record and a change to Maizina's Caddy |
| 7 | How long an operator session lasts | 12 hours from sign-in |
| 8 | Two-factor sign-in | not in Release 1 |
| 9 | Per-shop daily limits | not built; one setting for every shop |
| 10 | The dashboard's language | English (the operator reads English and French; the command line and the runbook are English); what a shop reads stays French |
| 11 | The report's day | the UTC day, as the shop's daily limit (it turns at 03:00 in Madagascar) |
| 12 | Sign-in limits | per address only; a limit over all addresses would let anyone lock the operator out |
