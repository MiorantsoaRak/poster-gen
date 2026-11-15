**Verdict: APPROVE WITH FIXES.** No bypass of the chat’s `commercial` gate found.

- **P2 — Feature lists can be refused as prices.** [_NUMBER at plans.py:54](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/plans.py:54) consumes `Bluetooth 5.2, 2026, 128` as one numeric token. The adjustment is refused even with `commercial=False`; using semicolons passes. Distinguish list separators from grouped amounts and add a regression while retaining rejection of `300\n000` and `300,000`. This affects supported feature requests; it is not a commercial bypass.

The six claims check out, with that qualification:

1. Both chat paths producing a refinement enter [`adjust`](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/reads.py:326). `commercial=True` stops them before the list. With no scene signal, refusal can become `same` or `unclear`; no adjustment escapes.
2. Actual word changes bypass this gate appropriately. With extracted price `420000` and a scene signal, “prix 420 000 Ar et ajoute promo” offers **only the price change**, then asks for the scene separately. The promotion text is discarded.
3. Missing, null, string and numeric `commercial` values fail strict validation and reach the existing `unclear` path.
4. Kept notes come from screened refinement fields or previously kept notes and are screened again by [`checked_adjustments`](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/visuals.py:67). An editor adjustment **can later ride into a chat request without reader reassessment**. That matches the accepted editor exception.
5. Numeric false refusals are described above.
6. The outgoing schema contains a required boolean and its full description.

No reader-written scene wording reaches the image prompt. Existing word checks remain. No ADR-097/098 changes or withdrawn redo implementation found.

| Round-three finding | Ruling |
|---|---|
| Commercial wording bypasses | **CLOSED under ADR-102**: chat reader gate wired correctly; editor limitation accepted |
| Injected instructions | **CLOSED under ADR-102**: named regex gaps fixed; semantic refusal wired |
| Partial numeric matching; reader-written plans/styles | **CLOSED** |
| Chain test; kept-adjustment precedence; redo residue | **CLOSED** |
| Restated words offer refinement | **OPEN, intentional and accepted** |

`walk_guards` checks requests, persisted outcomes and recovery meaningfully. Its [fixed 1.5-second wait](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/tests/chat_browser.py:1327) weakens late-response assertions. The copy test proves inheritance; its injected oversized history proves admission checking, not traversal through thirteen real adjustments.

No substantial production deletion is warranted. Still missing from lasting tests: malformed `commercial` answers and the mixed price/promotion case.

**Verified:** 43 targeted pure tests passed, including golden prompts; seven additional mocked read-path checks passed.

Not run: store-writing suites, browser/device, production, network or paid checks; the lead’s results are not counted as mine.  
No files changed; `backend/.env` was not read. Reader misclassification remains an accepted model limitation.