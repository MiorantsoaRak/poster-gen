**Verdict: REJECT.** v2 closes several round-1 findings, but the promised request settings and legacy free-price behavior still have P1 defects.

**Previous findings**

| Finding | Status | Reason |
|---|---|---|
| Round 1 #1 — legacy replay | PARTIAL | Absent-field hashing and both converter entries are covered; legacy price cards gain the wrong cost. |
| Round 1 #2 — brand request returns `same` | CLOSED | Brand separation now precedes equality checking whenever brand is returned. |
| Round 1 #3 — invented specifications | CLOSED | The amended requirement explicitly limits the word guard’s guarantee; recombinations remain subject to owner confirmation. |
| Round 1 #4 — quoted versus submitted request | OPEN | `restoreHeadline()` does not restore all settings used by generation. |
| Round 1 #5 — restore wrong words | PARTIAL | Version-derived values fix drawn fields; stale flags also cover cases with no stored restoration value. |
| Round 1 #6 — title validation | CLOSED | Drawn and layer titles now use their respective limits. |
| Round 1 #7 — older version targeting | PARTIAL | Target selection is specified, but the ownership rule conflicts with copied posters’ available versions. |
| Devil’s advocate #1a — instruction screening order | CLOSED | Discarding the instruction first removes the false refusal. |
| Devil’s advocate #1b — existing brand returns `same` | CLOSED | Explicitly covered before equality checking. |
| Devil’s advocate #2 — refs as current words | CLOSED | The server reads version metadata and the document. |
| Devil’s advocate #3 — partially saved change | PARTIAL | Derived restoration improves recovery; missing restoration values and unnecessary redraws remain. |
| Devil’s advocate #4 — empty-string removal | CLOSED | Explicit `remove` list. |
| Devil’s advocate #5 — old pending read/hash | PARTIAL | Hash preservation and both card entries are covered; legacy free-price semantics are lost. |
| Devil’s advocate #6 — actionable word refusal | CLOSED | The refusal names the word; excluding history follows the explicitly stated current-message guarantee. |
| Devil’s advocate #7 — field-table claim/process | PARTIAL | Labels are acknowledged, but stub/type changes remain outside the claimed extension cost; text retention is explicitly deferred. |
| Devil’s advocate #8 — brand string handling | PARTIAL | Embedded-token refusal is specified; separator cleanup and the disappearing accent remain unspecified. |

**Actionable defects**

1. **P1 — “The version’s settings plus the card” is false.**  
   [Design:288](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/text-first-generation.md:288) relies on [App.vue:129](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:129), which restores brand, subtitle, accent and price mode, but:
   - does not restore `brand_text`, contact mode or contact alignment;
   - writes `signature`, while the request actually depends on `headline.contact`;
   - leaves the current look when the version has no `look_id`;
   - does not restore the style reference; selection only partly restores logo/seal geometry.

   [headlineBody:303](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:303) and [generateScene:1087](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:1087) therefore send mutable settings absent from the card. Define complete restoration, including absent values and lookup failures, before claiming exact preservation.

2. **P1 — Legacy layer-price cards become paid redraws.**  
   [Design:283](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/text-first-generation.md:283) converts every old price card to `effect: "scene"` and removes `freePrice`. Today [chat.ts:147](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/chat.ts:147) makes those cards free when the selected visual has no drawn price. Preserve that classification using the resolved target version, while retaining `whole` and any already captured request. Otherwise compatibility weakens ADR-098.

3. **P2 — Selection mutates the document before ownership is checked.**  
   [Design:287](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/text-first-generation.md:287) places `owned()` after selection and restoration. Existing [select:1377](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:1377) can await a refresh, then queue and save selection, crop, visibility and logo changes without checking the chat token. A tab that lost the lock can therefore modify the document before stopping. Check ownership immediately before these new mutations and after awaited preparation; keep the final `sending` check.

4. **P2 — Server-read words need a client save barrier.**  
   [Design:262](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/text-first-generation.md:262) reads the saved document, but specifies no `flush()` before the read. [ChatView.vue:209](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:209) sends directly; switching views does not flush, and [autosave.ts:22](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/autosave.ts:22) delays saving. Pending or failed step-editor changes can yield a paid interpretation against obsolete words. Flush successfully before admitting a fresh read; preserve existing pending bodies unchanged.

5. **P2 — Stale flags are insufficient restoration data.**  
   [App.vue:731](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:731) and [App.vue:733](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:733) also report hidden title/price layers when no baked value exists. In that case [Design:296](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/text-first-generation.md:296) cannot truthfully name “the image’s words” or restore them through document setters. Offer restoration only for existing baked values; handle hidden layers separately. Also, returning document words to exactly the baked words needs no new scene, whereas the current effect rule still charges.

6. **P2 — The creation-membership rule rejects valid copied-poster versions.**  
   [Design:262](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/text-first-generation.md:262) refers to the visual’s `creation_id`, but [poster_visuals:21](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/migrations/versions/0007_poster_visuals.py:21) has none. Its job provides one. However, [api.py:503](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/api.py:503) deliberately lists versions across creations sharing the product input and size. Strict job-creation equality would reject versions already selectable on a copy. Match the existing eligibility rules explicitly.

7. **P2 — Brand separation leaves punctuation debris.**  
   Removing space-delimited brand tokens in [Design:268](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/text-first-generation.md:268) turns `Sony – WH-CH720N` into `– WH-CH720N`. Specify removal of adjacent separators and empty brackets. Also disclose or preserve an accent attached to the removed brand: [App.vue:300](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:300) otherwise silently drops it.

**Other claims checked**

- `baked_headline()` reads the job’s stored headline; refinements copy their base’s headline ([visuals.py:299](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/visuals.py:299)). `price_ar` and `brand_in_title` are conditional, not guaranteed keys.
- Selection permits unchecked and rejected visuals without changing their review status. Export still requires approval. A missing visual currently produces no selection error.
- `exclude_if` is compatible with `canonical()`’s `model_dump`; the proposed omission preserves old hashes. Check an existing ledger key **before** rejecting absent `visual_id`, then reject new admissions before insertion.
- An unknown 409 settles the old client’s pending read without retry or payment ([chat.ts:112](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/chat.ts:112)).
- Before `sending`, reload leaves a spent card with no paid request; existing reconciliation treats it as unsent. Document edits may already survive, while restored refs do not. After `sending`, the exact body/revision replay remains sound. Replacement cards must retain the complete target and change fields.

R-004’s truthful single card, cost, any-version and compatibility criteria remain unmet. Add tests for all omitted settings, legacy layer-price cards, copied posters, lock takeover during selection, unsaved document reads, and stale hidden layers.

Keep the new-poster reader unchanged. Remove `previous` and its restoration branches as proposed; qualify the “one row” extension claim.

Static review only; no files changed, tests or external commands run, or `backend/.env` read. Remaining risks are unlisted changes in paid images and charging for formerly free edits.