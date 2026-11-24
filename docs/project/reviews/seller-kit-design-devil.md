# Devil's advocate — seller-kit design, Draft v1 · 2026-11-23

Read: the walk (`reviews/user-walk-2026-11-23.md`), `requirements/seller-kit.md`, `designs/seller-kit.md`, ADR-131.
The code was read where cited (`main`, working tree of 2026-11-23). This review is read-only: nothing was run or paid.
It holds only the points that would change a decision, most important first.

---

## 1. The shop's lines drawn by the image model (Decision 3, D-KIT-005)

**Attacked.** ADR-131 §3, and in D-KIT-005: the lines exist only as drawn words, placed freely by the model, with no
Document change. Also: « the export is not blocked (there is no layer to compare): a stated limit » (design:180).

**Argument.**
- **It breaks a guarantee the export enforces today.** `exports.py:43-58` refuses a file when the drawn title, price,
  shop name or contact no longer matches the poster (« Showing the layer again never excuses stale words in the
  image »). The lines would be the only drawn words with no export check. A shop removes « Livraison gratuite à Tana »
  from its lines, and its old posters still export and post that promise, with no warning. Copies made for a price
  update carry the lines too.
- **The placement has not been tested.** Every other drawn text has a region in the plan (`plans.py:13` `FieldName`,
  the contact band). The model has already drawn into a reserved band once (ADR-055, `plans.py:454`). Free placement
  of up to three lines is the least proven part of the prompt. When it fails, the failure is on the same image as the
  price and the title.
- **The model draws small text that cannot be read.** Walk M15: the subtitle was « drawn very small … unreadable in a
  phone's feed ». The prompt for the lines asks for exactly that: « Small and clearly legible ».
- **Each change costs a credit, and a made image is never refunded** (`terms.py:22-23`). The `line` card (design:173)
  charges one credit to add « Garantie 6 mois » to a finished poster. That is walk finding 7 again, in the feature
  meant to fix finding 3. A spelling mistake costs one credit, and each try to fix it costs another.
- **With drawn texts off, there are no lines at all** (design:162). D-KIT-012's single switch makes this worse: the
  seller who wants exact texts that he can change for free loses his warranty line.
- The walk's own rule 3 and simplification 4 kept the lines on the app's side (« never written by the model »). ADR-131
  gives this reason: « the walk's best posters are the ones the model lettered ». That reason is about the title, not
  about three small lines.

**Instead.** Make the lines a text layer, beside the contact:
- one more `TextRole` `lines`, plus `Inclusion.lines`, `BrandSnapshot.lines`, and a region in the plan as the contact
  has;
- the lines are exact, free to add or edit, checked by the existing export rule, and shown whatever the drawn switch
  says;
- the `line` card becomes a free change;
- remove the prompt sentence, `text_lines`, `Headline.lines`, the `shop_lines` payload, and the placement question of
  T-KIT-010.

For readability, the text colour must come from the scene (walk simplification 13). The shop name needs this already
(finding 9).

*Minimum if the drawing stays:* put the lines in `brand_snapshot`, and make `effective_snapshot` refuse stale drawn
lines, as it does for the contact. Draw the lines in the contact band, not in free placement.

**Cost.**
- A Document change in lanes A and D: models, `document.ts`, `exports.py`, and the editor's default position.
- A plan region. This is about the « larger change » that open point 2 puts off, and the drawn path needs it too if
  free placement fails.
- The lines look laid over the scene, not composed into it.

---

## 2. Bare numbers ≥ 1 000 read as prices, in a phone shop (D-KIT-002)

**Attacked.** Rule 2 (design:61), and the one-candidate question with one button (design:72).

**Argument.** The pilot shop sells phones. The project already records that sellers write « a 4-digit year, "5000
mAh" » (`visuals/prompts.py:140-141`).

What rule 2 accepts:
- « Infinix Hot 40i 2024 5000 mAh 650000 » gives three valid prices: 2024, 5000 and 650000.
- « Powerbank 20000 mAh 85000 » gives 20000 and 85000.

Today the price must come from a number written before « Ar », or be the whole message. After this change, the server
accepts any of the numbers above as the price, so the reader can pick a wrong one.

