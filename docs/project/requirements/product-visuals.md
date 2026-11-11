# REQUIREMENTS — product-visuals

> Feature boundary (PROJECT.md): visual direction, product scenes generated from a reference photo, fidelity review, and evaluation of a photo-preserving fallback.
> **Inputs from other features:** confirmed product facts and original photos come from `catalogue-brand`. Until that feature exists, they come from a hand-made fixture set (R-PRODUCT-VISUALS-007). How long operations run (progress, retries, timeouts, usage metering) is defined in `generation-jobs`. This file defines only what the operator sees and what is kept.
> **Output to other features:** an approved **Visual**, a scene image linked to one product variant. `poster-editor` puts it under editable text, price and logo objects.

**Statuses:** `Draft` → `Approved` → `Implemented` → `Verified` (or `Dropped`)

**2026-11-09 approval (ADR-028):** The user approved R-009–011 after explicitly choosing GPT Image integration as primary. These amendments govern the normal poster flow. R-001–008 remain the approved phase-1 evaluator baseline; its automatic cutout comparison is not the normal product workflow. Phase-2 technical design approval is still required before implementation.

## Index

| ID | Title | Priority | Status |
|----|-------|----------|--------|
| R-PRODUCT-VISUALS-001 | Choose a visual direction | P0 | Approved |
| R-PRODUCT-VISUALS-002 | Generate a product scene from the original photo | P0 | Approved |
| R-PRODUCT-VISUALS-003 | Only confirmed facts; no text in the scene | P0 | Approved |
| R-PRODUCT-VISUALS-004 | Fidelity review before use | P0 | Approved |
| R-PRODUCT-VISUALS-005 | Revise a rejected scene | P0 | Approved |
| R-PRODUCT-VISUALS-006 | Photo-preserving fallback | P0 | Approved |
| R-PRODUCT-VISUALS-007 | Visual record, provenance and reuse | P0 | Approved |
| R-PRODUCT-VISUALS-008 | Pilot fidelity evaluation | P0 | Approved |
| R-PRODUCT-VISUALS-009 | Integrated scene as the primary path | P0 | Approved |
| R-PRODUCT-VISUALS-010 | Refine a selected scene without losing it | P0 | Approved |
| R-PRODUCT-VISUALS-011 | Optional photo-preserving alternative | P1 | Approved |

---

## R-PRODUCT-VISUALS-001 — Choose a visual direction

- **Status:** Approved (2026-11-06)
- **Priority:** P0
- **Story:** As the shop operator, I want to choose a starter mood or describe my own, so that the scene fits the offer without a fixed layout.

