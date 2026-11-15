**Verdict: REJECT.** The narrower settings promise is acceptable in principle; full restoration is not required by the amendment. One requirement gap and the selection ownership race still block approval.

**Previous findings**

| Finding | Status | Reason |
|---|---|---|
| Round 2 #1 — version settings | CLOSED | v3 explicitly withdraws full restoration; today’s `reprice` also uses current editor settings. |
| Round 2 #2 — legacy free prices | CLOSED | `effectOf` preserves layer-price/free, drawn-price/paid and `whole`/paid; captured requests remain unchanged. |
| Round 2 #3 — selection ownership | PARTIAL | Outer checks help, but selection can still mutate after losing ownership during its refresh. |
| Round 2 #4 — save before reading | CLOSED | Successful flush is required for a fresh read; kept bodies remain unchanged. |
| Round 2 #5 — restoration data/effect | CLOSED | Only stored values are restorable; returning to the image’s words is free. |
| Round 2 #6 — copied versions | CLOSED | Eligibility now matches the listing query. |
| Round 2 #7 — brand punctuation/accent | CLOSED | Cleanup and disclosure are specified and included in tests. |
| Round 1 #1 — legacy replay | CLOSED | Absent-field hashes, both normalization entries and free-price compatibility are covered. |
| Round 1 #4 — quoted/submitted words | PARTIAL | The headline-off refusal protects title/brand/subtitle; the price promise still needs qualification below. |
| Round 1 #5 — wrong restoration words | CLOSED | Restoration derives from stored image metadata. |
| Round 1 #7 — older-version targeting | CLOSED | Cards identify and select an eligible target. |
| Devil’s advocate #3 — partial saves | CLOSED | Persistent derived restoration replaces card-local rollback; unnecessary redraws are removed. |
| Devil’s advocate #5 — pending reads | CLOSED | Existing answers replay before absent-`visual_id` rejection. |
| Devil’s advocate #7 — extension claim | CLOSED | Type/setter/stub work is acknowledged; text retention is explicitly deferred. |
| Devil’s advocate #8 — brand strings | CLOSED | Separators, brackets and disappearing accent words are addressed. |

**Design defects**

- **P1 — Brand/subtitle support excludes versions without drawn words.** [Design:279](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/text-first-generation.md:279) returns `steps`, while the amendment says the chat changes all four fields and a word not drawn changes free ([requirements:82](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/requirements/text-first-generation.md:82), [requirements:84](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/requirements/text-first-generation.md:84)). As written, this criterion remains unmet. Either provide that behavior or obtain an explicit requirements exception; the stated settings limit does not supply one.

- **P2 — Round 2 #3 remains: ownership must be checked inside selection.** [Design:290](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/text-first-generation.md:290) checks around `select()`, but [App.vue:1377](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:1377) can await `refreshVisuals()`, then call `chooseVisual()` and save before returning. Pass the ownership callback into selection and check immediately before its mutations. The free `words()` path also needs a check after its awaited flush, before setters.

- **P2 — Setting four values does not guarantee four values in the image prompt.** [Design:299](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/text-first-generation.md:299) overstates the price guarantee. `headline.on` is insufficient: [headlineBody:303](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:303) sends the current `headline.price` switch, and [visuals.py:227](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/visuals.py:227) includes the amount in generation only when that switch is true. Either require the relevant price mode or say explicitly that the card fixes the amount while current settings determine whether it is drawn or layered. Full settings restoration is unnecessary.

- **P2 — One smoke expectation contradicts the adapter.** [Tests:352](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/text-first-generation.md:352) expects a brand-carrying request after texts are switched off; [design:291](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/text-first-generation.md:291) requires refusal without sending. Change that test to assert refusal and no spend.

**Other checks and implementation review**

The listing query is the correct eligibility rule: same shop, product input and size, including copies ([api.py:503](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/api.py:503)). The effect comparison correctly gives **scene** for a changed drawn price, **free** for a changed layer price, and **free** for restoring the image’s title. The no-drawn-words brand case is the requirement gap above.

During implementation review, verify ownership/thread identity again after `saved()` returns, legacy scene cards remain refinements, and captured requests bypass reconstruction. These are verification obligations, not additional architecture.

Keep the single normalizer and derived `stale` values; remove `previous` restoration branches as proposed. No complete settings snapshot or migration is needed.

Static review only: no files changed, tests or prohibited commands run, or `backend/.env` read. Runtime behavior remains unverified.