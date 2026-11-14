# REQUIREMENTS — poster-editor

**Status:** Approved by the user on 2026-11-09 ("go aheadt with the requirement"; ADR-028). Technical designs remain subject to their separate approval gate.

| ID | Title | Priority | Status |
|---|---|---|---|
| R-POSTER-EDITOR-001 | A complete, editable first draft | P0 | Approved |
| R-POSTER-EDITOR-002 | Polish and confirm a version | P0 | Approved |
| R-POSTER-EDITOR-003 | Manual and prompted text/effect editing | P0 | Approved |
| R-POSTER-EDITOR-004 | Guided creation in steps, one group of controls at a time | P0 | Approved 2026-11-13 (ADR-072) |
| R-POSTER-EDITOR-005 | Remove an element from the poster | P1 | Approved 2026-11-13 (ADR-072) |
| R-POSTER-EDITOR-006 | Visual language: the poster first, glass only on floating chrome | P2 | Approved 2026-11-13 (ADR-072); amended the same day (ADR-075) |
| R-POSTER-EDITOR-007 | Phone-first editor: the poster stays in view | P0 | Approved 2026-11-13 under the autonomy grant (ADR-075) |
| R-POSTER-EDITOR-008 | Honest waiting while a poster is generated | P1 | Approved 2026-11-14 under the autonomy grant (ADR-079) |

## R-POSTER-EDITOR-001 — A complete, editable first draft

As the operator, I receive a composed advertisement from my product photo, title and price, ready to polish.

Acceptance criteria:

- [ ] Generation opens a complete draft with the scene, exact confirmed title and price, and only the selected shop fields. Text and logo are separate editable objects; no fixed HTML poster template limits composition.
- [ ] A pending scene can be previewed and edited in a draft clearly marked as awaiting fidelity review. It cannot produce a confirmed/exportable poster until approved. This amends the old prohibition on placing any pending visual in an editor.
- [ ] On phone and desktop the operator can edit text/price, fonts, size, colour, alignment and position; resize/reposition the supplied logo; change shop inclusion choices; and crop the scene. These operations make no image-generation call.
- [ ] Undo/redo covers ordinary edits, including inclusion choices. Text can be edited with the keyboard; selection and controls have accessible labels and usable touch targets. French accents and multiline contact text render correctly.
- [ ] An integrated product remains part of its raster scene. Controls do not pretend to drag it independently; changing its pose, surroundings or lighting opens an explicit scene-refinement action.
- [ ] New text/identity choices can reflow overlays or be adjusted manually. A need for more scene space is explained and a paid refinement is optional, never automatic.
- [ ] Long titles, large prices or contacts cannot disappear or become silently tiny. Visible overflow/overlap indicators identify the affected layer and block final confirmation while required content is clipped.

Out of scope: a general-purpose graphics suite, automatic extraction of raster layers, multi-product posters and autonomous copywriting.

## R-POSTER-EDITOR-002 — Polish and confirm a version

As the operator, I can compare refinements, keep a good result and confirm exactly what I will download.

Acceptance criteria:

- [ ] Manual editing and paid scene refinement are clearly distinct actions. A refinement uses the selected previous scene and the original product references, preserving that previous version while the new result is reviewed.
- [ ] The operator can retain, reject or compare a refinement. Rejecting it does not reject or replace the approved base. Selecting another scene preserves existing text and shop choices; any resulting layout problem is shown.
- [ ] Scene fidelity approval checks the original product; final poster confirmation separately checks visible commercial content, identity, composition and the chosen format.
- [ ] Confirmation freezes the selected scene, exact layer contents, shop choices, layout and format as one version. Any later visible edit creates an unconfirmed version requiring confirmation again; prior confirmed versions remain accessible.
- [ ] Saving/rendering failure is visible and does not falsely mark the edited version as saved or confirmed. The operator can retry with their edits still available.

Out of scope: local masked retouching. Draft persistence/version rules belong to creation-library; download checks belong to format-export.

## R-POSTER-EDITOR-003 — Manual and prompted text/effect editing

**Status:** Approved from the user's explicit request and selected separate-layer approach, 2026-11-09 (ADR-030).

As the operator, I can polish the product title or price with manual controls or a prompt, while keeping the rest of my poster intact.

