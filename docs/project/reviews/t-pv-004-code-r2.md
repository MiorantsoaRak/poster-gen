**APPROVE**

1. **P1 — CLOSED.** [cutout.py:131](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/cutout.py:131>): imports, remote-model refusal and session creation are guarded, including import-time `SystemExit`. Failures become `CutoutUnavailable` with their cause preserved and are not cached. The regression test passes. Inference-error propagation matches the clarified contract; it leaves no concrete defect in this task.

2. **P2 — CLOSED.** [cutout.py:70](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/cutout.py:70>) and [cutout.py:84](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/cutout.py:84>): palette images retain their RGB ICC profile and pixels. CMYK, non-RGB profiles and unsupported gamma/primaries are rejected before masking. Preservation and rejection tests pass.

**No new actionable defects found.**

Validation: **135 passed, 3 deselected** using the requested command with `NUMBA_DISABLE_JIT=1`. Real-model tests were not rerun. No files modified; no network used.