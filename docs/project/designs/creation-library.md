# DESIGN — creation-library

**Status:** Approved v1, 2026-11-09. **Approval:** ADR-031. **Requirements:** [creation-library](../requirements/creation-library.md), approved ADR-028; text/effect versions also cover ADR-030.

## System overview

SQLite stores immutable document revisions plus a small mutable creation pointer. Existing content-addressed files store source/scenes/textures; export PNG metadata is in poster_renders. No asset deletion API or automatic retention cleanup in the pilot. A saved draft is not a confirmed poster. Future profile/catalogue changes never mutate stored revisions.

## D-CREATION-LIBRARY-001 — Saves, history and recovery

**Covers:** R-CREATION-LIBRARY-001; R-POSTER-EDITOR-001/002/003.

**Data model:**

| Table | Contract |
|---|---|
| creations | UUID id, shop_id, parent_creation_id nullable FK, current_revision>=1, status active/abandoned, created_at/updated_at. No product/offer duplication outside its current document. |
| creation_versions | creation_id FK, revision positive integer, document_json, document_hash, created_at. PRIMARY KEY(creation_id,revision); immutable. Hash from server-normalised validated document, not arbitrary browser JSON order. |
| confirmations | Owned by format-export; binds exact revision + format + render/hash; retained across later saves. |
| mutation_keys | Shared idempotent mutation records, catalogue-brand contract. |

Every persisted document references existing same-shop product input, visuals, logo and text-effect assets. Same-variant matching by name is insufficient: a reused scene must reference the exact input_id. Persist only canonical fields (no temporary selection handles, pixel cache, provider credentials or local object URLs). No generic arbitrary JSON extensions. Unknown schema versions fail with document_version_unsupported; future version migrations are explicit and preserve the original record.

**API:**

| Endpoint | Input / output |
|---|---|
| POST /api/creations | Idempotency-Key; {input_id,offer,brand_selection,primary_format}; 201 {id,revision:1,document}. Copies current profile values and explicit inclusion flags. |
| GET /api/creations | Cursor pagination (created_at,id), limit<=50; summaries include product/variant/title/date/thumbnail/confirmation state. No raw original in list payload. |
| GET /api/creations/{id} | Current document, revision/ETag, recent jobs/candidates and confirmed versions. |
| PUT /api/creations/{id} | If-Match + Idempotency-Key; complete validated document → 200 next revision. |
| GET /api/creations/{id}/versions | Cursor list of saved/confirmed revisions; GET .../versions/{revision} returns immutable document. |
| POST /api/creations/{id}/abandon | If-Match + Idempotency-Key → status abandoned; 409 image_job_running if work is active. No asset/history deletion. |

PUT transaction: auth → idempotency replay → compare current_revision → validate all references/document → insert revision N+1 → conditional pointer update → store response → commit. If validated document hash is unchanged, return N without another history record. A retry after lost response returns the original result; the next save uses the returned latest revision. Client saves serially so a slow response cannot overwrite newer local edits. Undo is another save; it does not delete history.

**State / errors:** active creations may save/submit jobs; abandoned ones are read-only and can be duplicated. Saved revisions are immutable. Local dirty/saving/failed is editor state, not a false server status. A concurrent save → 409 with current_revision, preserving unsaved local document; user chooses reload or save copy. Never merge two price changes automatically. Session expiry offers login before retry with the same key; no durable offline promise.

| Failure / edge | Handling |
|---|---|
| DB unavailable/full | Roll back pointer and new revision; return 503; UI keeps unsaved edits. |
| Asset unavailable after save | Record remains readable; affected render/download reports asset_missing; never recreate it with AI. |
| Worker finishes against old revision | Candidate/result retained; no overwrite of current pointer. Initial-scene auto-composition is allowed only under the narrow unchanged-revision rule in product-visuals. |
| Two devices or repeated operation key | Revision conflict or replay; one atomic document version per accepted operation. |
| Input image/variant changes | Create new immutable product input and an explicit new draft; do not silently change input_id on an existing creation. |
| Profile changed after creation | Existing brand snapshot persists. Applying new profile is an explicit document edit with a new revision. |

**Retention/backups:** keep all referenced sources, scenes, effects, confirmed renders and revision documents. Unreferenced temporary spools may be cleaned after confirmed local finalisation; no general asset GC in V1. Before hosted pilot, use SQLite's consistent backup mechanism plus the content-addressed files and render/spool directories under a stopped/drained writer or verified manifest snapshot. Verify restoration of one draft and one exact-hash confirmed PNG. Encrypt/protect backups like the source data; no public file URLs. Backup schedule/host remains deployment work, not implicit authorisation to deploy.

## D-CREATION-LIBRARY-002 — Reuse without generation

**Covers:** R-CREATION-LIBRARY-002; R-GENERATION-JOBS-002 restart rule.

POST /api/creations/{id}/copies with Idempotency-Key, {source_revision,new_input_id?,reason:price_update|new_campaign|replace_input|save_conflict}. Server loads the exact source revision, checks access, creates a new creation linked by parent_creation_id, and snapshots its document. For save_conflict, a validated explicit unsaved_document may be supplied; never mistake a stale saved revision for the user's unsaved work. Neither operation copies confirmation records or queued jobs.

- Same input_id: approved visual and existing texture assets may be reused; price/title/shop edits require new poster confirmation but no image or planner call. Display old and new amount when changing price.
- Different/replaced input: clear visual/cutout references and framing checks, retain only user-chosen offer/brand/layout as editable starting values. Do not inherit fidelity approval; prompt for confirmed product facts/offer. No generated texture containing product imagery may be repurposed; text material swatches are reusable only as nonfactual decoration.
- New campaign from an abandoned draft can generate without a prior approved scene. The new draft gets its own three scene slots, but parent linkage and combined global ledger remain. No background auto-generation on copy.
- Existing confirmed PNGs remain downloadable under their original IDs even if the new draft is edited or abandoned.

Failures: source not accessible → 404; requested source revision absent → 404; stale/invalid unsaved document → 422 with field errors; missing asset → preserve copy intent, refuse use of that asset, no replacement spending. Copy creation is atomic/idempotent, so reconnect cannot produce multiple drafts.

## Verification

Test exact reopen/round trip, concurrent saves, lost-response replay, no-op saves, undo history, pending/rejected alternatives, same-input reuse with zero provider/planner calls, different-input approval clearing, eight identity snapshots, text-effect asset retention, missing files, abandoned drafts and combined-ledger restart. Exercise a backup/restore before hosted pilot. Migration tests must preserve every phase-1 table/ledger row and FK integrity; no migration file is created merely by this draft design.
