# Devil's advocate — D-TEXT-FIRST-005 (2026-11-15)

Scope: `## D-TEXT-FIRST-005` of `designs/text-first-generation.md`, against the code. Read only. No paid call, no server, no test run. Everything below comes from reading the files named.

Only points that would change a decision are listed. The last section says what I tried to break and could not.

## 1. The report's own message can still fail, in two ways

### 1a. The check order refuses it (P1)

- The owner's message has layout words: « put it on top, the title on the second line ».
- A reader may put them in `instruction_fr` beside `brand`.
- Check 1 runs every field through its row. The instruction row is `RefinementRequest.scene_adjustment`. It refuses `titre`, `title`, `prix`, `police`, `font` (`backend/src/affiche/posters/visuals.py:66-70`).
- Check 1 then answers `refused` with no change card (« a change is whole or not offered »).
- Check 5 would have dropped that instruction anyway. It runs too late.
- Result: the brand change is refused because of a field the design throws away. Whether it happens depends on the model. That is what the user did not want.

Alternative: when the answer holds a word field, do not check the instruction. Drop it first. Add the sentence « Demandez ensuite le changement de scène » only when the dropped instruction passes its screen. A layout remark is not a scene change.

### 1b. A brand typed in the step editor gives « L’affiche a déjà ces textes. » (P1)

- A poster made in steps with brand `Sony` and title `Sony WH-CH720N` is a normal state. The editor says the brand will not be repeated (`frontend/src/App.vue:1539`). The job stores `brand: "Sony"` with `brand_in_title` (`visuals.py:251-253`).
- `restoreHeadline` puts `Sony` back in the brand ref (`App.vue:140`). So `words.brand` is `Sony`.
- The owner writes the report's message. The reader returns `brand: "Sony"`.
- Check 3 needs « the owner changed the brand in this message ». The value is equal, so it is not a change. Check 4 drops the field. Answer: `same`.
- The image shows no brand line. The sentence is false, and the request is lost again.

Alternative: check 3 runs when the reader **returned** a brand, not when its value differs. Run it before check 4. « A brand already inside the title is left as it is » then means: the message did not speak of the brand.

## 2. Brand and subtitle have no stored "current value"; the refs are the wrong source (P1)

The design reads the current brand and subtitle from the editor's refs (`state.words`). The refs are not the poster.

- They are filled once, in `adopt`, from the version selected at that time (`App.vue:928`, `App.vue:129-143`). Nothing fills them again when the chat selects another version (`chooseVisual`, `App.vue:1302-1327`, does not touch them).
- Once a version has a headline, the local entry is removed (`App.vue:893-896`). After that the refs are kept nowhere.

What goes wrong:

- **False `same`.** Version 2 (brand Sony) is refused in the review. Version 1 (no brand) is selected again. The ref still says `Sony`. « mets la marque Sony » answers « L’affiche a déjà ces textes. ».
- **Unlisted changes on a paid card.** Refs hold version 3's subtitle. The owner selects version 1 (no subtitle) and asks a brand. The card lists « Marque : Sony ». The scene also draws version 3's subtitle. The requirement « one card that lists each change » is broken.
- **The word guard's base** is then words that are not on the poster the owner looks at.

Alternative: the current brand and subtitle are the selected version's `headline` (server data, already on `Visual`). Title and price are the document's. Two ways:

- Smaller: the client builds `words` from `doc.offer` and the selected `visual.headline`, not from the refs. `revise` first resets the refs from the selected version (the body of `restoreHeadline`), then applies the card.
- Safer: the server reads them itself. It has `creation_id`, the document and `baked_headline` (`visuals.py:322`). Then the request body does not change. Point 5 below (hash) and the "old schema" path both go away. Cost: the read uses the last saved document, so the chat must `flush()` before a read.

## 3. A change of two fields is half stored when the scene fails (P1)

- `revise` saves the new title in the document, sets the brand in a ref, then asks the scene.
- The scene is refused for good, or the job fails. The document keeps `WH-CH720N`. The brand is only in a ref.
- A reload, another device, or any `adopt` puts the old brand back (`App.vue:140`). Now the document says `WH-CH720N` and no brand exists anywhere.
- The card « Remettre les anciens textes » is an unspent card. The next card retires it (`supersede`, `frontend/src/chat.ts:136-138`, called at `ChatView.vue:223`). `aside` then shows nothing (`ChatView.vue:80`).
- The owner sends « prix 450 000 Ar ». The card lists the price only. The paid image shows `WH-CH720N` with no `Sony`. A verified product fact left the poster and no card said so.

Today's price flow has the same retired-card weakness, but its state is whole: the document holds the price that was asked. D-005 makes it worse because half of the change is not in the document.

Also not covered by a remembered `previous`: the new version is made, then refused in the review. No failure card exists. Version 1 is selected again and cannot be exported (`staleHeadline`, `App.vue:673`, `731-734`). The owner writes the old title. `consequence` says « drawn → Refaire l’affiche · cost ». It should be free: the document would again equal what version 1 shows.

Alternative (derive, do not remember):

- "The image shows other words" is already derived from server data: `staleTitle` and `stalePrice` compare the document with `currentVisual.headline` (`App.vue:731-733`). The editor already says « ou remettez l’ancien titre » from it (`App.vue:1534`).
- The chat shows one line « L’affiche montre encore les anciens textes. » with « Remettre » whenever that is true. « Remettre » writes the selected version's `headline.title` and `headline.price_ar` into the document and resets the refs from the same headline.
- `previous` on cards, its `readThread` mapping and the `stale` branch of `again` (`ChatView.vue:340-341`) are then not needed. It works after a reload, on another device, and after a refused version.
- `consequence` gains one rule: when the words after the change equal the selected version's drawn words, the change is free.

