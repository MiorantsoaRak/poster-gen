# App redesign — requirements

**Status:** Approved v2, 2026-11-20, by the lead under the autonomy grant (ADR-123). The owner approved the mockup
[mockups/doka-console/](../mockups/doka-console/README.md) after two rounds ("we can proceed now") and asked for
parallel work ("tasks can be done in parallel"). v2 follows the design's first review and its devil's advocate
([reviews/app-redesign-design-r1.md](../reviews/app-redesign-design-r1.md),
[reviews/app-redesign-devils-advocate.md](../reviews/app-redesign-devils-advocate.md)): the sidebar starts at
1181 px, the phone's top bar is spelled out, the operator's console changes no server answer. The design's second
review approved it with fixes ([reviews/app-redesign-design-r2.md](../reviews/app-redesign-design-r2.md)).

**Goal.** The shops' app and the operator's console are rebuilt to follow that mockup: one visual system in the
Signal identity, a sidebar shell, a chat that reads like the AI chats people know, an operator console with an
overview. The mockup is the target for the look and the layout; this file says what must hold in the real
application, where the mockup's sample content is not the product.

**Out of scope.** Posters, poster fonts, the renderer and the editor's canvas. Any money rule, job, migration,
route or server answer: this is a change of the two interfaces only. The French sentences already approved, which
stay word for word unless a criterion below names a change. Suggestion chips in the chat (see « Not built »).
Merge into `main`, push and deploy: the owner's word (the work lives on the branch `redesign`).

## R-REDESIGN-001 — One system, in the kit's colours

- [ ] Light theme: ground Warm Paper `#F5F1E8`, text Charcoal `#20201D`. Dark theme: ground Charcoal `#20201D`, text
  Warm Paper. Both interfaces use the same values for the same roles; tests pin the same table of values in each
  stylesheet, and the two still share no file.
- [ ] The main action of a screen is charcoal text on Signal Yellow `#F2C744`, with no black outline. Yellow is never
  a text colour on a light ground and never carries white text. Where an approved design ranks two actions (the
  final panel: share first, the file second), the ranking is unchanged.
- [ ] A card, a list, a field or a chip at rest is an opaque surface with a hairline: no blur, no shadow. Blur and
  shadow are for what floats over content: the top bar, the phone's bottom bar, the drawer, a dialog, a toast, the
  bars that stick or are fixed today. The chat's composer keeps a soft shadow and no blur.
- [ ] Every text is at least 4.5:1 against what is behind it (3:1 when large, as WCAG AA defines it), every
  placeholder 4.5:1, every field boundary (the composer's included) and every ring or progress mark 3:1, in both
  themes, measured on the rendered screens. A button's own edge may be softer: its label names it.
- [ ] The interface typeface is Figtree in both interfaces; the type sizes of the shops' app do not change.
- [ ] A poster is unchanged: the bytes of a confirmed file, and the pixels of the poster in the editor.

## R-REDESIGN-002 — The shell of the shops' app on a wide screen (over 1180 px)

- [ ] The app sits in one framed window over the page's ground: a sidebar on the left, the screen on the right.
- [ ] The sidebar holds, top to bottom: the kit's horizontal logo (never under 220 px wide, never with the name typed
  beside it), which goes to Accueil; the main action « Nouvelle affiche »; the sections Accueil, Mes affiches and
  Styles, each with its count once the app knows it; « Affiches récentes », the same five posters as Accueil shows,
  each opening its poster; the credits (« N crédits », to Mes crédits); the shop's name (to Mon compte, « Votre
  boutique » until it is known) with « Se déconnecter ».
- [ ] The sidebar reduces to a rail of icons and comes back, by one button; each icon keeps its full accessible name;
  the D alone replaces the logo. The choice is kept on the device and applied before the first paint. In the step
  editor the sidebar is the rail.
