# DECISIONS

> Append-only log, newest first. Record context, decision, rationale, alternatives, and conditions for reconsideration. Reversals get a new entry. A confirmed constraint does not approve a design or library choice.

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
