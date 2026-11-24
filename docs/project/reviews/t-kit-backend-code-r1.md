# T-KIT-001, 002, 003 backend code review, round 1 (2026-11-23)

Reviewed: the uncommitted backend diff (`git diff -- backend/`) and the untracked
`backend/migrations/versions/0021_shop_lines.py`. I checked them against
`designs/seller-kit.md` v3 (the two tables at the top, D-KIT-001 to 005, D-KIT-007 and "Contracts as built") and
`requirements/seller-kit.md` (R-KIT-001 to 005, 007 and 013). The review was read-only. I did not review the frontend.

I ran only targeted commands from `backend/`:
- `uv run pytest tests/test_reads.py tests/test_plans.py -k "<the new tests>"`: 174 passed.
- Three throw-away probe scripts that call `candidate_amounts`, `screen_shop_line`, `build` and the new models directly.
  They are in the session scratchpad, not in the repo.

I did not run the whole suite.

**Verdict: APPROVE WITH FIXES.**
- No credit and no job can come from a refused new check.
- Every old request body keeps its hash.
- The migration and its rehearsal contract are correct.
- `TO_REVIEW` is correct for copies and for a poster with no scene, and it stays inside the creation's shop.

The five SHOULD FIX items are about which amounts the server accepts as candidates and what the line screen lets
through. Each one is a small local change with a few test rows. None of them can spend a credit by itself: the owner
still sees the amount, or the line, before he pays.

---

## Findings, most severe first

### 1. SHOULD FIX: the tail of a phone number can become the only candidate amount

- **Where.** `reads.py:223-226` (rule 3, bare runs).
- **What goes wrong.** `_cut` runs before the leading-zero test.
  - `_cut` drops every token except the last one when that token has 4 or more characters.
  - The test `span[0][0] == "0"` then looks only at the token that is left.
  - `_alone` accepts that token, because the token before it is a pure number.
- **Failing scenario.**
  - `candidate_amounts("Casque JBL, contact 034 1234567")` → `[1234567]`.
  - `candidate_amounts("Casque JBL 032 12 34567")` → `[34567]`.
  - Neither message holds a price. The card asks « Le prix est-il 1 234 567 Ar ? » and shows one button, with the wrong
    amount.
  - With the paid reader: if it returns `1234567`, `_price` accepts it and the recap shows that amount.
  - With the stub: `stub_read` takes the only candidate as the price.
  - R-KIT-002 says "never when it starts with 0". The intent was to cover phone numbers.
- **Smallest fix.** Test the run's first token before the cut: `or tokens[first][0] == "0"` in place of
  `span[0][0] == "0"`.
  - `"Casque JBL 034 12 345 67 250000"` then gives no candidate. The app asks for the price, and no amount is wrong.
- **Rows to add to `REJECTED`.** `("Contact 034 1234567", 1234567)` and `("JBL 032 12 34567", 34567)`.

### 2. SHOULD FIX: in « 1 200k », the server reads only 200 000

- **Where.** `reads.py:205-211` (rule 2, the thousands token).
- **What goes wrong.** A `k` token is "never grouped with a neighbour". `_alone` accepts a pure digit token before it
  (it treats that token as a number of the name).
- **Failing scenario.**
  - `candidate_amounts("Prix 1 200k Ar")` → `[200000]`.
  - `candidate_amounts("Casque 2 500k")` → `[500000]`.
  - The owner wrote 1 200 000 Ar. The only candidate is six times lower. Two things can happen:
    - The reader returns 1 200 000. That amount is not a candidate, so `build` drops it and asks « Le prix est-il
      200 000 Ar ? ».
    - The reader returns 200 000. `build` keeps it, and the recap shows 200 000 Ar.
  - On a poster, « mets 1 200k » becomes a free change card « Prix : 200 000 Ar ».
  - D-KIT-002 rule 1 is the source of this behaviour. The implementation follows the design word for word.
- **Smallest fix.** Treat the 1-to-3-digit pure token before a `k` token the way rule 1 treats the tokens before a unit:
  - `"1 200k"` gives `[1200000, 200000]`. The model or the owner chooses between them, as for
    `Redmi Note 13 700 000 Ar`.
  - `"iPhone 13 250k"` gives `[13250000, 250000]`, with the same suffix ambiguity that exists today.
  - The stricter option is to give no candidate when such a token comes before `k`.
