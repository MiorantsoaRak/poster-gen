# DESIGN — Creation by message (text-first generation)

## System overview

**Status:** v2, 2026-11-14, approved under the autonomy grant (ADR-094) after a fresh review ([round 1](../reviews/text-first-design-r1-2026-11-14.md): APPROVE WITH FIXES, four P1) and a devil's advocate ([report](../reviews/text-first-design-devils-advocate-2026-11-14.md)). v2 is a rewrite: it is about half the size of v1, and every P1 is either fixed or removed with the part it was in.
**Requirements file:** [../requirements/text-first-generation.md](../requirements/text-first-generation.md) (R-TEXT-FIRST-001 to 005, amended by ADR-094)
**Mockup:** [../mockups/chat-first/index.html](../mockups/chat-first/index.html): the reference for layout, words and the order of the cards, except the check and the download (D-003).

The chat is a second front door to the pipeline that exists. One thing is new on the server: a small paid model call that reads a message, with its ledger. The conversation is kept in the browser. Everything that makes, checks and exports a poster is the step editor's own code, called in place.

```
[ChatView.vue, child of App.vue] ── POST /api/reads ──▶ [api] ── reserve ─▶ [chat_reads ledger]
      │   thread, draft, unsent text: localStorage           └─ Claude (text only, structured) ─▶ fields ─▶ card
      │
      └─ on the owner's tap: App.vue's existing functions (createPoster, createScene, refineScene,
         chooseVisual, the review dialog, the final dialog), so the routes, guards and retries are the editor's.
```

## What changed from v1, and why

| v1 | v2 | Source |
|---|---|---|
| Conversation stored on the server (3 tables, 5 routes) | Thread in `localStorage`; one stateless route and one ledger table | Devil's advocate 3. Posters, versions and their states are already on the server; only the bubbles stay on the device. Removes review P1-3 and P1-4 (ownership and idempotency of stored messages) and the "poster made but not linked" crash window |
| Flows moved out of `App.vue` into `scene.ts` | `ChatView` calls the editor's functions in place through one small adapter | Devil's advocate 1, review P2: the functions close over about twenty refs and the retry guards |
| One tap on a thumbnail approves; two taps download | « Vérifier » opens the existing review dialog; « Télécharger » opens the existing final dialog | Devil's advocate 2: ADR-051 kept one agreement **with** the photo comparison and the summary of what to check |
| Paid read-back of the drawn price | Out of this slice; measured offline first | Devil's advocate 4: after one true warning, silence reads as "checked"; 2 of 2 real prices were exact, the failure seen was an invented line |
| Start view saved for the shop on the server | Saved per device | Devil's advocate 5: one shared login, so an employee's choice on the desktop would flip the owner's phone |
| "The price's digits appear in the message" | The server lists the amounts written before « Ar »; the model's value must be one of them | Review P1-2: `1000` passed for `Sony WH-1000XM6 noir, 700 000 Ar` |
| A card stays tappable after its paid call | The card's id is the idempotency key of its paid request, and a card is spent once tapped | Review P1-1 |
| Intents for title and format changes, events route, per-poster message limit | Dropped | YAGNI |

---

## D-TEXT-FIRST-001 — Start view and the two front doors (covers R-TEXT-FIRST-001)

**Approach:** the choice is a per-device preference, `localStorage` key `affiche.start` (`chat` or `steps`), like the theme and the last style. `App.vue` shows the choice screen when it is unset and the chat is available; afterwards a two-button switch sits in the header. `ChatView.vue` is loaded on demand (`defineAsyncComponent`) and never mounts the canvas or the poster fonts: it shows a version with `displayUrl(visual.image_url)`.

**Data model changes:** none.

**API contract / interface:** `GET /api/capabilities` adds `chat_available: bool` (planner mode is `claude` or `stub`).

