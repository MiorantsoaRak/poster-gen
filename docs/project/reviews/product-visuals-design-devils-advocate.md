# product-visuals design — devil's-advocate pass (once per design)

Reviewer: Claude general-purpose subagent, 2026-11-06, read-only, on design draft r1. Only the points that would change a decision are kept. Each line gives the summary and the disposition.

1. **The prompt's "no logos/text anywhere" contradicts "keep the product's logo".** Product markings (brand, "5G", camera text) would be erased. Front+back photos fail "one product". → **Accepted.** The prompt now bans only *added* text. Requirement wording amendment proposed (R-003 c.2, R-004 checklist).
2. **The evaluation cannot test its own revisit conditions** (limit 3, n=1, correction text never compared with a plain re-roll). → **Accepted as a user question:** an evaluation-only exception (limit 5, plain re-roll arm on half the products).
3. **The empty background + pasted cutout looks "pasted"** (light, perspective). The reason codes cannot record it. → **Partly accepted:** reason code `integration` proposed; a background arm with the product composited is kept as a follow-up if the evaluation shows integration rejections.
4. **Soft mask + original RGB → halo** of the original background at the edges. → **Accepted:** binary mask, hole fill, 2 px erosion; the pixel test runs on A=255.
5. **DQ-5:** building the phase-2 UI before the evaluation delays the evidence that may change the flow. → **Accepted:** phase-1 contact sheet + decisions CSV; phase 2 after the evaluation recommendation.
6. **Missing usage → cost per approved visual is circular.** → **Accepted:** dedicated OpenAI project; billed totals recorded per batch; probe call to check `usage`.
7. **DQ-4 per-chain limit contradicts the approved "per product variant".** → **Accepted:** per variant, since its last approved visual, allocated atomically.
8. **LAN without auth; no idempotency.** → **Accepted:** one API token exchanged for an HttpOnly cookie; a client-generated request UUID.

Notes kept without a decision change: SQLite, rembg, in-process asyncio, global cap, no cancel endpoint, 1088×1920 master; budget check + insert under `BEGIN IMMEDIATE`; async OpenAI client; rembg off the event loop; product height ratio to tune.
