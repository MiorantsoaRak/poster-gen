# DESIGN — catalogue-brand

**Status:** Approved v1, 2026-11-09. **Approval:** ADR-031. **Requirements:** [catalogue-brand](../requirements/catalogue-brand.md), approved ADR-028. Architecture proposals: ADR-029.

## System overview

Vue intake → authenticated FastAPI → existing content-addressed assets + SQLite. The pilot has one shop, with staff sharing access to that shop's creations. Product inputs are immutable; offers belong to editable creation versions. No catalogue administration screen is needed to create the first poster.

## D-CATALOGUE-BRAND-001 — Original intake and verified product input

**Covers:** R-CATALOGUE-BRAND-001; product-visuals R-003/007/009.

**Data:** forward-only migration, existing assets retained:

| Table | Fields and constraints |
|---|---|
| product_inputs | UUID id; shop_id; product_ref (generated UUID unless supplied valid SKU); name; variant; ordered photo_assets_json (1–3 original hashes); facts_json (confirmed strings only); supersedes_id nullable FK; confirmed_at UTC. Immutable after insert. |
| asset_access | shop_id, asset_sha FK assets, role original/logo/style; UNIQUE(shop_id,asset_sha,role). An asset hash alone grants no access. |

Name/variant: nonempty, maximum 160 Unicode characters each; optional confirmed facts: up to 10 strings, 200 characters each. To preserve the photo/title/price entry path, name initially uses the entered title; when no named variant is supplied, the operator can explicitly confirm 'Conforme à la photo' rather than inventing a colour/specification. Internal identity remains the immutable input UUID/hashes. Replacement keeps product_ref but creates a new input ID linked by supersedes_id. Changing identity is a new product_ref. Stored originals retain original bytes/metadata; only model-facing copies remove EXIF and convert colours using the existing preparation helper.

**Contracts** (shared conventions in D-CATALOGUE-BRAND-003):

| Endpoint | Input | Success / specific errors |
|---|---|---|
| POST /api/assets | multipart file, role=original/logo/style | 201 {asset, mime, width, height, warnings}; 413 too_large; 415 unsupported_type; 422 invalid_image/unsupported_colour |
| POST /api/product-inputs | {product_ref?, name, variant, photo_assets, facts, supersedes_id?}; Idempotency-Key | 201 immutable input; 422 unknown_asset/invalid_product; 404 inaccessible superseded input |
| GET /api/product-inputs/{id} | authenticated | 200 input with authorised original URLs; 404 unknown/inaccessible |
| GET /api/assets/{sha} | authenticated, ownership or retained-creation reference checked | bytes with correct MIME, nosniff; 404 unknown/inaccessible/missing file |

Upload limits: 10 MiB encoded file; 40 million decoded pixels; JPEG, PNG or WebP only; one static frame. Check actual decoder format, not just extension/MIME. Reject animated images and HEIC with a conversion instruction. Decode/prepare before recording access. Minimum short edge uses existing MIN_SOURCE_SHORT_EDGE; below it returns low_resolution, acknowledged explicitly on image-job submission. The scene route never imports/runs rembg or calls cutout.check_source. Logo aspect ratio and alpha are preserved; SVG is excluded initially to avoid active content.

**State:** upload temporary → validated asset → confirmed product input. Invalid uploads never become usable assets. No mutable 'approved photo' flag: each job freezes the referenced input ID/hashes. Replacing inputs creates a new creation via creation-library; previous fidelity approvals remain bound to the old input.

**Failures / edges:**

| Failure | Detection | Handling |
|---|---|---|
| Corrupt image, decompression bomb, unsupported colour | Decoder/input preparation | 422; retain valid files and entered form values; no provider call. |
| Disk full or interrupted upload | Write/fsync failure | Remove temporary file if possible; return storage_unavailable; do not record asset access. |
| DB fails after content-addressed write | Transaction rollback | File can remain unreferenced; never overwrite/delete a valid existing asset. Return failure; retry deduplicates by content. |
| Same hash written concurrently | Destination exists | Verify expected length/hash and reuse; otherwise propagate. Fix existing Windows assets.put race before exposing parallel API intake. |
| Image content changes at same local name | Hash differs | New immutable asset/input; no inherited candidate approval. |
| Duplicate upload | Content hash already stored | Reuse bytes; establish authorised shop reference; no duplicate file. |

