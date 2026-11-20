# Design baseline — client and operator interfaces (2026-11-20)

Step 1 of the polish work (T-DESIGN-BASELINE). No application code changed. Local build of `main`, stub providers,
temporary data seeded through the real screens (three posters, two shops, one bought and one offered grant), zero
spend. Not the live site, not a real phone.

## What was done

| Evidence | How | Where (git-ignored) |
| --- | --- | --- |
| 102 screenshots: 17 screens × 360, 768, 1440 px × light, dark | Playwright, full page | `outputs/design-baseline/*.png`, contact sheets in `sheets/` |
| 51 static snapshots of the signed-in screens | `page.content()` without scripts, CSS from `frontend/dist` | `outputs/design-baseline/html/` |
| Impeccable detector, element rules included | `impeccable detect --json` on the snapshots | `outputs/design-baseline/detect.json` (167 findings, 6 distinct kinds) |
| design-taste app inspector | `inspect.mjs --app --widths 1440,390` on 13 screens | `outputs/design-baseline/taste/*.json` |
| Read of every contact sheet | by the lead | this file |

Screens: sign-in, Accueil, Mes affiches, Mes crédits, Mon compte, Styles, chat (new, with a poster, unconfirmed),
Pas à pas, the final panel, the conditions dialog; operator sign-in, Shops, one shop, Money, Service.

Not done: Impeccable's scored critique (40 points, with its assessment subagents) and `DESIGN.md`. The earlier score
is the Codex session's 26/40 for the shop home (`.impeccable/critique/`), before T-SHOP-DASH-006 to 011.

## The first finding changes the plan

**The Doka Studio identity is already on the client**: the Signal logo, the name, the warm paper ground, charcoal
controls, both themes (T-SHOP-DASH-010 and the shop dashboard work). The plan called this a rebrand; it is a
consistency and finish pass. The open `T-BRAND-DOKA` is smaller than its TODO text says.

## Findings, by what they cost the user

### A. Brand left unfinished (small, certain)
1. The browser tab says « Affiche Gen » (`frontend/index.html`), and the installed app would be named « Affiche Gen » /
   « Affiches » with a dark theme colour (`frontend/public/manifest.webmanifest`). The operator page already says
   « Doka Studio · Operator ».
2. The operator interface has no mark: the name is plain text.
3. The app icon is not the Signal one: `frontend/public/icons/icon-192.png` differs from the kit's
   `brand/doka-studio-signal/web/icon-192.png` (the kit also has the favicon, the maskable icon and a manifest).

### B. Two interfaces, several habits (the main theme)
4. **Type.** The client uses Figtree (the owner's choice, ADR-077, 2026-11-14); the operator page uses the system's
   font (`admin.css`, on purpose: nothing to download); the Signal kit (2026-11-15) names Space Grotesk for titles and Noto Sans for text. Space Grotesk appears
   nowhere in the application. **An owner decision.**
5. **Page titles.** Accueil, Mes crédits and Mon compte have a 42 px title; Mes affiches and Styles a small one; the
   chat screens have no `h1` at all (inspector: `no-title`, `app-title-size`).
6. **Navigation changes between screen families.** Phone: four items on the dashboard screens, five on the creator
   screens, where « 117 crédits » is cut to « 117 cré… » and « Mes affiches » wraps to two lines at 360 px. Desktop:
   the credits link is present on creator screens and absent on dashboard screens.
7. **The main button** is charcoal on the client and Signal yellow on the operator page. The client uses the yellow
   only in the mark and the active navigation item.
8. **Two header rows on a phone in the creator**: the name wraps (« Doka / Studio ») beside the sign-out icon, the
   Message / Pas à pas switch and the theme button.

### C. Accessibility and mechanical checks
9. **Placeholders under 4.5:1 in the light theme** (detector, measured): 3.6:1 for « Ex. Soundcore R50i… », « 90 000… »,
   « Téléphone, adresse ou WhatsApp… » (`#837d77` on `#f4f1ec`); 3.9:1 for « Produit et prix… » and « Votre message… »
   (`#85807b` on white). The price placeholder « 90 000… » also looks like a filled value.
10. **A focus box around the page title** on Accueil, Mes crédits and Mon compte when the page is opened directly
    (the title receives focus for screen readers). To check on a phone: it should not show after a tap.
11. Text 12 px from the phone's edge on the dashboard screens, where the design's gutter is 16 px (inspector).
12. Line height 1.2 on the poster rows' second line (detector: 1.3 at least); three blocks with children flush against
    their border (`home-bal`, the poster `rows`, the steps' `details`).
13. Two endless animations are declared (`.load-line`, `.gen-pill`): correct for a wait, to check under
    `prefers-reduced-motion`.

### D. Layout
14. **Desktop leaves most of the first screen empty**: 53% on the new chat and on Mes affiches, 38% on a poster's
    chat; the dashboard column is about 510 px wide at 1440 px (inspector: `hero-void`).
15. **Operator tables**: all eight numeric cells of Shops are left-aligned; one shop's page leaves 390 px unused on
    the right while its form is narrow; the phone layout of the grant form is one long column.
16. The operator's Service screen lists every live session at full length (24 here, made by this run; one to four on
    the live site): no limit and no fold.

### Discarded, with the reason
- `cream-palette` / `palette-cream` (both tools): the warm paper is the Signal palette. The brief wins.
- `font-fallback: Figtree` (inspector): an artefact of the snapshots. The stylesheet loads `/fonts/…` by an absolute
  path, which a file snapshot cannot resolve; the application ships and loads the font.
- `broken-image`: the snapshots have no API behind them.
- `hero-void` on the operator screens: the seeded data is small.
- The flat colour posters: the stub provider's images.

## What the tools could not see
A real phone, a screen reader, the editor canvas, error states, long shop names, a shop with 50 posters, the live
site. The inspector judged snapshots, not the running app: motion and interaction counts are zero by construction.

## Proposed order (each its own task, each ending with the existing smokes)
1. **Finish the name** (A1–A3): title, manifest, icons, the operator's mark. Small.
2. **One frame for every screen** (B5, B6, B8, C10, C11): one title scale, one navigation with the same items
   everywhere, one header row on a phone.
3. **Contrast and text finish** (C9, C12, C13).
4. **Desktop use of space** (D14) for the chat and Mes affiches.
5. **The operator page** (B7, D15, D16, A2): numbers aligned, the form's width, the session list, the button rule.

Decision needed before 2: the interface typeface (B4).
