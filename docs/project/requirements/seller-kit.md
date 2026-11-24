# The seller's kit and the fixes of the first user walk

**Status** Approved for design, 2026-11-23, by the lead in the owner's place, on his words: « think the platform as a
framework the user can use to speedup the creation: a title font he can use, some scene model, etc., but they could
still free prompt if that is what they want », then « Proceed in the order you see fit; paid call still allowed; you
can continue till there is a testable app. When in doubt, take the place of the user and pick the one that is the most
likely to be the best solution. » Source of the findings: [the user walk](../reviews/user-walk-2026-11-23.md).
The existing rules stay binding: the product as photographed, the price as an exact number, nothing commercial invented
(prices, specifications, warranties, discounts), the review of the exact final file before use, the credit rules.

## The idea

A poster is the product (photo, name, price) and a few saved choices, the shop's **kit**: a scene model, a title style,
the shop's own lines. Each has a default, so the next poster is a photo, a name and a price. Each can be replaced by
words for one poster. Order of what wins: this message, then this poster's choices, then the shop's kit, then the house
defaults.

## Decisions taken in the owner's place (ADR-131)

1. The kit is the shop's own, beside the house models that exist. Models published by the operator for every shop: later.
2. Message is the way to create that the app puts first. « Pas à pas » stays, as the detailed way and the place to
   correct a finished poster; it loses nothing in this feature except the controls R-KIT-012 names.
3. The title stays drawn by the image model from a title style, as today's default (ADR-044): it is what makes a
   poster look made. The seller's own lines are drawn the same way, from his exact words, and are checked in the review
   like the title and the price.
4. Free words may change the scene, the staging, the layout and what the picture shows. They never change the product,
   never set a price, and never add a commercial line: those have their own fields.
5. A photo is a product photo unless the seller marks it as a model of style.
6. The order of « Publier » (description first, the owner's decision of 2026-11-22) is kept.

## Slice 1 — what the first user hits

| ID | Acceptance criterion |
|---|---|
| R-KIT-001 | A poster whose current revision has a confirmed file is shown as « Confirmée » on Accueil, in « Mes affiches », in the menu and on « Publier », and is not counted among the posters to check, whatever the state of its older versions. A poster with a new version that waits after its confirmation is « À vérifier », as today. One word names the state on every shop screen: « Confirmée » (the editor's version label included). |
| R-KIT-002 | In a message, an amount is read when it is written as `250000`, `250 000`, `250.000`, `250k`, with or without « Ar », « ar », « ariary » or « MGA ». Without a unit, a number counts as an amount only from 10 000 and never when it starts with 0 (amended 2026-11-23 on the devil's advocate: « 5000 mAh », a year, a phone number). The recap shows the amount read, large, before any credit is spent. When the message holds several amounts and none can be chosen, the answer names them and asks which one; it never repeats the same question without saying what it read. The form of « Pas à pas » reads the same writings. Two different prices in one message are still never guessed. |
| R-KIT-003 | What the first message says about the picture (background, light, where and how the product stands, what is written beside it such as its features) is used for the first image, in the seller's words, the same way a scene request is used today from the second image. Words of price, promotion or warranty never reach the image instructions (the existing rule). |
| R-KIT-004 | Before any credit is spent, the recap names what will be used: the product, the price, the format, the scene (a model's name, or the seller's words), the title, the shop's lines. It also names each part of the message that will not be used, with the reason in one sentence and what to do. A choice of the recap never changes between two recaps without being said. |
| R-KIT-005 | The shop keeps its own lines, typed once: up to three, 40 characters each at most (for example « Garantie 6 mois », « Livraison gratuite à Tana », « Paiement Mvola »). A line holds no amount and no discount (amended 2026-11-23): those belong to one offer. They are shown on a poster only as typed; the app never writes, completes or translates one. A poster includes them or not, by one choice the recap shows. A message that asks for a warranty, a delivery or a payment line (« ajoute garantie 6 mois ») is answered with the offer to keep that exact line among the shop's lines and to show it, never with a refusal that tells the seller to remove his words. The review lists each line among the words to check. |
| R-KIT-006 | A photo marked as a model of style in a message gives a poster in that model's style: it is described and saved the way « Créer un style depuis une affiche » does, the seller is told its name, and it is in the kit afterwards. Photos are product photos by default; the mark is one touch on the photo, visible before sending. |
| R-KIT-007 | A correction asked from the review of a poster made by message returns to the message field of that poster. Before a correction of words that needs a new image, the answer says that it costs one credit and redraws the picture. The product's name is written with the usual capitals of its brand and model; a straight quote in a name is replaced, not refused. While an image is drawn, the screen says how long it usually takes. |
| R-KIT-008 | On « Publier », the outcome of a post (published, with its link; failed; unknown) is the first thing visible after sending, at 360 px and on desktop, and nothing in the warning colour appears for a post that succeeded. With no Page connected, the page offers the connection itself and returns to the same post. Choosing « Publier plusieurs affiches » keeps the poster the seller came with as the first of the post. From the review, the action that prepares a post confirms the file and opens that page, which offers the connection when none exists (amended 2026-11-23: no second read of the Page inside the review). |

## Slice 2 — the kit

| ID | Acceptance criterion |
|---|---|
| R-KIT-009 | The message box shows the kit's choices before sending: the scene model (the house models and the shop's own, the most recently used first) and the shop's lines (shown or not). The last choices are the next poster's defaults. With a kit in place, a message of one photo, a name and a price gives a recap with no question. |
| R-KIT-010 | From a poster the seller likes, one action keeps its scene as a model of the kit, at no credit. The model is then offered like the others, in Message and in « Pas à pas ». |
| R-KIT-011 | « Styles » becomes « Mon kit »: the shop's scene models (rename, remove, as today's rules; the page says the two ways to add one: a photo marked as a model in a message, or R-KIT-010; amended 2026-11-23), the shop's lines (R-KIT-005), and the way to the shop's name, contact and logo. Every saved choice is shown as words the seller can read. |
| R-KIT-012 | A title style is a choice of the kit, apart from the scene: the house offers a few (for example bold condensed, italic sport, elegant serif), a scene model made from a poster brings its own, and the seller can keep one for all his posters. In « Pas à pas » the colour codes are no longer shown, the choices no seller needs (position and size in numbers, outline, shadow, font weight) sit in one closed section, and the three « dessiner dans l'image » boxes become two: the texts, and the price (the owner's ADR-044 choice stays; amended 2026-11-23). |

**Added 2026-11-23 (the owner's « guard », his message of the walk):** R-KIT-013 — A message that plainly asks for a picture that is not an advert for something the shop sells, or for the shop itself, gets one sentence that says what the app makes, and no paid step. In every doubt the message is treated as an advert.

## Later, named so that nothing is lost

- Several products in one poster (a pack): decided 2026-11-24 by the owner after the paid trial. No mark and no name per photo: the seller's words go to the image model as written and it decides which product a name means. The app asks nothing and refuses nothing for that.
- A visual guide on the first poster, shown on the real controls.
- Models published by the operator for every shop.
- The conditions of use shortened on the first screen.

## Not changed

Credits and their prices, the review and the confirmation of the exact file, the Facebook publishing rules (ADR-127
to 130), the formats, the operator's page, the conditions of use (their text is amended only where it must name the
shop's lines as kept data).
