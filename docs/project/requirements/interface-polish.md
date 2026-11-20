# Interface polish — requirements

**Status:** Approved v2, 2026-11-20, by the lead under the autonomy grant (the owner: "start, you can go to the end
without stopping"; ADR-122). v2 narrows v1 after the design's two reviews
([Codex r1](../reviews/interface-polish-design-r1.md), [devil's advocate](../reviews/interface-polish-devils-advocate.md)):
no yellow main button, the dark theme keeps its greys, no centred empty conversation, the operator's page gets its
numbers only. Evidence: [reviews/design-baseline-2026-11-20.md](../reviews/design-baseline-2026-11-20.md).

**Goal.** The shop's interface and the operator's page read as one product, Doka Studio, in the Signal identity
(`brand/doka-studio-signal/USAGE.md`), with the same frame on every screen and no text that is cut, faint or
misleading. Presentation only.

**Out of scope.** Posters and poster fonts (the identity dresses the service, never a shop's poster). Any route,
table, job, money rule or migration. New screens or features. New visible French sentences, except where a criterion
names one. The interface typeface: Figtree stays (ADR-077, ADR-122).

## R-POLISH-001 — The name and the mark everywhere

- [ ] The browser tab of the shop's interface says « Doka Studio ». No file shipped to a browser says « Affiche Gen ».
- [ ] The web manifest names the app « Doka Studio » (short name « Doka »), in French, and its icons, the favicon and
  the Apple touch icon are the Signal kit's files, unmodified.
- [ ] The operator's page shows the Signal mark beside its name, in both themes, with the kit's clear space, and
  keeps one accessible name.
- [ ] « Vos données » (`donnees.html`) carries the same name and icon.

## R-POLISH-002 — The Signal colours on the shop's interface

- [ ] In the light theme the ground and the main text of the shop's interface are the kit's Warm Paper `#F5F1E8` and
  Charcoal `#20201D`; in the dark theme the main text is Warm Paper. The dark theme keeps its present greys (ADR-091):
  the kit sets no ground for a dark interface.
- [ ] The accent is Signal Yellow `#F2C744`, replacing the amber of before the identity. It is used as a fill under
  charcoal (the send button, the mark), and as the tint of the phone navigation's active item (the desktop one keeps its neutral glass). Yellow is never a text
  colour on a light ground, and never carries white text.
- [ ] Every ring, border and progress mark that used the amber keeps at least 3:1 against what is behind it in both
  themes: a paid generation in progress stays as visible as today.
- [ ] The main button does not change its role or its look: charcoal on paper, paper on charcoal (its exact fill
  follows `--invert`, which takes the kit's values). A yellow main button waits for the owner's look at a phone in
  daylight.
- [ ] Every text is at least 4.5:1 against what is behind it in both themes, or 3:1 when it is large as WCAG AA
  defines it (from 24 px, or from 18.66 px in bold), the rule the interface was built on; every placeholder is at
  least 4.5:1 whatever its size. Measured on the rendered screens, over the darkest and the lightest point of the
  backdrop, and in every state, a pressed control and reduced motion included. (Amended after the code review of
  T-POLISH-002: v2 said 4.5:1 for every text.)
- [ ] States keep their own colours and meanings (success, warning, failure).
- [ ] A poster is unchanged: the bytes of a confirmed file, and the pixels of the poster in the editor.

## R-POLISH-003 — One frame for every screen of the shop

- [ ] Each signed-in screen has exactly one first-level title that a screen reader finds. Accueil, Mes affiches, Mes
  crédits, Mon compte and Styles show it at one size and weight; the chat carries one in every state.
- [ ] A page title that receives the focus for a screen reader shows no box around it; a focus the owner moved with
  the keyboard is still shown.
- [ ] Those five screens share one content width, the same left and right edges, and a side gutter of 16 px on a
  phone. The editor and the chat keep their present gutters.
- [ ] At 360 px no label of the bottom bar is cut or wraps, with four or five items, for the balances −2, 0, 117 and
  12 345 and an unread balance, and for 0, 3 and 120 posters. Each item keeps a 44 × 44 px target; its accessible
  name contains what is shown and keeps its full meaning.
- [ ] Nothing changes in what each screen offers, in its order, or in its French sentences.

## R-POLISH-004 — The operator's page

- [ ] Numbers in the Shops table, cells and headers, are right-aligned with tabular figures; under 600 px the
  labelled cards are unchanged.
- [ ] Nothing else changes on the operator's page here: the two-column shop page goes with T-ADMIN-008, and the
  session list is short on the live service.

## R-POLISH-005 — The record and the proof

- [ ] `DESIGN.md` at the repository root records the system as built: colour tokens of both themes, the type scale,
  spacing, the frame, the components, and what the Signal guide fixes.
- [ ] The capture script is kept in the repository, so the proof can be taken again.
- [ ] The baseline's captures are taken again on the final code; both checkers run again; the report says, finding by
  finding, what is closed, what is left and why.

## Constraints

- Verified on the local stub build only; a real phone and a screen reader remain owner checks.
- French sentences stay drafts until the owner reads them; a criterion that adds one names it.
- Every existing test and browser smoke passes, changed only where it names a colour, a title size or a layout that
  a criterion changes.