Offer title/price live in creation documents: title 1–240 characters; price integer 0…9,007,199,254,740,991 Ariary (JS safe-integer boundary), never floating arithmetic. Reject booleans/fractions/scientific notation in input. UI accepts plain digits or correctly grouped spaces/NBSP/narrow NBSP; formats as grouped digits + ' Ar'. Zero is shown as 0 Ar, not an invented 'free' offer. No AI populates these fields.

## D-CATALOGUE-BRAND-002 — Shop profile and per-poster identity

**Covers:** R-CATALOGUE-BRAND-002; R-POSTER-EDITOR-001 and R-CREATION-LIBRARY-002.

**Data:** shop_profile(singleton id=1, revision>=1, name nullable ≤160 chars, contact nullable ≤500 chars/up to 6 lines, logo_asset nullable FK, updated_at). Migration seeds one empty profile; shop_id foreign keys reference this row, which cannot be deleted in V1. French user text is preserved after trimming outside whitespace; no inferred phone/address. Only the pilot shop exists; shop_id is derived from the session, never accepted from browser JSON.

GET /api/shop-profile → {revision,name,contact,logo_asset}. PUT /api/shop-profile with If-Match and Idempotency-Key replaces these fields; 200 new revision or 409 revision_conflict. Reject a logo not uploaded with an allowed role/access. Clearing a field does not clear it in existing creations.

Creation document carries an exact brand snapshot {profile_revision,name,contact,logo_asset} and independent include {logo,shop_name,contact} booleans. Default each available field on, missing field off; the intake shows these choices before planning. Enabling an absent value returns 422 missing_brand_field; never render placeholder text. Applying current profile to a draft is an explicit save with a new snapshot, preserving earlier versions. All eight inclusion combinations are supported where all three source fields exist.

**State:** profile revision N → N+1, atomic. Draft inclusion/edit changes create a new document revision; they do not change scene fidelity status or call a provider.

| Failure / edge | Handling |
|---|---|
| Two tabs edit profile | If-Match prevents lost update; show latest and allow explicit reapply. |
| Save fails | Old profile stays current; retain unsaved form values. |
| Logo missing/corrupt later | Block render/confirmation with asset_missing; no replacement or generated logo. |
| Long contact or wide logo | Keep content/aspect ratio; editor reflows or shows overflow; never silently shrink text below its minimum. |

## D-CATALOGUE-BRAND-003 — Shared pilot API and access boundary

**Covers:** access and validation clauses of both requirements and all five dependent features. This is one shared boundary, not six auth implementations.

- Serve Vue/API/assets from one origin in hosted pilot. Vite's dev proxy forwards /api locally. HTTPS is mandatory except loopback development; no permissive CORS, arbitrary remote-image URLs or public static asset directory.
- One shop password, hash in server-only SHOP_PASSWORD_HASH (pwdlib Argon2 verification; version pinned/verified at implementation). No user registration, roles or multi-shop administration. Staff with this shared credential see the same shop data; this design does not promise per-staff private documents.
- POST /api/session {password} verifies the password and creates a random 256-bit opaque token; store only its SHA-256 in sessions(token_hash, shop_id, expires_at). Cookie: HttpOnly, Secure on HTTPS, SameSite=Strict, Path=/, fixed 12-hour lifetime. GET returns authentication state; DELETE revokes it and clears cookie. Never return password/hash/token in JSON or logs.
- Every mutating browser request, including login/logout, requires an exact configured Origin; reject missing/foreign origins. GET has no state changes. Login failures return the same 401 response and are limited to five per IP per 15 minutes (persist attempt counters); untrusted forwarding headers cannot choose the rate-limit key. Operational setup must configure the trusted proxy explicitly.
- Requests validate server-side with extra fields forbidden, finite coordinates, bounded strings and same-shop foreign keys. Responses use UTC timestamps, UUID strings, integer micro-USD costs and integer Ariary prices. No automatic remote fetch of a caller-supplied URL.
- Errors: {error:{code,message_fr,field?,retryable},request_id}. Common codes: 401 unauthenticated, 403 forbidden_origin, 404 not_found, 409 revision_conflict/idempotency_reused, 413 too_large, 422 validation_error, 429 rate_limited, 503 storage_unavailable. Do not expose provider bodies, SQL, filesystem paths or keys.
- If-Match: strong revision string (for example "7") on mutable resources. Missing → 428 precondition_required; outdated → 409 with current_revision. Compare inside BEGIN IMMEDIATE, not only before the transaction.
- Idempotency-Key: client UUID on state-creating/paid operations. mutation_keys(shop_id,key,method,path,payload_sha,status_code,response_json,created_at) has UNIQUE(shop_id,key). Check auth first; equal key+request returns the original response, unequal content returns 409. Store the response in the same transaction as domain changes/reservations; failed validations do not consume keys. Never replay a provider call to reconstruct a response.
- Session expiry preserves local unsaved form/document state in memory; prompt sign-in and retry the same operation key. No claim of durable offline edits. SQL/asset ownership checks still apply after reauthentication.

