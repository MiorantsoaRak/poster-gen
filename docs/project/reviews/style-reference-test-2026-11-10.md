# Recent shop-poster style test — 2026-11-10

Complete: a real black Soundcore R50i was integrated into a scene guided by the user's DJI Mic Mini reference, polished with editable reference-style typography, confirmed and downloaded through the application.

## Delivered poster

- File: `outputs/style-reference-2026-11-10/soundcore-r50i-reference-typography-final.png`, **1080 × 1350**.
- SHA-256: `e574e884916eb29f908d22d51f3d95fad531a98225da05a834a3da0f4870b5f9`.
- Creation `3d52918c-ca30-462b-9560-4586e9e17b3d`, revision **6**; approved visual `5137231c-d8d4-4129-b080-71cd76b7cfd2`.
- Render `fc513460-a199-4ace-8f7b-f04022532838`; confirmation `8730b2a2-9380-4753-9f63-ef0b40c2ee68`.
- Download equals the visually inspected server preview byte for byte. Pixel comparison with revision 5 proves every pixel outside the title/price boxes is unchanged. Scene, commercial values and shop layers are unchanged.
- Evidence and exact mutation keys/bodies: `style-poster-run.json`, `run_style_poster.py`, `typography-proof.json` in the same output directory. Existing confirmations and prior PNGs remain intact.

## Reference and product provenance

The user's Edge accessibility tree identified [Original Phone Mada's DJI Mic Mini poster](https://www.facebook.com/photo/?fbid=1451519837118449&set=a.503414078595701), displayed November 5 at 16:54. Desktop capture/input failed with missing coordinate geometry/window capture timeouts. Public mirror image links returned 404 and Facebook fetch was throttled. These failures supplied no evidence of the visual style. The user subsequently supplied the actual image; no further browser access was needed.

- Preserved attachment: `reference-dji-mic-mini.png`, 1254 × 1254, SHA-256 `667d42c6dce9d94cfddb1298fd7c18bf8fa3be78cbc4dbe4936c67d5ce1e63bd`.
- Exact product original: `outputs/review-2026-11-10/soundcore-r50i-black-original.jpg`, Anker Philippines R50i (not R50i NC), SHA-256 `80f4f22af084b688e4612f9a295315bffa2fbdf9ec7015681a0325f9e4c11198`. Source links and shop/contact evidence: [shop source review](shop-poster-sources-2026-11-10.md).
- Shop name: Original Phone Mada; contact: 038 93 028 00 / 034 93 028 00. No verified shop logo was available; name/contact were selected independently.
- **90,000 Ar is a dated August 13 offer used as test data. Current price and stock remain unverified.** The reference's DJI logo, microphone copy and 600,000 Ar were not copied.

## Visual evaluation and polish

The inspected reference has a white/grey curved backdrop, large floating dark product/components, soft oval shadow, centred heavy italic heading and black amount in a thin blue capsule with smaller upright AR.

The initial GPT Image result transferred lighting/background well but made the product too tall: the heading overlapped an earbud. `soundcore-r50i-before-framing.png` records this failure. Geometry warnings cannot detect semantic product pixels, so the operator framing check remains necessary.

A first refinement instruction containing four-digit image dimensions was refused by commercial-number screening **before a provider call**. Rephrasing with three-digit bounds passed validation. The accepted refinement uses base + original + style images, keeps the black earbuds/case/lanyard, and clears the title region. Original-photo fidelity was visually reviewed before approval.

Manual composition moved/enlarged the shop footer and kept the scene unchanged. Revision 5 produced `soundcore-r50i-reference-style-final.png`, hash `2c61abbf28e52a5af380b11b7291bb9d7e49d766a2fe8b08ab747ea3045fffee`.

The user then requested the font and price format too. Revision 6 adds genuine **Montserrat Black Italic 900** to title and digits, with an editable white capsule, cyan-to-blue border and smaller upright Noto Sans AR. Montserrat is a close visual match, not a verified identification of the reference's font. The [upstream font](https://github.com/JulietaUla/Montserrat/blob/master/fonts/ttf/Montserrat-BlackItalic.ttf) and its [OFL licence](https://raw.githubusercontent.com/JulietaUla/Montserrat/master/OFL.txt) are bundled unchanged. Font SHA-256: `ba072e896619782f65f2d4329b7de7326d253a905654981b8cb1a2f9a9ecd31b`.

Its font lacks narrow NBSP; price grouping uses its supported NBSP while retaining the exact integer amount. The result adapts the typography, palette and composition; it does not copy the DJI-specific subtitle or use mixed colours inside the single title.

## Implementation changes

- ADR-039: owned optional style reference through scene/refinement admission, dispatch, immutable provenance and French editor upload/recovery. Reference roles and hashes checked before spend; no new migration/dependency.
- ADR-041: licensed font choice and optional price-owned capsule in the strict document and Claude style-patch schemas. Manual controls, undo, autosave/reopen, prompt proposals, material fill and authoritative renderer use the same selected layer.
- Null badge omitted from canonical data so legacy request/style/effective hashes remain unchanged. Invalid font/weight pairs, wrong badge roles and invalid colours fail validation. Used-font export fingerprints include the separate AR font.
- Exact amount remains authoritative. Text/material edits cannot alter the scene or another layer. Oversized prices/boxes, missing glyphs and measured italic ink outside the canvas block final rendering. Historical confirmed PNG bytes remain unchanged.
- Browser testing found inaccurate accessible labels and damaged French accents in newly added controls; corrected both before the final smoke pass.

## Verification and spend

- Full backend suite: **671 passed, 3 deselected**, 185.95 s. After the final italic ink-bounds fix, shared-renderer tests **5 passed** and the complete Chromium smoke passed again.
- Focused typography/rendering checks before that final bounds addition: **34 passed**. Frontend: **26 passed**; final production build passed.
- Chromium smoke covers new font/capsule controls, exact grouped amount and small upright AR, selected-layer-only save, undo/redo, reopen, mobile-width overflow, patterned price glyphs, final preview/confirmation/download equality and stale-preview refusal. Existing reference upload, lost-response replay, conflict copy and text-effect checks also pass. Expected 409s are intentional conflict/stale tests.
- Actual shared renderer checks zero/large amounts, capsule overflow, italic edge clipping, pixel isolation and repeated PNG output. Export tests cover legacy format hashes and currency-font fingerprint changes.
- Real final preview has **no layout warnings**; final download equals it. The latest rebuilt renderer produces the same inspected PNG hash. Historical revision-5 download still equals its original file.
- Two paid GPT Image 2 high calls for this style evaluation: initial **$0.216440**, framing refinement **$0.228831**, total **$0.445271**. Combined ledger went from **$0.716693** to **$1.161964**, under the existing **$12** cap.
- Typography, local renders, approval, confirmation and downloads added **zero image calls/cost**. No paid ledger reset or extra paid data directory.
- Installed `postman status` remains unsupported; verification used local FastAPI/HTTP/Chromium without creating a cloud workspace.

## Limits and next work

The delivered feed PNG is usable as a reviewed visual test. Confirm current price/stock before publishing. Scene fidelity is a visual review, not an automatic guarantee. Real Claude scene planning and text-polish quality were not exercised; their constrained transport/application paths use controlled tests. No physical phone/Safari test, deployment or Facebook publication occurred. The initial/final scenes and previous dark poster remain preserved.

The next broader approved task is T-POSTER-009 (square/story layouts and library/history/reuse), followed by T-POSTER-010/011 and T-PV-011. Outputs and paid data are Git-ignored; protect their files and database together.
