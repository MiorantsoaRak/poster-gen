# DESIGN — Prepaid balance of generations (prepaid-balance)

## System overview

**Status:** v4, 2026-11-16. Approved under the user's autonomy grant after three review rounds (REJECT, REJECT, APPROVE WITH FIXES) and a devil's advocate; the round-3 fixes are in v4 and were not reviewed again as a design: the code reviews of the tasks check them ("What the code reviews check", under Tasks).
**Requirements file:** [../requirements/prepaid-balance.md](../requirements/prepaid-balance.md) (R-BALANCE-001 to 007), approved 2026-11-16 under the autonomy grant with the amendments of this design (its last-but-one section). Of the eight owner decisions one is decided by the owner (the pilot's opening balance); the others are in force on their recommended defaults, and the owner can still change each before the task that builds it (last section).
**Reviews:** [round 1, Codex, REJECT](../reviews/prepaid-balance-design-r1-2026-11-16.md); [devil's advocate](../reviews/prepaid-balance-devils-advocate-2026-11-16.md); [round 2, Codex, REJECT](../reviews/prepaid-balance-design-r2-2026-11-16.md); [round 3, Codex, APPROVE WITH FIXES](../reviews/prepaid-balance-design-r3-2026-11-16.md).
**Depends on:** [multi-shop](multi-shop.md) v4 as built (T-MULTI-SHOP-001 to 006 committed), its D-005, D-006 and the section "Amended on 2026-11-16", "After round 4": the server is the authority for a paid request.
**Release:** second feature of Release 1 « Invitation » (ROADMAP.md, ADR-105). Nothing is deployed until the whole release is ready.

A credit is one image. The balance is derived, never stored: **the sum of the operator's lines (grants and corrections) minus the shop's image jobs that took a credit and are `queued`, `running` or `succeeded`.** The job is the debit. A job that ends `failed`, `interrupted` or `cancelled` stops counting by itself: the credit is back with no write. Which jobs count is one column on `poster_jobs`, set at admission in the transaction that already writes the idempotency key, the job and its provider reservation. One trigger refuses any move out of a final state and any change of that column, and a permanent check in the rehearsal and in the suite fails when a later migration loses it. The operator writes grants and corrections with `python -m affiche.shops`; every one carries a reference its shop cannot use twice, and a payment's money lives in one shop at a time (moved only by one atomic operation). No dollar figure reaches a shop. One new table, one new column, five triggers, one new module, one new route, no new dependency.

```
tap ─▶ POST /scenes | /refinements | /text-effects ─▶ store.mutate: one BEGIN IMMEDIATE
         key unknown ─▶ feature checks ─▶ jobs.enqueue: poster rules ─▶ INSERT job (takes_credit = 1 for an image kind)
         ─▶ _reserve: provider_guard (suspended? paused? cap? shop's day?) ─▶ INSERT call
         ─▶ credits.require: grants − counted jobs (this one included) ≥ 0, else 402 ─▶ INSERT key ─▶ COMMIT
         key known ─▶ the stored answer; nothing checked, nothing counted again
worker ─▶ queued → running → succeeded: the version exists; the job keeps counting (spent)
                          └─▶ failed | interrupted | cancelled: the job stops counting (credit back, nothing written)
guard  ─▶ trigger poster_jobs_final: no move out of a final state, no change of takes_credit
           checked to exist with its exact SQL by the suite and by every rehearsal (rehearse.GUARDS)
shop   ─▶ GET /api/balance {available, pending, blocked: {scene, text_texture}, purchase_fr}
operator ─▶ python -m affiche.shops grant | move-payment | correct | create --welcome | pause | resume | purchase-text
           | after-restore [--apply]
```

### What changed from v3, and why

| Round-3 point or lead's decision | v4 |
|---|---|
| P2-1: an amount fix could erase or negate a payment; `credit_grants_one_payment` summed all other shops together | A new trigger, `credit_grants_payment_total`, keeps every shop's total for a payment above zero after an amount fix, and makes a reversal bring it to exactly zero; `correct` checks the same first. `credit_grants_one_payment` now tests each other shop's total apart (`EXISTS … GROUP BY shop_id HAVING SUM(amount_ar) > 0`). Scratch checks re-run. The sentences now claim only what the SQL holds (D-001, D-005) |
| P2-2, P2-3, P2-5 (lead's decision): restore printed commands per shop, lost dates, quoted names unsafely | **The commands are replaced by a copy.** `after-restore <kept file>` reports; with `--apply` it copies every missing `credit_grants` row of the kept database, in its global order, with its original date, in one transaction, through the same rules and triggers. Shops are mapped by identifier; while one is missing nothing is copied, and the one command shown, to create it, is built with `shlex.join` (D-005) |
| P2-4: replays gated in the browser | « Reprendre » and « Réessayer » are never gated: available at zero and while blocked; only new requests are gated. Test added (D-006, Tests) |
| P3: test_api.py:100-101 reads `/api/usage`; `interrupted` bypasses `jobFailure` (App.vue:1250-1251); the headroom example warned at 8.40 < 8.80 | Added to T-BALANCE-003; the sentence is appended in the common terminal branch (App.vue:1250); the example's numbers now warn for a reason (D-004, D-005, D-006) |
| Lead: approval | The status above; the owner decisions in force on their defaults, each with the task before which the owner can still change it; the cap stays cumulative (an open decision, not a task); the round-3 fixes mapped to the code reviews of their tasks |

### What changed from v2, and why

(v3's answers, kept as history. Where v4 changed one, notably the restore's printed commands and the per-shop order, the table above and the sections below win.)

| Review point (round 2) or decision | v3 |
|---|---|
| Owner, 2026-11-16: « grant by hand, 30 credits » | Decision 1 is decided: 30 offered credits typed by the operator right after the release; 0014 grants nothing. The release steps say to warn the pilot first, give the command, and say what he sees in that minute (D-005, Release gate). Option B and its rehearsal line are removed |
| P1: a payment could still fund two shops (`--move-from` after a money-only correction) | `--move-from` is gone. One atomic `credits.move` (`move-payment`) reverses the source's credits and ariary and grants the same to the destination in one transaction, refused unless the credits are still unspent. `grant` refuses a bought reference held in any shop, with no override. A new trigger, `credit_grants_one_payment`, refuses a positive amount for a reference whose money is still counted in another shop. An amount correction is kept only to fix a mistyped amount of the shop's own payment (D-001, D-005) |
| P2: restore replay looked only at the job's existence | A repayment is replayed only when the restored job is `succeeded` with `takes_credit = 1`; it is skipped when the job ended without an image or is gone; it is listed "decide after it ends" when the job is still `queued` or `running`. A move is replayed as a move. A missing shop is recreated with `--welcome 0` before its own grants (D-005) |
| P2: `blocked` computed with a scene's estimate disabled a cheaper texture | `blocked` is per charged operation, each with its real estimate: `scene` (scene and refinement) and `text_texture` (D-003, D-004, D-006) |
| P2: the history seam omitted returned credits | The history includes every job with `takes_credit = 1`, whatever its end, with its admission time, its final time and its state; only the balance filters by status (Seams) |
| P2: stored cancellation answers keep `usage` | `jobs.cancel` drops `usage` from the answer it returns, stored or fresh; it is the only stored answer with a dollar field (checked over every `mutate` caller). The "no dollars" proof becomes an API test over every shop route, with a pre-0014 cancellation replayed (D-004, Tests) |
| Split T-BALANCE-004 | T-BALANCE-004 is the operator's commands, T-BALANCE-005 the restore reconciliation, T-BALANCE-006 the browser (Tasks) |
| Reviewer's note: exact SQL fails closed on harmless formatting | Said in the guards: a legitimate change updates `GUARDS` in the same commit as its migration (D-001) |

### What changed from v1, and why

(v2's answers, kept as history. Where v3 or v4 changed one, notably `--move-from`, the single `blocked`, option B and the restore's printed commands, the tables above and the sections below win.)

| Review point | v2 |
|---|---|
| Devil's advocate 2: a debit line copies the job row | **The model changes.** No debit or release lines, no `poster_jobs_credit_back` trigger, no per-origin floor. Balance = operator lines − counted jobs; « en attente » = counted jobs `queued` or `running` (D-001, D-002). "Offered" stays a label on grants; "offered spent first" is dropped. |
| Codex P1-1: a rebuild of `poster_jobs` would drop the release trigger and the rehearsal would not see it | The release trigger is gone. The one trigger left on `poster_jobs` (`poster_jobs_final`), the operator table's two triggers, the table and the column are listed in `rehearse.GUARDS` and checked **after every rehearsal, whatever is pending**, and by a unit test on a fresh migrated database; a regression test rebuilds `poster_jobs` the way this project does and the rehearsal fails (D-001). |
| Codex P1-2: restore | A policy (grants and jobs return to the backup's time; images made after it are gone and not charged; the operator types again what was granted or corrected since) and a read-only command, `after-restore`, that compares the kept database with the restored one and prints what to type, shop by shop (D-005). |
| Codex P2-3: a moved payment counted twice | Corrections carry a signed `amount_ar`; money received is the sum of `amount_ar` over all lines. A bought grant whose reference another shop holds is refused unless `--move-from` names that shop and its lines for that reference sum to zero ariary. The per-shop unique key becomes `(shop_id, kind, ref)` so that the reversing correction can carry the payment's reference (D-005). |
| Codex P2-4: a job repaid twice | A correction naming a job is allowed only for this shop's `succeeded` job that took a credit, once per job (`job_id UNIQUE`), +1 only (D-001, D-005). |
| Codex P2-5: the pause stops a 429 retry; "images" is not true for reads | The pause is checked at admission only: `provider_guard(…, admission=call_no == 1)`; `reserve_rate_limit_retry` passes call 2 and is not stopped. `budget_exhausted` is reused for the pause, with one sentence true for images, styles, text proposals and reads (D-003). |
| Codex P2-6, devil's advocate 1 and 4: told to buy when buying cannot help | `GET /api/balance` returns `blocked` (`service`, `day`) and its sentence, computed by the same guard with a scene's estimate. The dialog's order is the server's: blocked, then zero, then « bientôt à court » at three credits or fewer, which shows the purchase text early (D-003, D-006). |
| Codex P2-7: consumers and tasks | Every reader of `/api/usage` and of a job's `usage` listed (one more than the review found: test_poster_visuals.py:182); every test module that admits image jobs and every fixture to fund listed; `backend/api/README.md` updated; six tasks; the "no dollars" gate moved to the task that removes the last of them (Tasks). |
| Codex P3: 500 for a constraint failure | 503 `storage_unavailable` (api.py:273-278); failure tables aligned. |
| Codex on the owner decisions | Decision 3 states its cost as it is; the pilot's grant lands before traffic (option B, D-005); decision 6 says suspension also removes editing and downloads; decision 7 is the admission-only pause. |
| Devil's advocate 1: the cap never resets | `grant` prints the cap's headroom against all outstanding credits and warns. How failed calls are costed is unchanged; whether the provider bills a refused 4xx is an open check for the next paid test; cumulative or monthly cap is an owner decision (D-005, decisions). |
| Devil's advocate 3: defects repaid by hand | Not built. An automatic option is described in the owner's decisions; the default stays the operator's correction. |
| Devil's advocate 5: purchase text in the environment | A `meta` key set by `shops purchase-text`; the runbook says the text must state when credits arrive (D-004, D-005). |
| Devil's advocate 6: the 100/20 read limit | One flat limit, 100 a day per shop (D-004). |
| Devil's advocate 7: task split, commands built twice | `_pending` fixed first and alone (T-PENDING-KINDS). The commands are those needed before the dashboard; no `ledger`, no balances in `list` (D-005, Tasks). |
| Found while checking v2 | A `NULL` inside a `CHECK (CASE …)` makes the check pass: a bought grant without amount was accepted in the scratch run. The rule is wrapped in `COALESCE(…, 0)` (D-001). |

### What the code already gives (read 2026-11-16; `test_poster_jobs.py`, `test_two_shops.py`, `test_reads.py`: 238 passed on this Linux machine)

| Property | Where |
|---|---|
| A mutation's key, its work and its answer are one write transaction; a replay returns the stored answer without running the work; a refusal raises before the key is written | `store.mutate` store.py:42-57 (`apply` at :53, key INSERT at :54); `write_tx` is `BEGIN IMMEDIATE` db.py:39-48 |
| Every paid image admission goes through `jobs.enqueue` inside `mutate` | scene visuals.py:232-295, refinement visuals.py:298-345, text texture typography.py:241-258 |
| `jobs.enqueue` is the only writer of `poster_jobs` rows | `INSERT INTO poster_jobs` appears only at jobs.py:103 in src/ |
| One image job queued or running per poster | jobs.py:87-90; UNIQUE index `poster_one_image` 0006_poster_jobs.py:22-23 |
| The provider guard runs inside the admission transaction (suspension, cap, shop's day); a refusal raises | `provider_guard` jobs.py:57-68, via `_reserve` jobs.py:71-77; reads at reads.py:570 |
| A 429 retry reserves call 2 through the same guard | `reserve_rate_limit_retry` jobs.py:208-223 (`_reserve(…, 2, …)` at :222); worker.py:63-74 |
| **No path moves a job out of a final state.** Every status writer and its precondition: `cancel_queued` jobs.py:127 (callers: `cancel` on `queued` :136, `suspend` on `queued` shops.py:97, `dispatch` on `running` :177, `recover` on `running` :285-286); `claim` jobs.py:158 (rows selected `queued` :152); `fail` jobs.py:198 (requires `running` :189-191); `finish_spool` jobs.py:270 (requires `running` :260, returns early on `succeeded` :258-259); `recover` jobs.py:292, :297, :302 (all over `running` rows :285-286). The requeue at :297 is `running → queued`, not out of a final state | grep of `UPDATE poster_jobs` in src/: only jobs.py. In the tests, only test_api.py:126-129 writes a status directly, moving `queued` render jobs into final states |
| The owner sees a new image exactly when the job becomes `succeeded`, in one transaction with the version or the text effect | `finish_spool` jobs.py:253-278; `PosterService.finalise` service.py:108-185 (effect :125-126, visual :130, first-scene version :182) |
| A refused (4xx) image call is recorded at its full reservation: `ProviderError` carries no cost | gateway.py:64-73; worker.py:78 passes `None`; jobs.py:201-205 keeps the reservation as an estimate |
| A constraint failure in a request is answered 503 `storage_unavailable` | `AccessBoundary` api.py:273-278 (`SQLAlchemyError`) |
| The rehearsal checks `ADDED` only for **pending** migrations, and hashes rows, not triggers | rehearse.py:90, :107-108, :48-59 |
| A restore keeps the replaced database with its WAL under the matching name, and removes its `-shm` | restore.sh:25, :42-44 |
| The release starts the new container with `up`, which migrates at start and serves at once | release.sh:85; the operator command refuses an old schema (shops.py:224-229) |

### Every call that makes an image, and who can start it

| Job kind | Route | Started by | Today's estimate | Credit |
|---|---|---|---|---|
| `scene` | `POST /api/creations/{id}/scenes` (api.py:561-563) | « Générer l’affiche », « Nouvelle version », the chat's « Créer l’affiche », « Refaire l’affiche » | 0.40 USD | 1 |
| `refine` | `POST /api/creations/{id}/refinements` (api.py:565-567) | « Ajuster la scène », the chat's « Créer » | 0.40 USD | 1 |
| `text_texture` | `POST /api/creations/{id}/text-effects` (api.py:604-606) | « Générer la matière du texte » (App.vue:1770) | 0.30 USD | 1 (owner decision 2) |
| `plan` (Claude), `plan` with `{"look": …}`, `text_patch` | plans, looks, text proposals | the planner mode `claude` (default `fixed`, App.vue:40), « Enregistrer ce style », « Proposer un ajustement » | 0.10 USD | none: no image |
| `render`, chat reads | renders, `POST /api/reads` | the final preview; the chat | 0; 0.02 USD | none |
| `background`, `cutout` | none: listed (jobs.py:18-20, 0006:14) but enqueued by no route and not served (service.py:21) | — | — | — |
| evaluation CLI | `python -m affiche.visuals.evaluate … --paid` | the operator only; ledger `provider_calls`, no shop | — | none |

The kinds that take a credit are `jobs.IMAGE_KINDS` (jobs.py:18); `background` is never enqueued. No new constant.

## Where the requirements pull against each other or against the code

1. **R-BALANCE-002 "a known failure gives the credit back" against `interrupted`.** In the code, `interrupted` means the provider's charge is unknown. The owner never gets an image from such a job, now or later. **Resolution:** every job that ends without an image stops counting at once, `interrupted` included (owner decision 3, with its cost).
2. **R-BALANCE-007 (100 with credits, 20 at zero) against reads.py:32 (200).** **Resolution (lead, after the devil's advocate):** one flat limit of 100 a day per shop. The rule for zero waits for self-service sign-up.
3. **R-BALANCE-001 "one generated image costs one credit" against ADR-107 ("textures … no credit").** **Resolution:** a text material is an image and costs one credit (owner decision 2).
4. **R-BALANCE-001 "every paid button says « 1 crédit »".** Style briefs and text proposals are paid by the service and cost no credit. **Resolution:** image buttons say « 1 crédit »; the two Claude buttons say « Sans crédit. ».
5. **R-BALANCE-003 "a debit, a release" as lines.** **Resolution:** the generation is its own record. It takes its credit while it waits, runs or has made its image, and gives the credit back by ending without one. Nothing of a job is ever deleted.
6. **R-BALANCE-005 and the shop's daily provider ceiling.** `SHOP_DAILY_SPEND_USD` (config.py:40) can refuse a shop that still has credits. **Resolution:** kept. The refusal takes no credit, and it is shown before the tap (the operation's entry of `blocked` reads `day`).
7. **R-BALANCE-006 "offered credits are spent first".** **Resolution:** not implemented. It changes nothing a shop can see while credits never expire and are never refunded in money, and it can be computed from the lines when either is built.
8. **R-BALANCE-003 "restoring a backup cannot grant twice".** **Resolution:** a restore by itself doubles nothing; it loses what came after the backup. `after-restore --apply` copies the lost lines back in their order and with their dates, and its match on the shop, the kind and the reference skips any line already present (D-005).

---

## D-BALANCE-001 — The balance: the operator's lines minus the counted jobs (covers R-BALANCE-003, R-BALANCE-006; the data of R-BALANCE-002)

**Approach:** the operator writes lines; the jobs are the debits. The only new state on `poster_jobs` is whether a job takes a credit, fixed at insert. The balance is one query:
```sql
SELECT (SELECT COALESCE(SUM(credits), 0) FROM credit_grants WHERE shop_id = :shop)
     - (SELECT COUNT(*) FROM poster_jobs WHERE shop_id = :shop AND takes_credit = 1
          AND status IN ('queued', 'running', 'succeeded'))                          AS available,
       (SELECT COUNT(*) FROM poster_jobs WHERE shop_id = :shop AND takes_credit = 1
          AND status IN ('queued', 'running'))                                       AS pending
```
`poster_jobs_shop_started (shop_id, started_at)` (0013:57) and the unique key of `credit_grants`, which begins with `shop_id`, serve it.

**Migration `0014_credits.py`** (forward-only, hand-written SQL, a `STATEMENTS` list as in 0013):
```sql
ALTER TABLE poster_jobs ADD COLUMN takes_credit INTEGER NOT NULL DEFAULT 0 CHECK (takes_credit IN (0, 1));
CREATE TABLE credit_grants (
  id INTEGER PRIMARY KEY,
  shop_id INTEGER NOT NULL REFERENCES shop_profile(id),
  kind TEXT NOT NULL CHECK (kind IN ('grant', 'correction')),
  origin TEXT CHECK (origin IN ('offered', 'bought')),                  -- a grant's label only
  credits INTEGER NOT NULL CHECK (typeof(credits) = 'integer'),
  amount_ar INTEGER CHECK (amount_ar IS NULL OR (typeof(amount_ar) = 'integer' AND amount_ar <> 0)),  -- signed on a correction
  method TEXT CHECK (method IS NULL OR length(method) BETWEEN 1 AND 40),
  ref TEXT NOT NULL CHECK (length(ref) BETWEEN 1 AND 100),
  job_id TEXT UNIQUE REFERENCES poster_jobs(id),                         -- a repayment: once per job
  note TEXT CHECK (note IS NULL OR length(note) BETWEEN 1 AND 500),
  actor TEXT NOT NULL CHECK (length(actor) BETWEEN 1 AND 64),
  created_at TEXT NOT NULL,
  CHECK (COALESCE(CASE kind                                              -- a NULL inside the rule must refuse, not pass
    WHEN 'grant' THEN credits > 0 AND job_id IS NULL AND (
         (origin = 'bought' AND amount_ar > 0 AND method IS NOT NULL)
      OR (origin = 'offered' AND amount_ar IS NULL AND method IS NULL))
    ELSE origin IS NULL AND method IS NULL AND note IS NOT NULL
      AND (credits <> 0 OR amount_ar IS NOT NULL)
      AND (job_id IS NULL OR (credits = 1 AND amount_ar IS NULL)) END, 0)),
  UNIQUE (shop_id, kind, ref)
);
CREATE TRIGGER credit_grants_never_changed BEFORE UPDATE ON credit_grants
  BEGIN SELECT RAISE(ABORT, 'a credit line is never changed'); END;
CREATE TRIGGER credit_grants_never_removed BEFORE DELETE ON credit_grants
  BEGIN SELECT RAISE(ABORT, 'a credit line is never removed'); END;
CREATE TRIGGER credit_grants_one_payment BEFORE INSERT ON credit_grants
  WHEN NEW.amount_ar > 0 AND EXISTS (SELECT 1 FROM credit_grants WHERE ref = NEW.ref AND shop_id <> NEW.shop_id
       GROUP BY shop_id HAVING SUM(amount_ar) > 0)
  BEGIN SELECT RAISE(ABORT, 'this payment is already counted in another shop'); END;
CREATE TRIGGER credit_grants_payment_total BEFORE INSERT ON credit_grants
  WHEN NEW.kind = 'correction' AND NEW.amount_ar IS NOT NULL AND (
       (SELECT COALESCE(SUM(amount_ar), 0) FROM credit_grants WHERE shop_id = NEW.shop_id AND ref = NEW.ref) <= 0
    OR (NEW.credits = 0 AND (SELECT COALESCE(SUM(amount_ar), 0) FROM credit_grants
                             WHERE shop_id = NEW.shop_id AND ref = NEW.ref) + NEW.amount_ar <= 0)
    OR (NEW.credits <> 0 AND (SELECT COALESCE(SUM(amount_ar), 0) FROM credit_grants
                              WHERE shop_id = NEW.shop_id AND ref = NEW.ref) + NEW.amount_ar <> 0))
  BEGIN SELECT RAISE(ABORT, 'a payment''s corrected total must stay positive, or a reversal must bring it to zero'); END;
CREATE TRIGGER poster_jobs_final BEFORE UPDATE OF status, takes_credit ON poster_jobs
  WHEN NEW.takes_credit IS NOT OLD.takes_credit
    OR (OLD.status IN ('succeeded', 'failed', 'interrupted', 'cancelled') AND NEW.status IS NOT OLD.status)
  BEGIN SELECT RAISE(ABORT, 'a finished job never changes status, and no job changes what it costs'); END;
```
0014 grants nothing: the pilot's opening balance is typed by the operator after the release (decided, D-005).

| Rule | What it stops |
|---|---|
| `ADD COLUMN … NOT NULL DEFAULT 0` | every job from before 0014 counting: they read 0 and never take a credit |
| `typeof(…) = 'integer'` | a fraction of a credit or of an ariary (SQLite keeps 1.5 in an INTEGER column otherwise) |
| the `CASE` rule | a grant of zero or fewer credits; a bought grant without amount or method; an offered grant with them; a grant naming a job; a correction without its reason, or with nothing in it; a repayment other than +1 credit without money |
| `UNIQUE (shop_id, kind, ref)` | a grant typed twice; a correction typed twice; a line brought back twice (the restore's copy matches on these three columns). A grant and its reversing correction may share the payment's reference |
| `job_id UNIQUE` | a job repaid twice |
| `credit_grants_never_changed`, `credit_grants_never_removed` | editing or deleting the operator's history |
| `credit_grants_one_payment` | a positive amount for a reference while **some other shop's own total** for it is above zero: a payment granted to a second shop, or moved without first being reversed where it is. Each other shop is tested apart, so a negative total in one could not hide a positive one in another (round 3). A positive amount in the same shop (a mistyped amount fixed) passes |
| `credit_grants_payment_total` | a correction carrying an amount when the shop has no positive payment under that reference; an amount fix (`credits = 0`) that would bring the payment's total in that shop to zero or below; a reversal (`credits ≠ 0`, the move's) that would not bring it to exactly zero. With it, no shop's total for a reference is ever below zero |
| `poster_jobs_final` | a finished job counting again or ceasing to count; a job changing whether it costs a credit. Other columns of a finished job may still change (`result_ref`, `input_json`; tests use the latter, test_editor_refinements.py:133) |

**What the two payment triggers guarantee together, and no more:** for each reference, at most one shop holds a positive total and none a negative one, so `SUM(amount_ar)` over all lines counts each payment once. They cannot know the true amount of a payment: a positive amount fix raises it, by the operator's word. Both read only `credit_grants`, so they constrain no rebuild of `poster_jobs`.

**ADD COLUMN on the release's SQLite:** SQLite's documented limits for `ADD COLUMN` are no PRIMARY KEY or UNIQUE, a non-NULL default with NOT NULL, and a NULL default with a REFERENCES clause; this column meets all three. Since 3.37 a CHECK is also tested against existing rows; the default 0 passes it, so 3.40.1 behaves the same either way. This is from the documentation as I know it: run here on 3.53.1, not on 3.40.1. The rehearsal gate runs it there.

**Checked in the scratchpad (not the repository), on a database migrated to 0013, SQLite 3.53.1:** 25 assertions on the SQL above. They cover each refusal of the table; a correction sharing its grant's reference; an amount-only correction; `running → queued` allowed; `succeeded → failed` and a change of `takes_credit` refused; the same final status written again allowed; the derived balance and the ariary sum. One finding came from this run: a rebuild of `poster_jobs` by SQLite's procedure (copy, drop, rename) **drops `poster_jobs_final` silently**. The guards below exist for that. **The two payment triggers were checked apart, on a table of the same keys (v4, SQLite 3.46.1):**
- A 1,000 Ar payment: a fix of −2,000 and a fix of −1,000 are refused, and a fix of −400 passes (total 600).
- With one shop's total forced negative, a third shop's grant is still refused while another shop's total is positive. v3's single sum read 0 there and would have let it pass.
- The chain A→B→C passes with receipts at 1,000; a partial reversal is refused; an amount fix in a shop whose payment was moved away is refused; a correction with an amount and no payment is refused.
- A second shop's grant of a counted payment is refused; an offered grant under the same reference passes.

### What this model loses, and what disappears

- **Lost:**
  - The debit is no longer an append-only line. The job row is the debit and its status changes; `poster_jobs_final` and the guards hold it.
  - The time a credit came back is the job's `finished_at`, not a line of its own.
  - "Offered spent first".
  - The shop's history becomes a union of two tables (the operator's lines, and every job that took a credit, whatever its end; Seams).
  - A later policy that keeps the credit of a failed job (for example "a provider refusal costs a credit") would need a new rule; today every failure gives it back.
- **Disappears:**
  - A lost release, a double release, a release without debit (there are no releases).
  - A job end that fails because its credit line cannot be written.
  - Per-origin floors.
  - The coupling of every job-ending path to the ledger.
  - Double debit is a single fact: one job, one credit.
  - The unit stays a query, so the price unit can change after the prices are tested (R-ADMIN-004).

### The permanent guards (answers Codex P1-1)

**Where they live:** `rehearse.py`, beside `LEDGERS` (rehearse.py:30). It holds no import of the application, and the rehearsal "reads no settings" (rehearse.py:10). Whitespace runs are collapsed on both sides before the texts are compared; the SQL is otherwise exact. **So the check fails closed on a harmless change too** (a reworded message, other quoting, a comment): a migration that legitimately changes one of these objects updates its `GUARDS` text in the same commit, and the suite's guard test fails until it does.
```python
# Schema objects every later migration must keep, checked after every rehearsal whatever is pending: rebuilding a
# table by SQLite's procedure drops its triggers without a word. A migration that changes one updates it here.
GUARDS = {  # (type, name): the CREATE statement as 0014 wrote it
    ("table", "credit_grants"): "CREATE TABLE credit_grants ( id INTEGER PRIMARY KEY, … UNIQUE (shop_id, kind, ref) )",
    ("trigger", "credit_grants_never_changed"): "CREATE TRIGGER credit_grants_never_changed BEFORE UPDATE … END",
    ("trigger", "credit_grants_never_removed"): "CREATE TRIGGER credit_grants_never_removed BEFORE DELETE … END",
    ("trigger", "credit_grants_one_payment"): "CREATE TRIGGER credit_grants_one_payment BEFORE INSERT … END",
    ("trigger", "credit_grants_payment_total"): "CREATE TRIGGER credit_grants_payment_total BEFORE INSERT … END",
    ("trigger", "poster_jobs_final"): "CREATE TRIGGER poster_jobs_final BEFORE UPDATE OF status, takes_credit … END",
}
GUARDED_COLUMNS = {"poster_jobs": "takes_credit INTEGER NOT NULL DEFAULT 0 CHECK (takes_credit IN (0, 1))"}
```
(The table's own text holds its CHECKs and both unique keys; `ALTER TABLE ADD COLUMN` appends the column's text to the table's stored statement, checked in the scratchpad.)

**In `rehearse.rehearse`:**
- After `added` (rehearse.py:107-108), still inside the temporary folder, on the migrated copy, compute `guards(db)`: `SELECT sql FROM sqlite_master WHERE type=? AND name=?` for each `GUARDS` entry, and the table's statement for each `GUARDED_COLUMNS` entry, then compare after collapsing whitespace.
- After the `ADDED` loop (rehearse.py:135-138): one report line per guard (`guard trigger poster_jobs_final: as expected`, or `missing`, or `different`) and one difference for each that is not.
- It runs on every rehearsal, also when nothing is pending: the copy is migrated (a no-op) and checked.
- One function, `rehearse.guard_differences(db) -> list[str]`, used by the rehearsal and by the test below.

**Tests:**
- **The suite** (test_credits.py): `guard_differences` on a fresh database from `migrate` is empty. This catches a later migration in the repository that loses a guard at its first test run, long before a release.
- **The rehearsal** (test_db.py, with the existing `damaging` pattern of test_db.py:372-381):
  - (a) After `migrate`, `poster_jobs` is rebuilt by SQLite's procedure, as a later migration changing its CHECK lists would do: `REHEARSAL FAILED` naming `guard trigger poster_jobs_final`.
  - (b) `DROP TRIGGER credit_grants_never_removed`: FAILED naming it.
  - (c) The same rebuild with the trigger recreated from its `GUARDS` text: OK.
  - (d) A database already at head whose trigger was dropped by hand, nothing pending: FAILED.

**No database floor under the balance** (the two payment triggers above are floors of another kind: they read only `credit_grants`). A negative correction larger than the shop's balance is refused by `credits.correct` in its transaction (D-005), and an admission by `credits.require` (D-002). A trigger could do the same: `BEFORE INSERT ON credit_grants` reading `poster_jobs`. **Not built.** In the scratchpad, a trigger on one table that reads another made `ALTER TABLE … RENAME` fail in that other table's rebuild ("error in trigger …: no such table"). So every later rebuild of `poster_jobs` would have to drop and recreate it. The lines that lower a balance are written by `correct` and `move`, which check it inside `BEGIN IMMEDIATE`, and by the restore's copy, which replays history as it was and reports any balance it leaves below zero (D-005). A balance below zero only shows as such and refuses the next admission until it is above zero again.

**The rehearsal contract of 0014:** `poster_jobs` is widened, so without a projection the rehearsal would hash it over its new column too and report "different content" (rehearse.py:51, :119-121). It is named with its 0013 columns (read from a database migrated to 0013), the same contract 0013 used for `login_failures`:
```python
PRESERVED = {"poster_jobs": ("id", "shop_id", "creation_id", "origin_revision", "input_id", "kind", "input_json",
                             "input_hash", "status", "result_ref", "error_code", "created_at", "started_at",
                             "finished_at", "recovery_count")}
ADDED = {
    "poster_jobs: no job from before 0014 takes a credit": (
        "SELECT count(*) FROM poster_jobs WHERE takes_credit <> 0", [(0,)]),
    "credit_grants: empty; no shop has a credit before the operator grants one": (
        "SELECT count(*) FROM credit_grants", [(0,)]),
}
```
The guards are not in `ADDED`: they are checked on every rehearsal (above).

**Failure modes & handling:**
| Failure | Detection | Behavior |
|---|---|---|
| 0014 fails half way | exception | rollback, version 0013 (`migrate`, db.py:56-78) |
| A line or a job update that breaks a rule | the constraint or trigger | `IntegrityError`: the whole transaction rolls back; the API answers 503 `storage_unavailable` (api.py:273-278); the command exits 1 with the driver's message (shops.py:238-239) |
| A later migration loses a guard | `guard_differences` | the suite fails at once; a database changed by hand fails the rehearsal and the release stops before anything changes |

**Edge cases:** a job queued before 0014 and run after it never counts. A backup from before 0014, restored, has no line and no counted job: every balance is 0 until the restore's copy brings the kept database's lines back (D-005).

---

## D-BALANCE-002 — Taking a credit at admission; the credit's states (covers R-BALANCE-001, R-BALANCE-002, R-BALANCE-004 on the server)

### `jobs.enqueue`

jobs.py:102-110 becomes:
```python
takes = int(kind in IMAGE_KINDS)                      # scene, refine, text_texture (owner decision 2)
INSERT INTO poster_jobs (…, takes_credit) VALUES (…, :takes)
if spec:
    _reserve(conn, settings, shop, id, 1, spec)       # provider_guard, admission=True (D-003)
if takes:
    credits.require(conn, shop)                       # this job is already counted: 402 when the balance is now < 0
```
```python
def require(conn, shop: int) -> None:
    """Inside the admission transaction, after the job's row: the sum of the grants minus the counted jobs, this one
    included, must not be below zero (D-BALANCE-002)."""
    if balance(conn, shop)["available"] < 0:
        raise Refused("no_credit", 402)
```
The sum and the count are read by the same connection, in the same `BEGIN IMMEDIATE` that inserted the job (store.py:46). `BEGIN IMMEDIATE` serialises every admission of the service, so two tabs or two phones cannot both take the last credit. The new module `backend/src/affiche/posters/credits.py` imports only `text` and `store.Refused`, so `jobs` can import it.

### Order of checks at admission

All inside one `mutate` transaction. **No refusal takes a credit:** the job, its reservation and its key are written together or not at all.

| # | Check | Where | Refusal |
|---|---|---|---|
| 0 | session of an active shop; `X-Affiche-Shop`; bundle | `AccessBoundary` api.py:224-241 | 401 / 409 |
| 1 | key already used: its stored answer; nothing below runs | store.py:47-52 | the stored 202, or 409 `idempotency_reused` |
| 2 | the request itself | visuals.py:233-293, :299-344; typography.py:242-255 | 409 / 422 / 404 |
| 3 | the poster: provider configured, revision, active, one image at a time, twelve scenes, mode lock | jobs.py:82-101 | 503 / 409 |
| 4 | the shop is suspended | `provider_guard` jobs.py:61-62 | 403 `shop_suspended` |
| 5 | the service is paused (admission only), or the cap would be passed | `provider_guard` (D-003) | 429 `budget_exhausted` |
| 6 | the shop's provider day | `provider_guard` jobs.py:66-68 | 429 `shop_daily_limit` |
| 7 | a credit is available | `credits.require` | 402 `no_credit` |

The balance comes last: when the service is paused or the shop's day is over, buying would not help, so the owner is not told to buy.

### The credit's states, one to one with the job's

| Job status | Counted | Shown |
|---|---|---|
| (refused at admission) | no job | the refusal's sentence |
| `queued`, `running` | yes | « en attente » |
| `running → queued` (`recover` requeues an unsent call, jobs.py:297) | yes; the same job, never counted twice | « en attente » |
| `succeeded` | yes: spent; the version exists in the same transaction | the version |
| `failed`, `interrupted`, `cancelled` | no: the credit is back, nothing written | « Votre crédit vous a été rendu. » |

### The same request again

- **A replayed key** (a lost answer, « Reprendre », a second tap that reached the server): the stored 202 is returned before `apply` runs (store.py:47-52), and no job is made.
- **A key whose first delivery was refused** stored nothing (store.py:53-54). Sent again after a grant, it is admitted then: that is its first admission.
- **Two keys on one poster:** `image_job_running` (jobs.py:87-90) and `poster_one_image`. **Two posters, one credit:** serialised; the second gets 402.
- **A sign-out between the tap and the server** (ADR-108): 401 before the handler; no job.

### Failure modes for money, under this model

| Failure | Detection | Behavior |
|---|---|---|
| **Double debit** | — | one admission makes one job; a replay makes none; one image job per poster at a time |
| **Lost or double release** | — | cannot happen: nothing is written when a job ends without an image |
| **Crash before the admission commits** | SQLite journal | nothing written; a resend is a first admission |
| **Crash after it commits** | `recover` at the next start | the job counts; requeued it still counts once; ended without image it stops counting; a spooled result is finalised (spent) |
| **The worker's 429 retry** | worker.py:63-74 | call 2 of the same job; counted once. A retry refused by the cap or the day fails the job: it stops counting |
| **Two tabs, one credit** | `BEGIN IMMEDIATE` | one 202, one 402 |
| **A balance below zero** | `require` at admission; `correct`'s and `move`'s checks | refused in the transaction; no database floor (D-001). The restore's copy replays history and may leave one while a restored generation holds a credit; it reports it (D-005) |
| **A finished job moved back, or `takes_credit` changed** (a bug, a hand edit) | `poster_jobs_final` | the UPDATE fails; in a request, 503 |
| **A later migration rebuilds `poster_jobs` and loses its trigger** | `guard_differences` | the suite fails at its first run; a hand-edited database fails the rehearsal |
| **A job that never ends** | it stays `queued` or `running` | its credit stays « en attente ». Only a broken service keeps a job running: `_pending` retries a failing finalisation each second, for every kind after T-PENDING-KINDS, and a dead process is recovered at the next start |
| **A job ends `interrupted` or `failed` after the provider may have charged** | — | the credit is back; the provider's possible charge stays the service's (owner decision 3). A refused 4xx is recorded at its full reservation today (gateway.py:64-73, worker.py:78), so it counts against the shop's day and the cap at 0.40 USD, probably more than it cost |
| **Failures on purpose** (a photo the provider refuses again and again) | — | each gives the credit back; bounded by the recorded reservations in the shop's day (2.00 USD, about five refused scenes) and by the cap, not by proven charges |
| **A grant or correction typed twice; a restore** | `UNIQUE (shop_id, kind, ref)` | D-005 |

**Edge cases:** a stub image costs 0 dollars and still one credit: credits are a product rule. A poster cannot be abandoned while its image job waits (store.py:334-336).

---

## D-BALANCE-003 — What blocks a generation: the pause, the cap, the shop's day (covers R-BALANCE-005; the server's side of R-BALANCE-004's priority)

### The pause, at admission only

`meta` row `generation_paused` (value: the time it was set; the table is 0001_initial.py:20). `provider_guard` gains a keyword, and `_reserve` passes it from the call's number:
```python
def provider_guard(conn, settings, shop, estimate_micros, *, admission=True):
    if conn.execute(text("SELECT state FROM shop_profile WHERE id=:shop"), {"shop": shop}).scalar() != "active":
        raise Refused("shop_suspended", 403)
    # The operator's pause stops new requests only: a 429 retry of an admitted job is not one (_reserve, call 2).
    if admission and conn.execute(text("SELECT 1 FROM meta WHERE key='generation_paused'")).first() is not None:
        raise Refused("budget_exhausted", 429)
    …the cap (jobs.py:63-64) and the shop's day (jobs.py:66-68), unchanged, for every call…

def _reserve(conn, settings, shop, job_id, call_no, spec: CallSpec):
    provider_guard(conn, settings, shop, spec.estimate_micros, admission=call_no == 1)
```
- **Admission:** `enqueue` reserves call 1 (jobs.py:108-109) for images, plans, styles and text proposals; `reads._admit` calls the guard with the default (reads.py:570).
- **A retry:** `reserve_rate_limit_retry` reserves call 2 (jobs.py:222), so `admission=False`: the pause does not stop it, while the cap and the day still do, as today. The admitted job finishes.
- Admitted jobs that are queued run and settle normally. Nothing is cancelled.

**One code, one true sentence.** The pause reuses `budget_exhausted`. That code is already in the chat's text-back list (ChatView.vue:255), outside its final list (chat.ts:148-151), and in `SPEND_REFUSALS` (jobs.py:25), so no frontend change is needed. The cap stops the same set of requests (reads included, reads.py:570). Its sentence (api.py:113) becomes one that is true for both, and for reads and styles too:

« Le service est en pause : l’IA ne prépare rien de nouveau pour le moment (images, styles, textes, lecture des messages). Vous pouvez encore modifier et télécharger vos affiches. Réessayez plus tard. »

### `blocked`: told before the tap

In jobs.py beside `provider_guard`, read-only (it only SELECTs), **per charged operation, each with its own estimate**:
```python
CHARGED = ("scene", "text_texture")   # a refinement is costed as a scene (call_spec, jobs.py:52-53): one answer for both

def blocked(conn, settings, shop, kind) -> Refused | None:
    """Why this charged operation would be refused now whatever the shop's credits (D-BALANCE-003): the admission's
    own guard with that operation's estimate."""
    try:
        provider_guard(conn, settings, shop, call_spec(settings, kind).estimate_micros)
    except Refused as refused:
        return refused
    return None
```
- `GET /api/balance` asks it once per entry of `CHARGED` and maps each refusal: `budget_exhausted` (pause or cap) and `provider_unavailable` (no image provider configured) give `"service"`; `shop_daily_limit` gives `"day"`. Each answer carries that refusal's own sentence from `MESSAGES`, the one place for sentences (api.py:42-44).
- With 0.35 USD left of the shop's day, `scene` is blocked (estimate 0.40) and `text_texture` is not (0.30). That is the case round 2 found; it now gets its own answer.
- A suspended shop cannot reach the route: its session reads as none.
- The planner's paid calls (estimate 0.10) are not predicted; the server refuses them as today.

### The cap: what changes and what does not

- Unchanged: how a failed call is costed (worker.py:78, jobs.py:201-205), and the cap counted from `SPEND_CAP_SINCE` (admission.py:295-306).
- New: `grant` prints the headroom (D-005).
- Open check for the next paid test: whether the provider bills a refused (4xx) image request (its dashboard against `poster_calls`).
- Owner decision 4: the cap stays cumulative in this design; a monthly cap is an open decision, not a task here.

**Failure modes & handling:**
| Failure | Detection | Behavior |
|---|---|---|
| The pause is set while jobs are queued | — | they run; only new requests are refused |
| A 429 retry while paused | `admission=False` | sent if the cap and the day allow it |
| `blocked` is stale by the time of the tap | the admission's own guard | the server's refusal and its sentence, nothing taken |

---

## D-BALANCE-004 — What a shop reads and is told (covers R-BALANCE-001, R-BALANCE-004, R-BALANCE-007; R-MULTI-SHOP-002)

### API contracts

```
GET /api/balance                      session; X-Affiche-Shop as every route
  200 { "available": int, "pending": int ≥ 0, "purchase_fr": str,
        "blocked": { "scene":        null | { "reason": "service" | "day", "message_fr": str },
                     "text_texture": null | { "reason": "service" | "day", "message_fr": str } } }
  401 unauthenticated · 409 shop_changed · 503 storage_unavailable

  example, 0.35 USD left of the shop's day:
  { "available": 4, "pending": 0, "purchase_fr": "…",
    "blocked": { "scene": { "reason": "day", "message_fr": "La boutique a atteint sa limite d’images pour aujourd’hui. …" },
                 "text_texture": null } }

POST /api/creations/{id}/scenes | /refinements | /text-effects     unchanged, plus:
  402 no_credit    { "error": { "code": "no_credit", "message_fr": "<sentence> <purchase_fr>", "retryable": false }, "request_id": … }

GET /api/jobs/{id}         "usage" removed; "credit": "pending" | "spent" | "given_back" | null   (null: takes_credit = 0)
GET /api/capabilities      scene_estimate_micros, plan_estimate_micros, texture_estimate_micros removed
GET /api/usage             removed (it gave the shop micro-dollars, api.py:482-487)
```
- **`purchase_fr`** is never empty. `credits.purchase_text(conn, settings)` returns `meta.purchase_text_fr` (set by the operator, D-005). Without it, it returns « Pour obtenir des crédits, contactez {SUPPORT_CONTACT_FR}. », else « Pour obtenir des crédits, contactez l’administrateur. ».
- **The 402 sentence** is built in the app's `refusal` handler (api.py:647-649): `MESSAGES["no_credit"] + " " + purchase_text(...)` on a connection of its own. If that read fails, the sentence goes alone and the failure is logged. `402` joins the documented statuses (api.py:469). It is not in the chat's final list, so a refused card keeps its request and « Réessayer ».
- **`credit` in the job view** is a pure function of the job's own row (`takes_credit`, `status`): no query.
- **Stored answers with a dollar field.** A replay returns the body stored in `mutation_keys` (store.py:52), so removing `usage` from `get_job` does not reach an answer stored before.
  - **Every stored answer was checked.** The `mutate` callers return `get_profile`, `get_input`, `get_creation` (store.py:140, :167, :245, :294-351); `get_plan`, `get_visual` (visuals.py:191, :208, :426-433); `{job_id, status_url}` (every 202, jobs.py:110, exports.py:102); `{confirmation_id, download_url}` (exports.py:183); `get_proposal`, `get_effect`, `save_version` (typography.py:225, :237, :288, :295); `get_look` (looks.py:159, :167); and `get_job` from `jobs.cancel` (jobs.py:139).
  - Only `get_job` builds a dollar field (jobs.py:115-121): no other answer holds `micros`, `usage` or `cost`. The chat reads' stored bodies (`chat_reads.response_json`, replayed at reads.py:595) are `reads.build`'s card and draft, which hold none.
  - **Rule:** `jobs.cancel` returns `mutate`'s answer with `usage` removed: `status, body = mutate(…); body.pop("usage", None); return status, body`. That covers both a stored body from before 0014 and a fresh one.
  - A stored body from before keeps its other fields and lacks `credit`; the browser reads `credit` from `GET /api/jobs/{id}`, never from the cancel answer.
  - Tested with a `mutation_keys` row written as the old code wrote it (with `usage.recorded_micros`), replayed through `POST /api/jobs/{id}/cancel` after the migration: no dollar field.
- **Readers of the removed dollar fields, all moved in the task that removes them:**
  - `/api/usage`: test_api.py:100-101, test_typography.py:267, and the smokes at browser_smoke.py:2354, :2492, :2584, :2753 and editor_refinements_browser.py:244. They read `spent_micros` or the operator's `/api/status` instead; the smokes can reach it with a loopback client and Host (api.py:408-417).
  - A job's `usage`: test_poster_jobs.py:440, test_poster_visuals.py:182 and :574. They read `poster_calls` directly.
  - The estimates: test_api.py:97, and the frontend's cost lines (App.vue:15, :628, :1400, :1768, :1770, :1774).
  - No file of frontend/src reads a job's `usage`.

### Sentences (`MESSAGES`, api.py:45-152)

| Code | Status | Sentence |
|---|---|---|
| `no_credit` | 402 | « Il ne vous reste plus de crédit : rien n’a été envoyé, et vos affiches restent disponibles. » then `purchase_fr` |
| `budget_exhausted` | 429 | changed, for the pause and the cap (D-003) |
| `read_limit` | 429 | unchanged |

### Chat reads (R-BALANCE-007)

`DAILY_LIMIT = 100` (reads.py:32, today 200), flat, per shop and UTC day, whatever the balance. Reads do not import credits. The order stays mode lock, `provider_guard`, the daily limit, `reads_busy`.

### Free at zero (R-BALANCE-004)

Only the three image routes look at credits. Opening, editing, approving, the final preview, downloading, copies, styles, text proposals and reads all work at zero.

**Security / data notes:**
- `/api/balance` takes no id: it is always the session's shop.
- `"day"` speaks of the shop's own day. `"service"` speaks of a state every shop is told at its next request anyway.
- `/api/jobs/{id}` reads its job by id and shop (jobs.py:113-114).

---

## D-BALANCE-005 — The operator (covers R-BALANCE-003, R-BALANCE-005, R-BALANCE-006; the seams of R-ADMIN-002 to 005)

Only what is needed before the administration dashboard exists. Each function takes a connection and never commits (shops.py:1-3).

### Functions

| Function | Does |
|---|---|
| `credits.grant(conn, shop, credits, *, origin, ref, actor, note=None, amount_ar=None, method=None) -> int` | `credits ≥ 1`. A bought grant needs `amount_ar > 0` and `method` (lowercased); an offered one neither. The shop's grant with this `ref` already exists → refused, naming the line. **A bought grant whose `ref` any shop already holds** (a bought grant, or any line with an amount, under that reference) → refused, naming the shop and the line, with no option to override: a payment changes shop only by `move` |
| `credits.move(conn, ref, from_shop, to_shop, actor, note) -> tuple[int, int]` | **One atomic move of a payment, in the caller's transaction.** Refused, nothing written, unless all of these hold: `from_shop` ≠ `to_shop`; `from_shop` has the bought grant with this `ref`, and no correction under it yet (not moved or corrected before); `to_shop` holds no line under this `ref`; each other shop's own total under this `ref` is 0 ariary (an earlier move left it at zero); and **`from_shop`'s available balance is at least that grant's credits** (they are still unspent). Then it writes the correction on `from_shop` (−credits, −amount, same `ref`, the note) and the bought grant on `to_shop` (the same credits, amount, method and `ref`). Order matters: the correction first (`credit_grants_payment_total` requires it to bring the source's total to exactly zero), so `credit_grants_one_payment` sees no other shop above zero when the grant comes. Receipts are unchanged by construction: +A, −A, +A. Returns both line ids |
| `credits.correct(conn, shop, credits, *, ref, note, actor, amount_ar=None, job_id=None) -> int` | `note` required; `credits ≠ 0` or an amount. **With `job_id`:** the job must be this shop's (`store._owned`), `succeeded`, `takes_credit = 1`, not repaid yet; `credits = 1` and no amount. **With `amount_ar`** (a mistyped amount fixed): `ref` must be a bought grant of this same shop with no correction yet, `credits = 0`, and **the payment's corrected total in this shop (the sum of `amount_ar` over its lines under that `ref`, this one included) must stay above zero**; `credit_grants_payment_total` holds the same rule. **With `credits < 0`:** refused when `balance + credits < 0`, in this transaction |
| `credits.balance(conn, shop)`, `credits.require(conn, shop)`, `credits.purchase_text(conn, settings)` | D-001, D-002, D-004 |
| `shops.pause(conn)`, `shops.resume(conn)` | `INSERT INTO meta VALUES ('generation_paused', :now) ON CONFLICT DO NOTHING` / `DELETE FROM meta WHERE key='generation_paused'`; returns whether it changed |
| `shops.set_purchase_text(conn, text)` | 1 to 500 characters; `INSERT … ON CONFLICT(key) DO UPDATE` on `meta.purchase_text_fr` |
| `shops.headroom(conn, settings) -> dict` | the cap in micro-USD; `spent_micros(conn, settings)` (admission.py:295); the outstanding credits = the sum over shops of `max(available, 0)`; the unit = the average real cost (`cost_is_estimate = 0`, `provider <> 'stub'`) of the last 50 `succeeded` image calls, else `ESTIMATE_SCENE_USD` |
| `shops.after_restore(live_db: Path, kept_db: Path, *, apply: bool) -> list[str]` | the restore's copy, below |

**What is enforced where, for money:**
- **The database:**
  - per shop, `UNIQUE (shop_id, kind, ref)` and `job_id UNIQUE`; the `CHECK`s; never changed or removed;
  - **across shops, `credit_grants_one_payment`**: a positive amount is refused while another shop's own total for the reference is above zero;
  - **per payment, `credit_grants_payment_total`**: an amount fix keeps the shop's total for that payment above zero, and a reversal brings it to exactly zero.
  - **Together, whatever writes the line:** at most one shop holds a positive total per reference, and none a negative one, so `SUM(amount_ar)` counts each payment once. A move that skips the reversal is refused.
  - **Not guaranteed by the SQL:** that a payment's amount is its true amount (a positive fix raises it on the operator's word), and that a reversal also removes the matching credits (`move` writes both).
  - A service-wide unique index on the reference is not used: it would forbid the move's grant.
- **`grant`:** stricter than the trigger. It refuses a bought reference that any shop holds, even one whose money a correction has set to zero, and sends the operator to `move-payment`.
- **`move`:** the only way a payment changes shop. Its preconditions are listed above, among them "the credits are unspent", which only a balance query can check; it writes both lines in one transaction.
- **`correct`:** a repayment only of a charged job; an amount fix only of the shop's own uncorrected payment, its total kept above zero; no balance below zero.
- **Signed `amount_ar` on a correction has two uses:**
  - the move's reversal (negative);
  - an amount fix of the shop's own payment (either sign, `credits = 0`).
  
  So the `CHECK` stays as in D-001. The fix is kept because R-ADMIN-003 lists payments with their total, and a mistyped amount on a line that can never be edited would otherwise stay wrong for good. It cannot fund another shop: `grant` refuses the reference, and `credit_grants_one_payment` refuses a positive amount elsewhere while this shop's total is above zero, which `credit_grants_payment_total` keeps it.
- **Money received is `SUM(amount_ar)` over all lines.** A moved payment counts once: +A in the source, −A by the move's correction, +A in the destination.

### Commands (`python -m affiche.shops`, added to shops.py:186-213)

```
uv run python -m affiche.shops create <identifier> [--name "…"] [--welcome 5]
        # the shop and its welcome grant in one transaction: offered, ref "welcome", note « Crédits de bienvenue »; 0: none
uv run python -m affiche.shops grant <identifier> <credits> --offered --ref <reference> [--note "…"]
uv run python -m affiche.shops grant <identifier> <credits> --bought --amount-ar <ariary> --method <mvola|orange|airtel|cash|…> --ref <payment reference> [--note "…"]
uv run python -m affiche.shops move-payment <payment reference> <from identifier> <to identifier> --note "<why>"
uv run python -m affiche.shops correct <identifier> <+n|-n> --ref <reference> --note "<reason>" [--job <job id>]
uv run python -m affiche.shops correct <identifier> 0 --ref <its payment reference> --amount-ar <±ariary> --note "<reason>"   # a mistyped amount
uv run python -m affiche.shops pause --yes            # without --yes, only says whether the service is paused
uv run python -m affiche.shops resume
uv run python -m affiche.shops purchase-text "…"      # without a text, prints the current one
uv run python -m affiche.shops after-restore <kept database file> [--apply]   # without --apply, only reports
exit 0 done · 1 refused (one line on stderr, nothing written) · 2 usage
```
- `actor` is `operator`; the dashboard will write its operator's name (R-ADMIN-001).
- `grant` and `correct` print the line written and the shop's balance after it. `grant` also prints the headroom:
  ```
  granted 10 bought credits to originalphone (line 42): available 12, en attente 0
  service cap 15.00 USD: 6.20 spent since 2026-11-01, 8.80 left; credits outstanding in all shops 280 × 0.035 USD (average of the last 50 images) = 9.80 USD
  WARNING: the outstanding credits would cost more than what is left of the cap: raise SPEND_CAP_USD (deploy/README.md)
  ```
  The warning appears only when the cost of the outstanding credits exceeds what is left (here 9.80 > 8.80); at 8.40 it would not.
- A defect repaid (R-BALANCE-001): `correct <identifier> +1 --ref <short reason> --job <job id> --note "<what was wrong>"`.
- **A payment credited to the wrong shop:**
  - `move-payment <ref> <wrong> <right> --note "…"`.
  - When the wrong shop has already spent some of those credits, the move is refused, and the payment stays where it is.
  - If the operator wants the right shop served anyway, that is his concession: `grant <right> <n> --offered --ref <ref>-geste --note "paiement <ref> crédité par erreur à <wrong>"`. It is visible as offered, and counts no money.
  - The runbook says so.
- Not built before the dashboard: `ledger`, and balances in `list`. No task needs them to be verified: `grant` and `correct` print the balance, and the tests read `credits.balance`.

**Welcome credits (R-BALANCE-006):** `create --welcome N`, default 5, in the transaction that creates the shop. Its reference `welcome` makes a second welcome grant to one shop refused.

**The purchase text:** set with `purchase-text` right after the release (the pilot's step 4), so before any invitation. The runbook says it must state the packs, the mobile money number, the reference to write, and **when credits arrive** (the operator's hours).

### Restore: the policy, then the copy (answers Codex r1 P1-2, r3 P2-2, P2-3, P2-5)

**Policy:**
- A restore returns grants, corrections and jobs to the backup's time (backup.py:47-62 copies the whole database; restore.sh puts it back).
- Images made after the backup are gone from the application with their jobs, so they are not charged: that is the service's loss. The operator may write a correction with a reason if he decides otherwise.
- **The operator's lines written since the backup are copied back from the database the restore replaced**, as they were: the same order, the same dates, the same references, actors, notes, amounts and methods. Nothing is typed again: no shell, no lost date, no order to work out by hand.
- **A repayment that named a job depends on that job's state in the restored database:**

  | The job in the restored database | The repayment line |
  |---|---|
  | `succeeded` with `takes_credit = 1` (still charged) | copied |
  | `failed`, `interrupted` or `cancelled` | not copied: it ended without an image there, so its credit is already back |
  | `queued` or `running` | not copied yet: decide after it ends. The next start's `recover` (jobs.py:281-306) requeues or interrupts it; a later run of the copy copies the repayment if the job then succeeded, and skips it if not |
  | absent (made after the backup) | not copied: the restore removed the image and its charge; copying it would give that credit twice |
- **A shop created since the backup** is created again by the operator with `--welcome 0`, then the copy brings its own lines back, its original welcome grant with its original amount included, so a default welcome never replaces a different original one.

**The tool: `python -m affiche.shops after-restore <kept database file> [--apply]`.**
- **(a) Without `--apply` it only reports** what it would copy and skip, and why.
- **(b) With `--apply` it copies, in one write transaction on the live database** (`write_tx`, `BEGIN IMMEDIATE`):
  - **which rows:** every `credit_grants` row of the kept database whose `(shop identifier, kind, ref)` the live database lacks;
  - **in what order:** the kept ledger's global insertion order (`ORDER BY id`), not shop by shop. A chain A→B→C therefore arrives as it happened, whatever the shops' ids;
  - **how:** each row is one plain `INSERT` keeping its original `created_at`, `actor`, `note`, `origin`, `credits`, `amount_ar`, `method`, `ref` and `job_id`, so every `CHECK`, unique key and trigger of D-001 applies to it in order. A move's two rows arrive in their own order by construction: the correction was written first. The rows get new ids in the live table; their order is kept;
  - **if any row is refused** (for example a payment the operator has meanwhile typed into another shop), the whole copy rolls back and the report names that row and the rule.
- **(c) Shops are mapped by identifier, never by id.** While **any** row to copy belongs to a shop the live database lacks, **nothing is copied**. A partial copy could replay a move without its first half, and the next run would then be refused. The report lists each missing shop with the one command to run first, built with `shlex.join` from the argument list (`["python", "-m", "affiche.shops", "create", identifier, "--name", name, "--welcome", "0"]`, `--name` left out when the shop had none), and says « then run after-restore again ». Running again is safe: rows already present are skipped by the match.
- **(d) Repayment rows** (`job_id` set) follow the table above. Each skipped one is listed with its reason.
- **(e) Per shop it prints:**
  - the number of counted images (`takes_credit = 1`, `succeeded`) of the kept database whose job id the live database lacks: « N images made after the backup are gone and are not charged »;
  - any shop whose available balance would be below zero after the copy. This happens when a generation still `queued` or `running` in the restored data holds a credit that a copied move or negative correction took away: it resolves when that generation ends without an image; if it succeeds, the operator decides.
- **(f) The kept file is read through a read-only connection of its own:** `sqlite3.connect(f"{kept.resolve().as_uri()}?mode=ro", uri=True)`, as rehearse.py:81 reads its source. The live database is written through the application's engine. There is no `ATTACH`: SQLite refuses one inside a transaction, and without URI support on the main connection it would take `file:…?mode=ro` as a file name to create.
  - Checked in the scratchpad (SQLite 3.46.1): a kept file is read through its renamed `-wal` (restore.sh:43), a write to it is refused, and SQLite creates a `-shm` beside it (restore.sh:44 had removed the old one). In the container `/data` is writable by the operator service's user.
  - The copy itself was simulated there too: the chain A→B→C with shop ids opposite to its movement order landed in C; ariary totals by month were identical in the kept and the restored-plus-copied ledgers; a rerun copied nothing; `shlex.split(shlex.join(…))` gave back a name holding `"`, a newline and `$(…)` unchanged.
- **When there is nothing to copy:**
  - The kept file is missing (there was no database before the restore, restore.sh:42) or unreadable: exit 1, and it says that the loss policy applies and that the operator works from his payment records.
  - The kept database is **older than 0014**: it has no `credit_grants` table, so nothing was ever granted there and there is nothing to copy. It says so and exits 0.
- **In restore.sh:**
  - After the shops list (restore.sh:62-64) it runs the report: `op python -m affiche.shops after-restore "$BEFORE" || echo "…from your payment records."`. A failure of this read-only step does not fail the restore.
  - The closing list (restore.sh:66-69) says: create each missing shop with the command the report printed; then run `after-restore <that file> --apply`, with the file's path printed; then `pause`/`purchase-text` if they were set since. It no longer lists grants or corrections to type.
  - deploy/README.md "Restore" step 4 says the same.
- **Residual, existing:** the provider spend recorded after the backup is lost with it, so the cap sees less than was spent until `SPEND_CAP_SINCE` or `SPEND_CAP_USD` is adjusted. Said in the runbook.

**Failure modes & handling:**
| Failure | Detection | Behavior |
|---|---|---|
| A grant typed twice | the reference check, then `UNIQUE` | exit 1, the existing line named |
| A payment typed for a second shop | `grant`'s check, then `credit_grants_one_payment` | exit 1, naming the shop that holds it and pointing to `move-payment` |
| A payment moved while the source has spent part of its credits | `move`'s balance check | exit 1, nothing written; the payment stays; the concession is an offered grant (above) |
| A payment moved back to a shop that held it before, or moved after its amount was fixed in the source | `move`'s checks, then `UNIQUE (shop_id, kind, ref)` | exit 1 (a move on to a third shop is allowed: the first shop's total is 0). An amount fix and a move of the same payment: move first, then fix the amount in the destination |
| An amount fix that would erase or negate a payment | `correct`'s check, then `credit_grants_payment_total` | exit 1, nothing written |
| The restore's copy meets a missing shop, a refused row, or a balance below zero | `after-restore` (D-005, the copy) | nothing copied while a shop is missing; one refused row rolls the copy back and is named; a balance below zero is reported with its reason |
| A move whose two writes are interrupted | one transaction (the command's `write_tx`) | both lines or neither |
| A repayment of a failed job, or a second one | `correct`'s check, then `job_id UNIQUE` | exit 1 |
| A correction below zero | `correct`'s check | exit 1 |
| Database not at head; the API holds the lock | shops.py:224-229; busy_timeout | exit 1 (existing) |

### The pilot's opening balance (owner decision 1, decided)

**Decided by the owner on 2026-11-16, in his words: « grant by hand, 30 credits ».** The pilot gets 30 offered credits, typed by the operator right after the release. 0014 grants nothing.

**Why there is a minute at zero.** release.sh as it is has no moment between the migration and the traffic. The new container migrates at start and serves at once (`up -d --wait`, release.sh:85). Before it, the database is at 0013 and the operator command refuses an old schema (shops.py:224-229). So the pilot is served at zero from the moment `up` answers until the grant is typed: a minute or two.

**The release steps for the pilot** (added to the release's user steps, deploy/README.md):
1. **Before the release, warn the pilot**, in his language, for example: « Ce soir vers <heure>, Doka Studio est mis à jour. Pendant une ou deux minutes après la mise à jour, l’application peut dire qu’il ne reste plus de crédit : rien n’est envoyé ni perdu. Attendez mon message « C’est prêt » avant de créer une affiche. »
2. Run the release as usual (pyinfra).
3. **As soon as it ends**, on mx1, inside the running container (the pattern of deploy/README.md "Shops"):
   ```bash
   sudo docker exec -it affiche-ia-affiche-ia-1 python -m affiche.shops grant originalphone 30 --offered --ref pilot-opening --note "Solde d’ouverture du pilote"
   ```
   It prints `granted 30 offered credits to originalphone (line 1): available 30, en attente 0` and the cap's headroom. Typed twice, the second is refused by its reference: nothing doubles.
4. Set the purchase text: `sudo docker exec -it affiche-ia-affiche-ia-1 python -m affiche.shops purchase-text "…"`. It states the packs, the mobile money number, the reference to write, and when credits arrive.
5. Tell the pilot « C’est prêt ».

**What the pilot sees in that minute:**
- Any button that makes a new image request opens the dialog « Plus de crédit », with « Il ne vous reste plus de crédit : rien ne sera envoyé. Vos affiches restent disponibles. » and the purchase text. Before step 4 that text is the fallback: « Pour obtenir des crédits, contactez {SUPPORT_CONTACT_FR}. », or « … contactez l’administrateur. ».
- A paid chat card shows that text instead of « Créer l’affiche ».
- A request already on its way gets the 402 sentence.
- Nothing is sent and nothing is paid. Editing, « Mes affiches », the final preview and downloads all work.
- After the grant, the balance is read again at the next dialog or when the page is shown again: « 1 crédit · il vous en reste 30 ».

**Not chosen:**
- **The grant inside 0014**, conditioned on shop 1 having posters (v2's option B). It is the owner's choice against it; it would also have frozen the number in a forward-only file.
- **A new release.sh step** between the backup and `up`. It adds a failure path after the stop, with the database migrated.

---

## D-BALANCE-006 — The browser (covers R-BALANCE-001, R-BALANCE-002 display, R-BALANCE-004)

**The balance** (`GET /api/balance`) is read:
- on its own when the shop's page loads, not inside App.vue:858's `Promise.all`, so its failure does not stop the page;
- when an image dialog opens;
- after each 202 of an image request (App.vue:1108-1122, :1131-1138, the text effect, the chat's `replay` ChatView.vue:324-335);
- when a followed job ends (`poll`, App.vue:1190);
- when the page becomes visible again.

Unread or failed, it is **unknown**, never 0 (R-SHOP-DASH-004).

**Every button that makes a new image request** follows the server's order, reading **its own entry** of `blocked`. Only new requests are gated (replays: below):
- `blocked.scene`: askScene (App.vue:629-633), askRefine (:638-641), « Nouvelle version » (:1840), the small line under « Ajuster la scène » (:1774), and every paid chat card (a recap is a scene; a change card makes a scene or a refinement; the chat's cost line App.vue:1400, shown at ChatView.vue:536).
- `blocked.text_texture`: askEffect (:646-649) and its small line (:1770).

| State | Condition | Says | Button |
|---|---|---|---|
| blocked | its entry of `blocked` is set | that entry's `message_fr`; no purchase text | « Fermer » only |
| zero | `available ≤ 0` | « Il ne vous reste plus de crédit : rien ne sera envoyé. Vos affiches restent disponibles. » and `purchase_fr` | « Fermer » only: nothing is sent |
| bientôt à court | `1 ≤ available ≤ 3` | « 1 crédit · il vous en reste {available} » (« , {pending} en attente » when `pending > 0`), then « Bientôt à court : » and `purchase_fr` | as today |
| normal | `available ≥ 4` | « 1 crédit · il vous en reste {available} » (+ « en attente ») | as today |
| unknown | not read | « 1 crédit · solde indisponible pour le moment » | as today: the server decides |

- **The chat.** A recap or change card that has not been tapped yet and would cost a credit shows `blocked.scene.message_fr`, or `purchase_fr` at zero, in place of its button. A free price change is unchanged.
- **Replays are never gated.** « Reprendre » and « Réessayer » send again the card's stored request with its own key (ChatView.vue:324-335, `replay`); the two differ only by the card's state (chat.ts:249). They stay offered at zero credits and while `blocked` is set, whatever the balance answer says.
  - The server decides: a request it already admitted gets its stored 202 back before any admission check (store.py:47-52), so a request that took the shop's last credit and lost its answer is still followed.
  - A request it never admitted is a first admission, refused, if it must be, with its own sentence (402, 429).
  - Under both buttons: « 1 crédit, une seule fois pour cette demande ».
- **The two Claude calls** (App.vue:634-637, :642-645, :1768) say « Sans crédit. ». `dollars` (App.vue:800), `costLine` (:628) and the estimate fields (:15) are removed.
- **A job that ended without an image:** the sentence « Votre crédit vous a été rendu. » is appended in the common terminal branch (App.vue:1250-1251), after whichever sentence it chose, when the job's `credit` is `given_back`. That branch handles `failed`, `interrupted` and `cancelled`; `interrupted` and a failed style take their own sentence there and never reach `jobFailure` (App.vue:805-811), so appending inside `jobFailure` would miss them.
- **A 402 on a race:** the sentence; the balance is read again.
- **`BUNDLE`** stays 3 (api.py:173, api.ts:27). No bundle 3 was ever deployed (the pilot runs bundle 2), so no open tab can show the old dollar lines against this server. If a bundle-3 build is deployed before T-BALANCE-006, raise it to 4 there.

---

## Seams for the two dashboards (their screens are not built here)

| Need | Requirement | Seam | Built here |
|---|---|---|---|
| Credits available and waiting; what blocks each charged operation | R-SHOP-DASH-001, R-ADMIN-002 | `credits.balance`, `jobs.blocked(…, kind)`; `GET /api/balance` | yes |
| The history, newest first, **returned credits included** | R-SHOP-DASH-002, R-ADMIN-002 | `credits.history(conn, shop, *, before=None, limit=50)`: one `UNION ALL` of the shop's `credit_grants` lines and **every** job of the shop with `takes_credit = 1`, whatever its end. Each job brings its admission time (`created_at`), its final time (`finished_at`, NULL while it waits or runs), its status and so its `credit` (`pending`, `spent`, `given_back`), its poster (`creation_id`) and its version (`result_ref` once succeeded). A returned credit is shown and explained by its job's end. **Only the balance filters by status** (D-001) | specified here; built with the shop dashboard, which decides its route and shape |
| Grant, move a payment, correct | R-ADMIN-003 | `credits.grant`, `credits.move`, `credits.correct` in the caller's transaction | yes |
| Payments by period; ariary received; credits spent | R-ADMIN-003, 004 | `SUM(amount_ar)` over `credit_grants` by `created_at`; counted `succeeded` jobs | no |
| What the credit of a job is doing | R-ADMIN-005 | the job view's `credit` | yes |
| The service's stop switch; one shop's | R-ADMIN-005 | `shops.pause`/`resume`; `shops.suspend`/`enable` | yes |
| Welcome credits, read limit, purchase text | R-ADMIN-006 | `--welcome`, `reads.DAILY_LIMIT`, `meta.purchase_text_fr` | as an option, a constant and a `meta` key; the purchase text is already in the database |

## Security and isolation

- A shop reads only its own balance (the session's shop) and its own job's `credit`. No route takes a credit line's id. The operator's functions have no route in this feature.
- **test_two_shops.py:**
  - `("GET", "/api/balance")` joins `OWN` and `("GET", "/api/usage")` leaves it (test_two_shops.py:33-34).
  - The usage block (test_two_shops.py:298-310) becomes: A's grant and A's image change A's balance only; B at zero gets 402 while A has credits; A's balance is unchanged; B's `GET /api/jobs/{A's job}` stays 404.
  - The coverage assertion (test_two_shops.py:341-343) then holds.
- **No dollar figure in any answer to a shop after T-BALANCE-006, proved at the API.** test_two_shops.py already sends every route of the schema (its coverage assertion). Every JSON answer either shop receives is walked recursively, and no key may contain `micros`, `usage`, `cost`, `estimate` or `usd`. A pre-0014 cancellation key replayed (D-004) is part of the walk. `/api/status` is the operator's (404 to shops) and is excluded by name. The page itself is not the proof.

## Release gate addition

- The rehearsal runs 0014 with 0013 when both are pending: `PRESERVED` for `poster_jobs`, `ADDED` as in D-001 (no grant: `credit_grants` empty).
- **Every rehearsal from now on prints and checks the guards**, pending migrations or not.
- User steps added:
  - before the release, warn the pilot; right after it, the pilot's opening grant and the purchase text (stating when credits arrive), exactly as in D-005 "The pilot's opening balance";
  - at each grant, the operator reads its headroom line, and raises the cap when it warns.

## Tests

- **Schema and guards** (new tests/test_credits.py, on the `engine` fixture of test_db.py:30-35):
  - each refusal of the rule table;
  - `UNIQUE (shop_id, kind, ref)` allowing a grant and its correction to share a reference, and allowing another shop to use it;
  - `credit_grants_one_payment`: a second shop's positive amount for a counted reference refused; the reversal then the grant passing; a positive amount fix in the same shop passing; an offered grant under the same reference passing; **with one shop's total forced negative (written with `credit_grants_payment_total` dropped, as no real path can), a third shop's grant still refused while another shop's total is positive**;
  - `credit_grants_payment_total`: on a 1,000 Ar payment, fixes of −1,000 and −2,000 refused, −400 accepted; a partial reversal refused; an amount fix in a shop whose payment was moved away refused; a correction with an amount and no payment refused;
  - `poster_jobs_final`: `running → queued` allowed, every final → other status refused, a change of `takes_credit` refused, the same final status written again allowed;
  - `balance` over every job state;
  - `guard_differences` empty on a fresh database.
- **Rehearsal** (test_db.py): 0014 on the 0012 pilot fixture is OK, with `ADDED` (no grant) and seven guard lines (six objects of `GUARDS`, one column of `GUARDED_COLUMNS`); the guard regressions (a) to (d) of D-001.
- **Admission** (test_poster_jobs.py):
  - `takes_credit` is 1 for the three image kinds and 0 for the others;
  - a refusal at each of checks 3 to 7 leaves no job, no call, no key;
  - 402 at zero;
  - the order: cap reached and zero credits gives `budget_exhausted`; day reached and zero gives `shop_daily_limit`;
  - two concurrent admissions with one credit (the threads of test_poster_jobs.py:100-116) give one 202 and one 402;
  - a replayed key makes one job;
  - **an accepted request that took the shop's last credit, replayed with its key at zero:** the stored 202 with the same job, no second job, no 402 (store.py:47-52 answers before any admission check);
  - each way a job ends without an image (`fail` failed and ambiguous, owner cancel, suspension, `dispatch` cutoff, `recover`'s branches) gives the credit back; `succeeded` keeps it; a requeue keeps it counted once; a job inserted with `takes_credit = 0` never counts.
- **Pause and blocked** (test_poster_jobs.py, test_reads.py, test_api.py):
  - paused: `budget_exhausted` for a scene, a plan, a look, a text proposal and a read; `resume` lifts it;
  - **a 429 retry while paused is reserved and sent** (call 2 written, the job goes on), while a retry refused by the cap or the day still fails the job at cost 0 (the existing parametrised test, test_poster_jobs.py:263);
  - `GET /api/balance` gives, for `scene` and for `text_texture`, `service` (paused; cap reached), `day` (the shop's day reached) or `null`, each with its own `message_fr`. With 0.35 USD left of the shop's day (set as test_poster_jobs.py:223-241 does, with the ceiling setting and an admitted reservation), `scene` is `day` and `text_texture` is `null`, and a text material is admitted.
- **API** (test_api.py):
  - `GET /api/balance`; the 402 body; `/api/usage` 404 (the assertions at test_api.py:100-101 move to `spent_micros`); capabilities without estimates; the job view with `credit` and without `usage`; `no_credit` has a sentence.
  - **A cancellation answered before 0014:** a `mutation_keys` row for `POST /api/jobs/{id}/cancel` whose stored body holds `usage.recorded_micros`, as the old code wrote it, replayed after the migration: 200, the same fields, and no `usage`.
- **Reads** (test_reads.py): the 100th read of the day passes, the 101st is refused, whatever the balance.
- **Operator** (test_shops.py):
  - `create --welcome` (5, 0, one transaction with the shop);
  - `grant` offered and bought; typed twice refused; **a bought reference held by any other shop refused**, with no option;
  - **`move-payment`:**
    - with the credits unspent: both lines in one transaction, the source's balance down by the grant's credits, the destination's up, `SUM(amount_ar)` unchanged;
    - refused when the source has spent part of them, when the source has no such grant, when it was already moved or its amount fixed, when the destination already holds the reference, and from a shop to itself;
    - a fault injected between the two writes leaves neither;
  - `correct`: a repayment of a succeeded charged job; refused for a failed job, a job of another shop, a second time, or other than +1; an amount fix of the shop's own payment (credits 0) accepted while its total stays positive, refused when it would erase or negate it, of another reference refused; below zero refused;
  - `pause`/`resume`, `purchase-text`;
  - `headroom` with history and without (falling back to the estimate), and its warning.
- **Restore copy** (test_shops.py, `after-restore` on a kept and a restored database built by the tests):
  - without `--apply`: the report, and nothing written to the live database;
  - **a chain A→B→C whose shop ids oppose its movement order** (A created last): after the copy the payment's money is in C only, and `SUM(amount_ar)` is unchanged;
  - **the ariary totals by month of `created_at` are identical** in the kept ledger and in the live ledger after the copy, and every copied row keeps its original `created_at`, actor and note;
  - **a rerun copies nothing**;
  - **a shop missing then created:** the first run copies nothing and prints its one command; after `create … --welcome 0`, a rerun copies its lines, its original welcome amount included;
  - **each repayment class:** `succeeded` and charged → copied; `failed` → skipped with its reason; `running` → skipped as "decide after it ends", then copied by a rerun once the job has succeeded; absent → skipped;
  - **a refused row** (the payment meanwhile typed into another shop) → nothing copied, the row named;
  - **the printed command for a shop named `Chez "Rado"`, a newline and `$(touch pwned)`:** `shlex.split` of the printed line gives back the exact argument list; the command is never executed, and no file `pwned` exists;
  - a balance below zero after the copy is reported; the count of lost images;
  - a missing kept file → exit 1 and the policy sentence; a kept file older than 0014 → exit 0, « nothing to copy ».
- **Restore script** (test_restore_script.py): the `after-restore` report with `$BEFORE`; a failure of it does not fail the restore; the closing lines (create the missing shops, then `after-restore … --apply`).
- **Isolation and no dollars:** test_two_shops.py as above, with its walk of every route checking that no key of any answer names a dollar figure (Security).
- **Vitest:** the five display states as a pure function of (balance, its entry of `blocked`, unknown); a texture button not blocked while scenes are; blocked before zero; zero and blocked send nothing; the chat card at zero and when blocked; **« Reprendre » and « Réessayer » offered at zero and while blocked**; a free price change unchanged; the returned-credit sentence after `failed`, `interrupted` and `cancelled` with `given_back`.
- **Browser smoke (stub, zero spend), `walk_credits`, at 360 px in both themes:**
  - shop 1 with 5 credits makes a poster: « il vous en reste 5 », then « Bientôt à court » with the purchase text at 3;
  - `STUB_FAIL=refused`: the credit is back, with « Votre crédit vous a été rendu. »;
  - paused (`meta` row set from the test): the dialog shows the pause sentence and no purchase text;
  - at 0: the purchase text, and no `/scenes` request in the log;
  - **a paid chat card that took the last credit, its answer lost** (the route answer dropped once): at 0, « Reprendre » is offered and succeeds, and the poster follows the same job;
  - editing and downloads work at 0; no « $ » or « USD » on any screen (a check of the screens; the API walk is the proof);
  - chat_browser.py's « Mode de démonstration » assertions (chat_browser.py:158, :396, :500, :534, :568, :653, :754, :1808) become the credit line.
- **Not proven here:** 0014 on SQLite 3.40.1 (the gate); the pilot's real database; a real phone; whether the provider bills a refused 4xx.

## Tasks

Seven tasks, each one session, each leaving the whole suite and the smokes runnable at its end. From `backend/` unless said; frontend commands on Linux are `corepack npm@10 …` (AGENTS.md).

0. **T-PENDING-KINDS — a spooled result of any kind is finalised by the running service.** A live bug, apart from credits:
   - `PosterService._pending` (service.py:187-191) loses `AND kind IN ('plan','scene','refine')`.
   - `recover`'s ready list goes to `app.state.pending_finalisations` (api.py:453), which nothing reads. It is removed if no test reads it (grep: none today).
   - Tests: a spooled `text_texture`, `text_patch` and `render` whose first finalisation failed are finalised by the serve loop, and no provider is called (a stub that fails the test if called).

   Verify: `uv run pytest tests/test_poster_jobs.py tests/test_poster_visuals.py tests/test_typography.py tests/test_exports.py -q` → all passed; `uv run pytest -q` → all passed.
1. **T-BALANCE-001 — The schema, the module, the permanent guards.**
   - 0014 (the column, the table, five triggers; no grant), with `PRESERVED`/`ADDED`.
   - `posters/credits.py`: `balance`, `require`, `grant`, `move`, `correct`, `purchase_text`.
   - `rehearse.GUARDS`, `GUARDED_COLUMNS`, `guard_differences`, checked after every rehearsal.
   - test_credits.py; test_db.py's guard regressions.
   - Nothing calls the module yet; the suite is otherwise unchanged.

   Verify: `uv run pytest tests/test_credits.py tests/test_db.py -q` → all passed; `uv run python -m affiche.rehearse data-probe/affiche.db` → `REHEARSAL OK` with the `0014 ADDED … as expected` lines and seven `guard … as expected` lines; `uv run pytest -q` → all passed.
2. **T-BALANCE-002 — Admission takes a credit; 402; every fixture funded.**
   - `takes_credit` in `enqueue`, and `require` after `_reserve`.
   - The 402 with its sentence and purchase text; `402` in the documented statuses.
   - **Fixtures funded** (100 offered credits, ref `tests`, through one helper `credited(engine, shop=1)` in test_db.py):
     - the `engine` fixture (test_db.py:30-35), for shop 1, used by test_poster_jobs, test_poster_visuals, test_exports, test_typography, test_reads, test_editor_refinements, test_looks and test_poster_drafts;
     - the API `client` fixture (test_api.py:56-59), through `create_app(settings, prepare=…)` (api.py:437-439);
     - `second_shop` (test_api.py:376-381), so every second shop (test_poster_jobs.py:182, :226, :302, :368; test_two_shops.py:84; test_reads.py:505, :583; test_shops.py:76, :101, :202) starts funded;
     - the smokes' `serve` (browser_smoke.py:1954-1960, also used by chat_browser.py and editor_refinements_browser.py), through `prepare`.
   - **Modules whose image admissions then run on funded fixtures (nine, by grep):** test_api.py (:227), test_editor_refinements.py (:61, :123, :160), test_exports.py, test_looks.py (:102, :112), test_poster_jobs.py (helper `enqueue`, :39), test_poster_visuals.py (helper `scene`, :31; HTTP :258), test_reads.py (:1078), test_two_shops.py (:105, :122), test_typography.py (:180, :184). Not needed: test_admission.py:609 enqueues a `render`; test_db.py:161 inserts job rows directly, and they never count.
   - The admission tests of "Tests".

   Verify: `uv run pytest tests/test_poster_jobs.py tests/test_credits.py tests/test_api.py tests/test_two_shops.py -q` → all passed; `uv run pytest -q` → all passed; `uv run python ../frontend/tests/browser_smoke.py` and `uv run python ../frontend/tests/chat_browser.py` → pass (screens unchanged).
3. **T-BALANCE-003 — What blocks, and what a shop reads.**
   - The pause in `provider_guard` (admission only); the `budget_exhausted` sentence; `jobs.blocked(…, kind)` for `scene` and `text_texture`.
   - `GET /api/balance`; `/api/usage` removed, its readers moved (test_api.py:100-101; test_typography.py:267; browser_smoke.py:2354, :2492, :2584, :2753; editor_refinements_browser.py:244).
   - `DAILY_LIMIT = 100`.
   - test_two_shops.py's `OWN` and usage block.
   - backend/api/README.md: the `/api/usage` row removed, `/api/balance` and the 402 added.

   Verify: `uv run pytest tests/test_api.py tests/test_reads.py tests/test_poster_jobs.py tests/test_two_shops.py -q` → pass; the mutation script of T-MULTI-SHOP-003 in the scratchpad → test_two_shops fails; `uv run pytest -q` → all passed; both smokes → pass.
4. **T-BALANCE-004 — The operator's commands.**
   - `shops grant` (refusing a bought reference held in any shop; the headroom), `move-payment`, `correct` (repayment, amount fix), `create --welcome`, `pause`/`resume`, `purchase-text`.
   - deploy/README.md: "Shops" (each command; a payment credited to the wrong shop; the concession when its credits are spent); the release steps (the pilot's warning, grant and purchase text, D-005; reading the headroom); phone sessions grant with the command on `data-probe`.
   - backend/api/README.md's command line (:11) and AGENTS.md's command table.

   Verify: `uv run pytest tests/test_shops.py tests/test_credits.py -q` → pass; `uv run pytest -q` → all passed.
5. **T-BALANCE-005 — The restore reconciliation: a copy, not commands.**
   - `shops after-restore <kept file> [--apply]`: the kept file read-only through its own connection; the report; with `--apply` one transaction copying the missing `credit_grants` rows in the kept ledger's global order with their original dates; shops mapped by identifier, nothing copied while one is missing, its one command built with `shlex.join`; repayments by the restored job's state; lost images; balances below zero.
   - restore.sh's report after the shops list and its closing lines; test_restore_script.py.
   - deploy/README.md "Restore" step 4.

   Verify: `uv run pytest tests/test_shops.py tests/test_restore_script.py -q` → pass; `sh -n ../deploy/restore.sh` → no output; `uv run pytest -q` → all passed.
6. **T-BALANCE-006 — The browser, and the last dollars.**
   - The balance reads, the five display states with each button's own entry of `blocked`, the chat cards (only new requests gated; « Reprendre » and « Réessayer » never), « Sans crédit. », the returned-credit sentence in the common terminal branch (App.vue:1250-1251).
   - The estimates out of `/api/capabilities` (and test_api.py:97); `usage` out of the job view and `credit` in it (test_poster_jobs.py:440, test_poster_visuals.py:182, :574 read `poster_calls` directly); `jobs.cancel` drops `usage` from a stored answer, with its replay test.
   - test_two_shops.py's walk of every answer for dollar keys.
   - Vitest; `walk_credits`; chat_browser.py's credit lines.
   - Removing the estimates before this task would make today's frontend say « Mode de démonstration : aucune dépense. » against a paid provider, so they leave here.

   Verify: `cd ../frontend && corepack npm@10 test && corepack npm@10 run build` → pass; `uv run python ../frontend/tests/browser_smoke.py`, `uv run python ../frontend/tests/chat_browser.py`, `uv run python ../frontend/tests/editor_refinements_browser.py` → pass; `uv run pytest -q` → all passed.

**What the code reviews check:**
- T-001: the `GUARDS` texts equal 0014's; the guards checked when nothing is pending; the `COALESCE` around the rule; `move` writes the correction before the grant. **Round-3 fix 1:** `credit_grants_one_payment` tests each other shop's total apart (`GROUP BY shop_id HAVING`); `credit_grants_payment_total` and `correct`'s positive-total check; the trigger tests with a negative total in one shop.
- T-002: `takes_credit` written only by `enqueue`; `require` after `_reserve` in the same `mutate`; no write when a job ends. **Round-3 fix 4 (server side):** the replay of an admitted request at zero returns its stored 202.
- T-003: `admission=call_no == 1` and the retry test; `blocked` asked with each operation's own estimate. **Round-3 P3:** test_api.py:100-101 no longer reads `/api/usage`.
- T-004: no override of `grant`'s payment rule; `move-payment` in one `write_tx`; the repayment and amount-fix rules. **Round-3 P3:** the headroom example and its warning agree (9.80 > 8.80).
- T-005: **round-3 fixes 2, 3 and 5:** the copy in the kept ledger's global order, with original dates, in one transaction; shops mapped by identifier and nothing copied while one is missing; the one printed command built with `shlex.join` and never executed; the kept file read-only; repayments by the restored job's state; no command line printed for an operator to type except that one.
- **T-006: no dollar figure left in any answer to a shop**, proved by the walk of every route, stored answers included. **Round-3 fix 4:** only new requests gated, both replay buttons offered at zero and while blocked, with its browser test. **Round-3 P3:** the returned-credit sentence in the common terminal branch (App.vue:1250-1251), so `interrupted` gets it.

**The riskiest task is T-BALANCE-002**: the fixtures of nine modules and the smokes, on shops that now start at zero. De-risked by funding at the four fixtures rather than in each test, and by both smokes run before the task is called done.

## Not built, on purpose

- **Ledger design:** debit and release lines; a stored balance; "offered spent first"; a service-wide unique index on the payment reference (it would forbid the move's grant: `credit_grants_one_payment` holds the rule instead); a free-form move or a money-only reversal (v2), replaced by `move`; a database floor under the balance (D-001).
- **Out of scope** (R-BALANCE-006): packs, prices, receipts, online payment, subscriptions, expiry, refunds in money.
- **No credit** for plans, looks, text proposals or reads.
- **Not a lighter switch:** a per-shop "stop images, keep editing" switch (decision 6).
- **Left to the dashboards and to later designs:**
  - automatic defect repayment (decision 8);
  - a monthly cap (decision 4);
  - the commands `ledger` and `list` with balances, and the history route;
  - the header balance pill (R-SHOP-DASH-001); the operator's audit table (R-ADMIN-001);
  - checking the guards at every start of the service: the suite and the rehearsal cover the migrations and the release.

## Traceability

| Requirement | Design |
|---|---|
| R-BALANCE-001 | D-002 (which jobs take a credit), D-004 (no dollars), D-006 (« 1 crédit » and what is left), D-005 (a defect repaid) |
| R-BALANCE-002 | D-001 (the job is the debit; `poster_jobs_final`), D-002 (counted in the admission transaction, states one to one, replay), D-006 (« en attente », credit back) |
| R-BALANCE-003 | D-001 (the operator's lines, never changed or removed; one payment in one shop; jobs never deleted), D-005 (references, money received, `move-payment`, restore policy and tool), Seams (the history with returned credits) |
| R-BALANCE-004 | D-002 (402 last), D-003 (blocked first), D-004 (sentence, purchase text, free at zero), D-006 (nothing sent at zero or blocked; « bientôt à court ») |
| R-BALANCE-005 | D-003 (the pause at admission; cap; day), D-005 (`pause`/`resume`, headroom; suspension for one shop) |
| R-BALANCE-006 | D-001 (`origin` label), D-005 (welcome credits) |
| R-BALANCE-007 | D-004 (flat 100) |

## Wording of the requirements this design asks for

**R-BALANCE-001**
- Replace « Every paid button says « 1 crédit » and shows what is left; the provider's cost in dollars is not shown to a shop. » with « Every button that makes an image says « 1 crédit » and shows what is left; a button that costs no credit says so. No dollar figure reaches a shop. »
- Add (owner decision 2): « The material of a text (« Générer la matière du texte ») is an image and costs one credit. »

**R-BALANCE-002**
- Replace « A generation that ends with no image and a known failure gives the credit back. » with « A generation that ends with no image gives the credit back at once, also when the provider's outcome is unknown; what the provider may have charged stays the service's cost. »
- Replace « While the outcome is not known, the credit is shown as « en attente », apart from what is available; it is settled when the outcome is known, and never debited a second time when the job is recovered. » with « While the generation waits or runs, its credit is shown as « en attente », apart from what is available. It is spent when the version arrives and given back when the generation ends without one; it is never taken a second time when the job is recovered. »

**R-BALANCE-003**
- Replace the first bullet with « Every grant and correction is a line that is never edited or removed: who, when, how many, why, the payment it answers (a correction may carry a signed amount), and for a correction its reason. Each generation is its own record: it holds its credit while it waits, runs or has made its image, and gives it back by ending without one; no generation is ever deleted. »
- Replace « The balance is the sum of the lines. Restoring a backup cannot grant twice. » with « The balance is the sum of the lines minus the generations that hold a credit. A grant or correction carries a reference its shop cannot use twice, so one typed twice, or brought back twice after a restore, is refused. A restore returns grants and generations to the backup's time; images made after it are gone and not charged; the grants and corrections made since are copied back from the database the restore replaced, in their order and with their dates. »
- Add: « Money received is the sum of the amounts of the lines: a payment moved from one shop to another is counted once. »

**R-BALANCE-004**
- Add: « Before the tap, the button says what blocks: a paused service or the shop's day reached come before the lack of credit. A shop with three credits or fewer is shown how to buy. « Reprendre » and « Réessayer » are not new requests: they stay available at zero and while blocked, and the server answers what it stored or refuses with its own sentence. »

**R-BALANCE-005**
- Add: « A shop's daily ceiling of provider spend (multi-shop) can also refuse a generation while credits are left; it says « Réessayez demain » and takes no credit. »
- Replace « The operator can stop new generations for the whole service, or for one shop, at once. » with « The operator can stop new requests to the AI for the whole service at once (images, styles, text proposals, reading messages); requests already admitted finish. One shop is stopped by suspending it, which also stops its sign-in. »

**R-BALANCE-006**
- Replace « Offered credits are spent first. **Default:** credits do not expire. » with « Which credits a generation used is not recorded; it can be computed from the lines if an expiry or a refund in money is ever built. **Default:** credits do not expire. »

**R-BALANCE-007**
- Replace « **Default:** 100 a day with credits left, 20 a day at zero. » with « **Default:** 100 a day per shop, whatever its balance. A lower limit for a shop with no credit waits for self-service sign-up (Phase 2). »

**For the administration requirements (devil's advocate 4):** R-ADMIN-003 adds « Granting credits is usable at 360 px on a phone. »

## Decisions only the owner can take

Decision 1 is the owner's. The others are **in force on their recommended defaults** under the autonomy grant (ADR-106); the owner can still change each one before the task named in the last column is built.

| # | Decision | In force | Changeable until |
|---|---|---|---|
| 1 | The pilot's opening balance | **Decided by the owner, 2026-11-16: « grant by hand, 30 credits ».** 30 offered credits, typed by the operator right after the release; 0014 grants nothing; the pilot is warned first and sees a minute or two at zero (D-005) | — |
| 2 | Does a text material (« Générer la matière du texte », about three quarters of a scene's estimate) cost a credit? It amends ADR-107's "textures … no credit" | Default in force: yes, one credit | T-BALANCE-002 (`takes_credit` for `IMAGE_KINDS`) |
| 3 | Every generation that ends without an image, `interrupted` included, gives its credit back at once. **Cost, as it is:** the service pays whatever the provider charged for those calls. The shop's day and the cap bound only the **recorded reservations and estimates**, not proven charges. A refused 4xx is recorded at its full 0.40 USD reservation (worker.py:78), which probably over-counts it and fills the shop's day after about five refusals | Default in force: yes; whether a refused 4xx is billed is checked at the next paid test | T-BALANCE-001 (the balance's status filter) |
| 4 | The service cap: cumulative from `SPEND_CAP_SINCE`, or monthly | **Stays cumulative in this design.** `grant` prints the headroom so the operator raises the cap in time. A monthly cap is an **open decision, not a task here**. It would need: `spent_micros` counting the service cap from the later of `SPEND_CAP_SINCE` and the first instant of the current UTC month (admission.py:295-306), its tests, the runbook's cap section, and an amendment of R-BALANCE-005 | — (its own requirement and task if chosen) |
| 5 | The purchase text (packs, mobile money number, reference, when credits arrive) and the first price | Default in force: written by the operator with `purchase-text` right after the release (D-005, step 4); until then the fallback names the support contact | T-BALANCE-004 (`purchase-text`) |
| 6 | One shop is stopped by suspension only. Suspension also stops its sign-in, so the shop loses editing and downloads too, until it is enabled | Default in force: suspension is enough for Release 1; nothing is built | — (a lighter switch would be its own task) |
| 7 | The pause stops new requests (images, plans, styles, text proposals, reads); admitted jobs finish, a 429 retry included | Default in force: yes | T-BALANCE-003 (the pause in `provider_guard`) |
| 8 | Defects: the operator repays by hand (`correct --job`), from a WhatsApp message, without seeing the image. **Option, not built:** a version rejected with a fidelity reason (prompts.py:12 codes, `decide` visuals.py:419-434) gives its credit back at once, limited to one per poster or three a week per shop, shown with actor `shop`. Cost about half a session; the leak is bounded by the limit, among invited shops; "cadrage" and "intégration" stay matters of taste and keep their credit | Default in force: not built; the operator's correction by hand | T-BALANCE-004 (`correct --job`); the option would be its own task |
