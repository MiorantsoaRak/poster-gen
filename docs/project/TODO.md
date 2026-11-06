# TODO

> Update statuses when work changes: `[ ]` not started, `[~]` in progress, `[x]` done and verified, `[!]` blocked, `[-]` dropped.
> Every task references an approved design section or is marked `chore`. One task may be in progress at a time. In-progress and blocked tasks require a note. Mark done only after running the verification step.

## Now (current focus — max 3 items)

- [ ] T-PV-010 (D-PV-008 `sheet`, `apply`, `new-cycle`) Static `sheet.html` + pre-filled `decisions.csv` (incl. scope rows), `apply` (validate all rows first, decisions then generation actions, uuid5 ids with `k`, `apply-result.csv`), `new-cycle`. The prevalidation must recognise matching replays before `review.next_status` (or a replayed file fails), must have its own check for cutout transitions, and must validate `kind` before calling `review.abandon` (Codex T-PV-008 r1). **`apply` spends (revise/background), so it must take `--paid` like `generate`** (ADR-022).
  - verify: `uv run pytest tests/test_apply.py -q`: one invalid row → nothing applied; replaying a file gives `already_applied` and no new request; after a failed request a replay creates a new one; abandon replay after `new-cycle` still addresses the original scope; on the stub data from T-PV-009, `sheet` writes a page that opens in a browser.

Work in C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia. No implementation task is in progress.

## Next (approved, ordered)

Phase 1 of designs/product-visuals.md (approved 2026-11-06, ADR-012). Every task runs with the stub provider or mocked SDK responses: **no paid call** until T-PV-012. Verify commands run from `backend/`.

- [ ] T-PV-011 (D-PV-008 `report`) `calls.csv`, `report.csv` (per run × variant × cycle × treatment, outcomes, reasons, estimated and allocated billed cost, `low_res`, `arm`) and `summary.md`.
  - verify: `uv run pytest tests/test_report.py -q`: outcome precedence (`approved` > `abandoned` > `pending` > `exhausted` > `failed_only` > `not_approved`); the billed allocation sums exactly to the billed total; `attempt_no` restarts per cycle.

## Blocked

- [!] T-PV-013 (D-PV-008, R-008) Paid evaluation: 5 products to calibrate, then 15; report; recommendation written with the user; then design v2.
  - note: Blocked on the user, and on T-PV-010/011:
    - the fixture photos (~20 products, incl. poor photos and look-alike variants);
    - the arm assignments;
    - the approval thresholds agreed before the run (R-008 c.6);
    - **a cap of about USD 25–30**. At the probe's measured USD 0.17 per scene (ADR-023): 20 × 3 scenes + 20 backgrounds ≈ USD 13.4; with limit 5 ≈ USD 20; plus retries or extra backgrounds.

    Run it in `DATA_DIR=data-openai` with `--paid`.
  - verify: `report` outputs exist for every run; the user approves the recommendation.

## Done (most recent first — prune monthly)

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
