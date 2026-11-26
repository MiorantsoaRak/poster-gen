# Creation UX, motion and poster diversity — research, 2026-11-26

Status: research direction accepted by the owner on 2026-11-26; technical design and implementation remain pending. The owner requested no application code edits. The subsequent explicit no-invented-logo requirement is approved as R-FREE-07; other detailed requirements/design approvals remain pending. Source reviewed: `4c2a5e1`. Research task: T-UX-RESEARCH-20261126.

## Recommendation

Make **Libre the main creation experience**. Keep **Pas à pas as optional help preparing the same kind of request**, with all visible poster content drawn by the image model. Retire **Message as a separate entry for new creations**, after useful kit/reuse features reach Libre. Preserve access to existing guided posters and their confirmed files.

Libre is already enough for expressive generation, several independently priced products and instruction-based corrections. It is **not yet a complete replacement** for the other workflows: it lacks kit integration, later attachments, reusable saved models in its composer, and a way to resume an earlier version. A completely empty prompt box would also make novice sellers do the art-direction work.

A single underlying generation experience with two ways to express a request is the target. This is a product recommendation, not permission to redesign the stored document contracts in this round.

## Evidence and limits

- Inspected current `FreeCreation.vue`, the editor and creation navigation in `App.vue`, `style.css`, `free_creation.py`, relevant generation prompt code in `plans.py`, gateway/configuration and existing browser checks.
- Built the actual frontend successfully; reran `free_creation_browser.py` on isolated stub data at 1366/390 px. Passed generation/correction, reopening, confirmation/download identity, simulated Facebook flow, no-credit behavior and refused-image credit return. Stub images prove UI behavior, not visual quality.
- Ran `design_capture.py ux-research-2026-11-26` at 360/768/1440 px in both themes. It produced the client creation/editor/kit/publishing captures, then exited 143 after `admin-signin`; the full capture suite did NOT finish. Do not report a full-suite pass. Relevant captures exist in `outputs/design-capture/ux-research-2026-11-26/`; the administrator pages are outside this review.
- Visually inspected current free mobile composer, guided mobile/desktop editor, and historical real-model images (`outputs/free-creation/comparison.jpg`, `outputs/user-walk-2/07-pack-reference-image-sent.png`, `outputs/degradation-trial/sheet-titles.jpg`). Also inspected current 360 px Pas à pas entry and Message empty state: the form exposes a default “Variante confirmée” and photo-verification checkbox; Message already shows style/title controls before the first request. These belong in optional help, not every user’s starting composer.
- Historical paid evidence: reference composition and individual-price correction succeeded in selected examples. The previous 27-image degradation trial found that a first-image quality anchor helped surfaces but could interfere with a requested bolder title. Those are prior experiments, not new successes in this session.
- New paid-trial results are recorded in the addendum below. User explicitly allowed loading the development `.env`; no secret contents are printed. All new trials use an isolated research database, not the deployed shop.
- No user interview, physical phone test, screen-reader audit, frame-time profiling or statistically representative model evaluation was performed. No claim of guaranteed text/logo fidelity, market conversion uplift or uniqueness.

## Keep / change / remove

| Area | What works | Change | Remove from the main workflow |
| --- | --- | --- | --- |
| Libre | Original wording goes to image model; optional source photos/reference; one-credit correction; shared review/download/publication infrastructure | Make default; integrate kit and saved references; add visible starting suggestions; enable recovery from an earlier version and later attachments | Three-way generation selector; technical fallback-style switch from the composer |
| Message | Helps a seller supply one product, one price and verified identity; useful recap and kit reuse | Carry the useful assistance into optional guided input; keep legacy posters reopenable | Separate restrictive chat for new creations; silent instruction loss or reinterpretation |
| Pas à pas | Explicit facts, visual choices, source comparison; useful for people who dislike prompting | Reduce to content → visual direction → generate/review; correction uses ordinary words and the image model | Logo/contact/shop-name position, size, font and layer controls; drawn-vs-layer switches for new fully generated posters; per-word accent and texture machinery in the main flow |
| Kit | Saved identity, lines and personal models reduce repeated work | One obvious inclusion summary before generating; personal references usable from Libre | Repeatedly retyping shop identity; implied automatic inclusion when it is actually absent |
| Review | Confirmed downloadable artifact, source photos, visible cost and failure feedback | Poster first; zoom; current exact words/amounts beside it; retain original history separately | Treating all past contradictory instructions as the current specification |
| Styles | Custom references already exist; existing defaults offer a starting point | Personal reference first, curated inspiration second, free description always available | Treating three presets as the limit of creative choice |