**A forgotten price becomes a proposed wrong price.** « Tecno Spark 20 5000 mAh », with no price, now gets « Le prix
est-il 5 000 Ar ? » and a button. Today it gets « Quel est le prix ? ».

**Two more false readings:**
- A phone number written as one token, « 0341234567 », reads as 341 234 567. `_values` refuses a leading 0 only on a
  suffix, not on the whole token (`reads.py:127-130`).
- « casque 250000, livraison 5000 Ar » has one candidate only: 5 000. Rule 2 applies only when no amount has a unit.
  This feature invites exactly this kind of delivery line.

Only the recap protects the seller. One tap on a wrong button costs a credit and draws the wrong price, because the
price is drawn by default (`App.vue:86`).

**Instead.** Keep `250k`, `250.000` and `250 000`, with or without a unit. For a number without a unit:
- (a) it is not a candidate when the next token starts with a letter (`5000 mAh`, `2024 noir`, `128 Go`). This is a
  rule on the shape of the text, not a list of words;
- (b) it is not a candidate when it starts with 0;
- (c) it is never offered alone on one button. When there are two or more, show them as buttons; the reader never
  picks among them;
- (d) it stays a candidate when another amount in the message has a unit.

**Cost.** A few lines in `candidate_amounts` and more test rows. A number missed (« 250000 noir ») costs one question.
A number misread costs a credit and puts a wrong price on a public poster.

---

## 3. Scope: the owner's requests come last, and the cheap parts of the kit wait

**Attacked.** The order of the slices (design:286-307) and the « Later » list (requirements:53-58).

**Argument.** The owner's last direction is the kit: « a title font he can use, some scene model ». Slice 1 holds the
walk's fixes. Every part of the kit is in slice 2, after ten tasks, five of them one after another in `App.vue`. If the
work stops at « a testable app » after slice 1, the owner gets none of the framework he asked for.

His five requests, against the design:
- **Three images in one composition:** in « Later ». The « paid trial first » is not a task.
- **Product and promotion images only:** no requirement covers this guard. Yet D-KIT-003 opens free words in the first
  message, and Message never asks for the photo attestation (walk P3).
- **A trimmed « Pas à pas »:** it is the last task, and it removes three of the twelve things the walk listed. Not
  fixed: the tab order (P9), the 250 px slot on a phone (P15), « Versions 1 sur 12 », undo and redo, the step bar,
  « Marque ».
- **The visual first-use guide:** in « Later». The walk justifies this delay.
- **The status on « Publier »:** fixed in slice 1.

**Instead.**
- **Move into slice 1:**
  - D-KIT-010, « Garder cette scène comme modèle ». The design itself rates it cheap: one field and one access row.
  - The server half of D-KIT-012: one `Literal` and one helper, with a « Titre » choice in the recap.

  This is the first part of the framework that the owner can see.
- **Add to T-KIT-010,** which is already paid and already measures the reader again:
  - two compositions of three products, about USD 0.45, so that idea 1 is decided on evidence;
  - one reader field `advert: bool` (« a poster for something the shop sells »). When it is false, the scene words are
    refused. This is the guard the walk recommended.
- **Cut D-KIT-011's `POST /api/looks` carrier route.** It writes a look job into the history of an unrelated poster,
  and D-KIT-006 and D-KIT-010 already make looks without it. Keep « Mon kit » as the new name of the page.
- **Cut the review's `GET /api/facebook` and « Confirmer et connecter ma Page »** (last bullet of D-KIT-008). The
  pilot connects its one Page once, and the button on the publish page covers that case.
- **Give slice 1 to a real seller before T-KIT-014.**

**Cost.** About USD 0.5 more in T-KIT-010. One reader field, in a read that is measured again anyway. Slice 1 gets two
small tasks and loses one route and one review branch.

---

## 4. The word guard punishes the tidying that this design asks the reader to do (D-KIT-003, D-KIT-007 §3)

**Attacked.**
- The rule « in French and in his own words » for the scene (design:112), with the word guard (design:92), and the
  fallback line `other` « Redemandez-le après la première image » (design:124).
- The new guard on the new-poster `product_name` (design:209), together with the rule « usual capitals (… iPhone 15
  Pro …) » (design:110).

