# DESIGN — generation-jobs

**Status:** Approved v1, 2026-11-09. **Approval:** ADR-031. **Requirements:** [generation-jobs](../requirements/generation-jobs.md), plus R-POSTER-EDITOR-003. ADR-028/030 approve requirements; ADR-029 proposes architecture.

## System overview

One FastAPI process owns a durable SQLite queue and bounded asyncio workers: two provider calls maximum, one Chromium render maximum. No Redis/Celery or distributed lease system for the single-shop pilot. A process holds the existing runtime owner lock for its lifetime. Queued work survives restart; started calls with unknown outcomes are never automatically replayed.

Vue → authenticated /api requests → atomic admission/queue → worker → OpenAI or Claude → immutable result → polling/review. The evaluator retains its current state rules; normal posters use the new job/visual tables. Reuse the existing adapters, image preparation, money helpers and asset store; do not route normal poster revisions through evaluation admission.

## D-GENERATION-JOBS-001 — Claude planning and validated scene instructions

**Covers:** R-GENERATION-JOBS-001; product-visuals R-003/009; poster-editor R-003 uses a separate constrained patch schema.

**Data:** scene_plans(id UUID, creation_id, origin_revision, input_id, job_id UNIQUE nullable for local builder, source=claude/manual/fixed, schema_version, plan_json, prompt_text, prompt_hash, created_at). Records are immutable. Editing a plan creates another record with optional parent_plan_id. Image jobs snapshot the chosen plan and prompt; later plan edits cannot change admitted jobs.

ScenePlanV1 (all objects reject extra fields):

```text
schema_version: 1
summary_fr: string <= 500                        # shown to operator, not sent as image instructions
scene: {setting: string <= 400, surface: string <= 160,
        lighting: soft_studio|daylight|dusk|neon, camera: eye_level|low|overhead}
product_region: {x,y,w,h}                        # normalised finite coordinates within [0,1]
overlay_regions: [{field: title|price|logo|shop_name|contact, box:{x,y,w,h}}]
palette: 2..4 opaque #RRGGBB colours
```

Only selected/present fields may occur; title and price are required. No duplicate field; positive boxes inside the format; planned product/text boxes must not intersect. This is a composition proposal, not detected proof of where the generated product actually sits. Geometry and string constraints are validated again locally; model JSON schema conformance alone is insufficient.

Claude input contains prepared original copies, confirmed name/variant, user's creative direction, primary format, selected field IDs and measured text-footprint hints. Do not send price/contact values or shop logo merely to reserve space. No inference becomes a verified product fact. Image contents and user text are data, never system instructions. A low-resolution poster preview may be sent for a selected-layer patch, with explicit shop consent implicit in requesting that model operation; it contains visible content and is not logged.

Compiler uses the existing fixed identity/no-added-text instructions, approved input identity, screened scene fields and geometry. Commercial text and arbitrary model instructions never become overlay values. Screen scene free text with the shared matcher; validate structured fields; show artistic summary before spend. Semantic fidelity cannot be fully proved by a schema/blocklist: operator review remains necessary. If the model puts a product claim in an artistic field, reject it when detectable; it never becomes an offer field, and the user can correct the brief.

**Provider contract:** server-only POST https://api.anthropic.com/v1/messages, x-api-key, anthropic-version: 2023-06-01; model from configured allowlist; system + user content blocks (image base64 and text), max_tokens=4096, stream=false, output_config.format={type:json_schema,schema:…}. Use installed httpx2 async client, already a dependency, with explicit timeout and no implicit retries; no additional SDK needed solely for this small endpoint. Parse an end_turn text JSON result, validate locally; refusal, max_tokens truncation, unexpected tool calls or invalid JSON fail the job. Record model, request ID and validated integer usage, not raw provider bodies. No hidden model upgrade or auto-repair request.

Proposed first evaluation model: claude-sonnet-5-5, documented at USD 2/input MTok and USD 10/output MTok on the check date. Record a versioned rate card with every call, count all returned billed token categories, and conservatively retain the estimate if usage is incomplete. Recheck the official rate/model capability at implementation; account access is untested. Keys/rates/estimate are required for paid planning; missing configuration exposes the explicit fixed-builder path, not a broken automatic planner.

