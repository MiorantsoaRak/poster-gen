# DESIGN — product-visuals

## System overview

**Status:** Draft r4 (after Codex r1 + r2 + r3 and the devil's-advocate pass; see `../reviews/`). User decisions UQ-1 … UQ-5 applied 2026-11-06 (ADR-011). Codex r3 fixes applied; final narrow r4 (authorised by the user) → APPROVE WITH FIXES; its 3 fixes applied 2026-11-06. No further review rounds.
**Requirements file:** [../requirements/product-visuals.md](../requirements/product-visuals.md) (R-PRODUCT-VISUALS-001 … 008, approved 2026-11-06; R-003 c.1–2, R-004 c.2 and R-005 amended 2026-11-06, ADR-011)
**Approval record:** **Approved for phase 1 by the user on 2026-11-06** ("go ahead"; ADR-012). Phase-2 contracts in this file stay draft until design v2.

```
 Phase 2: Vue (phone/desktop)       FastAPI process (owner = "api")                       Outside
 ────────────────────────────       ─────────────────────────────────────────────          ─────────────
 Direction ─┐                       api/visuals ──▶ visuals service ──▶ ImageGateway ───▶ OpenAI Images API
 Review     ├─ HTTPS JSON + cookie ▶     │              │   (logical request: reservation,
 Reject     │   + polling           assets API          │    allowance, guards; provider
 Cutout ────┘                            │              │    calls: retry, error mapping, cost)
                                         ▼              ├──▶ cutout (rembg, local CPU, thread pool)
 Phase 1: CLI (owner = "cli")       asset store         ├──▶ fixture catalogue (CSV)
 evaluate generate|sheet|apply|     (files by sha256)   └──▶ SQLite (SQLAlchemy + Alembic)
          report|new-cycle ── same service, same gateway, same budget
```

### Phasing and approval boundary

| Phase | Content | Starts when |
|---|---|---|
| 1 | Domain and state machines, gateway (stub + OpenAI), cutout, fixture loader, CLI (batch generate, contact sheet, decisions CSV, report) | This design is approved |
| — | Paid evaluation (R-008) | Phase 1 done + fixture photos + `OPENAI_API_KEY` + `SPEND_CAP_USD` |
| 2 | HTTP API + Vue screens (phone review per R-004). The contracts below are a **draft**. | The user approves the evaluation recommendation, and design v2 records the chosen defaults and the phase-2 transport/session design |

In phase 1 the evaluation reviews happen in a desktop browser (the contact sheet). The phone review experience required by R-004 is delivered and verified in phase 2. Both paths call the **same service functions**, so every state rule is built and tested once.

### Decided in this design (reviewers agreed; the user may override)

- **SQLite** (WAL, `busy_timeout = 5000` ms) via SQLAlchemy 2 + Alembic, forward-only migrations. `# ponytail: single writer; move to PostgreSQL for several API processes or several shops.`
- **Requests run in the process that created them** (asyncio task in the API, inline in the CLI) until generation-jobs is designed. That design must take over `generation_requests`.
- **One logical request owns:** idempotency, retries, the attempt slot and the concurrency guards (Codex r2 simplification).
- **No cancel endpoint.** A provider call cannot be stopped and may be billed.
- **Stub and paid data never mix:** the DB records its provider mode on first use (`meta.provider_mode`). Starting with the other mode is refused ("use another `DATA_DIR`").

### Stack (versions are checked at scaffold time, not trusted from this file)

| Need | Choice | Check |
|---|---|---|
| Python | 3.12, managed with **uv** (`pyproject.toml`, `uv.lock`, `.python-version`) | rembg 2.0.74 declares `>=3.11,<3.14` (PyPI). On the user's PC (2026-11-06): Python 3.12 and 3.13 installed, uv 0.11.8. |
| Provider | `openai` SDK, **async** client | Verify methods, multipart, exception classes and error fields on the installed version (T-PV-003). |
| Cutout | `rembg[cpu]` | Pick the model from the installed version's list. BiRefNet names changed between releases. |
| Image ops | Pillow (pulled in by rembg) | — |
| Phase 2 | Vue 3 + vue-router; `messages.fr.ts` | `# ponytail: vue-i18n when Malagasy is added.` |

---

## D-PRODUCT-VISUALS-001 — Data model and asset store  (covers R-002, R-005, R-006, R-007, R-008)

```sql
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);   -- provider_mode = 'stub' | 'openai'

CREATE TABLE assets (
  sha256 TEXT PRIMARY KEY, mime TEXT NOT NULL, width INTEGER NOT NULL, height INTEGER NOT NULL,
  bytes INTEGER NOT NULL, created_at TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('original','style_ref','provider_input','scene','background_raw','background','cutout'))
);

CREATE TABLE runs (                         -- immutable run configuration (Codex r2: no mixing under one label)
  label TEXT PRIMARY KEY, model TEXT NOT NULL, quality TEXT NOT NULL, size TEXT NOT NULL,
  attempt_limit INTEGER NOT NULL CHECK (attempt_limit BETWEEN 1 AND 5),       -- 4–5: ADR-011 evaluation only
  corrections_mode TEXT NOT NULL CHECK (corrections_mode IN ('on','by_arm')),   -- by_arm: ADR-011, CLI runs only
  created_at TEXT NOT NULL,
  UNIQUE (model, quality)     -- Codex r3: a new label for the same config must not grant a fresh allowance
);                            -- estimates are not here: they apply prospectively (D-PV-003 rule 6)

CREATE TABLE run_products (                  -- snapshot at `generate`; later commands never re-read the CSV for these
  run_label TEXT NOT NULL REFERENCES runs(label), variant_ref TEXT NOT NULL,
  arm TEXT CHECK (arm IN ('A','B')), fixture_row_sha256 TEXT NOT NULL,
  PRIMARY KEY (run_label, variant_ref)
);                                           -- amended: + name, variant (migration 0002, ADR-018, user decision)

CREATE TABLE abandonments (                  -- explicit "abandoned" outcome (R-008 c.2)
  variant_ref TEXT NOT NULL, run_label TEXT NOT NULL REFERENCES runs(label), cycle_no INTEGER NOT NULL,
  treatment TEXT NOT NULL CHECK (treatment IN ('scene','photo_preserved')),
  note TEXT, created_at TEXT NOT NULL,
  PRIMARY KEY (variant_ref, run_label, cycle_no, treatment)
);

CREATE TABLE variant_cycles (                -- ADR-011: "Nouvelle campagne"; no row = cycle 1
  variant_ref TEXT PRIMARY KEY, cycle_no INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE cutouts (
  id TEXT PRIMARY KEY, variant_ref TEXT NOT NULL, run_label TEXT NOT NULL REFERENCES runs(label),
  direction_json TEXT NOT NULL,              -- kept for the background request (CSV replay)
  source_asset TEXT NOT NULL REFERENCES assets(sha256),
  cutout_asset TEXT REFERENCES assets(sha256),          -- RGBA, A ∈ {0,255}, same size as the oriented source
  bbox_json TEXT,
  status TEXT NOT NULL CHECK (status IN ('proposed','confirmed','rejected','failed')),
  failure_reason TEXT CHECK (failure_reason IN ('no_product','multiple_products')),
  low_res_warning INTEGER NOT NULL, rembg_model TEXT NOT NULL, created_at TEXT NOT NULL, decided_at TEXT,
  cycle_no INTEGER NOT NULL                  -- a cutout belongs to one scope (variant, cycle, run); Codex r4
);

CREATE TABLE generation_requests (           -- one LOGICAL request
  id TEXT PRIMARY KEY,                        -- client UUID (UI) or deterministic uuid5 (CLI apply)
  payload_hash TEXT NOT NULL,                 -- sha256 of the canonical payload
  purpose TEXT NOT NULL CHECK (purpose IN ('scene','background')),
  variant_ref TEXT NOT NULL, cycle_no INTEGER NOT NULL,
  run_label TEXT NOT NULL REFERENCES runs(label),
  parent_id TEXT REFERENCES candidates(id),   -- set for a revision (scene or background)
  cutout_id TEXT REFERENCES cutouts(id),      -- set for every background
  request_json TEXT NOT NULL, corrections_applied INTEGER NOT NULL,
  owner TEXT NOT NULL CHECK (owner IN ('api','cli')),
  status TEXT NOT NULL CHECK (status IN ('running','succeeded','failed','interrupted')),
  error_kind TEXT, candidate_id TEXT REFERENCES candidates(id),
  created_at TEXT NOT NULL, finished_at TEXT,
  CHECK ((purpose = 'background') = (cutout_id IS NOT NULL))
);
-- Guards: a request row stays 'running' through its retries, so these hold across retries (Codex r2).
-- Together they make each (variant, cycle, run, purpose) one linear chain: one live/succeeded initial
-- request, then only revisions of a rejected candidate, one live/succeeded revision per parent (R-002 c.2).
CREATE UNIQUE INDEX req_one_revision ON generation_requests(parent_id)
  WHERE parent_id IS NOT NULL AND status IN ('running','succeeded');
CREATE UNIQUE INDEX req_one_initial ON generation_requests(variant_ref, cycle_no, run_label, purpose)
  WHERE parent_id IS NULL AND status IN ('running','succeeded');
CREATE INDEX req_allowance ON generation_requests(variant_ref, run_label, purpose, cycle_no, status);

CREATE TABLE provider_calls (                 -- one row per invocation (retry = call_no 2)
  id TEXT PRIMARY KEY, request_id TEXT NOT NULL REFERENCES generation_requests(id),
  call_no INTEGER NOT NULL CHECK (call_no IN (1,2)),
  provider TEXT NOT NULL, model TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('running','succeeded','failed','interrupted')),
  error_kind TEXT CHECK (error_kind IN ('refused','quota','budget_exhausted','timeout','rate_limited',
                        'provider_error','invalid_request','invalid_response','auth','storage','interrupted')),
  error_detail TEXT, usage_json TEXT, raw_asset TEXT REFERENCES assets(sha256),
  cost_micros INTEGER NOT NULL CHECK (cost_micros >= 0), cost_is_estimate INTEGER NOT NULL,
  started_at TEXT NOT NULL, finished_at TEXT,
  UNIQUE (request_id, call_no)
);
CREATE INDEX calls_budget ON provider_calls(started_at);

CREATE TABLE candidates (
  id TEXT PRIMARY KEY, variant_ref TEXT NOT NULL, cycle_no INTEGER NOT NULL,
  subject_name TEXT NOT NULL, subject_variant TEXT NOT NULL,
  treatment TEXT NOT NULL CHECK (treatment IN ('scene','photo_preserved')),
  status TEXT NOT NULL CHECK (status IN ('pending_review','approved','rejected')),
  request_id TEXT NOT NULL UNIQUE REFERENCES generation_requests(id),
  parent_id TEXT REFERENCES candidates(id),
  attempt_no INTEGER NOT NULL,                -- scene: position in the variant's allowance; photo_preserved: 1, 2, …
  direction_json TEXT NOT NULL, source_assets_json TEXT NOT NULL,
  prompt TEXT NOT NULL, corrections_applied INTEGER NOT NULL,
  provider TEXT NOT NULL, model TEXT NOT NULL, quality TEXT NOT NULL, size TEXT NOT NULL, run_label TEXT NOT NULL,
  image_asset TEXT NOT NULL REFERENCES assets(sha256),
  cutout_id TEXT REFERENCES cutouts(id), product_box_json TEXT,
  low_res_warning INTEGER NOT NULL,
  framing_checked INTEGER,                    -- set at approval, both treatments (R-002 c.4, R-004 c.2)
  rejection_reasons_json TEXT, rejection_note TEXT,
  created_at TEXT NOT NULL, reviewed_at TEXT,
  CHECK ((treatment = 'photo_preserved') = (cutout_id IS NOT NULL))
);
CREATE INDEX candidates_variant ON candidates(variant_ref, treatment, cycle_no, status);
```

**Asset store:** `put(bytes)` writes `tmp` → `fsync` → `os.replace` to `data/assets/<2 hex>/<sha>.<ext>`. It does nothing if the hash exists. Orphan files are harmless. `# ponytail: no GC; add a sweep when disk use matters.`

**Single process per owner (Codex r3):** the CLI holds an **OS lock** on `data/cli.lock` for its whole lifetime (`msvcrt.locking` on Windows, `fcntl.flock` elsewhere); the API does the same on `data/api.lock`. The OS releases the lock when the process exits or crashes, so a stale file never blocks a restart. If the lock is held, the process refuses and says another one is running.

**Crash recovery** (only after taking the lock): the process marks its own owner's (`api` or `cli`) `running` requests and their running calls (call 1 or call 2) as `interrupted`. Their cost stays at the reserved estimate. Interrupted requests leave the guard indexes, and nothing is regenerated automatically.

**Configuration validation at startup** (refuse to start on error):
- `SPEND_CAP_USD` > 0 and finite;
- `SPEND_CAP_SINCE` ≤ today (UTC);
- estimates > 0;
- `ATTEMPT_LIMIT` ≥ 1;
- `meta.provider_mode` = `IMAGE_PROVIDER`.

A budget sum over an empty ledger is 0 (`COALESCE`).

---

## D-PRODUCT-VISUALS-002 — Direction and building the request  (covers R-001, R-003)

```python
def build_scene_prompt(subject: SceneSubject, direction: Direction,
                       corrections: list[ReasonCode] | None, note: str | None) -> str
def build_background_prompt(direction: Direction,
                            corrections: list[ReasonCode] | None, note: str | None) -> str
def find_commercial_terms(text: str) -> list[str]
```
- `SceneSubject(name, variant)` only. Catalogue price, warranty, promo and facts never reach the builders, because the type has no field for them.
- **Direction:**
  - `mood` ∈ `neon|pastel|studio|lifestyle|minimal|None`;
  - `intent` ∈ `promotion|nouveaute|benefice|None`, mapped to a fixed atmosphere phrase, never to words in the image;
  - `description` ≤ 500 chars;
  - `style_ref`;
  - `is_default` = no mood, description or style_ref → the "studio, soft even light" default.
- **Fixed instruction block** (scene):
  1. Image 1 is the product. Keep it exactly as photographed: shape, colour, camera layout, buttons, ports, **and every marking printed on it** (brand logo, labels, camera-module text).
  2. **Do not add** any text, numbers, prices, badges, logos or watermarks to the scene. Only markings already printed on the product may appear.
  3. One product only; no added devices or accessories.
  4. Vertical 9:16; the product centred, fully visible, about `PRODUCT_HEIGHT_RATIO` (0.40) of the height, with clear space above and below.
- **Background block:** an empty product-photography scene, a surface in the lower-middle area, no product, no people, nothing written.
- **Corrections:** reason codes map to fixed sentences. Scene: `cameras → "The camera layout must match image 1 exactly."`. Background: `integration → "Match a neutral, soft front light and an eye-level camera angle."`, `extra → "Remove all objects from the surface."`. The note is added as `"Shop's correction note (French): …"`. Codes with no background meaning (`coloris`, `logo`, …) add no sentence to a background prompt.
- **Free-text screening** (description and correction note). This is best effort, as amended R-003 c.1 says (ADR-011):
  - case- and accent-insensitive;
  - currency words `ar|ariary|mga|euros?|dollars?|€|\$`;
  - `%`;
  - any number with ≥ 4 digits (spaces, dots and commas ignored);
  - stems `garanti|livr|remise|r[ée]duc|sold|promo|offert|gratuit|prix|cr[ée]dit|paiement|cadeau`.
  - A match → 422 `commercial_terms {field, matches}`. The UI says: "Les prix, remises, garanties et livraisons se mettent dans l'éditeur. Pour une promotion, utilisez « Intention »."
  - A blocklist cannot be complete. The remaining protection is instruction 2 and the review checklist.
- **Style reference upload:**
  ```
  POST /api/visuals/style-references   multipart: file
  201 { asset, width, height } | 413 too_large {max_bytes: 10485760}
  415 unsupported_type {accepted: jpeg/png/webp} | 422 not_an_image (Pillow decode, MAX_IMAGE_PIXELS = 40_000_000)
  ```
- **Tests:**
  - catalogue price, warranty and promo strings never appear in either prompt;
  - the screen matches `1 200 000 Ar`, `-20 %`, `500 euros`, `livré demain`, `Garantie 6 mois`;
  - the screen does not match `iPhone 15`, `128 Go`, `5G`, `lumière pastel`, `3 caméras`;
  - every reason code has a sentence or is explicitly ignored, for each prompt type.

---

## D-PRODUCT-VISUALS-003 — Requests, provider calls and the gateway  (covers R-002, R-005 c.3, R-008)

**Preflight (before any spend):**
```
GET /api/visuals/variants/{variant_ref}
200 { name, variant, cycle_no, attempts_used, attempt_limit, pending_review: bool,
      photos: [{ asset, width, height, low_resolution }] }
```
`low_resolution` = short edge of the EXIF-oriented photo < `MIN_SOURCE_SHORT_EDGE` (800). Any request (scene or cutout) using such a photo must include `acknowledged_warnings: ["low_resolution"]`, else 409 `warning_not_acknowledged`. The CLI asks once per product.

**Creating a logical request: one `BEGIN IMMEDIATE` transaction** (shared by the API and CLI processes; SQLAlchemy/pysqlite must actually emit it, which T-PV-001 verifies with a two-process test). Inside it:
1. **Idempotency:** the same `id` with the same `payload_hash` → return the existing request; with a different hash → 409 `request_id_reused`.
2. **Photos belong to the variant** (scene and cutout), else 422 `photo_not_in_variant`.
3. **Scope rules** (R-002 c.2, R-005), scoped to **(variant, cycle, run)**. A run is one (model, quality) pair (`UNIQUE` in `runs`), so a new label cannot reset the count:
   - **abandoned** scope (`abandonments` row for this treatment) → 409 `abandoned`;
   - **initial request** (no parent): refused if the scope already has a running or succeeded initial request of this purpose (`req_one_initial`). The message is 409 `review_pending` ("Vérifiez d'abord le visuel en attente") if that chain has a pending candidate or a running request, else 409 `use_revision` ("Rejetez puis révisez le visuel ; la note peut changer le style");
   - **scene allowance:** `used = COUNT(scene requests, variant, cycle_no, run_label, status IN ('running','succeeded'))`; `used ≥ run.attempt_limit` → 409 `attempt_limit_reached {fallback: "photo_preserved"}`; `attempt_no = used + 1`.
   - Why per run: an evaluation of a second model on the same products must not find its slots used by the first. Runs are created only by the CLI. The phase-2 run and its allowance are defined in design v2.
4. **Revision rules:** the parent must be `rejected` (409 `not_rejected`) and in the same scope. `req_one_revision` refuses a second live revision of the same parent (409 `revision_already_requested`).
5. **Background rules:** the cutout must be `confirmed` and belong to the scope (variant, cycle, run); a new cycle needs a new cutout (free, local).
   - **Background on a cutout** (`POST …/cutouts/{id}/background`, CSV `background`): if the scope has no `photo_preserved` candidate yet, it is the initial background. Otherwise it is a **revision of the scope's latest `photo_preserved` candidate**, which must be `rejected` (else 409 `review_pending`), with `parent_id` set. This replaces a wrong cutout without a new cycle and keeps the chain linear (Codex r4).
   - **Same cutout, new background:** `revise` the rejected candidate (rule 4).
6. **Budget:** `spent = COALESCE(SUM(cost_micros), 0)` over `provider_calls` since `SPEND_CAP_SINCE`. The reservation is `r = max(configured estimate for the purpose, ceil(1.25 × highest usage-based cost of an earlier call with the same model and purpose))`. Raising `ESTIMATE_*_USD` applies to new calls only; past calls are never rewritten. `spent + r > cap` → 409 `budget_exhausted`.
7. Insert the request (`running`) and call 1 (`running`, `cost = r`, `cost_is_estimate = 1`). Commit.

The same transaction rules (6–7, for call 2 only) apply to a **retry**. The request row stays `running`, so its slot and guards are held across the retry, and the count is right: no self-blocking and no undercount (Codex r2).

**Retry refused (Codex r3):** if rule 6 refuses call 2, the same transaction sets the request `failed` with `error_kind = 'budget_exhausted'`; call 1 keeps its cost. If `SQLITE_BUSY` remains after the busy timeout, the API returns 503 `busy` for a new request; for a retry, the request becomes `failed` with call 1's `error_kind`. The CLI waits 2 s, tries once more, then does the same. If even that write fails, the request stays `running` until owner recovery marks it `interrupted` at the next start, and the error is logged.

**The provider call:**
- **Request:** `images.edit`, `n=1`. Image 1 = the variant's photo(s) (≤ 3); then the style reference; `size=1088x1920`. `input_fidelity` is never sent (to omit for gpt-image-2 per the docs; nothing documented for 2.5/2.6). Background: `images.generate`, or `images.edit` with only the style reference.
- **Sent images:** `provider_input` copies — EXIF-oriented, long edge ≤ 1536, PNG with **no metadata**. Originals are untouched.
- **Client settings:** async client, `timeout=180 s`, `max_retries=0`.
- **One retry (call 2) after 5 s**, only for 5xx, a connection error, or 429 `rate_limit_exceeded`. Never for `insufficient_quota`, refusals, other 4xx or timeouts.
- **Validation:** decode `b64_json`; it must be PNG/WebP, exactly `1088×1920`; else `invalid_response`. `# ponytail: strict size; accept-and-crop larger outputs if the evaluation shows mismatches.`
- **Success, in one transaction:**
  - store `raw_asset`;
  - cost = `ceil(Σ tokens × rate)` from `usage` if present, else keep the estimate;
  - create the candidate (`pending_review`);
  - request `succeeded`.
- **Failure:** the call and the request are `failed`; `error_kind` is the last call's. Reserved estimates stay as the cost.

**Master and crops** (Codex r1 checked: x = [4, 1084) for all; y = [0, 1920), [285, 1635), [420, 1500)):

| Format | Centred crop from 1088×1920 | Scaling |
|---|---|---|
| Story 1080×1920 | 1080×1920 | none |
| Feed 1080×1350 | 1080×1350 | none |
| Square 1080×1080 (safe square) | 1080×1080 | none |

**Product visibility (R-002 c.4, R-004 c.2):**
- The review draws the 3 crop frames on the result, for both treatments.
- **Approving any candidate requires `framing_checked = true`.** In the UI, the box "Produit entier dans les 3 formats" must be ticked; in the CSV, `framing=ok`. Otherwise → 422 `framing_not_checked`.
- `photo_preserved` placement fits by construction (D-PV-006); the tick still confirms the background and shadow look right in each crop.

**What the spending cap means (Codex r1 #2 / r2):**
- `SPEND_CAP_USD` caps **estimated** spend, as R-008 c.4 says. It is not a guarantee on the bill: if usage is missing and the estimates are too low, the bill can be higher.
- What the design does about it:
  - (a) a **dedicated OpenAI project and key** for this app. Whether a project budget limit exists on your account, and whether it blocks requests or only alerts, is **not verified**. Check it in the OpenAI settings;
  - (b) a **probe call** (T-PV-012) checks whether `usage` is returned for the chosen model;
  - (c) estimates are kept ≥ 1.25 × the highest billed cost per call seen so far;
  - (d) the report puts **billed totals** (entered per run) next to the estimates, and decisions use the billed numbers.
- Money math: integer micro-USD. USD per 1M tokens equals micro-USD per token. `Decimal`, rounded up. Rates are kept in config with their source date (pricing page 2026-11-06: gpt-image-2 and 2.5 at $8 / $30 per 1M image input/output tokens, $5 per 1M text input).
- Tests: rounding, the empty ledger, rejection of a missing or invalid cap, and the cap boundary (`spent + estimate == cap` is allowed; one micro over is refused).

**Error mapping** (exact SDK classes and fields verified in T-PV-003):

| Signal | error_kind | UI (FR) → action |
|---|---|---|
| 400 `moderation_blocked` / `image_generation_user_error` | `refused` | "Image refusée par le service" → Modifier la direction / Garder ma photo |
| 429 `insufficient_quota`, billing limit | `quota` | "Quota du compte OpenAI atteint" → Revenir |
| Our cap | `budget_exhausted` | "Budget de génération atteint" → Revenir |
| 429 rate limit after the retry | `rate_limited` | "Service saturé, réessayez dans une minute" |
| Timeout | `timeout` | "Délai dépassé" → Réessayer / Revenir |
| 5xx / connection error after the retry | `provider_error` | "Service indisponible" → Réessayer / Revenir |
| Bad body / wrong size | `invalid_response` | "Résultat inutilisable" → Réessayer (cost kept) |
| 401 / 403 | `auth` | "Configuration du service à vérifier" |
| Other 4xx | `invalid_request` | "Erreur technique" (our bug, logged) |
| Disk write error | `storage` | "Erreur d'enregistrement" |

"Réessayer" creates a **new** logical request, with a new id.

**Phase-2 API (draft):**
```
POST /api/visuals/scene-requests { id, variant_ref, photo_assets?, direction, acknowledged_warnings? }
202 { id, attempt_no, attempt_limit } (200 if already known)
GET  /api/visuals/requests/{id}  200 { status, error_kind?, candidate_id?, calls: n, created_at, finished_at? }
```
The client polls every 3 s. "Annuler" only stops waiting. A semaphore allows ≤ 2 provider calls at a time per process.

**Stub provider:** cost 0; `provider='stub'`; a deterministic 1088×1920 image after a delay; `STUB_FAIL=<kind>` for failures. Its own `DATA_DIR`. No paid call ever happens in tests.

---

## D-PRODUCT-VISUALS-004 — Candidate review state machine  (covers R-004, R-002 c.4)

```
(validated generation) ──▶ pending_review ──approve──▶ approved   (final)
                                    └────reject───▶ rejected   (final; may get one live revision)
```
- **Transitions:** conditional `UPDATE … WHERE id=:id AND status='pending_review'`.
  - rowcount 1 → OK;
  - rowcount 0 → reload: same target and payload → OK (idempotent); otherwise 409 `invalid_transition`.
- **Pure** `next_status` is tested on all 6 combinations (4 refused).
- **approve:** requires `framing_checked`, both treatments (D-PV-003).
- **reject:** requires ≥ 1 known reason or a non-blank note (422 `reason_or_note_required` / `unknown_reason`). The note passes `find_commercial_terms`.
- **Reason codes:**
  - from R-004: `coloris, logo, cameras, boutons, forme, extra, texte`;
  - added by the R-004 c.2 amendment (ADR-011): `cadrage`, `integration`;
  - `texte` reads "Texte ajouté hors du produit".
- **Use in a poster:** only via `GET /api/visuals/reusable` (D-PV-007). The poster-editor design must check `approved` and the same `variant_ref` on the server when it saves.

**Phase-2 review UI:**
- phone: Original | Résultat toggle; desktop: side by side;
- a "Formats" toggle draws the frames;
- zoom = full-screen view at natural size, scroll container, 1× / 2× / 4× buttons.

---

## D-PRODUCT-VISUALS-005 — Revisions, the attempt limit and cycles  (covers R-005)

- **Allowance:** `run.attempt_limit` **scene** requests per variant, cycle and run. Requests that are running or succeeded count; failed or interrupted ones do not (nothing to review; the budget still limits them). The count happens inside the request transaction (D-PV-003 rule 3).
  - The phase-2 API run uses `ATTEMPT_LIMIT` = 3 (ADR-010).
  - CLI `--attempt-limit` accepts 1 … 5; 5 is the evaluation exception (ADR-011). `--corrections by_arm` exists only in the CLI.
- **Scene revision** (`POST …/candidates/{id}/revise {id}`) on a rejected scene candidate:
  - reuses the parent's photos, direction and subject;
  - adds the corrections (see the arm rule below);
  - uses one slot.
- **Fallback revision** on a rejected `photo_preserved` candidate:
  - a new background for the **same confirmed cutout** (`revise`), or for **another confirmed cutout** of the scope when the cutout was the problem (`background` on that cutout, D-PV-003 rule 5);
  - `parent_id` = the rejected candidate; corrections apply to the background prompt (see the arm rule below);
  - it does not use scene slots; the budget limits it.
- **Arm rule (ADR-011):** in a `by_arm` run, **every** revision (scene or background) of an arm-B product is a plain re-roll: no reason sentences and no note in the prompt; `corrections_applied = 0`. The arm comes from `run_products`, never from the CSV at that moment.
- **Abandon** (CLI `apply` action `abandon`; target = the scope id `variant_ref:run_label:cycle_no`, `kind` = the treatment; Codex r4): writes an `abandonments` row for exactly that scope.
  - Replay: the row already exists → `already_applied` (checked first).
  - Refused if the run or variant is not in `run_products`, the cycle is later than the current one, a request in that scope is running (409 `request_running`), or the scope already has an approved candidate of that treatment (409 `already_approved`).
  - Afterwards new requests in that scope are refused (D-PV-003 rule 3). A new cycle starts with no abandonment.
- **Cycles (ADR-011):**
  - `POST /api/visuals/variants/{ref}/cycles` (CLI: `evaluate new-cycle SKU`) starts cycle n+1, **only if** the current cycle has an approved candidate (any treatment, any run). Otherwise → 409 `cycle_not_approved`.
  - This is an explicit operator action ("Nouvelle campagne"), not a side effect of approving.
- **No automatic revisions:** only an operator action or a CSV row calls revise.
- **Tests:**
  - allowance counting;
  - two concurrent revision requests at `used = 2` → exactly one is accepted (two processes);
  - a retry holds its slot (no self-block, no fourth candidate);
  - a retry refused by the budget leaves the request `failed` (`budget_exhausted`) and frees its slot;
  - double revise refused, then allowed after a failure;
  - a second initial request in a scope is refused (`review_pending` while pending, `use_revision` after a rejection), for both purposes;
  - a run with the same model and quality as an existing run cannot be created;
  - a cycle cannot start without an approval;
  - a fallback revision does not consume a scene slot;
  - a wrong cutout can be replaced: `background` on a second cutout of the scope is a linked revision after a rejection, and `review_pending` while the latest fallback candidate is pending;
  - a cutout from an earlier cycle is refused for a background;
  - abandon replay after `new-cycle` still addresses the original scope;
  - an arm-B revision prompt (scene and background) contains no correction sentence or note;
  - abandon is refused while a request runs, and blocks new requests after;
  - a killed CLI process does not block the next start, and its running request becomes `interrupted`.

---

## D-PRODUCT-VISUALS-006 — Photo-preserving fallback  (covers R-006)

1. **Cutout** (`POST /api/visuals/cutouts {variant_ref, photo_asset?, direction, acknowledged_warnings?}`; CLI `generate`):
   - **Input:** the source is EXIF-oriented. The photo must belong to the variant.
   - **Mask:** computed on a copy with long edge ≤ 2048 (bounded CPU), in the thread pool with a semaphore of 1. No timeout is claimed, because inference cannot be interrupted.
     - `rembg.remove(copy, only_mask=True, session=…)`, upscaled to the source size;
     - threshold at 128;
     - **fill holes smaller than `MAX_HOLE_RATIO` (5 %) of the product area** (lens glass, glossy screen); bigger openings stay transparent;
     - **erode 1 px** (`MinFilter(3)`).
   - **RGBA built by us:** RGB = source pixels unchanged; A ∈ {0, 255}.
   - **Component check** (BFS on a 256-px copy):
     - no component ≥ 2 %, or mask > 95 % → `no_product`;
     - 2 or more components each ≥ 30 % of the largest → `multiple_products` ("choisissez une photo à une seule vue").
   - These thresholds are calibration knobs. The operator always sees the cutout before any spend.
2. **Decision:** conditional `proposed → confirmed | rejected`. Reject = no spend.
3. **Background:**
   - `POST …/cutouts/{id}/background {id}` on a `confirmed` cutout of the current scope, using the cutout's stored direction and run. Initial or linked revision per D-PV-003 rule 5.
   - **Placement:**
     ```
     s = min(0.45·1920 / bbox.h, 1000 / bbox.w)
     box = (w·s) × (h·s), centred on x = 544, bottom at y = 1440
     assert box ⊂ safe square [4,1084) × [420,1500)
     ```
     It is stored as `product_box_json`. The cutout asset is never resampled.
   - **Shadow (ADR-011):** a synthetic shadow from the alpha (squashed to 12 %, blur 24, 35 % black) under the box, baked into the background at the default placement. It is not stored separately. The candidate's `image_asset` is the background with the baked shadow; the call's `raw_asset` keeps it without.
   - The result is a `photo_preserved` candidate → review.

**Pixel test (R-006 c.3):**
- for A = 255, RGB equals the oriented source;
- A ∈ {0, 255};
- equal sizes;
- cases: 3 committed samples, an EXIF-orientation-6 sample, and the mask-downscale path.

Pixel equality does not prove the mask is *right* (thin details eroded, real openings filled). That is what the operator's preview and the `forme`/`extra` reasons are for.

**Failure modes:**

| Failure | Detection | Behavior |
|---|---|---|
| rembg model missing (offline first run) | exception at session creation | 503 `cutout_unavailable`. Downloading the model is a setup step (T-PV-004). |
| `MemoryError` | exception | 500 `cutout_error` (the 40 MP decode limit makes this unlikely). |
| Background fails | gateway | D-PV-003 mapping. The cutout stays `confirmed`; asking again creates a new request. |

---

## D-PRODUCT-VISUALS-007 — Reuse and provenance  (covers R-007)

- **Provenance:** candidate → its request (`request_id`) → its calls (cost, timings, usage) and its cutout.
- `GET /api/visuals/reusable?variant_ref=` → `approved` candidates of exactly that variant, newest first. It is a read only, so a price change makes no generation.
- **No delete operation** in this feature. creation-library will add deletion with its guard.
- **Tests:** another variant's visual is never returned; the reuse path makes no gateway call.

---

## D-PRODUCT-VISUALS-008 — Fixtures, evaluation and report  (covers R-007 fixture criterion, R-008)

**`fixtures/products.csv`** (UTF-8 / UTF-8-BOM, `;`):
```
variant_ref;name;variant;photos;price_ar;facts;mood;description;arm;notes
OPM-A15-NOIR;Samsung Galaxy A15;Noir 128 Go;a15-noir-1.jpg|a15-noir-2.jpg;899000;Garantie 6 mois;studio;;A;look-alike of A16
```
- **Validation:** required columns, unique refs matching `[A-Za-z0-9_-]+` (run labels too, so scope ids parse), files exist and decode, no HEIC, `arm ∈ {A,B}` when the run uses `by_arm`, and the description passes the screen. All errors are listed, and nothing is loaded if any row fails.
- `fixtures/photos/` is git-ignored; `products.example.csv` is committed.
- `price_ar`/`facts` exist only for the leak test.
- `arm` is set by the user, so easy and hard products are split evenly (ADR-011). With about 20 products, the evidence is weak either way.
- At `generate`, each product's arm and the sha256 of its CSV row are stored in `run_products`. A later `generate --run L` whose CSV row differs for an existing product is refused, naming the product. Other commands read the arm only from `run_products`.

**CLI** (`python -m affiche.visuals.evaluate`; `owner='cli'`; one at a time):

| Command | Does |
|---|---|
| `generate --fixtures F --run L [--model --quality --attempt-limit 1…5 --corrections on\|by_arm] [--only SKUs]` | Creates run L (immutable: an existing L with a different config is refused; a new L with the model and quality of an existing run is refused, naming that run). Snapshots `run_products`. For each product: a scene request (attempt 1) and a cutout (free, stops at `proposed`). Asks for the low-res acknowledgement. Prints `spent / cap` after each call. On `budget_exhausted`: exit 3, and the products not started are listed. |
| `sheet --out DIR` | `sheet.html` (static, stdlib). For each pending candidate: the original and the result at natural size, the 3 crop frames, attempt n / limit, the reasons legend. For each proposed cutout: on a checkerboard. Also `decisions.csv`, pre-filled with ids, plus one row per open scope and treatment with its scope id and an empty action (blank actions are skipped). |
| `apply decisions.csv` | Columns `target_id;kind;action;reasons;note;framing`. Decision actions: `approve`, `reject`, `confirm_cutout`, `reject_cutout`, `abandon` (target = scope id, kind = treatment). Generation actions: `revise`, `background`. See below. |
| `new-cycle SKU` | D-PV-005 (ADR-011). |
| `report --out DIR [--billed L=USD …]` | See below. |

**`apply` steps:**
1. **Validate every row first:** unknown id, more than one decision or generation per target, an illegal transition (taking the file's own decisions into account), missing reasons or framing, commercial terms. **Nothing is applied if any row fails.**
2. Apply the decisions (conditional updates, so replay is safe).
3. Then the generation actions. Each one's request id = `uuid5(NS, f"{target}:{action}:{k}")`, where `k` = the number of earlier failed or interrupted requests for that target and action. Replaying an unfinished file returns the same requests; after a failure, a new one is created. Every target (candidate or cutout) belongs to exactly one scope, so ids never collide across cycles or runs (Codex r4).
4. Write `apply-result.csv` (`applied | already_applied | refused:<reason> | request_failed:<kind>` per row). Running the same file again resumes where it stopped.

**`report` outputs:**
- `calls.csv`: one row per provider call, with timings.
- `report.csv`: per run × variant × cycle × treatment:
  - requests, calls, candidates, the first approved `attempt_no` (attempt numbers restart each cycle);
  - outcome `approved | abandoned | pending | exhausted | failed_only | not_approved` (first match wins; `abandoned` only from an explicit `abandon`);
  - reason counts;
  - estimated cost (failed and rejected included);
  - billed cost allocated pro rata to the estimates (marked as an allocation);
  - cost per approved;
  - `low_res`, `arm`.
- `summary.md`: totals and medians, approvals at attempt 1…limit per treatment and arm.

**Recommendation:** written by hand (Claude + user) from `summary.md`. It covers the default treatment, model, quality and attempt limit, against thresholds agreed before the run. The user approves it, then design v2 is written.

**Suggested run:** 5 products to calibrate, then 15.
- Base scenario per model/quality at the default estimates: 20 × (3 scenes × $0.40 + 1 background × $0.30) ≈ $30. With the evaluation limit of 5 (ADR-011): about $46.
- **Heavier example** (every call retried once, and one extra background per product): 20 × (scenes × $0.80 + 2 × $0.60) ≈ **$72** (limit 3) / **$104** (limit 5). This is not a ceiling: failed requests and background revisions are limited only by the cap.
- These are estimates; the billed totals decide.

---

## Cross-cutting

**Configuration (`.env`, git-ignored; `.env.example` with names only):**
`OPENAI_API_KEY` (dedicated project), `IMAGE_PROVIDER`, `OPENAI_IMAGE_MODEL`, `OPENAI_IMAGE_QUALITY`, `SPEND_CAP_USD`, `SPEND_CAP_SINCE`, `ESTIMATE_SCENE_USD`, `ESTIMATE_BACKGROUND_USD`, `ATTEMPT_LIMIT`, `PRODUCT_HEIGHT_RATIO`, `MIN_SOURCE_SHORT_EDGE`, `MAX_HOLE_RATIO`, `REMBG_MODEL`, `DATA_DIR`, `API_TOKEN` (phase 2).

**Security:**
- **Phase 1:** CLI on the user's PC. No network listener.
- **Phase 2 (required in design v2; transport method chosen there):**
  - HTTPS on the LAN, with a `Secure; HttpOnly; SameSite=Strict` cookie;
  - **server-side sessions** (opaque random id, 30-day expiry, revocable by deleting the row; rotating `API_TOKEN` revokes all);
  - `POST /api/session` is the only route without a session, rate-limited to 5/min per IP, constant-time token compare;
  - **no public hosting** before the access-control design.
- **API key:** read only by the gateway from the environment; never logged or returned; SDK logging at WARNING.
- **Uploads:** size limit, type from decoding, pixel limit, hashed names.
- **Privacy:** EXIF (GPS, device) stripped from provider inputs. Originals are served only behind the session.
- **Prompts:** free text can only steer an image that the operator reviews.

**Edge cases across the feature:**
- Times are UTC.
- Two devices on one candidate → conditional updates.
- A restart → owner-scoped recovery.
- No pagination. `# ponytail: add limit/offset past a few hundred candidates.`

## Requirement traceability

| Requirement | Design |
|---|---|
| R-001 direction, style upload | D-PV-002 |
| R-002 one candidate; reject+revise to get another; pending review; crops; original kept; errors; low-res before spend | D-PV-001, D-PV-003, D-PV-004 |
| R-003 only name/variant/direction; no added text; unit test | D-PV-002 (amended wording, ADR-011) |
| R-004 review, checklist, approve/reject, use only if approved, transitions | D-PV-004, D-PV-007; phone UI in phase 2 |
| R-005 linked revision, earlier unchanged, no auto, limit → fallback | D-PV-005, D-PV-003 |
| R-006 cutout, separate layer, pixel test, preview before spend, errors | D-PV-006 |
| R-007 provenance, reuse, same variant only, no deletion, fixtures | D-PV-001, D-PV-007, D-PV-008 |
| R-008 both treatments, report, estimated cap, key in env, stub until photos | D-PV-003, D-PV-008 |

## User decisions (2026-11-06, ADR-011)

| Question | Decision |
|---|---|
| UQ-1 Shadow | Baked into the background (D-PV-006). No shadow layer or asset. |
| UQ-2 Wording | R-003 c.1–2 and R-004 c.2 amended (D-PV-002, D-PV-004). |
| UQ-3 Phasing | Phase 1 CLI evaluation, then phase 2 UI in design v2. This approval covers phase 1. |
| UQ-4 Evaluation exception | CLI runs only: limit ≤ 5, `by_arm` corrections (D-PV-005, D-PV-008; R-005 last criterion). |
| UQ-5 Reset | Explicit cycle after an approval (D-PV-005; R-005 c.4). |