- [ ] A top bar holds that button, the poster's name in the creator, the « Message / Pas à pas » switch where it
  exists today, the credits, and the theme switch.
- [ ] The window stays the page's scroller, and the editor never has less width than its present minimum for two
  columns: nothing of the editor's or the chat's positioning changes behaviour.
- [ ] While the identity gate is closed the shell holds nothing of a shop (its name, its posters, its credits):
  the sidebar is not in the page. The rest of the page keeps the gate's present rules (hidden during a
  verification, erased after a sign-out). The signed-out screens show the horizontal logo and no sidebar.

## R-REDESIGN-003 — The shell of the shops' app on a tablet and a phone

- [ ] At 1180 px and under, the sidebar is a drawer opened from the top bar: the same content, the page behind it
  inert. Escape, a tap outside or its close button closes it and returns the focus to the menu button; choosing a
  destination closes it and the destination takes the focus as it does today (its title, or the question a
  departure raises). The browser's Back acts on the page, not on the drawer.
- [ ] At 720 px and under, a bottom bar holds Accueil, Affiches, a centre « Nouvelle affiche », Styles and Compte.
  No label is cut or wraps at 360 px; each target is at least 44 × 44 px; each accessible name is the full French
  name. The bar is not shown in the chat or the editor, where the composer or the tools take its place.
- [ ] The top bar is one row at 360 px, with a balance of five digits. From 721 px to 1180 px: the menu button, the
  D, the poster's name in the creator, the switch, the credits, the theme switch. At 720 px and under: the menu
  button, the D and the credits; in the chat, the menu button, the switch, « Nouvelle affiche » and the credits.
  The theme switch is then in the drawer. The phone's step editor keeps its own bar, as today.
- [ ] The credits are reachable from every signed-in screen; in the creator every way to them opens the panel over
  the work, and closing it returns the focus to where it was opened from (D-SHOP-DASH-001). The balance is seen
  from the chat and from the editor without going home (R-SHOP-DASH-002).

## R-REDESIGN-004 — The chat

- [ ] An empty conversation shows the D, the question « Quelle affiche créons-nous ? » and the present greeting
  sentence under it; on a wide screen the question and the composer form one group in the middle of the screen, on
  a phone the composer stays at the bottom.
- [ ] The composer is one box: the photos chosen, the words, and inside it, at the bottom, « Ajouter des images »,
  the three styles (while no poster exists) and « Envoyer » at the right. « Envoyer » is charcoal on yellow.
- [ ] The owner's messages are bubbles on the right; the assistant's are plain text on the left under the D.
- [ ] The recap before an image keeps every approved sentence and every rule that shows or hides one, in this order
  of weight: the facts (product, price, style, identity) as cells, one main button, then the cost sentence
  (« 1 crédit · il vous en reste N » and its variants, R-BALANCE-001) and the correction hint as small text. The
  cost is readable beside its button, before the tap, at 360 px.
- [ ] On a wide screen the poster stays in its side panel, a surface with a hairline; the thread is plain on the
  window's ground.
- [ ] No sentence, button name, route or state of the chat changes, except the new question above.

## R-REDESIGN-005 — The other screens of the shops' app

- [ ] Accueil, Mes affiches, Styles, Mes crédits, Mon compte, the signed-out screens, the step editor's panels, the
  review and final panels, the conditions dialog and « Vos données » use the system of R-REDESIGN-001: the same
  buttons, fields, cards, rows and badges as the chat and the shell.
- [ ] Each keeps its content, its order, its sentences, its one first-level title and its focus on arrival
  (R-POLISH-003), and its 860 px frame.
- [ ] A poster's state in a list (Brouillon, À vérifier, Approuvée, Confirmée) is a pale pill with dark text of the
  same hue, one per row. « Retirée » and Accueil's « needs attention » group keep their present form.

## R-REDESIGN-006 — The operator's console

