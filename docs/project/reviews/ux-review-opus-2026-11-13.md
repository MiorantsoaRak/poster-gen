# UI/UX review, second round (Opus, 2026-11-13)

Asked by the user after the first round (reviews/ux-review-2026-11-13.md): "do the same thing to see if you see more improvement to make on the UI / UX. Think of a modern UI style, mainstream but not the generic UI chosen template. If you are not sure, come up with a mockup in an artifact first."

## Method

- Every screen looked at from the smoke's screenshots (desktop, phone, both themes).
- A scripted walk as a **first-time user on empty stub data**, at **360 × 740 with a touch pointer** (a low-end Android phone) and at 1366 × 768, serving the built frontend from the API on its own port. Per screen it measured: where the first control starts, how much of the poster is in view while typing, controls under 44 px, nested scroll areas, text under 12 px, native controls, fixed and sticky chrome. Awkward but ordinary input: prices as owners write them, a 61-character title.
- The failure-path checks from the memory note on UX audits (refusals, collapsed sections, hidden rules) were rerun: no required control is collapsed any more, and every refusal has a sentence (test in tests/test_api.py).

## Findings

| # | Sev. | Finding (measured) | Status |
|---|---|---|---|
| 1 | P1 | **Prices as owners write them were refused**: « 90.000 », « 90 000 Ar », « 90000ar » and « 90 000 » with a trailing space (phone keyboards add one) all answered « Saisissez un montant entier en ariary. ». Only « 90 000 » and « 90000 » passed. | Fixed: dot or space groups of three, an optional « Ar », « ariary » or « MGA », stray spaces. The comma stays refused (the French decimal mark; an amount is never guessed). The message gives two examples. 14 new unit cases |
| 2 | P1 | **Sticky hover on touch**: after « Continuer », the next primary button is drawn under the finger and keeps the hover look (`opacity: .86`); « Générer l’affiche » looked disabled. | Fixed: hover looks only under `@media (hover: hover)` |
| 3 | P1 | **The review and the final check on a phone**: 2.3 and 1.5 screens tall, with the decision buttons at the very end. | Fixed: on phones the decision bar is fixed at the bottom of the screen. Smoke: in view without scrolling at 360 px |
| 4 | P1 | **« Mes affiches » at 360 px**: the subtitle squeezed to one word per line, the checkbox over the heading. A phone rule written for the editor's title row (`nowrap`) caught the lists' rows. Never seen before: the smoke only checked for horizontal overflow. | Fixed: the lists' title rows wrap. Smoke: no overlap, subtitle wider than 300 px |
| 5 | P2 | **Native file controls**: « Choose Files / No file chosen » in the browser's language, a small button, on the photos, the logo and the reference poster. | Fixed: the input covers its label, transparent; the label shows « Ajouter des photos », « Choisir le logo », « Choisir une affiche » (and « Changer… » once chosen). Keyboard focus ring on the label |
| 6 | P3 | « Variante confirmée » and « Prix » side by side at 360 px: « Conforme à la p… » cut. | Fixed: stacked on phones |
| 7 | P3 | The vendor's name in the owner's path: « Estimation Claude », « Claude décrit le style… », « une fois Claude configuré ». | Fixed: neutral wording. Costs in $US stay: the administrator asked to see them (owner vocabulary is T-REQ-AFTER-PILOT) |
| 8 | P3 | Left by the first round: a refusal line stayed after the brand or subtitle was corrected; « Aux couleurs du produit » uses the accent colour of « Textes » without saying so; an unused icon; the phone bar's main action never used at phone width by the smoke. | Fixed; the smoke now generates, confirms and reviews at 360 px |
| 9 | P1 | **On a phone the poster is never in view while editing it.** Steps: a 104 × 130 thumbnail. After the first version: poster at 479 px, tabs at 1,289 px, the first field at 1,725 px; while typing the price, 0 % of the poster is on screen. | **Mockup**: the poster stays on top, the tools under it (structure of mainstream mobile editors) |
| 10 | P1 | **Chrome before content on a phone**: the first field of « Textes » at 665 px of a 740 px screen, behind the bottom bar (sticky two-row header 109 px, demo banner, title block, coach card). « Style »: the first control at 931 px. | **Mockup**: a one-row editor bar (back, title, undo, redo); the three destinations in a bottom bar outside the editor; the step itself replaces the coach card |
| 11 | P2 | The review's two images are stacked on a phone: they can never be compared at the same time. | **Mockup**: one image at full width, « Votre photo / La version » toggle |
| 12 | P2 | The look reads as a settings form beside a preview: uniform weights, checkboxes for show/hide, numeric X/Y fields as the way to place things. | **Mockup**: switches, larger type hierarchy, shape change on selection, « Réglages » by element |
| 13 | P3 | The « Versions » column is empty before the first version (desktop); on a phone the versions sit between the poster and the tools. | **Mockup**: a version strip under the poster, shown once there is a version |
| 14 | P3 | The shop's show/hide choices are asked twice: on the first screen and in « Boutique ». | **Mockup**: only in « Boutique »; the first screen keeps the product |

## The proposed direction (mockup: https://claude.ai/artifact/6JoS82gMXkucaat4FKvUia)

- **Structure, phone first.** The poster stays visible at the top and changes as you type; the step or the tool is a sheet under it. After the first version: the poster, a strip of versions, four tools in a floating bar, one main action. The fidelity review shows one image at a time. Outside the editor, « Créer », « Mes affiches » and « Styles » are a bottom navigation bar. This is how Canva, CapCut and Instagram's editor work on a phone, so the owner already knows it.
- **Look.** Follows the phone's light or dark setting (today the app is dark until switched). Light: warm off-white ground, white surfaces, ink-black main buttons, the existing amber as the only accent (selection, progress). Large rounded shapes, a selected item changes shape as well as colour, switches for show/hide, a floating tool bar: the spirit of Android's current Material 3 Expressive style, which is what the owner's phone looks like. No gradients, no dashboard cards, no Inter.
- **Type.** Figtree for the interface (OFL, two small files bundled with the app, no network); the posters keep their own fonts.

## Not checked

A real phone and its keyboard (Playwright cannot open a virtual keyboard: a poster kept on top must shrink while typing, to be checked on the device); Safari and Firefox; a screen reader; the scene adjustment, text proposal and texture paths with awkward input.
