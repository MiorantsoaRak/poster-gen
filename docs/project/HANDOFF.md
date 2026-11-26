# HANDOFF

**Session date:** 2026-11-26
**Working on:** T-UNIFIED-04 — complete, uncommitted

## State of the world

Unified creation was committed as `b026b241eb5ec170860376431a38283ed183b674` and pushed to `origin/main`; its handoff followed in `c5194ea`. Libre is the primary flow; Pas à pas prepares the same prompt; Message entry points are removed. Existing saved product posters still open in their legacy editor. Neither that delivery nor this follow-up was deployed here.

The owner's latest screenshot explicitly requests removal of manual movement/framing controls. This follow-up is implemented and verified locally. No supplied shop logo means no invented shop logo; all new poster text and identity go through the image model.

## Done this session

- Removed movement toggle, zoom/pan sliders and manual layer position/dimension fields from `App.vue`; removed their unused scene helpers. Scene-only selectors disappear when no selectable layers exist.
- Reused the existing read-only canvas mode to remove drag, transform, keyboard movement and its misleading keyboard instructions. Existing stored crops/layers are unchanged; legacy typography settings and model-based scene correction remain.
- Extended `unified_creation_browser.py` to open an old Message link, generate a stub scene, check removed controls/read-only preview, open and cancel the model correction dialog, and assert the saved document remains unchanged.
- Updated affected expectations in three older browser scripts; they still encode retired creation routes and were not run in full.
- Verified production build, **420 frontend tests**, unified browser at **1366/390 px** (includes a **360 px** narrow check and refused-image recovery), Python parsing of all four changed browser scripts, and `git diff --check`. Inspected desktop light and phone dark screenshots: `outputs/unified-creation/legacy-adjustment-{1366,390}.png`.
- Updated requirements, design, TODO and decisions. No backend code, migration, dependency or paid image call.

## In progress — exact resume point

- **Task:** none unfinished for this request; T-UNIFIED-04 is complete.
- **Where I stopped:** local changes verified, not committed or pushed. Previous push authorization was fulfilled before this follow-up. No deployment requested.
- **Next action:** review/commit this follow-up when requested. Release remains the owner's operation through `deploy/README.md`.
- **Context:** `FreeCreation.vue` owns new Libre/guided creation. This change only affects the saved product editor in `App.vue`; it does not destructively convert old documents or change image generation.

## Landmines / gotchas discovered

- Legacy canvas geometry remains part of stored documents and rendering. Removing the controls must never reset that data. The shared `PosterCanvas.vue` retains its capabilities for other callers; only the editor opts into read-only preview.
- Old wizard/chat smoke scripts target retired entry routes. Their affected assertions were updated, but only the current unified browser was executed for this follow-up. No backend suite or paid image tests rerun for a frontend-only removal.
- Prior delivery validation/evidence: backend **2,142 passed**, 3 opt-in deselected, then 9 focused tests; build/420 frontend checks; free/unified browser scenarios; **22 paid outputs** inspected. Successful usage USD 1.001507 plus USD 1.20 estimated for 3 interrupted calls gives ledger USD 2.201507. Details and residual model limits: [acceptance report](reviews/unified-creation-acceptance-2026-11-26.md).
- Model output still needs human review of prices, text, product details and logo fidelity. Paid evidence remains ignored under `outputs/unified-creation/`; do not regenerate merely to inspect it.
- No physical-device check, live Facebook post or production change. Other tracks' pending-proof notes in TODO remain unchanged.

## Uncommitted / dirty state

- `frontend/src/App.vue`
- `frontend/tests/unified_creation_browser.py`
- `frontend/tests/browser_smoke.py`
- `frontend/tests/editor_refinements_browser.py`
- `frontend/tests/terms_browser.py`
- `docs/project/requirements/unified-creation.md`
- `docs/project/designs/unified-creation.md`
- `docs/project/TODO.md`
- `docs/project/DECISIONS.md`
- `docs/project/HANDOFF.md`

Pre-existing untracked `.impeccable/config.json` and `.impeccable/design.json` remain untouched. Ignored screenshots/output stay local. Browser test servers were stopped by their harness.

## Next session should

1. Review the verified T-UNIFIED-04 diff; commit/push on instruction, excluding unrelated `.impeccable/` and ignored evidence.
2. On release instruction, follow `deploy/README.md`, then check Libre/Pas à pas and an existing poster on the released build.
3. For generation issues, consult [the acceptance report](reviews/unified-creation-acceptance-2026-11-26.md) and exact selected base/instruction history before changing prompts.

## Decisions made this session

- Apply the screenshot removal to legacy posters as well as the already simplified new flow. Use read-only preview rather than leave hidden movement shortcuts.
- Preserve saved geometry and model correction; no data migration or paid regeneration is needed.
- The full historical multi-session handoff remains in `b026b24:docs/project/HANDOFF.md`. This handoff covers the current follow-up.
