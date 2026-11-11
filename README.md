# Affiche IA

AI-assisted product posters for Original Phone Mada, with editable prices, text and branding. The confirmed application stack is **Vite + Vue** with **FastAPI**.

## Current stage

The French Vue editor and FastAPI backend support original-photo intake, independently selected shop details, scene generation/review and editable text with autosave. Selected-text proposals, material effects and confirmed feed PNG export are implemented (see [Tasks](docs/project/TODO.md)).

- Pilot: Original Phone Mada first.
- Full editing on phones and desktop.
- French interface and captions; Malagasy after the pilot.
- Flexible visual composition without fixed HTML poster templates.

## Start here

1. [Handoff](docs/project/HANDOFF.md)
2. [Project charter](docs/project/PROJECT.md)
3. [Tasks](docs/project/TODO.md)
4. [Decisions](docs/project/DECISIONS.md)
5. [Project instructions](AGENTS.md)

The [French brief](docs/project/BRIEF.md) is retained as a source snapshot. The six feature designs and requirements are approved.

Local development: configure backend settings as described in [the API contract](backend/api/README.md), including `APP_ORIGIN=http://127.0.0.1:5173`, then run `uv run python -m affiche.api` from `backend/`. In a second terminal, run `npm.cmd ci` and `npm.cmd run dev` from `frontend/`. Open http://127.0.0.1:5173. The application does not expose provider secrets to the browser.

Frontend checks: `npm.cmd test` and `npm.cmd run build` from `frontend/`. Isolated real-browser smoke: `uv run python ../frontend/tests/browser_smoke.py` from `backend/`; this needs the documented R50i fixture under outputs and the pinned Playwright Chromium (`uv run playwright install --only-shell --no-remove chromium`). It uses temporary data and simulated providers; ports 8000/5173 must be free.

Backend tests: `cd backend; uv run pytest -q`. More commands are in [AGENTS.md](AGENTS.md). Local review copies under outputs/ are ignored by Git; docs/project/ contains the canonical documents.
