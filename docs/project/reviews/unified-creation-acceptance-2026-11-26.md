# Unified creation — implementation and acceptance

2026-11-26. Owner authorized design, implementation, browser iterations and paid generation. No deployment or publication. Requirements/design are `unified-creation.md`; task T-UNIFIED-03 owns this acceptance record.

## Delivered

- Libre is the primary creation entry. Message is removed from new-creation navigation. Existing Message document links open the legacy editor.
- Pas à pas prepares one editable request: announcement, exact text/prices, visual direction. Both paths use the same image generator; no separate logo/name/contact layers for new posters.
- Up to three product photos, an independent visual reference and independent supplied logo. Reference can guide layout or style. Shop kit is optional with an explicit identity summary. Existing kit styles now seed Libre correctly.
- Later corrections can replace/remove inputs, and an earlier version can be the explicit base. Every successful version retains its context. Failed requests leave the successful state intact; exact retries retain their original server-owned inputs and prompt.
- Explicit prohibition on invented shop logos and borrowing reference facts/marks. Plain shop name remains allowed; genuine product markings are preserved as source content.
- Stable reading position, latest-result affordance, short result reveal, transform-based switches and static reduced-motion waiting indicators. Mobile/desktop use the same workspace.

## Defects found through real generation and addressed

1. **Extra contextual restaurant name:** an exact-copy menu printed “Vary”, though it was outside the requested text list. Added explicit exact-copy precedence and plain shop-name treatment. Targeted repeat: case 16.
2. **Reference overruled card count:** a one-card prompt inherited three cards. Layout references now adapt to the owner's subject/card count and prohibit duplicate products merely to fill reference slots. Targeted repeat: case 17.
3. **Quality anchor restored a superseded price:** a second correction reverted 95,000 Ar to 85,000 Ar. Version documents now retain accepted instructions and their chronological precedence; branching follows its own history. Initial history-only repeat 18 passed, but 19 still failed. Stronger final content constraints passed the explicit chain 20–21 and the same-base repeat 22.
4. **Retry after reload:** formerly reconstructed from current composer state. Now scoped retry_job_id reuses the exact failed request; profile edits cannot silently change it.
5. **Missing quality-anchor bytes:** now fail before provider dispatch rather than silently shifting numbered reference/logo inputs.
6. **Kit style action:** formerly changed an unused legacy default. It now supplies a reference or editable direction to Libre. Removed the obsolete global title control and corrected help text.

## Verification

Production build and 420 frontend tests passed. Backend suite passed in three nonoverlapping groups: 893 + 557 + 692 = 2,142 tests, three opt-in tests deselected. The final nine focused backend tests passed after the prompt/history/preflight/idempotency changes. Final production build and all 420 frontend tests passed. Unified browser passed independently at desktop and phone widths, including stale-tab rejection without spend and failed-job retry after reload.

Browser scripts: `frontend/tests/free_creation_browser.py` and `frontend/tests/unified_creation_browser.py`. Desktop light and phone dark cover preparation/draft preservation, photos/reference/logo, kit, attachment replacement, removal, version branch, old Message links, kit style seeding, review/download, library reopening, stub Facebook publication, no credit, refusal and reload. Final narrow layout/reduced-motion checks use 360 px in addition to 390 and 1366 px. The old all-in-one wizard/chat browser suites still encode retired new-creation routes; they are not evidence for this replacement flow.

Paid evidence: `outputs/unified-creation/paid_browser.py`, `paid-report.json`, individual output PNGs and browser captures. Real app browser/API, isolated ledger, Flare medium, $5 cap. Three process interruptions occurred while a provider request was in flight; each retains a conservative $0.40 estimated cost, distinct from successfully recorded usage. No automatic ambiguous replay: stored job status was inspected before fresh attempts. Completed outputs are resumed without spending again.

## Limits

These are inspected scenario results, not a guarantee for every possible prompt. Images still require human checking of spelling, prices, contact details, product fidelity and logo fidelity. The model redraws supplied logos/products; exact pixels are not promised. Instruction history retains the original brief and twelve latest accepted requests; very long chains rely on the current image for older changes. Existing free documents recover their selected base's last instruction. No physical-device performance profiling, real Facebook post, production rollout or cross-model benchmark was performed.

## Final results