Acceptance criteria:

- [ ] Title and price keep authoritative text/numeric values and their own editable text/effect layers over a clean product scene. They can look integrated through typography, texture, colour, light and shadow without flattening the whole poster.
- [ ] The operator selects a text element and can either edit its controls or request a French prompt-based adjustment. Both routes change the same selected layer; other layer contents and the underlying scene remain unchanged.
- [ ] A prompt yields a reviewable proposal with before/after comparison. Applying it creates a new draft revision and supports undo. Rejection, provider failure or a stale proposal leaves the current poster unchanged.
- [ ] Exact spelling, font selection and price formatting come from confirmed content and an available font. A requested unsupported font is identified, not silently approximated or substituted.
- [ ] Any proposed title/price content change is shown explicitly and requires operator confirmation. Neither model can invent a new amount, specification or discount and silently apply it.
- [ ] Image-generated text effects, if requested, are isolated to the selected element. They do not require a cutout of the product, regeneration of the full scene, or rewriting other text. Manual text/font changes remain possible without a new image call.
- [ ] Ordinary manual edits have no provider spend. Prompt/model calls are explicit, budgeted and versioned; the user can choose the existing manual controls if a requested effect is unsupported or generation fails.
- [ ] Final confirmation/export includes the exact selected text/effect state. A later manual or prompted edit requires a new confirmation; prior confirmed PNGs remain unchanged.

Out of scope for this version: text engraved into physical scene surfaces; guaranteed exact typography from model-generated raster glyphs; automatic whole-poster polishing.

## R-POSTER-EDITOR-004 — Guided creation in steps, one group of controls at a time

**Status:** Approved on 2026-11-13 by Claude under the user's autonomy grant (ADR-072). From the user's request of that day: "make the image generation with multiple step with less control, instead of all control in one view, that will confuse user. Group similar control in the same panel".

As the owner, I am taken through a new poster one small step at a time, and I never face every control at once.

Acceptance criteria:

- [ ] Before a poster has its first version, the editor shows one step at a time, in this order: "Textes", "Boutique", "Style". (The product step, photo, name and price, is the existing first screen.) Each step shows only its own controls, a "Continuer" and a "Retour" action, and where the owner is ("Étape 2 sur 4").
- [ ] The owner can go straight through: with nothing changed in a step, "Continuer" works, and the last step's main action is "Générer l’affiche" with its paid confirmation, as today.
- [ ] A step that was visited can be reopened from the step indicator. Nothing typed in a step is lost by moving between steps.
- [ ] After the first version exists, the same groups are tabs beside the poster, one visible at a time, plus "Réglages" for fine adjustments. The poster and the main action stay visible.
- [ ] Controls of a kind live together and nowhere else: "Textes" holds title, price, brand, subtitle, the coloured word **and its colour**, and what the image draws of them; "Boutique" holds logo, shop name, contact, its position, the round seal and the drawn contact; "Style" holds the styles, "create a style from a poster" and the ambiance; "Réglages" holds the typography of the selected text, its position and size, and the text instruction.
- [ ] No control that an action needs is inside a closed section (T-UX-HIDDEN-RULES). WHEN the main action is blocked THEN its reason is shown beside it and, when the control that unblocks it is in another step or tab, the reason opens that step or tab.
- [ ] On a phone (360 px wide) a step fits without horizontal scrolling, the main action stays reachable at the bottom, and the poster can be looked at from any step.
- [ ] Error case: WHEN a refusal names a field THEN the step or tab that holds the field is opened and the message is shown there.
- [ ] Every rule that exists today still holds: the paid confirmation, the small-photo agreement, the reasons for a title that cannot be drawn, the fidelity review, the stale-text notices, autosave and its recovery.

Out of scope: changing the first screen (photo, name, price); removing any existing setting; a different order of the server's steps; the "three inputs and one button" shop kit (later requirement).

## R-POSTER-EDITOR-005 — Remove an element from the poster

**Status:** Approved on 2026-11-13 (ADR-072). From the user's request: "add a possibility to remove a comp from an affiche view".

As the owner, I select something on the poster and take it off, without looking for its checkbox.

Acceptance criteria:

