# Review r1 — DESIGN Creation by message (text-first generation)

**Date:** 2026-11-14. **Reviewer:** fresh reviewer (Claude), round 1.
**Reviewed:** `docs/project/designs/text-first-generation.md` (Draft v1) against `docs/project/requirements/text-first-generation.md`, the mockup `docs/project/mockups/chat-first/index.html` and the code. Code read, nothing run; no network call.

## Verdict: APPROVE WITH FIXES

The architecture holds: a synchronous read with its own ledger table summed in `spent_micros` is safe under `BEGIN IMMEDIATE`, `style_reference_asset` works without a saved look, and every route named in D-004 exists. Four points would cause a double charge, a wrong price or an unowned table as written (P1). The rest is underspecification that an implementer would resolve differently from the code.

No P0.

---

## P1 — fix before implementation

### P1-1. A recap or change card stays tappable after its paid call: double charge after a reload or on a second device
- Evidence: the design's guard is "the button is disabled at the tap" plus `image_job_running` (design l.239). `image_job_running` only holds while the job is `queued/running` (`jobs.py:72-75`, index `poster_one_image`). The client's lost-answer key reuse lives in memory only (`api.ts:40-47`, `uncertain` map), so it is gone after a reload and never exists on the other device.
- Path: device A taps « Créer l’affiche », the scene succeeds. Before step 8 (`events`) is stored, A reloads, or device B opens the same chat. The chat has `creation_id`, the last card is still the recap, the button is active (design l.125 says so for the unlinked case and says nothing for the linked one). A second tap runs steps 4 to 6 with new keys: a second scene is paid. Same for a `change` card.
- Fix: make "spent" a server fact, not client state. (a) The Idempotency-Key of the paid POST (`/scenes`, `/refinements`) is the card's message id; a replay then returns the stored 202 with the same `job_id` (`store.py:43-48`), and `idempotency_reused` (revision moved) is read as "already asked: reload jobs and visuals". (b) Only the last app card is actionable, and a card is spent when a scene/refine job of the poster is newer than it (`GET /api/creations/{id}/jobs` gives `created_at`). Add the browser smoke case "tap, reload, tap".

### P1-2. The price check "its digits appear in this message's text" accepts digits that are not the price
- Evidence: design l.161. In the requirement's own example, `Sony WH-1000XM6 noir, 700 000 Ar`, the model answering `1000` or `6` passes the check. `typography.validate_patch` (`typography.py:124-126`), cited as "the same idea", is stricter: exactly one amount followed by `Ar|ariary`, parsed by `parse_price`. Also `models.parse_price` (`models.py:27-34`) refuses `700.000` (spaces only), while the design says the check "accepts separators"; the dot form is accepted only by the frontend `parsePrice` (`document.ts`). "Existing price validation" therefore names two different rules.
- Fix: the server finds the candidates itself and the model only chooses among them. Candidate = a number not glued to a letter or hyphen (`(?<![\w.,-])…(?![\w-])`), groups of three with one separator kind (space, NBSP, dot), optional `Ar|ariary|MGA`. Accept `price_ar` only if it equals exactly one candidate, and, when several candidates exist, only the single one carrying the currency word; otherwise `ask_price`. Write this as one function with its regex in the design. Tests: `WH-1000XM6 … 700 000 Ar` never gives 1000; `Galaxy S24 128 Go 1 200 000 Ar`; `iPhone 15 128 Go` alone gives no price; `700.000`; `700k`; two amounts.

### P1-3. `chats` has no `shop_id`: ownership cannot be checked and `_owned` cannot be used
- Evidence: migration sketch l.71-76. Every poster table carries `shop_id INTEGER NOT NULL REFERENCES shop_profile(id)` (`0004_poster_drafts.py:24,29`, `0006_poster_jobs.py:11`, `0010_looks.py`), and every lookup goes through `store._owned(conn, table, shop, id)` (`store.py:56-62`). A chat without a poster has no path to a shop. The listed test "chat routes (ownership…)" cannot be written.
- Fix: `shop_id INTEGER NOT NULL REFERENCES shop_profile(id)` on `chats`; all chat reads through `_owned`; the link route checks that the creation is of the same shop.

