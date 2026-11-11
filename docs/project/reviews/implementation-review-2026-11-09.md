**Implementation and poster-workflow review — 2026-11-09**

Follow-up: the user accepted the direction and fixes (ADR-027), then explicitly prioritised GPT Image integration over cutouts. T-FIX-001/002 now close findings 1–2 with shared description screening and ordered-photo snapshots (migration 0003; legacy snapshots refuse new `generate` work rather than inventing hashes). Verification: 442 tests passed, 3 opt-in rembg tests deselected. The [requirements packet](../requirements/_INDEX.md) drafts the new workflow; it is not implemented. The remainder below records the original review findings.

What this change does: the implemented backend creates product scenes, prepares photo-preserving cutouts, tracks attempts and estimated/usage-based costs, and supports human review through a static HTML sheet and CSV decisions. It is an evaluation tool. It does not yet turn a product photo, title and price into an editable, branded poster with a final download.

This review covers T-PV-001 through T-PV-010, the T-PV-012 probe evidence, both migrations, the current source modules, relevant tests and the uncommitted sheet/apply changes. Expected load is the approved local, single-shop evaluation of about 20 products. A hosted API and concurrent browser users are not implemented. Recommendations below are proposals; they do not amend approved requirements or authorise implementation.

During the review, the user explicitly requested real JBL and Soundcore images from web search. Two paid scene tests were then completed through the existing backend: both succeeded on the first call for USD 0.344220 combined. Their generated scenes look promising; the Soundcore cutout retained an external award graphic. See [the real-product test evidence](real-product-scenes-2026-11-09.md) for sources, outputs, timing, fidelity observations and limitations.

**Answer to the requested workflow**

| User action | Available now | What is missing |
| --- | --- | --- |
| Product photo → generated scene | Yes, through the CLI and OpenAI adapter; synthetic probe plus two real-product smoke tests | Representative shop-photo fidelity evidence and the upload/generation UI |
| Photo + title + price → finished poster | No | Commercial-data intake, composition, editable text and price, rendering |
| Polish text, price, logo size, colours and layout | No | Vue editor, history and saved poster state |
| Polish an existing generated scene | Only a fresh generation from the original photos plus correction instructions | An explicit edit path using the selected result as visual context |
| Choose logo, shop name and contact independently | No | Shop profile and per-poster visibility choices |
| Confirm, then download exactly that version | No | Poster approval, immutable version/export record and download |
| Claude-written scene prompt | No | Claude integration, structured plan validation and evaluation |

The price and facts columns in the fixture CSV are deliberately discarded after validation; they exist for leak tests. There is no Anthropic dependency or call, FastAPI application, Vue application, canvas editor, or poster-export implementation. The review sheet's crop outlines are previews of scene framing, not three exported posters. These are planned feature gaps, not claims that phase 1 violated its approved scope.

**Verified findings**

1. **Keep evaluation source photos immutable as well as CSV rows.** Must fix before relying on comparative evaluation results. Evidence: `backend/src/affiche/visuals/fixtures.py:154`, `evaluate.py:164` and `evaluate.py:175`.

   What this is: a resumed run checks the hash of the CSV row. That hash includes photo filenames but not their contents.

   Problem: replacing `p1.jpg` without changing the CSV is accepted. I reproduced this with the stub: generate a scene and cutout, reject the cutout, overwrite `p1.jpg`, and run `generate` again. The old scene retains source A, while the new cutout uses source B in the same run and variant. Both commands return 0. The candidate provenance remains available, but the nominally comparable treatments now have different inputs.

   Fix: persist and compare the ordered original-photo asset hashes for each run/product, before admitting work. Preserve existing run evidence; do not silently rewrite snapshot hashes. Any new schema field needs a forward-only migration and an explicit legacy-data policy.

   If skipped: a retaken photo can confound the treatment/model comparison without a warning.

2. **Put direction screening at the shared admission boundary.** Should fix before exposing generation through HTTP or adding a Claude planner. Evidence: `backend/src/affiche/visuals/admission.py:71`, `fixtures.py:115`, `review.py:41`.

   What this is: fixture intake screens commercial terms, and rejection notes are screened. `Direction` itself does not screen descriptions, and `request_scene` does not either.

   Problem: a direct call with `Direction(description="Prix 899000 Ar, garantie 6 mois")` is admitted, reserves budget, and stores those exact words in the image prompt. I reproduced this in a disposable stub database without executing that request. The present CSV path blocks this input; there is no public endpoint currently exposing the bypass.

   Fix: use the existing screening helper in the shared service before reserving spend. Retain useful whole-file CSV validation, and add an admission test asserting that a matching description creates neither request nor reservation. The planner must also keep commercial values out of its scene prompt.

   If skipped: a new caller can bypass an approved requirement despite all existing fixture tests passing.

These two checks used temporary data, `_env_file=None`, the stub provider and injected masks. Neither touched the saved probe nor called a paid provider.

**What I would keep**

