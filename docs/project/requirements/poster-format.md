# REQUIREMENTS — poster-format

**Status:** Approved 2026-11-14 under the autonomy grant (ADR-080). User, 2026-11-14: "when generating from a model, can we also use the same aspect ratio as the reference in the result? Ask the user first if want that. (Make the user choose aspect ratio)?"

| ID | Title | Priority | Status |
| --- | --- | --- | --- |
| R-POSTER-FORMAT-001 | The owner chooses the poster's format | P1 | Approved |
| R-POSTER-FORMAT-002 | A model in another shape asks before changing the format | P1 | Approved |

## R-POSTER-FORMAT-001 — The owner chooses the poster's format

- [ ] The owner chooses the poster's format among Publication 4:5 (1080 × 1350), Carré 1:1 (1080 × 1080) and Story 9:16 (1080 × 1920), in the Style step. A new poster starts in Publication.
- [ ] The format can still be changed in the editor until the poster's first version exists. After that it is fixed, and the editor says why (the title, price and contact are drawn in an image of one size).
- [ ] A poster in any of the three formats goes through the whole path: plan, scene, fidelity check, final preview, confirmation, download; the downloaded PNG has exactly the format's size.
- [ ] The library, the versions strip, the sticky poster, the large view and the final preview show each poster in its own shape, on a phone (360 px) and on a wide screen, in both themes.
- [ ] Three formats in the pilot, no other ratio: each format's layout is tuned by hand (the image model itself accepts more sizes).
- [ ] On a poster whose format is fixed, one button makes a new poster of the same product in another format.
- [ ] Carré and Story are shown to the owner only once enabled on the server, after real scenes in those formats were judged.

## R-POSTER-FORMAT-002 — A model in another shape asks before changing the format

- [ ] When the owner picks a model image (« Affiche modèle ») or a saved style made from one, and its shape is nearer another format than the poster's, the editor asks whether to use that format. It never changes the format without a yes.
- [ ] The question is asked only when the model's shape is close to one of the three formats (3:4 counts as Publication); a landscape or odd model asks nothing.
- [ ] A refusal is remembered for that model on that poster: the question does not come back at every step.
- [ ] If the poster already has a version, the editor only says that the model has another format and that this poster keeps its own.
- [ ] Built-in styles have no model and ask nothing.

## Exclusions and open points

Several formats of one poster, a copy of a poster in another format, a landscape format and arbitrary ratios are out. Square and Story have never been generated live in this project: how the image model composes them, whether it accepts the Story size, and the real cost of a Story scene are unknown until paid scenes are made on the user's word.
