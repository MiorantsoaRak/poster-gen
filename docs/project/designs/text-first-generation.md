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

## D-TEXT-FIRST-005 — A change is a set of fields, not a kind (covers the ADR-099 amendments of R-TEXT-FIRST-004 and 005)

**Status:** v4, 2026-11-15, approved under the user's autonomy grant, restated on 2026-11-15 (ADR-099). [Round 3](../reviews/text-first-d005-design-r3-2026-11-15.md) rejected v3 on one P1 (a requirement gap, closed by an explicit exception in the requirements) and three P2; all four are fixed in v4 and listed under "What changed from v3". v4 itself has not been reviewed again: the code review of each task checks these four points. v1 was rejected by the fresh review ([round 1](../reviews/text-first-d005-design-r1-2026-11-15.md): four P1) and challenged by the devil's advocate ([report](../reviews/text-first-d005-devils-advocate-2026-11-15.md): three P1); v2 was rejected in [round 2](../reviews/text-first-d005-design-r2-2026-11-15.md) (two P1, five P2). "What changed" is at the end of the section. Replaces, for an existing poster only, the `intent` of D-002 and the two change cards of D-003. The reader of a new poster (D-002) is not touched.

**Problem:** the chat holds a hand-made copy of what the editor can change: an `intent` value, a prompt sentence, a `build` branch, a card kind (`change: 'scene' | 'price'`) and an adapter function (`change`, `reprice`, `price`) per kind. The editor's « Textes » group has title, brand, subtitle and price; the copy has the price only, so a brand request falls to `other`. The sentence « Dites ce qu’il faut changer : … » is written by hand beside them.

**Approach:** on an existing poster the reader fills the editor's own fields, against the words of one version that the server reads itself. No kind is asked from the model. One table on the server names the fields; the model's schema, the checks, the card's lines and the "what I can change" sentence are made from it. The server says what the change costs and which words the new image will carry; the client sets exactly those words in the editor and asks the editor's own « Nouvelle version ».

**The field table (`reads.py`). Adding a field is one row here, one setter in the adapter, its TypeScript type and one stub pattern; a change that is not a field of the editor stays impossible:**
| Field | Current value comes from | Check | Can be removed | Label |
|---|---|---|---|---|
| `title` | the version's stored `headline.title`; a version without drawn words: `document.offer.title` | drawn: `name_refusal` (1 to 60, `screen_headline`, no `"` or line break). A layer: `Offer` (1 to 240) | no | « le titre » / « Titre » |
| `brand` | the version's stored `headline.brand` | `HeadlineText` + `screen_headline` | yes | « la marque » / « Marque » |
| `subtitle` | the version's stored `headline.subtitle` | same | yes | « le sous-titre » / « Sous-titre » |
| `price_ar` | the version's stored `headline.price_ar`; when the price is not drawn: `document.offer.price_ar` | the candidate amounts of the message (ADR-095), then `Offer` | no | « le prix » / « Prix » |
| `instruction_fr` | — | `RefinementRequest.scene_adjustment`, 500 characters | no | « le fond, la lumière » / « Scène » |

**No data model change. No migration.**

**API contract (`POST /api/reads`, one addition):**
```
body  + visual_id?: uuid      -- the version the owner looks at; required with creation_id for a change.
                              -- Left out of the canonical body when absent (`exclude_if`, as `Headline.brand_text`),
                              -- so every request made before this change keeps its hash.
201 { card: { kind: "change", text_fr, visual_id,
              effect: "refine" | "scene" | "free",
              words?: { title?, price_ar?, brand?: string | null, subtitle?: string | null },
                 -- effect "scene": the four words the new image will carry, whole (null = none), changed or not.
                 -- effect "free": only the document fields to set (title, price_ar).
              instruction_fr? },                                   -- effect "refine" only
      draft }
404 not_found: the version is not this poster's.
409 reload_required « Rechargez la page pour continuer. »: `creation_id` without `visual_id` (a tab that still
    runs the old bundle, or a read kept from before that never reached the server). The key is looked up first, so
    a stored answer is still replayed; a new key is refused before any row is inserted: nothing is reserved,
    nothing is paid. The old client settles an unknown 409 without a retry (`chat.ts` `settled`). The old
    `scene_change` / `price_change` branches of `build` are deleted.
```
A read that succeeded before this change is replayed from `chat_reads.response_json` as it was stored (same key, same body, same hash). Its old card shape is converted on the client (below).