**Routing:** `#message` is the chat for a new poster; `#message-<creation id>` the chat of a poster. `''`, `#affiches`, `#styles` and `#<creation id>` are unchanged. With `affiche.start = chat`, the empty hash goes to `#message` and « Mes affiches » opens a poster at `#message-<id>`. The switch moves between `#message-<id>` and `#<id>` for the same poster, and between `#message` and `''` before a poster exists, carrying what is already typed (the chat draft fills the editor's form fields, which are the same refs).

**Failure modes & handling:**
| Failure | Detection | Behavior |
|---|---|---|
| `localStorage` unavailable | exception | the app opens on « Pas à pas »; the switch works for the visit |
| Chat not available | `chat_available` false | no choice screen, no switch; `#message` falls back to the editor |
| The chat's code fails to load (slow network) | import rejects | one sentence and « Réessayer »; the switch to « Pas à pas » stays |

**Edge cases:** a poster opened in the chat on a device that has no thread for it shows the versions, the list and an empty thread with « Dites ce qu’il faut changer. ». Abandoned posters open as today.

**Security / data notes:** none.

---

## D-TEXT-FIRST-002 — Reading a message (covers R-TEXT-FIRST-002, 004, 005)

**Approach:** `POST /api/reads` pays one model call that extracts fields from one message, checks them, merges them into the draft the client sent, and answers with the next card. The route keeps no conversation: the client sends its draft and the last messages with each request. The call is synchronous (the queue cannot hold it: `poster_jobs.creation_id` and `origin_revision` are `NOT NULL`, a first message has no poster, and a hidden draft poster is impossible because a product input needs a photo).

**Data model changes (migration 0012, forward-only, hand-written SQL):**
```sql
CREATE TABLE chat_reads (                    -- the ledger of the reading calls
  id TEXT PRIMARY KEY,                       -- server uuid
  shop_id INTEGER NOT NULL REFERENCES shop_profile(id),
  creation_id TEXT REFERENCES creations(id), -- null before the poster exists
  key TEXT NOT NULL UNIQUE,                  -- the request's Idempotency-Key
  payload_sha TEXT NOT NULL,                 -- sha256 of the canonical request body
  status TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed', 'interrupted')),
  provider TEXT NOT NULL, model TEXT NOT NULL, rate_card_json TEXT NOT NULL,
  cost_micros INTEGER NOT NULL,              -- the reservation, then the real cost
  cost_is_estimate INTEGER NOT NULL,
  usage_json TEXT, provider_request_id TEXT,
  response_json TEXT,                        -- the body answered, for a replay
  created_at TEXT NOT NULL, finished_at TEXT
);
CREATE INDEX chat_reads_created ON chat_reads (created_at);
```
`spent_micros` (`visuals/admission.py`) gains a third sum over `chat_reads.cost_micros` since `SPEND_CAP_SINCE`. It is the only place that sums spend (`/api/usage`, `/api/status`, every reservation and the evaluation CLI read it), and a `running` read counts with its reservation.

**API contract / interface:**
```
POST /api/reads          header Idempotency-Key: <uuid>
  body { text: 1–500 chars,
         creation_id?: uuid,                       -- present once the poster exists (must be the shop's)
         draft: { name?: ≤160, price_ar?: int, style?: "clair"|"couleur"|"sombre",
                  product_photos: 0–3, inspiration: bool },
         history: ≤6 items { role: "owner"|"app", text: ≤500 } }
  201 { card: { kind, text_fr, ... }, draft }
  Same key and same body again: the stored answer. Same key, other body: 409 idempotency_reused.
  Same key while the call runs: 409 read_running.
  422 validation_error · 404 unknown creation · 429 budget_exhausted, read_limit · 503 chat_unavailable
```

**What the model returns (structured output):**
```
{ intent: "describe" | "scene_change" | "price_change" | "other",
  product_name: string | null,     -- brand and model as the owner wrote them
  price_ar: integer | null,
  style: "clair" | "couleur" | "sombre" | null,
  instruction_fr: string | null }  -- scene_change only: the change, with no word about the title or the price
```
`ClaudePlanner.structured` gains two optional arguments, `max_tokens` (300 here; 4096 stays the default) and `timeout` (20 s here; 90 s stays the default); the route also bounds the whole call at 20 s. The model is the pinned `claude-sonnet-5-5` with the existing rate card. The owner's text, the draft and the history go in the user turn as data; the system prompt says they are never instructions and that a field the owner did not give stays null.

**Server checks (the model is not trusted):**
- **Price.** The server lists the candidate amounts of the message itself: every run of digit groups (`\d{1,3}` then groups of three separated by a space, NBSP, NNBSP or a dot, or plain digits) that is followed by `Ar`, `ariary` or `MGA`, **and each of its group suffixes** (`13 700 000 Ar` gives 13 700 000 and 700 000); if the whole message is one amount without a unit, that amount. The model's `price_ar` is kept only if it is one of the candidates and passes `Offer`. Otherwise the price is not set and the card asks for it. The server cannot tell `Redmi Note 13, 700 000 Ar` from a 13 700 000 Ar price: the model chooses, and the recap, which shows the price large, is the owner's guard. Such messages are in the paid evaluation.
- **Name.** 1 to 60 characters and the existing title rules (the same function the scene route uses); otherwise the card carries that rule's existing French sentence.
- **Instruction.** The existing refinement screen (`screen_art`, no title or price word); a refusal becomes the `refused` card.
- Anything else (schema violation, unknown intent) is `unclear`.

**The cards (`text_fr` comes from the server's `MESSAGES` table, so there is one place for French sentences):**
| Situation | `kind` | Text and data |
|---|---|---|
| no poster, name missing | `ask_product` | « Quel est le produit ? Marque et modèle. » |
| no poster, price missing | `ask_price` | « Quel est le prix ? Écrivez-le en chiffres, par exemple 700 000 Ar. » |
| no poster, `product_photos` = 0 | `ask_photo` | « Il me faut une photo du produit. » (`suggestions` added in T-CHAT-005) |
| no poster, all present | `recap` | `{name, price_ar, style}`; the client adds the photos, the cost and the button |
| poster, scene change | `change` | `{change: "scene", instruction_fr}` « Nouvelle version : « … ». L’actuelle reste gardée. » |
| poster, price change | `change` | `{change: "price", price_ar}` « Le prix est dessiné dans l’image : je refais l’affiche avec … » |
| poster, the instruction is refused | `refused` | the refinement screen's existing sentence |
| not understood, or `other` | `unclear` | before a poster: « Écrivez le produit et son prix. » After: « Dites ce qu’il faut changer : le fond, la lumière, le prix. Le titre et le format se changent dans Pas à pas. » |

**State machine of one read (`chat_reads.status`):**
```
(tx 1, BEGIN IMMEDIATE) sweep: every 'running' row older than 60 s becomes 'interrupted' (reservation kept)
        key known → replay rules above. Otherwise: mode lock, daily limit, cap, then insert 'running'
        with the reservation. A refusal here stores nothing.
        ▼
   call Claude outside any transaction, whole call bounded at 20 s, no retry
        ├─ answer, usage readable     → (tx 2) 'succeeded', real cost
        ├─ answer, usage unreadable   → (tx 2) 'succeeded', reservation kept as an estimate; the fields are used
        ├─ HTTP 429, or never sent    → (tx 2) 'failed', cost 0                    (the existing rule, worker.py)
        └─ anything else              → (tx 2) 'interrupted', reservation kept as an estimate
tx 2 is `UPDATE … WHERE id = ? AND status = 'running'`: an answer that arrives after the sweep changes nothing
and the client gets the failure answer. A crash between the two transactions is closed by the next sweep
(also run at start-up).
```
A failed or interrupted read answers 503 `read_failed` (« Je n’ai pas pu lire votre message. Réessayez, ou passez par Pas à pas. »), stored for the replay. A retry is the owner's: same text, new key, new paid read.

**Limits:** reservation `ESTIMATE_READ_USD` (new setting, default 0.02; added to `test_config.NAMES`); 200 reads per day for the shop (UTC day), then 429 `read_limit` « Limite de messages atteinte pour aujourd’hui. Continuez dans Pas à pas. ». The spend cap is the existing one. A text-only read is about 1 200 input and 150 output tokens, about USD 0.004 at the current rate; measured in T-CHAT-002.

**Stub and locks:** with `PLANNER_PROVIDER=stub` the reader is a deterministic parser at cost 0 (first candidate amount, the three style names, « fond », « lumière », « prix » for a change), and `STUB_FAIL` makes it fail, so the tests, the smoke and the free demo cover the failure path. `disabled` answers 503 `chat_unavailable`. A read follows the existing `meta.planner_mode` lock.

**Failure modes & handling:**
| Failure | Detection | Behavior |
|---|---|---|
| Claude times out, cuts or returns 5xx | exception | `interrupted`, the reservation stays on the ledger as an estimate, 503 `read_failed`; the owner's bubble stays, with « Réessayer » |
| Claude returns 429 | status | `failed`, cost 0, 503 `read_failed` |
| Cap reached | reservation rule | 429 `budget_exhausted`, the existing sentence; the text goes back into the composer |
| The answer is lost on the way back | client timeout (30 s) | the client sends the same key and body again: the stored answer, no second call |
| Reload while the request is in flight | the key is saved with the unsent text | same as above: the same key is sent again |
| The model gives a price the owner did not write | candidates check | the price is dropped, `ask_price` |
| Key missing, or the model is not the pinned one | existing `call_spec` rule | 503 `chat_unavailable` |

**Edge cases:** « non, 650 000 Ar » on a recap changes only the price; « c’est le blanc » changes only the name. Two different prices in one message: the model must return null. `700k`: no candidate, the price is asked. A message in Malagasy is read like any other; the cards stay French. An empty or 501-character text is refused by validation before any reservation.

**Security / data notes:** only text goes to Anthropic for a read: the owner's message, the draft and up to six earlier lines. No image. The output can only fill five typed fields, each checked; it cannot reach a route, a price the owner did not write, or the cap. `creation_id` is checked with `store._owned`. Every new refusal code has its `MESSAGES` entry (the existing test enforces it). `chat_reads` is in the database, so it is in the existing backup.

---

## D-TEXT-FIRST-003 — From the recap to the download, in the chat (covers R-TEXT-FIRST-002, 003, 004)

**Approach:** `App.vue` gives `ChatView` one adapter object built from its own functions and refs. The chat never calls a poster route itself, so the retry guards, the palette, the headline defaults, the acknowledged warnings and the scene selection are the editor's.

**The adapter (in `App.vue`; each member wraps existing code, no logic of its own):**
```
state      doc, visuals (versions and their status), current job and its phase, capabilities, product name and price refs
attach     (files, role) → uploads one file per request as soon as it is chosen (existing `upload`), each with its own
           progress, retry and remove; product photos land in the editor's photo list, the inspiration as the scene's
           style reference (`style_reference_asset`, upload role `style`)
start      (card id) → createPoster, then createScene, with the recap's name, price and style; no paid dialog
           (the recap button already states the cost)
change     (card id, instruction) → refineScene, then chooseVisual on success
reprice    (card id, price) → the editor's own price edit, then createScene, then chooseVisual on success
review     () → opens the existing review dialog (photos beside the image, the summary, one agreement)
download   () → opens the existing final dialog (render, warnings, confirmation, download)
```
`card id` is passed down as the `Idempotency-Key` of the paid request (`/scenes` or `/refinements`), so a card can pay once whatever the client does. The implementer adds an optional key argument where the editor's functions build their own.

**Attachments:** one button, `accept` JPEG/PNG/WebP, several files. The first image is the product, the next the inspiration, later ones product photos up to three; the label on each thumbnail is a button that swaps the role (a swap after upload re-uploads under the other role). Each file is uploaded when attached, not at send. With an inspiration image the style row is replaced by « Style : comme votre inspiration » and the scene uses the neutral style's direction with the image as `style_reference_asset`. Without one, the row shows the three built-in styles, the last used (`affiche.style`) selected.

**The thread (browser only):** `localStorage` key `affiche.chat.<creation id or "new">`: the last 100 items `{id, role, text, card?, spent?, at}`; `new` is renamed to the creation id when the poster is made. The unsent text and the key of a request in flight are in `affiche.chat.unsent`. Pure helpers in `frontend/src/chat.ts` (roles of attached images, thread trimming, which button a card shows, the list of modifications), tested with Vitest.

**One paid tap, never two (review P1-1):** at the tap the card is marked `spent` and saved before the request leaves; a spent card shows its outcome, never its button. The request carries the card id as key, so a repeat after a lost answer replays. While an image job is queued or running every paid button is disabled (`image_job_running` is the server's own guard) and « Envoyer » waits, so no read can produce a second paid card for the same wish. On another device there is no thread, so there is no card to tap.

**While it is made:** the existing phases of `generation.ts` as one line in the thread (no percentage), the current version stays in the strip, the composer accepts typing, and a reload resumes from the poster's jobs as the editor does.

**Check and download:** the result card shows the image and « Vérifier ». It opens the existing review dialog; approval and rejection are the editor's. After approval the card shows « Télécharger », which opens the existing final dialog. This is one tap more than the mockup and keeps the comparison with the photo and the summary of what to check; the recap and the review both show the asked price large.

**List of modifications:** built from the poster's visuals: number, state (« À vérifier », « Confirmée », « Refusée ») and a label: « Première affiche » for the first, the refinement's instruction for a scene change (the visual view gains `instruction_fr`, read from the refine job's payload), « Prix : … » when the drawn price differs from the previous version's. It is the same on every device. Choosing a line shows that version (`chooseVisual` is not called: looking is free and changes nothing).

**Price change:** `reprice` uses the editor's price edit, so a poster made in steps keeps its brand, look and contact. If the new scene fails, the document holds the new price and the old image; the existing `price_stale` guard blocks export, and the thread says « L’affiche montre encore l’ancien prix. » with « Réessayer » (its cost) and « Remettre l’ancien prix ».

**« Annuler »** on a change card puts its text back in the composer and removes the card (nothing was paid for the change; the read was).

**Slow phone (devil's advocate 6):** per-file upload with progress; a 30 s client timeout on `/api/reads` (an `AbortController` in `api.ts`, opt-in so other calls are unchanged); the key kept with the unsent text; while the text field has focus on a narrow screen the style row is hidden and the attachment tray is one line that scrolls sideways.

**Accessibility:** the thread is a `role="log"` live region; every icon button has a French label; after a send the focus returns to the text field; card buttons are real buttons reachable in order; the enlarged poster is the existing dialog; motion follows `prefers-reduced-motion`; the composer uses the existing `viewport.ts` so the keyboard never covers « Envoyer ».

**Failure modes & handling:**
| Failure | Detection | Behavior |
|---|---|---|
| An upload fails | `ApiError` | that thumbnail shows « Réessayer » and the server's sentence; the others and the text are kept |
| `start` fails part-way | `ApiError` from the editor's function | the editor's own retry guards apply (`pendingInput`, the uncertain-key map); the card shows the server's sentence and one « Réessayer » that is the same card id |
| Scene job fails or is interrupted | job status | the existing `jobFailure` sentence in the thread; a new attempt is a new card with its cost, never automatic |
| `headline_stale` on a change | 409 | « Le texte a changé : je refais l’affiche entière. » as a new card with the scene cost |
| Title rules refuse at scene time | 422 with `field` | the sentence in the thread; the next message is read as a new name |
| Palette not ready (« Couleurs du produit ») | the editor's `paletteBlocked` | the recap button waits with « Je lis les couleurs de la photo… »; on failure the recap says « Couleurs illisibles : Studio clair à la place. » |
| Thread storage full or blocked | exception | the chat works for the visit and says once that the conversation will not be kept |

**Edge cases:** the owner edits the poster in « Pas à pas » and comes back: the chat reads the same refs, so it is current. A second tab on the same device: the storage event reloads the thread. The twelve-version limit: at ten the change card adds « Il reste 2 versions pour cette affiche. »; at twelve the existing `attempt_limit` sentence replaces the button. Formats: the chat makes Publication (4:5); the others stay in « Pas à pas ».

**Security / data notes:** no new route; the thread holds only the owner's words and card data, on the owner's device.

---

## D-TEXT-FIRST-004 — Photos already used (covers R-TEXT-FIRST-002; last task)

**Approach:** the `ask_photo` card offers up to three photos this shop used for the same product. `POST /api/reads` adds `suggestions: [{asset, name}]` when `product_photos` is 0: the photos of the shop's product inputs whose name equals the draft's name, case and accents ignored (the normalisation of `brand_in_title`), newest first. « Reprendre cette photo » attaches the asset without an upload. A reused photo starts a new poster; no approval comes with it.

**Data model changes:** none. **Failure modes:** the lookup is a local query inside the request; if it fails the card is sent without suggestions and the error is logged. **Edge cases:** a removed poster's photos are still offered (the asset is the shop's). **Security:** assets are filtered by the shop's `asset_access`.

---

## Tests

- **Backend:** migration 0012 on a copy of a 0011 database; the read state machine with a mocked transport (succeeded, usage unreadable, 429, timeout, late answer after the sweep, crash recovery); replay (same key and body, same key other body, same key while running); money: reservation, real cost from usage, estimate kept, `spent_micros` over three tables with a `running` read counted, cap refusal, daily limit at the day's edge; the candidate amounts (`Sony WH-1000XM6 noir, 700 000 Ar`, `Redmi Note 13 700 000 Ar`, `700.000 Ar`, `700k`, two prices, a bare number, a price the owner did not write); every card from the stub reader; `STUB_FAIL`; ownership of `creation_id`; the mode lock; every new code has its French sentence; `instruction_fr` in the visual view; the suggestions query.
- **Frontend (Vitest):** `chat.ts`; the 30 s timeout and key reuse in `api.ts`.
- **Browser smoke (stub, zero spend):** the choice screen and the remembered start view; one message with two images to a confirmed download; reload in the middle (unsent text, spent card); a scene change; a price change and its failure; no photo; no price; read failed (`STUB_FAIL`); cap reached; 360 px with the keyboard-sized viewport; desktop; both themes; the step editor's existing run unchanged.
- **Paid (the user's standing word, inside the cap):** T-CHAT-002 reads about twenty real messages (French, Malagasy words, prices in several spellings, the `Redmi Note 13` trap) and reports cost and delay per read and every wrong field; if the median delay is over 3 s the model is reconsidered. T-CHAT-005 makes one poster through the chat on the pilot's image model, and measures a price read-back offline on existing scenes (no product code) to decide whether it is worth building.

## Tasks

1. **T-CHAT-001** backend: migration 0012, the reader (Claude and stub), `POST /api/reads` with its cards, checks, ledger, limit and French sentences; `chat_available`.
2. **T-CHAT-002** paid reading evaluation on real messages, with its report.
3. **T-CHAT-003** frontend, first request: the choice screen, the switch, the routes, `ChatView` with attachments, recap, generation, « Vérifier » and « Télécharger » through the existing dialogs; `chat.ts`; smoke.
4. **T-CHAT-004** polish: change cards (scene, price), « Annuler », the list of modifications (`instruction_fr`), the version limit lines; smoke.
5. **T-CHAT-005** photos already used; failure-path audit on empty data; free demo; one paid poster through the chat; the offline price read-back measurement; report.
