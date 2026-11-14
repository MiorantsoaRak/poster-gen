**APPROVE WITH FIXES**

No P0/P1 found. One introduced P2:

- **[frontend/src/ChatView.vue:175](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:175) — Reuse ignores unsent tray photos.** With `ask_photo` open, attach three product photos and one inspiration without pressing « Envoyer », then choose a suggestion. The recap shows only the suggested photo, but `sync()` includes the tray: submission contains **four product photos** and fails validation. Confirmed with an in-memory execution of the actual functions. **Smallest fix:** disable reuse while the tray is nonempty and enforce that guard inside `reuse()`; add a regression check.

The ownership and `original`-role filters look sound; reuse transfers no approval. Paid-request recovery preserves the request and idempotency key. Both new final codes satisfy ADR-097. The `perform` condition preserves step-editor behavior.

Verified independently: pinned plan/prompt hashes, 210 old/new brand-normalisation comparisons, and diff whitespace checks.

Not rerun: full suites, build or browser smokes. Upload/paid-request 401 recovery was code-traced only; no device, network, production or paid checks.