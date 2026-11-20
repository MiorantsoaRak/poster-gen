# Doka Studio — mockup of both entries (2026-11-20)

A clickable mockup of the shops' app and of the operator's console on **one design system**. Static files, sample
data, nothing sent anywhere. Not the application: no route, no state, no French text here is approved copy.

## Open it

```
python3 -m http.server 8777 --bind 127.0.0.1 --directory docs/project/mockups/doka-console
```

then `http://127.0.0.1:8777/` (the index links every state). A state is an address:
`client.html?view=chat|talk|home`, `admin.html?view=overview|shops`, plus `&theme=light|dark`, `&rail=1` (sidebar
collapsed), `&primary=ink` (the main action in charcoal instead of yellow). Under 900 px wide the phone layout shows.

Also published as a private artifact: https://claude.ai/artifact/TLAJXwcJihPh6Tp8R2pa5F (states by hash there:
`client.html#chat|talk|home`, `admin.html#overview|shops`).

## Round 2 (same day, on the owner's review)

- Layout after the Dribbble shot « Zyricon — AI Chatbot Web App »: the whole app in one framed window over the field,
  the sidebar a darker column inside it with labelled sections, suggestions above the composer, quiet tools at the
  bottom left of the composer and the send button at the bottom right. Structure only; nothing copied.
- Softer edges in the light theme: a button's edge is a 20% charcoal line, the yellow button's edge a darker yellow,
  no black outline. Fields keep a 3:1 line.
- Tables and cards after design-taste's app-screen rules and a web search on table design: one key-figures card
  split by hairlines (label over value, no icon), small grey sentence-case headers with no band, rows of one height
  on a faint rule, the identity column widest, figures on one right edge, pale status pills, « View all » with the
  total; cards are a surface and a hairline, a shadow only on what floats (the composer, the sheet).
- The conversation says less: one recap line, « Créer l’affiche · 1 crédit », « Votre affiche est prête. », three
  suggestions. The progress line, the remaining-credit sentence and the repeated cost are gone.
- No « Service running » badge; the active navigation item is a neutral fill, not a yellow bar.
- Kept against design-taste's own rule: the glass and the soft field, which the owner asked for.

## Files

| File | What |
| --- | --- |
| `doka.css` | The system both pages share: tokens of both themes, glass, buttons, fields, badges, the sidebar and its rail, the top bar, the phone drawer and bottom bar |
| `doka.js` | The icon set (one outline family) and the shared behaviours: theme, sidebar, drawer, views |
| `client.html` | The shops' app: the empty chat, a conversation with a poster, Accueil |
| `admin.html` | The operator's console: Overview, Shops, one shop's sheet |
| `assets/` | The Signal kit's logo files (unmodified), Figtree, three sample poster images from the app |

## What it answers

| Asked | In the mockup |
| --- | --- |
| Correct use of the logo | The kit's **horizontal logo** at its minimum width (220 px) in the sidebar; the **D alone** where space is short (collapsed sidebar, phone top bar, the assistant's mark). The name is never typed beside the symbol. Charcoal file on light, paper file on dark |
| Better navigation | One sidebar for both entries: the logo, one main action, the sections, recent posters (app), the account at the bottom. It collapses to an icon rail. On a phone it is a drawer; the app also has a bottom bar with « create » in the centre. The credits are always at the top right, on every screen |
| Correct theme | The kit's three colours as given: Warm Paper `#F5F1E8`, Charcoal `#20201D`, Signal Yellow `#F2C744`. The dark theme is on the kit's charcoal. Yellow marks the main action, with charcoal on it and a charcoal edge (yellow alone is 1.4:1 on paper). `&primary=ink` shows the other reading |
| Consistent styling across both | Both pages load the same `doka.css`: same sidebar, glass, buttons, badges, fields, radii, type |
| Admin console with a collapsible sidebar | `admin.html`: four figures, the shops table, « Needs you », recent payments, the service; a shop opens as a sheet over the list with the grant form |
| A chat that regular AI-chat users know | A greeting question, **one composer** with its tools inside (photo, style, format) and the send button at the bottom right, suggestions, the owner's message in a bubble, the answer without one, the poster in a side panel on a wide screen, a recap with the credit cost before anything is spent |

## Where the structure comes from

The Dribbble search « AI chat » (read 2026-11-20) for the common model only: sidebar with the brand, a new-chat
action and recents; a centred greeting over one composer card; tools inside the composer and a round accent send
button; suggestion chips; frosted panels over a soft field. No shot was copied. ui-ux-pro-max gave the rules checked
below (glass with 4.5:1 text, a bottom bar of five items at most, 44 px targets, one icon family, tokens per theme).

## Checked

- Rendered contrast with the app's own checker (`browser_smoke.check_contrast`), every state, 390 and 1440 px, both
  themes: no text under 4.5:1 (3:1 when large). It found the account initials at 2.38:1; fixed.
- No control under 44 × 44 px at 390 px. No sideways scroll and no console error in any state.
- Impeccable's detector: what is left is the paper ground (the brand) and sizes and radii that the current
  `DESIGN.md` does not list, which is expected of a proposal.

## Not checked, and open

- A real phone, a screen reader, forced colours. Keyboard order was not walked.
- The French sentences are drafts. Sample prices and figures are examples.
- Only three app screens and two console screens exist; « Mes affiches », « Styles », « Compte », Payments and
  Service are links that go nowhere.
- This reopens three decisions of ADR-122, on purpose, so that the owner can see them: a yellow main action, the
  dark theme on the kit's charcoal, and a bottom bar with four sections and a centre action in place of today's.
