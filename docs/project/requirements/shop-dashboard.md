# REQUIREMENTS — The shop's dashboard

**Status:** Draft v1, 2026-11-15 (Claude), with working defaults marked **Default**. Part of Release 1 « Invitation » ([roadmap](../ROADMAP.md), ADR-105; the user asked for it as a condition of the next deploy). Depends on [multi-shop](multi-shop.md) and [prepaid-balance](prepaid-balance.md). No design yet.

**What exists:** a choice screen (« Par message » / « Pas à pas »), « Mes affiches », the shop's profile inside the editor. No home, no balance, no account screen.

## Index

| ID | Title | Priority | Status |
|---|---|---|---|
| R-SHOP-DASH-001 | Home | P0 | Draft |
| R-SHOP-DASH-002 | Credits | P0 | Draft |
| R-SHOP-DASH-003 | Account | P1 | Draft |
| R-SHOP-DASH-004 | True and usable on a phone | P0 | Draft |

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
