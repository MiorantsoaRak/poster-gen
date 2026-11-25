# A general way to create, beside the product chat · research and code map · 2026-11-24

## Owner's follow-up · 2026-11-25 · proposal for discussion

The owner wants a chat where the seller prompts the image model directly, with a base template for a seller who gives little visual direction. Proposed entry under « Nouvelle affiche » is « Création libre », a conversation of its own alongside the guided product flow.

- A seller can generate from words alone or attach photos and an optional visual reference. Send the original wording and the ordered attachments. The generation button shows the credit cost. Skip the product reader, name/price/photo completeness test and extracted recap for this conversation.
- Offer one editable-by-instruction base style, « Style boutique ». Its brief covers composition, spacing, contrast and legibility. Apply it only to visual choices the seller leaves open. A reference or explicit request takes priority. A seller can turn it off. The same prompt can carry that precedence rule, so there is no preliminary call to classify the seller's intent.
- Shop facts and assets are a separate choice. The base style supplies no names, prices, discounts or warranties. Add a saved logo or contact when requested or selected. Use the seller's own spelling and wording for text to draw.
- Return the image to the conversation. A follow-up edits the selected version and keeps the earlier one available. The seller compares the image with the original request before confirming the final file, especially where several prices have to match several photos.

A first comparison on Flare could use a sparse request, the same request with a strong conflicting direction or reference, and an actual three-price poster followed by a correction to just one price. Assess the fallback, obedience to the override and unchanged surrounding content separately. This proposal has not been approved or tried.

Asked by the owner after his trial with a reference made of three product cards: « Think of a way we can handle those
kind of reference: if the reference is three images with product name on each, will the system be able to handle it?
… we keep the product based chat (and its step by step editor). But might be good to have one more general purpose and
less barrier on the possibility. For now, no code change, but do all the necessary research and code mapping. »

No code was changed for this note. The two code maps were made by read-only agents; six of their claims were checked
against the files (marked ✔). The rest is to be checked when a line is used.

## The answer to his question

**Today, no.** With a reference of three cards, each with a product name:

- **The layout** can be copied (T-KIT-021): shown once, on `gpt-image-2` at high quality. Not shown on the deployed
  model, `gpt-image-2.5-flare` at medium.
- **The names and prices under each product** cannot be written. A poster has one title and one price. A second
  product in a message is set aside with « une affiche montre un seul produit. Faites une affiche par produit. »
  (`api.py:161` ✔). A second price is asked away (« lequel ? »). And the free scene words refuse both amounts and
  « écris … texte » (`plans.py:56-74` ✔).

So the result is the three cards with one title and one price for the whole poster: a pack. Three priced products
side by side is not a thing the system can say.

## Why it is so: one contract, not one check

The one-product rule is the same contract at every level, hardest first (backend map, section 8):

| # | Where | What it fixes |
|---|---|---|
| 1 | `posters/models.py:43-46` ✔, `:224-229` ✔ | `Offer` = one `title` (required) and one `price_ar` (required int, 0 allowed). Every layout must hold exactly one `title` layer and one `price` layer. |
| 2 | `posters/visuals.py:25-35, 345-350, 398-400`, `exports.py:49-58` | The drawn words of a version are one title, one price, the contact, the shop's lines. The review, a refinement (`headline_stale`) and the export (`price_stale`) compare those. |
| 3 | `posters/plans.py:205-230, 427-437, 542-548` | `ScenePlan` has one `product_region`; the prompt says « one product set as a single large hero object » and « This is the only price ». |
| 4 | `visuals/prompts.py:143-147`, `plans.py:26-33, 56-74, 89-98` | Every free-text screen refuses amounts, currency, discount words and « write a text ». |
| 5 | `migrations/0006:13` ✔, `0007:13,23` ✔, `plans.py:350` ✔ | Jobs, plans and versions carry a NOT NULL `input_id` to one `product_inputs` row; 1 to 3 photos, enforced in four places. |

The frontend mirrors it: `Draft` has one `name` and one `price_ar` (`chat.ts:67-68`), a draft is complete with name +
price + photo (`chat.ts:309`), the recap, the review's word list and the stale checks read the same single values
(`ChatView.vue:666-683`, `App.vue:1194-1202, 1226-1229`).

## What the research says

- **Several input images:** OpenAI's guide says to name each image by number and purpose and to say how they
  combine. It gives no way to take only the layout from one image: what T-KIT-021 does is ours, proved on one case.
- **Several texts and numbers:** quote the exact wording, say how many times it appears, ask for no extra text, avoid
  tiny text, compare medium and high quality for small or dense text, and « check each number and any extra
  percentage the model adds ». Nothing is promised on how accuracy falls with the number of text blocks.
- **Current tools:** the ones found keep the two worlds apart. Either one product in a generated scene (Pomelli
  Photoshoot: one product, plain background, no text), or many items from a spreadsheet into a fixed template with
  real text layers (Canva Bulk Create). The trade guides advise text laid over the image for anything exact. None
  found draws several priced products from a free prompt and vouches for the numbers.
