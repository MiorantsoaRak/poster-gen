# HANDOFF

**Session date:** 2026-11-11 (Indian/Mauritius)
**State:** T-POSTER-SHOP-STYLE, T-POSTER-LOOK-PILL, T-POSTER-ONE-TAP (ADR-042), T-POSTER-SIGNATURE (ADR-043) T-POSTER-PRICE-IN-IMAGE (ADR-044), the 12-scene limit (ADR-045) and T-POSTER-REFERENCE-BRIEF (ADR-046) complete; five live tests in Microsoft Edge passed. **Migration 0010 is applied to backend/data-probe** (backup before it: data-probe/backups/before-looks-2026-11-11.db). T-POSTER-001–008, T-POSTER-STYLE-TEST and T-POSTER-REFERENCE-TYPE remain complete. No task is in progress; no test/server process is running. Nothing committed.

## Delivered result — latest user request

The user gave autonomy to change the process until posters match Original Phone Mada's own, tested on 5–10 products, and then asked for a style choice designed from the owner's point of view.

- Ten shop posters inspected; 13 study images on 9 real products; the application now produces the shop's style. Report: [style-study-2026-11-11.md](reviews/style-study-2026-11-11.md).
- Side by side (shop on top, ours below): outputs/style-study-2026-11-11/comparison-shop-top-ours-bottom.jpg.
- Real poster through the application: outputs/style-study-2026-11-11/app-poster-final.png, **1080 × 1350**, SHA-256 58c6bd98e8be665cb7843b46c026b4808752ca1f5788848a01dea1c798837a37. Creation/visual/keys: app-poster-run.json in the same folder. Download equals the preview; no render warnings. 340 000 Ar is the price on the shop's own poster for that model: test data.

## Saved looks from a reference poster (latest request, ADR-046)

- Built: editor "Créer un style depuis une affiche" (upload, name, "Enregistrer ce style"); Claude writes the brief; the look appears in the picker beside the built-in ones and is remembered for the next poster. Backend: posters/looks.py, migration 0010, routes POST /api/creations/{id}/looks, GET /api/looks, GET /api/looks/{id}; `headline.look_id` on scene requests; `compile_scene(headline_style=, align=)`.
- Live Edge run 5 (real Claude + GPT Image): the shop's Select 4 Go poster → look "Vagues bleues" → CMF Buds 2a poster. Evidence: outputs/style-study-2026-11-11/live-edge-5/ (`reference.png`, `brief.json`, `scene.png`, **live-edge-5-poster.png**, report.json). All eleven UI steps passed; left-aligned headline and price pill, blue waves, accent word, title, price, shop name and both numbers exact.
- The look "Vagues bleues" now exists in data-probe. The reference was a 495 px screenshot upscaled to 1000 px for the upload.
- The browser smoke found one defect before the live run: a finished look job was reloaded as a plan (404). Fixed by reporting the job kind as `look`.
- Needs a Claude credential and `PLANNER_PROVIDER=claude`; with the planner disabled the editor hides the action and the API answers `planner_unavailable`.
- `live_edge.py` now holds this scenario (run 5).

## Scene limit and reference-brief exploration (before the build)

