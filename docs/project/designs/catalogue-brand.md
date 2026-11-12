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

## D-CATALOGUE-BRAND-004 — Compact rendered contact with a position, logo-only identity

**Status:** Approved v2.1 by the user on 2026-11-12 ("approved, commit and go"; ADR-054). **Covers:** R-CATALOGUE-BRAND-003 as amended by ADR-053. Replaces draft v1, which drew the contact in the image and was returned REWORK ([round 1](../reviews/signature-design-r1-2026-11-12.md)). Round 2 returned APPROVE WITH FIXES ([round 2](../reviews/signature-design-r2-2026-11-12.md)); its fixes are in this text. Feed format only until T-POSTER-009.

**Principle.** The image model no longer draws the shop name or the contact in new scenes. The contact is the existing editable text layer, given a compact one-line style and written by the shared renderer, so its characters and size are exact. The scene leaves the footer calm, which the prompt already does for every field it does not draw ("Layout: these areas show only the calm backdrop").

**What changes for the owner.**

- In the "Textes" card, under "Boutique sur l’affiche": a choice "Position du contact" (Gauche, Centre, Droite), shown when "Contact" is ticked. It can be changed at any time, at no cost, and undone.
- The option "Dessiner aussi le nom de la boutique et le contact dans l’image" is removed from the editor.
- "Nom de la boutique" is unticked by default on a new poster: the logo identifies the shop, and without a logo the footer carries the contact only (user decision, ADR-053). The owner can still tick it; it is then an editable text layer above the contact, as today. This is a frontend default only (the intake form's initial selection); the backend already requires an explicit selection. It replaces "Default each available field on" in D-CATALOGUE-BRAND-002 for the shop name.

**Data.** No table and no migration. One optional field on text layers of the poster document, following the `price_badge` precedent (`Field(None, exclude_if=…)`, so stored documents, their hashes and their renders are unchanged):

| Field | Type | Rule |
|---|---|---|
| `icon` | `"phone" \| null` | Allowed only on the layer with role `contact` (422 `icon_requires_contact` otherwise). The shared canvas draws a telephone handset as a vector path at the start of the first line, in the layer's fill, as high as the digits, followed by a gap of half that height. Editor and server renderer use the same code (`frontend/src/canvas.ts`), so preview and PNG agree. |

The position is not a new field: it is the contact layer's existing `align` (`left`, `center`, `right`). The select reads and writes that property.

**Compact style.** One frontend function applies it to a one-line contact layer, in three places: right after a new poster is created (the server creates the layer at 24 px), when the owner uses the position choice, and when a contact layer becomes visible again on a poster whose earlier scene had drawn it. It sets: `font_id` noto-sans, weight 700 (the bundled Noto Sans has 400 and 700 only), `font_size` 32, `line_height` as today, `icon: "phone"`, no outline, no shadow, height 48 px. Bundled Noto Sans digits are about 0.71 em high, so 32 px gives digits of about 23 px on the 1080 × 1350 poster; a renderer test measures the drawn digit height and requires at least 22 px. The fill keeps today's rule (`stylePill`: white on the dark look, near-black on the others). Every property stays editable in "Réglages avancés".

**Layout.** No change to `fixed_plan`: the logo keeps the left of the footer and the text fields take the span to its right, as today. The contact layer is placed in that span on the first scene (`service.py`, unchanged) and `align` positions the line inside it: against the logo, centred in the span, or at the right margin. With a logo, "Centre" is therefore centred in the free span, not on the poster's axis; this is stated in the control's help line. Later scenes do not move layers, and nothing in a scene depends on the position, so the round-1 overlap finding does not arise.

Default for a new poster: `right` when the logo is included, `center` otherwise (ADR-053). The last choice on the device (`affiche.style`) wins over the default; the position choice saves it there itself, because today that entry is only written when a scene is requested.

Two existing behaviours must change for this to hold:

- `stylePill` forces `align: 'center'` on the shop-name and contact layers each time a scene is requested. It stops setting `align` (it keeps setting the fill).
- A logo ticked after the first scene is created at the bottom right, or comes back in its old box, while the contact keeps the full width. Ticking the logo therefore places it at the left of the footer and gives the contact layer the span to its right, with the same numbers as `fixed_plan`. Unticking it gives the contact the full width back.

**Scene request.** The editor stops sending `headline.signature: true`. The API still accepts it and the ADR-043 branch of `compile_scene` is left untouched, so stored scenes, their refinements and replayed requests behave as before. No `signature_align`, no `PlanContext` change.

**Old posters.** A poster whose current scene drew the contact (its stored headline has `contact`) keeps its hidden layer and its guards. For it the position choice is disabled with the reason "Le contact est dessiné dans cette image : générez une nouvelle version pour le déplacer." A new version of that poster follows the new rule: when the owner chooses the new version, `chooseVisual` shows the contact layer again (the first-scene placement does not run a second time), and the compact style is applied to it then, so its digits meet the 22 px minimum.

**States.** None new. A position or contact edit is an ordinary document revision: autosaved, undoable, no provider call, no change to the scene's fidelity status. A confirmed poster stays confirmed; a changed draft needs a new final preview, as for any edit (`preview_stale`).

| Failure / edge | Handling |
|---|---|
| The contact does not fit on one line at 32 px in the free span | The blocking issue `text_fit` ("Le texte dépasse son cadre…") appears in the editor at once and blocks the final preview. No paid call is involved. The owner shortens the contact or unticks the logo. This needs two changes in `canvas.ts`, where today only the price is non-wrapping and width-checked: a layer with `icon` is also non-wrapping, and its width check measures the line plus the handset and its gap. Without them a long contact would be cut silently. |
| The contact has several lines in the profile | The compact style is not applied; the layer stays as today (multi-line, no icon) and the position choice only sets `align`. One-line contact is the supported case (requirement: multiple lines out of scope). |
| No contact selected | No layer is shown and nothing is drawn; no placeholder. |
| The contact colour has poor contrast on a generated backdrop | Not measured. It is visible on the canvas and in the final preview; the fill is editable; "Tous les éléments sont lisibles" is part of the final agreement. |
| The owner drags the logo over the contact | The existing non-blocking overlap warning between layers appears and is listed on the final screen. Both are layers now, so the code sees it. |
| The scene draws something in the footer band | Not detected by code; "Aucun objet ni texte ajouté par l’IA" at the fidelity review. |
| A font without the digits or punctuation typed | Existing glyph warning. The handset is a path, not a glyph, so it needs no font. |
| Profile contact changed later | Unchanged: the poster keeps its snapshot; applying the new profile is an explicit edit, free of charge. |

**External systems.** None involved. No prompt wording changes for new scenes except that the signature sentence is no longer requested; no paid trial is needed for this section.

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

## Verification of D-004 and D-005

- Backend unit tests: `icon` accepted on the contact layer only; a stored document without `icon` keeps its canonical form and hash; `brand_text` wording, its refusal without a brand, and an unchanged idempotency body when it is absent; the ADR-043 prompt branch unchanged for a stored scene and its refinement.
- Renderer test (bundled Chromium, no spend): a contact with the compact style renders one line with the handset; measured digit height at least 22 px; left, centre and right positions with and without a logo; a too-long contact reports `text_fit`.
- Browser smoke (stub): a new poster has the shop name unticked and the contact compact; the position choice changes `align`, autosaves, undoes and survives a reload; the position survives a scene request (no forced centring); ticking the logo after the scene leaves logo and contact clear of each other; no signature is requested from the scene; the brand checkbox appears only with a brand.
- Paid: none for D-004. For D-005, one optional scene with `brand_text` on (about USD 0.21), only with the user's go.
- Not covered: square and story formats (T-POSTER-009), a real phone, contrast measurement.

## Verification / delivery boundary

Before this design is called implemented: validate input/price parsing, colour conversion without rembg, original hashes, all eight shop combinations, logo alpha/aspect ratio, stale profile saves, unauthorised assets, Origin checks, expired sessions and duplicate operation keys. Use synthetic fixtures offline; existing official product assets may be reused locally. No new paid calls are part of design approval.
