# DECISIONS

> Append-only log, newest first. Record context, decision, rationale, alternatives, and conditions for reconsideration. Reversals get a new entry. A confirmed constraint does not approve a design or library choice.

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
