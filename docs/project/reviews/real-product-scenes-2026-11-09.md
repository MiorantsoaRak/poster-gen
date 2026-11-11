**Real-product scene smoke test — 2026-11-09**

The user explicitly requested web-sourced JBL and Soundcore photos and real scene generation during the implementation review (ADR-026). Two initial requests ran through the existing project CLI, prompt builder, admission/budget checks and OpenAI adapter. No application code was changed and no creative rerolls were made. This tests the current implementation, not the proposed Claude planner or poster editor.

| Product | Reference | Generated scene | Usage-based cost | Recorded duration |
| --- | --- | --- | --- | --- |
| JBL Flip 7, blue | Official JBL image, 1605×1605 transparent PNG | Tropical terrace, stone table, lagoon at late-afternoon light | USD 0.172418 | 86.07 s |
| soundcore Motion 300, Mirage Black | Official Soundcore image, 1200×1200 JPEG, with an award graphic above the product | Wooden chalet terrace, forest and mountain background | USD 0.171802 | 82.00 s |

Both requests succeeded on their first provider call using `gpt-image-2`, quality `high`, output 1088×1920. Combined cost from returned token usage: **USD 0.344220**. Durations are provider-call ledger `started_at` to `finished_at`, which also include local preparation/waiting, not isolated provider-server latency. The two requests ran concurrently.

The existing `backend/data-probe/` ledger and `probe-high` run were reused so the configured USD 12 cap retained the previous probe's USD 0.168661. The ledger now contains three successful calls, total **USD 0.512881**. This is calculated usage cost, not a new dashboard billing reconciliation. The original synthetic phone candidate and assets remain unchanged.

**Source provenance**

