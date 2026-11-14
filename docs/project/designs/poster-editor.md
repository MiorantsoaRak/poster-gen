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

## D-POSTER-EDITOR-004 — Steps, tabs, removal and the glass chrome (covers R-POSTER-EDITOR-004, 005, 006)

**Status:** Approved on 2026-11-13 by Claude under the autonomy grant (ADR-072). No design review before building: the result is reviewed by a fresh reviewer and shown to the user on a local server before any deploy (he steers by looking).

**Approach:** the editor's rail stops being three stacked cards. One reactive value names the visible group (`textes`, `boutique`, `style`, `reglages`). While the poster has no version, the groups are steps with "Retour" and "Continuer" and the main action only on the last; once a version exists they are tabs and the main action is what it is today (review, final preview). Nothing changes on the server and nothing in the saved document: this is the editor's presentation only.

**Data model changes:** none. **API:** none.

**State:** `group` (the visible one), `visited` (steps already opened, for the indicator). Not persisted and not in the address: a reload returns to the first step of an unversioned poster, or to "Textes" of a versioned one. Field values live where they do today, so moving between groups loses nothing.

**Moves between groups:** the accent colour joins the accent word in "Textes"; "what the image draws" is split by subject (title and price in "Textes", contact and seal in "Boutique"); typography, position and the text instruction form "Réglages". No setting is removed.

**Blocked actions:** each reason knows its group (`whyNoHeadline` → `textes`, the contact reasons → `boutique`); the reason line carries a button that opens it. A refusal with `field` does the same (`offer.title` → `textes`, `contact` → `boutique`).

**Removal:** uses what exists: `include.logo`, `include.shop_name`, `include.contact` and the layer's `visible`, through the same `edit()` that feeds undo and autosave. A selected title or price shows why it stays. For an element drawn in the current image, the action sets the option for the next version and says so; the image is never edited.

**Glass:** two tokens per theme for a translucent surface and its border; `backdrop-filter` inside `@supports`, switched off under `prefers-reduced-transparency` and with a solid fallback colour first. Applied to the header, the phone's action bar, dialogs, sheets and notices only.

**Failure modes & handling:**

| Failure | Detection | Behaviour |
|---|---|---|
| A needed control ends up in a group that is not visible | Smoke: the walk on empty data never ticks or opens anything a first-time user would not | The reason opens the group; a test asserts it for the small photo and for a title with a quote |
| Blur is slow on a low-end phone | Seen in the phone session | Blur only on small fixed surfaces; one CSS switch turns it off |
| Text over a translucent surface loses contrast when content scrolls under it | Contrast check of the smoke; the surfaces' opacity is high enough that the worst case (lightest and darkest content under) still passes | Raise the opacity; the fallback is solid |
| The smoke's selectors move with the layout and a check is dropped by mistake | The count of assertions in the smoke does not go down; every removed line is listed in the review | — |

**Edge cases:** a reopened poster with versions opens on tabs, never on steps. A poster whose only version was rejected is in steps again (it has no usable version) but keeps its values. Keyboard: steps and tabs are buttons in a `tablist`; arrow keys move between tabs.

**Tests:** the browser smoke walks a new poster through the three steps on empty data without touching anything outside the visible step, checks the tabs after the first version, removes the logo from the poster and undoes it, checks that the title offers no removal, and keeps its contrast check on every screen in both themes. Vitest stays as it is (no logic moved out of the component).

## D-POSTER-EDITOR-005 — Phone-first editor (v2) and the look (covers R-POSTER-EDITOR-007, the amendment to 006)

**Status:** v2, 2026-11-13, after a fresh review and a devil's advocate on v1 (reviews/phone-first-design-r1-2026-11-13.md, ADR-075). Part A (structure) approved under the autonomy grant, to be built after the current fixes are released. Part B (look) waits for the user's choices. v2 was not reviewed again; its build gets a fresh code review.

**What changed from v1:** no sticky draft poster during the steps (the draft shows only title and price; the rest is drawn later by the image model), no `visualViewport` tracking, no `scroll-margin`, a smaller sticky area, the large view also in tabs, switches only where the change is immediate, the look separated and waiting.

