**Verdict: REJECT — four P1 defects block approval.**

The main code claims hold: A/B are stored headline fields; the server rejects an absent accent word and `brand_text` without a brand; changed included fields invalidate the old plan. `remakeIn` opens a copy without versions, so the format sentence is appropriate. The style branch would drop the model image and previous adjustments as advertised.

1. **P1 — `rows` does not protect an old tab from shared cards.**  
   [D-006:419](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/text-first-generation.md:419) gates new reads only. After a new bundle stores a settings card, an old tab can take ownership and load it: [ChatView.vue:437](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:437). Its converter preserves unknown settings, but its paid adapter call ignores them: [chat.ts:157](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/chat.ts:157), [ChatView.vue:297](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/ChatView.vue:297). A shared pending read has the same problem.  
   **Fix:** define compatibility for stored cards and pending reads, preserving exact replay and one unresolved request. Test takeover with the actual old bundle. Requirement line 105 cannot hold as written.

2. **P1 — `carries` checks listed changes but can lose preserved settings.**  
   [D-006:450](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/text-first-generation.md:450) checks only `settings`. Start with a drawn 37-character contact and no logo; ask to add the logo. The frontend now suppresses the unlisted contact because it subtracts the logo width: [App.vue:363](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:363). The logo check passes and an image can be paid without the preserved drawn contact.  
   Another case: removing the contact from a seal disables `sealOn`; the circle is excluded from planning, and selecting the resulting version disables its logo: [visuals.py:135](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/backend/src/affiche/posters/visuals.py:135), [App.vue:1333](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:1333).  
   **Fix:** check the complete intended result, including preserved identity and its representation, against the final request and plan. Refuse unsupported seal combinations before payment. Requirement line 99 is otherwise false.

3. **P1 — a style overwrites an explicitly requested colour.**  
   [D-006:447](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/text-first-generation.md:447) sets the colour before selecting the style. “Luxe sombre, avec Buds en rouge” becomes gold through [App.vue:110](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:110). `carries` then rejects a supported combined request. “Couleurs du produit” also overrides the headline colour through `sceneAccent`: [App.vue:55](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:55).  
   **Fix:** make an explicitly requested accent colour win in the outgoing headline while retaining the chosen style’s plan palette. Add both combined cases. Requirement line 99 cannot be met by the specified order.

4. **P1 — ownership is not checked after the new palette wait.**  
   [D-006:448](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/text-first-generation.md:448) waits like `start`, then changes style and potentially identity before the next `owned()` at step 8. A tab that lost ownership during that wait can therefore edit and queue document changes. The referenced wait has no ownership check: [App.vue:1393](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:1393).  
   **Fix:** check ownership immediately after the wait, before any mutation. Add a takeover test there. This violates ADR-097/098.

5. **P2 — identity recovery omits states the new path can create.**  
   [D-006:462](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/text-first-generation.md:462) excludes stale logos with `logo_box`. A hidden corner logo permits cropping; a mixed word/logo-on card can reveal it, then fail. Export is blocked, but the promised restore button is absent. Reversing booleans also does not restore geometry or a shape deleted by `placeLogo`.  
   **Fix:** reuse [restoreLogoRegion](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/frontend/src/App.vue:343) where appropriate and define restoration of the prior identity state. Requirement line 102 is incomplete.

6. **P2 — “contact on” conflates a visible layer with a drawn contact.**  
   [D-006:396](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/text-first-generation.md:396) counts either as shown; [the first identity-rule row](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/text-first-generation.md:404) then treats “on” as unchanged. Asking to draw an already visible contact therefore does not request `signature`.  
   **Fix:** distinguish visibility from the requested drawn representation. Requirement line 98 otherwise needs an unnecessary remove/add sequence.

**Tasks and simplification:** SET-001–003 are reasonably sized. Split SET-006 into free identity/recovery and paid identity/fresh-plan work. Complete their stub failure checks before paid evaluation. Do not advertise `rows: 2` in any runnable intermediate release before all its rows are supported. Keep format copying outside the approved implementation tasks; leave seal conversions in « Pas à pas ». The style branch can skip fetching the old plan it discards.

**Missing failure coverage:** mixed-bundle takeover; ownership loss during palette loading; identity restoration after failed saves, plan creation/revision and image jobs. Correct the reload test at [D-006:522](/home/miorantsoa/Documents/Miorantsoa/Vite/affiche-ia/docs/project/designs/text-first-generation.md:522): before `sending()` stores the scene request, recovery offers a new card, not « Reprendre ». Existing `commercial` screening and the unresolved invented-specifications issue must remain explicit regression constraints.

Not checked: execution, devices, network, production or paid behaviour; no files changed and `backend/.env` was not read.  
Risk: as drafted, an old tab can pay while ignoring the card’s settings.