**Where the current words come from (the server, inside the admission transaction's read):** `visual_id` must be one of the versions that `GET /api/creations/{id}/visuals` lists for this poster (same shop, same product input, same size: the query of `api.py` `creation_visuals`, moved to one function used by both; a copy of a poster shares its versions). `baked_headline(visual)` gives what that version was asked to draw: `title`, `brand`, `subtitle`, and `price_ar` when the price is drawn; nothing when the version has no drawn words. These are **the image's words**. The document gives `offer.title` and `offer.price_ar`, **the document's words**; they differ from the image's after an edit that was not followed by a new image. The client saves first: `ask` awaits the editor's `flush()` before a new read leaves (a kept pending body is sent as it is); if the save fails the message stays in the composer with the editor's sentence and nothing is read. The editor's refs and `localStorage` are not read: they are filled only when a poster is opened and are stored nowhere once a version has a headline.

**What the model returns on a poster:** `{title, brand, subtitle, price_ar, remove, instruction_fr}`; each field null when the owner did not ask to change it; `remove` lists `brand` or `subtitle` to take off (an explicit list: an empty string is easy to confuse with null). The rule of each field is its `description` in the schema (`wire_schema` keeps descriptions). The data sent is the message, the last lines and the current words. It has its own short system prompt (data is never an instruction; a field not asked stays null; `instruction_fr` is only about the picture). The new-poster prompt and schema stay as measured in T-CHAT-002.

**Server checks, in this order (the model is not trusted):**
1. **Words first.** When any of `title`, `brand`, `subtitle`, `price_ar`, `remove` is present, `instruction_fr` is dropped before it is screened, and the card's text ends with « Demandez ensuite le changement de scène : il partira de la nouvelle version. ». A whole new scene cannot take a refinement instruction (`/scenes` has no such field), and the refinement screen refuses the word « titre », which would refuse the whole change.
2. **Brand set apart.** When the reader returned a `brand` (even the one already stored), the title after the change is cut on spaces, and the run of whole tokens whose words (`name_words`) are the brand's words is taken out. Separators left at either end (spaces and `- – — : | / · ,`) and empty brackets are removed. The shorter title is part of the change. When the version's coloured word (`accent_word`) is no longer in the title, the card adds the line « Le mot en couleur est retiré. » (the editor drops it, `App.vue` `accentWord`). Nothing left of the title, or the brand found only inside a token (« Sony-WH »): `refused`, « Écrivez le titre sans la marque. ». Reason: `request_scene` compiles with `deduplicate_brand=True`, which drops a brand that is inside the title, so the paid image would show no brand line.
3. **Each field's check** from the table. The title's check depends on the version: drawn words → `name_refusal`; no drawn words → `Offer`. A refusal answers `refused` with that rule's sentence and no change card: a change is whole or not offered.
4. **Word guard.** Every word (`name_words`) of a returned `title`, `brand` or `subtitle` must be a word of the owner's message or of the current title, brand or subtitle. Otherwise `refused`, « Je ne peux pas écrire « {word} » : ce mot n’est ni dans votre message ni sur l’affiche. ». What this guarantees: the model brings no word of its own. What it does not: it cannot tell a wrong recombination of the owner's own words (« RAM 8 Go, stockage 128 Go » → « RAM 128 Go »). Against that, the card shows each text whole on its own line before the paid tap, and the review shows it again. R-TEXT-FIRST-005 is worded to this.
5. **The result and the effect**, one rule for every field. The result is the document's title and price (the owner's latest words, drawn or not yet, as « Nouvelle version » uses them) and the image's brand and subtitle, with the returned fields and removals applied. On a `scene` card each line is a difference with what the image shows, so a title edited in « Pas à pas » and never drawn has its line too (corrected during T-CHAT-006: starting from the image's title would silently undo that edit).
   - an instruction only → `refine`;
   - the result differs from the image's words in a word the version draws → `scene`, and the card carries the four resulting words;
   - otherwise, the result differs from the document's words → `free`, and the card carries the document fields to set. This is the price as a layer, the title as a layer, and also a request that puts the document back to what the image shows (« remets 450 000 Ar »): no image is paid for that;
   - otherwise → card `same`, « L’affiche a déjà ces textes. »;
   - `brand`, `subtitle` or `remove` on a version without drawn words (a requirements exception, ADR-099: a brand and a subtitle exist only as drawn words; such a poster has neither as a layer) → card `steps`, « Cette affiche n’a pas de textes dessinés dans l’image : la marque et le sous-titre se règlent dans Pas à pas. ».

