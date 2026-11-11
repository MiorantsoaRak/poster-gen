# REQUIREMENTS — creation-library

**Status:** Approved by the user on 2026-11-09 ("go aheadt with the requirement"; ADR-028). Technical designs remain subject to their separate approval gate.

| ID | Title | Priority | Status |
|---|---|---|---|
| R-CREATION-LIBRARY-001 | Save drafts and preserve versions | P0 | Approved |
| R-CREATION-LIBRARY-002 | Reuse an approved creation | P0 | Approved |

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