### P1-4. Idempotency of `POST /messages` is not the existing convention and has three holes
- Evidence: `store.mutate` (`store.py:33-53`) keys on `(shop_id, key)`, compares method, path and payload hash, and stores the response in the same transaction. The design replaces it by "the key becomes the owner message id" (l.142-146).
  1. `chat_messages.id` is a global primary key: the same key sent to another chat, or with another body, hits the primary key (500 `storage_unavailable`) or returns another message's answer. No payload comparison is specified.
  2. "The stored answer" cannot be rebuilt: nothing links the app card to the owner message (no `reply_to`; `seq + 1` is wrong when two devices post together), and an image-only message has no `chat_reads` row at all.
  3. The second transaction is not conditional. The 60 s sweep can mark a read `interrupted` and store `read_failed`; a late answer then writes `succeeded` and a second card. `httpx` `timeout=20` is per phase, not total (`planner.py:80` is the same pattern with 90), so a call can outlive 60 s.
- Fix: keep `chat_messages.id` a server uuid. tx 1 inserts the message and the read with `key` and `payload_sha` columns (`UNIQUE (chat_id, key)`); a different hash is `idempotency_reused`. tx 2 inserts the `mutation_keys` row with the full response (same table, same replay path as every route) and runs `UPDATE chat_reads … WHERE id=:id AND status='running'`; zero rows means "swept": record the real cost if known, add no card. Wrap the call in `asyncio.timeout(20)` so 20 s is total. Replay: `mutation_keys` hit → stored answer; message present without it → 409 `read_running`.

---

## P2 — should fix

### P2-1. Ledger rule differs from the existing one, and the state machine contradicts the failure table
- "4xx or connection refused → failed, cost 0" (l.189): today only a 429 and an unsent call are zeroed. Any other error keeps the reservation as an estimate (`worker.py:73-76`, `jobs.py:170-174`), and `structured` reports every `RequestError`, connection refused included, as ambiguous (`planner.py:84-87`).
- "usage unreadable → interrupted, card read_failed" (l.191) contradicts "the reservation is kept as an estimate, the fields are still used" (l.207). The code's behaviour is the second (`planner.py:95-112` returns the value with `usage=None`; `jobs.py:244`).
- Not covered: a 200 with unusable content (`stop_reason="max_tokens"` at the 300-token cap, schema violation). `structured` raises a non-ambiguous `PlannerError` carrying the real `cost_micros` (`planner.py:108-109`); "not ambiguous → cost 0" would undercount.
- Fix: one table: 429 → failed, 0. Valid answer → succeeded, real cost or kept estimate. 200 with invalid content → succeeded-as-`unclear`, real cost or kept estimate. Everything else (timeout, network, 5xx, other 4xx) → interrupted or failed with the estimate kept.

### P2-2. `ClaudePlanner.structured` cannot do what the design asks without a signature change
- `max_tokens` 4096 and `timeout=90` are hard-coded (`planner.py:75,80`); the design needs 300 and 20 s. `call_spec(settings, "plan")` returns `estimate_plan_usd` and raises `planner_unavailable`, not `chat_unavailable` (`jobs.py:39-44`). `capabilities.planner_available` ignores `claude_model != MODEL` (`api.py:417`).
- Fix: add `max_tokens` and `timeout` parameters (defaults unchanged); one `read_spec(settings)` used by the route and by `chat_available`. State that the route is `async def` with every DB step in `run_in_threadpool` (as `upload`, `api.py:600`), because the job scheduler shares the event loop.