**Approach:** presentation only. No change to the server, the saved document, the renderer or the poster's fonts.

### Part A — structure on one-column screens (task T-PF-STRUCT)

1. **Editor top bar (≤ 720 px).** While a poster is open, the application's header is hidden (a class `editing` bound on `<main>` and the header, since the component has several roots). The editor's title row is a sticky bar of about 56 px: « Retour à Mes affiches » (to `#affiches`), the poster's name on one line, the save state on one line, undo, redo; in demonstration mode a small « Démo » badge replaces the long notice. The phase list and the short phase text leave this bar. The 112 px `scroll-padding-top` rule for the old two-row header goes.
2. **Steps (≤ 1080 px): less chrome, same thumbnail.** The step count joins the row of steps (`.step-count` stays, the smoke reads it), the lead line is hidden on phones, the rail's paddings are tightened, the coach card is hidden (the bottom bar names the action). The poster stays the thumbnail with « Voir l'affiche », which opens the large view. Target: the first field of « Textes » above 444 px at 360 × 740. Tapping the thumbnail opens the large view instead of selecting an element (the selection and « Retirer » live in the large view and in « Boutique »).
3. **Tabs (≤ 1080 px): the real image on top.** Once a version exists, `.stage:not(.peek)` is sticky under the top bar and holds only the poster and one horizontally scrolling row of elements. The other blocks of the stage (head, job state, polish preview, save recovery, issues, the selection and its removal text) follow the stage: they sit in a wrapper that is `display: contents` on one column, so `.stage` stays the element of the large view. The poster's height is `posterHeight(visibleHeight)`: about 34 % of the visible height, at most 420 px, at least 96 px, in its own module with Vitest cases; the scale is `min(hostWidth / W, posterHeight / H)` when not peeking, the current rule when peeking. The canvas host loses its 240 px minimum on one column.
4. **Typing with the poster on top.** When a text field of the panel takes the focus, the sticky poster collapses to a strip of about 96 px and the bottom bar hides; both come back when the focus leaves the panel's fields. `<meta name="viewport">` gains `interactive-widget=resizes-content`, so on Chrome for Android the existing resize handler sees the keyboard; a rescale happens at most once per frame and ignores height changes under 100 px (the address bar). The offset under the sticky area is one variable, `--sticky-top`, measured by a `ResizeObserver` that ignores entries while peeking, applied as `scroll-padding-top` inside the editor only, and used by `go()` instead of its fixed 56/200.
5. **Large view in tabs.** « Voir l'affiche » exists in tabs too (the `stepping` condition leaves `peeking`); `.main-action` is hidden inside the large view.
6. **Versions strip (tabs, ≤ 1080 px).** One horizontal row of thumbnails about 56 × 70 under the poster, each with its state word in small type (not a dot alone), « Choisie pour l'export » under the chosen one, « Comparer » kept, then the « Nouvelle version » tile.
7. **Tools row.** The four groups as a row of tools (icon and label: add `store` and `sliders` to the icons), not sticky; the active one marked by a pill behind its icon.
8. **Notices in the editor** sit above the bottom bar on one column, not at `top: 108px` over the poster.
8b. **Pills and badges over the poster are always in front** (user, 2026-11-13: "make sure that pill and badge is always at the first plan", then "I am talking about the « Aperçu » pill too"; ADR-076). The generation chip, a small « Aperçu » pill on the draft poster during the steps (the draft is a preview: the scene comes at generation), and the version's state badge on the poster in tabs carry an explicit `z-index` above the canvas and are never covered by the sticky bars, the tools row or a panel. The tools row and the bottom bar stay visible above anything that opens under them. The smoke checks the topmost element at the pill's centre (`document.elementFromPoint`) is the pill.
9. **One image at a time in the review (≤ 720 px).** `compareSide` (« La version » first), reset in `resetChecks()`; a two-button choice « Votre photo / La version »; « Votre photo » shows the owner's photos one under the other; wide screens keep the two sides.
10. **Bottom navigation (≤ 720 px), if the user agrees.** One `.nav` element (the smoke clicks `.nav a`); at 720 px and below the header loses its `backdrop-filter` and the nav, fixed at the bottom with its own blur, shows « Créer », « Mes affiches », « Styles » with icons, labels, counts and `aria-current`; hidden while `editing`; `main` gets its height as bottom padding.

