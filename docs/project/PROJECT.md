# PROJECT — Affiche IA

**Status: Approved by the user on 2026-11-05 (charter and six-feature split; ADR-008). First feature: product-visuals.**  
**Created:** 2026-11-05 · **Working name:** Affiche IA  
**Phase:** Phase-1 product-visual evaluation backend implemented through T-PV-010; T-PV-011 report remains. The poster requirements, including separate manual/prompted text effects, are approved (ADR-028/030). Six matching phase-2 designs are approved (ADR-031); backend draft persistence and authenticated intake/profile/draft HTTP routes are implemented, together with durable scene generation/review and the French Vue/Konva editor. Isolated prompted typography and authoritative feed rendering/confirmation are implemented; a real R50i poster has been reviewed, polished and exported. Square/story/library enhancements, optional cutout and physical-device readiness remain queued.

Affiche IA helps Original Phone Mada turn a product photo, verified information and a price into promotional posters that a shop operator can polish, export and reuse. The proposed approach combines an AI-generated product scene with editable text, prices and branding in a flexible canvas. The pilot supports full editing on phones and desktop, with a French interface and French captions.

## Goal

- **Primary outcome:** Reduce the operator's time and assistance needed to produce an accepted poster, measured against the current workflow. Track correction effort, product-detail errors and repeat usage as well.
- **Proposed pilot:** Select/upload a product, generate a scene, edit the composition, review three formats, export and save, then reuse a creation with a new price.
- **Success thresholds:** Agree during requirements from an observed baseline. Neither one-minute generation nor a fixed acceptance rate is promised.
- **Explicit non-goals:** Multi-shop SaaS, subscriptions/billing, automated Facebook publishing, Odoo, competitor monitoring, video, arbitrary image-to-layer extraction, general-purpose design tooling and Malagasy localisation. Local AI retouching follows validation of the core editor.

## Users & context

- **Users:** Original Phone Mada staff/owner only for the pilot; other shops later.
- **Environment:** Web application with full editing on phones and desktop; FastAPI backend. Hosting remains undecided.
- **Language:** French interface and captions. Malagasy after the pilot.
- **Scale assumptions:** One shop and approximately 20 representative products for the proposed evaluation, including poor photos and easily confused product details. Measure concurrency before capacity decisions.
- **Journey:** Select/upload → confirm product facts and offer → choose or describe a visual direction → generate → edit → compare with original → review formats → export/save → reuse.

## Stack

| Layer | Choice | Notes |
| --- | --- | --- |
| Backend | **FastAPI — confirmed by user** | Python 3.12 + uv; CLI and authenticated draft API implemented. |
| Frontend | **Vite + Vue — confirmed by user** | Vue 3.5.45/Vite 8.3.7; French editor tested in Chromium desktop/mobile viewports; physical phone verification pending. |
| Canvas | Konva + vue-konva approved (ADR-031) | Shared document/component for editing and server Chromium preview; shared editor/server component and confirmed feed export verified. |
| Image generation | GPT Image integration is the primary direction (ADR-027) | Existing `gpt-image-2/high` tests succeeded; representative shop-photo evaluation remains. Cutout is optional for the future poster workflow. |
| Text/composition | Requirements approved; Claude planning/selected-text patches designed | Exact editable font glyphs with optional isolated textures; proposed Sonnet 5.5 evaluation model, not live-tested. |
| Database | SQLite + SQLAlchemy/Alembic for phase 1 | Phase-2 local persistence approved; hosting remains open. |
| Background processing | Durable SQLite queue in one FastAPI process | Approved design; implementation queued. |
| Asset storage | Existing content-addressed local files | Immutable originals/scenes/textures/exports, with database ownership. |
| Infra / deploy | One container (API, built frontend, Chromium, SQLite) on the shared Hetzner box, behind Maizina's Caddy; pyinfra releases (designs/hosted-pilot.md) | Requirements approved 2026-11-13 (ADR-064). Deployed on 2026-11-13 at https://affiches.miorantsoa.app, on the shared Hetzner box `mx1` behind Maizina's Caddy (ADR-066 to ADR-070); runbook in deploy/README.md. |

The canonical project location is `C:/Users/M Rakotozafy/Documents/Miorantsoa/Vite/affiche-ia`, alongside `tsena_scan`. The independent Git repository is on `main`; since 2026-11-13 it has the remote `origin`, the private GitHub repository `MiorantsoaRak/poster-gen`. The installed backend and verified CLI commands are documented in AGENTS.md. The authenticated API and Vue editor exist; deployment remains unconfigured.

## Constraints

### Confirmed by the user

- Vite + Vue alongside FastAPI.
- No fixed catalogue of HTML poster templates as the limit of V1; HTML in the Vue UI is unaffected.
- Original Phone Mada first, with full phone and desktop editing.
- French first; Malagasy after the pilot.
- Follow IDEA → REQUIREMENTS → DESIGN → TASKS → IMPLEMENT → HANDOFF. Bootstrap stops for project approval.

### Approved poster requirements

- Preserve original photos and confirmed commercial facts; review generated product fidelity and never invent specifications or offer conditions.
- Keep compositions flexible: the scene can remain one image while price, text, badges and shop logo are editable objects.
- Styles are optional starting points, not a closed list of fixed layouts.
- Reuse approved images for price-only changes without new image generation.
- Preserve history instead of silently rewriting old creations when catalogue prices change.
- Evaluate original-photo compositing as a fallback when generated scenes alter product details.
- Make progress/errors visible and editing recoverable; allow acceptance or rejection of generated revisions.

