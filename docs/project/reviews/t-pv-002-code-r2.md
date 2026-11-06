**APPROVE WITH FIXES** — one remaining P2 test gap.

1. **R1 #1: CLOSED — decimal-price screening.**  
   [prompts.py:146](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/visuals/prompts.py:146>)  
   Independently reproduced correct matches for `49,99`, `129.90`, and `1  200  000`. `iPhone 15, 128 Go` remains unmatched. Regression cases cover these behaviors. No additional actionable numeric regression or nondeterminism found beyond the documented tradeoffs.

2. **R1 #2: PARTIAL — noun-only assertions still permit incorrect instructions (P2).**  
   [test_prompts.py:23](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_prompts.py:23>), [test_prompts.py:28](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_prompts.py:28>), [test_prompts.py:86](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_prompts.py:86>)  
   The independent fixed-block assertions and three verbatim design sentences address the original examples. However, expectations such as `"colour"` and `"text"` check the topic without protecting the instruction.

   Two independent **in-memory mutations survived all 92 tests**:

   - Background `texte` → `"Add text, numbers, logos and watermarks."`
   - Scene `coloris` → `"Change the product colour to red."`

   Either regression contradicts the intended correction without failing validation. **Fix:** replace noun-only expectations with independent action clauses, such as `"The product colour must match image 1 exactly."` and `"Remove all text, numbers, logos and watermarks."` Apply this to the other noun-only entries; retain the existing parameterized test.

For terseness, strengthen the existing expectation table without adding another test framework or whole-prompt snapshots. The redundant `assert NOTE in prompt` at [test_prompts.py:49](<C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_prompts.py:49>) can be deleted: the dedicated note test already verifies inclusion and placement.

**Verification:** the requested cache-disabled command ran successfully: **92 passed**. Full suite not rerun. Mutations affected process memory only; no files modified and no network used.