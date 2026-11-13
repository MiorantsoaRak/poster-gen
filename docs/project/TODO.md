# TODO

> Update statuses when work changes: `[ ]` not started, `[~]` in progress, `[x]` done and verified, `[!]` blocked, `[-]` dropped.
> Every task references an approved design section or is marked `chore`. One task may be in progress at a time. In-progress and blocked tasks require a note. Mark done only after running the verification step.

## Now (current focus — max 3 items)

- [x] T-POSTER-SHOP-STYLE (ADR-042; D-PV-009/010, D-POSTER-EDITOR-001; user autonomy grant 2026-11-11) Reach the shop's own poster style: study on real products, new scene prompt, integrated headline, style looks.
  - delivered: 10 shop posters inspected; 13 study images on 9 products; `compile_scene` rewritten; optional `headline` on scene requests (title always from the offer, price never sent); title layer may be hidden only with a matching recorded headline; editor has a thumbnail look picker, accent colour and headline fields. Real application poster: outputs/style-study-2026-11-11/app-poster-final.png (1080×1350, SHA-256 58c6bd98e8be665cb7843b46c026b4808752ca1f5788848a01dea1c798837a37).
  - verified: see HANDOFF "Verification". Report: reviews/style-study-2026-11-11.md.
  - spend: application ledger 1.161964 → 1.370232; study 3.050078 outside the ledger.
- [x] T-POSTER-PRICE-IN-IMAGE (ADR-044; user decision 2026-11-11) The price label is drawn by the image model; changing it needs a new scene.
  - verified 2026-11-11: tests/test_plans.py::test_price_label_comes_only_from_the_integer_amount, tests/test_exports.py::test_price_drawn_by_the_scene_must_equal_the_offer_and_a_change_needs_a_new_scene; full suite and Edge smoke (see HANDOFF); live Edge run 4 with the real provider: outputs/style-study-2026-11-11/live-edge-4/.
- [x] T-POSTER-PRICE-ATTEMPTS (ADR-045; D-GENERATION-JOBS-002) Scene limit raised from 3 to 12 per poster.
  - verified 2026-11-11: tests/test_poster_jobs.py::test_scene_limit_and_failed_jobs_do_not_consume_slots; full suite (see HANDOFF).
- [x] T-UI-MOCKUP-BUILD (ADR-050; user "go for all" 2026-11-11) Editor rebuilt to the audited mockup: navigation views, one main action, stage with photo, versions column, confirmations on paid actions, nine-point review, final screen.
  - verified 2026-11-11: backend 690 passed/3 deselected; 26 Vitest; build; browser smoke in bundled Chromium and Edge 156.
- [x] T-UI-FINAL-AFTER-CONFIRM (ADR-050 defect seen in Chrome 2026-11-11) On an already confirmed poster the final screen still shows the four checks at "0 sur 4" and "Confirmer cette version".
  - delivered: in frontend/src/App.vue the checks and the confirm row render only while `confirmedDownload` is empty. The confirmed screen stays confirmed after a draft edit, as its own text promises ("Le fichier confirmé ne changera plus"). The smoke no longer clicks a second confirmation after the price change; it asserts the button and the checks are gone and the confirmed file is unchanged. `preview_stale` stays covered by backend/tests/test_exports.py.
  - verified 2026-11-12: 26 Vitest; build; browser smoke in bundled Chromium 156. Not verified: by eye in Chrome on a reopened confirmed poster; Edge.
- [x] T-UI-MOCKUP-GAPS (ADR-050, ADR-062) Differences left from the reviewed mockup: accent word as chips, accent colour as swatches, the paid confirmation as an in-place panel (it is a dialog), thumbnails in "Mes affiches".
  - delivered 2026-11-13 (user: "do as you recommend"): "Mot du titre en couleur" is one chip per word of the title plus "Aucun"; "Couleur d’accent" is five swatches plus "Autre…" with the browser's colour picker (frontend/src/App.vue, style.css). The in-place confirmation is dropped (ADR-062); thumbnails were done in T-UI-LIBRARY-THUMBNAILS.
  - verified 2026-11-13 on Linux: build, 26 Vitest, browser smoke in bundled Chromium (first chip chosen, "Rouge" chosen, the caught scene request carries that word and `#D92B2B`); outputs/editor-smoke/desktop.png looked at.
  - not verified: a real scene with an accent chosen this way; a reopened poster whose accent is several words; the swatches on a phone; the user has not seen the five colours.
- [x] T-UI-ONE-VALIDATION (ADR-051; user decision 2026-11-12) Both review screens: a read-only summary of the points and one agreement, no checkbox per point.
  - verified 2026-11-12: 26 Vitest, the build and the browser smoke in bundled Chromium 156; the user approved and confirmed live run 7 himself through both screens in Edge on real data. He did not comment on the screens.
- [x] T-REQ-HOSTED-PILOT (chore; ADR-063, ADR-064, ADR-065) Requirements and design for putting the application on the owner's phone.
  - verified 2026-11-13: requirements/hosted-pilot.md approved with its seven defaults under the user's autonomy grant (ADR-064); designs/hosted-pilot.md v1 reviewed by a fresh reviewer (APPROVE WITH FIXES, one P1) and a devil's advocate (reviews/hosted-pilot-design-r1-2026-11-13.md); v2 approved (ADR-065), not reviewed again. Indexes and PROJECT.md updated. T-UI-PHONE-CHECK is absorbed by R-HOSTED-PILOT-006.
- [x] T-HOST-001 (D-HOSTED-PILOT-001, D-HOSTED-PILOT-002, backend) Password verified before the write transaction; IPv6 limited by /64; forwarding headers trusted from loopback; 90-day session; a changed password hash ends every session at start; the budget message.
  - verified 2026-11-13 on Linux: `uv run pytest tests/test_api.py -q` 27 passed (a second writer succeeds while a password is being verified; the sixth attempt is refused without a verification; one IPv6 /64 shares the limit and an IPv4-mapped address counts as its IPv4; real uvicorn records a failure under the forwarded address; `Max-Age` 7776000; a new hash ends every session at start, the same hash keeps them); full suite 722 passed / 3 deselected.
  - side effect to know: the first start after this change ends the existing sessions once (no fingerprint was recorded before).
