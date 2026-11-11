# REQUIREMENTS — poster-editor

**Status:** Approved by the user on 2026-11-09 ("go aheadt with the requirement"; ADR-028). Technical designs remain subject to their separate approval gate.

| ID | Title | Priority | Status |
|---|---|---|---|
| R-POSTER-EDITOR-001 | A complete, editable first draft | P0 | Approved |
| R-POSTER-EDITOR-002 | Polish and confirm a version | P0 | Approved |
| R-POSTER-EDITOR-003 | Manual and prompted text/effect editing | P0 | Approved |

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