**Security failure modes:** wrong/missing password blocks all data routes; missing auth configuration refuses hosted startup; expired sessions fail closed; DB outage returns 503 and issues no session; logout invalidates the token server-side. App and renderer logs contain request IDs, states, timing and redacted error codes, never images, contacts or prompts by default. Private backups follow creation-library.

## D-CATALOGUE-BRAND-004 — Compact contact drawn in the composition, with a position; rendered line as fallback

**Status:** Approved v3.1 by the user on 2026-11-12 ("go"; ADR-056). Round 3 returned APPROVE WITH FIXES, no P1 ([round 3](../reviews/signature-design-r3-2026-11-12.md)); its fixes are in this text and were not reviewed again. **Covers:** R-CATALOGUE-BRAND-003 as amended by ADR-055. Feed format only until T-POSTER-009. The editor sends the fixed plan only; a Claude or hand-edited plan sent through the API is outside what this section guarantees.

**History.** v1 drew the contact and was returned REWORK ([round 1](../reviews/signature-design-r1-2026-11-12.md)). v2.1 wrote the contact with the renderer (ADR-053), was approved (ADR-054) and built (T-SIG-001/002). The first real poster showed its flaw: the image model drew the price pill below its band, into the band reserved for the contact, and the rendered contact landed on the pill. The user decided to draw the contact in the composition again (ADR-055). v3 keeps what v2.1 built as the fallback and answers the round-1 findings.

**Principle.** By default the image model draws the contact, so it composes it with the price. The rendered compact line (layer with `icon: "phone"`) is used when the owner unticks drawing, and for a contact the model cannot be asked to draw. The shop name is never drawn in a new scene; the logo stays the uploaded file as a layer.

**What changes for the owner.**

- "Ce que l’IA dessine dans l’image" gets back one option, on by default: "Dessiner aussi le contact dans l’image".
- "Position du contact" (Gauche, Centre, Droite) stays in the "Textes" card and is no longer disabled when the contact is drawn. With a drawn contact it sets where the next version draws it, and a help line says so: "Le contact est dessiné dans l’image : la position s’applique à la prochaine version." That next version goes through the existing cost confirmation. With a rendered contact it moves the line at once, as built. The layer says `center` where the request field says `centre`; the editor maps one to the other.
- The fidelity review point reads "Contact" when only the contact is drawn (today it always reads "Boutique et contact"), with the typed contact to compare. The stale-text notice under the Textes card names the contact only in that case.

**Data.** No table and no migration. `Headline` gains one optional field, omitted when unset like `brand_text` (`Field(None, exclude_if=…)`), so request bodies, idempotency hashes and stored payloads of earlier scenes are unchanged:

| Field | Type | Meaning |
|---|---|---|
| `signature_align` | `"left" \| "centre" \| "right" \| null` | Absent: the ADR-043 block (rule, shop name line, contact line, centred) for stored scenes, their refinements and replays; that branch of `compile_scene` is not touched. Set: the compact contact line at that position. |

The editor sends `signature: true` with `signature_align` only when "Laisser l’IA composer le titre" and the drawing option are ticked, the contact is selected and it is drawable; otherwise it sends neither. `signature_align` without `signature: true`, or with no contact selected, is refused 422 `invalid_headline` in `compile_scene`, before any job exists. A new scene request with `signature: true` and no `signature_align` is refused the same way in `request_scene`, so the older block that also draws the shop name cannot be requested any more; refinements are built from the stored payload and are not affected. This removes the round-1 contradiction: a poster with nothing to draw sends nothing.

