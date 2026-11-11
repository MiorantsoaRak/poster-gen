# Shop-style study — 2026-11-11

Goal: make generated posters match Original Phone Mada's own recent posters. Result: reached on 9 real products; the change is in the application (ADR-042).

## References

Twelve recent posters were opened on the shop's Photos tab; ten were captured as screenshots (about 495 px) in `outputs/style-study-2026-11-11/references/`: JBL Live 770NC, JBL Tune 770NC, JBL Tour One M3, Sony WH-1000XM6, Soundcore Q45, Soundcore Select 4 Go, CMF Buds 2A, CMF Headphones Pro, Galaxy Buds4 Pro, Harman Kardon Onyx Studio 9. The originals are 1254 × 1254 or 1086 × 1358.

Common style:

- Square (some 4:5). Product fills about 60–70 % of the frame, three-quarter angle, slightly tilted, floating over a soft shadow.
- Calm gradient backdrop with two or three large curved bands, tinted to the product or brand (lilac, blue, champagne); black with gold light arcs for premium models.
- Brand mark, heavy sans product name with one word in the accent colour, small widely spaced subtitle between thin rules.
- Dark rounded price pill at the bottom, white digits, smaller "AR". No shop name or contact.

## Method

Direct GPT Image 2 (high) calls with one official product photo each, 1088 × 1088. Product photos and their sources: `products/sources.json` (five manufacturer images, two retailer images; five were flattened from transparent PNG onto white). Prompts, images and cost per call: `results/` and `spend.json`.

| Round | What changed | Result |
| --- | --- | --- |
| r1 (3) | New text-free prompt: house style, product scale, quiet bands. With and without a shop poster as style reference. | Scale and backdrop fixed. The style reference added little over the text. |
| r2 (2) | Same, and the model sets brand, name with accent word, subtitle. | Text verbatim, typography at reference level. |
| r3pre (1) | The application's compiler. | Found two prompt defects: an example sentence made the model add earbuds to a speaker; the product ran into the price band. Both fixed. |
| r3 (7) | Fixed application prompt on 7 products that the shop has posters for. | 7 of 7 usable: text verbatim (including "À RÉDUCTION DE BRUIT"), product faithful on visual check, price band left clear. |

Checked by eye at full size: JBL Tune 770NC against its source photo (shape, buttons, logo, colour match). The other six were checked on contact sheets only.

## End-to-end through the application

`run_app_poster.py`: JBL Tune 770NC, feed 1080 × 1350, look "Aux couleurs du produit", integrated headline, price pill layer. One scene call, USD 0.208268, recorded in the `data-probe` ledger (1.161964 → 1.370232). The application hid the title layer itself, fidelity was approved, the render had no warnings, and the confirmed download equals the preview: `app-poster-final.png`, SHA-256 `58c6bd98e8be665cb7843b46c026b4808752ca1f5788848a01dea1c798837a37`. 340 000 Ar is the price printed on the shop's own poster for this model; it is test data.

## Follow-up the same day: pill, one tap, live Edge test

- A look now styles the price pill and the shop name/contact; one "Générer la scène" tap makes the plan and the scene; the last look, colour and brand are remembered on the device.
- Live run in installed Microsoft Edge 156 with the real provider (`live_edge.py`, evidence in `outputs/style-study-2026-11-11/live-edge/`): Sony WH-1000XM6, "Luxe sombre". Every UI step passed, the headline was verbatim, and the confirmed download equals the preview (`live-edge-poster.png`). Cost USD 0.204877, in the ledger (→ 1.575109).
- It exposed two defects, fixed afterwards and re-checked with the stub smoke in Edge only: white footer text on light looks, and a properties panel for the hidden title.
- Still open: the product ran below its planned area and the pill covers the bottom of the ear cup; with shop name and contact the footer looks empty.

## Exploration: a style brief written by Claude from a reference poster

Question: can the owner upload a poster he likes and let Claude write the composition prompt?

- Method: `explore_reference.py`. Claude sees one shop poster and returns a validated brief (French direction and surface, lighting, camera, palette, accent colour, English headline typography). The brief fills the application's own plan and prompt; GPT Image then makes a poster for a product the reference never showed. Two cases: Tour One M3 poster → Soundcore Space Q45; Select 4 Go poster → CMF Buds 2a.
- Carried over: backdrop treatment, palette, and headline typography, including the outlined pill around the subtitle. All text and both prices exact.
- Not carried over: layout. The Select 4 Go poster is left-aligned with the price pill at the left; the result is centred, because the prompt fixes where the headline and price go. One of two results did not colour the accent word.
- Safety: the brief is screened like any art direction (no prices, currency, long numbers, instruction wording), and the instructions tell Claude to leave out brand, product and any text in the image. Neither brief carried any.
- First attempt failed validation: an accurate brief of about 900 characters against a 400 limit. Stating the limits in the instructions fixed it.
- Verdict: feasible and cheap (about USD 0.007 per brief, then a normal scene). Worth building as "create a look from a poster" with a saved, reusable look; it needs a typography field and an alignment choice in the prompt to be faithful.

## Limits

- Ten headline images are a small sample: spelling must still be checked at the fidelity review.
- The brand mark is drawn by the model from the product photo and its own knowledge; it was correct for JBL, Sony, soundcore, harman/kardon and CMF here, and may be wrong for a lesser-known brand.
- Square and story export remain T-POSTER-009; the study images are square, the application poster is feed.
- No physical phone test. Study spend (USD 3.05) is outside the application ledger.

## Research used

Prompt order, reference-role labelling, "name the parts" of a style, quoted verbatim text and avoiding praise words come from [fal.ai's GPT Image 2 guide](https://fal.ai/learn/tools/prompting-gpt-image-2) and OpenAI's [image prompting cookbook](https://developers.openai.com/cookbook/examples/multimodal/image-gen-1.5-prompting_guide) and [image generation guide](https://developers.openai.com/api/docs/guides/image-generation). `input_fidelity` stays omitted for gpt-image-2, as the OpenAI guide says.