`text_fr` is one line per field from the table's labels: « Marque : Sony », « Titre : WH-CH720N », « Sous-titre : retiré », « Prix : 450 000 Ar », « Scène : « fond plus sombre » ». `card_unclear_poster` becomes « Dites ce qu’il faut changer : {the table's labels}. Le reste se change dans Pas à pas. ».

**The client (`chat.ts`, `ChatView.vue`):**
- The read on a poster sends `visual_id` = the version shown (`looked ?? selected`), or the selected one when the shown one is refused. A change is asked on the version the owner looks at, checked or not.
- One change card. Its button follows `effect`: `refine` « Créer · cost »; `scene` « Refaire l’affiche · cost »; `free` « Changer ».
- **One converter `normal(card)`**, used by `readThread` and by `ask` (the two places a card enters): a stored `change: 'scene'` becomes `effect: 'refine'`; a stored `change: 'price'` becomes `words: {price_ar}` with **no** `effect`. A card without `effect` or `visual_id` is an old one: it targets the selected version, sets only its own fields (as `reprice` did), and its effect is today's rule, kept in one function `effectOf(card, version)`: `whole`, or a drawn price in the selected version → `scene`; otherwise `free` (the body of today's `freePrice`). A card that already holds its kept request is replayed as it left, whatever its shape. `whole` (after `headline_stale`) stays.

**The adapter (`App.vue`):**
- `revise(card, visual, words, smallPhotoAccepted, owned, sending)` replaces `reprice`:
  1. `select(visual, owned)` if it is not the selected one: `select` takes the ownership check and calls it after its own awaited refresh, right before it changes and saves the document (a tab that lost the chat changes nothing). A version that is no longer listed: « Cette version n’existe plus. », nothing sent;
  2. if « Textes dans l’image » is off in the editor (`headline.on` false): stop with « Les textes dessinés sont désactivés pour cette affiche : réglez-les dans Pas à pas. ». Nothing is sent: the request would not carry the words the card lists;
  3. `flush()`, `owned()`;
  4. the four words of the card through the editor's setters, each one set, changed or not: `edit(d => d.offer.title = …, 'title')`, `typePrice`, `headline.value.brand`, `headline.value.subtitle` (null → empty);
  5. `createScene(card, sending)`.
- `words(visual, values, owned)` replaces `price`: `select(visual, owned)`, `flush`, `owned`, the document setters, `flush`.
- `change(card, visual, instruction, owned, sending)`: `select(visual, owned)`, then as today.
- `saved()`: the editor's `flush()`, for the read.

**Amended by ADR-100 (2026-11-15, after the paid test):** the new image keeps the version's style. `revise` runs `restoreHeadline()` on the card's version, takes its model image, and reuses its plan as a revision at the document's revision instead of asking a fresh plan; `createScene` is used only when that plan belongs to another poster or format, or is missing. The paragraph below describes what held before this amendment and still holds for that fallback.

**Amended by ADR-101 (2026-11-15, after the paid check of ADR-100):** the chat's scene request carries `keep_adjustments_of`, the card's version; `request_scene` adds the scene adjustments of that version's chain to the prompt and stores them with the job.

**What the card promises, and what it does not.** The words: the new image is asked with exactly the title, brand and subtitle that the card lists, and the document holds exactly the card's price, because all four are set from the card at the tap. Whether the price is drawn in the image or laid over it is the editor's switch (`headline.price`), like the other settings below; the amount is the card's in both cases; a subtitle typed in « Pas à pas » and never drawn cannot slip in. Everything else of the request (style, coloured word, contact line, logo seal, style reference, plain-lettering brand) is the editor's state at the tap, through `createScene`, exactly as for today's price card (ADR-098: "look, brand and contact stay the poster's") and for « Nouvelle version » in the editor. The plan itself is made from that state (`createScene` → `prepareScene`), so the server cannot rebuild it from the version alone, and `restoreHeadline()` restores only part of it. The card therefore says « Refaire l’affiche » and lists words; it does not claim the same scene. This is a stated limit, not a new one.

**After a paid card that did not make an image.** Only the title and the price are saved in the document before the scene is asked; the brand and the subtitle live in the request alone. The editor already computes the truth: `staleTitle` and `stalePrice` compare the document with the selected version's stored words, and block the export. `ChatAdapter.state` gains `stale: { title?: string; price_ar?: number }`: the selected version's stored `headline.title` and `headline.price_ar`, each present only when it exists and differs from the document. A version without stored words gives nothing here (its hidden-layer case stays the editor's, as today). While it is not empty and no paid card is unresolved, the newest unspent change card, or a line under the poster when there is none, says « L’affiche montre encore : {the image's words}. » with « Remettre les textes de l’image » → `words(selected, stale)`. `Card.previous` is no longer written; `normal` drops it. This holds after any number of later cards, a reload, or an edit made in « Pas à pas ». ADR-097 and ADR-098 do not change: one unresolved paid card, the card's id is the key, the kept request is replayed as it left, a card is retired only on a final refusal.

