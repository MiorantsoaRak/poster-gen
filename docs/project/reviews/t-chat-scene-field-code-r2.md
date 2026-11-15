**Verdict: REJECT**

- **P1 — Prices still bypass their field.** [plans.py:54](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/plans.py:54): `écris 9999 dessus`, `affiche 300k en gros`, `écris trois cent mille en bas` and `écris 300,000 en bas` all pass. I verified them through `_change`, `RefinementRequest` and compilation: each reaches `requested_adjustment` beside the independent offer price. Add these regressions; extending the separator list alone will not enforce the dedicated-price rule.

- **P1 — English warranty and promotion requests are newly admitted.** [plans.py:63](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/plans.py:63): `write the text WARRANTY 2 YEARS`, `write the text SALE` and `write the text FREE` pass both chat and refinement validation. Restoring `_INSTRUCTIONS` protects art directions, but adjustments now depend on a commercial-word filter that misses these terms. Cover the English requests explicitly allowed by ADR-102.

- **P2 — The amount regex rejects valid features through partial matching.** [plans.py:54](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/plans.py:54): `10 000 000 Hz` is refused because backtracking matches `10 000` before reaching the unit. Likewise, `1 000` is refused although `1000` passes; telephone `034 00 000 00` is refused. Match complete numeric tokens before applying the unit exception. The requested examples `WH-1000XM6`, `iPhone 15 128 Go`, `2026`, `IP68`, `20 000 Hz` and `108 MP` pass.

**Round-one findings**

| Finding | Status |
|---|---|
| P1 price bypass | **PARTIAL** — ordinary five-digit amounts blocked; bypasses above remain |
| P1 multiline injection | **CLOSED** — `re.S` and regression verified |
| P2 model-written text through art directions/styles | **CLOSED** — `_INSTRUCTIONS` source is byte-identical to HEAD |
| P3 restated words offer refinement | **OPEN, intentional** — recorded user decision; not blocking |
| Missing service-level refinement-chain test | **CLOSED** — wiring asserted by the added test; reviewed only |
| Stale T-CHAT-REDO claim | **CLOSED** — corrected; no withdrawn redo implementation found |

**Tests and remaining gaps**

`walk_guards` meaningfully checks requests, persisted outcomes and recovery controls. Its late-response assertions use a fixed 1.5-second wait, so their negative checks have a timing limit. The copy test verifies real inheritance; its limit check injects oversized history rather than constructing a thirteen-adjustment chain.

Still uncovered: browser refusal of an owner message, and precedence after a word change. The compiler currently emits both brand `Samsung` and kept adjustment `Use sony logo`, with no explicit rule resolving that conflict ([plans.py:509](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/plans.py:509)). Add the precedence rule and regression before relying on literal lettering history.

The shared `checked_adjustments` helper is appropriate; no obvious production-code removal is needed. The reader’s scene text is correctly discarded, and ADR-097/098 handling is unchanged.

Verified: **36 pure tests passed**, including golden prompts, plus in-memory probes; no files changed.  
Not run: service/full suites, browser/device, production, network or paid checks. Price and commercial-word bypasses remain blocking risks.