**Which words are drawn.** With `signature_align` set, `request_scene` passes only the contact to `compile_scene`, never the shop name. A ticked shop name stays an editable layer in its own plan region, as today.

**Layout.** No change to `fixed_plan` and no new `PlanContext` field. The plan already reserves a contact region: the full width, or the span to the right of the logo. The position is not a different box: it is how the line is aligned inside that box, stated in the prompt. Consequences:

- A plan does not go stale when the position changes; no plan code changes (round-1 claim b).
- The planned logo box and contact box never intersect (`ScenePlan` validation), and the drawn line stays inside its box whatever its alignment. The planned logo is always at the left, so no logo move is needed between versions (round-1 first P1). This is about planned areas: a logo layer the owner drags or ticks later is covered in the table below.
- No line width is needed from the editor (round-1 third P1).

**Fit rule.** A drawn contact must be one line: no line break, no double quote (existing rule), and at most `floor((box width in px − 50) / 23)` characters, which is 40 for the full width and 33 beside a 128 px logo. The divisor is an estimate for digits 2 % of the frame high (27 px), the size the prompt asks for. It is checked in the editor (reason under the option, which is then disabled) and again in `compile_scene` (`invalid_headline`). A contact that fails keeps the rendered layer, where the exact `text_fit` check applies. The server also screens the contact for price-like or instruction-like text (`screen_headline`); if it refuses a contact the editor allowed, the editor shows the refusal and the owner unticks drawing.

**Prompt (`compile_scene`).** With `signature_align` set:

- A new sentence replaces the signature sentence: a contact line, left-aligned at the left edge of, centred inside, or right-aligned at the right edge of the contact area, always given as explicit margins with `_area` (never "the full-width band", so that left and right mean the 5 % margins, not the frame edges); one single line; a small telephone handset icon then the contact, verbatim, each character exactly as written; clean sans-serif, evenly spaced digits about 2 % of the frame height; no rule, no second line, no other words; "these digits are a telephone contact, not a price". Only when the price is drawn and the contact area lies below it, the sentence adds "clearly smaller than the price and entirely below the price label".
- The price sentence gains a hard limit whenever a logo, shop-name or contact area lies below the price, drawn or not: the price label's lowest edge stays above the highest of those areas. All boxes are available in `compile_scene`. This also protects the rendered fallback and the layers from the failure seen on the real poster. It is not added to refinements, so the prompts of refinements of stored scenes stay as they were; "byte for byte" below is about the signature sentence.
- The closing constraint names "the contact line" among the only writing. No example text enters the prompt.

**Guards (existing code).** The job payload records `contact` and `signature_align`. `exports.py` refuses `signature_missing` when the drawn contact no longer equals the poster's snapshot, or when a selected contact is neither drawn nor a visible layer. The first scene hides only drawn roles (`service.py`); `chooseVisual` hides or shows the contact layer per version and gives a re-shown layer the compact style (built). Refinement rebuilds the headline from the stored payload, so it keeps `signature_align`, or its absence.

**The 22 px minimum.** For a drawn contact it is asked for, not enforced: nothing in the code measures drawn text. The owner checks it at the review. It is measured by a test only for the rendered fallback (built). R-CATALOGUE-BRAND-003 says this in its amended text.

**States.** None new. The position and the drawing option describe the next scene and are kept on the device (`affiche.style`). Changing the contact text, or unticking the contact, after it was drawn makes the poster stale exactly as today (`signature_missing`, notice under the Textes card) until a new version is made or the old text is restored.

| Failure / edge | Handling |
|---|---|
| The model draws a wrong or missing digit | Not detected by code. The review shows the typed contact beside the image; the owner refuses the version. This risk is the price of drawing and was accepted in ADR-055. |
| The model draws the contact at another place, on two lines, too small, or adds words | Not detected by code; refused at the review ("Contact", "Aucun autre texte que ceux ci-dessus"). |
| The model still draws the price into the contact region | Reduced by the new hard limit, not excluded. With a drawn contact the model places both itself; with the rendered fallback the owner can drag the line or refuse the version. |
| A logo layer is visible on a poster whose scene drew the contact (ticked after the scene, or dragged) | The logo may cover part of the drawn line; code cannot see it. Whenever a contact is drawn and the logo is shown, a help line under the checkboxes says: "Le contact est dessiné dans l’image : gardez le logo à l’écart, ou générez une nouvelle version." The final preview shows the result. |
| Contact too long, with a line break or a double quote | Drawing is disabled with the reason; the rendered layer is used. No paid call. |
| No contact selected | Nothing is drawn and no layer is shown; no placeholder. |
| Old scene with the ADR-043 block | Unchanged behaviour and guards; its refinement keeps the block. |
| Provider failure, timeout, budget | Unchanged scene-job handling (D-GENERATION-JOBS-002/003): no retry for unknown outcomes, the slot is freed on failure, the cap is checked before the call. |

