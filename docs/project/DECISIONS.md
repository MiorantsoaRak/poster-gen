# DECISIONS

## ADR-069 — 2026-11-13 — Hosted pilot phase B: round 2 fixes applied, built without Docker (Claude, under the autonomy grant)

- Round 2 on phase B: APPROVE WITH FIXES, five P1 (reviews/hosted-pilot-design-r2-2026-11-13.md). All applied as design v3.1, not reviewed again.
- Choices worth remembering: the session test of the access boundary is narrowed to `/api/` and nothing else is (Origin check and size limits stay on every path); the frontend is served by the application itself behind a boolean; at most two password verifications and one browser at a time, because the container has a hard 1 GB limit on a box without swap; the release stops the old container before it backs up and starts the new one (one SQLite writer), so each release has a short downtime; logs go to journald so that they survive a release.
- What could not be proven here: the development machine gives Claude no access to Docker, so the image was never built, and pyinfra never ran `deploy.py`. `docker compose config`, `sh -n` and `py_compile` pass; the shell text of the deploy parses. The first rollout is the proof, and `deploy/README.md` says so at its top.
- Not Claude's to do: the DNS record, the two changes in the Maizina repository and the Caddy recreate, the pilot's provider keys, the choice of an off-box backup, the commit, the push and the deploy itself.

## ADR-068 — 2026-11-13 — Phase B of the hosted pilot starts before the phone session (Claude, on the user's "next")

- ADR-065 put the server work after the owner's first session. Changed: the session waits on the user and the owner, the server exists and its deployment pattern is proven by PPN Market, and what the session can teach is about the editor, not about hosting. The session through the tunnel stays available and is still the fastest way to see the owner use the application.
- Phase B is detailed in designs/hosted-pilot.md v3: one more compose project on `mx1` in PPN Market's pattern. A fresh review runs before its container files are relied on.
- Limit on this machine: Claude cannot reach the Docker daemon (the user is not in the `docker` group), so the image build and a render inside the hardened container cannot be proven here.

## ADR-067 — 2026-11-13 — Budget for paid calls raised from USD 12 to USD 100 (user decision)

- The user, after seeing that about USD 1.94 was left: "You can update the limit to 100usd". Claude's reading: the whole development and test budget is now USD 100 (about 10.06 spent, about 89.94 left). The pilot's own cap on the server (USD 15 for the first month, ADR-064) is a separate default and is not changed by this.
- Applied on the Linux machine: `SPEND_CAP_USD=100` in `backend/.env`. The ledger does not contain the 5.277673 spent by the study scripts, so the two scripts that start the application on the real data (`outputs/style-study-2026-11-11/serve_local.py`, `deploy/phone_session.py`) cap the ledger at 94.72. The Windows machine's `.env` is not changed.
- A higher budget is not a standing go for paid calls: the user still confirms each paid action by Claude with its cost.

## ADR-066 — 2026-11-13 — The pilot's server is the Hetzner VPS the user already rents, shared with `ppn-market` (user fact)

