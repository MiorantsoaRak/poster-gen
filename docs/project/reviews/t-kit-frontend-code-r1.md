# T-KIT-004 … 009, 012 … 014 frontend code review, round 1 (2026-11-24)

Reviewed: the uncommitted frontend diff (`git diff -- frontend/src frontend/public`). I checked it against
`designs/seller-kit.md` v3 (the two tables at the top, D-KIT-002 to D-KIT-012 and "Contracts as built") and
`requirements/seller-kit.md` (R-KIT-001 to 013). I read the backend only to check that the client matches the server
(`api.py` MESSAGES and the profile validation handler, `reads.py` build and the `line` card, `visuals.py`
`request_scene` and `lettering`, `looks.py`). The review was read-only. The browser smokes and the Python tests are out
of scope.

What I ran, from `frontend/`: `corepack npm@10 exec vitest run` on `chat`, `publish`, `facebook`, `words`, `document`,
`api` and `dashboard` tests. Result: 207 passed. I did not run the build or a smoke. `App.vue`, `ChatView.vue` and
`chat.ts` had the same checksums at the start and at the end of the review, so nothing changed while I read them.

**Verdict: APPROVE WITH FIXES.** Fix finding 1 (BLOCKER) and the four SHOULD FIX items, then do round 2.
- No new path spends a credit when a pre-step fails. Keeping the lines, reading the style photo, the client's check of
  the lines and the server's 409 all stop before `sending`.
- The recap shown on the first tap, `kit`, the card fields and the request body agree.
- The problems are on the second tap after a failure, and on the `line` card. In both cases a paid image can draw
  something the card did not show.
- The « Publier » changes cannot send a post twice. The draft's stamp rule is unchanged, and the new buttons only move
  posters, answer an outcome or start the connection.

---

## Findings, most severe first

### 1. BLOCKER: after a failure past `createPoster`, the next recap does not show the kit, but the request still uses part of it

- **Where.** `ChatView.vue:93-99` (`sceneOf`, `titleOf`), `:109` (`shopLines`), `:171-177` (`recapDetails`), `:393`
  (`kit`): each one drops the kit when `state.creation` is set. `App.vue:2420-2455` (`start`) applies the kit only
  inside `if (!creation.value)`, then keeps it in memory (`ownerScene`, `kitLook`, `headline.lines`,
  `headline.title_style`). `ChatView.vue:477-479` (`again` → `recap()`).
- **What goes wrong.** When `createPoster` succeeds, the thread moves to the poster's key and `state.creation` is set.
  Each later failure that is not a kept request goes to `conclude` → `again` → `recap()`, and this new recap is a
  *poster's* recap:
  - it shows no scene words, no saved look (only `draft.style`), no title and no shop lines;
  - the next tap sends `kit = undefined`, and `start` skips the kit block.
  What the paid request then carries depends on what is still in memory:
  - the saved look (`kitLook`), the shop's lines (`headline.lines`) and the title style: used, but not shown;
  - the scene words: used only if the first scene request was never taken. After a taken request whose job failed,
    `ownerScene` is null and the words are dropped without a sentence;
  - the style photo: after a taken request, `styleReference` is null, so the retry uses the house style and not the
    model the first recap named.
- **Failing scenarios.**
  1. New poster with a style photo, the lines switch on and « fond rouge ». `readModel` fails: the 90 s limit,
     `look_limit` or `invalid_brief`. D-KIT-006 says that « Réessayer » is the same card. Here it is a new poster
     recap that shows « Scène : votre modèle de style » only. The tap draws the lines and sends « fond rouge », but
     the recap named neither.
  2. New poster, saved look « Style 4 » chosen in the kit row, lines on. The scene job fails at the provider. The
     new recap says « Scène : Studio clair ». The tap uses « Style 4 » (`App.vue:2443`) and draws the lines.
  3. The seller turns the lines switch **off**. `createPoster` creates the poster, then `adopt` fails later (for
     example `refreshEffects`, `App.vue:1486`). `headline.lines` keeps the `true` of `blankHeadline()`
     (`App.vue:1455`) because `App.vue:2439` never runs. The `keepWords` watcher also stores `lines: true` for the
     poster, so a reload does not fix it. The retry recap shows no lines, and the image draws them.

  A drawn line or a drawn scene can only be removed with a new paid image. This breaks R-KIT-004 (« the recap names
  what will be used », « never changes between two recaps without being said »).
