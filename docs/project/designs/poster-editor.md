# DESIGN — poster-editor

**Status:** Approved v1, 2026-11-09. **Approval:** ADR-031. **Requirements:** [poster-editor](../requirements/poster-editor.md), R-001/002 approved ADR-028 and R-003 approved ADR-030.

## System overview

Vite + Vue 3 + TypeScript + Konva/vue-konva. A versioned PosterDocument is the source of truth; the canvas is a rendering of it. The same PosterCanvas Vue component runs interactively in the browser and read-only in the server's pinned Chromium renderer. No HTML poster templates or saved Konva node trees. A clean scene remains reusable under independently editable text/effect and identity objects.

## D-POSTER-EDITOR-001 — Document, canvas and initial composition

**Covers:** R-POSTER-EDITOR-001; R-CATALOGUE-BRAND-002; R-FORMAT-EXPORT-001.

**Document contract (schema_version=1):**

```text
input_id: immutable product input UUID
offer: {title: string, price_ar: integer, currency: "MGA"}
brand_snapshot: {profile_revision, name?, contact?, logo_asset?}
include: {logo: boolean, shop_name: boolean, contact: boolean}
primary_format: feed|square|story
formats: {format: {scene:{visual_id?,crop:{x,y,w,h}}, layers:[Layer], framing_review?}}
Layer: {id,kind:text|logo|product_cutout,role:title|price|shop_name|contact|logo|product,
        x,y,width,height,visible,z, ...kind_specific_fields}
Text: {font_id,font_size,weight,fill,align,line_height,outline?,shadow?,texture_effect_id?,price_badge?}
Logo/product: {asset, keep_aspect:true}; product optional in preserved-photo treatment only
```

Coordinates are logical canvas pixels, independent of CSS size/devicePixelRatio. Crop is source-image pixel coordinates, positive and within the decoded image; use uniform scaling, no image stretching. Text nodes bind to authoritative offer/brand values through role; there is no duplicate editable copy of price or hidden model-generated text in node config. Include flags determine visibility; reject inconsistent flags/missing sources. One title and one price per format are required. Unknown properties, nonfinite numbers, duplicate IDs/roles and arbitrary URLs are refused. Shape/custom-code/plugin nodes are outside V1.

Application bounds: ≤20 layers per format; font size 24…240 logical pixels, line height 0.8…2; weight limited to bundled variants; opacity 0…1 on supported effects; x/y may extend during drag but final confirmation rejects required content outside canvas. Clamp render memory independently. Default fonts: bundled Noto Sans and Noto Serif, regular/bold, with their licences and hashes packaged at implementation. Font IDs refer to that manifest; no arbitrary CSS/font URL. A font not available is an explicit unsupported_font error, not a silent substitute. A font-upload UI is not needed for this slice; new licensed fonts can be registered in the manifest later.

**Initial layout:** compute flexible field boxes from the validated scene plan or a deterministic default allocator: product region reserved, title above, price below, selected brand details in remaining space. Use measured text footprint, margins and visible fields, not a catalogue of fixed HTML layouts. All placement/typography remains editable. If actual scene composition disagrees with planned geometry, show it; let the operator adjust overlays/crop or explicitly refine the scene. Never auto-cover the product to force a template.

Canvas fits available viewport with CSS scaling. Transformer controls for allowed objects; logo/product resize preserves aspect; text resize changes its wrapping box, font size is a separate explicit control. The integrated scene has crop/pan controls, not a fictitious independent product handle. Selection outlines, handles and comparison overlays are excluded from rendering/export.

**UI:** French guided intake → direction/plan → complete draft → fidelity comparison → polish → server preview → confirmation/download. On phone: canvas above a contextual bottom panel, minimum 44 CSS px controls, single selected object, scroll/pan mode distinct from object drag. On desktop: canvas + properties/layers panel. Use native labelled inputs/textarea for text editing and price entry, not canvas-only typing. Accessible layer list, keyboard selection/arrows, explicit position/size fields and announced save/error state provide alternatives to drag. Pointer/touch selection must not steal page scrolling outside the canvas.

**State:** local document dirty → saving → saved revision; save_failed retains in-memory edits. Undo/redo stores up to 100 document changes, coalescing a drag or typing burst into one action. No provider call for ordinary edits, visibility, crop, font or price. Save on 750 ms idle and at gesture end, serialising writes; flush before any paid action/render/confirmation. Refresh recovers the last server-saved revision only; beforeunload warns for unsaved edits. Persistence/conflict API is in creation-library.

