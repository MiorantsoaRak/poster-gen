# Code review r3 — T-FB-014: the draft's row as the owner asked (bin and handle at its right end, no « Plus tôt » / « Plus tard »)

Reviewer: Codex, read-only, 2026-11-22. Verdict: APPROVE WITH FIXES (one P2 in the walk, one P3 in the documents). Both fixed; not reviewed again.

- **P2** — [publish_browser.py:264](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/tests/publish_browser.py:264). The page can scroll between the last hit test and `mouse.down()`. A press on a neighboring handle also gives the list its `sliding` class, so the helper can pass for the wrong poster. Assert that `row(title)` has the `lifted` class after moving the mouse.
- **P3** — [facebook-post-page.md:190](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/facebook-post-page.md:190) still lists « Plus tôt » and « Plus tard » as current controls. [TODO.md:184](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/TODO.md:184) likewise says both buttons stay. Update both descriptions to specify the bin followed by the handle when at least two posters are selected.

Read-only review. The 360 px layout was checked from CSS only.

**APPROVE WITH FIXES**