**List of modifications:** the label of a version made by a new scene is the difference of its `headline` with the version before, with the table's labels (« Marque : Sony · Titre : WH-CH720N »); no difference: « Nouvelle version ». `Visual.headline` gains `subtitle` in the TypeScript type (the server already sends it).

**Stub reader:** on a poster, « marque X », « titre X », « sous-titre X » (to the end of the message), « sans marque », « sans sous-titre », the first candidate amount, « fond » or « lumière »; nothing else.

**Failure modes & handling:**
| Failure | Detection | Behavior |
|---|---|---|
| The model returns a word nobody wrote | word guard | `refused`, the word named; nothing is changed |
| The model recombines the owner's words wrongly, or splits brand and title wrongly | none on the server | each text is whole on its own line of the card before the paid tap; « Annuler » puts the message back; the review shows the words again |
| The reader puts the lettering request in `instruction_fr` only | the refinement screen | `refused` with the existing sentence; counted in the paid test |
| The title is saved, then the scene request is refused, lost or fails | `state.stale` | « L’affiche montre encore … » and « Remettre les textes de l’image », until the document and the image agree |
| The selected version changes between the read and the tap | the card holds `visual_id` | the adapter selects that version first; if that fails the card shows the editor's sentence and nothing is sent |
| « Textes dans l’image » was switched off in « Pas à pas » after the version was made | `revise` step 2 | nothing is sent; the sentence points to « Pas à pas » |
| The style or the contact line was changed in « Pas à pas » since the version | none; stated limit | the new image follows the editor's current settings, as « Nouvelle version » does |
| An unsaved edit of « Pas à pas » when a message is sent | `saved()` before the read | the read waits for the save; a failed save keeps the message and reads nothing |
| The tab lost the chat while a version was being selected | `owned()` before and after `select` | nothing more is changed, nothing is sent |
| A read from an old bundle, or kept from before | `visual_id` absent | 409 `reload_required`, nothing paid |
| The reader is down, slow, or over the cap | D-002, unchanged | D-002, unchanged |

**Edge cases:** « enlève la marque » without a brand: `same`. « mets Samsung » on a Sony poster: passes the guard (the owner wrote it); the card line and the review are the guard. A brand already stored and inside the title, asked again: check 2 takes it out of the title, so the change is real. A price and a brand in one message: one card, one scene. A version without drawn words and a title change: `free`. A twelfth version: the existing limit line and refusal. Malagasy message: read like any other.

**Security / data notes:** the current words sent to Anthropic are the shop's own text, read by the server from its own data (text only, as today). The output fills typed fields only. `visual_id` is checked for ownership before any spend.

**What this does not do:** lettering requests that are not a field (size, place, font of the title), the accent word, the format, the style, the photos. `chat_reads` keeps a hash of each message, not its text, so the requests the chat could not take can be counted (`unclear` in `response_json`) but not read; keeping the text needs a migration and a decision on keeping the owner's words, and is left to the user.

**What changed from v3 (round 3):** brand and subtitle on a poster without drawn words are an explicit exception in the requirements (P1); `select` takes the ownership check and runs it before its own mutations, and `words` checks after its flush (P2); the price promise is the amount, not whether it is drawn (P2); the smoke for texts switched off expects a refusal (P2).

**What changed from v2 (round 2):** the claim "the version's settings plus the card" is replaced by a narrower one that is true: the four words come whole from the card, the rest is the editor's state as for every new version (P1-1); old price cards keep today's free rule through `effectOf` (P1-2); `owned()` around `select` (P2-3); a save before each read (P2-4); `stale` only from stored words, and the effect compares the result with the image's words, so going back to them is free (P2-5); a version is accepted by the listing's own rule, copies included (P2-6); separators after a removed brand, and the coloured word that goes with it (P2-7); the key is looked up before `reload_required`.

