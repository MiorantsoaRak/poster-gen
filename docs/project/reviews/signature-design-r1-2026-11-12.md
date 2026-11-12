# D-CATALOGUE-BRAND-004/005 — design review round 1 and devil's advocate, 2026-11-12

Both reviewers were independent subagents, read-only, working from the draft in `designs/catalogue-brand.md` and the code. Line numbers are theirs, at commit `85e8296`.

## Fresh review: REWORK

P1:

- **Later scenes are not re-laid out.** Layers move to the plan's boxes only on the first scene (`service.py:144-159`); `chooseVisual` (`App.vue:516-528`) only toggles visibility. A second scene with the contact on the other side would draw it under the logo layer. Breaks "never overlap".
- **"The editor always sends a value" contradicts the 422 rule.** Rows with nothing drawn, an unticked "Dessiner" and a non-drawable contact send `signature: false` (`App.vue:109`); they would be refused.
- **`field_sizes` does not come from the editor.** The server builds it from saved layer boxes (`visuals.py:103-111`); default text layers are 952 px wide (`document.ts:59`); nothing in the frontend measures text. `shop_name` and `contact` are two fields, each needing its own region (`plans.py:124-142`), so "one box" has no carrier. Every left or right layout with a logo would fail.

P2:

- A shop name kept as a layer beside the logo needs a region; the layout does not say where.
- `fixed_plan` errors surface as `layout_not_plannable` (`visuals.py:150-151`), not as the message in the design.
- Auto-unticking the shop name when the logo is ticked makes a scene that drew the name fail `signature_missing` (`exports.py:50`).
- Claude and manual plans (`visuals.py:144`, `158-172`) ignore the position.

P3: `brand_text: false` survives `exclude_none` and changes the idempotency hash of a request retried across the deploy; the style restore is skipped after a saved look (`App.vue:74`); the review label is "Titre et sous-titre" today (`App.vue:185`).

Claims checked: (a) plan validation refuses intersecting boxes: true; (b) a new `PlanContext` field makes plans stale by itself: false, it must be threaded through `create_plan`, `revise_plan`, `request_scene` and the frontend, and every older plan goes stale once; (c) `signature_align: null` keeps old prompts and hashes: true if the old branch is untouched; (d) the first scene hides only drawn roles: true; (e) the export guard with logo, drawn contact and a visible shop-name layer: true; (f) sizes come from the editor: false.

Criteria not covered: "never overlap" for later scenes and non-fixed plans; "does not fit, told before any paid call" (no width source); "at least 22 px" (asked in the prompt only). R-CATALOGUE-BRAND-004: covered.

## Devil's advocate

Would change a decision:

1. **The contact drawn by the image model is the wrong tool.** A wrong digit is a dead phone number, code cannot read pixels, and the review is now one agreement. The renderer already writes exact text. Alternative: the contact stays the existing editable layer, restyled as one line in a palette colour; the scene keeps that band calm; the position is a free layer property. Lost: lettering matched to the headline, negligible at 22 px. Saved: `signature_align`, the prompt branch, the legacy path, the paid trial. Cost: an amendment to R-CATALOGUE-BRAND-003 (it says a contact or position change needs a new scene).
2. **22 px asked, not enforced**: the design does not meet its own criterion; point 1 makes it exact.
3. **Three paid scenes prove little**: if drawing stays, one scene at the hardest position first.
4. **Shop name and contact on one line without a logo**: about 51 characters for this shop, roughly 850–900 px of 972 at that size (an estimate), so the position means nothing or the plan fails. Alternative: contact only.
5. **Default position keyed on the look**: key it on the logo instead (logo left, contact right).

Could not break: the logo as the uploaded file; three positions; the shop name as a layer beside the logo; the contact on its own band; plain text as the only brand fallback.

## Outcome

Draft v1 is not submitted for approval. The P1 findings all come from drawing the contact; they disappear if the contact is a rendered layer. That choice reverses ADR-043 for the contact and changes an approved criterion, so it goes to the user.
