# REQUIREMENTS — Creation by message (text-first generation)

**Status:** Approved 2026-11-14 under the user's autonomy grant (ADR-093), with the two working defaults marked below. Draft v2 (Claude), Rewritten from Codex's Draft v1 to match the mockup the user steered ([chat-first](../mockups/chat-first/index.html), ADR-091) and his decision to pay a small model call per message (ADR-092). The two points marked **OPEN** are applied with their working default and stay reversible by the user.

Research: [text-first generation findings](../reviews/text-first-generation-research-2026-11-14.md).

## Decided by the user

- A proper chat inside the application, beside the step editor. Both stay.
- A first screen offers « Par message » or « Pas à pas »; the choice becomes the start view and can be changed from the top bar.
- One attachment button takes the product photo and the inspiration image together, with no difficult control.
- The chat stays for the first request and for every polish. The list of modifications is visible in the view.
- Each message is read by a model; that call is paid and counted in the ledger (ADR-092).
- The price stays drawn in the image (ADR-044). Account credits are deferred (ADR-090).
- Few words, few steps.

## Index

| ID | Title | Priority | Status |
|---|---|---|---|
| R-TEXT-FIRST-001 | Choose how to create | P0 | Approved (ADR-093) |
| R-TEXT-FIRST-002 | Ask for a poster in one message | P0 | Approved (ADR-093) |
| R-TEXT-FIRST-003 | One recap, one paid tap, one check | P0 | Approved (ADR-093) |
| R-TEXT-FIRST-004 | Polish in the same chat, with the list of modifications | P0 | Approved (ADR-093), amended 2026-11-15 (ADR-099) |
| R-TEXT-FIRST-005 | Paid reading of messages, limits and failures | P0 | Approved (ADR-093), amended 2026-11-15 (ADR-099) |

## R-TEXT-FIRST-001 — Choose how to create

- **Story:** As the shop owner, I pick the way of creating that suits me once, and the application opens on it.

