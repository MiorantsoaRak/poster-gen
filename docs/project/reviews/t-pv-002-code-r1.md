**APPROVE WITH FIXES** — two P2 findings.

1. **P2 — Ordinary decimal prices bypass the screen.** [prompts.py:145](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/prompts.py:145>)  
   Reproduced: `afficher 49,99 en grand` and `ajouter 129.90 en bas` both return `[]`. These contain ≥4 digits with punctuation ignored, as D-PV-002 specifies, and would pass screening before entering the prompt. `1  200  000` also escapes because separators must be single characters.  
   **Fix:** extend numeric matching to decimal amounts with ≥4 total digits and repeated spaces between thousands groups. Add these cases; retain the `iPhone 15, 128 Go` negative. The thousands-only interpretation narrows the design too far.

2. **P2 — Tests do not protect the essential prompt wording.** [test_prompts.py:32](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_prompts.py:32>), [test_prompts.py:62](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_prompts.py:62>)  
   Two independent, **in-memory** mutations survived all 84 tests:
   - Removing scene rule 2 and the background no-product/no-text rule.
   - Replacing the camera correction with `Add a price badge beside the camera.`

   The fixture-exclusion test does not check instructions, and correction tests import their expectations from production. Consequently, a regression can remove ADR-011’s main guard or introduce a price instruction unnoticed.  
   **Fix:** add one parameterized fixed-block test covering both builders. Replace correction assertions derived from production dictionaries with independent expected wording or essential fragments, including the three sentences specified verbatim by D-PV-002. Avoid duplicating whole prompts.

Interpretation rulings:

| # | Ruling | Reason |
|---|---|---|
| 1 | **Keep** | Explicit precedence supports rule 2; it does not guarantee model compliance. |
| 2 | **Keep** | Accommodates multiple product photos; the separate last-image instruction identifies the style reference. |
| 3 | **Keep** | Studio applies only when `is_default`; description/reference-only directions are intentional. |
| 4 | **Keep** | Omitting empty correction sections is correct and simpler. |
| 5 | **Keep normalization; change wording** | NFC handles decomposed accents correctly. At [prompts.py:152](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/prompts.py:152>), replace “as typed” with “NFC-normalized, with accents preserved.” Raw-text highlighting must normalize too. |
| 6 | **Keep the stated tradeoffs** | They follow the chosen boundaries and best-effort policy. The additional numeric misses in finding 1 need fixing. |

The background `texte` extension is justified. `Direction` JSON round trips preserve default-versus-explicit-studio behavior. Keep arm selection in callers; later code must not equate `bool(corrections)` with corrections actually emitted—ignored background codes can produce an unchanged prompt.

**Verification:** `uv` was blocked by cache permissions. From `backend`, this equivalent command ran successfully:  
`.venv\Scripts\python.exe -B -m pytest tests/test_prompts.py -q -p no:cacheprovider --capture=sys` → **84 passed**. Full suite not run. No files modified; no network used.