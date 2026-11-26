# Unified creation — delivery design

2026-11-26. Approved under the owner's explicit instruction to design then implement autonomously. Covers R-UNIFIED-01–08 and R-FREE-07. Replaces D-FREE-05's three-way entry and initial-only attachment restriction for new free posters.

## D-UNIFIED-01 — Durable context and image requests

Extend free JSON documents with optional photos, reference mode, and a typed identity snapshot (name, contact, lines, logo). Defaults read old documents. Retain accepted instruction history in each version (original brief plus twelve most recent requests); correction prompts reiterate chronological precedence so quality anchors cannot silently restore old prices. Legacy documents recover the selected base’s last successful request. Beyond this bound, the current image carries older changes. No SQL schema change: these are additional fields in the existing version JSON contract. The immutable product input remains the initial intake; later free jobs carry their validated photos in their own context. The worker continues shop/role checking each asset; only free jobs bypass the comparison with the original immutable intake's photo list.

Start accepts existing fields plus `use_shop`, `logo` and `reference_mode` (`layout`/`style`). Turn accepts optional replacement `photos`, `reference`, `logo`, `reference_mode`, `use_shop`, and `base_render_id`; omitted fields retain the chosen base's context, explicit null clears optional images. `use_shop=true` snapshots current server-owned profile; false clears identity. A supplied logo overrides the snapshot logo. Client cannot inject profile facts. Reference and logo retain distinct asset roles.

An explicit base render must belong to this same creation/shop. Read its immutable document; enqueue at the creation's current revision with that chosen context. Never roll back current revision or reuse a confirmed render as a newly confirmed result. Job stores `free_document`; only successful finish publishes its context and new source/render, so failures leave current state intact. Idempotency hashing preserves the legacy start defaults and distinguishes omitted correction fields from explicit null removals. Existing If-Match, terms, admission, budget, credit and one-active-job rules remain.

Image order: chosen base, source photos, first-version quality anchor if applicable, explicitly supplied reference (only first generation or reference changed), logo. Prompt numbers follow that order. Role-specific prompt rules prohibit borrowed reference facts/logo and invented shop marks, give exact kit facts, prefer explicit directions, keep broad quality guidance neutral to industry and preserve unrequested content on edits. New reference on edit intentionally replaces the previous visual direction; without it, don't resend an old reference and fight the correction.

A retry accepts only words plus `retry_job_id`, scoped to a failed/interrupted/cancelled scene job of this shop and creation at the same origin revision with unchanged words; it restores that job’s immutable input context. It cannot combine a retry snapshot with new context overrides. Transcript returns job ID and attachment/base context for accurate history; old jobs fall back to existing fields. Review keeps raw history but distinguishes latest instruction; no unreliable automatic extraction or OCR guarantee is introduced.

Failure modes: invalid/foreign asset/base rejected before spending; failed upload remains retryable; stale revision refreshes; dispatch timeout follows existing ambiguous-credit rules; file-read failure propagates or uses existing published-base fallback; failed generation leaves previous successful context; no publishing or deployment in tests.

## D-UNIFIED-02 — One browser workspace

Reuse `FreeCreation.vue` and existing chat CSS, paid dialog, upload API and review. New entry has only Libre / Pas à pas, retained within the mounted component so changing input mode preserves the draft and tray. `#creer`, `#message` redirect to free creation; `#etapes` opens its guided input; old `#message-ID` resolves to the legacy document editor. Remove Message switching UI; keep internal legacy compatibility rather than delete stored-document APIs.

Composer: editable example actions, visible attachment roles (Photo / Modèle / Logo), style-vs-layout choice for references, optional saved reference selection and shop identity summary. Later attachment controls explain replacement/removal; paid confirmation remains mandatory. Saved models supply their existing reference assets (same owner authorization as upload). The kit's logo does not use a photo slot.

Pas à pas is a compact input form in this same component: what to announce, exact text/prices (optional for announcements), visual direction. It assembles a visible editable request and then uses the same generation action. No canvas/layer/identity-position settings. Existing legacy editor remains solely for already saved product documents.

Versions: preview older version with explicit “Repartir de cette version”; correction targets that base and says so. No automatic restoration/charge on selection. Review shows current instruction plus expandable chronological history, originals and identity snapshot; original confirmation and downloads remain unchanged.

## D-UNIFIED-03 — Motion and resilience

Keep existing 160ms press feedback. Switch geometry moves via transform, not inset/size. Reduced motion leaves a static waiting indicator and status text. Preserve reading position; new-result affordance when scrolled up. Short opacity/transform reveal for result, no fake progress or animation dependency. Browser checks at 360/390 and desktop, light/dark, keyboard, reduced motion, upload/generation errors, no credit, reload, stale revision and legacy links.

## D-UNIFIED-04 — Validation

Paid matrix: brief/no image; detailed/no image; brief/photo; brief/photo/reference; reference only; three products/prices; supplied kit logo; no-logo kit and foreign-logo reference; style override; price-only correction; subsequent correction; new attachment; earlier-version branch; service/food/event use case. Use synthetic facts and isolated databases, existing cost ledger/caps. Visually assess every paid output and improve prompts then repeat failing cases. Acceptance requires no wrong supplied prices/contact, no invented claims or shop mark, recognizable products, requested composition and readable hierarchy. Do not fabricate missing facts in underspecified requests. Report residual model limits honestly.
