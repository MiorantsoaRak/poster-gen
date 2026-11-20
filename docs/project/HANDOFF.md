# HANDOFF

**Concurrent tracks share this checkout.** Claude owns the chat audit and implementation documented below. Codex completed publishing/SaaS research in this session and retains the older text-first mockup track. Changes from other tracks must be preserved; the working tree is not clean.

## App redesign — Claude, 2026-11-21 (READ FIRST)

No work order: the owner's own project. Goal: both interfaces follow the mockup he approved
([mockups/doka-console/](mockups/doka-console/README.md)); ADR-123, [requirements](requirements/app-redesign.md),
[design](designs/app-redesign.md) v2, tasks T-REDESIGN-001 … 007 in TODO.md.

**State: all seven tasks are done and committed on the branch `redesign`, NOT on `main`, NOT pushed, NOT deployed.**
The branch lives in the git worktree `../affiche-ia-worktrees/app` (its own `node_modules`, `.venv`; smoke ports
5273/8100). `redesign-chat` (worktree `../affiche-ia-worktrees/chat`) and `redesign-console`
(`../affiche-ia-worktrees/console`) are merged into it. `main` still holds the interface polish only
(T-POLISH-001 … 005), also not pushed. The report: [reviews/app-redesign-after-2026-11-21.md](reviews/app-redesign-after-2026-11-21.md).

**Proof, once on the merged branch:** Vitest 312; the build; all seven browser smokes; backend 1533 passed; 102
captures in `../affiche-ia-worktrees/app/outputs/design-capture/redesign/`.

**Exact next step: the owner's.**
1. Look at it (from the worktree):
   ```
   cd ../affiche-ia-worktrees/app/frontend && corepack npm@10 run build
   cd ../backend && uv run python ../frontend/tests/design_capture.py look
   ```
   then open `outputs/design-capture/look/sheets/` there.
2. Decide the five points of « For the owner » in the report (placement of « Needs you », the cost sentence, « Images »,
   « Payments », the theme switch in the phone drawer).
3. On his word only: merge `redesign` into `main` (`git merge --no-ff redesign` from `main`; no conflict expected,
   `main` has only docs since), push, deploy as an ordinary release (no migration).

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
- The worktrees are on disk next to the repo; delete them only after `redesign` is merged
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
