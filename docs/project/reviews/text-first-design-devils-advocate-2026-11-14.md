# Devil's advocate — design "Creation by message" (Draft v1)

**Date:** 2026-11-14. **Reviewed:** `designs/text-first-generation.md`, `requirements/text-first-generation.md`, mockup `mockups/chat-first/`, ADR-088 to 093, ADR-044/045/051.
**Method:** documents first; code read only to cost the alternatives. Nothing was run, no paid call, `backend/.env` not read.
**Rule of this report:** only points that would change a decision. Latency and network figures are estimates, not measurements.

## Summary

| # | Decision challenged | Recommendation |
|---|---|---|
| 1 | Move the flows of `App.vue` into `scene.ts` | **Change:** the chat calls the editor's functions in place |
| 2 | "One agreement" and download in the thread | **Change:** open the editor's existing review and final screens |
| 3 | Chat stored on the server (`chats`, `chat_messages`, 4 routes) | **Change:** one stateless reading route, conversation in the browser |
| 4 | Paid read-back of the drawn price in slice 1 | **Change:** measure offline first, build later or never |
| 5 | Start view saved for the shop on the server | **Change:** per device, `localStorage`, as in the mockup |
| 6 | Uploads and waiting on a slow phone are not designed | **Change:** add four rules to the design |
| 7 | Order of tasks (UI comes fifth) | **Change:** a two-task slice that makes a real poster by message |
| 8 | Synchronous read with its own ledger table | **Keep** (one money check to add) |
| 9 | Sonnet reads every message, no parser first | **Keep** (the hybrid is a trap on the price) |
| 10 | Gaps between requirements and design | **Fix** four small points |

Points 1, 3, 4 and 5 together remove about half of the planned work: T-CHAT-003, most of T-CHAT-001 and of T-CHAT-004.

---

## 1. Client flows: move them to `scene.ts`, or use them in place — CHANGE

**Decision challenged:** D-004 moves "the pure parts" of `createPoster`, `prepareScene`, `savePlan`, `generateScene`, `refineScene`, `decide`, `renderFinal`, `confirmFinal` out of `App.vue`.

**What the code shows:** these functions are not pure. They close over about fifteen refs (`creation`, `doc`, `saver`, `plan`, `look`, `headline`, `format`, `styleReference`, `intake`, `photos`, `job`, `review`…) and over `flush`, `edit`, `follow`, `adopt`, `stylePill`, `chooseVisual`, `headlineBody`. The money safety of the editor is in that closure: `pendingInput` (same product input on a retry), `planSignature` (same plan on a retry), the `uncertain` map of `mutation` (same Idempotency-Key when the answer was lost), `lowResAcceptedOf`. A move is a rewrite of the hottest paths of the deployed editor. The smoke is large (2 249 lines) but it does not pin the key reuse of a lost paid answer.

**Alternative:** no move. `ChatView.vue` is a second template over the same state of `App.vue` (props or `provide`). On « Créer l’affiche » it fills `intake` and `photos`, calls `pickLook`, then `perform(createPoster)` and `perform(createScene)`. A change calls `refineScene`; a price change calls `changePrice` then `createScene`. `poll()` already ends by setting `review`.

**Saves or prevents:** T-CHAT-004's refactor; regressions in the step editor (no function body changes); the design's edge case "the owner changes the title in Pas à pas and comes back" (same state, nothing to reload); the missing prefill of « Pas à pas » after a failed read (point 10) comes free; the route `#message-<chat id>` is not needed (`#<creation id>` serves both views).

**Costs:** the chat depends on `App.vue` internals and `App.vue` grows by the wiring. The chat template must not mount `PosterCanvas` or load the poster fonts (2.3 MB, 13.6 s at 1.6 Mbps per HANDOFF). A later clean extraction stays possible, with the chat's tests as a second cover.

## 2. Review and download in the thread — CHANGE

**Decision challenged:** « Oui, c’est bon » under a small poster in a bubble is the fidelity agreement; « Télécharger » then « Télécharger ce fichier » is the final confirmation.

