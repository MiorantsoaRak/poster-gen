# DECISIONS

## ADR-107 — 2026-11-15 — Multi-shop design v4 approved; one identity gate in the browser

- `designs/multi-shop.md` v4 is approved under the user's autonomy grant (ADR-106) after three review rounds by Codex and a devil's advocate (reviews/multi-shop-design-r1 to r3 and multi-shop-design-devils-advocate, 2026-11-15). Round 3 rejected v3 on four points; v4 answers them and was not reviewed again as a design: the code reviews of T-MULTI-SHOP-001, 005 and 006 check them.
- The migration (0013) rebuilds the shop table and the read ledger with foreign keys switched off around the migration and checked before commit, which needs a change of `affiche.db.migrate`. Three independent readings and two runs on copies of the test database (one with the process killed mid-way) found it sound. It has not run on the pilot's real database nor on the release image's SQLite 3.40.1: a rehearsal on a fresh copy of the hosted database, in the release image, is an automatic step of the release, before anything is stopped.
- **One identity gate replaces a list of cases.** Each review round found another path by which a browser could show the previous shop. A page is now bound to one shop for its life, shows it only while the server's session answer names it, and on any other evidence shows the signed-out screen; it never reloads into another shop. Cost: without the browser's cross-tab lock a late answer can leave someone signed out.
- Kept from the interim mechanisms: a daily ceiling of provider spend per shop (plans, textures, looks and text patches will cost the provider and no credit). Cut: a cap on queued generations (the fair queue serves every shop in turn), a password dialog (the route is built; its screen is the shop's dashboard).
- Suspension keeps sessions and makes them unusable, so enabling a shop undoes a mistake; no provider call is sent for a suspended shop, for a job or for a chat read.
- The pilot shop's identifier is `originalphone` until the user says otherwise.
- `requirements/multi-shop.md` is amended with the wording the reviews accepted (R-001, 003, 004, 005, 006).
- The release commands move from `deploy/deploy.py` into `deploy/release.sh` so that a failed rehearsal can be tested; the user's command stays pyinfra.

## ADR-106 — 2026-11-15 — Release 1 is built under the autonomy grant, multi-shop first

- User, on the roadmap and the six draft requirements: "You have the autonomy, start with what you consider more important. As always, you can run paid test." Requirements, designs, implementation, local commits and paid tests inside the cap are Claude's to pass; push stays the user's word; nothing is deployed (ADR-105).
- `requirements/multi-shop.md` is approved as drafted, with its working default: the shop's identifier is chosen by the operator. The other five files are approved when their turn comes, each with its defaults unless the user changes one first.
- Build order as in ROADMAP.md: multi-shop, prepaid balance, administration dashboard, conditions of use, the shop's dashboard, « Partager ».
- R-TERMS-002 (what the image may write) stays the user's decision; its default is not built before he has seen it again.

## ADR-105 — 2026-11-15 — Invite-only service first; no deploy until it is ready with both dashboards

- User decision after Codex's research and Claude's review: the findings become a roadmap, each feature its own requirements; "for now on, we won't deploy the change until an invite only feature is ready, with per user dashboard and an admin dashboard".
- Release 1 « Invitation » is six requirement files, drafted with working defaults: several shops with their own sign-in; a prepaid balance of generations; an administration dashboard; conditions of use and the owner's check; the shop's dashboard; « Partager ». Order and reasons in [ROADMAP.md](ROADMAP.md).
- Claude's review had advised a command line for the operator and a single credit line for the shop instead of two dashboards. The user asked for both dashboards as a condition of the release; they are specified, kept small (tables from the ledgers, no settings for secrets, models or prompts).
- The deploy freeze covers what is already pushed: the chat work of 2026-11-15 is on `origin/main` and stays undeployed; the pilot remains on the version deployed on 2026-11-14.
- PROJECT.md gains a scope-change note; its original charter text is kept.
- Still out: public sign-up, online payment, subscriptions, publishing through Meta's API (Phase 2 and 3 of the roadmap).
- Open, the user's: what the image may write (R-TERMS-002); the shop's identifier at sign-in; welcome credits; a first price to test.

## ADR-104 — 2026-11-15 — A price right after a number of the name, with no comma (amends ADR-095)

- Found by the paid test T-CHAT-REST-002: « iPhone 15 1 200 000 Ar » asked for the price again. The digit tokens `15 1 200 000` are not one correctly grouped amount, so the server offered no candidate.
- When the whole run of digit tokens before the unit is not one amount, its ending that is a correctly grouped amount of two groups or more is taken as the amount (« 1 200 000 »), with its own endings as before (« 200 000 »). What stands before it is a number of the name.
- Not relaxed: a lone last group (« Prix 1234 567 Ar » gives nothing, the adversarial case of ADR-095); a run with no unit; badly grouped digits (« 700 00 Ar », « 20 00 000 Ar »).
- The rest of ADR-095 holds: the model's price must be one of the candidates, and the recap shows it large.

## ADR-103 — 2026-11-15 — The rest of the chat audit: measure, then build only the style, identity in the first message, a sentence for the format

- User: "go ahead with the rest of the audit", then "you can go full automation" (requirements, design, implementation, local commits and paid calls inside the cap; push and deploy stay his word).
- A first design (settings as rows of the field table, an identity rule, a fresh-plan helper) was rejected by the design review and the devil's advocate. A paid baseline (USD 0.17) showed that the scene adjustment of ADR-102 already does a coloured word and the brand's lettering, and does not change the style.
- Built: a `style` field on a poster, answered by a new card kind `restyle` (a whole new image on a fresh plan; the model image and kept adjustments are not carried, and the card says so; a new kind so that an old tab cannot pay for it); the shop's logo and contact asked in the first message, through the editor's own selection when the poster is made; one sentence to « Pas à pas » for identity on an existing poster and for another format.
- Not built, on purpose: rows for the coloured word and the brand's lettering; identity changes on an existing poster (a free removal breaks the version's plan for later changes); format copies from the chat.
- The new-poster reader gains one field, so its reading test of 2026-11-14 is run again (done: its 19 new-poster messages read as then).
- **An older open tab changes nothing and pays nothing (found by the code review, twice).** Every request carries the bundle's number (`X-Affiche-Bundle`, `BUNDLE` in `frontend/src/api.ts`); the server refuses every state-changing request under `/api/` except the session from a lower or absent number, before any handler: 409 `bundle_outdated`, with a sentence that says nothing is saved and to note the last changes before reloading. Reads still work. One guard for the class, instead of a compatibility patch per card. Raise both constants together whenever a change makes an older open tab unsafe. Consequence at the next deploy: the bundle now on the pilot is refused on every change until the page is reloaded, in « Pas à pas » too.
- An explicit « sans logo ni contact » in the first message is kept and clears those two ticks of the form; saying nothing leaves the form's ticks as they are (they already went into a poster made from the chat before this change).

## ADR-102 — 2026-11-15 — In the chat, a message that changes no word is the scene adjustment, in the owner's own words

