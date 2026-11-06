# Affiche IA

AI-assisted product posters for Original Phone Mada, with editable prices, text and branding. The confirmed application stack is **Vite + Vue** with **FastAPI**.

## Current stage

Product-visuals phase 1 is being built (see [Tasks](docs/project/TODO.md)). The `backend/` scaffold exists (Python 3.12 + uv, SQLite schema, settings). There is no frontend yet.

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

The [French brief](docs/project/BRIEF.md) is retained as a source snapshot. Requirements and designs each have an index and template; feature documents will follow only after the applicable approvals.

Backend tests: `cd backend; uv run pytest -q`. More commands are in [AGENTS.md](AGENTS.md). Local review copies under outputs/ are ignored by Git; docs/project/ contains the canonical documents.