## 4. `""` for "remove" is fragile (P2)

- A model mixes `null` and `""` easily. `""` on a poster with a brand gives « Marque : retirée » inside a card the owner asked for another reason.
- No guard can catch it: the word guard has no word to check.
- Check 4 must also treat `""` and `null` as equal, or a poster without subtitle gets « Sous-titre : retiré » on every card. The design does not say it.

Alternative: removal is its own field, `remove: ("brand" | "subtitle")[]`, made from the table's "Empty string" column. An empty list costs nothing. A wrong removal then needs a positive wrong answer, not a wrong kind of empty.

## 5. A pending read from before the deploy is refused, not replayed (P2)

- The replay compares `payload_sha = sha(canonical(request))` (`reads.py:275`, `307`). `canonical` is `model_dump(mode="json")` (`models.py:21-24`). It writes every field, `null` included.
- A new optional `words` field adds `"words":null` to the dump of an old body. The hash differs from the stored one. The answer is 409 `idempotency_reused`, which the client treats as settled (`chat.ts:117`).
- The requirement « waiting messages kept on a device from before this change still work » fails.

Alternative: declare the field with `exclude_if` when unset, as `Headline.brand_text` does for the same reason (`plans.py:57-63`). Add the test: a body stored at the current code replays after the change. Or take the server-read option of point 2: no new body field.

Also: an old-shape card can arrive **live** (the replay of a stored answer), not only from a stored thread. The mapping of `change: 'price'` must be one function used on receipt and in `readThread`.

## 6. The word guard: keep it, but the refusal must name the word (P2)

- It refuses real requests when the reader tidies a name: `iphone15` → `iPhone 15`, `WHCH720N` → `WH-CH720N`, `pro2` → `Pro 2`. `name_words` splits on punctuation only (`plans.py:16-19`).
- It also refuses « oui, fais-le » after « Annuler »: the words are in the history, not in the message.
- The sentence « Je ne peux écrire que des mots de votre message ou de l’affiche. » does not say which word. The owner cannot act on it.
- The first poster has no such guard: `product_name` goes to the recap as the model wrote it (`reads.py:203-206`). The guard is not what protects the title. It protects the subtitle, which is free text. That is a good reason to keep it.

Alternative: keep the guard. The refusal names the word: « Je ne peux pas écrire « iPhone » : écrivez-le dans votre message. ». Add the owner's own history lines to the base, or say in the design why not.

## 7. "A table of fields": the claim is larger than the gain (P2)

- The table is a real gain for three things: no `intent`, one sentence made from the same list, one card shape.
- « Adding a field is one row and one setter » is not true as designed. A new field also needs: a rule in `consequence` (is it drawn in this version), a label in the list of modifications, the stub parser, the `Visual.headline` type. Still about five places in three files.
- `instruction_fr` is not a row like the others: no current value, another route, never combined. Keep it outside the table.
- The process gap stays: the next missing field is found only when the user hits it. `chat_reads` keeps a hash, not the text. The design defers it.

Alternative: say the true cost in the design. Decide now, not later, to keep the text of reads that end `unclear` or `refused` (the shop's own words, already sent to Anthropic). That list is the durable process: it shows what owners ask and the chat cannot do. It needs a forward migration (one nullable column), or a log line if the user refuses the column.

## 8. Brand set apart: specify the string work (P2)

- `brand_in_title` works on normalised words (`plans.py:22-24`). The removal must work on the original string. The design does not say how.
- `Sony – WH-CH720N` leaves `– WH-CH720N`. `WH-CH720N (Sony)` leaves `WH-CH720N ()`.
- The accent word may be the removed word. The client then drops it silently (`App.vue:300`); the card does not say it.
- It is not "the editor's own rule". The editor does the opposite with the same two values: it keeps the title and drops the brand (`plans.py:354`, `App.vue:1539`). The design should say this is a chat rule, justified by the owner's explicit wish.

Alternative: remove the matched span and the separators beside it, then trim. Tests: brand first, last, in the middle, in brackets, with a dash. Server-side removal is right: it is deterministic and the card shows the result before the tap.

## Tried to break, could not

- **ADR-097/098.** `revise` has the same order as `reprice` (`App.vue:1369-1375`): earlier saves, `owned()`, edits, then `createScene(key, sending)`. The kept request is the exact `/scenes` body, with brand and subtitle inside it, and its revision. A replay sends the same words. A retired card carries absolute values, so the next card applies the brand again. No weakening found.
- **Old bundle in an open tab.** A new-shape card that reaches old code goes to `adapter.change(id, undefined)` (`ChatView.vue:270-271`). The server answers 422, which is final. No money leaves. A scene-only card works as before.
- **Case and accents in the guard.** `sony` / `Sony`, `é` / `e` pass (`name_words`). Malagasy words pass when the owner wrote them. Model numbers with 4 digits pass `screen_headline` (`plans.py:40-47`).
- **The price rule** is unchanged (ADR-095).
- **A simpler design with the same result.** One more intent with three fields is smaller, but it is the "one more condition" the user refused. No better shape found than fields without a kind.
- **Server-side cost rule.** Reading `headline` of the selected version is server data. The server guards (`headline_stale`, `title_*`, export block) stay behind it.