- [JBL Flip 7 official product page](https://www.jbl.com/FLIP-7.html). [Downloaded product image](https://www.jbl.com/dw/image/v2/BFND_PRD/on/demandware.static/-/Sites-masterCatalog_Harman/default/dwad0b22ea/JBL_FLIP_7_HERO_BLUE_079_x1.png?sh=1605&sw=1605). SHA-256: `e624b0f6aa13c2980ea9f621309e950a940c7bd2028db1f08c6f5c396ecc3ab1`.
- [Soundcore Motion 300 official product page](https://www.soundcore.com/products/motion-300-speaker-a3135011). [Downloaded product image](https://cdn.shopify.com/s/files/1/0516/3761/6830/files/soundcore-motion-300-mirage-frost-blue-portable-bluetooth-speaker_3840x.jpg?v=1748311380). SHA-256: `34a70ac537fd49a43346665dead17e66f33aaa63c156f711005403f5aa82604a`.

The Soundcore CDN filename and image alt describe blue, but the actual image is the black speaker, consistent with the page's Mirage Black selection. It was inspected and labelled Mirage Black before generation. The original award graphic was not manually removed. No shop price, offer, contact information or specifications were inferred from the pictures.

**Visual assessment**

- **JBL scene:** a plausible scene asset for a poster. The visible blue cylindrical silhouette, grille and JBL mark remain recognisable and close to the reference. The light and table shadow integrate the product into the terrace. Colour is affected by the new lighting. One front view cannot verify hidden controls, rear ports or every physical detail.
- **Soundcore scene:** a plausible scene asset for a poster. The rounded rectangular case, diagonal grille, central symbol, blue speckles, strap and top controls remain visibly recognisable. The external award graphic is absent, as wanted. Fine textures and lettering are generated rather than guaranteed pixel-identical.
- **Framing:** both products appear whole within the central square guide used by the implementation. Soundcore sits near its bottom boundary, leaving little room for a footer inside that crop. This is a visual inspection, not an automated product-bounds measurement or a finished three-format poster check.
- **Composition:** both images leave substantial space above the product. This helps a headline, but the backgrounds vary in brightness and texture; typography still needs contrast and placement checks. Neither image contains an offer, shop identity or editable objects.
- **Cutout fallback:** JBL's extracted product looks usable on inspection. Soundcore's cutout retains the separate Red Dot award symbol and text above the speaker. Its alpha bounding box is `(57, 41, 1164, 964)`, extending into that award area. A check confirmed nontransparent pixels in the top 300 source rows, where the award sits and the speaker does not. The cutout is `proposed`, not approved; the human gate can reject it before any background spend.

The Soundcore cutout is an observed quality failure. `_check_components` in `backend/src/affiche/visuals/cutout.py:122` only refuses a second component when it reaches 30% of the largest; smaller disconnected graphics can survive. Do not assume a successful mask contains only the sale item. A clean input or user-selected product region, plus the existing cutout review, is needed for marketing graphics/screenshots. Blindly retaining only the largest component could also remove legitimate thin or disconnected product parts, so that change requires separate tests.

These results support retaining the existing scene-generation mode. They do not establish that the cutout treatment should be the default. Compare both treatments on representative shop photos, including poor lighting, before selecting a default.

**Saved outputs**

All deliverables are in the git-ignored `outputs/review-2026-11-09/` folder:

- `jbl-flip-7-scene.png`, `soundcore-motion-300-scene.png`: unmodified provider outputs, ready to open or download.
- `jbl-flip-7-cutout.png`, `soundcore-motion-300-cutout.png`: local rembg outputs for inspection; the Soundcore one should not be used as a clean product layer.
- `inputs/`: downloaded originals. The initial mislabelled Soundcore download is also retained; `sources.json` identifies the correctly named file used by the fixture.
- `sources.json`, `products.csv`, `results.json`: source URLs/hashes, exact fixture values, candidate IDs, usage and timestamps.
- `jbl-flip-7-scene-prompt.txt`, `soundcore-motion-300-scene-prompt.txt`: exact prompts produced by the existing builder, not Claude.
- `sheet/sheet.html`, `sheet/decisions.csv`: the existing review-sheet output with source/result pairs and crop guides. It includes the previous synthetic phone as well as these two products.

Candidate IDs are `3de4aee2-e6e8-440b-83be-b85df2e7b37f` (JBL) and `eb51d6e0-9f25-4d4d-a1cb-0236a560c1f6` (Soundcore). Both remain `pending_review`; their cutouts remain `proposed`. No approval decisions were applied on the user's behalf.

**Reproduction and checks**

Executed from `backend/` in PowerShell:

```powershell
$env:IMAGE_PROVIDER = 'openai'
$env:DATA_DIR = 'data-probe'
uv run python -m affiche.visuals.evaluate generate --paid --fixtures ../outputs/review-2026-11-09/products.csv --photos ../outputs/review-2026-11-09/inputs --run probe-high --only WEB-JBL-FLIP7-BLUE,WEB-SOUNDCORE-MOTION300-BLACK
uv run python -m affiche.visuals.evaluate sheet --out ../outputs/review-2026-11-09/sheet --run probe-high
```

Both commands returned 0. Fixture validation ran before spend. Assertions verified two successful new provider calls without retries, returned usage-based costs, the expected dimensions, original hashes unchanged, and copied output hashes matching the asset store. Both local cutouts were also generated by the real rembg model. The existing test suite had already passed: 432 passed, 3 opt-in rembg tests deselected.

The existing generated files should be opened directly; another paid run is unnecessary. Do not rerun `sheet` into the existing directory because it deliberately refuses to overwrite decisions.

Verdict: the current backend can generate credible real-product **scene assets**. It still cannot produce, polish, confirm and download a complete branded poster within an application. These clean manufacturer images are a two-product smoke test, not evidence for poor shop photos or a measured acceptance rate.

Not checked: Claude planning, scene refinement, completed posters with title/price/shop details, phone editing/export, or dashboard reconciliation. The Soundcore cutout demonstrates that human review remains necessary.