**API:** POST /api/creations/{id}/plans with If-Match, Idempotency-Key and {mode:claude|fixed, direction, format}. Claude → 202 job; fixed → 201 plan without a provider. GET /api/plans/{id} → plan/summary. POST /api/plans/{id}/revisions {scene,product_region,overlay_regions,palette} with current-creation If-Match/Idempotency-Key validates and returns an immutable manual plan (201), bound to that current revision. This also supports explicitly reusing/revalidating a stale plan after an ordinary input/layout edit without another Claude call. A changed product input requires a new plan. Editing a plan never silently queues an image. An unacknowledged stale creation/input or missing field returns 409 plan_stale/422 invalid_plan.

**State:** queued planning → running → validated plan or failed/interrupted. The operator then accepts/edits the description and explicitly requests the image. Failure leaves the original direction available. Prompt-based text patches follow the same job lifecycle but use only the schema in poster-editor, not ScenePlanV1.

| Failure | Detection | Handling |
|---|---|---|
| Missing key, unavailable model, invalid configuration | Before admission | 503 planner_unavailable; show fixed builder/manual direction; no spend. |
| Schema/semantic constraints fail or truncated/refused response | Local validation + stop_reason | Failed plan; record cost; show retry/fixed choices; no image call. |
| Rate limit | Explicit 429 | At most one bounded retry after delay if reservation fits; no retry loop. |
| Timeout/network loss after dispatch or provider 5xx | Ambiguous outcome | interrupted, estimate retained; manual retry is a distinct disclosed paid action. |
| Draft changed while plan ran | Origin revision differs | Keep the plan as history; require explicit rebase/replan before image submission. |

## D-GENERATION-JOBS-002 — Job admission, spending and crash recovery

**Covers:** R-GENERATION-JOBS-002; product-visuals R-009/010/011; poster-editor R-003; format-export R-002.

**Data / constraints:** new forward-only tables; all shop/creation/input references validated and FK-backed where relational:

| Table | Fields / invariants |
|---|---|
| poster_jobs | UUID id, shop_id, creation_id, origin_revision, input_id, kind, input_json immutable, status, result_ref nullable, error_code nullable, created_at/started_at/finished_at. kinds plan/scene/refine/text_patch/text_texture/render/cutout/background. States queued/running/succeeded/failed/interrupted/cancelled. |
| poster_calls | id, job_id FK, call_no 1 or 2, provider, model, rate_card_json, status reserved/running/succeeded/failed/interrupted/cancelled, cost_micros>=0, cost_is_estimate, validated usage_json, provider_request_id nullable, timestamps. UNIQUE(job_id,call_no). No row for render/cutout/fixed builder. |

Job admission under BEGIN IMMEDIATE: authenticate → parse/canonicalise request including If-Match → mutation-key replay → validate references/snapshot/current revision → check active image job and allowance → check global spend plus estimate → insert job + call-1 reservation + idempotent response in one transaction. Commit before waking workers. Replay precedes mutable domain guards so a lost response still returns the original job after the draft changes. Cross-kind/model calls share the same budget check.

Extend the existing spent_micros helper to sum provider_calls AND poster_calls since SPEND_CAP_SINCE. Both CLI admission and poster admission use it under the same write lock. Successful usage replaces a reservation, never adds to it. Missing/invalid usage and ambiguous charged failures retain the estimate. Definitely unsent calls release it to zero. Do not count a reservation twice in status totals. Existing paid ledger must remain in the same database; any later data-directory migration must carry its full ledger, not start a fresh cap.

Keep the existing meta.provider_mode safeguard for image calls; add a locked planner mode (stub/claude) when planning is first used. Pure render/manual edits remain free. Configured prospective estimates are separate for scene/refine, Claude plan/patch and text texture; all must be positive in paid mode. Store estimate and rates on the admitted call so config changes cannot rewrite past cost. Never expose a 'remaining credits' claim as an exact billing guarantee.

Normal draft scene allowance: at most three queued/running/succeeded scene or refine jobs. Failed/interrupted jobs do not use a successful-candidate slot but retain any possible spend. Text planning/textures use the budget and concurrency limit, not the scene-fidelity allowance. One active image-producing job per creation (scene/refine/texture/background) prevents overlapping paid edits; return 409 image_job_running rather than queuing conflicting intent. One active render per identical revision/format/build is deduplicated.

An explicit new draft can start after abandonment without approving a bad scene; it retains parent_creation_id and the global spend history. Never auto-restart at an attempt limit. User can retain a good version, use ordinary text controls, replace inputs or choose optional cutout.

**Worker transitions / crash semantics:**