Do not delete the underlying guided endpoints/layer renderer as a cosmetic simplification. Existing documents and exports depend on them. Retiring an entry point and deleting its storage/rendering behavior are separate decisions.

## Specific UX findings

| Priority | Finding and evidence | Proposal |
| --- | --- | --- |
| P0 | Three visually equal choices ask sellers to understand the app's generation architecture before starting. At phone widths this consumes most of the header (`App.vue` creation switch; current free screenshot). | One “Créer une affiche” entry. “Me guider” is secondary help; existing-document navigation follows the document's capabilities. |
| P0 | Free creation never includes the shop profile automatically; source contract has photos/reference/words but no kit fields. Users familiar with Message can assume the logo/contact will appear. | Visible “Identité de la boutique” summary with inclusion choice. Name/contact/logo remain editable in the kit, then are drawn by the model on the poster. Snapshot the chosen facts per request. |
| P0 | The free composer loses its attachment picker after creation (`FreeCreation.vue`: `v-if="!id"`). A seller cannot add a forgotten logo or replace a bad photo. | Permit attachments on corrections, with explicit roles and replacement semantics. This needs an approved contract change, not only a button. |
| P0 | “Modifications” lets the seller inspect an old version, but corrections still act on the current document. Older versions cannot be selected for confirmation (`FreeCreation.vue` current/shown/reviewed). | Show which version a correction targets. Offer “Repartir de cette version” and deliberate restoration without silently changing the confirmed file. |
| P1 | Free review lists every successful request (`asked()`), including superseded prices. “85 000 → 95 000” should not look like two simultaneously required amounts. | Keep request history, but show the latest expected facts separately. Any AI extraction assists review; it must not quietly rewrite the user's request or certify correctness. |
| P1 | The free empty state explains the tool but provides no concrete starting request. Upload/reference roles are tucked into thumbnail controls. | A short editable example and three starting actions: “Ajouter mes produits”, “Utiliser une affiche modèle”, “Me guider”. Each opens input, never starts a paid generation automatically. |
| P1 | “Style de base pour ce que vous ne précisez pas” is internal prompt behavior exposed as a prominent switch. | Keep quality defaults (spacing, contrast, legibility); let explicit words/reference override them. Remove the main switch or tuck it into secondary options only if users demonstrably need it. |
| P1 | On mobile the guided result is small while controls below remain extensive; the Textes panel alone includes brand, subtitle, word accent, accent palette and rendering toggles. | After generation, make the poster and “Corriger / Télécharger / Publier” the primary workspace. Content fields are a preparation step or deliberate edit, not a permanent settings wall. |
| P1 | The guided prompt says electronics-shop hero visual and defaults to studio gradients, sweeping bands and a floating product (`plans.py:413,455–480`). | General business-neutral quality baseline; use seller intent/reference for composition. Keep electronics-specific art direction as an optional suggestion. |
| P1 | Free title metadata is derived from the request; long requests can be poor library names. | Allow a short human-friendly library title independent from text drawn on the poster. Do not spend an image credit just to rename a library item. |
| P2 | Free thread scrolls to the bottom whenever turn count or job status changes (`FreeCreation.vue:179`). | Follow updates only when already near the bottom; otherwise show “Nouvelle version prête”. Verify focus and scroll during image loading. |
| P2 | “Libre” can be ambiguous next to credit-based pricing, and the three choices distinguish implementation more than user goals. | Prefer the main action “Créer”; reserve “Libre” for explanation if needed. Keep “1 crédit” beside the generation action and before charge. |

### Simplified Pas à pas

Keep this as assistance, not another editor competing with Libre:

1. **Votre contenu**: photos and exact names/prices/offer wording. Start with one item; allow additional items deliberately. Price optional for service/event announcements. Show the selected kit facts compactly.
2. **Votre direction**: upload a preferred poster, select a personal saved reference, pick inspiration, or describe a look. Optional supplementary words remain unrestricted creative input.
3. **Générer et vérifier**: one cost, one result, corrections in words, source comparison, download/publish.

The owner requested that logo, contact and name cease to be editable poster layers. Agree: remove their positioning/font/size controls from new creation. Keep the exact underlying details editable in the kit and, when needed, as content for a new generated version. Interpret “name” conservatively to cover shop-name visual controls as well as title styling; product-name content is still needed. Do not remove the ability to correct a spelling mistake.

**Tradeoff:** a fully generated poster is visually coherent but changing a phone number, name, logo or price needs another generation and review. The logo is a model-drawn approximation, not a guaranteed identical embedding of the original file. This matches the requested direction; document the cost and fidelity tradeoff plainly.

## References and creative diversity

### The repeated style has two causes

The front end supplies three visual starting points (`App.vue:94–99`): Studio clair, Aux couleurs du produit, Luxe sombre, plus free description. Separately, the guided scene compiler supplies a repeated hero/studio composition. Merely adding more colors or more preset names will retain much of the same silhouette.

Libre's fallback is much less prescriptive: focal point, spacing, contrast, lettering (`free_creation.py:prompt`). That is a useful quality baseline. Do not replace it with a long universal “professional” prompt that imposes a single visual treatment on restaurants, beauty salons, fashion sellers and electronics shops.

### Make the preferred-picture workflow first class

- Clearly separate **product photo**, **shop logo**, and **visual reference**. They carry different authority. A reference's price, competitor logo, contact and product do not become facts about the seller.
- Offer two understandable reference intents, initially as simple choices or words: **“Garder la disposition”** and **“S’inspirer du style”**. Current free prompting asks to match composition, framing, typography, spacing AND palette at once; it cannot express the distinction in its controls.
- Always send the actual reference when establishing the visual direction, not just a textual summary. Keep descriptions for browsing/search, not as substitutes for pixels.
- Let explicit user instructions override the reference; use the reference for remaining visual choices. No numerical “reference strength” slider unless the actual provider offers a meaningful, tested control.
- Save a liked result as a personal reference and reuse it from Libre. Offer “Même style, autre composition” as a deliberate new generation. Do not send every historical reference on every correction: competing references can reintroduce old text/layout.
- Reference consistency within one brand is desirable. Diversity between shops should come from personal references and intentional choices. Nobody can promise globally unique posters from shared prompts.
- For dense references, explain if three input photos cannot express the desired number of products. Do not silently duplicate products or treat the reference's stock photography as seller inventory.

Adobe documents separate style and composition references; this validates the distinction as a usable pattern, not proof that our provider implements Adobe's strength slider. [Style reference](https://helpx.adobe.com/firefly/web/work-with-images/generate-images/reference-images-for-styling.html), [composition reference](https://helpx.adobe.com/in/firefly/web/work-with-images/generate-images/match-image-composition-to-reference-image.html).

### More choice without a larger settings panel

Provide a modest inspiration gallery with visibly different composition families: editorial asymmetry, product cards/catalogue, lifestyle setting, bold typographic offer, minimal luxury, food/menu, event/service announcement. These are proposed examples, not rigid layouts or approved scope. Personal references should outrank the gallery.

“Proposer une autre direction” should deliberately change layout/typographic character/setting while preserving exact commercial facts. Avoid randomizing everything automatically. Generating three real alternatives costs three images; label that and make it optional. Start with one output, then a requested alternative.

Do not automatically add Madagascar flags, baobabs, local stereotypes, discounts, delivery claims or payment logos. Local relevance comes first from real seller products, prices in Ar, contact details, audience and supplied words.

## What “improve the model” should mean here

There are three different interventions:

1. **Improve application conditioning first:** clearer attachment roles, user instructions taking priority, fewer contradictory house rules, personal references, current facts and better edit recovery. No retraining required.
2. **Evaluate providers/settings:** compare the current deployed image model with a supported alternative on identical fixtures. Assess price/name pairing, accents, phone digits, real product features, logo reproduction, reference obedience, 3–5 edits and small-screen readability. Vendor claims are candidates for testing, not a ranking.
3. **Training/custom models only if justified later:** a reference upload does not train a model. Do not promise a self-improving proprietary model or automatic learning from customers' uploads. Save chosen styles and explicit preference feedback first.

The existing gateway recognizes GPT Image 2 / 2.5 Sunburst / 2.5 Flare in its rate cards. A new model requires capability and pricing validation, not just changing a string. Google's official documentation describes reference-based generation and conversational edits; it is an evaluation candidate, not a recommended provider migration from this research. [Google image generation](https://ai.google.dev/gemini-api/docs/image-generation).

OpenAI documents remaining limitations in precise text, recurring brand elements and exact composition. Therefore “everything through the image model” improves visual integration but does not guarantee logo/price accuracy. Preserve original files and human review. [OpenAI image generation limitations](https://developers.openai.com/api/docs/guides/image-generation).

### Professional-quality evaluation proposal

Build a small evaluation set from consenting businesses: electronics single product, three-item offers, food/menu, salon/service, clothing and an event announcement. Begin with 12 briefs, two distinct directions each and repeated outputs for the difficult cases; extend only if the result changes a decision. This is a proposed follow-up, not a completed benchmark.

Record input photos, exact expected text, reference, prompt/model/settings, cost, latency and corrections. Review blind to the model name. Reject an otherwise attractive result for a wrong price, invented guarantee, incorrect phone digit, swapped product labels or materially changed product. Separately score hierarchy, spacing, typography, reference adherence and legibility at a roughly 360 px feed width. Count accepted posters and total cost per accepted poster, not only cost per generated image. A failed exactness check must not be averaged away by a high aesthetics score.

Optional OCR/vision can flag suspect text or price pairing, but cannot certify correctness, and should not silently rewrite either the poster or user input. Test its false positives before inserting another mandatory gate.

## UI polish and animation review

Keep the current Doka identity, light/dark support, quick press feedback and visible loading/failure states. Spend visual space on the poster and a clear next action. The research does not justify a wholesale reskin or a new animation library.

| Before | After | Why |
| --- | --- | --- |
| Switch knob animates `inset`, `width`, `height` (`style.css:149–151`) | Fixed geometry with transform-based travel/scale, or remove the size change | Avoid layout-affecting animation; no measured frame-drop claim |
| Selected chips/layer buttons morph their border radius (`style.css:165,504`) | Stable shape with immediate selection and restrained color feedback | Repeated utility interaction gains little from shape morphing; reduces paint work |
| Free thread unconditionally scrolls on status changes (`FreeCreation.vue:179`) | Respect the reader's scroll position, offer a new-result affordance | Avoid pulling someone away from an earlier instruction or comparison |
| Reduced-motion mode slows some spinners but leaves them rotating (`style.css:1035–1046`) | Static progress/status for users requesting reduced motion, with textual state updates | Greater comfort; do not infer a blanket WCAG AA failure from this source review |
| Version arrival/review relies largely on immediate layout replacement | Optional brief opacity/transform reveal after image decoding, with space reserved | Helps connect a completed generation to its result without a layout jump |
| Global smooth scrolling (`style.css:58`) | Keep intentional navigation smooth only where useful; immediate focus/keyboard positioning | Predictable keyboard and correction workflow |

**Verdict: Block motion-polish sign-off pending the switch geometry simplification.** This is the review skill's craft verdict, not a security/release block or a measured performance regression. Existing 160 ms transform press feedback is good; the mobile drawer's 280 ms transform is within the reviewed UI budget. Keep those rather than introducing springs everywhere.

For proposed motion use the existing CSS approach: press feedback 100–160 ms; small popovers 125–200 ms; drawer/review transitions around 200–280 ms; strong ease-out such as the already used `cubic-bezier(.23,1,.32,1)`. Retargetable transitions for controls, transform/opacity for movement. Disable movement in reduced-motion mode. Never animate each text keystroke, number, image pixel or streaming instruction. No decorative infinite gradients, artificial percentage counter, staged fake “AI thinking”, confetti or autoplay carousel.

Current captures cannot establish motion smoothness, interruption behavior or real-phone GPU performance. Verify on a midrange Android phone, keyboard open, with network delay and repeated taps. Review reduced-motion behavior separately. W3C's interaction-animation criterion is AAA and supports respecting the user's motion preference; it does not prescribe our timing values. [W3C guidance](https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions).

## Madagascar and novice sellers

A prompt-only UI demands that the user articulate layout, hierarchy and brand details. Optional structured help and editable examples reduce that demand without rejecting creative words. NN/g specifically discusses combining graphical controls with prompts and using contextual suggestions. [NN/g research guide](https://www.nngroup.com/articles/designing-ai-study-guide/).

Keep French UI and user-supplied exact wording. Mixed French/Malagasy copy deserves a dedicated text-rendering evaluation before claiming language support. Keep Ar explicit and phone digits intact. Target service businesses as well as products when defining future requirements; the current electronics assumptions do not cover every business.

Test upload retry, background/foreground return, keyboard obstruction, generation reconnection, readable preview and download on sellers' actual phones. A successful emulated 390 px test does not establish network resilience. DataReportal's latest available country report labels its October 2026 observations “Digital 2027” and reports 4.55 million social-media identities; these are not unique customers or a measure of our users' connection quality. Use actual pilot observations for UX prioritization. [Country context](https://datareportal.com/reports/digital-2027-madagascar).

## Proposed order, without implementation approval

1. Agree on the product direction: Libre primary, optional simplified Pas à pas, guided Message retired for new work; legacy posters preserved.
2. Requirements for kit/reference use, exact content, version recovery and fully generated identity. Include the regeneration cost and fidelity tradeoff.
3. Design the shared creation experience and legacy compatibility; then create independently verifiable implementation tasks.
4. Implement the smallest complete slice, evaluate with sellers, then add additional reference/inspiration choice and narrowly targeted motion polish.
5. Reconsider a provider upgrade only if measured deficiencies survive the prompt/reference fixes.

Do not start by adding dozens of presets, a public template marketplace, fine-tuning, a layer-extraction editor or bulk multi-variant generation. None is required to resolve the current workflow confusion.

## New paid trials — 2026-11-26

The isolated trial harness and provider ledger are in `outputs/ux-research-2026-11-26/` (git-ignored). Trial prices/contact are synthetic test inputs, not verified live offers. Five planned images: sparse brief, three-product reference, one-price correction, second correction exercising the first-version quality anchor, and a conflicting direction overriding the same reference. Settings: `gpt-image-2.5-flare`, medium, application budget capped at USD 2. No publication, confirmation or production write.


Initial five-image sequence completed: **USD 0.279864**, 20.2–26.2 seconds per image, all jobs succeeded. These are API-to-provider trials, separate from the stub browser walk. No real-model browser interaction is claimed.

| Trial | Observed result | Judgment |
| --- | --- | --- |
| [01 sparse brief](../../../outputs/ux-research-2026-11-26/01-sparse.png) | Clear purple/white product ad; correct 120 000 Ar and supplied phone digits; prominent product and lettering. Invented a shop symbol although no logo was supplied. | Useful sparse-input baseline; not approved brand fidelity. |
| [02 reference](../../../outputs/ux-research-2026-11-26/02-reference.png) | Three cards, three correctly associated product names/prices; reference color/layout followed; source reference’s PACK 1 and total price replaced. Invented another shop symbol. | Reference and multi-item behavior work in this example; brand identity still unverified. |
| [03 price correction](../../../outputs/ux-research-2026-11-26/03-price-edit.png) | Only intended amount changed from 85 000 to 95 000 Ar; other prices and overall composition visually retained. | Successful targeted correction in this case; not pixel-identical preservation. |
| [04 second correction / quality anchor](../../../outputs/ux-research-2026-11-26/04-anchor-edit.png) | AUDIO becomes heavy serif; outer background navy; latest 95 000 price retained with other names/prices/contact. Header lettering also becomes white for contrast. | Anchor did not resurrect the old price or block this typography change. Two edits do not prove long-chain stability. |
| [05 explicit override](../../../outputs/ux-research-2026-11-26/05-reference-override.png) | Cream palette/serif type and no hearts achieved; three rectangular cards remain despite “aucune carte”. Shop name absent. | Partial instruction following. Prompt deliberately appended a priority exception to the earlier card request; a cleaner follow-up isolates that conflict. |

Inspecting the CMF source and results also shows why large product silhouettes are insufficient for fidelity review: tiny casing markings are re-rendered. This review does not certify every product inscription or hardware detail. A price-correct picture can still be unsuitable for a seller.

The sparse and reference runs demonstrate a concrete missing rule: **when no shop logo is supplied, render the requested shop name as text; do not invent a shop mark when none has been supplied.** This is a proposal for the image prompt and review, not a new barrier on creative user input.

### Two targeted counter-tests

| Trial | Observed result | Judgment |
| --- | --- | --- |
| [06 clean reference override](../../../outputs/ux-research-2026-11-26/06-reference-clean-override.png) | Removed the earlier contradictory instruction to retain cards. Explicitly requested open asymmetric layout, no frames, exact shop name, and no invented shop logo. Result has separated unframed products, cream background, serif lettering, the requested names/prices/contact and shop name; no invented shop mark. | Main layout override succeeds. This supports clearer instruction precedence and reference intent; does not establish repeatability or prove the model alone caused trial 05. |
| [07 supplied logo](../../../outputs/ux-research-2026-11-26/07-supplied-logo.png) | One product plus real shop logo uploaded through today's generic photo inputs. Gold phone/red-green bands and logo wording recognizable; correct price/contact. Separate requested shop name is repeated below the logo. | Feasible integrated identity. Not pixel-exact brand preservation; repeated identity hurts hierarchy. Kit should present logo and name coherently, not blindly append both twice. |

Follow-ups cost **USD 0.094375** (19.1 and 18.1 seconds). **Total: seven successful images, USD 0.374239** in the application's stored rate-card accounting; not an independently reconciled provider invoice. All seven publication previews verified as 1080 × 1350 PNG. No image was confirmed or posted. The two isolated test ledgers each had a USD 2 cap; aggregate spend was USD 0.374239. Research files: `paid_trial.py`, `paid_followup.py`, both JSON reports, PNGs, and their `paid-data*` ledgers under `outputs/ux-research-2026-11-26/`.

The logo trial also exposes a practical capacity issue: it uses one of today's three generic photo slots. Integrating the saved kit should not silently reduce a three-product composition to two products. Keep logo identity distinct from composition photos in the future requirements.

### Final assessment from these experiments

- **Works:** reference-based layouts, multiple independently priced products, targeted price edits, a second correction using the quality anchor, a deliberately different composition after clear override instructions, and recognizable supplied identity.
- **Needs changes:** identity inclusion and no invented shop marks by default; avoid duplicated logo/name; reference intent/precedence; later attachments; recoverable versions; latest-facts review; prompt assistance and simplified steps.
- **Can be removed from new creation:** the competing guided Message entry after parity, manual identity layers, most graphic settings, and the assumption that the three provided looks define the available output.
- **Not proved:** faithful microscopic product markings, exact logo geometry, nine-step correction stability in the built path, reliability across sectors/languages, or which provider is best. Current results justify prioritizing the experience and conditioning before model replacement.

No app source, migration, dependency, production data or deployment changed. Only research/workflow documents are tracked changes; reproducibility scripts and evidence are git-ignored research artifacts.


### Owner confirmation, 2026-11-26

The owner accepts the research direction with a strict correction: **if no shop logo is provided, do not invent one**. No generated monogram/emblem or symbol derived from the business name, and no borrowed shop logo from an inspiration picture. A requested shop name may be plain text. This supersedes the earlier exception for explicit requests to invent a shop mark. Approved constraint: [R-FREE-07](../requirements/free-creation.md#r-free-07--no-invented-shop-logo). No application code changed.
