# HANDOFF

**Two tracks share this checkout.** Claude's track (the deployed editor) is the next block. Codex's track (text-first generation: research and an isolated mockup, nothing built) follows it, newest first; its files are the only uncommitted ones.

## Changes by message are a set of fields — handoff of 2026-11-15, later session (READ FIRST)

**Why:** the user wrote « Sony is the brand, put it on top, the product title on the second line » on a poster and the chat answered that the title is changed in « Pas à pas ». He asked for a durable change, not a prompt patch (ADR-099).

**State: built, reviewed, committed on `main` (commit "T-CHAT-006, T-CHAT-007: a change asked in the chat is a set of the editor's fields (ADR-099)"), NOT pushed, NOT deployed.** T-CHAT-006 (backend) and T-CHAT-007 (frontend) are done in TODO.md. On a poster the reader fills the editor's fields (title, brand, subtitle, price, scene instruction) from one table in `backend/src/affiche/posters/reads.py` (`FIELDS`); the server reads the current words from the version the owner looks at and states the effect (`refine`, `scene`, `free`); the chat has one change card. Requirements amended (R-TEXT-FIRST-004, 005), design [D-TEXT-FIRST-005 v4](designs/text-first-generation.md), reviews in `reviews/text-first-d005-*` and `reviews/t-chat-006-*`, `t-chat-007-*`.

**Verified on Linux (stub data, zero spend):** `tests/test_reads.py` 175 passed; full backend suite 970 passed / 3 deselected (before the last test-only addition); 182 Vitest; build; `chat_browser.py`; `browser_smoke.py`. **Never verified:** a real phone, the hosted pilot, the check and download of a version made by a word change.

```sh
cd backend && uv run pytest tests/test_reads.py -q && uv run pytest -q
cd frontend && corepack npm@10 test && corepack npm@10 run build
cd backend && uv run python ../frontend/tests/chat_browser.py && uv run python ../frontend/tests/browser_smoke.py
```

**Pushed** (`origin/main` holds the commit above). **T-CHAT-008 done** on the user's word: [report](reviews/chat-change-eval-2026-11-15.md), 25 of 26 change messages read as expected, his own sentence included; one real brand change made version 3 of the JBL poster in `backend/data-probe`; USD 0.0974 on the ledger.

