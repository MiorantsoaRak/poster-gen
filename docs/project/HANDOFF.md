# HANDOFF

**Session date:** 2026-11-26
**Working on:** T-UNIFIED-01–03 and T-UNIFIED-PUSH — complete

## State of the world

Unified creation is committed as **`b026b241eb5ec170860376431a38283ed183b674`** and pushed to **`origin/main`** on the owner's “commit and push, then handoff”. Libre is the primary flow; Pas à pas prepares the same prompt; new Message entry points are removed. Existing saved product posters still open in their legacy editor. This delivery has **not been deployed**.

The owner authorized autonomous design/implementation, browser checks and paid generation. No supplied shop logo means no invented shop logo. All new poster text and identity go through the image model.

## Done this session

- Committed and pushed the 22-file verified implementation, requirements/design, tests and reports as `b026b24`.
- Reconciled TODO and recorded this concise handoff. This documentation update follows the implementation commit.
- Checked commit scope and whitespace; `.impeccable/`, secrets and ignored outputs were excluded. No application code changed or tests rerun during this commit/push follow-up.
- Earlier completed validation: backend regression **2,142 passed**, 3 opt-in deselected, then **9 final focused tests passed** after prompt/history/idempotency changes; production build and **420 frontend tests passed**.
- Browser: `free_creation_browser.py` passed desktop/phone confirmation, PNG download, library, simulated Facebook publishing, no-credit and refusal paths. `unified_creation_browser.py` passed 1366/390 px with a 360 px narrow check, keyboard, reduced motion, attachment replacement, kit/logo removal, version branching, old links, stale tabs without spend and exact retry after reload.
- Paid: **22 completed outputs inspected**, four initial/intermediate failures retained with successful final repeats. Successful usage **USD 1.001507**; three interrupted calls retain **USD 1.20 estimated**, not confirmed invoice charges. Ledger **USD 2.201507** within $5 cap. Earlier research's USD 0.374239 is separate.

## In progress — exact resume point

- **Task:** none unfinished for unified creation. T-UNIFIED-01–03 and T-UNIFIED-PUSH are done.
- **Where I stopped:** implementation pushed; this handoff is the documentation follow-up. No pending source edit. Next operational step is the owner's release using `deploy/README.md`; do not deploy without that instruction.
- **Mental context:** a quality-reference image can restore old prices. `backend/src/affiche/posters/free_creation.py:prompt` now reiterates accepted instructions as final content constraints. `enqueue`/`finish` retain version context/history; `turn` branches by same-creation render or retries the exact failed server payload. Original brief plus twelve latest instructions are retained; legacy documents recover their chosen base's last instruction.
- `frontend/src/FreeCreation.vue` owns both Libre and guided preparation. `App.vue` redirects new/old Message addresses appropriately and carries kit references/directions into Libre. No migration or new dependency.

## Landmines / gotchas discovered

- Model output still needs human checking of prices, text, contact, product details and logo fidelity. The model redraws supplied images; inspected examples do not guarantee every future output. No automatic OCR assurance or model fine-tuning was introduced.
- Paid failures: extra contextual restaurant name (02), copied card count (04), restored old price (08 and 19). Final repeats 16/17 and 20–22 passed. Case 19 branched from version 2; verified actual chain is case 18 → 20 → 21, with case 22 repeating 19 from the same base.
- Missing quality-anchor bytes fail before provider dispatch. Omitted correction fields retain context; explicit null can remove it, and idempotency hashing distinguishes these. Exact retry keeps its original identity even if the shop kit changed.
- Existing all-in-one wizard/chat browser scripts encode retired new-creation routes. Use the free/unified scripts for this delivery; old document access was explicitly tested.
- Paid scripts and PNGs are **git-ignored local evidence** under `outputs/unified-creation/`. Do not run paid generation merely to reopen results. Three process interruptions were recorded and inspected before fresh attempts.
- `/tmp` is memory-backed; full regressions used a workspace TMPDIR and smaller groups after an interrupted full run. No physical-device performance profiling, real Facebook post, cross-model benchmark or deployment was performed for this delivery.
- Other tracks' existing TODO entries (including T-FB-006 and T-HOST-009) retain their own pending-proof notes. Their production status was not revalidated here.

## Uncommitted / dirty state

The implementation and follow-up handoff are committed on `main`. The only expected untracked state is pre-existing **`.impeccable/config.json` and `.impeccable/design.json`**, intentionally untouched. Ignored output evidence remains local. No service was started by this commit/push follow-up.

## Next session should

1. Read [the acceptance report](reviews/unified-creation-acceptance-2026-11-26.md), [requirements](requirements/unified-creation.md) and [design](designs/unified-creation.md). No new implementation task is pending approval here.
2. On the owner's release instruction, follow `deploy/README.md` for the pushed revision, then check Libre/Pas à pas and a saved legacy poster in the released build. Release remains the owner's operation.
3. For a reported generation regression, inspect the exact selected base and accepted history before changing prompts. Compare [the local gallery](../../outputs/unified-creation/gallery.html); paid inputs, outputs and ledger are in that directory.

## Decisions made this session

- Explicit owner authorization covers committing and pushing the verified delivery and its handoff; it does not request deployment.
- Keep unrelated local `.impeccable/` files and ignored paid evidence out of the commits.
- The full preceding multi-session handoff is preserved [at implementation commit b026b24](https://github.com/MiorantsoaRak/poster-gen/blob/b026b241eb5ec170860376431a38283ed183b674/docs/project/HANDOFF.md), also accessible with `git show b026b24:docs/project/HANDOFF.md`. Do not re-derive those historical tracks from source. Details of this delivery remain in [DECISIONS](DECISIONS.md) and the acceptance report.