| State | Entry / permitted exits / recovery |
|---|---|
| queued | Durable admission. Worker atomically claims → running; user may cancel before claim. Restart leaves it queued. |
| running, no call dispatched | Preflight verifies assets and configuration. Local failure → failed with unsent reservation released. Crash with no persisted dispatch marker → queued, safe to resume. |
| running, call dispatch committed | Mark call running before sending. Success → persist validated result+actual usage+job success atomically; definite error → failed. Ambiguous error/crash → interrupted; never auto-dispatch again. A crash between marker and network send is conservatively ambiguous. |
| succeeded | Terminal immutable result. Saving a late result never overwrites a newer selected scene or revision. |
| failed/interrupted | Terminal record with error/cost. Explicit retry uses a new key/job, preserves history and rechecks budget. |
| cancelled | Only queued work can enter; atomically release unsent reservation. A claimed/dispatched call cannot be promised cancelled or unbilled. |

API startup recovery uses the exclusive owner lock; it cannot run while an old API worker lives. CLI recovery does not modify poster jobs. No generic reuse of old execute retryable=true for ambiguous errors: new job runner retries only definite 429 rejection once; adapter itself stays retry-free. Renderer jobs are safe to rerun once after crash because they have no provider spend and are immutable inputs; partial files stay unreferenced until commit.

Persist validated provider bytes in a job-ID spool before asset/DB finalisation when possible. If later finalisation fails, retry local finalisation, not the provider call. If both spool and DB persistence fail, leave interrupted/estimate retained and expose reconciliation required. A durable response never gets regenerated merely because a DB commit or UI connection failed.

**API:** GET /api/jobs/{id} → {status,kind,result_ref,error?,usage:{estimated,recorded_micros},timestamps}; GET /api/usage → combined ledger totals/cap. POST /api/jobs/{id}/cancel with Idempotency-Key → cancelled or 409 already_started. All paid routes return 202 {job_id,status_url}; 409 attempt_limit/image_job_running/stale_revision, 422 invalid_input, 429 budget_exhausted, 503 provider_unavailable. UI polls every 2 s while visible, backing off to 10 s; network loss pauses polling, not the job. Reopen restores state from storage.

## D-GENERATION-JOBS-003 — Failure matrix and verification

**Covers:** both requirements and shared external-system failure handling.

| Failure / edge | Result |
|---|---|
| Browser double-click or lost 202 response | Replay same UUID/payload; one job, one reservation. |
| Two concurrent cap admissions | BEGIN IMMEDIATE serialises sum/reservation; one is refused if combined estimate exceeds cap. |
| Model changes, bad rate card | New admissions refused until verified config; running jobs keep recorded model/rates. |
| 401/403/quota/policy refusal | No retry; readable French error; previous draft survives. Unknown usage stays estimated. |
| Output corrupt/wrong size or disk full | Failed/interrupted as appropriate, no successful candidate; retain known cost and any spool. |
| Process crash during finalisation | Recover local spool first; no repeat provider call. |
| User switches scenes during a job | Result appears as alternative; no automatic selection. |
| SQLite busy after bounded wait | 503, same operation key retry; no untracked dispatch. |

Tests must cover cross-ledger budget concurrency, duplicate keys, three-attempt bounds, abandon/new draft, unknown outcomes, response spooling, two-process lock ownership, cancelled-vs-claimed race, strict plan validation, malicious image/brief content, no commercial-field copying, all provider failure kinds and paused/reconnected polling. Transport mocks must exercise the actual adapters; live Claude/image calls require separate explicit test scope and capped spend.

## Evidence and limits checked 2026-11-09

- [Claude structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs): output_config.format, local validation still needed, refusal/truncation handling. [Vision](https://platform.claude.com/docs/en/build-with-claude/vision): image inputs. [Model/rates reference](https://platform.claude.com/docs/en/models/overview): proposed Sonnet model/rates, not measured application cost.
- Orbit resource urn:orbit:endpoint:v1:aGpMQ0zETnWFGtU94UdP02cOu2tRW646:anthropic:create-message confirmed Messages request shape but lacked a concrete success example. Official docs resolve that gap. Orbit's OpenAI edit example was incomplete and mask-oriented; it does not establish multi-reference behaviour. Installed SDK and official OpenAI docs are used in product-visuals instead.
- No live provider request or model-access check was performed. SQLite queue/concurrency, authentication and spooling are design proposals, not implemented guarantees.