- **Smallest fix.**
  - In ChatView, treat a recap as a new-poster recap while the poster has no version (`!versions.value.length`). Use
    this test in place of `state.creation` in `sceneOf`, `titleOf`, `shopLines`, `recapDetails` and `kit`.
  - In `start`, apply `headline.lines`, `ownerScene`, `title_style` and `kitLook` whenever `kit` is given: after
    `createPoster()`, or at once when the poster already exists. Keep `keepLines` and the lines check before
    `createPoster`.
  - Then the recap and the request come from the same draft on every tap.
  - Add one chat-smoke walk: a look read that times out → « Réessayer » → the recap still shows the scene words and the
    lines, and the body sends them.

### 2. SHOULD FIX: `shop_lines_changed` and `shop_lines_missing` are not final, so the card retries the same refused request

- **Where.** `chat.ts:258-261` (`FINAL`), `ChatView.vue:460` (`conclude`), `App.vue:1716-1719`.
- **What goes wrong.** Both 409s come back after `sending`, so the card keeps its request. The codes are not in
  `FINAL`, so the card stays with « Réessayer ». `replay` sends the same body with the same old lines, and the
  server refuses it again (`visuals.py:281-285` reads the profile each time). The card is `unresolved`, so `held` is
  true and the field of that poster's thread cannot send. A reload gives « Reprendre », which does the same. The only way
  out is to change the poster's revision in « Pas à pas », which then gives `revision_conflict`. A seller cannot find
  that.
- **Failing scenario.** The tab has been open for an hour. On the second phone (the shared login of the pilot), the
  seller edits his lines in « Mon compte ». In this tab, he asks a word change on a version that drew lines.
  `restoreHeadline` sets `lines: true`, the body sends the tab's old `profile.lines`, and the server answers 409
  `shop_lines_changed`. Every « Réessayer » gets 409 again.
- **Smallest fix.** Add `'shop_lines_changed', 'shop_lines_missing'` to `FINAL`. `generateScene` has already read
  the profile again, so `again()` offers a new card that uses the current lines. For the new-poster case, this depends
  on finding 1: without it, the new card is a poster recap that does not show the lines. Add one `chat.test.ts` row:
  `final('shop_lines_changed')`.

### 3. SHOULD FIX: the `line` card does not name every line that the paid image will draw

- **Where.** `App.vue:2469-2474` (`revise`: `keepLines(lines)`, then `headline.value.lines = true`), `App.vue:424`
  (`linesOn` sends `[...profile.lines]`). The server's card text is `card_line` « Je garde {} dans les lignes de la
  boutique et je refais l’affiche avec. » (`reads.py:613-617`).
- **What goes wrong.** The card quotes only the lines that the message asked for. The new image draws every line of
  the profile, including the lines kept earlier, which this version never drew.
