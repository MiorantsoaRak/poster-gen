# REQUIREMENTS — format-export

**Status:** Approved by the user on 2026-11-09 ("go aheadt with the requirement"; ADR-028). Technical designs remain subject to their separate approval gate.

| ID | Title | Priority | Status |
|---|---|---|---|
| R-FORMAT-EXPORT-001 | Compose and review each format | P0 | Approved |
| R-FORMAT-EXPORT-002 | Download the confirmed poster | P0 | Approved |

## R-FORMAT-EXPORT-001 — Compose and review each format

As the operator, I choose the intended placement before generation and can adapt the same creation to other formats.

Acceptance criteria:

- [ ] Support feed 1080×1350, square 1080×1080 and story 1080×1920. The selected primary format and visible-field choices inform scene composition before generation.
- [ ] A first implementation slice may deliver feed only, but the pilot is not complete until all three formats pass the same workflow.
- [ ] Each format has its own editable layer placement and scene crop. Reuse the approved scene where suitable; do not force one universal centre crop or generate three scenes automatically.
- [ ] Before confirmation, preview the exact format and check that the product remains whole, selected text/shop content is legible, and no required content is clipped. Confirmation is specific to that format/version.
- [ ] If cropping cannot preserve the product or leave suitable text space, offer an explicit separately budgeted scene adaptation. Its result needs fidelity review and that format needs confirmation again.
- [ ] Switching format preserves prior layouts and confirmations. Editing a shared value marks every affected draft format as needing confirmation without changing already confirmed historical exports.

Out of scope: print/PDF/CMYK, arbitrary format sizes, automatic social publishing.

## R-FORMAT-EXPORT-002 — Download the confirmed poster

As the operator, I download the same poster I confirmed, without a surprise change to the scene or wording.

Acceptance criteria:

- [ ] PNG download is available only for a confirmed version with an approved scene, loaded assets/fonts and passing layout checks. Pending/rejected scenes and unconfirmed visible changes are blocked on the server as well as in the UI.
- [ ] Preview and export use the same layout, font and asset definitions. Export dimensions match the chosen format exactly. No hidden image regeneration, creative upscale, model text rendering or layout change runs at download time.
- [ ] The stored export is linked to the confirmed version and content hash; repeated download returns the same bytes, even if the draft, product price or shop profile has changed since.
- [ ] If improved scene quality requires generation, it is an explicit new candidate with a new review and confirmation, not an invisible export step.
- [ ] Missing assets, font load failure, rendering/storage failure or interrupted download produces a French error and retry action. It never silently substitutes a different font, image, version or cropped output.
- [ ] Visual checks cover accented French, a long title, a large Ariary price, multiline contact, transparent logo, all eight identity combinations and each format on the agreed phone/desktop browsers.

Out of scope: JPEG, batch zip and print export for the first slice. Export renderer and browser/device test matrix must be settled in the design.
