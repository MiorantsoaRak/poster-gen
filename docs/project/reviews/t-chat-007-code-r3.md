**APPROVE** — no remaining P1/P2 defect found in this diff.

Previous findings:

- **Round 1: P1 CLOSED, P2 CLOSED, P3 CLOSED.**
- **Round 2: P1 CLOSED.** Ownership checks now protect plan requests, response adoption and `planSignature` updates ([App.vue:1041](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:1041)). Isolated probes passed for takeover during saves, plan responses and plan revisions. Removing the response guard in memory reproduced the adoption defect.
- **Round 2: selection P2 CLOSED.** `GONE` closes the card only after its recorded job reports success. It retains the card’s id and exact request, offers « Pas à pas », and creates no replacement paid card ([ChatView.vue:395](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:395)). Unknown outcomes and temporary selection failures keep waiting; probes confirmed this.
- **Round 2: canvas P2 OPEN as the acknowledged pre-existing follow-up**, excluded from this verdict. This diff does not worsen it.

The pre-send paths preserve the required ordering: ownership before document edits, `spent` saved before sending, and `sending` immediately before the paid mutation. Kept-request replay, legacy layer-price cards, server-supplied words and the D-005 client contract look consistent.

**P3 — regression coverage:** persist tests for late plan-response adoption and successful-job `GONE` recovery. The missing browser assertion for late adoption does **not** block this round: the guards are present and independently probed. The new save-takeover smoke alone does not cover those response guards.

Optional simplification: merge `choose` into its sole caller, `pickVersion`; the boolean-return wrapper is no longer needed.

Verified independently: TypeScript check, `git diff --check`, isolated ownership and reconciliation probes. No files changed.

Not rerun: Vitest, build or browser suites; those passes remain lead-reported. Real-model behavior remains unverified under T-CHAT-008.