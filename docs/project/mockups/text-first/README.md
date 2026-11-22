# Text-first creation — interactive concept

**Polish update (2026-11-14):** after the first result, the conversation remains available for follow-up requests. Try a suggested adjustment, prepare it, cancel to recover the message, or confirm a simulated revision. The previous example remains visible while working; you can draft the next message. Conversation and version number persist, and each new version resets review. On phones the composer follows the poster. Account credits are deferred; current cost confirmation, metering and budget safeguards remain the production expectation. The simulation uses no credits or paid calls and does not interpret/perform actual image edits.

Verified follow-up: real browser confirms cancellation restores input, generation requires confirmation, duplicate confirmation produces one revision, next unsent message survives completion, history stays visible, review is required again, and 320 px layout fits with the composer after the preview. Screenshot: ignored outputs/text-first-mockup/polish-desktop.png.

Requested by the user on 2026-11-14 to explore the flow before implementation. This isolated static mockup does not approve the Draft requirements or change the deployed app.

From the repository root:

```bash
python3 -m http.server 8776 --bind 127.0.0.1 --directory docs/project/mockups/text-first
```

Open <http://127.0.0.1:8776>. The directory is self-contained and can also be opened locally as `index.html`.

Try the Sony example, change a style, continue without a photo, check the product/price, then create and review the simulated result. The bottom demonstration shortcuts jump to photo/no-photo/result scenarios. Attach your own JPG/PNG/WebP to inspect attachment previews and product/inspiration roles. The moon button changes the theme.

Reference roles and the compact confirmation are proposals for discussion, not finalized UX. The mock parser only demonstrates product-before-price text ending with an Ariary amount; it is not the future natural-language extractor. Style selection uses the cards, not text parsing. The result is always the same existing Sony WH-1000XM6 scene regardless of the message, photos or selected style. A sample price is overlaid for layout only; the real feature retains the price inside the generated image. No download or real editor is connected. The simplified review is not a replacement for the production fidelity checklist.

Assets reuse the project's Figtree font (licence in `assets/`), built-in style thumbnails, and existing `outputs/style-study-2026-11-11/` Sony product/scene images. No new AI image was generated. Sony WH-1000XM6 is used because that matched pair already exists locally; the supplied ULT example remains the research reference.

Verified in Orca's real embedded browser: compose → confirmation → timed simulated generation → result; attachment shortcut and reference priority; required review checks; missing/invalid price and ambiguous-colour paths; light/dark appearance; no horizontal page overflow at 320 px (including attached-photo, confirmation and result states), 390 px and desktop. The 320 px attachment overflow found during inspection was fixed. One text-wait timed out because the heading includes a line break; the result state was subsequently verified directly. The browser's full-page mobile capture stitched incorrectly during an entrance animation; it is not delivery evidence. Stable viewport captures are in ignored `outputs/text-first-mockup/`.

Limits: no real search, generation, model calls or new API; no physical-phone keyboard, screen-reader speech or OS file-picker validation. Reduced-motion styles exist but were not emulated in this browser check. No production regression suite was run for this isolated concept.

Related: [Draft requirements](../../requirements/text-first-generation.md), [research](../../reviews/text-first-generation-research-2026-11-14.md).
