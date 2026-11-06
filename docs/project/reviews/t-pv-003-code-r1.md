**Verdict: APPROVE WITH FIXES.** Six reproducible defects; no files changed.

1. **P1 — A malformed configured key escapes unredacted.** [gateway.py:196](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/gateway.py:196>)  
   A key followed by an invisible `U+200B` passes configuration, then HTTP header construction raises `UnicodeEncodeError`. Its `repr` contains the complete key; this handler does not catch it. **Fix:** reject non-ASCII/control characters with a constant configuration error before constructing the client. Test the exception representation and chain.

2. **P2 — Raw usage bypasses secret redaction.** [gateway.py:242](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/gateway.py:242>)  
   Mocked `usage=KEY` prints the key through the warning at line 245. `input_tokens=KEY` also exposes it through Pydantic serialization warnings and `ProviderResult.__repr__`; arbitrary extra usage fields survive serialization. **Fix:** remove raw `%r` logging and replace unrestricted `to_dict()` with an allowlist of validated numeric usage fields. Test logs, warnings and result representations.

3. **P2 — Malformed usage can replace the reservation with an undercount.** [gateway.py:155](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/gateway.py:155>)  
   Through the real SDK, `input_tokens=true`, `output_tokens=false`, with `total_tokens=6000` and the existing token breakdown, becomes **5 micro-USD**. The SDK coerces booleans before `_token_count()` sees them. Zero totals with the same breakdown produce zero cost. T-PV-007 would replace its reservation with that amount. **Fix:** validate raw usage counts and consistency before SDK coercion; unusable usage must yield `None`. Exercise this through `MockTransport`, not only `cost_micros()` directly.

4. **P2 — Decoding failures escape classification or retain unsafe chains.** [gateway.py:196](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/gateway.py:196>), [gateway.py:131](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/gateway.py:131>)  
   Invalid UTF-8 JSON raises an uncaught `UnicodeDecodeError`; its representation includes response bytes. Separately, `b64_json=KEY+"é"` produces a sanitized `ProviderError` whose nested cause still contains the key. **Fix:** classify JSON decoding failures as `invalid_response`; raise image-validation failures outside their handlers without retaining raw causes or contexts. Add both regressions.

5. **P2 — Alpha flattening breaks valid grayscale ICC inputs.** [gateway.py:95](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/gateway.py:95>)  
   A grayscale PNG with a valid grayscale ICC profile succeeds in mode `L`, but fails in `LA`: flattening converts it to RGB before applying the grayscale profile, producing “cannot build transform.” **Fix:** separate alpha, transform the original colour channels to sRGB, then restore alpha and flatten.

6. **P2 — Removing non-ICC colour metadata changes appearance.** [gateway.py:103](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/gateway.py:103>)  
   A PNG with `gAMA=1.0`, no ICC profile and gray value 128 exits unchanged at 128 with its gamma removed; equivalent sRGB is approximately 188. **Fix:** honour declared colour metadata before stripping it, or explicitly reject unsupported interpretations. Replace the sRGB→sRGB spy test with a non-sRGB pixel assertion.

**Dependency cleanup:** keep the direct `httpx2` import and declare it explicitly in `pyproject.toml`; both the constructor contract and tests use it. Removing only the annotation import leaves the test dependency implicit.

The installed SDK contracts check out. No change requested to the documented quota/rate-limit or refusal mapping. [Error codes](https://developers.openai.com/api/docs/guides/error-codes), [image-generation errors](https://developers.openai.com/api/docs/guides/image-generation#handling-blocked-requests-and-other-errors).

**Verification:** 102 gateway/config tests passed using the venv Python with bytecode and pytest caching disabled. Additional reproductions ran entirely in memory with mocked transport. Full suite and pricing were not independently rechecked.