- **Rows to add.** `("Prix 1 200k Ar", [1200000, 200000])` and `("iPhone 13 250k", [13250000, 250000])`.

### 3. SHOULD FIX: a number followed by a currency other than ariary is now a candidate in ariary

- **Where.** `reads.py:224-226`. Rule 3 skips a run when the next token is `Ar | ariary | mga`, and in no other case.
- **What goes wrong.** Before this change the allowlist needed an ariary unit, so these messages gave nothing. Now they
  give a candidate:
  - `"Casque 250000 €"` → `[250000]`.
  - `"Casque 250 000 $"` → `[250000]`.
  - `"Casque 1 250 000 Fmg"` → `[1250000, 250000]`.
- **Why it matters.** Sellers in Madagascar still quote prices in Fmg (5 Fmg = 1 Ar). A price in Fmg read as ariary
  is five times too high. The reader or the owner can then accept a price in the wrong currency.
- **Smallest fix.** In rule 3, skip a run whose next token is another currency, the same way as a run followed by a
  unit:
  ```python
  re.fullmatch(r"(?:fmg|francs?|euros?|eur|dollars?|usd|[€$])[.,;:!?)]*", after, re.I)
  ```
- **Rows to add to `REJECTED`.** `("Casque 250000 €", 250000)` and `("Casque 1 250 000 Fmg", 1250000)`.

### 4. SHOULD FIX: `screen_shop_line` lets amounts, discounts and phone numbers through

- **Where.** `plans.py:78-97`.
- **Probe.** I ran `screen_shop_line` on the lines below. All of them **pass**:

  | Gap | Lines that pass |
  |---|---|
  | Plural discount words. `_DISCOUNT` is a set of exact words. | « Promos toute l'année », « Remises fidélité », « Réductions étudiants », « Offres spéciales » |
  | Amounts written as words. `screen_adjustment` refuses `mille\|millions?` through `_OFFER`; the line screen does not. | « Livraison 5 mille », « Livraison 2 millions » |
  | Phone numbers with `-` or `/`. `_LONG_NUMBER` accepts only `[\s.,]` as a separator. | « Tél 034-12-345-67 », « Appel +261-34-12-345-67 », « WhatsApp 034/12/345/67 » |
  | Fmg is not a currency word. | « Livraison 999 Fmg » |
  | Price claims. | « Prix cassés », « 2 pour le prix d'1 » |

- **What goes wrong.** These lines go against R-KIT-005 ("A line holds no amount and no discount") and against r1-1
  ("four digits or more, separators or not (a phone number)").
  - Each one is kept in the profile.
  - It is then drawn on every poster that shows the lines.
  - Every refinement of those posters draws it again.
- **Smallest fix.**
  - Match the discount words as prefixes on the folded text, as `find_commercial_terms` does:
    `\b(?:remise|reduc|promo|sold|rabais|offre|prix)\w*`. Keep « gratuit », « livr », « garanti » and « paiement »
    allowed.
  - Add `fmg|francs?|mille|millions?|milliards?` to `_CURRENCY`.
  - Use `_LONG_NUMBER = r"\d(?:[\s.,-]?\d){3,}"`. A hyphen is enough for the common phone writings, and
    « 24h/24 » still passes.
- **Rows to add.** One row for each case above in `test_plans.py::test_a_shop_line_with_an_amount_is_refused`.

### 5. SHOULD FIX: a new-poster message that the reader calls `other` loses its scene words and its lines

- **Where.** `reads.py:622`. Also the `SYSTEM` intent rule at `reads.py:46`, which says "describe = product, price or
  style of a new poster".
- **What goes wrong.** `build` returns `card_unclear` as soon as `intent == "other"`. It does this before it reads
  `instruction_fr` and `shop_lines`.