**Acceptance criteria:**
- [ ] GIVEN a confirmed product WHEN the operator opens the direction step THEN they see starter moods (at least: néon, pastel, studio, lifestyle, minimal), a free-text field in French, and an optional style-reference image upload. All three can be combined.
- [ ] GIVEN the direction step WHEN the operator picks a commercial intent (promotion, nouveauté, mise en avant d'un bénéfice) THEN that intent is stored with the request. Choosing an intent is optional.
- [ ] GIVEN no mood, text or reference WHEN the operator continues THEN a default direction is used, and the request records that it was the default.
- [ ] The direction controls only the scene (background, light, props). It does not fix where text, price or logo go.
- [ ] Error case: WHEN the style reference is not an accepted image type or is too large THEN the upload is refused with a French message giving the limit, and the rest of the direction is kept.

**Out of scope:** saved per-shop direction presets (creation-library); multi-product comparison scenes.

---

## R-PRODUCT-VISUALS-002 — Generate a product scene from the original photo

- **Status:** Approved (2026-11-06)
- **Priority:** P0
- **Story:** As the operator, I want the product placed in a coherent scene from my own photo, so that I get a publishable visual without a photo shoot.

**Acceptance criteria:**
- [ ] GIVEN a confirmed product variant with at least one original photo and a direction WHEN the operator requests a scene THEN the system sends the original photo as the reference image, and also the style reference if there is one.
- [ ] Each request produces exactly one candidate (ADR-009). To get another one, the operator must reject and revise (R-PRODUCT-VISUALS-005).
- [ ] GIVEN a finished generation THEN the result is a candidate with status `pending_review`. It cannot be used in a poster until it is approved (R-PRODUCT-VISUALS-004).
- [ ] The candidate can be cropped to all three formats (1080×1350, 1080×1080, 1080×1920) with the whole product visible. If one format needs an extended or new scene, that variant is a separate candidate and needs its own review.
- [ ] The original photo file is never modified or replaced. Its stored hash is the same before and after generation.
- [ ] Error case: WHEN the provider refuses the image, the quota is exhausted, or the call times out THEN the operator sees a French message saying which of these happened and what they can do next. The direction and inputs are kept, there is no automatic retry loop, and nothing is shown as a successful candidate.
- [ ] Error case: WHEN the original photo is below the minimum resolution THEN the operator is warned before generation. They can still continue, and the warning is stored with the candidate.

**Out of scope:** the job mechanics (generation-jobs); local AI retouching of an area (post-pilot, PROJECT.md).

---

## R-PRODUCT-VISUALS-003 — Only confirmed facts; no text in the scene

- **Status:** Approved (2026-11-06; criteria 1–2 amended 2026-11-06, ADR-011)
- **Priority:** P0
- **Story:** As the shop owner, I want the generated scene to add no claims, so that the poster never advertises something we did not confirm.

**Acceptance criteria:**
- [ ] GIVEN a scene request THEN the product information sent to the model is only the confirmed product name, variant/colour and the operator's direction. No catalogue price, discount, warranty or delivery term is sent. The operator's free text (description, correction note) is screened for such terms on a best-effort basis, and a match blocks the request with a French message.
- [ ] Every scene request instructs the model not to **add** text, prices, badges, logos or watermarks. Markings printed on the product itself (brand logo, labels) are kept. Text added outside the product is a rejection reason in the review checklist (R-PRODUCT-VISUALS-004).
- [ ] A unit test builds the request from a product fixture with a price, warranty and promo and checks that none of these values are in the request.

**Out of scope:** caption and headline generation (poster-editor / text model, later requirement).

---

## R-PRODUCT-VISUALS-004 — Fidelity review before use

- **Status:** Approved (2026-11-06; criterion 2 amended 2026-11-06, ADR-011)
- **Priority:** P0
- **Story:** As the operator, I want to compare the scene with my original photo before using it, so that I do not advertise the wrong model or colour.

**Acceptance criteria:**
- [ ] GIVEN a `pending_review` candidate WHEN the operator opens it THEN the original photo and the candidate are shown side by side on desktop, and with a toggle or swipe on a phone. Both can be zoomed.
- [ ] The review shows a French checklist: colour/coloris, manufacturer logo, camera layout, buttons/ports, shape/proportions, no extra product or accessory, no text added outside the product, product whole in all three formats (must be ticked to approve, R-PRODUCT-VISUALS-002), realistic integration (light, perspective).
- [ ] WHEN the operator approves THEN the status becomes `approved`, and the approval time is stored.
- [ ] WHEN the operator rejects THEN they must select at least one checklist reason or type a note. The status becomes `rejected`, and the candidate is kept (not deleted) for the evaluation.
- [ ] A candidate that is not `approved` cannot be added to a poster. The block is enforced in the API and the UI.
- [ ] The allowed status changes are only `pending_review → approved` and `pending_review → rejected`. Any other change is refused, and a unit test covers every refused change.

**Out of scope:** automatic fidelity scoring (could be evaluated later; not required for the pilot).

---

## R-PRODUCT-VISUALS-005 — Revise a rejected scene

- **Status:** Approved (2026-11-06)
- **Priority:** P0
- **Story:** As the operator, I want to ask for a corrected version after a rejection, so that I do not start over.

**Acceptance criteria:**
- [ ] GIVEN a `rejected` candidate WHEN the operator requests a revision THEN the new request reuses the same original photo and direction, and adds the rejection reasons and the note as correction instructions.
- [ ] The revision is a new candidate, linked to the candidate before it. Earlier candidates do not change.
- [ ] Each request comes from one explicit operator action. The system never starts a revision automatically.
- [ ] GIVEN a product variant that has reached the attempt limit of **3 generated attempts** (ADR-010) WHEN the operator requests another generated attempt THEN the system offers the photo-preserving fallback (R-PRODUCT-VISUALS-006) instead, and says why. The count restarts only when the operator explicitly starts a new campaign for that variant, which is allowed only after one of its visuals was approved (ADR-011).
- [ ] Evaluation exception (ADR-011): during the pilot evaluation only (R-PRODUCT-VISUALS-008), the limit is 5, and products the user assigns to arm B get revisions without correction instructions (plain re-rolls). Outside the evaluation, the rules above apply unchanged.

**Out of scope:** area selection or masked edits (post-pilot local retouching).

---

## R-PRODUCT-VISUALS-006 — Photo-preserving fallback

- **Status:** Approved (2026-11-06)
- **Priority:** P0
- **Story:** As the operator, I want a result that keeps my real product photo when the generated product is wrong, so that I still get a poster.

**Acceptance criteria:**
- [ ] GIVEN any candidate or product variant WHEN the operator chooses "Garder ma photo" THEN the product is cut out of the original photo, and a background scene without the product is generated around where it sits (with a shadow if possible).
- [ ] The result has two separate parts (ADR-009): the **cutout layer** (transparent PNG made from the original photo) and the **background**. They are stored separately and never merged into one image. poster-editor lets the operator move and resize the cutout layer.
- [ ] The cutout layer's pixels come only from the original photo: they are masked, not regenerated or retouched. An automated test checks that every opaque pixel of the cutout matches the original photo at the same position.
- [ ] The UI tells the operator that the shadow is part of the background and does not follow the product when it moves.
- [ ] The operator sees the cutout before the scene is built. If the cutout edges are wrong, they can reject it and nothing is spent on the scene.
- [ ] The fallback result goes through the same review (R-PRODUCT-VISUALS-004) before use.
- [ ] Error case: WHEN the cutout fails or finds no single product THEN the operator sees a French message and a suggestion for a better photo (plain background, one product, full frame). No partial result is shown as usable.

**Out of scope:** removing a product from an existing generated scene; automatic conversion of a flattened image into layers.

---

## R-PRODUCT-VISUALS-007 — Visual record, provenance and reuse

- **Status:** Approved (2026-11-06)
- **Priority:** P0
- **Story:** As the shop owner, I want an approved visual stored with its product and history, so that I can reuse it when only the price changes.

**Acceptance criteria:**
- [ ] Each candidate stores: product and variant, original photo reference(s), style reference if any, direction, treatment (`scene` or `photo_preserved`; for `photo_preserved`, both the cutout layer and the background, plus the product's position on the background when it was approved), provider and model ID, the request sent (prompt), the parent candidate if it is a revision, status, rejection reasons, time, and the measured cost from generation-jobs if available.
- [ ] GIVEN an approved Visual WHEN a poster for the same product variant is created or its price changes THEN the Visual is offered for reuse and no generation request is made.
- [ ] An approved Visual is never offered for a different product or variant.
- [ ] Approved Visuals cannot be deleted while a saved creation uses them (creation-library defines the lifetime).
- [ ] Before catalogue-brand exists, a fixture file with ~20 products (name, variant, confirmed facts, photo paths) is enough to run every requirement in this file.

**Out of scope:** a cache of backgrounds without a product shared across products; catalogue editing.

---

## R-PRODUCT-VISUALS-008 — Pilot fidelity evaluation

- **Status:** Approved (2026-11-06)
- **Priority:** P0
- **Story:** As the project owner, I want measured results on real products, so that I choose the model, the default treatment and the pricing from evidence.

**Acceptance criteria:**
- [ ] GIVEN the fixture set (~20 Original Phone Mada products, including poor photos and easily confused variants) WHEN the evaluation runs THEN each product is tried with both treatments, `scene` and `photo_preserved`.
- [ ] A report (CSV + short summary) lists for each product and treatment: attempts until approved (or abandoned), rejection reasons, cost per approved visual including rejected attempts, and wall-clock time per attempt.
- [ ] The evaluation uses the user's OpenAI account. The API key is read only from the server environment (`.env`, git-ignored). It never appears in code, logs, the frontend bundle or the docs.
- [ ] The spending cap is a required configuration value in USD, set by the user. If it is missing, the evaluation refuses to start and makes no paid call. During the run, the spend so far is shown, and no new request starts if its estimated cost would go over the cap.
- [ ] The evaluation starts only when the user has supplied the fixture photos. Until then, it runs only against a stubbed provider (no paid calls).
- [ ] The summary makes a recommendation (default treatment, model, attempt limit), and the user approves it before the design is finalised. Thresholds are set with the user before the run.

**Out of scope:** competitor/provider benchmarking beyond the models that can be accessed with the user's account.

---

## R-PRODUCT-VISUALS-009 — Integrated scene as the primary path

- **Status:** Approved (2026-11-09; ADR-028)
- **Priority:** P0
- **Amends for phase 2:** R-002 candidate use/cropping, R-004 review scope, R-006 fallback priority. The existing evaluator remains a separate comparison tool.

As the operator, I want GPT Image to recreate/integrate my referenced product naturally into the scene, without depending on a perfect cutout.

Acceptance criteria:

- [ ] The default generation path sends the original product photo(s) directly as product references. A cutout is neither required nor automatically generated; an unavailable segmentation model cannot block scene generation.
- [ ] Instructions preserve the confirmed model, colour, proportions, manufacturer markings and visible hardware details, while integrating perspective, light and contact shadows. Generative fidelity is reviewed, never guaranteed by prompt wording alone.
- [ ] The target format and space needed for selected overlays inform the composition. The model adds no commercial text, shop logo, price, claims, watermark, external award graphic or extra product/accessory. Markings on the product itself remain subject to fidelity review.
- [ ] A finished candidate is `pending_review` and appears within an editable poster draft, with an explicit unapproved indicator. Final confirmation/export remains blocked until fidelity review approves it.
- [ ] Review compares original and generated product at useful zoom on phone/desktop. It checks shape, colour, branding, visible hardware, unwanted objects/text and realistic integration, plus the whole-product framing for each format being confirmed. It does not pretend an unreviewed crop is approved.
- [ ] Refinement or a new scene creates a separate candidate; no generation overwrites an approved image or changes the original files.
- [ ] Tests include the saved real JBL/Soundcore references and representative messy shop photos. A result that looks attractive but changes product identity fails fidelity review. The two manufacturer-image successes alone do not establish pilot readiness.

Out of scope: arbitrary product dragging within the raster scene and automatic fidelity certification.

## R-PRODUCT-VISUALS-010 — Refine a selected scene without losing it

- **Status:** Approved (2026-11-09; ADR-028)
- **Priority:** P0
- **Amends for phase 2:** R-002's reject-only alternative rule and R-005's revision/campaign rule; normal draft allowances are defined in generation-jobs.

As the operator, I can improve a useful scene without discarding it or restarting blindly from the source photo.

Acceptance criteria:

- [ ] An explicit refinement can start from a selected pending, approved or rejected scene for the same product/input version. The request includes that scene as the editing reference and the original product photo(s) as identity references, with clearly distinct roles.
- [ ] The user specifies the desired change, such as softer lighting, less clutter or more headline space. Unrequested details should be preserved; review checks whether the model complied. The operator is not promised pixel-local editing.
- [ ] Keep the base candidate's pixels, status and provenance unchanged. The result is a new linked `pending_review` candidate recording the base, original hashes, instructions, model and cost.
- [ ] Failure, rejection, cancellation of selection or simply keeping the base leaves the previous draft scene available. An approved base does not lose approval merely because another version was requested.
- [ ] Each creative attempt is explicit and budgeted. There is no automated polish-until-approved loop and no background generation triggered by ordinary text/price edits.
- [ ] Same-request replay cannot spend twice or create duplicate alternatives. Selecting an older candidate after a late result is respected; new results never silently replace the selected scene.

Out of scope: brush masks, local retouching, image-to-layer extraction. The phase-1 evaluator's revision algorithm remains unchanged until an approved phase-2 design/task replaces it for normal drafts.

## R-PRODUCT-VISUALS-011 — Optional photo-preserving alternative

- **Status:** Approved (2026-11-09; ADR-028)
- **Priority:** P1; not a blocker for the integrated-scene workflow
- **Amends for phase 2:** R-006's automatic assumptions and baked-shadow warning.

As the operator, I may choose to preserve my original product pixels when a source is suitable, without being forced into this route.

Acceptance criteria:

- [ ] The photo-preserving route is an explicit optional action, including at a generation limit. It is never a prerequisite or automatic replacement for integrated generation.
- [ ] Preview and confirm the cutout before spending on a background. Show edges and retained source graphics clearly; inference success is not approval. Rejecting an unsuitable mask preserves the original and offers a better source or the integrated route.
- [ ] Opaque product pixels come from the original. No blind largest-component cleanup may silently delete legitimate detached product parts; no promise is made of a perfect mask for every photo.
- [ ] If this route supports moving/resizing the product, any rendered contact shadow follows its transform or is explicitly disabled. A stale baked shadow must not remain behind after moving the product.
- [ ] Keep the cutout, background and any independently required shadow available for editable composition, with their original provenance. The composed result still requires fidelity and format review.

Out of scope: manual mask painting or a new segmentation model in this change. Implementation of this amended alternative follows the primary scene/editor path, with its own design and tests.

## Open questions (must be answered before approval)

None. R-009–011 were approved on 2026-11-09 (ADR-028); renderer/model/job/storage choices belong to the separately approved technical designs. Earlier approvals remain scoped to R-001–008 and phase 1.

## Resolved questions

- 2026-11-06 — **Design questions** (ADR-011, user: "go with all recommended"): shadow baked into the background; R-003 c.1–2 and R-004 c.2 wording amended; phase 1 (CLI evaluation) before the phone UI; evaluation-only limit 5 with an arm without corrections; attempt count restarts only with an explicit new campaign after an approval (R-005).
- 2026-11-06 — **Account and cap:** the user's own OpenAI account; the user provides the key through `.env`. The cap is a required configuration value that the user sets before the paid run (R-008, ADR-010).
- 2026-11-06 — **Attempt limit: 3** generated attempts per product variant (R-005, ADR-010).
- 2026-11-06 — **Prototype:** there is none. The cutout tool for R-006 is chosen in the design, from scratch.
- 2026-11-06 — **Fixture photos:** the user will supply them. They block only the paid evaluation run (R-008), not the design.
- 2026-11-06 — **Candidates per request: 1** (ADR-009). See R-002.
- 2026-11-06 — **Fallback product: separate layer, option A** (ADR-009). See R-006 and R-007. poster-editor requirements must support moving and resizing the cutout layer. The product in a `scene` treatment still cannot be moved on its own.
