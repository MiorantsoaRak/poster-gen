# D-CATALOGUE-BRAND-006 (logo seal) — design review round 1 and devil's advocate, 2026-11-12

Two independent subagents, read-only, on draft v1 of the design and of R-CATALOGUE-BRAND-005. Line numbers are theirs, at commit `9c88819`.

## Fresh review: REWORK

P1:

- **Refinement is refused once the seal is placed.** `context_for` measures the logo layer (`visuals.py:103-108`) and `validate_plan` raises `overlay_too_small` when it exceeds the planned box (`plans.py:146-149`): the planned logo is 128 px (`store.py:179`), the seal 134 px.
- **The geometry was never tested with the application's plan.** The study's prompt had no logo region (price band 79–88 %, contact from 91 %, disc at 90 %). With a logo selected, `fixed_plan` gives price 73.5–82.5 % and contact 85.5–89.1 %, the price hard limit still says "above 86 %", and the default pill is centred, directly over a disc at 50 %.

P2:

- The fit rule is unchanged: a right-aligned contact over 16 characters reaches a disc at 50 % by the design's own estimate; the shop's contact has 29.
- Ticking the logo again calls `placeFooter`, which puts it at the left margin, not on the disc (`App.vue:102-108, 179-181`).
- The cover guard "contains the centre and at least as large" passes a logo half a diameter off.
- The review shows the raw scene (`App.vue:740`), where the disc is empty, so "the logo sits on its disc" cannot be judged there.
- Disc not found: the logo's planned place was removed from the calm areas, so nothing is reserved for it, and the logo cannot be hidden while selected (`models.py:231-232`).

P3: `chooseVisual` and `shape`; the 1088 to 1080 conversion; the option needs the headline on (`App.vue:143`); "cover" against `fittedImage`'s contain (`PosterCanvas.vue:79`).

Claims: (a) `placement_json` can hold the disc without a migration: true (nullable text; its CHECK concerns `photo_preserved` only, `0007_poster_visuals.py:28, 34-35`; nothing reads it); (b) first-scene placement in the same transaction: true; later scenes move nothing on the server; (c) the export guard has the visual row and the layer boxes in scope: true; (d) a circular clip is feasible in the shared canvas: true, not run; (e) Pillow flood fill is enough: true, crop first; the threshold is a summed channel difference; nine seeds on such a window take 0.3–0.4 s; a synthetic disc with a shadow on pure white was found; (f) the planned centres can collide with the pill or the contact: yes; (g) refinement keeps `logo_seal`: yes, but the request was refused first.

Criteria not covered in v1: a place per price position; the 12 % size untested; "nothing is drawn under it"; the amendments to R-CATALOGUE-BRAND-002.

## Devil's advocate

Would change the design:

1. **"Not found" had no guard**: the logo would stay at its plain place, on the price pill in the tested look, with one warning line as the only signal.
2. **The cover guard is too loose**: require the layer's circle to cover the disc's circle.
3. **The disc need not be white**: the seal covers it, so a flat keyed colour could be found on any backdrop. Untested; the model may tint it.
4. **The seal's size is the model's**: a 116 px disc gives unreadable lettering with no warning. Warn under about 125 px.
5. **Untested positions**: ship only the tested layout; keep the plain layer elsewhere.
6. **One paid scene is too thin**: test the chosen variant at 12 %, a second look, and a white look.

Could not break: printing the real file (the drawn ribbon changed the national colours twice, and R-CATALOGUE-BRAND-002 forbids an imitation); detection rather than pasting blind (the measured offset exceeds the margin); the JSON column; an option that can be turned off.

## Outcome

v2 of the design and of the requirement: the seal is a property of the logo layer and is left out of the plan (the plan is then the study's plan, and refinements pass); one footer row with stated places for a left and a centred price; the contact at the right and a little smaller, with a 29-character limit; a circle-covers-circle guard; "not found" unticks the logo and says so; ticking again returns the seal to its disc; the cover point moves to the final screen with a size warning; two paid scenes proposed. The keyed-colour disc is not adopted: the white disc worked twice on real scenes and the alternative is untested; it stays the fallback idea if a white look fails.
