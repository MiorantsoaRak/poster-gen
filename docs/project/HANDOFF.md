# HANDOFF

**Session date:** 2026-11-11, closed 2026-11-12 (Indian/Mauritius)
**Work order:** none (no ClickUp ticket; personal project for the shop Original Phone Mada).
**State:** nothing in progress, working tree clean, six commits on `main` this session (`05682e3` … `6f18f8c`), no remote. No server or test process is running: the local verification server was stopped by Claude Code because the machine was low on memory; it was not restarted.

## What the application does now

The owner uploads a product photo, types name and price, picks a style, and the image model composes the whole poster: brand, product name, subtitle, price pill, shop name and contact. Every drawn word must still equal what the poster says, or export is refused. He checks fidelity, confirms the final file and downloads a 1080 × 1350 PNG.

Decisions of this session, newest first, all in [DECISIONS.md](DECISIONS.md): ADR-050 (editor rebuilt to the audited mockup), 049 (usability pass), 048 and 047 (two earlier looks, superseded), 046 (saved looks written by Claude from a reference poster), 045 (twelve scenes per poster), 044 (price drawn in the image, user decision), 043 (shop signature drawn), 042 (integrated headline, new scene prompt, looks).

Reports: [style-study-2026-11-11.md](reviews/style-study-2026-11-11.md). Reviewed mockup and audit findings: https://claude.ai/artifact/8zwVrymwP1up1L12SUS422 (private to the user); its sources are in `outputs/style-study-2026-11-11/audit-mockup/`.

## Exact resume point

**T-UI-FINAL-AFTER-CONFIRM is done (2026-11-12, not committed):** the final screen hides the four checks and "Confirmer cette version" once the poster is confirmed (`v-if="!confirmedDownload"` in `frontend/src/App.vue`). The smoke test no longer confirms a second time after a price change; `preview_stale` is covered by `backend/tests/test_exports.py`. Verified with 26 Vitest, the build and the bundled-Chromium smoke; not yet seen by eye in Chrome.

Next, in order:

