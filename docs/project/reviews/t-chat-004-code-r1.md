**REJECT.** Two paths can issue distinct paid requests for one unresolved wish. Price changes also charge unnecessarily when the selected version uses an editable price layer.

| Divergence | Ruling |
|---|---|
| **1. Store `instruction_fr`** | **ACCEPT.** The compiled prompt and its hash are unchanged. New jobs’ `input_hash` changes because their payload gains metadata; existing jobs, spool hashes and idempotent replays remain unchanged. The provider receives the same explicit prompt/images/size arguments. Legacy null → « Scène ajustée » is sound. |
| **2. `headline_stale` → whole-scene card** | **ACCEPT.** Reusing the editor’s scene path preserves its settings. Keep this fallback distinguishable from a genuine price-only change when adding the free path below. |
| **3. `Envoyer` waits on `held`** | **PARTIAL.** Correct for the composer, but fresh paid-card buttons bypass `held`—finding 1. |
| **4. Thread-bound pending read, replaceable elsewhere** | **REJECT.** Association by `creation_id` is correct; replacement discards an unresolved paid identity—finding 2. |
| **5. Save selection before closing** | **ACCEPT.** The ordering is sound. In-memory checks confirmed repeated reconciliation during selection waits and selects once. |
| **6. Count from `/jobs`, omit line on failure** | **ACCEPT** source and degradation; fix the response-order race in finding 6. |
| **7. New final codes** | **ACCEPT** under current server semantics; reasoning below. Keeping asset failures transient is correct. |
| **8. Skip unsupported reads** | **ACCEPT.** No version or an images-only message on an existing poster correctly avoids a paid read. |

For **each new final code**, a late delivery of the **same stored request cannot become admissible**:

- `headline_stale`, `base_not_selected`, `logo_disc_uncovered`, `logo_placement_stale`, `format_missing`: correction requires changing the document, which advances its revision and invalidates that request.
- `scene_format_mismatch`, `invalid_reference`, `unsupported_visual`: the relevant plan format, input association or visual treatment is immutable.
- `invalid_plan`: compilation fails deterministically for the same request, document, plan and immutable look brief.

`asset_missing`, `asset_corrupt` and `unknown_asset` can be repaired without changing the document revision, so retaining those requests is necessary.

**Findings, by severity**

1. **P1 — Refusing an older result opens another paid card while a change remains unresolved.**  
   [ChatView.vue:413](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:413), [ChatView.vue:226](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:226).

   Start refinement X from a version still awaiting review; lose its response. Review and reject that older version. The versions watcher adds recap Y although X remains unresolved. Y’s button checks `locked`, not `held`, and `create()` admits it.

   I reproduced two distinct paid request keys. If delayed X completes during Y’s preparation, both jobs can pass sequentially: rejecting the base and completing a refinement do not advance the document revision.

   **Smallest fix:** prevent every fresh paid-card admission while another spent card remains unresolved. Preserve explicit replay of X; defer the replacement recap.

2. **P1 — Changing threads loses a pending read’s replay identity.**  
   [ChatView.vue:182](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:182), [ChatView.vue:218](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:218).

   Read X on poster A loses its answer. Open B and send a message: B replaces the global pending record. Return to A and press « Réessayer »: `resend()` creates a fresh key because the pending record belongs elsewhere. X may already have been billed.

   Reproduced in memory: A → B → retry A produced three reads, with different keys for A’s identical message.

   **Smallest fix:** with one pending slot, block new reads in other threads until that record settles. Never replace it merely because its `creation_id` differs.

3. **P1 — Layer-only price changes unnecessarily buy another image.**  
   [App.vue:1368](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:1368).

   `reprice()` always calls `createScene()`, including posters made in steps whose price remains an editable layer.

   **Smallest fix:** inspect the **selected** visual’s persisted `headline?.price_ar`. A present integer means the price is drawn; absence means it is not recorded as drawn. For a genuine price-only request in the latter case, call the existing `adapter.price(value)` (`changePrice()` + `flush()`), retain the approved visual, and use the normal final-render/download flow. Update the card’s redraw/cost wording accordingly. The `headline_stale` whole-scene fallback must still redraw.

4. **P2 — An obsolete lock acquisition can still save its queued price change.**  
   [App.vue:1369](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:1369).

   An earlier autosave is awaiting its response. A queues the new price and waits in `flush()`. B takes the lock and cancels the replacement card. When the earlier save resolves, A’s saver sends the queued price despite lost ownership. The later `/scenes` guard stops the image request, leaving the cancelled price under the old image.

   Reproduced using the actual `DraftSaver`: the price PUT occurred after ownership became false.

   **Smallest fix:** drain earlier saves, then validate the captured acquisition token before queuing/sending the price edit. Apply equivalent protection to restoration.

5. **P2 — « Remettre l’ancien prix » can restore a price the image never showed.**  
   [ChatView.vue:230](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:230).

   Image: **700,000**. A failed scene leaves the document at **600,000**. Request **650,000**, then fail again: `previous` becomes the document’s **600,000**. Restoration saves 600,000 while the image still shows 700,000; export remains blocked.

   **Smallest fix:** for drawn-price recovery, capture the selected image’s persisted `headline.price_ar`, rather than the possibly stale offer price.

6. **P2 — An older count response can hide an available version slot.**  
   [ChatView.vue:406](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:406).

   A count sees twelve occupied slots. The last job fails; a newer count reports one available slot. If the older response arrives last, it overwrites the count with zero and hides « Créer » until another refresh. Checking only the creation ID does not prevent this.

   **Smallest fix:** accept only the latest count request’s response. The current helper-only Vitest coverage misses this ordering.

I found no step-editor regression in `refineScene(key, sending)`: confirmation invokes it without arguments, preserving the editor’s key behavior. Modification labels and states follow the design. Keep the adapter and existing helpers; these fixes need no broader refactor.

Verified: `vue-tsc --noEmit`, diff whitespace checks, prompt/replay-input AST comparison against `410265a`, and targeted in-memory reproductions. Files remained unchanged.

Not rerun: pytest, Vitest, build or browser/device checks; no servers, network, paid calls, persistent-store writes or `backend/.env` access.  
Remaining risks: duplicate spending, unnecessary image charges, and incorrect price recovery.