**Never** put `backdrop-filter`, `filter`, `transform` or `will-change` on `.stage` or `.app-header` children that hold fixed elements: they become the containing block of `position: fixed` descendants.

### Part B — the look (task T-PF-LOOK; approved 2026-11-13, ADR-077)

**Amendment 2026-11-14 (ADR-077):** the user approved mockup version 20 ("let's go with that for now"). The conditionals below are settled: the theme follows the phone, Figtree is used, and glass is on every surface. Added to this part:

- **Glass on every surface** (replaces ADR-072's "floating chrome only"): panels, cards, sheets, bars, the tools row, badges, fields, chips, secondary buttons and tiles are translucent with `backdrop-filter`. Tokens as in the mockup: light `--glass-panel: rgb(255 255 255 / .74)`, field `.62`, strong `.92`; dark `rgb(30 28 26 / .58)`, field `rgb(255 255 255 / .07)`. Panels blur 26 px, fields 16 px. The backdrop is three fixed soft colour patches on the page ground (pale blue, pale blue, warm cream; 12 % strength in dark), on a fixed pseudo-element of the root, never a blurred copy of the poster.
- **Constraints:** the rule at the end of part A holds: no `backdrop-filter` on an ancestor of a `position: fixed` element (the bottom bar, the bottom navigation, dialogs, the large view); put the blur on the leaf or a pseudo-element. Text on glass keeps 4.5:1 over the darkest and lightest part of the backdrop (the smoke's contrast check measures it). `@supports not (backdrop-filter: blur(1px))` and `prefers-reduced-transparency: reduce` give opaque surfaces. `forced-colors` unchanged.
- **Controls:** one reset that single-class rules can override; on one-column screens every tappable element is at least 44 px and bottom-bar buttons 52 px, bold 15.5 px; the poster's shadow is short (light `0 1px 2px .08, 0 6px 16px -6px .16`).
- **Owed before release:** a speed check on a low-end Android phone (the observed session, T-HOST-004).


- Theme default: if the user chooses "follow the phone": a one-line inline script in the head of `index.html` sets `data-theme` before the first paint, two `theme-color` metas with `media`, the `theme` ref follows a device change while no choice is stored, `toggleTheme` reads the colour from the tokens; the smoke pins `color_scheme="dark"` where it toggles. If he keeps dark: only the light tokens change.
- Light tokens as in v1, with faint `#67605A` (4.5:1 on the well) and the off switch track outlined in `--muted` (3:1).
- Figtree (if chosen): variable woff2, Latin, checked with fontTools for U+202F and tabular figures; licence file alongside; replaces the two Noto Sans preloads.
- Switches only for immediate changes: Logo, Nom de la boutique, Contact, Contour, Ombre, Déplacer les éléments. « Laisser l'IA composer le titre », « Dessiner aussi le prix », « Dessiner aussi le contact », « Écrire la marque en texte simple » and « Logo en sceau rond » stay checkboxes under a heading « Pour la prochaine version ». `forced-colors` restores the native control.
- Selection by shape, 48/52 px controls, larger radii, as in v1.

**Data model, API:** none.

**Failure modes & handling:**

| Failure | Detection | Behaviour |
|---|---|---|
| The keyboard on a browser without `interactive-widget` (Safari, perhaps Samsung Internet) | — | the poster still collapses on focus and the bottom bar hides; the field stays reachable by scrolling. Checked on the owner's phone (T-HOST-004) |
| The address bar shows and hides during scrolling | height change under 100 px | ignored: no rescale under the finger |
| A short screen (landscape) | `posterHeight` | 96 px floor, never more than about 40 % |
| The large view opened from tabs | smoke | full size, no bottom bar inside, the page behind inert |
| A smoke assertion loses its target | smoke | kept or retargeted; changes listed in the code review |

**Tests:** Vitest for `posterHeight`. Smoke at 360 × 740 with a touch pointer: first field of « Textes » above 444 px; in tabs the poster is on screen and at least 200 px tall with nothing focused, collapses when « Prix » takes the focus and comes back after; the large view in tabs; the editor's top bar and back button; the review's choice shows one side at a time; the bottom navigation if built; contrast in both themes. The measurement walk rerun at 360 px.

## D-POSTER-EDITOR-006 — Waiting while a poster is generated (covers R-POSTER-EDITOR-008)

**Status:** v1, 2026-11-14, approved under the autonomy grant (ADR-079). Adapted from Codex's reviewed prototype (worktree `codex/generation-cost-ux`: `frontend/src/generation-lab/Lab.vue`, `lab.css`, `simulation.ts`, design `docs/project/designs/generation-experience.md`). Its build gets a fresh code review.

**Approach:** frontend only. `GET /api/jobs/{id}` already returns `status`, `created_at`, `started_at`, `finished_at`. No server change.

1. **A pure module `frontend/src/generation.ts`** (Vitest): `phase(job, loaded)` gives `queued | running | receiving | ready | failed` from the job's status and whether the result image has loaded; `elapsedLabel(ms)` gives `m:ss`; `overdue(phase, runningMs)` is true after 100 000 ms in `running`. The `Job` type gains the three timestamps.
2. **Elapsed time** counts from the moment the editor started following the job when it created it, and from the server's `created_at` when it finds a job already active on opening a poster (corrected by the difference between the response's `Date` header and the local clock when the header is readable, never negative). A 1 s ticker runs only while a scene or refine job is followed and the tab is visible; it is cleared when the job ends and on unmount.
3. **The waiting block** replaces the one-line `.job-state` for the kinds `scene` and `refine` (other kinds keep today's line): a heading and one sentence inside one `role="status"` (state changes only), the elapsed time outside it (not announced), a 2 px rail with a moving segment, the three steps as a list, « Annuler la demande » while `queued`. Words as in the prototype, adjusted to the app (« Votre affiche prend forme. » …); the existing sentence about what stays editable is kept under it.
4. **Over the poster:** the existing generation chip shows the state word (« En attente », « Création en cours », « Réception ») with a pulsing dot, z-index as in D-005 item 8b; the frame gets `aria-busy`. The stage label says « Version précédente conservée » when a version exists.
5. **Receiving:** when the job succeeds, the new visual's image is decoded (`Image.decode()`) before the document switches to it; meanwhile the phase is `receiving`. A decode failure shows the image anyway through the normal path with a notice (the visual exists server-side; nothing is lost). The swap fades in 200 ms.
6. **Connection:** a failed poll does not clear the job: the block shows « Connexion interrompue. La demande continue… », polling goes on with a backoff (2 s, 4 s, 8 s, then 10 s), and the first success restores the state. `visibilitychange` to visible polls at once instead of waiting for the 10 s hidden timer.
7. **Reduced motion:** the rail is a still full-width line at reduced opacity and the dot does not pulse.

**Failure modes & handling:**

| Failure | Detection | Behaviour |
|---|---|---|
| The poll fails (network, 5xx) | rejected request | connection state, backoff, no new attempt, no lost job |
| The job fails or its outcome is uncertain | `status` | today's `jobFailure` sentence, previous version kept; the uncertain-outcome protection is unchanged |
| The result image cannot be decoded | `decode()` rejects | switch through the normal path, notice |
| Client clock wrong | `Date` header | elapsed corrected; without the header, counted from first sight |
| The tab sleeps for minutes | `visibilitychange` | immediate poll; elapsed recomputed from timestamps, not from tick counts |

**Tests:** Vitest for `generation.ts`. Smoke with the stub provider slowed enough to see each state (if the stub's delay can be set for the smoke's isolated server; otherwise route interception on `/api/jobs/*`): the pill and words while queued and running, the elapsed time advancing, cancel only while queued, a poll failure showing the connection state then recovering without a second `POST /scenes`, the long-wait sentence with a mocked clock, reduced motion (no running animation), the pill topmost (`elementFromPoint`), 360 px and 1366 px, contrast in both themes.

