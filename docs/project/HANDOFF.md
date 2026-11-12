# HANDOFF

**Session date:** 2026-11-12 (Indian/Mauritius), still open when this was written
**Work order:** none (no ClickUp ticket; personal project for the shop Original Phone Mada).
**State:** nothing in progress. The contact is drawn in the composition again by default (ADR-055, design v3.1 approved in ADR-056); T-SIG-004 and 005 are built, tested and committed. T-SIG-006 is done: live run 8 drew the contact at the right with exact digits and no collision with the price, though beside the pill rather than below it and about 20 px high (details in TODO). "Mes affiches" now uses small resized thumbnails (T-UI-THUMBNAIL-SIZE). Everything up to here was committed with this handoff. No remote. No server is running. Next: ask the user to look at "Mes affiches" and a new poster on the real data, then T-UI-MOCKUP-GAPS, T-PLANNER-CLAUDE-INVALID, T-UI-PHONE-CHECK and T-POSTER-009; the numbered list below predates the drawn-contact work and its items 1 and 2 are done or replaced.

**Logo seal (ADR-057, ADR-058), built on 2026-11-12:** the scene is asked for an empty white disc, the program finds it (`backend/src/affiche/posters/seal.py`) and the real logo file is printed on it as a round seal at 130 px. The shop's real logo is now saved in the `data-probe` profile. Two paid scenes are left pending review in `data-probe` (one of them with its logo unticked by the first, too strict, size rule). The user has seen the composed left-aligned result and has not yet seen or judged the centred dark one. Open: confirm with him the two rule changes of ADR-058, and whether the seal's place with a centred price suits him.

**Guideline review fixes (T-UI-WEB-GUIDELINES, ADR-059), 2026-11-12:** the view is in the address hash, the three panels are real dialogs with the page behind inert, every paid or destructive tap asks first, the price error sits beside its field. Build, 26 Vitest and the browser smoke pass; a screen reader and a real phone were not tried.

