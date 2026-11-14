**APPROVE** — no correctness or money-handling defect found.

- **(a) Price guard:** no counterexample found outside the explicitly accepted rules. Across 20,000 adversarial messages, every candidate came from whole numeric tokens immediately before a recognized unit. All 1,981 accepted candidates also passed both `build()` paths.
- **(b) Shared adapter:** plan, look and text-patch request bodies matched commit `41c0906` byte for byte, including prompts; none acquired a `thinking` field. Thinking-plus-text responses now succeed as intended. Malformed, duplicate-text, truncated and unexpected-model responses retained their failure and cost behavior in 54 mocked adapter probes.
- **(c) P3, optional cleanup — [reads.py:117](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/reads.py:117):** `or "." in span[-1]` is redundant. Every dotted token allowed by `_PURE` already exceeds three characters (`1.000` is five). **Failing input:** none; behavior is equivalent. **Smallest fix:** remove that clause.

Verification: **183 selected tests passed**, including pinned feed/square prompt checks; `git diff --check` passed. No files changed.

Not verified: the full 939-test claim, database integration, or live API/26-message results. No network, paid, device or store-writing operations ran; `backend/.env` was untouched.  
Remaining risk: real-model extraction accuracy is supported only by the supplied evaluation report.