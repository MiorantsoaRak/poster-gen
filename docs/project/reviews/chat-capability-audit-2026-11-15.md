# What the chat cannot do yet, against « Pas à pas » — 2026-11-15

**Why:** user request, before any more work on refinements: list what the chat still cannot do, since « Pas à pas » already does it. Read from `frontend/src/App.vue` (the four groups « Textes », « Boutique », « Style », « Réglages »), `frontend/src/ChatView.vue`, `backend/src/affiche/posters/reads.py`, `plans.py`, `visuals.py`, at commit "T-CHAT-LIST-LABEL…". (T-CHAT-REDO, uncommitted when this was read, was withdrawn the same day.) Nothing was run for this audit; where a line rests on a test already made, it says so.

## The user's four questions

| Question | In the chat today | In « Pas à pas » |
|---|---|---|
| Adjust the result? | Words (title, brand, subtitle, price) and the scene's background, light and setting. Not the framing, not the lettering, not the place of an element. | All of these. |
| Add the brand's logo (Sony, JBL)? | Setting a brand asks the image for the brand "written as on the product". The model decides: in three real JBL runs it drew the mark twice and plain letters once. « Use sony logo » on a poster that has the brand is not understood as a request about the drawing. | The same request, plus the switch « Écrire la marque en texte simple ». No guarantee either: "guaranteed manufacturer logos" is out of scope in the requirements. |
| Add the shop's logo? | No. A poster made in the chat has the shop's identity off. | « Boutique »: logo, shop name, contact, logo at the top, round seal, contact drawn in the image. |
| Change or add something in the background? | Yes: « fond plus sombre » and « mets un fond bleu nuit avec des reflets » made real images; « ajoute des éclairs bleus derrière le casque » was read as a scene change (card only, no image made). | « Ajustement de la scène », the same request. |
| Add an object (a gift box, a hand, a second product)? | No, and not in « Pas à pas » either: every scene request says "no duplicated products, extra devices, invented attachments, people, hands, props or packaging". | Same. |
| Add specifications? | One line: the subtitle, 60 characters, made of words the owner wrote, with no price, promotion or warranty word. | **Corrected by the user the same day, with a poster he made:** « Ajustement de la scène » draws a list of specifications with icons (« Réduction de bruit », « Autonomie longue durée », « Confort premium », « Bluetooth 5.2 »), a stylised product name and the brand's mark. The first version of this audit said there was no such thing; it had read the document's elements and missed that the scene adjustment takes free text and the image model draws what it asks. |

## Everything « Pas à pas » does that the chat does not

**« Textes »**
- The word in colour (accent word) and its colour.
- The three switches for the next version: the title composed in the image, the price drawn in the image, the brand in plain letters.

**« Boutique »**
- Shop name, contact and logo on the poster.
- Logo at the top (a copy of the poster), contact position (left, centre, right), logo as a round seal, contact drawn in the image.

**« Style »**
- Changing the style of an existing poster: the three provided styles, « Décrire moi-même » with its free text, a saved style.
- Correcting the product's main colour, taking the colours of the photo again.
- A model poster (« Affiche modèle ») for an existing poster, and saving a style from it. (The chat takes an inspiration image only with the first message.)
- Another format (« Refaire en … »).

**« Réglages »**
- « Ajustement de la scène »: the chat has it, narrower (see below).
- Framing: zoom, horizontal and vertical position.
- For a text laid over the image: font, size, colour, weight, alignment, price presentation and its colours, outline, shadow, position and dimensions, « Déplacer les éléments ».
- « Ajuster ce texte avec une consigne » and « Générer la matière du texte ».

**Elsewhere**
- Changing or adding photos of an existing poster (the chat says « Les photos d’une affiche se changent dans Pas à pas. »).
- Undo and redo.

**What the chat does have:** a first poster from one message with photos and an inspiration image; the recap; the check and the download through the editor's dialogs; word changes; scene changes; the list of modifications; and, since ADR-102 the same day, any adjustment of the scene in the owner's own words.

## « Ajustement de la scène »: where the chat is narrower than the editor

- It is the same function and the same request (`refineScene`): the instruction plus the current image as the base, composition kept.
- The editor's field refuses only words about title, price or font, and commercial terms.
- The chat's reader is told the instruction is "background, light, setting" only, and drops it when the message also names a word, even one that does not change. So « Use sony logo » became "brand: Sony" and was answered « L’affiche a déjà ces textes. ».

## Three mechanisms cover the list

1. **The scene instruction, as wide as the editor's** (T-CHAT-SCENE-FIELD). Covers: anything about how the image is drawn that is not one of the four words. The brand's mark, the product's size and place, more of the background, a list of specifications with icons, a stylised product name. Starts from the image shown, so it keeps the composition and earlier adjustments.
2. **More rows in the field table** (ADR-099): each a setting of the next image, already a field of the editor. Covers: the word in colour, the brand in plain letters, the shop's logo, name and contact, the style, the format. Each row is one line in the table, one setter and one test; the style and the format need their own effect (a new image with another plan, a copy in another format).
3. **Free edits of the layout**: framing and the typography or place of a laid-over text. They cost nothing and need no image, but they are drawn on the canvas, which the chat does not load. Least suited to a message; « Pas à pas » stays the place for them unless the user decides otherwise.

**Not possible in either mode, by rule:** added objects or people (the scene request forbids them; not tried through an adjustment); a guaranteed manufacturer logo; any price, promotion or warranty wording outside the price field.

**What the scene adjustment's screen refuses** (`screen_art` and `RefinementRequest.scene_adjustment`): commercial terms; the words « titre », « prix », « police », « font », « typograph… »; and "add / write / print / render / ajoute / écris" directly followed by "text", "price", "prix" or "logo". So « ajoute le logo Sony » is refused and « Use sony logo » is not: the screen is a list of phrasings, not a rule about content.

**Consequence for the product rule "never invent specifications":** in « Pas à pas » the owner types the specifications himself. In the chat a reader stands between his message and the image request, so the instruction must be his own words, not the reader's rewriting of them.

## Not verified

Nothing here was run. The lists come from reading the editor's template and the reader; a control that is hidden by a condition may have been missed. The behaviour of the real model on composition requests (a logo, a larger product) through a refinement is unknown until a paid test.
