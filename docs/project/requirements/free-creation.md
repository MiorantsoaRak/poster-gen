# Création libre

The owner authorized delivery on 2026-11-25 and delegated routine product decisions. The guided product conversation and step editor remain available.

| ID | Acceptance |
| --- | --- |
| R-FREE-01 | From creation, a seller can open a separate French conversation on a phone or desktop. An initial prompt alone suffices, including requests without a product, price or writing. The app preserves the seller's wording. |
| R-FREE-02 | A seller can attach one or multiple ordered composition photos and one optional visual reference. The model receives the images themselves with distinct roles. The reference guides layout, hierarchy and visual treatment. An explicit direction wins over the reference and the optional default. |
| R-FREE-03 | A simple default composition is on initially and can be disabled. It supplies visual direction only. The app never adds commercial facts. |
| R-FREE-04 | One explicitly confirmed generation or polish uses one image credit. A seller can keep polishing the latest result while funded, under existing service availability and spending rules. Replaying a request never spends twice. A failed attempt preserves earlier work. |
| R-FREE-05 | The conversation reopens with its prompts and images. A seller reviews the final pixels, confirms the chosen current version, downloads that exact PNG and can start a Facebook publication using it. A later edit retains the earlier image and needs a new confirmation. |
| R-FREE-06 | Check on desktop and phone in Chromium, including a real download and a publication with the Facebook stand-in. Judge a real reference-guided image and polish visually on the pilot model. Preserve existing guided behavior and shop isolation. |

## R-FREE-07 — No invented shop logo

**Status: Approved by the owner, 2026-11-26.** Applies to the proposed unified creation experience as well as free creation. Not implemented or verified yet.

The owner accepted the UX research direction and clarified: “for the shop logo, if none is provided, we don't invent a logo”. This replaces the research suggestion that allowed an invented shop mark on explicit request.

Acceptance criteria:
- With no shop logo supplied or selected from the shop kit, the generation instruction explicitly prohibits inventing a shop logo, monogram, emblem or substitute brand symbol. Do not derive one from the shop name or business category.
- A requested shop name can appear as plain text, integrated into the composition; it is not a request to design a logo.
- A visual reference does not supply the seller's identity: its shop logo must not be copied or adapted as the seller's logo.
- With an explicitly supplied shop logo, use that identity and do not invent a replacement. Existing product markings in product photos remain product details, not a shop-logo source.
- The same rule applies to initial generations and corrections. A model output containing an invented shop mark when none was supplied fails visual acceptance; a successful API response alone is not evidence of compliance.

Verification: prompt-contract checks for initial/correction requests with and without a shop logo, plus real-model visual checks for a name-only request and a reference containing another shop's mark. These are future implementation checks; no new model calls were made to record this requirement.
