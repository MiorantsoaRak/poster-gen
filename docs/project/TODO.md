# TODO

> Update statuses when work changes: `[ ]` not started, `[~]` in progress, `[x]` done and verified, `[!]` blocked, `[-]` dropped.
> Every task references an approved design section or is marked `chore`. One task may be in progress at a time. In-progress and blocked tasks require a note. Mark done only after running the verification step.

## Now (current focus — max 3 items)

- [ ] T-PV-002 (D-PV-002) `Direction`/`SceneSubject` types, `build_scene_prompt`, `build_background_prompt`, the reason-code sentences, and `find_commercial_terms`. Pure functions.
  - verify: `uv run pytest tests/test_prompts.py -q`: a fixture's price, warranty and promo never appear in either prompt; the screen matches and does not match the D-PV-002 lists; every reason code has a sentence or is explicitly ignored, per prompt type; arm-B mode adds no correction sentence and no note.

Work in C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia. No implementation task is in progress.

## Next (approved, ordered)

Phase 1 of designs/product-visuals.md (approved 2026-11-06, ADR-012). Every task runs with the stub provider or mocked SDK responses: **no paid call** until T-PV-012. Verify commands run from `backend/`.

- [ ] T-PV-003 (D-PV-003 provider call, error mapping, stub, money math) Check the installed `openai` SDK (images.edit/generate signatures, multipart, exception classes, error codes) and record the version. Provider adapter: `provider_input` preparation (EXIF orientation, long edge ≤ 1536, PNG without metadata), client settings (timeout 180 s, `max_retries=0`), strict 1088×1920 validation, usage → cost (Decimal, ceil, micro-USD), the error-mapping table, retryable vs not. Stub provider with `STUB_FAIL`. No network.
  - verify: `uv run pytest tests/test_gateway.py -q` with mocked SDK responses and exceptions covers each error-mapping row, retryable classification, size validation and cost rounding; the provider input has no EXIF; the SDK version and any deviation from the design are recorded in DECISIONS.md.
- [ ] T-PV-004 (D-PV-006 steps 1 and 3, image operations) rembg setup: pick the model from the installed version's list and document its one-time download. Mask pipeline (≤ 2048 copy, threshold 128, holes < `MAX_HOLE_RATIO`, 1 px erosion), RGBA built from source pixels, component check, placement, baked shadow.
  - verify: `uv run pytest tests/test_cutout.py -q`: pixel test on 3 committed sample images (made or freely licensed; no shop photos), an EXIF-orientation-6 sample and the downscale path (opaque pixels equal the oriented source, A ∈ {0, 255}, same size); synthetic images give `no_product` and `multiple_products`; placement stays inside the safe square for tall, wide and square boxes.
- [ ] T-PV-005 (D-PV-001 asset store, process lock, crash recovery, provider mode) Content-addressed asset store (tmp → fsync → `os.replace`). OS lifetime lock on `data/cli.lock` / `data/api.lock`. Owner-scoped recovery after taking the lock. The `meta.provider_mode` guard.
  - verify: `uv run pytest tests/test_store_lock.py -q`: `put` is idempotent; a second process cannot take a held lock; after killing a lock holder, the next start takes the lock and marks its running requests and calls `interrupted`; starting with the other provider mode is refused.
- [ ] T-PV-006 (D-PV-003 rules 1–7, D-PV-005 allowance and scopes) Request admission in one `write_tx()`: idempotency (`payload_hash`), photo membership, abandoned scope, `req_one_initial` → `review_pending` / `use_revision`, allowance per (variant, cycle, run), revision and background rules (incl. a new cutout as a linked revision), budget with the reservation floor.
  - verify: `uv run pytest tests/test_admission.py -q`: allowance counting; two processes at `used = 2` → exactly one accepted; same id + same payload returns the request, same id + other payload → `request_id_reused`; cap boundary (`spent + r == cap` allowed, one micro over refused); empty ledger sums to 0; the floor raises the reservation after a higher usage-based cost; every 409 code in rules 3–6 has a test.
