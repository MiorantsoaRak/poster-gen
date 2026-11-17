**REJECT.** Five P1 findings break the money/request guarantees. Review anchored to HEAD `d77557a`; no files changed.

1. **P1 — Cross-tab admission and storage updates are not atomic.** [admin.ts:183](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/admin/admin.ts:183)

   Two tabs can both read an empty map before either writes it. Both then keep and POST different requests; the last storage write replaces the other. Two offered grants get different generated references, so the server accepts both. Even requests for **different shops** can overwrite each other’s stored entries. `release()` has the same read-modify-write race.

   **Fix:** serialize admission and every map mutation across tabs, for example with one Web Lock around the shared map’s read/check/write. Release the lock before awaiting HTTP. Test simultaneous admission and simultaneous keep/release with controlled interleaving; the current cross-tab tests execute these operations sequentially.

2. **P1 — An unrelated storage event deletes a memory-only unresolved request.** [Admin.vue:213](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/admin/Admin.vue:213)

   If `setItem()` fails, the request correctly remains in memory. When another tab changes the pending map, `shared()` deletes every local request absent from storage—including that unanswered request. Its forms become available again without resolution or Discard.

   Also, `storable` checks only whether the storage object exists. Quota failure therefore produces no warning before POST; an epoch-dropped answer can leave the warning undisplayed indefinitely.

   **Fix:** track actual persistence success and preserve memory-only requests when reconciling storage. Apply removals only to the corresponding previously persisted request. Show the storage limitation immediately when saving fails.

3. **P1 — `refKey` can falsely resolve an unrelated payment as “as sent.”** [admin.ts:89](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/admin/admin.ts:89)

   The claimed one-way limitation is false across Unicode versions. Here, Node lowercases **U+1C89 and U+1C8A** identically; the backend’s Python **3.12.16 / Unicode 15** casefold treats them as distinct. With otherwise equal figures, `inHistory()` selects the unrelated line and `recorded()` says “as sent”; `resolve()` clears the real request.

   **Fix:** let the server provide/compare its canonical reference key, or conservatively restrict automatic history resolution to equivalences whose semantics are guaranteed across both runtimes. Keep other requests for resend. Add this exact counterexample.

4. **P1 — The same payment can generate two different concession references.** [admin.ts:80](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/admin/admin.ts:80)

   These valid payment spellings have the same server key:

   - `"A".repeat(90) + " XYYYYY"`
   - `"A".repeat(90) + "  XYYYYY"`

   Truncating before collapsing spaces produces different `-geste` keys. Repeat the refused move using the second spelling, and the destination can receive another offered grant.

   **Fix:** derive the bounded concession reference from the server’s canonical payment identity, before truncation—preferably a stable payment-line identifier. This needs a design amendment: the current truncation recipe itself permits the defect.

5. **P1 — Parseable but unusable success JSON clears the request before interpretation.** [admin.ts:218](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/admin/admin.ts:218)

   A `201` containing `{}` makes `settle()` release both copies. Then `answered()` throws while reading `answer.balance`. The operator gets no usable answer and the request is forgotten. Existing unreadable-response coverage tests JSON parsing failure, not a malformed JSON object.

   **Fix:** validate each money response’s required fields before releasing the request. Treat an invalid response shape as uncertain and retain the frozen request. Test malformed grant, correction and move responses.

6. **P2 — Loading the matching older history page does not resolve the request.** [Admin.vue:142](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/admin/Admin.vue:142)

   Only the first page invokes `resolve()`. A matching line revealed by “Older” remains visibly unresolved and continues blocking money forms.

   **Fix:** resolve against newly appended history items too, preserving the existing in-flight guard. Test a matching line beyond the first 50 items.

7. **P2 — Payments’ guard does not identify the last request.** [Payments.vue:21](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/admin/Payments.vue:21)

   Two reads for the same period can finish backwards, letting an older total overwrite the newer total. A stale failure can also overwrite the current message because the catch has no guard.

   **Fix:** use an incrementing read identifier for success and displayed-error assignment. Continue processing authentication failures even when their display result is stale.

The eight deviations:

| # | Ruling |
|---|---|
| 1 | **Acceptable.** Source history cannot establish a move’s destination; resend obtains authoritative `moved_to`. |
| 2 | **Acceptable.** Naming the actual cause preserves the uncertainty warning. |
| 3 | **Acceptable.** Both shops and the reference identify the operation; the current move contract supplies no figures beforehand. |
| 4 | **Acceptable.** Labelled native selects support keyboard operation; Bought still requires amount and method. |
| 5 | **Acceptable, but fragile.** The backend returns generic `operator_refused` plus prose; there is no safer structured reason already present. Gate the match on that code/status. A dedicated reason would remove the coupling. |
| 6 | **Acceptable.** Retaining the draft/reference avoids unnecessary new identities. |
| 7 | **Acceptable.** The headroom response supplies no “since” date. |
| 8 | **Defect.** See finding 3. |

Other checks: ordinary JSON save/reload preserves property order, so `same()` has no normal reload-order failure. History distinguishes kinds, and its job branch reflects server repayment deduplication; different figures produce the mismatch message. Money results are scoped to their request’s shop.

A crafted valid storage entry **can** become a resendable request without a prior confirmation. That requires storage modification or same-origin execution; such execution can already call these endpoints directly. The path check prevents arbitrary endpoint selection. Stronger body validation would improve corruption handling, but cannot establish confirmation provenance.

No new XSS sink or stored secret found. Number bounds/sign handling agree with the backend; negative amount fixes that exhaust the payment are properly refused server-side. Empty payment periods display zero. The README’s reload-persistence claim currently overstates reliability because of findings 1–2.

Checks performed: source/design/backend tracing, `git diff --check`, and deterministic in-memory probes confirming the storage interleavings, memory loss, Unicode mismatch, concession divergence and malformed-success release.

Not rerun: suites, builds, browser/device smokes or shop-file hashes; your reported results remain the validation evidence. No production, deployment, store-writing commands or prohibited paths were accessed.