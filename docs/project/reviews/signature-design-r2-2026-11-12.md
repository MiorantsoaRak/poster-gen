# D-CATALOGUE-BRAND-004/005 — design review round 2, 2026-11-12

Fresh independent subagent, read-only, given draft v2 (rendered contact, ADR-053) and what changed since round 1. Line numbers are the reviewer's, at commit `85e8296`.

## Verdict: APPROVE WITH FIXES

P1:

- **"weight 600".** The document model allows 400, 700 or 900 (`models.py:147`) and the font manifest has Noto Sans at 400 and 700 only. Fix: 700.
- **"`align` positions the line" and the default position.** `stylePill()` forces `align: 'center'` on the shop-name and contact layers (`App.vue:106`) at every `createScene` (`App.vue:380`). Fix: stop setting `align` there.

P2:

- **`text_fit` does not exist for this case.** Only the price is non-wrapping (`canvas.ts:14`) and width-checked (`canvas.ts:75`). With no wrapping and a fixed width, Konva probably cuts the line (not run). Fix: extend both to `icon` layers; the measured width includes the handset and its gap.
- **Logo ticked after the first scene.** A late logo layer lands bottom right (`document.ts:60`) or keeps its old box; the contact keeps the full span, so a right-aligned contact sits under it with only a warning. Fix: place the logo at the footer left on tick, or accept it explicitly.

P3:

- The design did not say where the compact style is applied; the server creates the contact layer at 24 px (`store.py:172-176`).
- `rememberStyle()` runs only in `createScene` (`App.vue:385`); a later position change would not be remembered.
- The `brand_text` refusal must be raised in `compile_scene` to return `invalid_headline` (`visuals.py:218-219`).
- D-CATALOGUE-BRAND-002 still says "Default each available field on".

Claims: (a) an optional field declared like `price_badge` leaves stored documents and hashes unchanged: true; (b) `text_fit` is blocking and blocks the preview: true, but not yet raised for the contact; (c) the logo/text overlap warning exists and reaches the final screen: true, on layer boxes; (d) with no signature requested the footer areas are in the "calm backdrop" sentence and the first scene places a visible contact layer: true; (e) `align` alone positions the line in the span (about 817 px with the 128 px logo, 972 px without): true once the forced centring is removed; (f) the shop-name default is frontend only (`App.vue:19`, `App.vue:235`): true; (g) an old poster's hidden contact layer returns on a new version: through `chooseVisual` only, and with its old 24 px style.

Criteria not covered in v2: the 22 px minimum for an old poster's new version; the default position and "remembered on the device". R-CATALOGUE-BRAND-004 covered; R-CATALOGUE-BRAND-002 not broken.

## Outcome

Every finding is fixed in draft v2.1 of the design (weight 700; `stylePill` no longer sets `align`; non-wrapping and width check for `icon` layers; logo placement on tick; one named function for the compact style, applied in three places; the position choice saves itself; refusal in `compile_scene`; D-002 default noted). Not re-reviewed after these fixes. Submitted to the user for approval.
