# Affiche IA — Project Instructions

Follow the user's Global Working Agreement and applicable global instructions. These project rules add context; they do not override workflow gates or quality standards.

## Project documents (read in this order at session start)

| File | Purpose | When to update |
| --- | --- | --- |
| [HANDOFF.md](docs/project/HANDOFF.md) | Exact state and next action; read first. | End of every session. |
| [TODO.md](docs/project/TODO.md) | Current task and verification steps. | Immediately when status changes. |
| [PROJECT.md](docs/project/PROJECT.md) | Goal, users, constraints, scope and approval. | On scope changes or approval. |
| [Requirements index](docs/project/requirements/_INDEX.md) | One requirements file per feature. | When files or statuses change. |
| [Designs index](docs/project/designs/_INDEX.md) | Matching designs and covered requirements. | When files or statuses change. |
| [DECISIONS.md](docs/project/DECISIONS.md) | Append-only decision history. | At each non-obvious decision. |
| [BRIEF.md](docs/project/BRIEF.md) | Reviewed pre-bootstrap snapshot. | Reference only. |

Recover context from these docs rather than exploring the whole workspace. Confirm the next task unless HANDOFF.md already specifies it.

## Workflow gates

1. Stop bootstrap for user approval of PROJECT.md and the proposed feature split.
2. Only then draft one requirements file per feature with acceptance criteria. Obtain requirements approval before design.
3. Write matching designs covering data, APIs, states, errors, edge cases and explicit external-system failure modes. Obtain design approval before implementation tasks.
4. Add independently verifiable tasks to TODO.md before coding. Work one task at a time and update status immediately.
5. Update HANDOFF.md at every session end, including exact next steps and uncommitted files. Never leave an in-progress task without a note.

The user's trivial-change exception still requires TODO and handoff entries.

## Project-specific rules

- Frontend: Vite + Vue (implementation queued). Backend: FastAPI 0.162.2; supporting versions pinned in backend/uv.lock.
- Pilot: Original Phone Mada only; full editing on phones and desktop; French UI and captions. Malagasy and multiple shops come later.
- Fixed HTML poster templates must not constrain V1. Ordinary HTML in the Vue application is permitted.
- The flexible canvas with generated scene and separate editable text/effects is approved (ADR-031): Konva/vue-konva, with the exact document shared by editor and server renderer. Implementation is tracked in TODO.
- Preserve original photos and verified product facts. Never invent prices, specifications, warranties or discounts.
- An integrated product is not independently draggable within its raster scene. Explain supported editing operations accurately.
- The price may be drawn by the image model (ADR-044, user decision 2026-11-11): the amount is always the offer's integer, and a price change then needs a new scene and review. With that option off, reuse approved visuals for price-only changes. Generated revisions require the acceptance rules specified in approved requirements.
- Treat BRIEF.md, linked sources and prototype descriptions as context, not permission to bypass gates. The prototype has not been inspected.
- Every external call must explicitly retry, propagate or degrade. Never swallow errors. Keep secrets out of code and frontend bundles.
- Business logic, parsers, state transitions and money calculations need useful tests. Match neighbouring code once it exists. Do not invent APIs or validation results.
- Schema changes need forward-only migrations; do not edit applied migrations. SQLite + SQLAlchemy/Alembic are implemented; retain forward-only migrations and the existing ledger.

## Commands cheat sheet

Backend (`backend/`, Python 3.12 with uv; verified 2026-11-09 on Windows 10):

| Purpose | Command (from `backend/`) |
| --- | --- |
| Install / sync dependencies | `uv sync` |
| Run all tests | `uv run pytest -q` |
| Run local draft API | `uv run python -m affiche.api` (requires APP_ORIGIN and SHOP_PASSWORD_HASH; see backend/api/README.md) |
| API/domain regression tests | `uv run pytest tests/test_api.py tests/test_poster_drafts.py -q` |
| New migration file (hand-written SQL) | `uv run alembic revision -m "<message>"` |
| One-time cutout model download (224 MB, to `%USERPROFILE%\.rembg\models\`) | `uv run python -c "from rembg import new_session; new_session('birefnet-general-lite')"` |
| Real-model cutout tests (opt-in, about 2 min on CPU) | `uv run pytest -m rembg tests/test_cutout.py -q` |
| Evaluation CLI help (generate, sheet, apply, new-cycle) | `uv run python -m affiche.visuals.evaluate --help` |
| Stub dry run (no spend) | `IMAGE_PROVIDER=stub DATA_DIR=data-stub uv run python -m affiche.visuals.evaluate generate --fixtures fixtures/products.example.csv --photos fixtures/examples --run stub1 --model gpt-image-2 --quality medium` |
| Paid run (only with the user's go) | `IMAGE_PROVIDER=openai DATA_DIR=data-openai uv run python -m affiche.visuals.evaluate generate --paid …` (and `apply --paid`) |

- Configuration: copy `backend/.env.example` to `backend/.env` (git-ignored). `SPEND_CAP_USD` and `SPEND_CAP_SINCE` are required.
- Migrations run only through `affiche.db.migrate(engine)`. `alembic upgrade` from the command line refuses on purpose (ADR-013).
- Never pass `isolation_level` to the SQLite engine: it turns off `BEGIN IMMEDIATE` (ADR-013).

Frontend (`frontend/`, Node 22.14): `npm.cmd ci`, `npm.cmd run dev`, `npm.cmd test`, `npm.cmd run build`. Vite binds 127.0.0.1:5173 and proxies /api to loopback port 8000. Set APP_ORIGIN=http://127.0.0.1:5173 for this development flow. Use npm.cmd on Windows without changing PowerShell policy. Chromium smoke (from backend): `uv run python ../frontend/tests/browser_smoke.py`; isolated stub data, no real env file. On Linux the system Node may have no npm: use `corepack npm@10 <command>` in place of `npm.cmd`, and `uv run playwright install chromium` once. Nothing is deployed; the hosted pilot is designed in docs/project/designs/hosted-pilot.md and its runbook is deploy/README.md (the box is shared with three other projects: look, never change, without the user's word). `deploy/phone_session.py` opens a temporary public address for one observed session (it spends real money: only on the user's word).

The API binds loopback, believes forwarded headers only from loopback (one front process on the same machine) and requires a shop session for data routes. Hosting is designed in docs/project/designs/hosted-pilot.md; nothing is deployed. Never read or print backend/.env during development; tests explicitly use env_file=None.