- [ ] WHEN the logo, the shop name or the contact is selected on the poster (tap, click or keyboard) THEN an action "Retirer de l’affiche" is shown next to the poster. It removes the element at once, the change is saved like any edit, and "Annuler" brings it back.
- [ ] A removed element can be put back from the "Boutique" group; its box there reflects what the poster shows.
- [ ] The title and the price cannot be removed: a poster always states the product and its price. WHEN one of them is selected THEN the action is not offered and a short line says why.
- [ ] WHEN the selected element is drawn inside the image of the current version (drawn contact, logo on its disc) THEN the poster says that this version's image contains it, and offers to leave it out of the **next** version instead; nothing is erased from the image.
- [ ] Error case: WHEN the change cannot be saved THEN the existing save-recovery applies and the element is not silently lost or kept.

Out of scope: deleting versions; erasing part of a generated image; removing the product.

## R-POSTER-EDITOR-006 — Visual language: the poster first, glass only on floating chrome

**Status:** Approved on 2026-11-13 (ADR-072). From the user's request: "You can explore glassmorphism, or another styles."

Acceptance criteria:

- [ ] The poster is the brightest and largest thing on the editing screen; panels are quiet.
- [ ] Translucent, blurred surfaces are used only on what floats above content: the header, the fixed action bar on a phone, dialogs and sheets, notices. Content panels and fields keep solid surfaces. WHERE the browser cannot blur, or the person asked for less transparency or less motion, THEN the same surfaces are solid.
- [ ] Every text keeps a contrast of 4.5:1 or more in both themes (3:1 from 24 px), measured by the browser smoke on the screens it visits.
- [ ] Touch targets are at least 44 px on touch screens; focus is always visible; no layout jump when a step or tab changes.
- [ ] No new dependency and no image or font downloaded from another site.

Out of scope: a new brand, illustration or logo; the look of the posters themselves.

### Amendment to R-POSTER-EDITOR-006 (2026-11-13, ADR-075)