**Why it weakens a safeguard the user asked for:**
- ADR-051 (user decision, after a scene with an invented line) is "one validation **with a summary of what to verify**". The chat keeps the one tap and drops the summary. Its question names the product, the title and the price; it does not say "no other text", which is the failure really seen (T-SCENE-INVENTED-TEXT is still open: only the owner's reading detects it).
- The editor's review compares with the original photo and zooms. The chat shows a thumbnail. ADR-044 says "the fidelity review must read every digit".
- The client still sends every check as true (`colour`, `markings`, `hardware`, `shape`, `extras_text`, `integration`, `text_title`, `text_price`; then `framing`, `content`, `identity`, `readability` and every warning). The stored record says the owner checked points that were never shown to him.
- The step editor asks « Les photos correspondent au produit et à la variante indiqués » before a poster is made (`intake.confirmed`). The chat drops it without saying so.

**Alternative:** the result card has one button « Vérifier » that opens the editor's existing review screen (already phone-tested, approved by the user in live run 7), with « Tout est conforme, approuver ». « Télécharger » opens the existing final screen. With point 1 this is no new code. The recap sentence carries the photo agreement in its words.

**Saves or prevents:** an approval given on a thumbnail; a second review UI to keep in step with the first. **Costs:** it differs from the mockup the user steered (one more screen, same number of taps as the design: one to agree, two to download). Show him this difference; it is his to accept.

## 3. Conversation stored on the server — CHANGE

**Decision challenged:** tables `chats` and `chat_messages`, routes create/get/link/events, a draft kept by the server.

**What the owner really loses if the conversation lives in the browser:** the bubbles, when he changes device or clears the browser. Nothing else. The poster, every version, its state and the photos are already on the server. Before a poster exists the loss is one message to type again. The design already made this trade for the unsent text (decision 6), and ADR-083 keeps the typed words per poster in `localStorage`.

**Alternative:** one route `POST /api/reads` with body `{text, draft, has_poster, recent (≤ 6)}` that answers `{fields, card}`. One table `chat_reads` (the ledger, with the text that was read). The thread is kept in `localStorage` per poster. The list of modifications comes from `GET …/visuals`; the owner's words for a version need one key added to the refine job payload and to `get_visual` (to verify: today the payload keeps the compiled prompt, not `instruction_fr` as a field) and a price change is read from `headline.price_ar`.

**Saves or prevents:** two tables, four routes, the crash window between "poster created" and "chat linked", the `409 chat_linked` and "two devices" cases, the 200-message guard. **Costs:** R-TEXT-FIRST-004 "the conversation survives a change of device" becomes "a reload on the same device; the list survives everywhere". The limit "40 messages per poster" becomes a count of reads per poster id (nullable column) or only the daily limit. The draft comes from the client: acceptable, it is the owner's own session and `Offer` and the recap still check it.

**Caution:** the user said "permanent chat for the first request and polish". Read as "the composer stays for polish", this alternative honours it. If he means "I find my conversation on any device", keep the design. One question to him settles it.

## 4. Paid read-back of the drawn price — CHANGE (out of slice 1)

**Decision challenged:** D-005, the author's own default; the requirement marks it OPEN and nobody asked for it.

**Against it:**
- False trust is built in. After one true warning the owner learns "the application warns me". From then on, no warning means "checked", whatever the words say. `match` is silent, so a wrong `match` is invisible.
- It checks the failure not yet seen (2 of 2 prices exact, ADR-044) and not the one seen (invented text, ADR-051).
- False warnings on stylised digits are unmeasured; each one teaches the owner to ignore the card.
- It adds a vision call and some seconds after every version, a route, a ledger purpose, two cards and their failure rows.

**Alternative:** slice 1 shows the asked price in large digits beside the image in the review (free; with point 2 the list already says "read every digit"). T-CHAT-006 keeps its offline measure on existing scenes with a right and a wrong price. Build the route only if the false-warning rate is low, and then ask the model for every text in the image, so the same call also catches an invented line.

**Saves:** T-CHAT-003 and part of T-CHAT-002/005. **Costs:** a wrong drawn price depends on the owner's eye alone, as in the step editor today: no regression.

## 5. Start view saved for the shop — CHANGE

**Decision challenged:** `GET/PUT /api/preferences`, a `meta` key, "last write wins" between devices.

**Problem:** the session is one shared shop login. An employee who picks « Pas à pas » on the desktop silently changes the owner's phone at its next opening. Per shop is worse than per device here. The mockup the user steered uses `localStorage`.

**Alternative:** `localStorage`, read with try/catch, default « Pas à pas » when unreadable. **Saves:** one route, three failure rows, one edge case. **Costs:** a new device asks the question once more. Also drop `read_estimate_micros` from capabilities: no screen shows it.

## 6. The cheap phone at 1.6 Mbps, keyboard open — CHANGE (design gaps)

1. **Uploads are not designed.** `POST /messages` takes asset ids, so four files go up first. There is no shrinking in the client and the limit is 10 MB per file: four camera photos are about 12 to 20 MB, one to two minutes or more on this line, sent one after the other, with « Envoyer » silent. Rule to add: each image uploads when it is attached, with its own state and « Réessayer » on its thumbnail; « Envoyer » waits for them. The inspiration image may be reduced in the browser (it is a style reference, not an original); product photos are not (project rule).
2. **`fetch` has no timeout in `api.ts`.** The server gives up after 20 s, but a stalled phone connection waits without end and the composer stays locked. Rule to add: the client gives up after about 30 s and says so; the read stays on the ledger.
3. **Lost answer after a reload:** the kept unsent text is sent again with a new key, so the message is read and shown twice. Rule to add: keep the Idempotency-Key with the unsent text.
4. **Height:** at 360 × 740 with the keyboard open about 300 px remain. Tray + three style chips + input row take about 180 px. Rule to add: the style row is hidden while the text field has the focus, or the style is chosen on the recap card. Use the existing `visualViewport` height of `App.vue`.

« Créer l’affiche » is six requests in a row; a drop in the middle is likely on this line. With point 1 the editor's retry rules apply as they are.

## 7. Order of tasks — CHANGE

**Decision challenged:** three backend tasks, a refactor, and the first visible screen in the fifth task. The user steers by looking.

**Alternative (with points 1 to 5):**
1. Reader (Claude and stub), `chat_reads` in `spent_micros`, limits, `POST /api/reads`. Then at once the paid reading of about twenty real messages (about USD 0.10): it decides point 9 and the model before any card is drawn.
2. `ChatView` for the first request only: message with images, recap, « Créer l’affiche », the existing review, the existing download, the choice screen. **A real poster made by message on the pilot.**
3. Polish: change cards, price change, list of modifications.
4. Photos already used by the shop, failure-path audit, free demo.

## 8. Synchronous read with its own ledger table — KEEP

- The queue cannot take it without touching migration 0006: `creation_id` and `origin_revision` are `NOT NULL` with a foreign key to `creation_versions`, and `enqueue` checks the revision. The "look as a `plan` job" trick works only because a look is asked from an open poster.
- A hidden draft poster is not possible either: `ProductInput` needs at least one photo, and the first message may have none. It would also fill « Mes affiches » with empty drafts.
- A queue adds a poll round trip on a slow line for an answer that takes a few seconds.

**One money check to add:** `spent_micros` is the single sum (used by `jobs._reserve`, `admission`, `/api/usage`, `/api/status`, `evaluate`); the third term goes there and nowhere else. The test must prove that a `running` read counts against the cap before its answer. `ClaudePlanner.structured` has `timeout=90` and `max_tokens=4096` fixed: the design's 20 s and 300 tokens need two parameters there.

## 9. Sonnet for every message, no parser first — KEEP

The hybrid looks free (the stub parser exists) but it fails on the one field that must not be wrong. Phone names end in numbers: `Redmi Note 13 700 000 Ar` gives 13 700 000 Ar with the mockup's expression, and "128 Go 1 200 000 Ar" is one space from the same error. It would also give two behaviours to test in production, against the user's decision (ADR-092), to save about USD 0.004.

**Consequences for the design as it is:**
- The server's digits check does not catch this error either: the digits of a wrong `13700000` do appear in the message as one amount. The recap is the only guard: write that in the design, and put these messages in the paid evaluation and in the stub parser's tests.
- The only safe shortcut is a message that is nothing but an amount (the answer to « Quel est le prix ? », or a price change). Do not build it now; reconsider if the measured delay of a read hurts.
- Measure the delay of a read in the evaluation. If the median is over about 3 s, a faster model is worth its second rate card.

## 10. Requirements against design — FIX

- **Wrong request body:** step 1 of D-004 posts `{name, photo_assets}`; `ProductInput.variant` is required (the editor sends « Conforme à la photo »). As written the call is refused.
- **Dropped:** "switch to « Pas à pas » with what is already known filled in" (R-005) has no design before a poster exists. Point 1 gives it.
- **Dropped:** "the last style used is selected" (R-002); `rememberStyle` exists in the editor.
- **Built and not asked:** `/api/preferences` (point 5), `events` and the 200-message guard (point 3), the price check (point 4), `read_estimate_micros`, the intents `format_change` and `title_change` as model outputs (a format request can fall under `other` with the same sentence).
- **Keep:** the shop's earlier photos for a product. The user asked for reuse (ADR-088). Exact name matching will often find nothing; it can wait for the fourth task.
