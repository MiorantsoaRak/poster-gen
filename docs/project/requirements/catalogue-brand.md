# REQUIREMENTS — catalogue-brand

**Status:** Approved by the user on 2026-11-09 ("go aheadt with the requirement"; ADR-028). Technical designs remain subject to their separate approval gate.

| ID | Title | Priority | Status |
|---|---|---|---|
| R-CATALOGUE-BRAND-001 | Confirm the product and offer | P0 | Approved |
| R-CATALOGUE-BRAND-002 | Optional shop identity | P0 | Approved |
| R-CATALOGUE-BRAND-003 | Discreet shop signature in a composed poster | P1 | Approved 2026-11-12 (ADR-052), amended (ADR-053) |
| R-CATALOGUE-BRAND-004 | Product brand mark | P1 | Approved 2026-11-12 (ADR-052) |

## R-CATALOGUE-BRAND-001 — Confirm the product and offer

As the operator, I can start with a real product photo, title and price without creating a full catalogue first.

Acceptance criteria:

- [ ] One to three JPEG/PNG/WebP originals can be uploaded and previewed. Original bytes are preserved with their hashes; generated images never replace them.
- [ ] The operator confirms product identity/variant, the poster title and an exact Ariary price. The price is a nonnegative integer; missing, negative or fractional amounts are refused before generation. Formatting does not change the value.
- [ ] Additional specifications, discounts, warranties and delivery terms are optional and require explicit operator confirmation. Neither photo analysis nor either AI provider can turn an inference into a verified fact.
- [ ] Invalid/unreadable uploads show a French error; valid inputs and entered data remain available. Low resolution shows a warning before paid generation.
- [ ] Choosing the integrated-scene path does not require a successful cutout, a segmentation model or a cutout-compatible colour profile. Provider input validation still applies.
- [ ] Replacing a photo or correcting the variant creates a new input version. Existing candidates and exported posters retain their original source references; changed inputs never inherit fidelity approval silently.

Out of scope: catalogue scraping, automatic prices and multi-product posters. Upload limits and colour handling must be explicit in the design before implementation.

## R-CATALOGUE-BRAND-002 — Optional shop identity

As the operator, I can save Original Phone Mada's supplied logo, exact shop name and contact text, then choose what appears on each poster.

Acceptance criteria:

- [ ] Logo, shop name and contact text are independently optional profile fields. Contact supports multiple lines supplied by the operator; it is never invented by a model.
- [ ] Each poster has three independent inclusion choices: logo, shop name, contact. All eight combinations work, including none and all. A missing field cannot produce a placeholder or invented value in the poster.
- [ ] The original logo is an editable image layer, preserving its aspect ratio and transparency. A generated approximation of the logo is never substituted.
- [ ] The operator sees the inclusion choices before scene generation so the composition can leave suitable space, and can change them in the editor without another image call.
- [ ] A saved or confirmed poster keeps a snapshot of its selected shop details. Updating the shop profile does not rewrite old posters; applying newer details is an explicit edit.
- [ ] A failed profile/logo save leaves the prior stored version intact and shows an error with a retry action.

Out of scope: multiple shops, automatic logo generation, contact verification and social publishing.

## R-CATALOGUE-BRAND-003 — Discreet shop signature in a composed poster

**Status:** Approved by the user on 2026-11-12 ("go with the new requirement"; ADR-052), amended the same day by his decision to have the contact written by the renderer, not drawn by the image model ("B, and yes to the two smaller points"; ADR-053). The technical design has its own approval gate. Supersedes ADR-043 for new scenes. Background: [research summary](../reviews/signature-research-2026-11-12.md), [design review round 1](../reviews/signature-design-r1-2026-11-12.md).

As the operator, I want my contact to be part of the poster without competing with the product and the price, and my shop to be identified by its logo alone.

Acceptance criteria:

- [ ] The contact is written by the renderer, never drawn by the image model in a new scene. It is one compact line: a telephone icon and the contact exactly as typed, with no rule and no second line.
- [ ] The contact is visibly smaller than the price and stays readable on a phone: on the 1080 × 1350 poster its digits are at least 22 px tall. A renderer test measures this.
- [ ] The operator chooses where the contact goes in the footer: left, centre or right. The choice can be changed at any time without a new scene and without cost, and is remembered on the device. Default: right when the logo is included, centre otherwise.
- [ ] When the logo is included, the logo alone identifies the shop. Without a logo, the footer carries the contact only. The shop name is unticked by default in both cases; the operator can still tick it as an editable text layer. The logo is the uploaded file, placed by the renderer; the image model never draws or imitates it (R-CATALOGUE-BRAND-002 stays in force).
- [ ] The logo and the contact do not overlap when the poster is created, in any of the three positions. If the operator later moves one over the other, the editor warns him.
- [ ] Changing the contact, its position or the logo never needs a new scene. The scene leaves the footer free of objects and writing.
- [ ] Error case: WHEN the contact does not fit on one line at the minimum size THEN the editor says so at once and the final preview is blocked until the operator shortens it, removes the logo or removes the contact. No paid call is involved.
- [ ] Error case: WHEN no contact is selected THEN nothing appears in its place: no placeholder and no invented number.
- [ ] A poster whose existing scene already carries a drawn contact (ADR-043) keeps working with its guards; moving that contact needs a new version of the scene.

Out of scope: a logo drawn by the image model; a contact drawn by the image model in new scenes; a compact style for a multi-line contact; adding the contact to captions.

Decided on 2026-11-12 (ADR-053): the contact keeps its own band under the price; without a logo the shop name is not written by default.

## R-CATALOGUE-BRAND-004 — Product brand mark

**Status:** Approved by the user on 2026-11-12 ("go with the new requirement"; ADR-052). The technical design has its own approval gate.

As the operator, I want the product's brand to appear correctly on the poster, and a safe choice when the image model does not know the brand.

Acceptance criteria:

- [ ] By default the image model draws the brand mark from the brand the operator typed and from the product photo, as today. With no brand typed, no brand mark is drawn.
- [ ] The operator can choose "brand as plain text" for a poster: the typed brand is then written in the headline lettering and the model does not imitate a logo.
- [ ] The fidelity review asks the operator to compare the brand mark with the product, and shows the typed brand.
- [ ] Error case: WHEN the drawn brand mark is wrong THEN the operator refuses the version; the application never states that a brand mark is correct.

Out of scope: uploading manufacturer logo files; any statement about trademark permission (the operator decides what his shop may show).

Open question, approved without an answer; working default (Claude's choice, ADR-052) to confirm at the design review:

4. Is "brand as plain text" enough as the fallback, or do you also want to upload a brand logo file that the renderer places exactly? Default: plain text is enough; brand logo upload stays out of scope.