From the second UI review and its mockup (https://claude.ai/artifact/6JoS82gMXkucaat4FKvUia), which the user called "promising". **Waiting for the user's choices** (ADR-075): the theme by default, Figtree. Until he answers, dark stays the default. These criteria add to the ones above once chosen.

- [ ] The application follows the device's light or dark setting until the person picks one with the theme button; that choice is remembered on the device and wins afterwards. The browser's bar colour (`theme-color`) matches the theme in use.
- [ ] Light theme: warm off-white ground, white panels, ink-black main buttons, the brand amber as the only accent (current step, selection). Dark theme: as today.
- [ ] Interface type: Figtree, bundled with the application with its licence file; nothing is requested from another site. The poster's own fonts and the renderer are unchanged.
- [ ] Choices that change the poster at once (logo, shop name, contact, outline, shadow, moving the elements) look like switches; their keyboard and screen-reader behaviour stays that of a checkbox. Choices that only change the next version (what the image draws, the round seal) stay checkboxes under a heading « Pour la prochaine version ». Agreements stay checkboxes.
- [ ] A selected choice (word chips, colour swatches, styles, steps and tabs) differs from the others in shape as well as in colour.
- [ ] Main buttons and fields are at least 48 px high, 52 px on touch screens.

## R-POSTER-EDITOR-007 — Phone-first editor: the poster stays in view

**Status:** Approved on 2026-11-13 by Claude under the user's autonomy grant (ADR-075), after the user called the mockup "promising".

**Background, measured on 2026-11-13 at 360 × 740 with a touch pointer** (reviews/ux-review-opus-2026-11-13.md): in the steps the poster is a 104 × 130 thumbnail; after the first version the poster starts at 479 px, the tabs at 1,289 px and the first field at 1,725 px, so 0 % of the poster is on screen while the owner types a price. On arrival in « Textes », the first field starts at 665 px, behind the bottom bar.

As the owner on my phone, I see my poster change while I type its words, and I reach every control without losing sight of it.

Acceptance criteria (all on one-column screens, measured at 360 × 740 with a touch pointer unless said otherwise). Amended the same day after the design review (ADR-075): the draft poster before the first version shows only the title and the price, so during the steps the chrome is cut rather than the draft pinned.

- [ ] On arrival in « Textes », the first field starts in the upper 60 % of the screen.
- [ ] During the steps, the poster is a thumbnail beside the step; « Voir l’affiche » shows it large.
- [ ] Once a version exists, the poster stays on screen while the controls scroll under it, at least 200 px tall when no field has the focus. When a text field has the focus, the poster collapses to a strip of about 96 px and the bottom bar hides; both come back when the focus leaves. The focused field is never under the poster.
  - *Amended 2026-11-14 (ADR-086):* in tabs the sticky poster is about 163 px tall at 360 × 740 (`posterHeight`, 22 % of the visible height, 96 to 180 px), not at least 200 px; on phones the versions row folds behind a « Versions (n) » button; while a text field has the focus, and on any screen under 500 px of visible height (keyboard open), the poster shrinks to the strip of about 96 px instead of disappearing, and the controls stay reachable. Reason: user report that the controls were hard to reach ([UX audit](../reviews/ux-audit-2026-11-14.md)) and user decision of 2026-11-14.
- [ ] « Voir l’affiche » shows the poster large in tabs too.
- [ ] The editor has one bar at the top: back to « Mes affiches », the poster's name and its save state, undo, redo. The application's header is not shown in the editor on phones.
- [ ] After the first version, the versions are a horizontal strip under the poster, each with its state in words, and the groups (« Textes », « Boutique », « Style », « Réglages ») are a row of tools with an icon and a label each; the main action stays at the bottom of the screen.
- [ ] The fidelity review shows one image at a time, at full width, with a « Votre photo / La version » choice; « La version » first. Its decision stays at the bottom of the screen (done in T-UI-REVIEW-2).
- [ ] If the user agrees: outside the editor, « Créer », « Mes affiches » and « Styles » are a bar at the bottom of the screen, each with an icon and its label; the current one is marked.
- [ ] Nothing scrolls sideways at 360 px; touch targets are at least 44 px; the smoke's contrast check passes on these screens in both themes.
- [ ] Every rule that exists today still holds: steps and tabs (R-POSTER-EDITOR-004), removal from the poster (005), the paid confirmation, the small-photo agreement, the reasons beside a blocked action, the fidelity review, the stale-text notices, autosave and its recovery.

Out of scope: the desktop layout (a later task: tools in a vertical rail, versions under the poster); « Mes affiches » as a grid of cards with status filters (a later task); the share sheet; the owner's vocabulary (no dollars).

## R-POSTER-EDITOR-008 — Honest waiting while a poster is generated

- **Status:** Approved 2026-11-14 under the autonomy grant (ADR-079). User: "Can we implement also codex finding on the generation animation? It have a preview in it's branch". Source: Codex's local prototype and its reviewed requirements R-GEN-EXP-003 and 004 (worktree `codex/generation-cost-ux`, `docs/project/requirements/generation-experience.md`, `frontend/src/generation-lab/`), here applied to the real editor and the real job.
- [ ] While a scene or an adjustment of the scene is being made, the editor tells apart: waiting to start, being created, image being received, ready to check, failed. The words come from the real job's state, never from a timer alone.
- [ ] The elapsed time is shown (minutes and seconds), with no percentage, no countdown and no invented sub-stage. Three steps are shown: « Demande enregistrée », « Création de l'affiche », « Image prête à vérifier ».
- [ ] After 100 seconds of creation a sentence says it is longer than usual, that the request is still running and that starting again is useless. It asserts neither failure nor success.
- [ ] « Annuler la demande » exists only while the job waits to start. Once creation started, nothing suggests that leaving cancels the call or refunds it.
- [ ] A lost connection is its own state: « Connexion interrompue », the request continues, the editor keeps looking and never starts another attempt. On return to the tab the state is refreshed at once.
- [ ] The poster area stays visible: the previous version labelled as kept, or the draft at the first generation; a small state pill sits over it, in front (R-007's pill rule). No fake preview of the image being made.
- [ ] The new image appears only once loaded, with a short fade; it still needs the owner's fidelity check. A failure says so, keeps the previous version and adds none.
- [ ] Motion is calm (a thin moving rail, a pulsing dot); with reduced motion nothing repeats and the state stays clear. Screen readers hear state changes, not every second. Works at 360 px and on wide screens, both themes.
- **Out of scope:** the server, the job queue, streaming partial images, any change to what is paid or when.
