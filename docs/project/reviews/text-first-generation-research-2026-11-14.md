# Text-first poster generation — research, 2026-11-14

Status: research complete; proposed requirements drafted, not approved. No implementation, paid generation, provider subscription or deployment in this session.

## Direction confirmed by the user

- Start with a simple chat-like text box inside Affiche IA.
- Enter the product name including brand, exact price, and a predefined style.
- Image attachments are optional. Use attached product photos first; when absent, find/reuse product images automatically.
- Keep the price inside the generated composition. The wider ambition is to use the same product service from other surfaces, but messaging integrations are not this first slice.

Example: `Sony ULT Wear noir, 700 000 Ar, style Studio clair`, with an optional attached photo. No slash command or prompt engineering should be necessary.

## What the existing application can reuse

Source inspection, not a runtime verification:

| Existing capability | Evidence | Consequence |
|---|---|---|
| Product inputs require 1–3 reference photos | `backend/src/affiche/posters/models.py`, `ProductInput` | Resolve references before entering the existing poster workflow; do not remove the fidelity invariant just to accept a text message. |
| Image provider supports generation and reference editing | `backend/src/affiche/visuals/gateway.py`, `_check_request`, `_send` | No new image provider is needed. Empty images are allowed for backgrounds, not product scenes. |
| Authenticated uploads and preserved original assets | `backend/src/affiche/posters/store.py`, `upload`; `backend/src/affiche/api.py` | Chat attachments should reuse the current upload path and validation. External image retrieval is new work. |
| Durable jobs, immutable inputs, metering and review | `backend/src/affiche/posters/service.py` and current jobs/review workflow | Keep one generation pipeline across entry points, including existing handling of unknown paid outcomes. |
| Integer Ariary price parsing | `backend/src/affiche/posters/models.py`, `parse_price`, `Offer` | Text extraction must feed the existing validation; never replace the user's amount with a web price. |
| Three built-in styles and saved style briefs | `frontend/src/App.vue`, `backend/src/affiche/posters/looks.py` | Reuse Studio clair, Aux couleurs du produit, Luxe sombre initially. Preset meaning must be consistent across clients. |
| Configured deployment default | `deploy/compose.yml` | Repository configuration is `gpt-image-2.5-flare`, medium. This is not a fresh verification of the deployed runtime. |

The preset definitions currently live partly in the frontend. A later channel must not independently reinterpret them. No general-purpose agent framework or new conversation platform is necessary for the first slice.

## Source research and concrete example

