# DESIGN — poster-format

**Status:** v2, 2026-11-14, approved under the autonomy grant (ADR-080) after a fresh review (APPROVE WITH FIXES, two P1) and a devil's advocate (go ahead with changes); every point below is applied in "v2 changes", which wins over the v1 text under it. v2 was not reviewed again; each build task gets a fresh code review. v1 was written by a planning subagent from the code at `159892b`. **Requirements:** [poster-format](../requirements/poster-format.md); R-FORMAT-EXPORT-001 (first criterion).

## v2 changes (these win over the sections below)

1. **Format belongs to the poster; a scene belongs to one size (review P1).** Versions are listed by product input, so a copy can meet a scene of another size and send a paid refinement at the wrong size. Server: `_references` refuses a scene whose `size` is not `POSTER_SIZES[format]` (`scene_format_mismatch`); `request_refinement` refuses when the base's plan format differs from `request.format`; `GET /api/creations/{id}/visuals` returns only the versions of the poster's format size. The lock condition becomes "no version of this input **in another size than the requested one** is selected in the document, and no version exists for this input at all" stays as written for the change itself; the filter and the two refusals make the mixed state harmless. Clearing `pendingInput` stays, as a courtesy.
2. **`copy_creation` applies the same rule (review P1).** An `unsaved_document` whose `primary_format` or format keys differ from the source is refused (`format_locked`) unless the copy gets a new input (point 3). Test.
3. **A way out of the lock (devil's advocate).** On a poster with versions, the locked sentence carries one button, « Refaire en Story » (or the model's format): a new product input with the same body (photos, name, variant) is created, the poster is copied onto it with `new_input_id` (`store.py:283-286`), and the copy is reformatted. The new poster has no version, so its format is free. To verify in the build: that the input endpoint gives a fresh id for an identical body; if it deduplicates, add an explicit way to get a fresh input.
4. **Ask only when the model is close to a format.** `nearestFormat` returns a format only when |ln(r / target)| ≤ 0.08 (covers 3:4 → Publication, 2:3 → nothing, any landscape → nothing). The "snapped" wording goes: one sentence, « Votre modèle est au format Story (9:16). Utiliser ce format pour l'affiche ? ».
5. **One place to choose: the Style step.** No picker in the intake form; a new poster starts in Publication. The question shows where the model or the saved style is picked. This removes "the question also shows at intake".
6. **The lock says why:** « Le format ne change plus après la première version : le titre, le prix et le contact sont dessinés dans une image à cette taille. »
7. **Jobs:** the guard refuses during a queued or running `scene` or `refine` job only (a style brief is a `plan` job and must not lock).
8. **Autosave and undo.** A format step is not undoable once a scene or refine job has started (the history is cut at job start for format steps); on `format_locked` the client reloads the stored document and says so, instead of resending the refused save.
9. **Refusal memory:** a "no" is kept per creation id and model asset, in memory for the visit; a reload asks again once.
10. **`reformat()`** also clears the plan (`plan.value = null`) and keeps every layer inside the new canvas (clamp after the move); overlaps before the first scene are accepted, since the first scene re-places the layers.
11. **Cost:** the reservation stays the flat `ESTIMATE_SCENE_USD` (0.40), far above measured costs (0.03–0.21 for 4:5; Story has 1.6 times the pixels). The real Story cost is recorded in T-FMT-007 and the estimate raised if it comes within a factor of two.
12. **Wrong size returned:** already handled: the size check raises a `ProviderError` inside the provider result and the worker records its cost (`gateway.py:173, 303`, `worker.py:71-73`). A stub test pins it in T-FMT-001.
13. **Story margins:** a per-format constant (default 13 % top and bottom), tuned on the app the shop really posts stories to (asked to the user; T-FMT-007).
14. **Order of tasks:** T-FMT-003 (margins and contact size) lands before Story is enabled, because a seal prompt recompiles the fixed plan and compares it with the stored one (`plans.py:264-269`): 003 → 002 (with points 1, 2, 7) → 001 → 004 → 005 → 006 → 007.
15. **Paid check before the owner sees the new formats:** the Style step shows Carré and Story only when the server says they are enabled (`FORMATS_ENABLED`, a setting, default `feed` only); the pilot's `deploy/compose.yml` turns them on after T-FMT-007 passed, on the user's word.
16. **Tests added to the list:** wide screen (1366 px) for Square and Story; the refusal memory; the locked sentence with its button; confirmation and download for Square as well as Story.
17. **Records:** this design replaces, for the pilot, the part of D-FORMAT-EXPORT-001 that reuses one approved scene across formats ("no automatic additional scene request"): with the text drawn in the image (ADR-044, ADR-055) a scene cannot be recropped, so each format has its own scene. T-POSTER-009's square/story part is narrowed accordingly.

