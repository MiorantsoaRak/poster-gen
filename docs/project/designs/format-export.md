# DESIGN — format-export

**Status:** Approved v1, 2026-11-09. **Approval:** ADR-031. **Requirements:** [format-export](../requirements/format-export.md), approved ADR-028; prompted text effects approved ADR-030 are included in the rendered document.

## System overview

Saved revision → deterministic per-format document → server Chromium using the same PosterCanvas component → stored PNG → user sees that PNG → atomic confirmation → download those same bytes. No provider call occurs during rendering, confirmation or download. The interactive canvas is the editing view; the server PNG is the authoritative final preview.

## D-FORMAT-EXPORT-001 — Format layouts and framing

**Covers:** R-FORMAT-EXPORT-001; R-POSTER-EDITOR-001/002.

Format is an enum with fixed dimensions: feed 1080×1350, square 1080×1080, story 1080×1920. Start implementation with feed end-to-end; later enable square/story through the same schema and tests. Primary format informs initial image dimensions and planning. Other formats are created locally by reusing the selected approved scene, proportional initial overlay positions and an explicit editable crop, then remeasuring text. No automatic additional scene request.

Document formats map holds independent scene selection/crop/layer styles. Shared title/price/brand values resolve into each format's role-bound text. Editing style changes one format; changing a shared price changes every format where price is shown. Switching the UI tab is not a document mutation. Confirmed historical renders always remain accessible.

Compute format_hash from the effective selected-format spec: exact source input/visual and crop, ordered visible layer geometry/style/effects, resolved content/price formatting, logo/texture/font content hashes and inclusion choices. Exclude unrelated formats, UI selection state and timestamps. Store it beside each render. An unchanged format may still match an earlier confirmation despite a document revision in another format. Any affected visible value changes its hash and needs a new preview/confirmation.

Validation: positive uniform crop transform within image bounds, required title/price present, fonts/assets available, no required glyph/effect content clipped outside the canvas or its text box. Measure actual text wrapping/bounds in the shared renderer; do not trust browser-supplied fit assertions. Overlap/product-safe-area warnings are shown and require acknowledgement, while missing/clipped required content is blocking. Actual product framing remains an explicit human check; a planned product rectangle is not a reliable detector of generated boundaries.

If the product cannot fit the chosen crop, offer an explicit new scene/refinement for that format. It consumes budget/allowance and requires its own fidelity review. No stretch, content-aware fill or generative upscale at export time. Standard deterministic resampling to the output canvas is allowed and visible in the final preview.

**Data/API:** format maps are saved through creation-library's revisioned document API. No separate hidden layout state. The render submission/confirmation interfaces below take an explicit format. Unknown/not-yet-enabled format → 422 format_unavailable; invalid geometry → 422 layout_invalid. Creating another format returns an unconfirmed draft and preserves the original format's layout.

## D-FORMAT-EXPORT-002 — Render once, inspect, confirm, download

**Covers:** R-FORMAT-EXPORT-002; R-POSTER-EDITOR-002/003; R-CREATION-LIBRARY-001.

**Data model:**

| Table | Fields / constraints |
|---|---|
| poster_renders | UUID id, creation_id, source_revision, format, format_hash, renderer_build_hash, font_manifest_hash, asset_manifest_json, png_sha256, width/height/bytes, warnings_json, created_at. Only successful verified renders have a row. UNIQUE(creation_id,source_revision,format,renderer_build_hash,format_hash). |
| confirmations | UUID id, creation_id, source_revision, confirmed_revision, format, format_hash, render_id FK UNIQUE per creation, png_sha256, checklist_json, confirmed_at. Immutable. |

PNG files reuse assets.put/path content-addressed storage, but poster_renders owns their metadata. Do not label final posters as scene assets or rebuild the legacy assets.kind CHECK solely for exports. Download loads/verifies the render's file via its recorded hash/path. Original/logo/style/generated scene assets retain existing kinds; authorisation and usage roles come from their owning domain references.

**API:** all routes use catalogue-brand access/error conventions.

| Endpoint | Contract |
|---|---|
| POST /api/creations/{id}/renders | If-Match + Idempotency-Key; {format}; 202 render job or existing identical job/result. Snapshot exact revision and manifests. |
| GET /api/renders/{id} | 200 metadata/status-preview URL/hash/warnings; authorisation checked. |
| GET /api/renders/{id}/preview | Authenticated PNG bytes of successful render; used in final confirmation screen. |
| POST /api/creations/{id}/confirmations | If-Match + Idempotency-Key; {render_id,png_sha256,checks:{framing,content,identity,readability},acknowledged_warning_ids}; 201 {confirmation_id,download_url}. |
| GET /api/confirmations/{id}/download | Authenticated stored PNG; Content-Disposition attachment with safe filename; ETag is PNG hash. No rendering/provider work. |

