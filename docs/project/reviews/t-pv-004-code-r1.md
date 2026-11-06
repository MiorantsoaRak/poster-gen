**APPROVE WITH FIXES**

1. **P1 — rembg failures escape the adapter.** [cutout.py:129](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/cutout.py:129>) and line 123. An unavailable ONNX DLL makes rembg call `sys.exit(1)` during import, outside the handler; reproduced as `SystemExit`. Inference failures also escape unchanged, potentially aborting T-PV-009’s batch. **Fix:** protect imports, explicitly translate rembg’s import-time `SystemExit`, and replace the unguarded lambda with inference error handling that raises `CutoutUnavailable`. Preserve `MemoryError` for the design’s `cutout_error` mapping. Add mocked failure tests.

2. **P2 — dropping profiles changes product colours.** [cutout.py:71](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/cutout.py:71>). A palette PNG can have a valid **RGB** ICC profile, which this mode check discards. Gray profiles also cannot simply be dropped without changing appearance: reproduced source grey displaying as `(188,188,188)` becoming `(128,128,128)` in the cutout. **Fix:** preserve RGB profiles when expanding palette images; reject unsupported profiled gray/CMYK inputs with `ValueError` unless their appearance can be preserved without changing pixels. Replace `test_a_gray_icc_profile_is_dropped_from_the_rgb_cutout` with that contract’s test.

No RGB-byte/binary-alpha violation or mask-order, placement or shadow-formula mismatch found.

Validation: **59 passed, 3 deselected with `NUMBA_DISABLE_JIT=1`**; the normal run stalled importing rembg. Real-model tests were not run. Synthetic-mask peak memory at 12/40/50 MP: **393/1086/1331 MiB**, excluding ONNX inference.

No edits or network calls.