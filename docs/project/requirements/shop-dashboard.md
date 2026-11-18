# REQUIREMENTS — The shop's dashboard

**Status:** Approved for design by the owner, 2026-11-18 (ADR-113). Part of Release 1 « Invitation » ([roadmap](../ROADMAP.md), ADR-105; the user asked for it as a condition of the next deploy). Depends on [multi-shop](multi-shop.md) and [prepaid-balance](prepaid-balance.md). See the [approved design](../designs/shop-dashboard.md).

**Mobile amendment:** R-SHOP-DASH-005 through 009 were approved for design by the owner on 2026-11-18. The original approval covers 001 through 004.

**At requirements approval:** a choice screen (« Par message » / « Pas à pas »), « Mes affiches », the shop's profile inside the editor. The prepaid balance API and generation checks already existed. Home and Account were new screens.

## Index

| ID | Title | Priority | Status |
|---|---|---|---|
| R-SHOP-DASH-001 | Home | P0 | Approved |
| R-SHOP-DASH-002 | Credits | P0 | Approved |
| R-SHOP-DASH-003 | Account | P1 | Approved |
| R-SHOP-DASH-004 | True and usable on a phone | P0 | Approved |
| R-SHOP-DASH-005 | Keep or discard shop profile edits | P1 | Approved |
| R-SHOP-DASH-006 | Explain spendable credits | P1 | Approved |
| R-SHOP-DASH-007 | Identify the poster needing attention | P2 | Approved |
| R-SHOP-DASH-008 | Identify Doka Studio in the dashboard header | P2 | Approved |
| R-SHOP-DASH-009 | Explain who sees the shop contact | P2 | Approved |

## R-SHOP-DASH-001 — Home
- **Story:** As a shop owner, I open the application and see what I have and what to do next.
- [ ] After sign-in: credits available and waiting, one button to make a poster (the chat, or the steps if that is the saved choice), the last posters with their state.
- [ ] What needs me is said first: a version to check, a generation that failed, no credit left.
- [ ] The balance is visible from the chat and from the editor without going home.
- **Out of scope:** publications, a calendar, reach or sales figures.

## R-SHOP-DASH-002 — Credits
- **Story:** As a shop owner, I see where my credits went and how to get more.
- [ ] The history, newest first: credits received (offered or bought, with the date), each credit spent with its poster, each credit given back.
- [ ] The last thirty days in one line: posters made, generations, credits spent.
- [ ] How to buy: the operator's text.
- **Out of scope:** paying in the application; receipts.

## R-SHOP-DASH-003 — Account
- **Story:** As a shop owner, I manage my shop's details and my access myself.
- [ ] The shop's name, logo and contact (the existing profile) in one place.
- [ ] Change the password; « Se déconnecter »; the date the conditions of use were accepted, with a link to them, and a link to « Vos données » (`/donnees.html`, R-TERMS-003; verified from a signed-in shop that has accepted).
- [ ] How to reach the operator.
- **Out of scope:** several users; deleting the account from the application (asked of the operator).

## R-SHOP-DASH-004 — True and usable on a phone
- **Story:** As a shop owner on a small phone, I can use all of it with one hand and trust what it shows.
- [ ] Usable at 360 px wide with the keyboard open, by keyboard and screen reader, in both themes.
- [ ] A new shop sees honest empty states. No invented number, no sample chart.
- [ ] A figure that could not be loaded says so; it is never shown as zero.

## R-SHOP-DASH-005 — Keep or discard shop profile edits

- [ ] Changing the shop name, contact or logo, then leaving Mon compte via an app link, tab or browser Back, offers « Continuer la modification » and « Abandonner » before the draft is lost.
- [ ] Continuing keeps all edits and returns focus to the profile. Discarding opens the requested destination once. Reopening Account shows the saved values.
- [ ] A successful save or restoring the original values allows ordinary navigation. A failed save keeps the edits protected. Ending the session clears shop details and password fields.

## R-SHOP-DASH-006 — Explain spendable credits

- [ ] With a pending reservation, Mes crédits explains that the available figure already excludes it. For example, with 2 available and 1 pending, the shop has 2 spendable credits.
- [ ] At zero or below, show the actual signed balance, explain that new image generation requires credit and existing posters remain accessible, and show the operator’s purchase instructions. Other service or terms restrictions retain their existing precedence.
- [ ] An unavailable balance has its own state. A previous balance, if displayed, is identified as the last known value.

## R-SHOP-DASH-007 — Identify the poster needing attention

- [ ] For review and failure groups, identify the linked poster by its shop-visible title when available, including posters outside the five most recent. A missing title has a plain French fallback. Retain the remaining count and open the identified poster.
- [ ] A successful check with neither group populated shows « Aucune affiche à vérifier » or equivalent. Loading and failed checks cannot announce that all is clear. Balance and service alerts remain visible when applicable.
- [ ] The outcome precedes its timestamp. On a 360 px phone, creation remains a single action from Home.

## R-SHOP-DASH-008 — Identify Doka Studio in the dashboard header

- [ ] Accueil, Mes crédits and Mon compte identify the service as Doka Studio using the [approved Signal artwork](../brand/doka-studio-signal/USAGE.md). At 360 px the header remains legible in both themes and its controls remain usable.
- [ ] Assistive technology reads the product name once in the header. The shop’s own logo remains independently identifiable in its profile.

## R-SHOP-DASH-009 — Explain who sees the shop contact

- [ ] Before saving a contact, staff can read that customers may see it on posters when the shop chooses to include it. The explanation is associated with the field for screen-reader users.
- [ ] The operator’s support details have a distinct label. Saving a shop contact alone does not imply that existing posters have been updated.