**Rendering:** generation-jobs queues model-free render work. Resolve authorised local assets and registered fonts, validate/decode them, and prepare bounded sRGB render copies without altering originals. Both browser canvas and server render receive the same defined image-preparation recipe; the authoritative PNG catches browser-specific rasterisation differences. Maximum one render at once, 30-second timeout, fixed allowed canvas sizes, no oversized pixelRatio.

Use Playwright Python + a pinned Chromium build. Load a trusted compiled render shell containing the same Vue PosterCanvas component as the editor in a fresh browser context. Inject validated document/asset/font bytes as structured data, never concatenated HTML/JS. The worker may use page.set_content/page.evaluate with its own bundled code; block all network requests, extensions and arbitrary file paths. No internal unauthenticated HTTP asset route or provider credentials inside Chromium.

Await all decoded images and document.fonts readiness; fail if any manifest font fails to load. Freeze animations and selection controls, render at exact logical width/height with scale=1 and pixelRatio=1, then export PNG from the stage. Validate PNG signature, decode/dimensions and SHA-256. Store bytes first, then atomically insert poster_renders and mark the job succeeded. On DB failure, retain local spool and retry finalisation; no need to rerun image generation. Normalised content, renderer build and font manifest are recorded for reproducibility; the stored PNG itself is the download authority.

**Confirmation transaction:** authenticate → mutation-key replay → compare current revision → resolve current effective format_hash → verify render belongs to creation and same format_hash/input/approved visual → verify PNG/hash/assets exist and checks/warning acknowledgements match → insert immutable confirmation and idempotent response → commit. The render may be from an older document revision only if the selected format's effective hash is identical; record both source and current confirmation revision for audit. No silent switch to the newest candidate/render. Missing If-Match → 428; stale content/render → 409 preview_stale; unapproved visual → 409 scene_unapproved; failed checklist/layout → 422 confirmation_incomplete.

At download, verify saved file bytes against png_sha256 before returning them. A corrupt or missing file → 503 export_missing; restore the exact saved bytes from backup, do not reconstruct or regenerate under the same confirmation ID. Repeat downloads have the same SHA-256 even after edits, profile updates or software upgrades. New renderer/quality output is a new preview and confirmation, never a replacement of old confirmed bytes.

**State:** saved draft → render queued/running → immutable ready render → immutable confirmation. Editing does not delete historical ready renders/confirmations; a different current format_hash is simply unconfirmed. Queued render cancellation is allowed; running render failure is locally retryable because its inputs are immutable and it has no provider cost.

| Failure / edge | Detection | Handling |
|---|---|---|
| Pending/rejected scene | Server preflight and confirmation check | Block final render/confirmation; ordinary draft editing remains available. |
| Font unavailable, unsupported glyph, image decode failure | Asset/font preflight + canvas readiness | Visible error; no substitute font/image and no successful PNG record. |
| Browser crash/timeout/memory bound | Worker timeout/process error | Render failed; close context; retry once locally, then explicit retry. Draft/old exports intact. |
| User edits during render | Current format_hash differs | Keep old preview for history; show stale status; no confirmation of changed draft using it. |
| Duplicate confirm or lost response | Mutation key + unique render binding | Return original confirmation; no extra render. |
| Disk/DB outage | Verified file write/transaction | No false confirmed state; retain draft and spool when possible. |
| Two formats, price changed globally | Per-format effective hashes | Every affected current format becomes unconfirmed; historical PNGs stay unchanged. |
| Content/image change requested for better quality | Explicit new job | New candidate review and preview/confirmation; no download-time charge. |

## Evidence and verification

[Konva export](https://konvajs.org/docs/data_and_serialization/High-Quality-Export.html) documents pixelRatio/output dimensions; [Playwright Python](https://playwright.dev/python/docs/library) documents Chromium automation. These support the proposed rendering path, not proof of identical fonts on every device. The authoritative server-preview bytes resolve that final-confirmation ambiguity.

Required checks: exact PNG dimensions/hash repeatability; downloaded bytes equal displayed preview bytes; no provider/planner calls on render/confirm/download; changed revision and changed price/profile; partial-write recovery; missing fonts/assets; both approved and refused confirmations; all eight identity combinations; French accents, long title/contact and large price; shadow/texture clipping; current-format versus historical-format confirmations. Compare interactive and final previews on desktop Chrome/Edge, Android Chrome and iOS Safari, current and previous major versions at implementation. Physical phone tests and a renderer prototype are required before claiming this design delivered; no frontend/browser tests ran in this design session.
