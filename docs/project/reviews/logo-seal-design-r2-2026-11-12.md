# D-CATALOGUE-BRAND-006 (logo seal) — design review round 2, 2026-11-12

Fresh independent subagent, read-only, on draft v2 of the design and of R-CATALOGUE-BRAND-005, given what changed since round 1. Nothing was run. Line numbers are the reviewer's, at commit `9c88819`.

## Verdict: APPROVE WITH FIXES

P1:

- **The footer row was defined only for a drawn price, a drawn contact and no shop name.** Without a contact the price band is 86–95 % (`plans.py:159-163`), a 121 px row for a 130 px disc; a rendered contact keeps a full-width calm band the disc crosses (`plans.py:369-374`); with no drawn price there is no price sentence (`plans.py:355`); a ticked shop name puts a calm band across the row (`plans.py:158-175`). Fix: refuse the seal outside that one footer, and disable the option with the reason.
- **"Not the fixed plan" cannot be tested by the plan's source.** With any look the editor changes the palette and posts a plan revision (`App.vue:405-411, 429-431`), stored as `manual` (`visuals.py:170`). Fix: compare `product_region` and `overlay_regions` with `fixed_plan(context)`.

P2:

- **"Tested: yes, twice" was not true of v2's wording.** The tested prompt kept the two bands, the 91 % limit, 2 % digits and the disc at 90 %; v2's single row, 1.5 % digits and removed limit were new. Without a look the alignment is `centre` (`plans.py:215`), the untested row. Fix: mark both untested, or keep the tested sentences and add only the badge sentence.
- **A seal layer with the title option off** gets no disc, no reserved region and no placement rule (`service.py:150-151`). Fix: allow the seal only with the title option on.
- **"On by default"**: new posters only. Setting `shape` on a poster that has scenes makes refinement fail on `unselected_or_missing_overlay` (`plans.py:144`, `visuals.py:244-264`).

P3: the pill is asked at "about half the frame width" against a 37 % slot; "at the right of the disc" is wrong for the centred row; the help line "Gardez le logo à l’écart" contradicts the seal; `chooseVisual` must tick the logo again on a version with a disc after a not-found one.

Claims: (a) a seal logo left out of `context_for` gives the plan of a poster without a logo, and nothing else requires a region per layer: true; (b) the row fits the usual plan: true; (c) the centred row is geometrically possible: true; (d) the server can untick the logo and hide its layer in the first-scene transaction: true (`models.py:226-233`); (e) the fixed plan can be recognised only by comparing regions; (f) the 29-character arithmetic is right, on an unmeasured 12 px constant with no margin; (g) forcing the contact to the right conflicts with nothing on the server; the editor must override a remembered position without overwriting it.

Criteria not covered in v2: the "contact not drawn" choice of the too-long case; the eight combinations of R-CATALOGUE-BRAND-002 with the seal; "posters made before keep working" depended on the default-on fix.

## Outcome

v2.1: the seal is available only for the chosen footer (logo and contact, no shop name, title, price and contact drawn), set before the first scene and locked afterwards; the fixed plan is recognised by its regions; the prompt is the tested one plus the badge sentence, with the single-row wording, the 1.5 % digits and the 29-character limit removed; the centred-price place is marked untested; the remembered contact position is kept; `chooseVisual` ticks the logo again on a version with a disc. The requirement is reworded to match. Not re-reviewed after these fixes. Submitted to the user for approval.