| Failure / edge | Handling |
|---|---|
| Canvas/font/image loading fails | Show failing asset/font; retain form controls/document; block render/confirmation, no fallback substitution. |
| Long French title/contact or large price | Measure wrapped text, show overflow badge and affected layer; allow resize/edit; never auto-shrink below 24 px or truncate. Price is nonbreaking. |
| Title/price overlap or cover product region | Warn in editor and require acknowledgement; clipped required content blocks confirmation. User reviews actual product framing visually. |
| Change brand switches after generation | Add/remove selected layers and optional reflow proposal; no scene call. |
| Two tabs save | Show revision conflict and reload/save-copy options; never silently overwrite. |
| Small phone | Accessible properties inputs remain available even when canvas handles are hard to use; test physical touch, not just desktop emulation. |

### Reference typography (2026-11-10, user-requested ADR-041)

`montserrat-black-italic` uses the bundled genuine italic face at weight 900; Noto IDs retain 400/700. Invalid pairs fail validation. Only price may set `price_badge:{fill,border_start,border_end}` (hex colours; defaults white/cyan-blue/darker blue). Shared rendering groups the exact amount with supported no-break spaces (U+00A0 for capsule/Montserrat; legacy Noto plain text retains U+202F) and smaller upright Noto Sans 400 `AR` inside a thin rounded gradient outline. The badge uses the layer's box; text keeps alignment and bounded outline/shadow/material. No separate scene/shape node. Manual edits and reviewable Claude patches address the same layer; null badge removes it. Missing/corrupt fonts and overflow fail explicitly. Null badge is omitted from canonical data to preserve existing hashes/replays; export fingerprints include the extra currency font. Historical PNG bytes remain unchanged. Verify genuine browser rendering, zero/large prices, invalid font/role, patch isolation, default compatibility and stale confirmation. No image call is needed for this typography adjustment.

## D-POSTER-EDITOR-002 — Scene approval and final confirmation

**Covers:** R-POSTER-EDITOR-002; R-FORMAT-EXPORT-002.

Visual status and poster status are separate. Pending scene may be previewed/edited; fidelity decision belongs to product-visuals. A draft with an approved scene still needs format/content confirmation. Selecting a new scene preserves offer/brand/layers and invalidates the changed format's framing review; it does not approve the new scene. Full scene refinement is a distinct action from selected text editing.

The editor requests a server preview for an exact saved revision/format. It displays that PNG at fit-to-screen with zoom and a visible checklist: product framing, exact title/price, selected shop details, readability. Confirmation submits the render ID/hash and revision; the server rechecks them and current approval/asset state. Download uses the stored confirmed render only. Any later visible edit creates another revision, without editing historical confirmations. Details and endpoints: format-export.

State: editing → saved → rendering → preview_ready → confirmed; edits during render yield a stale preview available for history but not confirmation of the current draft. Failure at any step leaves the draft and earlier confirmed posters. No automatic quality regeneration during export.

## D-POSTER-EDITOR-003 — Manual or prompted typography and isolated effects

**Covers:** R-POSTER-EDITOR-003; R-GENERATION-JOBS-001/002. This implements the user's separate-layer choice, not surface-embedded text.

**Approach:** exact letters/prices always come from the available font renderer. Claude interprets a French text-polish instruction as a constrained proposal for one selected role in one format. Optional GPT Image generates a decorative material texture; the renderer clips it to the selected text glyph mask, with outline/shadow owned by that same layer. No provider is asked to redraw the full poster or supply authoritative price glyphs. This avoids misspellings and keeps manual text/font edits possible.

**Data:** text_proposals(id,creation_id,origin_revision,format,layer_id,job_id UNIQUE,patch_json,status pending/applied/rejected,applied_revision nullable,created_at); text_effects(id,shop_id,job_id UNIQUE,input_layer_style_hash,texture_asset FK assets,material_prompt,palette_json,status proposed/applied/rejected,applied_revision nullable,created_at). Texture pixels use existing background_raw asset classification; usage in a text effect is determined by text_effects, not assets.kind. Texture bytes are immutable; only their first apply/reject decision changes. Applied effects can be retained in same-shop copies. Proposal apply/reject decision is terminal and idempotent.

TextPatchV1:

```text
schema_version: 1
layer_id: exact selected layer
style: optional allowed fields from Text plus x/y/width/height
content_change: null | {field:title|price_ar, value}       # proposed, never directly applied
texture_request: null | {description<=300,palette:[#RRGGBB]}
summary_fr: <=300
```

Only title/price text nodes are supported initially. No JSON Patch arbitrary paths, new layers, scene changes, hidden field changes or unsupported font names. Server compares the proposed field to the selected role and checks current revision/style hash, geometry, safe integer price, available font and effect bounds. Model output cannot address any other layer. A content change must match an explicit quoted title or unambiguous literal amount in the user's instruction and requires an extra before/after acknowledgement on apply. If the instruction is ambiguous or the value is not directly supplied, refuse that content change and offer manual entry; do not rely on a model to certify invented claims. Show affected formats because title/price content is shared, whereas style changes apply only to the selected format. No automatic new price/discount.

