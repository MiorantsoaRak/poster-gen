# Doka Studio (Affiche IA)

Doka Studio helps a shop turn a product photo and a verified price in ariary into an advertising poster. Sellers can work in French on a phone or desktop. The application uses Vue and Vite with a FastAPI backend.

## Create and use a poster

1. In **Libre**, describe the poster and optionally add product photos, a reference image and your shop kit. **Pas à pas** helps prepare the same editable prompt. Check the one-credit cost before generating.
2. Compare the finished poster with the original photo and price. Choose **Confirmer pour plus tard** to keep the reviewed PNG in **Mes affiches**, or **Confirmer et télécharger le PNG** to download it immediately.
3. To post a Publication-format image to a Facebook Page, choose **Confirmer et préparer la publication**. Check the destination, description and image order in the composer before choosing **Publier**.

All text, prices and shop identity are drawn by the image model. Without a supplied shop logo, no shop logo is requested. Corrections can change attachments or start from an earlier version; each new image needs review.

The four-step guide is available under **Aide** in the shop. [French walkthrough](docs/project/guide-premiere-affiche.md)

## Pilot scope

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

The [French brief](docs/project/BRIEF.md) is retained as a source snapshot. The [requirements index](docs/project/requirements/_INDEX.md) and [design index](docs/project/designs/_INDEX.md) track approvals by feature. See the [deployment runbook](deploy/README.md) for the hosted pilot.

Local development: configure backend settings as described in [the API contract](backend/api/README.md), including `APP_ORIGIN=http://127.0.0.1:5173`, then run `uv run python -m affiche.api` from `backend/`. In a second terminal, run `npm.cmd ci` and `npm.cmd run dev` from `frontend/`. Open http://127.0.0.1:5173. The application does not expose provider secrets to the browser.

Frontend checks: `npm.cmd test` and `npm.cmd run build` from `frontend/`. Isolated real-browser smoke: `uv run python ../frontend/tests/free_creation_browser.py` and `uv run python ../frontend/tests/unified_creation_browser.py` from `backend/`; build the frontend first and install the pinned Playwright Chromium (`uv run playwright install --only-shell --no-remove chromium`). It uses temporary data and simulated providers; ports 8000/5173 must be free.

Backend tests: `cd backend; uv run pytest -q`. More commands are in [AGENTS.md](AGENTS.md). Local review copies under outputs/ are ignored by Git; docs/project/ contains the canonical documents.