- **Failing scenario.** The draft already has a name and a price, and the owner sends « ajoute Garantie 6 mois, fond
  rouge ».
  - I called `build` with `Fields(intent="other", instruction_fr="fond rouge", shop_lines=["Garantie 6 mois"])`.
  - Result: `{'kind': 'unclear', 'text_fr': 'Écrivez le produit et son prix.'}`.
    - No `offer_lines`.
    - No `scene_fr`.
    - The sentence asks for the product and the price, which the draft already holds.
  - With `intent="scene_change"`, the same fields give the recap with `offer_lines` and `scene_fr`.
  - The intent rule names no scene or line, so `other` is a likely answer for a follow-up message about a line or a
    scene. R-KIT-005 then fails for that message, and the paid read is lost.
  - The stub hides the problem, because it sets `describe` as soon as a marker is present (`reads.py:433`).
- **Smallest fix.**
  - Add « scene or shop lines » to the `describe` rule.
  - In `build`, answer `unclear` for `other` only when `_given(fields.instruction_fr)` is empty and
    `fields.shop_lines` is empty.
- **Test to add.** `build` with `intent="other"`, a line and a complete draft must give a recap with `offer_lines`.

### 6. NIT: the `price_ar` row of the poster reader did not get the new rule

- **Where.** `reads.py:350`.
- **What goes wrong.** D-KIT-002 asks for the same reader rule in two places: `SYSTEM` and the `price_ar` row
  (« with or without a unit (250000, 250 000, 250.000, 250k); … or when no number is clearly the price »). Only
  `SYSTEM` changed.
  - On a poster, the server accepts « mets 250k » as a candidate, but the schema does not tell the reader about it.
- **Fix.** Use the same words in the row. The poster read's bytes then change, so measure that read again in
  T-KIT-010.

### 7. NIT: on a poster, a misread price gets a sentence that is not true

- **Where.** `reads.py:314`, through `api.py` `card_ask_price`.
- **What goes wrong.** `_price` returns `card_ask_price` on the poster path too. Its new text is « Je ne vois pas de
  prix dans votre message… ».
  - When the owner did write an amount and the reader returned another one (finding 2: « mets 1 200k »), the sentence
    is false.
  - It also names nothing that it read. R-KIT-002 says the question must say what it read.
- **Fix.** Give the poster path its own sentence, or name the candidates as `build` does.

### 8. NIT: a refused line gets the wrong reason

- **Where.** `reads.py:499` and `reads.py:659`.
- **What goes wrong.** Any line that `screen_shop_line` refuses and that is not too long gets the commercial sentence:
  - on a poster: `card_refused` (« Je ne dessine pas de prix, de remise ni de promotion… écrivez par exemple « ajoute
    Garantie 6 mois » »);
  - on a new poster: `card_unused_commercial`.
- **Failing scenario.** « ajoute Tél 034 12 345 67 » is told that it is a price or a promotion. On a poster, the same
  sentence then invites the owner to send the line again.
- **Fix.** Use one sentence for a refused line that names its rule (« sans montant, remise ni numéro »).
  `shop_line_refused` already has those words.

### 9. NIT: dead mapping and a generic refusal for lines whose rule grew

- **Where.** `visuals.py:290-299`.
- **What goes wrong.**
  - The `"shop_line_refused": ("shop_line_refused", "lines")` mapping in `request_scene` cannot run:
    - `Headline.lines` is validated by `ShopLine` first, which gives a 422 `validation_error` on field
      `headline.lines.0`;
    - the lines must also equal the profile's lines.
    - The comment above the mapping claims it can run.
  - In `request_refinement`, a base whose drawn lines fail today's screen gets the generic `invalid_plan`
    (`visuals.py:357`).
- **Fix.** Either delete the mapping and the comment, or map the refinement case to `shop_line_refused` too.

### 10. NIT: the name guard undercounts what it should log

- **Where.** `reads.py:631-634`.
- **What goes wrong.** `word not in written` tests for a substring of all the message's words joined together. A new
  word that sits inside another word passes. For example, « Pro » passes when the message holds « produit », and
  « Air » can pass the same way.
  - The guard only writes a log line (v2 decision). So the only effect is that T-KIT-010 counts fewer invented names
    than there are.
