# REQUIREMENTS — creation-library

**Status:** Approved by the user on 2026-11-09 ("go aheadt with the requirement"; ADR-028). Technical designs remain subject to their separate approval gate.

| ID | Title | Priority | Status |
|---|---|---|---|
| R-CREATION-LIBRARY-001 | Save drafts and preserve versions | P0 | Approved |
| R-CREATION-LIBRARY-002 | Reuse an approved creation | P0 | Approved |
| R-CREATION-LIBRARY-003 | Manage posters from "Mes affiches" | P1 | Approved 2026-11-12 (ADR-060) |
| R-CREATION-LIBRARY-004 | Manage saved styles | P2 | Approved 2026-11-12 (ADR-060) |

## R-CREATION-LIBRARY-001 — Save drafts and preserve versions

As the operator, I can leave and reopen my work without losing my edits or the last good scene.

Acceptance criteria:

- [ ] Save the original input version, exact commercial fields, selected shop snapshot, editable layers, per-format layout, selected scene, plan/prompt provenance and generation/refinement history.
- [ ] Show saving/saved/failed state. Refresh or reopening restores the last successfully saved version. Failed saves preserve the current edits and expose retry; the UI does not claim unsaved work is safe.
- [ ] Conflicting edits from two tabs/devices are detected before overwriting newer saved work; the operator can reload or save a separate copy.
- [ ] Pending/rejected alternatives, approved bases and confirmed posters remain distinguishable. Refinement failure or rejection never destroys the last good version.
- [ ] A confirmed version and its exported bytes are immutable. Assets referenced by saved/confirmed versions cannot be removed by normal cleanup.
- [ ] The library shows enough product, variant, preview and date information to reopen the intended creation without mixing look-alike variants. Server access checks apply to both records and assets.

Out of scope: multi-shop sharing, collaborative live editing and offline operation. Storage, backup, retention and access policy require design before hosting.

## R-CREATION-LIBRARY-002 — Reuse an approved creation

As the operator, I can publish a new price using an already approved visual without paying to regenerate it.

Acceptance criteria:

- [ ] Duplicate a creation for the same confirmed product/variant, reusing the approved scene and layout. Editing only the price/title/shop details makes no image request or planner call.
- [ ] A reused poster starts as an unconfirmed draft. It needs layout/content review and confirmation before download; the original confirmed version/export remains unchanged.
- [ ] A different product/variant or replaced product image does not inherit the old scene's fidelity approval. The user must create/review a suitable candidate.
- [ ] Catalogue or shop-profile changes are offered as explicit updates to a draft. They never silently alter existing saved snapshots or exported bytes.
- [ ] If an asset is unavailable, show an error and retain the record; do not silently regenerate, charge or substitute another variant's visual.

Out of scope: a cross-product background cache and automatic campaign generation.

## R-CREATION-LIBRARY-003 — Manage posters from "Mes affiches"

**Status:** Approved by the user on 2026-11-12 with the five working defaults ("approved, go"; ADR-060). Written after the UX audit (T-UI-UX-AUDIT). The technical design has its own approval gate.

Background, checked in the code on 2026-11-12: the server can already mark a poster as abandoned (`POST /api/creations/{id}/abandon`, refused while an image job runs) and copy one (`POST /api/creations/{id}/copies`, reasons `price_update` and `new_campaign`), but the editor offers neither. The list returns every poster, abandoned ones included, 50 at most per request, and the editor asks for one page only.

As the operator, I want to tidy my list of posters and start a new one from an old one, without opening each poster.

Acceptance criteria:

- [ ] Each row shows what the poster's state is, in words: "Brouillon" (no approved version), "À vérifier" (a version waits for the fidelity review), "Approuvée" (a version is approved, no confirmed file), "Confirmée" (a confirmed file exists for the poster as it is now; after a later edit the row goes back to "Approuvée" or "À vérifier" until it is confirmed again: user decision, ADR-061). The state is never shown by colour alone.
- [ ] A row offers "Dupliquer". The copy opens as an unconfirmed poster with the same product, texts, style and approved version, and costs nothing (R-CREATION-LIBRARY-002 stays in force: no image or planner call).
- [ ] A row offers "Retirer de la liste". The poster leaves the list after a confirmation that names it. Nothing is erased: its versions, its confirmed file and its download link keep working.
- [ ] Removed posters can be shown again with one control ("Afficher les affiches retirées") and restored from there.
- [ ] The list shows all posters of the shop, however many: more are loaded when the end of the list is reached or on a "Voir plus" button, and the count in the navigation is the real total.
- [ ] Error case: WHEN a generation is running for a poster THEN "Retirer de la liste" is refused with the reason, and nothing changes.
- [ ] Error case: WHEN removing, restoring or duplicating fails THEN the row stays as it was and an error with a retry is shown.
- [ ] Error case: WHEN the poster was changed in another tab since the list was loaded THEN the action is refused, the list is reloaded and the operator is told.

Out of scope: erasing a poster and its images for good (storage cleanup needs its own design, R-CREATION-LIBRARY-001 forbids removing assets of confirmed versions); renaming from the list (the title is edited in the poster); a search by title or product name (decided 2026-11-12: later); sorting choices; folders or tags; selecting several posters at once.

Decided on 2026-11-12 (the working defaults, ADR-060): "Retirer de la liste" exists for every poster, confirmed ones included; no search in this version; "Dupliquer" asks nothing and the copy is recorded as a new campaign.

## R-CREATION-LIBRARY-004 — Manage saved styles

**Status:** Approved by the user on 2026-11-12 with the five working defaults ("approved, go"; ADR-060). Written after the UX audit (T-UI-UX-AUDIT). The technical design has its own approval gate.

Background, checked in the code on 2026-11-12: a saved style (ADR-046) can be created and listed (`POST /api/creations/{id}/looks`, `GET /api/looks`); the server has no route to rename or remove one. A scene records the style it was made with, and reopening that poster selects the style again.

As the operator, I want to rename a style I created, remove one I no longer use, and see what a style is before I pick it.

Acceptance criteria:

- [ ] On the "Styles" page, a style created by the shop can be renamed. The name is 1 to 40 characters; two styles may not have the same name.
- [ ] A style created by the shop can be removed after a confirmation that names it. It then no longer appears among the styles to choose.
- [ ] Posters and versions made with a removed style keep working unchanged: they open, export and download as before. Reopening such a poster shows its texts and colours, and the style choice falls back to "Décrire moi-même" with the style's description kept.
- [ ] Opening a style on the "Styles" page shows its model poster in large and its description (ambiance, palette, alignment) in words. Nothing there costs money.
- [ ] From an opened style, "Créer une affiche avec ce style" goes to the new-poster screen with that style already chosen.
- [ ] The three styles supplied with the application cannot be renamed or removed, and the page says so.
- [ ] Error case: WHEN a rename is empty, too long or already used THEN it is refused beside the field and the old name stays.
- [ ] Error case: WHEN removing or renaming fails THEN the style stays as it was and an error with a retry is shown.

Out of scope: editing a style's description or palette by hand; sharing styles between shops; a style made from several model posters; restoring a removed style; creating a style from the "Styles" page without an open poster (decided 2026-11-12: today's path stays).

Decided on 2026-11-12 (the working defaults, ADR-060): a style is still created from an open poster; a removed style cannot be recovered, the confirmation says so, and its model poster stays stored because old versions refer to it.
