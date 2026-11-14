# Editor refinements — verification, 2026-11-14

Implementation authorized autonomously by the owner. Requirements/design independently reviewed before implementation; code review r1 defects resolved and r2 approves with nits (both nits applied). No commit, push, release, paid image call, schema migration or dependency addition.

## Verified

- Full backend: `cd backend && .venv/bin/python -m pytest -q` — **793 passed, 3 deselected**. The three opt-in real-cutout-model tests were not run.
- Additional original-logo render checks: `tests/test_editor_refinements.py` — **21 passed** after extending the six corner/format cases to render actual exported sources. Publication, Carré and Story, both corners: original translucent 1:2 logo stays within its reserved box, retains aspect ratio, blends at its source alpha. Title placement, crop/movement refusals before refinement charging/export, and both legacy/new two-generation brand behavior also pass.
- Frontend: `corepack npm@10 test` — **150 passed**; `corepack npm@10 run build` passes type checking and bundling.
- Focused production-build browser: `cd backend && .venv/bin/python ../frontend/tests/editor_refinements_browser.py` — **passed**, real Chromium with isolated HTTP API, stub providers, `_env_file=None`, temporary data and no keys. Two explicitly confirmed simulated scene calls; recorded spend zero. Checks include:
  - empty and populated profiles start all identity switches off, including reload;
  - explicit missing-detail import, profile revision-conflict recovery without draft mutation;
  - duplicate-brand notice and server marker; unchanged exact title/integer price;
  - neutral palette from a black product photo, manual persistence, delayed decoder cannot overwrite a manual choice, failed sampling blocks generation and manual/retry recover, submitted palette matches swatches;
  - corner choice/save/reload, moved-logo refusal/recovery/navigation, corner → historical footer restoration; explicit missing-disc scenes hide the logo instead of guessing a footer position;
  - controls and versions at 320/360/390 px; hide/show preview, unique version names and outline padding, measured contrast; at 360×282 the proof automatically hides and the focused field remains entirely below the sticky tabs without test-side scrolling;
  - no page JavaScript errors.
- Existing browser smoke coverage completed in sections: the combined run completed the main workflow, seal reselection/copy preservation, waiting/reconnection, word persistence, desktop/mobile themes and unauthenticated reopening before termination during formats. The same `walk_wait` and `walk_formats` helpers were also run independently against isolated stub services and passed. One isolated format attempt reported `render_unavailable`; rerun with a stable completed build and diagnostics passed all formats/themes, without a renderer source change. The monolithic command did not produce a clean final exit, so it is not recorded as a monolithic pass. Scratch launchers: `/tmp/affiche-wait-check.py`, `/tmp/affiche-format-check.py`; checked-in scenarios remain in `frontend/tests/browser_smoke.py`.
- Screenshots inspected: `outputs/editor-refinements/controls-360.png` and `keyboard-282.png`. Other focused artifacts/results in the same ignored directory.

## Limits

The reserved logo area and photo palette are generation instructions, not proof that a paid image model obeys them. No new paid visual fidelity/collision comparison was performed; final composite review remains required. Product-colour sampling is a small local heuristic and has a visible manual override for difficult backgrounds.

Browser checks use simulated devices in desktop Chromium, not a physical Android keyboard, screen-reader speech, or native browser zoom. The user's Edge window was inspected only enough to determine it was on another site and was left alone. The deployed frontend has not been changed or verified with these fixes: deployment is user-controlled under AGENTS.md and deploy/README.md. No Postman CLI is installed; the existing HTTP/API and browser suites were used without adding a dependency.
