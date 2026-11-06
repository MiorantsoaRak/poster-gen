# HANDOFF

> Updated at session end. Read this before exploring the project.

**Session date:** 2026-11-06 (Indian/Mauritius)  
**Working on:** product-visuals phase 1. T-PV-001 (backend scaffold) done and reviewed; next is T-PV-002.

## State of the world

Canonical repository: C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia (branch main, unborn: no commits, no remotes).
- PROJECT.md and the six-feature split: approved (ADR-008).
- requirements/product-visuals.md: R-001 … R-008 approved; R-003, R-004 and R-005 amended on 2026-11-06 (ADR-011).
- designs/product-visuals.md r4: approved for **phase 1** (ADR-012). Phase-2 HTTP/session/UI contracts are draft until design v2, after the paid evaluation.
- `backend/` exists (T-PV-001, ADR-013):
  - Python 3.12 + uv project, package `affiche` (`src/affiche/config.py`, `src/affiche/db.py`);
  - Alembic migration 0001 with the whole D-PV-001 schema;
  - 23 pytest tests;
  - commands are in AGENTS.md → Commands cheat sheet.
- No `backend/.env`, no database file, no service and no paid API call exist.

## Done this session

- Requirements drafted and approved (ADR-009, ADR-010); design reviewed through Codex r1–r4 + devil's-advocate and approved for phase 1 (ADR-011, ADR-012).
- TODO.md: T-PV-001 … T-PV-011 buildable now (stub/mocked only); T-PV-012 (paid probe) and T-PV-013 (paid evaluation) blocked on user inputs.
- **T-PV-001 done** via /implement-review:
  - an Opus agent implemented it;
  - Codex r1 → APPROVE WITH FIXES: the alembic command-line fallback was deleted, and the two-process test was rewritten with handshakes and bounded reads;
  - Codex r2 → APPROVE;
  - reviews: docs/project/reviews/t-pv-001-code-r1.md and -r2.md;
  - verified: `cd backend; uv run pytest -q` → 23 passed; 3 mutations killed.

## In progress — exact resume point

- **Task:** none in progress.
- **Next action:** T-PV-002 (D-PV-002 prompts and the commercial-terms screen; pure functions). The user asked for /implement-review for T-PV-001; confirm the same flow for T-PV-002. One task at a time; mark `[~]` with a note when starting.

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
- **Codex sandbox:** it cannot create temp files, so it cannot run the DB tests; it ran the 19 config tests only. Always run the full suite locally before calling a task done.
- **Secret-guard hook false positive:** it blocked `uv run pytest -q -W error::pytest.PytestUnhandledThreadExceptionWarning` as an "org token". Don't retry that variant; use the plain command and read the warnings summary.
- **Artifact tool paths:** the short scratchpad path `C:\Users\MRAKOT~1\...` is refused by a Read permission rule; use `C:\Users\M Rakotozafy\AppData\Local\Temp\...`.
- **Codex review command:** `codex exec --sandbox read-only -C "<repo>" -o "<review.md>" - < "<brief.md>" > "<log>" 2>&1`, run in the background (codex-cli 0.162.1). The design's review cap is used up; any further design change needs the user's decision on reviewing.
- **No paid call** before T-PV-012. It needs:
  - `OPENAI_API_KEY` from a dedicated OpenAI project, in `backend/.env` (git-ignored);
  - `SPEND_CAP_USD` set;
  - the user's check of that project's budget-limit behaviour.

  The cap only limits *estimated* spend.
- **Unverified, to check in tasks:** OpenAI SDK method signatures and error fields (T-PV-003); whether gpt-image-2 returns `usage` (T-PV-012); rembg model names (T-PV-004).
- **OpenAI docs read 2026-11-06:** gpt-image-1 shut down 2026-10-23; gpt-image-2 / 2.5 cost $8 / $30 per 1M image input/output tokens; omit `input_fidelity` for gpt-image-2.
- **Toolchain:** Python 3.13 is the system default; `backend/.python-version` pins 3.12 (3.12.10 installed). rembg 2.0.74 needs `<3.14`, hence `requires-python = ">=3.12,<3.14"`.
- **Behaviour the user should not be surprised by:**
  - after a rejection, a fresh request for the same product is refused (`use_revision`); the correction note can change the style;
  - a new campaign (cycle) is allowed only after an approval.
- **Git trust:** an exact safe.directory entry is in C:/Users/M Rakotozafy/.gitconfig (ADR-007). There is no initial commit; the user has not asked for one.
- BRIEF.md is a pre-bootstrap snapshot; `poster-kit.zip` does not exist (ADR-010).

## Uncommitted / dirty state

Branch main, unborn; nothing staged. Everything is untracked:

- .gitignore, README.md, AGENTS.md
- docs/project/BRIEF.md, PROJECT.md, TODO.md, HANDOFF.md, DECISIONS.md
- docs/project/requirements/_INDEX.md, _TEMPLATE.md, product-visuals.md
- docs/project/designs/_INDEX.md, _TEMPLATE.md, product-visuals.md
- docs/project/reviews/product-visuals-design-r1.md, -r2.md, -r3.md, -r4.md, -devils-advocate.md, t-pv-001-code-r1.md, t-pv-001-code-r2.md
- backend/: pyproject.toml, uv.lock, .python-version, .env.example, alembic.ini, src/affiche/{__init__,config,db}.py, migrations/{env.py,script.py.mako,versions/0001_initial.py}, tests/{test_config,test_db,tx_worker}.py

`backend/.venv/` exists locally (git-ignored). Review briefs and raw Codex outputs are in the session scratchpad only.

## Next session should

1. Read this file, then TODO.md, then designs/product-visuals.md D-PV-002 (lines 177–220) for T-PV-002.
2. Confirm T-PV-002 with the user and implement it with /implement-review; run its verify step; mark it done only after the review is clean.
3. Continue T-PV-003 … T-PV-011 in order, one at a time.
4. Ask the user for the T-PV-012 / T-PV-013 inputs when T-PV-007 is done (key, cap, budget-limit check, photos, arms, thresholds).
5. Offer an initial commit; commit only when asked.

## Decisions made this session

- ADR-008: charter and split approved; product-visuals first.
- ADR-009: one candidate per request; fallback cutout as a separate layer.
- ADR-010: user's OpenAI account, 3 attempts, no prototype, user supplies photos, cap required.
- ADR-011: design questions: baked shadow, wording amendments, phase 1 first, evaluation exception (limit 5, arm B), cycles after approval.
- ADR-012: design approved for phase 1; Python 3.12 + uv + pytest.
- ADR-013: backend scaffold choices (pydantic-settings and `ConfigError`, no ORM, `BEGIN IMMEDIATE` recipe, migrate-only Alembic).