- **Scene limit:** 12 scene/refinement jobs per poster instead of 3 (ADR-045, `jobs.SCENE_LIMIT`).
- **Exploration, not built:** Claude (the application's adapter, claude-sonnet-5-5) read two shop posters and wrote a style brief each (direction, surface, lighting, camera, palette, accent colour, headline typography); GPT Image applied each brief to a different product. Script and evidence: outputs/style-study-2026-11-11/explore_reference.py and reference-brief/ (`sheet-reference-vs-result.jpg`, briefs as JSON).
- Result: backdrop, palette and headline typography carried over well (champagne rings and the outlined subtitle pill from the Tour One poster; blue waves from the Select 4 Go poster). Layout did not: the left-aligned headline and left price pill of the Select 4 Go poster came out centred, because the scene prompt fixes the layout. The accent colour was not applied in one of two.
- Two findings for a build: Claude's first brief was accurate but about twice the allowed length, so limits must be in the instructions, not only the schema; the typographic style needs its own screened field in the prompt (the exploration injected it by string replacement).
- Cost: about USD 0.007 per brief; two failed-length attempts were billed too. Next step is T-POSTER-REFERENCE-BRIEF, which needs the user's go.

## Price drawn by the AI (ADR-044)

- User decision: the price is part of the composition; changing it later means a new scene. Editor: "Dessiner aussi le prix dans l’image", default on. The amount is the offer's integer, formatted in code.
- Live Edge run 4 (JBL Tune 770NC, "Aux couleurs du produit", title + price + shop name + contact all drawn): outputs/style-study-2026-11-11/live-edge-4/, **live-edge-4-poster.png** is the current best output. All ten UI steps passed, including: changing the price shows "Le prix est dessiné dans l’image" and disables the export; restoring it clears the notice. Title, "340 000 AR", shop name and both numbers exact.
- The first attempt of run 4 failed an assertion and exposed a real defect (a pill-styled price layer was not hidden at the first scene, so the price would appear twice). Fixed in service.py with a regression test; that failed attempt still cost one scene (0.209323) and left creation with a doubled price in data-probe; it was never approved or exported.
- With every text drawn, the editor's pill styling and footer fitting only matter when an option is switched off.
- Open: T-POSTER-PRICE-ATTEMPTS (three scenes per creation).

## Shop signature drawn by the AI (ADR-043)

- The image model now also draws the shop name and contact when the poster includes them (ADR-043). Editor: "Dessiner aussi le nom de la boutique et le contact dans l’image", default on. Words come from the poster's profile snapshot only.
- Live Edge runs 2 and 3 (JBL Tune 770NC, "Aux couleurs du produit"): outputs/style-study-2026-11-11/live-edge-2/ and live-edge-3/. Both passed every UI step, including the new notice when the contact is unticked after the image drew it. Digits exact in both; run 2 wrote the shop name in capitals.
- Run 2 showed the pill on the lower ear cup. Fixed by giving the plan the signature's real footprint and stating a hard lower limit for the product; run 3 (**live-edge-3-poster.png**, the current best output) has the pill touching only the bottom rim.
- After the last change (prompt wording in plans.py) only tests/test_plans.py and tests/test_poster_visuals.py were re-run, plus live run 3. The last full backend run was 676 passed, 3 deselected, just before it.
- `live_edge.py` now holds the run-3 scenario; the run-1 (Sony, dark look) settings are no longer in the file.

## Live test in Microsoft Edge (run 1)

- `outputs/style-study-2026-11-11/live_edge.py --paid`: installed Edge 156, visible window, real GPT Image 2 call, real ledger. Sony WH-1000XM6, look "Luxe sombre", one tap. Evidence in outputs/style-study-2026-11-11/live-edge/: report.json, five screenshots, scene.png, **live-edge-poster.png** (1080 × 1350).
- Passed in the UI: sign-in, upload, draft, look, headline fields, one tap → one scene job and no plan call, pill styled and centred, title layer hidden, fidelity approval (after the scene was inspected against the photo), stale-title notice blocks then frees the export, preview, confirmation, download equals preview, phone width without horizontal overflow. No page errors, no HTTP errors.
- Found by the live run and fixed afterwards: white shop name/contact (invisible on light looks; now set by the look and centred); the properties panel showed the hidden title layer. Both fixes are covered by the stub smoke in Edge, **not** by a second paid run.
- Seen and not fixed: the product ran lower than its planned area, so the pill covers the bottom of the ear cup (the shop's own posters overlap too, but less). With shop name and contact included, the pill sits high and the footer looks empty. 1 900 000 Ar is the shop's printed price for this model: test data.

## What changed

- **Process (ADR-042):** the image model may set brand, product name and subtitle in the scene ("titre intégré", default on in the editor). The price is never sent and stays an exact layer. This supersedes ADR-030 for the title only.
- **Prompt:** `compile_scene` in posters/plans.py rewritten: use → references → house-style scene → subject scale against the plan's product area → lighting → headline → quiet full-width bands → constraints. `Headline` model and `screen_headline` added there.
- **Backend:** `SceneRequest.headline`; job payload and visual expose `headline` with the exact title sent; first scene hides the title layer (service.py); a hidden title needs a matching recorded headline, else `title_missing` (exports.py); refinement keeps the headline or refuses `headline_stale`; `context_for` plans a hidden title's area; `Document` now only requires the price visible.
- **Editor:** thumbnail look picker (Studio clair, Aux couleurs du produit, Luxe sombre, Décrire moi-même), one accent colour, headline fields (brand, subtitle, accent word), notice and blocked export when the title was edited after the image drew it. Thumbnails: frontend/public/styles/.
- Docs: ADR-042, backend/api/README.md scenes row, TODO, this file. No migration, no dependency. Old requests replay unchanged (`headline` omitted when absent).

## Verification

- Backend, last full run 2026-11-11: 689 passed, 1 failed, 3 deselected. The failure was one stale assertion in tests/test_exports.py (the headline payload gained `look_id`); it was corrected and tests/test_exports.py + tests/test_looks.py then passed (21). No full run after that one-line test fix.
- Frontend: `npm.cmd test` → **26 passed**; `npm.cmd run build` passed, after the last frontend change.
- Browser smoke: `uv run python ../frontend/tests/browser_smoke.py` → passed in bundled Chromium and, with `SMOKE_CHANNEL=msedge`, in Edge 156, after the last frontend change. It picks "Luxe sombre", **unticks the integrated headline** to keep testing the editable title layer, uses the one-tap button and checks the automatic pill.
- After the pill/one-tap work: backend **674 passed, 3 deselected** (227 s); 26 Vitest; build.
- New tests: tests/test_plans.py (headline verbatim, screening, accent word, no component example), tests/test_exports.py (hidden title needs matching headline; rename → refusals; hidden title still plans).
- Real provider: 13 direct study calls and 1 application scene, GPT Image 2 high.
- **Not tested:** the light looks' footer colours on a real scene; a pill restyled by hand then regenerated; Claude planner with looks; physical phones; six of the seven r3 images were checked on reduced contact sheets, not at full size.

## Spend

- Application ledger backend/data-probe/affiche.db, cap **$12**: 1.161964 → **2.630726** (seven scenes and one Claude brief: application run 0.208268, live Edge runs 0.204877, 0.208983, 0.209093, 0.209323 (failed attempt), 0.209323, then brief 0.008612 + scene 0.210283). Never reset it or start another paid data directory.
- Study, direct provider calls **outside the ledger**: **4.196172** (outputs/style-study-2026-11-11/spend.json, including Claude brief calls). Real total spent so far ≈ 6.83; treat the remaining budget as 12 − 2.63 − 4.20 ≈ **5.17**. The study's own USD 5 budget in experiment.py is nearly used. The application's own cap check does not see the 3.05.

## Exact next step

1. Open points, none blocking: the shop name's letter case is not guaranteed (capitals in 1 of 5); a poster without the AI signature still uses the tall default footer boxes, so its pill sits high; the dark look with a signature was tested in the study only, not through the application.
2. Then T-POSTER-009 (square/story, library): the shop's posters are mostly square, and the application still exports feed only.

Ideas seen on the shop's posters and not built: feature list with icons (JBL Tune poster), coloured brand logo box. Both need verified facts or a logo asset, so they need requirements first.

## Landmines added this session

- An example inside the scene prompt is taken literally by the image model (it added earbuds to a speaker). Keep examples out of `compile_scene`.
- The promotion blocklist matches "réduction"; the headline screen exempts only "réduction de bruit".
- `outputs/style-study-2026-11-11/experiment.py` pays outside the ledger and has its own $5 budget; finished tags are skipped. Do not re-run rounds to inspect; images are in results/.
- The product photos in products/ were fetched from manufacturer/retailer sites for testing (sources.json); they are not shop photos.
- Facebook image URLs cannot be read out of the browser tool; references are viewer screenshots.

## Previous deliveries (unchanged)

- R50i reference-typography poster: outputs/style-reference-2026-11-10/soundcore-r50i-reference-typography-final.png, SHA-256 e574e884916eb29f908d22d51f3d95fad531a98225da05a834a3da0f4870b5f9; details in [style-reference-test-2026-11-10.md](reviews/style-reference-test-2026-11-10.md). Earlier dark poster: outputs/review-2026-11-10/. Shop/contact evidence: [shop-poster-sources-2026-11-10.md](reviews/shop-poster-sources-2026-11-10.md).

## Architecture already in place

- Strict Pydantic application document, exact integer MGA offer, immutable product/profile snapshots, owned original uploads, optimistic revisions, idempotent replay and copies/history.
- Shared-shop Argon2/opaque sessions, Origin and ownership checks. SQLite BEGIN IMMEDIATE transactions and forward migrations 0001–0009.
- Fixed/Claude planning with strict geometry/commercial screening; durable jobs/spend ledger; high-quality original-guided GPT integration/refinement; fidelity review separate from final poster confirmation.
- French Vue/Vite/Konva editor with five bundled font files, independent identity fields, manual editing/undo/autosave/conflict recovery and selected-layer Claude proposals/material review.
- Shared offline Chromium renderer, immutable PNG previews/confirmations, exact downloads, effective-format/source/font fingerprints and stale checks.
- No server deployment or publishing integration. Backend/API README and project designs describe contracts.

## Commands and landmines

- Backend: from backend/, uv run pytest -q; uv run python -m affiche.api.
- Frontend: from frontend/, npm.cmd test; npm.cmd run build; npm.cmd run dev. Use npm.cmd; npm.ps1 is blocked. Do not change execution policy.
- Browser smoke: from backend/, uv run python ../frontend/tests/browser_smoke.py. Needs ports 8000/5173 free, current dist and downloaded R50i fixture; uses temporary stub data, no real .env.
- Renderer needs frontend/dist and pinned Playwright Chromium. Install if missing: uv run playwright install --only-shell --no-remove chromium. Build changes never replace historical confirmed PNGs.
- **Never read/print/grep backend/.env.** Legitimate application settings loading is allowed; keys never enter frontend or logs. Runner uses a random in-memory auth password, never persisted.
- Never edit applied migrations 0001–0009. Migrate only through affiche.db.migrate; never set engine isolation_level. Backups: backend/data-probe/backups/before-poster-2026-11-10.db and before-style-poster-2026-11-10.db.
- Outputs/data are Git-ignored; protect database and content-addressed assets together. No commit/push/deploy/publication was requested or done.
- Product framing still requires visual review: geometry checks do not locate semantic product pixels. Integrated product is not independently draggable.
- Live Claude scene planning/text polish and real generated material quality were not tested. Controlled transport/schema/queue and Chromium glyph masking were tested. No physical phone/Safari or backup restoration test.
- Computer-use skill permits native UI only through node_repl @oai/sky. Prior Edge observations are stale; no need for desktop access to finish this task.
- No subagents used. Previous feed goal was completed; no new goal was created for this follow-up.

## Uncommitted files

None after the 2026-11-11 commit on main (no remote). outputs/ and backend/data-*/ are Git-ignored: protect them yourself.
