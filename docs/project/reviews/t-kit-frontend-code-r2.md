# T-KIT-004 … 009, 012 … 014 frontend code review, round 2 (2026-11-24)

Reviewed: the fixes for `t-kit-frontend-code-r1.md`. They are in the uncommitted `frontend/src/App.vue`, `ChatView.vue`,
`chat.ts`, `ShopPublish.vue` and `ShopAccount.vue`, in the same checkout. I compared the current `git diff` of each
file with the diff that I reviewed in round 1, then read the changed functions in full. The review was read-only.

What I ran, from `frontend/`: `corepack npm@10 exec vitest run` on `chat`, `publish`, `facebook`, `words`, `document`,
`api` and `dashboard` tests. Result: 207 passed. `chat.test.ts:124` now pins `final('shop_lines_changed')` and
`final('shop_lines_missing')`. I did not run the build or a smoke. The five files had the same checksums at the start
and at the end of this round.

**Verdict: APPROVE.** The BLOCKER and the four SHOULD FIX items are fixed, and so are six of the seven NITs. The fix
added nothing above NIT level. The new NITs (N1 to N3) and the open part of finding 3 are for the lead to decide.

---

## Round-1 findings

| # | Severity | Status | Evidence |
|---|---|---|---|
| 1 | BLOCKER | **Fixed** | See below. |
| 2 | SHOULD FIX | **Fixed** | `chat.ts:264-271`: `FINAL` gains `shop_lines_changed` and `shop_lines_missing`, with a `ponytail:` note for the one case left. `ChatView.vue:470` then retires the card. `again()` offers a new card. |
| 3 | SHOULD FIX | **Fixed** (the optional part is open) | `ChatView.vue:114` (`lineCardLines`) and `:675`: an untapped `line` card shows « Lignes de la boutique : … » with every line that will be drawn. `App.vue:2477-2482`: `revise` builds `shown` from the same list, keeps the lines, reads the profile again and stops before the request (« … vérifiez-les, puis relancez. ») if the list changed. The `again()` card then shows the lines read now. Still open, as round 1 said: a scene change card on a version that drew lines draws the *current* profile lines, and the card does not list them. The design allows this ("the next image takes the new ones"). |
| 4 | SHOULD FIX | **Fixed** | `ShopPublish.vue:348` (`whyShown`), used at `:762` and `:764`. Only the `empty` reason gives way to the outcome block. |
| 5 | NIT | **Fixed** | `App.vue:2435-2437`: `keepLines` runs (the profile is read again) whenever lines are drawn, not only when a line is kept. The comment at `:2431-2434` is now true. |
| 6 | NIT | **Fixed** | `App.vue:2421`: `drawn` is `!creation.value \|\| headline.value.on`. |
| 7 | NIT | **Fixed** | `App.vue:1698`: `createScene` no longer calls `rememberTitle`. The title is kept only from `chooseTitle` (`:440`), the chat's kit row (`keepTitle`, `App.vue:2425`, `ChatView.vue:732`) and « Mon kit » (`:2947`). The look is kept from the first scene of a poster, or when the seller picks one. The comment at `App.vue:336-337` was not updated: see N2. |
| 8 | NIT | **Fixed** | `App.vue:1001`: the « Générer » / « Nouvelle version » dialog adds « Lignes de la boutique : … . » when `linesOn`. The request sends the same `profile.lines`, and the server's 409 catches a copy that is out of date. |
| 9 | NIT | **Fixed** | `ShopAccount.vue:161`: `@input="linesError = ''"`. |
| 10 | NIT | **Fixed** | `chat.ts:208`: `scene_fr` is kept only up to 500 characters. |
| 11 | NIT | **Fixed** | `ShopPublish.vue:432, 436, 445`: `linePost` records which post the sentence is about. `:695` and `:809` show the sentence in the block only for that post, and otherwise in « Publications ». |

### Finding 1 in detail

- **The recap.** `ChatView.vue:57` adds `newPoster = !versions.length`. `sceneOf`, `titleOf`, `shopLines`, `recapDetails`
  and `kit` (`:98-102, 112, 179-181, 399`) now use this test, not `state.creation`. So the recap that comes after a
  failure past `createPoster` shows the scene words, the look or the style photo, the title, and the lines switch with
  its offered lines. Each tap then passes `kit`, always as an object, and `{}` when nothing is chosen.
- **The request.** `kitLook` is removed. `start` (`App.vue:2435-2450`) reads the profile again and checks the lines on
  every tap. After `createPoster`, or at once when the poster already exists, it sets these from the tap's own `kit`:
  `ownerScene`, `headline.lines`, `headline.title_style` and the look.
- **The style photo after the request is taken.** `ChatView.vue:422` sets `draft.look` to the model made from the
  photo. If the job then fails, the next recap names the model and sends it. Before the request is taken, the photo is
  given back (`App.vue:2459`). Then the recap shows « votre modèle de style », and the next tap reads the same look
  again through `known` or `lookJobs`.
