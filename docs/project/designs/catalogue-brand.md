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

## Verification / delivery boundary

Before this design is called implemented: validate input/price parsing, colour conversion without rembg, original hashes, all eight shop combinations, logo alpha/aspect ratio, stale profile saves, unauthorised assets, Origin checks, expired sessions and duplicate operation keys. Use synthetic fixtures offline; existing official product assets may be reused locally. No new paid calls are part of design approval.
