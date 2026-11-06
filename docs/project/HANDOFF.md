# HANDOFF

> Updated at session end. Read this before exploring the project.

**Session date:** 2026-11-06 (Indian/Mauritius)  
**Working on:** product-visuals phase 1. T-PV-001 … T-PV-003 are done and reviewed; next is T-PV-004.

## State of the world

Canonical repository: C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia (branch main, no remotes).
- PROJECT.md and the six-feature split: approved (ADR-008).
- requirements/product-visuals.md: R-001 … R-008 approved; R-003, R-004 and R-005 amended on 2026-11-06 (ADR-011).
- designs/product-visuals.md r4: approved for **phase 1** (ADR-012). Phase-2 HTTP/session/UI contracts are draft until design v2, after the paid evaluation.
- `backend/` (Python 3.12 + uv, package `affiche`; commands in AGENTS.md → Commands cheat sheet):
  - `config.py` and `db.py` (T-PV-001, ADR-013); Alembic migration 0001 with the whole D-PV-001 schema;
  - `visuals/prompts.py` (T-PV-002, ADR-014): `Direction`, `SceneSubject`, both prompt builders, the reason-code sentences, `find_commercial_terms`;
  - `visuals/gateway.py` (T-PV-003, ADR-015): `prepare_provider_input`, `validate_image`, money (`usd_to_micros`, `cost_micros`, `parse_usage`, `RATES`), `OpenAIProvider`, `StubProvider`, `make_provider`;
  - 223 pytest tests.
- No `backend/.env`, no database file, no service and no paid API call exist.

## Done this session

- Requirements drafted and approved (ADR-009, ADR-010); design reviewed through Codex r1–r4 + devil's-advocate and approved for phase 1 (ADR-011, ADR-012).
- TODO.md: T-PV-001 … T-PV-011 buildable now (stub/mocked only); T-PV-012 (paid probe) and T-PV-013 (paid evaluation) blocked on user inputs.
- **T-PV-001 done**: Codex r1 → 2 fixes, r2 → APPROVE. Committed (initial commit).
- **T-PV-002 done**: Codex r1 → 2 fixes, r2 → 1 fix, r3 → APPROVE. Committed.
- **T-PV-003 done** via /implement-review:
  - Codex r1 → 6 fixes: a pasted invisible key character leaked the key; usage was logged and kept raw; malformed usage could under-count; decoding errors; grayscale ICC with alpha; gamma metadata;
  - r2 → 3 fixes: a contradictory token split; grayscale tRNS; P3 `cHRM`;
  - r3 → APPROVE;
  - reviews: docs/project/reviews/t-pv-003-code-r1.md … -r3.md;
  - verified: `uv run pytest -q` → 223 passed; 25 mutations killed;
  - **not committed yet**.

## In progress — exact resume point

- **Task:** none in progress. T-PV-003 is done but **not committed** (see Uncommitted). Offer the commit to the user first.
- **Next action:** T-PV-004 (D-PV-006 steps 1 and 3: rembg cutout, mask pipeline, placement, baked shadow), with /implement-review. Pick the rembg model from the installed version's list; never trust model names from the design. One task at a time; mark `[~]` with a note when starting.

## Landmines / gotchas discovered

- **SQLite engine (ADR-013):**
  - `make_engine()` sets pysqlite `isolation_level = None`; a `begin` event emits `BEGIN IMMEDIATE` for `write_tx()`.
  - **Never pass `isolation_level` to this engine**: the dialect then turns pysqlite's implicit deferred BEGIN back on, and `write_tx()` stops locking.
  - Do not use Python 3.12's `autocommit=False` either.
- **Migrations:**
  - They run only through `affiche.db.migrate(engine)`. `alembic upgrade` from the command line refuses on purpose.
  - `uv run alembic revision -m "..."` creates a new file. There is no autogenerate (no ORM models; the schema is plain SQL).
- **Settings:**
  - `load_settings()` raises `ConfigError`, never pydantic's `ValidationError`, which keeps the raw API key in `.errors()`.
  - Tests must call `load_settings(env_file=None)` so they never read a real `backend/.env`.
  - The API key must be printable ASCII with no whitespace (ADR-015).
- **Gateway (ADR-015):**
  - openai 3.46.0 uses **httpx2**, not httpx (`httpx2.MockTransport` in tests).
  - Model ids are `gpt-image-2`, `gpt-image-2.5-sunburst`, `gpt-image-2.5-flare`; there is no bare `gpt-image-2.5`. A model without `RATES` raises `ValueError` before any call, so **T-PV-006/009 must check the run's model against `RATES` before reserving budget**.
  - The adapter never retries; `ProviderError.retryable` tells T-PV-007 whether to make call 2.
  - **`usage` may be absent for gpt-image-2** (the SDK docstring says "gpt-image-1 only"). Then `cost_micros=None` and the reserved estimate stays as the cost. The T-PV-012 probe settles this.
  - `ProviderErrorKind` lives in `config.py` (settings must not import the SDK).
  - `prepare_provider_input` refuses some photos with `ValueError`: an unreadable ICC profile, or non-sRGB PNG gamma/primaries without ICC. T-PV-009 fixture validation must list these errors. HEIC needs pillow-heif (not installed); fixtures refuse HEIC per the design.