**External systems.** No new call: the same single GPT Image request with a different prompt. Cost and rate handling are unchanged.

**Verification of D-004 v3.**

- Unit tests (no spend): the three position wordings and their boxes; contact only, never the shop name; refusals (`signature_align` without `signature`, without a contact, too long, with a quote); absent `signature_align` keeps the ADR-043 sentence byte for byte and is omitted from dumps; the price hard limit appears when a contact or logo region lies below the price and not otherwise; refinement of an old and of a new scene; export guard for a changed contact.
- Browser smoke (stub): the option is on by default and sends `signature` with `signature_align`; unticking it gives the rendered line; the position choice is remembered; the too-long reason.
- Paid, only with the user's go: one scene with the position at the right and the logo ticked (about USD 0.21). Read every digit, measure the digit height, and check the pill and the contact are clear of each other. One scene shows it can work, not that it always does.
- Not covered: square and story formats, a real phone.

## D-CATALOGUE-BRAND-005 — Product brand mark: drawn or plain text

**Status:** Approved v2.1 by the user on 2026-11-12 ("approved, commit and go"; ADR-054). **Covers:** R-CATALOGUE-BRAND-004. Both review rounds found this section sound; their minor points are fixed here.

**Data.** `Headline` gains `brand_text: Literal[true] | null = null`. Absent or null means today's behaviour, and the field then disappears from the idempotency body (`exclude_none`), so a request retried across the deploy keeps its key. `brand_text: true` without a typed `brand` is refused 422 `invalid_headline`, before any job exists. The check is raised in `compile_scene`, as for the other headline rules, because a model validator would return a generic 422.

**Editor.** Under "Marque (facultative)", a checkbox "Écrire la marque en texte simple (si l’IA ne connaît pas son logo)", shown only when a brand is typed. Kept on the device in `affiche.style`; the restore of that entry must also run when a saved look is selected (today it is skipped in that case).

**Prompt.** Without `brand_text`: today's wording, "written as on the product". With it: the brand name in small plain capitals of the headline lettering, with "do not imitate a logo or a trademark shape". No brand typed: no brand sentence; the counted quoted strings of the headline already exclude an extra line.

**Review.** The text point reads "Marque, titre et sous-titre" when a brand was typed (today it always reads "Titre et sous-titre"), with the typed brand first. "Marque et inscriptions fidèles" stays the point for the mark on the product itself. The application never states that a mark is correct.

| Failure / edge | Handling |
|---|---|
| The model still draws a logo shape with `brand_text` on | Not detected by code; the owner refuses the version. |
| The model draws a brand mark although no brand was typed | "Aucun autre texte que ceux ci-dessus" at the review; not detected by code. |
| Brand typed with a price-like or instruction-like text | Existing `screen_headline` refusal, unchanged. |
| Provider failure, timeout, budget | Unchanged scene-job handling (D-GENERATION-JOBS-002/003). |

No brand logo upload (ADR-052 default 4).

## D-CATALOGUE-BRAND-006 — Logo seal printed on a disc the scene provides

**Status:** Approved v2.1 by the user on 2026-11-12 ("approved, go"; ADR-057). **Covers:** R-CATALOGUE-BRAND-005. Feed format only. Evidence: [logo study](../reviews/logo-study-2026-11-12.md), rounds two and three. v1 was returned REWORK and challenged by the devil's advocate ([round 1](../reviews/logo-seal-design-r1-2026-11-12.md)); v2 was returned APPROVE WITH FIXES ([round 2](../reviews/logo-seal-design-r2-2026-11-12.md)); its fixes are in this text and were not reviewed again.