### P2-3. `chat_reads` lacks columns the existing ledger has, and one the price check needs
- No `provider` (stub or claude; the mode lock compares it, `jobs.py:81-86`), no `usage_json`, no `provider_request_id` (both on `poster_calls`, `0006:33`; needed to reconcile with the invoice), no `CHECK (cost_micros >= 0)` or `CHECK (cost_is_estimate IN (0,1))`.
- "One paid check per visual" (l.270) has no `visual_id` column and no unique constraint: two parallel requests pay twice. Add `visual_id TEXT REFERENCES poster_visuals(id)` and `CREATE UNIQUE INDEX … ON chat_reads(visual_id) WHERE purpose='price_check' AND status IN ('running','succeeded')`. Say what a failed or interrupted check returns on the next request.
- `/api/status.failed_jobs_24h` (`api.py:410-412`) counts `poster_jobs` only: add failed and interrupted reads, or a second counter. `/api/usage`, `/api/status.spend`, the evaluation CLI (`evaluate.py:362`) and the backup (whole database) all follow `spent_micros`: confirmed, nothing else sums spend.

### P2-4. A new version is not selected by the server after the first one; "current version" and "choosing a line" are undefined
- `finalise` selects a scene in the document only for the first visual of the poster, on an unchanged revision (`service.py:153-154`). Every later version (refinement, price or title change, retry) needs the client's PUT with the crop and layer visibility of `chooseVisual` (`App.vue:1256-1282`). The design says so for a refinement only; the price/title line ("then 4 to 9 again", l.233) has no selection step. Without it, approval succeeds but `/renders` exports the old scene or refuses (`exports.py:36-48`).
- `/refinements` requires the base to be the document's selected scene (`visuals.py:264-265`). R-004 "choosing a line shows that version" is view-only in the mockup. Define: showing a line never saves; "current" is the document's selected scene; the client selects (PUT) each new version when its job succeeds, before the agreement.
- `chooseVisual` is not in the list of functions to move, yet it is the one the chat needs most.

### P2-5. Price or title change: `reformat` is wrong, and step-made posters lose their words
- `reformat` (`document.ts`) empties the scene and shows every layer; the step editor does not use it for a price change (it saves the offer and asks a new scene, `App.vue:997`, `629-633`). With it, a failed job leaves the poster with no scene. Remove it from the flow.
- After the offer is saved, the old version can no longer be exported or refined (`price_stale`, `headline_stale`: `exports.py:44-48`, `visuals.py:278-281`). If the new scene fails or is not wanted, the chat has no way back. Add « Garder l’ancien prix » (PUT the old offer) to the failure card.
- "Headline defaults of the step editor" for a poster made in steps drops its brand, subtitle, accent, saved look, contact and seal; the editor restores them from the current visual for this reason (`App.vue:126-141`). Lazy fix: the chat offers a price or title change only when the current visual's `headline` holds nothing but title and price; otherwise `refused` → « Pas à pas ». Same for a poster whose price is not drawn (AGENTS.md: price-only change reuses the visual): the card's sentence « Le prix est dessiné dans l’image » would be false.
- Write the exact `headline` body of a chat scene (`{brand: null, subtitle: null, accent_word: null, accent_colour: null, price: true}`), and the direction and palette used with an inspiration image (no style is chosen then).

### P2-6. Step 1 body is refused as written; attachment roles need an upload rule
- `ProductInput.variant` is required (`models.py:52`); the editor sends `'Conforme à la photo'` (`App.vue:28,829`). `POST /api/product-inputs {name, photo_assets}` gets 422.
- An asset is usable as a product photo only with `asset_access.role='original'`, as an inspiration only with `'style'` (`store.py:72-76`, `visuals.py:218-219`), and the role is fixed at upload (`api.py:590-601`). The label swap of R-002 therefore needs a second upload with the other role (also the only way to get the `low_resolution` warning). Say it, or let `POST /messages` grant the role.

### P2-7. `scene.ts` as described is not a realistic move
- The eight functions are closures over about twenty refs (`saver`, `doc`, `creation`, `plan`, `headline`, `look`, `flush`, `follow`, `job`): `App.vue:825-842`, `1005-1068`, `1240-1291`. Their "pure parts" are the request bodies only. The chat also needs job following (`poll`, `App.vue:1117-1195`), which is not listed.
- Smaller cut: `scene.ts` exports `LOOKS`, `sceneBody(...)`, `selectVisual(document, visual, format)` (the body of `chooseVisual`), `approveBody`, `confirmBody`, `jobFailure`, and a small `followJob(id, onChange)`. `App.vue` keeps its functions and calls these. Resize T-CHAT-004 and T-CHAT-005 accordingly.