- User reports 2026-11-15: « Use sony logo » was answered « L’affiche a déjà ces textes. »; then a poster he made with « Ajustement de la scène » in « Réglages » (a list of features with icons, the Sony mark, a stylised product name) showed that this field is the general tool, and that the chat used a small part of it. He said: go ahead with T-CHAT-SCENE-FIELD.
- On a poster, when the reader finds no change of title, brand, subtitle or price, the message goes whole and unchanged to the scene adjustment (the editor's `refineScene`, from the image shown). The reader's `instruction_fr` is only a signal that the message asks something of the picture; its text is never sent, so the reader cannot add a feature.
- A word that does change keeps its own path (a whole new image); the scene is asked after, as before.
- T-CHAT-REDO is withdrawn before it was committed: a refinement from the image answers « Use sony logo » better than a blind redraw. With no word to change and a message the scene's screen refuses (a price already on the poster), the answer is « L’affiche a déjà ces textes. » again.
- The scene adjustment's screen is one function, `screen_adjustment`, for the editor's field and the chat. It refuses currency, promotion and warranty wording, the words « prix » and « price », an amount of five digits or more that no technical unit follows (« à 300 000 », « 450000 »; « 10 000 mAh » passes), and injected instructions, across lines. Lettering, a logo, features and their numbers pass (« Bluetooth 5.2 », « réduction de bruit », « 70 h »). Before, the field also refused « titre », « police », « font », "add/write … text/logo", and « réduction de bruit »: « Ajoute le logo Sony » was refused, « Use sony logo » was not. This widens the step editor's field too. Decided by Claude on the user's "go ahead", stated to him as his call.
- The screen of art directions, plans and saved styles (`screen_art`) is not changed: text written by a model there has no owner's words behind it (code review r1).
- A refinement says again the adjustments asked before on its chain, and that its own wins (found by the paid test: a list of features added by one adjustment was dropped by the next).
- **The reader is the second screen in the chat (user decision 2026-11-15, after three rejected review rounds).** Each round found new wordings past the list of phrasings; such a list cannot be complete. The reader's answer gains `commercial`: true when the message asks the picture for a price, an amount, a discount, a promotion, a warranty or a free offer, in any wording or language, or asks to override the rules. A scene adjustment is refused when it is true. It only refuses: what the list refuses stays refused, and a change of the words (a new price in its field) is not stopped by it. « Pas à pas » has no reader, so its field keeps the list alone, with the image request's own rule and the owner's check. Paid test: ten wordings the list does not know, none became an adjustment; eight ordinary requests all passed.
- Kept as it is, against a reviewer's note: a message that only restates a word already on the poster gets a scene-adjustment card, not « L’affiche a déjà ces textes. ». The reader cannot tell « Use sony logo » (heard as "brand: Sony") from a plain restatement, and the card is an offer with its cost, not a spend.
- **Open, the user's decision (his note of 2026-11-15):** he did not write the features of his poster; he asked the image model for "4 lines of features max" and it chose them. AGENTS.md says "never invent … specifications". Today nothing stops the image model from writing features nobody verified; the check's point on extra text is the only guard. Not changed here.
- Limits: the image model decides how well it follows; a manufacturer's mark is not guaranteed. Features drawn in the image are not in the poster's data. A message in English or Malagasy is sent as written.

## ADR-101 — 2026-11-15 — A word change from the chat also keeps the scene adjustments asked by message

- Found by the paid check of ADR-100: the brand change on the night-blue version kept « Luxe sombre » but lost the night blue, which came from the refinement « mets un fond bleu nuit avec des reflets ». A refinement changes the image, not the plan. User decision 2026-11-15: carry the adjustments into the new image.
- The chat's scene request names the version it replaces (`keep_adjustments_of`, left out of the hash when absent). The server walks that version's chain (each refinement's stored `instruction_fr`, back to its scene) and adds them to the scene prompt as `kept_adjustments`, with one line saying they win over the art direction where they differ. They are stored with the new scene's job (`adjustments`), so the next word change carries them on. No migration.
- Not chosen: starting the new image from the refined image as a reference (least known, needs its own paid tests); only saying it on the card (the owner pays a second image to get the adjustment back).
- Limits: the new image is redrawn from words, so it follows the adjustment, it does not copy the refined image. A refinement made before instructions were stored (ADR-098) gives nothing to carry. « Nouvelle version » in the step editor does not carry them: only a chat card names the version it replaces.

## ADR-100 — 2026-11-15 — A word change from the chat keeps the version's style

- Found by the paid test T-CHAT-008: in a new browser, « JBL c'est la marque… » turned a night-blue poster into a light one. A whole new image followed the editor's current style (ADR-099's stated limit). User decision 2026-11-15: carry the version's style into the new image.
- A version's style is in its plan (direction, colours, surface, light, camera), its stored headline settings and its model image. `revise` now takes all three from the version the card targets: `restoreHeadline()`, the version's `style_reference_asset`, and the version's plan, saved again as a revision at the document's revision (the existing `/api/plans/{id}/revisions`). No fresh plan is asked, so no planner call is paid for a word change.
- `GET` of a version now gives its `plan_id`. No migration.
- `restoreHeadline()` restored `signature`, a key nothing reads; it now restores `contact` and `brand_text`. This also applies when a poster is opened in « Pas à pas ».
- Stated limit: a version whose plan belongs to another poster (a copy) or to another format, or that has no plan, is redrawn with the editor's style, as « Nouvelle version » does.
- Not carried: the coloured price pill of a layer price follows the editor's style as before.

## ADR-099 — 2026-11-15 — A change asked in the chat is a set of the editor's fields, not a kind

- User report: « Sony is the brand, put it on top, the product title on the second line » was answered « Le titre et le format se changent dans Pas à pas ». He asked for a durable change of process, not a prompt patch or one more condition. He restated the autonomy grant for this work on 2026-11-15; push, deploy and paid calls stay his word.
- On an existing poster the reader fills the editor's own fields (title, brand, subtitle, price, scene instruction) from one table on the server; the schema, the checks, the card's lines and the "what I can change" sentence come from that table. The reader of a new poster is not touched.
- The server reads the current words from the version the owner looks at (its stored job) and from the document, never from the editor's refs, and states the effect by one rule: a result that differs from the image's drawn words is a whole new image; otherwise a free edit; an instruction alone is a refinement.
- The card promises the words (all four set from the card at the tap). Style, coloured word and contact line stay the editor's state, as for the price card of ADR-098. A complete restoration of a version's settings was rejected: the plan is made from the editor's state.
- A brand asked for is taken out of the title; without that the scene route drops it and the paid image shows no change.
- Word guard: a word of a title, brand or subtitle must be in the owner's message or already on the poster. It cannot detect a wrong arrangement of the owner's own words; the card and the check show each text whole.
- Exception: brand and subtitle are not offered on a poster without drawn words.
- A read from before this change that never reached the server is refused without spend (`reload_required`); one user, no read on the pilot yet.
- Not decided: keeping the text of messages the chat could not take (`chat_reads` holds a hash only). The user's call.
- Gates: requirements amended (R-TEXT-FIRST-004, 005); design D-TEXT-FIRST-005 v4 after three review rounds and a devil's advocate (reviews/text-first-d005-*-2026-11-15.md). Round 3 rejected v3 on four points, fixed in v4 and not reviewed again; each task's code review checks them.

## ADR-098 — 2026-11-15 — Changes from the chat: one unresolved paid card, one waiting message, a free price change when the price is not drawn

- While a paid card has no known outcome, no other paid card is admitted (recap, change, replacement after a refused version); its own « Reprendre » / « Réessayer » stay. While a read waits for its answer, no thread sends another one; the composer points to the poster where it waits.
- A price change redraws the poster (paid) only when the selected version has its price drawn in the image (`headline.price_ar` on the visual). Otherwise it is the editor's price edit, free, and the approved image is kept (the project rule "reuse approved visuals for price-only changes"). « Remettre l’ancien prix » restores the price the image shows.
- A refinement refused with `headline_stale` becomes a whole-poster card at the document's price, through the editor's scene path, so a poster made in steps keeps its look.
- New refine jobs store the owner's instruction for the list of modifications; older ones show « Scène ajustée ».

## ADR-097 — 2026-11-14 — The chat never guesses what a paid request became (after five review rounds)

- One chat tab per device: `ChatView` holds the Web Lock `affiche-chat`; another tab shows « Le chat est ouvert dans un autre onglet. » and « Continuer ici », and sends nothing. Each acquisition has its own token, and work started under an older token stops. Without Web Locks the chat is not offered (« Pas à pas » instead).
- A paid card keeps the exact `/scenes` request (key = the card's id, body, revision), saved before it leaves. After a reload or a return from « Pas à pas » nothing is sent by itself: the card shows « Reprendre » with the cost, which sends that same request again; the server answers what it stored, runs it once, or refuses.
- A card is retired, and a new one offered, only on a refusal that also blocks a late delivery of the same request (`plan_stale`, `revision_conflict`, `attempt_limit`, `acknowledgement_required`, `validation_error`, `format_locked`, `not_found`, `idempotency_reused`, `title_*`). Every other answer keeps the request and « Réessayer ».
- A pending read is one record apart from the typed text, cleared only by the answer to its own key.
- Check and download go through the editor's own dialogs; « Télécharger » shows only on the version selected in the document. The recap tap stands for the editor's « Les photos correspondent… » agreement.
- One change to the step editor, accepted: a focused field is revealed again when only the visible height shrinks (a keyboard opening after the focus); with the new « Continuer par message » button in the phone bar, one browser check failed 4 runs in 12 without it.

## ADR-096 — 2026-11-14 — A read asks the model for no reasoning; the Claude adapter accepts reasoning blocks

- Paid test (reviews/chat-read-eval-2026-11-14.md): 9 of 26 reads failed because `claude-sonnet-5-5` reasons by default and returned a reasoning block before the text, which `ClaudePlanner.structured` refused. A read now sends `thinking: {"type": "between_tools"}` (the model refuses `disabled`), verified on the live API: one text block, about 40 output tokens, same fields. `structured` accepts `thinking` and `redacted_thinking` blocks beside exactly one text block, for every caller; the other callers' request bodies are unchanged.
- The price guard of ADR-095 is widened for two everyday spellings: the token before the amount may be a code of ASCII letters and digits with at least one letter (`256Go`, `5G`, `13C`), and a last token of four characters or more is the amount alone (`airpods pro 2 350000ar`). Accepted: `12 3456 Ar` gives 3456.
- The model stays `claude-sonnet-5-5`: median 2.6 s and about USD 0.0025 per read, under the design's 3 s threshold.

## ADR-095 — 2026-11-14 — The price read from a message: an allowlist of whole digit tokens (user choice after three review rejections)

- Three Codex rounds broke every "forbidden character" version of the price guard (`-700 123 Ar` gave 123, a superscript minus, a foreign digit, `A55..123 Ar`). Asked, the user chose the allowlist rewrite.
- Rule (`posters/reads.py`): the message is split on spaces; an amount is only whole ASCII-digit tokens (or one dotted token) directly before `Ar`, `ariary` or `MGA`, correctly grouped as a whole; nothing is salvaged from a malformed one. The token before it may hold a digit only if it starts with a letter (a model code: `A55`, `WH-1000XM6`) or ends with `,` `;` `:` (the end of the name: `JBL Flip 7, 700 000 Ar`).
- Accepted on purpose: `Redmi Note 13 700 000 Ar` and `iPhone 15, 1 200 000 Ar` offer the whole amount and its group suffixes, the model chooses and the recap shows the price large; `700, 123 Ar` gives 123; `(700 000 Ar)` gives nothing and the chat asks again.
- Also decided in the task: a read for an abandoned poster is refused (`creation_abandoned`), as the poster routes do; a model answer cut, refused or without text is a failed read with its cost kept, only a complete answer outside the schema is the « unclear » card.

## ADR-094 — 2026-11-14 — Creation by message: design v2 approved; five requirement amendments

- [Design v2](designs/text-first-generation.md) is approved under the autonomy grant after a fresh review (APPROVE WITH FIXES, four P1) and a devil's advocate. Kept against challenge: a synchronous paid read with its own ledger table `chat_reads` summed in `spent_micros` (the job queue needs a poster, a first message has none), and the model on every message (a parser reads `Redmi Note 13 700 000 Ar` as 13 700 000 Ar).
- Changed after the devil's advocate: (1) the conversation lives in the browser; the server has one stateless route `POST /api/reads` and the ledger; the list of modifications is built from the poster's versions, so it is the same everywhere; (2) the chat calls the step editor's functions in place, nothing is moved out of `App.vue`; (3) the check and the download use the existing review and final dialogs, one tap more than the mockup, to keep the photo comparison and the summary (ADR-051); (4) no automatic price read-back in this slice, measured offline first; (5) the start view is remembered per device.
- Fixed after the review: the price must be one of the amounts the owner wrote before « Ar » (the server lists them), the card's id is the idempotency key of its paid request and a tapped card is spent, the ledger rule is the existing one (cost 0 only on a 429 or a call never sent), `ClaudePlanner.structured` takes `max_tokens` and `timeout`.
- Requirements amended to match (marked in the file): start view per device, check through the existing review screen, read-back deferred, conversation per device, limits per message and per day. The user can reverse any of these.

## ADR-093 — 2026-11-14 — Full autonomy for creation by message; requirements approved with two working defaults

- User: "go full automation again for the implementation and if there is additionnal search needed. You can make as many paid call as needed". For this feature Claude decides the open points, researches, designs, implements, commits locally and makes paid calls inside the configured cap, reporting the spend. Push and deploy stay the user's word.
- R-TEXT-FIRST-001 to 005 (Draft v2) are approved under this grant with two working defaults, both reversible by the user: (1) no web image search in the first slice, the chat asks for a photo or offers the shop's own photos (this sets aside the automatic lookup of ADR-088 for now; reasons: the search provider's retention terms, image rights, wrong-variant risk and the cost of safe remote fetching); (2) the automatic read-back of the drawn price is in the first slice, as a warning only.

## ADR-092 — 2026-11-14 — Each chat message is read by a paid model call (user decision)

- User: "go for the paid call per message". Every message of the creation chat is read by a model that extracts product, price and style and classifies a change request. The call is reserved and recorded in the spend ledger and counts against the cap.
- Consequence accepted with it: reading a message is not confirmed tap by tap, unlike an image generation. It is bounded instead (maximum per message, per poster and per day; values in design). The model never starts a generation and the price still passes the existing validation.
- Draft v2 of [text-first-generation.md](requirements/text-first-generation.md) is rewritten on this basis. Still the user's to decide: web image search or shop photos only, and the automatic read-back of the drawn price. The reading model is chosen in design.

## ADR-091 — 2026-11-14 — Creation by message is a real chat beside the step editor (user direction; mockup only)

- User direction: a proper chat, one attachment button for the product photo and the inspiration image together, a first screen with the choice « Par message » / « Pas à pas » that becomes the default view, the chat kept for the first request and every polish, a visible list of the modifications, and one colour behind the glass instead of blue plus cream. Fewer steps and fewer words.
- Mockup `docs/project/mockups/chat-first/` replaces the three-step wizard of ADR-089 as the concept to judge. In it: the first image is the product and the next the inspiration, one tap on the label swaps them; the recap and the paid confirmation are one card with one button and its cost; a correction is typed, not edited in fields; a price change says that the image is redrawn.
- Claude's pushback on the research, open until the user answers: (1) no web image search in the first slice (a photo is attached or reused from the shop's own photos); (2) reading a free message needs a small paid model call per message, to meter in the ledger; (3) an automatic read-back of the drawn price before the owner's check. None is decided. Requirements R-TEXT-FIRST stay Draft; no production code changed.

## ADR-090 — 2026-11-14 — Persistent polish chat; account credits deferred

- User requires the chat to remain available for polish after generation. Update the isolated mockup with follow-up requests, conversation history and explicit confirmation before simulating a new version; keep unsent text during generation and show the prior result. Real edit routing remains subject to design.
- Retain current confirmation, budget and metering behavior. Account credits are a later feature; no credit balance/purchase/deduction UI or implementation now. These choices amend Draft requirements but do not approve the complete feature or authorize paid calls.

## ADR-089 — 2026-11-14 — Isolated text-first concept before feature design

- User explicitly requested a mockup to continue research. Build a standalone local HTML concept in docs/project/mockups/text-first/, reusing current Figtree/warm-glass/amber visual language and existing Sony assets. This authorizes the mockup only; Draft requirements and subsequent design gates remain.
- Demonstrate optional product/inspiration attachment roles and compact reference/offer/style confirmation. Reuse a fixed historical scene, with an explicitly labelled layout-only price overlay; real generation still draws price into the raster. No app routing, API, provider, schema, paid call or deployment change. Keep all assets local and serve only the mockup directory on loopback.

## ADR-088 — 2026-11-14 — Text-first generation research scope (user choices; criteria still Draft)

- User chose a simple text box in the app first, automatic product-image lookup/reuse when no image is attached, and optional product-photo attachments. Attached photos take priority. Price remains drawn into the composition.
- Research recommends reusing the existing reference-based poster service and predefined styles, with a compact product/reference/price/style confirmation. This is a recommendation, not an approved design; no new provider, schema, model, paid call or integration is authorized here.
- Source selection remains open: Brave documents image search but its standard retention restrictions conflict with durable reference provenance/cache without a suitable agreement. Separate permitted image use from search access. Findings: reviews/text-first-generation-research-2026-11-14.md; proposed criteria: requirements/text-first-generation.md.

## ADR-087 — 2026-11-14 — Every tap answers at once; slow actions show a spinner and a top progress line (user report after the deploy; Claude under the autonomy grant)
- User, on his phone after the deploy: no feedback when tapping navigation, buttons and tabs; he tapped « Dupliquer » several times. He named Emil Kowalski's design-engineering approach.
- Checked first: the extra taps did not create extra copies (`perform` refuses while busy and every button is disabled), so this is feedback, not a data fault. The existing press rule scaled buttons by 2 % for 100 ms and never applied to the navigation links.
- Then, same day: "the saved version take time to load in the scene too". Measured: version thumbnails loaded the full 1.4–2.4 MB scene each, the editor's scene was re-encoded by the server on every request, and every `/api/` answer was `no-store`. Decided: content-addressed images (`/api/assets/{sha}`, `/api/thumbnails/{sha}`) become `private, max-age=31536000, immutable`, a change to the rule "shop data is never cached" for these immutable images only (JSON stays `no-store`; cost: images remain in the device's browser cache after sign-out, acceptable for a one-shop pilot); thumbnails for the strip; a lighter JPEG display copy for the editor's canvas, encoded once. Exports and the server's final preview are unchanged.
- Decided: a stronger press on every pressable (scale .97, 160 ms ease-out; colour only with reduced motion; iOS needs a touch listener for `:active`), a spinner in the element that started a slow action, and a thin top progress line after 300 ms of waiting on the server, not for background polling or autosave (R-POSTER-EDITOR-009, D-POSTER-EDITOR-007). No devil's advocate round: a small, frontend-only change answering a reported fault; the build gets a fresh code review.
- After the code review (same day): images made by code carry their encoder's version in the address (`v`, one constant per encoder: `rendering.CANVAS_IMAGE_VERSION`, `api.DISPLAY_VERSION`, `api.THUMBNAIL_VERSION`, mirrored in `frontend/src/api.ts`; the display copies live in `data/display/v<n>/`). Bump the constant when an encoder's output changes; an address at another version gets the current encoding and is not cached. Thumbnails grow to a 320×568 box (≥ 3× at 104 px in every format). With reduced motion the press is a background step, or a ring on the ink button and the picture tiles.

## ADR-086 — 2026-11-14 — Editor refinements: code-review fixes, footer logo restore, keyboard strip

- Independent code review found saved-profile opt-in and implicit seal defaults; remove both. Restore historical footer logo geometry via optional visual `logo_footer_box`, separate from strict corner reservations. Below 500 CSS px of visual viewport height, replace pinned preview with the existing fullscreen action so keyboard/landscape controls remain reachable. No paid or release authorization added.
- Editor verification follow-up: compact mobile generation badge shows its version number while assistive text says the previous version is preserved. Explicit `logo_disc: null` remains a missing-disc state and never falls back to footer placement. Browser smoke coverage completed in sections after a terminated combined run; final verification report distinguishes completed sections from a monolithic pass and records one transient renderer failure.
- User decision (2026-11-14), superseding the hidden preview above: below 500 px of visual viewport height and while a text field has the focus, the sticky poster shrinks to the ~96 px strip (D-POSTER-EDITOR-005 part A item 4) instead of disappearing; the 163 px poster at 360 × 740 and the folded « Versions (n) » row stay (T-EDITOR-REFINEMENTS-FIXES).

## ADR-085 — 2026-11-14 — Autonomous audit fixes with legacy composition compatibility

- User: “go for the fix autonomously, and test on live browser too”. Requirements and design editor-refinements.md passed independent Codex reviews with documented fixes before implementation. Reuse current document/plan/job JSON; no migration or dependency. Palette suggestions are local, visible and overridable; brand-in-title marker preserves refinement behaviour; original logo overlays use reserved corners and unchanged framing. Legacy seals require a fresh-composition copy to switch. Profile import fills missing values only. The compact preview supersedes the earlier 200 px minimum while retaining full-screen view.
- No paid test or shared-server change inferred. Build and browser-test everything before any release permission is needed. Existing model/rates/reserves unchanged; reservation wording corrected.

## ADR-084 — 2026-11-14 — Deployed-editor audit; corner placement means the boutique logo

- User requests: avoid brand/title duplication; fix clipped mobile versions and hard-to-reach controls; boutique identity off by default; make “Aux couleurs du produit” respect product colours; top-left/top-right logo placement. Explicit clarification: **the boutique's uploaded logo**, not the product brand. Price remains drawn in the composition.
- Scope this session: browser audit and recommendations only, with read-only live navigation and temporary stub-provider scenarios; no paid generation or product implementation. Findings: [ux-audit-2026-11-14.md](reviews/ux-audit-2026-11-14.md). Mobile visuals use the identical deployed frontend assets with isolated data because the Edge desktop tool cannot capture/resize its window. The proposed compact collapsible preview and visible tabs remain recommendations, not an approved design.

## ADR-081 — 2026-11-14 — While a poster is made, nothing else moves: no waiting sentence under disabled buttons, the poster keeps its size (T-WAIT-DEFORM; user report on the pilot; Claude)
- User: "When the generation animation is playing, the panel with the controls is deforming." Measured at six sizes (360 to 1920 px): the animations move nothing; the controls changed when a wait started and ended. « Une tâche est en cours : patientez quelques instants. » was added under each disabled button (bottom bar +26 px; on a wide screen the rail +28 px through its step bar; at 360 px the « Réglages » panel +20 px), and on a wide screen the poster shrank (374 × 468 to 270 × 338 at 1366 × 768) to fit the waiting block.
- Decided: during a scene or scene-adjustment wait, those reasons stay what they were before it (the waiting block and the pill over the poster say why); other job kinds keep the sentence. The wide-screen poster keeps its size: under it the block's state, time and rail are in view at 1366 × 768 and 1920 × 1080, its steps (and « Annuler la demande », which lasts only while queued) may need a scroll.
- Kept by design (D-POSTER-EDITOR-006): on one column the waiting block sits between the poster and the controls, so the controls move down by its height when it appears (the page goes to the top at that moment) and up when it ends (behind the review). Its height also drops by 56 px when « Annuler la demande » leaves at the start of creation. If the user still sees a jump on his phone, the next step is to keep the block's height constant or to take it out of the flow.

## ADR-080 — 2026-11-14 — Three poster formats, chosen in the Style step; a model in another shape asks first; each format has its own scene (user request; requirements and design passed by Claude under the autonomy grant)
- User: "when generating from a model, can we also use the same aspect ratio as the reference in the result? Ask the user first if want that. (Make the user choose aspect ratio)?" Requirements R-POSTER-FORMAT-001/002, design D-POSTER-FORMAT-001 v2 (designs/poster-format.md), after a fresh review (two P1 on the lock) and a devil's advocate.
- Decided: Publication 4:5, Carré 1:1, Story 9:16 only (the limit is ours: each format's layout is tuned by hand; the image model accepts more sizes). The format changes until the first version, then is fixed, with one button to remake the poster in another format. The question is asked only when the model is close to a format. One place to choose, the Style step (Claude's pick against a second picker at creation, after the devil's advocate: one decision fewer at the start; the user asked that the owner can choose, which this keeps).
- This replaces, for the pilot, D-FORMAT-EXPORT-001's reuse of one approved scene across formats: with the title, price and contact drawn in the image (ADR-044, ADR-055) a scene cannot be recropped. T-POSTER-009's square/story part is narrowed to this.
- Not known without paid scenes: whether the provider accepts 1152×2048, how gpt-image-2.5-flare composes Square and Story, the real cost of a Story scene. So Carré and Story stay hidden (`FORMATS_ENABLED`) until T-FMT-007, on the user's word.
- Answered by the user, 2026-11-14: the shop posts stories on Facebook and Instagram. The Story margins keep the 13 % default (Instagram's usual guidance from memory; Facebook's bottom zone may be deeper: unverified) and are tuned on real stories in T-FMT-007.
- Paid check approved by the user, 2026-11-14 ("Yes, run both"): one Carré and one Story scene locally with the real model once the build is done, about USD 0.10 in total at the Flare medium rate (reservation at most USD 0.80), shown to him before `FORMATS_ENABLED` is set for the pilot. This approval covers these two scenes only.

## ADR-083 — 2026-11-14 — Story names its covered zones; Carré and Story enabled for the pilot; typed words kept across a reload (user: "go ahead" on the three proposals)
- Claude proposed three things after the first paid check and the user answered "go ahead": one more paid Story scene with a firmer margin sentence, enabling the formats, and keeping the brand and subtitle across a reload.
- Story: the bands alone did not hold the model, so the prompt now names the top and bottom 13 % as covered by the application's interface (new scenes only). The second paid scene (USD 0.030) kept the footer at about 87 % and the disc was found. One sample: the owner's review stays the guard, and the 13 % itself is still Instagram's usual figure from memory, to be looked at on a real Facebook and Instagram story.
- Enabled: `FORMATS_ENABLED: feed,square,story` in `deploy/compose.yml`. Claude had proposed Carré first and Story once its footer was right; the second scene made it right, so both go. Total spent on the format check: USD 0.091 for three scenes.
- Words typed before the first version (brand, subtitle, accent word) are kept in the browser per poster (T-KEEP-WORDS), not in the saved document: the smallest change that survives a reload on the same device. They are still not carried to another device before the first version; saying it here so it is not taken for done.

## ADR-082 — 2026-11-14 — First paid Carré and Story scenes: both sizes accepted at about USD 0.03; the Story footer lands 5 % low (measured)
- On the user's go (ADR-080), one scene each with gpt-image-2.5-flare at medium through the real editor: Carré USD 0.031488 in 16 s, Story USD 0.029693 in 26 s. The provider accepts 1152×2048. The flat USD 0.40 reservation is safe for every format (design v2 point 11 settled).
- Carré is composed as asked. In Story the model drew the footer about 5 % lower than asked, so the contact enters the bottom zone the story interface covers, and the logo disc was out of the finder's reach.
- Decided by Claude: the disc finder looks up to 6 % higher or lower (free, proven on the two real images). The Story margin problem is not solved by this: it needs a stronger prompt sentence and one more paid Story scene, which waits for the user's word. The formats stay hidden on the pilot meanwhile.

## ADR-079 — 2026-11-14 — Codex's waiting experience goes into the real editor, frontend only (user request; requirements and design passed by Claude under the autonomy grant)
- The user asked to implement Codex's finding on the generation animation, previewed in its branch. Codex built it as a separate simulated page; its requirements and design were reviewed there. Claude adapts them to the real job (R-POSTER-EDITOR-008, D-POSTER-EDITOR-006) instead of merging the branch: the lab page stays a prototype in its worktree, and the editor uses the real job's state and timestamps.
- Not taken: the lab's scenario controls (simulation only), a separate page, any server change. Kept: no percentage or countdown, cancel only while queued, a lost connection as its own state, the long-wait sentence at 100 s, calm motion with a reduced-motion form.
- No devil's advocate round on this design: it restates a design already reviewed in Codex's worktree; the build gets a fresh code review.

## ADR-078 — 2026-11-14 — Trial of GPT Image 2.5 Flare at medium on the pilot; the application is named « Affiche Gen » (user)
- Asked whether to try GPT Image 2.5 Flare at medium on his next real posters (Codex's benchmark, ADR-077), the user wrote "No go for 3". Claude first read it as a refusal and recorded that; he corrected: "I meant let's try 2.5 flare". The trial is on.
- How: `deploy/compose.yml` sets `OPENAI_IMAGE_MODEL: gpt-image-2.5-flare` and `OPENAI_IMAGE_QUALITY: medium`. A scene's quality was fixed to "high" in `posters/visuals.py`; it now follows `OPENAI_IMAGE_QUALITY` and stays "high" when unset (T-FLARE-TRIAL). `gateway.py`'s rates for the model (5 / 8 / 30 USD per million tokens) equal the benchmark's rate card. The cost shown before a paid call stays the conservative estimate (`ESTIMATE_SCENE_USD`), so the owner sees "au plus" a figure above the real cost.
- It takes effect at his next deploy. He judges the posters; back to `gpt-image-2` / high by restoring the two lines. Each visual records its model and quality, so old and new can be told apart.
- "Replace the title with affiche gen": the wordmark, the page title and the manifest name are « Affiche Gen » (T-NAME).

## ADR-077 — 2026-11-13 — The mockup's look is the target, glass on every surface; the accent word must stay readable; the benchmark's model is a candidate only (user: "let's go with that for now", "go", "go full autonomous")
- The user reviewed the mockup through version 20 (https://claude.ai/artifact/6JoS82gMXkucaat4FKvUia) and said "let's go with that for now", then "go full autonomous". Claude reads this as: build T-PF-STRUCT then T-PF-LOOK to that mockup without further gates. Commit locally; push, deploy and paid calls stay his.
- The three choices left open in ADR-075 are taken from the mockup he approved: Figtree; bottom navigation on phones (Créer, Mes affiches, Styles); the theme follows the phone's setting, with the existing switch kept (Claude's pick: the mockup shows both themes and the light one first).
- Glass: this replaces "glass on floating chrome only" (ADR-072, ADR-073). He asked for "consistent glass on all the element, even the panel and card too". The backdrop is fixed light colour patches, never a blurred copy of the poster (a dark product blurs to grey). Claude said once that the design-taste skill bans glass on app screens and that blur costs on a cheap phone; the speed check on a low-end phone stays owed before release.
- From the mockup review, to carry into the app: one button reset that single-class rules can override; 44 px touch targets on phones; 52 px bottom-bar buttons; a short poster shadow.
- Codex's paid benchmark (worktree codex/generation-cost-ux, reviews/generation-benchmark-2026-11-13.md there): GPT Image 2.5 Flare at medium passed 3 of 3 at about USD 0.028 and 14 s, against USD 0.21 and 79 s for the pilot's gpt-image-2 at high. One sample per cell, judged unblinded by the agent: a candidate. The pilot's default is unchanged; a trial on real posters needs his word. `gateway.py` prices 2.5 Flare at GPT Image 2's rates: check against the benchmark's rate card before any switch.
- From the benchmark, done now (T-ACCENT-READABLE): a pale accent word on a pale backdrop came out unreadable at every quality, so the scene prompt now asks that the accent word stays as easy to read as the rest of the name (new scenes only). The price label entering the contact band was already covered by ADR-055's hard limit; the benchmark ran older stored prompts.

## ADR-075 — 2026-11-13 — Phone-first editor: structure reduced after review; the look waits for the user; release the current fixes first (Claude, under the autonomy grant)

- The user called the mockup "promising". Claude first read it as approval of everything in it and wrote R-POSTER-EDITOR-007, an amendment to 006 and D-POSTER-EDITOR-005 v1. A devil's advocate and a fresh reviewer (reviews/phone-first-design-r1-2026-11-13.md) changed that: "promising" is not his usual "go", and the default theme and the font were already said to be his (ADR-074).
- Structure (approved under the grant, built after the current fixes are released): during the steps, cut the chrome (one-row editor bar, no header in the editor on phones, tighter step panel) and keep the thumbnail with « Voir l'affiche ». Why: before the first version the draft poster shows only title and price; the accent word and colour, brand, subtitle and style are drawn later by the image model, so a large pinned draft would promise more than it shows (the mockup's live accent colour overstated this, and the user was told). Once a version exists, the real image stays on top and collapses to a strip while a text field has the focus; `interactive-widget=resizes-content` instead of tracking the visual viewport. The reviewer's P1s are designed out (D-POSTER-EDITOR-005 v2).
- Waiting for the user: the default theme (follow the phone, or keep dark), Figtree, the bottom navigation, and the release order. Recommended order: release the steps editor and the eight fixes now (the live pilot still refuses « 90.000 »), then the observed phone session, then the structure, then the look, so that each change can be judged on its own.
- Switches only for changes that act at once; the options for the next paid version stay checkboxes (a switch promises an immediate effect).

## ADR-076 — 2026-11-13 — The price pill and the shop badge are always in the foreground (user request)

- The user: "make sure that pill and badge is always at the first plan" (au premier plan). Claude's reading: the price pill and the shop's badge (the logo, round seal or not) are never covered, on the screen and in the downloaded file. He then added: "I am talking about the « Aperçu » pill too": the pills and badges laid over the poster on screen as well (the mockup's « Aperçu en direct » pill sat partly behind the poster). Rule: every pill or badge over the poster has an explicit stacking order in front of it, and the tools row and the bottom bar stay in front of anything that opens under them.
- Two places, both fixed. (1) The editor and the server renderer draw with the same component; they now draw every other layer first, then the badge, then the price, and use the layers' `z` only within those ranks. Before, a contact or shop name ticked after the logo, or any layer with a higher `z`, was drawn over it. The price wins over the badge if the two meet, so the amount stays readable. (2) The scene prompt asks the image model, for new scenes, to keep the drawn price label and the empty disc of the seal in the foreground with nothing overlapping them, not the product or its shadow. Refinements of stored scenes keep the prompt they were made with, as for the footer limit (ADR-055).
- Not proven: that the image model obeys the new sentence. It needs paid scenes, only with the user's go. Confirmed files already downloaded are immutable and unchanged; a new final preview of an older poster may differ where layers overlap.

## ADR-074 — 2026-11-13 — Second UI/UX round: prices read as owners write them; a phone-first editor proposed in a mockup, not built (Claude/Opus; user request)

- Prices: « 90.000 », « 90 000 Ar », « 90000ar » and stray spaces are now read as the integer they show (dot or space groups of three, one kind per number, an optional « Ar », « ariary » or « MGA »). The comma stays refused because it is the French decimal mark; « 1.5 », « 9.0000 » and mixed separators are refused. Why: the walk as a first-time user had five ordinary ways of typing a price refused, including the trailing space a phone keyboard adds; dots are common in Madagascar. The amount is shown back formatted at once, so a misreading would be visible. This reverses the earlier unit cases that refused « 12 Ar » and « 12 » with a leading space.
- Fixed without asking (no product decision): sticky hover on touch screens, the « Mes affiches » header at 360 px, native file controls replaced by French buttons, the review and final decisions fixed at the bottom on phones, the vendor's name removed from the owner's path, the first round's leftovers.
- Not built, waiting for the user: the phone-first structure (poster always in view, tools under it, bottom navigation) and the light, rounded look in the spirit of Android's Material 3 Expressive with Figtree. Why a mockup first: it changes the layout of every editing screen and the default theme, and the user steers by looking (HANDOFF). Mockup: https://claude.ai/artifact/6JoS82gMXkucaat4FKvUia. Review: reviews/ux-review-opus-2026-11-13.md.

## ADR-073 — 2026-11-13 — The owner's accent colour wins over a style's; glass stays restrained; the progress line says « Préparation » (Claude's picks, asked by the user: "What would be the direction you would pick", then "go")

- Accent colour: a style used to replace the colour picked two steps earlier and say so afterwards. Now a colour the owner picked himself stays when he chooses a style, and the style's colour is proposed with one button (« Utiliser la couleur du style »). When he never touched the colour, the style's applies as before. Because: an explicit choice is not overridden by a default.
- Glass: kept on floating chrome only (ADR-072). If the screens feel flat, add depth with the poster's shadow and the stage's contrast, not with blur on panels.
- Progress line: « Préparation → Génération → Fidélité → Téléchargement » names the poster's phases; « Étape n sur 4 » names what is being filled in. The earlier « Textes et style » made two step counters.

## ADR-072 — 2026-11-13 — Editor in steps and tabs, removal from the poster, glass on floating chrome only (user request; requirements and design passed by Claude under the autonomy grant)

- The user: "Run another improvement review … run another autonomous edit and search and test locally first. You can explore glassmorphism, or another styles. And you can make the image generation with multiple step with less control, instead of all control in one view, that will confuse user. Group similar control in the same panel, and add a possibility to remove a comp from an affiche view."
- R-POSTER-EDITOR-004 to 006 and D-POSTER-EDITOR-004 are written and approved by Claude. Deviation from the usual gate, on purpose: no design review before building. The user steers by looking and asked for a local result; the built editor gets a fresh review, and nothing is committed or deployed before he has seen it.
- Glass is limited to what floats (header, phone action bar, dialogs, notices). Why not everywhere: the owner's phone is a low-end Android, blur is costly there, and text over a changing backdrop cannot be held at 4.5:1. The poster stays the hero.
- "Remove" means leaving an element off the poster with undo, never erasing pixels of a generated image; title and price stay, because a poster always states the product and its price.

## ADR-071 — 2026-11-13 — Every refusal the owner can cause has its own sentence; a test reads the source to keep it so (Claude, after the user's remark on the hidden box)

- Context: the first poster on the live pilot failed on a box hidden in a closed section, with "Vérifiez les informations saisies.". Three audits had missed it. A scripted audit found 39 refusal codes of 75 without a sentence, and rules on the drawn title that no screen stated.
- Decision: the sentences live in one table (`MESSAGES`, api.py). A test collects every `Refused("code")` in the source and fails when a code has neither a sentence nor a place in a short list of codes that only a programming error can produce. Refusals caused by what the owner types get their own code and field. Rules that can be checked without a second copy of server logic (length, quote) are also said in the editor before the paid step; the word list is not copied into the editor.
- Because: a missing sentence is invisible in review and in a smoke that follows the happy path; only a check over the code finds it every time.
- Open: the word list (`promo`, `gratuit`, `%`, `ar`, `livr…`, `sold…`, `prix…`, `garanti…`) refuses some ordinary product names. Kept as it is; the user decides whether to loosen it.

## ADR-070 — 2026-11-13 — Maizina's files for Affiche IA: made in a local copy that was older than the box (user: "maizina project is cloned in the pc, make the necessary changes")

- The local `../maizina` has no `.git` and its `deploy/compose.yml` and `deploy/maizina.caddy` had neither the `ppn` network nor the `buy.miorantsoa.app` block. Both exist in the files that run on the box (read there on 2026-11-13; the box's compose file carries a mangled comment, so it looks edited by hand). A deploy from the local copy as it was would have taken PPN Market offline.
- Claude's choice: make the local files equal to the box's live files plus the Affiche IA parts (network `affiche_ia_edge`, site `affiches.miorantsoa.app`), rather than add only the Affiche IA parts to an old tree. Nothing else in Maizina was touched: no documents (its ADR and task numbers cannot be trusted in an old copy), no commit (not a repository), nothing on the box.
- The whole Caddy file was validated with the box's Caddy version in a throwaway container there (`docker run --rm --pull=never --network none`): "Valid configuration". No image was pulled and the running Caddy was not touched.
- `affiches.miorantsoa.app` is still Claude's proposal for the name.
- Later the same day the user initialised git in `../maizina` and added the remote. The working tree equalled the remote's `master` except for these two files and three missing dot-files; the local branch was attached to the remote's `master` without touching the files (`git reset` to it, dot-files restored), and the change was committed there with Maizina's own T-086 and ADR-051. The remote's `master` confirms that PPN Market's parts were never committed. Pushed on the user's "push" the same day.

## ADR-069 — 2026-11-13 — Hosted pilot phase B: round 2 fixes applied, built without Docker (Claude, under the autonomy grant)

- Round 2 on phase B: APPROVE WITH FIXES, five P1 (reviews/hosted-pilot-design-r2-2026-11-13.md). All applied as design v3.1, not reviewed again.
- Choices worth remembering: the session test of the access boundary is narrowed to `/api/` and nothing else is (Origin check and size limits stay on every path); the frontend is served by the application itself behind a boolean; at most two password verifications and one browser at a time, because the container has a hard 1 GB limit on a box without swap; the release stops the old container before it backs up and starts the new one (one SQLite writer), so each release has a short downtime; logs go to journald so that they survive a release.
- What could not be proven here: the development machine gives Claude no access to Docker, so the image was never built, and pyinfra never ran `deploy.py`. `docker compose config`, `sh -n` and `py_compile` pass; the shell text of the deploy parses. The first rollout is the proof, and `deploy/README.md` says so at its top.
- Not Claude's to do: the DNS record, the two changes in the Maizina repository and the Caddy recreate, the pilot's provider keys, the choice of an off-box backup, the commit, the push and the deploy itself.

## ADR-068 — 2026-11-13 — Phase B of the hosted pilot starts before the phone session (Claude, on the user's "next")

- ADR-065 put the server work after the owner's first session. Changed: the session waits on the user and the owner, the server exists and its deployment pattern is proven by PPN Market, and what the session can teach is about the editor, not about hosting. The session through the tunnel stays available and is still the fastest way to see the owner use the application.
- Phase B is detailed in designs/hosted-pilot.md v3: one more compose project on `mx1` in PPN Market's pattern. A fresh review runs before its container files are relied on.
- Limit on this machine: Claude cannot reach the Docker daemon (the user is not in the `docker` group), so the image build and a render inside the hardened container cannot be proven here.

## ADR-067 — 2026-11-13 — Budget for paid calls raised from USD 12 to USD 100 (user decision)

- The user, after seeing that about USD 1.94 was left: "You can update the limit to 100usd". Claude's reading: the whole development and test budget is now USD 100 (about 10.06 spent, about 89.94 left). The pilot's own cap on the server (USD 15 for the first month, ADR-064) is a separate default and is not changed by this.
- Applied on the Linux machine: `SPEND_CAP_USD=100` in `backend/.env`. The ledger does not contain the 5.277673 spent by the study scripts, so the two scripts that start the application on the real data (`outputs/style-study-2026-11-11/serve_local.py`, `deploy/phone_session.py`) cap the ledger at 94.72. The Windows machine's `.env` is not changed.
- A higher budget is not a standing go for paid calls: the user still confirms each paid action by Claude with its cost.

## ADR-066 — 2026-11-13 — The pilot's server is the Hetzner VPS the user already rents, shared with `ppn-market` (user fact)

- The user: "we already have a hetzner vps where ppn run". No server is rented; open question 1 of the hosted-pilot requirements is answered.
- What it changes in phase B: the machine is shared, so the application is one more site of the proxy already there (not necessarily Caddy), on its own Unix user, its own loopback port and with a memory limit on the service. Its facts (memory, disk, proxy, backup option) are not known on the development machine: `ppn-market` has no code or deployment notes here, and no SSH alias points to that server.
- Later the same day the user pointed to the `ppn-market` checkout. Its `deploy/README.md` and a read-only look at the box (`nproc`, `free`, `df`, `docker ps`, no sudo, nothing changed) give: Hetzner `mx1`, 2 vCPU, 3.8 GB with about 1.6 GB available and no swap, 13 GB free; Docker everywhere; Maizina's Caddy on 80/443; pyinfra deploys; backups on the box only. Phase B is therefore one more compose project in PPN Market's pattern, with two changes in the Maizina repository (edge network, site block) and a DNS record. This supersedes the previous point where it says the facts are unknown.
- What it does not change (Claude's choice): the owner's phone session through the tunnel stays first. It is ready today; even a small deployment beside another project needs a look at the server and a review first.

## ADR-065 — 2026-11-13 — Hosted pilot: the owner's phone session first, through a tunnel; design v2 approved (Claude, under the autonomy grant)

- Design v1 put six requirements of server work before the owner's first touch. The devil's advocate argued for one observed session through a temporary HTTPS tunnel to the administrator's machine first. Accepted: it is the audit's own reason for doing this feature at all (ADR-063). Phase A (built now): what any exposure to the internet needs, the long session, the home-screen icon, the tunnel script and the record. Phase B (server, Caddy, backups, deploy, status): designed in outline, started only after the session, with a fresh review.
- The session runs on the test data and its ledger (about USD 2.36 left), not on a new paid data folder.
- Changed after the review (reviews/hosted-pilot-design-r1-2026-11-13.md): no seed command (a style row needs the job that made it; profile and logo are typed once); a fixed 90-day session instead of 30 days sliding (no write on the read path); the copy outside the server is the provider's daily backup, not a pull by rsync from a laptop; forwarding headers are always trusted from loopback, with no setting to forget; the password is verified before the write transaction and IPv6 addresses are limited by /64.
- Requirements amended to match: R-HOSTED-PILOT-001 (French message when the application's process is down; the browser's page when the machine is), 002 (90 days), 003 (no "posters left" figure here; profile and logo by hand; the pilot's keys only on the server), 004 (provider's backup), 006 (session before the server).
- Running the tunnel exposes a paid-capable application to the internet and needs the owner: it stays the user's action.

## ADR-064 — 2026-11-13 — Autonomy grant: Claude passes the approval gates; hosted-pilot requirements approved with their defaults

- The user, asked to approve the hosted-pilot requirements: "so if you have autonomy, you don't have to ask me for approval". Claude's reading: on this project Claude approves requirements, designs and task splits itself, still runs the fresh review and the devil's advocate, records each gate here, and tells the user afterwards.
- Not covered by the grant, by Claude's own limit: paid provider calls (the user wants each one confirmed with its cost), renting a server or a domain, creating provider keys, commit and push, anything destructive on the paid data.
- Under it, R-HOSTED-PILOT-001 to 006 are approved with the seven working defaults: one small rented Linux server in the administrator's name; a sub-domain he owns; a separate pilot cap of USD 15 for the first month; the owner's Android phone with Chrome; one shared password on at most three phones; no test posters, but the profile, logo and saved styles carried over; the administrator observes the first session. Each default is the user's to change.
- `hosted-pilot` is added to PROJECT.md as a seventh feature.

## ADR-063 — 2026-11-13 — Order of work after the end-user audit: hosted pilot first (Claude's proposal; user: "go ahead")

- Asked what an end user would need most, Claude proposed five things in this order: (1) the application on the owner's phone (hosting, HTTPS, long session, home-screen icon, a real-phone session); (2) three inputs and one button, the rest from a shop kit set once; (3) the application reads the drawn texts back itself before the owner's review (live run 6: a scene with an invented line was approved by a person); (4) end with the phone's share sheet and a French caption, story format before square; (5) the owner's path without dollars, "version", "fidélité" or "scène".
- The user answered "go ahead". Claude's reading: start with (1) and draft its requirements; (2) to (5) each need their own requirements later. Why (1) first: until the owner makes a poster himself on mobile data, the other four are guesses.
- (1) is a seventh feature, `hosted-pilot`, outside the six of the approved split. Its requirements are a draft (requirements/hosted-pilot.md); PROJECT.md is changed only when the user approves them.
- Said once and not acted on: Claude would revisit the price drawn in the image (ADR-044), because each price change costs a scene. It stays the user's decision.

## ADR-062 — 2026-11-13 — Mockup gaps closed: accent word as chips, accent colour as swatches, the paid confirmation stays a dialog (user: "do as you recommend")

- The accent word is chosen among the title's own words (plus "Aucun"), no longer typed. Why: the server refuses a word that is not in the title (`headline_accent_not_in_title`); chips make that error unreachable. An accent that the title no longer contains is not sent.
- The accent colour is five preset swatches (blue, night blue, red, orange, gold) and "Autre…", which keeps the browser's own colour picker. The five colours are Claude's choice, not the shop's: the mockup had three and the user has not seen this list.
- The in-place paid confirmation of the mockup is dropped. Why: the dialog built for ADR-059 traps focus, makes the page behind inert and opens on "Annuler", so a held Enter key cannot pay; an in-place panel would lose that.

## ADR-061 — 2026-11-12 — Design D-CREATION-LIBRARY-003/004 approved at v2.1; "Confirmée" only while the file matches the poster (user decision)

- The user approved the design for managing posters and saved styles ("approved, go with your recommendation") after two review rounds and a devil's advocate (reviews/library-manage-design-r1-2026-11-12.md).
- His choice on the one open point: a row says "Confirmée" only while a confirmed file exists for the poster as it is now (a confirmation of the current revision). After a later edit the row falls back to "Approuvée" or "À vérifier" until he confirms again. This amends the wording of R-CREATION-LIBRARY-003 ("a confirmed file exists").
- Decisions of the design worth remembering: "Retirer de la liste" is the existing `abandoned` status plus a new restore route, with no schema change; a style is removed softly (`removed_at`, migration 0011) because old versions still read it; a poster made with a removed style keeps it for new versions; a style creation never fails on its name.

## ADR-060 — 2026-11-12 — Managing posters and saved styles: requirements approved with the working defaults (user decision)

- The user approved R-CREATION-LIBRARY-003 and 004 ("approved, go") without changing the five answers proposed as defaults: a poster of any state can be removed from the list (nothing is erased); no search yet; "Dupliquer" asks nothing; a style is still created from an open poster; a removed style is not recoverable.
- The two criteria that the defaults left out (search, creating a style from the "Styles" page) moved to "out of scope" in the requirement.
- Next gate: the design D-CREATION-LIBRARY-003/004, its review and the user's approval, before any task or code.

## ADR-059 — 2026-11-12 — Editor: hash routes, inert page behind a panel, confirmation for every paid or destructive tap (Claude's choices while fixing the guideline review; user request "fix all of them")

- The view lives in the address hash (`''` new poster, `affiches`, `styles`, or a poster id) and the navigation is plain links; one `hashchange` handler does the routing. A hash is enough for three views and needs no router dependency or server rewrite rule. A route change that fails (for example an invalid price that cannot be saved) puts the previous hash back.
- The three panels (paid confirmation, fidelity review, final check) stay ordinary elements with `role="dialog"`, a small focus directive and `inert` on the page behind. The native `<dialog>` was not used: it sits in the top layer, above the error message, which must stay visible and usable while a panel is open.
- Consequence: nothing behind an open panel can be edited any more (the browser test used to change the price behind the final check).
- "A paid call is never one tap" now holds for the scene refinement, the text proposal and the text material too; discarding unsaved work asks first. All use the existing confirmation sheet.
- Not changed, against the letter of the guidelines: colour transitions on controls, French sentence case, no list virtualisation (`content-visibility: auto` on the rows instead).

## ADR-058 — 2026-11-12 — Logo seal: two rules changed after the paid scenes (Claude's decision under the user's autonomy grant; to confirm)

- The approved design (ADR-057) accepted a disc only from 85 % of the asked diameter and printed the seal at the disc's size. The first paid scene through the application drew the disc exactly in place at 81 % (105 px for 130 asked): it was rejected and the logo removed. Across four real scenes the model drew 77 %, 79 %, 81 % and 107 % of the asked size.
- Changed: the disc is accepted from 60 % of the asked diameter, and the seal is printed at the size the user chose (12 % of the width, 130 px) centred on the disc, larger only if the disc is larger. The small-seal warning is dropped, since the seal is no longer small.
- Consequence to watch: the printed seal reaches about 14 px beyond a 102 px disc on every side. On the two paid scenes nothing was touched. The export guard (the logo covers the disc) is unchanged.
- Also changed: the seal is locked once the poster itself uses a version, not once the product has any version (a new poster of a known product lists that product's earlier versions); a version without a disc chosen on a seal poster unticks the logo.
- Second paid scene, with these rules, centred price on a dark backdrop: the application found the disc and placed the seal. The design and the requirement record the results.

## ADR-057 — 2026-11-12 — Logo as a round seal printed on an empty disc that the scene provides (user decision; R-CATALOGUE-BRAND-005 and D-CATALOGUE-BRAND-006 approved)

- Study with the user's logo (reviews/logo-study-2026-11-12.md, five paid scenes, USD 1.081501 outside the ledger). A logo drawn by the model composes well but redraws the striped ribbon, which carries the national colours. The real file added afterwards is exact but collides unless the scene left its place empty.
- Found in the study: the model draws an empty white disc where asked and composes the price and the contact around it; the program finds the disc and prints the real logo, cut to a circle, exactly on it. The model never draws and never receives the logo.
- User's choices: "add the logo in a round circle", then "smaller footprint", then the full logo at about 130 px in the footer between the price and the contact. The emblem-only crop was offered and not chosen.
- Approved at v2.1 after two review rounds (REWORK, then APPROVE WITH FIXES) and one devil's-advocate pass; the last fixes were not reviewed again.
- Limits accepted: the seal is offered only for one footer (logo and contact, no shop name, title, price and contact drawn), chosen before the first version and locked afterwards; the contact is then at the right; a centred price is untested; removing the logo from a seal poster needs a new version.
- Not adopted: a keyed-colour disc (untested; the white disc worked twice on real scenes), kept as the idea to try if white backdrops fail.
- Tasks: T-SEAL-001 (backend), T-SEAL-002 (editor and renderer), T-SEAL-003 (two paid scenes with the real logo in the shop profile).

## ADR-056 — 2026-11-12 — Design approved: contact drawn in the composition (D-CATALOGUE-BRAND-004 v3.1)

- The user approved v3.1 ("go") after review round 3 (APPROVE WITH FIXES, no P1; fixes applied, not reviewed again). The devil's-advocate pass of this design was done on v1 and is not repeated.
- Tasks: T-SIG-004 (backend prompt and request rules), T-SIG-005 (editor), T-SIG-006 (one paid scene, only with the user's go).

## ADR-055 — 2026-11-12 — The contact is drawn in the composition again; the rendered line is the fallback (user decision; reverses ADR-053's default; amends R-CATALOGUE-BRAND-003)

- Evidence: the first real poster made with the rendered contact (Soundcore Space One, scene `f3714e6b`, 2026-11-12). The prompt reserved 79–88 % of the height for the price and 91–95 % for the contact; the image model drew the pill at about 86–94 %, and the renderer wrote the contact on top of it. The user: "This is why having the contact not part of the comp [is] a bad idea".
- What was wrong in ADR-053 and design v2.1: both relied on "the scene keeps the band calm". Neither review tested that on a real scene. Claude recommended that approach.
- Decision: by default the image model draws the contact as one compact line with a telephone icon, at the left, centre or right of its region, so it composes it with the price. The rendered compact line built in T-SIG-001/002 stays as the fallback when the owner unticks drawing or the contact cannot be drawn.
- Accepted cost: a drawn digit is checked only by the owner's eye at the review, and a new position needs a new version (about USD 0.21).
- Kept from ADR-053: the shop name is unticked by default and never drawn in new scenes; the logo is the uploaded file as a layer; default position right with a logo, centre without; brand as plain text.
- Added: the price label gets a hard lower limit in the prompt whenever a contact or logo region lies below it.
- Open: the logo is still added after the scene, so the same collision can happen under it; the owner can drag the logo for free.

## ADR-054 — 2026-11-12 — Design approved: compact rendered contact, logo-only identity, brand as plain text

- The user approved D-CATALOGUE-BRAND-004 and 005 at v2.1 ("approved, commit and go") after two review rounds (REWORK on the drawn-contact v1, APPROVE WITH FIXES on v2) and one devil's-advocate pass. The round-2 fixes were applied and not reviewed again.
- Implementation is split into T-SIG-001 (layer icon and canvas), T-SIG-002 (editor) and T-SIG-003 (brand as plain text) in TODO.
- No paid call is needed for the contact. One optional scene would test "brand as plain text" and needs the user's go.

## ADR-053 — 2026-11-12 — The contact is written by the renderer, not drawn by the image model (user decision; supersedes ADR-043 for new scenes; amends R-CATALOGUE-BRAND-003)

- Trigger: design draft v1 drew a compact contact in the scene. Its review returned REWORK (layers are placed on the first scene only, no source for the line's width, a contradiction in the refusal rule), and the devil's advocate argued that drawing a phone number is the wrong tool: a wrong digit does silent harm, code cannot read pixels, and the review is one agreement since ADR-051. Review: reviews/signature-design-r1-2026-11-12.md.
- Decision by the user ("B, and yes to the two smaller points"): the contact is the existing text layer with a compact one-line style and a telephone icon, written by the shared renderer. Its position (left, centre, right) and its text change freely, with no new scene. New scenes no longer draw the shop name or the contact; the ADR-043 path stays for stored scenes.
- Also decided: without a logo the footer carries the contact only, and the shop name is unticked by default; the default position is right with a logo, centre without.
- Kept: the price stays drawn by the image model (ADR-044); the logo stays the uploaded file as a layer; the contact keeps its own band under the price; "brand as plain text" is the only brand fallback.
- Given up: contact lettering matched to the headline style.
- R-CATALOGUE-BRAND-003 is amended accordingly: the criterion "changing the contact or its position needs a new scene" is reversed.

## ADR-052 — 2026-11-12 — Requirements approved: discreet contact, logo-only shop identity, brand mark

- The user asked for a smaller but visible contact with a left, centre or right position, a shop identity carried by the logo alone, and asked about the product brand logo. Research: reviews/signature-research-2026-11-12.md. He approved R-CATALOGUE-BRAND-003 and 004 with "go with the new requirement".
- The logo stays the uploaded file placed by the renderer; the image model never draws it. This is Claude's reading of "logo only if the user wants it integrated in the scene", stated to the user before approval, and it keeps R-CATALOGUE-BRAND-002.
- Four open questions were not answered. Working defaults, chosen by Claude and to be confirmed at the design review: without a logo the shop name is still written; the contact defaults to the side opposite the price for a left-aligned look, centre otherwise; the contact keeps its own line under the price; "brand as plain text" is the only brand fallback.
- Next gate: a design, its review, and the user's approval before any task or code.

## ADR-051 — 2026-11-12 — One agreement per review screen instead of one checkbox per point (user decision; supersedes the nine-point review of ADR-050)

- Trigger: live run 6 produced a scene with an invented line ("POUR TOUTES VOS NOTES"). The live script ticked every box once a flag existed, and the user asked what the boxes are for, then asked for one validation with a summary of what to verify, on both screens.
- Decision: the fidelity review and the final screen each show a read-only list of the points to verify and one action: "Tout est conforme, approuver" and "Tout est conforme, confirmer". "Signaler un problème" sits beside the approval. The text group gains the line "Aucun autre texte que ceux ci-dessus", and the image point now reads "Aucun objet ni texte ajouté par l’IA".
- Layout warnings on the final screen are listed with the other points; the one confirmation acknowledges them. Their separate checkbox is removed.
- Backend unchanged: the one click sends every check the server requires (`fidelity_incomplete`, final `checks`, `acknowledged_warning_ids`). The stored record no longer distinguishes points ticked one by one from one agreement; nothing read that distinction.
- Requirements still met: the review covers shape, colour, branding, hardware, unwanted objects or text and integration (product-visuals), and fidelity approval stays separate from final confirmation (poster-editor).
- Open: nothing in the code detects text the image model adds beyond the typed texts; only the owner's reading does (T-SCENE-INVENTED-TEXT).

## ADR-050 — 2026-11-11 — Editor rebuilt to the audited mockup (supersedes ADR-048's layout and look)

- Process: an audit with the design-taste-frontend skill's app-screen rules (run on screenshots and the stylesheet; its inspector was not run because the app sits behind sign-in), then a mockup the user reviewed (https://claude.ai/artifact/8zwVrymwP1up1L12SUS422), then "go for all". The user added three points during the review: the review and final screens, the fact that several versions can be generated and one chosen, and a confirmation before every paid action.
- Look: the skill's dealt "true-black flat" app style (seed 1429845225) on a warm near-black ground. Elevation is a lightness step only; no gradients, glows or resting shadows. Chrome is neutral. The main action is white on black. One hue marks the chosen style and work in progress. Buttons: one 40px pill, three levels. One 16px outline icon set drawn inline. Type stays the bundled Noto Sans (the sheet dealt Inter; no new font was added).
- Navigation: a top bar with three destinations, "Créer", "Mes affiches" and "Styles", with counts. "Mes affiches" and "Styles" are new views; the poster list left the first screen. Styles are created from the editor only, because a style job is tied to a poster.
- Editor: a title row (poster name, save state, progress, undo/redo, the one main action whose label follows the state, and the reason when it is blocked); a rail with Textes, Style and Réglages avancés; a stage with the owner's photo beside the poster; a Versions column.
- Versions: "n sur 12", the chosen one labelled "Choisie pour l’export", each with its state, and a "Nouvelle version" tile. Said before the first scene exists.
- Paid actions (first scene, new version, style from a poster) open one confirmation that says what happens and the estimated cost, or that the demonstration mode spends nothing.
- Fidelity review: three groups. The product (four checks), the image (two checks), and one check per kind of text the image model drew, each showing the typed words: title and subtitle, price, shop and contact. Backend: `TEXT_CHECKS`; `decide` refuses `fidelity_incomplete` when a drawn text is not ticked. Scenes without drawn text still need the six checks only.
- Final screen: facts strip, the four existing checks with a counter, then after confirmation the download, "Nouvelle affiche" and "Changer le prix" (returns to the price field and explains that a new version is needed).
- Verified: 690 backend tests; 26 Vitest; build; browser smoke in bundled Chromium and Edge 156. Not verified: a live paid run after the rebuild, a real phone, a contrast audit with a tool.

## ADR-049 — 2026-11-11 — Usability pass after the owner's first real session

- User report: two ways to import a reference; a new user does not know what to do; he added a photo, title, price and a reference, chose the Claude composition, and a button stayed grey with nothing on screen saying why.
- What the database shows for that session: three `plan` jobs with `kind='plan'` failed with `invalid_plan` (Claude's composition did not pass validation; USD 0.048572 in total). The editor's only message was a generic line at the top of the page, out of view, and in that mode the Generate button exists only after a valid plan. The Claude composition had never been run against the real model.
- Decisions:
  - The editor no longer offers the Claude composition. The simple composition with looks is the only path; the API route and code stay. Fixing the planner is a separate task (T-PLANNER-CLAUDE-INVALID).
  - One way to use a reference poster: "Créer un style depuis une affiche". "S’inspirer d’une affiche" (a second image passed to the image model) is removed from the editor; the API still accepts `style_reference_asset`. The study had measured little gain from it.
  - Every blocked main button states its reason beneath it (draft, generate, save style, final preview). A style name is optional (default "Style N").
  - A coach line above the stage always says the next action.
  - Errors and notices are fixed on screen (errors at the bottom, notices under the header) with a "Fermer" button; the fidelity check and the final preview open in front of the page instead of below it.
- Verified: 26 Vitest, build, browser smoke in Edge 156 (it now asserts the coach line, the reasons and the absence of the removed controls), and by eye in Chrome on the production build with the data-probe data. Not verified: the review sheets by eye in Chrome, a real phone.

## ADR-048 — 2026-11-11 — Interface designed as an image-generation tool (supersedes ADR-047's look)

- User feedback on ADR-047: the hard-shadow "printer's proof" look is an overused template; then: "think like if you were designing a UI for an image generation AI tool".
- Decision: keep ADR-047's three numbered steps and wording, replace its visual language and layout with the conventions of image-generation tools.
  - The result is the hero: a dark, neutral stage in the middle; the generated poster is the only bright thing on the page.
  - Controls are a compact rail on the left (01 Textes, 02 Style et génération, 03 Vérifier et télécharger). On a phone the stage comes first and the rail follows.
  - Generations are a filmstrip under the stage ("Versions de la scène"), no longer a list inside the rail.
  - While a scene is generated the stage itself shows it (a light sweep and a "Génération en cours…" chip), in addition to the rail status.
  - Style presets are a three-column wall of real result thumbnails with a check on the selected one.
  - One warm "safelight" orange is reserved for Generate and Export; no purple, no gradients on surfaces.
  - A light variant (header button "Thème clair", remembered on the device) exists for bright daylight.
- No font or dependency added; no logic change besides the theme toggle and the stage class.
- Verified with the stub browser smoke in Edge 156 after the last change (screenshots in outputs/editor-smoke/). Not verified: bundled Chromium after this restyle, the light variant in a browser, a real phone, a contrast audit, the live paid flow.

## ADR-047 — 2026-11-11 — Interface direction: printer's proof, three numbered steps

- User request: a modern, usable interface for the shop owner, any direction allowed except the default AI template; use the ui-ux-pro-max skill.
- The skill's generated system (pink brutalism with a scroll-storytelling landing pattern) fits a marketing page, not a working tool; its accessibility, touch and form rules were kept, its palette and pattern were not. A web search for professional poster-tool references returned only general 2026 trend articles (the editor recedes behind the content; warmer, less glossy surfaces), no Dribbble or Behance examples: the direction below is a design judgement, not a copy of a reference.
- Direction: "épreuve d'imprimeur". Warm paper background with a dot grid, ink-black frames and hard offset shadows, one vermilion signal colour reserved for the action that moves the poster forward, gold for hover/focus and work in progress, crop marks around the poster. Display type is the already bundled Montserrat Black Italic, text is Noto Sans: no new font, no network.
- Flow: the sidebar is three numbered cards with an anchor rail: 01 Textes (title, price, brand, subtitle, accent word, shop identity, one closed disclosure for what the AI draws), 02 Style et scène (looks as a contact sheet with always-readable names, create a look, generate), 03 Vérifier et télécharger (export, with layer-level editing under "Réglages avancés"). Nothing was removed; every label kept its wording.
- Fixed on the way: look names were white on white; the header button wrapped on phones.
- Verified with the stub browser smoke in bundled Chromium and Edge 156 (screenshots in outputs/editor-smoke/: intake.png, studio-start.png, desktop.png, mobile.png). Not verified: a real phone, a contrast audit with a tool, the live paid flow after the restyle.
- Revisit if: the owner finds three cards on one scrolling column slower than separate screens.

## ADR-046 — 2026-11-11 — Saved looks written by Claude from a reference poster

- User request after the exploration ("go"), with one requirement: the look is saved beside the others and reusable for later posters. The user's go replaced the separate requirements/design files for this feature; this entry and backend/api/README.md hold the contract.
- Flow: the owner uploads a poster he likes (existing `style` asset role) and names it. Claude returns a `StyleBrief` (French direction and surface, lighting, camera, palette, accent colour, English headline typography, left/centre alignment). It is stored in `looks` (migration 0010) and shown in the picker with the reference as its thumbnail.
- Trust boundary: the brief is validated and screened like any art direction (no prices, currency, long numbers, instruction wording, quotes), once when Claude answers and again before it is stored. A scene request names a look by `headline.look_id`; the server reads typography and alignment from the shop's own stored look. The client cannot send typography text. An unknown or foreign look is 404, never a silent fallback.
- Prompt: `compile_scene` takes `headline_style` and `align`. Left alignment moves the headline and the price label to the left edge; the shop signature stays centred.
- Queue: a brief runs as a planner job (`kind='plan'` with a `look` payload) because job kinds are fixed by applied migration 0006; `get_job` reports it as `look`, after the browser smoke showed the editor loading it as a plan. It uses the planner budget estimate and the same spend cap. At most 24 looks per shop; no delete yet.
- Measured in the live application (Edge, real Claude and image providers): the Select 4 Go poster became the look "Vagues bleues"; a CMF Buds 2a poster made with it has the left-aligned headline, the left price pill, the blue waves and the blue accent word, with every text exact. Brief USD 0.008612; scene USD 0.210283.
- Revisit if: owners need to rename or delete looks, or briefs start carrying words from the reference.

## ADR-045 — 2026-11-11 — Twelve scenes per poster

- User request: raise the scene limit so price changes are not blocked (ADR-044 made each price change a new scene).
- Decision: `jobs.SCENE_LIMIT = 12` scene/refinement jobs per creation (was 3, hard-coded). Failed jobs still do not count. The spend cap remains the money guard; the limit only stops a runaway loop on one poster. The French message now says twelve and points to a copy.
- The phase-1 evaluation limit (`ATTEMPT_LIMIT`, runs table, 1–5) is a different mechanism and is unchanged.
- Revisit if: owners reach twelve in ordinary use.

## ADR-044 — 2026-11-11 — Price drawn by the image model (explicit user decision)

- Status: explicit user choice: "make the price part of the comp, so if the user want to change it later, he need to re-gen again". Reason given: an overlaid price is visually inconsistent with the rest of the composition.
- Decision: `Headline.price` (default on in the editor) lets the image model draw the price label. The amount is `offer.price_ar`, an integer formatted in code as "340 000" + "AR"; no free text can carry an amount (brand/subtitle/direction screening is unchanged). The job payload records `price_ar`.
- This supersedes, for posters that use the option: ADR-042's "the price is never sent", and the project rule "reuse approved visuals for price-only changes" (AGENTS.md updated). A price change now costs one new scene (about USD 0.21) and a new fidelity review. Turning the option off restores the exact editable pill and free price changes.
- Guard: the drawn amount must equal the offer's amount whether or not the price layer is shown; a hidden price layer needs a drawn price. Otherwise render/confirm refuse 409 `price_stale` and refinement refuses `headline_stale`. `Document` no longer requires a visible price layer; export does that check with the scene.
- Measured: 2 of 2 live application scenes drew "340 000 AR" exactly, and with the pill in the composition the model kept the product clear of it without help. Two images are a small sample: the fidelity review must read every digit.
- Found by the live Edge run, not by the unit tests: the first-scene code skipped hiding a price layer that already carried pill styling, which would have doubled the price. Fixed; the regression test now styles the pill first.
- Open: a creation still allows three scene/refinement jobs in total (`attempt_limit`), so repeated price changes on one poster will need a copy. Not changed here.

## ADR-043 — 2026-11-11 — Shop name and contact drawn by the image model

- Context: the user found the overlaid shop name/contact poorly integrated and asked whether the AI could compose them too. Measured first: 3 of 3 direct study images and 2 of 2 live application scenes rendered "Original Phone Mada" and "038 93 028 00 / 034 93 028 00" with every digit correct, in the poster's colours with a handset icon. One of the five wrote the shop name in capitals.
- Decision: `Headline.signature` (default on in the editor) lets the image model draw the shop name and/or contact that the poster includes. The words come only from the poster's profile snapshot, never from the request. One line each, at most 80 characters, no quotes; otherwise they stay editable layers. The price is still never sent.
- Guard, also tightened for the title: any word the image model drew must still equal what the poster says, whether or not the layer is shown again, and a hidden layer must be replaced by drawn words. Otherwise render/confirm refuse `title_missing` / `signature_missing` and refinement refuses `headline_stale`. Unticking a contact that the image shows is refused the same way. `Document` now allows an included shop name/contact layer to be hidden.
- Layout: with an AI-drawn signature the editor gives the plan the real two-line footprint (48 and 56 px) instead of the default layer boxes; the prompt states the product's lowest edge as a hard limit above the price label. Live run 3 against run 2: the pill went from covering the lower ear cup to touching only its bottom rim.
- No migration or dependency. Earlier payloads without `signature` replay unchanged.
- Revisit if: a wrong digit is ever seen at the fidelity review (then default the option off), or the shop wants a multi-line contact.

## ADR-042 — 2026-11-11 — Integrated headline, house-style scene prompt and style looks

- Context: the user gave autonomy to change the process so that generated posters reach the level of Original Phone Mada's own recent posters, with a 5–10 product test. Ten shop posters were inspected (reviews/style-study-2026-11-11.md). Their common language: product filling most of the frame at a three-quarter hero angle, calm gradient with large curved bands tinted to the product, brand + heavy two-tone product name + spaced subtitle, dark price pill. Their 1254²/1086×1358 sizes suggest (hypothesis, unconfirmed) that they are AI-generated whole.
- Measured: a text-free plate with the new prompt fixes scale and backdrop, but an overlaid single-font title still looks plain. When GPT Image 2 also sets the headline, 11 of 11 images rendered every word verbatim (French accents included; six were read on reduced contact sheets only) and matched the references' typography.
- Decision: the image model may set **brand, product name and subtitle** in the scene ("integrated headline"), default on in the editor. The **price never enters the prompt** and stays an exact editable layer, so price-only changes still reuse the approved visual. The product name is always taken from `offer.title`, never from the plan or the planner. This partly supersedes ADR-030 (all text as separate layers) for the title only; the layer remains available by turning the option off.
- Guards: brand/subtitle/accent word are screened (currency, promotion, instruction wording, quotes, line breaks; digits allowed because model names contain them; "réduction de bruit" is exempt from the promotion blocklist). The job payload records the exact title sent. The title layer may be hidden only when the selected scene's recorded headline title equals the current offer title: otherwise render/confirm refuse `title_missing`, and a refinement refuses `headline_stale`. The fidelity review remains the check on spelling.
- Prompt: rewritten in the provider-recommended order (use, references, scene, subject, light, layout, constraints) with a house style that the shop's art direction can override. Subject scale is stated against the plan's product area; quiet zones are stated as full-width bands. An example of components ("both earbuds…") was removed after it made the model add earbuds to a speaker: the prompt now says to show only what the photos show.
- Style choice: three measured looks (Studio clair, Aux couleurs du produit, Luxe sombre) plus free text, picked from thumbnails, with one accent colour. A look sets the French art direction and the plan palette; no schema change.
- No migration, no dependency. `headline` is omitted from request/payload when absent, so earlier idempotency keys and hashes replay unchanged. Old plans recompile with the new prompt on their next scene request only.
- Study spend was made by direct provider calls outside the application ledger (USD 3.05, outputs/style-study-2026-11-11/spend.json): treat the remaining budget as cap − ledger − 3.05.
- Revisit if: a headline is misspelt in real use more than rarely, or the shop needs to edit a title without a new scene.

## ADR-041 — 2026-11-10 — Editable reference typography and price capsule

- User's “font and price format too” extends the evaluation under approved R-POSTER-EDITOR-003 and supersedes ADR-040's font/capsule limitation. Register unmodified OFL Montserrat Black Italic (900), a close match rather than an asserted identification of the reference font. Keep Noto files unchanged.
- Add optional `price_badge` to price only: white fill, two blue border colours, thin rounded outline, exact grouped amount and smaller upright Noto Sans AR. Both runs and capsule remain one selectable/undoable layer. No arbitrary shape nodes, duplicate monetary content, font upload or rich-text engine.
- Upstream Montserrat Black Italic lacks narrow NBSP U+202F. Its price/capsule grouping uses the supported NBSP U+00A0; Noto plain-price formatting is unchanged. Verify French glyphs, real 900/italic metadata and hashes, never synthesize a font or fall back silently. Canvas clipping checks include measured italic ink beyond the advance box.
- Reach: model/Claude patch validation, font manifest/loader, shared geometry/material renderer, properties UI, export font fingerprints, API contract, tests and real poster. Omit null badge from canonical data to preserve old hashes/replays. Fingerprint the extra currency font. No migration/dependency; retain earlier PNGs and confirm a new revision without another image call.

## ADR-040 — 2026-11-10 — Reference-guided white studio evaluation

- User supplied the November 5 DJI Mic Mini poster; preserve the exact attachment and use it only as the last style reference. Reuse the exact black R50i original and dated 90,000 Ar fixture in a separate creation, existing paid ledger and cap. The DJI product, logo and 600,000 Ar price must not carry over.
- Translate the inspected reference into a white/very-light-grey curved studio, floating product hero and soft contact shadow; use a manually revised plan with matching palette and centred editable blue title/black price. Keep Original Phone Mada and contact as separate selected text layers. Use existing composition API/renderer only; no new schema, fonts or shape nodes for this evaluation. The current font set cannot reproduce the reference's italic mixed-colour title or outlined price capsule exactly; report that limit instead of flattening commercial text into the scene.
- Verify both references and prompt roles before paid dispatch; inspect generated product fidelity, polish the saved layout, inspect authoritative PNG and confirm/download exact bytes. Preserve the previous dark poster and its runner state. Record live cost from the same ledger.

## ADR-039 — 2026-11-10 — Connect the approved style-reference path

- Scene/refinement requests accept an optional owned `style_reference_asset` SHA-256 uploaded with role `style`. Validate ownership, role and bytes before reservation and again before dispatch; append it after original views (and base, for refinement). The reference supplies appearance only, never product identity, lettering, claims or prices.
- Reuse immutable job JSON for the reference hash and return it with visual provenance; no schema migration or new provider transport. Keep original-photo comparison separate. Omitted/null style fields retain old idempotency hashes so existing uncertain requests remain replayable.
- Scope: scene/refinement contracts and admission, worker preparation, visual provenance, editor upload/reuse, domain/HTTP/browser regressions, and the requested paid style evaluation. Existing exports, prices and confirmed PNGs are unchanged. The live evaluation requires an actual inspected poster; inaccessible mirror images are not evidence of its style.

> Append-only log, newest first. Record context, decision, rationale, alternatives, and conditions for reconsideration. Reversals get a new entry. A confirmed constraint does not approve a design or library choice.

## ADR-038 — 2026-11-10 — Authoritative local PNG export

- Render the saved feed document with the existing PosterCanvas in a pinned headless Chromium process. Serve only trusted bundled files through intercepted virtual HTTPS routes; inject validated assets/fonts as data, block every other request and close the context on failure. No local unauthenticated asset server, model call or provider credential is involved.
- Preserve alpha/EXIF/colour using a shared bounded sRGB preparation function for editor and server sources. Record original/prepared hashes, font manifest and renderer build. A stored successful PNG is the confirmation/download authority; new edits require a matching preview and cannot replace old confirmed bytes.
- This completes the requested feed poster first. Square/story/library enhancements and optional cutout remain their own queued tasks; real product validation follows the feed export, not an expanded template catalogue.

## ADR-037 — 2026-11-10 — Isolated prompted typography

- Implement approved D-POSTER-EDITOR-003 using the existing job ledger and retry-free Claude transport; no second queue or arbitrary JSON Patch API. Store immutable proposal/effect provenance in a new migration, and apply only a selected title/price layer after checking the originating revision.
- Exact text always comes from bundled fonts. A proposed title must occur in explicit quotes in the instruction; a price must match a single explicit literal Ariary amount. Content changes require separate acknowledgement. Reject other target roles or unrepresentable changes; manual controls remain usable.
- The installed Konva Text renderer uses CanvasPattern directly in CanvasRenderingContext2D.fillText. Reuse this native glyph mask rather than maintaining a second custom offscreen lettering renderer; the exact font glyphs, layer outline/shadow and pixel-isolation contract remain the same. Verify changed pixels with actual Chromium renders.
- GPT generates a text-free material swatch only after an explicit action. Clip it locally to exact font glyphs in the shared canvas. This supplies editable metallic/patterned typography without trusting generated price spelling or re-rendering the scene. Reconsider surface-embedded effects only after separate approved requirements.

## ADR-036 — 2026-11-10 — Editor presentation and shared canvas

- The approved French shop workflow remains the scope. Desktop: poster canvas beside a properties/layers column; mobile: canvas above contextual controls. Intake and scene review use ordinary labelled forms. The poster is the visual focus; no decorative metrics/cards, fake product handles or HTML poster templates.
- Compact palette: workspace #F1F5F9, panel #FFFFFF, ink #17324D, action #186C80, divider #D6E2EA, error #A43139. Noto Sans for interface and default poster text; Noto Serif is the approved alternate poster font. Poster colours are editable independently of application chrome.
- Sketch: desktop [toolbar above canvas | selected-layer controls]; mobile [toolbar / canvas / selected-layer controls]. Align forms and reading text left; use clear spacing instead of repetitive card shells. This follows the subject's image-editing task, not a marketing landing-page layout.
- Frontend-design skill reviewed against the approved brief before code. Use one shared Vue/Konva renderer, a small serial autosave state helper and native accessible controls; no state-management/UI-kit dependency unless actual complexity requires it.
- Node 22.14 and npm.cmd 10.9.2 are available. npm.ps1 is blocked by PowerShell policy; using the shipped .cmd entry point avoids changing system policy. Official Vite and Konva Vue/Transformer docs checked.
- Pinned Vue 3.5.45, Konva 10.9.1/vue-konva 4.0.1, Vite 8.3.7/plugin-vue 6.0.10, TypeScript 5.9.3/vue-tsc 3.3.14 and Vitest 5.1.0 after checking engines/peers. npm install reports zero vulnerabilities. FontTools 4.68.0 builds a checked glyph/hash manifest; Playwright 1.64.1 supplies the browser verification and approved later renderer, with its pinned headless Chromium. No system execution-policy changes.
- Four unmodified Noto static fonts are bundled from the upstream noto-fonts archive with OFL licence. Manifest generation checks French/narrow-space glyphs and 400/700 weights. Browser font loading checks SHA-256 and reports missing glyphs, avoiding silent substitution.
- Browser testing found an upload race immediately after sign-in; inputs now stay disabled while intake/profile loading finishes. Uncertain mutations retain their key; unchanged scene plans retain their ID so retrying a lost scene response returns the admitted job instead of spending again. The Chromium smoke deliberately drops that response and proves only one scene job exists.
- Conflict recovery explicitly offers saving local edits into a copy or discarding them and loading the current server version. It never reloads the stale object originally opened. Job polling ignores responses for a different opened creation; completed planner jobs can be recovered after reload.
- Desktop canvas fits available height; phone controls retain page scrolling unless object movement is enabled. Native crop/position sliders and keyboard movement complement drag. The simulated browser test covers undo, reopen, conflict copy, long-text and unsupported-glyph warnings; this is not physical-device validation.

## ADR-035 — 2026-11-10 — Scene integration and real-draft composition fixes

- T-005 adds forward-only migration 0007 for immutable plans and reviewable visuals, uses original images directly, and keeps generated-image access scoped through owned visual records. Pending/rejected visuals remain editable drafts; final approval/export checks belong to the renderer task.
- The fixed planner now allocates footer/title/price regions from the current layer boxes rather than hardcoded small rectangles. This fixes actual initial-draft widths and contact/logo heights; a layout that leaves insufficient product space is refused explicitly. Bundled-font measurement and layout polish remain T-006.
- Scene completion selects only the first candidate when the originating revision is still current and has no scene. Refinements remain alternatives, retain the selected base, and identify base/original roles separately. Generic draft saves validate same-input visual ownership and a crop bounded by the image with the target format's aspect ratio.
- Workers use admitted model/rate snapshots, immutable original hashes and a local spool. Two provider slots run inside the API owner process; scheduler errors are recorded/logged without exposing raw provider data or replaying uncertain calls.
- The public Soundcore R50i fixture is a product set (earbuds and case), so the scene compiler explicitly preserves visible components while refusing duplicate products or invented extras. No model may invent the commercial offer.
- Focused integration verification: 80 plan/visual tests passed, including all eight branding combinations, late-result preservation, approved-base/rejected-refinement history, manual plan rebase, ownership/crop refusal, no-call price-only edits and actual HTTP scene/review flow. Full regression subsequently passed: 625 passed, 3 deselected (138.83 s). No paid calls yet.

## ADR-034 — 2026-11-10 — Scene planner implementation and durable queue boundary

- T-POSTER-003 uses the installed httpx2 transport directly for retry-free Claude Messages requests; strict schema and semantic validation remain local. Only the verified Sonnet model/rate card is accepted. Unexpected model or billed cache categories retain the conservative reservation rather than assigning an invented price.
- Fixed plans reserve measured field space without receiving commercial values. Image prompts use only validated scene fields, identity references and geometry; display summaries cannot inject image instructions. Base scene and style references have separate image roles. Compiler revalidates mutable model objects before use.
- Verification: full backend suite 579 passed, 3 deselected; final revalidation addition then passed all 62 planner tests. No live Claude/image calls.
- Queue implementation reuses shared mutation transactions and extends spent_micros to both ledgers. Feature-specific input/reference validation stays in the same admission transaction. Dispatch is recorded before sending, and durable local results are finalised without another paid request.
- T-004 verified: full suite 607 passed, 3 deselected (124.68 s). Migration 0006, reservation/replay/concurrency, cancellation races, slots, terminal allowance, 429-only retry, ambiguous failure, disk/commit failures and local spool recovery are tested. No paid database migration or live call.
- A contract check also made PNG output explicit in both existing OpenAI request paths; requested dimensions and omission of input_fidelity remain unchanged.

## ADR-033 — 2026-11-10 — Usable shop-poster test and scene-planning boundary

- User explicitly requested continued implementation until a JBL or Soundcore test produces a usable Facebook/Instagram poster, using Original Phone Madagascar found through their Edge session, and authorised reasonable implementation defaults. This authorises a bounded real test within the existing configured global cap; preserve the existing paid ledger and record every new call. It does not authorise posting, messaging, deployment or invented commercial facts.
- Edge's logged-in Facebook shortcuts identify Original Phone Mada at https://www.facebook.com/MiaryAndrian10/. Navigation is currently unverified: input reported missing geometry and capture/recovery failed with "window capture timed out: timed out waiting on channel". Stop UI input; public search can supply corroborating public facts while implementation continues.
- Scene plans use strict local validation; Claude's wire JSON schema removes unsupported numeric/string/array bounds and describes them instead. Local validation remains authoritative. Official structured-output docs document these limits: https://platform.claude.com/docs/en/build-with-claude/structured-outputs. The fixed builder is explicitly labelled and never presented as a Claude response.
- Extend the existing image gateway with an explicit size while preserving the legacy default; original-photo identity references and a refinement's selected base have separate compiled roles.

## ADR-032 — 2026-11-09 — First poster implementation slice

- Domain persistence uses strict Pydantic documents and existing SQLAlchemy BEGIN IMMEDIATE transactions; canonical request+revision hashes preserve lost-response replays before stale-version guards. Migration 0004 adds only the input/profile/draft tables needed now, leaving evaluation tables and cost records intact.
- Original uploads are decoded/colour-validated without rembg and stored unchanged. Asset writes verify existing bytes and recover only from a concurrent destination that contains the expected bytes.
- Until the scene/effect tasks supply owned reviewable records, draft saves explicitly reject generated references. Font IDs are validated now; bundling and measured layout remain the renderer task. No silent placeholder image or font substitution.
- Verification: full backend suite 513 passed, 3 deselected; actual local Uvicorn HTTP session smoke passed. Tests cover auth/Origin/private assets, schema/money boundaries, original-byte preservation, all eight identity choices, revision/replay/concurrency and rollback. Postman status remains unsupported by the installed WindowsApps executable; verification uses local pytest/ASGI and actual HTTP, without a cloud workspace.
- HTTP implementation follows the approved opaque cookie session (not JWT), Argon2 via pwdlib, exact Origin checks and persisted failed-login counters. API-only settings must not break existing CLI startup. Official FastAPI guidance checked: https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/ and https://fastapi.tiangolo.com/tutorial/request-files/; installed signatures remain the implementation check.

## ADR-031 — 2026-11-09 — Poster technical designs approved

- User: "approve", responding to the six-file design approval packet and explicit implementation gate.
- Decision: approve ADR-029's architecture and all six phase-2 designs, including the separate editable typography/effect approach in ADR-030. Proceed with independently verifiable implementation tasks in TODO, preserving the phase-1 evaluation tools and ledger.
- First slice: immutable product inputs, shop snapshots, strict document/price validation and atomic versioned drafts; then the authenticated HTTP boundary. Reuse existing SQLAlchemy transactions and content-addressed files. No deployment, commit or new paid provider call is implied.

## ADR-030 — 2026-11-09 — Prompt-assisted text with separate editable effects

- User requested title/price typography controllable through prompts as well as manual editing, with changes confined to the selected element. In the clarification they chose "Separate text/effect layers first (Recommended)" over text embedded into scene surfaces.
- Requirement decision: keep the clean product scene, exact title/price values and independently editable text/effect layers. Both manual controls and prompt proposals can target a selected text element; preserve other layers, version history and explicit review. No whole-poster regeneration for a text-only polish. Surface-embedded lettering is deferred.
- Added approved R-POSTER-EDITOR-003 from this explicit request/choice. Implementation mechanics remain Draft design: Claude proposes a validated selected-layer patch; the renderer draws exact fonts/glyphs; optional GPT Image texture is clipped to that layer's glyph mask. Image-generated glyphs cannot guarantee exact spelling/font or remain ordinary editable text, so they are not the source of authoritative letters/prices in this first version.
- Limit: changing a text layer changes its occupied pixels; underlying scene/other-layer content remains untouched. A prompt alone does not guarantee pixel preservation. Approval of this requirement does not approve the pending technical designs or extra paid tests.

## ADR-029 — 2026-11-09 — Proposed phase-2 architecture (design approval pending)

- Status: Proposed, not implementation approval. Covers the requirements approved in ADR-028.
- Use one FastAPI process, the existing SQLite/asset store, a durable local job queue and a Vite/Vue editor. Add phase-2 tables with forward-only migrations; retain phase-1 evaluation data and rules. Both call ledgers count toward the same budget transaction.
- Use Konva + vue-konva with a versioned application document, rather than serialising library nodes. One shared Vue canvas component renders interactive drafts and read-only headless Chromium previews. Store the server-rendered PNG before user confirmation; confirmation freezes its bytes and download never regenerates it. Fabric and native SVG remain evaluated alternatives, not additional implementations.
- Reuse GPT Image edits and the existing adapter, extending its explicit size argument rather than creating another image client. Initial comparison baseline remains gpt-image-2/high; original images and selected base scene have explicit separate roles. No cutout dependency on this path.
- Claude Messages receives image references and produces a validated ScenePlanV1. Proposed evaluation model: claude-sonnet-5-5, configurable with recorded rates/model metadata; access/quality/cost are untested. Fixed-prompt fallback is explicit. Authoritative title/price/contact/logo never come from either model.
- Evidence checked: installed OpenAI SDK accepts image sequences and size; official OpenAI guide documents gpt-image-2 custom sizes and omission of input_fidelity; official Claude docs document structured outputs and current model ID; Konva documents Vue bindings, application-state persistence and export; Playwright documents Python Chromium support. Links and discovery limitations are recorded in the design files.
- Orbit discovery/integration was used for both providers. Its OpenAI collection is incomplete/outdated (single-file/mask example, no concrete response); installed SDK and official provider documentation take precedence. No provider calls, credentials or product images were sent during discovery.
- Revisit: multiple shops/processes, measured queue contention, renderer fidelity failures, or comparative product-fidelity results. These are reasons to change the design, not infrastructure to add now.

## ADR-028 — 2026-11-09 — Poster requirements approved

- User: "go aheadt with the requirement", responding to the explicit approval request for requirements/_INDEX.md and its six files.
- Decision: Approve the 13 new requirements: catalogue-brand 001–002, generation-jobs 001–002, product-visuals 009–011, poster-editor 001–002, format-export 001–002, creation-library 001–002. Earlier product-visuals 001–008 remain the phase-1 baseline; the approved amendments govern normal poster drafts.
- Next authorised work: matching technical designs, including a complete feed-format slice and extension to square/story. The representative-photo evaluation remains a release-quality gate, not a reason to delay these newly authorised designs. No new paid calls or implementation are implied by design work; design approval remains the next explicit project gate.

## ADR-027 — 2026-11-09 — Accepted review direction and corrective work

- User: "go ahead with the recommendations and any fix from your tests", then explicitly favoured GPT Image recreation/integration over forcing a cutout into a scene.
- Decision: GPT Image receives original product references and generates the integrated scene as the primary product flow. Cutout is optional and must never gate that flow. Product fidelity still requires review; do not promise exact pixels from a generative model.
- Authorised now: repair the two reproduced implementation gaps under existing R-PV-003/007 and D-PV-002/008, with regression tests. New poster/editor/planner/refinement criteria are drafted under the existing six-feature split; the explicit requirements/design gates still apply to their implementation.
- Snapshot repair: add ordered original asset hashes with forward-only migration 0003; keep the existing CSV hash. Legacy NULL means unverified, never a hash inferred from current files. Refuse `generate` for an unverified existing product; existing stored candidates remain readable/reviewable through `sheet`/`apply`. Do not rewrite historical evidence or reset a spend ledger to bypass this guard.
- Screening repair: the shared admission boundary checks the resolved description before spend; idempotent replay stays first. CSV validation remains for aggregate diagnostics.
- No new paid calls, commit or push are needed for these fixes. Existing JBL/Soundcore outputs remain pending review.

## ADR-026 — 2026-11-09 — User-authorised real-product scene smoke test

- Status: Explicitly requested by the user during T-REVIEW-001.
- Decision: Source one JBL and one Soundcore product image from official public pages and generate one scene for each through the existing backend, within the configured spending cap. Record source URLs and original hashes, inspect the results and report actual usage. No automatic creative revisions or model comparison.
- Rationale: The user asked for real-product evidence instead of relying on the synthetic phone probe. These manufacturer images are a two-product smoke test, not the representative shop-photo evaluation T-PV-013.
- Scope: This authorises the two scene requests and their existing bounded transport-retry behaviour. It does not approve a redesigned editor, Claude integration, or publishing the images as shop advertisements.
- Result: Two first-call successes, USD 0.344220 combined usage cost; existing `data-probe` ledger reused (USD 0.512881 including prior probe). Scenes look promising; Soundcore cutout retained external award artwork. Evidence in `reviews/real-product-scenes-2026-11-09.md`; no approval decisions applied.

## ADR-025 — 2026-11-09 — Review the whole poster workflow before resuming implementation

- Status: Review scope requested by the user; product recommendations remain unapproved.
- Context: The user requested a review of all implemented changes and reconsideration of photo/title/price generation, polishing, optional shop identity and Claude scene prompts, without treating existing choices as fixed.
- Decision: Complete T-REVIEW-001 instead of automatically resuming T-PV-011. Assess committed and pending work, verify offline behaviour and existing probe evidence, and record proposals in `reviews/implementation-review-2026-11-09.md`. No application changes, paid calls, commits or design approvals are implied.
- Rationale: The phase-1 evaluation backend is not the requested complete poster workflow. Refinement, movable shadows and poster/campaign state need explicit requirements decisions before implementation.
- Next gate: Agree the reviewed direction, then draft/amend the relevant per-feature requirements; obtain requirements and matching design approvals before coding the new flow.

## ADR-024 — 2026-11-06 — `sheet`, `apply` and `new-cycle` choices (T-PV-010)

- Status: Implementation decisions inside D-PV-008. Codex r1–r3 reviewed them (r3 APPROVE).
- Decision:
  1. **`decisions.csv`:**
     - UTF-8 with BOM, `;`-separated;
     - columns `target_id;kind;action;reasons;note;framing;info`, where `info` is read-only for the operator and ignored by `apply`;
     - `reasons` are comma-separated codes, and `framing=ok` is required to approve;
     - `sheet` refuses to overwrite an existing `decisions.csv`.
  2. **What the sheet lists:**
     - **every** pending candidate and proposed cutout, whatever the scope's state (an abandoned scope's pending candidate can still be approved, ADR-020);
     - generation suggestions (revisable rejected tips, confirmed cutouts) and abandon rows only for open scopes;
     - rejected scenes at the attempt limit are not offered for revision.
  3. **Reading the file in `apply`:** the whole file is decoded strictly before parsing. A BOM means UTF-8; without one, UTF-8 is tried, then cp1252 (Excel's "CSV (point-virgule)" on a French Windows). It never uses replacement characters, and a malformed file is exit 2.
  4. **Validation:** two passes over the whole file, nothing applied on any error.
     - In-file transitions are simulated, and a matching replay passes before `next_status`.
     - Cutout transitions have their own check.
     - Abandon is refused while any request runs in the scope.
     - A column an action doesn't read is refused.
  5. **Execution and results:**
     - per-row error boundaries: an unexpected error gives the row `error:<Type>`, the other rows continue, admitted requests still execute, the results are written, and the exit is 1;
     - the CSV result comes from the request's **persisted** outcome (`applied` / `request_failed:<stored kind>`), never from a printing error;
     - the results are `applied | already_applied | refused:<code> | request_failed:<kind> | not_started | error:<exception>`, where `not_started` is a generation row skipped after `budget_exhausted`.
  6. **Generation ids:** `uuid5(target:action:k)`, where `k` is the first id that does not exist or is not `failed`/`interrupted`. A replay never spends twice, and a failure gets a new attempt.
  7. **Commands:** `apply` needs `--paid` with openai, like `generate`. `new-cycle` exits 1 if any SKU is refused.
- Revisit if: Excel saves in another encoding (e.g. UTF-16 "Unicode text"), or the operator needs to edit an existing `decisions.csv` across sheet runs.

## ADR-023 — 2026-11-06 — Probe result: gpt-image-2 returns usage; a high scene costs about USD 0.17 (T-PV-012)

- Status: Measured on 2026-11-06 with one paid call (user's go), in `DATA_DIR=data-probe`.
- **Facts:**
  - **gpt-image-2 returns `usage`**, despite the SDK docstring "For gpt-image-1 only" (ADR-015). Each call's cost is therefore usage-based (`cost_is_estimate = 0`), and the cap counts **real** token costs, not only estimates.
  - **One scene at `high`, 1088×1920, 1 input photo:**
    - input 1271 tokens (text 169, image 1102), output 5300;
    - cost = 169×5 + 1102×8 + 5300×30 µUSD = **168 661 µUSD (USD 0.169)**, recomputed exactly;
    - the call took 55.1 s;
    - the output is exactly 1088×1920, so the strict-size validation holds.
  - **The result on the made example phone:**
    - the camera layout, colour and diagonal panel are kept;
    - no text was added;
    - the product is about 41 % of the height and inside the safe square;
    - the corner radius is slightly reduced.

    This says nothing yet about real logos and fine markings (T-PV-013).
  - **Billing check:** the user's OpenAI usage dashboard (screenshot, 2026-11-06) shows **November spend $0.17, 1 request**, matching the recorded 168 661 µUSD. So the app's usage-based ledger matches the bill (D-PV-003 cap, item (d)). The dashboard's "Total tokens" shows 1,271, i.e. the input tokens only; the output tokens are billed (they make up most of the $0.17) but are not counted in that tile.
- **Consequences:**
  1. **The estimates are conservative:** `ESTIMATE_SCENE_USD` 0.40 ≈ 2.4× the real cost. The floor would be ceil(1.25 × 168 661) = 210 827 µUSD, so the reservation stays at 0.40. They are kept: reservations only affect admission headroom, and costs are recorded from usage. Lowering the scene estimate to 0.25 is optional.
  2. **The background cost is not measured yet:** `images.generate` has no input photo. It is expected near the scene cost (output-dominated); measure it in the first evaluation run.
  3. **The evaluation budget is revised down:**
     - 20 × (3 scenes × 0.17 + 1 background × ~0.16) ≈ **USD 13.4** at limit 3;
     - about **USD 20** at limit 5 (ADR-011);
     - add retries and extra backgrounds: **a cap of USD 25–30** is enough (down from the USD 30–46 in D-PV-008).
  4. **The probe's spend is in the `data-probe` ledger, not `data-openai`.** The OpenAI project limit (blocks) is global.
- Revisit if: OpenAI pricing changes, or a quality, size or multi-photo input changes the token counts materially.

## ADR-022 — 2026-11-06 — CLI `generate` and fixtures choices (T-PV-009)

- Status: Implementation decisions inside D-PV-008. Codex r1 and r2 reviewed them.
- Decision:
  1. **`--paid` is required whenever `IMAGE_PROVIDER=openai`, and refused with the stub.** It is checked before `runtime.start`, so a refused command creates nothing. Any CLI command that can spend must take it (`apply` in T-PV-010).
  2. **Exit codes:**
     - 0: done, including request outcomes recorded in the DB (refused, quota, timeout, a failed `no_product` cutout);
     - 1: configuration or startup refused, an unexpected error in the batch, `cutout_unavailable`, or a refusal outside the four scope-state codes; the other products still finish;
     - 2: usage or validation errors, nothing written;
     - 3: budget exhausted (takes precedence).
  3. **Photos** are `|`-separated names under `--photos DIR` (default `<csv dir>/photos`). The committed examples (2 made images) are in `fixtures/examples/`, because `fixtures/photos/` is git-ignored.
  4. **The CSV** is parsed strictly (`csv.reader(strict=True)`), so a broken quote can't swallow other products. Every row is validated, and compared with the run snapshot, even with `--only`.
  5. **The row sha** covers all 10 raw fields: any change, even to `notes`, refuses a later `generate` on that run.
  6. **Qualities:** low/medium/high, plus xhigh/max for `gpt-image-2.5-*` only (SDK docstring). `auto` is refused, because a run must name what it measures.
  7. **The printed `committed $X / cap $Y`** includes the reservations of calls still running.
  8. **Cutouts** run in a thread under `Semaphore(1)` while the scene calls wait. A failed (`no_product`) cutout doesn't block a new one on a re-run.
- Seen once, not reproduced: an onnxruntime "bad allocation" during a cutout. It was contained per product, and a re-run made the cutout. If it recurs, try `OMP_NUM_THREADS=4`.
- Revisit if: the evaluation needs `--only` without validating the other rows, or memory becomes an issue (all photos are held in memory).

## ADR-021 — 2026-11-06 — Paid probe inputs (T-PV-012)

- Status: User answers (2026-11-06). The user put the key and the cap in `backend/.env` themselves.
- Decision:
  1. **Key:** an OpenAI project key (`sk-proj-…`; format checked without printing it), only in `backend/.env` (git-ignored).
  2. **Cap:** `SPEND_CAP_USD=12`, `SPEND_CAP_SINCE=2026-11-06`. That covers the probe and the 5-product calibration (about USD 7.50 at the base estimates), not the full 20-product evaluation (about USD 30–46): raise the cap before T-PV-013.
  3. **Model and quality:** `gpt-image-2`, `high`. Product fidelity (logos, camera layout) is the main risk; the probe measures the real cost of this exact pair.
  4. **The dedicated project's OpenAI budget limit blocks requests** (user-checked). This is a second hard stop under the app's estimated-spend cap.
  5. **Paid mode is switched on only by the probe command line** (`IMAGE_PROVIDER=openai DATA_DIR=data-openai …`). `.env` leaves `IMAGE_PROVIDER` empty (default stub), so development commands cannot spend. Paid data lives in its own `data-openai` folder (the provider-mode guard refuses mixing).
- Revisit if: the probe shows `usage` missing (then estimates decide the cap) or a per-call cost far from the USD 0.40 estimate (adjust `ESTIMATE_SCENE_USD`).

## ADR-020 — 2026-11-06 — Review, cycle and abandon interpretations (T-PV-008)

- Status: Implementation decisions inside D-PV-004/005/006/007. Codex r1 and r2 judged them acceptable.
- Decision:
  1. **Every write is a conditional update** (`WHERE status = <from>`) returning `applied`; a replay with the same canonical payload returns `already_applied`; anything else gives `invalid_transition`. Input checks run first, so a replay with an invalid payload gets its validation code.
  2. **Rejection:** the reasons are stored deduplicated in `REASON_CODES` order; a note-only rejection stores `"[]"`; the note is stripped and screened with `find_commercial_terms`.
  3. **Cutout confirm/reject** (D-PV-006 step 2) are in this task, because no other task owned them.
  4. **Abandon is refused while any request of the scope runs**, whatever its purpose (design line 357; my first instruction limited it to the treatment's purpose, which Codex caught). The replay is checked first, so a replay after `new-cycle` still addresses the original scope. Cycle numbers below 1 are refused.
  5. **Approving a candidate that was pending when its scope was abandoned is allowed** (the design is silent). Abandon only stops new generation, and the report's precedence `approved > abandoned` resolves the outcome.
  6. **`new_cycle` has no replay token:** a second call refuses (`cycle_not_approved`), because the new cycle has no approval yet.
- For T-PV-010 (`apply`):
  - its whole-file validation must recognise matching replays before `next_status`;
  - it needs its own cutout-transition check;
  - it must validate `kind` before `abandon`, where an unknown treatment raises `KeyError`.
- Revisit if: the operator abandons with pending candidates often, and approvals after an abandon confuse the report.

## ADR-019 — 2026-11-06 — Request execution choices (T-PV-007)

- Status: Implementation decisions inside D-PV-003 and D-PV-006. Codex r1 APPROVE.
- Decision:
  1. **`execute` is async and takes the semaphore** (`asyncio.Semaphore(2)`), created **per event loop** by the caller and shared by all requests of that loop. DB, file and image work run synchronously on the loop. The phase-2 API should move them to a thread.
  2. **Inputs are prepared before any spend:** the input images and, for a background, the cutout are loaded and the `provider_input` copies made before call 1. A missing file fails as `storage` with no call.
  3. **Costs of failed calls:** a `storage` or unexpected failure **after** a successful call keeps the usage-based cost, because the call was billed. Before or without usage, the reservation stays.
  4. **An unexpected exception** marks the call and the request `failed` with `invalid_request` (type and message in `error_detail`), then re-raises. A cancellation is not caught; owner recovery marks the request `interrupted`.
  5. **The `SQLITE_BUSY` handling** (design line 249) covers the call-2 transaction only.
  6. **File extensions come from `assets.extension(mime)`** (the subtype, e.g. `.jpeg`). Every writer must use it.
  7. **The cutout row format that T-PV-009 must write:** `bbox_json = json.dumps([x, y, w, h])`, and `cutout_asset` set when the cutout is made.
- Revisit if: the phase-2 API needs concurrency beyond one event loop, or busy errors appear outside the retry transaction.

## ADR-018 — 2026-11-06 — Request admission: the subject in `run_products` (schema amendment) and rule interpretations (T-PV-006)

- Status:
  - Item 1 amends the approved D-PV-001 schema: the user chose it ("Save name in run") after Codex r1 found the gap;
  - items 2–6 are implementation interpretations of D-PV-003/005; Codex r1 judged them correct or reasonable.
  - No further design review round, because the change is small and recorded here.
- Decision:
  1. **Migration 0002** adds `run_products.name` and `run_products.variant`, written at `generate` like the arm:
     - `NOT NULL DEFAULT ''` with `CHECK (trim(x) <> '')`, so a value is required;
     - SQLite 3.47 checks it on ADD COLUMN, and fails on a table that already has rows.

     Admission reads the subject (and the arm) from `run_products` for every purpose. Why: `apply decisions.csv` runs without the fixture CSV, so a background request could not get the product's name. Alternatives were `apply --fixtures` (one more argument on every apply), or copying from the first scene request (fragile).
  2. **`request_scene` takes `variant_photos`** (the variant's photos, from the CSV loaded by `generate`) for the membership check and the default first 3 photos. There is no variants table in phase 1.
  3. **"The latest fallback candidate" is `ORDER BY attempt_no DESC`**, not by time, so a clock change cannot pick the wrong one.
  4. **A stale target is checked first:** a parent or cutout from another cycle or run gives `wrong_scope` before the scope rules, so the message names the real problem.
  5. **Design line 242 ("else 409 `review_pending`"):** `review_pending` is returned only when the latest fallback candidate is pending; an approved one gives `not_rejected`. `use_revision` cannot occur for backgrounds: a later background is always a linked revision.
  6. **The idempotency payload** holds the caller's fields as given and excludes `owner`.
  7. **Codes the design did not name:**
     - 409 `wrong_scope`, `cutout_not_confirmed`;
     - 422 `unknown_run`, `variant_not_in_run`, `unknown_target`, `unknown_asset`.

     A model without `RATES` gives `ValueError` before any row is written.
- For T-PV-007: `reserve()` only checks. Call 2 must be inserted in the same `write_tx`, with a budget refusal caught inside it to mark the request `failed` (`budget_exhausted`).
- Revisit if: phase 2 adds a variants table (then the catalogue moves to the DB).

## ADR-017 — 2026-11-06 — Startup, lock and asset store choices (T-PV-005)

- Status: Implementation decisions inside D-PV-001.
- Decision:
  1. **`runtime.start(settings, owner)` is the only startup entry** (CLI now, API later): OS lock → engine → migrate → provider-mode guard → owner-scoped recovery. A failure at any step after the lock disposes the engine and releases the lock.
  2. **`acquire_lock` retries a held lock for up to 2 s.** Measured on the user's PC: Windows releases a dead process's `msvcrt.locking` lock up to about 12 ms after the process ends (6 of 30 runs). Microsoft's `LockFile` docs say the delay "depends upon available system resources". Without the retry, back-to-back CLI commands would sometimes refuse.
  3. **`recover` marks every running call of the owner's requests** (not only those of running requests), so the two updates are order-independent. The reserved cost is kept.
  4. **Assets:** the file is written first (temp file in the same folder → fsync → `os.replace`), and the `assets` row is recorded in the caller's transaction (`ON CONFLICT DO NOTHING`, first kind wins). There is no GC, and the folder is not fsynced (Windows cannot).
  5. Times are stored as `db.utc_now()`: ISO 8601 UTC with microseconds, so text order is time order.
- Known gap: on Windows, if the API and the CLI `put` identical new bytes at the same moment, `os.replace` can raise `PermissionError` (it propagates). Handle this before the API and the CLI run at the same time (phase 2).
- Revisit if: a supervisor restarts the API within 2 s and needs a longer wait, or several API processes are needed (PostgreSQL).

## ADR-016 — 2026-11-06 — Cutout model and pipeline choices (T-PV-004)

- Status: Implementation decisions inside D-PV-006. The model is checked against the installed rembg 2.0.87.
- Decision:
  1. **Model `birefnet-general-lite`** (`REMBG_MODEL` default), 224 MB, downloaded once to `%USERPROFILE%\.rembg\models\birefnet-general-lite\`. Chosen from the installed list as a general-purpose model with sharp edges, about 4× smaller than `birefnet-general`. Not `bria-rmbg` (rembg's default): its licence needs a paid agreement for commercial use. Remote models (`withoutbg`, `atlascloud`) are refused, because they send the photo out and charge outside the cap.
  2. **Speed on the user's PC** (i5-1235U, CPU): 20–36 s per mask, plus about 22 s for the first session. `OMP_NUM_THREADS=4` measured about 35 % faster; it is not set in code.
  3. **The cutout keeps the source pixels and their ICC profile (RGB sources only), and no EXIF.** It is not converted to sRGB, unlike provider inputs (ADR-015), because R-006 requires the product pixels unchanged.
  4. **Hole filling and labelling use numpy + `scipy.ndimage`**, declared directly. A background region that touches the image border is never filled, even when small.
  5. **Real-model tests are opt-in** (`-m rembg`, about 2 minutes); the default suite uses injected masks.
- Licence (checked 2026-11-06, not a legal review): the BiRefNet code and the BiRefNet_lite weights are labelled **MIT** by the author (GitHub repository, Hugging Face card). rembg says weights carry their own licences. Two things are **unverified**: whether the rembg-hosted `BiRefNet-general-bb_swin_v1_tiny-epoch_232.onnx` is the same checkpoint, and the training-data terms. Confirm both before production use.
- Revisit if: the evaluation shows poor masks (try `birefnet-general`, slower), the CPU time is too long for the phone flow (try `isnet-general-use`, untested), or the licence check fails.

## ADR-015 — 2026-11-06 — Provider gateway: SDK facts and deviations from the design (T-PV-003)

- Status: Verified on the installed SDK and OpenAI docs (read 2026-11-06); implementation decisions inside D-PV-003.
- **Versions:** openai 3.46.0 (its HTTP client is **httpx2** 2.16.0, not httpx; declared directly because the gateway and tests import it), pillow 13.0.0.
- **SDK facts (installed source):**
  - `images.edit` takes a list of images, sent as `image[]` multipart parts in order;
  - `size` is a free string, and its docstring allows any WxH in multiples of 16 for gpt-image-2/2.5, so 1088×1920 is valid;
  - the `input_fidelity` docstring says to omit it for gpt-image-2; `response_format` is unsupported for GPT image models;
  - `APITimeoutError` subclasses `APIConnectionError`.
- **`usage` may be missing for gpt-image-2:** the SDK docstring says "For gpt-image-1 only". Without it, every call's cost stays at the reserved estimate. T-PV-012 checks this.
- **Deviations from the design:**
  1. **Model ids:** there is no bare `gpt-image-2.5`. `RATES` has `gpt-image-2`, `gpt-image-2.5-sunburst` and `gpt-image-2.5-flare` at $5 / $8 / $30 per 1M text-input / image-input / image-output tokens. A model without rates is refused before any call. T-PV-006/009 must check the run's model against `RATES` before they reserve budget.
  2. **Error codes** (OpenAI error-codes and image-generation guides):
     - the ordinary 429 rate limit has **no code** (`rate_limit_exceeded` is undocumented), so every 429 that is not about quota is `rate_limited` and retryable;
     - quota is `insufficient_quota` (documented as an error type; also accepted as a code) or one of the 429 codes `credit_balance_exhausted`, `project_spend_limit_exceeded`, `organization_spend_limit_exceeded`, `organization_usage_limit_exceeded`;
     - refused is code `moderation_blocked`, or type `image_generation_user_error`, whatever the status (none is documented).
  3. **`retryable` follows from the kind** (`rate_limited`, `provider_error`), so the stub and the real adapter cannot disagree. The adapter never retries; T-PV-007 does the one retry.
- **Additions (Codex r1–r2):**
  - **API key:** it must be printable ASCII with no whitespace. A pasted invisible character would otherwise make the HTTP library print the whole key.
  - **Errors:** `error_detail` redacts `sk-…` and is truncated to 500 characters. No SDK exception travels as a cause or context.
  - **Usage:** only allowlisted integer counts are kept. Usage is used for the cost only when it is consistent: `output_tokens > 0`, the total equals input + output, and the split is ≤ input. Otherwise the estimate stays.
  - **Provider input:**
    - an ICC profile is converted to sRGB, keeping gray as gray, before the profile is removed;
    - alpha is flattened onto white after the colour conversion;
    - a PNG declaring non-sRGB gamma or primaries with no ICC or sRGB chunk is refused ("re-export as sRGB").
- Revisit if: T-PV-012 shows `usage` is returned (calibrate the estimates) or never returned (estimates only), or OpenAI documents new error codes.

## ADR-014 — 2026-11-06 — Prompt and screen interpretations (T-PV-002)

- Status: Implementation decisions inside D-PV-002. Codex r1 agreed with them.
- Decision:
  1. **Background `texte` sentence:** a rejected background for the "text added outside the product" reason gets "Remove all text, numbers, logos and watermarks." The design names only `integration` and `extra` for backgrounds. Text in a background is exactly the `texte` case. `coloris, logo, cameras, boutons, forme, cadrage` add nothing to a background prompt.
  2. **Number rule of the screen:** "any number with ≥ 4 digits (spaces, dots and commas ignored)" means ≥ 4 digits where two digits are separated by nothing, one dot or comma, or a run of spaces, but not a mix (`\d(?:(?:[.,]|\s+)?\d){3,}`). So `49,99`, `1 200 000` and `1  200  000` are blocked, but `iPhone 15, 128 Go` is not.
  3. **Wording added to the design's blocks:** a "Rules (they override everything below)" header; instruction 1 also covers further product photos; the mood line appears only for the default or a chosen mood.
- Because: the blocklist is best effort (ADR-011). Its false positives cost one rephrase, while its false negatives are caught by rule 2 and the review checklist.
- Known false positives: two numbers separated only by a space (`Galaxy S24 128 Go`), a 4-digit year, `5000 mAh`.
- Consequence for T-PV-007/008: `corrections_applied` must mean "a correction line was added to the prompt", not "the operator gave reasons". Codes that are ignored for a background leave the prompt unchanged.
- Revisit if: the evaluation shows the screen blocks real descriptions often, or text appears in backgrounds despite the sentence.

## ADR-013 — 2026-11-06 — Backend scaffold choices (T-PV-001)

- Status: Implementation decisions inside the approved design (D-PV-001, Cross-cutting).
- Decision:
  1. **Settings:** pydantic-settings (pydantic comes with FastAPI in phase 2). `backend/.env` is found from the module path, not the current folder. `SPEND_CAP_USD` and `SPEND_CAP_SINCE` have no default. Estimates default to 0.40 / 0.30 USD (design D-PV-008). `load_settings()` raises `ConfigError` with the printed message only. Reason: a pydantic `ValidationError` keeps the raw inputs, the API key included, in `.errors()` and `.json()` even with `hide_input_in_errors`.
  2. **No ORM models:** the schema is plain SQL in migration 0001, copied from the design. Later code uses `text()` queries.
  3. **Transactions:** the SQLAlchemy 2.1 recipe "Using SQLAlchemy to emit BEGIN in lieu of SQLite's transaction control". pysqlite's `isolation_level` is set to `None`, and a `begin` event emits `BEGIN IMMEDIATE` when the engine option `affiche_write_tx` is set (`write_tx()`). Python 3.12's `autocommit=False` was not used: with it, sqlite3 always sends a deferred `BEGIN`, so `BEGIN IMMEDIATE` cannot be sent. **Never pass `isolation_level` to this engine:** the dialect then turns pysqlite's implicit BEGIN back on.
  4. **Migrations run only through `affiche.db.migrate(engine)`**, which applies the pragmas and `BEGIN IMMEDIATE`. `alembic upgrade` from the command line refuses to run. `alembic revision -m` still creates new migration files; `--autogenerate` is not available, because there is no ORM metadata.
- Versions locked on 2026-11-06: sqlalchemy 2.1.8, alembic 1.20.1, pydantic 2.14.3, pydantic-settings 2.16.2, pytest 9.2.0; build backend uv_build 0.11.
- Revisit if: a second database engine is added, or autogenerate becomes worth having ORM models.

## ADR-012 — 2026-11-06 — product-visuals design approved for phase 1; Python tooling

- Status: Explicit user approval ("go ahead") of designs/product-visuals.md r4, phase 1 only.
- Context: Codex r1–r3 REWORK, then a fourth narrow round the user authorised past the 3-round cap ("go for a last review"). r4 → APPROVE WITH FIXES; the 3 local fixes were applied and self-checked without another round.
- Decision: (1) Implement phase 1 as designed: domain and state machines, stub + OpenAI gateway, cutout, fixtures and the CLI evaluation. The draft phase-2 HTTP/session contracts are not approved. (2) Python 3.12 with uv (`pyproject.toml` + `uv.lock`), pytest for tests. Both are installed on the user's PC (uv 0.11.8).
- Because: Phase 1 is the smallest thing that produces the R-008 evidence. uv gives a lockfile and a pinned interpreter with one tool that is already installed.
- Not verified yet: OpenAI SDK methods and error fields (T-PV-003), whether gpt-image-2 returns `usage` (T-PV-012 probe), and rembg model names (T-PV-004).
- Revisit if: the evaluation recommendation changes the review flow (design v2), or rembg/onnxruntime wheels are missing for 3.12 on Windows.

## ADR-011 — 2026-11-06 — product-visuals design questions: all recommended options

- Status: User decision on design r3 UQ-1 … UQ-5 ("go with all recommended DQs"). This is not the design approval; Codex r3 and explicit approval are still required.
- Decision:
  1. **Shadow (UQ-1 a):** a synthetic shadow is baked into the background at the default product position. It stays in place when the cutout moves, as ADR-009 already accepted. No separate shadow layer is stored.
  2. **Requirements wording (UQ-2):** R-003 c.1 (catalogue terms never sent; operator free text screened best-effort), R-003 c.2 (do not *add* text; product markings kept) and R-004 c.2 (text added outside the product; `cadrage` required to approve; `integration`) are amended.
  3. **Phasing (UQ-3):** phase 1 = domain, gateway, cutout and CLI evaluation with a desktop contact sheet; then the paid evaluation; then phase 2 (HTTP API and phone/desktop UI) in design v2. The design approval covers phase 1 only.
  4. **Evaluation exception to ADR-010 (UQ-4):** for CLI evaluation runs only, the attempt limit is 5, and products the user assigns to arm B get plain re-rolls without corrections. About +$16 per model at base estimates.
  5. **Attempt-limit reset (UQ-5 a):** an explicit "Nouvelle campagne" action starts a new cycle for a variant, allowed only after one of its candidates in the current cycle is approved. Approving never resets the count by itself.
- Because: (1) avoids a "ghost" product and an extra layer; (2) the old wording would make the model erase real product logos, and the blocklist cannot be complete; (3) the evaluation can change the review flow before UI work is spent; (4) measures whether 3 is the right limit and whether corrections help; (5) a variant gets a fresh allowance per campaign without a loophole.
- Alternatives: a movable shadow layer (amends R-006 c.4); a background generated around the product (ghost when moved); never resetting the allowance.
- Revisit if: the evaluation shows frequent `integration` rejections (consider the generated-around-product background) or that the A/B evidence is too weak to decide.

## ADR-010 — 2026-11-06 — User's OpenAI account, 3-attempt limit, no prototype

- Status: User answers to the product-visuals open questions.
- Decision: (1) Use the user's own OpenAI account; the user provides the API key, which is held only in the server's `.env` (already git-ignored). (2) Allow 3 generated attempts per product variant, then offer the photo-preserving fallback. (3) There is no prototype to inspect; build the cutout step from scratch. (4) The user will supply the fixture photos.
- Spending cap: no amount was given. It is therefore a required configuration value; with no cap set, no paid call can start. This is a deliberate guard, not an assumed amount.
- Because: The cap stays in the user's hands without blocking the design. The key never reaches code, chat or the frontend.
- Revisit if: The evaluation shows that 3 attempts are often not enough for a fidelity-correct scene, or a shared or company account replaces the personal one.
- Note: BRIEF.md mentioned a `poster-kit.zip` prototype. The user confirmed on 2026-11-06 that it does not exist yet.

## ADR-009 — 2026-11-06 — One candidate per request; fallback product kept as a separate layer

- Status: User decision after reviewing the product-visuals mockup ("go with option A, 1 result per request").
- Context: Open questions 3 and 4 in requirements/product-visuals.md.
- Decision: (1) Each generation request produces one candidate. (2) In the photo-preserving fallback, the cutout of the original photo stays a separate layer above a generated background. The two parts are never merged, and the operator can move and resize the product in the editor.
- Because: One candidate keeps the cost per attempt low and predictable during the evaluation. A separate layer avoids a server-side compositing step, makes it simple to prove the product pixels are untouched (they are the cutout file), and gives the operator a movable product.
- Trade-off accepted: the shadow is part of the background and does not follow the product. The UI must say so.
- Consequences: poster-editor requirements must support an image layer that can be moved and resized. The product in a `scene` treatment still cannot be moved on its own. Creation records must store the cutout and the background separately.
- Revisit if: The evaluation shows that operators often move the product far enough to break the shadow, or that one candidate per request leads to many more revisions.

## ADR-008 — 2026-11-05 — Charter and feature split approved; product-visuals first

- Status: Explicit user approval ("approved, start with product-visuals").
- Context: T-BOOT-002 gate. PROJECT.md and the six-feature split were in Draft.
- Decision: Approve PROJECT.md as written and the six features (catalogue-brand, generation-jobs, product-visuals, poster-editor, format-export, creation-library). Draft product-visuals requirements first.
- Because: Product-detail drift in generated scenes is the highest product risk, and the results of the model/fallback evaluation affect the cost, the editor (flattened scene or separate product layer) and the reuse rules.
- Alternatives: poster-editor first (phone editing risk) was the other recommended option. catalogue-brand first is lower risk but would delay the main unknown.
- Open at approval: paid-evaluation budget, prototype inspection and an initial commit were raised but not answered. They are carried into the product-visuals open questions or the handoff.
- Revisit if: The fidelity evaluation shows that neither treatment is acceptable, which would change the scope of the pilot.

## ADR-007 — 2026-11-05 — Trust only affiche-ia across sandbox and desktop users

- Status: Applied and verified as T-BOOT-004 in response to the user's local-host failure.
- Context: The repository and .git were created by DESKTOP-N8QV4L5/CodexSandboxOffline, while the desktop host runs as M Rakotozafy. Git therefore rejected the repository on the desktop despite succeeding during the original sandbox checks.
- Decision: Add exactly C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia as safe.directory in C:/Users/M Rakotozafy/.gitconfig after obtaining filesystem permission. Preserve all existing settings; retain a backup in the original chat workspace, outside this repository.
- Because: This is the user-requested repository created in this session; an exact protected-config entry permits the intended cross-user use while retaining checks for other repositories. Git documents this mechanism at https://git-scm.com/docs/git-config#Documentation/git-config.txt-safedirectory.
- Alternatives: A wildcard trust entry would be unnecessarily broad. Changing ownership/ACLs is more invasive. Repository-local safe.directory is not a valid protected trust configuration.
- Validation: Reproduced the failure with GIT_TEST_ASSUME_DIFFERENT_OWNER=1, tested the proposed config, then verified both the original command and forced-ownership check with the actual user config. The desktop UI has not been reopened by the assistant.
- Revisit if: The project moves, its ownership changes, or a host uses a different user/configuration. Remove the exception when it is no longer needed.

## ADR-006 — 2026-11-05 — Place the canonical project beside tsena_scan and initialise Git

- Status: Explicitly requested by the user; completed and verified as T-BOOT-003 on 2026-11-05.
- Context: ADR-005 used a generated chat workspace. The user requested a sibling project beside tsena_scan and a local Git repository.
- Decision: Use C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia as the canonical root. Copy the prepared project without deleting the chat copy, initialise an independent repository on main, and add a minimal README and .gitignore for the confirmed Python/Vue stack. Do not create a remote or a commit as part of git init.
- Because: This matches the user's explicit location and version-control request while preserving the existing documents.
- Alternatives: Leaving the project in the generated chat folder would not satisfy the request. A new worktree is unnecessary for an independent repository.
- Revisit if: The user requests a different location, repository policy or remote. This entry supersedes ADR-005 only for the canonical location; project approval gates remain unchanged.

## ADR-005 — 2026-11-05 — Bootstrap the documentation in the current workspace

- Status: Bootstrap execution decision within the user's request.
- Context: The current workspace contains the reviewed brief and feedback but no application or Git repository.
- Decision: Use this workspace as the local project root; create AGENTS.md and docs/project/ from the available templates. Preserve the existing outputs/ and work/ directories. Stop for PROJECT.md and feature-split approval before requirements or application scaffolding.
- Because: The user requested a local bootstrap under an explicit documentation-first workflow.
- Alternatives: A new worktree is unnecessary without an existing repository; application scaffolding would skip the project approval gate.
- Revisit if: The user requests a different project location or repository setup.

## ADR-004 — 2026-11-05 — Single-shop, French-language pilot with full phone and desktop editing

- Status: Confirmed by the user in the bootstrap interview.
- Context: The brief left pilot scope, device support, and initial language open.
- Decision: Start with Original Phone Mada only; support full editing on both phones and desktop; launch the interface and generated captions in French. Add Malagasy after the pilot.
- Because: These are the user's explicit answers on 2026-11-05.
- Alternatives: Several shops at launch, desktop-only editing, and bilingual launch were not selected.
- Revisit if: Pilot evidence or an explicit scope change justifies expanding users or languages.

## ADR-003 — 2026-11-05 — Keep formal specification behind the bootstrap approval gate

- Status: Required by the user's Global Working Agreement.
- Context: The existing brief includes product and technical proposals but has not been approved as formal requirements or design.
- Decision: Populate PROJECT.md and propose a feature split now. Leave requirements and designs as templates and empty indexes until project approval. Then follow requirements approval, design, tasks, implementation, and handoff in order.
- Because: A request to bootstrap authorizes the bootstrap phase, not all later proposals in the brief.
- Alternatives: Creating feature requirements, choosing a canvas SDK, or writing application code during bootstrap would bypass the agreed gates.
- Revisit if: The user explicitly changes the working agreement.

## ADR-002 — 2026-11-05 — Avoid fixed HTML poster templates as a V1 constraint

- Status: User direction recorded from the brief discussion.
- Context: The first brief used Jinja2/HTML poster templates. The user considers fixed templates too limiting for the first version.
- Decision: Do not constrain poster creation to a fixed catalogue of HTML layouts. Carry a flexible canvas with AI-proposed compositions forward as the recommended approach; preserve the distinction between that recommendation and an approved technical design.
- Because: The product should accommodate different products and creative directions while making routine changes easy.
- Alternatives: Reusing the old HTML renderer as the governing layout system would impose the rejected constraint. Ordinary HTML in the Vue application's interface is unaffected.
- Revisit if: The user explicitly chooses a different composition strategy after evaluating the editor.

## ADR-001 — 2026-11-05 — Vite + Vue frontend alongside FastAPI

- Status: Explicit user choice.
- Context: The brief originally left the frontend framework open.
- Decision: Use Vite + Vue for the web UI and FastAPI for the API. Evaluate canvas integration within that stack. Do not select a library by switching the application to a different frontend framework.
- Because: The user specified this stack before requesting bootstrap.
- Alternatives: HTMX, Svelte, or a React application are not the selected application stack.
- Revisit if: The user explicitly changes the stack constraint.


## Research scope confirmation — Codex, 2026-11-15 — Publishing and SaaS

- User requested research and suggestions alongside Claude's chat audit, then explicitly confirmed a Madagascar selling business and ordinary Facebook/Instagram posts first; paid advertising comes later.
- Research is saved in [the publishing and SaaS report](reviews/social-publishing-saas-research-2026-11-15.md). Prepaid-first packaging, wallet rules, login/payment options, dashboards and the feature split are proposals, not approved architecture, prices, provider choices or implementation authorization. Existing PROJECT.md scope and workflow gates remain unchanged.
- No provider credentials requested, application code changed, paid calls made, social posts sent or production resources accessed in this research track.


## Verification scope confirmation — Codex, 2026-11-15 — No provider accounts yet

- User authorized necessary verification and explicitly confirmed that no provider accounts are set up. Ran existing isolated regression checks and a synthetic local JPEG probe; verified further public setup documentation. No account was created, credential requested in chat, external message sent, real post/payment made or production resource accessed.
- Live Meta and payment verification requires provider setup first. The passing pilot checks do not establish multi-tenant, customer-wallet or publishing readiness; no implementation authorization or formal design approval is inferred.


## Research update — Codex, 2026-11-15 — Papi as the first local checkout candidate

- User supplied papi.mg as another Malagasy payment processor. Official coverage, hosted checkout, direct/transit collection, pricing and callback/status contracts make Papi hosted checkout the first candidate to evaluate for local prepaid packs; direct MVola remains a cost/settlement comparison. This supersedes the research recommendation only, not an approved provider selection or implementation design.
- Published callback signature vector matched locally; public demo payment was not completed. Merchant verification, transit settlement/refunds and automatic recurring debit remain unresolved. No app source, merchant account or production payment was created.


## Brand exploration — Codex, 2026-11-15 — Three concepts, no selected name

- User explicitly requested logo-design, several logo/brand-identity options and possible new names. Fast-track assumptions: Malagasy shops, French UI, approachable/capable tone, phone-first symbol and room beyond generation.
- [Concepts](mockups/brand-directions/README.md): Affisoa (recommended), Saryko and Vitraka. Names, palette/type/voice directions and vector art are proposals; the application remains Affiche IA. Two render/test rounds were completed; the full identity kit awaits selection under the invoked skill’s concept checkpoint. No app branding rollout is authorized by a concept choice alone.
- Name availability/legal clearance, customer language reactions and physical reproduction remain unverified. No application code or dependencies were changed.


## Brand exploration addition — Codex, 2026-11-15 — Doka Studio

- User asked to add Doka Studio as a fourth proposal; this does not select it as the application name. Added a geometric cut-corner D, outlined doka/STUDIO lockup and yellow/charcoal/paper identity proposal alongside the original three.
- Two iterations were rendered/inspected, with corrected centering and a larger descriptor. Naming overlap with the former Doka image editor (now Pintura) and existing Doka Studio event usage is documented for eventual clearance. No application source or installed identity changed.


## Brand direction selected — Codex, 2026-11-15 — Doka Studio

- User: “Let’s go with Doka studio, explore more style and more design identity using logo-design and image-gen.” Doka Studio is the selected name for this identity work; the other three names are no longer the recommendation.
- Authorized: further visual exploration and AI-generated brand mockups. Three styles will share the selected name and build from the cut-corner D, with different typography, composition, graphic language and palettes. A final style and application rollout are not yet selected. No paid application-provider evaluation or app rename is implied.

## Identity direction selected — Codex, 2026-11-15 — Signal

- User: “I think I prefer more the Signal version.” Record Signal as the chosen direction for further Doka Studio identity work: yellow `#F2C744`, charcoal `#20201D`, paper `#F5F1E8`, bold Space Grotesk lettering and the cut-corner D. Editorial and Complice remain archived alternatives; no hybrid was requested.
- This selects the direction, not final production artwork or an application rollout. The next proposed deliverable is the refined Signal kit; no additional generation or export task was requested in this message.

## Signal kit authorized — Codex, 2026-11-15

- User says “go” to the offered final Signal logo kit. This authorizes Phase 7 asset refinement, vector/raster/icon exports and usage notes; the previously selected identity brief is the scope. No new app feature, implementation or deployment is included.
- Keep the selected D and bold wordmark; derive compact/stacked layouts from the same outlines. Use charcoal on yellow for icon tiles, paper or white on charcoal for reverse artwork, and a slightly expanded D counter for large reverse marks. Print color numbers will be explicitly provisional; do not invent Pantone matches or claim physical proofing.

## Signal kit delivered — Codex, 2026-11-15

- [Digital kit v1](brand/doka-studio-signal/README.md) delivers exact outlined SVGs and transparent PNGs, horizontal/stacked/name-only/symbol layouts, optically lighter reverse D, yellow-backed favicons and platform-safe icons. Minimum screen widths are 220 px horizontal, 160 px stacked/name-only and 16 px favicon; these are conservative inspected sizes, not print-proof claims.
- Fonts are bundled unchanged with SIL OFL notices. Presentation examples use explicit placeholder contact/domain details. The manifest/head snippet is integration material only; no PWA behavior or application rollout is implemented. Digital/structural/browser/export checks pass; print and naming clearance remain open. ZIP content hashes and CRC verified.

## ADR-108 — Sign-out keeps nothing on the device; the server is the authority for a paid request — Claude, 2026-11-16

- **Decision (user: "explore a new solution instead of patching it", then "go" on the comparison):** the `kept` record that carried a waiting paid chat card across a sign-out is removed. Sign-out ends the session on the server first, then deletes every key of the shop on the device. A paid request leaves the browser only after its thread was stored. R-MULTI-SHOP-004 is amended; the design's amendment section "After round 4" has the detail.
- **Why:** four code reviews of T-MULTI-SHOP-006 rejected the kept card, each on a new way to lose or overwrite the request where its three copies met or where browser storage failed. The server already writes the key, the job and the reservation in one transaction and refuses any request of an ended session, so a request it received is safe there and one it did not receive cost nothing.
- **Compared and not chosen:** one browser record per card (same device only; more of the storage work that failed); refusing sign-out while a card waits (can hold the owner until the next day when the daily limit is why it waits).
- **Cost accepted:** after signing in again the card does not come back; the image is found on the poster or in « Mes affiches ». A browser that cannot store data refuses paid chat cards.

## ADR-109 — Prepaid balance: the job is the debit; design v4 approved — Claude, 2026-11-16

- **Decision:** [designs/prepaid-balance.md](designs/prepaid-balance.md) v4 and its requirements (amended) are approved under the autonomy grant, after three review rounds (REJECT, REJECT, APPROVE WITH FIXES) and a devil's advocate. A credit is one generated image. The balance is derived: the operator's append-only lines (`credit_grants`: grants and corrections) minus the shop's image jobs marked `takes_credit` that are queued, running or succeeded. A job that ends without an image stops counting with no write. The first draft's ledger of debit and release lines kept by a trigger was dropped on the devil's advocate's point: the lines copied the job row, and a later rebuild of `poster_jobs` could have dropped the trigger unseen.
- **User decision (2026-11-16, "grant by hand, 30 credits"):** the pilot shop's opening balance is 30 offered credits, typed by the operator right after the release; migration 0014 grants nothing.
- **Also decided in the design:** a payment belongs to one shop (one atomic move while its credits are unspent); a restore is reconciled by copying the missing lines from the kept database with their dates; chat reads get one flat limit of 100 a day per shop (R-BALANCE-007 amended; it replaces 200); no dollar figure reaches a shop; the service pause is checked at admission only; a text material costs a credit (amends ADR-107's "textures … no credit").
- **On defaults the user can still change before the task that builds each:** credit back at once when the provider's outcome is unknown (the ceilings bound recorded estimates, not proven charges); suspension as the only per-shop stop; the purchase text written by the operator. **Not built:** automatic credit back for a version rejected for a fidelity defect; a monthly cap (the cap stays cumulative; `grant` warns when it runs short).

## ADR-110 — The admin dashboard: a thin page over the command line; the operator's password in the database; no actions table (2026-11-17)

- **Decision:** [designs/admin-dashboard.md](designs/admin-dashboard.md) v3 and its requirements v4 are approved under the autonomy grant, after two Codex design rounds (both APPROVE WITH FIXES; the round-2 fixes were not reviewed again) and a devil's advocate. The dashboard is `/admin/`, a second page of the same frontend built apart from the shops' bundle; every money route calls `credits.grant`, `correct` and `move`; the command line stays the break-glass path.
- **Lead's calls the user may overturn:** the operator's password hash lives in the database, set by `python -m affiche.shops operator-password` (run again after a restore, before the restart); no `operator_actions` table: money keeps its actor in `credit_grants`, other dashboard writes are logged, best effort; nothing is cut from Release 1, but tasks T-ADMIN-008 to 010 (usage report, problems and queue, Reka UI trial) come last and may move after the release on the user's word; the Reka UI trial stays on AlertDialog and is kept only if it beats the native dialog on a measured point (Tabs is the recorded alternative).
- **Why:** recording actions inside `shops.py` was the most error-prone part of v1 (nested calls, refused restores) for one operator; a hash in the environment added a silent "dashboard off" state and a restart of every shop's service at each rotation.
- **Residual, accepted for Release 1:** the dashboard shares the shops' origin, so a script injected in the shop app could act as the operator in the operator's browser; a subdomain would close it and needs a change on the shared box (the user's decision). A stolen operator session is bounded by the spend cap and the shop's daily limit, and what it creates outlives it: the runbook gets a suspected-compromise procedure.
- **Not built:** cancelling a payment that never arrived (the ariary stay counted as received); two-factor sign-in; per-shop daily limits.

## ADR-111 — Invented features: the owner is warned and checks; admin tasks 008 to 010 after Release 1 (2026-11-17)

- **Decision (the user, 2026-11-17):** for R-TERMS-002 the default is kept: when a request asks for product features without listing them, the card says so before the paid tap (« L’IA choisira les caractéristiques : vérifiez-les avant de publier. ») and the check before download cannot be skipped. The alternative (the image writes only features the owner listed) is not built.
- **Decision (the user, 2026-11-17):** T-ADMIN-008 (usage report), T-ADMIN-009 (problems and queue) and T-ADMIN-010 (Reka UI trial) are built after Release 1. The command line and `/api/status` cover usage and problems until then.
- **Decision (the user, 2026-11-17):** the one open finding of T-ADMIN-006's third review is accepted as a known limit: no cross-tab lock around a kept money request's storage key (TODO.md, T-ADMIN-006; designs/admin-dashboard.md "Not built").
- **Why:** the free « ajoute 4 lignes de caractéristiques » request is what the user did with his own poster on 2026-11-15, and the conditions of use (R-TERMS-001) put the check on the owner; the conditions gate inviting a second shop, the three admin screens do not.

## ADR-112 — Conditions of use: design v3 approved; R-TERMS-003 amended; no erase command in Release 1 (2026-11-18)

- **Decision:** [designs/service-terms.md](designs/service-terms.md) v3 is approved under the autonomy grant after two Codex design rounds (REJECT, then APPROVE WITH FIXES; the round-2 fixes were not reviewed again) and a devil's advocate. The conditions are a versioned text in the code, accepted per shop (migration 0017, two columns); one shared check refuses every new shop AI request without acceptance, before the admission limits and the credit; the dialog has « J’accepte » and « Plus tard » and never blocks free work.
- **Decision (the user, 2026-11-18):** R-TERMS-003 is amended. On a request to delete, the shop is suspended at once and the operator then tells the owner what is erased and when: no deadline, no claim about backups, no erase command in Release 1. The page says accurately that the result of a reading is kept and can repeat the instruction typed; storage does not change.
- **Lead's calls the user may overturn:** the warning of ADR-111 is shown on every scene-adjustment card and in « Ajuster la scène », behind a conditional lead-in (« Vous demandez des caractéristiques sans les lister ? »), with no change to the paid reading; one check wording for every poster; only the last acceptance per shop is kept; the page names OpenAI, Anthropic and Hetzner; the operator's view of who accepted is not built; all French texts are drafts until the user reads them.
- **Why:** the first draft's erase command could remove a file another shop uses and could stop the API from starting once the pilot shop was erased; a reading-based warning could be missed on a wrong answer or an old card, and needed a paid evaluation.
- **Accepted limits:** a preview's pixels can be saved without the check; the style quota and the adjustment-chain limit can answer before `terms_required` (neither takes a credit nor reaches a provider); SQLite 3.40.1 is verified only at the release rehearsal.

## ADR-113 — Shop dashboard requirements approved for design (2026-11-18)

The owner approved Home, Credits and Account, the 30-day usage line, and accessible small-phone use. This authorizes the dashboard design. Implementation awaits design approval.

## ADR-114 — Shop dashboard design approved (2026-11-18)

The owner approved v3 for implementation, including one linked poster plus the remaining count per attention group and gross credits spent by completion time alongside posters created and images generated over 30 days.

## ADR-115 — Implementation model follows the orchestrator (2026-11-18)

The owner directs Codex to use GPT for implementation when Codex orchestrates. Independent code review and the existing workflow gates remain in force.

## ADR-116 — Home review closure (2026-11-18)

After three rounds the owner chose to fix both outstanding navigation cases and close T-SHOP-DASH-003 after passing checks.

## ADR-117 — Credits review closure (2026-11-18)

The owner approved closing T-SHOP-DASH-004 after fixing the current-poster history action and checking that the creator retains its attachment, undo history and focus.

## ADR-118 — Account review closure (2026-11-18)

The owner approved fixing the delayed terms read on a verified return to Account and closing T-SHOP-DASH-005 after its two-device regression and Account checks pass.

## Impeccable product context — 2026-11-18

Owner confirmed the invited Malagasy shop positioning and chose image mockups first for landing pages and showcases. App screens and documents follow the code-first workflow.

## Mobile dashboard follow-up — 2026-11-18

Owner selected all five mobile critique findings for the next design. Leaving edited shop details should prompt to keep editing or discard.

Owner approved R-SHOP-DASH-005 through 009 for design. Proposed contract choice: return the linked title in the existing summary snapshot so Home can identify older posters even when the recent list fails.

## ADR-119 — Mobile dashboard design approval (2026-11-18)

The owner approved the v4 shop dashboard amendment covering D-SHOP-DASH-005 through 009, including the keep-editing/discard choice and the nullable title in each attention group.

The owner authorized closing T-SHOP-DASH-006 after fixing the round-three history issue and passing its regression and dashboard checks. Codex may resolve subsequent routine implementation and review decisions autonomously within the approved dashboard design.

## ADR-120 — « Partager »: design v3 approved; the JPEG and the caption stay on the phone; one read-only field names the current confirmation (2026-11-18)

- **Decision:** [designs/share-poster.md](designs/share-poster.md) v3 is approved under the autonomy grant after two Codex design rounds (REJECT, then APPROVE WITH FIXES; the round-2 fixes were not reviewed again) and a devil's advocate. The user said "go" on the defaults.
- **Lead's calls the user may overturn:** the JPEG is made in the browser from the confirmed PNG the final panel already shows (no server encoding, no extra mobile data); the caption is kept on the device only, per shop and poster, like a poster's typed words (ADR-083), erased by a successful sign-out, with no entry cap; « Partager » lives in the editor's final panel, and the chat's « Télécharger » becomes « Télécharger ou partager »; caption bound 2 000 code points; after a cancelled share the system clipboard may already hold the caption.
- **Reversed during review:** v2 had no backend change and found the confirmed file by walking the poster's recent jobs. Round 2 showed that after a price edit an older confirmed image could open beside the new price and be shared, and that the jobs list stops at 50. `GET /api/creations/{id}` now carries `confirmation` (the confirmation made at the poster's current revision, else null; one shop-scoped SELECT, no migration). « Partager » is offered only for it; an older confirmed file keeps its download, labelled as an earlier version, without the live price.
- **Why:** a caption column, a save route and a server JPEG were the over-built part (devil's advocate); the wrong-price share is the one outcome that must never happen.
- **Open:** R-SHARE-005 (real phones) stays open until the owner fills the test sheet; the iPhone rows need HTTPS and an iPhone; the French texts are drafts.

## ADR-121 — Release 1 ships before « Partager » is tried on a real phone; the sheet is filled on the live site (2026-11-19)

- **Decision (the owner's, 2026-11-19: "Release first, test on the live site"):** no Android phone was at hand for the USB test of D-SHARE-005. Release 1 goes out first; the owner then fills the phone sheet ([reviews/share-poster-phones-2026-11-19.md](reviews/share-poster-phones-2026-11-19.md)) on `https://affiches.miorantsoa.app` with any phone, on a poster already confirmed (confirming takes no credit and calls no provider: only image jobs do, `jobs.IMAGE_KINDS`).
- **Lead's addition the owner may overturn:** invitations to new shops wait until rows 1 (Facebook as the Page) and 3 (WhatsApp) work (deploy/README.md, « Partager » on a real phone). It costs nothing and keeps a failing share away from shops who never saw the app.
- **Accepted risk:** the pilot sees « Partager » before any real-phone check; if an app fails, he still has « Télécharger » beside it. HTTPS also makes the iPhone rows possible at the same time.
- **Changed:** ROADMAP.md (Release 1's definition of done), D-SHARE-005 (amended), deploy/README.md, the sheet's header, T-SHARE-005, HANDOFF.

## ADR-122 — Interface polish: a consistency pass in the Signal identity; Figtree stays; the main button stays charcoal (2026-11-20)

- **Context:** the owner asked to polish the look of the shop's interface and the operator's page with the impeccable, design-taste and ui-ux-pro-max skills, then: "start, you can go to the end without stopping". The baseline ([reviews/design-baseline-2026-11-20.md](reviews/design-baseline-2026-11-20.md)) showed that the Signal identity is already on the client, so this is consistency and finish, not a rebrand.
- **Decision:** [requirements/interface-polish.md](requirements/interface-polish.md) v2 and [designs/interface-polish.md](designs/interface-polish.md) v2 are approved by the lead under the autonomy grant. Five tasks, T-POLISH-001 to 005: the name and the mark everywhere; the amber accent becomes Signal Yellow with a separate line colour; one frame for every screen of the shop; the operator's numbers; `DESIGN.md` and the after captures.
- **The owner did not answer the typeface question; the lead's recommendation stands:** Figtree stays (ADR-077). It is one bundled file with the weights the interface uses; the kit's Space Grotesk and Noto Sans are not loaded. He may overturn it.
- **Reversed by the two reviews of v1** (Codex REJECT, [reviews/interface-polish-design-r1.md](reviews/interface-polish-design-r1.md); devil's advocate, [reviews/interface-polish-devils-advocate.md](reviews/interface-polish-devils-advocate.md)): no yellow main button (1.43:1 against the paper, not seen on a phone in daylight); the dark theme keeps its greys (ADR-091) instead of the kit's charcoal; contrast is measured on the rendered screens, not on a table of tokens; no centred empty conversation; no two-column shop page (it goes with T-ADMIN-008). v2 was not reviewed again as a document: each task's code gets its own review.
- **Each skill has one role:** Impeccable for the craft floor before an edit, the detector after it and `DESIGN.md`; design-taste for its app-screen rules and its inspector on the captures; ui-ux-pro-max for single lookups. When they disagree: the Signal guide, PRODUCT.md, the approved designs, the design, then a skill. Both checkers flag the cream ground and Space Grotesk as overused: the brief wins.
- **Lead's calls the owner may overturn:** listed at the end of the design (the accent, the dark ground, the bottom bar's bare number, two new titles for screen readers).
- **Nothing is deployed by this work.** A deploy stays the owner's word; the phone test of « Partager » and the invitations come first for him.

## ADR-123 — App redesign: both interfaces follow the approved mockup; built on the branch `redesign`, not on `main` (2026-11-20)

- **Context:** after the interface polish (ADR-122) the owner asked for a new mockup of both entries ([mockups/doka-console/](mockups/doka-console/README.md), T-MOCKUP-CONSOLE), corrected it in two rounds (softer button edges, new table and card styles, a leaner conversation, the layout of a known AI chat, a quieter composer shadow), then said "we can proceed now" and "Not necessarly one task at a time, tasks can be done in parallelle".
- **Decision:** [requirements/app-redesign.md](requirements/app-redesign.md) v2 and [designs/app-redesign.md](designs/app-redesign.md) v2 are approved by the lead under the autonomy grant. Seven tasks, T-REDESIGN-001 to 007: tokens and primitives; the shops' shell (sidebar, rail, drawer, phone bar); the chat; the other screens; the console's shell; the console's Overview; the record and the proof. Presentation and navigation only: no migration, no job, no money rule, no route, no server answer.
- **It reverses, on the owner's approval of the mockup:** ADR-122's "the main button stays charcoal" (the main action is charcoal on Signal Yellow) and its dark ground (now the kit's Charcoal `#20201d`); ADR-077's glass on every surface (a resting surface is opaque with a hairline; blur and shadow only on what floats); D-POLISH-003's phone bar (now five items with a centre « Nouvelle affiche », absent in the chat and the editor); poster-editor.md's one `.nav` in the header; R-SHOP-DASH-008 (the product is named by the kit's logo, the name is no longer typed beside the mark); D-ADMIN-005's system fonts, device-only theme, header and "Shops (the home)" (the console is in Figtree, has a theme switch, a sidebar and Overview as its home). D-ADMIN-005's isolation, its 44 px targets, its one column at 360 px and "nothing fixed to the bottom" stay.
- **The mockup is the target for the look, not for the content.** What the application keeps against it is listed in the requirements (« Not built, on purpose »): the approved cost sentence (R-BALANCE-001), no suggestion chips, one shop as a page, no « Conditions pending », a visible edge on the composer.
- **Two reviews shaped v2** (Codex REJECT of v1, [reviews/app-redesign-design-r1.md](reviews/app-redesign-design-r1.md); devil's advocate, [reviews/app-redesign-devils-advocate.md](reviews/app-redesign-devils-advocate.md)): no wrapper around the page (a fixed sidebar, the frame painted behind the content, the window still the scroller), because dialogs and the phone's approval buttons are fixed to the screen from inside `main`; the sidebar from 1181 px, so the editor never has less width than today; shop data in the shell not rendered while the identity gate is closed; no server field (the console's « Conditions pending » is not built).
- **Where it lives:** branches `redesign` and `redesign-console`, in git worktrees under `../affiche-ia-worktrees/` (each with its own dependencies and smoke ports, T-SMOKE-PORTS). `main` keeps the polish, so the owner can release it alone. Merging into `main`, pushing and deploying are his word. The tasks are cut so that the tokens, then the shell and the chat, then the console could each be released alone.
- **Lead's calls the owner may overturn:** the nine points at the end of the design.

## ADR-124 — An element pass on both interfaces: one balance card, quiet row actions, a payments table (2026-11-21)

**Context.** After the redesign (ADR-123) the owner looked at the running branch and asked for the credits card to be "a correct balance card, like a finance app's", then for the same care on every element: lists, thumbnails, the link to the account, button positions, forms, text placement, tables and cards. His rule for this work: search the web for the current practice first, then apply it with the design skills' app-screen rules.

**Decision.** One pass, on the branch `redesign`, that changes looks and positions only: no sentence, route, state or server answer.
- **The balance is one card in two places** (Accueil and Mes crédits): the available credits lead (36 px, label above, the unit « crédits » after), the pending ones are clearly second, the action is under the figures. It is the dark card in both themes: charcoal in the light theme, so the yellow action sits on charcoal as in the kit. That makes one exception to "a table token is written only in the two themes": inside `.balance-card` the light theme writes the dark theme's values again, and `tokens.test.ts` pins them equal. No gradient: the first version's corner glow was removed (flat surfaces).
- **Rows.** A poster's second actions (« Dupliquer », « Retirer de la liste ») are words, not outlined buttons; the row and its chevron stay the main action. Thumbnails are 64 × 80 in Mes affiches (48 × 60 on Accueil), with 4 px corners. Accueil's rows end with a chevron, and « Mon compte » is a row of its own.
- **Positions.** A page's action is on its title's line, at the right (« Nouvelle affiche », the console's « Refresh »); a filter is directly on the list it filters; the way back is before the title; « Se déconnecter » is the last thing on Mon compte, outside the assistance card; the sign-in card's buttons take its width.
- **Forms fill their card** (the owner's rule: he showed three blocks whose content stopped short of its card, and each was changed). Where the fields would be too wide, the card or the column is narrower, never the form inside it: one shop's page in the console is a 600 px column, the console's period one row across its card, « Needs you » shares its card's width among its lines. A first try of this pass capped Mon compte's fields at 30rem; it was undone for the same rule. its head shows the name, the state as a badge and the two balances as figures. Its sections, their order, its confirmations and its kept requests are unchanged (R-REDESIGN-006).
- **« New shop » is a window** (the owner's word: "a new window or a pop up window"): a native modal dialog in place of the fold over the shops table, opened from the sidebar and from a button on the Shops page's title line. Created, it closes and the password shown once takes the focus, as before; a page out of date closes it, since the reload banner is behind it.
- **Tables.** The console's payments are a table (When, Shop, Entry, Method, Reference, Credits, Amount) in place of paragraphs; under 600 px a table's cards put the label on the left and the value on the right edge.

**Why.** The sources found agree on each point (design systems and vendor guides, named to the owner in the session; conventions, not studies): the balance is the dominant figure with its action under it; a list row has one trailing element; a page's actions are right of its title; a field's width says what it takes; money in rows is a table with right-aligned figures. The skill's study of 23 working screens gave the sizes (a leading figure of 30 to 36 px, never 48; labels above values; flat cards).

**Left as it was, on purpose.** The chat, the step editor, the review and final panels (reviewed three times in the redesign); the sections of one shop's page in the console; every approved sentence, including the check times. The Overview's short right column and the chevron before the row's words on a wide screen are noted in the report, not changed.

**The owner may overturn:** the dark card in the light theme; « crédits » after the two figures (the shell's word, new in the card); the 64 px thumbnails; the 600 px column of one shop's page.

## ADR-125 — The features warning follows the request's words (2026-11-21)

**Context.** The redesign was released and the owner used it. Under a scene adjustment for « Podium smaller » the card said « Vous demandez des caractéristiques sans les lister ? … », "every time now". That was the design of 2026-11-17 (D-TERMS-005, owner decision 2): the sentence on every scene-adjustment card, because a field answered by the paid reader could be lost by a replayed or restored card. The requirement itself (R-TERMS-002) only asked for it "when a request asks for features without listing them".

**Decision (the owner: "word test").** The page shows the warning only when the request's own words could ask for features or for text to write: one fixed list, French and English, in `generation.ts` (`asksText`), used by the chat's card and by the confirmation of « Ajuster la scène ». The words of a scene are kept out of the list (« texture », « qualité », « plus de détails » alone, « affiche »).

**Consequence, accepted.** A request worded outside the list has no warning before the paid tap. The check before download still names the texts that were added and cannot be skipped, and the accepted conditions still say that the AI chooses unlisted features. Not chosen: the warning once per poster (it would still stand under « Podium smaller »), no warning at all (the only notice before payment), a field from the paid reader (a server change; the next step if the list misses too much).

**The owner may overturn:** any word of the list; the choice to warn on icons, badges, labels and banners (they carry invented text).

## ADR-126 — A product photo sent on an existing poster offers a copy on that photo (2026-11-21)

**Context.** On the released app the owner sent an image with « Use this as product » on an existing poster. The image was labelled « Inspiration » (the poster's own photo counted as the first image), and the answer was a paid scene adjustment that never used the image. The chat also said « Les photos d’une affiche se changent dans Pas à pas », which was not true. A version belongs to its product's photos and a poster's product never changes on the server; the one way to other photos is a copy onto a new product input (`replace_input`, as « Refaire en … »).

**Decision (the owner: "yes copy with the new photo").** Page only, no server change, no new paid path, no change to an existing one (D-TEXT-FIRST-007 v5).
- On an existing poster every attached image is a product photo. A message with images is not sent to the paid reader; the chat answers with a card that offers a copy of the poster on the new photos. The copy costs nothing; the poster it came from is unchanged.
- The copy is the editor's own action, as « Refaire en … »: it opens in « Pas à pas », without a version, and its image is the editor's « Générer l’affiche ». The chat adds no paid card and keeps nothing of the copy.

**How it got there.** Four designs made the copy and its first image in the chat (v1 to v4), and four reviews rejected them. v1 also took an inspiration image on an existing poster: a tab on the released bundle could have paid for it without sending the image. From v2 on, every blocking finding was in the recap that the chat added by itself for a poster without an image: a stale list of versions, a card restored from the device, a card replaced after a refusal, a card pushed out of what is stored. The owner's word after the fourth: "When blocked, think of another way it can be done, without keeping on polishing it." v5 removes that recap and reaches the image through what is already released and reviewed.

**Cost of the choice.** The copy's image is made in « Pas à pas », not in the chat: one change of screen. A poster without a version is still not served by the chat. A second tap after a reload can make a second free copy, as « Refaire en … » can.

**Not chosen.** A new poster from the chat's ordinary path with the photo, name and price filled (the brand, subtitle, layout and format are lost): the devil's advocate's alternative. Changing the photo in place (a server change against `input_immutable`).

**The owner may overturn:** the copy's image in « Pas à pas » rather than in the chat; no inspiration image on an existing poster; the French sentences of the card and of the editor's notice.

## ADR-127 — Publishing on the shop's Facebook Page is in scope, as stage 1 (2026-11-21)

**Context.** Automated Facebook publishing was a non-goal (PROJECT.md; ADR-105 kept it out). The research of 2026-11-15 and its review had found the feature possible but its public form blocked by an unknown: Meta's Business Verification for a business in Madagascar. On 2026-11-21 the owner asked how to add publishing and gave his Meta app « Doka studio »: its use case is the Pages API with Facebook Login for Business, it is not published, and `pages_manage_posts` and `pages_read_engagement` are not yet added.

**Decision (the owner: "yes stage 1, free, only link to the post").**
- Publishing a confirmed poster on the shop's own Page is in scope, for shops whose Page admin has a role on the Meta app: Meta allows that without its review.
- It takes no credit.
- The app shows the link to the post. It does not edit or remove a post.
- Any shop without a role (stage 2) waits for Meta's verification and review, and for stage 1 to work.

**Before the implementation, three free proofs with the owner's hands on the Meta app** (the requirements list them): who sees a post made while the Meta app is not published; what a Page admin must do to accept the tester role; one real post of a poster's JPEG.

**Later the same day, after the proofs and the design's three reviews (the owner: "yes to all").** The Meta app is published; no business verification was asked. Approved by him: the five requirement amendments (he says whether a lost publication is on his Page, the app does not look; a post removed on Facebook keeps its link; no Page picture; « a copy of the database cannot use the access » in place of « encrypted »; he chooses among the Pages he allowed); the permission `business_management`, which a Page in a business portfolio needs and which will weigh on Meta's review in stage 2; a new version of the conditions of use, read as released with the feature (his to correct: that point was an either-or). Design v3 is approved under the autonomy grant after reviews r1 (REJECT), r2 (REJECT) and r3 (APPROVE WITH FIXES): v1 was parked and the proofs run before v2, not patched.

**The owner may overturn:** one Page per shop; the caption of « Partager » as the post's text.

## ADR-128 — A publish page: one Facebook post with several posters is in scope (2026-11-21)

**Context.** Stage 1 (ADR-127) publishes one confirmed poster from its final panel; « several images in one post » was out of scope. On 2026-11-21, with T-FB-003 built, the owner asked whether a post could hold several images and a formatted description, and showed a post of the pilot's Page: about fifteen lines, emoji, and « bold » made of Unicode look-alike letters whose accented letters show as empty boxes.

**Decision (the owner's words).** "we will have a dedicated button/menu, while clicked, open a publish page where we choose confirmed poster to use, and add the post description"; the images in the order he chooses; "we can handle the publish page now, no max nb of image, as long as facebook support it; but add the feature for the max nb of image in case we add tier subscription. a post should be publication format only".
- A publish page of its own is in scope, beside the final panel's one-poster button: [requirements](requirements/facebook-post-page.md), R-FB-POST-001 to 007, approved under the autonomy grant on those words.
- The app sets no largest number of images: Meta documents none, so the limit is Facebook's and is said when it refuses. A limit per shop exists as a setting of the operator, none by default, for a later tier. No subscription is built.
- Only posters confirmed in the « Publication » format (4:5) go in a post (my reading of "publication format only").
- The description editor (look-alike bold with readable accents, emoji bullets, the shop's fixed block) is a separate candidate, T-FB-007, not approved.

**Why a page and not more on the final panel.** A post of several posters belongs to no single poster; its choice, order and text need room that a confirmation sheet has not.

**What it costs.** One post takes one call per image and then one that publishes: it cannot be one request as a single poster is, so it needs a design of its own for « never twice, never half ». Four free proofs with the owner's token come before the implementation (the requirements list them): the calls, the order shown, Facebook's own limit, and what becomes of a photo uploaded and never attached.

**The owner may overturn:** the final panel's one-poster button stays; the limit is set with the `shops` command; the description starts empty and keeps the caption's 2 000 characters.

## ADR-129 — One way to publish on the Page: a poster alone is a post of one image (2026-11-21)

**Context.** T-FB-003 built the single poster's publication (`facebook_publications`, `facebook_publish.py`, three routes, the final panel's sheet), reviewed twice and committed the same day, on no remote. The publish page (ADR-128) adds a post of several posters. The page's design v1 kept both, with rules against one being played against the other (`seen_publication` / `seen_post`, in-flight checks both ways); its first review's worst findings were in those rules, and its devil's advocate argued that two records for one act cost two lists, two restore steps and two texts for ever once real rows exist.

**Decision (the lead, under the autonomy grant; the owner's to overturn: the default told to him before was that the one-poster path stays as built).** One model. A publication of one poster is a post of one image. `facebook_posts` and `facebook_post_items` replace `facebook_publications`: migration 0019 converts what 0018's table holds, counts, and drops it; 0018 is not edited, and 0018 and 0019 are released together. `facebook_posts.py` replaces `facebook_publish.py` and keeps its proven parts (the key in the table's own column, `_live`, the shielded task, the 30 s rule on the monotonic clock, the settling retries, the start-up and shutdown rules). The final panel's « Publier sur ma Page » stays: it opens the publish page for that poster alone, with the poster's own caption, so R-FB-PUBLISH-002 to 004 keep their cover. Design: `designs/facebook-post-page.md` v3, approved after three reviews (REJECT, REJECT, APPROVE WITH FIXES) and a devil's advocate.

**Also decided there:** nothing uploaded is deleted by the app (a photo left behind is not shown on the Page); the owner can stop a post while its images are being sent; the draft is kept until its post is published; the request and its key are kept on the device before they leave, and a device that cannot keep them sends nothing.

**What it costs.** T-FB-003's backend and its sheet are rewritten before they ever ran for a shop; publishing one poster goes through two calls to Facebook in place of one (an upload that shows nothing, then the post). To prove before the backend task: that a post of one photo made this way reads as a photo post.

## ADR-130 — How the publish page keeps one post from being sent twice, and what the release checks (2026-11-22)

**Context.** The reviews of T-FB-010 and T-FB-013 found, round after round, races in a second stored object, between two tabs, and in a release rehearsal that counted rows. Each time the cause was removed rather than patched (the owner's rule, memory `blocked-change-approach`). The design `designs/facebook-post-page.md` holds the details; this records the decisions.

**Decisions (the lead, under the autonomy grant).**
- The draft's stamp, made anew at each edit, is the request's `Idempotency-Key`; the request's hash leaves out what the page had seen. No second stored object.
- One tab at a time holds the publish page (a Web Lock, as the chat); a draft that cannot be read is never taken for an empty one.
- The release's rehearsal refuses a table that a pending migration drops while it holds rows; the posts are hashed in `rowid` order. (Migrations 0018 to 0020 are released together, so the live database never holds the old table.)
- `shops after-restore` on posts: the kept row wins; a kept `posting` or `unknown` makes the post `unknown`; the restored file compared with itself makes every `uploading` or `posting` post `unknown`.
- The owner's own choices on the page (2026-11-22): drag by a handle at the row's right end, a bin icon, no « Plus tôt » / « Plus tard » (the gap for whoever cannot drag was told to him once), the description before the images.

**Left:** T-REHEARSE-ORDER (a rehearsal gap from before, in another table).


## 2026-11-22 · Product UX review scope

Use release 05a12ee and its browser captures for the simplification review. Keep the Signal identity and treat a faster path through fidelity review, exact-file confirmation and public-post consent as a presentation change. Recommendations and onboarding requirements are proposals pending owner approval.

## 2026-11-22 · First-poster guide and publishing recovery design

The owner said « continue » after the two requirements were presented for approval. Proceed with design. Use in-context reading help and an optional empty-state invitation; retain the open work surface underneath. Review the repair and confirmed-output flow with an isolated responsive mockup before implementation.

2026-11-22 · The owner’s « next » after the design-approval handoff advances both designs to implementation. Start with the read-only exclusions contract.

2026-11-22 · A repaired batch addition carries the poster ID and the confirmed download URL for one navigation. The locked composer compares both with its fresh candidate before appending, so a newer confirmation cannot silently replace the file the seller chose.

2026-11-22 · Keep the fidelity dialog open while its final-file request runs. Closing it abandons that navigation. A completed server render remains reusable. The explicit review checks the selected visual, shop, revision and format. Opening a saved poster normally retains its primary-format confirmation preference.

2026-11-22 · Preparation opens on Style and leaves Textes and Boutique directly accessible on the same draft. The offer summary uses the saved product input for its source photos and variant, so a reopened draft shows the same offer as a new one. Generation still uses the existing credit and photo-quality confirmation.

2026-11-22 · Keep an unfinished title in the editor field, like an invalid price, so the shop can correct it while other valid edits still save. Replay an already submitted chat request using its recorded format and key even if the current product cannot be read. A fresh generation waits for the source product.

2026-11-22 · Accueil’s review action and the library’s confirmed-file action use separate read-only opening paths. A waiting alternative and a current confirmed PNG can coexist, so the existing protected listing exposes its current-file flag independently of the displayed review state. Older list responses retain the confirmed-state fallback.

2026-11-22 · The first-poster guide opens a native modal on the existing shop route and keeps its step in page memory. A drawer launch returns focus to the menu toggle. Contextual entries on the guided editor and Facebook composer open the corresponding instruction without moving or saving the underlying work.

2026-11-22 · The console lists unresolved money requests first, tagged with the saved operation, shop and reference. Inspecting the row opens the existing shop recovery controls. Reads and layout changes use the existing request and financial confirmation rules.

2026-11-22 · In release verification the owner identified entering the product or choosing a format as the first difficult point. Keep Publication as the existing default, explain its destinations before generation, and keep optional shop identity available on demand. This changes presentation under D-JOURNEY-002/007. The price, photo attestation, generation charge and final checks retain their existing rules.

2026-11-22 · Owner approved a single review of the current finished PNG. Opening its private preview carries no approval. Download or preparation of a Facebook post accepts the shown product and file together. Public posting retains its own confirmation.

2026-11-23 · Following the owner’s successful trial and feedback on the hidden confirmation, expose the existing exact-file confirmation as an optional library-only action. Name confirmation on the download and Facebook shortcuts. Keep all actions on the same reviewed PNG and keep public send in the composer.

## ADR-131 — The seller's kit: saved choices that the seller's words may replace; six decisions taken in the owner's place (2026-11-23)

**Context.** The owner asked for a walk of the app as a new seller ([report](reviews/user-walk-2026-11-23.md)), then, before any fix: « think the platform as a framework the user can use to speedup the creation: a title font he can use, some scene model, etc., but they could still free prompt if that is what they want », then « Proceed in the order you see fit; paid call still allowed; you can continue till there is a testable app. When in doubt, take the place of the user and pick the one that is the most likely to be the best solution. » The walk showed that Message keeps a name, a price and a style and drops the rest of a first message without saying it, while the same free sentence is taken from the second image and gives the best result; that a reference poster works through a saved style and not as a raw image; that a seller cannot show his own warranty line.

**Decision.** `requirements/seller-kit.md` (R-KIT-001 to 012) is approved for design by the lead under this grant. A poster is the product and the shop's saved choices (a scene model, a title style, the shop's own lines); what wins is this message, then this poster's choices, then the shop's kit, then the house defaults.
1. The kit is the shop's own, beside the house models. Models published by the operator: later.
2. Message is the way to create that the app puts first; « Pas à pas » stays as the detailed way and the place to correct.
3. The title stays drawn by the image model (ADR-044). The shop's own lines are drawn the same way, from the seller's exact words, and are checked in the review. This replaces the lead's first proposal (lines laid over the picture): the walk's best posters are the ones the model lettered, the contact already works this way, and no new layer of the document is needed. The app never writes, completes or translates a line.
4. Free words may change the scene, the staging, the layout and what the picture shows; never the product, a price, or a commercial line.
5. A photo is a product photo unless the seller marks it as a model of style (today the second photo of a message is a model by its position).
6. « Publier » keeps the description first (the owner, 2026-11-22).

**Not decided here.** Several products in one poster (a paid trial first), a visual first-use guide, a shorter first screen of the conditions.

2026-11-24 · Seller's kit (ADR-131), decisions taken while building it, in the owner's place. A line of the shop holds no amount, no number and no discount; a delay passes (« Livraison 24-48h »). Without a unit a number is a price only from 10 000, never when it starts with 0, never before another currency or a measure (« 20000 mAh »): a short list of measures for bare numbers only, against ADR-095's no-list rule, because a phone and audio shop writes them every day. A poster draws exactly the lines its recap showed (the request carries them; the server refuses when the shop's lines changed). The reader is not sent the shop's lines. A request that is not an advert gets one sentence and no paid step. The action « Tout est conforme, approuver » left the editor: a version is confirmed only with its file. The three « dessiner dans l'image » boxes are two (texts; price: ADR-044 stays). No route creates a model from « Mon kit »: a photo marked in a message or « Garder cette scène comme modèle » do. The kit's defaults are per device and change only by the seller's own choice. On a first image the owner's scene words lead the scene sentence (the second walk showed the house style winning otherwise). Reviews: design r1 and a devil's advocate, backend code r1, frontend code r1 and r2 (`reviews/seller-kit-design-*`, `reviews/t-kit-*`).

2026-11-24 · A correction by message is an instruction to the image model (T-KIT-020, the owner's trial « Aura studio on the center »). Before, the owner's request reached the model only inside the data block labelled « not additional instructions », against « preserve its composition »: a request that moves a product lost by construction. Chosen: say the request as an instruction that may move, swap, resize or replace what the base shows, keep the rest of the base; lead the scene sentence with the owner's words on a correction too; read a brand or model name in his words as one of the products. Not chosen now: a name per photo of a pack (several products as a feature, T-KIT-019) and a check that a paid correction changed the picture. The byte-for-byte capture of the prompts stays the reference: its test puts the two reworded sentences back.

2026-11-24 · The owner, after T-KIT-020: « For that case, we let the image model decide, so we don't block any user prompt ». When the seller's words name something the app does not know (a product of a pack, « Aura studio »), they go to the image model as written and it decides what they mean. The chat asks no question and refuses nothing for that reason; no name or mark per photo of a pack is built. Unchanged: the words that set a price, a discount or a commercial claim keep their own fields and their screen (ADR-131, decision 4), and the advert guard (R-KIT-013).

2026-11-24 · A saved model goes to the image model with its own poster (T-KIT-021; replaces the part of D-KIT-006 that said « never the raw image »). The owner's reference, three products each in its own card, gave its colours only on the deployed build (the image was sent, but the prompt asked for its backdrop and light alone) and its colours and lettering only with the kit's look (words alone, layout described: not built). Chosen, in line with his « we let the image model decide »: the model's words stay (they are what « Mon kit » shows and what sets the lettering), and its poster is sent with every first image made with it, with a sentence that asks for its composition. Done on the server, in `request_scene`, so that Message, the kit's chip and « Pas à pas » behave the same. A model kept from a finished poster sends that poster, product and words included: the prompt tells the image model to ignore them; not judged on a real image yet. A refinement is unchanged: its base image carries the layout. Also: past three product photos the next attached image is taken as the style model (before, a pack of three could take none), and the chat's composer takes a pasted or dropped image.

2026-11-24 · First trials on the deployed image model, and what they changed (T-KIT-018). Until now every paid proof of this track was on `gpt-image-2` at high, the local default; the owner asked for `gpt-image-2.5-flare` in the tests (medium, as deployed). On Flare: (a) a correction by message came back identical to its base with the wording of T-KIT-020 (the request named in a rule, its words in the data block). Chosen: the request is the first line of a correction's prompt, quoted in the owner's own words, with « an image that looks the same as image 1 has failed ». The words are still screened by `screen_adjustment` (no amount, no instruction) and stay in the data block too. Proved once on the same poster. (b) The layout of a model's poster was followed in 2 of 3 first images: not changed. (c) An image with three product photos and a model costs about 0.06 USD on Flare, not the 0.03 of the benchmark with one photo. Also decided in the owner's place while fixing the walk's findings: a poster already on the Page keeps its place on « Publier », the button says « Publier à nouveau… » (a second post of the same poster is allowed, it must be said); the remembered accent colour is kept only with its look.

2026-11-24 · The shop's logo is drawn by the image model when the title is (T-KIT-022; the owner: « Try giving the logo to the model so it can draw it in the comp, placement to the choice of the user », then « go »). Before, the logo was the shop's own file laid over the finished image at a planned place, pixel for pixel; the deployed image model does not keep the title inside its planned area, so the two met, and no wording moved the title. Chosen: the logo is one more input image, drawn in the composition where the image leaves room or where the owner's words say; it becomes a thing to check in the review, as the title and the price are, and the export refuses a logo that is no longer the poster's. What is given up: the logo is no longer an exact copy; on five paid images it came out exact once the prompt asked for the whole of it with its words, and lost its background or its name before that. Unchanged: a poster whose title is a layer keeps the logo as a layer; the round seal keeps its disc. Not chosen: moving the laid logo to the footer's left (Claude's first proposal). Scope taken while building: Message asks for the drawn logo (`headline.draw_logo`); « Pas à pas » does not, because its logo is a layer the seller places in a corner or the footer, with a guard and an exact rendering that its tests pin (translucent logos included); making the editor ask too is T-KIT-024, the owner's to decide. Decided the same night by the owner (« it should draw too »): « Pas à pas » asks for the drawn logo as well; the place it lets the seller choose becomes the place told to the image model, and the exact-file guarantee of the laid logo is given up there too. The rules of a laid logo stay in the code for the versions made before.

## 2026-11-25 · Direct creation

Under the owner's end-to-end delivery instruction, free creation uses the original prompt with a switchable visual fallback, up to three content photos plus a reference, feed output and consecutive credit-funded edits. Shares the job ledger, immutable renders and publication path. The reference and explicit words have precedence over visual defaults.

2026-11-25 · The free way of creating lives in the chat's shell, as a third way beside « Message » and « Pas à pas » (D-FREE-05). The owner asked for a review of the first delivery and of its screen « to make sure it doesn't diverge »; the review found a form page with its own words for things the product already names, and he answered « go ahead » to the rebuild. Kept: the whole server side of the first delivery. Changed: the page (the chat's classes and wording, one review panel, « Modifications »), the entry (a segment « Libre », remembered as the two other ways are; the side-menu item and the two links are gone), the failed image (the app's own sentences instead of « code : refused … donnez ce code à l'administrateur »), and a correction no longer sends the reference again (the previous image carries its layout; « match its composition » argued with « preserve the rest »; one input image less to pay). Taken in the owner's place while building: the reference is called « Modèle de style » here too; the review lists the seller's requests in his own words instead of one tick box, and the buttons « Confirmer et … » are the consent, as in the product; images are taken with the first request only. Left as delivered, his to decide: the seller's words go to the image model with no screen (an instruction hidden in them, or « -50 % », is sent as written; the prompt only asks the model to invent nothing), and no automatic reading checks the drawn amounts. Not built: sharing to another application from this page.

2026-11-25 · A correction of a free creation is given the first version as a clean reference (D-FREE-06). The owner, on the released build: « the product image seems to degrade throughout the generations ». Cause: each correction redraws the whole picture from the previous one, and the loss adds up; the image service has no setting against it. Trial on his word, 27 images on Flare medium, USD 0.7468: the chain as built reproduced the grain at version 9; the previous version with version 1 as a rendering reference stayed clean and kept the layout, the texts and the price; redrawing from version 1 with every request stayed clean but wrote « 125 000 ar » for « 1 250 000 ar » and changed the features, so it is not chosen. Also changed: a correction edits the image model's own file, not the published PNG resized from it. Cost: one more input image per correction, about 0.012 USD, the same credit. Known and not settled: a correction of something the first version shows (the weight of the name's letters) was followed in part only, on one request. Not changed: the guided poster's corrections (« Message », « Ajuster la scène ») chain the same way, with the product's photo sent each time and twelve images at most; no complaint there, no trial.

### 2026-11-26 — Creation UX and poster-diversity research (T-UX-RESEARCH-20261126)

Owner requests UI/UX/motion research only, with no application code edits; paid image trials are authorized. Owner subsequently explicitly allows use of the development `.env` (configuration loaded without printing secrets). Research recommendation, **not approved architecture**: Libre primary, optional simplified Pas à pas, retire guided Message for new work after feature parity; model-drawn identity with exact kit facts and legacy poster compatibility. Findings and alternatives: [research report](reviews/ui-ux-generation-research-2026-11-26.md). No requirements/design gate bypass or deployment authorization.

### 2026-11-26 — Research direction accepted; no invented shop logo

Owner: “Sound good to me, but for the shop logo, if none is provided, we don't invent a logo”. The research direction is accepted; the logo rule is explicitly approved as R-FREE-07. No provided/selected shop logo means no invented shop mark, including from a shop name or style reference; a requested name may be plain text. This supersedes the research's “unless explicitly requested” exception. No application implementation or technical design is approved by this documentation update; retain the workflow gates for the broader redesign.

### 2026-11-26 — Unified creation delivery authorized

Owner explicitly requests design then implementation without further questions, authorizes paid tests and browser checks each iteration. Requirements `unified-creation.md` formalize accepted scope under that authorization. Choose a shared free generation pipeline for Libre and optional guided preparation; retain old guided documents in the legacy editor instead of destructive conversion. No deployment authorization. No invented shop logo remains mandatory.

- 2026-11-26: Failed Libre retries restore the server-owned job input snapshot via scoped retry_job_id, including identity even after the shop kit changes; avoid reconstructing paid requests from current UI state. Reduced motion uses static waiting indicators.

- 2026-11-26 paid finding: a quality-anchor correction reverted 95,000 Ar to the original 85,000 Ar. Free documents now retain the original brief plus twelve latest accepted instructions, scoped to the selected version branch, and repeat their precedence to the model. Legacy documents recover the chosen base’s last instruction. No OCR/price guarantee; visual review remains required.

- 2026-11-26: Free correction idempotency includes only supplied fields so omitted reference/identity fields differ from explicit removal. Start hashing retains the legacy words/photos/reference/default_style defaults for compatible replay after an upgrade.

- 2026-11-26 delivery verified: 22 paid browser outputs, four failed iterations retained as evidence, exact-copy/card-count and final accepted-text precedence repeats passed. No model fine-tuning or automatic OCR assurance claimed. User reviews each raster result; no logo supplied means no shop mark requested. No deployment.