**Principle.** A "calm area" is not reliably kept by the image model (ADR-055). An empty white disc is an object: in the study the model drew it, composed the price and the contact around it, and the program found it 0.4 % of the height from where it was asked, at 10.7 % of the width for 10 % asked. The real logo file is then printed on the disc by the shared renderer, so nothing of the logo is drawn by the model.

**What changes for the owner.** Under the "Logo" checkbox: "Logo en sceau rond dans l’image". It is ticked by default on a new poster that includes the logo. With it:

- the scene is asked for the disc, and after the scene the logo appears as a round seal on it; it stays a layer he can drag or resize;
- the contact is drawn at the right, and "Position du contact" is disabled with the reason "Avec le sceau, le contact est à droite";

**When the seal is available.** Only for the one footer this design can vouch for: the logo and the contact are selected, the shop name is not, "Laisser l’IA composer le titre" is on, the price and the contact are drawn in the image, and the poster has no scene yet. In every other case the option is disabled with its reason under it, and the logo is the plain movable layer of today. The seal is therefore chosen before the first version: turning it on or off later would change which layers the plan covers and make refinements of the existing scenes fail (`unselected_or_missing_overlay`), so it is locked once a scene exists, with the reason "Le sceau se choisit avant la première version : créez une copie de l’affiche pour le changer."

**Data.** No new table and no migration.

| Where | Field | Meaning |
|---|---|---|
| Logo layer of the poster document | `shape: "circle" \| null`, omitted when unset like `price_badge`; allowed only on the logo layer (`shape_requires_logo`) | The seal mode of this poster. The renderer draws the image clipped to the circle inscribed in the layer box, scaled to cover it (not "contain", which the plain logo uses), on a white fill. The editor sets it at poster creation and when the option is changed before the first scene. |
| `Headline` (scene request, stored in the job payload) | `logo_seal: Literal[true] \| null`, omitted when unset | Ask the scene for the empty disc. Refused 422 `invalid_headline` unless: the logo layer is a seal; the price is drawn; the contact is drawn with `signature_align: "right"`; the shop name is not selected; and the plan's `product_region` and `overlay_regions` equal those of `fixed_plan` for this context. The plan's source cannot be used for that last test: the editor posts a plan revision for every look, stored as `manual`. |
| `poster_visuals.placement_json` (existing nullable text column; its CHECK concerns `photo_preserved` rows only; nothing reads it for scenes) | `{"logo_disc": {"x", "y", "d"}}`, `{"logo_disc": null}`, or NULL | Disc found (centre and diameter in poster pixels, that is scene pixels × 1080 / 1088); disc asked and not found; no disc asked. Returned by `GET /api/visuals/{id}` as `logo_disc` (object, null) or absent. |

**The seal is outside the plan.** `context_for` leaves a seal-shaped logo layer out of the plan's fields, so the plan is the one of a poster without a logo: the price band and a full-width contact area, as in the study. This also removes the round-1 blocker: a refinement no longer measures a 134 px seal against a 128 px planned logo box. A plain (non-seal) logo keeps its planned box as today.

**Prompt (`compile_scene`, with `logo_seal`).** The study's tested prompt is kept as it is: the price sentence with its hard limit, the contact sentence, the calm areas and the constraints are the ones the application already writes. One sentence is added, the study's badge sentence, and the constraints name "the empty white badge" among what may appear. Only the disc's centre depends on the price alignment:


| Price alignment (from the look) | Disc centre | Tested |
|---|---|---|
| left | x 50 %; y 1 % of the frame height above the top of the contact area (90.4 % in the usual plan) | With this prompt structure and these places, yes, twice (study rounds two and three), at 19 % and 10 % of the width; not at 12 %. The model then put the price, the disc and the contact on one row by itself. |
| centre (also the case without a look) | x 11 %; same y | No. Geometrically the disc (5–17 % of the width) is clear of a centred pill and of a right-aligned contact line. |

- Disc: 12 % of the frame width in diameter; "one small, plain, flat, pure white circular disc with a very soft shadow, completely empty: no writing, no icon, no pattern and no outline inside it, because the shop's logo is printed on it later; a discreet seal, clearly smaller than the price label; the price label and the contact line do not touch it".
- The contact's existing fit rule and size wording are unchanged. In the study the model itself drew the contact smaller to make room (digits about 15 to 20 px); the owner sees that at the review. No new character limit is introduced, because the only measured constant for one would leave no margin.
- In seal mode the editor sends `signature_align: "right"` whatever position is remembered on the device, and does not overwrite the remembered one. The help line "Gardez le logo à l’écart du contact" is not shown for a seal.

