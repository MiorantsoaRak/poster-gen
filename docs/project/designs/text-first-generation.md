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

## D-TEXT-FIRST-006 — Settings of the next image as rows of the field table (covers the second 2026-11-15 amendment of R-TEXT-FIRST-004)

**Status:** draft v1, 2026-11-15. **NOT approved, not to be built as written.** The fresh review rejected it ([round 1](../reviews/text-first-d006-design-r1-2026-11-15.md): four P1: an old tab can take over a stored settings card and pay while ignoring its settings; the guard before paying misses settings the card does not list; a style overwrites a colour asked in the same message; no ownership check after the palette wait). The devil's advocate ([report](../reviews/text-first-d006-devils-advocate-2026-11-15.md)) argued that its premise is out of date: since ADR-102 a message that changes no word is already a scene adjustment from the image shown, so the coloured word, the plain-letters brand and the style may already work, and nobody measured that. Next step, the user's word: a paid baseline of those three through today's scene adjustment; then only what fails is designed again, smaller. Kept below as the record of the reading of the code (its table "What the code says" was confirmed by the review).

**Problem:** D-005 gave the chat the four words and the scene adjustment. The audit's mechanism 2 lists five more things that « Pas à pas » sets for the next image and the chat cannot: the coloured word, the brand in plain letters, the shop's identity, the style, the format. Three of them (A, B, D) are fields of the scene request and fit the table as it is. Two (C, E) are not only fields: C changes the document and the plan's regions; E makes another poster.

**Approach:** the table gains rows marked `setting`. A setting is not a word: its current value is read from the version's stored headline or from the document, its change is carried on the card as `settings`, and the adapter sets it through the editor's own state after `restoreHeadline()`, so everything the card does not list stays the version's (ADR-100, ADR-101). One guard in the adapter compares the request about to leave with the card and stops before paying when they differ. C is built in a smaller version (logo at the top right, contact drawn); E is answered by a sentence, and its full version is the last task, built only on the user's word.

### What the code says (A to E)

