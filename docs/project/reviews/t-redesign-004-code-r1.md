# T-REDESIGN-004 — code review (Codex, 2026-11-21)

Verdict: APPROVE.

**Approve T-REDESIGN-004.** The frontend maps all four states correctly through `stateNames` on both Accueil and Mes affiches. `draft` shows « Brouillon » with the plain badge, `to_review` shows « À vérifier » with `.warn`, and `approved` and `confirmed` show « Approuvée » and « Confirmée » with `.ok`.

- **French and reading order.** No sentence or field order changed. In an active library row, the button’s contents read title → state → price → date → variant. Only the separator between state and price disappeared when the state moved to its own line. Accueil retains title → state. Removed rows retain « Retirée · prix · date · variante ». Thumbnails have empty alt text, icons are hidden from assistive technology, and the badge dot is an empty CSS pseudo-element drawn with a border. It contributes no spoken text.
- **Grid and selector.** Active rows have three central lines, with the thumbnail and chevron spanning all three. Removed rows have two, with `.details` directly below the title. The library template is the only producer of `.library-item`, and its details span always gets `.details`. The narrower selector leaves no other use unstyled.
- **Test coverage.** `four_states` rewrites the HTTP response while both Vue templates still render normally, so a swapped French label or tone would fail. A listing endpoint that returned `draft` for every real poster could still pass this smoke. There are two smaller gaps: `check_states` reads `textContent`, so it can miss a badge hidden from assistive technology, and the removal smoke restores the row without asserting its « Retirée » details or badge absence. An accessible-name assertion on an active gallery row and two assertions on the existing removed row would cover those cases.

Read-only source review. The passing checks are the implementer’s results. Screen-reader behavior was assessed from markup, without a device run.