**Finding the disc (`posters/seal.py`, pure function, Pillow only).** `find_disc(image, centre, diameter) -> (x, y, d) | None`, called when the scene or refinement result is stored (`service.py`), before the first-scene layer placement:

1. Crop a window of three times the asked diameter around the planned centre.
2. Seeds: the planned centre and eight points around it (3 % of the width, 2 % of the height). A seed counts only if every channel of its pixel is at least 249.
3. Flood from the seed with `ImageDraw.floodfill` inside the window; its threshold is the summed channel difference from the seed pixel, set to 12.
4. Accept the region when it is round and plausible: bounding box within 6 % of square, filled area between 70 % and 86 % of the box (a disc fills 78.5 %), diameter between 85 % and 160 % of the asked one, and it does not touch the window's edge.
5. Otherwise `None`. Any exception is logged and treated as `None`: finding the disc can never fail a paid job.

Cost measured by the reviewer on a window of this size: 0.3 to 0.4 s. A white backdrop is not excluded: with the asked shadow the reviewer's synthetic disc on pure white was found; without a visible edge it is not, and the fallback applies.

**Placing the seal.**

- Disc found, first scene: in the same transaction as the other layer placements, the logo layer gets the box of diameter + 4 px centred on the disc.
- Disc asked and not found, first scene: nothing is printed at a guessed place. The logo is unticked on this poster (`include.logo` false, layer hidden) in that same revision, and the review says: "Le disque du logo n’a pas été trouvé dans l’image : le logo a été retiré de cette affiche. Cochez « Logo » pour le placer vous-même, ou générez une nouvelle version."
- Later scenes and refinements: the server does not touch the document. When the owner chooses a version, `chooseVisual` applies the same two rules from that version's `logo_disc`: found, the logo is ticked again if a not-found version had unticked it, and placed on the disc; not found, the logo is unticked with the message.
- Ticking "Logo" again on a version with a disc puts the seal back on the disc, not at the footer's left; on a version without one it is placed by the existing `placeFooter` as a plain layer.

**Guards.**

- Export (`exports.py`, where the selected `visual` row and the layer boxes are both in scope): when the selected scene has a disc, the logo layer must be visible and its inscribed circle must cover the disc: distance between centres + disc radius ≤ layer radius + 2 px. Otherwise 409 `logo_disc_uncovered`: "L’image contient un disque prévu pour le logo : replacez le logo dessus ou générez une nouvelle version." The editor shows the same reason under the main action.
- This amends R-CATALOGUE-BRAND-002 for seal posters: unticking the logo, or moving it off its disc, needs a new version or the seal put back. The requirement says so.
- Refinement keeps the base scene's stored headline, so `logo_seal` is kept and the disc is searched in the refined image.

**Review and final screen.**

- Fidelity review (it shows the raw scene, where the disc is empty): one line in the group "L’image" when a disc was asked: "Un disque blanc vide est prévu pour le logo : rien ne doit être dessiné dedans", or the not-found message above.
- Final screen (it shows the composed poster): one line added to the points: "Le logo recouvre bien son disque". When the found disc is under 125 px, a warning line: "Le sceau est petit : le nom du logo peut être difficile à lire."
- Neither is a new server check key.

**States of a scene.** No disc asked; disc asked and found; disc asked and not found. Stored once with the visual, never recomputed. Older visuals have NULL and behave as "no disc asked".