- [x] T-HOST-002 (D-HOSTED-PILOT-001, D-HOSTED-PILOT-002, D-HOSTED-PILOT-006, editor) Service-down message with a retry; manifest and icons; return to the poster after sign-in; contrast check at phone width in the smoke.
  - verified 2026-11-13 on Linux: build, 26 Vitest, browser smoke in bundled Chromium (a 503 on `/api/session` shows the message and "Réessayer" brings the sign-in back; manifest and four icons served as PNG; a poster's address opened without a session lands on that poster after sign-in; contrast of every visible text measured on sign-in, intake, the editor and the final screen at 390 px and "Mes affiches", the editor and the list also in the light theme: no text under 4.5:1). The check itself was proven on a made page (two failing texts found, a large text and a disabled button passed).
  - not verified: installation from a real phone's browser (T-HOST-004); contrast of placeholders, of text over images and of the review panels, which the smoke does not measure.
- [x] T-HOST-003 (D-HOSTED-PILOT-006) `deploy/phone_session.py` and the record template (reviews/phone-session-TEMPLATE.md).
  - verified 2026-11-13 on Linux: `uv run pytest tests/test_phone_session.py -q` 3 passed (address read from the tunnel's output only; nothing starts without the program; a tunnel without an address is stopped). Run once with a stand-in for `cloudflared` on the test data: the page answered for the tunnel's host and 403 for another host, sign-in worked with the tunnel's origin, and killing the stand-in closed the page server and the API. No provider call was made.
  - not verified: the real `cloudflared` (not installed here; exposing the application is the user's action), and so whether its quick tunnel passes the phone's address in `X-Forwarded-For` (a line of the record template).
- [!] T-HOST-004 (D-HOSTED-PILOT-006; R-HOSTED-PILOT-006) The owner's first session on his own phone, through the tunnel.
  - note: blocked on the user: install `cloudflared`, agree a time with the owner, run the script, observe, fill the record. It exposes the application to the internet for the length of the session and spends from the test ledger (budget raised to USD 100 on 2026-11-13, ADR-067: about USD 89.9 left; the script caps the ledger at 94.72).
  - verify: docs/project/reviews/phone-session-<date>.md exists and every finding is a TODO entry or a decision.
- [x] T-HOST-005 (D-HOSTED-PILOT-001 container part, backend) `API_HOST`, `FORWARDED_ALLOW_IPS`, `SERVE_FRONTEND`; the access boundary's session test narrowed to `/api/`; cache headers; two password verifications and one browser at a time.
  - verified 2026-11-13 on Linux: `uv run pytest tests/test_api.py -q` 31 passed (settings reach uvicorn and a host off loopback needs a named proxy; the built page and a hashed file are public with the right cache headers, a missing file answers 404 in the application's envelope, five `/api/` paths answer 401 with `no-store`, a foreign Origin is refused on `/`; every declared route is under `/api/`; peak of two concurrent verifications); full suite 731 passed / 3 deselected; browser smoke.
- [x] T-HOST-006 (D-HOSTED-PILOT-004) `python -m affiche.backup <folder>`.
  - verified 2026-11-13: `uv run pytest tests/test_backup.py -q` 5 passed (a backup during an open write transaction is consistent and restores the same asset bytes and migration; assets copied once and never overwritten; 14 days kept and the newest always; a failure exits 1 and leaves the marker; no database is an error).
- [x] T-HOST-007 (D-HOSTED-PILOT-005) `GET /api/status`.
  - verified 2026-11-13: tests/test_api.py::test_status_tells_the_administrator_what_runs_and_how_old_the_backup_is (401 without a session; commit, migration, spend; failed jobs of 24 hours only; backup age, late over 48 hours, null without a marker or with an unreadable one).
- [x] T-HOST-008 (D-HOSTED-PILOT-005, 001 container part) `Dockerfile`, `.dockerignore`, `deploy/compose.yml`, `deploy/deploy.py`, `deploy/daily.sh`, `deploy/verify.sh`, `deploy/README.md`.
  - verified 2026-11-13 on the box (read by Claude after the user's deploy): the image built there (2.26 GB), container `running`, `healthy`, 0 restarts, not OOM-killed, no published port, revision label `7f4fa6d`, 222 MiB at rest; Chromium 156 starts inside it; `last-backup.json` written at start; the application's settings are the hosted ones. One bug found by the first run and fixed (the archive was deleted before the upload).
  - not seen by Claude: the output of `verify.sh` itself (the user reported "deployed").
- [~] T-EDITOR-STEPS (D-POSTER-EDITOR-004; R-POSTER-EDITOR-004, 005, 006; ADR-072) Editor in steps then tabs, controls grouped, "Retirer de l’affiche", glass on floating chrome; with a best-practice review written to reviews/ux-review-2026-11-13.md.
  - note 2026-11-13: built locally by a subagent (frontend/src/App.vue, api.ts, style.css, the smoke; no backend change), then read by a fresh reviewer: APPROVE WITH FIXES, one P1 (a refusal inside the final-file dialog was written in the inert groups behind it) and four P2. Fixed by Claude: refusals behind an open dialog go to the message above it; a link from the phone's poster sheet closes the sheet; leaving a drawn element out now says that this version can no longer be downloaded; links inside reasons are 44 px on touch; the element can be chosen inside « Réglages »; the blur switch covers the step bar; the seal's reason names « Contact ». Not fixed (reviewer's P3 and smoke remarks): a stale field message after the brand is corrected, no link from « Aux couleurs du produit » to the accent colour, the unused `sliders` icon, the phone bar's main action never used at phone width in the smoke, whether four step labels fit at 360 px.
  - verified 2026-11-13: build, 26 Vitest, browser smoke (all 188 earlier checks word for word, about 95 new: steps on defaults, tabs, blocked action opening its group, removal and undo, phone walk with the poster sheet and its link, refusal above the final dialog, contrast in both themes). Screenshots in outputs/editor-smoke/ looked at (steps, phone, removal).
  - waiting: the user looks at it on the free local demo (`uv run python ../outputs/serve_demo.py ../outputs/demo-password.txt` from backend/; simulated images, data in backend/data-demo). The three open choices were settled on his "go" with Claude's picks (ADR-073): glass stays restrained, a hand-picked accent colour wins over a style's (built: the style's colour is proposed with « Utiliser la couleur du style »; smoke updated and passing), the progress label stays « Préparation ». Nothing is committed or deployed.
  - verify: build, Vitest, browser smoke (steps on empty data, tabs, removal and undo, contrast in both themes); the user has seen it.
- [x] T-UX-HIDDEN-RULES (fix; user, 2026-11-13: "That is the UX error I was expecting to be audited: a compulsory field that is hidden in a collapsed panel") Audit of that class of error over the whole editor, and its fixes.
  - how it was audited: by script, not by eye. (1) Every refusal code raised by the server against the table of French sentences: 39 of 75 had none and answered "Vérifiez les informations saisies." (2) Every collapsed section of the editor and the controls inside: the small-photo agreement was the only compulsory one (fixed in T-PILOT-SMALL-PHOTO); the others hold optional settings. (3) Hidden rules on fields: a title drawn by the image model must have 60 characters at most, no straight quote or line break, and no price, promotion or guarantee word (`promo`, `gratuit`, `%`, `Ar`, `livr…`, `sold…`); the intake accepts 160 characters and says none of this; all of it surfaced only after the paid confirmation, as one vague sentence. (4) A failed generation said "La tâche n’a pas abouti" whatever the cause.
  - delivered: `MESSAGES` in `backend/src/affiche/api.py` has a sentence that says what to do for every refusal the owner can cause (69 entries); the fallback for the 13 that only a programming error can produce names the code and no longer blames the form. The four refusals he can cause by typing have their own code and field (`title_too_long`, `title_unsupported`, `title_commercial_text`, `contact_unsupported`) instead of `invalid_headline`. The editor refuses a title, brand or subtitle that is too long or carries a quote under the main button, before the paid step, for "Nouvelle version" too. A failed generation is worded by its cause (refused by the image service, service unavailable, account to be checked by the administrator).
  - verified 2026-11-13: tests/test_api.py::test_every_refusal_the_owner_can_meet_has_its_own_french_sentence (reads the source: a new refusal code without a sentence fails it); tests/test_exports.py (four titles refused with their code and field before any job, and accepted when the renderer writes the title); backend 736 passed / 3 deselected; 26 Vitest; build; browser smoke (a title with a quote disables the main button with its reason, and clearing it enables it).
  - not done, on purpose: the list of forbidden words is not copied into the editor (two copies would drift); the server's sentence names examples. Not walked: the refine, text-proposal and texture paths with awkward input; a real phone.
  - open question for the user: the word list refuses ordinary product names ("Livre", "Soldering", "100 %", "AR"). It protects against a price or a promotion drawn in the image; whether it is too strict for the shop's catalogue is his call.
- [x] T-PILOT-SMALL-PHOTO (fix; first finding of the live pilot, 2026-11-13) A product photo under 800 px made "Générer l’affiche" fail with "Vérifiez les informations saisies."; and on a new shop the contact typed at the first poster was not put on it.
  - found: the user's first poster on the box (a 474 × 474 px WebP) answered 422 on `/scenes`. Read on the pilot's data (read-only): the refusal is `acknowledgement_required`, which had no French message, and the agreement box sat in the closed section "Ambiance et qualité". The same poster had `include.contact` false although the contact was typed on that screen: the box follows the saved profile, which was empty when the page loaded (the smoke ticked it by hand, which hid this).
  - delivered: a French message for the refusal; a line under a small photo at upload; the agreement asked in the paid confirmation itself ("Lancer la génération" stays disabled until it is ticked), also when the server is the one that reports the small photo (reopened poster); the agreement is kept per poster and no longer carries to the next one; the old box is removed and the section is named "Ambiance"; a contact typed for the first time ticks "Contact", as an uploaded logo ticks "Logo".
  - verified 2026-11-13: build, 26 Vitest, browser smoke (474 px photo: line at upload, agreement in the dialog and confirm disabled, after a reload the server's refusal brings the dialog back, a request without agreement is sent once and refused, the next carries `low_resolution` and the scene is made); tests/test_api.py and tests/test_poster_visuals.py pass.
  - deployed 2026-11-13, 15:53 UTC (second release, revision `18fb91e`): read on the box by Claude: healthy, no restart, the poster, profile, ledger and sessions kept, a backup taken before and after, 69 sentences in the running code, the new bundle carries the upload note and no longer the hidden box; neighbours at 200.
- [~] T-HOST-009 (deploy/README.md "First rollout") First rollout on `mx1`.
  - note 2026-11-13, later: **deployed by the user; `https://affiches.miorantsoa.app` is live and he signed in from Edge.** Runbook steps done: 1 (DNS), 2 (Maizina), 3 (deploy), 7 (forged header: a wrong password with `X-Forwarded-For: 203.0.113.9` was recorded under the caller's real address; foreign Origin 403), and the service-down answers (seen before the container existed). Still open: 4 (profile, logo, styles in the application), 5 (memory during a real render: `free -m` open, then `docker inspect -f '{{.State.OOMKilled}}'`), 8 (restore proof), 9 (the owner's phone), the off-box backup decision, an uptime check, the journal's retention. Disk after the build: 7.9 GB free of 38.
  - note: blocked on the user, in this order: commit and push; DNS record `affiches.miorantsoa.app` (name to confirm); the Maizina change (committed and pushed on 2026-11-13 in `../maizina`; it also commits PPN Market's parts, which ran on the box without being in the repository): Maizina's own deploy; the pilot's provider keys in their own project; `uv tool install pyinfra`; the deploy with the first-deploy variables; then steps 4 to 9 of the runbook. Open decision: Hetzner's backup option or a regular pull (R-HOSTED-PILOT-004).
  - note 2026-11-13, first run by the user: DNS done, Maizina deployed with the new network and block (the three other sites answer 200; `affiches.miorantsoa.app` answers the French 503 and the `service_down` envelope with a valid certificate). `deploy.py` created folders, secrets, scripts and cron, passed the prechecks, then failed at the upload: Claude's bug, the archive was deleted when the script was read, before pyinfra executed the upload. Fixed in `deploy/deploy.py`; the fix must be committed and pushed before the next run. Until a container exists, the 00:40 UTC cron run logs one failed backup: harmless.
  - verify: `verify.sh` passes; runbook steps 5 to 8 recorded in docs/project/reviews/.
- [-] T-HOST-PHASE-B (replaced by T-HOST-005 to 009) The rented server: backups, deploy and rollback, status route, runbook, first deployment.
  - note: not split yet on purpose (ADR-065): re-scope from the phone session's findings, fresh review, then tasks. The server is Hetzner `mx1`, shared with Maizina, Trap Duel and PPN Market (ADR-066); the design's phase B is rewritten for it (outline v3: a compose project in PPN Market's pattern). Before tasks: a fresh review. Needs from the user: the DNS record `affiches.miorantsoa.app` (name to confirm), the two Maizina changes through Maizina's own workflow, the pilot's provider keys in their own project, and a decision on off-box backups (Hetzner's option or a pull).
  - verify: split into tasks after T-HOST-004.
- [ ] T-REQ-AFTER-PILOT (chore; ADR-063) Requirements still to draft, in this order, each after the one before is approved or the first phone session has been observed: three inputs and one button with a shop kit; automatic read-back of the drawn texts; share sheet and French caption (story format first); the owner's vocabulary (no dollars, "version", "fidélité", "scène").
  - verify: one requirements file or amendment per item, approved by the user.
- [x] T-ENV-LINUX (chore, trivial; 2026-11-13) Make a fresh Linux clone run every free check.
  - delivered: the browser smoke took its product photo from the Git-ignored `outputs/`; it now uses the tracked `backend/fixtures/examples/phone-noir.jpg`. The system Node 22.22.1 has no npm: use `corepack npm@10 <command>` from `frontend/` (npm 12 refuses this Node). Chromium for the renderer: `uv run playwright install chromium` from `backend/`.
  - verified 2026-11-13 on Linux (Python 3.12, Node 22.22.1, bundled Chromium 156): `uv run pytest -q` 716 passed/3 deselected (165 s); 26 Vitest; build; browser smoke passed with zero spend.
  - `backend/data-probe`, `outputs/` and `backend/.env` copied here by the user the same day; database read-only check: integrity ok, migration 0011, ledger 4.362064 (equal to the Windows reading), 4 backups, 55 asset files. The ledger now exists on two machines: paid work must stay on one of them.
- [x] T-SCENE-INVENTED-TEXT (ADR-051 open point; live run 6) The image model added a line nobody typed ("POUR TOUTES VOS NOTES") under the title.
  - closed 2026-11-13 on the user's "go": live runs 7 and 8 with "Vagues bleues" carried only the typed texts. Two scenes are not proof that the model always obeys; the review screen stays the guard.
  - cause (hypothesis): the saved look's style phrase describes "a lighter … subtitle below in grey"; `compile_scene` put it in as the product name's style and added the typed subtitle separately, so one described line had no words.
  - note 2026-11-12: prompt changed in backend/src/affiche/posters/plans.py: with a look, the typed subtitle takes the style's subtitle lettering; the headline states its exact number of quoted strings and forbids any other line; with a look and no subtitle, a described subtitle is ignored. tests/test_looks.py covers the four cases; 104 focused tests pass. Not yet proven on a real scene: that needs one paid scene with the user's go.
  - verify: the next paid scene with "Vagues bleues" carries only the typed texts.
- [x] T-UI-CAPSULE-CONTRAST (trivial; seen in the smoke's final preview 2026-11-12) Switching "Présentation du prix" back to "capsule" gave a white pill under the look's white digits: an invisible price in the exported file.
  - delivered: a new capsule takes a dark fill under light digits and white under dark ones (`capsuleFill` in frontend/src/App.vue). The "scene ready" notice that covered the review's instructions is removed; the review opens in front by itself.
  - verified 2026-11-12: 26 Vitest; build; browser smoke in bundled Chromium (asserts the dark fill); final preview seen with a readable price.
- [x] T-UI-LIBRARY-THUMBNAILS (R-CREATION-LIBRARY preview criterion; one of the T-UI-MOCKUP-GAPS items; user request 2026-11-12) "Mes affiches" shows each poster's own image.
  - note 2026-11-12: `GET /api/creations` returns `thumbnail_url` (last final preview, else the current scene, else none); the list shows it. tests/test_api.py (23 passed), 26 Vitest and the build pass. The browser smoke in bundled Chromium asserts the confirmed poster's 1080 px preview in the list and passes. Still open: the user has not yet seen the list on real data.
  - verify: browser smoke passes; the user has seen the list on real data.
- [x] T-REQ-SIGNATURE (chore; user request 2026-11-12) Requirements for a discreet contact with a position choice, logo-only shop identity and the product brand mark.
  - verified 2026-11-12: the user approved R-CATALOGUE-BRAND-003 and 004 ("go with the new requirement", ADR-052); statuses updated in requirements/catalogue-brand.md and _INDEX.md. Four open questions carry working defaults to confirm at the design review. Research: reviews/signature-research-2026-11-12.md.
- [x] T-SIG-004 (D-CATALOGUE-BRAND-004 v3.1 "Data", "Which words are drawn", "Fit rule", "Prompt") `Headline.signature_align`; compact contact sentence at left, centre or right; contact only, never the shop name; price hard limit above the footer (not on refinements); refusals (`signature_align` without `signature` or contact, `signature` without `signature_align` on a new scene, too long, quote).
  - verified 2026-11-12: tests/test_plans.py::test_compact_contact_line_has_a_position_and_the_price_stays_above_the_footer (three positions with explicit margins, price clauses only when the price is drawn, hard limit present, absent on refinements and when nothing lies below the price, refusals, 40 and 33 character limits, the older block unchanged); tests/test_exports.py::test_shop_signature_drawn_by_the_scene_must_match_the_poster_profile (old block refused on a new scene, contact only in the payload, shop name stays a visible layer, guards after a contact change); backend 693 passed/3 deselected.
- [x] T-SIG-005 (D-CATALOGUE-BRAND-004 v3.1 editor parts) "Dessiner aussi le contact dans l’image" on by default; position sent as `signature_align` and applied to the next version when drawn; fit reason; review label "Contact"; logo help line.
  - verified 2026-11-12: browser smoke in bundled Chromium (option ticked by default; a caught scene request carries `signature: true` and `signature_align: "right"` and no `brand_text`; with the title option off the contact is the rendered line, as before); 26 Vitest; build.
  - not verified: the too-long and multi-line reasons, the review label "Contact", the help lines for a drawn contact and the logo, and a poster with a drawn contact reopened have no browser test. No real scene yet: T-SIG-006.
- [x] T-SEAL-001 (D-CATALOGUE-BRAND-006 backend) `posters/seal.py` `find_disc`; `shape: "circle"` on the logo layer; `Headline.logo_seal` with its refusals and the badge sentence; a seal logo left out of the plan's fields; the disc stored in `placement_json` and returned as `logo_disc`; first-scene placement or logo unticked when not found; export guard `logo_disc_uncovered`; the stub provider draws the asked disc.
  - verified 2026-11-12: tests/test_seal.py (generated discs, nothing guessed, three real scenes as fixtures, failures swallowed and logged); tests/test_plans.py::test_logo_seal_adds_one_badge_sentence_to_the_tested_prompt; tests/test_exports.py (seal placed on the disc and rendered as a circle in real Chromium with pixel checks; uncovered disc refused in three ways; refinement accepted; not found removes the logo; five refusals outside the seal's footer); backend 713 passed/3 deselected.
- [x] T-SEAL-002 (D-CATALOGUE-BRAND-006 editor and renderer) Circle clip in the shared canvas; the option with its conditions and lock; `logo_seal` and `signature_align: "right"` sent; `chooseVisual` and re-tick rules; review and final-screen lines.
  - verified 2026-11-12: browser smoke in bundled Chromium with the stub provider drawing the disc (option on by default, request carries `logo_seal` and `signature_align: "right"`, seal on the disc, locked after the first version, unticking the logo blocks the final preview with the reason, ticking again restores it, final screen line); 26 Vitest; build.
  - not verified in a browser: the reasons for an unavailable seal; a seal turned off before the first version; a version without a disc chosen on a seal poster; dragging the seal off its disc.
- [x] T-SEAL-003 (D-CATALOGUE-BRAND-006 paid check) The real logo saved in the shop profile; one scene with a left-aligned look and one with a centred look, about USD 0.42.
  - verified 2026-11-12 (`outputs/style-study-2026-11-11/live-seal/`, USD 0.422076): results and the two rules they changed are in the design's "Result of the paid check" and in ADR-058. Centred dark look: the application found the disc and placed the seal. Left-aligned look: the disc was in place but rejected by the first size rule; the corrected rule finds it (test fixture), and the composed picture was made outside the application.
  - not verified: the application itself placing the seal on a real scene with a left-aligned price; a white backdrop; the user has not yet said whether the result suits him.
- [x] T-LIB-001 (D-CREATION-LIBRARY-003, server) `status` filter, `state` and `total` on `GET /api/creations`; `POST /api/creations/{id}/restore`; a `new_campaign` copy refused on a stale revision.
  - verified 2026-11-12: `uv run pytest tests/test_api.py -q` 24 passed; one test walks a poster through the four states (including "Confirmée" lost after an edit and a waiting version the document has not chosen), the removed view, restore, replays and the stale copy.
- [x] T-LIB-002 (D-CREATION-LIBRARY-003, editor) Row state and actions ("Dupliquer", "Retirer de la liste"), the removed view with "Remettre dans la liste", "Voir plus", the real total, a removed poster reached by its address.
  - verified 2026-11-12: build, 26 Vitest, browser smoke in bundled Chromium (state in words, copy opens in the editor, removal with its confirmation, removed poster reached by address, restore, counts, zero spend).
  - not verified in a browser: "Voir plus" (needs more than 50 posters); the refusals (generation running, list out of date); the phone layout of the rows beyond the stub screenshot.
- [x] T-LIB-003 (D-CREATION-LIBRARY-004, server) Migration 0011 (`looks.removed_at`); rename and remove routes; list filter; limit and name rule; free numbered name when a look is stored.
  - verified 2026-11-12: `uv run pytest tests/test_looks.py tests/test_db.py -q` 20 passed (names compared without case including accents, numbering within 40 characters, rename refusals and retries, removal twice, a scene still accepted with a removed look, the limit, no provider call).
  - migration 0011 applied to the paid database `backend/data-probe` on 2026-11-13 through `affiche.db.migrate`, after the copy `backups/before-looks-removed-2026-11-13.db` (made with the SQLite backup call so the write-ahead log is included; integrity ok). Row counts of every table unchanged, 3 styles, none removed.
  - not verified: the two new routes through HTTP in a backend test (the browser smoke calls them).
- [x] T-LIB-004 (D-CREATION-LIBRARY-004, editor) Style panel on the "Styles" page; rename, remove, "Créer une affiche avec ce style"; a poster keeps its removed style.
  - verified 2026-11-12: build, 26 Vitest, browser smoke (a supplied style opens without rename or removal, a shop style opens with its description, rename to a supplied name refused beside the field, rename, removal with its confirmation, counts, zero spend).
  - not verified in a browser: a poster reopened with a removed style and its next version (the server side is tested; the editor side is read from code only); "Créer une affiche avec ce style"; the panel on a phone.
- [x] T-LIBRARY-MANAGE-REQ (user request 2026-11-12: "commit; then draft the requirement") Requirements for managing posters and saved styles.
  - drafted 2026-11-12: R-CREATION-LIBRARY-003 and 004 in requirements/creation-library.md, with five open questions and their working defaults.
  - approved by the user the same day with the five defaults ("approved, go"; ADR-060).
  - design D-CREATION-LIBRARY-003/004 drafted in designs/creation-library.md and reviewed twice by fresh reviewers and once by a devil's advocate (reviews/library-manage-design-r1-2026-11-12.md); it stands at v2.1, and no review was run on v2.1 itself. Approved by the user at v2.1 with "Confirmée" only while the file matches the poster (ADR-061). Tasks: T-LIB-001 to 004.
- [x] T-UI-UX-AUDIT (user request 2026-11-12: UX audit with ui-ux-pro-max on usability, focus, flows and consistency, then "fix") The findings that needed no decision.
  - done: at one-column widths the main button and its reason stay at the bottom of the screen; the "dessiné dans l’image" notices sit under the field that causes them; title and price are locked while a scene that draws them is being generated, and the wait message says so; the paid confirmation opens with focus on "Annuler" (a held Enter key must not pay); a missing photo or unticked box takes focus; focus goes to the content after a change of view; 16 px fields on phones; 44 px targets on touch screens; notices leave after 8 s; phone header on two rows; the final check on a phone shows only the price fact.
  - verified 2026-11-12: build, 26 Vitest, browser smoke in bundled Chromium; the phone-width screenshot shows the bottom bar and the two-row header.
  - not verified: a real phone; the locked fields during a real one-minute generation; a keyboard-only pass.
  - second pass, same day (user: "you can fix the remainings too"), wording by Claude's proposal: the main flow says "affiche" and "version" ("Préparer mon affiche", "Générer l’affiche"; "scène" stays for the image in the advanced settings and the review groups); "approuver" for fidelity and "confirmer" for the final file, no "valider"; the review images enlarge in place; one photo can be removed; the price field shows "90 000"; the notice about a drawn price says "AR" as drawn; one "Comparer" link (under each version); outlined buttons have one look; "Étape n sur 4" on a phone; "Mes affiches" rows show price and date (`price_ar` added to `GET /api/creations`) and the list asks for 50 posters instead of the default 20.
  - verified 2026-11-12: backend full suite, 26 Vitest, build, browser smoke in bundled Chromium (labels and the price display updated in it).
  - not verified in a browser: enlarging in the review, removing a photo, the locked fields during a real generation; a real phone.
  - not done, each needs a requirement first (new server behaviour): rename and delete a saved style; delete and duplicate a poster from "Mes affiches"; a status on each row (draft, to check, confirmed); more than 50 posters in the list (the API pages by 50, the editor does not ask for the next page).
- [x] T-UI-WEB-GUIDELINES (user request 2026-11-12: "Review my UI against web design guidelines", then "fix all of them"; ADR-059) Fixes from the review against the Vercel Web Interface Guidelines.
  - done: the view is in the address (`#affiches`, `#styles`, poster id) with real links; the three panels are dialogs that take and return focus, close on Escape and make the page behind inert; the price error is written beside its field and takes focus; "Ajuster la scène", "Proposer un ajustement", "Générer la matière du texte" and "Abandonner mes modifications" ask for confirmation; focus ring distinct from the chosen ring; `theme-color` follows the theme; safe-area insets; image dimensions and lazy loading; one price format; `name`, `autocomplete`, `spellcheck`, placeholders; skip button; canvas role and touch behaviour; long shop name and long messages.
  - verified 2026-11-12: build (vue-tsc), 26 Vitest, browser smoke in bundled Chromium (it now covers the confirmation before a text proposal with Escape, and a reload that stays on "Mes affiches").
  - not verified: a screen reader; a real phone (safe areas, `touch-action: none` on the canvas while "Déplacer les éléments" is on, the tap highlight): part of T-UI-PHONE-CHECK. Edge.
  - left as it was, on purpose: colour and border transitions (150 ms, off under reduced motion); French sentence case instead of Title Case; no virtual scroller for "Mes affiches" (`content-visibility` instead).
- [x] T-DESIGN-LOGO-SEAL (chore; R-CATALOGUE-BRAND-005) Requirement and design for the logo as a round seal printed on a disc the scene provides; fresh review and one devil's-advocate pass; user approval of both.
  - note 2026-11-12: the user chose the variant (full logo, round badge, about 130 px, footer). R-CATALOGUE-BRAND-005 and D-CATALOGUE-BRAND-006 drafted. Round 1: REWORK plus devil's advocate (reviews/logo-seal-design-r1-2026-11-12.md); round 2: APPROVE WITH FIXES (reviews/logo-seal-design-r2-2026-11-12.md); fixes applied as v2.1, not re-reviewed. 
  - verified 2026-11-12: the user approved both at v2.1 (ADR-057).
- [x] T-LOGO-STUDY (chore; user request 2026-11-12 with the shop's logo and autonomy for paid tests) How to bring the logo into the composition.
  - note 2026-11-12: study done, reviews/logo-study-2026-11-12.md. Two free composites of the real file and two paid scenes where the model draws the logo (USD 0.439210, outside the ledger). Drawn: composes well, lettering and phone right, the striped ribbon is redrawn and not exact. Real file: exact, but collides unless the scene left its spot empty. Second round on the user's request "in a round circle" (two more paid scenes, total USD 0.870198): a badge drawn by the model redraws the ribbon again; an empty white disc drawn by the model with the real logo file printed on it gives an exact logo that sits in the composition (the disc came out smaller than asked: 14.6 % of the width against 19 %). Third round on "smaller footprint" (one more paid scene, study total USD 1.081501): a disc asked at 10 % came out at 10.7 %, well placed; at that size the full logo's lettering is unreadable and an emblem-only badge (phone and ribbon) reads clearly. Blocked on the user's choice; a drawn logo contradicts R-CATALOGUE-BRAND-002 ("never draws or imitates") and needs that requirement amended, then a design.
  - verify: the user chooses; requirement and design follow if needed.
- [x] T-SIG-006 (D-CATALOGUE-BRAND-004 v3.1 paid check) One real scene with the contact drawn at the right and the logo ticked, about USD 0.21, only with the user's go.
  - verified 2026-11-12, live run 8 (`outputs/style-study-2026-11-11/live-edge-8/`, CMF Buds 2a, look "Vagues bleues", USD 0.210658): contact "038 93 028 00 / 034 93 028 00" with a handset, every digit exact, at the right with a 4.6 % margin; no shop name; no invented line; 211 px clear between the pill and the contact. The fidelity was approved in the Edge window, not by Claude; the script then ran its remaining steps.
  - measured against the prompt: the model put the contact beside the pill, not below it (pill bottom at 93.5 % of the height, asked above 91 %); digits about 20 px high on 1350, under the 22 px asked.
  - not covered: the logo case (the shop profile has no logo); one scene only.
- [x] T-UI-THUMBNAIL-SIZE (trivial; seen in live run 8) "Mes affiches" loaded each full 1080 × 1350 PNG as its thumbnail. With 15 posters the list was still loading when the screenshot was taken (two and a half thumbnails shown).
  - delivered: `GET /api/thumbnails/{sha}` returns a 192 × 240 JPEG of a final preview or a scene of the signed-in shop, cached in memory and by the browser; the list points to it.
  - verified 2026-11-12: browser smoke (thumbnail 192 × 240, under 40 kB); tests/test_api.py (unknown image refused); on the real images, read-only: 31 images, 54.3 MB at full size against 247 kB as thumbnails, all built in 1.5 s; backend 693 passed/3 deselected; 26 Vitest; build.
  - not verified: the list itself has not been looked at in a browser on the real data since this change.
- [x] T-DESIGN-SIGNATURE-V3 (chore; R-CATALOGUE-BRAND-003 as amended, ADR-055) Design v3: contact drawn in the composition with a position, rendered line as fallback, price kept above the footer; one fresh review; user approval.
  - verified 2026-11-12: round 3 APPROVE WITH FIXES, no P1 (reviews/signature-design-r3-2026-11-12.md); the user approved v3.1 (ADR-056).
- [x] T-SIG-001 (D-CATALOGUE-BRAND-004 "Data", "Compact style", `text_fit` row) Optional `icon: "phone"` on the contact text layer (backend model and TypeScript type); the shared canvas draws the handset, keeps an icon layer on one line and raises `text_fit` when the line with its icon is wider than the layer.
  - verified 2026-11-12: tests/test_poster_drafts.py::test_contact_icon_is_optional_and_only_for_the_contact; tests/test_rendering.py::test_compact_contact_is_one_line_with_a_handset_at_a_readable_size (real Chromium: ink height 22–30 px at 32 px bold, left/centre/right, too-long contact refused); backend 692 passed/3 deselected; 26 Vitest; build; browser smoke. The rendered line was also looked at.
- [x] T-SIG-002 (D-CATALOGUE-BRAND-004 editor parts) Compact style function applied in its three places; "Position du contact" choice saved on the device; shop name unticked by default; "Dessiner aussi le nom de la boutique et le contact" removed and no signature requested; `stylePill` stops setting `align`; ticking the logo after a scene places it at the footer left and narrows the contact; old posters with a drawn contact keep their guards and a disabled position choice.
  - verified 2026-11-12: browser smoke in bundled Chromium asserts the unticked shop name, the compact contact (icon, 32 px, bold, 48 px high, centred without a logo), the removed signature option, the position choice saved in the document and on the device and kept through a scene request, and a logo ticked after the scene placed at the footer left clear of the contact; 26 Vitest; build. The final preview with a right-aligned contact was looked at (outputs/editor-smoke/final.png).
  - not verified: a poster whose scene already has a drawn contact (disabled position choice, compact style on its next version) has no browser test; the user has not seen a real poster with the new footer.
- [x] T-SIG-003 (D-CATALOGUE-BRAND-005) `brand_text` on the headline (refused without a brand, absent from the idempotency body when unset), plain-text prompt wording, editor checkbox remembered on the device, review label "Marque, titre et sous-titre".
  - verified 2026-11-12: tests/test_looks.py (both wordings, refusal without a brand, true-or-absent, field omitted from dumps when unset); the existing export test proves the stored headline payload is unchanged when unset; browser smoke (checkbox only with a typed brand); backend 692 passed/3 deselected; 26 Vitest; build.
  - not verified: no real scene has been generated with the option on (one paid scene, about USD 0.21, only with the user's go); the review label with a brand has no browser test.
- [x] T-DESIGN-SIGNATURE (chore; R-CATALOGUE-BRAND-003/004, ADR-052) Design for the compact contact with a position, logo-only identity and the brand-as-text choice; fresh review and one devil's-advocate pass; user approval.
  - verified 2026-11-12: the user approved v2.1 (ADR-054).
  - note 2026-11-12: draft v1 written (D-CATALOGUE-BRAND-004/005). Round 1: REWORK, and the devil's advocate argues for a rendered contact layer instead of a drawn one (reviews/signature-design-r1-2026-11-12.md). The user chose the rendered contact (ADR-053); R-CATALOGUE-BRAND-003 amended; draft v2 reviewed: APPROVE WITH FIXES (reviews/signature-design-r2-2026-11-12.md); fixes applied as v2.1, not re-reviewed. Waiting for the user's approval of the design. None of this is committed.
  - verify: design file and designs/_INDEX.md updated; review saved in reviews/; the user approves, including the four defaults.
- [x] T-UI-LIVE-AFTER-REBUILD (ADR-050 open point) One live paid run through the rebuilt editor, and the phone check of T-UI-PHONE-CHECK.
  - verified 2026-11-12, live run 8 in Edge on real providers: sign-in, draft, saved look, cost confirmation, scene, review, the stale title, price and contact notices shown and cleared, final preview, confirmation, download equal to the preview, no second confirmation, phone-width layout without horizontal overflow, "Mes affiches" and "Styles" opened. No page error and no failed request. The script itself pressed the final confirmation after the fidelity was approved by hand. The phone check on a real phone stays in T-UI-PHONE-CHECK.
  - note 2026-11-12: run 6 (`outputs/style-study-2026-11-11/live-edge-6/`, saved look "Vagues bleues", one scene call) passed sign-in, draft, saved look, cost confirmation, scene and the review screen. The scene was not approved because of the invented line, so the stale notices, final preview, confirmation, "Mes affiches" and "Styles" stay untested on real data. The scene is left pending in data-probe. Blocked on T-SCENE-INVENTED-TEXT, then one more paid scene with the user's go.
  - note 2026-11-12, later: run 7 (`live-edge-7/`, same product and look, fixed prompt) drew only the typed texts. The user approved it, made the final preview and confirmed it by hand in the Edge window (database: approved 09:00:02 UTC, confirmed 09:00:25 UTC). The run 6 scene with the invented line is also recorded as approved (08:35:11 UTC) with a final preview and no confirmation; Claude did not approve it. Not exercised on real data: the stale title/price/signature notices and the script's own remaining steps.
  - verify: scene, nine-point review with drawn texts, confirmation, download, all on real providers.
- [x] T-UI-USABILITY-1 (ADR-049; user report 2026-11-11) One reference import, no Claude composition in the editor, reasons under blocked buttons, coach line, always-visible messages, review sheets in front.
  - verified 2026-11-11: 26 Vitest; build; browser smoke in Edge 156; Chrome on the production build.
- [ ] T-PLANNER-CLAUDE-INVALID (ADR-049; D-PV-009) The Claude composition returns plans that fail validation with the real model (3 of 3 on 2026-11-11). Find the failing rule from a captured answer before offering it again.
  - verify: a captured real answer in a test; three real plans in a row validate, or the mode stays hidden.
- [x] T-UI-IMAGE-TOOL (ADR-048; user feedback 2026-11-11) Interface redone as an image-generation tool: dark stage, control rail, generations filmstrip, light variant.
  - verified 2026-11-11: 26 Vitest; build; browser smoke in Edge 156. Light variant and bundled Chromium not run after this change.
- [x] T-UI-REDESIGN (ADR-047, look superseded by ADR-048; user request 2026-11-11) Three-step editor.
  - verified 2026-11-11: 26 Vitest; build; browser smoke in bundled Chromium and Edge 156 after the last change. No backend change.
- [ ] T-UI-PHONE-CHECK (ADR-047 open point) Check the redesigned editor on a real phone and run a contrast audit.
  - verify: owner completes photo → poster on his phone without help; no text under 4.5:1.
- [x] T-POSTER-REFERENCE-BRIEF (ADR-046; user go 2026-11-11) Owner uploads a poster he likes; Claude writes the style brief; it is saved as a reusable look beside the built-in ones.
  - verified 2026-11-11: tests/test_looks.py (brief boundary, prompt only through a look, saved look styles a later scene, foreign/unknown look refused, spooled brief revalidated); full suite (see HANDOFF); stub smoke in Edge creates and selects a look; live Edge run 5 with real Claude and image providers (outputs/style-study-2026-11-11/live-edge-5/).
  - not built: rename/delete a look; looks for the "Avec Claude" composition (it keeps its own palette).
  - user requirement 2026-11-11: the look made from a reference is saved beside the built-in looks in the picker (with the reference as its thumbnail) and can be chosen for later posters.
  - scope seen in the exploration: a brief job (Claude vision, about USD 0.007), a screened `headline_style` phrase in the scene prompt, a headline alignment choice (left/centre) so layout can follow the reference, stored looks (new table and migration), editor entry "Créer un style depuis une affiche".
  - verify: reference → brief → scene on another product, compared side by side; brief refused when it carries words, prices or brand names from the reference.
- [x] T-POSTER-SIGNATURE (ADR-043; D-PV-009/010, D-CATALOGUE-BRAND-001) Shop name and contact drawn by the image model, with the same exact-match guard as the title.
  - verified 2026-11-11: backend 676 passed/3 deselected before the last prompt wording change, then tests/test_plans.py + test_poster_visuals.py; 26 Vitest; build; stub smoke in Edge 156; live Edge runs 2 and 3 (real provider) with digits read at full size. Spend: ledger 1.575109 → 1.993185; study +0.704928 outside the ledger.
- [x] T-POSTER-LOOK-PILL (ADR-042 follow-up; D-POSTER-EDITOR-001) A chosen look also styles the price pill, and the shop name/contact colours.
  - delivered: `stylePill` in App.vue (dark pill per look, white digits, half canvas width; shop name/contact centred, dark on light looks); a pill restyled by hand is left alone. The first scene keeps a styled pill's size and centres it in the plan's price band (service.py).
  - verified 2026-11-11: tests/test_poster_visuals.py::test_first_scene_keeps_a_styled_price_pill_size_and_centres_it; smoke asserts badge, width 540, x 270; live Edge run asserts the same on real data.
- [x] T-POSTER-ONE-TAP (ADR-042 follow-up; D-CREATION-LIBRARY-001) One "Générer la scène" action for the simple composition; the last look, accent colour and brand come back on the next poster.
  - delivered: `createScene` reuses an unchanged plan, so a retry after a lost response replays the same scene key (smoke: one scene job). The Claude composition keeps its two steps. Style memory is localStorage `affiche.style` on this device.
  - changed scope: "Même style que…" from a previous confirmed poster was not built. It needs the library (T-POSTER-009) and scene assets accepted as style references, and the study measured little gain from a style reference over a look.
  - verified 2026-11-11: full backend 674 passed/3 deselected; 26 Vitest; build; smoke in bundled Chromium and in Edge 156 (`SMOKE_CHANNEL=msedge`); live Edge run (see HANDOFF).

- [x] T-POSTER-REFERENCE-TYPE (D-POSTER-EDITOR-001/003; R-POSTER-EDITOR-003) Match the reference's heavy italic font and price capsule while retaining manual/prompt editing.
  - delivered: Montserrat Black Italic, grouped exact amount with smaller upright AR and editable gradient capsule. Same scene/shop layers. Revision 6 confirmed PNG: outputs/style-reference-2026-11-10/soundcore-r50i-reference-typography-final.png; SHA-256 e574e884916eb29f908d22d51f3d95fad531a98225da05a834a3da0f4870b5f9. No additional image cost; combined ledger $1.161964. Price remains dated test data.
  - verified: 671 backend tests/3 deselected; final italic-bound correction then passed all 5 shared-renderer tests and full Chromium smoke; 26 frontend tests/build passed. New controls/undo/reopen, patterned price glyphs, schema/patch isolation, exact amount, zero/large-price bounds, legacy hashes/currency font fingerprint, unchanged historical download and exact final preview/download equality. Pixel proof confirms all pixels outside title/price boxes unchanged. See reviews/style-reference-test-2026-11-10.md.

- [x] T-POSTER-STYLE-TEST (D-PV-009/010; chore evaluation) Reproduce the style of a recent accessible Original Phone Mada poster using a real product and editable commercial layers.
  - note: User-supplied DJI Mic Mini reference inspected and preserved. Live R50i style adaptation complete: initial GPT Image scene, framing refinement to clear the heading, manual typography/footer polish, fidelity review, authoritative PNG confirmation/download. Final outputs/style-reference-2026-11-10/soundcore-r50i-reference-style-final.png is 1080×1350; hash 2c61abbf28e52a5af380b11b7291bb9d7e49d766a2fe8b08ab747ea3045fffee equals inspected preview. Two live calls cost $0.445271; combined ledger $1.161964/$12. Previous dark poster unchanged. Price remains dated test data. Font/capsule controls were subsequently completed by T-POSTER-REFERENCE-TYPE; mixed-colour title runs remain outside scope.
  - verified: Existing implementation checks: 662 backend tests/3 deselected; 25 focused reference/visual tests; 26 frontend tests; build and Chromium smoke passed. This follow-up: real original+style generation and base+original+style refinement, exact reference hashes/provenance, local plan validation, scene-preserving manual text polish, inspected final PNG/download equality, recorded spend. No application code changed after those regression checks.
  - verify: reference provenance and visual comparison; reference-role/ownership checks if code changes; generated product fidelity, polished PNG preview/download equality and incremental spend recorded.

- [x] T-POSTER-001 (D-CATALOGUE-BRAND-001/002/003; D-CREATION-LIBRARY-001/002; D-POSTER-EDITOR-001) Persist validated product inputs, shop snapshots and editable draft versions.
  - verified: 66 focused tests passed; full backend suite 491 passed, 3 deselected (102.27 s). Migration 0003→0004 preserves legacy rows including a nonzero provider ledger; all eight identity combinations, original-byte/alpha preservation, races/replay and rollback covered. Generated references and renderer remain dependent tasks; no paid calls.
  - scope: forward-only schema; safe concurrent asset writes/intake; strict money/document validation; atomic idempotency, profile/draft revisions, history and copies. Existing CLI callers and tests remain supported.
  - verify: focused domain/migration/storage tests for bad images/prices/identity flags, original hashes, immutable history, stale/concurrent saves, lost-response replay and rollback; complete backend suite.

- [x] T-DESIGN-POSTER (chore; ADR-028/030) Record requirements approval and write matching phase-2 designs for the complete poster workflow.
  - verified: 22 total Approved requirement groups (14 new); five new design files plus product-visuals v2 sections, six-file approval index, 32 local links and all requirement indexes checked; all three proposed image sizes satisfy documented constraints and exact export ratios; git diff --check passes.
  - research: installed OpenAI SDK signatures/callers; official OpenAI, Claude, Konva/Fabric and Playwright docs; Orbit discovery/integration for both providers, with incomplete OpenAI collection explicitly superseded by primary docs. No dependencies installed, API/renderer code, live model calls or test reruns; the last backend suite remains 442 passed, 3 deselected.
  - outcome: technical designs subsequently approved (ADR-031). User chose separate text/effect layers for manual or prompt edits (ADR-030); surface-embedded text deferred. No implementation tasks added before that gate.
  - verify: all approved requirements mapped, concrete data/API/state/error contracts, explicit provider/spend failure modes, consistent cross-feature references and local links; submit designs for approval.

## Completed review work

- [x] T-FIX-001 (D-PV-002 / R-PRODUCT-VISUALS-003) Screen commercial descriptions in shared admission before reserving spend.
  - note: User authorised review fixes on 2026-11-09. Reuse the existing screen; preserve idempotent replays.
  - verify: direct scene/background/revision regressions, no request or cost on refusal; full backend suite.
  - verified: `uv run pytest tests/test_admission.py -q` → 39 passed. Full suite with both fixes: 442 passed, 3 deselected (149.19 s).
- [x] T-FIX-002 (D-PV-001/008 / R-PRODUCT-VISUALS-007) Lock evaluation snapshots to ordered photo hashes; refuse changed or unverified legacy sources before new work.
  - note: Migration 0003 preserves old rows with NULL hashes; legacy `generate` is refused, not silently backfilled (ADR-027).
  - verify: changed bytes at the same path, secondary photos, `--only`, unchanged replay, old database migration, no writes/spend on refusal.
  - verified: `uv run pytest tests/test_fixtures_generate.py tests/test_db.py -q` → 44 passed. Full suite: 442 passed, 3 deselected (149.19 s). Migration tested on a real temporary revision-0002 database and repeated startup; paid evidence database was not migrated or changed.
- [x] T-REQ-POSTER (chore) Draft per-feature criteria for the accepted poster direction, GPT Image primary and cutout optional; submit the new requirements before feature design.
  - verified: five new feature files plus product-visuals R-009–011, 13 Draft groups, 16 valid local links and matching requirement indexes. General direction approved; detailed criteria submitted for the explicit requirements gate.
  - verify: requirements index, consistent approval/export/refinement rules, acceptance criteria and local links.

## Queued evaluation tooling

- [ ] T-PV-011 (D-PV-008 `report`) `calls.csv`, `report.csv` (per run × variant × cycle × treatment, outcomes, reasons, estimated and allocated billed cost, `low_res`, `arm`) and `summary.md`.
  - verify: `uv run pytest tests/test_report.py -q`: outcome precedence (`approved` > `abandoned` > `pending` > `exhausted` > `failed_only` > `not_approved`); the billed allocation sums exactly to the billed total; `attempt_no` restarts per cycle.

Work in C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia. T-POSTER-001–008 are verified. T-POSTER-STYLE-TEST and T-POSTER-REFERENCE-TYPE are complete: reference-guided R50i scene/refinement, editable italic typography/price capsule and confirmed PNG delivered. The next broader approved task remains T-POSTER-009 (square/story/library). Requirements/designs are approved (ADR-028/030/031); T-PV-011 remains queued.

## Poster implementation (approved, ordered)

- [x] T-POSTER-002 (D-CATALOGUE-BRAND-003; D-CREATION-LIBRARY-001) Add authenticated FastAPI intake/profile/draft routes, shared error responses and protected assets.
  - verified: full suite 513 passed, 3 deselected (106.47 s); 22 API tests include actual Uvicorn HTTP sign-in/protected access/logout, Origin/session/rate-limit/ownership errors, draft round trip, history/copy/abandon, private OpenAPI and safe storage failures. API-only settings preserve CLI startup; migrations 0004/0005 are forward-only. No real env file or paid database was read/migrated by tests; no provider calls.
  - verify: HTTP tests for Origin/session/rate limits, ownership, strict requests, idempotent replay, revision conflicts and storage errors; local OpenAPI contract; full suite.
- [x] T-POSTER-003 (D-PV-009/010; D-GENERATION-JOBS-001) Extend the existing image gateway sizes/reference roles and implement validated fixed/Claude scene plans.
  - verified: full suite 579 passed, 3 deselected (112.43 s); a final compiler revalidation regression then passed with all 62 planner tests. Explicit feed/square/story/texture sizes preserve legacy callers. Fixed plans and retry-free Claude Messages transport validate geometry, selected fields, measured footprints, commercial isolation, reference roles and cost/error handling. No live calls; persistent plan routes integrate with T-004/005.
  - verify: installed SDK transport tests, size validation, plan schema/injection failures, identity and commercial-value isolation; no live calls.
- [x] T-POSTER-004 (D-GENERATION-JOBS-002/003) Durable jobs, combined budget, dispatch/recovery and cancellation.
  - verified: full backend suite 607 passed, 3 deselected (124.68 s); migration 0006, both-ledger cap/concurrency, replay, cancel/claim race, two provider/one local slots, three scenes, active-job abandonment, no retry for unknown outcomes, bounded 429 retry, spool/commit/disk failure and recovery covered. Read/cancel/usage routes are authenticated. Admission endpoints and scheduler registration are T-005; render deduplication remains T-008.
  - verify: concurrent admission, both ledger totals, crash boundaries, unknown-outcome no replay, bounded definite-429 retry and stale result tests. Add the active-image-job guard to draft abandonment when jobs become available.
- [x] T-POSTER-005 (D-PV-009/010; D-CREATION-LIBRARY-001) Wire scene generation/refinement and fidelity decisions to drafts.
  - verified: full suite 625 passed, 3 deselected (138.83 s). Migration 0007; actual HTTP original→fixed plan→scene→review; all eight identities; local spool recovery/scheduler; explicit stub planner, manual rebase, late results, approved-base/rejected-refinement isolation, owned generated assets/crops and no-call price edits. No real provider call. The real R50i reference is downloaded and inspected; shop/source caveats are recorded in reviews/shop-poster-sources-2026-11-10.md.
  - verify: stub end-to-end HTTP flow, immutable references, three slots, late results, selected-base ordering and review guards. Replace the explicit generated-reference refusal in posters/store.py and extend protected asset reads to owned generated references.
- [x] T-POSTER-006 (D-POSTER-EDITOR-001/002; D-CATALOGUE-BRAND-001/002) Build the French Vue feed workflow and shared canvas, bundled fonts, manual editing and autosave.
  - verified: Vue/Konva editor, bundled/hashed Noto fonts, manual typography/identity/crop controls, serial autosave/history and protected capabilities/job recovery. Production build, 26 Vitest tests, full backend 625 passed/3 deselected (150.16 s) and real Chromium smoke pass. Browser: real photo upload, identity, dropped scene response replay (only one job), fidelity review, price undo, keyboard movement, reopen, two-tab conflict copy and overflow/glyph warnings at desktop/mobile viewport. No paid calls; physical phones untested (T-011).
  - verify: browser upload → draft → scene → review, all eight identity choices, touch/keyboard controls, undo, save conflicts, measured overflow; production build.
- [x] T-POSTER-007 (D-POSTER-EDITOR-003) Constrained Claude text proposals and explicit GPT texture jobs; manual/prompted selected-layer polish.
  - verified: migration 0008, strict selected-layer proposals/explicit values/acknowledgement, reviewed texture jobs, reused Claude transport, API and shared Konva glyph fill. Full backend 647 passed/3 deselected (153.47 s), 26 Vitest tests and production build pass. Real Chromium verifies proposal preview/apply, separate texture generation/review/undo, glyph-mask pixel isolation, unchanged scene/other layers and free manual edits. No live Claude or real texture provider call.
  - verify: content acknowledgement, stale proposals, reference checks, no unrelated document/pixel changes and manual edits without provider calls.
- [x] T-POSTER-008 (D-FORMAT-EXPORT-002; D-POSTER-EDITOR-002) Shared Chromium PNG preview, exact confirmation and stored download.
  - verified: migration 0009, offline shared Chromium render, prepared assets/fonts, model-free jobs, confirmation/hash/download API/UI. Full backend 655 passed/3 deselected (171.38 s), production build, 26 Vitest and real Chromium flows pass. Real R50i + Original Phone Mada feed poster generated, visually reviewed, manually polished, confirmed and downloaded; PNG 1080×1350 hash b1aca99e80656940fcaa378abd416c839bbae4f1ed29a82f618aa195484aae27 equals inspected preview. One image call $0.203812; final combined ledger $0.716693. Report: reviews/real-feed-poster-2026-11-10.md. Current price/stock, live Claude and physical phones unverified.
  - verify: real renderer font/image/error tests; preview/download byte equality, stale/edited/rejected blocking, no network during rendering.
- [ ] T-POSTER-009 (D-FORMAT-EXPORT-001; D-CREATION-LIBRARY-001/002) Square/story layouts, library/history/reuse and effective-format hashes.
  - verify: all dimensions, unchanged-format confirmation reuse, shared-price invalidation, copy without generation, restored draft/PNG backup.
- [ ] T-POSTER-010 (D-PV-011) Optional reviewed original-photo cutout/background route.
  - verify: rejection leaves scene path usable, original pixel/aspect preservation, transformed shadows, Soundcore award negative case.
- [ ] T-POSTER-011 (all phase-2 designs) Integrated regression and real-device/provider evaluation readiness.
  - verify: full suite/build/browser flows, agreed physical phone checks; report untested paid models/sizes/textures and request only the concrete remaining test scope.

## Next (approved, ordered)

Phase 1 of designs/product-visuals.md (approved 2026-11-06, ADR-012). Verify commands run from `backend/`. Paid runs only with `IMAGE_PROVIDER=openai` + `--paid` and the user's go.

## Blocked

- [!] T-PV-013 (D-PV-008, R-008) Paid evaluation: 5 products to calibrate, then 15; report; recommendation written with the user; then design v2.
  - note: Blocked on the user, and on T-PV-011 (`report`):
    - the fixture photos (~20 products, incl. poor photos and look-alike variants);
    - the arm assignments;
    - the approval thresholds agreed before the run (R-008 c.6);
    - **a cap of about USD 25–30**. At the probe's measured USD 0.17 per scene (ADR-023): 20 × 3 scenes + 20 backgrounds ≈ USD 13.4; with limit 5 ≈ USD 20; plus retries or extra backgrounds.

    Run it in `DATA_DIR=data-openai` with `--paid`.
  - verify: `report` outputs exist for every run; the user approves the recommendation.

## Done (most recent first — prune monthly)

- [x] T-REVIEW-001 (chore) Review the complete implementation and requested editable branded-poster workflow; run the user's real JBL/Soundcore scene smoke test.
  - verified 2026-11-09: `uv run pytest -q` → 432 passed, 3 deselected (116.05 s); source/migration/connected-test review; two additional gaps reproduced in temporary stub data (same-filename photo replacement, admission-screening bypass).
  - paid test explicitly requested by the user (ADR-026): two official product images, `gpt-image-2/high`, two successful calls without retries, USD 0.344220 total, 82–86 s recorded durations; real rembg cutouts also produced. Existing `data-probe` ledger total now USD 0.512881 including the original probe.
  - result: generated scenes look promising; Soundcore cutout retains the source's external award graphic. Candidates remain pending review. No application changes or approval decisions.
  - evidence: `reviews/implementation-review-2026-11-09.md`, `reviews/real-product-scenes-2026-11-09.md`; deliverables in `outputs/review-2026-11-09/`. Links, file existence, sheet image references, output/source hashes, dimensions and cost total checked.
  - next gate: proposed refinement, shadow and poster-flow changes require amended/drafted per-feature requirements and approval, then matching designs. T-PV-013 remains the separate representative shop-photo evaluation.

- [x] T-PV-010 (D-PV-008 `sheet`, `apply`, `new-cycle`)
  - **Code:** `backend/src/affiche/visuals/sheet.py` (`sheet.html` with natural-size images, the 3 crop frames, the `photo_preserved` composite and the French reasons legend; `decisions.csv` UTF-8-BOM) and `evaluate.py`:
    - `sheet --out DIR`;
    - `apply FILE --paid`: two-pass validation including in-file transitions and replays; decisions then generations; uuid5 ids with `k`; per-row error boundaries; strict UTF-8 → cp1252 decoding; `apply-result.csv`;
    - `new-cycle SKU…`;
    - `review.rejection_payload` is shared.
  - **Verified 2026-11-06** (Windows 10, Python 3.12.10):
    - `uv run pytest tests/test_apply.py -q` → 34 passed; `uv run pytest -q` → 432 passed, 3 deselected.
    - Manual stub run: `generate` → `sheet` → approve/reject/revise → `apply` → replay all `already_applied` → confirm + background → `new-cycle`. The page was checked in Chrome: 6 images, the frames, the composite.
    - About 24 mutations killed.
    - Codex r1 APPROVE WITH FIXES (3 P2 + encoding + terseness), r2 APPROVE WITH FIXES (1 P2 regression from the terseness change), r3 APPROVE (docs/project/reviews/t-pv-010-code-r1.md … -r3.md).
    - ADR-024.

- [x] T-PV-012 (D-PV-003 cap section (b)) One paid probe call, with the user's go on 2026-11-06.
  - **Command (from `backend/`):**
    `IMAGE_PROVIDER=openai DATA_DIR=data-probe uv run python -m affiche.visuals.evaluate generate --paid --fixtures fixtures/products.example.csv --photos fixtures/examples --run probe-high --model gpt-image-2 --quality high --only EX-PHONE-NOIR`
    → exit 0 in 60 s. The made example phone was used, not a shop photo.
  - **Verified:**
    - one `provider_calls` row: `succeeded`, `cost_micros = 168661` (**USD 0.168661**), `cost_is_estimate = 0`;
    - **`usage` was returned**: input 1271 (text 169, image 1102), output 5300; the cost recomputes exactly;
    - the call took 55.1 s; the result is a 1088×1920 PNG; the candidate is `pending_review`; the cutout is `proposed`.
  - **The image:** the product layout and colour are kept, no text is added, the height is about 41 %, and it fits the safe square.
  - **Billing:** the user's OpenAI dashboard shows $0.17 and 1 request for November, matching the ledger.
  - Recorded in ADR-023.

- [x] T-PV-009 (D-PV-008 fixtures, runs, `generate`)
  - **Code:**
    - `backend/src/affiche/visuals/fixtures.py` (strict CSV, every error listed, nothing loads if any row fails);
    - `backend/src/affiche/visuals/evaluate.py` (CLI `generate`): an immutable run (model in `RATES`, unique model+quality), the `run_products` snapshot with name/variant/arm/row sha, the scene requests with re-run-safe uuid5 ids, `execute` under `Semaphore(2)`, cutouts in a thread overlapping the calls, per-product error boundaries;
    - `--paid` required with `IMAGE_PROVIDER=openai`;
    - exit codes 0/1/2/3;
    - `fixtures/products.example.csv` + 2 made example photos.
  - **Verified 2026-11-06** (Windows 10, Python 3.12.10):
    - `uv run pytest tests/test_fixtures_generate.py -q` → 33 passed; `uv run pytest -q` → 398 passed, 3 deselected.
    - Manual: `IMAGE_PROVIDER=stub DATA_DIR=<scratch> … generate --fixtures fixtures/products.example.csv --photos fixtures/examples --run stub1 --model gpt-image-2 --quality medium` → exit 0 in 74 s, 2 `pending_review` scene candidates + 2 `proposed` cutouts (real rembg). The re-run is idempotent (6 s, nothing new).
    - 26 mutations killed.
    - Codex r1 APPROVE WITH FIXES (2 P1: the paid opt-in, the cutout error boundary; 3 P2: strict CSV, `--only` vs the snapshot, exit 1 on errors), r2 APPROVE (docs/project/reviews/t-pv-009-code-r1.md, -r2.md).
    - ADR-022.

- [x] T-PV-008 (D-PV-004, D-PV-005 cycles and abandon, D-PV-006 step 2, D-PV-007)
  - **Code:** `backend/src/affiche/visuals/review.py`:
    - `next_status`;
    - `approve` (framing required) and `reject` (reasons/note, note screened);
    - `confirm_cutout` / `reject_cutout`;
    - `new_cycle`, `abandon`, `reusable`.

    Every write is a conditional update with an idempotent replay (`applied` / `already_applied`).
  - **Verified 2026-11-06** (Windows 10, Python 3.12.10):
    - `uv run pytest tests/test_review.py -q` → 31 passed; `uv run pytest -q` → 365 passed, 3 deselected.
    - The tests cover:
      - the 6 transitions (4 refused);
      - `framing_not_checked`, `reason_or_note_required`, `unknown_reason`, `commercial_terms` on the note;
      - cutout decisions;
      - a cycle only after an approval, with a fresh allowance in cycle 2;
      - abandon: the replay first, `request_running` for any request in the scope, `already_approved`, and the admission refusal after;
      - reuse: the exact variant only (prefix trap), newest first, no gateway.
    - 7 mutations killed.
    - Codex r1 APPROVE WITH FIXES (the abandon guard was too narrow; my instruction, not the code), r2 APPROVE (docs/project/reviews/t-pv-008-code-r1.md, -r2.md).
    - ADR-020.

- [x] T-PV-007 (D-PV-003 execution, D-PV-006 background flow)
  - **Code:** `backend/src/affiche/visuals/execution.py`:
    - `async execute(engine, settings, provider, request_id, *, slots, sleep)`: provider inputs → call 1 → at most one retry, reserved with `admission.reserve` in the same transaction → an atomic success (raw asset, cost, `pending_review` candidate; for a background, the baked shadow and `product_box_json`) or a failure;
    - `assets.load` / `assets.extension`.
  - **Verified 2026-11-06** (Windows 10, Python 3.12.10, stub only):
    - `uv run pytest tests/test_execution.py -q` → 24 passed; `uv run pytest -q` → 334 passed, 3 deselected.
    - The tests cover:
      - the slot kept on retry, with no 4th candidate;
      - a budget-refused retry → `failed budget_exhausted`, slot freed;
      - non-retryable kinds with 1 call only;
      - atomicity; the background `cutout_id` / `product_box_json`;
      - provider inputs with no EXIF; the semaphore peak of 2;
      - storage and busy paths; a request that is not running;
      - a usage-based cost vs the kept estimate.
    - 19 mutations killed.
    - Codex r1 APPROVE (docs/project/reviews/t-pv-007-code-r1.md); its non-blocking test gap was closed and checked by mutation.
    - ADR-019.

- [x] T-PV-006 (D-PV-003 rules 1–7, D-PV-005 allowance and scopes) `backend/src/affiche/visuals/admission.py`: `request_scene`, `request_revision`, `request_background` (one `write_tx` each), `reserve` (for call 2), `Refused`, `Admitted`. Migration 0002 adds `run_products.name/variant` (user decision, ADR-018).
  - verified 2026-11-06 (Windows 10, Python 3.12.10, SQLite 3.47.1):
    - `uv run pytest tests/test_admission.py -q` → 36 passed; `uv run pytest -q` → 310 passed, 3 deselected.
    - The tests cover:
      - allowance counting;
      - **two processes at `used = 2` → exactly one admitted, the other `attempt_limit_reached`** (5 of 5 runs);
      - the idempotent replay vs `request_id_reused`;
      - the cap boundary at exactly `cap` and +1 µUSD; the empty ledger; the floor;
      - every `Refused` code;
      - the arm-B plain re-roll;
      - the stale-cycle `wrong_scope`.
    - 30 mutations killed.
    - Codex r1 APPROVE WITH FIXES (4 + 1), r2 APPROVE (docs/project/reviews/t-pv-006-code-r1.md, -r2.md).

- [x] T-PV-005 (D-PV-001 asset store, process lock, crash recovery, provider mode)
  - **Code:** `backend/src/affiche/assets.py` (`put`, `path`, `record`) and `backend/src/affiche/runtime.py`:
    - `acquire_lock` (OS lock, retries up to 2 s);
    - `recover` (owner-scoped);
    - `check_provider_mode`;
    - `start()`: lock → engine → migrate → mode guard → recovery; it releases everything on failure.
    - `db.utc_now()`.
  - **Verified 2026-11-06** (Windows 10, Python 3.12.10):
    - `uv run pytest tests/test_store_lock.py -q` → 13 passed (repeated 5–10 runs green); `uv run pytest -q` → 273 passed, 3 deselected.
    - The tests cover:
      - `put` idempotent, no temp file left on failure;
      - a held lock refused across processes; api and cli independent;
      - after a kill, or a clean exit, the next process takes the lock;
      - crash recovery marks only this owner's running request and call `interrupted`, with the cost kept;
      - the other provider mode is refused, and the lock is released;
      - a failing log after recovery releases the lock.
    - 16 mutations, 15 killed; the survivor (`seek(0)`) was accepted by the review.
    - Codex r1 APPROVE WITH FIXES (2 P2s), r2 APPROVE (docs/project/reviews/t-pv-005-code-r1.md, -r2.md). ADR-017.

- [x] T-PV-004 (D-PV-006 steps 1 and 3) `backend/src/affiche/visuals/cutout.py`: `make_cutout` (mask on a ≤ 2048 copy, threshold, small-hole fill, 1 px erosion, RGBA from source pixels, component check), `place`, `bake_shadow`, `CutoutUnavailable`. rembg 2.0.87, model `birefnet-general-lite` (ADR-016).
  - verified 2026-11-06 (Windows 10, Python 3.12.10):
    - `uv run pytest -q` → 260 passed, 3 deselected.
    - `uv run pytest -m rembg tests/test_cutout.py -q` → 3 passed (real model, about 140 s).
    - The tests cover:
      - the pixel invariants on 3 made samples, EXIF orientation 6 and the > 2048 downscale path;
      - `no_product` / `multiple_products`;
      - placement in the safe square for tall, wide and square boxes;
      - shadow position and strength;
      - colour-profile keep or refuse;
      - session failures, including rembg's `sys.exit`.
    - Samples are generated in the tests, not committed binaries; no shop photos.
    - 21 mutations killed.
    - Codex r1 APPROVE WITH FIXES (2 findings: SystemExit, profiles), r2 APPROVE (docs/project/reviews/t-pv-004-code-r1.md, -r2.md).

- [x] T-PV-003 (D-PV-003 provider call, error mapping, stub, money math) `backend/src/affiche/visuals/gateway.py`: `prepare_provider_input`, `validate_image`, `usd_to_micros`/`cost_micros`/`parse_usage`/`RATES`, `OpenAIProvider` (no retry of its own), `StubProvider`, `make_provider`; `stub_fail` setting.
  - verified 2026-11-06 (Windows 10, Python 3.12.10, openai 3.46.0, pillow 13.0.0):
    - `uv run pytest tests/test_gateway.py -q` → 101 passed; `uv run pytest -q` → 223 passed. The real SDK is driven through `httpx2.MockTransport` (no network).
    - The tests cover:
      - every error-mapping row with retryable / not;
      - the request shape (no `input_fidelity`);
      - strict 1088×1920 validation;
      - cost rounding and usage validity;
      - provider input with no EXIF or ICC, colour handling, and key hygiene.
    - 25 mutations killed.
    - Codex r1 and r2 APPROVE WITH FIXES (6 + 3 findings fixed), r3 APPROVE (docs/project/reviews/t-pv-003-code-r1.md … -r3.md).
    - SDK facts and deviations in ADR-015.

- [x] T-PV-002 (D-PV-002) `Direction`/`SceneSubject` types, `build_scene_prompt`, `build_background_prompt`, reason-code sentences, `find_commercial_terms` (`backend/src/affiche/visuals/prompts.py`).
  - verified 2026-11-06 (Windows 10, Python 3.12.10):
    - `uv run pytest tests/test_prompts.py -q` → 92 passed; `uv run pytest -q` → 115 passed.
    - The tests cover:
      - fixture price, warranty and promo absent from both prompts;
      - the D-PV-002 match and no-match lists, plus decimals, accents and no-break spaces;
      - every reason code has an independent expected sentence or is ignored, per prompt type;
      - `corrections=None, note=None` gives the initial prompt.
    - About 15 mutations killed, including rule 2 removed and reversed or "price badge" sentences.
    - Codex r1 and r2 APPROVE WITH FIXES, r3 APPROVE (docs/project/reviews/t-pv-002-code-r1.md … -r3.md).
    - Interpretations in ADR-014 (background `texte` sentence, the number rule, `corrections_applied` meaning).

- [x] T-PV-001 (D-PV-001, Cross-cutting configuration) Scaffold `backend/`: uv project (Python 3.12), package `affiche`, pytest; SQLAlchemy 2 + Alembic initial migration for the whole D-PV-001 schema incl. `req_one_revision` and `req_one_initial`; settings from `.env` with the startup validation list; `.env.example`; `.gitignore` additions; `write_tx()` with `BEGIN IMMEDIATE`.
  - verified 2026-11-06 (Windows 10, Python 3.12.10, uv 0.11.8):
    - `cd backend; uv run pytest -q` → 23 passed. The tests cover:
      - the migration tables and both guard indexes in `sqlite_master`;
      - WAL and foreign keys;
      - a `req_one_initial` behaviour check;
      - the config refusals;
      - the two-process `write_tx()` wait.
    - `git check-ignore .env` → `.env`.
    - Mutations killed: `BEGIN IMMEDIATE` → `BEGIN`, cap `gt=0` → `ge=0`, `allow_inf_nan` False → True.
    - Codex r1 APPROVE WITH FIXES (2 fixes applied), r2 APPROVE (docs/project/reviews/t-pv-001-code-r1.md, -r2.md).
    - Decisions in ADR-013.
    - The `meta.provider_mode` check is left to T-PV-005 on purpose.

- [x] T-PV-DES (chore) Write docs/project/designs/product-visuals.md, review it, and obtain user approval.
  - verified 2026-11-06: every R-PRODUCT-VISUALS requirement maps to a design section (traceability table); Codex r1–r3 REWORK and r4 APPROVE WITH FIXES (3 fixes applied) plus the devil's-advocate pass are saved in docs/project/reviews/; user decisions in ADR-011; the user replied "go ahead" to the phase-1 approval request (ADR-012).

- [x] T-PV-REQ (chore) Draft docs/project/requirements/product-visuals.md and obtain user approval.
  - verified 2026-11-06: 8 requirements with acceptance criteria; open questions empty (ADR-009, ADR-010); user replied "go" to the approval request; statuses set to Approved in the file and in _INDEX.md.

- [x] T-PV-MOCK (chore) Throwaway mockup of product-visuals for the requirements review: https://claude.ai/artifact/AJdfWgWxzHjewsP6DtXZ2X (private).
  - done 2026-11-05: a clickable phone flow (R-001 to R-007) with scenario tweaks for each error case; a static desktop review screen; two editor comps for open question 4. Grey placeholders only. This is not an approved design and is not code to reuse.

- [x] T-BOOT-002 (chore) Obtain user approval of PROJECT.md and its proposed six-feature split.
  - verified 2026-11-05: The user replied "approved, start with product-visuals". The approval is recorded in the PROJECT.md status line and approval checkpoint, and in ADR-008.

- [x] T-BOOT-004 (chore) Fix the desktop host's Git dubious-ownership error for affiche-ia.
  - verified 2026-11-05: Confirmed sandbox ownership differs from the desktop user; reproduced exit 128 using Git's ownership-test flag; verified the proposed exact-path safe.directory entry resolves it; applied the tested user config preserving existing settings; normal and forced-ownership git worktree list --porcelain -z both return 0. Desktop UI retry is not directly observed.
  - scope: Only C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia is added to the user's Git safe.directory list. No wildcard, ownership change, commit or remote was introduced. Backup retained outside the repository in the chat's work/git-ownership-fix/ directory.

- [x] T-BOOT-003 (chore) Place the project alongside tsena_scan and initialise its local Git repository.
  - verified 2026-11-05: 13 prepared files copied with matching hashes; 25 local Markdown links resolve; requirements/designs remain template-only; git rev-parse resolves to C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia; initial branch main; no refs/commits or remotes. README and .gitignore added, original chat copy retained, final repository state recorded in HANDOFF.md.
  - note: This authorises location and version control only. PROJECT.md approval is still pending.

- [x] T-BOOT-001 (chore) Bootstrap local project documentation from the available templates and revised brief.
  - verified 2026-11-05: 11 expected files present; 19 local Markdown links resolve; requirements/designs contain only _INDEX.md and _TEMPLATE.md; all confirmed constraints recorded; BRIEF.md matches its source; no application manifests introduced.
  - handoff: HANDOFF.md records the exact approval gate, decisions and all local files. No application tests apply because no application code exists.

## Icebox (ideas, unapproved — no design exists yet)

- Requirements drafting after PROJECT.md and its feature split are approved.
- Local AI retouching after the core editing workflow is validated.
- Malagasy, multiple shops, Odoo, publishing integrations, campaign packs, video, and automatic layer extraction in later phases.