**Argument.** The guard requires every word of the reader's text to be in the message (`plans.py:16-19` `name_words`).
This design asks the reader to tidy, and the guard refuses the tidied text:
- **Scene words.** A model told to answer « in French » rewrites « fond rouge flammes, casque sur table bois » as
  « un fond rouge avec des flammes, le casque posé sur une table en bois ». The added words « un, avec, des, le, posé,
  une, en » fail the guard, and the scene is dropped.
- **Malagasy.** The reader's own instructions say messages come « in French or Malagasy » (`reads.py:36`). A Malagasy
  word translated into French always fails the guard.
- **What the seller is then told.** The drop tells him to pay for a first image and ask again. That is the credit per
  poster that the walk saw wasted (finding 2), now said to him openly.
- **Product names.** Sellers glue model numbers together: « redmi note13 », « iphone15 ». The capitals rule makes the
  reader write « Redmi Note 13 ». The word « 13 » is not in the message's words (`note13` is one word), so the name is
  refused, and `ask_product` asks for a name the seller has just typed. Today the name is kept as typed.
- **Two ways to do one thing.** On an existing poster the same wish needs no guard, because the whole message is the
  adjustment (ADR-102, `reads.py:364-371`). That is again two ways for one promise (walk finding 5).

**Instead.**
- **The scene rule:** « copied from the message word for word, in the language it is written in; leave words out,
  never add or change one ».
- **A refused scene:** the card says « Je n'ai pas compris la scène : écrivez-la en une phrase », before any credit.
  Never send the seller to « après la première image ».
