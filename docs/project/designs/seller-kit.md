# DESIGN — The seller's kit and the fixes of the first user walk

## System overview

**Status:** v3, 2026-11-23, approved for implementation by the lead under ADR-131: the devil's advocate ([report](../reviews/seller-kit-design-devil.md)) and review r1 ([report](../reviews/seller-kit-design-r1.md), APPROVE WITH FIXES) are applied. T-KIT-001 and T-KIT-004 were built on v1: their sections did not change, except the end of D-KIT-008. **Where a section below and the table « Review r1 » differ, the table wins.**

**What v2 changed (devil's advocate, the lead's decisions):**
| Point | Decision |
|---|---|
| 1. Lines drawn by the image model | Kept (ADR-131, decision 3): the contact already works this way and the walk's overlaid shop name was the unreadable one. Tightened: discounts refused in a line (point 5); the prompt asks for the contact's size at least; the paid check T-KIT-010 decides the placement before the feature is called done; the stated limit (a version keeps the lines it drew) stays. |
| 2. Bare numbers as prices | Tightened: without a unit a number counts from 10 000, never when it starts with 0; unit amounts and bare amounts are candidates together. |
| 3. Scope | Cut: `POST /api/looks` (D-KIT-011) and the Facebook read inside the review (D-KIT-008). Added: the reader's `advert` field (D-KIT-004), a three-product trial in T-KIT-010. Both slices are built in this round, so the order of the kit's tasks stays. |
| 4. The word guard against tidying | Scene words are copied in the language written, never translated. The name's guard compares letters and digits only, and a name that fails it is kept as the reader gave it, as today: no new question. |
| 5. Discounts in a line | Refused: `%` and the discount words. |
| 6. Looks piling up | A style photo the shop already has a model from reuses that model. |
| 7. Kit defaults per shop | Not taken: per device, as the start view and the last style (D-TEXT-FIRST-001). |
| 8. Title styles are not a font | Each title style also names the font of a title that is a layer (D-KIT-012); T-KIT-015 judges two posters of one style side by side. |
| 9. One draw switch | Two: the texts, and the price (ADR-044 stays the owner's option). |
| 10. A recap nobody reads | The recap stays short: name, price, one line for the scene and the lines; the unused parts set apart. |
**Requirements:** [seller-kit](../requirements/seller-kit.md), R-KIT-001 … 012, approved for design 2026-11-23 (ADR-131).
**Evidence:** [user walk 2026-11-23](../reviews/user-walk-2026-11-23.md).

**Review r1: fixes that bind (v3).**
| r1 | Section | Fix |
|---|---|---|
| 1, 13 | D-KIT-005, rule of a line | `screen_shop_line` refuses: a currency word, `€`, `$`, `%`; four digits or more in the line, separators or not (« 5 000 », a phone number); `\d\s*k\b`; the discount words of v2; an injection by `_INJECTION` (as `screen_adjustment`), not `_INSTRUCTIONS`. « Garantie 12 mois », « Livraison 24h » pass. Test rows: « Livraison 5k », « Livraison 5 000 », « -20 % », « 034 12 345 67 » refused. |
| 2 | D-KIT-005, per poster | `Headline.lines: list[ShopLine] \| None` (at most 3, `exclude_if` None) carries the lines the screen showed, in place of `Literal[True]`. Before `enqueue`, `request_scene` answers `409 shop_lines_changed` « Les lignes de la boutique ont changé : relisez le récapitulatif. » unless the list equals the profile's lines, in order; `409 shop_lines_missing` when the profile has none. The request's hash now covers the words. A refinement keeps its base's lines, as designed. |
| 3 | D-KIT-004, reader schema | The wire types have no bounds (`list[str]`, `list[Unused]`, `text: str`): `build` keeps the first three items and cuts to 80 (40 for a line is a refusal, not a cut). One test row with four unused parts. |
| 4 | D-KIT-005, data | `initial_document` (`store.py:174-190`) leaves `lines` out of `BrandSnapshot(**profile)`. |
| 5 | D-KIT-001, words | The action « Tout est conforme, approuver » and its sentence « approuver cette variante pour plus tard » leave the editor's version dialog (`App.vue:3118`): a version becomes `approved` only with the confirmation of its file, so « Confirmée » is true wherever it is read. The route stays (the single review uses it). `App.vue:2840` is reworded without « approuver ». `browser_smoke.py:824-825` follows. Refusing a version stays. |
| 6 | D-KIT-005, migration | 0021 declares `PRESERVED` (`shop_profile`: the columns 0019 names, plus `post_image_limit`) and `ADDED = {"shop_profile: no line yet": ("SELECT count(*) FROM shop_profile WHERE lines_json <> '[]'", [(0,)])}`, as 0017 and 0019 do; the column has `CHECK (json_valid(lines_json) AND json_type(lines_json)='array')` if SQLite's `ADD COLUMN` takes it with the default, else no check. T-KIT-002 owns every test that pins the head at "0020": `test_db.py`, `test_phone_session.py`, `test_reads.py:111`, `test_api.py:891`. |
| 7 | D-KIT-005, « Mon compte » | `lines` is one field of `fieldNames`, copied and compared by value (`JSON.stringify`) in `dirty` and in the two-device merge, and offered in the « modifié sur les deux appareils » choice (T-KIT-009). |
| 8 | Tasks | `api.ts` (`Profile.lines`, `writeProfile` sending `lines` only when given) belongs to T-KIT-009, which runs before T-KIT-006. New members of the chat adapter are optional until T-KIT-007. The ChatView half of D-KIT-007 item 1 (`adapter.focus`, the placeholder) is T-KIT-005. Frontend tasks run one after the other (one build at a time): 005, 009, 006, 007, 008. |
| 10 | D-KIT-007, the name | As v2: a name that fails the guard is kept as the reader gave it; no question. |
| 11 | D-KIT-002 | The 10 000 floor applies to every amount without a unit, `k` included (« TV 4K » is no price; « 250k » is). A run whose next token holds a digit is not read (« 1 250 000,00 »). Rule 2 runs whatever rule 1 found. Five candidates and more: `card_ask_price_many` « J’ai lu plusieurs montants. Écrivez le prix seul, par exemple 250 000 Ar. », no button. |
| 12 | D-KIT-004 | `identity` joins the fields whose change is said (« J’ai changé : le logo et le nom de la boutique (avant : sans). »). |
| 16 | D-KIT-005, « Vos données » | Three more facts on `donnees.html`: a style photo of a message is read by the service that reads messages; so is a poster's scene kept as a model; so are the shop's lines when a message is read (T-KIT-009). |
| 17 | D-KIT-005, older bundle | T-KIT-002 checks that the `fidelity_incomplete` sentence tells the owner to reload the page, and amends it if not. |
| 18 | D-KIT-006 | The page keeps the look's **job** id per asset; after the 90 s limit « Réessayer » waits on that job again, and posts no second look. |
| 20 | D-KIT-005, capitals | The offer card shows the exact line that will be kept (« Je garde « Garantie 6 mois » … »): what the seller sees and accepts is what is kept. No rebuild from tokens. |
| 9, 14 | — | Moot: `POST /api/looks` and the review's read of the Page were cut in v2. 15: no index; the comment above `TO_REVIEW` says the cost (T-KIT-001). 19: T-KIT-010 counts the guard's drops. |

The smallest change per criterion, on what exists. One column (migration 0021), no new table, one new route (slice 2). The kit is three things that already have a home: the scene models are the looks (ADR-046); the shop's lines are a new `shop_profile.lines_json`; the title style is one more optional field of the scene request's `Headline`. The last choices stay per device, as the start view and the last style do (D-TEXT-FIRST-001, devil's advocate 5).

```
Message ──POST /api/reads──▶ reader: + scene words, + lines offered, + unused parts, prices as written
   │  recap: what will be used, what will not (before any credit)        shop_profile.lines_json (0021)
   └─ tap ─▶ App.vue adapter: keep new lines (PUT /api/shop-profile) → createPoster
               → style photo? POST /api/creations/{id}/looks, wait, pickLook → createScene
                   body + adjustment_fr, headline.lines, headline.title_style (slice 2) ──▶ compile_scene
```

**Approved decisions this design amends** (named again where they apply):
| Decision | Amended in | Why |
|---|---|---|
| D-CREATION-LIBRARY-003, the `to_review` rule | D-KIT-001 | an older undecided version keeps a confirmed poster « À vérifier » |
| ADR-095, the price allowlist | D-KIT-002 | `250000` after the name, `250k` |
| D-TEXT-FIRST-002, the new-poster reader ("stays as measured in T-CHAT-002"); `instruction_fr` "scene_change only" | D-KIT-003, 004 | scene words and the shop's lines in the first message |
| ADR-043, drawn words "only from the poster's profile snapshot" | D-KIT-005 | the shop's lines exist only as drawn words; their snapshot is the job's payload |
| D-TEXT-FIRST-003, image roles by position, the inspiration as a raw `style_reference_asset` | D-KIT-006 | product by default; a style photo is read into a look |
| D-FB-POST-005, the page's layout (ADR-127 … 130 unchanged) | D-KIT-008 | the outcome first; the connection on the page |
| ADR-044/055 as switches of the editor (the API is unchanged) | D-KIT-012 | one switch |

---

## D-KIT-001 — One state, one word (R-KIT-001)

**Now.** `api.py:560-562` `TO_REVIEW`: the shown scene is `pending_review`, **or any visual of any job of the poster** is. `api.py:1076` tests it before `confirmed`. The ordinary Message path (version 1 never decided, a correction, version 2 confirmed) ends « À vérifier » for ever. The same constant counts Accueil's « Affiches à reprendre » (`api.py:669`, `ShopHome.vue:15-19`). Words: « Approuvée » / « approuvée » in `dashboard.ts:8` (list state `approved`), `App.vue:604, 2944, 2951, 3095`, `ChatView.vue:63, 604`; `chat.ts:316` already says « Confirmée » for an approved version.

**Change (one clause; the order of `api.py:1076` stays).** A waiting version counts only when it is newer than both the scene the poster shows and the poster's last confirmation:
```sql
... OR EXISTS(SELECT 1 FROM poster_jobs j JOIN poster_visuals w ON w.job_id=j.id
      WHERE j.creation_id=c.id AND j.shop_id=c.shop_id AND w.status='pending_review'
        AND w.created_at > max(COALESCE((SELECT s.created_at FROM poster_visuals s WHERE {SCENE}), ''),
                               COALESCE((SELECT max(k.confirmed_at) FROM confirmations k WHERE k.creation_id=c.id), '')))
```
SQLite's two-argument `max` is NULL when one argument is, hence the COALESCE; both stamps are `db.utc_now()` text. A version made after the confirmation is still « À vérifier », as required. The superseded version 1 stays in the editor's list and can still be refused; it no longer speaks for the poster. The list, the menu, Accueil and its count all read this one rule.

**Words.** Every version state on a shop screen: « Confirmée » / « confirmée » (`App.vue:604, 2951`, `ChatView.vue:63, 604`); `App.vue:2944` « Version confirmée. »; the dialog of an approved version `App.vue:3095` « Version confirmée ». The list state `approved` (confirmed once, edited since, no file for this revision: `has_current_file` false) becomes « À confirmer » with the neutral `badge`: « Confirmée » would be false there, and « Approuvée » is the word that goes.

**Edge cases.** A copy that shows a version waiting in its source: clause 1, unchanged. A poster without a scene: any waiting version counts (newer than ''). The owner went back to an older version and confirmed it while a newer one waited: that one is older than the confirmation, so it no longer counts (it was there when he confirmed).

**Failure modes.** No external system. Both stamps come from the API process clock; a scene takes a minute, so a tie is not possible in practice.

**Tests.** `test_api.py::test_a_confirmed_poster_is_confirmed_whatever_its_older_versions`: v1 pending, v2 by refinement chosen and confirmed → `confirmed`, `/api/shop-dashboard` `review.total` 0; then v3 → `to_review`; a version waiting before the confirmation of an older one → `confirmed`. `test_list_states_removed_view_restore_and_stale_copy` (`test_api.py:1076`) and `test_shop_dashboard.py::test_review_counts_what_the_library_shows_to_review` stay green unchanged. Vitest `dashboard.test.ts`: the names. Smokes: `shop_dashboard_browser.py:154` `("approved", "À confirmer", "badge")`; `chat_browser.py:326, 643, 712, 726, 773, 1246, 1340` and `browser_smoke.py:825` take the new words.

---

## D-KIT-002 — Prices as sellers write them (R-KIT-002)

**Now.** `reads.py:102-167`: an amount is whole ASCII-digit tokens right before `Ar | ariary | MGA`, or the whole message. `casque sony wh-ch720n noir 250000` and `250k` give no candidate; `test_reads.py:128-138` `REJECTED` pins `700k`, `arrivage 700 000`, `2 350000`, `700 000 Argent` and `700 000 A r` as no amount. The card repeats `card_ask_price` (`api.py:143`). The form's `parsePrice` (`document.ts:46-53`) takes `185000 ar` but not `250k`.

**Change (ADR-095 amended; still an allowlist of whole tokens).**
1. A token `[0-9]{1,4}k` (any case), alone or with its unit (`250k`, `250kAr`, `250k Ar`), is one amount × 1 000, never grouped with a neighbour.
2. Every maximal run of number tokens **not followed by a unit token** is read with today's span rules (`_values` with suffixes; the long-last-token cut of `reads.py:144-147`), and only values ≥ 10 000 whose first token does not start with `0` count (v2: « 5000 mAh », « 2024 », « 0341234567 » are no price; a cheaper article needs its unit or is asked). They are candidates **beside** the amounts written with a unit (« 250000, livraison 5000 Ar » has both, and the model or the owner chooses). A run followed by a unit was judged by rule 1 and is not read again without it, so `JBL 7+ 700 000 Ar` stays refused.
3. The whole-message rule keeps `suffixes=False` and gets a 1 000 floor (`500` alone is no price; `5000` alone is one: the message says nothing else).

Moved from `REJECTED` to accepted: `700k` → 700 000, `arrivage 700 000`, `700 000 Argent`, `700 000 A r` → 700 000, `2 350000` → 350 000. Still no amount: `Armani 700`, `Sony WH-1000XM6 noir`, every signed, foreign-digit, comma and bracket case of the list.

**Reader rule** (`reads.py:43-44` and the `price_ar` row `reads.py:242-243`): « the price in ariary, only when written in digits in this message, with or without a unit (250000, 250 000, 250.000, 250k); null when two different prices are written or when no number is clearly the price. »

**The question names what it read.** In `build` (`reads.py:450-469`), when no price is set:
| Candidates in this message | Card | `text_fr` |
|---|---|---|
| none | `ask_price` | `card_ask_price` « Je ne vois pas de prix dans votre message. Écrivez-le en chiffres, par exemple 250 000 Ar. » |
| one | `ask_price` + `amounts: [n]` | `card_ask_price_one` « Le prix est-il {} ? » |
| two to four | `ask_price` + `amounts` | `card_ask_price_which` « J’ai lu {} : lequel est le prix ? » (« 13 700 000 Ar ou 700 000 Ar ») |

`ChatView` shows one button per amount (« 250 000 Ar »). A tap sets `draft.price_ar` on the device and builds the recap (`ChatView.vue:153`): no paid read, the amount is the owner's own words, and the recap shows it large before any credit (`ChatView.vue:598` `.recap-price`, unchanged). Two prices are still never guessed: the owner taps one.

**Form.** `parsePrice` takes `^([0-9]{1,4}) ?k$` after the unit is cut, ×1 000. No floor: the field is the price. Its sentence becomes « Écrivez le prix en ariary : 90 000, 90.000 ou 90k. Sans virgule. »

**Edge cases.** `Redmi Note 13 700 000` without unit: 13 700 000 and 700 000, the model chooses, else two buttons. `SSD 1000 Go 350000`: 1000 is under the floor, one candidate. A long number before the price (« ref 123456 250000 ») gives a second candidate: no list of measurement units (ADR-095 refused deny-lists); the model chooses, the buttons are the fallback. `1,5k` is refused (a decimal comma).

**Failure modes (reader).** It picks a model number among the candidates: the recap shows it large before paying (the existing guard). It returns null for a clear price: one button instead of a second paid read.

**Tests.** `test_reads.py::test_candidate_amounts` new rows (each writing with each unit and without; the five moved rows; `Armani 700` and `JBL 7+ 700 000 Ar` still none; `Redmi Note 13 700 000`); `::test_the_price_question_names_what_it_read`. Vitest `document.test.ts`: `250k`, `250K Ar`, `1,5k` refused. Chat smoke (the stub reads `candidate_amounts`): « casque sony wh-ch720n noir 250000 » → recap; « 250k » → recap; « 13 700 000 ou 700 000 » → two buttons, a tap → recap, no second read.

---

## D-KIT-003 — Scene words in the first message (R-KIT-003)

**Now.** The new-poster reader returns `instruction_fr` "scene_change only" (`reads.py:44-45`) and `build` drops it (`reads.py:437-473`). The first scene follows the house direction (`App.vue:90-95`) through a fixed plan. On a poster the request works because the owner's whole message is the adjustment (`reads.py:364-371`, ADR-102: the reader's `instruction_fr` there is only a signal) and kept adjustments win over the art direction (`plans.py:515-524`).

**Change.**
- **Reader.** On a new poster `instruction_fr` carries the scene words (rule in D-KIT-004). `Draft` gains `scene_fr: str | None` (1–500, `exclude_if` None: earlier bodies keep their hash). `build` keeps the words only after two checks: the **word guard** of D-TEXT-FIRST-005 (every `name_words` word is in this message or in the draft's `scene_fr`: the reader selects the owner's words, it cannot add a feature; the whole message cannot be sent as on a poster, it holds the name and the price), then `screen_adjustment` (`plans.py:65-74`, the refinement's own screen). Refused by the screen: the words become an unused part (`commercial`, D-KIT-004). Refused by the guard: dropped, `log.warning` (counted in T-KIT-010), and an unused part `other` with the owner's message cut to 80.
- **Scene request.** `SceneRequest.adjustment_fr: str | None` (1–500, `screen_adjustment`; absent from the hash, `visuals.py:296` dumps `exclude_none`). `request_scene` appends it to `adjustments` (`visuals.py:264-268`), hence to `payload["adjustments"]`: the next refinement and word change keep it (`kept_adjustments`, `visuals.py:55-65`). No new prompt branch.
- **Prompt words** (`plans.py:351-353, 517-524`): « House style, unless the quoted art direction or the kept adjustments say otherwise »; « The owner asked, in his own words, for the changes listed as kept_adjustments: this image keeps them … » (the clause "on earlier versions of this poster" goes: false for a first image, useless for the others); `Subject:` « … unless the art direction or a kept adjustment places it on a surface ».
- **App.vue.** `ownerScene` beside `keptFrom` (`App.vue:388`), set only by the chat's `start`, sent as `adjustment_fr` by `generateScene` (`App.vue:1604`), cleared by `adopt`/`fresh` and once the request has left.

**Edge cases.** « fond rouge » with « Luxe sombre » chosen: the words win over its direction and palette (the existing precedence); the recap says both. Features with their values pass (`_UNIT` exempts `W`, `h`, `mAh`…); five digits without a unit are a price and are refused. A later message replaces or completes the draft's scene (the reader returns the whole wanted scene).

**Failure modes.** The image model ignores the words: seen on the image; the next message adjusts, paid as today. The reader invents a word: the guard drops it and the recap shows nothing it did not keep.

**Tests.** `test_reads.py::test_scene_words_of_the_first_message_reach_the_draft` (guard, screen, replace, hash of a body without them). `test_poster_visuals.py::test_a_first_scene_carries_the_owners_words_and_keeps_them` (prompt `kept_adjustments`, payload `adjustments`, a later refinement says them again). `test_plans.py`: the new sentences.

---

## D-KIT-004 — The recap says what will be used and what will not (R-KIT-004)

**Now.** The recap (`ChatView.vue:592-598`) shows photos, name, price, format, style, identity. Unused words vanish; a later read changes the style without a word (walk, finding 2).

**Reader schema (new poster, `reads.py:92-99`).** `Fields` gains `shop_lines: list[str] = []` (≤ 3, D-KIT-005) and `unused: list[Unused] = []` (≤ 3; `Unused = {text: str, reason: "commercial" | "product" | "format" | "photo" | "other"}`); the defaults keep every existing constructor. `SYSTEM` (`reads.py:35-47`) changes in these sentences only:
- product_name: « brand and model with their usual capitals (Sony WH-CH720N, iPhone 15 Pro, JBL Flip 7), only from the owner's words, without the price » (R-KIT-007);
- style: « only when the owner names one of the three styles or plainly asks for a light studio, the product's own colours, or dark and premium; a described background is instruction_fr, not a style »;
- instruction_fr: « the picture the owner wants, copied in his own words and in the language he wrote (never translated, never completed): background, light, setting, where and how the product stands, what is written beside it such as its features with their values as written; the draft's scene kept, completed or replaced as this message says; never the product name, a price, a promotion, a warranty, a delivery or a payment »;
- shop_lines: « each line of the shop's own conditions that the owner asks to show (a warranty, a delivery, a payment method), as he wrote it, at most 40 characters, never an amount »;
- unused: « each part of the message that no field takes, quoted in the owner's words (at most 80 characters), with its reason ».
- advert (v2, the owner's guard): « false only when the message plainly asks for a picture that is not an advert for something the shop sells or for the shop itself (a portrait, a joke, a document, a logo for someone else); true in every doubt ». `Fields.advert: bool = True`. False → card `unclear` with `card_not_advert` « Je fais des affiches pour ce que votre boutique vend. Envoyez la photo d’un produit, son nom et son prix. », nothing kept from that message. The same field joins `poster_fields()` for a scene request on a poster (false → `card_not_advert`, no paid card).
Each `unused.text` passes the word guard (else dropped and logged) and is cut to 80.

**Card text (server, `MESSAGES`, so French stays in one place).** After its sentence, every new-poster card gets one line per unused part:
| Reason | Line |
|---|---|
| `commercial` | « « {} » : un prix, une remise ou une promotion ne va pas dans l’image. Le prix a son champ ; le reste va dans la description de la publication. » |
| `product` | « « {} » : une affiche montre un seul produit. Faites une affiche par produit. » |
| `format` | « « {} » : par message, l’affiche est au format Publication ; les autres formats se font dans Pas à pas. » |
| `photo` | « « {} » : touchez l’étiquette d’une photo pour dire si c’est le produit ou un modèle de style. » |
| `other` | « « {} » : je ne sais pas le mettre sur l’affiche. Dites-le autrement. » |

And when this read changed a field the recap already had (`name`, `price_ar`, `style`, `scene_fr`): « J’ai changé : le style (avant : Studio clair). » (one clause per field, `STYLES` and `format_price`). The client already draws `text_fr` with its line breaks (change cards).

**Recap lines (client, `ChatView.vue:598`), all above the paid button, kept short (v2):** the name; the price, large (unchanged); the format (unchanged); « Scène : Studio clair », plus « , avec vos mots : « {scene_fr} » » when set, or « Scène : votre modèle de style » (D-KIT-006); « Lignes de la boutique : … » when some will be drawn (D-KIT-005); the identity line (unchanged). No title line in slice 1 (the name is the title); slice 2 adds « Titre : Gras condensé » only when it is not the default. The unused parts are a block of their own under the recap, before the button, in the warning colour: they are what the seller must read. `ChatAdapter.state` gains `drawn: boolean` (`headline.on`) and `shop.lines: string[]`.

**Edge cases.** A message of unused words only (« publie-la sur Facebook »): `unclear` plus its line. An unused part on an `ask_price` card is said there once. A style changed by a chip is the owner's own act: not repeated.

**Failure modes (reader).** It forgets an unused part: lost as today, but the recap now lists everything that will be used, so a missing wish shows before paying. A wrong reason: one wrong sentence, nothing paid. Every new field changes the bytes of the new-poster read: re-measured (T-KIT-010).

**Tests.** `test_reads.py::test_unused_parts_are_said_with_their_reason`, `::test_a_changed_recap_field_is_said`, `::test_an_unused_quote_nobody_wrote_is_dropped`; the existing test that every code has its `MESSAGES` entry. Vitest `chat.test.ts`: the scene and lines lines of the recap. Stub reader, deterministic markers: « scène : X » → `instruction_fr` X; « ligne : X » → `shop_lines` [X]; « pas utilisé : X » → `unused` other.

---

## D-KIT-005 — The shop's lines (R-KIT-005)

**Now.** No place for them: the title refuses commercial words (`api.py:51`; `screen_headline`, `plans.py:40-48`, blocks `garanti|livr|paiement|gratuit…` through `prompts.py:143-149`). On a poster « ajoute garantie 6 mois » sets `commercial` and gets `card_refused` « … retirez les mots … » (`api.py:146`, `reads.py:368`).

**Data.** Migration `0021_shop_lines.py`, hand-written (`uv run alembic revision -m "shop lines"`), forward-only, run only by `affiche.db.migrate`:
```sql
ALTER TABLE shop_profile ADD COLUMN lines_json TEXT NOT NULL DEFAULT '[]';
```
`store.get_profile` (`store.py:128-132`) returns `lines`.

**Rule of a line** (`plans.py`, beside `screen_headline`): `ShopLine` is 1–40 characters after trim, without `"` or a line break; `screen_shop_line` refuses an injection (`_INSTRUCTIONS`) and any amount or long number (a currency word `ar | ariary | mga | euro | dollar`, `€`, `$`, or four digits and more: the price and the contact have their fields, and the prompt allows one amount, `plans.py:458-459`). Commercial words of a condition are not screened (warranty, delivery, payment, « gratuit »): these are the seller's own conditions (requirements, decision 3). A discount is refused (v2): `%`, and the words `remise | réduction | reduction | promo | promotion | solde | soldes | rabais | offre` as whole words without case or accent: a discount belongs to one offer, not to every poster. At most three, distinct without case.

**API.**
```
GET /api/shop-profile   200 {revision, name, contact, logo_asset, lines: [str]}
PUT /api/shop-profile   If-Match, Idempotency-Key; body + lines?: [ShopLine] (≤ 3; absent = unchanged)
    422 shop_line_refused, field "lines": « Une ligne de la boutique : 40 caractères au plus, sans guillemet droit,
        sans montant ni numéro (le prix et le contact ont leurs champs). »
    409 revision_conflict (unchanged)
POST /api/creations/{id}/scenes   headline + lines?: true
    409 shop_lines_missing « La boutique n’a pas encore de lignes : ajoutez-les dans Mon compte. »
```
`ProfileUpdate(Profile)` sits in `api.py` beside `ProfileView` (`api.py:370`): `lines` with `exclude_if` None, so earlier bodies keep their hash, `BrandSnapshot` (`models.py:78`) does not gain it, and the callers that send no `lines` (`App.vue` `saveProfile`, `ShopAccount.vue`) erase nothing.

**Per poster: drawn, like the price; not in `include`.** A line exists only as words the image model draws; there is no layer, so the document's `include` and `brand_snapshot` stay as they are (no `Document` change). `Headline.lines: Literal[True] | None` (`exclude_if` None). `request_scene` reads the profile's lines in its own transaction and writes them to `payload["headline"]["shop_lines"]`: the version's snapshot, as for the drawn title (ADR-043's "profile snapshot" does not apply: the document holds no line). A refinement keeps its base's `shop_lines` (`visuals.py:322-345`), not compared with the profile. `restoreHeadline` (`App.vue:206`) sets `headline.lines` from `drawn.shop_lines`. « Boutique » tab: one checkbox « Afficher les lignes de la boutique », off with its reason when the shop has none or when drawn texts are off.

**Prompt** (`compile_scene`, after the contact line), each line re-checked with `screen_shop_line`:
> Shop lines, rendered verbatim, each character exactly as written, one per line in this order: "Garantie 6 mois", "Livraison gratuite à Tana". Clearly legible on a phone, at least as large as the contact line, in the headline's colour family, each after a small check-mark icon, grouped in free backdrop beside the product or just above the price label; never over the product, the headline, the price label or the areas listed under Layout. They are conditions of sale, not prices; add no other condition.

The `Constraints:` sentence (`plans.py:492-504`) names « the shop lines » among the only writing.

**Review.** `text_lines` joins `TEXT_CHECKS` and `FidelityChecks` (`visuals.py:22, 101`); `required_checks` (`visuals.py:25-32`) asks for it when the version draws `shop_lines`. `textChecks` (`App.vue:1133-1140`) adds « Lignes de la boutique » with the lines joined by « · »: « Détails à vérifier » lists them, and the confirmation sends the key with the others.

**Reader.** `_admit` also reads the shop's lines.
- *New poster.* Each `shop_lines` item passes the word guard and `screen_shop_line`. The card carries `offer_lines` (lines not yet kept), or the line « « {} » est déjà dans les lignes de la boutique. », or at three « La boutique a déjà trois lignes : remplacez-en une dans Mon compte. ». A refused line is an unused part (`commercial`, or « « {} » : une ligne de la boutique fait 40 caractères au plus. »). Recap: « Lignes de la boutique : Garantie 6 mois · Paiement Mvola » with a switch (on by default when the shop has lines); each offered line « nouvelle, gardée pour la boutique » with « Ne pas garder ». The tap keeps the offered lines first (GET, then PUT with If-Match, one retry on `revision_conflict`; any failure stops before anything is paid), then sets `headline.lines`.
- *Poster.* `poster_fields()` (`reads.py:258-278`) gains `shop_lines`. `_change` answers it after `format` and `identity` and **before** the `commercial` refusal, with a new card kind **`line`** `{kind, text_fr, visual_id, lines, words, effect: "scene"}` (an older bundle shows an unknown kind as text, with no paid button): « Je garde « Garantie 6 mois » dans les lignes de la boutique et je refais l’affiche avec. » plus the redraw line (D-KIT-007). Button « Garder et refaire l’affiche » with its cost. It is a paid card (`chat.ts:248-250` `changes`/`paid` include it; ADR-097/098 hold). The adapter's `revise(…, style?, lines?)` keeps the lines, sets `headline.lines`, then runs as for a `scene` card. A version without drawn words: `steps` « Les lignes de la boutique sont dessinées dans l’image : cette affiche n’a pas de textes dessinés. ». Every asked line already drawn: `same`. Other wishes in the same message: « Demandez le reste ensuite. ».
- `card_refused` (`api.py:146`) no longer asks to remove words: « Je ne dessine pas de prix, de remise ni de promotion dans l’image. Le prix se change par message ; une garantie, une livraison ou un paiement va dans les lignes de la boutique : écrivez par exemple « ajoute Garantie 6 mois ». »

**Where they are typed in slice 1.** « Mon compte » (`ShopAccount.vue:150-160`): three fields « Ligne 1 », « Ligne 2 », « Ligne 3 » under the contact (`maxlength` 40), saved with the profile. Slice 2 shows the same fields in « Mon kit ».

**« Vos données », not the conditions.** `frontend/public/donnees.html:39` « … son contact, ses lignes (garantie, livraison, paiement), … »; `:60` « … les textes à dessiner (dont le contact et les lignes de la boutique quand ils sont dessinés) … ». The conditions (`terms.py` `PARAGRAPHS_FR`) only point to that page; their text does not change, so no new `VERSION` and no shop is asked again.

**Edge cases.** Lines edited after a version: the version keeps its drawn words, the next image takes the new ones, and the export is not blocked (there is no layer to compare): a stated limit. Lines on and the switch off: none drawn. Carré and Story: the same sentence; the safe zones apply.

**Failure modes.** The image model misspells, drops or misplaces a line: `text_lines` in the review, then « Signaler un problème » or a new version. The placement is not measured yet: two paid images in T-KIT-010 decide (open point 2). The profile save fails at the tap: nothing paid, the card says the server's sentence.

**Tests.** `test_poster_drafts.py::test_migration_0021_keeps_every_profile_with_no_line`, `::test_shop_lines_are_kept_checked_and_left_alone_by_older_clients`. `test_plans.py::test_shop_lines_are_drawn_verbatim_and_named_in_the_constraints`, `::test_a_shop_line_with_an_amount_is_refused`. `test_poster_visuals.py::test_a_scene_draws_the_profiles_lines_and_its_review_requires_them`, `::test_lines_asked_without_lines_are_refused_before_any_spend`, `::test_a_refinement_keeps_its_bases_lines`. `test_reads.py::test_a_warranty_by_message_is_an_offer_not_a_refusal` (new poster; poster; three already; already kept; no drawn words). Vitest: `paid({kind: 'line'})`, the recap's lines. Chat smoke: « ligne : Garantie 6 mois » on a new poster → kept, in the stub prompt, listed by the review; on a poster → a `line` card and one scene.

---

## D-KIT-006 — A style photo in Message becomes a saved model (R-KIT-006)

**Now.** `chat.ts:99-104` `nextRole` makes the second image « Inspiration » by its position; `start` sends it as a raw `style_reference_asset` (`App.vue:2303-2312`, `visuals.py:283-285`), and the house sentence wins. The look pipeline needs a poster: a brief is a `plan` job on a creation (`looks.py:78-90`; `poster_jobs.creation_id` is NOT NULL), and its reference must be a `style` asset (`looks.py:80`, `service.py:37-40`).

**Change (client only).**
- `nextRole` returns `product` while fewer than three products are attached, else null: « Trois photos du produit au plus. Pour un modèle de style, touchez l’étiquette d’une photo. » The label button (`ChatView.vue:36, 645`) toggles « Produit » ↔ « Modèle de style » (`aria-label` « Marquer comme modèle de style »). The stored role stays `inspiration`, so stored threads read as before; one style photo at most (`swapRole`, unchanged).
- The style row (`ChatView.vue:658-661`) with a style photo: « Scène : votre modèle de style »; the recap adds « (lu, puis gardé dans vos styles) ».
- Adapter `start`: after `createPoster`, when the recap holds a style photo: `POST /api/creations/{id}/looks` `{name: "Style {n}", reference_asset}` at the saved revision; wait for its job (`/api/jobs/{id}` every 1.5 s, 90 s at most; thread line « Je lis votre modèle de style… »); `pickLook(look)`; `styleReference = null`; then `createScene`. A look the shop already has from the same image is reused, with no new brief (v2): `request_look` answers the existing look when a look of this shop, not removed, has this `reference_asset` (same 201 body, `reused: true`; the job row is not written). The look made for that asset is also kept in page memory, so « Réessayer » after a later failure makes no second request. The thread then says « Votre modèle de style est gardé dans vos styles : « Style 4 ». ».

**Errors.** `look_limit` (24), `budget_exhausted`, a failed job (`invalid_brief`, provider): the card shows the sentence, nothing is paid (the scene request has not left), « Réessayer » is the same card (D-TEXT-FIRST-003's failure table). The brief costs the planner budget (about USD 0.009) and no credit (ADR-046). Over 90 s: « La lecture du modèle a pris trop de temps : réessayez. ».

**Edge cases.** A thread kept from before, with a spent recap holding an inspiration, replays its kept request as it left (raw reference). On an existing poster every image is a product photo (D-TEXT-FIRST-007). « Pas à pas »'s own model image is unchanged.

**Tests.** Vitest: `nextRole` (three products, no role by position), the labels. Smokes `chat_browser.py:230-258, 1280-1286` and `guide_browser.py:144, 181`: two photos read « Produit », « Produit »; one tap → « Modèle de style »; the start makes one look job, then one scene whose body has `headline.look_id` and no `style_reference_asset`; the look is in « Styles »; at the limit nothing is paid.

---

## D-KIT-007 — Corrections where the seller is (R-KIT-007)

1. **« Corriger l’affiche » from Message.** `correctFile` (`App.vue:2152-2156`) goes to `#<id>`, the editor, when `chatting`. Now it closes the review, stays on `#message-<id>` and focuses « Votre message », whose placeholder becomes « Dites ce qu’il faut corriger. » (the adapter gains `focus?: () => void`, set by `ChatView` as `waiting` is). From the editor: unchanged.
2. **A word change that redraws.** `_change` adds `card_redraw` to every `effect: "scene"` card made from words (not `restyle`): « Le texte est dessiné dans l’image : cette correction refait toute l’image, pour 1 crédit. » (one image is one credit: the conditions' rule).
3. **Capitals.** The reader's rule (D-KIT-004). The new-poster `product_name` is compared with the message on letters and digits only (case, accents, spaces and punctuation ignored: « redmi note13 » → « Redmi Note 13 » passes, a new word does not). A name that fails is kept as the reader gave it, as today, with a `log.warning` (v2: never a new question for a name the seller just typed). « Pas à pas » keeps what the seller types.
4. **Straight quotes.** One rule, two places: a pair of `"` becomes « … », a lone `"` becomes ″ (`55"`). Server: `curl_quotes` in `reads.py` on `product_name`, before `name_refusal`. Client: `words.ts` `curlQuotes`, applied by the title field on blur and before a scene. `compile_scene` keeps refusing `"`.
5. **Duration.** `generation.ts` `DRAW_TIME = 'En général 1 à 2 minutes.'` (the walk measured 60 to 120 s; `OVERDUE_MS`, 100 s, still says "longer than usual"). Chat `ChatView.vue:79`: « Je dessine l’affiche… En général 1 à 2 minutes. »; editor `WAIT_WORDS.running` (`App.vue:1643`): « L’IA compose une nouvelle version. En général 1 à 2 minutes. ».

**Failure modes.** The reader capitalises wrongly (« Sony Wh-Ch720n »): the name is on the recap and in the review; the next message corrects it, free before the image.

**Tests.** `test_reads.py::test_a_word_change_that_redraws_says_so`, `::test_quotes_in_a_name_are_curled`, `::test_the_name_guard_lets_capitals_pass`. Vitest `words.test.ts`: `curlQuotes`. Smokes: the chat's « Corriger l’affiche » keeps `#message-<id>` and focuses the field; the wait contains « En général 1 à 2 minutes »; `guide_browser.py:211`, `terms_browser.py:193` and `publish_browser.py:1095` (reviews opened from the editor) still land in the editor.

---

## D-KIT-008 — « Publier »: the outcome first, the connection on the page (R-KIT-008)

**Now.** After a send the draft empties (`ShopPublish.vue:255-256`) and « Choisissez au moins une affiche. » shows in `.why`, the warning colour (`publish.ts:182`, `ShopPublish.vue:701`, `style.css:430`); the post's line is in « Publications » at the bottom (`ShopPublish.vue:741-765`). Without a Page: a sentence and a link to « Mon compte » (`ShopPublish.vue:639`); the way back is a link (`ShopAccount.vue:200`). « Publier plusieurs affiches » is a plain link (`ShopPublish.vue:707`). The review's « Confirmer et préparer la publication » shows whenever the feature is on (`App.vue:3036`).

**Change (frontend only; ADR-127 … 130 unchanged, description first kept).**
- **The outcome block.** `sent = ref<string | null>`, the post answered by `send` (`ShopPublish.vue:367-393`). A section right under the title (`aria-labelledby="titre-resultat"`) shows that post's `postLine` from `posts`: its state in the server's words, « Voir la publication » or « Ouvrir ma Page », and the owner's buttons of an unknown outcome. Its heading takes the focus after the send, so it is in view at 360 px and on desktop. It stays until a poster is added or the page is left. While it shows, `why` is hidden; the `empty` reason is drawn with `.help`, never `.why`.
- **Connecting on the page.** `facebook.ts` gains `startFacebook(shop, origin)`: `POST /api/facebook/connect`, `keepFacebookOrigin`, `location.assign(url)`, i.e. the body of `ShopAccount.vue:124-138`, which then calls it. The block of `ShopPublish.vue:639` becomes « Aucune Page Facebook n’est connectée. » (« Votre Page est à reconnecter. ») with the primary button « Connecter ma Page Facebook » (« Reconnecter ma Page »). A tab that cannot keep the return gets the sentence of `ShopAccount.vue:191`, then the same button goes on. Back from Facebook the app opens « Mon compte » as today (« Connecter cette Page », one Page or several); after a successful `choosePage` with a publish origin, « Mon compte » goes to `#<origin>` by itself (the link stays as a fallback). The draft and the caption are on the device (ADR-130): the same post is back.
- **Several posters.** « Publier plusieurs affiches » becomes a button that emits `several({id, download_url})`; `App.vue` sets `addPoster = {id, download_url, first: true}` and opens `#publier`. The composer's checked add (`ShopPublish.vue:610-620`, against a fresh candidate) appends, then `moveTo(…, 0)`; a poster already in the draft is moved first.
- **The review (v2: no change).** The button stays « Confirmer et préparer la publication »: it confirms, then opens `#publier-<id>`, where the page now offers the connection itself and comes back to the same post. No read of the Page from the review (one more failure path for one label). R-KIT-008's last sentence is amended to say so.

**Failure modes (Facebook).** `/api/facebook/connect` fails: its sentence under the button, nothing kept. The dialog is cancelled or refused: « Mon compte »'s card says why (existing) and the link back stays. The confirmation succeeds and the connection cannot start: the file stays confirmed and the app opens `#publier-<id>`, where the button is.

**Edge cases.** A post settled before the block was read: shown from `posts`. A second send replaces `sent`. Several Pages: the choice stays in « Mon compte ».

**Tests.** Vitest `publish.test.ts` (`empty` is help, not a fault), `facebook.test.ts` (`startFacebook` keeps the origin before leaving; keeps nothing when the request fails). Smokes `publish_browser.py:29, 115-151, 356, 810, 856` and `share_browser.py:1414-1466`: no Page → the page's button → the stand-in → « Connecter cette Page » → back on the same post; after a publish the outcome is the focused first block and no `.why` is visible; « Publier plusieurs affiches » shows the poster first.

---

## D-KIT-009 — The kit in the message box (R-KIT-009, slice 2)

**Now.** The style row offers the three house styles only (`ChatView.vue:659-661`); the last style is remembered per device, but only a house one is read back (`App.vue:316-325` checks `LOOKS`).

**Change.** One kit row above the field, hidden while it has the focus on a narrow screen (as the style row is, D-TEXT-FIRST-003):
- scene models as chips: the house ones and the shop's looks, most recently used first (`shopKey('kit.recent')`, ids updated at each start; an unknown id is skipped). A look chip sets the device's `draft.look`; the reader's body does not change (its `style` still names a house style);
- « Titre » as a native `<select>` of the title styles (D-KIT-012), with « Celui du modèle » when a look is chosen;
- the « Lignes de la boutique » switch when the shop has lines.
`rememberStyle` (`App.vue:308-313`) also keeps `title_style` and `lines`; `readStyle` accepts a saved look once the looks are read. `start(key, style, smallPhotoAccepted, sending, identity, kit)` with `kit = {look?, title?, lines?, scene?, keep?}`: one object for the slice-1 extras and these. With a kit, « photo + Casque Sony WH-CH720N 250000 » is a recap with no question (D-KIT-002).

**Tests.** Vitest: the order of use, a removed look dropped. Chat smoke: a saved look chosen → the scene body has its `look_id`; the next poster starts with the same choices.

## D-KIT-010 — Keep a poster's scene as a model (R-KIT-010, slice 2)

**Change.** `LookRequest` (`looks.py:61-63`) gains `visual_id: Id | None`: exactly one of it and `reference_asset`, both `exclude_if` None (earlier bodies keep their hash). With `visual_id`, the visual must be the shop's and a `scene`; in the same transaction `INSERT OR IGNORE INTO asset_access (shop_id, asset_sha, role) VALUES (:shop, :image_asset, 'style')`, and the job's `reference_asset` is that image, so `request_look` and `service.prepare` read it unchanged. In the final panel's « Autres actions » (`App.vue:3064-3070`): « Garder cette scène comme modèle », « Sans crédit. » under it, no dialog; name « Modèle {title} » cut to 40 (`free_name` settles a clash). Then « Le modèle « … » est dans votre kit. ». It is offered in Message and in « Pas à pas » through `savedLooks`.

**Errors.** `look_limit`, `not_found` (another shop's version), `budget_exhausted`: the sentence; nothing changes.

**Tests.** `test_looks.py::test_a_versions_scene_becomes_a_look_and_its_access_is_granted_once`, another shop's version 404, an earlier body's hash.

## D-KIT-011 — « Mon kit » (R-KIT-011, slice 2)

**Now.** `#styles` (`App.vue:2785-2787`) shows the house and own looks; a panel renames, removes, or starts a poster (`App.vue:3078-3087`, D-CREATION-LIBRARY-004). It cannot create one.

**Change (the same `#styles` route; label and heading « Mon kit »).** Sections: « Modèles de scène » (the wall and its panel; no colour codes, D-KIT-012; a look's lettering said as « Titre : comme sur l’affiche modèle », never the English brief), with under it the two ways to get one, as two sentences and one button: « Pour ajouter un modèle : dans un message, joignez une affiche que vous aimez et touchez son étiquette « Modèle de style » ; ou, sur une affiche finie, « Garder cette scène comme modèle ». » and « Nouvelle affiche » (v2: no creation on this page, see below); « Titre par défaut » (per device); « Lignes de la boutique » (the three fields, `PUT /api/shop-profile`); « Nom, contact et logo » (a link to « Mon compte »).

**No creation from the page (v2).** A look is a `plan` job on a poster (`poster_jobs.creation_id` is NOT NULL); a route that hangs it on the shop's newest poster puts a job in an unrelated poster's history, and rebuilding the table is out of proportion. The two ways above cover it: R-KIT-011's « create one from a poster here » is amended to « says how to add one ».

**Tests.** Smokes: `shop_dashboard_browser.py:267, 288-303, 336, 1079, 1365-1366`, `guide_browser.py:127`, `publish_browser.py:982` (« Styles » becomes « Mon kit »).

## D-KIT-012 — Title styles; « Pas à pas » trimmed (R-KIT-012, slice 2)

**Now.** The lettering is the look's `headline_style_en` only (`visuals.py:351-356`), refused without a look (`plans.py:306-307`); otherwise « a heavy, modern geometric sans-serif » (`plans.py:387-388`).

**Title styles (server).** `Headline.title_style: Literal["moderne", "condense", "sport", "serif"] | None` (`exclude_if` None). `plans.TITLE_STYLES`: `condense` « extra-bold condensed sans-serif in capitals, tight letter spacing, no ornaments »; `sport` « heavy italic sans-serif slanted forward, dynamic, no ornaments »; `serif` « elegant high-contrast serif in mixed case, generous letter spacing, no ornaments »; `moderne` gives today's default. One helper `lettering(conn, shop, headline)` replaces `look_style` at its three calls (`visuals.py:263, 333, 346`): a `title_style` wins, else the look's lettering, else none. The guard of `plans.py:306` accepts a `headline_style` from a `title_style`; an alignment other than centre still needs a look. French names: « Moderne », « Gras condensé », « Italique sport », « Élégant », « Celui du modèle ». Each also names the font of a title that is a layer (v2), from the three the renderer has: `moderne` and `condense` → `noto-sans` bold, `sport` → `montserrat-black-italic`, `serif` → `noto-serif`; choosing a title style sets the title layer's `font_id` when the title is a layer, so the choice means something with drawn texts off too. Chosen in Message (D-KIT-009) and in the « Style » tab; the default in « Mon kit », per device. Recap: « Titre : {name} · Gras condensé ».

**« Pas à pas » trimmed (`App.vue`).**
- No colour codes: the swatches of `App.vue:2871` and of the look panel (`App.vue:3083`) lose their `{{ colour }}` text.
- « Réglages »: Taille, Graisse, Contour, Ombre, Position X/Y, Largeur, Hauteur (`App.vue:2883-2884`) go into one closed `<details>` « Réglages avancés ». Police, Couleur, Alignement, Présentation du prix and the crop sliders stay.
- Two boxes replace the three (`App.vue:2841-2842, 2860`) (v2): « Dessiner les textes dans l’image » sets `headline.on` and the contact (when it can be drawn; `whyNoDrawnContact` says when not); « Dessiner aussi le prix » stays as it is (ADR-044: a price that is a layer changes without a credit). `headlineBody` (`App.vue:384`) is unchanged, so ADR-044 and ADR-055 hold. A restored version keeps its state until a box is touched. What goes: a drawn title with a contact as a layer.

**Tests.** `test_plans.py::test_a_title_style_reaches_the_prompt_without_a_look`, `::test_a_title_style_wins_over_the_looks`; a refinement keeps it. Smokes: `browser_smoke.py:577, 2446, 2900, 2912, 3016` and `chat_browser.py:953` (one switch); `terms_browser.py:194` and `editor_refinements_browser.py:177` (the crop sliders stay in view); `editor_refinements_browser.py:124` unchanged.

---

## Tasks

Four lanes own disjoint files and can run side by side in one checkout. **A** backend (`backend/src/affiche/**`, migrations, `backend/tests/**`). **B** publish (`ShopPublish.vue`, `publish.ts`, `facebook.ts`, `ShopAccount.vue`, `public/donnees.html`, `publish_browser.py`). **C** chat (`chat.ts`, `ChatView.vue`, `generation.ts`, their Vitest). **D** editor (`App.vue`, `document.ts`, `words.ts`, `browser_smoke.py`, `chat_browser.py`, `guide_browser.py`, `share_browser.py`). A task waits only for the tasks named after it. Backend commands run from `backend/`; frontend ones from `frontend/` with `corepack npm@10` on Linux. Every verify also means: `corepack npm@10 test` and `run build` pass for a frontend task, `uv run pytest -q` passes for a backend task.

**Slice 1 (R-KIT-001 … 008), shippable alone:**
| Task | Lane | Design | Owns | Verify → expected |
|---|---|---|---|---|
| T-KIT-001 | A | D-001 rule; `approved` word | `api.py` (TO_REVIEW), `test_api.py`, `test_shop_dashboard.py`, `frontend/src/dashboard.ts`, `dashboard.test.ts`, `shop_dashboard_browser.py` (STATES) | `uv run pytest tests/test_api.py tests/test_shop_dashboard.py -q` → passed, the new test included; `uv run python ../frontend/tests/shop_dashboard_browser.py` → OK |
| T-KIT-002 | A, after 001 | D-005 storage and drawing; D-003 scene request; r1 1, 2, 4, 6, 17 | migration 0021, `store.py`, `plans.py`, `visuals.py`, `api.py` (ProfileUpdate, ProfileView, the codes), `test_plans.py`, `test_poster_visuals.py`, `test_poster_drafts.py`, the head pins of `test_db.py`, `test_phone_session.py`, `test_reads.py`, `test_api.py` | `uv run pytest tests/test_plans.py tests/test_poster_visuals.py tests/test_poster_drafts.py tests/test_api.py -q` → passed |
| T-KIT-003 | A, after 002 | D-002 server; D-003/004/005 reader; D-007 2-4 | `reads.py`, `api.py` (MESSAGES), `test_reads.py` | `uv run pytest tests/test_reads.py tests/test_api.py -q` → passed |
| T-KIT-004 | B | D-008 page parts | `ShopPublish.vue`, `publish.ts`, `facebook.ts`, `ShopAccount.vue` (connect, choose), `publish.test.ts`, `facebook.test.ts`, `publish_browser.py` | `uv run python ../frontend/tests/publish_browser.py` → OK |
| T-KIT-005 | C | D-002 buttons; D-004 recap; D-005 recap lines, `line` card; D-006 roles; D-007 1 (ChatView half) and 5; chat words; new adapter members optional | `chat.ts`, `ChatView.vue`, `generation.ts`, `chat.test.ts`, `generation.test.ts` | `corepack npm@10 test` → all pass, new cases included (smoke in T-KIT-007) |
| T-KIT-006 | D, after 002, 005, 009 | D-001 editor words; D-002 form; D-005 Boutique box, review line; D-007 1, 4, 5 editor | `App.vue`, `document.ts`, `words.ts`, `document.test.ts`, `words.test.ts`, `browser_smoke.py`, `guide_browser.py` | `uv run python ../frontend/tests/browser_smoke.py` and `guide_browser.py` → OK |
| T-KIT-007 | D, after 003, 005, 006 | the adapter: D-003 `ownerScene`, D-005 keep lines and `revise(lines)`, D-006 look at start | `App.vue`, `chat_browser.py` | `uv run python ../frontend/tests/chat_browser.py` → OK, its new walks included |
| T-KIT-008 | D, after 004, 007 | D-008 « plusieurs »: `@several` sets `addPoster = {...poster, first: true}` and opens `#publier`; `connectForPost` and `@account` deleted; `share_browser.py:1465-1473` takes the page's own connection | `App.vue`, `share_browser.py` | `share_browser.py` and `publish_browser.py` → OK |
| T-KIT-009 | B, after 002, 004, 005 | D-005 « Mon compte » fields (r1 7), `api.ts` profile (r1 8), « Vos données » (r1 16) | `ShopAccount.vue`, `api.ts`, `public/donnees.html` | `uv run python ../frontend/tests/terms_browser.py` and `shop_dashboard_browser.py` → OK; `uv run pytest tests/test_api.py -k data_page -q` → passed |
| T-KIT-010 | — , after 003, 007 | paid check of slice 1, on the lead's word | report `docs/project/reviews/seller-kit-eval-<date>.md` | the 26 reads of 2026-11-14 plus about 20 new ones (each price writing, scene words in French and in Malagasy, lines, unused parts, capitals, four messages for `advert`), two posters with lines and scene words, one with a style photo, one trial of three products in one picture (evidence for the later feature, not a criterion); every wrong field listed, the guard's drops counted; no price outside the candidates; about USD 1.50 |

**Slice 2 (R-KIT-009 … 012):**
| Task | Lane | Design | Owns | Verify → expected |
|---|---|---|---|---|
| T-KIT-011 | A | D-010; D-012 server (no route, v2) | `plans.py`, `visuals.py`, `looks.py`, `api.py`, `test_looks.py`, `test_plans.py`, `test_poster_visuals.py` | `uv run pytest tests/test_looks.py tests/test_plans.py tests/test_poster_visuals.py -q` → passed |
| T-KIT-012 | C | D-009 kit row | `chat.ts`, `ChatView.vue`, `chat.test.ts` | `corepack npm@10 test` → pass |
| T-KIT-013 | D, after 011, 012 | D-011 page; D-010 action; D-012 title choice; adapter `kit`; remembered defaults | `App.vue`, `chat_browser.py`, `shop_dashboard_browser.py`, `guide_browser.py`, `publish_browser.py` (`:982` only) | those four smokes → OK |
| T-KIT-014 | D, after 013 | D-012 « Pas à pas » trimmed | `App.vue`, `browser_smoke.py`, `chat_browser.py`, `editor_refinements_browser.py`, `terms_browser.py` | those smokes → OK; the full suite once at the end of the slice |
| T-KIT-015 | — , after 013 | paid check of slice 2, on the lead's word | report | three title styles and one model kept from a scene, every text exact or listed; about USD 1 |

Start together: T-KIT-001 (A), T-KIT-004 (B), T-KIT-005 (C). T-KIT-006 (D) starts when T-KIT-002 is in.

## Contracts as built

**Chat client (T-KIT-005, 2026-11-23).** The server (T-KIT-003) and the adapter (T-KIT-007) match these.
```ts
// Card additions (all optional on the wire)
amounts?: number[]        // ask_price: one button each; positive whole numbers, distinct, the first 4 kept
unused_fr?: string[]      // each unused-part sentence, ALSO present in text_fr as its own "\n" line, byte-identical:
                          // the client removes those lines from text_fr and shows them in the warning block
offer_lines?: string[]    // any new-poster card: lines asked, not kept yet. Present = replaces the draft's offered
                          // lines; absent = keeps them. Held on the device, never sent to the server
scene_fr?: string         // recap: the client fills it from the draft
shop_lines?: string[]     // recap: written by the client at the tap (the lines drawn)
lines?: string[]          // `line` card: {kind:'line', text_fr, visual_id, lines, words, effect:'scene'}
// Read answer: draft.scene_fr?: string|null is read back. wireDraft sends scene_fr only when non-null.

// Adapter (all new members optional)
state.drawn?: boolean              // headline.on; undefined counts as drawn
state.shop.lines?: string[]
focus?: () => void                 // set by ChatView; App.vue calls it after closing the review
start(card, style, smallPhotoAccepted, sending, identity?, kit?: Kit): Promise<void | { look?: string }>
interface Kit { scene?: string; lines?: string[]; keep?: string[] }
  // lines = the profile's lines + the offered lines, in the order the recap showed them (for headline.lines)
  // keep  = the offered lines to save first; both present only when the switch is on and drawn !== false
  // returning {look} makes the thread say « Votre modèle de style est gardé dans vos styles : « {look} ». »
revise(card, visual, words, smallPhotoAccepted, owned, sending, style?, lines?: string[]): Promise<void>
```
`kit` is always passed for a new poster (sometimes `{}`), never on an existing one. A look job followed through `state.job` with `kind: 'look'` makes the wait line « Je lis votre modèle de style… ». Chosen where the design was silent: the label's accessible name is « Produit : marquer comme modèle de style » / « Modèle de style : marquer comme produit » (the visible word is in the name); the refusal of a fourth product photo is « Trois photos du produit et un modèle de style au plus. »; the recap box keeps name, price and format, and the scene, the lines switch and the identity sit under it. Smoke lines this breaks until T-KIT-007: `chat_browser.py:236-258, 326, 391, 597, 712, 726, 1246, 1277-1286, 1340, 2213, 2394, 2397`; `guide_browser.py:144, 181`.

**Server storage and drawing (T-KIT-002, 2026-11-23).**
- `GET /api/shop-profile` → `{revision, name, contact, logo_asset, lines: [str]}`; `lines` always present, `[]` when none.
- `PUT /api/shop-profile` takes `lines?: [str]`: at most 3, distinct without case, each 1–40 after trim, no `"`, no line break; absent = unchanged; `[]` removes all; an empty string is refused, so the client leaves empty fields out. Refusal: `422 shop_line_refused`, field `lines`, « Une ligne de la boutique : 40 caractères au plus, sans guillemet droit, sans montant, remise ni numéro (le prix et le contact ont leurs champs). Trois lignes au plus, toutes différentes. »
- A line refuses: `%`, `€`, `$`, the currency words (also glued to digits); a number of four digits or more, its digits separated by nothing, a space or a dot (« 5 000 », a phone number; « 24h/24 » passes: amended in T-KIT-003); a digit followed by `k`; the discount words; an injection.
- `POST /api/creations/{id}/scenes`: `headline.lines?: [str]` (absent = none; present = asked, and must equal the profile's lines in order): `409 shop_lines_missing`, `409 shop_lines_changed`, both before any job or credit; `adjustment_fr?: str` (1–500).
- A version's headline (`GET /api/visuals/{id}`) carries the drawn words as `headline.shop_lines`. The review's key is `text_lines`, required when `shop_lines` is there. `fidelity_incomplete` now ends « … Si un texte de l’image manque à la liste, rechargez la page. »
- Departures from the text above, kept: the D-KIT-003 sentences change only when a scene has kept adjustments (every other prompt stays byte-identical, the golden prompt test holds); the lines' sentence names the contact line and the price label only when they are drawn.

**The reader (T-KIT-003, 2026-11-23).** Shapes as the chat client expects them. `ask_price`: no amount read → the sentence alone; one → « Le prix est-il 250 000 Ar ? » + `amounts:[250000]`; two to four → « J’ai lu A ou B : lequel est le prix ? » + `amounts`; five and more → `card_ask_price_many`, no `amounts`. `text_fr` lines in order: the card's sentence, « J’ai changé : … », the line notes, the unused lines (also in `unused_fr`, present only when non-empty, as `offer_lines`). The draft answers `scene_fr` only when set. `line` card: `{kind:"line", visual_id, lines, words, effect:"scene", text_fr}`, with `card_redraw` and, when the message asked more, « Demandez le reste ensuite. ». Not an advert: `unclear` with `card_not_advert`. Scene `change` cards made from words end with `card_redraw`. Stub markers: « scène : X », « ligne : X », « pas utilisé : X », each up to the next marker or the end; the stub returns no price when the message has two candidate amounts or more. Departures kept: the reader is **not** sent the shop's lines (the server compares; « Vos données » says only that a line written in a message is part of that message); a comma and any white space also count as a separator in the line's number rule; the identity clause reads « le logo et le contact de la boutique »; the guard's logs name the field, never the words. Proof: the whole backend suite 2069 passed.

**Review fixes and the kit's server (T-KIT-016, T-KIT-011, 2026-11-24).**
- Amounts: a run that starts with `0` is never a candidate (a phone number); « 1 200k » offers 1 200 000 and 200 000; a number followed by another currency or by a measure (`mah, go, gb, mo, w, hz, …`, the lead's decision for bare numbers only) is no candidate; a poster's price question names what it read (no buttons on a poster).
- A line refuses discount words as word starts (« Promos », « Offres », « Prix cassés »), amounts in words, `fmg`, and a number of seven digits joined by dashes; « Livraison 24-48h », « 24h/24 », « 7j/7 » pass. A refused line in a message says `card_line_refused` « « {} » : une ligne de la boutique ne contient ni montant, ni remise, ni numéro. ».
- A follow-up on a draft read as `other` keeps its scene words and lines; `unclear` only when nothing usable came back.
- `POST /api/creations/{id}/looks`: body `{name, reference_asset}` or `{name, visual_id}` (exactly one; `422` otherwise); with `visual_id` the version must be the shop's (`404`) and a scene (`unsupported_visual`). A new look answers `202 {job_id, status_url}`; a look the shop already has from the same image answers `200 {job_id, status_url, reused: true}` (the job that made it, already succeeded: the client follows it unchanged), nothing spent, checked before `look_limit`.
- `headline.title_style: "moderne" | "condense" | "sport" | "serif"`; the title style wins over the look's lettering, the alignment always comes from the look; a refinement keeps it. The title layer's `font_id` from the style is client work (T-KIT-013).

**The kit row (T-KIT-012, 2026-11-24).** What `App.vue` provides (all optional): `state.looks?: {id, name, reference_asset}[]` (`savedLooks` fits), `state.recent?: string[]` (house-style and look ids mixed, most recent first), `state.kit?: {look?, style?, title?}` (the last choices, used for a new poster's fresh thread); `Kit` gains `look?: string` and `title?: 'moderne'|'condense'|'sport'|'serif'`. `start`'s `style` argument stays a house style even with `kit.look`: the adapter picks the look after it. `kit.title` is absent when it is the scene's default; with a style photo `kit.look` is never sent. A message that names another house style drops the chosen look; an unknown look id is not used.

**Found by the second walk (2026-11-24).** A first image ignored the owner's scene words although they were in `kept_adjustments`: the scene sentence led with the house style. `compile_scene` now writes, for an image made from nothing with owner's words: « Scene: the owner described the picture he wants. His words are listed as kept_adjustments: they set the backdrop and its colours, the setting, the light and what stands around the product. Follow them first, even where they differ from the palette. Use the house style only for what they leave open … », and the constraint on props excepts what a kept adjustment asks for. Proof: the same words gave the grey studio before and the red backdrop with flames on a wooden table after ([walk](../reviews/user-walk-2-2026-11-24.md)).

**Found by the owner's own trial (2026-11-24, T-KIT-020).** On the pack of three, « Aura studio on the center » gave a version with every product where it was, a studio glow in the centre and the kept wooden table gone. Three causes, all in `compile_scene` on a refinement: the request was only a value of the data block that the prompt itself calls « not additional instructions », against « preserve its composition »; the scene sentence led with the house style again; nothing said that a name in the owner's words can be a product. Now: « Image 1 is the selected base scene to refine. It is not the identity reference. The owner asks for one change to it, in his own words, listed as requested_adjustment: make that change, clearly visible, even where it moves, swaps, resizes or replaces what image 1 shows. Everything the request does not touch stays as in image 1. »; the owner's scene sentence whenever kept adjustments exist; and, with kept adjustments or on a refinement, « Where the owner's words hold a brand or a model name, it most likely names one of the products of the reference photos, not a kind of scene … ». Prompts are compiled when asked and stored with the job: nothing already asked changes. Proof: the same words on the same poster then put the Aura Studio in the centre with the table back (one paid image).

**Found by the owner on the deployed build (2026-11-24, T-KIT-021).** A reference with a layout of its own (three cards, one product in each) gave its colours only. Now a first image made with a saved model carries `style_reference_asset` = the look's `reference_asset`, set by the server in `request_scene` when the request names `headline.look_id` and sends no reference of its own (`reference_roles` ends with `style`); the request body and its hash are unchanged. `compile_scene` on a first image: « Image N is a style reference only, a finished advert. Borrow its composition: how the frame is divided, and the frames, cards, panels or podiums that hold a product; where it shows several, rebuild them inside the product area and set one product of the identity references in each, in place of the single floating hero object. Borrow also its backdrop treatment … »; with a look, also « Composition: where the quoted art direction describes frames, cards, podiums, panels or several places for products … ». `looks.SYSTEM` asks for the composition first in `direction_fr`. Client: `nextRole` gives `inspiration` to the image attached after three product photos (null only when a model is there too; the notice is « Trois photos du produit et un modèle de style au plus. »); the composer's form handles `paste` and `drop` of image files through the same path as the picker. The job's payload marks it `style_reference_from_look`: the visual's view keeps `style_reference_asset` null and the reader's `model_image` false, so the page does not send it again with a correction (the base image carries the layout) and a change of style says nothing about a lost model image.

**T-KIT-018, 2026-11-24 (the walk's remaining findings and the first trials on `gpt-image-2.5-flare`).** A correction's prompt now begins with « Task: edit image 1. The owner asks for this change, in his own words: "{requested}". The new image must show that change clearly: an image that looks the same as image 1 has failed. » (the same screened words as `requested_adjustment`, which stays in the data block). The shop's lines: « Clearly legible on a phone, in semi-bold letters about {2.8% | 3.5% | 2%} of the frame height » (Publication, Carré, Story). Client: `ShopPublish.vue` `again` (every chosen poster has `published_at`) words the button « Publier à nouveau… »; `ShopAccount.vue` scrolls the Facebook card to the top when its state is `choose`; `ChatView.vue` `waiting` keeps a send asked during an upload (the button is off only for a failed photo; the field is read-only and « Envoi dès que la photo est prête… » is shown until it leaves; a photo that fails or is taken out drops it), and a recap made while the poster has no version carries `first`: tapped once the poster has one, it is retired with a sentence and nothing is sent; `App.vue` `keptAs` (a saved look whose `reference_asset` is the file's scene image) replaces « Garder cette scène comme modèle » by a sentence; the chat adapter's `shop.logo` and `shop.contact` are the open poster's own ticks, and a recap before the first version carries `identity: true` when one is ticked; `rememberStyle(false)` keeps the contact's place and the brand's writing only.

**T-KIT-022, 2026-11-24 (the logo drawn by the image model).** A scene request whose `headline.draw_logo` is true (optional, omitted when unset so that earlier bodies keep their hash; the page sets it on every scene with a drawn title, in Message and in « Pas à pas », T-KIT-024; a request without it keeps the logo as a layer, with the rules of before) on a poster that includes a plain logo: `request_scene` appends the logo to the job's images (`reference_roles` ends with `logo`, after `style`) and writes the file's hash as `headline.logo` in the job's payload, so `get_visual(...).headline.logo` tells every reader that this version drew it. `compile_scene(logo_image=True)`: « Image N is the shop's logo. Draw it once in the picture, whole and exactly as it is: every shape, its background if it has one, its colours and proportions, and every word it holds, letter for letter; flat, not redrawn, not restyled, nothing added and nothing left out. About 14% of the frame width. Place it where the owner's words name a place for the logo; otherwise in a free corner of the backdrop … » (a refinement adds « It is already in image 1: keep it as it is and where it is, unless the requested change moves it. »); the Layout sentence keeps no area for the logo; the constraint on writing names « the shop's logo with any words it holds ». `request_refinement` refuses `headline_stale` when the base drew a logo that the poster no longer includes or has changed. `required_checks` adds `logo_drawn`. `exports`: `logo_stale` (409, « Le logo dessiné dans l’image ne correspond plus à celui de l’affiche. Générez une nouvelle version. ») when a drawn logo is also a visible layer, is not included, is not the poster's file, or when an included logo is neither visible nor drawn. `Document.consistent_layers`: a logo layer may be hidden while the logo is included. Client: `chooseVisual` hides the plain logo layer for a version whose `headline.logo` is set and shows it for one without; the identity tick does not show it over a drawn one; `textChecks` adds « Logo de la boutique »; a copy or a change of format shows the layer again. Reader: a place named for the shop's logo is `instruction_fr`, not `identity`. T-KIT-024: the logo sentence says the plan's logo box in words when the plan has one (« otherwise at the {top|bottom} {left|centre|right} of the frame », the place chosen in « Pas à pas »), and, for a file with transparency (`headline.logo_transparent`), that the white around the logo is no part of it; `logo_region` returns nothing for a version that drew its logo, so `logo_box` and `logo_footer_box` are absent from its view.

## Open points

Only what would change the design; each with the recommendation taken above.
1. **The kit's defaults per device or per shop.** Per device (taken): no migration, and the shared login of the pilot would otherwise flip one phone from another (D-TEXT-FIRST-001). Per shop needs one more column and a rule for two devices.
2. **Where the lines are drawn.** Free placement by the image model (taken), measured by T-KIT-010. If two images out of three misplace them, add a `lines` region to the plan (`FieldName`, `fixed_plan`, the Claude plan schema): a larger change, decided on that evidence.
3. **What a line may say.** Amounts and numbers refused, commercial words allowed (taken): the seller's own conditions, reread in the review. The other way is a list of allowed words (warranty, delivery, payment), which cannot be complete and would refuse « Retrait en boutique ».
4. **A model created on « Mon kit » with no poster yet.** It rides on the newest poster (taken) and is refused without one. The other way is a migration that rebuilds `poster_jobs` with a nullable `creation_id`.

## Costs and risks

- **Expensive.** R-KIT-003/004/005 change the bytes of the new-poster read, measured in T-CHAT-002: a paid re-read before calling it working, and a real risk that scene words take part of the name (the word guard and the recap are the only defences). R-KIT-005 adds a prompt sentence whose placement is unproven (open point 2). R-KIT-012's boxes rewrite the smoke paths built on three boxes.
- **Cheap.** R-KIT-001 (one clause), R-KIT-002 (the parser and the buttons), R-KIT-006 (client only), R-KIT-007, R-KIT-008 (frontend only), R-KIT-010 (one field and one access row).
- **Serial work.** Lane D (`App.vue`, 3 100 lines) carries five tasks; it sets the pace of each slice.
- **Smokes that change.** `chat_browser.py` (roles, words, wait, price buttons, lines, the switch), `guide_browser.py` (roles, « Mon kit »), `shop_dashboard_browser.py` (state names, « Mon kit »), `publish_browser.py` and `share_browser.py` (no-Page flow, outcome, several), `browser_smoke.py` (version words, the switch, « Réglages avancés »), `terms_browser.py` and `editor_refinements_browser.py` (« Réglages »).
- **Money.** No credit rule changes. New spend: one planner brief per style photo or kept scene (about USD 0.009, no credit), the two paid checks (about USD 2 in all).