- [ ] The same shell as the shops' app, in English: a sidebar with the logo, « New shop », Overview, Shops, Payments
  and Service, the theme switch and « Sign out »; it reduces to a rail; at 1180 px and under it is a drawer.
- [ ] **Overview** is the home: four figures in one card (active shops; credits outstanding with their estimated
  cost; ariary received this UTC month; provider spend against the cap, with since when), the shops, « Needs you »,
  this month's payments, and the service's state. Every figure comes from the server's answers; none is typed.
- [ ] « Needs you » lists only what the operator can act on: a request with no definite answer, a shop with no
  password, no purchase text, a late or unknown backup, failed jobs, the cap warning. It says it is empty only when
  everything it reads was read; otherwise it says what could not be checked.
- [ ] The shops table has small plain headers, rows of one height, the identifier and name first and widest, figures
  right-aligned, one state per row (suspended, else no password, else active) beside today's mark of an unanswered
  request. A field filters it by identifier or name. Under 600 px each shop is a card.
- [ ] One shop keeps its page, its one column, its sections and their order (the unanswered request first, then the
  grant), its confirmations and its kept requests exactly.
- [ ] The page still takes and asks nothing of the shops' app (D-ADMIN-005): its own stylesheet, its own copies of
  the font and the logo, no request outside `/admin/` and `/api/admin/`.
- [ ] Every target is at least 44 px at every width; nothing is fixed to the bottom of the screen; at 360 × 640
  nothing scrolls sideways, everything is one column and a confirmation's two buttons are in view.
- [ ] The theme follows the device until the operator switches it; the switch is kept on the device; a refused
  storage changes nothing else.

## R-REDESIGN-007 — The record and the proof

- [ ] `DESIGN.md` describes the system as rebuilt. The decisions this reverses are recorded (ADR-123).
- [ ] The 17 screens are captured again, with the console's new screens; both checkers run; a report compares with
  the mockup, screen by screen, and lists what differs and why.

## Not built, on purpose

| In the mockup | In the application | Why |
| --- | --- | --- |
| Suggestion chips above the composer | Not built | New French text that promises a result: « Une promotion » invites a discount the app must never invent, « Prix plus grand » needs a new paid image when the price is drawn (ADR-044). Proposed as its own task |
| « Créer l’affiche · 1 crédit », no balance sentence | The approved cost sentence stays, small | R-BALANCE-001; its variants (unknown balance, credits waiting, three or fewer left, none) say more than the top bar's number. The shorter form is an owner decision |
| A format choice in the composer | Not built | The chat has no format choice today |
| « Obtenir des crédits » under the balance | « Mes crédits » | Credits are not bought in the app |
| One shop as a side sheet | One shop stays a page | Seven sections and their confirmations; a dialog over a sheet |
| « Conditions pending » on a shop | Not built | No server answer gives it to the operator, and the operator cannot act on it. Proposed as its own task |
| « Spend today » per shop; search by payment reference | Not built | No server answer gives them without a call per shop or a new route |
| The poster's name in the phone's top bar | Not shown at 720 px and under | The real bar also holds the « Message / Pas à pas » switch |
| A soft edge on the composer | A 3:1 edge | A field's boundary must be seen in daylight on a cheap screen |

## Constraints

- Verified on the local stub build only; a real phone and a screen reader remain owner checks. Before any release:
  the yellow main button in daylight, the dark theme's cards on a cheap screen, the drawer and the phone's top bar
  on an Android phone with a larger text size.
- New French, drafts until the owner reads them: « Quelle affiche créons-nous ? », « Affiches récentes »,
  « Photo », and the names of new controls: « Ouvrir le menu », « Fermer le menu », « Réduire le
  menu », « Agrandir le menu ». « Nouvelle affiche » replaces « Créer » in the navigation (it is the app's word
  already).
- Every existing test and smoke passes, changed only where it names a colour, a layout, a navigation item or a
  heading that a criterion changes; what each asserted about behaviour is asserted again through the new control.