### P2-8. Requirements not covered or contradicted
- **R-001** « Styles » reachable from the chat view: not stated.
- **R-002** "the last one used being selected": no storage named (the editor uses `localStorage` `affiche.style`, `App.vue:224`).
- **R-004** « Annuler » on a change card, which puts the text back in the composer: absent from the card table.
- **R-004** "survive … a change of device": a chat without a poster is unreachable from another device, and from the same one once `#message` opens a new chat (no list of chats). Reopen the latest unlinked chat at `#message`, or state the limit. The unsent-message amendment (decision 6) changes an approved criterion: edit the requirements file and record the ADR in the same change, not in the design alone.
- **R-005** "switch to « Pas à pas » with what is already known filled in": no handover of the chat draft (name, price, photos) to the intake form is described.
- **R-005** keyboard, screen reader, phone keyboard not hiding « Envoyer », reduced motion: no design text and no test.
- **R-005** "a free local simulation covers every failure": the stub reader is a deterministic parser with no way to fail; `STUB_FAIL` is for images only (`config.py:34`, `110-115`). Name the stub's failure triggers (read failed, interrupted, slow).
- **R-003** read-back "before the owner's check": the agreement button is shown while the check runs, so the warning can arrive after the agreement. Hold the question until the check answers or 20 s pass.

### P2-9. `POST /events` can go
- The list of modifications can be derived on the client: the label of a version is the owner message before `visual.created_at`. That removes a route, the "event not stored" failure, and its retry key, which is lost at reload anyway. If the route stays, its Idempotency-Key must be derived from the visual id.

---

## P3 — notes

- Orphan poster when the browser dies between step 2 and step 3: accepted by the design; keep the editor's `pendingInput` pattern (`App.vue:831`) so a retry in the same session does not create a second input.
- `POST /chats/{id}/creation`: a creation already linked to another chat violates `UNIQUE` → map to 409, not 500.
- `POST /api/chats` without `creation_id` at every visit of `#message` leaves empty rows: create the chat at the first send.
- Merge the fields in tx 2 against the draft as it is then, not as read in tx 1 (two devices).
- "200 reads per day": say rolling 24 h or UTC day. "Names of earlier products" sent to Anthropic: not needed by the read (photo suggestions match on the server); drop it and the input size is bounded.
- One `intent` per message: say what « fond bleu et prix 650 000 » gives. `title_change` has no title field: say it reuses `product_name`.
- The change card should show `instruction_fr` (what is sent and paid), not only the owner's words.
- `start_view` in `meta` is fine for the single-shop pilot (`shop_profile` has `CHECK (id = 1)`); `read_estimate_micros` in capabilities has no reader in the design: drop it.
- Mode-lock mismatch has no code in the table (`provider_mode_mismatch` exists but has no French sentence in `MESSAGES`).
- Migration style: follow `0010_looks.py` (a `STATEMENTS` list, `downgrade` raises). FK targets `creations(id)` are correct.

## Missing tests

1. Tap a recap or change card, reload, tap again: one scene job (P1-1). Same on two sessions.
2. Price candidates: the model-number and `128 Go` cases of P1-2, on the Claude path with a mocked answer (not only the stub).
3. Same key, different body; same key, other chat; two parallel requests with one key: one provider call, one 409.
4. Late answer after the sweep: one card, one final status, real cost recorded.
5. 200 with `stop_reason="max_tokens"`, 200 without usage, 400, 429, connection refused: status and `cost_micros` of each.
6. Real cost above the reservation; a read at the cap boundary together with a scene reservation (two processes, as `admission_worker.py`).
7. Two parallel price checks for one visual: one paid call.
8. Second version: the document selects it before the agreement, and the render carries the new scene.
9. Price change whose scene job fails: the old version is exportable again after « Garder l’ancien prix ».
10. Price or title change on a poster made in steps with a brand, a look or a contact: refused, nothing saved.
11. `/api/status` and `/api/usage` include chat reads; start-up recovery marks a `running` read `interrupted` with its estimate kept.
