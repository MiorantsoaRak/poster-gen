**Verdict: APPROVE WITH FIXES.** No P1 found.

1. **P2 — The twelve-job limit does not bound inherited notes.**  
   [visuals.py:62](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/visuals.py:62) accumulates everything. Copies share versions through `listed_visuals`, while [jobs.py:76](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/jobs.py:76) counts jobs per creation. Repeated copies can therefore carry arbitrarily long histories. Add an explicit total-length/count limit with a clear refusal; never silently truncate. Test inheritance across copies.

2. **P2 — Contradictory adjustments have no stated precedence.**  
   [plans.py:492](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/plans.py:492) says adjustments override art direction, surface and palette, but does not resolve « fond bleu nuit », followed by « fond rouge ». Both reach the model correctly ordered. Add one sentence: later adjustments override earlier conflicting adjustments. Test both order and wording.

3. **P2 — Re-screening refuses safely, but gives misleading recovery advice.**  
   `screen_art` raises `ValueError("scene_contains_commercial_or_instruction_text")`. [visuals.py:259](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/visuals.py:259) catches it and returns `invalid_headline` (422), whose [message](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/api.py:47) blames text settings and recommends reloading. Reloading cannot repair a rejected stored adjustment. Add a specific refusal/message, classify it as final in the chat, and test that nothing is queued or reserved.

Other claims check out:

- Traversal returns oldest first and continues through a scene’s stored adjustments. Current creation paths cannot form cycles: each refinement points to an existing visual, and those links are never rewritten.
- Notes pass `RefinementRequest.scene_adjustment` initially and `screen_art` again during compilation.
- `document.model_dump()` has the shape `listed_visuals` expects. Unknown or foreign shop/input/size references are rejected before enqueue; copies intentionally share eligible versions.
- Without the field, request hashes match HEAD and existing golden prompts remain byte-for-byte unchanged.
- `keptFrom` is scoped to `revise` and cleared in `finally` before the busy lock releases. Saved-request replay remains unchanged; no step-editor leak found.

No substantial removable code found; the traversal needs no new abstraction.

Only in-memory checks ran: golden assertion, hash comparison, traversal order and screen exception. Full suites, build and browser smokes remain unverified; copied histories and conflicting notes are the main uncovered risks.