- **`corrections_applied` (ADR-014):** set it from what the prompt builder actually added (any correction line or note), not from "reasons were given". Reasons such as `coloris` that mean nothing for a background leave the background prompt unchanged. This applies when T-PV-006/007/008 create revision requests.
- **Prompt tests carry the expected sentences literally** (`SCENE_MEANING`, `BACKGROUND_MEANING`, `SCENE_RULES` in tests/test_prompts.py). A deliberate wording change in prompts.py must change them too.
- **Codex sandbox:**
  - `uv` is blocked there, and it cannot create temp files;
  - give it `.venv\Scripts\python.exe -B -m pytest <tests> -q -p no:cacheprovider --capture=sys`;
  - it cannot run the DB tests, so always run the full suite locally before calling a task done.
- **Review diffs:** new files are marked intent-to-add (`git add -N`) to appear in `git diff`. They then show as `A` in `git status`; their content is not staged.
- **Secret-guard hook false positive:** it blocked `uv run pytest -q -W error::pytest.PytestUnhandledThreadExceptionWarning` as an "org token". Don't retry that variant; use the plain command and read the warnings summary.
- **Artifact tool paths:** the short scratchpad path `C:\Users\MRAKOT~1\...` is refused by a Read permission rule; use `C:\Users\M Rakotozafy\AppData\Local\Temp\...`.
- **Codex review command:** `codex exec --sandbox read-only -C "<repo>" -o "<review.md>" - < "<brief.md>" > "<log>" 2>&1`, run in the background (codex-cli 0.162.1). There are at most 3 rounds per artifact. The design's review cap is used up; any further design change needs the user's decision on reviewing.
- **No paid call** before T-PV-012. It needs:
  - `OPENAI_API_KEY` from a dedicated OpenAI project, in `backend/.env` (git-ignored);
  - `SPEND_CAP_USD` set;
  - the user's check of that project's budget-limit behaviour.

  The cap only limits *estimated* spend.
- **Unverified, to check in tasks:** whether gpt-image-2 returns `usage` (T-PV-012); rembg model names (T-PV-004).
- **Toolchain:** Python 3.13 is the system default; `backend/.python-version` pins 3.12 (3.12.10 installed). rembg 2.0.74 needs `<3.14`, hence `requires-python = ">=3.12,<3.14"`.
- **Behaviour the user should not be surprised by:**
  - after a rejection, a fresh request for the same product is refused (`use_revision`); the correction note can change the style;
  - a new campaign (cycle) is allowed only after an approval.
- **Git trust:** an exact safe.directory entry is in C:/Users/M Rakotozafy/.gitconfig (ADR-007). Commit only when the user asks; push only on "push".
- BRIEF.md is a pre-bootstrap snapshot; `poster-kit.zip` does not exist (ADR-010).

## Uncommitted / dirty state

Branch main, two commits made at the user's request on 2026-11-06: the initial commit (all docs + T-PV-001) and T-PV-002. No remote; nothing pushed.

Not committed (T-PV-003 and doc updates):
- backend/src/affiche/visuals/gateway.py, backend/tests/test_gateway.py (new, intent-to-add);
- backend/src/affiche/config.py, backend/tests/test_config.py, backend/.env.example, backend/pyproject.toml, backend/uv.lock;
- docs/project/DECISIONS.md (ADR-015), TODO.md, HANDOFF.md;
- docs/project/reviews/t-pv-003-code-r1.md, -r2.md, -r3.md.

`backend/.venv/` exists locally (git-ignored). Review briefs and raw Codex outputs are in the session scratchpad only.

## Next session should

1. Read this file, then TODO.md, then designs/product-visuals.md D-PV-006 (lines 382–426) for T-PV-004.
2. Ask the user whether to commit T-PV-003, if that is not done yet.
3. Implement T-PV-004 with /implement-review. Check the installed rembg version and its model list first; the sample images must be made or freely licensed (no shop photos). Run its verify step; mark it done only after the review is clean.
4. Continue T-PV-005 … T-PV-011 in order, one at a time.
5. Ask the user for the T-PV-012 / T-PV-013 inputs when T-PV-007 is done (key, cap, budget-limit check, photos, arms, thresholds).

## Decisions made this session

- ADR-008: charter and split approved; product-visuals first.
- ADR-009: one candidate per request; fallback cutout as a separate layer.
- ADR-010: user's OpenAI account, 3 attempts, no prototype, user supplies photos, cap required.
- ADR-011: design questions: baked shadow, wording amendments, phase 1 first, evaluation exception (limit 5, arm B), cycles after approval.
- ADR-012: design approved for phase 1; Python 3.12 + uv + pytest.
- ADR-013: backend scaffold choices (pydantic-settings and `ConfigError`, no ORM, `BEGIN IMMEDIATE` recipe, migrate-only Alembic).
- ADR-014: prompt and screen interpretations (background `texte` sentence, the number rule, `corrections_applied` meaning).
- ADR-015: provider gateway: SDK facts (openai 3.46.0 / httpx2), model ids, error codes, usage validity, provider-input colour rules.
