**Verdict: REJECT.**

1. **P1 — Ownership check happens after state changes.**  
   At [App.vue:1403](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:1403), `restoreHeadline()` can await a removed style’s fetch, then change `look`, `direction`, `keptLook` and `headline` before `owned()` runs. A takeover during that fetch violates ADR-097. Pass the ownership check into restoration and run it after the fetch, outside its catch, before any mutation.

2. **P2 — Unrelated saved typography can enter the request.**  
   [App.vue:132](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:132) leaves the current saved look active when the version has no `look_id`. `headlineBody()` then sends that unrelated look alongside the preserved plan. Clear the effective saved look when the version has none, without changing the editor’s fallback policy.

3. **P2 — Drawn contact alignment is not preserved.**  
   [App.vue:140](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:140) restores the contact switch but ignores `signature_align`. A version’s left-aligned contact can become centred through the device’s remembered setting. Carry the stored alignment into the chat scene request.

The read-only, in-memory probes reproduced all three. They also confirmed that `contact` and `brand_text` restore correctly when present or absent.

The other checks hold: revisions preserve direction and supplied style fields; failed plan fetches propagate; `planSignature = ''` prevents editor reuse. Brand addition and subtitle removal compile with unchanged regions. Prior changes to layer dimensions or included fields can still invalidate those regions and send the card to “Pas à pas”; the new smoke does not cover that recovery.

The texts-off guard still implements explicit D-005 step 2. Its rationale needs updating under ADR-100 before moving or deleting it. No other removable code stood out.

Not checked independently: full suites, build or browsers, including the pending editor smoke. The remaining risk is paid output changing typography or contact placement despite keeping the palette.