- **To verify:** the fetch of OpenAI's model page reported `gpt-image-2` as « Status: Deprecated », with the guides
  now on 2.5 and 2.6. Not confirmed here. The price table of the code knows `gpt-image-2`, `gpt-image-2.5-sunburst`
  and `gpt-image-2.5-flare` only (`visuals/gateway.py:57-61`): 2.6 would be refused.

## The idea: the guard moves from what the seller writes to what the image shows

The product chat is safe because the app controls the words: one name, one amount formatted in code, and free words
that may not hold an amount. A general way cannot work like that: its whole point is the seller's own text.

The rule « never invent a price, a warranty, a discount » is about the app, not about the seller. It holds in a general
way if three things are true:

1. **Only the seller's own strings are drawn.** The reader already may return only words the owner wrote (the word
   guard, `reads.py:279-285`). Each string to draw is kept as a string, never mixed into the scene words.
2. **Amounts are still formatted in code.** « 185k » becomes « 185 000 Ar » by the same parser as today, then goes
   into the prompt as a quoted string.
3. **Everything drawn is listed for the review.** Today's review lists the title, the price and the lines. A general
   poster lists each string. An automatic reading of the finished image against that list is the natural next step
   (the vendor's own advice is to check each number).

Nothing the seller writes is then blocked for being commercial; the screens that remain are the ones against
instructions hidden in a text and the advert guard.

## Proposal: « Affiche libre », a second kind of poster in the same chat

**For the seller.** At « Nouvelle affiche »: « Un produit » (today's way, unchanged, with « Pas à pas ») or « Affiche
libre ». In the free way he attaches photos, marks a reference if he has one, and writes what he wants in his own
words. The answer is one recap: each photo with the name and price read for it (one touch to move a name to another
photo), the list « Ce qui sera écrit, mot pour mot », the scene words, the reference. One tap draws it. The review
lists each written string. A correction is a message, as today.

The sentence « une affiche montre un seul produit » becomes an offer to switch to the free way.

**Why not a third tab, and why not only a relaxed product chat.** The frontend map's advice is to relax the existing
chat, not to add a tab: thread, composer, tray, waiting, credits, result, review and versions are already generic
(`chat.ts:165-357`, `ChatView.vue:139-174, 460-561`). But the product way's guarantees (one exact price, a recap with
no question) are what makes it fast and safe; loosening them for everyone would cost the simple case. So: one chat
shell, two kinds of draft, chosen openly.

**What stays product-only.** « Pas à pas »: it is built on the title and price layers (`models.py:224-229`,
`typography.py:91-97`). A free poster is made and corrected by message in a first version.

### Code map: what changes, what is reused

| Area | Today | For a free poster | Size |
|---|---|---|---|
| Creation and document (`models.py:43-62, 90, 201-228`) | one `offer`, title and price layers required | a `kind` on the creation; `offer.title` stays as the poster's name (lists, publishing and the credit history read it: `api.py:1115-1128`, `facebook_posts.py:215`, `credits.py:250`); add `items` (photo, name, optional amount) and `texts`; price optional when `items` exist | the hard one |
| Photos (`models.py:49-62`, `store.py:298`) | one `product_inputs` row, 1 to 3 photos, one name | **keep one row per poster** (the photos of several products): every foreign key of jobs, plans and versions keeps working. The 3-photo limit is a separate question (trial first) | small |
| Drawn words (`visuals.py:25-35, 315-318, 398-400`) | `headline` = title, price, contact, lines | a list of drawn strings with a kind each; `required_checks` and `record_decision` per string; `headline_stale` and `price_stale` compare the list | medium |
| Prompt (`plans.py:336-625`) | `compile_scene`: one hero, one pill, fixed regions | **a new builder**, not branches: images named by number and role, « Image 2 is the second product: write "…" and "…" beside it », the free strings quoted, the reference leads the layout, « no other writing » | medium |
| Scene plan (`plans.py:172-230`, `0007:13`) | required, one `product_region`, overlays for title and price | a plan row is needed by the foreign key; the free builder does not use its regions. To decide: a neutral plan or a nullable column | small, but a design point |
| Reader (`reads.py:78-131, 113-115, 331-351, 656-732`) | one name, one amount; a second product goes to `unused`, a second amount is asked | a second shape for the free kind: `items[]`, `texts[]`, scene words; the word guard and the amount parser reused as they are | medium |
| Free-text screens (`plans.py:26-98`, `prompts.py:143-147`) | amounts and « write a text » refused | unchanged for scene words; the strings to draw go by their own channel with the injection screen only | small |
| Chat client (`chat.ts:41-68, 150-163, 282-284, 309`; `ChatView.vue:188-214, 228-237, 339-344, 666-683`) | `Draft`, `Card`, `Words` single | a draft variant, a recap that lists, no copy to the « Pas à pas » form for this kind | medium |
| App adapter (`App.vue:424, 1406-1423, 2426-2462`) | `start` goes through `createPoster` and the form's fields | build the creation from the draft | medium |
| Review and stale checks (`App.vue:1194-1202, 1226-1229`; `chat.ts:429-445`) | list from `visual.headline`, one title and price compared | list from the drawn strings | small once the server sends the list |
| Entry (`App.vue:703-736, 851-885, 2857`) | `Start = 'chat' \| 'steps'` | a choice of kind on a new poster; the two-button switch stays | small |
| Reused as is | | jobs, credits, idempotency (`store.py:45-60`, `jobs.py:104-144`), uploads, looks and the model's poster (T-KIT-021), corrections with kept adjustments (T-KIT-020), shop lines, confirmation of the exact file, publishing (its caption is the seller's own text) | none |