The existing provider adapter, original-file preservation, colour/EXIF handling, content-addressed assets, integer money calculations, transactional admission, idempotent requests, bounded retries, crash recovery and explicit review states are useful foundations. The tests exercise meaningful concurrency, failure and accounting cases. I would not replace these merely to start over.

The scene/overlay separation also earns its place independently of the existing design: exact commercial content needs to remain editable, while generated imagery can remain a raster asset. Current image-generation documentation still identifies text placement, recurring brand consistency and precise composition as limitations. [OpenAI image-generation limitations](https://developers.openai.com/api/docs/guides/image-generation#limitations)

**What I would change for the product**

3. **Build around a complete poster draft.** The first useful result should already show the title, exact price and chosen shop details in a proposed composition. Asking the operator to turn a blank scene into an advert defeats much of the automation. Keep the internal visual-fidelity review, but integrate it into a coherent poster workflow. A saved scene approval and a final poster confirmation are different decisions.

4. **Offer two clear image treatments.** An integrated generated scene provides coherent lighting and perspective but can redraw product details; its product cannot be dragged independently. A preserved product cutout over a generated background supports independent movement and keeps the source appearance, but its edges and lighting integration require inspection. Both remain useful. For catalogue phones I would start evaluation with the preserved-photo treatment as the conservative option, then choose the default from actual results. Neither treatment has sufficient real-shop evidence yet.

   The subsequent two-product test changes the weight of this recommendation: both integrated scenes look promising, while the Soundcore cutout incorrectly retains an award graphic. Do not select the cutout route as the default on the assumption that it is automatically cleaner or more accurate.

   A completely AI-rendered poster, including text and branding, is worth comparing as a visual concept. I would not make it the editable master: changing a phone number or price would then require regeneration and another full review. The model's ability to render attractive lettering does not supply editable text objects.

5. **Separate ordinary editing from image regeneration.** Price, title, contact visibility, fonts, logo placement and text size should change immediately without an image-provider call. Natural-language instructions such as “agrandis le prix” can become validated editor operations; direct touch/mouse controls must remain available. Scene changes such as lighting or props create a new candidate while retaining the current version and its overlays. No automatic loop should keep spending until an AI reviewer approves.

   Current `request_revision` (`admission.py:96`) reloads original photos; `_insert` (`admission.py:227`) never supplies the parent's generated image. Thus “keep this composition, soften its lighting” is currently another attempt, not a faithful edit. Add a distinct refinement action that supplies the selected scene and original product references with explicit roles. Start by assessing this with the existing image-edit adapter; a wholesale transport change is not automatically required. OpenAI also documents a conversational editing path if that later proves useful. Neither path guarantees unchanged product pixels. [OpenAI image-generation and editing guide](https://developers.openai.com/api/docs/guides/image-generation)

   Refining an approved result should create a new pending version without rejecting or overwriting the good one. This changes the current linear reject→revise policy and needs amended requirements. Masked/local retouching is presently out of scope; it should be a separate decision, not silently included in this review.

6. **Move the shadow with the cutout.** `cutout.py:165` bakes it into the background, as previously approved in ADR-011. Moving the product later leaves its shadow behind. For the proposed editor, keep the clean background and render the shadow with the product transform, with an option to reduce or remove it. Existing raw backgrounds are already retained. This is a proposed reversal of an approved tradeoff, not an implementation defect.

   Also evaluate softer alpha edges. The current binary mask and one-pixel erosion (`cutout.py:100`) intentionally preserve source RGB but can remove thin details or produce harsh edges. Keeping original RGB while allowing partial edge alpha is possible; it changes the present binary-alpha tests/design and still needs visual validation. Pixel equality alone does not prove a good cutout.

7. **Compose for the selected format.** The current prompt fixes the product near 40% of a vertical master, and all formats are centred crops (`prompts.py:94`, `sheet.py:20`). That is convenient for evaluation but constrains every poster to a similar composition. Choose the primary format before generation and reserve space based on the visible title, price and shop fields. Reflow overlays for other formats and review each crop. Generate a new scene variant only when cropping cannot preserve the product; do not pay for three images automatically.

8. **Keep evaluation policy out of everyday poster editing.** `runs` has a global unique `(model, quality)` pair; changing a snapshotted CSV row is refused; a new cycle requires an approved candidate (`review.py:72`). These are deliberate experiment rules. They should not become the shop's campaign model. A user must be able to abandon an unsuccessful idea, replace a poor photo and start a new explicitly budgeted draft without approving a bad result. Limit paid work per draft and overall budget; keep historical attempts and approvals.

**Shop identity choices**

Store the shop's uploaded logo, exact name and contact text once. Each poster has independent choices for `Logo`, `Nom de la boutique` and `Contact`: any single field, any combination, all three, or none. Missing values must be visible to the user; never invent contact information. These choices affect both the layout proposal and the final rendered output.

Render the actual logo asset and exact text as editable objects. The image model should not redraw the shop logo or typeset the phone number. The downloaded PNG/JPEG includes the selected objects after composition, so they are present in the final image. Save the selected values and logo reference with each poster version; editing the shop profile later must not silently alter an already confirmed advert.

**Claude's role**

Yes: Claude is a reasonable candidate for writing the scene prompt and proposing the composition. It should receive the product image, user-confirmed title/facts, visual direction, target format and the selected identity fields. It can propose a palette, scene description and space allocation. The image provider renders the scene; the application renders the commercial information.

Claude's image-input and structured-output capabilities support this approach. Structured JSON gives the application a constrained plan, not arbitrary HTML or executable code. It does not guarantee correct product facts or precise visual placement. [Claude vision](https://platform.claude.com/docs/en/build-with-claude/vision), [Claude structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)

The plan should refer to the supplied title, price, logo and contact fields rather than rewriting their values. The backend retains final authority over those values and the no-commercial-text scene rules. Keep a simple fixed-prompt path for comparison and for an explicit fallback when planning is unavailable. A planner is justified only if it improves accepted posters or reduces correction time enough to cover its cost and delay.

Illustrative scene instruction, written for this review, **not generated or tested by Claude**:

> Create a restrained charcoal studio setting around the product in image 1. Keep its visible shape, colour and camera arrangement. Use soft side lighting and a subtle surface reflection. Leave an uncluttered area above the product for the headline and below it for the offer and shop identity. Add no lettering, prices, badges or shop logos. Keep only markings already present on the product.

This is only the image instruction. The exact commercial text remains in the poster document. Layout proposals must be checked against the actual returned scene; a requested empty region is not a guarantee. On planner timeout, refusal, truncated output or invalid fields, retain the draft, show the error and offer retry or the simple prompt path. Do not start paid image generation from an invalid plan. Measure planner usage separately as well as in total cost per accepted poster.

**The smallest useful workflow to specify next**

Upload product image → enter/confirm title and price → select shop fields and primary format → generate a composed draft → compare product with original and polish → inspect the final format → confirm → download that exact version.

Keep undo/redo and previous candidates. If the operator changes the confirmed draft, it becomes a new draft. Export must use the selected full-resolution assets and the same layout/font definitions as the preview. Wait for fonts and images; refuse an export with missing assets, empty required values or clipping. Do not secretly regenerate or “improve” the image during download. If a later high-quality render changes the scene, it needs a new preview and confirmation.

For an initial vertical slice, prove one format end to end before expanding to all three. The project-level requirement for feed, square and story remains; a one-format slice is an implementation sequence, not a reduction in scope. The Vue/FastAPI stack still fits. No canvas library choice or new infrastructure is justified by this review alone.

The next planning work should amend `product-visuals` where refinement/shadow/campaign rules change, and draft the relevant `catalogue-brand`, `poster-editor`, `format-export`, `creation-library` and `generation-jobs` requirements for this slice. Use the existing feature split; do not create a competing poster specification. Requirements approval precedes matching designs and implementation tasks. T-PV-011 remains unfinished and useful for the existing evaluation, but it does not deliver the requested product flow.

**Evidence and verification**

- `cd backend; uv run pytest -q`: **432 passed, 3 deselected**, 116.05 seconds. The three deselected tests use the real rembg model. This run used the existing offline/mocked suite; it proves software behaviour, not generated visual quality.
- Read the probe database through SQLite `mode=ro`, and visually inspected the source and generated scene. One successful `gpt-image-2` call at high quality, 1088×1920, cost **USD 0.168661** from returned usage, about **55.1 seconds** between recorded timestamps. The candidate is still `pending_review`.
- The source is a synthetic drawing of a phone. The output preserves the broad silhouette and camera arrangement while inventing realistic lens/material detail. It demonstrates a working paid integration; it is not a fidelity test on an actual sale item and not a finished advertisement.
- Both additional code findings were reproduced with assert-based checks in disposable stub data. No application files or tests were modified. The user's later request authorised two real-product scene calls; their evidence is recorded separately above.
- Provider research used current official OpenAI and Anthropic documentation. Postman Orbit located a Claude Messages image-analysis example, but its integration brief was partial and used an older model example; it was not treated as the current capability contract. The installed Postman CLI rejects `postman status`, so no workspace, collection or simulation was created. Existing SDK MockTransport tests supplied local adapter evidence.

Before selecting a default treatment or paying for a large evaluation, use a small set of real shop photos and judge complete posters: product correctness, legibility, branding, time spent correcting, exact price/contact output, and cost including Claude, rejected attempts and refinements. Include a price-only reuse, independent identity toggles, a scene edit and confirmation/download. The synthetic probe and two manufacturer-image tests do not answer those questions.

Verdict: keep the generation foundations, fix finding 1 before trusting comparative evaluation and finding 2 before adding new callers. The requested poster product is **not usable as is**; specify the complete editing and export slice before extending the backend around assumptions from the evaluation harness.

Not checked: Claude output quality, actual shop photos, real-device editing/export, generated refinements, or the unresolved rembg checkpoint licence. Two new paid generations and their local cutouts were checked as documented above. Main risk: attractive generated scenes can still misrepresent the actual product.