- **My three round-1 scenarios, traced again.**
  1. The look read times out. The recap keeps the photo, the words and the lines, and `kit` sends them.
  2. The job fails. The recap names « Style 4 » or the model, and the same look is sent.
  3. The lines switch is off and `adopt` fails. `kit` has no `lines`, so `headline.lines = false` (`:2449`), and the
     `keepWords` watcher stores `false`. A reload reads the stored thread draft (`lines: false`), so the result is the
     same.

## The three questions

- **Can a tap send something that the card on screen does not show?** Not on the paths of round 1. Three narrow cases
  are left:
  - the identity line (left-open note 3, below);
  - a stale recap on a poster that has since got a version (N3);
  - the scene change card (the open part of finding 3).
- **Can the lines switch off still end in drawn lines?** No, for every tap of a recap while the poster has no version.
  `kit` is always given, and `lines` follows the switch (`App.vue:2449`). It can still happen only through N3, where the
  recap has no switch any more.
- **Can the message field be left blocked?** No. The two lines codes are final. The client's own lines checks
  (`App.vue:2437, 2481`) throw before any request, so the card is retired. If the profile read in `generateScene`'s
  catch fails, the network error hides the 409. The card then keeps « Réessayer », and the replay gets the 409, which
  is now final.

## The four notes the fixer left open

1. **A delayed copy of the same request passes after the lines are changed back on another device: acceptable.** For
   this to happen, all of these must be true:
   - a delivery of the request is still on its way after the replay got 409 under the same key;
   - the profile goes back to exactly the old lines before that delivery arrives;
   - the seller also taps the new card.

   The worst case is a second image for a second credit, and that image is correct. The `ponytail:` note at
   `chat.ts:267-269` records it. Without the change, the card stayed blocked.
2. **After « Réessayer » returns the 409, the next tap stops with a sentence: acceptable.** `replay` does not read the
   profile, so the new card shows the page's copy of the lines. The next tap reads them (`keepLines`), stops with
   « Les lignes de la boutique ont changé : relisez le récapitulatif. », and the card after it shows the lines read
   now. Nothing is paid. The cost is one extra tap, and only after a lost answer and an edit on another device.
3. **The retry recap still does not show the logo and contact line: acceptable for this round, NIT.**
   - It is not one of R-KIT-004's named items.
   - The choice does not change. `include` was set from the first recap's `identity` when the poster was made, and the
     first recap said it.
   - But a drawn contact can only be removed with a new paid image, and the line goes away without a sentence. As a
     follow-up, show the identity line from the poster's `include` on a recap while `newPoster`.
4. **The recent order of models changes on every scene: acceptable.** R-KIT-009 says « the most recently used first »,
   and a scene made with a model is a use. It changes only the order of the chips, never what is drawn.

## New findings (all NIT)

### N1. NIT: `moveContact` still saves the look as the next default, and the colour can lose its look

- **Where.** `App.vue:386-390` (`moveContact` → `rememberStyle()`), `App.vue:332-335`.
- **What goes wrong.** The new rule is "the look becomes the default only when the seller picks it". Moving the contact
  on an older poster calls `rememberStyle()` with the look, so the look of that version becomes the next poster's
  default. Also, `rememberStyle(false)` on every later scene stores that poster's accent colour beside the look kept
  earlier. At the next page load, `readStyle` gives, for example, « Luxe sombre » with another look's accent.
- **Smallest fix.** Call `rememberStyle(false)` in `moveContact`. You can also store `accent_colour` only together with
  the look (when `withLook`).

### N2. NIT: a comment says the opposite of the new rule

- **Where.** `App.vue:336-337`: « the scene model and the title style of the last scene asked ».
- **What goes wrong.** The title is now only the seller's choice. The look comes from a poster's first scene or from the
  seller's pick.
- **Smallest fix.** Reword the comment.

### N3. NIT: a retry recap stays tappable after the poster gets a version elsewhere, and loses its kit

- **Where.** `ChatView.vue:57` (`newPoster` is a property of the poster, not of the card), `ChatView.vue:198-202`
  (`importForm` keeps an open recap on a poster).
- **What goes wrong.** Sequence:
  1. A retry recap is open on the poster, which has no version yet.
  2. The seller makes a version in « Pas à pas », or another device does.
  3. He comes back to Message, and the recap is still open. `newPoster` is now false, so the recap shows no scene words,
     no lines and no title.
  4. A tap sends `kit = undefined`. `start` then uses the editor's `headline.lines` and `title_style`, so it can draw
     lines that the recap does not show.

  This is one more paid image, which the seller asked for with « Créer l'affiche ». The sequence is unusual.
- **Smallest fix.** Retire an open recap once the poster has a version. For example, in `importForm`: `if (state.creation &&
  versions.value.length) supersede(items.value)`. Another way is to make `create()` refuse a recap when `!newPoster`.

## Not checked

- I did not check the build, `vue-tsc` or any smoke.
- I traced the stored-words watcher order after the fix (finding 1, scenario 3) from the code, not in a browser.
