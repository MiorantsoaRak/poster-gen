# REQUIREMENTS — Conditions of use and the owner's check

**Status:** v2, 2026-11-17: approved under the autonomy grant, with R-TERMS-002 decided by the user on 2026-11-17 (ADR-111: the owner is warned and checks). Part of Release 1 « Invitation » ([roadmap](../ROADMAP.md), ADR-105). Design: [designs/service-terms.md](../designs/service-terms.md), approved v3 (ADR-112). R-TERMS-003 amended by the user on 2026-11-18. The French sentences of the conditions wait for the user's reading. A jurist has not read any of this.

**Why:** on 2026-11-15 the user noted that the image model writes product features nobody verified when asked for "4 lines of features", and left it as "just noted" for his own shop. AGENTS.md says never to invent specifications. With other shops, an invented feature goes on a paying customer's advert.

## Index

| ID | Title | Priority | Status |
|---|---|---|---|
| R-TERMS-001 | The conditions, accepted once | P0 | Draft |
| R-TERMS-002 | What the image may write | P0 | Decided 2026-11-17 (ADR-111) |
| R-TERMS-003 | What is kept, and where it goes | P1 | Draft |

## R-TERMS-001 — The conditions, accepted once
- **Story:** As a shop owner, I am told plainly, before my first poster, what the service does and what stays my responsibility.
- [ ] At the first sign-in the owner reads short conditions in French and accepts them. Without acceptance nothing can be generated.
- [ ] They say: images are made by an AI and can be wrong; the owner checks every word, price, feature and mark before using a poster; credits are prepaid and what a spent credit bought is not repaid; how to reach the operator.
- [ ] The acceptance is recorded with its date and the version of the text. A new version asks again.
- **Out of scope:** legal review (needed before Phase 2, by a jurist); terms in Malagasy.

## R-TERMS-002 — What the image may write
- **Story:** As a shop owner, I do not publish a feature my product does not have without having been warned.
- **Decided (ADR-111): the owner is warned and checks:**
  - [ ] When a request asks for features without listing them, the card says before the paid tap: « L’IA choisira les caractéristiques : vérifiez-les avant de publier. »
  - [ ] The check before download keeps its point on texts that were added, and it cannot be skipped.
- **Not chosen (the image writes only what the owner listed):** a request for features must list them; the image request forbids any other; « ajoute 4 lignes de caractéristiques » is answered by asking for them. Safer, and it removes what the user did with his own poster on 2026-11-15.
- [ ] Whichever is chosen applies to the chat and to « Ajustement de la scène » alike.

**Amendment of 2026-11-21 (ADR-125; owner's report on the released app: the warning stood under « Podium smaller », "every time now"):**
- [ ] The warning is shown only when the request's own words could ask for text or features: a fixed list of words, French and English, tested by the page (« caractéristiques », « specs », « détails », « infos », « texte », « écris »…). « Podium smaller » and « fond plus sombre » show nothing.
- [ ] The test is the same in the chat (the owner's message and the instruction read from it) and in « Ajuster la scène » (the typed instruction, when its confirmation opens).
- [ ] Known limit, accepted by the owner: a request worded with none of the listed words loses the warning before the paid tap. The check before download still names the added texts and cannot be skipped, and the accepted conditions still say it.
- **Out of scope:** checking a feature against a product database.

## R-TERMS-003 — What is kept, and where it goes
- **Story:** As a shop owner, I know what happens to my photos and my words.
- [ ] One short page says what is stored (photos, posters, each message's cost, and the result of a reading, which can repeat the instruction typed), which outside services receive what, per operation, and what happens on a request to delete: the shop is suspended at once (new requests are blocked), then the operator tells the owner what is erased and when. *(Amended by the user, 2026-11-18, ADR-112: no deadline and no claim about backups until an erase procedure exists; the stored reading is named instead of "not their text".)*
- [ ] It is reachable from the sign-in screen and from the account screen. *(The account screen is the shop dashboard's, R-SHOP-DASH-003, which carries this link as its own acceptance line; Release 1 is not complete without it.)*
- **Out of scope:** automatic export or deletion of a shop's data; an erase command (designed when the first request arrives: designs/service-terms.md, "Not built").