Tests that pin today's shape: `chat.test.ts` (roles, `wireDraft`, `complete`), `chat_browser.py` (recap, scene
bodies), `document.test.ts`, `test_plans.py` (the byte-for-byte prompts: untouched if the free builder is separate),
`test_reads.py`.

**Rough size (a guess, not an estimate):** about the size of the seller's kit, 10 to 14 tasks, most of it in the
document contract and the drawn-words list.

### Another route, kept in reserve: the texts laid over the image

The app writes the names and prices itself, as text layers over a scene the image model draws without words. Every
string is then exact, and a price changes at no credit. It needs to know where each product ended up (a reading of the
image), a layout engine for several labels, and it loses the drawn look that ADR-044 chose. Worth it only if the paid
trials show that the production model cannot write several prices reliably.

## Before any requirements: paid trials, no code

Nothing above is worth designing if the production model cannot do it. Hand-written prompts sent with the evaluation
tool or a scratch script, on `gpt-image-2.5-flare` at medium and at high, three tries each:

| Trial | Question |
|---|---|
| Three products, a name and a price beside each, the owner's three-card reference | Are the six strings exact? Is each price beside its own product? |
| Three products, a title, two free lines (« -20 % jusqu'à dimanche », « Stock limité ») | Does it write what is quoted and nothing more? |
| Six to eight short strings on one poster | Where does accuracy fall? |
| Five and six product photos | Do products stay faithful above three photos? |
| The same two cases that proved T-KIT-020 and T-KIT-021 | Do today's fixes hold on the production model? |

About 30 images: near 1 USD at Flare medium, more at high. Each string counted exact or not: that number decides
between drawing and laying over, and between medium and high for this kind.

## Decisions that are the owner's

1. **The entry:** an open choice « Un produit » / « Affiche libre » at « Nouvelle affiche » (proposed), or the chat
   decides alone from the message.
2. **Prices in a free poster:** drawn by the image model and checked (proposed, if the trials allow), or laid over.
3. **A wrong drawn text:** who pays for the new image. Today a correction costs a credit.
4. **The check:** the seller's eyes only, or also an automatic reading of the image before he sees it.
5. **Limits:** how many products and photos (three today), how many strings.
6. **A poster with no price at all** (« Nouveautés de la semaine »): allowed in the free kind?
7. **Commercial words** written by the seller (« Promo », « -20 % »): drawn as written in the free kind (proposed;
   never added by the app), while the product way keeps today's rule.

## Sources

- [OpenAI image prompting guide](https://developers.openai.com/api/docs/guides/image-prompting)
- [OpenAI image generation guide](https://developers.openai.com/api/docs/guides/image-generation)
- [OpenAI gpt-image-2 model page](https://developers.openai.com/api/docs/models/gpt-image-2)
- [CapCut: text rendering in AI images, what works in 2026](https://www.capcut.com/create/ai-image-text-rendering-works-in-2026)
- [Google: Photoshoot in Pomelli](https://blog.google/innovation-and-ai/models-and-research/google-labs/pomelli-photoshoot/)
- [Canva Bulk Create](https://www.canva.com/help/bulk-create/)

## Delivery evidence · 2026-11-25

Three real medium-quality Flare generations used the application ledger on the isolated local trial shop. The first poster used three source photos and a grey reference with an underlined red title, heart motifs and a black price capsule. The result reproduced those visual elements, replaced the reference subjects with the supplied products in order, and put 120 000 Ar, 85 000 Ar and 150 000 Ar under the matching subjects. A polish changed the middle price to 95 000 Ar with the other prices and arrangement retained. A separate text-only request produced a greeting card reading « Fety sambatra ». The individual calls cost USD 0.060915, 0.072306 and 0.012290. Local comparison and full-size images are in `outputs/free-creation/`.

The Chromium walkthrough covers a 1366 px light desktop with all four attachments and a 390 px dark phone with no attachments. It reopens the conversation, compares the actual download hash with the preview, and submits a post to the Facebook stand-in. It also exercises exhaustion of the last credits while the confirmed file remains downloadable. An initial walkthrough caught broken attachment previews. The final browser test checks all four images decode.
