**Verdict: APPROVE WITH FIXES.** Three remaining P2 defects. **119 gateway/config tests passed**, plus in-memory reproductions. No files changed; no network used. Full suite not rerun.

| R1 finding | Ruling | Evidence |
|---|---|---|
| 1. Malformed key leakage | **CLOSED** | `config.py:51` rejects invalid characters; configuration regressions pass without values or exception chains. |
| 2. Raw usage leakage | **CLOSED** | `gateway.py:164–182` retains numeric allowlisted fields. Additional raw-secret/count/split probes produced no leaks or serialization warnings. |
| 3. Malformed usage undercount | **PARTIAL** | Reported guards work, but contradictory image counts remain accepted; finding 1 below. |
| 4. Decoding failures | **CLOSED** | Invalid UTF-8 and non-ASCII base64 yield sanitized `invalid_response`, without chains. A pre-send `ValueError` remains a `ValueError`. |
| 5. Gray ICC with transparency | **PARTIAL** | `LA` works; grayscale `tRNS` still fails; finding 2. |
| 6. Non-ICC colour metadata | **PARTIAL** | Unsupported gamma is rejected, but non-sRGB chromaticities are silently discarded; finding 3. |
| 7. Direct dependency | **CLOSED** | `pyproject.toml:8` declares `httpx2`; lock resolves 2.16.0. |

1. **P2 — Contradictory image counts still replace the estimate.** [gateway.py:169](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/gateway.py:169>)  
   Through MockTransport, `input_tokens=10`, `output_tokens=2`, details `{text_tokens:10, image_tokens:10}` returns **110 micro-USD**, despite the breakdown exceeding input. An image-only count of 11 against input 10 also passes.  
   **Fix:** reject when the sum of supplied text/image counts exceeds `input_tokens`. This preserves partial breakdowns without requiring equality. Add both transport regressions; expect usage and cost `None`.

2. **P2 — Grayscale transparency still changes mode before ICC conversion.** [gateway.py:99](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/gateway.py:99>)  
   A valid `L` PNG with `transparency=0` and the gray ICC fixture becomes RGBA, then RGB. Applying its GRAY profile fails with **“cannot build transform”**. Mode `1` with a gray profile fails similarly.  
   **Fix:** extract the transparency mask while retaining `L` colour data; expand mode `1` to `L`. Apply the ICC before flattening. Add a grayscale `tRNS` regression. Palette PNGs with RGB ICC and both indexed and partial transparency passed my probes.

3. **P2 — Matching gamma does not establish sRGB primaries.** [gateway.py:95](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/gateway.py:95>)  
   A PNG with `gAMA=0.45455`, P3 `cHRM` primaries and no ICC passes. Its `(100,150,100)` pixels remain unchanged while all colour metadata disappears, causing those values to be interpreted as sRGB.  
   **Fix:** extend the chosen rejection policy to unsupported chromaticities when no authoritative ICC/sRGB declaration exists. Add a non-sRGB `cHRM` fixture.

The requested usage variants **all passed through the installed SDK**: `output_tokens_details` present, `total_tokens` absent, image-only input details, and their combination. Missing text details retain the conservative image-input rate.

The hand-built ICC fixture is **sound for this regression**: LittleCMS reads v2.1 GRAY/XYZ, and six gray levels matched an independently calculated sRGB transfer curve, including **128 → 188**.

Optional simplification: delete [test_gateway.py:423](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_gateway.py:423>)’s `stub_generate` wrapper and call `generate` directly; their defaults are identical.