OpenAI documents reference-image generation through its image edits endpoint. This fits the existing provider path; the plain Images API call in this repository does not itself search for product photos. [Official image generation guide](https://developers.openai.com/api/docs/guides/image-generation).

The supplied screenshot contains two references above the message. It demonstrates a simple chat experience, not proof of reference-free product accuracy.

Sony's official product page identifies ULT WEAR and lists black, forest gray and off-white variants. A search can locate an authoritative candidate, but `Sony ULT Wear` alone does not identify the colour. Ask one short question or show variant thumbnails instead of silently choosing black. The page was found and read; no image was downloaded, licensed or used in generation. [Sony ULT WEAR](https://electronics.sony.com/audio/headphones/all-headphones/p/whult900n-b).

Brave is a technically plausible image-search supplier, not a selected vendor. Its Search plan lists USD 5 per 1,000 requests, so one search is USD 0.005 before credits and other work. Its image-search endpoint is documented. However, its current FAQ prohibits retaining API data without an arrangement, and the product page directs storage users to a custom plan. The default price must not be presented as the price of a cacheable reference catalogue. Search access also does not grant third-party image rights. Verify supplier terms and image-use permissions before adopting automatic retrieval/storage. [Pricing and storage FAQ](https://brave.com/search/api/), [image search API](https://api-dashboard.search.brave.com/api-reference/images/image_search), [retention and content-rights FAQ](https://api-dashboard.search.brave.com/documentation/resources/help-feedback).

## Recommended experience

1. A text composer, attachment button with previews/removal, and the existing style choices. A style typed in the message resolves to a visible preset; unknown or conflicting choices require a selection.
2. Attached product photos take priority. Otherwise, reuse an approved reference of the exact model/variant from this shop, then search permitted sources if needed. Reusing a photo never transfers approval of an old generated poster.
3. Show one compact confirmation card: product/variant, reference thumbnail, exact price and style. Explain whether the image was attached, reused or found, with a source link for found references. Corrections are available before the paid action.
4. Ask only for missing or conflicting facts. A product/photo mismatch, uncertain colour or ambiguous price cannot be silently guessed. If retrieval fails, keep the draft and offer another search or an attachment.
5. Reuse the current generation, fidelity review and export. Show truthful stages such as `Recherche du produit`, `Photo à confirmer`, `Création de l’affiche`, `À vérifier`; no invented percentage. Preserve input through failure, navigation and retries.

Keep the composer usable with the mobile keyboard: visible send/attachment actions, labelled controls, status announcements, reduced motion, and feedback immediately after submitting. Retain access to the existing full editor.

## Accuracy boundaries

- Product photos and marketing/style references have different roles. A marketing poster must not silently become an authoritative photo or contribute its price, warranty or promotional copy. Optional attachments in this first slice are product photos; arbitrary style-reference attachments need a separate approved extension.
- Manufacturer wordmarks/sub-brand lettering are distinct from the boutique logo. The current manufacturer-brand behavior can be reused, but exact Sony/ULT glyph reproduction is not guaranteed by a preset or a text prompt. Exact manufacturer-logo assets are outside this slice.
- `Aux couleurs du produit` must derive from the selected product reference and expose the existing correction mechanism. The iridescent ULT campaign treatment in the screenshot is a brand/campaign look, not the colour of the black headphones.
- Reference photos reduce uncertainty but do not prove that generated geometry, lettering or price is correct. Keep human review before final export.

## Cost and speed

This primarily reduces operator effort. It does not establish faster image inference or a lower generation bill.

| Path | Added work | Expected effect, not measured |
|---|---|---|
| Attached photo | Upload and existing validation | No product search; closest to the current generation path. |
| Approved saved reference | Exact product/variant lookup | Avoid repeated search and upload. |
| New product | Search, match, download/validation and confirmation | More preparation time and some search cost; uncertain results may need another user choice. |

Total cost includes extraction if model-assisted, searches, input/output image usage and retries. Avoid a fresh art-direction planning call for every predefined style; use existing fixed planning where applicable. Measure time to a usable, accepted poster and cost per accepted poster, not only cost per API call. The user's USD 0.26 observation from the earlier session is not a per-image estimate for this feature.

No model upgrade is needed to research this flow. Keep the current default for the first comparison so retrieval/UX effects can be separated from model changes. No promises about first-result correctness or completion in a fixed number of seconds.

## Scope that a later design must cover

- Composer and accessible mobile behavior; preset resolution and existing price parser callers/tests.
- Input/reference lookup with ownership, source provenance and exact variant matching; upload and image-validation reuse.
- Safe remote retrieval: reject internal/private network targets, recheck redirects, enforce byte/dimension/type limits and timeouts. Retrieved text is untrusted data, not instructions for changing price or spending.
- Search and optional extraction costs, bounded retries, durable request identity and duplicate-submit protection before paid generation. A separate search budget cannot silently escape the existing spend limit.
- Review/export lineage, status recovery and reference changes invalidating approvals.
- If persistent provenance/cache needs schema changes, forward-only migration and tests. No schema/API design is approved by this report.

## Next evidence to collect after requirements/design approval

Build a free local simulation first: attached photo, exact saved match, ambiguous variant, no result, corrupt/blocked remote image, duplicate submit and interrupted generation. Test narrow mobile widths and keyboard use.

Then evaluate a small fixed set of real product lookups: exact model/colour, ambiguous family name, variant mismatch and obscure model. Record source quality, ability to obtain a usable permitted image, number of questions and preparation latency. A paid generation comparison needs a separate explicit budget; measure exact product/colour, title/brand duplication, price, style and acceptance effort against the existing upload flow.

Research limits: one manufacturer's example, not a retrieval benchmark; no authenticated search API call, source licensing clearance, new browser flow, paid generation or cross-channel integration test. Search supplier selection remains open. Messaging and ChatGPT adapters are deferred, not promised as already supported.

## Follow-up: generation gaps, 2026-11-14

The user authorized further research into unhandled image-generation behavior. This section records findings and proposals, not additions to approved scope. The four text-first requirements remain Draft.

### Capability audit

| Need | Current source evidence | Gap / recommended research priority |
|---|---|---|
| Product photo plus campaign reference | `visuals.SceneRequest` and `RefinementRequest` accept `style_reference_asset`; `plans.compile_scene` assigns original/base/style roles. `App.vue` already uploads a style reference separately. | Existing machinery can be reused, but the proposed chat currently treats attachments as product photos. A mixed attachment set needs an explicit role choice: product vs inspiration. Do not guess silently. High priority if reproducing the screenshot's workflow. |
| Sony/ULT brand treatment | `compile_scene` explicitly ignores every word, logo and price in style references. Brand heading supports plain capitals or lettering like the product. Saved looks describe reusable style, not brand content. | A ULT marketing image does not currently mean “copy the ULT wordmark treatment.” Propose a distinct campaign/brand-treatment extension; exact logo reproduction would need an approved asset route, beyond prompt instructions. Keep boutique-logo handling separate. |
| Accurate model, colour, ports and markings | Identity-preservation instructions and manual checks exist in `plans.py` / `visuals.py`. | Instructions are not a pixel lock. Compare result against selected originals, including found references. If exact product pixels become necessary, assess the existing cutout/compositing path separately; it changes the integrated-scene creative tradeoff. No need to change the baked price. |
| Correct raster title and price | `required_checks` adds title/price checks; export enforces reviewed lineage and offer compatibility. | The inspected flow does not read generated lettering automatically. A wrong rendered digit can survive if a person misses it. Candidate: OCR/vision comparison as an advisory warning before human review, evaluated on false positives and missed errors. It must not silently rewrite the offer, approve output, or trigger paid retries. |
| Chat revisions | Scene refinement uses the base plus original photos. It rejects price/title/font requests with `use_selected_text_polish`. `typography.py` patches document text layers, not arbitrary raster pixels. | A composer must route “make the background darker,” “change to 650000 Ar,” and “change the font” differently. Drawn title/price changes need a new scene and review under current rules. Generic chat editing is not already supported. |
| Feed, square and story | Three formats and matching generation dimensions exist; drawn-text versions are format-bound. | “Make it a story too” cannot promise a free crop that preserves all lettering. Present the existing format/new-generation consequence. Keep format choice outside natural-language inference when unclear. |
| Live generation preview | `OpenAIProvider._send` waits for a complete PNG; `ProviderResult` holds the final image. | Partial-image streaming is absent from the application. It needs provider-event handling, safe preview delivery and reconnect behavior; a partial image must never be treated as export-ready. Prioritize truthful stage feedback first. |
| New model controls | `gateway.RATES` allows image-2 and the two 2.5 models. `_send` sends model, quality, size and PNG format; no complexity/markup/streaming fields. Evaluation quality choices special-case 2.5. | 2.6 is not a config-only switch. Model admission, SDK compatibility, usage accounting/reservations, validation and benchmark fixtures must be checked together before adoption. |

### New provider capabilities worth evaluating

OpenAI's current guide documents 2.6 `complexity` separately from rendering `quality`: omitted complexity is high, and higher complexity can increase latency or unwanted changes. It also documents streamed partial images, with 100 additional output tokens per partial. Text precision, brand consistency and exact placement remain limitations. These capabilities are documented, not tested in this application. [Generation guide](https://developers.openai.com/api/docs/guides/image-generation).

The model pages list 2.6 Flare for fast iteration and 2.6 Sunburst for detailed work. Both list USD 5/million text-input tokens, USD 8/million image-input tokens and USD 30/million image-output tokens, plus cached-input rates. Equal token rates do not imply equal cost per accepted poster: token usage, retries and review effort differ. At the listed output rate, 100 tokens is USD 0.003, excluding the rest of the request. This is an illustrative preview increment, not a verified bill. [Flare](https://developers.openai.com/api/docs/models/gpt-image-2.6-flare), [Sunburst](https://developers.openai.com/api/docs/models/gpt-image-2.6-sunburst).

The prompting guidance recommends comparing identical prompts/references/settings first, then changing one setting at a time. It also says that pixel-identical preservation requires compositing rather than relying on an edit prompt. [Prompting guide](https://developers.openai.com/api/docs/guides/image-prompting).

An image-understanding model can inspect inputs and outputs, but that is a separate operation from generating an image. An automated verifier would need its own cost, accuracy and failure evaluation; it is not proof of correctness. [Images and vision](https://developers.openai.com/api/docs/guides/images-vision).

### Smallest useful next investigation

1. Resolve attachment roles and whether campaign lettering belongs in the first scope. The screenshot's reference workflow is broader than a plain product-photo attachment. No new user decision is presumed here.
2. Extend a free simulation with mixed photo/inspiration attachments, conflicting brands, changed price, scene-only revision and format change. Confirm the correct action and review requirements without image spending.
3. With a separately approved budget, compare current 2.5 Flare/medium against 2.6 Flare at the same quality/dimensions; use Sunburst only to investigate cases that fail the acceptance criteria. Then test complexity at fixed quality on representative cases. Repeat enough to expose variability; do not run an expensive full Cartesian grid by default.
4. Score product/variant, title/price, wordmark treatment, style, unintended changes and acceptance effort. Record time to first useful preview separately from final completion, and total spend per accepted poster. Test OCR/vision warning usefulness separately so it cannot mask generator errors.

No automatic model fallback is proposed: a retry on a different model can spend twice, change fidelity and obscure an unknown outcome. Keep explicit escalation and current billing safeguards. SVG/GIF generation and a wholesale Responses API migration are deferred; a chat-shaped UI alone does not require either. This continuation adds no provider calls, image samples, new browser verification or implementation.
