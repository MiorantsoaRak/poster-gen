# Real Soundcore feed-poster test — 2026-11-10

The requested feed workflow now produces a usable **1080 × 1350 PNG** from a real product reference, title, price and selected shop details. The result was inspected, polished, confirmed and downloaded through the application. This is a tested pilot flow; it is not evidence that all products or generated layouts are automatically correct.

## Result and provenance

- Final file: `outputs/review-2026-11-10/soundcore-r50i-original-phone-mada-final.png`.
- SHA-256: `b1aca99e80656940fcaa378abd416c839bbae4f1ed29a82f618aa195484aae27`.
- The final download bytes exactly equal `soundcore-r50i-poster-preview.png`, the PNG visually inspected before confirmation. The server stores that file immutably; later changes cannot replace it.
- Creation `d4f21a6d-e0a2-43c0-8250-91a91a1c768e`, final revision 3; visual `7106c7b4-3639-45d0-997e-eca5afb93640`; render `94aa65a3-58a1-4dd0-8599-398e57b3d77d`; confirmation `59b295f3-026f-4c15-a047-127f4e8e73f2`.
- Product: black Soundcore R50i, original [Anker Philippines reference](https://www.anker.com.ph/products/soundcore-r50i). Original bytes and ordered input hash retained; no rembg/cutout used.
- Shop: **Original Phone Mada**, **038 93 028 00 / 034 93 028 00**. The user's Edge session exposed the matching Facebook shortcut; live page capture failed. Public shop mirrors corroborated the contact details. See [source notes](shop-poster-sources-2026-11-10.md) for exact links and limitations.
- **90,000 Ar is a dated August 13 offer used as test data. Current price/stock were not verified.** No warranty, discount or performance claim was invented. No verified shop logo was available; the real test selected name/contact only. Independent logo/name/contact choices are implemented and covered by tests.

## What the real image test showed

GPT Image 2, high quality, generated an integrated 1088×1360 scene from the original JPEG. The dark studio/stone surface and turquoise light integrate the product naturally. Visual comparison found the two earbuds, open case, lanyard, colour, visible markings, charging details and overall proportions retained well enough for this test. Fidelity approval is an operator judgement, not a pixel-level proof that generative reconstruction preserves every manufacturing detail.

The first automatic composition placed the price over the lanyard/case. The image model did not fully respect the planned empty regions. This is why the final poster preview and editable overlays are required: a valid plan alone does not establish a usable ad.

Manual polish moved the price into the clear upper area, increased title/footer sizes, used a cyan price colour and improved contact contrast. The selected scene and commercial facts remained unchanged. The final checklist explicitly asks whether the product is clear of text. No extra image generation was needed.

Correction during the style-reference follow-up: the persisted visual and actual scene request used `high`, even though the local test runner set a `medium` configuration value. Poster admission explicitly requests high quality. The output and recorded cost below are unchanged.

## Cost and preservation

- Exactly **one new image call**, usage-based cost **$0.203812**.
- Existing combined ledger: $0.512881 before, **$0.716693 after**, against the existing $12 cap. No new paid data directory or reset ledger.
- Approval, manual polish, two local previews, confirmation and download added no provider calls or cost.
- Paid database backed up to `backend/data-probe/backups/before-poster-2026-11-10.db` before normal forward migrations through 0009. The same original/scene assets remain in the content-addressed store.
- Local runner/state: `outputs/review-2026-11-10/run_real_poster.py` and `real-poster-run.json`. Mutations persist exact request keys/bodies/revisions before submission. Replays return existing operations; do not delete this state to rerun a paid request.

## Verification and limits

- **655 backend tests passed, 3 opt-in rembg tests deselected**; **26 frontend tests passed**; production build passed.
- Actual Chromium smoke covers photo intake, independent identity controls, a deliberately lost generation response (one job only), scene review, manual edits/undo, keyboard movement, autosave/reopen, conflict copy, text overflow/glyph errors, prompted proposal/effect review/undo and final preview/download byte equality. A changed price blocks confirming the old preview; previous confirmed bytes still download unchanged.
- Pixel tests verify native material fills remain inside exact font glyphs and changes remain inside the changed text region. Backend proposals constrain targets and require explicit quoted titles/literal Ariary values plus content acknowledgement. Other layers and the scene are preserved.
- Real Claude and real material generation were **not** exercised; their transport/schema/queue paths were tested with controlled responses and stubs. The real scene used the available fixed planner and GPT Image integration. Missing Claude configuration is explicit in the UI.
- Physical phones, Safari, deployment, publication and backup restoration were not tested. Desktop Chromium and phone-sized Chromium layouts were tested. Square/story/library enhancements and optional cutout are still queued; this test proves the requested feed output.
- Generated images still need fidelity and composition review. The shop must verify the current price and availability before posting this test poster.