- **Failing scenario.** The shop has « Paiement Mvola » and « Livraison gratuite à Tana ». The poster's version was
  made without lines. The seller writes « ajoute garantie 6 mois », and the card names only « Garantie 6 mois ». The
  paid image draws all three lines. The same applies to a word-change card on a version that drew older lines: the
  current profile lines are drawn, and the card says nothing about lines. The design allows this ("the next image
  takes the new ones"), but the card should still say it.
- **Smallest fix.** In ChatView, under an untapped `line` card, add one line:
  `linesLine([...(state.shop.lines ?? []), ...newLines(texts(item.card.lines), state.shop.lines)])`. That is the
  list that `revise` will send after `keepLines`. You can also say it on a scene change card whose version has
  `headline.shop_lines`.

### 4. SHOULD FIX: the outcome block hides every reason why « Publier… » is off, not only the "nothing chosen" reason

- **Where.** `ShopPublish.vue:757-759` (`why && !outcome`).
- **What goes wrong.** D-KIT-008 hides `why` because a published post empties the draft, so the only reason left is
  `empty`. A **failed** post keeps its items with a new stamp (`publish.ts:151`), and the outcome block stays. While
  the block shows, these reasons are hidden and « Publier… » is disabled with no reason given:
  - `pending` « Une de ces affiches attend votre réponse … répondez plus bas »;
  - `stale` « Vos affiches n’ont pas pu être relues … »;
  - `terms`, `running` and `checking`.
  The `aria-describedby` reference is removed too.
- **Failing scenario.** A post fails. One of its posters is also in an older post with an unknown result. The block
  says « Échec », and the button is disabled. The sentence that says to answer the older post is hidden.
- **Smallest fix.** Use `why && !(outcome && helpOnly(action))` in both places. Then only the `empty` reason gives
  way to the outcome.

### 5. NIT: the lines check in `start` compares with an old copy when no line is kept, and its comment says otherwise

- **Where.** `App.vue:2426-2430`.
- **What goes wrong.** The comment says « lines changed elsewhere stops the tap before the poster is made ». That is
  true only when `kit.keep` is not empty, because then `keepLines` reads the profile again. Without a kept line,
  `shown` is compared with the page's own `profile.lines`, which is the same source. The server's 409 then comes after
  the poster is made, and that leads to finding 2. Nothing is paid.
- **Smallest fix.** Correct the comment. As an option, do one `GET /api/shop-profile` before the check when
  `kit.lines` is set.

### 6. NIT: `state.drawn` is the previous poster's `headline.on` while a new poster is composed

- **Where.** `App.vue:2416`, `ChatView.vue:110`, `ChatView.vue:657-660`.
- **What goes wrong.** Before `createPoster`, `headline` still holds the last poster's settings. If the last poster
  did not draw its texts:
  - the new poster's recap hides the lines switch and drops the lines from `kit`;
  - when lines are offered, the recap says « … cette affiche n’a pas de textes dessinés »;
  - then `adopt` sets `on: true`, so the new poster draws its texts but no lines.
  The recap and the request agree, so no credit is spent on something hidden. But the sentence is false and the lines
  are lost.
- **Smallest fix.** For a new poster, give `drawn` as `true` (`computed(() => !creation.value || headline.value.on)`).

### 7. NIT: every `createScene` writes over the « Titre par défaut » of « Mon kit »

- **Where.** `App.vue:1693` (`rememberTitle(headline.value.title_style)`), `App.vue:340`.
- **What goes wrong.** « Nouvelle version » or a restyle card on an older poster first restores that version's title
  style. For a version made before this change, that style is `null`. The scene then stores `title: null`, so the
  default that the seller chose in « Mon kit » goes back to « Moderne » without a sentence. D-KIT-009 says "the last
  choices are the next defaults", but R-KIT-012 says « keep one for all his posters », and the page says « Pour vos
  prochaines affiches ».
- **Smallest fix.** Ask the lead. If « Mon kit » wins, call `rememberTitle` only from the chat's new poster
  (`start`), from `chooseTitle` and from « Mon kit », not from `createScene`.

### 8. NIT: « Pas à pas » draws the shop's lines by default and the « Générer » dialog does not say so

- **Where.** `App.vue:90` (`blankHeadline().lines: true`), `App.vue:995-999` (`askScene` text).
- **What goes wrong.** A poster opened in « Pas à pas », or a draft from before this change (`readWords` has no
  `lines`), draws every shop line on the next « Générer ». Only the « Boutique » tab shows that box.
- **Smallest fix.** Add « Avec les lignes de la boutique : … » to the dialog text when `linesOn`. Another option is to
  start the box off.

### 9. NIT: a refused line keeps its error after the seller corrects it

- **Where.** `ShopAccount.vue:69`, `:161-162`.
- **What goes wrong.** `linesError` and `aria-invalid` stay until the next save or read. When the seller has
  corrected the line, the three fields still say they are invalid.
- **Smallest fix.** Clear `linesError` in a `watch(() => draft.value?.lines, …, { deep: true })`, or `@input` on
  the three fields.

### 10. NIT: `readThread` takes any length of `scene_fr` from storage

- **Where.** `chat.ts:202`.
- **What goes wrong.** The module's own rule is "the storage is never trusted; a field of the wrong size is left out".
  `wireDraft` sends `scene_fr` to the reader. A stored value over 500 characters gives a 422 on every read of that
  thread (« Ce message ne peut pas être lu tel quel »).
- **Smallest fix.** Keep `scene_fr` only when its length is 500 or less, as `readWords` does with its 60.

### 11. NIT: the outcome block takes `postsLine` from any post

- **Where.** `ShopPublish.vue:690` and `:804`.
- **What goes wrong.** While the block shows, a failed « Arrêter l’envoi » or « Elle n’y est pas » on another post in
  « Publications » shows its sentence at the top of the page, far from the button that the seller touched.
- **Smallest fix.** Show `postsLine` in the block only when the action was on `outcome.post`. Otherwise keep it in
  « Publications ».

---

## Checked and found correct

- **Money, first tap.** The recap is spent and saved before anything leaves. Then `keepLines` (GET, PUT at that
  revision, one retry on `revision_conflict`, any other error thrown) and the client's lines check run before
  `createPoster`. `readModel` runs before `createScene`. `sending` is the last step before the paid request. A double
  tap is stopped by `spend`, and a second tab by the chat lock and `owned`. The lines in the body
  (`[...profile.lines]`) are equal to the recap's `kit.lines` at that time, and the server compares them again in the
  same transaction.
- **Style photo.** `start` never sends a raw `style_reference_asset` with a style photo: `styleReference` is null
  before `createScene` and is given back on a refusal. `lookJobs` keeps the job per asset, so « Réessayer » after the
  90 s limit waits on the same job (r1 18). A look that the shop already has is found in `savedLooks`, or the server
  reuses it.
- **`ownerScene` and `kitLook`.** `adopt` and `fresh` clear them, so they never reach another poster.
  `generateScene` clears `ownerScene` once the server has taken the request. A kept request replays its own body,
  `adjustment_fr` included.
- **Per-device memory.** `kit.recent` and `style` use `shopKey`, a sign-in reloads the page, and a sign-out forgets
  the shop's prefix. A look id that was removed, or that belongs to another shop, is skipped by `lastKit`,
  `rememberRecent`, `kitChips`, `chosenKit` and `start`. A removed look still reads on the server
  (`looks.get_look`).
- **Older stored threads.** `readThread` gives every new `Draft` field its default and keeps the old `identity` rule.
  A card from before has no `look`, `title`, `scene_fr` or `shop_lines`, and the recap still shows its scene.
- **`restoreHeadline`.** On a version from before this change, it gives `lines: false` and `title_style: null`. It
  keeps the old `on`/`contact` pair until the seller touches the box.
- **Price buttons.** The server sends `amounts` only after the name is set, and never on a poster (`reads.py:581`,
  `:725-728`). `amountsOf` keeps positive safe integers only. The buttons are disabled while a read waits, and the
  photo stays in `draft.pictures`.
- **`unused_fr` and `textOf`.** The lines are removed from `text_fr` exactly. No `v-html` exists in the changed files.
  Server and owner text is shown with mustaches or bound attributes.
- **« Mon compte ».** The client compares `lines` by value in `dirty`, in the two-device merge and in the
  « modifiées sur les deux appareils » choice. `writeProfile` sends `lines` only when a caller gives them: `saveProfile`
  does not, `keepLines` and « Mon compte » do. Every lines validation error comes back as `shop_line_refused`, field
  `lines` (`api.py:968-971`), and is shown at the three fields.
- **« Publier ».** `sent` is set only from this hold's own answer (`holding(at)`). `begin()` clears it when the poster
  changes or the hold is taken back, and adding a poster clears it too. `startFacebook` keeps nothing when the request
  fails. A tab that cannot store the origin clears it. The return is bound to the shop and checked by
  `isPublishOrigin`. `putFirst` adds once and moves first. When the draft is at its limit, it leaves the draft the
  same. It is refused while a post of the draft is followed.
- **Focus.** The outcome heading takes the focus after the sheet closes. « Corriger l’affiche » focuses « Votre
  message » after `v-modal` gives its focus back (`vModal.unmounted` runs in the same flush). « Réglages avancés » is a
  native `<details>`. The new controls have names: the chips, « Titre », « Ne pas garder « … » », the lines boxes, the
  label buttons and the connect button.
- **`curlQuotes`.** It is the same as the server's `curl_quotes`, and `savePlan` saves the curled title before the
  scene's revision is read.

## Not checked

- I did not check the build, `vue-tsc` or any smoke, as the brief says.
- I did not check the stored-words watcher order in a real browser. Scenario 3 of finding 1 is from reading the code.
- I did not check how the image model places the lines (T-KIT-010).
- I did not check if the server keeps a 409 under the idempotency key. Finding 2 is the same in both cases.
