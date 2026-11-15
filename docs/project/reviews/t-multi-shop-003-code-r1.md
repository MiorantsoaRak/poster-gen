**Verdict: APPROVE WITH FIXES.** Three P2 findings; no P1 found.

1. **P2 — The test does not enforce identical response bodies.** [`test_two_shops.py:57`](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_two_shops.py:57) keeps only status and error code. Differences in `field`, `current_revision`, message or additional data pass unnoticed. A read-only probe confirmed this. Compare the complete JSON after removing only `request_id`. The unused success-shape branch can then go.

2. **P2 — `/api/status` violates its unconditional non-operator 404 contract.** [`api.py:224`](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/api.py:224) returns `409 shop_changed` before `operator(request)` runs when the header is present without a session, or mismatches one. Ensure non-operators receive 404 before this guard; add header cases to the status tests. Removing the session requirement itself is intentional.

3. **P2 — The look-creation attempt misses creation ownership.** [`test_two_shops.py:172`](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_two_shops.py:172) supplies A’s style asset, which [`looks.py:80`](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/looks.py:80) rejects before checking the creation. Use B’s valid style asset when targeting A’s creation and the nonexistent creation. Separately test B’s creation referencing A’s style.

The other declared deviations are acceptable:

- `mutant_two_shops.py` does **not** match pytest’s configured default collection patterns. Its replacements affect process memory; it does not rewrite source.
- `OWN` is reasonable, and all five current entries have concrete checks.
- Header tests may live solely in this file. Header-bearing sign-out without a session returning 409 is consistent with the guard and the designed client recovery.
- `base_not_selected` and `input_immutable` legitimately prevent those operations before referenced-object lookup. Keep those restrictions.

The UUID and SHA controls have valid formats. Attempt entries use their declared method, and the path assertion prevents claiming a different template. However, [`test_two_shops.py:296`](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/tests/test_two_shops.py:296) covers **OpenAPI routes**, not every possible application route: `include_in_schema=False`, mounts, and unchecked additions to `OWN`/`EXEMPT` can escape it.

The per-shop spend query correctly separates job calls and reads, excluding evaluation calls. Service-wide cap callers and operator status retain the unfiltered total, including `provider_calls`. No existing ownership, bundle or idempotency rule was weakened; no later-task implementation leaked in.

Under the documented deployment, public Host routing and Caddy’s rewritten forwarding headers prevent the two operator checks being satisfied remotely. Uvicorn ignores forwarded-host headers; no bypass emerged from the inspected IPv6, port or absolute-target handling. Direct in-container loopback access remains available. This depends on the documented proxy configuration.

Remaining coverage gaps include foreign references in `keep_adjustments_of`, refinement styles, unsaved-copy documents and reads targeting B’s creation with A’s visual. Worker isolation is exercised for B’s scene, not every worker/recovery path. No WebSocket or streaming routes were found; the static mount serves the frontend build.

No files changed. Pytest, mutation, browser and deployment checks were not run because they write stores or require prohibited access; reported passes remain implementer evidence.