**Acceptance criteria:**
- [ ] With no saved choice, the first screen after sign-in offers « Par message » and « Pas à pas », each with one short sentence.
- [ ] The choice is saved on the device and is the start view at its next opening (amended by ADR-094: one shared login, so a choice per shop would flip the owner's phone when an employee chooses on the desktop).
- [ ] A switch in the top bar changes the view at any time and saves the new choice. Changing never loses a poster or an unsent message.
- [ ] « Pas à pas » is the current editor, unchanged. A poster made in one view opens in the other.
- [ ] « Mes affiches » and « Styles » stay reachable from both views.

**Out of scope:** a choice per poster, removing the step editor.

## R-TEXT-FIRST-002 — Ask for a poster in one message

- **Story:** As the shop owner, I write the product and its price, add my images, and send.

**Acceptance criteria:**
- [ ] `Sony WH-1000XM6 noir, 700 000 Ar` gives the product name with its brand and the integer price 700000 MGA, through the existing price validation. No slash command, no fixed word order.
- [ ] One button attaches up to four images (JPEG, PNG, WebP; existing size rules): one to three product photos and at most one inspiration image. The first image is taken as the product and the next as the inspiration; each shows its label, and one tap on the label swaps it. Each can be removed before sending.
- [ ] With an inspiration image, the style follows it and the three built-in styles are not asked. Without one, the three built-in styles are offered as one row, the last one used being selected. No word, logo or price is copied from the inspiration image.
- [ ] A missing product or price gets one short French question; the message and the valid images are kept. The price is never guessed, and never taken from anywhere but the owner's words.
- [ ] **OPEN — no product photo.** Working default (Claude's recommendation, against the user's earlier choice in ADR-088): the chat asks for a photo and offers the photos this shop already used for the same product; there is no web image search in this first slice. If the user keeps the web search, R-TEXT-FIRST-002 of Draft v1 (source link, variant choice, permitted storage, bounded and safe fetching) comes back as a sixth requirement.
- [ ] A photo reused from an older poster never carries that poster's approval.

**Out of scope:** voice, several products in one poster, general conversation unrelated to a poster, Malagasy.

## R-TEXT-FIRST-003 — One recap, one paid tap, one check

- **Story:** As the shop owner, I see what will be drawn and what it costs before I pay, and I check the result once.

**Acceptance criteria:**
- [ ] Before any image is generated, one card shows the product photo, the inspiration image if any, the product name, the price and the style, with one button that states the cost. Nothing is generated before that tap.
- [ ] A correction is typed in the chat (« non, 650 000 Ar ») and updates the card; there is no form to fill.
- [ ] A second tap, or a repeated message while a generation runs, never starts a second paid generation. The existing rule for an unknown outcome stays: no automatic paid retry.
- [ ] While the image is made, the chat shows a truthful status without a percentage, the previous version stays visible, and the next message can be typed.
- [ ] The result is checked in the existing review screen (the photos beside the image, the summary of what to check, one agreement, ADR-051), opened from the chat. Download is offered only after it, through the existing final screen. A new version needs its own agreement. (Amended by ADR-094.)
- [ ] **Automatic read-back of the drawn price: not in this slice** (ADR-094, after the devil's advocate: once a true warning has been seen, no warning reads as "checked"). The recap and the review show the asked price large. A read-back is measured offline on existing scenes first; building it is a later decision.
- [ ] Brand and title deduplication, boutique identity off by default, formats and the existing export rules apply unchanged.

**Out of scope:** an editable price overlay, guaranteed manufacturer logos, automatic publishing.

## R-TEXT-FIRST-004 — Polish in the same chat, with the list of modifications

- **Story:** As the shop owner, I ask for a change in my own words and I can see everything I changed.

**Acceptance criteria:**
- [ ] After the first version the same composer takes change requests for that poster; the product, the references and the earlier versions are kept.
- [ ] Each request gets one line saying what will happen and one button with the cost, plus « Annuler », which puts the text back in the composer.
- [ ] The answer is truthful about the kind of change: a change of scene, light or background is a new version from the current one; a change of price or title redraws the image and needs a new check; a request the application cannot do is refused in one sentence, with what is possible.
- [ ] The view shows the list of modifications: one line per version with its number, the owner's words and its state (to check, confirmed). Choosing a line shows that version. On a phone the list folds beside a small poster; on a wide screen it stays open.
- [ ] The list of modifications is the same on every device. The conversation and an unsent message survive a reload on the same device; they do not follow the owner to another device (amended by ADR-094).
- [ ] The twelve-scenes limit per poster applies and is said before it is reached, not after.

**Amendment of 2026-11-15 (ADR-099; user report: « Sony is the brand, put it on top, the product title on the second line » was answered « Le titre et le format se changent dans Pas à pas »):**
- [ ] The chat changes the same words as the step editor's « Textes » fields: the title, the brand, the subtitle and the price. A scene change (background, light, setting) stays.
- [ ] Exception: a brand and a subtitle exist only as words drawn in the image. On a poster whose image has no drawn words (made in « Pas à pas » with « Textes dans l’image » off), or while that switch is off, the chat says so in one sentence and points to « Pas à pas »; nothing is paid.
- [ ] One message may change several of them; the owner gets one card that lists each change, and pays once.
- [ ] The card is truthful about the cost by one rule, the same for every word: a word that is drawn in the selected version needs a whole new image and a new check; a word that is not drawn changes free and keeps the approved image.
- [ ] A brand set apart is not repeated in the title.
- [ ] The owner can remove the brand or the subtitle by message.
- [ ] A change is asked on any version, checked or not. The current version is kept.
- [ ] The sentence that says what the chat can change names exactly the changes it takes; it is built from the same list as the reader, so the two cannot differ.
- [ ] Cards and waiting messages kept on a device from before this change still work.

**Out of scope:** undoing a paid generation, editing an older message, merging two versions. Also out, and still done in « Pas à pas »: lettering requests that are not a field (size, position or font of the title), the accent word and its colour, the format, the style, the photos, the shop's contact line.

**Amendment of 2026-11-15, second (ADR-103; the rest of the [audit](../reviews/chat-capability-audit-2026-11-15.md), after a rejected draft and a paid baseline):**
- [ ] A word of the title in colour and the brand in plain letters are asked like any change to the image (they already are scene adjustments; nothing is added for them).
- [ ] By message I can ask for another of the three provided styles on an existing poster. It is a whole new image and a new check. The card says what is not carried into the new style: the model image and the scene adjustments asked before.
- [ ] In my first message I can ask for the shop's logo and contact on the poster. The recap says so before I pay. They are the shop's own logo file and contact, never drawn from my words.
- [ ] On an existing poster, a request for the shop's logo or contact, or for another format, gets one sentence that says where it is done in « Pas à pas ». Nothing is paid, nothing is changed.
- [ ] A tab that still runs the application from before this change cannot pay for a style change.

**Out of scope, still done in « Pas à pas »:** the shop's identity on an existing poster; the seal, the positions, the shop's name alone; a saved style and « Décrire moi-même »; another format made from the chat; and, unchanged, framing, typography and place of a laid-over text, photos, undo and redo.

## R-TEXT-FIRST-005 — Paid reading of messages, limits and failures

- **Story:** As the shop owner, I can write freely without a surprise on the bill and without losing my words when something fails.

**Acceptance criteria:**
- [ ] Each sent message is read by a model. That call is reserved and recorded in the spend ledger like the other paid calls, and the spend cap applies to it.
- [ ] Reading a message is not confirmed tap by tap (an exception to "every paid action is confirmed", accepted with ADR-092). Its cost is bounded: a maximum per message and a maximum number of messages per day, set in design and stated to the owner when reached (amended by ADR-094; the spend cap is the other bound).
- [ ] The model only extracts and classifies: product, price, style, kind of change. The price goes through the existing integer validation; the model's output never starts an image generation, never changes the cap and never bypasses the recap card.
- [ ] Text inside an attached image or a message is data, never an instruction to the application.
- [ ] (ADR-099) On an existing poster the model also extracts the poster's words (title, brand, subtitle). Each goes through the step editor's own rule for that field. A word that the owner did not write in this message and that is not already on the poster is never drawn: the model brings no word of its own. The application cannot tell a wrong arrangement of the owner's own words; each text is shown whole on the card before the paid tap, and again in the check.
- [ ] When the reading fails or the cap is reached, the message is kept, one French sentence says what happened, and the owner can retry or switch to « Pas à pas » with what is already known filled in.
- [ ] Composer, labels, recap and list work with a keyboard and a screen reader; the phone keyboard never hides the send button; motion respects the reduced-motion setting.
- [ ] A free local simulation covers the normal path and every failure above before any paid evaluation; a paid evaluation needs the user's budget and word.

**Out of scope:** WhatsApp, Telegram or other channels; per-account credits; a model benchmark without a separate budget.

## Open before approval

1. **No product photo:** shop photos only (working default) or web image search as chosen in ADR-088.
2. **Automatic read-back of the drawn price:** later, after an offline measurement (ADR-094).

Design follows the approval of these criteria; it must choose the reading model and its limits, and say where the conversation is stored (a schema change needs a forward-only migration).
