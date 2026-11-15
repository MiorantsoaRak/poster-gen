# REQUIREMENTS — Conditions of use and the owner's check

**Status:** Draft v1, 2026-11-15 (Claude), with working defaults marked **Default**. Part of Release 1 « Invitation » ([roadmap](../ROADMAP.md), ADR-105). **Its second requirement holds a decision the user has not made.** No design yet. A jurist has not read any of this.

**Why:** on 2026-11-15 the user noted that the image model writes product features nobody verified when asked for "4 lines of features", and left it as "just noted" for his own shop. AGENTS.md says never to invent specifications. With other shops, an invented feature goes on a paying customer's advert.

## Index

| ID | Title | Priority | Status |
|---|---|---|---|
| R-TERMS-001 | The conditions, accepted once | P0 | Draft |
| R-TERMS-002 | What the image may write | P0, **open** | Draft |
| R-TERMS-003 | What is kept, and where it goes | P1 | Draft |

## R-TERMS-001 — The conditions, accepted once
- **Story:** As a shop owner, I am told plainly, before my first poster, what the service does and what stays my responsibility.
- [ ] At the first sign-in the owner reads short conditions in French and accepts them. Without acceptance nothing can be generated.
- [ ] They say: images are made by an AI and can be wrong; the owner checks every word, price, feature and mark before using a poster; credits are prepaid and what a spent credit bought is not repaid; how to reach the operator.
- [ ] The acceptance is recorded with its date and the version of the text. A new version asks again.
- **Out of scope:** legal review (needed before Phase 2, by a jurist); terms in Malagasy.

## R-TERMS-002 — What the image may write (open)
- **Story:** As a shop owner, I do not publish a feature my product does not have without having been warned.
- **Default (the owner is warned and checks):**
  - [ ] When a request asks for features without listing them, the card says before the paid tap: « L’IA choisira les caractéristiques : vérifiez-les avant de publier. »
  - [ ] The check before download keeps its point on texts that were added, and it cannot be skipped.
- **Alternative (the image writes only what the owner listed):** a request for features must list them; the image request forbids any other; « ajoute 4 lignes de caractéristiques » is answered by asking for them. Safer, and it removes what the user did with his own poster on 2026-11-15.
- [ ] Whichever is chosen applies to the chat and to « Ajustement de la scène » alike.
- **Out of scope:** checking a feature against a product database.

## R-TERMS-003 — What is kept, and where it goes
- **Story:** As a shop owner, I know what happens to my photos and my words.
- [ ] One short page says what is stored (photos, posters, messages' cost but not their text), which outside services receive what (the image provider: photos and the request; the reading provider: the message's text), and that the operator deletes a shop's data on request.
- [ ] It is reachable from the sign-in screen and from the account screen.
- **Out of scope:** automatic export or deletion of a shop's data.
