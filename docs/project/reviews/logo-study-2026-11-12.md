# Shop logo in the composition — study, 2026-11-12

Question from the user, with the shop's logo supplied: how to bring the logo into the composition. He gave autonomy for the paid tests. No application code was changed.

Files: `outputs/style-study-2026-11-11/logo-study/` (Git-ignored). Runner: `outputs/style-study-2026-11-11/logo_study.py`.

## The logo

960 × 960 JPEG-like image on white: a thin gold phone outline, a wide ribbon of red, white and green stripes passing behind it from edge to edge, "ORIGINAL PHONE" and "MADAGASCAR" underneath. The mark is 1.9 times wider than high once the white margin is trimmed. The profile in `data-probe` has no logo; the file was not added to it.

For the composites, the white touching the border was made transparent (`logo-transparent.png`); the phone's white body and the white stripes are kept. This derived file is for the study only.

## What was tried

Same product, look and texts as live run 8 (CMF Buds 2a, "Vagues bleues", price at the left, contact drawn at the right). The paid prompts are the application's own prompt for that scene with a logo rule and a placement sentence added (`*.prompt.txt`).

| Variant | How | Cost | Result |
|---|---|---|---|
| `file-top-right` | Real file composited on the run 8 scene, 250 px wide, top-right corner | free | Exact logo. The corner was empty in this left-aligned look, so it sits cleanly beside the title. Nothing guarantees that corner is empty in a centred look. |
| `file-footer-centre` | Real file composited in the footer of the run 8 scene | free | Collides with the contact: the scene had kept no room for it. Same weakness as the rendered contact (ADR-055). |
| `logo-drawn-top-right` | The logo is sent as a second reference image; the model draws it top-right | USD 0.219590 | Composes well; the model moved the title slightly to make room. Lettering and phone outline right. |
| `logo-drawn-footer` | Same, drawn at the bottom centre between the price and the contact | USD 0.219620 | Composes very well: the model shrank the pill and made a three-part footer (price, logo, contact). All texts exact. |

Close-up of the two drawn logos beside the real one: `compare-logos.png`. Four posters side by side: `compare-posters.png`.

## Fidelity of the drawn logo

Recognisable, not exact, in both scenes:

- The phone outline and both lines of lettering match in shape, weight and spacing.
- The ribbon is redrawn: thinner bands in a different order, less white between them, a darker green; the footer version has bluish tints. The ribbon is also shorter than in the file.

The stripes carry the national colours, so this is the part a customer could notice. Two scenes are a small sample.

## Reading

- Drawn by the model: the logo is truly part of the composition and the footer balances itself, but the brand mark is an imitation that only the owner's eye checks.
- Real file as a layer: exact, but it only looks placed when the scene happens to leave its spot empty, which the model does not reliably do.

Not tried: the real file pasted over the logo the model drew (it needs the drawn logo to be located in the image); a dark look; a centred look; the logo at the application's current size and place (128 px, footer left).

## Second round: the logo in a round badge (user request)

The square logo cut to a white disc (`logo-circle.png`): the ribbon then runs from edge to edge of the circle, and the disc brings its own background.

| Variant | How | Cost | Result |
|---|---|---|---|
| `round-file-top-right` | Real badge composited on the run 8 scene, top-right corner, 19 % of the width | free | Exact logo, reads as a seal beside the title. Works because that corner was empty. |
| `logo-round-drawn-footer` | The model draws the badge with the logo inside, footer centre | USD 0.219780 | Composes very well (price, badge, contact). The ribbon is again redrawn: more bands, orange and blue tints. |
| `logo-round-empty-footer` | The model draws only an empty white disc in the footer and composes around it; no logo image is sent | USD 0.211208 | The disc is clean, empty, and well placed between the price and the contact. |
| `round-file-on-empty-disc` | Real badge pasted on that scene at the planned place and size (19 % of the width, slightly enlarged) | free | Exact logo. It covers the disc but comes within about 11 px of the price pill, because the disc the model drew is smaller than asked. |
| `round-file-fitted-to-disc` | The disc is located in the image (the white region around its planned centre) and the real badge is printed exactly on it | free | Exact logo, exactly where the model made room. Small: the disc is 159 px, so "MADAGASCAR" is hard to read. |

Measured on `logo-round-empty-footer`: disc centre at 50.3 % of the width and 88.7 % of the height (asked 50 % and 89.5 %); diameter 14.6 % of the width (asked 19 %).

Sheets: `compare-round.png` (the four posters), `compare-round-logos.png` (the real logo, the drawn badge, the real badge fitted to the disc).

Reading: an empty white disc is an object the model draws and composes around, unlike a "calm area" it is only asked to keep free. Printing the real file on that disc gives an exact logo that sits in the composition, and a plain white disc is easy for code to locate. Open points: the model drew the disc smaller than asked, on one sample; the logo is then small; not tried on a dark or a centred look.

## Third round: a smaller footprint (user request)

Runner for the free steps: `outputs/style-study-2026-11-11/logo_fit.py`.

- Free mock-ups on the run 8 scene, badge between the price and the contact (`compare-small-footers.png`): the full logo at 130 px and 100 px, and an emblem-only badge (the phone and the ribbon cut from the logo, without the lettering) at 100 px and 80 px. At 100 px the lettering of the full logo is no longer readable. The emblem stays clear at 80 px.
- One paid scene, `logo-round-small-empty-footer` (USD 0.211303): the model draws an empty disc asked at 10 % of the width, centre at 50 % and 90.5 %. Found by the program at 50.0 % and 90.9 %, diameter 10.7 % (116 px). The model kept the price and the contact clear of it.
- The real badge printed on that disc, full logo and emblem only: `small-fitted-full.png`, `small-fitted-emblem.png`, side by side with the bare scene in `compare-small-fitted.png`.

Reading: at this size the method still works, and the disc came out at the size asked (unlike the 19 % request of round two, which came out at 14.6 %). The full logo is then a white seal with unreadable lettering; the emblem-only badge reads clearly. The emblem is a crop of the logo, so using it is the owner's decision.

## Spend

Five calls, USD 1.081501, outside the application ledger, recorded in `outputs/style-study-2026-11-11/spend.json` (study total 5.277673; its budget was raised from 5.0 to 5.6 for the later rounds, on the user's go for paid tests).