- **A refused name:** keep the name as typed (today's behaviour), not `ask_product`.
- **Measure it:** T-KIT-010 counts the guard drops on short, misspelt and Malagasy messages. If more than one in five is
  dropped, the recap's scene line becomes a field that the owner's text fills. His own words need no word guard, only
  the amount screen.

**Cost.** Changed sentences, one branch, and one rate to measure. The field is built only if the evidence asks for it.

---

## 5. The shop's lines open a door to discounts that the rest of the app closes (D-KIT-005)

**Attacked.** « Commercial words are not screened » in `screen_shop_line` (design:148), and the lines « on by default »
(design:172).

**Argument.**
- **It breaks a rule the requirements keep.** Their header keeps « nothing commercial invented (prices,
  specifications, warranties, discounts) ». « Promo -20 % » and « Remise 20 % » pass `screen_shop_line`: no currency
  word, and fewer than four digits.
- **The design contradicts itself.** Its new refusal says « Je ne dessine pas de prix, de remise ni de promotion »
  (design:174).
- **The image model gets two opposite orders on one image.** The price sentence in the prompt says « no other amount,
  discount, old price … anywhere » (`plans.py:452-453`), and a line asks it to draw « Remise 20 % ».
- **One offer spreads to every poster.** A line is kept for the shop and shown by default. So « -20 % », typed once
  for one product, is drawn on every later poster of every product. The seller did not make that offer for those
  products; the app applied it again.

**Instead.** `screen_shop_line` refuses `%` and the discount words of `_COMMERCIAL_TERMS`
(`remise|reduc|sold|promo`, `visuals/prompts.py:147`). Warranty, delivery, payment and « gratuit » pass. A discount
belongs in the description of the post.

**Cost.** One regex and one refusal sentence. « Solde » and « Promo » can no longer be a line.

---

## 6. Each style photo in Message makes a new saved look (D-KIT-006)

**Attacked.** The start flow (design:195-197), and « Produit » as the default label of every photo (design:193).

**Argument.**
- **Looks pile up, and nothing checks for the same photo.** `request_look` counts the active looks and refuses at 24
  (`looks.py:19, 78-82`). It never checks whether a look of the same reference already exists. Each Message poster
  made from the shop's usual reference adds another « Style n ».
- **The page memory does not last.** It is lost at a reload, and with one login on several phones the limit of 24 comes
  fast.
- **At the limit, the seller is stuck.** The card says « Réessayer » and shows the same card again. That retry always
  fails, and the way out is a page the card does not name. This is a refusal without a way forward, the kind the walk
  memo says to check.
- **The new label invites the pack the app cannot draw.** Three photos all labelled « Produit » read as « three
  products ». That is the pack the owner asked for (idea 1), and the app cannot draw it: the prompt asks for « one
  product set as a single large hero object » (walk finding 10). The made image costs a credit that is not refunded.

**Instead.**
- Reuse the shop's active look whose `reference_asset` is this photo: one SELECT. Then say « Votre modèle
  « Style 4 » ».
- At `look_limit`, the card offers « Ouvrir mes styles », not « Réessayer ».
- Label the photos « Même produit », and write « 3 photos du même produit » in the recap.

**Cost.** One query, two sentences, one button.

---

## 7. The kit's defaults kept per device (open point 1)

**Attacked.** Open point 1 (design:314), the default title « per device » on « Mon kit » (design:261, 271), and the
lines switch per device (design:245).

**Argument.** D-TEXT-FIRST-001 kept a passing preference per device: the start view, which one employee should not flip
for the owner (`text-first-generation.md:27`). A kit is the opposite: it is the shop's look, the same on every poster,
whoever makes it.
- With one login on several phones, the shop's posters get different title styles depending on the phone.
- Clearing the browser, or opening the app in Facebook's own browser, loses the kit.
- A page called « Mon kit » shows a default that the next phone does not have.

**Instead.** Keep the explicit defaults (the title style and the default scene model) on `shop_profile`:
- in the same migration 0021, as two nullable columns;
- through the same `PUT /api/shop-profile`.

Only the « most recent first » order stays per device.

**Cost.** Two columns and two fields, on a route that changes anyway. The `If-Match` revision already handles two
devices.

---

## 8. Four sentences of title style are not « a title font he can use » (D-KIT-012)

**Attacked.** `TITLE_STYLES` (design:271), and what T-KIT-015 checks (design:307).

**Argument.** The owner asked for a title font that he can use again. A sentence given to the image model gives
different letters on each image: two « Gras condensé » posters will not share a typeface. The shop gets no lettering
that people recognise, and that recognition is the purpose of a kit. T-KIT-015 checks that the words are exact, not
that two posters of one style look the same. The editor already has real fonts for the title layer (walk: « three real
fonts in Réglages »).

**Instead.** Each title style is its sentence plus one of the fonts already in the app; that font is used when the title
is a layer. T-KIT-015 puts two products of one style side by side and judges whether the letters look the same. If they
do not, tell the owner that a drawn title is a style, not a font.

**Cost.** A table of four rows, and two more images (about USD 0.4).

---

## 9. One « Dessiner les textes » switch removes the price change without credit (D-KIT-012)

**Attacked.** « What goes: choosing a drawn title with a price as a layer » (design:276).

**Argument.**
- ADR-044 (the owner's decision) made the drawn price an option because the price is the fact that changes. When the
  option is off, a price-only change reuses the approved image: no credit and no new review.
- In a phone shop, prices change often. With one switch, a drawn title is possible only with a drawn price, so every
  price change costs a credit, a new scene and a new review. That keeps walk finding 7 for good.
- If point 1 is not taken, switching « off » also removes the shop's lines.

**Instead.** One switch for the title and the contact. The price keeps its own box, named by its effect: « Prix écrit
par-dessus l'image (modifiable sans crédit) ».

**Cost.** None: the box exists already (`App.vue:2842`), and the smokes keep it.

---

## 10. A recap that lists everything cannot protect the seller (R-KIT-004)

**Attacked.** « The recap names what will be used » (R-KIT-004), and « the word guard and the recap are the only
defences » (design:321).

**Argument.** The recap gets all of these above the paid button, on a 360 px phone (design:126-128, 172):
- a scene line;
- a title line;
- a lines line with its switch;
- each offered line with « Ne pas garder »;
- one line for each unused part;
- the « J'ai changé » lines.

The walk shows this seller taps through: in P5, the next click missed a button that had moved. He reads a long recap as
he reads the conditions (S3): not at all. Then the reader's errors that the design leaves to the recap reach a paid
image: a wrong name, a number without a unit taken as the price, a scene that was dropped.

**Instead.** The recap shows the name and the price in large type. After them, it shows only what differs from the
shop's kit or the house default, and the unused parts. When nothing differs, « Scène : Studio clair · Titre : … » is
one line.

**Cost.** One comparison with the kit's defaults, which the client already holds, and fewer recap tests.
