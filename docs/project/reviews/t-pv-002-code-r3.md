**Verdict: APPROVE**

- **r1 #1: CLOSED** — unchanged from r2.
- **r1 #2: CLOSED** — [test_prompts.py](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_prompts.py:23>) now independently specifies all 9 scene sentences and 3 applicable background sentences. Assertions check only the appended correction text, so the reported reversed instructions fail; ignored background codes still must add nothing.
- **New actionable defects:** none. The dedicated note test retains coverage after removal of the redundant assertion.

Verified the supplied diff matches all three current files. Ran the exact requested pytest command from `backend` through the local subprocess fallback: **92 passed in 0.47s**.

No files modified; no network used.