**API / steps:**

1. POST /api/creations/{id}/text-proposals with If-Match, Idempotency-Key, {format,layer_id,instruction_fr<=500} → 202 Claude patch job. The operator has explicitly requested a paid prompt action; manual controls remain free.
2. GET /api/text-proposals/{id} → validated patch + before/after diff. Preview applies it to a temporary local document only. POST .../{id}/apply {acknowledged_content_change:boolean}, with If-Match and Idempotency-Key, atomically applies allowed selected-layer changes as one new revision. Reject uses POST .../{id}/reject; neither path changes unrelated layers. 409 stale_proposal if the draft changed; no silent rebase.
3. If texture was requested, show the additional image-call estimate and a separate Generate effect action. POST /api/creations/{id}/text-effects {format,layer_id,proposal_id}, If-Match/Idempotency-Key → 202 texture job. Require the proposal already applied to the current revision; snapshot its current layer style/content hash. Rendered glyph content remains the current confirmed text. No automatic image call merely because Claude suggested a texture.
4. GPT Image creates one 1024×1024 material swatch with requested palette, no writing/product/logos, using images.generate through the existing gateway's background path. It need not support transparent output: the local glyph mask supplies alpha. The texture stays proposed until POST /api/text-effects/{id}/apply with If-Match/Idempotency-Key validates the originating creation/format/layer and unchanged revision/style hash, then adds the effect and saves one new revision. Reject uses POST .../{id}/reject. A generic document save may retain/reuse an already applied effect but cannot attach a proposed/rejected effect and bypass this review.
5. Text stays editable. Manual content/font/size changes rerender the glyph mask with the existing texture, without a provider call. Removing/changing the effect never alters the clean scene. If the requested effect cannot be represented by these layer controls/material fill, return unsupported_effect with manual alternatives; do not flatten the poster as a workaround.

The same shared renderer implements texture-filled glyphs in browser and server: render glyph alpha with the registered font, crop/scale the texture to the text box, apply source-in masking offscreen, then draw the result and the layer's bounded outline/shadow. It computes hit/overflow bounds including effects. Pixel tests must show unchanged output outside the union of old/new selected-layer bounds, given unchanged other layers/renderer inputs. Underlying scene hashes and other layer JSON must remain identical. A changed text layer necessarily changes pixels it occupies; no broader promise of image-model determinism is made.

| Failure / edge | Handling |
|---|---|
| Prompt tries to edit product/background/contact | Reject unsupported_target; keep selection; offer the distinct scene action only if user chooses. |
| Unsupported font or invented value | No silent substitution/application; show validation error or explicit content proposal requiring confirmation. |
| Provider/texture failure | Keep existing text/effect and offer manual controls; known/estimated cost retained. |
| User edits price while proposal/effect runs | Mark stale; preserve result for inspection but require a new explicit proposal/application against current state. |
| Texture reduces contrast/legibility | User rejects it; price/title remain readable controls; final preview checks before confirmation. |
| Effect extends beyond text bounding box | Bounds include outline/shadow; clip to selected effect surface, flag canvas clipping. |

## Choice, evidence and verification

| Option | Decision |
|---|---|
| Konva + vue-konva | Proposed: documented Vue bindings, object interaction, image/text rendering, predictable shared canvas component. Native form controls supply text editing/accessibility. |
| Fabric | Capable interactive text/object editor; not selected because it needs more imperative state synchronisation with the chosen Vue document model. No claim that it cannot work. |
| Native SVG | Fewer graphics dependencies, but more custom selection/transform/measurement/texture tooling for the requested editing flow. |

[Konva Vue bindings](https://konvajs.org/docs/vue/index.html), [application-state persistence](https://konvajs.org/docs/vue/Save-Load.html), [text editing](https://konvajs.org/docs/sandbox/Editable_Text.html) and [export](https://konvajs.org/docs/data_and_serialization/High-Quality-Export.html) support this proposed approach; [Fabric concepts](https://www.fabricjs.com/docs/core-concepts/) informed the alternative. Versions/licences must be pinned and the shared-component texture path proven in the first approved implementation slice.

Verification: pure document/schema/price/layout tests; manual/prompt changes with undo; stale/malicious patches; texture mask pixel isolation and no image call on manual edits; all eight identity combinations; French accents; long content; two-tab conflict; new scene preserving text; physical phone touch/keyboard; server preview equality. No such UI or effect-rendering spike has been implemented in this design session.
