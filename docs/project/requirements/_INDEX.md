# Requirements Index

> One file per feature. All 22 requirement groups are Approved: the existing eight phase-1 groups, 13 approved on 2026-11-09 (ADR-028), and the selected-layer prompt editing requirement approved in ADR-030. Requirements approval does not approve the technical designs.

| Feature file | Requirements | Status | Design |
|---|---|---|---|
| [product-visuals.md](product-visuals.md) | R-PRODUCT-VISUALS-001 … 011 | 001–008: phase-1 baseline; 009–011: approved normal-poster amendments | [product-visuals](../designs/product-visuals.md) |
| [catalogue-brand.md](catalogue-brand.md) | R-CATALOGUE-BRAND-001 … 005 | 001–004: Approved (003–004 on 2026-11-12, ADR-052; 003 amended by ADR-053 then ADR-055; design D-004 v3.1 approved, ADR-056); 005 (logo seal): Approved 2026-11-12 with its design (ADR-057) | [catalogue-brand](../designs/catalogue-brand.md) |
| [generation-jobs.md](generation-jobs.md) | R-GENERATION-JOBS-001 … 002 | Approved | [generation-jobs](../designs/generation-jobs.md) |
| [poster-editor.md](poster-editor.md) | R-POSTER-EDITOR-001 … 003 | Approved | [poster-editor](../designs/poster-editor.md) |
| [format-export.md](format-export.md) | R-FORMAT-EXPORT-001 … 002 | Approved | [format-export](../designs/format-export.md) |
| [creation-library.md](creation-library.md) | R-CREATION-LIBRARY-001 … 004 | 001–002: Approved; 003 (manage posters) and 004 (manage saved styles): Approved 2026-11-12 (ADR-060; "Confirmée" amended by ADR-061), design D-CREATION-LIBRARY-003/004 approved v2.1 (ADR-061) | [creation-library](../designs/creation-library.md) |

Approved flow: photo/title/exact price → optional Claude planning → GPT Image integrated scene → editable poster with independently selected logo/name/contact → fidelity review → manual or prompted selected-text polish → server preview → confirm → download the same PNG. Cutout is optional. Scene refinements preserve the base and use it plus originals. Separate text/effect layers preserve manual editing; surface-embedded lettering is deferred. Feed is the first slice; square and story remain required for the pilot.

Next gate: review the [technical designs](../designs/_INDEX.md), then approve them before implementation tasks, as required by [AGENTS.md](../../../AGENTS.md). No new feature code or paid testing was performed during design.
