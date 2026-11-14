**REJECT** — the price guard can accept an amount the owner did not write.

1. **P1 — Partial amounts become valid prices.** [reads.py:77](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/reads.py:77)  
   Confirmed with in-memory checks: `Prix 700<TAB>000 Ar` accepts **0**, `Prix 1234 567 Ar` accepts **567**, and `Prix -700 000 Ar` accepts **700000**. With those model outputs, `build()` returns a recap. The regex restarts inside malformed or signed amounts.  
   **Smallest fix:** validate the complete numeric run before generating suffix candidates; reject malformed grouping and signed amounts. Add these cases through `build()`, asserting `ask_price`.

2. **P2 — Truncation and unexpected models become successful reads.** [reads.py:291](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/reads.py:291)  
   `ClaudePlanner.structured()` reports envelope failures and schema failures with the same `invalid_read` code. Consequently, `stop_reason="max_tokens"` and an unexpected response model both produce `succeeded` plus `unclear`. Confirmed using mocked transport and in-memory finalisation. The design requires provider cuts to follow the failure path.  
   **Smallest fix:** distinguish incomplete/unexpected provider responses from schema violations. Only schema violations should become successful `unclear` cards; preserve readable usage costs on failures. Correct the expectation at `test_reads.py:276`.

3. **P2 — The timeout test passes without a timeout.** [test_reads.py:302](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_reads.py:302)  
   Remove `wait_for`: `slow()` eventually returns `None`, unpacking raises `TypeError`, and the generic exception handler produces exactly the failure and ledger state asserted by this test.  
   **Smallest fix:** make `slow()` return a valid successful tuple after sleeping. Without the timeout, the test must then fail.

4. **P2 — The required combined-ledger test is missing.** [test_reads.py:344](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_reads.py:344)  
   The cap test seeds only `chat_reads`. A regression that omits existing `poster_calls` or `provider_calls` from read admission would escape it. For example, with a $0.03 cap, an existing $0.02 poster call must block a $0.02 read.  
   **Smallest fix:** seed distinct costs across all three tables, including rows before `SPEND_CAP_SINCE`, and assert both the combined total and admission refusal.

5. **P3 — Invalid UUID keys can initiate paid reads.** [api.py:439](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/api.py:439)  
   The shared `Key` pattern accepts `------------------------------------`. Unlike routes using `store.mutate`, this route performs no subsequent UUID validation.  
   **Smallest fix:** validate a canonical UUID before admission; add a rejection test asserting no provider call or reservation.

By inspection, admission correctly serializes reservations with `BEGIN IMMEDIATE`, counts running reads, and calls the provider outside transactions. The conditional finalisation protects swept rows. Earlier migrations, dependencies and golden prompt tests are unchanged.

Rulings on the stated divergences:

| # | Ruling |
|---|---|
| 1 | Accept both French sentences. |
| 2 | Accept the small duplication; the checks currently match `compile_scene`. Pinning the prompt does not itself require duplication. |
| 3 | Accept the short mode-lock duplication. |
| 4 | Accept; committing before replay refusal preserves the sweep. |
| 5 | Accept status-derived failure replay; storing identical failure JSON adds little here. |
| 6 | Accept stricter configuration readiness. It does **not** establish admission against the mode lock, cap or daily limit. |
| 7 | Accept; the reservation remains counted, and replay can persist the sweep. |
| 8 | Fix finding 5. |
| 9 | Partially reject: malformed-run suffix extraction breaks the price guard. Refusing decimals and letter-attached amounts is reasonable. |
| 10 | Accept genuine schema violations as `unclear`; exclude provider-envelope failures per finding 2. |

Additional coverage missing: simultaneous read admissions competing for the last reservation, another shop’s creation, and another shop’s replay key. The current ownership test checks only a nonexistent creation.

No files changed; only read-only inspection, in-memory checks and `git diff --check` ran. The claimed 39/835 passing results remain unverified; no prohibited commands ran and `backend/.env` was not accessed.  
Remaining risk: prompt-string assertions do not establish injection resistance or extraction accuracy; those need the planned T-CHAT-002 evaluation.