1. **T-UI-LIVE-AFTER-REBUILD**: one live paid run through the rebuilt editor. `outputs/style-study-2026-11-11/live_edge.py` predates the rebuild and must be updated first: it expects the heading "Votre affiche" (now the poster's own name as `h1`), clicks "Générer la scène" without the confirmation dialog (now followed by "Lancer la génération"), saves a style without "Créer le style", and ticks six review checks (now up to nine: `.review-checks input` still selects them all).
2. **T-UI-MOCKUP-GAPS**: ask the user which remaining mockup differences he wants (accent word as chips, colour swatches, in-place confirmation panel, thumbnails in "Mes affiches").
3. **T-PLANNER-CLAUDE-INVALID**: the Claude composition fails validation with the real model (3 of 3). It is hidden from the editor; capture one real answer before touching it.
4. **T-UI-PHONE-CHECK**, then **T-POSTER-009** (square/story export: the shop's own posters are mostly square).

## Commands

Tests (from `backend/` unless stated):

```bash
uv run pytest -q                                   # last full run: 690 passed, 3 deselected (192 s)
uv run python ../frontend/tests/browser_smoke.py   # bundled Chromium; needs ports 8000 and 5173 free
SMOKE_CHANNEL=msedge uv run python ../frontend/tests/browser_smoke.py   # same flow in installed Edge
```

```powershell
# from frontend/ (npm.ps1 is blocked: always npm.cmd)
npm.cmd test          # 26 passed
npm.cmd run build     # the smoke test and the renderer use frontend/dist
```

Local server on the real test data (real providers, so generating costs money). It serves the production build on 5173 and the API on 8000, and writes a one-off sign-in password to the file you name:

```bash
cd backend
uv run python ../outputs/style-study-2026-11-11/serve_local.py ../outputs/style-study-2026-11-11/local-password.txt
```

Open `http://127.0.0.1:5173/`. Stop it before running the smoke test (same ports). If a port stays taken on Windows:

```bash
for p in 5173 8000; do pid=$(netstat -ano | grep LISTENING | grep ":$p " | awk '{print $5}' | head -1); [ -n "$pid" ] && taskkill //F //PID $pid; done
```

## Spend

- Application ledger `backend/data-probe/affiche.db`, cap **USD 12**: **2.679298** (seven scenes, one Claude style brief, three failed Claude plans). Never reset it or start another paid data directory.
- Study calls made directly to the providers, **outside the ledger**: **4.196172** (`outputs/style-study-2026-11-11/spend.json`); one failed Claude brief of about one cent is missing from that file. The application's cap check does not see this amount.
- Real total ≈ 6.88. Treat the remaining budget as ≈ **5.12**. The study runner's own USD 5 budget is nearly used.

## Verification state

- After the last code change (`6f18f8c`): backend 690 passed / 3 deselected; 26 Vitest; build; browser smoke in bundled Chromium. Edge 156 passed the same flow one small CSS fix earlier.
- Live runs with real providers (five, all before the editor rebuild): `outputs/style-study-2026-11-11/live-edge` … `live-edge-5/`.
- **Not verified:** any live paid run through the rebuilt editor; "Mes affiches", "Styles", the confirmation dialog and the nine-point review on real data (only the final screen was seen in the user's Chrome); a real phone; a contrast audit with a tool.

## Mental context that the code does not show

- The user steers by looking: he rejected two looks (the first as "overused", then asked to think like an image-generation tool) and approved a mockup before the rebuild. Show a mockup or a screenshot before large visual changes.
- He wants every paid action confirmed with its cost, and wants it visible that several versions can be generated and one chosen.
- The price is drawn in the image by his decision (ADR-044): a price change costs a new scene. Do not "fix" that back to an overlay.
- The scene prompt takes examples literally (an example about earbuds put earbuds on a speaker). Keep examples out of `compile_scene`.
- The Vue dev server cannot be driven from the user's Chrome (a browser extension blocks automation on it). Use the production build (`vite preview`, as `serve_local.py` does).
- The commit hook refuses password literals; test passwords are generated per run.

## Landmines

- **Never read, print or grep `backend/.env`.** Loading settings through the application is fine.
- Never edit applied migrations 0001–0010; migrate only through `affiche.db.migrate`; never set the engine's `isolation_level`. Migration 0010 (`looks`) is applied to `backend/data-probe`; backup before it: `backend/data-probe/backups/before-looks-2026-11-11.db`.
- A style brief runs as a `plan` job with a `look` payload (job kinds are fixed by migration 0006); `jobs.get_job` reports it as kind `look`.
- `outputs/` and `backend/data-*/` are Git-ignored: the paid database and its content-addressed assets must be kept together by hand.
- `outputs/style-study-2026-11-11/experiment.py` and `explore_reference.py` pay outside the ledger; finished tags are skipped. Do not re-run them to look at results.
- The product photos in `outputs/style-study-2026-11-11/products/` came from manufacturer and retailer sites for testing (`sources.json`); they are not shop photos. Prices used in tests are copied from the shop's own posters and are not verified offers.
- `data-probe` holds one draft with a doubled price from a failed live attempt (never approved or exported) and the saved look "Vagues bleues".
- Product framing still needs the owner's eye: geometry checks do not locate product pixels.

## Architecture in place

- Strict Pydantic documents, exact integer MGA offers, immutable product/profile snapshots, owned uploads, optimistic revisions, idempotent replay, copies and history.
- Shared-shop Argon2 sessions, Origin and ownership checks, SQLite `BEGIN IMMEDIATE`, forward migrations 0001–0010.
- Durable jobs with a spend ledger; scene, refinement, texture, render and style-brief jobs; twelve scenes per poster.
- `posters/plans.py` `compile_scene`: house-style prompt with optional drawn headline, shop signature, price label, and a saved look's typography and alignment.
- Guards in `posters/exports.py`: drawn title, signature and price must equal the poster's (`title_missing`, `signature_missing`, `price_stale`); refinement refuses `headline_stale`; approval refuses `fidelity_incomplete`.
- French Vue/Vite/Konva editor; shared offline Chromium renderer; immutable PNG previews, confirmations and downloads.
- No deployment and no publishing integration.

## Uncommitted files

Not committed since `6f18f8c`:

```text
 M docs/project/HANDOFF.md
 M docs/project/TODO.md
 M frontend/src/App.vue
 M frontend/tests/browser_smoke.py
```