- The user: "we already have a hetzner vps where ppn run". No server is rented; open question 1 of the hosted-pilot requirements is answered.
- What it changes in phase B: the machine is shared, so the application is one more site of the proxy already there (not necessarily Caddy), on its own Unix user, its own loopback port and with a memory limit on the service. Its facts (memory, disk, proxy, backup option) are not known on the development machine: `ppn-market` has no code or deployment notes here, and no SSH alias points to that server.
- Later the same day the user pointed to the `ppn-market` checkout. Its `deploy/README.md` and a read-only look at the box (`nproc`, `free`, `df`, `docker ps`, no sudo, nothing changed) give: Hetzner `mx1`, 2 vCPU, 3.8 GB with about 1.6 GB available and no swap, 13 GB free; Docker everywhere; Maizina's Caddy on 80/443; pyinfra deploys; backups on the box only. Phase B is therefore one more compose project in PPN Market's pattern, with two changes in the Maizina repository (edge network, site block) and a DNS record. This supersedes the previous point where it says the facts are unknown.
- What it does not change (Claude's choice): the owner's phone session through the tunnel stays first. It is ready today; even a small deployment beside another project needs a look at the server and a review first.

## ADR-065 — 2026-11-13 — Hosted pilot: the owner's phone session first, through a tunnel; design v2 approved (Claude, under the autonomy grant)

- Design v1 put six requirements of server work before the owner's first touch. The devil's advocate argued for one observed session through a temporary HTTPS tunnel to the administrator's machine first. Accepted: it is the audit's own reason for doing this feature at all (ADR-063). Phase A (built now): what any exposure to the internet needs, the long session, the home-screen icon, the tunnel script and the record. Phase B (server, Caddy, backups, deploy, status): designed in outline, started only after the session, with a fresh review.
- The session runs on the test data and its ledger (about USD 2.36 left), not on a new paid data folder.
- Changed after the review (reviews/hosted-pilot-design-r1-2026-11-13.md): no seed command (a style row needs the job that made it; profile and logo are typed once); a fixed 90-day session instead of 30 days sliding (no write on the read path); the copy outside the server is the provider's daily backup, not a pull by rsync from a laptop; forwarding headers are always trusted from loopback, with no setting to forget; the password is verified before the write transaction and IPv6 addresses are limited by /64.
- Requirements amended to match: R-HOSTED-PILOT-001 (French message when the application's process is down; the browser's page when the machine is), 002 (90 days), 003 (no "posters left" figure here; profile and logo by hand; the pilot's keys only on the server), 004 (provider's backup), 006 (session before the server).
- Running the tunnel exposes a paid-capable application to the internet and needs the owner: it stays the user's action.

## ADR-064 — 2026-11-13 — Autonomy grant: Claude passes the approval gates; hosted-pilot requirements approved with their defaults

- The user, asked to approve the hosted-pilot requirements: "so if you have autonomy, you don't have to ask me for approval". Claude's reading: on this project Claude approves requirements, designs and task splits itself, still runs the fresh review and the devil's advocate, records each gate here, and tells the user afterwards.
- Not covered by the grant, by Claude's own limit: paid provider calls (the user wants each one confirmed with its cost), renting a server or a domain, creating provider keys, commit and push, anything destructive on the paid data.
- Under it, R-HOSTED-PILOT-001 to 006 are approved with the seven working defaults: one small rented Linux server in the administrator's name; a sub-domain he owns; a separate pilot cap of USD 15 for the first month; the owner's Android phone with Chrome; one shared password on at most three phones; no test posters, but the profile, logo and saved styles carried over; the administrator observes the first session. Each default is the user's to change.
- `hosted-pilot` is added to PROJECT.md as a seventh feature.

## ADR-063 — 2026-11-13 — Order of work after the end-user audit: hosted pilot first (Claude's proposal; user: "go ahead")

- Asked what an end user would need most, Claude proposed five things in this order: (1) the application on the owner's phone (hosting, HTTPS, long session, home-screen icon, a real-phone session); (2) three inputs and one button, the rest from a shop kit set once; (3) the application reads the drawn texts back itself before the owner's review (live run 6: a scene with an invented line was approved by a person); (4) end with the phone's share sheet and a French caption, story format before square; (5) the owner's path without dollars, "version", "fidélité" or "scène".
- The user answered "go ahead". Claude's reading: start with (1) and draft its requirements; (2) to (5) each need their own requirements later. Why (1) first: until the owner makes a poster himself on mobile data, the other four are guesses.
- (1) is a seventh feature, `hosted-pilot`, outside the six of the approved split. Its requirements are a draft (requirements/hosted-pilot.md); PROJECT.md is changed only when the user approves them.
- Said once and not acted on: Claude would revisit the price drawn in the image (ADR-044), because each price change costs a scene. It stays the user's decision.

## ADR-062 — 2026-11-13 — Mockup gaps closed: accent word as chips, accent colour as swatches, the paid confirmation stays a dialog (user: "do as you recommend")

- The accent word is chosen among the title's own words (plus "Aucun"), no longer typed. Why: the server refuses a word that is not in the title (`headline_accent_not_in_title`); chips make that error unreachable. An accent that the title no longer contains is not sent.
- The accent colour is five preset swatches (blue, night blue, red, orange, gold) and "Autre…", which keeps the browser's own colour picker. The five colours are Claude's choice, not the shop's: the mockup had three and the user has not seen this list.
- The in-place paid confirmation of the mockup is dropped. Why: the dialog built for ADR-059 traps focus, makes the page behind inert and opens on "Annuler", so a held Enter key cannot pay; an in-place panel would lose that.

## ADR-061 — 2026-11-12 — Design D-CREATION-LIBRARY-003/004 approved at v2.1; "Confirmée" only while the file matches the poster (user decision)

- The user approved the design for managing posters and saved styles ("approved, go with your recommendation") after two review rounds and a devil's advocate (reviews/library-manage-design-r1-2026-11-12.md).
- His choice on the one open point: a row says "Confirmée" only while a confirmed file exists for the poster as it is now (a confirmation of the current revision). After a later edit the row falls back to "Approuvée" or "À vérifier" until he confirms again. This amends the wording of R-CREATION-LIBRARY-003 ("a confirmed file exists").
- Decisions of the design worth remembering: "Retirer de la liste" is the existing `abandoned` status plus a new restore route, with no schema change; a style is removed softly (`removed_at`, migration 0011) because old versions still read it; a poster made with a removed style keeps it for new versions; a style creation never fails on its name.

## ADR-060 — 2026-11-12 — Managing posters and saved styles: requirements approved with the working defaults (user decision)

- The user approved R-CREATION-LIBRARY-003 and 004 ("approved, go") without changing the five answers proposed as defaults: a poster of any state can be removed from the list (nothing is erased); no search yet; "Dupliquer" asks nothing; a style is still created from an open poster; a removed style is not recoverable.
- The two criteria that the defaults left out (search, creating a style from the "Styles" page) moved to "out of scope" in the requirement.
- Next gate: the design D-CREATION-LIBRARY-003/004, its review and the user's approval, before any task or code.

## ADR-059 — 2026-11-12 — Editor: hash routes, inert page behind a panel, confirmation for every paid or destructive tap (Claude's choices while fixing the guideline review; user request "fix all of them")

- The view lives in the address hash (`''` new poster, `affiches`, `styles`, or a poster id) and the navigation is plain links; one `hashchange` handler does the routing. A hash is enough for three views and needs no router dependency or server rewrite rule. A route change that fails (for example an invalid price that cannot be saved) puts the previous hash back.
- The three panels (paid confirmation, fidelity review, final check) stay ordinary elements with `role="dialog"`, a small focus directive and `inert` on the page behind. The native `<dialog>` was not used: it sits in the top layer, above the error message, which must stay visible and usable while a panel is open.
- Consequence: nothing behind an open panel can be edited any more (the browser test used to change the price behind the final check).
- "A paid call is never one tap" now holds for the scene refinement, the text proposal and the text material too; discarding unsaved work asks first. All use the existing confirmation sheet.
- Not changed, against the letter of the guidelines: colour transitions on controls, French sentence case, no list virtualisation (`content-visibility: auto` on the rows instead).

## ADR-058 — 2026-11-12 — Logo seal: two rules changed after the paid scenes (Claude's decision under the user's autonomy grant; to confirm)

- The approved design (ADR-057) accepted a disc only from 85 % of the asked diameter and printed the seal at the disc's size. The first paid scene through the application drew the disc exactly in place at 81 % (105 px for 130 asked): it was rejected and the logo removed. Across four real scenes the model drew 77 %, 79 %, 81 % and 107 % of the asked size.
- Changed: the disc is accepted from 60 % of the asked diameter, and the seal is printed at the size the user chose (12 % of the width, 130 px) centred on the disc, larger only if the disc is larger. The small-seal warning is dropped, since the seal is no longer small.
- Consequence to watch: the printed seal reaches about 14 px beyond a 102 px disc on every side. On the two paid scenes nothing was touched. The export guard (the logo covers the disc) is unchanged.
- Also changed: the seal is locked once the poster itself uses a version, not once the product has any version (a new poster of a known product lists that product's earlier versions); a version without a disc chosen on a seal poster unticks the logo.
- Second paid scene, with these rules, centred price on a dark backdrop: the application found the disc and placed the seal. The design and the requirement record the results.

## ADR-057 — 2026-11-12 — Logo as a round seal printed on an empty disc that the scene provides (user decision; R-CATALOGUE-BRAND-005 and D-CATALOGUE-BRAND-006 approved)

- Study with the user's logo (reviews/logo-study-2026-11-12.md, five paid scenes, USD 1.081501 outside the ledger). A logo drawn by the model composes well but redraws the striped ribbon, which carries the national colours. The real file added afterwards is exact but collides unless the scene left its place empty.
- Found in the study: the model draws an empty white disc where asked and composes the price and the contact around it; the program finds the disc and prints the real logo, cut to a circle, exactly on it. The model never draws and never receives the logo.
- User's choices: "add the logo in a round circle", then "smaller footprint", then the full logo at about 130 px in the footer between the price and the contact. The emblem-only crop was offered and not chosen.
- Approved at v2.1 after two review rounds (REWORK, then APPROVE WITH FIXES) and one devil's-advocate pass; the last fixes were not reviewed again.
- Limits accepted: the seal is offered only for one footer (logo and contact, no shop name, title, price and contact drawn), chosen before the first version and locked afterwards; the contact is then at the right; a centred price is untested; removing the logo from a seal poster needs a new version.
- Not adopted: a keyed-colour disc (untested; the white disc worked twice on real scenes), kept as the idea to try if white backdrops fail.
- Tasks: T-SEAL-001 (backend), T-SEAL-002 (editor and renderer), T-SEAL-003 (two paid scenes with the real logo in the shop profile).

## ADR-056 — 2026-11-12 — Design approved: contact drawn in the composition (D-CATALOGUE-BRAND-004 v3.1)

- The user approved v3.1 ("go") after review round 3 (APPROVE WITH FIXES, no P1; fixes applied, not reviewed again). The devil's-advocate pass of this design was done on v1 and is not repeated.
- Tasks: T-SIG-004 (backend prompt and request rules), T-SIG-005 (editor), T-SIG-006 (one paid scene, only with the user's go).

## ADR-055 — 2026-11-12 — The contact is drawn in the composition again; the rendered line is the fallback (user decision; reverses ADR-053's default; amends R-CATALOGUE-BRAND-003)

- Evidence: the first real poster made with the rendered contact (Soundcore Space One, scene `f3714e6b`, 2026-11-12). The prompt reserved 79–88 % of the height for the price and 91–95 % for the contact; the image model drew the pill at about 86–94 %, and the renderer wrote the contact on top of it. The user: "This is why having the contact not part of the comp [is] a bad idea".
- What was wrong in ADR-053 and design v2.1: both relied on "the scene keeps the band calm". Neither review tested that on a real scene. Claude recommended that approach.
- Decision: by default the image model draws the contact as one compact line with a telephone icon, at the left, centre or right of its region, so it composes it with the price. The rendered compact line built in T-SIG-001/002 stays as the fallback when the owner unticks drawing or the contact cannot be drawn.
- Accepted cost: a drawn digit is checked only by the owner's eye at the review, and a new position needs a new version (about USD 0.21).
- Kept from ADR-053: the shop name is unticked by default and never drawn in new scenes; the logo is the uploaded file as a layer; default position right with a logo, centre without; brand as plain text.
- Added: the price label gets a hard lower limit in the prompt whenever a contact or logo region lies below it.
- Open: the logo is still added after the scene, so the same collision can happen under it; the owner can drag the logo for free.

## ADR-054 — 2026-11-12 — Design approved: compact rendered contact, logo-only identity, brand as plain text

- The user approved D-CATALOGUE-BRAND-004 and 005 at v2.1 ("approved, commit and go") after two review rounds (REWORK on the drawn-contact v1, APPROVE WITH FIXES on v2) and one devil's-advocate pass. The round-2 fixes were applied and not reviewed again.
- Implementation is split into T-SIG-001 (layer icon and canvas), T-SIG-002 (editor) and T-SIG-003 (brand as plain text) in TODO.
- No paid call is needed for the contact. One optional scene would test "brand as plain text" and needs the user's go.

## ADR-053 — 2026-11-12 — The contact is written by the renderer, not drawn by the image model (user decision; supersedes ADR-043 for new scenes; amends R-CATALOGUE-BRAND-003)

- Trigger: design draft v1 drew a compact contact in the scene. Its review returned REWORK (layers are placed on the first scene only, no source for the line's width, a contradiction in the refusal rule), and the devil's advocate argued that drawing a phone number is the wrong tool: a wrong digit does silent harm, code cannot read pixels, and the review is one agreement since ADR-051. Review: reviews/signature-design-r1-2026-11-12.md.
- Decision by the user ("B, and yes to the two smaller points"): the contact is the existing text layer with a compact one-line style and a telephone icon, written by the shared renderer. Its position (left, centre, right) and its text change freely, with no new scene. New scenes no longer draw the shop name or the contact; the ADR-043 path stays for stored scenes.
- Also decided: without a logo the footer carries the contact only, and the shop name is unticked by default; the default position is right with a logo, centre without.
- Kept: the price stays drawn by the image model (ADR-044); the logo stays the uploaded file as a layer; the contact keeps its own band under the price; "brand as plain text" is the only brand fallback.
- Given up: contact lettering matched to the headline style.
- R-CATALOGUE-BRAND-003 is amended accordingly: the criterion "changing the contact or its position needs a new scene" is reversed.

## ADR-052 — 2026-11-12 — Requirements approved: discreet contact, logo-only shop identity, brand mark

- The user asked for a smaller but visible contact with a left, centre or right position, a shop identity carried by the logo alone, and asked about the product brand logo. Research: reviews/signature-research-2026-11-12.md. He approved R-CATALOGUE-BRAND-003 and 004 with "go with the new requirement".
- The logo stays the uploaded file placed by the renderer; the image model never draws it. This is Claude's reading of "logo only if the user wants it integrated in the scene", stated to the user before approval, and it keeps R-CATALOGUE-BRAND-002.
- Four open questions were not answered. Working defaults, chosen by Claude and to be confirmed at the design review: without a logo the shop name is still written; the contact defaults to the side opposite the price for a left-aligned look, centre otherwise; the contact keeps its own line under the price; "brand as plain text" is the only brand fallback.
- Next gate: a design, its review, and the user's approval before any task or code.

## ADR-051 — 2026-11-12 — One agreement per review screen instead of one checkbox per point (user decision; supersedes the nine-point review of ADR-050)

- Trigger: live run 6 produced a scene with an invented line ("POUR TOUTES VOS NOTES"). The live script ticked every box once a flag existed, and the user asked what the boxes are for, then asked for one validation with a summary of what to verify, on both screens.
- Decision: the fidelity review and the final screen each show a read-only list of the points to verify and one action: "Tout est conforme, approuver" and "Tout est conforme, confirmer". "Signaler un problème" sits beside the approval. The text group gains the line "Aucun autre texte que ceux ci-dessus", and the image point now reads "Aucun objet ni texte ajouté par l’IA".
- Layout warnings on the final screen are listed with the other points; the one confirmation acknowledges them. Their separate checkbox is removed.
- Backend unchanged: the one click sends every check the server requires (`fidelity_incomplete`, final `checks`, `acknowledged_warning_ids`). The stored record no longer distinguishes points ticked one by one from one agreement; nothing read that distinction.
- Requirements still met: the review covers shape, colour, branding, hardware, unwanted objects or text and integration (product-visuals), and fidelity approval stays separate from final confirmation (poster-editor).
- Open: nothing in the code detects text the image model adds beyond the typed texts; only the owner's reading does (T-SCENE-INVENTED-TEXT).

## ADR-050 — 2026-11-11 — Editor rebuilt to the audited mockup (supersedes ADR-048's layout and look)

- Process: an audit with the design-taste-frontend skill's app-screen rules (run on screenshots and the stylesheet; its inspector was not run because the app sits behind sign-in), then a mockup the user reviewed (https://claude.ai/artifact/8zwVrymwP1up1L12SUS422), then "go for all". The user added three points during the review: the review and final screens, the fact that several versions can be generated and one chosen, and a confirmation before every paid action.
- Look: the skill's dealt "true-black flat" app style (seed 1429845225) on a warm near-black ground. Elevation is a lightness step only; no gradients, glows or resting shadows. Chrome is neutral. The main action is white on black. One hue marks the chosen style and work in progress. Buttons: one 40px pill, three levels. One 16px outline icon set drawn inline. Type stays the bundled Noto Sans (the sheet dealt Inter; no new font was added).
- Navigation: a top bar with three destinations, "Créer", "Mes affiches" and "Styles", with counts. "Mes affiches" and "Styles" are new views; the poster list left the first screen. Styles are created from the editor only, because a style job is tied to a poster.
- Editor: a title row (poster name, save state, progress, undo/redo, the one main action whose label follows the state, and the reason when it is blocked); a rail with Textes, Style and Réglages avancés; a stage with the owner's photo beside the poster; a Versions column.
- Versions: "n sur 12", the chosen one labelled "Choisie pour l’export", each with its state, and a "Nouvelle version" tile. Said before the first scene exists.
- Paid actions (first scene, new version, style from a poster) open one confirmation that says what happens and the estimated cost, or that the demonstration mode spends nothing.
- Fidelity review: three groups. The product (four checks), the image (two checks), and one check per kind of text the image model drew, each showing the typed words: title and subtitle, price, shop and contact. Backend: `TEXT_CHECKS`; `decide` refuses `fidelity_incomplete` when a drawn text is not ticked. Scenes without drawn text still need the six checks only.
- Final screen: facts strip, the four existing checks with a counter, then after confirmation the download, "Nouvelle affiche" and "Changer le prix" (returns to the price field and explains that a new version is needed).
- Verified: 690 backend tests; 26 Vitest; build; browser smoke in bundled Chromium and Edge 156. Not verified: a live paid run after the rebuild, a real phone, a contrast audit with a tool.

## ADR-049 — 2026-11-11 — Usability pass after the owner's first real session

- User report: two ways to import a reference; a new user does not know what to do; he added a photo, title, price and a reference, chose the Claude composition, and a button stayed grey with nothing on screen saying why.
- What the database shows for that session: three `plan` jobs with `kind='plan'` failed with `invalid_plan` (Claude's composition did not pass validation; USD 0.048572 in total). The editor's only message was a generic line at the top of the page, out of view, and in that mode the Generate button exists only after a valid plan. The Claude composition had never been run against the real model.
- Decisions:
  - The editor no longer offers the Claude composition. The simple composition with looks is the only path; the API route and code stay. Fixing the planner is a separate task (T-PLANNER-CLAUDE-INVALID).
  - One way to use a reference poster: "Créer un style depuis une affiche". "S’inspirer d’une affiche" (a second image passed to the image model) is removed from the editor; the API still accepts `style_reference_asset`. The study had measured little gain from it.
  - Every blocked main button states its reason beneath it (draft, generate, save style, final preview). A style name is optional (default "Style N").
  - A coach line above the stage always says the next action.
  - Errors and notices are fixed on screen (errors at the bottom, notices under the header) with a "Fermer" button; the fidelity check and the final preview open in front of the page instead of below it.
- Verified: 26 Vitest, build, browser smoke in Edge 156 (it now asserts the coach line, the reasons and the absence of the removed controls), and by eye in Chrome on the production build with the data-probe data. Not verified: the review sheets by eye in Chrome, a real phone.

## ADR-048 — 2026-11-11 — Interface designed as an image-generation tool (supersedes ADR-047's look)

- User feedback on ADR-047: the hard-shadow "printer's proof" look is an overused template; then: "think like if you were designing a UI for an image generation AI tool".
- Decision: keep ADR-047's three numbered steps and wording, replace its visual language and layout with the conventions of image-generation tools.
  - The result is the hero: a dark, neutral stage in the middle; the generated poster is the only bright thing on the page.
  - Controls are a compact rail on the left (01 Textes, 02 Style et génération, 03 Vérifier et télécharger). On a phone the stage comes first and the rail follows.
  - Generations are a filmstrip under the stage ("Versions de la scène"), no longer a list inside the rail.
  - While a scene is generated the stage itself shows it (a light sweep and a "Génération en cours…" chip), in addition to the rail status.
  - Style presets are a three-column wall of real result thumbnails with a check on the selected one.
  - One warm "safelight" orange is reserved for Generate and Export; no purple, no gradients on surfaces.
  - A light variant (header button "Thème clair", remembered on the device) exists for bright daylight.
- No font or dependency added; no logic change besides the theme toggle and the stage class.
- Verified with the stub browser smoke in Edge 156 after the last change (screenshots in outputs/editor-smoke/). Not verified: bundled Chromium after this restyle, the light variant in a browser, a real phone, a contrast audit, the live paid flow.

## ADR-047 — 2026-11-11 — Interface direction: printer's proof, three numbered steps

- User request: a modern, usable interface for the shop owner, any direction allowed except the default AI template; use the ui-ux-pro-max skill.
- The skill's generated system (pink brutalism with a scroll-storytelling landing pattern) fits a marketing page, not a working tool; its accessibility, touch and form rules were kept, its palette and pattern were not. A web search for professional poster-tool references returned only general 2026 trend articles (the editor recedes behind the content; warmer, less glossy surfaces), no Dribbble or Behance examples: the direction below is a design judgement, not a copy of a reference.
- Direction: "épreuve d'imprimeur". Warm paper background with a dot grid, ink-black frames and hard offset shadows, one vermilion signal colour reserved for the action that moves the poster forward, gold for hover/focus and work in progress, crop marks around the poster. Display type is the already bundled Montserrat Black Italic, text is Noto Sans: no new font, no network.
- Flow: the sidebar is three numbered cards with an anchor rail: 01 Textes (title, price, brand, subtitle, accent word, shop identity, one closed disclosure for what the AI draws), 02 Style et scène (looks as a contact sheet with always-readable names, create a look, generate), 03 Vérifier et télécharger (export, with layer-level editing under "Réglages avancés"). Nothing was removed; every label kept its wording.
- Fixed on the way: look names were white on white; the header button wrapped on phones.
- Verified with the stub browser smoke in bundled Chromium and Edge 156 (screenshots in outputs/editor-smoke/: intake.png, studio-start.png, desktop.png, mobile.png). Not verified: a real phone, a contrast audit with a tool, the live paid flow after the restyle.
- Revisit if: the owner finds three cards on one scrolling column slower than separate screens.

## ADR-046 — 2026-11-11 — Saved looks written by Claude from a reference poster

- User request after the exploration ("go"), with one requirement: the look is saved beside the others and reusable for later posters. The user's go replaced the separate requirements/design files for this feature; this entry and backend/api/README.md hold the contract.
- Flow: the owner uploads a poster he likes (existing `style` asset role) and names it. Claude returns a `StyleBrief` (French direction and surface, lighting, camera, palette, accent colour, English headline typography, left/centre alignment). It is stored in `looks` (migration 0010) and shown in the picker with the reference as its thumbnail.
- Trust boundary: the brief is validated and screened like any art direction (no prices, currency, long numbers, instruction wording, quotes), once when Claude answers and again before it is stored. A scene request names a look by `headline.look_id`; the server reads typography and alignment from the shop's own stored look. The client cannot send typography text. An unknown or foreign look is 404, never a silent fallback.
- Prompt: `compile_scene` takes `headline_style` and `align`. Left alignment moves the headline and the price label to the left edge; the shop signature stays centred.
- Queue: a brief runs as a planner job (`kind='plan'` with a `look` payload) because job kinds are fixed by applied migration 0006; `get_job` reports it as `look`, after the browser smoke showed the editor loading it as a plan. It uses the planner budget estimate and the same spend cap. At most 24 looks per shop; no delete yet.
- Measured in the live application (Edge, real Claude and image providers): the Select 4 Go poster became the look "Vagues bleues"; a CMF Buds 2a poster made with it has the left-aligned headline, the left price pill, the blue waves and the blue accent word, with every text exact. Brief USD 0.008612; scene USD 0.210283.
- Revisit if: owners need to rename or delete looks, or briefs start carrying words from the reference.

## ADR-045 — 2026-11-11 — Twelve scenes per poster

- User request: raise the scene limit so price changes are not blocked (ADR-044 made each price change a new scene).
- Decision: `jobs.SCENE_LIMIT = 12` scene/refinement jobs per creation (was 3, hard-coded). Failed jobs still do not count. The spend cap remains the money guard; the limit only stops a runaway loop on one poster. The French message now says twelve and points to a copy.
- The phase-1 evaluation limit (`ATTEMPT_LIMIT`, runs table, 1–5) is a different mechanism and is unchanged.
- Revisit if: owners reach twelve in ordinary use.

## ADR-044 — 2026-11-11 — Price drawn by the image model (explicit user decision)

- Status: explicit user choice: "make the price part of the comp, so if the user want to change it later, he need to re-gen again". Reason given: an overlaid price is visually inconsistent with the rest of the composition.
- Decision: `Headline.price` (default on in the editor) lets the image model draw the price label. The amount is `offer.price_ar`, an integer formatted in code as "340 000" + "AR"; no free text can carry an amount (brand/subtitle/direction screening is unchanged). The job payload records `price_ar`.
- This supersedes, for posters that use the option: ADR-042's "the price is never sent", and the project rule "reuse approved visuals for price-only changes" (AGENTS.md updated). A price change now costs one new scene (about USD 0.21) and a new fidelity review. Turning the option off restores the exact editable pill and free price changes.
- Guard: the drawn amount must equal the offer's amount whether or not the price layer is shown; a hidden price layer needs a drawn price. Otherwise render/confirm refuse 409 `price_stale` and refinement refuses `headline_stale`. `Document` no longer requires a visible price layer; export does that check with the scene.
- Measured: 2 of 2 live application scenes drew "340 000 AR" exactly, and with the pill in the composition the model kept the product clear of it without help. Two images are a small sample: the fidelity review must read every digit.
- Found by the live Edge run, not by the unit tests: the first-scene code skipped hiding a price layer that already carried pill styling, which would have doubled the price. Fixed; the regression test now styles the pill first.
- Open: a creation still allows three scene/refinement jobs in total (`attempt_limit`), so repeated price changes on one poster will need a copy. Not changed here.

## ADR-043 — 2026-11-11 — Shop name and contact drawn by the image model

- Context: the user found the overlaid shop name/contact poorly integrated and asked whether the AI could compose them too. Measured first: 3 of 3 direct study images and 2 of 2 live application scenes rendered "Original Phone Mada" and "038 93 028 00 / 034 93 028 00" with every digit correct, in the poster's colours with a handset icon. One of the five wrote the shop name in capitals.
- Decision: `Headline.signature` (default on in the editor) lets the image model draw the shop name and/or contact that the poster includes. The words come only from the poster's profile snapshot, never from the request. One line each, at most 80 characters, no quotes; otherwise they stay editable layers. The price is still never sent.
- Guard, also tightened for the title: any word the image model drew must still equal what the poster says, whether or not the layer is shown again, and a hidden layer must be replaced by drawn words. Otherwise render/confirm refuse `title_missing` / `signature_missing` and refinement refuses `headline_stale`. Unticking a contact that the image shows is refused the same way. `Document` now allows an included shop name/contact layer to be hidden.
- Layout: with an AI-drawn signature the editor gives the plan the real two-line footprint (48 and 56 px) instead of the default layer boxes; the prompt states the product's lowest edge as a hard limit above the price label. Live run 3 against run 2: the pill went from covering the lower ear cup to touching only its bottom rim.
- No migration or dependency. Earlier payloads without `signature` replay unchanged.
- Revisit if: a wrong digit is ever seen at the fidelity review (then default the option off), or the shop wants a multi-line contact.

## ADR-042 — 2026-11-11 — Integrated headline, house-style scene prompt and style looks

- Context: the user gave autonomy to change the process so that generated posters reach the level of Original Phone Mada's own recent posters, with a 5–10 product test. Ten shop posters were inspected (reviews/style-study-2026-11-11.md). Their common language: product filling most of the frame at a three-quarter hero angle, calm gradient with large curved bands tinted to the product, brand + heavy two-tone product name + spaced subtitle, dark price pill. Their 1254²/1086×1358 sizes suggest (hypothesis, unconfirmed) that they are AI-generated whole.
- Measured: a text-free plate with the new prompt fixes scale and backdrop, but an overlaid single-font title still looks plain. When GPT Image 2 also sets the headline, 11 of 11 images rendered every word verbatim (French accents included; six were read on reduced contact sheets only) and matched the references' typography.
- Decision: the image model may set **brand, product name and subtitle** in the scene ("integrated headline"), default on in the editor. The **price never enters the prompt** and stays an exact editable layer, so price-only changes still reuse the approved visual. The product name is always taken from `offer.title`, never from the plan or the planner. This partly supersedes ADR-030 (all text as separate layers) for the title only; the layer remains available by turning the option off.
- Guards: brand/subtitle/accent word are screened (currency, promotion, instruction wording, quotes, line breaks; digits allowed because model names contain them; "réduction de bruit" is exempt from the promotion blocklist). The job payload records the exact title sent. The title layer may be hidden only when the selected scene's recorded headline title equals the current offer title: otherwise render/confirm refuse `title_missing`, and a refinement refuses `headline_stale`. The fidelity review remains the check on spelling.
- Prompt: rewritten in the provider-recommended order (use, references, scene, subject, light, layout, constraints) with a house style that the shop's art direction can override. Subject scale is stated against the plan's product area; quiet zones are stated as full-width bands. An example of components ("both earbuds…") was removed after it made the model add earbuds to a speaker: the prompt now says to show only what the photos show.
- Style choice: three measured looks (Studio clair, Aux couleurs du produit, Luxe sombre) plus free text, picked from thumbnails, with one accent colour. A look sets the French art direction and the plan palette; no schema change.
- No migration, no dependency. `headline` is omitted from request/payload when absent, so earlier idempotency keys and hashes replay unchanged. Old plans recompile with the new prompt on their next scene request only.
- Study spend was made by direct provider calls outside the application ledger (USD 3.05, outputs/style-study-2026-11-11/spend.json): treat the remaining budget as cap − ledger − 3.05.
- Revisit if: a headline is misspelt in real use more than rarely, or the shop needs to edit a title without a new scene.

## ADR-041 — 2026-11-10 — Editable reference typography and price capsule

- User's “font and price format too” extends the evaluation under approved R-POSTER-EDITOR-003 and supersedes ADR-040's font/capsule limitation. Register unmodified OFL Montserrat Black Italic (900), a close match rather than an asserted identification of the reference font. Keep Noto files unchanged.
- Add optional `price_badge` to price only: white fill, two blue border colours, thin rounded outline, exact grouped amount and smaller upright Noto Sans AR. Both runs and capsule remain one selectable/undoable layer. No arbitrary shape nodes, duplicate monetary content, font upload or rich-text engine.
- Upstream Montserrat Black Italic lacks narrow NBSP U+202F. Its price/capsule grouping uses the supported NBSP U+00A0; Noto plain-price formatting is unchanged. Verify French glyphs, real 900/italic metadata and hashes, never synthesize a font or fall back silently. Canvas clipping checks include measured italic ink beyond the advance box.
- Reach: model/Claude patch validation, font manifest/loader, shared geometry/material renderer, properties UI, export font fingerprints, API contract, tests and real poster. Omit null badge from canonical data to preserve old hashes/replays. Fingerprint the extra currency font. No migration/dependency; retain earlier PNGs and confirm a new revision without another image call.

## ADR-040 — 2026-11-10 — Reference-guided white studio evaluation

- User supplied the November 5 DJI Mic Mini poster; preserve the exact attachment and use it only as the last style reference. Reuse the exact black R50i original and dated 90,000 Ar fixture in a separate creation, existing paid ledger and cap. The DJI product, logo and 600,000 Ar price must not carry over.
- Translate the inspected reference into a white/very-light-grey curved studio, floating product hero and soft contact shadow; use a manually revised plan with matching palette and centred editable blue title/black price. Keep Original Phone Mada and contact as separate selected text layers. Use existing composition API/renderer only; no new schema, fonts or shape nodes for this evaluation. The current font set cannot reproduce the reference's italic mixed-colour title or outlined price capsule exactly; report that limit instead of flattening commercial text into the scene.
- Verify both references and prompt roles before paid dispatch; inspect generated product fidelity, polish the saved layout, inspect authoritative PNG and confirm/download exact bytes. Preserve the previous dark poster and its runner state. Record live cost from the same ledger.

## ADR-039 — 2026-11-10 — Connect the approved style-reference path

- Scene/refinement requests accept an optional owned `style_reference_asset` SHA-256 uploaded with role `style`. Validate ownership, role and bytes before reservation and again before dispatch; append it after original views (and base, for refinement). The reference supplies appearance only, never product identity, lettering, claims or prices.
- Reuse immutable job JSON for the reference hash and return it with visual provenance; no schema migration or new provider transport. Keep original-photo comparison separate. Omitted/null style fields retain old idempotency hashes so existing uncertain requests remain replayable.
- Scope: scene/refinement contracts and admission, worker preparation, visual provenance, editor upload/reuse, domain/HTTP/browser regressions, and the requested paid style evaluation. Existing exports, prices and confirmed PNGs are unchanged. The live evaluation requires an actual inspected poster; inaccessible mirror images are not evidence of its style.

> Append-only log, newest first. Record context, decision, rationale, alternatives, and conditions for reconsideration. Reversals get a new entry. A confirmed constraint does not approve a design or library choice.

## ADR-038 — 2026-11-10 — Authoritative local PNG export

- Render the saved feed document with the existing PosterCanvas in a pinned headless Chromium process. Serve only trusted bundled files through intercepted virtual HTTPS routes; inject validated assets/fonts as data, block every other request and close the context on failure. No local unauthenticated asset server, model call or provider credential is involved.
- Preserve alpha/EXIF/colour using a shared bounded sRGB preparation function for editor and server sources. Record original/prepared hashes, font manifest and renderer build. A stored successful PNG is the confirmation/download authority; new edits require a matching preview and cannot replace old confirmed bytes.
- This completes the requested feed poster first. Square/story/library enhancements and optional cutout remain their own queued tasks; real product validation follows the feed export, not an expanded template catalogue.

## ADR-037 — 2026-11-10 — Isolated prompted typography

- Implement approved D-POSTER-EDITOR-003 using the existing job ledger and retry-free Claude transport; no second queue or arbitrary JSON Patch API. Store immutable proposal/effect provenance in a new migration, and apply only a selected title/price layer after checking the originating revision.
- Exact text always comes from bundled fonts. A proposed title must occur in explicit quotes in the instruction; a price must match a single explicit literal Ariary amount. Content changes require separate acknowledgement. Reject other target roles or unrepresentable changes; manual controls remain usable.
- The installed Konva Text renderer uses CanvasPattern directly in CanvasRenderingContext2D.fillText. Reuse this native glyph mask rather than maintaining a second custom offscreen lettering renderer; the exact font glyphs, layer outline/shadow and pixel-isolation contract remain the same. Verify changed pixels with actual Chromium renders.
- GPT generates a text-free material swatch only after an explicit action. Clip it locally to exact font glyphs in the shared canvas. This supplies editable metallic/patterned typography without trusting generated price spelling or re-rendering the scene. Reconsider surface-embedded effects only after separate approved requirements.

## ADR-036 — 2026-11-10 — Editor presentation and shared canvas

- The approved French shop workflow remains the scope. Desktop: poster canvas beside a properties/layers column; mobile: canvas above contextual controls. Intake and scene review use ordinary labelled forms. The poster is the visual focus; no decorative metrics/cards, fake product handles or HTML poster templates.
- Compact palette: workspace #F1F5F9, panel #FFFFFF, ink #17324D, action #186C80, divider #D6E2EA, error #A43139. Noto Sans for interface and default poster text; Noto Serif is the approved alternate poster font. Poster colours are editable independently of application chrome.
- Sketch: desktop [toolbar above canvas | selected-layer controls]; mobile [toolbar / canvas / selected-layer controls]. Align forms and reading text left; use clear spacing instead of repetitive card shells. This follows the subject's image-editing task, not a marketing landing-page layout.
- Frontend-design skill reviewed against the approved brief before code. Use one shared Vue/Konva renderer, a small serial autosave state helper and native accessible controls; no state-management/UI-kit dependency unless actual complexity requires it.
- Node 22.14 and npm.cmd 10.9.2 are available. npm.ps1 is blocked by PowerShell policy; using the shipped .cmd entry point avoids changing system policy. Official Vite and Konva Vue/Transformer docs checked.
- Pinned Vue 3.5.45, Konva 10.9.1/vue-konva 4.0.1, Vite 8.3.7/plugin-vue 6.0.10, TypeScript 5.9.3/vue-tsc 3.3.14 and Vitest 5.1.0 after checking engines/peers. npm install reports zero vulnerabilities. FontTools 4.68.0 builds a checked glyph/hash manifest; Playwright 1.64.1 supplies the browser verification and approved later renderer, with its pinned headless Chromium. No system execution-policy changes.
- Four unmodified Noto static fonts are bundled from the upstream noto-fonts archive with OFL licence. Manifest generation checks French/narrow-space glyphs and 400/700 weights. Browser font loading checks SHA-256 and reports missing glyphs, avoiding silent substitution.
- Browser testing found an upload race immediately after sign-in; inputs now stay disabled while intake/profile loading finishes. Uncertain mutations retain their key; unchanged scene plans retain their ID so retrying a lost scene response returns the admitted job instead of spending again. The Chromium smoke deliberately drops that response and proves only one scene job exists.
- Conflict recovery explicitly offers saving local edits into a copy or discarding them and loading the current server version. It never reloads the stale object originally opened. Job polling ignores responses for a different opened creation; completed planner jobs can be recovered after reload.
- Desktop canvas fits available height; phone controls retain page scrolling unless object movement is enabled. Native crop/position sliders and keyboard movement complement drag. The simulated browser test covers undo, reopen, conflict copy, long-text and unsupported-glyph warnings; this is not physical-device validation.

## ADR-035 — 2026-11-10 — Scene integration and real-draft composition fixes

- T-005 adds forward-only migration 0007 for immutable plans and reviewable visuals, uses original images directly, and keeps generated-image access scoped through owned visual records. Pending/rejected visuals remain editable drafts; final approval/export checks belong to the renderer task.
- The fixed planner now allocates footer/title/price regions from the current layer boxes rather than hardcoded small rectangles. This fixes actual initial-draft widths and contact/logo heights; a layout that leaves insufficient product space is refused explicitly. Bundled-font measurement and layout polish remain T-006.
- Scene completion selects only the first candidate when the originating revision is still current and has no scene. Refinements remain alternatives, retain the selected base, and identify base/original roles separately. Generic draft saves validate same-input visual ownership and a crop bounded by the image with the target format's aspect ratio.
- Workers use admitted model/rate snapshots, immutable original hashes and a local spool. Two provider slots run inside the API owner process; scheduler errors are recorded/logged without exposing raw provider data or replaying uncertain calls.
- The public Soundcore R50i fixture is a product set (earbuds and case), so the scene compiler explicitly preserves visible components while refusing duplicate products or invented extras. No model may invent the commercial offer.
- Focused integration verification: 80 plan/visual tests passed, including all eight branding combinations, late-result preservation, approved-base/rejected-refinement history, manual plan rebase, ownership/crop refusal, no-call price-only edits and actual HTTP scene/review flow. Full regression subsequently passed: 625 passed, 3 deselected (138.83 s). No paid calls yet.

## ADR-034 — 2026-11-10 — Scene planner implementation and durable queue boundary

- T-POSTER-003 uses the installed httpx2 transport directly for retry-free Claude Messages requests; strict schema and semantic validation remain local. Only the verified Sonnet model/rate card is accepted. Unexpected model or billed cache categories retain the conservative reservation rather than assigning an invented price.
- Fixed plans reserve measured field space without receiving commercial values. Image prompts use only validated scene fields, identity references and geometry; display summaries cannot inject image instructions. Base scene and style references have separate image roles. Compiler revalidates mutable model objects before use.
- Verification: full backend suite 579 passed, 3 deselected; final revalidation addition then passed all 62 planner tests. No live Claude/image calls.
- Queue implementation reuses shared mutation transactions and extends spent_micros to both ledgers. Feature-specific input/reference validation stays in the same admission transaction. Dispatch is recorded before sending, and durable local results are finalised without another paid request.
- T-004 verified: full suite 607 passed, 3 deselected (124.68 s). Migration 0006, reservation/replay/concurrency, cancellation races, slots, terminal allowance, 429-only retry, ambiguous failure, disk/commit failures and local spool recovery are tested. No paid database migration or live call.
- A contract check also made PNG output explicit in both existing OpenAI request paths; requested dimensions and omission of input_fidelity remain unchanged.

## ADR-033 — 2026-11-10 — Usable shop-poster test and scene-planning boundary

- User explicitly requested continued implementation until a JBL or Soundcore test produces a usable Facebook/Instagram poster, using Original Phone Madagascar found through their Edge session, and authorised reasonable implementation defaults. This authorises a bounded real test within the existing configured global cap; preserve the existing paid ledger and record every new call. It does not authorise posting, messaging, deployment or invented commercial facts.
- Edge's logged-in Facebook shortcuts identify Original Phone Mada at https://www.facebook.com/MiaryAndrian10/. Navigation is currently unverified: input reported missing geometry and capture/recovery failed with "window capture timed out: timed out waiting on channel". Stop UI input; public search can supply corroborating public facts while implementation continues.
- Scene plans use strict local validation; Claude's wire JSON schema removes unsupported numeric/string/array bounds and describes them instead. Local validation remains authoritative. Official structured-output docs document these limits: https://platform.claude.com/docs/en/build-with-claude/structured-outputs. The fixed builder is explicitly labelled and never presented as a Claude response.
- Extend the existing image gateway with an explicit size while preserving the legacy default; original-photo identity references and a refinement's selected base have separate compiled roles.

## ADR-032 — 2026-11-09 — First poster implementation slice

- Domain persistence uses strict Pydantic documents and existing SQLAlchemy BEGIN IMMEDIATE transactions; canonical request+revision hashes preserve lost-response replays before stale-version guards. Migration 0004 adds only the input/profile/draft tables needed now, leaving evaluation tables and cost records intact.
- Original uploads are decoded/colour-validated without rembg and stored unchanged. Asset writes verify existing bytes and recover only from a concurrent destination that contains the expected bytes.
- Until the scene/effect tasks supply owned reviewable records, draft saves explicitly reject generated references. Font IDs are validated now; bundling and measured layout remain the renderer task. No silent placeholder image or font substitution.
- Verification: full backend suite 513 passed, 3 deselected; actual local Uvicorn HTTP session smoke passed. Tests cover auth/Origin/private assets, schema/money boundaries, original-byte preservation, all eight identity choices, revision/replay/concurrency and rollback. Postman status remains unsupported by the installed WindowsApps executable; verification uses local pytest/ASGI and actual HTTP, without a cloud workspace.
- HTTP implementation follows the approved opaque cookie session (not JWT), Argon2 via pwdlib, exact Origin checks and persisted failed-login counters. API-only settings must not break existing CLI startup. Official FastAPI guidance checked: https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/ and https://fastapi.tiangolo.com/tutorial/request-files/; installed signatures remain the implementation check.

## ADR-031 — 2026-11-09 — Poster technical designs approved

- User: "approve", responding to the six-file design approval packet and explicit implementation gate.
- Decision: approve ADR-029's architecture and all six phase-2 designs, including the separate editable typography/effect approach in ADR-030. Proceed with independently verifiable implementation tasks in TODO, preserving the phase-1 evaluation tools and ledger.
- First slice: immutable product inputs, shop snapshots, strict document/price validation and atomic versioned drafts; then the authenticated HTTP boundary. Reuse existing SQLAlchemy transactions and content-addressed files. No deployment, commit or new paid provider call is implied.

## ADR-030 — 2026-11-09 — Prompt-assisted text with separate editable effects

- User requested title/price typography controllable through prompts as well as manual editing, with changes confined to the selected element. In the clarification they chose "Separate text/effect layers first (Recommended)" over text embedded into scene surfaces.
- Requirement decision: keep the clean product scene, exact title/price values and independently editable text/effect layers. Both manual controls and prompt proposals can target a selected text element; preserve other layers, version history and explicit review. No whole-poster regeneration for a text-only polish. Surface-embedded lettering is deferred.
- Added approved R-POSTER-EDITOR-003 from this explicit request/choice. Implementation mechanics remain Draft design: Claude proposes a validated selected-layer patch; the renderer draws exact fonts/glyphs; optional GPT Image texture is clipped to that layer's glyph mask. Image-generated glyphs cannot guarantee exact spelling/font or remain ordinary editable text, so they are not the source of authoritative letters/prices in this first version.
- Limit: changing a text layer changes its occupied pixels; underlying scene/other-layer content remains untouched. A prompt alone does not guarantee pixel preservation. Approval of this requirement does not approve the pending technical designs or extra paid tests.

## ADR-029 — 2026-11-09 — Proposed phase-2 architecture (design approval pending)

- Status: Proposed, not implementation approval. Covers the requirements approved in ADR-028.
- Use one FastAPI process, the existing SQLite/asset store, a durable local job queue and a Vite/Vue editor. Add phase-2 tables with forward-only migrations; retain phase-1 evaluation data and rules. Both call ledgers count toward the same budget transaction.
- Use Konva + vue-konva with a versioned application document, rather than serialising library nodes. One shared Vue canvas component renders interactive drafts and read-only headless Chromium previews. Store the server-rendered PNG before user confirmation; confirmation freezes its bytes and download never regenerates it. Fabric and native SVG remain evaluated alternatives, not additional implementations.
- Reuse GPT Image edits and the existing adapter, extending its explicit size argument rather than creating another image client. Initial comparison baseline remains gpt-image-2/high; original images and selected base scene have explicit separate roles. No cutout dependency on this path.
- Claude Messages receives image references and produces a validated ScenePlanV1. Proposed evaluation model: claude-sonnet-5-5, configurable with recorded rates/model metadata; access/quality/cost are untested. Fixed-prompt fallback is explicit. Authoritative title/price/contact/logo never come from either model.
- Evidence checked: installed OpenAI SDK accepts image sequences and size; official OpenAI guide documents gpt-image-2 custom sizes and omission of input_fidelity; official Claude docs document structured outputs and current model ID; Konva documents Vue bindings, application-state persistence and export; Playwright documents Python Chromium support. Links and discovery limitations are recorded in the design files.
- Orbit discovery/integration was used for both providers. Its OpenAI collection is incomplete/outdated (single-file/mask example, no concrete response); installed SDK and official provider documentation take precedence. No provider calls, credentials or product images were sent during discovery.
- Revisit: multiple shops/processes, measured queue contention, renderer fidelity failures, or comparative product-fidelity results. These are reasons to change the design, not infrastructure to add now.

## ADR-028 — 2026-11-09 — Poster requirements approved

- User: "go aheadt with the requirement", responding to the explicit approval request for requirements/_INDEX.md and its six files.
- Decision: Approve the 13 new requirements: catalogue-brand 001–002, generation-jobs 001–002, product-visuals 009–011, poster-editor 001–002, format-export 001–002, creation-library 001–002. Earlier product-visuals 001–008 remain the phase-1 baseline; the approved amendments govern normal poster drafts.
- Next authorised work: matching technical designs, including a complete feed-format slice and extension to square/story. The representative-photo evaluation remains a release-quality gate, not a reason to delay these newly authorised designs. No new paid calls or implementation are implied by design work; design approval remains the next explicit project gate.

## ADR-027 — 2026-11-09 — Accepted review direction and corrective work

- User: "go ahead with the recommendations and any fix from your tests", then explicitly favoured GPT Image recreation/integration over forcing a cutout into a scene.
- Decision: GPT Image receives original product references and generates the integrated scene as the primary product flow. Cutout is optional and must never gate that flow. Product fidelity still requires review; do not promise exact pixels from a generative model.
- Authorised now: repair the two reproduced implementation gaps under existing R-PV-003/007 and D-PV-002/008, with regression tests. New poster/editor/planner/refinement criteria are drafted under the existing six-feature split; the explicit requirements/design gates still apply to their implementation.
- Snapshot repair: add ordered original asset hashes with forward-only migration 0003; keep the existing CSV hash. Legacy NULL means unverified, never a hash inferred from current files. Refuse `generate` for an unverified existing product; existing stored candidates remain readable/reviewable through `sheet`/`apply`. Do not rewrite historical evidence or reset a spend ledger to bypass this guard.
- Screening repair: the shared admission boundary checks the resolved description before spend; idempotent replay stays first. CSV validation remains for aggregate diagnostics.
- No new paid calls, commit or push are needed for these fixes. Existing JBL/Soundcore outputs remain pending review.

## ADR-026 — 2026-11-09 — User-authorised real-product scene smoke test

- Status: Explicitly requested by the user during T-REVIEW-001.
- Decision: Source one JBL and one Soundcore product image from official public pages and generate one scene for each through the existing backend, within the configured spending cap. Record source URLs and original hashes, inspect the results and report actual usage. No automatic creative revisions or model comparison.
- Rationale: The user asked for real-product evidence instead of relying on the synthetic phone probe. These manufacturer images are a two-product smoke test, not the representative shop-photo evaluation T-PV-013.
- Scope: This authorises the two scene requests and their existing bounded transport-retry behaviour. It does not approve a redesigned editor, Claude integration, or publishing the images as shop advertisements.
- Result: Two first-call successes, USD 0.344220 combined usage cost; existing `data-probe` ledger reused (USD 0.512881 including prior probe). Scenes look promising; Soundcore cutout retained external award artwork. Evidence in `reviews/real-product-scenes-2026-11-09.md`; no approval decisions applied.

## ADR-025 — 2026-11-09 — Review the whole poster workflow before resuming implementation

- Status: Review scope requested by the user; product recommendations remain unapproved.
- Context: The user requested a review of all implemented changes and reconsideration of photo/title/price generation, polishing, optional shop identity and Claude scene prompts, without treating existing choices as fixed.
- Decision: Complete T-REVIEW-001 instead of automatically resuming T-PV-011. Assess committed and pending work, verify offline behaviour and existing probe evidence, and record proposals in `reviews/implementation-review-2026-11-09.md`. No application changes, paid calls, commits or design approvals are implied.
- Rationale: The phase-1 evaluation backend is not the requested complete poster workflow. Refinement, movable shadows and poster/campaign state need explicit requirements decisions before implementation.
- Next gate: Agree the reviewed direction, then draft/amend the relevant per-feature requirements; obtain requirements and matching design approvals before coding the new flow.

## ADR-024 — 2026-11-06 — `sheet`, `apply` and `new-cycle` choices (T-PV-010)

- Status: Implementation decisions inside D-PV-008. Codex r1–r3 reviewed them (r3 APPROVE).
- Decision:
  1. **`decisions.csv`:**
     - UTF-8 with BOM, `;`-separated;
     - columns `target_id;kind;action;reasons;note;framing;info`, where `info` is read-only for the operator and ignored by `apply`;
     - `reasons` are comma-separated codes, and `framing=ok` is required to approve;
     - `sheet` refuses to overwrite an existing `decisions.csv`.
  2. **What the sheet lists:**
     - **every** pending candidate and proposed cutout, whatever the scope's state (an abandoned scope's pending candidate can still be approved, ADR-020);
     - generation suggestions (revisable rejected tips, confirmed cutouts) and abandon rows only for open scopes;
     - rejected scenes at the attempt limit are not offered for revision.
  3. **Reading the file in `apply`:** the whole file is decoded strictly before parsing. A BOM means UTF-8; without one, UTF-8 is tried, then cp1252 (Excel's "CSV (point-virgule)" on a French Windows). It never uses replacement characters, and a malformed file is exit 2.
  4. **Validation:** two passes over the whole file, nothing applied on any error.
     - In-file transitions are simulated, and a matching replay passes before `next_status`.
     - Cutout transitions have their own check.
     - Abandon is refused while any request runs in the scope.
     - A column an action doesn't read is refused.
  5. **Execution and results:**
     - per-row error boundaries: an unexpected error gives the row `error:<Type>`, the other rows continue, admitted requests still execute, the results are written, and the exit is 1;
     - the CSV result comes from the request's **persisted** outcome (`applied` / `request_failed:<stored kind>`), never from a printing error;
     - the results are `applied | already_applied | refused:<code> | request_failed:<kind> | not_started | error:<exception>`, where `not_started` is a generation row skipped after `budget_exhausted`.
  6. **Generation ids:** `uuid5(target:action:k)`, where `k` is the first id that does not exist or is not `failed`/`interrupted`. A replay never spends twice, and a failure gets a new attempt.
  7. **Commands:** `apply` needs `--paid` with openai, like `generate`. `new-cycle` exits 1 if any SKU is refused.
- Revisit if: Excel saves in another encoding (e.g. UTF-16 "Unicode text"), or the operator needs to edit an existing `decisions.csv` across sheet runs.

## ADR-023 — 2026-11-06 — Probe result: gpt-image-2 returns usage; a high scene costs about USD 0.17 (T-PV-012)

- Status: Measured on 2026-11-06 with one paid call (user's go), in `DATA_DIR=data-probe`.
- **Facts:**
  - **gpt-image-2 returns `usage`**, despite the SDK docstring "For gpt-image-1 only" (ADR-015). Each call's cost is therefore usage-based (`cost_is_estimate = 0`), and the cap counts **real** token costs, not only estimates.
  - **One scene at `high`, 1088×1920, 1 input photo:**
    - input 1271 tokens (text 169, image 1102), output 5300;
    - cost = 169×5 + 1102×8 + 5300×30 µUSD = **168 661 µUSD (USD 0.169)**, recomputed exactly;
    - the call took 55.1 s;
    - the output is exactly 1088×1920, so the strict-size validation holds.
  - **The result on the made example phone:**
    - the camera layout, colour and diagonal panel are kept;
    - no text was added;
    - the product is about 41 % of the height and inside the safe square;
    - the corner radius is slightly reduced.

    This says nothing yet about real logos and fine markings (T-PV-013).
  - **Billing check:** the user's OpenAI usage dashboard (screenshot, 2026-11-06) shows **November spend $0.17, 1 request**, matching the recorded 168 661 µUSD. So the app's usage-based ledger matches the bill (D-PV-003 cap, item (d)). The dashboard's "Total tokens" shows 1,271, i.e. the input tokens only; the output tokens are billed (they make up most of the $0.17) but are not counted in that tile.
- **Consequences:**
  1. **The estimates are conservative:** `ESTIMATE_SCENE_USD` 0.40 ≈ 2.4× the real cost. The floor would be ceil(1.25 × 168 661) = 210 827 µUSD, so the reservation stays at 0.40. They are kept: reservations only affect admission headroom, and costs are recorded from usage. Lowering the scene estimate to 0.25 is optional.
  2. **The background cost is not measured yet:** `images.generate` has no input photo. It is expected near the scene cost (output-dominated); measure it in the first evaluation run.
  3. **The evaluation budget is revised down:**
     - 20 × (3 scenes × 0.17 + 1 background × ~0.16) ≈ **USD 13.4** at limit 3;
     - about **USD 20** at limit 5 (ADR-011);
     - add retries and extra backgrounds: **a cap of USD 25–30** is enough (down from the USD 30–46 in D-PV-008).
  4. **The probe's spend is in the `data-probe` ledger, not `data-openai`.** The OpenAI project limit (blocks) is global.
- Revisit if: OpenAI pricing changes, or a quality, size or multi-photo input changes the token counts materially.

## ADR-022 — 2026-11-06 — CLI `generate` and fixtures choices (T-PV-009)

- Status: Implementation decisions inside D-PV-008. Codex r1 and r2 reviewed them.
- Decision:
  1. **`--paid` is required whenever `IMAGE_PROVIDER=openai`, and refused with the stub.** It is checked before `runtime.start`, so a refused command creates nothing. Any CLI command that can spend must take it (`apply` in T-PV-010).
  2. **Exit codes:**
     - 0: done, including request outcomes recorded in the DB (refused, quota, timeout, a failed `no_product` cutout);
     - 1: configuration or startup refused, an unexpected error in the batch, `cutout_unavailable`, or a refusal outside the four scope-state codes; the other products still finish;
     - 2: usage or validation errors, nothing written;
     - 3: budget exhausted (takes precedence).
  3. **Photos** are `|`-separated names under `--photos DIR` (default `<csv dir>/photos`). The committed examples (2 made images) are in `fixtures/examples/`, because `fixtures/photos/` is git-ignored.
  4. **The CSV** is parsed strictly (`csv.reader(strict=True)`), so a broken quote can't swallow other products. Every row is validated, and compared with the run snapshot, even with `--only`.
  5. **The row sha** covers all 10 raw fields: any change, even to `notes`, refuses a later `generate` on that run.
  6. **Qualities:** low/medium/high, plus xhigh/max for `gpt-image-2.5-*` only (SDK docstring). `auto` is refused, because a run must name what it measures.
  7. **The printed `committed $X / cap $Y`** includes the reservations of calls still running.
  8. **Cutouts** run in a thread under `Semaphore(1)` while the scene calls wait. A failed (`no_product`) cutout doesn't block a new one on a re-run.
- Seen once, not reproduced: an onnxruntime "bad allocation" during a cutout. It was contained per product, and a re-run made the cutout. If it recurs, try `OMP_NUM_THREADS=4`.
- Revisit if: the evaluation needs `--only` without validating the other rows, or memory becomes an issue (all photos are held in memory).

## ADR-021 — 2026-11-06 — Paid probe inputs (T-PV-012)

- Status: User answers (2026-11-06). The user put the key and the cap in `backend/.env` themselves.
- Decision:
  1. **Key:** an OpenAI project key (`sk-proj-…`; format checked without printing it), only in `backend/.env` (git-ignored).
  2. **Cap:** `SPEND_CAP_USD=12`, `SPEND_CAP_SINCE=2026-11-06`. That covers the probe and the 5-product calibration (about USD 7.50 at the base estimates), not the full 20-product evaluation (about USD 30–46): raise the cap before T-PV-013.
  3. **Model and quality:** `gpt-image-2`, `high`. Product fidelity (logos, camera layout) is the main risk; the probe measures the real cost of this exact pair.
  4. **The dedicated project's OpenAI budget limit blocks requests** (user-checked). This is a second hard stop under the app's estimated-spend cap.
  5. **Paid mode is switched on only by the probe command line** (`IMAGE_PROVIDER=openai DATA_DIR=data-openai …`). `.env` leaves `IMAGE_PROVIDER` empty (default stub), so development commands cannot spend. Paid data lives in its own `data-openai` folder (the provider-mode guard refuses mixing).
- Revisit if: the probe shows `usage` missing (then estimates decide the cap) or a per-call cost far from the USD 0.40 estimate (adjust `ESTIMATE_SCENE_USD`).

## ADR-020 — 2026-11-06 — Review, cycle and abandon interpretations (T-PV-008)

- Status: Implementation decisions inside D-PV-004/005/006/007. Codex r1 and r2 judged them acceptable.
- Decision:
  1. **Every write is a conditional update** (`WHERE status = <from>`) returning `applied`; a replay with the same canonical payload returns `already_applied`; anything else gives `invalid_transition`. Input checks run first, so a replay with an invalid payload gets its validation code.
  2. **Rejection:** the reasons are stored deduplicated in `REASON_CODES` order; a note-only rejection stores `"[]"`; the note is stripped and screened with `find_commercial_terms`.
  3. **Cutout confirm/reject** (D-PV-006 step 2) are in this task, because no other task owned them.
  4. **Abandon is refused while any request of the scope runs**, whatever its purpose (design line 357; my first instruction limited it to the treatment's purpose, which Codex caught). The replay is checked first, so a replay after `new-cycle` still addresses the original scope. Cycle numbers below 1 are refused.
  5. **Approving a candidate that was pending when its scope was abandoned is allowed** (the design is silent). Abandon only stops new generation, and the report's precedence `approved > abandoned` resolves the outcome.
  6. **`new_cycle` has no replay token:** a second call refuses (`cycle_not_approved`), because the new cycle has no approval yet.
- For T-PV-010 (`apply`):
  - its whole-file validation must recognise matching replays before `next_status`;
  - it needs its own cutout-transition check;
  - it must validate `kind` before `abandon`, where an unknown treatment raises `KeyError`.
- Revisit if: the operator abandons with pending candidates often, and approvals after an abandon confuse the report.

## ADR-019 — 2026-11-06 — Request execution choices (T-PV-007)

- Status: Implementation decisions inside D-PV-003 and D-PV-006. Codex r1 APPROVE.
- Decision:
  1. **`execute` is async and takes the semaphore** (`asyncio.Semaphore(2)`), created **per event loop** by the caller and shared by all requests of that loop. DB, file and image work run synchronously on the loop. The phase-2 API should move them to a thread.
  2. **Inputs are prepared before any spend:** the input images and, for a background, the cutout are loaded and the `provider_input` copies made before call 1. A missing file fails as `storage` with no call.
  3. **Costs of failed calls:** a `storage` or unexpected failure **after** a successful call keeps the usage-based cost, because the call was billed. Before or without usage, the reservation stays.
  4. **An unexpected exception** marks the call and the request `failed` with `invalid_request` (type and message in `error_detail`), then re-raises. A cancellation is not caught; owner recovery marks the request `interrupted`.
  5. **The `SQLITE_BUSY` handling** (design line 249) covers the call-2 transaction only.
  6. **File extensions come from `assets.extension(mime)`** (the subtype, e.g. `.jpeg`). Every writer must use it.
  7. **The cutout row format that T-PV-009 must write:** `bbox_json = json.dumps([x, y, w, h])`, and `cutout_asset` set when the cutout is made.
- Revisit if: the phase-2 API needs concurrency beyond one event loop, or busy errors appear outside the retry transaction.

## ADR-018 — 2026-11-06 — Request admission: the subject in `run_products` (schema amendment) and rule interpretations (T-PV-006)

- Status:
  - Item 1 amends the approved D-PV-001 schema: the user chose it ("Save name in run") after Codex r1 found the gap;
  - items 2–6 are implementation interpretations of D-PV-003/005; Codex r1 judged them correct or reasonable.
  - No further design review round, because the change is small and recorded here.
- Decision:
  1. **Migration 0002** adds `run_products.name` and `run_products.variant`, written at `generate` like the arm:
     - `NOT NULL DEFAULT ''` with `CHECK (trim(x) <> '')`, so a value is required;
     - SQLite 3.47 checks it on ADD COLUMN, and fails on a table that already has rows.

     Admission reads the subject (and the arm) from `run_products` for every purpose. Why: `apply decisions.csv` runs without the fixture CSV, so a background request could not get the product's name. Alternatives were `apply --fixtures` (one more argument on every apply), or copying from the first scene request (fragile).
  2. **`request_scene` takes `variant_photos`** (the variant's photos, from the CSV loaded by `generate`) for the membership check and the default first 3 photos. There is no variants table in phase 1.
  3. **"The latest fallback candidate" is `ORDER BY attempt_no DESC`**, not by time, so a clock change cannot pick the wrong one.
  4. **A stale target is checked first:** a parent or cutout from another cycle or run gives `wrong_scope` before the scope rules, so the message names the real problem.
  5. **Design line 242 ("else 409 `review_pending`"):** `review_pending` is returned only when the latest fallback candidate is pending; an approved one gives `not_rejected`. `use_revision` cannot occur for backgrounds: a later background is always a linked revision.
  6. **The idempotency payload** holds the caller's fields as given and excludes `owner`.
  7. **Codes the design did not name:**
     - 409 `wrong_scope`, `cutout_not_confirmed`;
     - 422 `unknown_run`, `variant_not_in_run`, `unknown_target`, `unknown_asset`.

     A model without `RATES` gives `ValueError` before any row is written.
- For T-PV-007: `reserve()` only checks. Call 2 must be inserted in the same `write_tx`, with a budget refusal caught inside it to mark the request `failed` (`budget_exhausted`).
- Revisit if: phase 2 adds a variants table (then the catalogue moves to the DB).

## ADR-017 — 2026-11-06 — Startup, lock and asset store choices (T-PV-005)

- Status: Implementation decisions inside D-PV-001.
- Decision:
  1. **`runtime.start(settings, owner)` is the only startup entry** (CLI now, API later): OS lock → engine → migrate → provider-mode guard → owner-scoped recovery. A failure at any step after the lock disposes the engine and releases the lock.
  2. **`acquire_lock` retries a held lock for up to 2 s.** Measured on the user's PC: Windows releases a dead process's `msvcrt.locking` lock up to about 12 ms after the process ends (6 of 30 runs). Microsoft's `LockFile` docs say the delay "depends upon available system resources". Without the retry, back-to-back CLI commands would sometimes refuse.
  3. **`recover` marks every running call of the owner's requests** (not only those of running requests), so the two updates are order-independent. The reserved cost is kept.
  4. **Assets:** the file is written first (temp file in the same folder → fsync → `os.replace`), and the `assets` row is recorded in the caller's transaction (`ON CONFLICT DO NOTHING`, first kind wins). There is no GC, and the folder is not fsynced (Windows cannot).
  5. Times are stored as `db.utc_now()`: ISO 8601 UTC with microseconds, so text order is time order.
- Known gap: on Windows, if the API and the CLI `put` identical new bytes at the same moment, `os.replace` can raise `PermissionError` (it propagates). Handle this before the API and the CLI run at the same time (phase 2).
- Revisit if: a supervisor restarts the API within 2 s and needs a longer wait, or several API processes are needed (PostgreSQL).

## ADR-016 — 2026-11-06 — Cutout model and pipeline choices (T-PV-004)

- Status: Implementation decisions inside D-PV-006. The model is checked against the installed rembg 2.0.87.
- Decision:
  1. **Model `birefnet-general-lite`** (`REMBG_MODEL` default), 224 MB, downloaded once to `%USERPROFILE%\.rembg\models\birefnet-general-lite\`. Chosen from the installed list as a general-purpose model with sharp edges, about 4× smaller than `birefnet-general`. Not `bria-rmbg` (rembg's default): its licence needs a paid agreement for commercial use. Remote models (`withoutbg`, `atlascloud`) are refused, because they send the photo out and charge outside the cap.
  2. **Speed on the user's PC** (i5-1235U, CPU): 20–36 s per mask, plus about 22 s for the first session. `OMP_NUM_THREADS=4` measured about 35 % faster; it is not set in code.
  3. **The cutout keeps the source pixels and their ICC profile (RGB sources only), and no EXIF.** It is not converted to sRGB, unlike provider inputs (ADR-015), because R-006 requires the product pixels unchanged.
  4. **Hole filling and labelling use numpy + `scipy.ndimage`**, declared directly. A background region that touches the image border is never filled, even when small.
  5. **Real-model tests are opt-in** (`-m rembg`, about 2 minutes); the default suite uses injected masks.
- Licence (checked 2026-11-06, not a legal review): the BiRefNet code and the BiRefNet_lite weights are labelled **MIT** by the author (GitHub repository, Hugging Face card). rembg says weights carry their own licences. Two things are **unverified**: whether the rembg-hosted `BiRefNet-general-bb_swin_v1_tiny-epoch_232.onnx` is the same checkpoint, and the training-data terms. Confirm both before production use.
- Revisit if: the evaluation shows poor masks (try `birefnet-general`, slower), the CPU time is too long for the phone flow (try `isnet-general-use`, untested), or the licence check fails.

## ADR-015 — 2026-11-06 — Provider gateway: SDK facts and deviations from the design (T-PV-003)

- Status: Verified on the installed SDK and OpenAI docs (read 2026-11-06); implementation decisions inside D-PV-003.
- **Versions:** openai 3.46.0 (its HTTP client is **httpx2** 2.16.0, not httpx; declared directly because the gateway and tests import it), pillow 13.0.0.
- **SDK facts (installed source):**
  - `images.edit` takes a list of images, sent as `image[]` multipart parts in order;
  - `size` is a free string, and its docstring allows any WxH in multiples of 16 for gpt-image-2/2.5, so 1088×1920 is valid;
  - the `input_fidelity` docstring says to omit it for gpt-image-2; `response_format` is unsupported for GPT image models;
  - `APITimeoutError` subclasses `APIConnectionError`.
- **`usage` may be missing for gpt-image-2:** the SDK docstring says "For gpt-image-1 only". Without it, every call's cost stays at the reserved estimate. T-PV-012 checks this.
- **Deviations from the design:**
  1. **Model ids:** there is no bare `gpt-image-2.5`. `RATES` has `gpt-image-2`, `gpt-image-2.5-sunburst` and `gpt-image-2.5-flare` at $5 / $8 / $30 per 1M text-input / image-input / image-output tokens. A model without rates is refused before any call. T-PV-006/009 must check the run's model against `RATES` before they reserve budget.
  2. **Error codes** (OpenAI error-codes and image-generation guides):
     - the ordinary 429 rate limit has **no code** (`rate_limit_exceeded` is undocumented), so every 429 that is not about quota is `rate_limited` and retryable;
     - quota is `insufficient_quota` (documented as an error type; also accepted as a code) or one of the 429 codes `credit_balance_exhausted`, `project_spend_limit_exceeded`, `organization_spend_limit_exceeded`, `organization_usage_limit_exceeded`;
     - refused is code `moderation_blocked`, or type `image_generation_user_error`, whatever the status (none is documented).
  3. **`retryable` follows from the kind** (`rate_limited`, `provider_error`), so the stub and the real adapter cannot disagree. The adapter never retries; T-PV-007 does the one retry.
- **Additions (Codex r1–r2):**
  - **API key:** it must be printable ASCII with no whitespace. A pasted invisible character would otherwise make the HTTP library print the whole key.
  - **Errors:** `error_detail` redacts `sk-…` and is truncated to 500 characters. No SDK exception travels as a cause or context.
  - **Usage:** only allowlisted integer counts are kept. Usage is used for the cost only when it is consistent: `output_tokens > 0`, the total equals input + output, and the split is ≤ input. Otherwise the estimate stays.
  - **Provider input:**
    - an ICC profile is converted to sRGB, keeping gray as gray, before the profile is removed;
    - alpha is flattened onto white after the colour conversion;
    - a PNG declaring non-sRGB gamma or primaries with no ICC or sRGB chunk is refused ("re-export as sRGB").
- Revisit if: T-PV-012 shows `usage` is returned (calibrate the estimates) or never returned (estimates only), or OpenAI documents new error codes.

## ADR-014 — 2026-11-06 — Prompt and screen interpretations (T-PV-002)

- Status: Implementation decisions inside D-PV-002. Codex r1 agreed with them.
- Decision:
  1. **Background `texte` sentence:** a rejected background for the "text added outside the product" reason gets "Remove all text, numbers, logos and watermarks." The design names only `integration` and `extra` for backgrounds. Text in a background is exactly the `texte` case. `coloris, logo, cameras, boutons, forme, cadrage` add nothing to a background prompt.
  2. **Number rule of the screen:** "any number with ≥ 4 digits (spaces, dots and commas ignored)" means ≥ 4 digits where two digits are separated by nothing, one dot or comma, or a run of spaces, but not a mix (`\d(?:(?:[.,]|\s+)?\d){3,}`). So `49,99`, `1 200 000` and `1  200  000` are blocked, but `iPhone 15, 128 Go` is not.
  3. **Wording added to the design's blocks:** a "Rules (they override everything below)" header; instruction 1 also covers further product photos; the mood line appears only for the default or a chosen mood.
- Because: the blocklist is best effort (ADR-011). Its false positives cost one rephrase, while its false negatives are caught by rule 2 and the review checklist.
- Known false positives: two numbers separated only by a space (`Galaxy S24 128 Go`), a 4-digit year, `5000 mAh`.
- Consequence for T-PV-007/008: `corrections_applied` must mean "a correction line was added to the prompt", not "the operator gave reasons". Codes that are ignored for a background leave the prompt unchanged.
- Revisit if: the evaluation shows the screen blocks real descriptions often, or text appears in backgrounds despite the sentence.

## ADR-013 — 2026-11-06 — Backend scaffold choices (T-PV-001)

- Status: Implementation decisions inside the approved design (D-PV-001, Cross-cutting).
- Decision:
  1. **Settings:** pydantic-settings (pydantic comes with FastAPI in phase 2). `backend/.env` is found from the module path, not the current folder. `SPEND_CAP_USD` and `SPEND_CAP_SINCE` have no default. Estimates default to 0.40 / 0.30 USD (design D-PV-008). `load_settings()` raises `ConfigError` with the printed message only. Reason: a pydantic `ValidationError` keeps the raw inputs, the API key included, in `.errors()` and `.json()` even with `hide_input_in_errors`.
  2. **No ORM models:** the schema is plain SQL in migration 0001, copied from the design. Later code uses `text()` queries.
  3. **Transactions:** the SQLAlchemy 2.1 recipe "Using SQLAlchemy to emit BEGIN in lieu of SQLite's transaction control". pysqlite's `isolation_level` is set to `None`, and a `begin` event emits `BEGIN IMMEDIATE` when the engine option `affiche_write_tx` is set (`write_tx()`). Python 3.12's `autocommit=False` was not used: with it, sqlite3 always sends a deferred `BEGIN`, so `BEGIN IMMEDIATE` cannot be sent. **Never pass `isolation_level` to this engine:** the dialect then turns pysqlite's implicit BEGIN back on.
  4. **Migrations run only through `affiche.db.migrate(engine)`**, which applies the pragmas and `BEGIN IMMEDIATE`. `alembic upgrade` from the command line refuses to run. `alembic revision -m` still creates new migration files; `--autogenerate` is not available, because there is no ORM metadata.
- Versions locked on 2026-11-06: sqlalchemy 2.1.8, alembic 1.20.1, pydantic 2.14.3, pydantic-settings 2.16.2, pytest 9.2.0; build backend uv_build 0.11.
- Revisit if: a second database engine is added, or autogenerate becomes worth having ORM models.

## ADR-012 — 2026-11-06 — product-visuals design approved for phase 1; Python tooling

- Status: Explicit user approval ("go ahead") of designs/product-visuals.md r4, phase 1 only.
- Context: Codex r1–r3 REWORK, then a fourth narrow round the user authorised past the 3-round cap ("go for a last review"). r4 → APPROVE WITH FIXES; the 3 local fixes were applied and self-checked without another round.
- Decision: (1) Implement phase 1 as designed: domain and state machines, stub + OpenAI gateway, cutout, fixtures and the CLI evaluation. The draft phase-2 HTTP/session contracts are not approved. (2) Python 3.12 with uv (`pyproject.toml` + `uv.lock`), pytest for tests. Both are installed on the user's PC (uv 0.11.8).
- Because: Phase 1 is the smallest thing that produces the R-008 evidence. uv gives a lockfile and a pinned interpreter with one tool that is already installed.
- Not verified yet: OpenAI SDK methods and error fields (T-PV-003), whether gpt-image-2 returns `usage` (T-PV-012 probe), and rembg model names (T-PV-004).
- Revisit if: the evaluation recommendation changes the review flow (design v2), or rembg/onnxruntime wheels are missing for 3.12 on Windows.

## ADR-011 — 2026-11-06 — product-visuals design questions: all recommended options

- Status: User decision on design r3 UQ-1 … UQ-5 ("go with all recommended DQs"). This is not the design approval; Codex r3 and explicit approval are still required.
- Decision:
  1. **Shadow (UQ-1 a):** a synthetic shadow is baked into the background at the default product position. It stays in place when the cutout moves, as ADR-009 already accepted. No separate shadow layer is stored.
  2. **Requirements wording (UQ-2):** R-003 c.1 (catalogue terms never sent; operator free text screened best-effort), R-003 c.2 (do not *add* text; product markings kept) and R-004 c.2 (text added outside the product; `cadrage` required to approve; `integration`) are amended.
  3. **Phasing (UQ-3):** phase 1 = domain, gateway, cutout and CLI evaluation with a desktop contact sheet; then the paid evaluation; then phase 2 (HTTP API and phone/desktop UI) in design v2. The design approval covers phase 1 only.
  4. **Evaluation exception to ADR-010 (UQ-4):** for CLI evaluation runs only, the attempt limit is 5, and products the user assigns to arm B get plain re-rolls without corrections. About +$16 per model at base estimates.
  5. **Attempt-limit reset (UQ-5 a):** an explicit "Nouvelle campagne" action starts a new cycle for a variant, allowed only after one of its candidates in the current cycle is approved. Approving never resets the count by itself.
- Because: (1) avoids a "ghost" product and an extra layer; (2) the old wording would make the model erase real product logos, and the blocklist cannot be complete; (3) the evaluation can change the review flow before UI work is spent; (4) measures whether 3 is the right limit and whether corrections help; (5) a variant gets a fresh allowance per campaign without a loophole.
- Alternatives: a movable shadow layer (amends R-006 c.4); a background generated around the product (ghost when moved); never resetting the allowance.
- Revisit if: the evaluation shows frequent `integration` rejections (consider the generated-around-product background) or that the A/B evidence is too weak to decide.

## ADR-010 — 2026-11-06 — User's OpenAI account, 3-attempt limit, no prototype

- Status: User answers to the product-visuals open questions.
- Decision: (1) Use the user's own OpenAI account; the user provides the API key, which is held only in the server's `.env` (already git-ignored). (2) Allow 3 generated attempts per product variant, then offer the photo-preserving fallback. (3) There is no prototype to inspect; build the cutout step from scratch. (4) The user will supply the fixture photos.
- Spending cap: no amount was given. It is therefore a required configuration value; with no cap set, no paid call can start. This is a deliberate guard, not an assumed amount.
- Because: The cap stays in the user's hands without blocking the design. The key never reaches code, chat or the frontend.
- Revisit if: The evaluation shows that 3 attempts are often not enough for a fidelity-correct scene, or a shared or company account replaces the personal one.
- Note: BRIEF.md mentioned a `poster-kit.zip` prototype. The user confirmed on 2026-11-06 that it does not exist yet.

## ADR-009 — 2026-11-06 — One candidate per request; fallback product kept as a separate layer

- Status: User decision after reviewing the product-visuals mockup ("go with option A, 1 result per request").
- Context: Open questions 3 and 4 in requirements/product-visuals.md.
- Decision: (1) Each generation request produces one candidate. (2) In the photo-preserving fallback, the cutout of the original photo stays a separate layer above a generated background. The two parts are never merged, and the operator can move and resize the product in the editor.
- Because: One candidate keeps the cost per attempt low and predictable during the evaluation. A separate layer avoids a server-side compositing step, makes it simple to prove the product pixels are untouched (they are the cutout file), and gives the operator a movable product.
- Trade-off accepted: the shadow is part of the background and does not follow the product. The UI must say so.
- Consequences: poster-editor requirements must support an image layer that can be moved and resized. The product in a `scene` treatment still cannot be moved on its own. Creation records must store the cutout and the background separately.
- Revisit if: The evaluation shows that operators often move the product far enough to break the shadow, or that one candidate per request leads to many more revisions.

## ADR-008 — 2026-11-05 — Charter and feature split approved; product-visuals first

- Status: Explicit user approval ("approved, start with product-visuals").
- Context: T-BOOT-002 gate. PROJECT.md and the six-feature split were in Draft.
- Decision: Approve PROJECT.md as written and the six features (catalogue-brand, generation-jobs, product-visuals, poster-editor, format-export, creation-library). Draft product-visuals requirements first.
- Because: Product-detail drift in generated scenes is the highest product risk, and the results of the model/fallback evaluation affect the cost, the editor (flattened scene or separate product layer) and the reuse rules.
- Alternatives: poster-editor first (phone editing risk) was the other recommended option. catalogue-brand first is lower risk but would delay the main unknown.
- Open at approval: paid-evaluation budget, prototype inspection and an initial commit were raised but not answered. They are carried into the product-visuals open questions or the handoff.
- Revisit if: The fidelity evaluation shows that neither treatment is acceptable, which would change the scope of the pilot.

## ADR-007 — 2026-11-05 — Trust only affiche-ia across sandbox and desktop users

- Status: Applied and verified as T-BOOT-004 in response to the user's local-host failure.
- Context: The repository and .git were created by DESKTOP-N8QV4L5/CodexSandboxOffline, while the desktop host runs as M Rakotozafy. Git therefore rejected the repository on the desktop despite succeeding during the original sandbox checks.
- Decision: Add exactly C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia as safe.directory in C:/Users/M Rakotozafy/.gitconfig after obtaining filesystem permission. Preserve all existing settings; retain a backup in the original chat workspace, outside this repository.
- Because: This is the user-requested repository created in this session; an exact protected-config entry permits the intended cross-user use while retaining checks for other repositories. Git documents this mechanism at https://git-scm.com/docs/git-config#Documentation/git-config.txt-safedirectory.
- Alternatives: A wildcard trust entry would be unnecessarily broad. Changing ownership/ACLs is more invasive. Repository-local safe.directory is not a valid protected trust configuration.
- Validation: Reproduced the failure with GIT_TEST_ASSUME_DIFFERENT_OWNER=1, tested the proposed config, then verified both the original command and forced-ownership check with the actual user config. The desktop UI has not been reopened by the assistant.
- Revisit if: The project moves, its ownership changes, or a host uses a different user/configuration. Remove the exception when it is no longer needed.

## ADR-006 — 2026-11-05 — Place the canonical project beside tsena_scan and initialise Git

- Status: Explicitly requested by the user; completed and verified as T-BOOT-003 on 2026-11-05.
- Context: ADR-005 used a generated chat workspace. The user requested a sibling project beside tsena_scan and a local Git repository.
- Decision: Use C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia as the canonical root. Copy the prepared project without deleting the chat copy, initialise an independent repository on main, and add a minimal README and .gitignore for the confirmed Python/Vue stack. Do not create a remote or a commit as part of git init.
- Because: This matches the user's explicit location and version-control request while preserving the existing documents.
- Alternatives: Leaving the project in the generated chat folder would not satisfy the request. A new worktree is unnecessary for an independent repository.
- Revisit if: The user requests a different location, repository policy or remote. This entry supersedes ADR-005 only for the canonical location; project approval gates remain unchanged.

## ADR-005 — 2026-11-05 — Bootstrap the documentation in the current workspace

- Status: Bootstrap execution decision within the user's request.
- Context: The current workspace contains the reviewed brief and feedback but no application or Git repository.
- Decision: Use this workspace as the local project root; create AGENTS.md and docs/project/ from the available templates. Preserve the existing outputs/ and work/ directories. Stop for PROJECT.md and feature-split approval before requirements or application scaffolding.
- Because: The user requested a local bootstrap under an explicit documentation-first workflow.
- Alternatives: A new worktree is unnecessary without an existing repository; application scaffolding would skip the project approval gate.
- Revisit if: The user requests a different project location or repository setup.

## ADR-004 — 2026-11-05 — Single-shop, French-language pilot with full phone and desktop editing

- Status: Confirmed by the user in the bootstrap interview.
- Context: The brief left pilot scope, device support, and initial language open.
- Decision: Start with Original Phone Mada only; support full editing on both phones and desktop; launch the interface and generated captions in French. Add Malagasy after the pilot.
- Because: These are the user's explicit answers on 2026-11-05.
- Alternatives: Several shops at launch, desktop-only editing, and bilingual launch were not selected.
- Revisit if: Pilot evidence or an explicit scope change justifies expanding users or languages.

## ADR-003 — 2026-11-05 — Keep formal specification behind the bootstrap approval gate

- Status: Required by the user's Global Working Agreement.
- Context: The existing brief includes product and technical proposals but has not been approved as formal requirements or design.
- Decision: Populate PROJECT.md and propose a feature split now. Leave requirements and designs as templates and empty indexes until project approval. Then follow requirements approval, design, tasks, implementation, and handoff in order.
- Because: A request to bootstrap authorizes the bootstrap phase, not all later proposals in the brief.
- Alternatives: Creating feature requirements, choosing a canvas SDK, or writing application code during bootstrap would bypass the agreed gates.
- Revisit if: The user explicitly changes the working agreement.

## ADR-002 — 2026-11-05 — Avoid fixed HTML poster templates as a V1 constraint

- Status: User direction recorded from the brief discussion.
- Context: The first brief used Jinja2/HTML poster templates. The user considers fixed templates too limiting for the first version.
- Decision: Do not constrain poster creation to a fixed catalogue of HTML layouts. Carry a flexible canvas with AI-proposed compositions forward as the recommended approach; preserve the distinction between that recommendation and an approved technical design.
- Because: The product should accommodate different products and creative directions while making routine changes easy.
- Alternatives: Reusing the old HTML renderer as the governing layout system would impose the rejected constraint. Ordinary HTML in the Vue application's interface is unaffected.
- Revisit if: The user explicitly chooses a different composition strategy after evaluating the editor.

## ADR-001 — 2026-11-05 — Vite + Vue frontend alongside FastAPI

- Status: Explicit user choice.
- Context: The brief originally left the frontend framework open.
- Decision: Use Vite + Vue for the web UI and FastAPI for the API. Evaluate canvas integration within that stack. Do not select a library by switching the application to a different frontend framework.
- Because: The user specified this stack before requesting bootstrap.
- Alternatives: HTMX, Svelte, or a React application are not the selected application stack.
- Revisit if: The user explicitly changes the stack constraint.