### Deferred details

- The original bootstrap authorised no paid calls. Later explicit approvals covered the synthetic probe and two real-product tests (ADR-023/026), now complete. Representative evaluation budget/inputs remain pending; current evidence and spending are in HANDOFF.md.
- Specify supported phones/browsers, connectivity and persistence before editor implementation; offline operation is not promised.
- Agree input constraints, export checks and pilot thresholds before evaluation.
- Canvas, queue, storage and shared-shop authentication designs are approved (ADR-031). Production provider validation and hosting remain open. Phase-1 choices do not approve phase-2 deployment. Single-shop scope does not imply public unauthenticated access.
- Pricing and subscription-credit estimates in the brief are hypotheses, not guarantees or spending limits.

## Definition of done (project level)

These pilot outcomes are covered by the approved per-feature requirements and designs.

- [ ] An operator completes the French upload/generate/edit/review/export workflow on the agreed phone and desktop browser set.
- [ ] The operator can change a price, enlarge a headline, reposition a logo, adjust colours/fonts, crop and undo without assistance in the pilot exercise.
- [ ] Verified product information, price and branding remain editable; generated appearance is compared with the source before approval.
- [ ] Feed (1080 × 1350), square (1080 × 1080) and story (1080 × 1920) can be reviewed and exported without unreported clipping or missing assets.
- [ ] Saved creations reopen and support price-only reuse without regenerating the scene or overwriting prior exported versions.
- [ ] Generation, save and export failures expose visible errors and the recovery behaviour agreed in requirements.
- [ ] Pilot results record accepted-output cost, correction time, fidelity issues and repeat usage, and meet thresholds agreed before evaluation.
- [ ] Required checks pass; access, deployment and backup decisions precede a hosted pilot; TODO.md and HANDOFF.md accurately record delivery.

## Risks known upfront

| Risk | Impact | Mitigation / watch signal |
| --- | --- | --- |
| Product details drift during generation. | Wrong item/variant is advertised. | Keep originals, compare results, evaluate photo-preserving fallback. |
| Small-screen editing is difficult. | Confirmed phone workflow fails. | Test touch selection, resizing, text entry and export on real phones early. |
| Product and scene are one raster image. | Users expect independent product dragging. | Accurately expose supported operations; restaging needs an appropriate edit. |
| Revisions/support exceed cost estimates. | Pricing becomes unsustainable. | Measure all attempts and assistance per accepted output; define budget before paid tests. |
| Preview and export differ. | Fonts/layout break in downloads. | Evaluate French content and every format on the chosen export path. |
| Premature SDK/infrastructure choice. | Cost or conflict with Vue/mobile needs. | Decide after requirements and focused evaluation. |
| Uninspected prototype assumptions are reused. | Old HTML constraints enter V1. | Inspect supplied code before reuse; distinguish evidence from claims. |
| Brief mistaken for an approved specification. | Workflow gates are bypassed. | Explicit statuses and empty feature indexes. |

## Feature split — approved 2026-11-05

These are planning boundaries, not requirement files or implementation tasks. Each gets one requirements file and a matching design after its gates.

| Feature slug | Scope | Future ID prefixes |
| --- | --- | --- |
| catalogue-brand | Shop identity, verified product/variant data, original-photo intake. | R-CATALOGUE-BRAND-, D-CATALOGUE-BRAND- |
| generation-jobs | Long operations, progress, recovery and measured usage. | R-GENERATION-JOBS-, D-GENERATION-JOBS- |
| product-visuals | Direction, reference scenes, fidelity review, fallback evaluation. | R-PRODUCT-VISUALS-, D-PRODUCT-VISUALS- |
| poster-editor | Flexible composition, French text/prices/branding, phone/desktop editing and undo/redo. | R-POSTER-EDITOR-, D-POSTER-EDITOR- |
| format-export | Format-specific layout/crop, previews, checks and downloads. | R-FORMAT-EXPORT-, D-FORMAT-EXPORT- |
| creation-library | Save/reopen, versions, approved assets and price-only reuse. | R-CREATION-LIBRARY-, D-CREATION-LIBRARY- |
| hosted-pilot (added 2026-11-13, ADR-064) | One HTTPS address for the shop's phones, long session, the pilot's own ledger and cap, backups, deployment, the first real-phone session. | R-HOSTED-PILOT-, D-HOSTED-PILOT- |

Access control, storage, validation and observability must be covered wherever applicable. Publishing/Odoo require separate later scope approval.

## Approval checkpoint

- Confirmed inputs: frameworks, no fixed HTML template constraint, pilot shop, devices and language.
- Approved 2026-11-05: this complete charter, scope/definition of done and six-feature split (ADR-008).
- Order: product-visuals requirements first. The remaining features get requirements later, in an order agreed with the user. Design or code for a feature starts only after its requirements are approved.

## Source and precedence

- [BRIEF.md](BRIEF.md): reviewed French brief snapshot before bootstrap.
- [DECISIONS.md](DECISIONS.md): explicit choices and interview answers.
- [HANDOFF.md](HANDOFF.md) and [TODO.md](TODO.md): current workflow state.
- No prototype archive or reference screenshots were inspected. Recheck provider capabilities, models and prices when selecting or integrating them.
