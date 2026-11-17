What this change does: adds the operator’s money forms, retained requests, history and payments screen. **Verdict: REJECT** — three P1 paths remain.

| Round-1 finding | Ruling |
|---|---|
| 1. Cross-tab admission/storage | **OPEN**, narrowed to request loss described below. |
| 2. Memory-only request deleted | **PARTIAL** — protected initially, but a blocked retry removes protection. |
| 3. `refKey` false match | **CLOSED** — identical text or ASCII-only equivalence avoids the Unicode-version false match. |
| 4. Two concession references | **PARTIAL** — ordinary internal spaces fixed; trailing Python whitespace still permits two grants. |
| 5. Malformed 2xx released | **CLOSED** — grant, correction and move shapes are checked before release; invalid answers remain kept. |
| 6. Older history page | **CLOSED** — appended items now invoke `resolve()`, retaining the in-flight guard. |
| 7. Payments read guard | **CLOSED** — latest read wins for success and displayed failure; stale authentication failures still reach `failure()`. |

Deviation 5 is acceptable with the added `operator_refused` gate.

**Must fix**

1. **P1 — A response in one tab can erase another tab’s unanswered request.** [admin.ts:195](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/admin/admin.ts:195), [Admin.vue:218](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/admin/Admin.vue:218)

   The admission argument is reasonable: two separately confirmed gifts are two intended grants. However, two near-simultaneous confirmations are unnecessary for the storage failure:

   - Tab A has a request awaiting its answer.
   - The operator confirms request B for another shop while A’s answer arrives.
   - `release(A)` reads `{A}`; `keep(B)` writes `{A,B}`; `release(A)` then removes the storage key using its earlier snapshot.
   - B receives the storage event. `shared()` deletes B from memory too.

   Thus **“it stays in that tab’s memory” is false**. If B committed but its answer and subsequent history read fail, reopening the shop creates a fresh offered reference without a kept-request warning. Repeating the intended gift can then credit it twice.

   **Fix:** serialize complete shared-map mutations, revisiting the no-lock decision, or persist requests separately so releasing A cannot erase B. This cannot be accepted solely as a microsecond admission limit.

2. **P1 — A `busy` retry drops protection while its memory-only request still lives.** [Admin.vue:322](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/admin/Admin.vue:322)

   This requires no simultaneous operations:

   - A’s storage write fails; its unanswered request remains in memory with `memoryOnly`.
   - Another tab successfully keeps B for that shop. A correctly ignores B’s storage event.
   - A presses **Send again**. `send()` removes its marker, then `keep()` returns `busy` because storage contains B.
   - A’s request still exists, but its marker is gone. When B resolves, `shared()` deletes A.

   **Fix:** preserve the marker on `busy`. Change persistence bookkeeping only when admission succeeds: `'stored'` removes the marker; `'memory'` adds it; `'busy'` leaves it unchanged. Add a regression covering this sequence.

   I found this premature removal, rather than a normal path where the marker outlives a released request.

3. **P1 — One payment still produces two valid concession keys.** [admin.ts:84](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/admin/admin.ts:84)

   The short-reference branch returns raw `ref`, despite having computed collapsed text. These payment spellings reach the same server payment:

   ```text
   "MV-123"
   "MV-123\u0085"
   ```

   U+0085 is whitespace to Python but survives JavaScript `.trim()`. Both spellings pass the frontend field constraints. Their concessions become:

   ```text
   "MV-123-geste"        → server key "mv-123-geste"
   "MV-123\u0085-geste"  → server key "mv-123 -geste"
   ```

   Both concession references are valid and distinct. Repeat the refused move with the pasted trailing character and confirm its prefilled concession: the destination can receive a second offered grant for the same payment.

   **Fix:** append `-geste` to the collapsed text in both branches. Add this exact regression.

**Should fix**

4. **P2 — The same branch can generate an oversized concession.** [admin.ts:84](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/admin/admin.ts:84)

   `"A".repeat(90) + "  XYZ"` is a valid 95-character payment reference. Its collapsed length is 94, so the function returns the original text plus the suffix: **101 characters**, rejected by the API.

   **Fix:** always return `chars.slice(0, 94).join('') + '-geste'`. This also closes finding 3.

The **casefold-at-cut concern alone did not establish a double grant**. For example, equivalent payment spellings `A×93 + ßX` and `A×93 + ssX` produce different concessions, but the former’s folded concession key has 101 characters and the backend refuses it. That remains a concession rejection limitation, rather than two accepted grants.

Checked through source/design/backend tracing, `git diff --check`, and read-only in-memory probes using the actual functions. The probes reproduced findings 1–4 and verified the closed fixes.

Not rerun: suites, builds, shop hashes or browser smokes; smokes remain unverified. No files modified, prohibited paths accessed, or device/production/deployment/store-writing commands run.