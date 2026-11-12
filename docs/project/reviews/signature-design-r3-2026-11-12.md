# D-CATALOGUE-BRAND-004 — design review round 3, 2026-11-12

Fresh independent subagent, read-only, given draft v3 (contact drawn in the composition again, ADR-055) and what changed since the built v2.1. Line numbers are the reviewer's, at commit `68e7178`.

## Verdict: APPROVE WITH FIXES, no P1

The three round-1 P1s are answered for the fixed plan, which is the only mode the editor sends (`App.vue:24`).

P2:

- **Fit rule against the prompt size.** The divisor 19 assumed 32 px digits, but the prompt asks for 2 % of the frame height (27 px), about 22 px per character. Fix: divide by 23 (about 40 characters full width, 33 beside the logo).
- **Price wording when the price is not drawn.** "smaller than the price; entirely below the price label" was unconditional; with `headline.price` false the price band is a quiet area (`plans.py:338-340`). Fix: add both clauses only when the price is drawn and the contact lies below it.
- **"contact region" wording.** `_band` turns any box at least 0.8 wide into "the full-width band" (`plans.py:201-205`), so "left edge" would mean the frame edge. Fix: always use `_area`.
- **Hard limit.** A ticked shop-name layer sits above the contact (`plans.py:170-172`) and was left out. Fix: the highest of the logo, shop-name and contact boxes below the price.
- **"The logo is always at the left".** True for the plan box only; layers are placed on the first scene only (`service.py:144`) and the owner may drag the logo. Fix: show the notice whenever a contact is drawn and the logo is shown.

P3:

- The hard limit would change the prompt of refinements of stored scenes (`visuals.py:251`).
- The review label is "Boutique et contact" today (`App.vue:222`).
- The position select is disabled when the contact is drawn (`App.vue:652`); the layer says `center`, the field `centre`.
- `signature: true` without `signature_align` would still draw the shop name (`plans.py:320`).
- The drawing option needs `headline.on` (`App.vue:141`).
- `screen_headline` can refuse a contact the editor allows (`plans.py:316`).

Claims: (a) a line aligned inside the contact region cannot be under the planned logo box: true for the fixed plan, false for a dragged logo or a Claude plan sent through the API; (b) passing only the contact passes the existing validation and the export guard, if the payload stores the filtered dict: true; (c) the contact layer is hidden when drawn and shown when not: true; (d) an omitted `signature_align` keeps stored payloads and the ADR-043 signature sentence: true; not for the price sentence; (e) `staleSignature` is correct with only the contact drawn; the notice and the review label still name the shop; (f) the hard limit can be computed from the plan boxes: true; (g) the character rule does not conflict with the 80-character rule: true.

Criteria not covered in v3: "confirmed with its cost" for a new position (not stated). "Never overlap" is covered for planned areas only, as the requirement is worded.

## Outcome

Every finding is fixed in v3.1 of the design text. Not re-reviewed after these fixes. Submitted to the user for approval.
