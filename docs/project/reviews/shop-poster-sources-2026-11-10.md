# Original Phone Mada — poster test source notes

The user requested a usable JBL or Soundcore Facebook/Instagram test poster and explicitly asked to use their Edge Facebook session. Implementation and a bounded real test under the existing spend cap are authorised (ADR-033). No posting or messaging is authorised.

## Shop identification

- The existing logged-in Edge session exposed the Facebook shortcut **Original Phone Mada**, linking to https://www.facebook.com/MiaryAndrian10/.
- No page navigation or live shop-post inspection succeeded. Computer Use reported missing coordinate geometry; fresh capture and recovery failed with `window capture timed out: timed out waiting on channel`. Stop UI input until a usable window is available. No login/password/cookie extraction was attempted.
- Public corroboration: https://www.findglocal.com/MG/Antananarivo/111875903561009/Original-Phone-Mada and https://www.globuya.com/MG/Antananarivo/111875903561009/Original-Phone-Mada identify the shop at Ankadifotsy, near the Shell station/opposite Vulka Atrika, with **038 93 028 00 / 034 93 028 00**. WorldPlaces also lists the latter phone number: https://madagascar.worldplaces.me/review/99731673-original-phone-mada.html.
- Display the verified public trading name **Original Phone Mada**. “Original Phone Madagascar” is the user's descriptive name, not evidence for redrawing/replacing the shop's logo.

## Candidate offer

- Search-index text from the FindGlocal page includes a **13 August 2026 Soundcore R50i offer at 90,000 Ar**, with 034 93 028 00 as its call/WhatsApp number.
- Opening that page returns a different, newer October snapshot without this offer. The indexed August offer is suitable only as a dated test fixture, not proof of current stock or price. Preserve this distinction in the test report and require current offer verification before publication.
- No source-backed Flip 7 or Motion 300 shop price has been found. Do not invent a price to reuse the earlier scene tests. No verified shop logo has yet been downloaded.
- Existing real test photos/scenes remain in `outputs/review-2026-11-09/`, with provenance in the previous review. They do not establish a current shop offer.

## Downloaded product reference

- Product page: https://www.anker.com.ph/products/soundcore-r50i (Anker Philippines; exact R50i, not R50i NC).
- Observed image link: https://www.anker.com.ph/cdn/shop/files/soundcore-r50i_1024x.jpg?v=1787208672
- Saved unchanged to `outputs/review-2026-11-10/soundcore-r50i-black-original.jpg`.
- SHA-256: `80f4f22af084b688e4612f9a295315bffa2fbdf9ec7015681a0325f9e4c11198`.
- JPEG, 1024×1024, RGB. Visually inspected: two black earbuds, open charging case, attached black/grey lanyard, white background; no external award or commercial overlay.
- Use only the exact product name/black variant as confirmed input. The Philippine price/warranty is unrelated to the Madagascar shop and must not be copied.

## Remaining test work

The feed application slice and real R50i test are complete. One GPT Image call integrated the original product into a scene without cutout; the reviewed poster was manually polished and exported through the exact preview/confirmation/download workflow. See [real test report](real-feed-poster-2026-11-10.md). No verified shop logo was available, so the real poster uses the source-backed name and contacts. Current offer verification is still needed before publication.