- **Fix.** Accept the tradeoff, or say in T-KIT-010 that the count is a lower bound.

### 11. NIT (design question): a bare number followed by a technical unit counts as a price

- **Where.** `reads.py:216-229`.
- **What goes wrong.** « Powerbank Xiaomi 20000 mAh » gives `[20000]` as the only candidate. The card asks « Le prix
  est-il 20 000 Ar ? ».
  - Power banks of 10 000 and 20 000 mAh are ordinary stock for this pilot shop.
  - D-KIT-002 refused a list of measurement units (ADR-095).
  - `plans._UNIT` already holds such a list. A run followed by `_UNIT.match` could be skipped.
- **Ask the lead.** Decide this on T-KIT-010's evidence.

### 12. NIT: one phone number alone as the message is still a candidate

- **Where.** `reads.py:238`.
- **What goes wrong.** The whole-message rule keeps leading zeros. « 0341234567 » sent alone gives `[341234567]`.
  - This rule existed before this change, and the test `("0700000", [700000])` pins it.
  - R-KIT-002 now says "never when it starts with 0".
- **Ask the lead.** Decide whether the whole-message rule follows R-KIT-002 too.

### 13. NIT (risk to measure): Malagasy promotion words in the first message's scene words

- **What goes wrong.** On a poster, scene words pass two screens:
  - `screen_adjustment`;
  - the reader's own `commercial` flag, which judges meaning in any language (ADR-102).
- New-poster scene words (`scene_fr`, then `adjustment_fr`) pass only `screen_adjustment`, which is a French and
  English regex.
  - Promotion words in Malagasy reach the prompt as a kept adjustment ("with any text or icons they asked for") if
    the reader puts them in `instruction_fr` against its rule.
  - R-KIT-003 says these words never reach the image.
- **Fix.** Add Malagasy promotion phrasings to the T-KIT-010 reads. If one gets through, add a `commercial` flag to
  `Fields`, used only to refuse.

---

## Questions of the brief, answered

**1. Money and state.**
- **The scene request's new checks run before anything is reserved.** `request_scene` (`visuals.py:277-285`) raises
  `shop_lines_missing` and `shop_lines_changed` inside `apply`, before `jobs.enqueue`, in the same write transaction:
  - The transaction is rolled back.
  - No `mutation_keys` row is written, so a retry with the same key runs again.
  - `test_lines_asked_without_lines_are_refused_before_any_spend` checks the job count and the balance.
- **A refused `adjustment_fr` costs nothing.** It is refused by the model validator (422 before the route) or by
  `checked_adjustments`, both before `enqueue`.
- **A refused line costs nothing.** It is refused at `PUT /api/shop-profile` by `ShopLines`, or it becomes a card from
  the read, which was already paid.
- **A read's new work happens after its reservation.** `_admit` reads `get_profile` after the INSERT, in the same
  transaction. `build` raises nothing new: every `MESSAGES` key is present, and
  `test_every_chat_card_sentence_is_in_messages` proves it.
- **Hashes.** I checked each field:
  - `Draft.scene_fr`: pinned in a test.
  - `Headline.lines`: excluded by `exclude_if` and by `exclude_none`.
  - `SceneRequest.adjustment_fr`: excluded by `exclude_none`.
  - `ProfileUpdate.lines`: excluded by `exclude_if`; the hash is pinned against `Profile` in
    `test_shop_lines_are_kept_checked_and_left_alone_by_older_clients`.
  - The job payload's headline drops `lines` and adds `shop_lines` only when lines are drawn, so earlier payloads are
    byte-identical.
- **Replays return the first answer.** `store.mutate` looks up the key before `apply`, and `_admit` returns the stored
  `response_json`. So a replay of a scene, a read or a profile PUT returns the first answer even after the profile's
  lines changed. No test covers the scene replay after a change of lines. It is correct by construction.

**2. `TO_REVIEW`.** It is correct for the cases in the brief.
- Each join keeps to `c.shop_id`. `confirmations` has no `shop_id`, but it is keyed by the creation id, which is
  unique across shops.