- [ ] T-PV-007 (D-PV-003 execution, D-PV-006 background flow) Request execution: call 1, one retry (call 2) only for the retryable kinds, refused-retry finalisation, success and failure transactions, candidate creation for both treatments (background + baked shadow via T-PV-004). Semaphore of 2 provider calls.
  - verify: `uv run pytest tests/test_execution.py -q` (stub): a retry keeps its slot and makes no fourth candidate; a retry refused by the budget → request `failed` (`budget_exhausted`) and the slot is freed; non-retryable kinds never get call 2; a success stores the raw asset, the cost and a `pending_review` candidate in one transaction; a `photo_preserved` candidate stores the cutout id and `product_box_json`.
- [ ] T-PV-008 (D-PV-004, D-PV-005 cycles and abandon, D-PV-007) Review state machine (`next_status`, conditional updates, idempotent replay), approval requires `framing_checked` (both treatments), rejection reasons/note (screened), cycles, abandon, the reuse query.
  - verify: `uv run pytest tests/test_review.py -q`: all 6 transition combinations (4 refused); approve without framing → `framing_not_checked`; reject without a reason or note refused; a cycle needs an approval; abandon is refused while a request runs or after an approval, and blocks new requests after; reuse never returns another variant and makes no gateway call.
- [ ] T-PV-009 (D-PV-008 fixtures, runs, `generate`) Fixture CSV loader and validation, `runs` creation (immutable; `UNIQUE (model, quality)`), the `run_products` snapshot, CLI `generate` with the low-res acknowledgement, `spent / cap` printing, exit 3 on `budget_exhausted`.
  - verify: `uv run pytest tests/test_fixtures_generate.py -q`: every validation error is listed and nothing loads; a new label with an existing model+quality is refused; a changed CSV row for an existing product is refused; `uv run python -m affiche.visuals.evaluate generate --fixtures fixtures/products.example.csv --run stub1` (stub `DATA_DIR`) creates one scene candidate and one proposed cutout per product.
- [ ] T-PV-010 (D-PV-008 `sheet`, `apply`, `new-cycle`) Static `sheet.html` + pre-filled `decisions.csv` (incl. scope rows), `apply` (validate all rows first, decisions then generation actions, uuid5 ids with `k`, `apply-result.csv`), `new-cycle`.
  - verify: `uv run pytest tests/test_apply.py -q`: one invalid row → nothing applied; replaying a file gives `already_applied` and no new request; after a failed request a replay creates a new one; abandon replay after `new-cycle` still addresses the original scope; on the stub data from T-PV-009, `sheet` writes a page that opens in a browser.
- [ ] T-PV-011 (D-PV-008 `report`) `calls.csv`, `report.csv` (per run × variant × cycle × treatment, outcomes, reasons, estimated and allocated billed cost, `low_res`, `arm`) and `summary.md`.
  - verify: `uv run pytest tests/test_report.py -q`: outcome precedence (`approved` > `abandoned` > `pending` > `exhausted` > `failed_only` > `not_approved`); the billed allocation sums exactly to the billed total; `attempt_no` restarts per cycle.

## Blocked

- [!] T-PV-012 (D-PV-003 cap section (b)) One paid probe call with the chosen model, to see whether `usage` is returned and to calibrate the estimates.
  - note: Blocked on the user: `OPENAI_API_KEY` from a dedicated OpenAI project in `backend/.env`, `SPEND_CAP_USD` set, and a check of that project's budget-limit behaviour in the OpenAI settings. Also needs T-PV-003 and T-PV-007.
  - verify: one `provider_calls` row with a non-zero `cost_micros`; the design or DECISIONS.md records whether `usage` was present and the observed cost.
- [!] T-PV-013 (D-PV-008, R-008) Paid evaluation: 5 products to calibrate, then 15; report; recommendation written with the user; then design v2.
  - note: Blocked on the user: the fixture photos (~20 products, incl. poor photos and look-alike variants), the arm assignments, and the approval thresholds agreed before the run (R-008 c.6). Also needs T-PV-002 … T-PV-012.
  - verify: `report` outputs exist for every run; the user approves the recommendation.

## Done (most recent first — prune monthly)

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
