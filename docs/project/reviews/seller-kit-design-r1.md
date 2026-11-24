# Seller kit design review, round 1 (2026-11-23)

Reviewed: `docs/project/designs/seller-kit.md` (Draft v1) against `requirements/seller-kit.md` (R-KIT-001 to 012), ADR-131 and
the code at `HEAD` (c044170). Read-only. Other sessions were editing `api.py`, `ShopPublish.vue`, `ShopAccount.vue`, `publish.ts`,
`facebook.ts` and `dashboard.ts` during this review, so line claims were checked with `git show HEAD:`. The work-in-progress
edits were not reviewed.

**Verdict: APPROVE WITH FIXES.** The design approach holds. The cited code says what the design says it does (see "Claims
checked" at the end). The 10 SHOULD FIX items below are local changes and need no new architecture. Fix them before the
tasks go into TODO.md.

---

## Findings, most severe first

### 1. SHOULD FIX: the shop-line screen lets amounts and discounts through (D-KIT-005, "Rule of a line")

- **Evidence.** The line rule ([design:148](../designs/seller-kit.md)) refuses currency words, `€`, `$` and "four digits and more".
  - It does not refuse `250k`. The scene screen catches that form with `\d\s*k\b` ([plans.py:60](../../../backend/src/affiche/posters/plans.py)).
  - It does not refuse `%`. The existing term list catches `%` ([prompts.py:143-147](../../../backend/src/affiche/visuals/prompts.py)).
  - "Four digits" does not say whether digits separated by spaces count (`5 000`, `034 12 345 67`). The prompt tells the model that the price label is "the only price … with no other amount, discount, old price or currency sign anywhere" ([plans.py:452](../../../backend/src/affiche/posters/plans.py)).
- **Consequence.** These lines pass: « Livraison 5k », « -20 % ce week-end », « Frais 5 000 ». The image model then draws them beside a price that the app promises is the only exact amount. The prompt now contradicts itself. The review's `text_price` check does not cover this.
- **Fix.** `screen_shop_line` refuses the same things as `find_commercial_terms`, except its word list (`garanti|livr|paiement|…`):
  - currency words;
  - `€ $ %`;
  - four or more digits, with or without separators;
  - `\d\s*k\b`.
  Add these rows to `test_a_shop_line_with_an_amount_is_refused`: « Livraison 5k », « Livraison 5 000 », « -20 % », « 034 12 345 67 ».

### 2. SHOULD FIX: the image draws the profile's lines at request time, not the lines the recap showed (D-KIT-005, "Per poster")

- **Evidence.**
  - `request_scene` "reads the profile's lines in its own transaction" ([design:162](../designs/seller-kit.md)).
  - The recap's lines come from `ChatAdapter.state.shop.lines` ([design:128](../designs/seller-kit.md)), which comes from App.vue's `profile`.
  - App.vue reads `profile` once, at load ([App.vue:1274](../../../frontend/src/App.vue)), and adopts it again only after its own saves ([App.vue:1281](../../../frontend/src/App.vue)).
  - The contact works differently: it comes from the poster's snapshot ([visuals.py:249-254](../../../backend/src/affiche/posters/visuals.py)).
  - `Headline.lines: Literal[True]` puts no line text into the idempotency digest.
- **Consequence.** The owner edits the lines in « Mon compte » on a second device or tab. Back in the first tab he taps the recap: the credit pays for lines he never saw. It is a paid request whose text was not shown before the tap (ADR-097/098 spirit, R-KIT-004).
- **Fix.** Make `Headline.lines` carry the lines the client showed: `list[ShopLine]` (at most 3) in place of `True`, still `exclude_if` None. Before `enqueue`, `request_scene` refuses with `409 shop_lines_changed` unless the list equals the profile's lines. The digest then covers the text. A refinement keeps the lines of its base, as designed.

### 3. SHOULD FIX: list bounds on the reader's new fields fail the whole paid read (D-KIT-004, "Reader schema")

- **Evidence.**
  - `Fields` gains `shop_lines` (at most 3) and `unused` (at most 3, `text` at most 80) ([design:109, 114](../designs/seller-kit.md)).
  - `wire_schema` removes `maxItems` and `maxLength` from the schema the model sees ([plans.py:528-539](../../../backend/src/affiche/posters/plans.py)).
  - The answer is then validated against the bounded model ([planner.py:118-120](../../../backend/src/affiche/posters/planner.py)).
  - A failed validation becomes `invalid_read` with `complete=True`, which gives the « unclear » card at full cost ([reads.py:673](../../../backend/src/affiche/posters/reads.py)).
- **Consequence.** The walk's own first message (warranty, delivery, red background, flames, wooden table) can easily produce four unused parts. The owner pays for the read and gets « Écrivez le produit et son prix. ». The same applies to `shop_lines` in `poster_fields()`.
- **Fix.** Leave the wire types unbounded (`list[str]`, `list[Unused]`, `text: str`). `build` cuts them: the first 3 items, 80 characters. Today `product_name` is already handled this way: unbounded in `Fields`, checked in `build`. Add one test row with four unused parts.

### 4. SHOULD FIX: `get_profile` returning `lines` breaks every poster creation (D-KIT-005, "Data")

- **Evidence.**
  - The design makes `store.get_profile` return `lines` and keeps `BrandSnapshot` unchanged ([design:146, 160](../designs/seller-kit.md)).
  - `initial_document` builds `BrandSnapshot(**profile)` from that dict ([store.py:174-176, 190](../../../backend/src/affiche/posters/store.py)).
  - `Model` is `extra="forbid"` ([models.py:17-18](../../../backend/src/affiche/posters/models.py)).
- **Consequence.** `POST /api/creations` raises a validation error (500) for every shop. The first test run catches it, but the design text leads straight to it.
- **Fix.** `initial_document` also pops `lines`. State this in D-KIT-005.

### 5. SHOULD FIX: « Confirmée » would name a version that was only approved; « approuver » remains (D-KIT-001, "Words"; R-KIT-001)

- **Evidence.**
  - The review still offers « Tout est conforme, approuver » ([App.vue:3118](../../../frontend/src/App.vue)). It calls `decide('approve')`, which sets the version to `approved` without any confirmation ([visuals.py:422-441](../../../backend/src/affiche/posters/visuals.py); [test_api.py:1103-1104](../../../backend/tests/test_api.py) then expects the list state `approved`).
  - The design maps this version status to « Confirmée » (App.vue:604, 2951) and the dialog heading to « Version confirmée » (App.vue:3095).
  - The same dialog then says « Vérifiez le cadrage, les textes et le prix sur le fichier final » ([App.vue:3103](../../../frontend/src/App.vue)), and the list calls the poster « À confirmer ».
  - [browser_smoke.py:824-825](../../../frontend/tests/browser_smoke.py) walks exactly this path.
  - « approuver » stays at [App.vue:2840](../../../frontend/src/App.vue) and 3118. [chat.ts:316](../../../frontend/src/chat.ts) already has the same mismatch.
- **Consequence.** One version is « Confirmée » in the editor while its poster is « À confirmer » and has no file. R-KIT-001's "one word" is only partly met.
- **Fix (smallest).** Remove « Tout est conforme, approuver » and its line "approuver cette variante pour plus tard". The walk already lists the action as unused (M10, simplification 8). Then `approved` comes only from a confirmation. Reword App.vue:2840. Update browser_smoke.py:824-825, which belongs to T-KIT-006.

### 6. SHOULD FIX: migration 0021 has no rehearsal contract, and the tests pinned to head "0020" have no owner (D-KIT-005, "Data"; T-KIT-002)

- **Evidence.**
  - `affiche.rehearse` refuses any pending migration that does not state `PRESERVED` and `ADDED` ([rehearse.py:195-198](../../../backend/src/affiche/rehearse.py)).
  - Earlier migrations that widened `shop_profile` state them ([0017:23-29](../../../backend/migrations/versions/0017_terms_acceptance.py), [0019:48-50](../../../backend/migrations/versions/0019_facebook_posts.py)).
  - These tests assert that the head is "0020":
    - test_db.py:122, 321, 404, 476, 559, 609, 661, 731, 822, 834, 890;
    - test_reads.py:111;
    - test_phone_session.py:68, 85;
    - test_api.py:891.
  - T-KIT-002 owns none of these files except test_api.py, and test_reads.py belongs to T-KIT-003.
- **Consequence.** The release gate prints REHEARSAL FAILED. `uv run pytest -q`, which the design requires for every backend task, fails after T-KIT-002.
- **Fix.**
  - 0021 declares `PRESERVED = {"shop_profile": <the 0019 tuple + "post_image_limit">}`.
  - 0021 declares `ADDED = {"shop_profile: no line yet": ("SELECT count(*) FROM shop_profile WHERE lines_json <> '[]'", [(0,)])}`.
  - T-KIT-002 owns test_db.py and test_phone_session.py, and the head line of test_reads.py.
  - Optional: `CHECK (json_valid(lines_json) AND json_type(lines_json) = 'array')`.

### 7. SHOULD FIX: the « Mon compte » merge and save do not cover the lines (D-KIT-005, "Where they are typed"; T-KIT-009)

- **Evidence.** ShopAccount works field by field over `name`, `contact` and `logo_asset` only:
  - `fieldNames` ([ShopAccount.vue:11](../../../frontend/src/ShopAccount.vue));
  - `dirty`, which compares by reference ([ShopAccount.vue:19](../../../frontend/src/ShopAccount.vue));
  - the merge after a conflict ([ShopAccount.vue:40-49](../../../frontend/src/ShopAccount.vue)).

  `draft = { ...saved }` is a shallow copy, so the draft and the baseline would share one lines array.
- **Consequence.**
  - Editing a line changes both objects, so the form never becomes dirty and « Enregistrer le profil » stays disabled.
  - After a `revision_conflict` (for example, the chat kept a line meanwhile), the merge takes the saved lines and drops the owner's line edits. The page still says « Vos modifications sont conservées ».
- **Fix.** Add `lines` to `fieldNames` as one field. Copy and compare it by value (`JSON.stringify`) in `dirty` and in the merge, and show it in the « modifié sur les deux appareils » choice.

### 8. SHOULD FIX: the task lanes are not file-disjoint, and some tasks cannot pass `run build` alone (Tasks)

- **`api.ts` has no owner.** The `Profile` type and `writeProfile` ([api.ts:310-315](../../../frontend/src/api.ts)) must gain `lines`. Both T-KIT-007 (lane D: the adapter keeps lines) and T-KIT-009 (lane B: « Mon compte ») need this. `writeProfile` must send `lines` only when the caller passes them. App.vue's `profile` will hold `lines` after `adoptProfile`, and the design says App.vue's `saveProfile` "erases nothing".
- **T-KIT-005 breaks the type check of App.vue.** `npm run build` runs `vue-tsc --noEmit` ([package.json:8](../../../frontend/package.json)). Adding required members to `ChatAdapter.state` (`drawn`, `Shop.lines`; [chat.ts:198](../../../frontend/src/chat.ts)) makes App.vue's `chat` object ([App.vue:2298-2300](../../../frontend/src/App.vue)) fail until T-KIT-007. So T-KIT-005 and T-KIT-006 cannot meet "run build passes". Fix: the new adapter members are optional until T-KIT-007, as `waiting?` already is.
- **Half of D-KIT-007 item 1 has no task.** The ChatView half (set `adapter.focus`, the placeholder « Dites ce qu'il faut corriger. ») is in lane C. T-KIT-005 does not list D-007 1, and T-KIT-006 owns only App.vue. Fix: add it to T-KIT-005.
- **T-KIT-006's verify depends on T-KIT-005.** T-KIT-006 verifies `guide_browser.py`, whose role assertions (`:144, 181`) follow D-KIT-006 (T-KIT-005). But T-KIT-006 depends only on T-KIT-002. Fix: make T-KIT-006 run "after 002, 005", or move those lines to T-KIT-007.

### 9. SHOULD FIX (slice 2): the idempotency of `POST /api/looks` breaks on a retry (D-KIT-011)

- **Evidence.**
  - The route reuses `request_look` with a carrier poster and revision that the server chooses ([design:263](../designs/seller-kit.md)).
  - `request_look` passes `revision=` to `mutate` ([looks.py:78-90](../../../backend/src/affiche/posters/looks.py)), and `mutate` puts the revision into the key's digest ([store.py:48](../../../backend/src/affiche/posters/store.py)).
  - `enqueue` checks the revision ([jobs.py:108](../../../backend/src/affiche/posters/jobs.py)).
- **Consequence.**
  - If any edit or new poster changes the carrier before a lost answer is retried, the same key gets `409 idempotency_reused` instead of a replay.
  - If the route reads the carrier outside the transaction, a concurrent edit gives `revision_conflict` on a page that shows no poster.
- **Fix.** Choose the carrier and its current revision inside `apply`, and call `mutate` with `revision=None`. Add a test: a retry with the same key after the carrier is edited replays the first answer.

### 10. SHOULD FIX: the new-poster name guard can repeat the same question in a loop (D-KIT-007, item 3)

- **Evidence.**
  - When a word of the name is not in the message, the reader's name is refused and the card is `ask_product` ([design:209](../designs/seller-kit.md)). Its sentence is « Quel est le produit ? Marque et modèle. » ([api.py:142](../../../backend/src/affiche/api.py)).
  - `name_words` splits on non-alphanumeric characters ([plans.py:16-19](../../../backend/src/affiche/posters/plans.py)).
  - So two common reader habits fail the guard: adding the brand's usual word (« samsung a55 » becomes « Samsung Galaxy A55 ») and splitting units (« 256go » becomes « 256 Go »).
- **Consequence.** The owner types the same name again, the reader adds the same word, and he gets the same question again, paid each time. Elsewhere the design rules out repeating a question without saying why (R-KIT-002/004).
- **Fix.** On a guard failure, drop the unknown words from the reader's name and keep its order and capitals. Ask only when nothing is left, and name the dropped word as `card_word_unknown` does.

---

## Suggestions and questions (no decision changes)

### 11. SUGGESTION: D-KIT-002 rule 2 has edges the table does not cover

| Message | Today | With the design |
|---|---|---|
| « 1 250 000,00 » | no candidate | candidate 1 250. The run stops at the comma token. Fix: skip a run whose next token contains a digit, as the `before` guard does on the other side. |
| « TV 4K 2 500 000 » | — | candidate 4 000 from « 4K » |
| A phone number written as one token (« 0341234567 ») | — | it becomes a price candidate |

Also:
- The design does not say what happens with 5 or more candidates. Today it would give the false « Je ne vois pas de prix ».
- "Judged by rule 1" on design line 61 should say "by today's unit rule".
- Say whether rule 2 runs when only `k` amounts were found.

Add these rows to `test_candidate_amounts`.

### 12. SUGGESTION: R-KIT-004 is partly met

The list of changed fields (`name`, `price_ar`, `style`, `scene_fr`) leaves out `identity`. Identity is a recap choice, and a later read can flip it without a word. Add it to the list.

### 13. SUGGESTION: a weak injection screen for the lines

`screen_shop_line` uses `_INSTRUCTIONS`, which only matches the English « ignore » ([plans.py:26](../../../backend/src/affiche/posters/plans.py)). The lines sit in an instruction line of the prompt, not in the descriptive data. Use `_INJECTION` ([plans.py:51](../../../backend/src/affiche/posters/plans.py)), as `screen_adjustment` does.

### 14. SUGGESTION: a Page that needs reconnection (D-KIT-008, "The review")

The read gives three states: connected, none, unknown. A Page with `state: 'reconnect'` ([facebook.ts:13](../../../frontend/src/facebook.ts)) would get « Confirmer et préparer la publication ». It should get the connect button, as for "none".

### 15. SUGGESTION: the cost of the D-KIT-001 query

The new clause is a correlated EXISTS for each poster. No index serves `poster_jobs(creation_id)`: `poster_one_image` is a partial index. No index serves `confirmations(creation_id)` either. The comment at [api.py:554-557](../../../backend/src/affiche/api.py) promises "once per query, not once per poster". This is cheap at pilot scale. Either add `CREATE INDEX confirmations_creation ON confirmations(creation_id, confirmed_at)` in 0021, or update the comment.

### 16. SUGGESTION: « Vos données » (D-KIT-006, D-KIT-010)

- A Message style photo now goes to Anthropic, not to OpenAI.
- A poster's own scene goes to Anthropic when it is kept as a model.
- If the reader receives the shop's lines, Anthropic receives them too.

[donnees.html:60, 63-64](../../../frontend/public/donnees.html) should say all three. The design updates only the lines.

### 17. SUGGESTION: an older bundle with the new server

- `required_checks` adds `text_lines`, so an older tab cannot confirm a version that has lines (`fidelity_incomplete`).
- Its `restoreHeadline` drops the lines on a word change.

Both are acceptable if the `fidelity_incomplete` sentence tells the owner to reload. Check it.

### 18. SUGGESTION: the look wait times out after 90 s (D-KIT-006)

After the timeout the job still runs. « Réessayer » posts a new look, because page memory keeps the look and not the job. The result is a second brief and « Style 4 (2) ». Keep the job id for each asset and wait on it again.

### 19. QUESTION: the scene-word guard is all or nothing (D-KIT-003)

One linking word that the reader adds drops the whole scene. The owner is then back at the walk's finding 2, now with a sentence. T-KIT-010 should count the guard drops separately. If they are frequent, the fallback is a decision to take on that evidence.

### 20. QUESTION: the lines' capitals (R-KIT-005, "shown only as typed")

The word guard ignores case, so the reader can change the capitals of a line before it is kept. Should the kept line be rebuilt from the message's own tokens?

---

## Criteria only partly met

| Criterion | What is missing | Finding |
|---|---|---|
| R-KIT-001 | One word and one meaning | 5 |
| R-KIT-002 | 5 or more candidates; false candidates | 11 |
| R-KIT-004 | « never changes without being said »: identity | 12 |
| R-KIT-004 | What the recap showed against what is drawn | 2 |
| R-KIT-005 | "only as typed" | 20 |
| R-KIT-005 | The lines a poster draws are the ones the recap showed | 2 |
| R-KIT-005 | « never an amount » | 1 |
| R-KIT-008 | A Page that needs reconnection | 14 |

When the Facebook read fails ("unknown"), the design keeps today's button. That is an acceptable fallback.

R-KIT-003, 006, 007, 009, 010, 011 and 012 have designs that satisfy them. R-KIT-012's "for all his posters" is per device, as open point 1 decided.

## D-KIT-001 SQL (question 4)

The clause is correct against the schema:
- `{SCENE}` reads the outer `v`, which is bound in both `attention()` and the list.
- Both stamps come from `db.utc_now()`, with fixed-width microseconds ([db.py:52-54](../../../backend/src/affiche/db.py); [service.py:132-139](../../../backend/src/affiche/posters/service.py); [exports.py:209-212](../../../backend/src/affiche/posters/exports.py)), so text order is time order.
- `max(a, b)` with COALESCE to `''` is right.

Cases:
- **A copy** owns none of its source's jobs, so only clause 1 applies to it. Unchanged.
- **A poster with no confirmation:** only versions newer than the shown scene count. This is a deliberate change: a poster with an older undecided version becomes « À confirmer » instead of « À vérifier ».
- **Several formats:** the comparison uses the primary format's scene and the latest confirmation in any format. A Story confirmation can therefore hide a Feed version that waits from before it. This fits the design's rule "it was there when he confirmed".
- **Tests:** [test_api.py:1076](../../../backend/tests/test_api.py) and [test_shop_dashboard.py:161, 185](../../../backend/tests/test_shop_dashboard.py) stay green. The `at_now` fixture patches only `affiche.api.utc_now`, not the visuals' stamps.

## Claims checked

These hold at `HEAD`, within a few lines:
- **D-KIT-001:** `api.py:560-562, 669, 1076`; the words at `dashboard.ts:8`, `App.vue:604, 2944, 2951, 3095`, `ChatView.vue:63, 604`, `chat.ts:316`.
- **D-KIT-002:** `reads.py:102-167, 143-146, 43-44`; `test_reads.py:128-138`. The five moved rows work as described under the stated rules. Every other `REJECTED` row stays without a candidate: each is followed by a unit or falls below 1 000.
- **D-KIT-003:** the chain of `kept_adjustments` reads the first scene's `payload["adjustments"]` ([visuals.py:55-65](../../../backend/src/affiche/posters/visuals.py)); `request_scene` hashes `model_dump(exclude_none=True)`; `exclude_if` exists in pydantic 2.14.3 and is already used.
- **D-KIT-005:** `screen_headline` and the term list; `card_refused`.
- **D-KIT-006:** `looks.py:78-90`; `service.py:37-40`; `poster_jobs.creation_id NOT NULL`; `nextRole` at `chat.ts:99-104`; the adapter's `start` at `App.vue:2303-2312`.
- **D-KIT-008:** `ShopPublish.vue:255-256, 367-393, 639, 707`; `ShopAccount.vue:124-138`; `App.vue:3004, 3036`.
- **D-KIT-012:** `plans.py:306-307, 387-388`; `visuals.py:351-356`.

## Not checked

- Nothing was run: no tests, no build, no smoke, and no paid call.
- The reader's real behaviour with the new rules is T-KIT-010's measurement.
- The placement of the lines by the image model is open point 2.
- The work-in-progress edits by other sessions were ignored.
