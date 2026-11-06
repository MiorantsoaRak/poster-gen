**Verdict: APPROVE.** All three remaining findings are **CLOSED**. No new actionable defects found in the r2 → r3 changes.

| Finding | Ruling | Evidence |
|---|---|---|
| r1 #3 / r2 #1 — Contradictory split | **CLOSED** | [gateway.py:189](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/gateway.py:189>) rejects supplied counts whose sum exceeds input. Both reported cases yield usage/cost `None`; valid partial splits remain accepted through MockTransport. |
| r1 #5 / r2 #2 — Grayscale transparency | **CLOSED** | [gateway.py:100](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/gateway.py:100>) preserves grayscale channels for ICC conversion and expands mode `1`. Regressions confirm transparent white and opaque gray ≈188. |
| r1 #6 / r2 #3 — Chromaticities | **CLOSED** | [gateway.py:120](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/gateway.py:120>) rejects unsupported gAMA/cHRM declarations while respecting ICC/sRGB authority. Acceptance and rejection regressions pass. |

The optional `stub_generate` wrapper was removed.

**Verification:** 127 gateway/config tests passed using the supplied flags, plus 19 additional in-memory cases covering split accounting, transparency and ICC precedence. Current gateway/tests match the supplied artifact. Full suite and mutation runs were not independently repeated.

No files modified; no network used.