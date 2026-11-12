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

## D-CREATION-LIBRARY-003 — Manage posters from "Mes affiches"

**Status:** Approved v2.1 by the user on 2026-11-12 (ADR-061), after two review rounds and the devil's advocate ([findings](../reviews/library-manage-design-r1-2026-11-12.md)). **Covers:** R-CREATION-LIBRARY-003 (approved, ADR-060).

**What exists (checked in the code on 2026-11-12):** `creations.status` is `active` or `abandoned`; `POST /api/creations/{id}/abandon` (If-Match, Idempotency-Key, 409 `image_job_running`); `POST /api/creations/{id}/copies` with `reason: "new_campaign"`; a save on an abandoned creation is refused (`creation_abandoned`). `GET /api/creations` pages by `(created_at, id)` with `limit <= 50` and returns every status. There is no route back from `abandoned`.

**Data model:** no schema change and no migration. "Retirer de la liste" is the existing `abandoned` status. The row state is computed at read time, never stored:

| `state` | Rule, first match wins |
|---|---|
| `to_review` | a visual with status `pending_review` exists that was made for this creation (its job's `creation_id`), whether or not the document has chosen it; or the visual named by the current document's feed scene is `pending_review` (a copy can name a waiting version made in its source) |
| `confirmed` | a `confirmations` row exists for the creation's current revision (`confirmed_revision = current_revision`): the confirmed file is the poster as it is now (user decision, ADR-061) |
| `approved` | the visual named by the current document's feed scene has status `approved` |
| `draft` | anything else (no version, or only rejected ones) |

Why this order (v2): only the first version is placed in the document by the server; later versions wait outside it until chosen, so "a version waits for the review" cannot be read from the document alone. `to_review` comes first because it is the one state that asks the operator to act. A confirmed poster edited afterwards no longer says "Confirmée": it falls back to "Approuvée" (or "À vérifier") until it is confirmed again, and its earlier file stays downloadable from the poster. Versions made in a copy of the poster do not count for the source's row, although the editor lists them under the same product: the row describes the poster, not the product.

**API:**

| Endpoint | Change |
|---|---|
| `GET /api/creations` | New query `status=active` (default) or `abandoned`. Each item gains `state` (above); `status`, `revision`, `price_ar`, `created_at`, `thumbnail_url` stay. The response gains `total`: the count of the shop's creations with the asked status, independent of the page. Default page size stays 20; the editor asks for 50 and follows `next_cursor`. |
| `POST /api/creations/{id}/abandon` | Unchanged. |
| `POST /api/creations/{id}/restore` | New. If-Match + Idempotency-Key, same shape as abandon: sets `status='active'`, returns the creation. On an active creation it returns 200 unchanged (restoring twice is not an error). |
| `POST /api/creations/{id}/copies` | One change: for `reason: "new_campaign"` the copy is refused with 409 `revision_conflict` when `source_revision` is not the creation's current revision, so a stale row cannot silently copy an old price. `save_conflict` keeps copying the revision it names (that is its purpose). The editor sends `{source_revision: <row revision>, reason: "new_campaign"}`. Works on an abandoned source (D-CREATION-LIBRARY-002). |

Breaking change for the only client: the default list no longer contains abandoned creations. The editor is the only caller.

**Editor:**

- Each row keeps its "open" button and gains a state label in words and two actions: "Dupliquer" and "Retirer de la liste". They are separate buttons beside the row's open button, not nested inside it.
- "Retirer de la liste" opens the existing confirmation sheet, naming the poster's title, with the text that nothing is erased, that a confirmed file is kept, and that the poster must be put back in the list to open it or download its file again. No cost line.
- Idempotency keys: abandon, restore (and, for styles, rename and remove) are safe to repeat, so the editor sends a new key on every attempt and never reuses a kept one; otherwise "retirer, remettre, retirer" would replay the first stored answer without doing anything. Only "Dupliquer" keeps its key across a retry, so a lost response cannot create two copies. The list is reloaded after every action, successful or refused.
- "Dupliquer" asks nothing, creates the copy and opens it in the editor.
- A switch "Afficher les affiches retirées" replaces the list by the abandoned ones (a second request with `status=abandoned`); their rows offer "Remettre dans la liste" and "Dupliquer" only, and cannot be opened for editing.
- "Voir plus" appears while `next_cursor` is not null and appends the next page. The navigation count is `total` of the active list.
- An abandoned poster reached by its address (`#<id>`) is not opened: the editor goes to "Mes affiches" with the removed ones shown and says why. This avoids an editor in which every save is refused.

**State / errors:**

| Case | Handling |
|---|---|
| Image job queued or running | abandon → 409 `image_job_running`; message "Une génération est en cours pour cette affiche : attendez sa fin." The row does not change. |
| Row stale (poster saved elsewhere since the list was loaded) | abandon, restore or duplicate → 409 `revision_conflict`; the list is reloaded and the operator is told to try again. |
| A plan or a style job is in flight when the poster is removed | Allowed: 409 `image_job_running` covers image jobs only (scene, refinement, text material). The other job finishes and its result is stored as usual; nothing is lost. |
| Poster already abandoned or restored in another tab | Same request replayed with a new key and the old revision: abandon on an abandoned creation and restore on an active one both return 200 unchanged; the list is reloaded. |
| Network or server failure | The row stays and the general error message offers to retry. A retry of "Dupliquer" reuses its Idempotency-Key, so a lost response cannot create two copies; a retry of abandon or restore sends a new key (see "Idempotency keys"). |
| Copy of a poster whose asset file is missing | Existing behaviour: the copy is refused with the asset error; nothing is regenerated. |
| Not the shop's poster, or unknown id | 404, as today. |

**Money:** none of these routes calls a provider or touches the ledger. A copy starts with the source's approved version and costs nothing until the operator asks for a new version, which has its own confirmation.

**Security:** all routes are on the protected router (shop session, Origin check); ownership through the existing `_owned` lookup. `status` is a closed set validated by the route.

## D-CREATION-LIBRARY-004 — Manage saved styles

**Status:** Approved v2.1 by the user on 2026-11-12 (ADR-061), after two review rounds and the devil's advocate ([findings](../reviews/library-manage-design-r1-2026-11-12.md)). **Covers:** R-CREATION-LIBRARY-004 (approved, ADR-060).

**What exists:** table `looks` (migration 0010: id, shop_id, job_id, name, reference_asset, brief_json, source, created_at), `GET /api/looks`, `GET /api/looks/{id}`, creation through a planner job on an open poster, at most 24 per shop. A scene stores the `look_id` it was made with, and a refinement of that scene reads the look again by id for its typography and alignment (`visuals.look_style`).

**Data model:** migration 0011, forward only: `ALTER TABLE looks ADD COLUMN removed_at TEXT` (NULL = in use). A removed look is kept as a row because old versions refer to it and their refinements still read its brief; only the lists hide it. No row and no asset is deleted.

- Name rule: 1 to 40 characters after trimming (the existing `LookRequest` rule). Among the shop's looks that are not removed, a name is unique without regard to case. The comparison is done in Python (`casefold`) inside the same write transaction as the change: SQLite folds ASCII only and would treat "Été" and "été" as different. The look being renamed is left out of the comparison, so a retried rename and a change of case only are accepted. No database constraint, because existing data may already hold two equal names and an applied migration must not fail on them.
- The three supplied styles exist only in the editor. The editor refuses a rename to one of their labels; the server does not know them, and a clash there is cosmetic.
- The limit of 24 counts only looks that are not removed.

**API:**

| Endpoint | Contract |
|---|---|
| `GET /api/looks` | Returns only looks that are not removed. |
| `GET /api/looks/{id}` | Returns the look whether removed or not, with `removed_at` (null or a timestamp). Needed to reopen a poster made with a removed look. |
| `PUT /api/looks/{id}` | New. Idempotency-Key; body `{name}`; 200 with the look. Refusals: 422 `validation_error` with field `body.name` (empty or too long; the existing shape of a refused body), 409 `look_name_taken` (field `name`), 409 `look_removed`, 404. |
| `DELETE /api/looks/{id}` | New. Idempotency-Key; sets `removed_at`; 200 with the look. Removing an already removed look returns 200 unchanged. 404 for another shop's or an unknown id. |
| `POST /api/creations/{id}/looks` | Unchanged request. A creation never fails on its name: when the job stores the look and the name is taken, the server stores it under the first free "name (2)", "name (3)"…, shortening the name so that the whole stays within 40 characters. One rule, applied at the only moment the name is written, so a paid brief is never lost to a name clash and the editor's default name ("Style 3") cannot be refused. |
| `POST /api/creations/{id}/scenes` | Unchanged: a `look_id` of a removed look is accepted, because the look is still stored (see "Reopening"). |

No revision on a look: there is one operator, and a rename is the last write. Two tabs renaming the same look end with the later name; neither loses anything else.

**Editor ("Styles" page):**

- Every card is a button that opens a panel (the same dialog pattern as the review: focus, Escape, page behind inert) with the model poster in large, the name, and the description in words: ambiance (`direction_fr`), surface, the palette as swatches with their colour codes, and the alignment (left or centre). Opening costs nothing and calls no provider.
- For a look created by the shop the panel offers: "Renommer" (a field with the error beside it), "Retirer ce style" (confirmation sheet naming the style and saying it cannot be undone and that posters made with it keep working), and "Créer une affiche avec ce style" (goes to the new-poster screen with the style chosen and remembered as today).
- For the three supplied styles the panel shows the picture and the ambiance text, offers only "Créer une affiche avec ce style", and says "Style fourni : il ne peut pas être renommé ni retiré."
- After a rename or a removal the editor reloads `GET /api/looks`. If the removed look was the remembered one on this device, the remembered style falls back to "Studio clair".

**Reopening a poster made with a removed look (changed in v2):** the version's `look_id` is not in the list; the editor reads `GET /api/looks/{id}`, shows "Décrire moi-même" as the choice with the look's ambiance and accent colour filled in, and one line: "Le style « name » a été retiré : cette affiche le garde." The editor keeps the removed look's id and brief for this poster: a new version (for example after a price change, which needs a new scene) is asked with the same `look_id` and the same palette, surface, lighting and camera, so it is the same poster. The link is dropped only when the operator edits the ambiance or picks another style; the next version then follows what he chose. A removed look can therefore not be picked for another poster, but a poster that has it does not lose it. The removal confirmation can then truthfully say that posters made with the style keep it.

How the editor holds it, so that it cannot leak: the kept look is a state of its own, bound to the open poster's id and cleared whenever a poster is opened or left (`adopt`, `fresh`). It is never put in the chosen style (`look` stays "Décrire moi-même") nor in the list of saved styles, so the picker cannot show it and the style remembered on the device is "Décrire moi-même" with its ambiance text, as for any hand-written ambiance. Three places read it when present: the scene request (the `look_id` sent), the plan's palette, surface, lighting and camera, and the ambiance field, whose first edit drops the link. Result to expect and test: after a new version on such a poster, the next new poster starts from "Décrire moi-même" with that ambiance and without the removed look's typography.

**State / errors:**

| Case | Handling |
|---|---|
| Rename empty, too long, or name taken | Refused before any change; the message is written beside the field; the old name stays. |
| Rename or removal fails (network, server) | The style stays as it was; error with retry. The retry sends a new Idempotency-Key: both actions are safe to repeat, and a rename to the name the look already has succeeds unchanged. |
| Style removed in another tab while its panel is open here | Rename → 409 `look_removed`; the panel closes, the list reloads, the operator is told. |
| A style-creation job finishes into a taken name | Stored under the first free numbered name (rule in the API table). |
| Scene asked with a removed `look_id` | Accepted (see "Reopening"). The first draft refused it; that would have made a paid new version of an old poster lose its style, and the refusal came after a plan that can itself be paid. |
| Poster open on a version made with the look being removed | Allowed. Nothing in that poster changes; see "Reopening" above for what the style block shows next time. |

**Money:** rename, removal and opening are free and never reach the planner or the image provider. The one paid path, creating a look, is unchanged and keeps its confirmation.

**Security:** protected router; ownership through `_owned("looks")`; the name goes through the existing `LookRequest` string rule. A look's name is only ever shown as text and is never part of a prompt (a scene request names a look by id).

## Tasks (in TODO.md as T-LIB-001 to 004)

1. Server, posters: `status` filter, `state`, `total` on the list; `restore` route; stale-revision refusal for a `new_campaign` copy; tests for the four states (including a waiting version that the document has not chosen), the filter, restore, conflict and replay.
2. Editor, posters: row state and actions, removed view, "Voir plus", real total, abandoned poster reached by address; smoke steps.
3. Server, styles: migration 0011, rename and remove routes, list filter, limit and name rule (`casefold`), free numbered name when a look is stored; tests.
4. Editor, styles: panel, rename, remove, "create with this style", reopening with a removed look; smoke steps.

## Verification

Test exact reopen/round trip, concurrent saves, lost-response replay, no-op saves, undo history, pending/rejected alternatives, same-input reuse with zero provider/planner calls, different-input approval clearing, eight identity snapshots, text-effect asset retention, missing files, abandoned drafts and combined-ledger restart. Exercise a backup/restore before hosted pilot. Migration tests must preserve every phase-1 table/ledger row and FK integrity; no migration file is created merely by this draft design.