| Failure / edge | Handling |
|---|---|
| Disc asked, none found | Logo unticked on the poster with the message above; no export guard applies. If the model drew a disc that was not recognised, it stays visible in the image: the review line and "Aucun objet ni texte ajouté par l’IA" cover it. |
| Disc found, but the model drew something inside it | Usually the flood fails (not found). If found, the printed seal covers it. |
| Two discs drawn | The one reached from the seeds is used; the other is an added object for the review. |
| The model draws the price or the contact over the disc | The region is then not round: not found, logo unticked, message shown. |
| Found disc much smaller than asked (85–96 %) | The seal is printed at that size; the final screen warns under 125 px. Below 85 % it counts as not found. |
| The owner unticks the logo or drags it off the disc | `logo_disc_uncovered` blocks the final preview with the reason. Ticking again puts it back on the disc. |
| A logo that is not square | The circle shows the centre of the image scaled to cover the disc; the corners are cut. Stated in the option's help line. Transparency is lost on the white fill. |
| Logo file missing or unreadable at render | Existing `asset_missing` refusal (D-CATALOGUE-BRAND-002). |
| The shop name is ticked, the contact is unticked, not drawn or too long to be drawn, or the price is not drawn | The seal is not available for this poster (see "When the seal is available"); the option shows which condition is missing. The logo is a plain layer. |
| A plan whose regions differ from the fixed plan's (Claude or hand-edited, through the API) | `logo_seal` is refused: the disc's place assumes the fixed plan's bands. |
| A poster created before this change, or one that already has scenes | No seal; it keeps working as before. A copy of the poster can use the seal. |
| Provider failure, timeout, budget | Unchanged scene-job handling (D-GENERATION-JOBS-002/003). |

**External systems.** No new call and no new reference image: the logo file is never sent to the provider.

**Verification.**

- Unit tests for `find_disc` on generated images: a disc with a soft shadow on a gradient (found within 2 px); off-centre by 3 %; no disc; an oval; a disc touched by another white shape; a disc on pure white with and without a shadow; too small and too large; an exception inside is swallowed.
- The study's two real scenes with an empty disc, reduced copies in the test fixtures: both found at the positions measured in the study.
- Prompt tests: with `logo_seal` the prompt equals the prompt without it plus the badge sentence and the constraints wording; the disc centre for a left and a centred price; each refusal (no seal layer, price not drawn, contact not drawn or not at the right, shop name selected, regions not those of the fixed plan, and a plan revised only in its palette accepted); `logo_seal` omitted from dumps when unset; a seal logo left out of the plan's fields; refinement of a seal scene accepted.
- Store and guard tests: found, not found (logo unticked in the first-scene revision), uncovered (unticked, moved away, made smaller), covered after a move back.
- Renderer test: a `shape: "circle"` logo is clipped to a circle on white, covering its box.
- Browser smoke with the stub provider, which draws the asked disc when the prompt contains the badge sentence: the option is on for a new poster with a logo and locked after the first scene; the request carries `logo_seal` and `signature_align: "right"`; the seal lands on the disc; unticking the logo blocks the final preview with the reason; ticking again restores it.
- Paid, only with the user's go, with the real logo in the shop profile: one scene through the application with a left-aligned look (the chosen variant) and one with a centred look, about USD 0.42. For each: the disc's measured place and size, digits read, nothing touching the seal. A white look is a third, optional scene.
- Not covered: square and story formats, a real phone, non-fixed plans.

## Verification of D-004 and D-005

This list is what was verified for the v2.1 build (T-SIG-001 to 003: rendered contact and brand as plain text). The verification of D-004 v3 is at the end of its own section.

- Backend unit tests: `icon` accepted on the contact layer only; a stored document without `icon` keeps its canonical form and hash; `brand_text` wording, its refusal without a brand, and an unchanged idempotency body when it is absent; the ADR-043 prompt branch unchanged for a stored scene and its refinement.
- Renderer test (bundled Chromium, no spend): a contact with the compact style renders one line with the handset; measured digit height at least 22 px; left, centre and right positions with and without a logo; a too-long contact reports `text_fit`.
- Browser smoke (stub): a new poster has the shop name unticked and the contact compact; the position choice changes `align`, autosaves, undoes and survives a reload; the position survives a scene request (no forced centring); ticking the logo after the scene leaves logo and contact clear of each other; no signature is requested from the scene; the brand checkbox appears only with a brand.
- Paid: none for D-004. For D-005, one optional scene with `brand_text` on (about USD 0.21), only with the user's go.
- Not covered: square and story formats (T-POSTER-009), a real phone, contrast measurement.

## Verification / delivery boundary

Before this design is called implemented: validate input/price parsing, colour conversion without rembg, original hashes, all eight shop combinations, logo alpha/aspect ratio, stale profile saves, unauthorised assets, Origin checks, expired sessions and duplicate operation keys. Use synthetic fixtures offline; existing official product assets may be reused locally. No new paid calls are part of design approval.
