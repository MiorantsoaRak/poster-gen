# REQUIREMENTS — catalogue-brand

**Status:** Approved by the user on 2026-11-09 ("go aheadt with the requirement"; ADR-028). Technical designs remain subject to their separate approval gate.

| ID | Title | Priority | Status |
|---|---|---|---|
| R-CATALOGUE-BRAND-001 | Confirm the product and offer | P0 | Approved |
| R-CATALOGUE-BRAND-002 | Optional shop identity | P0 | Approved |

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
