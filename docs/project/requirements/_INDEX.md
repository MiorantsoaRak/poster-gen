# Requirements Index

> One file per feature. All 22 requirement groups are Approved: the existing eight phase-1 groups, 13 approved on 2026-11-09 (ADR-028), and the selected-layer prompt editing requirement approved in ADR-030. Requirements approval does not approve the technical designs.

| Feature file | Requirements | Status | Design |
|---|---|---|---|
| [multi-shop.md](multi-shop.md) | R-MULTI-SHOP-001 … 006 | Approved 2026-11-15 under the autonomy grant (ADR-106), Release 1 « Invitation » ([roadmap](../ROADMAP.md), ADR-105) | [multi-shop](../designs/multi-shop.md) v4, approved under the autonomy grant (ADR-107) |
| [prepaid-balance.md](prepaid-balance.md) | R-BALANCE-001 … 007 | Approved 2026-11-16 under the autonomy grant, amended by its design (ADR-109), Release 1 | [prepaid-balance](../designs/prepaid-balance.md) v4 |
| [admin-dashboard.md](admin-dashboard.md) | R-ADMIN-001 … 006 | Approved v4 2026-11-17 under the autonomy grant, amended by its design (ADR-110), Release 1 | [admin-dashboard](../designs/admin-dashboard.md) v3 |
| [service-terms.md](service-terms.md) | R-TERMS-001 … 003 | v2 2026-11-17, approved (autonomy grant); R-TERMS-002 decided by the user (ADR-111) | [service-terms.md](../designs/service-terms.md), approved v3 (ADR-112) |
| [shop-dashboard.md](shop-dashboard.md) | R-SHOP-DASH-001 … 009 | 001–009 approved for design | [approved v3 and v4 amendment](../designs/shop-dashboard.md) |
| [share-poster.md](share-poster.md) | R-SHARE-001 … 005 | Approved 2026-11-18 with defaults (ADR-120), Release 1 | [share-poster.md](../designs/share-poster.md), approved v3 |
| [text-first-generation.md](text-first-generation.md) | R-TEXT-FIRST-001 … 005 | R-TEXT-FIRST-004 and 005 amended 2026-11-15 (ADR-099: title, brand and subtitle by message). Approved 2026-11-14 under the autonomy grant with working defaults (ADR-091 to 093), amended by ADR-094 | [text-first-generation](../designs/text-first-generation.md) |
| [editor-refinements.md](editor-refinements.md) | R-EDITOR-REFINEMENTS-001 … 004 | Approved autonomously after independent review, 2026-11-14 | [editor-refinements](../designs/editor-refinements.md) |
| [product-visuals.md](product-visuals.md) | R-PRODUCT-VISUALS-001 … 011 | 001–008: phase-1 baseline; 009–011: approved normal-poster amendments | [product-visuals](../designs/product-visuals.md) |
| [catalogue-brand.md](catalogue-brand.md) | R-CATALOGUE-BRAND-001 … 005 | 001–004: Approved (003–004 on 2026-11-12, ADR-052; 003 amended by ADR-053 then ADR-055; design D-004 v3.1 approved, ADR-056); 005 (logo seal): Approved 2026-11-12 with its design (ADR-057) | [catalogue-brand](../designs/catalogue-brand.md) |
| [generation-jobs.md](generation-jobs.md) | R-GENERATION-JOBS-001 … 002 | Approved | [generation-jobs](../designs/generation-jobs.md) |
| [poster-editor.md](poster-editor.md) | R-POSTER-EDITOR-001 … 007 | 001–003: Approved; 004 (steps and tabs), 005 (remove an element), 006 (visual language): Approved 2026-11-13 under the autonomy grant (ADR-072); 006 amended and 007 (phone-first editor) approved the same day (ADR-075) | [poster-editor](../designs/poster-editor.md) |
| [format-export.md](format-export.md) | R-FORMAT-EXPORT-001 … 002 | Approved | [format-export](../designs/format-export.md) |
| [creation-library.md](creation-library.md) | R-CREATION-LIBRARY-001 … 004 | 001–002: Approved; 003 (manage posters) and 004 (manage saved styles): Approved 2026-11-12 (ADR-060; "Confirmée" amended by ADR-061), design D-CREATION-LIBRARY-003/004 approved v2.1 (ADR-061) | [creation-library](../designs/creation-library.md) |
| [hosted-pilot.md](hosted-pilot.md) | R-HOSTED-PILOT-001 … 006 | Approved 2026-11-13 with seven working defaults, under the user's autonomy grant (ADR-064); a seventh feature | [hosted-pilot](../designs/hosted-pilot.md) |

Approved flow: photo/title/exact price → optional Claude planning → GPT Image integrated scene → editable poster with independently selected logo/name/contact → fidelity review → manual or prompted selected-text polish → server preview → confirm → download the same PNG. Cutout is optional. Scene refinements preserve the base and use it plus originals. Separate text/effect layers preserve manual editing; surface-embedded lettering is deferred. Feed is the first slice; square and story remain required for the pilot.

Next gate: review the [technical designs](../designs/_INDEX.md), then approve them before implementation tasks, as required by [AGENTS.md](../../../AGENTS.md). No new feature code or paid testing was performed during design.
| [poster-format.md](poster-format.md) | R-POSTER-FORMAT-001 … 002 | Approved 2026-11-14 (ADR-080) | [poster-format](../designs/poster-format.md) |
