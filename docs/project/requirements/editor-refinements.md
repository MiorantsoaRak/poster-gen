# Editor refinements after the deployed audit

Status: approved scope under the user's 2026-11-14 instruction “go for the fix autonomously”; independent review before design. Source: reviews/ux-audit-2026-11-14.md. Price remains inside the generated composition; corner placement is for the original boutique logo.

Requirements gate: APPROVE WITH FIXES, all six findings incorporated below; approved autonomously 2026-11-14. No paid/release authorization inferred.

## R-EDITOR-REFINEMENTS-001 — Reachable mobile controls

- At 320/360/390 px, a compact preview can be shown/hidden without changing the document. Existing full-screen inspection stays accessible.
- Textes/Boutique/Style/Réglages remain reachable while scrolling; preview and fixed action must not cover the focused control. Preserve typing collapse, reduced motion and keyboard use.
- The first/last version and their selection/focus outlines are not clipped. Versions have consistent visible numbers and unique accessible action names.

## R-EDITOR-REFINEMENTS-002 — Truthful composition preparation

- If the complete brand already occurs in the title (whole words, case/accent insensitive), draw it only in the unchanged title, not a second brand heading. No substring deletions, no mutation of product facts or offer. Explain the outcome before generation. Existing scenes remain readable/refinable.
- “Aux couleurs du produit” proposes colours from the first product photo, independently of remembered accents. Show the proposed swatches and allow explicit override. A black product on white/transparent background yields a neutral palette. Sampling is a proposal, not semantic segmentation; ambiguous photos may need correction. Sampling failure is visible and does not silently use an unrelated accent or enable a paid call with an unknown palette.
- Title/brand/subtitle limits and errors have field associations. Copy distinguishes current image from next-generation settings and keeps the exact integer price drawn.

## R-EDITOR-REFINEMENTS-003 — Optional boutique identity and original logo corners

- New posters start with logo/name/contact off, including after profile load, typing contact or uploading a logo. Stored shop details and existing posters retain their values; explicit inclusion remains possible.
- Add missing shop details to the current draft through an explicit action using the existing profile/document save flow. Never silently refresh approved historical versions or confirmed exports.
- For an included original boutique logo offer top-left/top-right; reserve its area before composing the title, in feed/square/story safe regions. Use the uploaded file, never an AI recreation. Position survives save/reload and generation/review. Existing lower/footer and round-seal documents remain supported; switching from seal must explicitly explain that it changes the next composition.
- A change affecting occupied space may require a new scene; say so and block export/refinement if the current scene no longer matches the chosen logo region. Confirmed files remain unchanged.

## R-EDITOR-REFINEMENTS-004 — Trust and verification

- Clearly identify the existing conservative budget reservation; do not present it as the actual charge or a guaranteed provider maximum. No unsupported numeric cost claims.
- Unit/domain tests cover deduplication, palette selection and logo positioning/compatibility. Run existing backend/frontend suites, build and meaningful browser regression scenarios including failure paths.
- Test the working UI in a real browser with isolated free data; inspect the deployed browser as authorized. No paid generation is authorized by this fix request. Deployment follows the repository's user-controlled release workflow; no unapproved shared-server change.

## Review resolutions / regression acceptance

- Legacy footer and seal layouts retain existing eligibility. After a seal version exists, moving to a corner uses an explicit copy/new scene; the existing uncovered-disc guard remains. No automatic conversion on reopen.
- Corner changes or adding a corner logo without a matching reserved region block refinement/export before charging. Same-region logo-file replacement preserves the region and requires final composite review. Missing-profile import fills null fields only, preserves inclusion choices and existing values, and retains the draft on error/conflict. Existing title/price/contact stale rules and origin-revision result-adoption guards remain.
- Check the actual composite (original logo with aspect ratio/transparency) for collisions with title/product/price/contact in final review. A reserved rectangle is a prompt instruction, not proof that the model obeyed. An occupied region is corrected by explicit new generation/review, never automatic retries.
- Palette shown and sent must match, independently of remembered accent and saved-style palettes. Overrides persist on reload for this poster; late results from another product are discarded. Failure offers retry/manual colour/another style. All preparation actions are free; only explicit confirmed generation/planning may incur spend.
- Correct introduction/library edit promises, provide contextual terminology hints and visible drawn-text limits. Browser tests include pointer reachability, keyboard, both themes, constrained height and expanded/collapsed toggle state.