**What changed from v1, and why:**
| v1 | v2 | Source |
|---|---|---|
| The client sends the current words from the editor's refs | The client sends `visual_id`; the server reads the words from the version's job and the document | Devil's advocate 2: the refs are filled only at `adopt` and stored nowhere; false `same`, unlisted subtitle |
| `words` in every body | `visual_id`, left out of the hash when absent | Review P1-1, devil's advocate: `payload_sha` of kept requests |
| Old schema kept one release for bodies without `words` | 409 `reload_required` before admission; old branches deleted | The pilot has one user and no read yet; one path instead of two |
| Old cards converted in `readThread` | One `normal(card)` at both entries | Review P1-1 |
| Brand set apart only when the brand changed | Whenever the reader returns a brand, before the "equal" check; token rule written | Review P1-2, devil's advocate 1 and P2 |
| Instruction screened, then dropped | Dropped first when words are present | Devil's advocate 1 |
| The client decides the cost from the selected version | The server states `effect` and the resulting words; `revise` sets all four | Review P1-4, P2-7 |
| `previous` kept on the card for « Remettre » | `state.stale` from the editor's `staleTitle` / `stalePrice` | Devil's advocate 3, review P2-5 |
| Title always 1 to 60 | 60 when drawn, 240 as a layer | Review P2-6 |
| `""` removes | `remove` list in the model's answer; null in the card's resulting words | Devil's advocate P2 |
| The word guard "closes" invention | Its limit is written; the refused word is named; the requirement is reworded | Review P1-3 |
| New-poster reader loses `intent` | Not touched | Review, "simpler logic" |

## D-TEXT-FIRST-006 — The rest of the audit: a style change, the shop's identity in the first message, a sentence for the format (v2)

