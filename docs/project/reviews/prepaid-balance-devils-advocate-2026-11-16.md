# Devil's advocate — prepaid balance design, Draft v1 (2026-11-16)

I found seven points that would change a decision, most consequential first. I changed no file. The only command beyond reading code was one read-only query on `backend/data-probe/affiche.db`.

## 1. The service's spending cap never resets, and selling credits will trip it for every paying shop

**Decision it changes:** resolution 6 and R-BALANCE-005 treat the provider cap as settled. Today it counts from one date and never resets.

**Evidence:**
- `spent_micros` counts from `SPEND_CAP_SINCE` with no end (admission.py:295-306). Raising the cap means `sudo nano app.env` and recreating the container (deploy/README.md:327, :330). The runbook's example cap is 15 USD (README:33).
- Some failures are recorded at the full 0.40 reservation even though the provider probably charged nothing. `ProviderError` has no `cost_micros` (gateway.py:64-73). So `worker.py:78` passes `None`, and `jobs.fail` keeps the reservation as the cost (jobs.py:201-205). This applies to `refused`, `invalid_request`, `auth`, `quota` and `invalid_response`; only `rate_limited` records 0. The probe ledger has one interrupted scene still sitting at 750,000 µ$.
- This design gives the credit back on every one of those failures, so the shop has no reason not to tap again. A product photo the moderation refuses five times fills the shop's 2.00 USD day: « Réessayez demain » while it still holds credits. Each failure also takes 0.40 off the service cap.
- Estimate, not measured: five shops making ten images a day each would use up a 15 USD cap in about 8 to 10 days. Every shop then reads « en pause pour tout le service », and the operator only learns of it when a shop calls.

**Instead:**
- `grant` prints the cap headroom against outstanding credits × the average of recent real image costs, and warns when the headroom is short. He then raises the cap at grant time, at his laptop, not when it trips on a Sunday.
- Record cost 0 for the definite 4xx kinds (`refused`, `invalid_request`, `auth`, `quota`), as worker.py:78 already does for `rate_limited`. That the provider does not bill a 4xx is a hypothesis; check it on the provider's dashboard at the next paid test.
- `GET /api/balance` also returns `paused`, so a shop sees the pause when the page loads, not after composing a poster.

**Cost:** about two hours, plus one decision for the owner: whether the cap stays cumulative or becomes monthly.

## 2. A separate debit line copies the job row; derive the balance from the jobs instead

**Decision it changes:** D-BALANCE-001 and 002: debit and release lines, the `poster_jobs_credit_back` trigger, `origin` on debits, the per-origin below-zero trigger, `UNIQUE (job_id, kind)`.

**Evidence:**
- The design itself says "the server has the debit if and only if it has the job" (line 10) and that the credit's states are "one to one with the job's" (line 240).
- Nothing ever deletes a `poster_jobs` row (grep of src/). Every status writer is in jobs.py, and no code moves a job out of a final state (design line 36).
- The trigger lives on `poster_jobs`. This project changes a CHECK list by rebuilding the table (0013_shops.py:4-31), and `poster_jobs.kind` and `status` are CHECK lists (0006:14-16). `DROP TABLE` drops a table's triggers. After such a rebuild, only the tests of each way a job ends would notice; the rehearsal does not check triggers.

**Instead:**
- One operator-written table, `credit_grants`: grants and corrections, with `origin`, `ref`, `amount_ar`, `method`, `note`, `actor`, an optional `job_id`, `UNIQUE (shop_id, ref)`, and the two "never changed / never removed" triggers.
- A column (or a `meta` start time) marks which image jobs count. Balance = sum of grants − count of counted image jobs that are `queued`, `running` or `succeeded`. `debit` becomes only the check `≥ 1` inside the existing `BEGIN IMMEDIATE`.
- Whole failure classes disappear: a lost release, a double release, an `IntegrityError` when `finished_at` is missing.
- The unit (an image or a poster) stays a query, so it can change after the prices are tested (R-ADMIN-004 measures first).
- "Offered spent first" can be computed when an expiry or refund ever needs it. The design admits it "changes nothing a shop can see" (line 91).

**Lost:** debits are no longer append-only, because a job's status can be updated. One trigger that refuses any move out of a final state guards that, and protects the job lifecycle itself.

**Cost:** rewriting D-001 and D-002, and the wording of R-BALANCE-003 and 006. T-BALANCE-001 gets much smaller.

## 3. Repaying a defect "by hand" puts every model mistake on one operator who cannot see the images

**Decision it changes:** R-BALANCE-001, bullet 4.