| | Where the editor keeps it | How it reaches the image or the document | What a version stores | Editor's refusals |
|---|---|---|---|---|
| **A** coloured word, colour | `headline.accent_word`, `headline.accent_colour` (`App.vue:38`); offered words `accentWords` (`:305`); five colours `ACCENTS` (`:306`) plus a free colour input (`:1588`) | `headlineBody()` (`App.vue:307`): `accent_word` only if it is still in the title (`accentWord`, `:304`), `accent_colour` = `sceneAccent` (`:55`: the photo's colour when the look is « Couleurs du produit ») | `headline.accent_word`, `headline.accent_colour` in the job payload (`visuals.py:284`); `poster_words` already returns `accent_word` (`reads.py:484`) | server: `headline_accent_not_in_title` (`plans.py:375`) → `invalid_headline` |
| **B** brand in plain letters | `headline.brand_text` (`App.vue:38`, switch at `:1592`, shown only with a brand) | `headlineBody()`: `brand_text: true` only with a non-empty brand (`:307`); prompt sentence `plans.py:382-384` | `headline.brand_text: true` when set, absent otherwise (`plans.py:95`) | server: `brand_text_requires_brand` (`plans.py:380`); no effect when the brand is inside the title (`deduplicate_brand`, `plans.py:381`) |
| **C** logo, shop name, contact | `document.include` (`models.py:82-85`), the layers, `brand_snapshot`; drawn contact: `headline.contact` (`App.vue:38`, switch `:1609`); position: `rememberedAlign` in `localStorage` (`:244-250`); seal: `logo.shape = 'circle'` (`setSeal`, `:387-390`) | switches → `edit(d => toggleIdentity(d, role, on))` (`:1596`, `:401-412`, `document.ts:63-77`); drawn contact → `headlineBody()` `signature`, `signature_align`, `logo_seal` when `drawContact` / `sealOn` (`:369`, `:381`); the plan's regions come from the included layers (`context_for`, `visuals.py:135-150`) | drawn contact: `headline.contact` (`visuals.py:253`, `:284`); logo place: the plan's `logo` region → `logo_box` / `logo_footer_box` (`logo_region`, `visuals.py:367-374`); seal: `placement_json.logo_disc` (`service.py:139-147`) | `whyNoDrawnContact` (`:363-368`: several lines, `"`, too long); `whyNoSeal` (`:374-379`: after the first version « créez une copie »); `staleLogo` (`:335`), `discUncovered` (`:382-386`), `staleSignature` (`:740`) block the export (`:681`; server `check_logo_placement`, `visuals.py:377-390`, `signature_missing`, `exports.py:49-53`); a missing shop detail cannot be ticked (`identitySource`, `:541`) |
| **D** style | `look` (`App.vue:51`), `direction` (`:35`), `LOOKS` (`:42-47`), `savedLooks` | `pickLook` (`:104-111`) sets `direction` and, for « Luxe sombre », the accent colour; `prepareScene` (`:1049-1066`) asks a plan with `direction` and lays the look's palette on it; a saved look also sends `look_id` (`:307`) | the plan (`scene`, `palette`; `visual.plan_id`, `visuals.py:408`); `headline.look_id` for a saved look. **The id of a provided style is stored nowhere.** | `paletteBlocked` (`:56`) while the photo's colours are unread |
| **E** format | `document.primary_format`; « Refaire en … » (`:1614`) → `remakeIn(to)` (`:190-209`) | a new product input, a copy of the poster onto it (`store.py:302-328`), `reformat` (`document.ts:92-105`), then `adopt(copy)`: **the open poster becomes the copy, which has no version** | the version's `size`; a copy in another format shares no version (`listed_visuals`, `visuals.py:393-399`) | `format_locked` after a first version (`store.py:267-280`); formats offered = `FORMATS_ENABLED` (pilot: `feed,square,story`, `deploy/compose.yml:32`) |

**Three findings that shape the design:**
1. **A plan cannot be reused when the identity changes.** `validate_plan` refuses a plan whose regions are not exactly the included fields (`plans.py:188-189`), and `revise_plan` validates against the document's current context (`visuals.py:201-207`). ADR-100's "revise the version's plan" therefore answers `invalid_plan` after a logo or a contact is switched. The regions must be made again (`POST /plans`, mode `fixed`: free, synchronous, `visuals.py:185-191`; `plannerMode` is always `'fixed'`, `App.vue:35`); the look is kept by laying the version's `scene` and `palette` on the fresh plan, as `prepareScene` already does for a saved look (`:1057-1060`). The prompt reads the look from `plan.scene` and `plan.palette` only (`plans.py:509-510`).
2. **Layers are placed in the plan's regions for the first version only** (`service.py:153-171`). On a later version a laid-over shop name or contact stays where `setIdentity` put it (`document.ts:72`), not where the new image kept room. The logo is the exception: `chooseVisual` moves it to the version's `logo_box` (`App.vue:1337-1338`). The chat does not mount the canvas, so nothing measures an overlap. This is why the shop name and a contact that is not drawn stay in « Pas à pas ».
3. **`headlineBody()` drops silently what cannot be sent** (an accent that left the title, `brand_text` without a brand, a contact that is not drawable). A card that lists such a change would pay for an image without it. Hence the guard `carries` below.

### Recommendation per item

| | Effect | Cost | Verdict |
|---|---|---|---|
| A | whole new image, the version's plan and words kept | one image | **simple rows** (`accent_word`, `accent_colour`) |
| B | whole new image, the version's plan and words kept | one image | **simple row** (`brand_text`) |
| D | whole new image with **another** plan (`pickLook` + `createScene`); the version's model image and kept adjustments are **not** carried, and the card says so | one image | **simple row** (`style`, three values), one branch in `revise`. A saved style is not simple (see "What this does not do") |
| C | logo on / contact on: whole new image with fresh regions and the version's look. Off: free when the element is only laid over; a new image when the image carries it (drawn contact, seal disc) | one image, or free | **harder**: a second effect function, a fresh-plan helper, a way back after a failure. Built in the smaller version: `logo` (top right), `contact` (drawn). Shop name, seal, positions: left in « Pas à pas » |
| E | another poster | free copy + one image | **not a row.** Now: the reader recognises the request and the chat says where it is done. Full version: task 7, on the user's word only |

### The new rows (`reads.py` `FIELDS`)

`Row` gains `setting: bool = False` and `since: int = 1`. Setting rows are outside the word guard's "words of the poster" set and outside `card.words`.

| Row (`since: 2`) | Type | Current value comes from | Check, in `_change` | Effect | Label / card line |
|---|---|---|---|---|---|
| `accent_word` (removable) | `str` | the version's `headline.accent_word` | `Headline(accent_word=…)` (`HeadlineText`, `screen_headline`); must be a substring of the **resulting** title (the server's own rule, `plans.py:375`), else `refused` « « {} » n’est pas dans le titre. »; under the word guard | differs from stored → `scene` | « le mot en couleur » / « Mot en couleur : {word} » · « Mot en couleur : retiré » |
| `accent_colour` | `Literal["bleu","bleu nuit","rouge","orange","or"]` → hex by one constant `ACCENT_COLOURS`, the values of `App.vue:306` | the version's `headline.accent_colour`, compared without case | the result has an accent word, else `refused` « Dites quel mot du titre mettre en couleur. » | differs → `scene` | « sa couleur » / « Couleur du mot : {name} » |
| `brand_text` | `bool` | `bool(headline.get("brand_text"))` | `true` needs a brand in the resulting words (set apart, so never inside the title), else `refused` « Donnez d’abord la marque. » | differs → `scene` | « le lettrage de la marque » / « Lettrage de la marque : lettres simples » · « … : comme sur le produit » |
| `style` | `Literal["clair","couleur","sombre"]` (`reads.py:54`) | none: the id of a provided style is not stored | — | always `scene` | « le style » / « Style : {label} », then « L’affiche modèle n’est plus suivie. » when the version has `style_reference_asset`, and « Les ajustements de scène demandés avant ne sont pas repris. » when `kept_adjustments(version)` is not empty |
| `logo` | `bool` | `shown` = `include.logo`; `carried` = the version's plan has a `logo` region or the version has a disc | on: `brand_snapshot.logo_asset`, else `steps` « Cette affiche n’a pas le logo de la boutique : ajoutez-le dans Pas à pas, « Boutique ». » | identity rule below | « le logo de la boutique » / « Logo de la boutique : en haut à droite » · « … : retiré » |
| `contact` | `bool` | `shown` = `include.contact` and (drawn in the version, or its layer visible); `carried` = `"contact" in headline` | on: `brand_snapshot.contact`, else `steps` as for the logo; with `"` or a line break: `steps` with the editor's sentence (`App.vue:365`) | identity rule below | « le contact » / « Contact : dessiné dans l’image » · « Contact : retiré » |
| `format` | `Literal["feed","square","story"]` | `document.primary_format` | — | card `steps`, « Un autre format est une nouvelle affiche : dans Pas à pas, « Style », « Refaire en … ». »; the other fields of the message are not offered. (Task 7 would change this row's effect to `copy`.) | « le format » / — |

Rules written in each row's `rule` (the schema description), to be measured in the paid test: `logo` is the **shop's** logo, never the product brand's mark (that is `instruction_fr`, ADR-102); `accent_colour` is the colour of one word, `style` the look of the whole poster; `brand_text` only when the owner speaks of plain or simple letters, or of the brand's logo being wrong.

**Identity rule (one function for `logo` and `contact`, asked value against the image):**
| Asked | The image carries it (`carried`) | Shown now | Effect |
|---|---|---|---|
| on | — | yes | none (`same` if nothing else changes) |
| on | yes | no | `free` (the layer or the drawn line is there; `toggleIdentity` shows it again, `App.vue:407`, `:411`) |
| on | no | no | `scene` |
| off | drawn contact, or seal disc | — | `scene` (a hidden one blocks the export: `staleSignature`, `discUncovered`) |
| off | no, or a kept logo place | yes | `free` |
| off | — | no, and not carried | none |

**Order in `_change` (additions to D-005's five steps):** `format` first (its `steps` answer); then step 1 as today, with settings counted as "asked" (an instruction with them is dropped with « Demandez ensuite le changement de scène… »); any `since: 2` row asked on a version without drawn words → card `steps`, sentence generalised to « Cette affiche n’a pas de textes dessinés dans l’image : ce changement se règle dans Pas à pas. »; steps 2 to 4 unchanged (the word guard reads `accent_word` only among the settings); step 5: `scene` when a word differs from the image's, or a setting row's effect is `scene`; else `free` when a document word differs or an identity effect is `free`; else `same` / the scene adjustment as today. A card is whole: `scene` carries every asked change, free ones included.

**No data model change. No migration. No new route.**

### API contract additions

```
POST /api/reads
body  + rows?: 2          -- the highest table version this client can carry out. Left out of the canonical body when
                          -- absent (`exclude_if`, as `visual_id`), so kept requests keep their hash. Absent: only rows
                          -- with since <= 1 are in the model's schema, the checks and the "what I can change" sentence:
                          -- a tab on the old bundle gets D-005's behaviour and never a card it cannot carry out.
201 card (kind "change")  + settings?: { accent_word?: string | null, accent_colour?: "#RRGGBB", brand_text?: boolean,
                                         style?: "clair" | "couleur" | "sombre", logo?: boolean, contact?: boolean }
                          -- only the settings that change. effect "scene": with `words` (the four, whole) as today.
                          -- effect "free": `logo` / `contact` only, beside the document words if any.
GET /api/visuals/{id}, GET /api/creations/{id}/visuals: unchanged.
POST /api/creations/{id}/scenes: unchanged. A style card sends no `keep_adjustments_of`.
```
`poster_words` (`reads.py:474-486`) also returns `settings` (stored `accent_word`, `accent_colour`, `brand_text`), `identity` (`{logo, contact}` × `{shown, carried}`, from `document.include`, the contact layer's `visible`, `baked`, `logo_region(...)` and `placement_json`), `snapshot` (which of `logo_asset`, `contact` exist; whether the contact is one line without `"`), `model_image` and `adjustments` (booleans, for the style card's two lines). Nothing of it is sent to the model except `settings`.

### The client

`chat.ts`: `Settings` type; `Card.settings`; the read body sends `rows: 2`; `Stale` gains `identity?: { logo?: boolean; contact?: boolean }`; `staleLine` adds « La boutique sur l’affiche ne correspond plus à l’image. »; the button becomes « Remettre comme sur l’image » and sends both the stale words and `stale.identity`. `differences` (`chat.ts:209-216`) also compares `accent_word` and `brand_text`, so the list of modifications says « Mot en couleur : Buds ». A style or identity version is labelled « Nouvelle version » (its cause is not stored; see limits). `ChatView.create` (`:277-297`) passes `card.settings` beside `card.words`.

### The adapter (`App.vue`)

`ChatAdapter.revise(card, visual, words, settings, smallPhotoAccepted, owned, sending)` and `words(visual, values, settings, owned)`: one more argument each. New local functions: `setSettings`, `carries`, `freshPlan`, the computed `staleIdentity`.

**`revise`, exact order (new steps in bold):**
1. `pickVersion(visual, owned)`.
2. `headline.on` false → stop, as today (`:1406`).
3. `flush()`, `owned()`.
4. `base = currentVisual`; `restoreHeadline(owned)`; `styleReference = base.style_reference_asset`.
5. `setWords(words)`.
6. **`setSettings(settings)`**, in this order:
   - `accent_word` → `headline.accent_word = value ?? ''`; `accent_colour` → `headline.accent_colour = value.toLowerCase()` (not `pickAccent`: it also writes the product palette and `accentPicked`, `:115`); `brand_text` → `headline.brand_text = value`.
   - `style` → when `'couleur'`: wait for `paletteLoading` as `start` does (`:1393`); `pickLook(style)`; `paletteBlocked` → throw its sentence (no silent fall back to « Studio clair »: the card listed the style); `styleReference = null`.
   - `logo` / `contact` → one `edit()`: `toggleIdentity(d, role, on)`; logo on: `placeLogo(d, 'right')` (as `copyForCorner`, `:356`); contact on: its layer `visible = false` (the image will draw it; `Document` allows an included, hidden contact, `models.py:234`) and `headline.contact = true`.
7. **`carries(headlineBody(), settings, doc)`**: each listed setting is in the request about to leave (`accent_word`, `accent_colour` upper case, `brand_text`, `signature` present for contact on and absent for off, `include.logo`). If not: the identity edit of step 6 is reversed by the same `toggleIdentity`, and the card fails with the editor's reason (`whyNoDrawnContact`) or « Ce changement ne peut pas être demandé ici : réglez-le dans Pas à pas. ». Nothing is sent.
8. `lowResAccepted`; `kept = GET /api/plans/{base.plan_id}`; `owned()`.
9. `keptAlign = base.headline?.signature_align`; `keptFrom = base.id`, **or `null` when `settings.style` is set**.
10. The plan:
    - **`settings.style`** → `createScene(key, sending, owned)`: a fresh plan in the new style.
    - `kept` belongs to another poster or format, or is missing → `createScene`, as today.
    - **identity changed** → `flush()`, `owned()`, **`freshPlan(kept, owned)`** = `prepareScene(owned)`, then `plan.plan.scene = kept.plan.scene`, `plan.plan.palette = kept.plan.palette`; `generateScene` saves it as a revision (`savePlan`, `:1088-1094`).
    - otherwise → `acceptPlan(kept)`, `generateScene`, as today.
11. `finally`: `keptAlign = keptFrom = null`.

**`words` (free), exact order:** `pickVersion`, `flush`, `owned`, `setWords(values)`, **the identity toggles of `settings` in one `edit()` (`toggleIdentity` only)**, `flush`.

**`state.stale.identity`** (computed, the editor's own truths, only what blocks the export): `logo: true` when `discUncovered`; `logo: false` when `staleLogo` and the selected version has no `logo_box`; `contact:` `currentVisual.headline?.contact !== undefined` when `staleSignature` holds for the contact (`:740`). `staleLogo` with a `logo_box` (a moved logo or a crop) and a stale shop name stay the editor's matter.

**What the card promises.** The words as in D-005; each listed setting is in the request (step 7); everything else is the version's, through `restoreHeadline()` and its plan. For a style card: the words and the listed style; the accent colour follows the editor's rule (`pickLook`: « Luxe sombre » sets gold, « Couleurs du produit » takes the photo's colour, « Studio clair » keeps the version's). It does not promise that the image model obeys: the review and its text checks stay the guard (`required_checks`, `visuals.py:25-33`, adds the contact's check when it is drawn).

### Failure modes & handling

| Failure | Detection | Behavior |
|---|---|---|
| The reader takes « mets le logo Sony » for the shop's logo | none on the server | the line says « Logo de la boutique : … » before the paid tap; « Annuler »; counted in the paid test. If the rate is high, `logo` is offered only when the message has « boutique » or « mon / notre » (a check in the row, not a prompt patch) |
| The reader confuses the word's colour and the style | none | each has its own line; paid test |
| A listed setting would not be in the request (accent not in the title, brand empty, contact too long) | `carries`, step 7 | nothing sent, nothing paid; identity edit reversed; the editor's sentence |
| The scene request is refused, lost, or its job fails after the identity was saved | `staleLogo`, `staleSignature`, `discUncovered` → `state.stale.identity` | the card keeps its request (« Réessayer » / « Reprendre », ADR-097) or is offered again; « La boutique sur l’affiche ne correspond plus à l’image. » with « Remettre comme sur l’image », free |
| The owner chooses an older version, made without the logo, after a version with it | same computeds on the selected version | same line and button |
| `freshPlan`: the fixed plan does not fit (`composition_does_not_fit` → `layout_not_plannable`) | the `/plans` refusal, before any paid request | the card fails with the server's sentence; the document keeps the identity change → the line above |
| The photo's colours cannot be read for « Couleurs du produit » | `paletteBlocked` in step 6 | nothing sent; its sentence |
| A style card on a version with scene adjustments | `kept_adjustments` at the read | the card says they are not carried; the request has no `keep_adjustments_of` |
| A tab on the old bundle | `rows` absent | only the D-005 rows are read and offered |
| The saved look of the version was removed and cannot be read | `restoreHeadline(owned)` throws (`:139`) | as today: nothing sent |
| Twelve versions | as today | as today |

ADR-097/098 are not changed: one unresolved paid card; the card's id is the key of the one `/scenes` request; `owned()` after every wait, `/plans` included (`prepareScene` already takes it, `:1050-1052`); nothing is sent by itself. `freshPlan` adds one unpaid request before the paid one; a lost answer there leaves no kept request, so the card is offered again (`nextStep` → `'new'`, `chat.ts:124`).

### Edge cases

- Accent word and a new title in one message: the accent is checked against the new title. A title change that drops the kept accent: D-005's line « Le mot en couleur est retiré. », unchanged.
- A colour alone on a version with an accent word: `scene`. A colour alone without one: `refused`.
- `brand_text` with a brand given in the same message: one card, both lines. « comme sur le produit » on a version that never had `brand_text`: `same`.
- Logo on, on a version with a seal whose logo was switched off: `carried` (disc) → `free`; `toggleIdentity` puts the seal back on its disc (`:407`).
- Logo off on a version with a seal: `scene`; `sealOn` is false without `include.logo` (`:381`), so no disc is asked.
- Contact on while the shop name is shown as a layer: allowed; the new plan keeps both regions. The shop name's layer is not moved (finding 2) — the final preview is the guard; noted as a limit.
- Contact on with the logo on: `whyNoDrawnContact` subtracts the logo's width even for a corner logo (`:366`), stricter than the server (`plans.py:415`). A contact of 34 to 40 characters is refused by step 7 with the logo on. Accepted: the editor's rule is the one source.
- A style asked that is the version's own: a new image is offered (the id is not stored, so `same` cannot be known). Stated limit.
- Style and words in one message: one card; the words are the card's, the plan is new.
- Format with other fields: the format sentence only.
- A message in Malagasy or English: read like any other.

### What this does not do (and why)

- **Shop name**: a laid-over text; later versions do not re-place layers (`service.py:153`) and the chat has no canvas to measure an overlap. Mechanism 3.
- **Logo as a round seal**: the editor refuses it once a version exists (« créez une copie », `App.vue:375`) and the request needs the fixed footer, a drawn price and a contact at the right (`plans.py:326-333`, `visuals.py:255-259`). A copy is E.
- **Logo at the top left or in the footer, contact position**: one more row each; little value for one shop. The contact keeps the version's `signature_align` (`keptAlign`) or the device's remembered one.
- **A contact that cannot be drawn** (several lines, `"`, too long): it would be a laid-over layer (finding 2).
- **Missing shop details**: a form with a file upload (`importMissingProfile`, `:546-556`).
- **A saved style**: the reader would need the shop's style names in its schema (a schema per shop), and a saved style's model image raises the format question (`askFormat`, `:167`). Add when the owner has saved styles and asks for one by name.
- **« Décrire moi-même »**: the scene adjustment already takes the owner's words (ADR-102).
- **Another format (E)**: `remakeIn` opens another poster, without version, in another conversation, where the chat answers « L’affiche n’a pas encore de version. » (`ChatView.vue:224`). See task 7.
- **The two switches « composer le titre / dessiner le prix dans l’image »**: not asked; `revise` still refuses when drawn texts are off.

### Not established from the code

- Nothing was run. `freshPlan` (a fixed plan with the version's `scene` and `palette` laid on it, saved as a revision) is assembled from `prepareScene`, `savePlan` and `revise_plan` as read; it has never executed.
- Whether the image model keeps a corner free for the logo, obeys an accent colour or plain brand letters on a redraw: paid test only.
- `ChatView.reconcile` was read in part; the claim "a failed job offers the same card again" rests on its comments (`:363`, `:380-381`).
- `api.py` `MESSAGES` was read by grep only; the new sentences must be added there and each new code needs its French sentence (existing test).
- The formats enabled on the running pilot were read from `deploy/compose.yml`, not from the box.

### Tests

- **Backend (`tests/test_reads.py`)**: a `setting` row added in a test appears in the schema, the sentence and the card's lines; `rows` absent → the schema, the sentence and the cards are D-005's, and the body's hash is unchanged; each row's check and refusal; accent against the resulting title (kept, changed, removed); colour names to hex and case; `brand_text` with and without a brand, and with the brand inside the title; the identity rule's six lines for the logo and for the contact (drawn, layer visible, layer hidden, seal disc, kept logo place); snapshot without logo or contact → `steps`; a setting on a version without drawn words → `steps`; style lines with and without a model image and kept adjustments; `format` → `steps`, other fields not offered; settings with an instruction → words-first line; mixed free and scene → one `scene` card; the stub's new patterns.
- **Vitest (`tests/chat.test.ts`)**: `differences` with accent and `brand_text`; `staleLine` with `identity`; `carries` (extracted to `chat.ts` as a pure function of the request body and the settings) for each setting, present and dropped.
- **Browser smoke (`tests/chat_browser.py`, stub, zero spend)**: accent word then colour → the `/scenes` body carries both, the plan is a revision of the version's; brand in plain letters; a style card → a new plan with the style's palette, no `style_reference_asset`, no `keep_adjustments_of`; logo on → the plan has a `logo` region and the version's palette, the new version has `logo_box`, the export is not blocked; contact on → `signature` in the body, the text check lists it; logo off free; a contact of 60 characters → refused, no request, `include.contact` back to off; `STUB_FAIL` on the scene after logo on → the stale line, « Remettre comme sur l’image », export unblocked; an older version chosen after a logo version → the same line; a read without `rows` (old bundle) → no settings card; reload between the identity save and the request → « Reprendre » sends the kept request.
- **Paid (the user's word; reads about USD 0.10, each image at the pilot's price)**: about 25 real messages on the new rows, with the confusions named above (shop logo against brand mark, word colour against style, plain brand against a new brand), every wrong field reported; then one image each for: accent word with a colour, brand in plain letters, a style change on a version with a model image, logo and contact together.

### Tasks (each one session, in this order)

1. **T-CHAT-SET-001** backend: `Row.setting`, `Row.since`, `rows` in the request, `card.settings`, `poster_words` settings; rows `accent_word`, `accent_colour`, `brand_text`; row `format` with its `steps` sentence; stub patterns; sentences. Verify: `uv run pytest tests/test_reads.py tests/test_api.py -q`.
2. **T-CHAT-SET-002** frontend: `Settings`, `rows: 2`, `setSettings` (the three headline settings), `carries`, `revise`'s new argument, list labels. Verify: Vitest, then the chat smoke's accent and brand cases. A, B and E's sentence are done here: no new plan path, no document change.
3. **T-CHAT-SET-003** style (D): row `style` with its two lines; the style branch of `revise`. Verify: pytest, the smoke's style case.
4. **T-CHAT-SET-004** paid reads of the new rows, and three images (accent, plain brand, style). Report; the row rules are corrected from it before C is built. Needs the user's word.
5. **T-CHAT-SET-005** identity, backend (C): rows `logo`, `contact`, the identity rule, `poster_words` identity and snapshot. Verify: pytest.
6. **T-CHAT-SET-006** identity, frontend (C): the identity part of `setSettings`, `freshPlan`, `words` with toggles, `staleIdentity` and its line. Verify: Vitest, the smoke's identity cases; then one paid image with logo and contact (the user's word).
7. **T-CHAT-SET-007** another format from the chat (E) — **only on the user's word, after its own design round.** Sketch: (a) a poster without version gets a recap card in its conversation (name and price from the document; tap = the existing `start`, which skips `createPoster` when the poster exists, `App.vue:1389`); (b) row `format` → effect `copy`, free, « Créer la copie » → `pickVersion`, `remakeIn(to)`; the chat follows the opened copy to its conversation; (c) the recap card keeps the source version's `plan_id`, and `start` lays its `scene` and `palette` on the first plan (`freshPlan`). Open points for that round: a second tap or a retry after a lost answer may make a second copy (`remakeIn` is not idempotent across reloads); the paid card and its request then belong to another poster than the message that asked.

Tasks 1 to 3 need no document change and no new plan path: the cheapest safe slice. Tasks 5 and 6 carry the risks named in the failure table. Task 7 may stay in « Pas à pas » for good.

## Tests

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
