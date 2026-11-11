**Verdict: APPROVE WITH FIXES.** One new P2 regression; the requested decision/admission containment fixes are complete.

**P2 — The CSV now confuses a reporting error with a failed request.** At [evaluate.py:409](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/evaluate.py:409>), every non-`None` outcome becomes `request_failed:<outcome>`. However, [`_scene`](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/evaluate.py:285>) returns `UNEXPECTED` for exceptions in execution **or subsequent progress reporting**.

Two concrete paths:

- Generation succeeds, then `_committed_line` raises once: the database contains `succeeded`, but the CSV says `request_failed:unexpected`.
- Execution records `failed / invalid_request` and rethrows an unexpected exception: the CSV loses the stored kind and says `request_failed:unexpected`.

R1’s second query preserved the persisted outcome in both cases. **Fix:** return the request outcome separately from the unexpected-error flag; use the former for CSV and the latter for exit 1. Keep this inside `_scene`, without restoring the second query loop. Add regressions for a one-time progress-reporting exception and an execution exception after failure recording.

| Item | Ruling | Evidence |
|---|---|---|
| **1. Abandon running guard** | **CLOSED** | Replay precedes the scope-wide running check at [evaluate.py:541](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/evaluate.py:541>). [Test:334](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_apply.py:334>) covers an API-owned scene revision blocking `photo_preserved` abandonment, with K1 still proposed. |
| **2. Per-row containment** | **CLOSED** | Both loops catch unexpected exceptions; `Refused` retains its separate handling. [Test:387](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_apply.py:387>) asserts the exact five results, exit 1, C1’s success, and no running provider calls. Admission writes remain inside one rollback-capable transaction. |
| **3. Complete sheet listing** | **CLOSED** | [sheet.py:69](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/sheet.py:69>) enumerates pending candidates and proposed cutouts independently of open scopes. [Test:143](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_apply.py:143>) checks both HTML and CSV after abandonment. |
| **4. Encoding** | **CLOSED** | [`_decode`:457](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/evaluate.py:457>) implements strict BOM→UTF-8 and BOM-less UTF-8→cp1252. [Tests:355](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_apply.py:355>) cover all three encodings, replay, malformed BOM input, and `0x81`. |
| **5. Interrupted replay regression** | **CLOSED** | [Test:344](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_apply.py:344>) uses `recover`, then asserts k=0 interrupted and k=1 succeeded. |
| **6. Result documentation** | **CLOSED** | [Help text:729](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/evaluate.py:729>) documents `not_started` and `error:<exception>`. |
| **7. Terseness** | **PARTIAL** | **(a) CLOSED:** shared [`rejection_payload`](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/review.py:41>). **(b) PARTIAL:** second query removed, but outcome conflation needs the fix above. **(c) CLOSED:** `sheet.COLUMNS` supplies both writer and reader. |

No additional actionable decoding or listing defects found. The new decision/admission boundaries introduce no identified request-stranding or duplicate-spend path. No further substantial deletion in `evaluate.py` is clearly warranted.

Static review only: the launcher failed. All supplied diff hunks match the inspected files; your test and mutation results were not independently rerun. No files modified, no network used, and `backend/.env` never opened.