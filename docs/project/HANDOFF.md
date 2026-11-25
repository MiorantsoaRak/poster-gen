# HANDOFF

## Création libre · built by Codex, reviewed and rebuilt on the chat's shell by Claude, 2026-11-25 · current track (READ FIRST)

**State in one line:** « Libre » is on `origin/main` (pushed 2026-11-25 on the owner's « push ») and on the live site (seen there: the owner's own test address is a `#libre-…` of https://affiches.miorantsoa.app); his test found that **the product degrades through the corrections**; the fix (T-FREE-006, D-FREE-06) is built and **uncommitted**, its final checks were running when this was written.

**The fix in short.** Each correction used to redraw the picture from the previous version only, and the loss added up (nine corrections: grain on the product). Now a correction edits the image model's own file of the previous version, and from the second correction on the first version's file goes with it as a reference for rendering quality. Chosen on a paid trial of his nine requests run three ways (27 Flare images, USD 0.7468, `outputs/degradation-trial/`, table in [the research note](reviews/free-poster-research-2026-11-24.md#correction-chain--2026-11-25)). Files: `backend/src/affiche/posters/free_creation.py` (`FreeDocument.source` and `first`, `prompt(..., anchor)`, `enqueue`, `finish`, `stored`), `backend/src/affiche/posters/service.py` (`prepare`: the base, then the reference last), `backend/tests/test_free_creation.py`. No migration; a creation made before the fix takes its first published PNG as the reference.

**What it is.** A third way of creating a new poster, « Libre », beside « Message » and « Pas à pas »: the seller's own words go to the image model as they are, with up to three photos and one style model, and the model draws everything, texts and prices included. One credit per image; a later message corrects the last image. The Publication PNG is confirmed, downloaded, kept in « Mes affiches » and published like any poster. Requirements: [requirements/free-creation.md](requirements/free-creation.md). Design and wire shapes: [designs/free-creation.md](designs/free-creation.md) (D-FREE-01 to 03 as Codex built them; **D-FREE-05 replaces the browser part of D-FREE-04**).

**How it came to this.** Codex delivered it on the owner's word the same day (T-FREE-002 to 004): server, a page of its own, three real Flare images (USD 0.145511; `outputs/free-creation/`, the three-card reference followed, three prices under the right products, a correction of one price). The owner then asked Claude to review it « and the UI it produces to make sure it doesn't diverge ». Found: the server is sound (every guided route was tried on a free creation: none fails, the ones that would alter it answer `free_creation_only`); the page was a form, not the product's chat, with its own names for things the product already names; a failed image said « code : refused … donnez ce code à l'administrateur ». On his « go ahead » (T-FREE-005):
- `frontend/src/FreeCreation.vue` is rewritten on the chat's classes (`style.css` `.chat`; `ChatView.vue` is untouched and has no free mode): thread, pinned composer with one picker, the version panel and « Modifications », the chat's waiting line, one review panel with the seller's requests in his words and the product's buttons.
- `frontend/src/App.vue`: a segment « Libre » in « Façon de créer » on a new poster (`WAYS`), remembered under `affiche.start` (`freeFirst`, `rememberStart`), `talking` gives the page the chat's shell (title in the top bar, no phone bar). The side-menu item and the two « Ouvrir Création libre » links are gone.
- `backend/src/affiche/posters/free_creation.py`: a turn carries `credit` as a job does (the page says a failure with `generation.ts` `ended`); a correction no longer sends the reference again (`prompt`, `enqueue`).
- `frontend/src/style.css`: at 400 px and less, the three-way switch takes the place of « + » and of the mark in the top bar (two ways already filled it at 360 px).

**Verified on the final build (stub providers, no spend):** backend suite `2137 passed, 3 deselected`; Vitest 420; `free_creation_browser.py` (1366 px light, 390 px dark, and a refused image), `chat_browser.py`, `terms_browser.py` passed. `browser_smoke.py` passed too, run alone on the owner's « run it » (its first run had failed at its 360 px bottom-bar check, on the overflow fixed since: the page measures 360 px on `#creer`, `#libre`, `#etapes`). `editor_refinements_browser.py` passed on the build just before that fix (CSS only since). No paid image was made for the rebuild: the prompt of a first image is unchanged; the prompt of a correction lost its reference, untried on Flare.

**Exact resume point.**
1. Read the end of the two logs below; if the suite and the smoke passed, set T-FREE-006 to `[x]` in TODO, then the owner's « commit », « push » and release (no migration). If one failed, the fix's only files are the three named above.

```bash
tail -2 /tmp/claude-1001/-home-miorantsoa-Documents-Miorantsoa-Vite-affiche-ia/80da9bf7-858d-46c2-9af1-961d2cf1b776/scratchpad/checks/pytest2.log
# if that folder is gone, from backend/: uv run pytest -q   (about 10 min, alone)
# then: SMOKE_WEB_PORT=5591 SMOKE_API_PORT=8591 uv run python ../frontend/tests/free_creation_browser.py
```

   After the release, his own conversation is the proof to look at: one more correction on `#libre-52ccfc6f-c6ed-44e3-8a7a-e448825d5df7` should come back with clean headphones (its version 1 is the reference). Not settled by the trial: a correction of something version 1 shows (« Name with bolder font ») was followed in part only; if he reports a correction ignored, the place is the reference's sentence in `prompt` (`free_creation.py`).
2. On his word only, one Flare image: a poster made with a style model, then a correction, to see that the layout holds without the reference sent again. If it does not, restore the reference on a correction in `free_creation.py` (`prompt`: drop `and not editing`; `enqueue`: `style_reference_asset: document.reference`) and its test line in `backend/tests/test_free_creation.py`.

**His to decide (recorded in DECISIONS, 2026-11-25):** the seller's words reach the image model with no screen (an instruction hidden in them, or « -50 % », is sent as written); no automatic reading checks the drawn amounts, the review lists his requests and he reads the image; sharing to another application is not on this page; images are taken with the first request only; the kit (saved models, logo, contact, lines) is not used here.

**What the code does not say.** The free document is `kind: "free"` in the same version table, with `offer: {title, price_ar: null}` only so that the lists, the credit history and the Facebook candidates keep reading a title. « Création libre » stays the name of the kind in « Mes affiches » and in « Vos données »; « Libre » is the name of the way, in the switch. A failed first image leaves a « Brouillon » in « Mes affiches », as a guided draft does; « Réessayer » in its thread asks the same words again.

**Commands.**

```bash
# from frontend/
corepack npm@10 run build && corepack npm@10 test
# from backend/ (build first; the smoke serves frontend/dist)
uv run pytest tests/test_free_creation.py tests/test_two_shops.py -q
SMOKE_WEB_PORT=5591 SMOKE_API_PORT=8591 uv run python ../frontend/tests/free_creation_browser.py
```

**Uncommitted, this track's (T-FREE-006):** `backend/src/affiche/posters/free_creation.py`, `backend/src/affiche/posters/service.py`, `backend/tests/test_free_creation.py`, `docs/project/{DECISIONS,HANDOFF,TODO}.md`, `docs/project/designs/free-creation.md`, `docs/project/reviews/free-poster-research-2026-11-24.md`. Untracked and not this track's: `.impeccable/`. Everything else is on `origin/main`.

**Concurrent tracks share this checkout.** Claude owns the chat audit and implementation documented below. Codex completed publishing/SaaS research in this session and retains the older text-first mockup track. Changes from other tracks must be preserved; check `git status` before you assume the working tree is clean.

## The seller's kit: built, walked three times, committed and pushed (2026-11-25) · Claude, 2026-11-25

**Since this section was written:** its two commits were pushed with « Libre »; the lines below that say « not pushed » are of before.

**State in one line:** everything of this track is committed on `main`; `origin/main` holds the kit (`T-KIT-001` to `017`, `020`), T-KIT-021 (a model's layout) and the research note T-FREE-001; **two commits are on `main` and not pushed**: T-KIT-018 (the walk's remaining findings, first trials on Flare) and T-KIT-022 to 024 (the logo drawn by the image model); nothing is deployed (the live site is still build `05a12ee`, which is why the owner's trials on it show none of this). The working tree is clean but for the untracked `.impeccable/` (a local tool's files, not this track's). The next move is the owner's: « push », then a release.

**What happened.** After [the first walk](reviews/user-walk-2026-11-23.md) the owner asked to think the platform as a kit the seller reuses, free words still allowed, then gave the go: « Proceed in the order you see fit; paid call still allowed; you can continue till there is a testable app. When in doubt, take the place of the user … When everything is fixed, do a live test as an user again ». Built under that word: requirements `requirements/seller-kit.md` (R-KIT-001 to 013), design `designs/seller-kit.md` v3 (review r1, one devil's advocate; its « Contracts as built » is the reference for every wire shape), ADR-131 and three dated entries of 2026-11-24 in DECISIONS, tasks T-KIT-001 to 017 and T-KIT-020 done, [the second walk](reviews/user-walk-2-2026-11-24.md) with real providers.

**What a seller gets now:** prices as he writes them (« 250000 », « 185k »); the scene he describes in his first message; his own lines (warranty, delivery, payment) kept once and drawn on each poster; a photo marked « Modèle de style » read into a saved model; « Mon kit » (models, title by default, lines); « Garder cette scène comme modèle »; a recap that names what will be used and what will not; « Confirmée » as soon as the file is confirmed; « Publier » with the result first and the connection on the page; « Pas à pas » without colour codes, with « Réglages avancés » closed; a guard for a request that is no advert. Migration 0021 (`shop_profile.lines_json`), no new table, no new route.

**The owner's own trial, after the walk (T-KIT-020).** On the pack of three he wrote « Aura studio on the center » and got a version with nothing moved (« The chat seems not aware »). Cause: a correction reached the image model only inside the data block the prompt calls « not additional instructions », against « preserve its composition ». Fixed in `compile_scene` (`backend/src/affiche/posters/plans.py`): a correction is an instruction that may move, swap, resize or replace what the base shows; the owner's words lead the scene on a correction too; a brand or model name in his words is read as one of the products. One paid image on the same poster proved it (`outputs/user-walk-2/05-pack-aura-centre-after-fix.png`, git-ignored). **His decision then:** « For that case, we let the image model decide, so we don't block any user prompt »: no name per photo of a pack, no question from the chat. I read « that case » as names the app does not know; the screens on price, discount and warranty words and the advert guard are unchanged. He did not answer whether he meant those too.

**After the handoff, the same day: a reference poster with a layout (T-KIT-021).** On the deployed build the owner gave a reference of three cards, one product in each: « it copied only the color ». Now a first image made with a saved model sends the model's own poster to the image model (`request_scene`, `backend/src/affiche/posters/visuals.py`) and the prompt asks for its composition; the describer writes the layout too; past three product photos the next attached image is the style model (before, a pack of three took none); the composer takes a pasted or dropped image; « Vos données » says where the model's poster goes. Proof: with his reference and three products, words alone built no card, the poster sent built the three cards (`outputs/user-walk-2/06-…` and `07-…`). This replaces D-KIT-006's « never the raw image » (DECISIONS, 2026-11-24). The page is not told of that image (the job's payload marks it `style_reference_from_look`), so a correction does not send it again. Checks after it: whole backend suite `2133 passed, 3 deselected` (run before the last small change to `visuals.py` and `reads.py`; the five test files they touch then passed, 610), Vitest 420, `chat_browser.py`, `browser_smoke.py` and `terms_browser.py` passed. Three paid images this afternoon, about 0.65 USD. Not judged: a model kept from a finished poster now sends that poster, product and words included; the prompt says to ignore them, no real image has shown it.

**Research only, same day (T-FREE-001):** the owner asked how to handle a poster of several products, each with its name and price, with free text: « one more general purpose and less barrier », the product chat and « Pas à pas » kept. Answer, code map and proposal (« Affiche libre »: a second kind of poster in the same chat, the guard moved from what the seller writes to what the image shows) are in [reviews/free-poster-research-2026-11-24.md](reviews/free-poster-research-2026-11-24.md). No code. Found on the way: **every paid proof of this track (both walks, T-KIT-020, T-KIT-021) was made on `gpt-image-2` at high, the local default; the deployed build runs `gpt-image-2.5-flare` at medium (`deploy/compose.yml`, ADR-078).** None of the prompt fixes is shown on the production model yet. Asked about the model, the owner answered « no need to change, keep it at the current version »: then « For your next test, set the model to 2-5 flare, it is faster »: the local instance now runs `gpt-image-2.5-flare` at medium, as the deployed build does, and every next paid test uses it. No rerun was done yet. The new kind of poster is for later (« we will handle the new kind of affiches later, just note it »).

**Evening, on the owner's « continue on the finding this morning » (T-KIT-018):** the walk's remaining findings are fixed (the list is in TODO: « Publier à nouveau… », the Page choice in view, larger shop lines, a kept scene said in the panel, a send asked during an upload, the faded model strip, the review's notes N1 and N2, the logo and contact on a retry recap). **First trials on the deployed model, `gpt-image-2.5-flare` at medium** (5 images, 0.31 USD, about 22 s and 0.06 USD each with three photos and a model): the model's layout was followed in 2 of 3 first images; **a correction came back identical to its base with the morning's wording**, and worked once `compile_scene` put the request first (« Task: edit image 1. The owner asks for this change, in his own words: "…" »). Review note N3 is done another way (a recap made before the first version is retired at the tap once the poster has one). **Measured, not built:** whether a correction that came back unchanged can be told from its pixels: no (mean difference on Flare 4.5 for the unchanged pair, 11.6 for a real swap of two products, 22 to 39 on `gpt-image-2`; a small real correction would fall under any safe threshold). Telling the seller needs a reading of the image by a model: his decision (cost, and who pays the redo). Not done: the name lost in « Pas à pas » right after a photo (no cause found in code). The local instance's launcher now sets Flare at medium. Checks on the final code: backend suite `2133 passed, 3 deselected`, Vitest 420, `browser_smoke.py`, `publish_browser.py` and `chat_browser.py` passed. `chat_browser.py` stopped 2 runs in 7 waiting for « Envoyer »: the kept send let the next message be typed and left in the middle of it. Fixed (the field is held until the send leaves), a smoke step now pins it, and `chat_browser.py` then passed three runs in a row. A sixth Flare image judged one title style (« Gras condensé »: followed; 0.03 USD with one photo); the test shop `essaikit` then reached its daily limit of images (2 USD of provider spend a day). On the owner's word (« Add credit for the test ») it got 20 offered credits with `affiche.shops grant` on `data-walk`, and the local launcher sets `SHOP_DAILY_SPEND_USD='5.00'` (this test instance only; the handoff's copy of the launcher below does not carry it). « Italique sport » and « Élégant » were then drawn: the three title styles are followed on Flare and plainly different (`outputs/user-walk-2/16-flare-title-styles-side-by-side.png`). Eight Flare images in all, 0.40 USD.

**Night, on the owner's « Let's continu », then « go » (T-KIT-022 to T-KIT-024, committed 2026-11-25 on his « commit », not pushed):** a third pass on Flare over what the walk had not tried (table in [the walk report](reviews/user-walk-2-2026-11-24.md)). Fixed: the three-lines refusal has its button to « Mon compte »; the recap's logo-and-contact line read the form's ticks and was wrong once the poster existed (a fault of T-KIT-018, never pushed). Found: **the shop's logo, laid over the image, covered the end of a long title** (the model draws the title higher and wider than its area; two prompt wordings to move it failed on paid images). The owner's fix, built: **with a drawn title, the plain logo is given to the image model and drawn in the picture**, in Message and, on his word (« it should draw too », T-KIT-024), in « Pas à pas », where « Position du logo » is now the place told to the model; a transparent logo is said to be so; it is listed in the review, kept by a correction, checked by the export (`logo_stale`). Details and wire shapes: TODO T-KIT-022, DECISIONS, `designs/seller-kit.md`. Proved on Flare, final file and a correction that moves the logo included. What to know: the logo is no longer a pixel copy, it is checked like the title; in a first message a place for the logo was half followed (one image), in a correction it was followed (one image); Carré and Story are not tried; the rules of a logo laid over the image stay for versions made before (`editor_refinements_browser.py` asks two scenes as before by taking `draw_logo` out of the request). Three test posters of `data-walk` made by the first trial cannot be exported (`logo_stale`). Checks on the final code: backend suite `2134 passed, 3 deselected`, Vitest 420, `editor_refinements_browser.py`, `browser_smoke.py` and `chat_browser.py` passed (`chat_browser.py` stopped once in `walk_sign_out`, waiting for the phone bar's « Créer », while the machine was loaded, and passed when run alone); `terms_browser.py` last passed before T-KIT-024, which did not touch the data page. Flare images so far: 21, about 0.86 USD.

**Proof (Linux laptop, 2026-11-24):** whole backend suite on the final code `2133 passed, 3 deselected` (9 min); Vitest 420; the nine browser smokes passed on the frontend before the review fixes, and the five that cover the changed screens after them (the frontend has not changed since); backend code review r1 (fixes in), frontend code review r1 then r2 APPROVE; 5 paid images over the second walk and the trial, about 1.1 USD (about 2.3 USD with the first walk).

**Exact resume point.** No file is half-edited and nothing is in progress. Do not start code: ask the owner which of these he wants, in this order of use to a first real seller:
1. **« push »** (his word): `main` is two commits ahead of `origin/main`. Before it, `git fetch` and `git log --oneline HEAD..origin/main` (other sessions share this checkout).
2. **A release** (his alone: his pyinfra, his word). It brings migration 0021 and every fix of this track; the rehearsal passes in tests (`backend/tests/test_db.py`). Runbook: `deploy/README.md`, « Each release ». The box is shared: look, never change. After it, the first thing worth his eyes on the live site: a poster with a long title and the shop's logo (the logo must be drawn in the picture and listed in the review as « Logo de la boutique »).
3. **The drawn logo, not yet tried on paid images** (T-KIT-022/024; each is one Flare image, about 0.03 USD, only on his word): the Carré and Story formats; « Position du logo » set to the footer; a logo whose own artwork is white (the copy sent to the model is flattened onto white, `transparent()` in `backend/src/affiche/posters/visuals.py` only says the logo has transparency: a white logo would be invisible in that copy). If the white logo fails, the place to change is the logo's line in `prepare` (`backend/src/affiche/posters/service.py`, « the shop's logo for the image model to draw »): it calls `prepare_provider_input` (`backend/src/affiche/visuals/gateway.py`), which flattens onto white for every input; give the logo a mid grey ground when its opaque pixels are near white, and name that grey in place of « The white around it » in the logo sentence of `compile_scene` (`backend/src/affiche/posters/plans.py`). Not built, not tried: a hypothesis until one paid image shows the fault.
4. **Not built, found by his trial:** nothing tells the seller when a paid correction changed nothing. Measured: pixels cannot tell (see the evening paragraph). It needs a reading of the image by a model: his decision on cost and on who pays the redo, before requirements. No task yet.
5. **T-FREE-001**: reopened and built the same day as « Création libre » (the section at the top of this file). What it does not cover of the research note: a name and a price checked per product, an automatic reading of the image.
6. **T-KIT-019** (later): a visual first-use guide, the conditions shorter on the first screen, the review's six actions (the title styles are judged: done).
7. **T-FB-012**, the first real Facebook post with the owner: unchanged.

Open observations with no task, none blocking: Malagasy scene words are half followed; a text asked for in the scene words is not drawn and nothing says so; a title in « Gras condensé » mixes capitals and the typed case; the name lost in « Pas à pas » right after a photo (no cause found in code); `affiche.start` was once found set to `steps` on the test browser with no known cause.

**Commands.**

```bash
# backend, from backend/ (whole suite: about 9 min; run it alone, other sessions load this machine)
uv run pytest -q
uv run pytest tests/test_plans.py tests/test_poster_visuals.py tests/test_reads.py tests/test_looks.py -q   # the prompt and reader tests: 551 passed
# frontend, from frontend/
corepack npm@10 test
corepack npm@10 run build
# a browser smoke, from backend/, on its own port pair (build first)
SMOKE_WEB_PORT=5546 SMOKE_API_PORT=8546 uv run python ../frontend/tests/chat_browser.py
```

The release, by the owner only, from his checkout (never add `--diff` or `--debug`: they print secrets):

```bash
cd deploy; pyinfra 89.167.56.26 deploy.py --user deploy -y
```

**The local trial instance.** http://127.0.0.1:5536 (API 8536), real image and message providers from `backend/.env` (never read or print that file), Facebook simulated, data `backend/data-walk` (git-ignored; test shops `essaiclaude` and `essaikit`, sign-in in `backend/data-walk/acces.txt`). **It is stopped** (2026-11-25: Claude Code ended it when the machine ran low on memory; this laptop is short of memory when other sessions run, so stop it after use). The test shop `essaikit` holds about 11 credits; its profile logo is a transparent test logo and its contact a made-up number. For this test instance only, the owner allowed a higher daily limit of images: add `SHOP_DAILY_SPEND_USD='5.00'` to the `os.environ.update(...)` of the launcher below (the default, 2.00, stops a test day after about 30 images with a message that reads like a fault). It spends real money each time someone creates an image: start it only on the owner's word. Its launcher lived in the session's scratchpad and may be gone; this is the whole of it (save it outside the repo, run it from `backend/` with `.venv/bin/python <file>`; it serves `frontend/dist`, so build first; the original served a copy of that folder, this variant with `frontend/dist` itself was not run):

```python
import logging, os, subprocess
from pathlib import Path
import uvicorn
from affiche.api import create_app, uvicorn_options
from affiche.config import load_settings

root = Path('/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia')
os.environ.update(IMAGE_PROVIDER='openai', PLANNER_PROVIDER='claude', FACEBOOK_PROVIDER='stub',
                  DATA_DIR=str(root / 'backend/data-walk'), APP_ORIGIN='http://127.0.0.1:5536',
                  # the deployed model (deploy/compose.yml, ADR-078): the owner, 2026-11-24
                  OPENAI_IMAGE_MODEL='gpt-image-2.5-flare', OPENAI_IMAGE_QUALITY='medium')
os.environ.pop('STUB_FAIL', None)
settings = load_settings()
web = subprocess.Popen(['node', 'node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1', '--port', '5536',
                        '--strictPort', '--outDir', str(root / 'frontend/dist')], cwd=root / 'frontend',
                       env={**os.environ, 'SMOKE_WEB_PORT': '5536', 'SMOKE_API_PORT': '8536'})
try:
    uvicorn.run(create_app(settings), **{**uvicorn_options(settings), 'port': 8536})
finally:
    web.terminate()
```

To stop it without killing your own shell (a plain `pkill -f` matches its own command line):

```bash
pgrep -f "walk/serve[.]py" | xargs -r kill
pgrep -f "vite/bin/vite[.]js preview --host 127.0.0.1 --port 5536" | xargs -r kill
```

**What the code does not say.**
- The image prompt has two zones: rules, and a data block the model is told not to obey. The seller's words stay in the data block (that is what keeps them from setting a price); what the fixes of this track added is one sentence in the rules zone that points at them. Keep that shape for any next wording.
- Prompts are compiled when a job is asked and stored with it: a wording change never touches a job already asked. `test_feed_and_square_plans_and_prompts_are_unchanged_byte_for_byte` (`backend/tests/test_plans.py`) pins older prompts; its helper `as_captured` puts the two reworded sentences of a correction back before it compares. A next deliberate wording change extends that helper; it does not re-capture the digests.
- Every proof of a prompt wording here is one paid image: the scene words (poster 3 of the walk), the pack of three, the moved product. None is proof for every way of asking.
- Three products in one picture work as a by-product of the photo roles and the scene words; the prompt still says « one product ». By the owner's decision it stays so.
- « Nouvelle affiche » opens the way last used on the device (D-TEXT-FIRST-001), so a tester who used « Pas à pas » once lands there, not in Message.

**Landmines:** `chat_browser.py` and `browser_smoke.py` are long (background, their own port pair). The whole backend suite can fail once under load with `test_exports.py::test_hidden_title_requires_scene_headline_with_the_current_title`, which passes alone and with its file (T-SUITE-FLAKE). The reader's SYSTEM text changed (scene words, lines, unused parts, advert): the measurements of 2026-11-14 are not repeated. A phone number sent alone as a whole message is still read as an amount (an older test pins it). Twice in the walk a key press right after attaching a photo was lost; it may be the automation's instant typing, unconfirmed on a real phone. `chat_browser.py` can stop in `walk_sign_out` (waiting for the phone bar's « Créer ») when the machine is loaded: rerun it alone before reading it as a fault. `editor_refinements_browser.py` takes `draw_logo` out of its first two scene requests on purpose (route `as_before`): that is what still exercises the rules of a logo laid over the image; do not « fix » it. Three posters of `backend/data-walk` made by the first drawn-logo trial cannot be exported (`logo_stale`): test data, not a fault. Paid tests run on `gpt-image-2.5-flare` at medium only; a local instance started without `OPENAI_IMAGE_MODEL` falls back to `gpt-image-2` at high, seven times the price and not the production model.

**Uncommitted from this session:** `docs/project/HANDOFF.md` only (this handoff, written after the commit; commit it on the owner's word). Untracked and not this track's: `.impeccable/`. Not pushed: the two commits named in the state line.

## User walk as a new seller · Claude, 2026-11-23 (done; its findings are answered by the section above)

The owner asked for a walk of the app in Edge as a real user before polishing: Message to a confirmed poster, « Pas à pas » to a confirmed poster, a poster from a reference photo, « Publier ». Done on `main` (not the released build) with real providers on his word, Facebook simulated. No code change. The findings, the simplifications, the features a seller would not use and his five ideas weighed are in [reviews/user-walk-2026-11-23.md](reviews/user-walk-2026-11-23.md); the six posters are in `outputs/user-walk/`.

**The three that change the plan:** (1) a confirmed poster stays « À vérifier » when an older version was left undecided: a defect of the server's rule, his remark on « Publier » (T-STATUS-STALE-REVIEW, proposed); (2) Message drops, without saying it, every word of the first message that is not a name, a price or a style, yet takes a free scene request from the second image on, with the best result of the walk; (3) a seller cannot put his own warranty or delivery line on a poster.

**Left running by this session:** the walk's instance, http://127.0.0.1:5536 (API on 8536), real image and message providers from `backend/.env`, data in `backend/data-walk` (git-ignored), sign-in in `backend/data-walk/acces.txt`. It dies with the session; its script is in the session's scratchpad (`walk/serve.py`). It spends only when someone creates an image. Also: a fourth shop `essaiclaude` was added to the trial instance on port 5526 (its line is at the end of `/tmp/doka-journey08-trial/acces.txt`), and the owner's Edge session there was signed out.

**Was the next step (done since, see the section above):** before any fix, the owner asked (2026-11-23) to think the platform as a kit the seller reuses (a title style, scene models, his own lines), free words still allowed. The concept is the last section of the report, not approved; his four decisions on it are awaited (shop-only kit or operator models; one way to create or two; title drawn or laid over; what free words may change). Then requirements for its first slice. No fix of the report is started. T-FB-012 (the first real post) is unchanged.

**Uncommitted from this session:** nothing (committed and pushed with the kit, 2026-11-24).

## Repository handoff · 23 November 2026

The owner requested committing and pushing the seller and operator journey to main. The change includes the shared review, confirm-for-later, PNG and Facebook actions, four-step guide, relevant service contracts, tests and approved design records. The follow-up documentation commit includes the root README, deployment runbook, brand kit, design mockups, research and outstanding project-log edits. The local .impeccable/ tool files remain outside this commit. The next release work is tracked by T-JOURNEY-08. Production deployment is a separate owner operation.

## Confirmation feedback · 23 November 2026

The owner reported that the single review worked and that the confirmation on download or Facebook preparation was easy to miss. The review now offers « Confirmer pour plus tard » to keep the reviewed PNG in « Mes affiches ». The download, post-preparation and sharing shortcuts name their confirmation. The server acknowledges the current file before the interface shows « Affiche confirmée ». The existing Page composer still controls the public send. The updated local trial runs at http://127.0.0.1:5526/ with the existing sign-ins. Production releases remain owner-operated.

The production build, 383 frontend tests and the four-step tutorial and publishing browser walks passed. A direct check on a connected simulated Page confirmed the poster and opened the description with zero sends. In the 360 px review the library-only action made one confirmation request, stayed on the poster and produced zero download, paid or Facebook mutations. Reopening the library item and downloading later returned the exact PNG that had been reviewed. See the [review](../../outputs/guide01/single-review-phone.png) and [confirmed state](../../outputs/guide01/confirmed-for-later.png). T-JOURNEY-08 retains the operator and physical-phone observations.

Uncommitted files touched here are PRODUCT.md, frontend/src/{App.vue,FirstPosterGuide.vue,share.ts}, frontend/tests/{browser_smoke.py,design_capture.py,guide_browser.py,publish_browser.py,share_browser.py,terms_browser.py}, and docs/project/{DECISIONS.md,HANDOFF.md,TODO.md,guide-premiere-affiche.md,requirements/saas-journey.md,designs/first-poster-guide.md,designs/saas-journey.md,reviews/journey-acceptance-2026-11-22.md}. Earlier entries record other uncommitted work in the checkout.

## One review of the finished poster · Codex, 2026-11-22

The owner approved the [single-review amendment](designs/saas-journey.md). The editor and Message now show the selected version’s actual rendered PNG, original photos and offer price together. Choosing « Télécharger le PNG » or « Préparer la publication » records the product and file checks in one transaction. The Page composer retains its own send confirmation. An existing confirmed PNG remains downloadable by its immutable link. Choosing an alternative version first is explicit and free. The walkthrough now has four steps.

The local development shop is at http://127.0.0.1:5273/. The isolated trial at http://127.0.0.1:5526/ uses the same saved shops and private local access file described below. Both use simulated providers. Production releases are owner-operated.

The production build and all 383 frontend tests passed. Backend verification covered all 1,946 default tests across [overlapping runs](../../outputs/single-review/backend.log). The combined run was interrupted and one logo-seal test had failed during the build; all 27 export tests passed against the final build. Three opt-in real-model tests were excluded. The [phone review regression](../../outputs/single-review/private-review-verified.log) checked correction without approval, failed-photo recovery, replacement of a render while open, stale confirmation responses, and a byte-identical PNG. The complete Message, sharing, publishing, tutorial, conditions, refinements and dashboard browser walks passed with simulated providers. The editor was verified in groups, including both responsive layouts, saved words, waiting, low-credit recovery, the three output formats, keyboard and two-shop isolation.

The grouped editor checks cover every scenario. The combined runner subsequently exposed an ordering assumption when a fixture reopened an already-reviewed poster. The test now dismisses that preview before testing editor navigation. Compilation and diff checks passed after the test-only change. The combined runner was not repeated.

The owner confirmed they had already tested the flow. Record the outcome of that existing test when supplied. Check which device and destination scenarios it covered before scheduling any further observation under T-JOURNEY-08. Use the [participant briefs](reviews/journey-acceptance-2026-11-22.md). The [360 px review](../../outputs/single-review/single-review-360.png) shows the two output actions and the offer alongside a simulated preview. The build uses the private render API, so reload the backend as well as the frontend when trying an old development instance.

Uncommitted files for this slice include PRODUCT.md, backend/api/README.md, backend/src/affiche/posters/{exports.py,visuals.py}, backend/tests/test_exports.py, frontend/src/{App.vue,FirstPosterGuide.vue,style.css}, frontend/tests/{browser_smoke.py,chat_browser.py,design_capture.py,editor_refinements_browser.py,guide_browser.py,publish_browser.py,share_browser.py,shop_dashboard_browser.py,terms_browser.py}, docs/project/{DECISIONS.md,HANDOFF.md,TODO.md,guide-premiere-affiche.md,designs/first-poster-guide.md,designs/saas-journey.md,requirements/_INDEX.md,requirements/first-poster-guide.md,requirements/poster-editor.md,requirements/saas-journey.md,reviews/journey-acceptance-2026-11-22.md}. Earlier entries cover the other uncommitted work.

## Release verification and first-use feedback · Codex, 2026-11-22

The owner raised the extra scene and file confirmations after the initial verification. The single-review amendment above supersedes that initial interaction.

The owner identified entering the product or choosing a format as the first difficult point. Message now labels the phone photo button and gives a concrete example of what to type. Pas à pas puts photo, product details, attestation and preparation ahead of optional shop identity. A new affiche uses Publication without an extra selection. The format helper explains what the selected format can do and accounts for a shop with Page publishing disabled. On a 360 px phone, preparation moved from y=1351 to y=891. See [guided intake and format captures](../../outputs/journey08/intake/) and the [release verification record and participant briefs](reviews/journey-acceptance-2026-11-22.md).

The normal development shop remains at http://127.0.0.1:5273/. A separate local observation instance is at http://127.0.0.1:5526/, using the same frontend build, simulated providers, its own data and temporary private logins in `/tmp/doka-journey08-trial/acces.txt`. Its user service is `doka-journey08-trial.service`. Two empty shops support independent first-use trials. The returning shop has a connected simulated Page, one confirmed file and one approved scene awaiting file confirmation. This temporary service is independent of the pilot and the main dev service.

T-JOURNEY-08 still needs an observed seller retry on the simplified entry, the returning seller and operator observations, and physical phone accessibility and sharing. Record which route the seller took, whether they obtained the PNG or prepared the ordered post, any assistance, and the first point of difficulty. A real first public post is the owner's release operation. Do not enter automated outcomes as observations.

Two acceptance defects also received fixes. A failed chat save now leaves the send button and retry reachable with a short keyboard-height viewport. Orca now separates the step counter from the title. The operator discard confirmation announces the original shop, reference and local effect. The design-capture tool now includes privacy, guide, editor, publishing and confirmation, and checks for horizontal overflow.

Local verification finished. All 1,944 default backend tests and 383 frontend tests passed. The three opt-in model tests were deselected. The full editor, editor refinements, Message, sharing, publishing, guide, dashboard, terms and operator browser checks passed. The editor test now handles sign-out occurring between a test navigation check and a click, and verifies both the format advice and the locked-format reason. All 144 responsive captures passed the horizontal overflow check. The next step is the unaided retry in the observation shop.

Uncommitted files touched during this slice are AGENTS.md, PRODUCT.md, frontend/src/{App.vue,ChatView.vue,FirstPosterGuide.vue,style.css,admin/Admin.vue}, frontend/tests/{admin_browser.py,browser_smoke.py,chat_browser.py,design_capture.py,editor_refinements_browser.py,guide_browser.py,publish_browser.py}, backend/tests/test_facebook_posts.py and docs/project/{DECISIONS.md,HANDOFF.md,TODO.md,designs/first-poster-guide.md,guide-premiere-affiche.md,reviews/journey-acceptance-2026-11-22.md}. The earlier entries below list the other uncommitted work in the shared checkout.

## Operator console · Codex, 2026-11-22

T-JOURNEY-07 puts financial recovery first in the local [operator console](http://127.0.0.1:5273/admin/). Next is **T-JOURNEY-08**. Use the proof scenarios in [the journey design](designs/saas-journey.md) and [tutorial design](designs/first-poster-guide.md) to reconcile the cross-screen failures already exercised, run the outstanding checks, and record which outcomes still require an observed seller, a physical phone or the release owner.

On Overview, « Needs you » precedes the four figures. Each unresolved row identifies the operation, shop and saved reference while the independent reads settle. On a 360 × 640 viewport the first recovery link moved from y=651 to y=194 and retained its 44 px touch target. Compare the [previous phone view](../../outputs/journey07/before-overview-360-light.png), [updated phone view](../../outputs/journey07/after-overview-360-light.png) and [desktop view](../../outputs/journey07/after-overview-1440-light.png).

Shop detail shows identity, balance and the kept request before its History, Access and Grant credits controls. The form retains its fields while closed, and an unanswered request remains accessible if the shop detail read fails. Money confirmations show the signed-in operator and preparation time in UTC. Payments leads with the applied UTC range and received amount, protects unsubmitted date edits across refresh and retry, and links each shop to its detail. Service surfaces unknown or late backup, failed jobs and AI pause ahead of technical details. The existing financial endpoints and saved request format remain in use.

The production build, all 383 frontend unit tests, 55 admin backend tests and all eight operator Chromium walks passed. The browser suite covered duplicate and uncertain payments, same-request replay, authorization expiry, confirmation cancellation, preserved form values, failed shop detail, safe read retries and keyboard operation. From frontend run `corepack npm@10 run build` and `corepack npm@10 test`. From backend run `.venv/bin/python -m pytest tests/test_admin.py -q` and `.venv/bin/python ../frontend/tests/admin_browser.py` with unused `SMOKE_WEB_PORT` and `SMOKE_API_PORT`. Let the production build finish before starting the browser suite. The capture set in outputs/journey07 covers Overview, shop recovery, Payments and Service at 360, 768 and 1440 px. No live ledger, provider, service control or production release was used.

Uncommitted in this slice are frontend/src/admin/{Admin.vue,Confirm.vue,Overview.vue,Payments.vue,Service.vue,admin.css}, frontend/tests/admin_browser.py and docs/project/{DECISIONS.md,HANDOFF.md,TODO.md,designs/app-redesign.md}. Other uncommitted shop, backend, deployment, brand, mockup and review files are listed in earlier handoffs below.

## First-poster tutorial · Codex, 2026-11-22

T-GUIDE-01 is implemented in the development shop. Next is **T-JOURNEY-07** in [the journey design](designs/saas-journey.md), prioritizing pending grants, access problems and payment recovery in the operator console. T-JOURNEY-08 retains the first-time seller observation, physical phone and assistive-technology checks before release.

An empty Accueil offers « Ma première affiche » next to creation after the shop has answered the terms prompt. « Aide » in the desktop sidebar or phone menu opens the same five steps anywhere in the shop. The guided editor and Publier have contextual entries. The panel preserves work, returns keyboard focus, resumes after an early close and starts from step one after « Terminer ». A route or session change dismisses the panel. The French walkthrough uses the shop's labels and covers the photo, price and credit decision, fidelity review, exact-file confirmation, PNG download and single or ordered Facebook publication.

The dedicated Chromium fixture exercised both entry modes, fresh and failed Accueil reads, deferred terms, keys in both directions, route changes, session re-verification, draft photos and their roles, and a batch's selection order, text and tab lock. It obtained two valid PNGs from the simulated provider and reached confirmation with the simulated Facebook Page. Traversing the guide made zero mutation requests. See [phone](../../outputs/guide01/guide-phone-dark.png), [desktop](../../outputs/guide01/guide-desktop-light.png), [short viewport](../../outputs/guide01/guide-short-zoom.png) and [publishing](../../outputs/guide01/guide-publishing.png). Reproduce with `corepack npm@10 run build` in frontend and `.venv/bin/python ../frontend/tests/guide_browser.py` in backend. The existing development shop is at http://127.0.0.1:5273/. Production releases remain with the owner.

The production build and all 383 frontend unit tests passed. The editor, shop dashboard, publishing, conditions and guide Chromium suites passed using isolated data. The guide suite also exercised contextual entries after generation and approval, and a keyboard regression where the previous step heading was hidden after scrolling through troubleshooting. Returning from the 180 × 200 layout to the 360 × 400 layout now restores the heading to view, as shown in the [keyboard capture](../../outputs/guide01/guide-short-keyboard.png). The live development service answered HTTP 200 after verification.

Uncommitted files for this task are frontend/src/{App.vue,FirstPosterGuide.vue,ShopHome.vue,ShopPublish.vue,style.css}, frontend/tests/{guide_browser.py,shop_dashboard_browser.py} and docs/project/{DECISIONS.md,HANDOFF.md,TODO.md,guide-premiere-affiche.md}. The earlier entries below inventory the other uncommitted work in the shared checkout.

## Shop home, library and navigation · Codex, 2026-11-22

T-JOURNEY-06 is complete. Next is **T-GUIDE-01**, the optional French in-product walkthrough in [first-poster-guide.md](designs/first-poster-guide.md). Make its five steps reachable from Accueil and the creation flows. Verify keyboard focus and replay, intact attachments and batch order, and zero mutations from browsing the guide. Operator priorities and the release/observed-device checks remain queued.

Accueil puts creation beside its heading, then the first poster awaiting fidelity review and the first failed generation when present. Matching recent artwork identifies the poster. A healthy balance stays in the shell, while pending, low, blocked or unavailable credit states appear on Accueil. Each dashboard section retains its own failure, timestamp and retry. The phone bar labels Créer and offers Publier when the service supports Facebook, otherwise Styles. The drawer retains Styles. In Mes affiches, Actives/Retirées and the count sit above the rows. A named disclosure keeps duplicate, remove and restore accessible. The confirmed file has its own visible action, including when an alternate visual awaits review. The existing list API exposes its current-revision confirmation boolean. Opening the file or the fidelity review checks the poster again without selecting a version, rendering, or posting. The French guide describes both return paths.

At 360 × 640, the Accueil creation action moved from y=505 to y=160. In the two-poster fixture both library rows and the confirmed-file action now fit above the phone bar. Compare [previous Accueil](../../outputs/journey06/before-accueil-360-dark.png) and [current Accueil](../../outputs/journey06/after-accueil-360-dark.png), or [previous library](../../outputs/journey06/before-affiches-360-light.png) and [current library](../../outputs/journey06/after-affiches-360-light.png). The directory contains 24 before/after captures across 360, 768 and 1440 in both themes, plus library detail checks. These use temporary stub data.

Verified locally: production build, all 383 frontend unit tests, 61 backend API and two-shop tests, and the editor, dashboard, sharing and Facebook publishing Chromium suites. Focused checks cover the concurrent confirmed file and pending visual in either remembered mode, stale file after a price change, review completed elsewhere, filter counts, decoded thumbnails and keyboard focus for row actions. To reproduce, run `corepack npm@10 run build` and `corepack npm@10 test` in frontend, then `.venv/bin/python -m pytest tests/test_api.py tests/test_two_shops.py -q` and `.venv/bin/python ../frontend/tests/shop_dashboard_browser.py` from backend. Separate `SMOKE_WEB_PORT` and `SMOKE_API_PORT` pairs isolate concurrent smokes.

The existing local user service `doka-shop-dev.service` now serves the updated stub API and Vue app from the same demo database. Shop and console remain at http://127.0.0.1:5273/ and http://127.0.0.1:5273/admin/. Its runtime systemd drop-in `resume-existing-demo.conf` invokes `resume_doka_dev.py` beside the previously documented scratch launcher and private credentials. Shop login and the new protected list field were verified. All three posters, revisions, recorded jobs, shop and operator session counts, and grants survived the restart. The owner controls production releases. No live Facebook or paid provider was used.

Uncommitted files in this slice include backend/src/affiche/api.py, backend/tests/test_api.py, frontend/src/{App.vue,ShopHome.vue,dashboard.ts,style.css}, frontend/tests/{browser_smoke,shop_dashboard_browser,publish_browser,share_browser}.py and docs/project/{designs/saas-journey,guide-premiere-affiche,DECISIONS,TODO,HANDOFF}.md. Other changes in this shared checkout belong to the preceding or concurrent work inventoried below.

## Prepare an offer in one screen · Codex, 2026-11-22

T-JOURNEY-05 opens a valid guided draft on Style with its original photos, variant, title, exact price, included shop details, format and style. Textes and Boutique edit the same draft in any order. The primary generation button opens the existing cost decision from any preparation tab. On a phone the fixed footer also opens the full preview. A failed product read offers a retry. The format picker explains direct Facebook publication when the feature is enabled. The message recap shows the current request’s format and photo roles. A replacement photo creates a separate draft and its first generation still requires an explicit action.

[Previous phone](../../outputs/journey05/before-360-light.png) · [Current phone](../../outputs/journey05/ready-360-light.png) · [Dark phone](../../outputs/journey05/ready-360-dark.png) · [Tablet](../../outputs/journey05/ready-768-light.png) · [Desktop](../../outputs/journey05/ready-1440-light.png). At all three widths the preparation view fits horizontally, displays one generation action and sends no plan or scene request on entry. The capture verifies that the original product image decodes. Local demo at http://127.0.0.1:5273/ uses simulated providers.

Verification passed for the production build, all 383 frontend tests and 48 backend draft tests. The Chromium chat, dashboard, terms, editor refinements, Facebook publishing and sharing suites passed using temporary data. Additional focused checks covered a Story and square PNG, preserving a prior paid chat request during a product-read failure, and reopening an in-progress first generation on a second phone tab. An incomplete title blocks new generation while other valid edits can still save. The complete guided editor Chromium suite passed, including the first generation, protected paid retry, two-shop separation, confirmed downloads and all three formats. Reproduce with `corepack npm@10 run build` and `corepack npm@10 test` in frontend, then `.venv/bin/python ../frontend/tests/browser_smoke.py` and `.venv/bin/python ../frontend/tests/chat_browser.py` from backend. Use separate `SMOKE_WEB_PORT` and `SMOKE_API_PORT` pairs for concurrent suites. T-JOURNEY-05 is complete. Next is T-JOURNEY-06 (Accueil, Mes affiches and navigation). The in-product walkthrough and operator console follow as separate approved tasks. This slice updates the [French walkthrough](guide-premiere-affiche.md). Releases remain with the owner.

Uncommitted in this slice: frontend/src/{App.vue,ChatView.vue,chat.ts,document.ts,style.css}, frontend/tests/{browser_smoke,chat_browser,editor_refinements_browser,shop_dashboard_browser,terms_browser}.py, frontend/tests/chat.test.ts and docs/project/{guide-premiere-affiche,TODO,DECISIONS,HANDOFF}.md. Prior shared-checkout changes are listed below. Screenshots are local verification artifacts under outputs/journey05/.

## From visual approval to the final PNG · Codex, 2026-11-22

T-JOURNEY-04 connects an approved visual to « Vérifier le fichier final » in Pas à pas and Par message. The reviewer can select a different approved version explicitly, return to the same poster’s settings, or close the review. Closing a review discards its pending navigation. Confirming the exact PNG remains a separate action. In the ready panel the confirmed format, dimensions, amount, Facebook composer and PNG download sit ahead of the image on phones. Native sharing and caption editing are grouped together. History sits under « Autres actions » and uncertain publications stay visible. « Changer le prix » opens the same poster’s price field and distinguishes an editable price from a price drawn in the scene.

Compare the [previous 360 px screen](../../outputs/journey04/before-360-light.png) with the [current phone](../../outputs/journey04/ready-360-light.png), [dark phone](../../outputs/journey04/ready-360-dark.png), [tablet](../../outputs/journey04/ready-768-light.png) and [desktop](../../outputs/journey04/ready-1440-light.png). At 360 × 640 the two outputs moved from below y=1,100 to the first viewport. The local shop and operator demo still run on 5273. All development used simulated providers.

Verification passed locally with the production build, 381 frontend tests, 25 backend export tests, and all six Chromium suites (editor, chat, sharing, publishing, conditions, editor refinements). The PNG matched the inspected bytes. An intentionally delayed render did not reopen a dismissed review. An unexpected format left the reviewer in the approval dialog. A matching existing confirmation reopened without a mutation. Keyboard focus cycles through the review and the file panel, including its disclosures. Verified at CSS widths 360, 768 and 1440. The editor harness now holds the image request before expiring its simulated session, and a chat test tolerates its already-verified notice expiring before dismissal during screenshot capture.

T-JOURNEY-04 is complete. Next is T-JOURNEY-05 in D-JOURNEY-002, making the unchanged text and shop settings optional on the preparation screen while keeping their controls and the generation charge confirmation. The tutorial and operator layout are still queued. The owner controls release. Physical-phone and live Facebook checks remain outside this local verification.

Uncommitted files for this slice include frontend/src/{App.vue,style.css}, frontend/tests/{browser_smoke,chat_browser,editor_refinements_browser,publish_browser,share_browser,terms_browser}.py and docs/project/{TODO,DECISIONS,HANDOFF}.md. Other uncommitted implementation, documentation, mockups and review work is itemized in the entries below.

## Return to the Facebook publication · Codex, 2026-11-22

The shop can leave a single or batch publication to fix an excluded poster or connect its Facebook Page. Returning reopens the originating composer. « Ajouter à ma publication » is an explicit, one-use batch action. The composer reloads the current draft and checks the confirmed file, Page, publication state and capacity under its existing tab lock. A format copy can replace a single target only after « Continuer avec cette copie ». The account takes keyboard focus at Page Facebook and provides a return link. Its full-page return marker is bound to the authenticated shop and consumed once.

T-JOURNEY-03 is complete. The final production build, all 381 frontend tests, and both the publishing and sharing browser smokes passed. The focused backend exclusions regression passed as well. At 360 and 1440 CSS px, keyboard focus reached the Facebook section, its return link opened the batch, and the page fit the viewport. The mobile publishing smoke generated and confirmed a format copy using the simulator, then asserted the new ID, preserved source and intact batch. Next is T-JOURNEY-04 in the approved design, connecting fidelity approval to the current final-file check and moving the Facebook/PNG actions ahead of the tall phone preview. The in-app walkthrough and operator polish are tracked separately in TODO.

The running development shop and console use a simulated provider at http://127.0.0.1:5273/ and http://127.0.0.1:5273/admin/. The existing seeded development launcher now runs independently of the terminal as the user service doka-shop-dev.service, frontend port 5273 and API port 8100. This launch created fresh demo data and wrote matching credentials to its private credentials.txt (the launcher path is documented below). The design mockups still have their own preview on 5376.

Uncommitted for this slice: frontend/src/App.vue, ShopPublish.vue, ShopAccount.vue, facebook.ts, publish.ts, frontend/tests/facebook.test.ts, publish.test.ts, publish_browser.py, and docs/project/TODO.md, DECISIONS.md and HANDOFF.md. Additional uncommitted backend, design, review and parallel-track files are inventoried in the preceding work below. No production release, real Facebook post, migration or paid generation.

## Missing posters on the Facebook picker · Codex, 2026-11-22

The owner’s « next » after the design review was taken as implementation approval. T-JOURNEY-01 adds a shop-scoped read of active, excluded posters, using the same reasons as the existing picker. T-JOURNEY-02 shows each name, reason and applicable next action in « Affiches à préparer ». The list loads on expansion, pages by 20 and offers local retry. Before navigating away, the shop verifies the current ordered publishing draft is safely stored. The editor opens on the affected poster and preserves the existing explicit generation, confirmation and publish controls.

Local proof: 1,943 backend tests passed in four module groups (3 opt-in real-model tests deselected), all 377 frontend tests, typecheck and production build. Screenshot of the real component with stub data: outputs/publish-browser/affiches-a-preparer-1366.png. Both publish_browser.py and share_browser.py passed against isolated providers. The publish smoke exercises a failed second page, retries the identical cursor, tests changed-price and square-format editor destinations and verifies the saved description/order. The smoke now uses its existing stable-handle helper for two drag gestures that previously sampled moving rows. No migration, deployment or production Facebook request. Next slice is T-JOURNEY-03: return from repair or connection to the originating batch/single composer and revalidate under the current tab lock before an explicit addition. Today the owner can navigate back to Publier to find the saved batch.

Uncommitted implementation files: backend/src/affiche/api.py, backend/src/affiche/posters/facebook_posts.py, backend/tests/test_facebook_posts.py, backend/tests/test_two_shops.py, frontend/src/App.vue, frontend/src/ShopPublish.vue, frontend/src/publish.ts, frontend/tests/publish.test.ts, frontend/tests/publish_browser.py. Both designs, their indexes, TODO, decisions and handoff also have local edits. Earlier review and concurrent-track changes are listed below.

## Shop and operator journey designs · Codex, 2026-11-22

The owner’s « continue » after the requirements presentation was taken as approval of both requirements. The [journey design](designs/saas-journey.md) and [guide design](designs/first-poster-guide.md) are now ready for **design approval**. [Shop prototype](mockups/poster-journey/index.html) (also opens the normal ready file with #fichier) and [operator prototype](mockups/operator-priorities/index.html). A local preview server was started on loopback port 5376, rooted at docs/project/mockups. To recreate it, run `python3 -m http.server 5376 --bind 127.0.0.1 --directory docs/project/mockups` from the repo root.

Verified shop and operator mockups with synthetic data in Chromium at 360, 768 and 1440 px. A repaired image returns to a composed batch without losing its description/order. The exact PNG, Page composer and five-step guide were exercised locally. Operator alerts link to a sample ledger. No production changes or live post. The designs specify the protected, paginated exclusions read, the lock and identity checks on return, and distinct scene/file/post decisions. The mocks simulate these data and effects. Next on design approval: enter the independently verifiable implementation tasks in TODO before starting the named-exclusion read and its shop-isolation tests. Physical-phone and assistive-technology checks remain release work.

New uncommitted files for this phase: designs/saas-journey.md, designs/first-poster-guide.md, mockups/poster-journey/ (HTML, CSS, JS, sample poster and four screenshots), mockups/operator-priorities/ (HTML and two screenshots). Updated both requirement drafts, both indexes, TODO.md, DECISIONS.md and HANDOFF.md. The concurrent files and preceding review outputs are inventoried below.

## Shop and operator UX review · Codex, 2026-11-22

Completed the [screen inventory](reviews/saas-ux-2026-11-22.md), [French first-poster guide](guide-premiere-affiche.md) and draft requirements for [journey simplification](requirements/saas-journey.md) and [in-product onboarding](requirements/first-poster-guide.md). Next gate is owner approval of those requirements, then matching designs. First design slice should show the missing-poster recovery and both output actions on a phone and desktop. Preserve the three distinct decisions on generated content, exact file and actual Page send.

Release checked through public HTML and sign-in, local matching asset names, stub captures and current source. Edge exposed only its window frame. No production operation or app change. Uncommitted in this review: the linked report and its JPG, guide, two requirements, requirements/_INDEX.md, TODO.md, DECISIONS.md and HANDOFF.md. Existing concurrent work in deploy/README.md, PROJECT.md, shared tracking files, root PRODUCT.md, .impeccable/, brand/, mockups/brand-directions/, mockups/doka-studio-identity/, mockups/text-first/ and reviews/social-publishing-saas-research-2026-11-15.md remains in the checkout.

## After the release: the warning by words and the copy on a new photo — Claude, 2026-11-21 (READ FIRST)

No work order. The owner released the redesign and reported two things; his word: "handle now, word test, and yes copy with the new photo".

**State: on `main`, committed, pushed, and released with `05a12ee` on 2026-11-22 (the owner).**
- **T-WARN-WORDS (ADR-125):** the features warning shows only when the request's words could ask for features or text (`asksText`, `generation.ts`; used by `warns` in `chat.ts` and by `askRefine` in `App.vue`).
- **T-CHAT-PHOTO (ADR-126, D-TEXT-FIRST-007 v5):** on an existing poster every attached image is a product photo; the chat's `photo` card offers a free copy of the poster on it (`offer`, `copyWith` in `ChatView.vue`); the copy is the editor's own action (`remake` in the chat adapter, `App.vue`, modelled on `remakeIn`) and opens in « Pas à pas », where « Générer l’affiche » makes its image. The chat adds no paid card and stores nothing of the copy.
- **How it got there (read before changing it):** four designs made the copy's first image in the chat and four reviews rejected them, each time in the recap the chat added by itself. The owner: "When blocked, think of another way it can be done, without keeping on polishing it". v5 is that other way. Do not bring the chat's own recap back.
- **Reviews:** six Codex reports in `reviews/chat-photo-*-2026-11-21.md` and a devil's advocate. r5 (on v5): no automatic charge, five smaller points, all fixed. r6 (confirmation): the preparing save cannot overwrite an edit; nothing is paid, read or generated without a tap on an existing paid control; two sentences fixed after it; one cross-tab race on the words store recorded in the design as known and left. Its formal verdict stayed REJECT on those three; no further round was run, on the owner's word about polishing.
- **Proof on the final code (Linux, local stub):** Vitest 359; the build; all seven browser smokes (`chat_browser.py` with `walk_photo`, `editor_refinements_browser.py`, `browser_smoke.py`, `shop_dashboard_browser.py`, `share_browser.py`, `terms_browser.py`, `admin_browser.py`). Backend untouched, not run.
- **French sentences to read:** the copy card and its two buttons, « La copie est créée : retrouvez-la dans Mes affiches. … », the editor's notice « Copie de l’affiche avec la nouvelle photo, sans version : … », « … son chargement est incomplet … » (all in D-TEXT-FIRST-007).

**Nothing of this track is left uncommitted.** Its next step was the owner's release: done.

## Publishing on a Facebook Page — Claude, 2026-11-23 (READ FIRST: released, connected, no real post yet)

No work order: the owner's own project. Scope ADR-127 (stage 1: shops whose Page admin has a role on his Meta app « Doka studio », app id `29711342541804784`; free; a link to the post), ADR-128 (a publish page: one post of one or several confirmed posters, in his order, no limit of the app, a limit per shop as the operator's setting, « Publication » format only), ADR-129 (one way to publish: a poster alone is a post of one image), ADR-130 (how a post is never sent twice; the rehearsal; the restore rule; his UI choices). Requirements `requirements/facebook-publishing.md`, `requirements/facebook-post-page.md` (with « What the proofs showed »); designs `designs/facebook-publishing.md`, `designs/facebook-post-page.md`; runbook `deploy/README.md` « Publishing on a Facebook Page ».

**State:**
- **Code: complete; released by the owner on 2026-11-22 at `05a12ee`** (the container's image revision checked). Since then `main` holds Codex's journey work on top (`0b67fbe` « Simplify poster creation, review, and Facebook publishing », `ad6cacc`: pushed, NOT released), which changes `facebook_posts.py`, `ShopPublish.vue`, `publish.ts` and their tests (« Affiches à préparer », the return to the publication, confirm for later): read its sections above before touching this feature. Tasks T-FB-001 to 004, 008 to 011, 013, 014 done; reviews in `reviews/t-fb-0*`.
- **On the box:** `FACEBOOK_PROVIDER='meta'`, the app id and secret set by the owner in `app.env`, recreated. Gates of T-FB-005 all passed: (1) the front proxy keeps no access log (Maizina's Caddy has no `log` directive; a dummy `facebook.html?code=…` is in no log); (2) « Clé requise » is on and works (without the proof: code 100; with it: the answers; `me/accounts` lists his four Pages); (3) the redirect URI `https://affiches.miorantsoa.app/facebook.html` was missing in « Facebook Login for Business → Paramètres » — added by Claude on his word, saved; then **the pilot's Page Original Phone Mada is connected** (his words: « It's connected now »).
- **No real post yet** (T-FB-012).
- **Meta app « Doka studio »:** published; permissions `pages_show_list`, `pages_manage_posts`, `pages_read_engagement`, `business_management`; privacy address « Vos données »; « Domaines de l'app » holds `affiches.miorantsoa.app` twice (harmless). With « Clé requise » on, the Graph API Explorer no longer lists Pages (its own call has no proof); use a user token with the proof (`/tmp/claude-1001/-home-miorantsoa-Documents-Miorantsoa-Vite-affiche-ia/9b8248f7-9429-41d2-92de-a2b67ec798ff/scratchpad/gate2.py`, scratchpad, asks for the token and the secret with getpass, prints only Facebook's answers).
- **Nothing of the proofs is left on Facebook:** every test post deleted by the owner, the three never-attached photos deleted by Claude on his word. Deleting a post on Facebook deletes its photos.

**Open with the owner (his words awaited):**
- **T-FB-015 is superseded** (TODO `[-]`): the owner's question (« Approuvée » posters missing from the publish page) is answered by Codex's approved D-JOURNEY-005, built as T-JOURNEY-01 to 03 (each left-out poster named with its reason and the way to fix it), committed in `0b67fbe`, not released.
- **T-FB-012:** the first real post, public, his choice of poster and moment. Then check with him: « Voir la publication » opens the post; the collage a visitor sees (order, layout); for several images, read the post back in the Explorer (`<post id>?fields=attachments{subattachments{target{id}}}`, with a proof now: use the script's approach).
- **T-REHEARSE-ORDER:** the rehearsal hashes tables other than the posts in their primary key's order (`run_products` shows in `rowid` order): a reorder there would pass. From before this work; no pending migration touches it.

**Landmines:**
- Every Graph call needs `appsecret_proof` now; a token alone is refused (code 100).
- Never set `FACEBOOK_PROVIDER=stub` on the box: the first Facebook call records the data folder's mode and the other is then refused.
- A restore: `FACEBOOK_PROVIDER='off'` until the LAST successful `after-restore --apply`, then the recreate command (never `docker start`): runbook « Restore » steps 1, 3, 4, 7.
- The publish page holds one tab at a time (Web Lock `affiche-publish`); a second tab shows « … ouverte dans un autre onglet » with « Continuer ici ».
- The local dev shop on http://127.0.0.1:5273 is now Codex's user service `doka-shop-dev.service` (stub providers, the Facebook stand-in); this session's own dev server was stopped by Claude Code for low memory on 2026-11-22 and is not to be restarted beside it (same ports).

**Uncommitted from this track:** nothing. The owner committed and pushed this track's last docs (ADR-130, the runbook's gate notes, TODO's statuses, this section) inside `ad6cacc` on 2026-11-23.

**Exact next step:** with the owner, the first real post (T-FB-012), at his moment and with his poster, on the released app (`05a12ee`, Page Original Phone Mada connected). Then check with him: « Voir la publication » opens the post; the collage a visitor sees (order, layout); for several images, read the post back with the proof (the approach of `gate2.py`). The release of `0b67fbe`/`ad6cacc` is his (pyinfra); it has no migration of this feature. T-REHEARSE-ORDER stays open, small.

## App redesign — Claude, 2026-11-21

No work order: the owner's own project. Goal: both interfaces follow the mockup he approved
([mockups/doka-console/](mockups/doka-console/README.md)); ADR-123, [requirements](requirements/app-redesign.md),
[design](designs/app-redesign.md) v2, tasks T-REDESIGN-001 … 007 in TODO.md.

**State: all seven tasks, and the element pass T-REDESIGN-008 (ADR-124, below), are done and merged into `main` (2026-11-21, on the owner's word "merge redesign into main": a `--no-ff` merge, no conflict). Pushed on his word ("push", the same day): `origin/main` holds the merge. Deployed by the owner the same day (his word; checked from outside: https://affiches.miorantsoa.app/ serves the same three asset names as a build of `main`).** `origin/redesign` holds the same code.
The branch lives in the git worktree `../affiche-ia-worktrees/app` (its own `node_modules`, `.venv`; smoke ports
5273/8100). `redesign-chat` (worktree `../affiche-ia-worktrees/chat`) and `redesign-console`
(`../affiche-ia-worktrees/console`) are merged into it. After the merge the code of `main` equals the branch
(`git diff redesign main -- frontend backend DESIGN.md` is empty); Vitest 313 and the build pass in the main checkout; the
smokes were not run again there (the same tree as the run on the branch). The report: [reviews/app-redesign-after-2026-11-21.md](reviews/app-redesign-after-2026-11-21.md).

**Proof, once on the merged branch:** Vitest 312; the build; all seven browser smokes; backend 1533 passed; 102
captures in `../affiche-ia-worktrees/app/outputs/design-capture/redesign/`.

**The element pass (T-REDESIGN-008, ADR-124), after the owner looked at the running branch.** Looks and positions only.
The owner's rules from it, to keep: search the web for the current practice before designing an element; a card's
content fills its card (narrow the card or the column, never cap the form inside it). What changed is listed in the
TODO entry and in `DESIGN.md` on the branch; the decision and what he may overturn (the dark balance card in the
light theme, « crédits » after the figures, the 64 px thumbnails, the 600 px column of one shop's page) are in ADR-124.
Proof on the final code: Vitest 313, the build, the seven browser smokes; the backend is untouched (no run). No Codex
review of this pass. Not done: the 108 captures were not taken again after the last console fixes; the report
[reviews/app-redesign-after-2026-11-21.md](reviews/app-redesign-after-2026-11-21.md) describes the branch before this pass.

**To look at it running** (stub, no spend, throwaway data; the script writes the sign-in details beside itself):
```
cd ../affiche-ia-worktrees/app/backend
SMOKE_WEB_PORT=5273 SMOKE_API_PORT=8100 uv run python <scratchpad>/dev/dev_serve.py
```
The script lives in a session scratchpad and may be gone: it is `smoke.serve()` on a temporary folder, `vite` in dev
mode on the web port, and `design_capture.seed()` for the data.

**Exact next step: the owner's.**
1. Look at it (from the worktree):
   ```
   cd ../affiche-ia-worktrees/app/frontend && corepack npm@10 run build
   cd ../backend && uv run python ../frontend/tests/design_capture.py look
   ```
   then open `outputs/design-capture/look/sheets/` there.
2. Decide the five points of « For the owner » in the report (placement of « Needs you », the cost sentence, « Images »,
   « Payments », the theme switch in the phone drawer).
3. Done by the owner: the release is live. Open from his first look at it (2026-11-21, not yet tasks): the features warning shows on every scene-adjustment card (« Podium smaller »); on an existing poster an image attached in the chat is labelled « Inspiration » and is not used, and the product photo cannot be changed, in the chat or in « Pas à pas ».

**Open, small (from the `DESIGN.md` rewrite, not yet tasks):** the console's yellow hover is a `color-mix()` (the
shops' app uses `--signal-hover`); the two apps' blur values differ; the console's scrim is a literal; the console's
badge dot may vanish in forced colours; two out-of-date contrast comments in `style.css` (~42, ~843); the console's
top bar has no safe-area inset. Also: the phone bar shows on the « Pas à pas » intake before a poster exists; the
sidebar's « Affiches récentes » shows the state as grey text, not a badge.

**Landmarks:**
- Owner's rule (2026-11-21): run the browser smokes only when product code changed, and only those that cover it;
  the full suite once at the end.
- Rule 1 of the design: nothing with blur, filter, transform or containment between a fixed element and the window
  (the phone's review buttons are fixed from inside the review panel). The window is the page's scroller.
- The worktrees are on disk next to the repo; `redesign` is merged, so they can go on the owner's word
  (`git worktree remove ../affiche-ia-worktrees/<name>`).
- The mockup's local server (port 8777) may still be running from 2026-11-20; it serves only the mockup folder.

## Interface polish — Claude, 2026-11-20 (READ FIRST)

No work order or ClickUp ticket: the user's own project. Goal: the shop's interface and the operator's page read as one product in the Signal identity, with one frame on every screen and no text cut or faint (ADR-122; [requirements](requirements/interface-polish.md) v2, [design](designs/interface-polish.md) v2).

**State: T-POLISH-001 to 005 are done and committed locally on `main`; NOT pushed, NOT deployed** (`git rev-list --count origin/main..main` says how far ahead). **Release 1 itself is live:** the user deployed it on 2026-11-20 (revision `2944ea0`, schema 0017, started 09:30 UTC); Claude read it through the operator dashboard in Chrome the same day: 30 offered credits granted to `originalphone`, the operator password set, 7 posters kept, no failed job. The polish is NOT on the live site.

**What the polish changed** (the proof: [reviews/design-after-2026-11-20.md](reviews/design-after-2026-11-20.md), against [the baseline](reviews/design-baseline-2026-11-20.md)):
- The name and the mark: « Doka Studio » in the tab and the manifest, the kit's icons, the operator's mark (in its own stylesheet: its page still asks the server for nothing but its own files).
- The amber accent is gone: `--signal` (`#f2c744`) is a fill, always under `--on-signal`; `--hue` is every ring, border and progress mark (an ochre, `#8f6b00`, in the light theme). The main button stays charcoal; the dark greys stay.
- One frame for Accueil, Mes affiches, Styles, Mes crédits and Mon compte: `.page-title`, `--page: 860px`, a 16 px phone gutter. The phone's bottom bar shows « Affiches » and the credits as a number alone; the accessible names keep the full words. One hidden title for the chat route.
- `DESIGN.md` at the root records the system as built. `frontend/tests/design_capture.py` takes the 102 captures again.

**Also done, 2026-11-20: a mockup of both entries** ([mockups/doka-console/](mockups/doka-console/README.md), T-MOCKUP-CONSOLE): the shops' app (chat first, sidebar, glass) and an operator console with a collapsible sidebar, on one stylesheet, in the Signal kit's colours as given. It shows a yellow main action, the dark theme on the kit's charcoal and a new phone bottom bar, three things ADR-122 held back: the owner's verdict decides whether the app follows. Serve it with `python3 -m http.server 8777 --bind 127.0.0.1 --directory docs/project/mockups/doka-console`.

**Exact next step: the user's.** Nothing is in progress.
1. Look at the polish locally before any deploy: from `frontend/`, `corepack npm@10 run build`; from `backend/`, `uv run python ../frontend/tests/design_capture.py look`, then open `outputs/design-capture/look/sheets/`.
2. Decide the six points of « For the owner » in the after report (the typeface, a yellow main button, the dark ground, « Affiches » and the bare number in the phone bar, two new titles for screen readers, the name typed beside the mark).
3. Then, on his word only: push, and deploy as an ordinary release (`cd deploy; pyinfra 89.167.56.26 deploy.py --user deploy -y`; no migration, so the rehearsal has nothing to run; never `OPERATOR_BOOTSTRAP` again).
4. Still his from Release 1: the purchase text (the dashboard's Service screen: none set, shops read the fallback with his e-mail address), the phone sheet of « Partager » on the live site before inviting shops (ADR-121), the French texts.

**Landmines:**
- The smokes share ports 5173 and 8000 and `frontend/dist`: one at a time, and never while `design_capture.py` runs. A subagent told to wait for the lead's smokes with a background watcher stayed idle 45 minutes: make it wait in the foreground.
- Tests now read stylesheets as text (`vite.config.ts`, `test: { css: true }`): before, Vitest handed them over empty, and `admin.test.ts`'s isolation rule had never seen `admin.css`.
- `--hue` is a line, `--signal` a fill: a yellow line on paper is 1.4:1. `check_marks` and `check_contrast` in `browser_smoke.py` measure what is painted; when one fails on a changed screen, fix the CSS.
- A page title takes the focus on arrival; its underline needs `:root[data-keys]` (set in `main.ts` on a key press). Without it every page opened directly shows an underlined title: a browser counts a script's focus as the keyboard's until the first tap.
- Review state: the design's v2 was not reviewed again after v1's REJECT; the last fixes of T-POLISH-002 and 003 and the lead's two fixes in T-POLISH-005 were not reviewed by Codex; T-POLISH-001 and 004 were not reviewed as code.
- `.impeccable/design.json` (the sidecar of `DESIGN.md`) and `PRODUCT.md` are uncommitted: they sit with the other session's files. Claude edited `PRODUCT.md` on 2026-11-20 (`/impeccable init`: Release 1 live, « Partager », the conditions, the channels).
- Proposed, not confirmed: T-POLISH-BORDERS (control borders at about 1.2:1), T-POLISH-MOTION (what still moves under reduced motion, forced colours).

## Release 1 « Invitation » — Claude, 2026-11-19 (READ FIRST for Release 1)

No work order or ClickUp ticket: the user's own project. Goal of the release: open Doka Studio to a few invited shops as a prepaid service ([ROADMAP.md](ROADMAP.md), ADR-105).

**Every build task of Release 1 is done, pushed to `origin/main` (2026-11-19) and deployed by the user on 2026-11-20** (see the section above for what Claude read on the live site):
- Multi-shop (ADR-108), prepaid balance (ADR-109), T-SHOP-REPLACE (migration 0015).
- Admin dashboard core T-ADMIN-001 to 007 (ADR-110, migration 0016) at `/admin/`. T-ADMIN-008 to 010 come after Release 1 (ADR-111).
- Conditions of use T-TERMS-001 to 004 (ADR-112, migration 0017): acceptance, the server gate, the dialog, the warning, « Vos données ».
- Shop dashboard T-SHOP-DASH-001 to 011 (ADR-114 to 119; built by the Codex session).
- « Partager » T-SHARE-002 to 004 (ADR-120; design `designs/share-poster.md` v3): a poster opens on its current confirmation (`confirmation` on `GET /api/creations/{id}`, no migration); the caption kept on the device; a JPEG made in the browser and shared through the phone's share sheet, the caption copied in the same tap. The last migration of the release is still 0017.

**Last verified on this Linux machine (stub, zero spend, SQLite 3.53.1), 2026-11-19:** frontend Vitest 294 and the build; `share_browser.py`, `browser_smoke.py`, `chat_browser.py`, `terms_browser.py` pass on the final code; backend 1533 passed, 3 deselected (before the frontend-only « Partager » tasks).

**Exact next step: the owner's work, then the release.** None of it can be done by an agent alone:
1. **T-SHARE-005 moves after the release (ADR-121, the owner's choice: no Android phone at hand).** The empty sheet is `reviews/share-poster-phones-2026-11-19.md`; he fills it on the live site with any phone, on a poster already confirmed (nothing paid), and invites new shops only once rows 1 and 3 work (deploy/README.md). Each failure becomes its own follow-up task. R-SHARE-005 stays open until then. T-SHARE-001 is moot.
2. **Read the French texts** (all drafts): the conditions in `backend/src/affiche/posters/terms.py` `PARAGRAPHS_FR` (a changed word needs a new `VERSION` and its hash in `tests/test_terms.py`), the refusal sentences, the dialog, the warning's lead-in, « Vos données », the « Partager » sentences (the table in `designs/share-poster.md`), the message to the pilot in `deploy/README.md`.
3. **T-DEPLOY-DOCKER-RUN is done** (2026-11-19, on this laptop's Docker, reached with `sg docker`; [report](reviews/t-deploy-docker-run-2026-11-19.md)): the pilot's `0e5fa64` started, `release.sh` released `2944ea0` over its 0012 database (rehearsal 0013 to 0017 OK on SQLite 3.40.1), a hung backup hit the real `timeout` and the old container came back, `restore.sh` brought a backup taken by the old code before 0013 to 0017 and the pilot's password signs in after it, no operator password reached the journal. Left for the box: the rehearsal on the pilot's real rows (the release gate does it) and `verify.sh`'s second half.
4. **The release, by the user only:** push; one deploy with `OPERATOR_BOOTSTRAP=1`; `python -m affiche.shops operator-password`; `verify.sh` by hand; set `SUPPORT_CONTACT_FR`; `grant originalphone 30 --offered --ref pilot-opening`; `purchase-text`; warn the pilot (draft message in `deploy/README.md`); the phone sheet (item 1); then invite shops telling them to open the link in Chrome, not inside Messenger or Facebook.

**How this session works (the user's standing rules):** the lead passes requirement and design gates himself; Claude-led work uses Opus subagents (`model: "opus"`), Codex-led work GPT implementers (ADR-115); every artifact gets a Codex review (`codex exec --sandbox read-only`, at most three rounds, then the user decides); local commits only; push and deploy only on the user's word.

**Owner decisions waiting (defaults in force):** listed at the end of each design (`admin-dashboard.md`, `service-terms.md`, `prepaid-balance.md`, `share-poster.md`: caption on this device only, 2 000 characters, the clipboard may hold the caption after a cancelled share, iPhone rows, the probe) and under T-BALANCE-006 in TODO.md. Proposed, not confirmed: T-SESSION-REPLACE.

**Landmines:**
- Memory: this machine runs a 6 GB virtual machine, VS Code, Teams and Postman; swap is often full. Run one test or smoke at a time and check `free -m` (the "available" column) first; never restart a run the system killed without the user's word. Smokes with fixed 10 s waits have failed under load and passed on rerun (T-SUITE-FLAKE in TODO.md lists them).
- Not proven: the migrations on the pilot's real rows (the release gate rehearses a copy on the box); `deploy.py` and `verify.sh`'s box half (neighbours, Caddy, cron); a real phone, a screen reader; a real app switch during a share (headless Chromium never hides the page; the smoke simulates it).
- Review state: the last fixes of several tasks were not reviewed again (the TODO entries say which); T-SHARE-002 had three REJECT rounds, its four last findings fixed on the owner's choice without a fourth; T-ADMIN-006 has one accepted cross-tab limit (ADR-111).
- « Partager »: the final panel's preview is one object, and `frontend/src/share.ts` holds the one rule for what is presented as current (`presentedAsCurrent`); never add a second path that shows a price beside an image without it.
- The admin page: the shops' built files must stay byte-identical when only the admin page changes, and `dist/admin` byte-identical when only the shops' page changes (`sha256sum` before and after, from `frontend/`).
- No erase command exists; « Vos données » must not promise one (ADR-112).
- The checkout is shared with a Codex session: its uncommitted work (PROJECT.md, PRODUCT.md, `.impeccable/`, `brand/`, the mockups, the social-publishing research, and its older hunks in DECISIONS.md, TODO.md and this file) is never staged with Claude's commits. For a shared file, stage only Claude's lines: `git show HEAD:<path>`, apply the edit, `git hash-object -w --stdin`, `git update-index --cacheinfo 100644,<sha>,<path>`, and the same edit in the working file.
- Old Codex processes from about 2026-11-14 (a `pytest tests/test_editor_refinements.py` and two python heredocs under `codex-linux-sandbox`) were still running on 2026-11-18; safe to stop if that session is gone.

## Mobile dashboard critique · 2026-11-18

T-IMPECCABLE-DASH-CRITIQUE complete. [Mobile critique](../../.impeccable/critique/2026-11-18T14-24-13Z__frontend-src-shophome-vue.md) records the first baseline, 26/40. Local mobile Chromium reproduced silent loss of unsaved shop details. Clarifying pending and negative credits is the other pre-release priority. Owner selected all five findings and chose a keep-editing/discard prompt. T-SHOP-DASH-AMEND drafted R-SHOP-DASH-005 through 009 in requirements/shop-dashboard.md and updated requirements/_INDEX.md. Owner approved all five criteria groups. T-SHOP-DASH-MOBILE-DESIGN drafted the v4 amendment in designs/shop-dashboard.md. Owner approved v4 (ADR-119). T-SHOP-DASH-006 through 011 are implemented locally. The exact clean Account → failed Styles → edit → Back regression failed on old assets and passed after fixing the history anchor. Owner authorized closure after checks. Independent review approved 007–011 after correcting stale balance notices during retry and keeping the shared header out of the mobile editor. Final build, 262 Vitest tests, full dashboard Chromium, 10 dashboard backend tests and 1,531 full backend tests passed (3 deselected). A broader chat regression caught the 360 px creator growing to two rows after review. A CSS adjustment keeps the product name inside the brand control and restores the original single-row height. Build, all 262 frontend tests, dashboard and full chat Chromium passed on the final layout. Terms, editor/gallery, editor refinements and operator Chromium passed before that compact-creator-only adjustment. Next dashboard release checks are a physical phone, screen reader and owner French copy reading.

Uncommitted implementation files are backend/src/affiche/api.py, backend/tests/test_shop_dashboard.py, frontend/src/{App.vue,ShopAccount.vue,ShopCredits.vue,ShopHome.vue,dashboard.ts,style.css}, frontend/src/assets/{doka-horizontal.svg,doka-horizontal-reverse.svg,doka-symbol-small.svg} and frontend/tests/{browser_smoke,shop_dashboard_browser}.py. Review records are docs/project/reviews/t-shop-dash-006-code-r{1,2,3}.md and t-shop-dash-007-011-code-r{1,2,3}.md. The first five dashboard tasks above describe the original release slice. Additional uncommitted documents include designs/{shop-dashboard,_INDEX}.md and the approval in DECISIONS.md. Both requirements files are uncommitted alongside the files listed below. The Partager requirements gate remains pending. Real phone, screen reader and owner copy checks remain open.

This review added the uncommitted critique snapshot and updated TODO.md and HANDOFF.md. Other uncommitted work includes PRODUCT.md, .impeccable/config.json, docs/project/{PROJECT,DECISIONS}.md, brand, mockups and the social-publishing research listed above.

## Impeccable initialization

T-IMPECCABLE-INIT complete. New uncommitted PRODUCT.md and .impeccable/config.json carry confirmed positioning and workflow preference. Verified local evidence links, schema marker, platform and JSON. Workflow changes in TODO.md, DECISIONS.md and this handoff accompany the earlier uncommitted files listed above. The dashboard critique can now use this context; the release next step remains the Partager requirements gate.

## Impeccable installation

The user requested installation. The Codex skill installer installed upstream pbakaus/impeccable at d41d9860 in ~/.codex/skills/impeccable. SKILL.md and both critique and harden references verified. Available next turn. Release next step and prior uncommitted files are listed above. This installation entry updates TODO.md and HANDOFF.md.

## Codex Impeccable skill assessment — 2026-11-17

**Done:** T-IMPECCABLE-REVIEW, an opinion request about https://impeccable.style/. Reviewed official website/repository, the actual Codex SKILL.md and critique/harden playbooks, Live-mode docs and configuration; compared local frontend-design and design-taste skill text. These files were evaluated as reference material, not invoked to audit or edit Doka. No install, binary execution, hook changes, subagents or app audit.

**Assessment:** useful as a focused design critique/refinement tool. The skill explicitly prioritizes the existing brief and distinguishes expressive marketing from restrained task-oriented app screens. Preserve Doka's chosen Signal palette/type/logo; useful commands cover critique, accessibility/technical audit, typography, UX copy, hardening and polish. Its benefit over the current design skills is the organized playbooks and detector feedback, not a guaranteed improvement in taste. It can complement UI SDK or Reka components; it is not a replacement component library. The agreed Reka UI trial remains unchanged.

**Caveats:** detector findings are heuristics, not proof of user success or accessibility. Critique is a substantial workflow (two isolated assessments plus detector/browser evidence and persistence, with an explicit Codex subagent permission step); do not assume it is a lightweight pass. PRODUCT.md/DESIGN.md should align with current project/brand truth, not create another conflicting source of requirements. The official README documents Live copy Apply falling back to codex/claude with approvals/sandbox disabled if no active chat is polling; it documents `IMPECCABLE_LIVE_COPY_AGENT=chat` or `off` to avoid that fallback. This was discovered in documentation; it was not executed or penetration-tested.

**Exact next step:** assessment delivered; no active task or pending approval. Recommendation only: evaluate a bounded existing screen, preserving project gates and the Signal brief, before adopting commands/hooks. No app changes, install, tests, commit, push or deploy for this task. Concurrent Release 1 work is untouched.

**Sources:** [actual Codex skill](https://github.com/pbakaus/impeccable/blob/main/.agents/skills/impeccable/SKILL.md), [critique playbook](https://github.com/pbakaus/impeccable/blob/main/.agents/skills/impeccable/reference/critique.md), [harden playbook](https://github.com/pbakaus/impeccable/blob/main/.agents/skills/impeccable/reference/harden.md), [official repository/Live disclosure](https://github.com/pbakaus/impeccable), [command docs](https://impeccable.style/docs/).

**Files changed by this assessment:** TODO.md and this HANDOFF only. Uncommitted snapshot (other agents may change it):

```text
 M backend/api/README.md
 M backend/src/affiche/admin.py
 M backend/src/affiche/api.py
 M backend/src/affiche/posters/reads.py
 M backend/src/affiche/posters/store.py
 M backend/src/affiche/shops.py
 M backend/tests/test_admin.py
 M deploy/README.md
 M docs/project/DECISIONS.md
 M docs/project/HANDOFF.md
 M docs/project/PROJECT.md
 M docs/project/TODO.md
?? docs/project/brand/
?? docs/project/mockups/brand-directions/
?? docs/project/mockups/doka-studio-identity/
?? docs/project/mockups/text-first/
?? docs/project/reviews/social-publishing-saas-research-2026-11-15.md
```


## Codex UI SDK assessment — 2026-11-16

**Done:** T-UI-SDK-REVIEW, answering the user's opinion request about https://ui-sdk.dev/. Read the official Vue introduction/installation, styling, agent bridge/permissions and benchmark, changelog, repository and package metadata; compared `frontend/package.json`. No adoption or implementation requested.

**Assessment:** promising for selectively building Signal-styled controls. The Vue package requires >=3.5; the app pins 3.5.45. Unstyled components/interaction behaviors leave visual design to Doka. Candidate trials: shop/Page selector, ordered poster selection, attachment input or dialogs. Keep existing Konva document/rendering behavior and domain validation separate from UI primitives. The optional agent bridge is a distinct capability; it does not supply Doka's chat intelligence or persistence. Avoid equating direct UI actions with authorization for generation spend, publication or purchases. The docs explain its allow callback/defaults and confirmation annotations.

**Limits:** beta; changelog introduction dated November 12, 2026. Public benchmark is a vendor-reported settings task with three runs per column, comparing its bridge with browser tooling; it does not establish speed/cost gains for Doka. Some direct docs opens initially failed; subsequent linked navigation loaded the Vue installation and changelog. No packages/skills installed; no runtime integration, bundle measurement, mobile/keyboard/accessibility verification, app tests, commit, push or deploy.

**Exact next step:** opinion delivered; no active task remains. If the user requests an evaluation implementation, scope one component and follow requirements/design/task gates before application changes. This recommendation is not an architecture/adoption decision. All concurrent tracks remain untouched.

**Sources:** [Vue setup](https://ui-sdk.dev/docs/vue/installation), [agent capabilities/benchmark](https://ui-sdk.dev/docs/agents), [permissions](https://ui-sdk.dev/docs/agents/connect-an-agent/permissions), [changelog](https://ui-sdk.dev/docs/core/changelog), [repository](https://github.com/vercel-labs/ui).

**Files changed by this assessment:** TODO.md and this HANDOFF only. Current uncommitted snapshot (other agents may change it):

```text
 M docs/project/DECISIONS.md
 M docs/project/PROJECT.md
 M docs/project/TODO.md
?? docs/project/brand/
?? docs/project/mockups/brand-directions/
?? docs/project/mockups/doka-studio-identity/
?? docs/project/mockups/text-first/
?? docs/project/reviews/social-publishing-saas-research-2026-11-15.md
```


## Codex Doka Studio — Signal kit v1 delivered, 2026-11-15

**User decisions:** Doka Studio is the selected brand name; Signal is the chosen identity direction. The user then said **“go”** to the offered final logo kit, authorizing Phase 7 of the invoked logo-design skill. PROJECT.md metadata records the delivered digital kit; application code and technical identifiers remain as before for this track. Claude’s Release 1 changes below are independent and must be preserved.

**Done:** T-DOKA-SIGNAL-KIT. [Kit README](brand/doka-studio-signal/README.md), [visual overview](brand/doka-studio-signal/preview.html), [PNG overview](brand/doka-studio-signal/preview.png), [portable ZIP](brand/Doka-Studio-Signal-v1.zip). Horizontal, stacked, name-only and symbol layouts in charcoal/black/paper/white; nine masters, 16 digital SVG variants, two web SVGs, transparent PNGs, 16/32/48 ICO, Apple and PWA/maskable icons, bundled Space Grotesk/Noto Sans fonts with SIL OFL notices, palette metadata, six-context presentation and compact French usage guide. Archive: 77 files, 1,830,320 bytes, SHA256 `4322954545bec49cd8182e896fc6386d53d2d2e5ed95609f0513e5cf3cf2d4ab`.

**Refinements:** preserved the selected cut-corner D and bold wordmark; reverse counter grows by one source unit to reduce apparent weight; small artwork enlarges the same simple silhouette. Yellow-backed favicons remain visible on light and dark browser chrome. Platform icons have opaque backgrounds and safe masking space. Screen minima: 220 px horizontal, 160 px stacked/name-only, 16 px favicon. Print minima/CMYK numbers are provisional, without invented Pantone equivalents.

**Verified:** two exact-artwork proofs, native 16/20/24/32/48/64/96 px samples, reverse/circle crops, exported icon sheet and mobile preview inspected. Assertions in `outputs/doka-signal-kit-2026-11-15/verify_kit.py` passed: 27 outlined SVGs without raster/text/effects, 33 PNG files, transparent counters/lower reverse ink coverage, dimensions/ICO sizes, maskable ink radius 166.39 px inside the 204.8 px safe circle, French glyph/licence metadata, 51 relative links, contrast 10.13:1 and 14.49:1, preview at 1400 and 390 px without overflow, missing images/fonts or page errors. Master audits 90–100 with no FAIL; outlined-font angles/complexity, small-symbol precision and a deliberately raised stacked composition are documented notices. ZIP CRC and 76 content hashes match. Evidence is in `brand/doka-studio-signal/checks/`; the kit contains SHA256SUMS.txt.

**Exact next step:** this asset deliverable is complete; no brand task remains in progress and no approval is pending. A separately requested app integration should follow applicable project requirements/design/task gates and coordinate with Release 1. Do not deploy or silently change app branding as part of asset delivery. No commit, push, deploy, application tests or production access was performed for this task.

**Landmines:** name/domain/trademark clearance and physical print proof remain open. RGB vectors are digital artwork, not certified CMYK/Pantone files. The generated exploration boards are illustrative and not logo masters. Presentation contact/handle/domain examples are placeholders. The manifest/head snippet needs real app paths and merging; it does not implement offline/PWA behavior. Do not force Doka’s colors or logo into customer posters. White text on Signal yellow fails; use charcoal. Icon tiles and transparent artwork serve different uses; keep their export choices intact.

**History:** T-BRAND-CONCEPTS, T-BRAND-DOKA, T-DOKA-IDENTITY and T-DOKA-SIGNAL-CHOICE are complete. [Earlier identity studies](mockups/doka-studio-identity/README.md) and [four-name comparison](mockups/brand-directions/README.md) are retained. Earlier Affisoa/Saryko/Vitraka recommendations are superseded. Exact build/export/verification scripts, two proofs and archive verification are in git-ignored `outputs/doka-signal-kit-2026-11-15/`. No new imagegen call was needed for the exact vector kit; the earlier generated boards remain untouched.

**Files changed by this task:** new `docs/project/brand/` kit and ZIP; updates to PROJECT metadata, the identity exploration README, TODO, DECISIONS and this HANDOFF. Other source/test changes are concurrent work, not this task. No task-owned app changes were made.

**Uncommitted snapshot** (other agents may change it after this note):

```text
 M backend/src/affiche/api.py
 M backend/src/affiche/config.py
 M backend/src/affiche/posters/auth.py
 M backend/src/affiche/shops.py
 M backend/tests/test_api.py
 M backend/tests/test_config.py
 M backend/tests/test_phone_session.py
 M backend/tests/test_reads.py
 M deploy/verify.sh
 M docs/project/DECISIONS.md
 M docs/project/PROJECT.md
 M docs/project/ROADMAP.md
 M docs/project/TODO.md
 M frontend/src/App.vue
 M frontend/src/api.ts
 M frontend/tests/api.test.ts
 M frontend/tests/browser_smoke.py
 M frontend/tests/chat_browser.py
 M frontend/tests/editor_refinements_browser.py
?? backend/tests/test_shops.py
?? docs/project/brand/
?? docs/project/mockups/brand-directions/
?? docs/project/mockups/doka-studio-identity/
?? docs/project/mockups/text-first/
?? docs/project/reviews/social-publishing-saas-research-2026-11-15.md
```


## Codex publishing and SaaS research — 2026-11-15

**Done:** T-SAAS-RESEARCH, T-SAAS-VERIFY and T-PAPI-RESEARCH; research plus user-authorized local verification, no application implementation. Deliverable: [Social publishing and SaaS research](reviews/social-publishing-saas-research-2026-11-15.md). The user confirmed **Madagascar** as the selling business country and **ordinary posts first, paid ads later**. No implementation or scope expansion approved. Claude's chat work remains independent.

**Findings/proposals:** app-owned Meta credentials with customer authorization; connect existing Pages/professional accounts (actual Facebook Page creation is restricted); compose captions and ordered exact approved exports; local history and per-destination outcomes, including unknown/partial results. Current Meta docs recommend Unified Login with a business portfolio, support 20-item Instagram carousels and require JPEG publishing derivatives; their day-quota examples conflict, so validate the chosen route/version rather than hardcode those numbers. Public customer access depends on Meta review/verification. SaaS needs account/workspace/brand/channel separation, an atomic customer-credit ledger separate from provider costs, one lifetime trial grant, bounded abuse exposure and separate customer/operator dashboards. Papi hosted checkout is now the first local prepaid candidate (added on the user’s suggestion), with direct MVola as a cost/settlement comparison and Paddle as an optional international candidate; Stripe does not list Madagascar merchant support. No merchant approval obtained.

**Verified update:** user authorized necessary verification and confirms **no provider accounts have been set up**. Targeted existing suites: **125 passed in 81.16 s** (39 admission, 25 poster jobs, 22 exports, 34 API, 5 backup), exit 0. Isolated temporary data, fake/stub providers, `env_file=None`; `backend/.env` was never read. Synthetic Pillow 13.0.0 PNG-to-JPEG probe passed RGB/sRGB, dimensions, byte limits and alpha flattening; feed/square meet the documented feed ratio, story does not. Artifacts: `outputs/saas-verification-2026-11-15/` (git-ignored). See the report's [verification addendum](reviews/social-publishing-saas-research-2026-11-15.md#verification-addendum-of-2026-11-15). These checks do not prove the unbuilt wallet, multi-tenancy or social integration. No real publishing/listing, payment sandbox, merchant approval, paid call, production access, commit, push or deploy. Frontend build/smokes not rerun; running services on 8000/5173 left alone. Postman CLI remains unavailable.

**Provider follow-ups:** Meta Unified Login setup adds app/business-portfolio, HTTPS callback, real professional-account and permission conditions; compare its actual consent burden with Instagram Login before selecting it. Paddle's supplier-policy search result suggests candidacy, but direct fetch returns 404: Madagascar seller/payout eligibility is unverified. Create/configure provider test accounts first, then run authenticated Meta ordering/listing/recovery and merchant sandbox fulfillment checks. Public API documentation and local tests cannot substitute for them.

**Papi research update:** [addendum](reviews/social-publishing-saas-research-2026-11-15.md#papi-assessment-added-on-2026-11-15). Hosted checkout covers mobile money and cards; direct/transit modes documented. Published fees: Direct 1.20% plus operator/bank fees; Transit MVola 3.80%, Orange/Airtel 3.60%, cards 4.20% (including tax; confirm settlement terms). Local reproduction of the public HMAC vector matched; changed body changed signature. Public demo catalogue/add request returned 200, but cart navigation/payment was not completed. No production payment, account creation, callback endpoint or app code. API link deduplication is only for active links, and callbacks are automatically sent once: permanent local fulfillment and read-back reconciliation are necessary in the eventual design. Recurring debits, merchant acceptance, settlement details and refund operations remain unverified. Evidence in git-ignored `outputs/papi-research-2026-11-15/signature-vector.json`; temporary demo browser state removed.

**Exact next step for this track:** provider account setup is needed for live integration verification; separately, user chooses/approves the proposed scope expansion and priorities before per-feature requirements with acceptance criteria. Proposed boundaries: accounts-workspaces, credits-billing, trial-abuse, social-publishing, customer-dashboard, platform-operations. Requirements approval precedes formal designs and implementation tasks. No task in this track remains in progress.

**Landmines:** never assume Facebook sign-in grants publishing; never expose tokens/private libraries; never blindly retry an ambiguous post; copying/deleting/new workspaces must not replenish trial credits; restoring a backup must not repeat payments, credits or publications. Existing invented-product-features gap is a prelaunch concern. Prepaid publishing/retention limits and final prices still need decisions.

**Files changed by this research:** this HANDOFF, TODO, DECISIONS and the new research report. Other modified source/docs and the old mockup are from concurrent/earlier work. Snapshot of all uncommitted paths at handoff (another agent may change this list afterwards):

```text
 M backend/src/affiche/api.py
 M backend/src/affiche/posters/reads.py
 M backend/tests/test_reads.py
 M docs/project/DECISIONS.md
 M docs/project/HANDOFF.md
 M docs/project/TODO.md
 M docs/project/designs/text-first-generation.md
 M docs/project/requirements/text-first-generation.md
 M frontend/src/App.vue
 M frontend/src/ChatView.vue
 M frontend/src/chat.ts
 M frontend/tests/chat.test.ts
 M frontend/tests/chat_browser.py
?? docs/project/mockups/text-first/
?? docs/project/reviews/social-publishing-saas-research-2026-11-15.md
```


## Roadmap and Release 1 requirements — 2026-11-15, latest (READ FIRST)

**The release rule (user, ADR-105): nothing is deployed until Release 1 « Invitation » is complete: several shops by invitation, a prepaid balance, a dashboard per shop and an administration dashboard.** The chat work already on `origin/main` stays undeployed; the pilot stays on the version of 2026-11-14. Do not offer a deploy before then.

**Done, NOT committed:** [ROADMAP.md](ROADMAP.md); six requirement files, Draft v1 with working defaults, no design (`requirements/multi-shop.md`, `prepaid-balance.md`, `admin-dashboard.md`, `service-terms.md`, `shop-dashboard.md`, `share-poster.md`); `requirements/_INDEX.md`; a scope-change note in PROJECT.md; ADR-105; T-SAAS-ROADMAP in TODO.md.

**Since then (user: "You have the autonomy, start with what you consider more important", ADR-106):** `requirements/multi-shop.md` approved and amended; [design multi-shop v4](designs/multi-shop.md) approved under the grant (ADR-107) after three review rounds and a devil's advocate (reviews/multi-shop-design-*.md). Six tasks T-MULTI-SHOP-001 to 006 are in TODO.md. **001 to 004 are done and committed locally** (the migration, the password in the database, the rehearsal; sign-in by identifier, bundle 3; the two-shop route test in the suite, spend per shop, the status view for the operator only; the daily provider-spend ceiling per shop, the fair queue, reads under the same guard, the password-change route); 005 is in progress with an Opus subagent; 006 is not started.

**T-MULTI-SHOP-005 is done and committed locally (2026-11-16):** suspension stops calls where they are sent, the operator command `python -m affiche.shops`, `deploy/release.sh` (rehearsal gate, backup under a deadline, the old container started again on a failure), `deploy/restore.sh` (never starts the service), the `operator` service of `deploy/compose.yml` (no log, no network), the runbooks. Three Codex rounds, all REJECT; the last round's three findings were fixed after it on the user's word and not reviewed again (TODO.md has the detail).

**T-MULTI-SHOP-006 is done and committed locally (2026-11-16): the multi-shop feature is built.** The browser has one identity gate, a cross-tab lock on sign-in and sign-out, storage keys per shop, and a sign-out that keeps nothing on the device: the kept paid card was removed after four rejected reviews (user decision, ADR-108; the server is the authority for a paid request; R-MULTI-SHOP-004 amended). Round 5 approved with fixes; those fixes were not reviewed again. TODO.md has the detail, the accepted limits and one French sentence the user has not yet approved.

**The prepaid balance is designed and approved (2026-11-16, ADR-109):** [design v4](designs/prepaid-balance.md), requirements approved with its amendments, three Codex rounds (REJECT, REJECT, APPROVE WITH FIXES) and a devil's advocate in `reviews/prepaid-balance-*`. The job is the debit: balance = the operator's lines (`credit_grants`) minus the shop's image jobs that took a credit and are queued, running or succeeded. The round-3 fixes are in v4 and were not reviewed again as a design; each task's code review checks its own. The pilot gets 30 offered credits typed by hand right after the release (user decision).

**Exact next step:** T-PENDING-KINDS (a small fix of a live bug), then T-BALANCE-001 to 006 in order, each with an Opus subagent and a Codex code review (TODO.md has the verify lines). After the balance: administration dashboard (its design gets a Reka UI trial, user ok 2026-11-16), conditions of use, shop dashboard, « Partager ».

**Landmine:** one run had both browser smokes fail and three later runs on the same code passed (T-SUITE-FLAKE). Run them again before believing a failure, and do not run two sessions' smokes at the same time.

**Not pushed:** `main` is ahead of `origin/main` by every commit since the roadmap (the roadmap and requirements, the multi-shop design, T-MULTI-SHOP-001 to 006, handoffs). Push on the user's word only; no deploy (ADR-105).

**Uncommitted files, all Codex's, not to be staged by Claude:** `docs/project/DECISIONS.md` and `docs/project/PROJECT.md` (brand edits), `docs/project/brand/`, `docs/project/mockups/brand-directions/`, `docs/project/mockups/doka-studio-identity/`, `docs/project/mockups/text-first/`, `docs/project/reviews/social-publishing-saas-research-2026-11-15.md`.

**Waiting on the user:** whether to keep T-DEPLOY-DOCKER-RUN; what the image may write (R-TERMS-002); the pilot's identifier `originalphone` (changeable in migration 0013 until it first runs on a real database); welcome credits (default 5); a first price to test.

**Landmine:** the deploy scripts and the operator service have run with a fake docker only. T-DEPLOY-DOCKER-RUN (proposed, not confirmed by the user) asks for one real run on a throwaway host before the Release 1 deploy.

**Landmine:** the backend suite failed once on 2026-11-16 with one test whose name was not captured, and passed on every run since (T-SUITE-FLAKE). Run it with `-rf`.

**The product is named « Doka Studio », identity « Signal » (user, 2026-11-15).** The final kit is in `docs/project/brand/doka-studio-signal/` (Codex's, uncommitted). It is applied when the screens are built: T-BRAND-DOKA in TODO.md. Posters never get the Doka logo. Local commits only; push on the user's word; no deploy (ADR-105). Still the user's: what the image may write (R-TERMS-002); the pilot's identifier `originalphone`.

**Landmines:** the audit's two-shop test is git-ignored in `outputs/saas-review-2026-11-15/`; it must enter `backend/tests/` with multi-shop. Subagents run on Opus (the user's rule). The requirements do not follow `_TEMPLATE.md`'s GIVEN/WHEN/THEN wording; they keep the checklist style of `text-first-generation.md`.

## Claude's review of the SaaS research — 2026-11-15

**Done, NOT committed:** [review](reviews/saas-review-claude-2026-11-15.md) of Codex's [research](reviews/social-publishing-saas-research-2026-11-15.md) (T-SAAS-REVIEW in TODO.md). Research only; no application code changed; no paid call. Uncommitted: the review file, `docs/project/TODO.md`, `docs/project/HANDOFF.md`. Codex's research file is still untracked and is Codex's to commit.

**Exact next step:** the user's five decisions at the end of the review (the order of work; sharing before publishing; invented features before other shops; starting Meta's business verification; changing PROJECT.md, which excludes all of this). Nothing is to be built before he changes the charter and requirements are approved.

**Landmines:** the audit's two-shop test is git-ignored in `outputs/saas-review-2026-11-15/` and is not part of the suite; its browser-storage finding is from reading. The Meta and market facts were gathered through fetch tools on 2026-11-15; Meta's business help pages could not be read.

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

**T-CHAT-LIST-LABEL done**, committed and pushed (commit "T-CHAT-LIST-LABEL: …"): a version made by a chat card from an older one is labelled by its difference with that version (`replaces_visual_id` on the scene job and on the version).

**T-CHAT-D005-TESTS done, T-CHAT-REDO dropped, T-CHAT-SCENE-FIELD done (ADR-102); committed and pushed (commit "T-CHAT-SCENE-FIELD, T-CHAT-D005-TESTS: …").** On a poster, a message that changes no word now goes whole, in the owner's words, to the scene adjustment (« Ajustement de la scène » of « Réglages »); its screen is one function and wider (in the step editor too); a refinement repeats the adjustments asked before on its chain. Paid test: 15 of 15 reads, five real adjustments, USD 0.2542 ([report](reviews/chat-change-eval-2026-11-15.md), last section). [Audit of what the chat cannot do yet](reviews/chat-capability-audit-2026-11-15.md). **Review of T-CHAT-SCENE-FIELD:** three rounds rejected on wordings past the list of phrasings (`screen_adjustment` in `backend/src/affiche/posters/plans.py`); the user then chose to add the reader's judgement as a second screen in the chat (`commercial` in the reader's answer); round 4 on that design: APPROVE WITH FIXES, its fix applied (reviews/t-chat-scene-field-code-r1.md to r4.md). Paid test of the second screen: USD 0.0563, 18 of 18.

**Uncommitted:** only Codex's old `docs/project/mockups/text-first/` (untracked). Final check before the commit, Linux, stub: backend 1004 passed / 3 deselected.

**Landmine:** the user's note of 2026-11-15, "just noted": the image model invents the features it draws when asked for "4 lines of features" (AGENTS.md forbids invented specifications; the check's extra-text point is the only guard). Do not present this as verified product facts.

**The rest of the audit (user request, later the same day, then "you can go full automation"): built, committed locally, NOT pushed.** A first design was rejected in review and by the devil's advocate; a paid baseline showed that a coloured word and the brand's lettering already work as scene adjustments; what was built is D-TEXT-FIRST-006 v2 (ADR-103): a style change on a poster (card kind `restyle`), the shop's logo and contact asked in the first message, one sentence to « Pas à pas » for identity on an existing poster and for another format, and a guard that refuses every change from an older open tab (`X-Affiche-Bundle`, 409 `bundle_outdated`). Tasks T-CHAT-REST-001 and 002 in TODO.md; reviews in reviews/t-chat-rest-001-code-r*.md; paid results in reviews/chat-change-eval-2026-11-15.md.

**Landmine for the next deploy:** the bundle now on the pilot is refused on every change by this backend until the page is reloaded (« Cette page est une ancienne version… »), in « Pas à pas » too. Backend and frontend go out together; an open tab must be reloaded after it. Raise `BUNDLE` in `frontend/src/api.ts` and `backend/src/affiche/api.py` together when a later change makes an older tab unsafe.

Spend of the day for this work: USD 0.8574, all on the ledger. `backend/data-probe` has fifteen versions of the JBL product, one copy of its poster and one more poster made by the last test.

**Pushed** on the user's word (`origin/main` holds the commit "T-CHAT-REST-001, T-CHAT-REST-002…").

**T-CHAT-PRICE-NO-COMMA done**, committed and pushed (commit "T-CHAT-PRICE-NO-COMMA: …"; ADR-104): « iPhone 15 1 200 000 Ar » now gives its price. Backend 1019 passed / 3 deselected; four real reads right (USD 0.0108). Spend of the day for this work: USD 0.8682.

**T-CHAT-CANVAS-LOAD done**, committed and pushed (commit "T-CHAT-CANVAS-LOAD: …"): `App.vue` loads the canvas on demand, so the chat no longer loads Konva or `fonts.ts`; the chat smoke fails if it does.

**Exact next step:** the user's deploy, backend and frontend together. Open in TODO.md: T-CHAT-CANVAS-LOAD, keeping the text of messages the chat could not take. Spend of the day for this work: USD 0.4691, all on the ledger; `backend/data-probe` has ten versions of the JBL poster. Open follow-ups in TODO.md: T-CHAT-D005-TESTS, T-CHAT-CANVAS-LOAD, keeping the text of messages the chat could not take.

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