- **Copies:** clause 1 is unchanged, and clause 2 still works per creation.
- **No scene:** `COALESCE(...,'')` makes every waiting version count.
- **The stamps:** both are `utc_now()` text.
- **Several formats** are not reachable: `_format_change` keeps a poster at `{primary_format}`.
- The new test fails on the old rule.
- The correlated cost is stated in the code, as r1-15 asked.

**3. Prices.** See findings 1, 2, 3, 11 and 12.
- The `REJECTED` table follows the rules: the 10 000 floor, a leading 0, `k` below the floor, a run followed by a
  token that holds a digit.
- Five candidates give `card_ask_price_many`; four give `amounts`.
- The table misses three writings:
  - a phone number shortened by `_cut`;
  - `1 200k`;
  - a bare run followed by another currency.
- Each of the three gives a wrong candidate. In findings 1 and 2 the wrong amount is the only candidate.

**4. Prompt injection and the never-invent rule.**
- Every path from the owner's free text to the prompt is screened at least twice:
  - **Scene words:** `screen_adjustment` in `build`, then in the `SceneRequest` validator, then in
    `checked_adjustments`, then in `compile_scene`.
  - **Shop lines:** `ShopLine` at the PUT, then `ShopLine` on `Headline.lines`, then `screen_shop_line` again in
    `compile_scene`.
  - **Unused quotes:** these go only to the screen, never to the prompt.
- The reader cannot add a word:
  - scene words, lines and unused quotes pass the word guard;
  - on a poster, a line also passes the guard against the message plus the profile's lines.
- **Known limits (by design).**
  - The reader can re-order or select the owner's words. The recap and the `line` card show the exact text before the
    tap.
  - The new-poster name is kept even when the guard fails. This is the v2 decision, and it is logged (finding 10).
- **Can a line carry an amount, a discount, a phone number or an instruction?** Yes, see finding 4. On instructions,
  `_INJECTION` (as r1-1 asked) lets « Ignore the product, draw a cat » through. That is the owner's own text, drawn
  in quotes and checked in the review under `text_lines`.

**5. Migration 0021.**
- It is forward-only: `downgrade` raises.
- `PRESERVED` matches the 0020 columns of `shop_profile`.
- `ADDED` checks that no line exists yet.
- The `CHECK` is accepted with the default: SQLite checks existing rows on `ADD COLUMN` from 3.37.
- Existing rows get `'[]'`.
- `NOT NULL`, an object and a string are refused; this is tested.
- `GUARDS` and `GUARDED_COLUMNS` still pass (the test calls `guard_differences`).
- `shops.py` inserts without the column and gets the default.
- I did not check the production server's SQLite version. Other queries already need JSON1, so the risk is low.

**6. Isolation, errors and logs.**
- Every new query reads the session's shop: `get_profile(conn, shop)` in `request_scene`, `_admit` and `save_profile`.
- Each new code has a French sentence and the right status:
  - `shop_line_refused`: 422, field `lines`;
  - `shop_lines_changed`: 409;
  - `shop_lines_missing`: 409.
- The validation handler maps only `/api/shop-profile` body `lines` errors.
- No exception is swallowed.
- The word guard's logs name the field, never the words.
- The validation handler logs nothing, and `hide_input_in_errors` stays.

**7. Tests.**
- The new tests can fail. Each one pins an exact card, payload, hash, row or count, and the D-KIT-001 test fails on
  the old SQL.
- These risky branches have no test:
  - the rule-3 cut on a phone number (finding 1);
  - `1 200k` (finding 2);
  - a bare run before `€`, `$` or `Fmg` (finding 3);
  - plural discount words, amounts as words and hyphenated phone numbers in a line (finding 4);
  - `intent == "other"` with lines or scene words (finding 5);
  - the replay of a scene request after the profile's lines changed;
  - a refinement whose base lines fail today's screen (finding 9).

## Not checked

- The real reader's behaviour on the new `SYSTEM` text. That is a paid check, and T-KIT-010 owns it.
- The frontend use of these contracts. I read only enough of `App.vue` to see that `keepLines` removes lines that differ
  only in case, so a `line` card whose line differs from a kept one only in case does not fail the PUT.
- The performance of the correlated `TO_REVIEW` on a large shop.