**UX audit fixes (T-UI-UX-AUDIT), 2026-11-12:** main button fixed at the bottom on one-column widths, stale notices under their fields, title and price locked while a scene draws them, focus rules, phone sizes. A second pass changed the wording of the main flow ("Préparer mon affiche", "Générer l’affiche", "version"; Claude's proposal, the user said to fix the rest) and added price and date to "Mes affiches" (`backend/src/affiche/api.py` and `backend/tests/test_api.py` are also modified). Managing styles and posters (rename, delete, duplicate, status, more than 50 posters) needs requirements first; see the TODO entry.

**Read this first about the footer:** it changed direction twice on 2026-11-12. ADR-053 made the contact a rendered text layer; the first real poster showed that layer landing on the drawn price pill (the image model had drawn the pill into the band kept for the contact); ADR-055 went back to a drawn contact and kept the rendered line as the fallback. The text below about T-SIG-001 to 003 describes that fallback.

## What the application does now

The owner uploads a product photo, types name and price, picks a style, and the image model composes the whole poster: brand, product name, subtitle, price pill, shop name and contact. Every drawn word must still equal what the poster says, or export is refused. He checks fidelity, confirms the final file and downloads a 1080 × 1350 PNG.

Decisions of this session, newest first, all in [DECISIONS.md](DECISIONS.md): ADR-050 (editor rebuilt to the audited mockup), 049 (usability pass), 048 and 047 (two earlier looks, superseded), 046 (saved looks written by Claude from a reference poster), 045 (twelve scenes per poster), 044 (price drawn in the image, user decision), 043 (shop signature drawn), 042 (integrated headline, new scene prompt, looks).

Reports: [style-study-2026-11-11.md](reviews/style-study-2026-11-11.md). Reviewed mockup and audit findings: https://claude.ai/artifact/8zwVrymwP1up1L12SUS422 (private to the user); its sources are in `outputs/style-study-2026-11-11/audit-mockup/`.

## Exact resume point

Done on 2026-11-12 (details and verification in TODO.md; decisions ADR-051 and ADR-052):

- The confirmed final screen no longer shows the checks or a second confirmation.
- Both review screens are a read-only summary with one agreement, no checkbox per point (ADR-051, user decision).
- The scene prompt counts the quoted headline strings and maps a look's described subtitle to the typed one. Live run 6 had drawn an invented line; run 7, with the fix, drew only the typed texts. One scene is not proof that the model always obeys.
- A new price capsule takes a fill that contrasts with the digits; the "scene ready" notice no longer covers the review.
- "Mes affiches" shows each poster's last final preview, or its scene, as a thumbnail.
- R-CATALOGUE-BRAND-003 and 004 are approved (ADR-052) and 003 amended (ADR-053): the contact is one compact line with a telephone icon written by the renderer, never drawn by the image model in new scenes; its position (left, centre, right) is the layer's alignment and is free to change; the shop name starts unticked; the brand can be written as plain text. Design D-CATALOGUE-BRAND-004/005 approved at v2.1 (ADR-054) and built as T-SIG-001 to 003.

Next, in order:

1. Ask the user to look at a real poster with the new footer (start `serve_local.py`, see Commands). Things to look at: the contact size and colour on a real backdrop, and that with a logo the contact line is level with the top of the logo, not centred on it (this is how `fixed_plan` has always placed footer texts).
2. With the user's go only: one paid scene with "Écrire la marque en texte simple" on (about USD 0.21).
3. **T-UI-LIBRARY-THUMBNAILS** stays `[~]` until the user has seen the list on real data.
4. **T-UI-MOCKUP-GAPS** (thumbnails are done), **T-PLANNER-CLAUDE-INVALID**, **T-UI-PHONE-CHECK**, then **T-POSTER-009**.

Open points from the live runs:

- The run 6 scene with the invented line "POUR TOUTES VOS NOTES" is recorded as approved in `data-probe` (approved in the Edge window, not by Claude), with a final preview and no confirmation. The user has been told; he has not said whether it was intended.
- The stale title, price and signature notices were not exercised on real data after the rebuild.
- With three groups of points the review's buttons sit below the fold of a 1000 px tall window; the panel scrolls.
- `outputs/style-study-2026-11-11/live_edge.py` now writes to `live-edge-7/` and waits 45 minutes for `approve.flag`. If the reviewer approves in the browser instead, the script cannot finish its own steps.

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

- Application ledger `backend/data-probe/affiche.db`, cap **USD 12**: **3.313306**, read from both ledger tables on 2026-11-12 after live runs 6 and 7 (0.210283 and 0.210483). The figure in the previous handoff (2.679298) left out the last brief and scene of 2026-11-11. Never reset it or start another paid data directory.
- Study calls made directly to the providers, **outside the ledger**: **4.196172** (`outputs/style-study-2026-11-11/spend.json`); one failed Claude brief of about one cent is missing from that file. The application's cap check does not see this amount.
- Real total ≈ 7.52. Treat the remaining budget as ≈ **4.48**. The study runner's own USD 5 budget is nearly used.
- Later on 2026-11-12: the ledger read **3.939988** after two scenes the user generated in the editor and live run 8 (0.210658). Real total ≈ 8.15; remaining ≈ **3.85**.
- Logo study, same day: five direct calls, 1.081501, outside the ledger (study file now 5.277673; its own budget was raised to 5.6). Real total ≈ 9.22; remaining ≈ **2.78**.
- Logo seal paid check, same day: two scenes through the application, 0.422076; the ledger reads **4.362064**. Real total ≈ 9.64; remaining ≈ **2.36**. Results: reviews/logo-study-2026-11-12.md; waiting for the user's choice (T-LOGO-STUDY).

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

None expected: the logo seal, T-UI-WEB-GUIDELINES and T-UI-UX-AUDIT were committed on the user's "commit" of 2026-11-12. Check `git status`; anything listed there was written afterwards (the draft requirements R-CREATION-LIBRARY-003 and 004 were started right after that commit).