22 completed real generations inspected. Four initial/intermediate outputs (02, 04, 08, 19) exposed defects; their targeted final repeats passed. Scenario 19 was a branch from version 2 rather than a continuation of case 18; database payloads verified the true chain 18 → 20 → 21, and case 22 repeats 19 from the same base. Current tested scenarios produce usable posters, but prompt changes cannot guarantee every future model output.

Successful-call usage: **USD 1.001507**. Three interrupted calls retain **USD 1.20 estimated total** (not confirmed invoice amounts). Implementation trial ledger: **USD 2.201507**, within its $5 cap. Earlier research's USD 0.374239 is separate. Generation times for completed outputs were approximately 15–26 seconds, excluding interruptions and browser setup.

[Visual gallery with prompts and browser captures](../../../outputs/unified-creation/gallery.html). All evidence is local under ignored outputs/; the report is the version-controlled record.

| Case | Result |
| --- | --- |
| [01-short-no-image](../../../outputs/unified-creation/01-short-no-image.png) | Short prompt, no image: readable celebration, no invented business facts. |
| [02-detailed-no-image](../../../outputs/unified-creation/02-detailed-no-image.png) | Initial failure: contextual restaurant name added outside the exact text list. Superseded by 16. |
| [03-short-photo](../../../outputs/unified-creation/03-short-photo.png) | Short product prompt: recognizable supplied headphones and correct price. |
| [04-short-photo-reference](../../../outputs/unified-creation/04-short-photo-reference.png) | Initial failure: reference card count overrode the one-card request. Superseded by 17. |
| [05-reference-only](../../../outputs/unified-creation/05-reference-only.png) | Reference style only: no copied products, price or shop identity. |
| [06-three-products](../../../outputs/unified-creation/06-three-products.png) | Three products: correct individual prices and contact. |
| [07-price-correction](../../../outputs/unified-creation/07-price-correction.png) | Price correction: 85,000 → 95,000 Ar, other amounts unchanged. |
| [08-anchor-correction](../../../outputs/unified-creation/08-anchor-correction.png) | Initial failure: quality anchor restored 85,000 Ar. Superseded by 18 and 20–22. |
| [09-branch](../../../outputs/unified-creation/09-branch.png) | Earlier-version branch: original 85,000 Ar preserved, title changed as requested. |
| [10-kit-logo](../../../outputs/unified-creation/10-kit-logo.png) | Supplied logo retained without duplicating the shop name as a headline. |
| [11-kit-no-logo-foreign-reference](../../../outputs/unified-creation/11-kit-no-logo-foreign-reference.png) | No supplied logo: plain shop name/contact, no borrowed reference logo. |
| [12-override](../../../outputs/unified-creation/12-override.png) | Reference override: cream editorial layout, no cards, correct prices/contact. |
| [13-service](../../../outputs/unified-creation/13-service.png) | Service without source image: requested wording and contact only. |
| [14-new-photo-base](../../../outputs/unified-creation/14-new-photo-base.png) | Initial product image for the replacement test. |
| [15-new-photo-edit](../../../outputs/unified-creation/15-new-photo-edit.png) | New photo replaces headphones with speaker; correct model and new price. |
| [16-exact-copy-retest](../../../outputs/unified-creation/16-exact-copy-retest.png) | Exact-copy repeat passes: no extra restaurant name or logo. |
| [17-one-card-retest](../../../outputs/unified-creation/17-one-card-retest.png) | Card-count repeat passes: exactly one card and correct price. |
| [18-anchor-price-retest](../../../outputs/unified-creation/18-anchor-price-retest.png) | Anchor correction preserves 95,000 Ar with accepted instruction history. |
| [19-second-anchor-price-retest](../../../outputs/unified-creation/19-second-anchor-price-retest.png) | Intermediate failure: reused version 2, not the result of case 18; reverted to 85,000 Ar. Same-base repeat 22 passes after stronger final constraints. |
| [20-anchor-chain-contact](../../../outputs/unified-creation/20-anchor-chain-contact.png) | Correct base explicitly selected: larger contact, 95,000 Ar preserved. |
| [21-anchor-chain-border](../../../outputs/unified-creation/21-anchor-chain-border.png) | Next correction from 20: orange border only, all prices/contact preserved. |
| [22-anchor-same-base-retest](../../../outputs/unified-creation/22-anchor-same-base-retest.png) | Repeat of 19 from the same base: larger contact and 95,000 Ar preserved. |

Final keyboard/reduced-motion narrow-browser rerun passed after all application changes. `git diff --check` and local evidence links checked.