**Evidence:**
- The price, contact and title are drawn by the image model. Their digits are checked only by the owner's eye (DECISIONS.md:375, ADR-044).
- A missed logo disc gives a poster without its logo (service.py:178-181).
- Each format is its own scene (visuals.py:279; DECISIONS.md:191).
- The operator does not see pictures (R-ADMIN-002 default), and the shop never sees job ids. So every defect becomes a WhatsApp exchange, a timestamp search in `ledger`, and `correct --job <uuid>`.
- The shop already reports defects in the app, as structured reasons: coloris, logo, cameras, boutons, forme, extra, texte (prompts.py:12; `decide`, visuals.py:419-434).
- A rejected version cannot be approved again (visuals.py:423-425) or exported (exports.py:35-38).

**Instead:** a version rejected with a fidelity reason gives its credit back at once, with a limit (for example three a week per shop, or one per poster), shown in the operator's ledger with actor `shop`. "Cadrage" and "integration" stay matters of taste and cost the credit.

**Cost:** about half a session. The leak is a screenshot of a rejected scene, bounded by the limit, among invited shops.

## 4. A shop at zero on a Sunday evening gets no poster until Monday

**Decision it changes:** D-BALANCE-005's three display states, the content of the purchase text, and R-ADMIN-003.

**Evidence:**
- The display has only three states: at least one credit, unknown, zero.
- Grants happen only on the box. R-ADMIN-001 to 006 have no phone criterion, unlike R-SHOP-DASH-004.
- Nothing warns a shop before it hits zero.

**Instead:**
- A « bientôt à court » state (three credits or fewer) that shows the purchase text early.
- The runbook requires the purchase text to state when credits arrive (the operator's hours).
- R-ADMIN-003 adds: "granting is usable at 360 px on a phone".

**Cost:** about an hour in T-BALANCE-004, and one line in the admin requirements.

## 5. `CREDIT_PURCHASE_FR` should not be an environment setting

**Decision it changes:** D-BALANCE-003 makes the purchase text a setting in `app.env`.

**Evidence:** ROADMAP open decision 4 is "a first price to test", so the text will change several times in the first weeks. Each change is `sudo nano` plus a container recreate (README:327). R-ADMIN-006 moves it into the database in the same release anyway.

**Instead:** a `meta` key plus a `shops purchase-text "…"` command.

**Cost:** about the same size as the setting, and it saves the admin design a migration.

## 6. Drop the 100/20 read limit and keep one flat limit

**Decision it changes:** R-BALANCE-007's default and D-BALANCE-003's coupling of reads to the balance.

**Evidence:**
- About 100 reads × USD 0.003-0.004 ≈ USD 0.35 a day per shop at most (review), already bounded by `SHOP_DAILY_SPEND_USD` through `provider_guard` on reads (reads.py:569).
- The coupling adds a dependency from reads to credits, a balance query on every read, and a mid-day cut-off the design itself admits.
- The 20-at-zero rule only matters for free self-service accounts, which are Phase 2.

**Instead:** `DAILY_LIMIT = 100`, flat.

**Cost:** one wording change. A test set disappears.

## 7. Task split

**Decision it changes:** the four tasks.

**Evidence and instead:**
- **Fix `_pending` now, alone.** The bug is live today and has nothing to do with credits: `_pending` filters the kinds (service.py:189-190), and `recover`'s ready list goes to `app.state.pending_finalisations` (api.py:453), which nothing reads (grep). A spooled `text_texture` whose finalisation failed stays `running` and blocks its poster for ever.
- **T-BALANCE-001 is more than one session:** a migration, a seven-function module, the wiring, the 402, a setting, fixtures across about a dozen test files, and both smokes. Split the schema and module from the wiring and fixtures. Point 2 shrinks the first half.
- **Trim T-BALANCE-003.** Nothing is deployed before the admin dashboard (ROADMAP), so `ledger`, `correct` and `list` with balances would be built twice. Keep `grant` (tests, smokes, phone sessions, restore) and `pause`/`resume`.

**Cost:** TODO entries only.

## What I tried to break and could not

- **Double debit, two tabs on the last credit, a replayed key:** `mutate` returns the stored answer before `apply` runs (store.py:47-50), inside `BEGIN IMMEDIATE`, with `poster_one_image`. It holds.
- **Credit back at once on `interrupted`:**
  - The owner sees an image only in `finish_spool`'s `succeeded` transaction (jobs.py:256-271).
  - A shop cannot provoke a billed failure that gives it something.
  - Losses are bounded by the shop's daily ceiling. Only the phantom 0.40 in point 1 remains.
- **Check order (suspension, cap, shop's day, then balance):** correct, and the reason given is right.
- **Restore and references unique per shop:** it holds. The only residual is a mistyped payment reference, which grants twice.
- **Removing dollar figures from the shop:** the operator loses nothing that `/api/status` and R-ADMIN-004 do not give him.
- **The pilot's opening grant as a release step, not in the migration:** right, because shop 1 exists in every test database (0004:18).
- **`text_texture` costing one credit:** right. Free, it would be the one image a shop could make without credits.
- **The trigger itself (if point 2 is rejected):** it fails closed, and the suite runs on the migrated schema. But write the warning about a `poster_jobs` rebuild into the design.