**T-CHAT-STYLE-KEPT done** (ADR-100, the user's decision): a word change from the chat now reuses the version's plan, drawn settings, model image and contact alignment, so the new image keeps the version's style. Built, reviewed, committed and pushed (commit "T-CHAT-008, T-CHAT-STYLE-KEPT: …"). Stub checks pass (backend 971 / 3 deselected, 182 Vitest, build, the three browser smokes).

The paid check (the user's word, USD 0.0304) showed the plan's style kept for real: the brand change on the night-blue version gave a charcoal and gold image, not a light one. It also showed a gap: the night blue itself, which came from a refinement by message, was lost.

**T-CHAT-REFINE-KEPT done** (ADR-101, the user's decision): the chat's scene request names the version it replaces, and the server carries that version's scene adjustments into the new image. Reviewed, committed and pushed (commit "T-CHAT-REFINE-KEPT: …"). A second paid check (USD 0.0308) gave a night-blue image with the right words. `backend/data-probe` now has five versions of the JBL poster. Spend of the day for this work: USD 0.1586, all on the ledger.

**Exact next step:** the user's deploy, backend and frontend together. Open follow-ups in TODO.md: T-CHAT-D005-TESTS, T-CHAT-CANVAS-LOAD, the list label of a version made from an older one, keeping the text of messages the chat could not take.

**Landmines:**
- Backend and frontend of this change go out together. An old frontend against this backend answers « Rechargez la page pour continuer. » (`reload_required`) to every change message; nothing is paid.
- The new-poster reader (prompt, schema, the unused `scene_change` / `price_change` intents) is left as it was on purpose: its prompt was measured in the paid test of 2026-11-14. Do not tidy it without a new paid test.
- The design was approved under the autonomy grant after three REJECT rounds; v4's last four fixes were checked by the code reviews, not by a fourth design round.
- Since ADR-100 a word change keeps the version's style. Left to the editor's state: a version whose plan belongs to another poster (a copy) or format, and the coloured pill of a layer price. A kept plan can be refused if the layout was changed in « Pas à pas » since; the card then points there.
- The word guard cannot detect a wrong arrangement of the owner's own words; the card and the check show each text whole.
- Open for the user: keep the text of messages the chat could not take (`chat_reads` holds a hash only); T-CHAT-CANVAS-LOAD (the chat loads the canvas modules, against the rule below); T-CHAT-D005-TESTS.

**Uncommitted:** only Codex's old `docs/project/mockups/text-first/` (untracked). The paid scripts are in `outputs/chat-change-eval-2026-11-15/` (git-ignored); do not rerun them to look at results.

## Creation by message — handoff of 2026-11-15, earlier session

**State:** the feature is pushed (`origin/main` = `0e5fa64`) and **deployed by the user on 2026-11-14 21:03 UTC**. Claude read the box on 2026-11-15 (read only): container `affiche-ia-affiche-ia-1`, image revision `0e5fa64`, healthy, no restart, 112 MiB of 1 GiB, no error in its logs, migration 0012 applied, `planner_mode` claude, no chat read yet. Built and committed: T-CHAT-001 to 005 are done (TODO.md). Requirements R-TEXT-FIRST-001 to 005, [design v2](designs/text-first-generation.md), decisions ADR-091 to ADR-098. The user gave full autonomy for this feature, paid calls included (ADR-093); push and deploy stay his word. Nothing is in progress.

**What exists:** a choice screen and a switch « Message » / « Pas à pas »; a chat that reads each message with a paid Claude call (`POST /api/reads`, ledger `chat_reads`, migration 0012), shows one recap with its cost, makes the poster through the editor's own functions, hands the check and the download to the editor's dialogs, changes a scene or a price from a message, and lists the modifications. Reports: [reading test](reviews/chat-read-eval-2026-11-14.md), [failure audit](reviews/chat-failure-audit-2026-11-15.md), [first real poster and read-back measurement](reviews/chat-paid-run-2026-11-15.md).

**Verified on Linux at the last commit:** backend 940 passed / 3 deselected; 179 Vitest; build; `browser_smoke.py`; `chat_browser.py`; `editor_refinements_browser.py` (before the last one-line fix; the chat smoke, Vitest and build were rerun after it). One real poster and one change through the chat on `backend/data-probe` with `gpt-image-2.5-flare`. **Never verified:** a real phone, a screen reader, the hosted pilot.

```sh
cd backend && uv run pytest -q
cd frontend && corepack npm@10 test && corepack npm@10 run build
cd backend && uv run python ../frontend/tests/browser_smoke.py && uv run python ../frontend/tests/chat_browser.py
# free look at the chat (simulated images, no spend); password in outputs/demo-password.txt
cd backend && uv run python ../outputs/serve_demo.py ../outputs/demo-password.txt
```

**Exact next step:** the user's report from his phone on the live chat (the first read on the pilot will show in `chat_reads`). Then T-CHAT-FOLLOW-UPS in TODO.md, each on his word.

**Landmines of this feature:**
- Read ADR-097 and ADR-098 before touching `frontend/src/ChatView.vue`: the chat never guesses what a paid request became. Five review rounds were lost to time-based and order-based inference.
- Every fresh browser context of the smokes presets `affiche.start=steps`; without it a test lands on the choice screen.
- The chat must never mount `PosterCanvas` or load `fonts.ts`.
- `ClaudePlanner.structured` accepts a reasoning block beside the text; a read asks for none (`thinking: between_tools`, ADR-096). `claude-sonnet-5-5` refuses `disabled`.
- The price read from a message is an allowlist of whole digit tokens (ADR-095); do not relax it without the adversarial cases of `backend/tests/test_reads.py`.
- Migration 0012 is applied to `backend/data-probe` (backup `backups/before-chat-reads-2026-11-14.db`). Spend of the feature: about USD 0.34, of which 0.21 on that ledger.
- Paid scripts of this feature are in `outputs/chat-read-eval-2026-11-14/`, `outputs/chat-paid-2026-11-15/` and `outputs/price-readback-2026-11-15/` (git-ignored); the last one pays outside the ledger. Do not rerun them to look at results.

**Uncommitted:** only Codex's old `docs/project/mockups/text-first/` (untracked, superseded by `mockups/chat-first/`; about 1.7 MB of images).

## Creation by message — Claude, 2026-11-14 (later session; T-CHAT-MOCKUP, ADR-091)

The user asked Claude to challenge Codex's text-first research and to mock a proper chat. Done: `docs/project/mockups/chat-first/` (self-contained; open `index.html`, or https://claude.ai/artifact/767SDMWe3h45kJHpcJ3vJT, private to the user). `#recap`, `#versions` and the other names of the « Aller à » list open a state directly. Nothing is generated; the poster is the fixed Sony scene with a price laid over it, as in Codex's mockup. The user then decided the paid reading of each message (ADR-092), and Claude rewrote the requirements as Draft v2 (R-TEXT-FIRST-001 to 005, replacing Codex's v1 in the same file). The user then gave full autonomy for this feature, paid calls included, inside the cap (ADR-093). Requirements are approved and amended (ADR-094); [design v2](designs/text-first-generation.md) is approved after a review and a devil's advocate (reports in reviews/text-first-design-*-2026-11-14.md). **Exact next step:** T-CHAT-001 in TODO.md, then 002 to 005 in order. Push and deploy stay the user's word. Commit `T-NEUTRAL-GROUND, T-CHAT-MOCKUP` holds the stylesheet and the mockup, not pushed. After three rounds the user chose a neutral ground with the glass on the elements, neutral user messages, themed scrollbars and a softer shadow on messages (mockup version 6). The neutral ground is also applied to the application (T-NEUTRAL-GROUND: `--patch-1` to `--patch-3` and `--ambient` in `frontend/src/style.css`; 154 Vitest, build and browser smoke pass), not committed and not deployed. **Uncommitted, added to Codex's:** `mockups/chat-first/`, `frontend/src/style.css`, and lines in DECISIONS.md, TODO.md and this file. Codex's server on port 8776 still serves its own mockup.

## Claude's track — handoff of 2026-11-14 (session of 2026-11-13 and 14)

**Work order:** none (no ClickUp ticket; personal pilot for the shop Original Phone Mada). **Live:** https://affiches.miorantsoa.app. **Branch:** `main`, clean for this track: everything is committed and pushed; `origin/main` contains the last commit of this track, "T-TAP-FEEDBACK: every tap answers at once…" (check with `git fetch && git log --oneline origin/main -5`).

**Deploy state:** the user confirmed on 2026-11-14 that he deployed the last version of this track (the release with T-TAP-FEEDBACK). Claude did not read the box afterwards; to see it:

```sh
ssh deploy@89.167.56.26 'docker inspect affiche-ia --format "{{.Config.Image}} {{.State.Status}} {{.State.Health.Status}}"'
```

**Done in this session, all committed and pushed (details in TODO.md and ADR-074 to 087):**
- Phone-first editor (T-PF-STRUCT, T-PF-LOOK; D-POSTER-EDITOR-005): one-row top bar, the real poster sticky on top, tools row, versions strip, bottom navigation, Figtree, glass on every surface, theme follows the phone. Later amended by Codex's audit fixes and the user's decision (ADR-086): the sticky poster is about 163 px at 360 × 740, versions folded behind « Versions (n) », a 96 px strip while typing.
- Waiting experience during a generation (T-GEN-WAIT, D-POSTER-EDITOR-006) and the fix for the panel deforming during it (T-WAIT-DEFORM).
- Three formats (T-FMT-001 to 007; `poster-format.md`): Publication 4:5, Carré 1:1, Story 9:16, chosen in the Style step, fixed after the first version with « Refaire en … », enabled on the pilot (`FORMATS_ENABLED: feed,square,story` in `deploy/compose.yml`). Three paid scenes for USD 0.091 in `outputs/format-check-2026-11-14/`.
- The pilot's image model is gpt-image-2.5-flare at medium (T-FLARE-TRIAL, ADR-078; the user's "let's try 2.5 flare").
- T-BLANK-WORDS, T-KEEP-WORDS, T-RAIL-WIDTH, T-NAME (« Affiche Gen »), T-ACCENT-READABLE.
- Codex's editor refinements verified, completed and committed (T-EDITOR-REFINEMENTS-FIXES), then the image-build fix (T-IMAGE-BUILD-FIXTURE).
- Tap feedback, a spinner on the working control, a top progress line, and faster images (T-TAP-FEEDBACK, D-POSTER-EDITOR-007, ADR-087).

**Verified on Linux at the last commit:** backend 796 passed / 3 deselected; 154 Vitest; build; the frontend-only build the image does; the browser smoke; `editor_refinements_browser.py`.

```sh
cd backend && uv run pytest -q
cd frontend && corepack npm@10 test && corepack npm@10 run build
cd backend && uv run python ../frontend/tests/browser_smoke.py            # ports 8000 and 5173 free; about 3 min
cd backend && uv run python ../frontend/tests/editor_refinements_browser.py
```

**In progress:** nothing. **Exact resume point:** wait for the user's report from his phone after the deploy; there is no half-made edit. If he reports nothing, the first candidate is the fonts (below).

**Open, in the order Claude would take them (none started; each needs the user's word or report):**
1. The user's feedback on tap feedback and loading on his real phone. Never tested by touch on a real device: `:active` on iPhone, the spinner, the top line, the Android keyboard with the sticky strip, the blur's speed on a cheap phone.
2. First opening of a poster still takes about 13.6 s at 1.6 Mbps, almost all of it the poster fonts (about 2.3 MB, loaded by `frontend/src/fonts.ts` for the canvas). Not started. Idea only: load the fonts a poster uses first, the rest later.
3. A real Story posted on Facebook and on Instagram, to confirm the 13 % zones (`MARGINS` in `backend/src/affiche/posters/plans.py`); one good paid scene is the only evidence.
4. An edit made while the first scene is being generated ends in a save conflict (« Une autre version existe »). Older than this session, seen by the format builder, not fixed, no task yet.
5. Whether the image model leaves the reserved logo corner empty (Codex's corner logo): needs a paid scene, not approved.
6. T-HOST-004, the observed phone session, still blocked on the user. The USD 0.75 reservation of Codex's interrupted benchmark job `84996e31-34f8-4251-b0a0-1787c252c6ae` is still to check against the OpenAI invoice.

**Landmines:**
- The image's frontend stage sees only `frontend/`: a frontend test or source file must never import from `backend/` (the deploy of `df198bf` failed on that). Before saying "ready to deploy", build from a copy of the git-listed `frontend/` files alone.
- Images made by code (`?prepared=true`, `&display=true`, thumbnails) are cached immutable for a year under a version: bump `CANVAS_IMAGE_VERSION` (`posters/rendering.py`), `DISPLAY_VERSION` or `THUMBNAIL_VERSION` (`api.py`) and the matching constants in `frontend/src/api.ts` whenever an encoding changes; a backend test compares them. Display copies live in `data/display/v1/` and are not backed up (they are rebuilt).
- Never `backdrop-filter`, `filter`, `transform` or `will-change` on an ancestor of a `position: fixed` element; the press rule is scoped to leaf controls for that reason. The smoke refuses a blur inside a blurred surface and anything sticking out of the editor panel (`RAIL_FITS_JS`).
- Figtree has no U+202F: that character comes from Noto Sans through a `unicode-range` face; keep both.
- The feed and square prompts and plans are pinned byte for byte by a golden test (`backend/tests/test_plans.py`): a prompt change must be gated on new scenes only.
- Free local demo and paid local run kill each other's ports (8000, 5173). Stop a server by the PID of its port, never with `pkill -f <script name>` (it matched the calling shell twice in this session).
- Paid calls, servers, push and deploy stay the user's word each time; the autonomy grant (ADR-064, ADR-077) covers requirements, design and local commits only.

```sh
# free local demo (simulated images, no spend); password in outputs/demo-password.txt
cd backend && uv run python ../outputs/serve_demo.py ../outputs/demo-password.txt
# the user's deploy, from his own checkout: see deploy/README.md
```

**Uncommitted files at this handoff:** none of this track. Codex's: `docs/project/DECISIONS.md` (ADR-088 to 090), `HANDOFF.md`, `TODO.md` (T-TEXT-FIRST-*), `requirements/_INDEX.md`, new `requirements/text-first-generation.md`, `reviews/text-first-generation-research-2026-11-14.md`, `mockups/`. This handoff also edits `HANDOFF.md` and one line of `TODO.md` (T-EDITOR-STEPS closed), left uncommitted with them.

## Codex's track and older history (Codex's text-first notes first, newest first; then its audit and editor refinements, already committed; then the hosted pilot of 2026-11-13)

**Latest mockup refinement, 2026-11-14 (Codex; T-TEXT-FIRST-POLISH-MOCKUP, ADR-090).** User wants chat kept available for polish and account credits deferred, with default behavior retained. Added persistent follow-up composer and conversation history to the isolated mockup. Revision confirmation/cancel, previous-image visibility while generating, version indicator, preserved next-message draft and reset review are simulated. On mobile the chat follows the poster. Draft requirements now record persistent polish chat and unchanged cost confirmation, spend limits and metering; no credits UI or billing implementation.

**Verified / next:** real Orca browser assertions passed: confirmation before revision, cancel restores text, duplicate confirmation produces one revision, next draft/history survives completion, review required again, 320 px no overflow and composer follows preview. Desktop capture in outputs/text-first-mockup/polish-desktop.png. Browser left on desktop result/chat; same preview http://127.0.0.1:8776. Next user feedback, then full requirements approval/design gate. No real image edits, production changes, paid calls or API work; no phone keyboard/screen-reader test. This refinement changed mockup index/README, Draft requirements, TODO, DECISIONS and HANDOFF; prior uncommitted inventory still applies.

**Preview recovery, 2026-11-14 (Codex).** User reported the mockup server stopped. Restarted the same loopback-only static preview as detached process 2386136; verified HTTP 200 for `/`, the font and product image in a separate subsequent call. URL remains http://127.0.0.1:8776/. PID/log: ignored outputs/text-first-mockup/server.pid and server.log. This replaces exec-session 7846 below; mockup content and production unchanged. Next: user reviews the mockup. Uncommitted inventory below remains applicable; this recovery only adds TODO/HANDOFF notes.

**Latest mockup, 2026-11-14 (Codex; T-TEXT-FIRST-MOCKUP, ADR-089).** User says Claude finished and deployed the latest changes, then requested a mockup before continuing research. Main is `89e03d8`; tap feedback is now complete in TODO. Delivered isolated [clickable concept](mockups/text-first/index.html) and [usage/verification notes](mockups/text-first/README.md). Local preview: http://127.0.0.1:8776, served by `python3 -m http.server 8776 --bind 127.0.0.1 --directory docs/project/mockups/text-first` (exec session 7846). Opened in Orca browser page `168e47eb-f969-4a39-bc69-a78ad19e2225`, left at the desktop composer.

**Verified:** real browser compose/confirm/timed simulation/result, sample-attachment priority, required review checks, missing/invalid price and colour ambiguity. Checked light/dark appearance and no horizontal overflow at 320/390 px and desktop; fixed attachment/min-content overflow at 320 px. Stable viewport screenshots: ignored outputs/text-first-mockup/desktop.png, mobile-confirm.png, desktop-dark.png. One exact heading wait timed out on a line break, followed by direct successful result-state verification; mobile full-screenshot stitching was unsuitable and not retained as evidence. No full regression suite for an isolated static concept.

**Exact next step:** user tries the mockup and gives feedback; then update/approve Draft R-TEXT-FIRST requirements and write/approve technical design before implementation tasks. Mockup request authorizes this concept exploration, not feature implementation. Reference roles/inspiration support remain proposed. New source/model evaluation still needs a separate budget before paid calls.

**Limits/landmines:** no real lookup/generation, no new API or deployment. Fixed WH-1000XM6 historical example, independent of input/style; sample price overlay is layout-only and explicitly labelled. Production price remains baked. No physical keyboard/phone, screen-reader speech or OS file picker test; reduced-motion CSS present but not emulated. Never read backend/.env. Local preview only; production deployment reported by user, not reverified.

**Uncommitted files:** docs/project/DECISIONS.md, HANDOFF.md, TODO.md, requirements/_INDEX.md; new requirements/text-first-generation.md, reviews/text-first-generation-research-2026-11-14.md, and mockups/text-first/ (index.html, README.md, six local asset files plus font licence). No production source modifications. Older statements below that tap-feedback is in progress are superseded.

**Research continuation, 2026-11-14 (Codex; T-TEXT-FIRST-GAPS).** User authorized further search into unhandled image-generation behavior. Extended the [research report](reviews/text-first-generation-research-2026-11-14.md#follow-up-generation-gaps-2026-11-14) with a source-backed capability audit. Main gaps: mixed attachment roles, explicit campaign/wordmark treatment (style references currently ignore logos/text), automatic raster-text checking, routing chat edits between scene/text/offer changes, and streamed previews. Official docs describe 2.6 models and complexity controls, but the app's allowlist/request path does not support them yet. No model change or paid calls.

**Next action / limits:** review Draft requirements and decide whether inspiration attachments/campaign lettering enter the first slice before design. Free simulation first; later model comparison only with explicit budget. Recommendations remain research, not approval or implementation tasks. Verified source/doc comparisons and whitespace only; no new outputs, browser flow or runtime performance measurements. No new non-obvious implementation decision. Uncommitted file inventory below remains applicable; this continuation changed only the report, TODO and HANDOFF. Separate T-TAP-FEEDBACK remains in progress with its existing note.

**Latest research, 2026-11-14 (Codex; T-TEXT-FIRST-RESEARCH, ADR-088).** User requested a search session for generation from a product name/brand, price and predefined style. Confirmed: start with an in-app text composer; allow optional product-photo attachments; automatically find/reuse references only when none are attached. Price remains in the generated image. Delivered [research](reviews/text-first-generation-research-2026-11-14.md) and [Draft requirements](requirements/text-first-generation.md), indexed. No product code, paid generation, subscription, commit or deployment by this session.

**Current state / exact next step:** research complete; obtain approval of R-TEXT-FIRST-001…004 before writing the matching design, then approve design and add implementation tasks. Recommended first implementation is a free local simulation. Provider selection must account for retention and image-use permissions; no search vendor has been selected. A later paid comparison needs explicit authorization. Other channels remain deferred. T-TAP-FEEDBACK is still in progress in another agent's work; preserve its changes and status.

**Verified / limits:** inspected current intake, provider dispatch, style and price paths; checked official OpenAI reference-generation docs, Sony's ULT WEAR product/variant page, and Brave image-search pricing/retention docs. Checked local links and whitespace for this session's documents. No provider integration, downloads, image licensing clearance, new UI/browser test or test-suite run: documentation only. Main is now `79cf6e4`, including Claude's `df198bf` refinements and fixture-build fix. Older handoff statements below saying these fixes are uncommitted are historical; deployment state was not reverified here.

**Landmines:** the screenshot includes reference images; do not claim it proves reference-free accuracy. An attached product photo outranks a search result. Missing/ambiguous variant must not be guessed; external prices must not override the user's price. Existing scene calls require original references and final review. Brave's standard plan does not authorize retained API results, so USD 0.005/search is not a quote for a cacheable reference service. Keep remote retrieval bounded and protected from internal-network access. Do not read backend/.env or overwrite the concurrent UI work.

**Uncommitted files at research handoff:** this session added `docs/project/requirements/text-first-generation.md`, `docs/project/reviews/text-first-generation-research-2026-11-14.md`, and changed `docs/project/HANDOFF.md`, `docs/project/requirements/_INDEX.md`, with additive entries in the already-dirty `docs/project/DECISIONS.md` and `docs/project/TODO.md`. Pre-existing concurrent modifications remain: `backend/src/affiche/api.py`, `backend/tests/test_api.py`, `backend/tests/test_exports.py`, `docs/project/designs/poster-editor.md`, `docs/project/requirements/poster-editor.md`, `frontend/src/App.vue`, `frontend/src/PosterCanvas.vue`, `frontend/src/api.ts`, `frontend/src/main.ts`, `frontend/src/style.css`, `frontend/tests/api.test.ts`, `frontend/tests/browser_smoke.py`.

Prior handoffs follow; the current research status above supersedes their next-action statements for this session.

**Latest implementation, 2026-11-14 (Codex; T-EDITOR-REFINEMENTS-001…003, ADR-085/086).** User authorized autonomous fixes after the deployed audit. Implemented brand/title deduplication for new scenes with legacy-compatible refinement behavior; local photo palette with visible override/retry and async race protection; boutique identity off on every new form/profile load; explicit missing-detail import; original boutique logo top-left/top-right reserved above the title; historical footer/seal restoration and pre-export/pre-refinement guards; compact/collapsible mobile preview, sticky tools, accessible numbered versions, short-viewport fullscreen preview and focused-field visibility; truthful drawn-text/reservation copy. Price remains in the generated composition. Existing posters/confirmed PNGs are preserved. No new dependencies or migrations.

**Current state:** T-EDITOR-REFINEMENTS-001…003 complete, verified and independently reviewed; no implementation task remains in progress. Requirements/design gates passed independent reviews under the autonomy grant. Code r1's four findings fixed; r2 APPROVE WITH NITS, both nits fixed. See [verification report](reviews/editor-refinements-verification.md), [requirements](requirements/editor-refinements.md), [design](designs/editor-refinements.md), and code reviews r1/r2.

**Verified:** full backend 793 passed / 3 opt-in cutout tests deselected; extended all-format/both-corner original-logo rendering and compatibility checks 21 passed; frontend 150 passed; production build passed; focused production-build Chromium flow passed, including profile conflict without draft loss, delayed decoder/manual override, failure recovery, exact submitted neutral palette, corner/footer transitions and 360×282 keyboard-sized viewport with the focused field below sticky tabs. Browser smoke coverage completed in sections: the combined run completed the main flow, waiting/words/theme/redirect checks then terminated during formats; standalone waiting and complete format helpers passed. One isolated format attempt returned render_unavailable, not reproduced on the stable-build rerun. This is documented as section coverage, not a clean monolithic command pass. Final focused build check also covers explicit missing-disc compatibility. Artifacts: ignored `outputs/editor-refinements/` and `outputs/editor-smoke/`. API/browser tests explicitly use `_env_file=None`, temporary data, no keys and stub providers. No paid generation.

**Exact next step:** owner reviews the local changes and performs the commit/push/release under the existing release workflow; after release, verify these controls on the deployed app and physical phone. Work is uncommitted on local main based on `4e39373`; nothing was pushed/deployed and production does not yet contain these fixes. The user's Edge window was on another site when checked, so it was left alone; changed UI was exercised in real local Chromium.

**Landmines/limits:** `logo_box` means a strict corner reservation; `logo_footer_box` only restores historical footer geometry. Corner-logo export/refinement requires original scene framing. Legacy `brand_in_title` absence deliberately preserves prior prompt behavior. New product palette is an edge-background heuristic, not segmentation; ambiguous photos need visible manual correction. No new paid-image fidelity/collision test and no physical-phone keyboard/screen-reader-speech test; final composite review is still required. Do not read backend/.env. Codex transmission was initially rejected by automatic approval review, then explicitly approved by the user; independent reviews completed. No Postman CLI installed; existing HTTP/browser suites used.

**Uncommitted files for this session (including the preceding audit):**

- `backend/api/README.md`
- `backend/fixtures/brand-title-cases.json`
- `backend/src/affiche/api.py`
- `backend/src/affiche/posters/exports.py`
- `backend/src/affiche/posters/plans.py`
- `backend/src/affiche/posters/visuals.py`
- `backend/tests/test_editor_refinements.py`
- `docs/project/DECISIONS.md`
- `docs/project/HANDOFF.md`
- `docs/project/TODO.md`
- `docs/project/designs/_INDEX.md`
- `docs/project/requirements/_INDEX.md`
- `frontend/src/App.vue`
- `frontend/src/composition.ts`
- `frontend/src/document.ts`
- `frontend/src/palette.ts`
- `frontend/src/style.css`
- `frontend/src/viewport.ts`
- `frontend/tests/browser_smoke.py`
- `frontend/tests/composition.test.ts`
- `frontend/tests/editor_refinements_browser.py`
- `frontend/tests/viewport.test.ts`
- `docs/project/designs/editor-refinements.md`
- `docs/project/requirements/editor-refinements.md`
- `docs/project/reviews/editor-refinements-code-r1.md`
- `docs/project/reviews/editor-refinements-code-r2.md`
- `docs/project/reviews/editor-refinements-design-r1.md`
- `docs/project/reviews/editor-refinements-requirements-r1.md`
- `docs/project/reviews/editor-refinements-verification.md`
- `docs/project/reviews/ux-audit-2026-11-14.md`

Prior handoffs follow; their older next-action/deployment statements are historical.

**Latest audit, 2026-11-14 (Codex; T-UX-AUDIT-20261114, ADR-084).** User reported six deployed-editor issues and requested a browser audit. Completed [report](reviews/ux-audit-2026-11-14.md). Main was `4e39373`, clean before audit. Live signed-in Edge inspected Create, library, first QuietComfort's Textes/Style/Boutique and a generation confirmation; cancelled the confirmation and verified it closed. No paid call or intentional production document edit. The live dialog still estimates USD 0.40. User clarification: top-left/top-right is for the **boutique's uploaded logo**; price remains drawn.

**Audit verification:** deployed and local production frontend referenced identical JS/CSS assets. Existing smoke server reused with `_env_file=None`, no keys, stub providers and temporary data; Chromium desktop, 390/360/320 px touch, reduced layout space at 200%-equivalent width, dark/reduced-motion state. 34 settled screenshots/measurements, no JS errors or page overflow, measured text contrast and touch targets passed, dialog focus/Escape and tab arrow key worked. Confirmed mobile tabs below fold/covered by sticky preview; first selected thumbnail outline clipped by the scroll container. Source confirms duplicated quoted brand/title and product-colour style actually driven by remembered accent. Extra findings: editability promises, immutable missing shop details, unnumbered version controls, missing error associations and cost wording. Full limits in report, including no real phone or paid accuracy check. The tool's Edge display-session environment read was rejected by automatic approval review; not retried or bypassed.

**Exact next step after audit:** present findings to the owner, then carry selected fixes through matching requirements/design/tasks; do not silently implement the proposed mobile redesign. Recommended compact collapsible preview + visible tabs, truthful text/palette preparation, identity-off defaults, original-logo corner placement. No app source changed. Local audit servers were stopped; Edge was left on the existing poster with the paid dialog closed. Ignored artifacts: `outputs/ux-audit-2026-11-14/` (one-off walk.py, results.json, 34 PNGs, filtered live trees). The title-error screenshot's save conflict came from the audit's multiple contexts touching the same temporary fixture, not a newly established single-user defect; the brand-error artifact did not trigger an error. **Uncommitted audit files:** this HANDOFF, TODO.md, DECISIONS.md, reviews/ux-audit-2026-11-14.md. No commit/push/deploy. Prior historical handoff below is preserved; statements that the latest main is not deployed are superseded by today's frontend asset parity and the user's deployment report.

**Session date:** 2026-11-12 (Indian/Mauritius), still open when this was written
**Work order:** none (no ClickUp ticket; personal project for the shop Original Phone Mada).
**State:** nothing in progress. The contact is drawn in the composition again by default (ADR-055, design v3.1 approved in ADR-056); T-SIG-004 and 005 are built, tested and committed. T-SIG-006 is done: live run 8 drew the contact at the right with exact digits and no collision with the price, though beside the pill rather than below it and about 20 px high (details in TODO). "Mes affiches" now uses small resized thumbnails (T-UI-THUMBNAIL-SIZE). Everything up to here was committed with this handoff. Remote `origin` (private GitHub repository `MiorantsoaRak/poster-gen`, added 2026-11-13) tracks `main`; push only on the user's "push". No server is running. Next: ask the user to look at "Mes affiches" and a new poster on the real data, then T-UI-MOCKUP-GAPS, T-PLANNER-CLAUDE-INVALID, T-UI-PHONE-CHECK and T-POSTER-009; the numbered list below predates the drawn-contact work and its items 1 and 2 are done or replaced.

**Hosted pilot, 2026-11-13 (ADR-063, 064, 065) — read this first.** After an end-user audit the user said "go ahead" on Claude's order of work, then "if you have autonomy, you don't have to ask me for approval" (ADR-064: Claude passes the requirements, design and task gates itself, still with a fresh review and a devil's advocate; paid calls, servers, keys, commit and push stay the user's). Feature `hosted-pilot`: [requirements](requirements/hosted-pilot.md) approved, [design v2](designs/hosted-pilot.md) approved after [round 1](reviews/hosted-pilot-design-r1-2026-11-13.md). The devil's advocate changed the order: **the owner's first phone session comes before any server**, through a temporary tunnel to this machine (phase A); the server, backups and deployment (phase B) are designed in outline and start only after that session, with a fresh review.

Phase A is built and verified (T-HOST-001 to 003; backend 722 passed / 3 deselected, 26 Vitest, build, browser smoke): the password is verified outside the write transaction, IPv6 is limited by /64, forwarding headers are believed from loopback only (`UVICORN` in `api.py`), sessions last 90 days and end when the password hash changes, the budget message is in the owner's words, the editor shows a service-down message, the home-screen manifest and icons exist, the smoke measures text contrast in both themes, and `deploy/phone_session.py` runs the session.

**Server (ADR-066):** the pilot will go on the Hetzner box `mx1` (`deploy@89.167.56.26`), shared with Maizina, Trap Duel and PPN Market: 2 vCPU, 3.8 GB with about 1.6 GB available and no swap, Docker, Maizina's Caddy on 80/443, pyinfra deploys (see `../ppn-market/deploy/README.md`). The design's phase B is rewritten for it (outline v3, not reviewed). It is a production box of three other projects: Claude only looked (no sudo); anything that changes it, and the two Maizina changes, are the user's.

**Phase B is written too (ADR-068, ADR-069; T-HOST-005 to 008).** On the user's "next", the server part was detailed for `mx1`, reviewed ([round 2](reviews/hosted-pilot-design-r2-2026-11-13.md), APPROVE WITH FIXES, all applied) and built: container settings, the frontend served by the application, `python -m affiche.backup`, `GET /api/status`, `Dockerfile`, `deploy/compose.yml`, `deploy/deploy.py`, `daily.sh`, `verify.sh` and the runbook `deploy/README.md`. Backend 731 passed / 3 deselected, 26 Vitest, build, browser smoke. **The container files have never run:** Claude cannot reach Docker on the Linux machine, pyinfra is not installed, and nothing was changed on the box (Claude only read `nproc`, `free`, `df`, `docker ps`, the Docker and Caddy versions).

**Deployed on 2026-11-13.** `https://affiches.miorantsoa.app` runs on `mx1` since 15:24 UTC (revision `7f4fa6d` of the image inputs), behind Maizina's Caddy; the user signed in from Edge. Claude read the result on the box: healthy, no restart, no published port, 222 MiB of 1 GiB, Chromium starts in the container, first backup taken, neighbours at 200, forged forwarding header refused by the sign-in limit. The pilot's ledger starts empty with a cap of USD 15 since 2026-11-13, on the pilot's own keys; it is separate from the development ledger below.

**First finding on the live pilot (T-PILOT-SMALL-PHOTO; fixed and deployed in the second release, 2026-11-13 15:53 UTC, revision `18fb91e`, with T-UX-HIDDEN-RULES):** the user's first poster used a 474 px photo and "Générer l’affiche" failed with a vague message; the agreement for a small photo was hidden in a closed section, and the contact he had just typed was not on the poster. Fixed and covered by the smoke. The second release kept the data (one poster, profile, sessions) and took a backup before and after. The pilot's ledger read USD 0.82 after it (about four scenes by the user), of a cap of 15.

**Later the same day (ADR-075, ADR-076).** The user called the mockup "promising" and asked that the price pill and the badge always be in the foreground. Done locally: T-FOREGROUND (draw order in the shared canvas and two foreground sentences in the scene prompt; renderer test proven to fail without the rule) and T-THEME-COLOR. The phone-first design went through a devil's advocate and a fresh review and is now v2 (D-POSTER-EDITOR-005): structure reduced and approved, the look waiting for his choices. **Exact next step:** his answers on the release order (recommended: commit, push, deploy the current work first), the default theme, Figtree and the bottom navigation; then T-HOST-004, T-PF-STRUCT, T-PF-LOOK. Uncommitted: everything since `bc3d79c` (see `git status`); `bc3d79c` itself is not pushed.

**Second UI/UX round (Opus), 2026-11-13 (T-UI-REVIEW-2, ADR-074).** Eight fixes made locally and tested (prices as owners write them, sticky hover, decisions fixed at the bottom on phones, « Mes affiches » at 360 px, French file buttons, vendor names); not committed, not deployed. The structural proposal is a mockup only: https://claude.ai/artifact/6JoS82gMXkucaat4FKvUia (8 phone screens light, 2 dark, 1 laptop). **Exact next step:** the user's choices on the mockup (T-UI-PHONE-FIRST), then requirements, design and tasks; on his word, commit and release the eight fixes. Review: [reviews/ux-review-opus-2026-11-13.md](reviews/ux-review-opus-2026-11-13.md).

**In progress, local only (T-EDITOR-STEPS, ADR-072): the editor in steps then tabs, « Retirer de l’affiche », glass on floating chrome.** Built by a subagent, reviewed by a fresh one, fixes applied; build, Vitest and smoke pass. Committed on the user's "commit first" (2026-11-13), not pushed and not deployed: he asked to test locally first. Another session (Codex) was auditing the image generation at that time: fetch and read `git status` before editing. Free demo: from `backend/`, `uv run python ../outputs/serve_demo.py ../outputs/demo-password.txt` (simulated images; `outputs/` is not in git). Requirements R-POSTER-EDITOR-004 to 006, design D-POSTER-EDITOR-004, reviews/ux-review-2026-11-13.md. The three open choices are settled (ADR-073). Exact next step: his look at the demo, then on his word commit, push and a release.

**Audit of hidden rules (T-UX-HIDDEN-RULES, deployed with the second release):** the user said the hidden box was "the UX error I was expecting to be audited". A scripted audit then found 39 refusals without a French sentence and hidden rules on the drawn title (60 characters, no straight quote, no price or promotion word). All fixed and tested; see TODO. Lesson, also saved in Claude's memory: audit failure paths mechanically (every refusal code against the message table, every collapsed section, hidden field rules) and on empty data; a smoke that ticks boxes for the user hides this kind of bug.

**Exact next steps (T-HOST-009, runbook `deploy/README.md`):**
1. In the application: shop name, contact, logo; make the saved styles again (step 4).
2. First real poster on the box with memory watched (step 5): `ssh deploy@89.167.56.26 'while true; do date +%T; free -m | sed -n 2p; sleep 5; done'`. It is the first paid call of the pilot (about USD 0.21).
3. Decide the off-box backup (Hetzner's option for `mx1`, or a pull). Until then every backup is on the box only.
4. Restore proof (step 8), then the owner's phone (step 9, record in a copy of [reviews/phone-session-TEMPLATE.md](reviews/phone-session-TEMPLATE.md); the tunnel script is no longer needed for it).
5. Then the four later audit items (T-REQ-AFTER-PILOT).

Maizina (ADR-070): its change is committed, pushed and deployed (the user deployed it; Caddy serves the four sites). Maizina's own T-086 still reads "not pushed, not deployed" and is to be closed there.

**Spend seen on 2026-11-13:** the ledger of `backend/data-probe` on this Linux machine reads **4.781245**, up from 4.362064: two scenes on one existing poster at 12:16 and 12:19 UTC, made through the application while the local server was up for the user to look. The user confirmed on 2026-11-13 that he generated them; Claude made no paid call. Real total ≈ 10.06. **Budget raised by the user on 2026-11-13 from USD 12 to USD 100 (ADR-067): remaining ≈ 89.94.** `SPEND_CAP_USD` is 100 in `backend/.env` on the Linux machine (changed by one blind line replacement, read back through `load_settings`); the Windows machine's file still says 12. `serve_local.py` and `deploy/phone_session.py` cap the ledger at 94.72, because the application does not see the 5.28 that the study scripts spent outside it. Each paid call by Claude still needs the user's go.

A local server on the real data may be running on ports 8000 and 5173 (started for the user to look; its password is rewritten at each start in `outputs/style-study-2026-11-11/local-password.txt`).

**Linux machine, 2026-11-13 (T-ENV-LINUX):** a fresh clone at `/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia` now runs every free check: backend 716 passed / 3 deselected, 26 Vitest, build, browser smoke (bundled Chromium 156). From `frontend/` use `corepack npm@10 ci|test|run build` (the system Node has no npm; the `npm.cmd`, `msedge` and `taskkill` commands below are for Windows). The Git-ignored `backend/data-probe`, `outputs/` and `backend/.env` were copied here by the user on 2026-11-13; the database was read (read-only): integrity ok, migration 0011, ledger **4.362064**, the same as on Windows. There are now two copies of the paid data: paid calls made on one machine are not in the other's ledger, so keep one machine as the place for paid work (not yet decided with the user) and never start another paid data directory. `serve_local.py` runs unchanged on Linux. T-SCENE-INVENTED-TEXT is closed. T-UI-MOCKUP-GAPS is done (ADR-062): the accent word is chips made from the title's words, the accent colour is five swatches plus "Autre…", the paid confirmation stays a dialog; the user has not yet seen them. Committed and pushed with the rest of 2026-11-13. Next: see the hosted-pilot paragraph above; T-PLANNER-CLAUDE-INVALID and T-POSTER-009 stay queued. To stop `serve_local.py` on Linux, kill the Python process and then the `vite preview` child if it still holds port 5173 (`ss -ltnp | grep 5173`).

**Logo seal (ADR-057, ADR-058), built on 2026-11-12:** the scene is asked for an empty white disc, the program finds it (`backend/src/affiche/posters/seal.py`) and the real logo file is printed on it as a round seal at 130 px. The shop's real logo is now saved in the `data-probe` profile. Two paid scenes are left pending review in `data-probe` (one of them with its logo unticked by the first, too strict, size rule). The user has seen the composed left-aligned result and has not yet seen or judged the centred dark one. Open: confirm with him the two rule changes of ADR-058, and whether the seal's place with a centred price suits him.

**Guideline review fixes (T-UI-WEB-GUIDELINES, ADR-059), 2026-11-12:** the view is in the address hash, the three panels are real dialogs with the page behind inert, every paid or destructive tap asks first, the price error sits beside its field. Build, 26 Vitest and the browser smoke pass; a screen reader and a real phone were not tried.

**UX audit fixes (T-UI-UX-AUDIT), 2026-11-12:** main button fixed at the bottom on one-column widths, stale notices under their fields, title and price locked while a scene draws them, focus rules, phone sizes. A second pass changed the wording of the main flow ("Préparer mon affiche", "Générer l’affiche", "version"; Claude's proposal, the user said to fix the rest) and added price and date to "Mes affiches" (`backend/src/affiche/api.py` and `backend/tests/test_api.py` are also modified). Managing styles and posters (rename, delete, duplicate, status, more than 50 posters) needs requirements first; see the TODO entry.

**Managing posters and styles (T-LIB-001 to 004), built on 2026-11-12, committed on the user's "commit" of 2026-11-13:** requirements R-CREATION-LIBRARY-003/004 approved (ADR-060), design approved at v2.1 (ADR-061), all four tasks done. "Mes affiches": state in words, "Dupliquer", "Retirer de la liste" (the existing `abandoned` status), a removed view with "Remettre dans la liste", "Voir plus". "Styles": a panel per style, rename, removal (soft, `looks.removed_at`), and a poster keeps a removed style for its new versions. Verified: backend 716 passed / 3 deselected, 26 Vitest, build, browser smoke. Migration 0011 was applied to the paid database `backend/data-probe` on 2026-11-13 after the copy `backend/data-probe/backups/before-looks-removed-2026-11-13.db` (row counts unchanged; the database is in WAL mode, so a copy must go through the SQLite backup call, not a file copy of `affiche.db` alone). Not seen in a browser: a poster reopened with a removed style; "Voir plus". Uncommitted: only this file and TODO.md (the note about the applied migration).

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
uv run pytest -q                                   # last full run: 716 passed, 3 deselected (212 s)
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

- (Budget since 2026-11-13: **USD 100**, ADR-067; the lines below are the history under the earlier cap of 12.)
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

Everything up to and including 2026-11-13 (mockup gaps, Linux setup, hosted pilot phases A and B) is committed and pushed. Nothing is expected to be uncommitted; check `git status`, and `git status -sb` for commits not yet pushed.
