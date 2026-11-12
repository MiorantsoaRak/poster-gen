# Shop signature, shop logo and brand mark — research, 2026-11-12

Research only: no code changed, no paid call. It supports the draft requirements R-CATALOGUE-BRAND-003 and 004.

## What exists today

- `compile_scene` draws the signature as a fixed centred block: a thin full-width rule, the shop name in spaced letters, then a handset icon and the numbers (`backend/src/affiche/posters/plans.py`).
- Measured on live run 6 (`outputs/style-study-2026-11-11/live-edge-6/scene.png`): the block takes about 9 % of the poster height; the digits are about 20 px tall on 1350. It is readable, but it reads as a second headline under the price pill.
- `align` (left or centre) exists for the headline and the price pill, taken from a saved look. The signature ignores it.
- The shop logo is only an editable layer at the left of the footer. It is never sent to the image model.
- The brand mark is drawn by the model from the typed brand, "written as on the product". No logo file is involved.
- The shop's ten reference posters carry no shop name, contact or shop logo: only brand mark, title, subtitle and price.

## Findings

1. **Contact.** One line (icon and numbers), digits about 22–24 px on 1350. This size is an estimate from the run 6 image; the search found no usable standard. A left, centre or right position, separate from the headline alignment. A left or right contact can share the price band, which frees about 6 % of the height for the product. The prompt must keep saying that these digits are a telephone contact, not a price.
2. **Shop logo.** Two ways: (A) the uploaded file composited by the renderer on a calm area: exact, no cost, no review point; (B) the logo sent as a reference for the model to reproduce: the provider guides describe the method (label the reference by role, name the placement, repeat a "preserve" list) but none promises exact reproduction, and nothing in the code would detect a wrong logo. A is recommended.
3. **Brand mark.** The current behaviour was correct for JBL, Sony, soundcore, harman/kardon and CMF. Weak spot: a lesser-known brand, or a photo that does not show the mark. Fallback: the brand as plain text.
4. **Permission.** Legal commentary says a reseller may name a brand to identify genuine goods; logos are treated more strictly and manufacturers' guidelines often require written permission. General information, mostly US-based, not checked for Madagascar.

Not checked: whether the logo layer (left of the footer) and the drawn signature (centred, full width) can overlap today.

## Sources

- [OpenAI GPT image models prompting guide](https://developers.openai.com/cookbook/examples/multimodal/image-gen-models-prompting-guide.md)
- [fal.ai GPT Image 2 prompting guide](https://fal.ai/learn/tools/prompting-gpt-image-2)
- [Atlabs GPT Image 2 prompting guide](https://www.atlabs.ai/blog/the-ultimate-gpt-image-2-prompting-guide-how-to-use-openai%E2%80%99s-best-image-model-2026)
- [Wisconsin DHS accessibility guide](https://www.dhs.wisconsin.gov/publications/p03450f.pdf)
- [Fish & Richardson: third-party trademarks, fair use or foul](https://www.fr.com/third-party-trademarks-fair-use-or-foul/)
- [Kelley Drye on the Chanel resale ruling](https://www.kelleydrye.com/viewpoints/client-advisories/what-comes-around-how-chanels-win-may-help-brands-protect-their-rights-in-the-resale-market.md)
- [Logitech trademark guidelines](https://futureisnow.logitech.com/en-ca/tos/trademark-guidelines.html)
- [Pelican domain name and website policy](https://www.pelican.com/storage/downloads/Pelican-Domain-Name-and-Website-Policy_v5-2018-0524.pdf)