**Status:** v2, 2026-11-15, approved under the user's autonomy grant, renewed the same day ("you can go full automation"; ADR-103). It replaces draft v1 (in the history at commit "Rest of the chat audit: a rejected draft…"), which the fresh review rejected (four P1) and the devil's advocate challenged ([review](../reviews/text-first-d006-design-r1-2026-11-15.md), [devil's advocate](../reviews/text-first-d006-devils-advocate-2026-11-15.md)). v2 is what is left after the paid baseline ([report](../reviews/chat-change-eval-2026-11-15.md), last section): a coloured word and the brand's lettering already work as scene adjustments and get nothing; a style change does not work and gets one field; identity and format get the smallest thing that is true. v2 answers the review's four P1 by what it removes (no settings rows, no `rows` marker, no `carries`, no identity rule) and by the rules marked "review" below. Its code reviews check it; no second design round was run.

**1. Style of an existing poster (field `style` of the poster reader).**
- Reader: `style: "clair" | "couleur" | "sombre" | null`, not null only when the owner asks for another of the three provided styles by its name or its plain description. It is a row of `FIELDS` for the schema and the sentence (« le style »).
- Card: a **new kind, `restyle`** (review P1-1: a tab on the old bundle shows an unknown kind as text with no paid button, so it cannot pay for a card it would carry out wrongly). `{kind: "restyle", text_fr, visual_id, style, words}`: `words` are the four resulting words as on a `scene` card (word changes asked in the same message are in them, with their lines and checks). Lines: « Style : Luxe sombre », then « L’affiche modèle n’est plus suivie. » when the version has a `style_reference_asset`, and « Les ajustements de scène demandés avant ne sont pas repris. » when its chain has kept adjustments. A style asked on a version without drawn words: `steps`.
- No comparison with the current style: the id of a provided style is not stored with a version. Asking for the style it already has redraws it; the button says « Refaire l’affiche ».
- Adapter `revise(…, style)`: as today up to `setWords`, then `pickLook(style)`; if the photo's colours are being read, wait, then **`owned()` right after the wait** (review P1-4); `paletteBlocked` → stop with its sentence, nothing sent; the model image is dropped (`styleReference = null`); `keptFrom` and `keptAlign` are not set (a kept « fond bleu nuit » would win over the new style, ADR-101); then `createScene(key, sending, owned)`: a fresh plan in the new style. The version's drawn settings (brand lettering, contact, accent word) come from `restoreHeadline`, before `pickLook`; the accent colour follows the style, as in the editor (« Luxe sombre » is gold). There is no colour field, so no asked colour can be lost (review P1-3).
- Everything of ADR-097/098 holds: the card is paid, spent before sending, its id is the key, retired only on a final refusal; after it the new version becomes the poster's, as for a `change` card.

**2. The shop's logo and contact, in the first message only.**
- A scene adjustment must never draw them: the logo is a file, the contact is data. On a new poster the editor already places them when the poster is made (`createPoster`: `brand_selection`, then `placeLogo`).
- New-poster reader: one field, `identity: true | false | null` (the owner asks for the shop's logo or contact on the poster, or asks to leave them off). **This changes the bytes sent for a new poster, so the reading test of 2026-11-14 is run again** (the 26 messages, plus identity ones) before it is called working.
- The recap card shows a line « Avec le logo et le contact de la boutique » when the draft has it, and the tap sets the editor's own selection before `createPoster`. Only what the shop's profile holds is turned on; with an empty profile the line says « La boutique n’a pas encore de logo ni de contact : ajoutez-les dans Pas à pas. » and nothing is turned on. The contact is drawn in the image or laid over it by the editor's own rule; the chat does not choose.
- On an existing poster: field `identity` of the poster reader → card `steps`, « Le logo et le contact de la boutique se règlent dans Pas à pas, « Boutique ». ». Nothing is changed (the devil's advocate confirmed that a free removal breaks the version's plan for every later change).

**3. Another format.** Field `format: true | null` of the poster reader → card `steps`, « Un autre format est une nouvelle affiche : dans Pas à pas, « Style », « Refaire en … ». ». Nothing is copied.

**Order of the three answers on a poster:** `format`, then `identity`, each a `steps` card alone; then `style` (a `restyle` card); then D-005's steps.

**No data model change, no migration, no new route.** A stored thread without these cards is untouched; a `restyle` card in an old tab is text.

**Failure modes:** the reader takes « luxe sombre » for a scene adjustment → a refinement that changes little (the baseline's result), one image lost, the list line says what was asked; counted in the paid test. The reader takes « mets le logo Sony » for the shop's logo → a `steps` sentence instead of an adjustment; counted in the paid test. The fresh plan is refused (`layout_not_plannable`) → the card fails with the server's sentence, nothing paid. Everything else as D-005.

**Not done:** the coloured word, the brand's lettering (already scene adjustments); identity on an existing poster; the seal, positions, the shop's name alone; a saved style and « Décrire moi-même »; another format made from the chat.

## D-TEXT-FIRST-007 — Images on an existing poster (covers the ADR-126 amendment of R-TEXT-FIRST-004)

**Status:** v5, 2026-11-21, under the owner's word ("handle now … yes copy with the new photo"; then, after four rejected rounds, "when blocked, think of another way it can be done, without keeping on polishing it"). v1 to v4 made the copy and its first image in the chat; their reviews ([r1](../reviews/chat-photo-design-r1-2026-11-21.md), [r2](../reviews/chat-photo-r2-2026-11-21.md), [r3](../reviews/chat-photo-r3-2026-11-21.md), [r4](../reviews/chat-photo-r4-2026-11-21.md), and the [devil's advocate](../reviews/chat-photo-design-devils-advocate-2026-11-21.md)) each found a new way to pay wrongly, from round 2 on always in the recap that the chat added by itself for the copy. v5 is another way, not a fifth patch: **the copy is the editor's own action, as « Refaire en … », and its image is the editor's own « Générer l’affiche ». The chat adds no paid card, keeps no request and writes no other poster's thread.** Page only: no server change, no new route, no new paid path, no change to an existing paid path.

**What the server already has.** A version belongs to a product input, and a poster's input never changes (`input_immutable`). `POST /api/product-inputs` takes `supersedes_id` (the new input keeps the product's reference). `POST /api/creations/{id}/copies` with `reason: replace_input` copies a stored revision onto another input: the copy has no scene and no cut-out layer (store.py `copy_creation`). « Refaire en … » (`remakeIn`, released) already makes such a copy and opens it without a version, to be generated in « Pas à pas ».

**1. Attaching.** On an existing poster every attached image is a product photo: up to three per message, counted on the tray alone, each uploaded as an original; the label says « Produit » in plain words, with nothing to swap. On a new poster nothing changes. On an existing poster the thread's draft no longer takes the images of a message.

**2. Sending.** On an existing poster, with or without a version, a message with images is not read: no paid read leaves, and no save is forced before it. The bubble shows the words and the images, earlier open cards are superseded, and the chat adds a `photo` card that holds the message's `pictures`: « Cette affiche garde sa photo. Je peux en faire une copie avec la nouvelle photo : même titre, même prix. La copie s’ouvre dans Pas à pas, où vous créez son image. L’affiche actuelle reste dans Mes affiches. » (« les nouvelles photos »), and, when words came with the images, « Votre message n’est pas lu avec une photo : envoyez-le ensuite. » The sentence « Les photos d’une affiche se changent dans Pas à pas » and its branch are removed.

**3. The `photo` card.** A kind the released bundle does not know: there it is text, with no button. It is not a paid card (`paid`, `changes`, `unresolved` and `reconcile` never see it). While it is not done it shows « Copier avec cette photo » (« ces photos »), off while anything runs or while images wait in the tray, with « La copie est gratuite. Sa nouvelle image coûtera 1 crédit. » under it, and « Annuler ». What stops a new image stops the copy, which would stay without one: with no credit or a blocked shop the card says the credit line's sentence and has no copy button; with the conditions not accepted it offers « Lire les conditions », as a paid card does. Its product photos are its `pictures` of role product, distinct, three at most, checked as stored data is.

**4. The copy: the adapter's `remake(photos, owned, made)`,** under the editor's busy guard; `owned` throws when this tab no longer holds the chat. While it runs no image can be attached.
1. the editor's pending save is flushed; the source input is read;
2. `POST /api/product-inputs` (`name`, `variant`, `facts` of the source input, `supersedes_id` its id, `photo_assets` the card's). The input made is kept in the page for a second tap with the same poster and photos, as `createPoster` keeps its own;
3. `POST /api/creations/{id}/copies` (`source_revision` the saved revision, `reason: 'replace_input'`, `new_input_id`);
4. `made()`: the card is done, with « La copie est créée : retrouvez-la dans Mes affiches. Cette affiche reste telle quelle. » (true whether or not it opens), stored when this tab still holds the chat;
5. the copy is prepared where it is stored, before it is opened and whether or not it is ([round 5](../reviews/chat-photo-r5-2026-11-21.md): the answer of step 3 may be the stored one of an earlier tap, and the copy may have been opened and edited since, so nothing is written over it after it opens):
   - the brand, subtitle and coloured word of the open poster go under the copy's own key (`keepWords`), only when it has none: `adopt` reads them for a poster without a version (ADR-083);
   - the title and price layers that the source's scene had hidden are shown again, and the shop's name and contact as `include` says (no layer moves): one `PUT` of the copy's document at its creation revision. The server refuses it once the copy was saved by anyone: it is then left as it is;
6. `openCreation(id, the address the tap was made at, not as chat)`: the copy is read from the server as it is now, and opened in « Pas à pas » unless the owner has gone elsewhere. Opened without a version, the editor goes to the « Style » step and says « Copie de l’affiche avec la nouvelle photo, sans version : générez-la quand vous êtes prêt. L’affiche d’origine est conservée. » What stops or cuts short the opening is said by the editor itself (« La copie est dans Mes affiches, mais son chargement est incomplet (…). »): the chat may already be closed, and the copy may already be on the screen.

The image is then « Générer l’affiche » and its confirmation, as for any poster without a version: the editor's cost line, conditions, small-photo question and lost-answer handling, unchanged.

**5. A recap on an existing poster.** The thread's draft may hold images that the released bundle put there by mistake, under either role. On an existing poster a recap therefore shows no thumbnail from the draft (the poster is beside it), and « comme votre inspiration » follows the editor's own model image (`state.styleReference`), which is what `start` sends.

**6. « Annuler » on a photo card** takes the card away and puts its words back in the field only when the field is empty: words typed since are kept.

**Failure modes.**
- *The copy's answer is lost:* the card stays with the editor's sentence. The same tap on this page reuses the kept input and the kept key of the unanswered request: the server answers the copy it stored. One copy.
- *The page is reloaded before that second tap, or the poster was edited in between:* a second tap makes a second copy. It costs nothing, has no image, and « Retirer de la liste » removes it; the same holds for « Refaire en … » today. Accepted: keeping the keys in the thread is what v2 to v4 did, with the storage and recovery rules that came with it.
- *The input or the copy is refused* (an asset that is not the shop's, the shop suspended): the server's sentence under the card, which stays; nothing was made, or one input that no poster uses.
- *The copy is made and cannot be opened:* the card is done, the editor's line says why; the copy is in « Mes affiches », prepared.
- *The preparing save is refused or lost:* the copy keeps the hidden title and price of its source until its first image draws them. The editor's two sentences « … est dessiné dans l’image » now wait for a version, so nothing false is said.
- *Known and left ([round 6](../reviews/chat-photo-r6-2026-11-21.md)):* the copy's words are seeded only when it has none, but another tab editing that same copy at that same instant, after its words entry was evicted, could be written over. It needs a lost answer, the copy open elsewhere, more than thirty posters' words kept since, and a keystroke in the same millisecond.
- *The tab loses the chat between two requests:* `owned` stops the next one. After the copy exists the work is the editor's, in this tab, like any edit made in a tab that does not hold the chat; the chat's thread is written only by the tab that holds it.
- *Money:* nothing here takes a credit or asks a provider. No paid request is added, changed or moved.

**Edge cases.** An unsaved edit of « Pas à pas » is saved before the copy. The copy's input carries the source's name, variant and facts: a photo of another product gives a poster of the old product's words (the card says « même titre, même prix »; another product is a new poster). Two posters then have the same title in « Mes affiches »: the copy is the newer one, without an image until it is generated. A poster without a version, opened in the chat, is answered « L’affiche n’a pas encore de version. » as before: its image is made in « Pas à pas ».

**Not done:** the copy's image asked in the chat (v2 to v4); an inspiration image on an existing poster (v1); reading the message sent with the images; a photo control in « Pas à pas ».

## Tests

- **D-007 (v5):** Vitest: `photo` has the copy button, none when done, none without a product photo, none under a stop (the conditions offered); it is not `paid`; its photos are distinct and three at most; `warns` and `asksText` (ADR-125). Browser smoke (chat, `walk_photo`): the warning under a features request and not under « fond plus sombre »; on an existing poster a photo sent with words makes no read and gives the card, labelled « Produit » with nothing to swap; the copy's answer lost, then the same tap: one input (the new asset, `supersedes_id`) and one copy; the copy opens in « Pas à pas » with the notice, without a version, its title and price shown again, its layers the source's; the source's revision and document unchanged; no read, no scene, no refinement; « Générer l’affiche » is offered; back in the source's chat the card is done and no paid card was added. The editor's confirmation: the warning under « Ajoute ses caractéristiques », not under « Podium plus petit ».

- **D-006 (v2):** backend: the three fields in the poster schema and the sentence; `restyle` card (lines, warnings, with a word change, without drawn words); `format` and `identity` give `steps` alone; `identity` on a new poster merges into the draft; the stub. Vitest: an unknown kind has no button in `cardButton`; `restyle` is paid; the recap's identity line. Browser smoke: a style change makes a new plan (not a revision of the version's), with no model image and no `keep_adjustments_of`, and the new version becomes the poster's; ownership lost during the palette wait sends nothing; a first poster asked with the shop's identity has it in the document; format and identity sentences on a poster. Paid: the 26 new-poster messages of 2026-11-14 again plus identity ones; style, identity and format messages on a poster; one real style change; one real first poster with the logo and contact.
- **D-005, backend:** the field table drives the schema, the card lines and the sentence (a row added in a test appears in all three); each check in its order; words with an instruction containing « titre »; brand set apart (the report's own message; the brand already stored and inside the title; the title that would be empty; the brand inside a token); the word guard (a new word named, case and accents, a word of the current title, « garantie 2 ans »; the recombination case passes and is documented); `remove`; `same`; `effect` for each row (drawn and layer title, drawn and layer price, version without words); the title limit 60 or 240; `visual_id` of another poster; a body without `visual_id` has the hash it had before and answers 409 with no ledger row; a stored old answer replays unchanged; the stub.
- **Order as built (T-CHAT-006):** the `steps` answer is given right after "words first", before the brand is set apart, so that a brand asked on a poster without drawn words is never answered « Écrivez le titre sans la marque ». A dropped instruction on a `same` card is not mentioned. The card's lines follow the table's order.
- **ADR-100:** browser smoke: the plan of the version made by a word change is a revision of the plan of the version it replaces, with the same colours. Paid: one real word change on a dark poster keeps its look.
- **D-005, backend, added in v3:** a version of a copied poster is accepted; going back to the image's words is `free`; separators and the coloured word after a removed brand; a known key without `visual_id` replays, a new one is refused with no row.
- **D-005, frontend (Vitest):** `normal` (old price card, old scene card, a numeric `previous`); `effectOf` for an old price card on a drawn and on a layer price, and with `whole`; the button for each `effect`; the modification labels; `stale` with and without stored words.
- **D-005, browser smoke, added in v3:** an old layer-price card is still free; an unsaved step edit before a message; the chat taken by another tab during a selection; a subtitle typed in steps and never drawn is not in the request.
- **D-005, browser smoke (stub):** the report's message on an unchecked version to a new version to check, with its list line; a change asked while an older version is shown; a subtitle removed; a free title change on a poster without drawn words; « Textes dans l’image » switched off in steps, then a brand by message (refused with its sentence, no request, no spend); a refused scene after the title edit, then a later price card, « Remettre les textes de l’image » still offered; reload between the edit and the request; a kept old price card; an old stored answer received after the upgrade.
- **D-005, paid (needs the user's word; about USD 0.10 for the reads and one scene at the pilot's price):** about twenty real change messages, the report's own included, with cost, delay and every wrong field; one real brand change through the chat.
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