## D-POSTER-FORMAT-001 — Choose the poster format, and ask when the model has another shape

### 1. Findings that shaped the design

1. **Format change needs no new endpoint.** `save_creation` (`store.py:254-269`) only refuses a changed `input_id`. A `PUT` with another `primary_format` and a one-layout `formats` map is accepted today, with no guard.
2. **Versions are listed by product input, not by poster** (`api.py:411`). A duplicate shows its source's versions. `pendingInput` (`App.vue`) is never cleared, so retyping the same photos, name and variant reuses the input: a new Story poster would show 4:5 versions.
3. **The model's size is already known.** Upload returns `width`/`height` after EXIF rotation (`store.py:101, 117`) and stores them in `assets` (migration 0001). A saved look keeps `reference_asset` (`looks.py:110`). No migration, no browser image decoding.
4. **A look is not tied to a shape.** `StyleBrief` (`looks.py:45-53`) has no geometry, and its prompt excludes text positions.
5. **`chooseStyle` is not in the template.** `styleReference` only comes back from an existing version. Today "the model" in the UI is « Affiche modèle » and saved looks.
6. **Story is the format with design work.** The fixed plan puts the title at 5 % and the contact at 92.5–95 % of the height. Instagram covers roughly the top and bottom 13 % of a story (unverified; to check on the owner's phone).

### 2. Decision: when can the format change

| Option | Cost | Risk | Verdict |
|---|---|---|---|
| 1. Choose at intake; change while the poster has no version | Client `reformat()` + existing `PUT` + one server guard | Low: before the first scene, layers only feed `field_sizes`; the first scene re-places them (`service.py:153-168`) | **Chosen** |
| 2. Second layout in `formats`, switch primary | The UI reads only `primary_format`; needs a format switcher, per-format versions, D-FORMAT-EXPORT-001 in full | High | Rejected here |
| 3. Copy in the other format | The copy shares the input, so it shows the source's versions and opens in tabs; choosing a 4:5 scene in 9:16 would cut the drawn title | Medium | Deferred; needs versions filtered by size first |

**Posters that already have versions:** the format is locked. A scene has one pixel size, and its drawn title, price and contact cannot be recropped. The UI says so and offers no switch.

### 3. Data model and API

**No migration. No new endpoint.**

- `POST /api/creations`: unchanged; `primary_format` is already accepted (`models.py:92`). The client sends the chosen value instead of `'feed'`.
- `PUT /api/creations/{id}`: new guard in `save_creation`. When `primary_format` or the keys of `formats` differ from the stored revision, refuse `409 format_locked` unless all hold: `set(formats) == {primary_format}`; the new layout has no scene; no `poster_visuals` row has this `input_id` (the rule of `api.py:411`); no queued or running job exists for the creation.
- French sentence in `api.py`: « Le format se choisit avant la première version de l'affiche. » The `format_unavailable` sentence goes.
- `GET /api/looks`, `GET /api/looks/{id}`: `_public` (`looks.py:109`) adds `reference_width` and `reference_height`, joined from `assets`.
- `POST /api/creations/{id}/renders`: remove the gate at `exports.py:99-100`.
- `GET /api/creations`: `api.py:610, 612` hard-code `$.formats.feed`; use `'$.formats.' || json_extract(v.document_json,'$.primary_format') || '.scene.visual_id'`.

### 4. Audit

| Area | State | Evidence or work |
|---|---|---|
| Create, initial layers | Works | `store.py:170-185` is parametric on height; all layers stayed inside the canvas for the three formats in the read-only run. No test passes a format yet. |
| `fixed_plan` geometry | Works; Story needs margins | `test_plans.py:19-30` covers three formats × eight identity choices. Work: top/bottom per format (`plans.py:159-171`), Story 0.13/0.87; feed and square unchanged. |
| `compile_scene` | Mostly generic | Size sentence uses `POSTER_SIZES[context.format]`; bands and "Hard limit" are fractions. Work: contact digits "about 2 % of the frame height" give 21.6 px in square (under the 22 px minimum) and 38 px in story (breaks the 23 px-per-character rule): use 2 % / 2.5 % / 1.4 %. The feed prompt must stay byte-identical: refinements recompile stored scenes. |
| `seal_place`, `find_disc` | Generic, never run outside feed | Fractions; `service.py` scales by `FORMATS`. |
| Scene request, refinement, size check | Works | `validate_image` is strict on size, tested for the three sizes (`test_gateway.py:94`). |
| Cost reservation | Unverified | One `estimate_scene_usd` for every size; Story has 1.6 times the pixels of feed. |
| Renderer | Generic, untested outside feed | The 1080×1920 viewport (`rendering.py:101`) fits Story. |
| Export, confirmation | One gate | `format_hash` includes `format`; sizes and file name come from the format. Work: the gate at `exports.py:99`. |
| Copies | Works | `copy_creation` copies the document whole. |
| Library | Needs work | The query of section 3; `.library-item img` is 48×60 `cover`: use `contain`. |
| Looks | Works | Finding 4. |
| Evaluation CLI | Unaffected | It is the phase-1 master path, not the poster path. |

### 5. Model shape and snapping

A pure function in `frontend/src/document.ts`: `nearestFormat(width, height) → { format, exact }`. With r = width / height: r ≥ 0.894 → `square`; 0.671 ≤ r < 0.894 → `feed`; r < 0.671 → `story` (thresholds are the geometric means √(1 × 0.8) and √(0.8 × 0.5625): nearest by log-ratio). `exact` when |ln(r / target)| ≤ 0.02. Sources: the upload response for a new « Affiche modèle »; `reference_width`/`reference_height` for a saved look. Built-in looks have no model, so no question.

### 6. UI and states

- **Intake:** a three-option radio group « Format », after the price row: « Publication 4:5 », « Carré 1:1 », « Story 9:16 ». Default Publication. Native radios with the existing chip style.
- **Style step:** the same group above the look grid, enabled while the poster has no version and no job. Otherwise disabled, with « Le format se choisit avant la première version. »
- **The question:** inline, `role="status"`, under the picker that triggered it, with two buttons. It never switches alone. Shown when `nearestFormat(model).format !== format`, the format is changeable, and this model was not declined for this poster (one in-memory ref).
  - Exact: « Votre modèle est au format Story (9:16). Utiliser ce format pour l'affiche ? » [Utiliser Story] [Garder Publication]
  - Snapped: « Votre modèle n'a pas un format d'affiche ; le plus proche est Carré (1:1). Utiliser ce format ? »
  - Locked: « Ce modèle est au format Story. Cette affiche garde son format : il se choisit avant la première version. » No button.
  - It also shows at intake when the remembered look is a saved one.
- **`reformat(document, to)`** in `document.ts`: width is 1080 in every format, so x and width stay. A layer whose centre is in the lower half moves by the height difference. `formats = { [to]: layout }`, scene empty. Sent through `edit()`, so it is undoable and saved by the existing `PUT`. `planSignature` already contains the format.

Sizes at 360 × 740:

| View | Feed | Square | Story | Work |
|---|---|---|---|---|
| Sticky poster in tabs (`posterHeight` = 252) | 202 × 252 | 252 × 252 | 142 × 252 | None: bounded by height |
| Typing strip (96) | 77 × 96 | 96 × 96 | 54 × 96 | None |
| Step thumbnail (104 px column) | 104 × 130 | 104 × 104 | 104 × 185 | Cap at 130 px high (the smoke requires the first field above 444 px) |
| Large view (332 px wide) | 415 high | 332 | 590 | Scrolls; optional height bound |
| Versions strip | 56 × 70 | cut | cut | `aspect-ratio: var(--poster-ratio)` set on `.editor`, height 70 px, width auto |

Hard-coded text and sizes to replace in `App.vue`: « Publication · 1080 × 1350 », the final preview's `width="1080" height="1350"` (`get_render` already returns width and height), « 1080 × 1350 px », the `104 × 130` thumbnail.

### 7. Failure modes

| Failure | Detection | Behaviour |
|---|---|---|
| Format changed after a version exists, or during a job | Guard in `save_creation` | `409 format_locked`, French sentence; the draft is unchanged |
| Format changed in a second tab | Existing revision check | Existing conflict flow |
| A plan made for the old format | `plan_stale`; `planSignature` | Re-planned before the scene; no paid call on a stale plan |
| The provider refuses 1152×2048 or returns another size | Strict size check | Job fails; no version is stored. Unverified whether the cost is recorded in this case |
| The title does not fit the Story or Square plan | `layout_not_plannable` | Existing refusal sentence |
| Story text under the Instagram interface | Human check on a phone | Section 4 margins; paid check |
| Seal disc not found in a new format | `find_disc` returns None | Existing path: the poster goes on without its logo and the review says so |
| Same product typed twice, in two formats | `pendingInput` reuse | Clear `pendingInput` after a successful creation |
| Look reference file missing from `assets` | Join returns null | No question; the format stays |

### 8. Free and paid verification

**Free:** stub scenes at the three sizes, plan geometry, prompt strings, the real Chromium render to exact PNG dimensions, the guard, snapping, `reformat`, the smoke at 360 × 740.

**Paid, never done in this project:** whether the provider accepts 1152×2048; whether the headline, pill, contact and seal are composed correctly in Square and Story; whether the product keeps its size in the shorter Square band; the real cost of a Story scene against the single estimate. One scene each in Square and Story, judged on a phone inside Instagram, on the user's word only (T-FMT-007).

### 9. Out of scope

Several formats in one poster, a copy in another format, reuse of a scene across formats, arbitrary ratios, a landscape format.

### 10. Tasks

- **T-FMT-001 — Backend: formats enabled end to end.** Remove the export gate; the library query follows `primary_format`; drop the `format_unavailable` sentence. Tests over the three formats: create → fixed plan → stub scene → first-scene placement → approve → render → PNG size equals `FORMATS[f]`; the library item has a thumbnail and the right state. Verify: `uv run pytest`.
- **T-FMT-002 — Backend: the `format_locked` guard and look dimensions.** Verify: `uv run pytest tests/test_poster_drafts.py tests/test_looks.py tests/test_api.py`.
- **T-FMT-003 — Backend: Story margins and contact size per format.** The feed and square plans and the feed prompt unchanged (strings captured before the change); Story boxes inside 0.13–0.87; `logo_seal` compiles in the three formats. Verify: `uv run pytest tests/test_plans.py tests/test_seal.py tests/test_poster_visuals.py`.
- **T-FMT-004 — Frontend: `nearestFormat` and `reformat`, with Vitest.** Verify: `corepack npm@10 test`.
- **T-FMT-005 — Frontend: format choice and the question.** Smoke: create a Story poster; a 9:16 model on a Publication poster shows the question, accept, the saved `primary_format` is story, generate with the stub, download a 1080 × 1920 PNG; with a version the group is disabled. Verify: Vitest, build, browser smoke.
- **T-FMT-006 — Frontend: shapes at 360 × 740.** `--poster-ratio`, versions strip, library thumbnail, step thumbnail cap. Smoke for Story and Square in both themes. Verify: build, browser smoke.
- **T-FMT-007 — Paid check.** After the user's word only: one Square and one Story scene through the application; record size acceptance, composition, seal detection and cost.
