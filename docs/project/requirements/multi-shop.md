# REQUIREMENTS — Several shops, each with its own sign-in

**Status:** Approved 2026-11-15 under the user's autonomy grant (ADR-106), with its working defaults marked **Default**. Draft v1 by Claude. Part of Release 1 « Invitation » ([roadmap](../ROADMAP.md), ADR-105). Source: the two-shop audit in the [review](../reviews/saas-review-claude-2026-11-15.md). Design: [multi-shop](../designs/multi-shop.md) v4, approved (ADR-107). Wording amended from the design reviews the same day.

**What exists:** every data query is already limited to the signed-in shop (67 cross-shop attempts refused in the audit's test). The schema allows one shop; there is one password for everyone; sign-in always opens shop 1; the spend cap and the job queue are one for the whole service.

## Index

| ID | Title | Priority | Status |
|---|---|---|---|
| R-MULTI-SHOP-001 | A shop signs in as itself | P0 | Approved |
| R-MULTI-SHOP-002 | No shop sees or changes another's | P0 | Approved |
| R-MULTI-SHOP-003 | One shop cannot use up what all share | P0 | Approved |
| R-MULTI-SHOP-004 | Two shops on one phone | P1 | Approved |
| R-MULTI-SHOP-005 | The pilot shop keeps everything | P0 | Approved |
| R-MULTI-SHOP-006 | A shop can be suspended | P1 | Approved |

## R-MULTI-SHOP-001 — A shop signs in as itself
- **Story:** As a shop owner, I sign in with my shop's identifier and my own password, and nobody else's password opens my shop.
- [ ] The sign-in form asks for an identifier and a password, and says whom to contact when the password is forgotten. The identifier is one the operator chooses when he creates the shop, which may be a phone number in one written form; case, accents, spaces and punctuation are ignored.
- [ ] A wrong identifier and a wrong password give the same sentence. Nothing says whether a shop exists.
- [ ] Wrong attempts are limited for that identifier from that address, with a looser limit for the address alone, so shops behind one mobile address do not lock each other out.
- [ ] The owner can change his password while signed in, giving the current one (the screen for it is the shop's dashboard, R-SHOP-DASH-003). The operator can set a new one. Either ends that shop's other sessions and no other shop's.
- [ ] « Se déconnecter » is on every screen's menu and ends the session on the server.
- **Out of scope:** public sign-up; signing in with Google, Facebook or email; password recovery by message (the operator resets it); several people per shop.

## R-MULTI-SHOP-002 — No shop sees or changes another's
- **Story:** As a shop owner, I am certain my photos, posters and spending are mine alone.
- [ ] Every route that reads or changes data refuses another shop's poster, version, image, thumbnail, plan, job, style, export, product input and chat read, with the same answer as for something that does not exist.
- [ ] A shop sees only its own usage and spending. The service's totals, its version and its health are the operator's only.
- [ ] A file uploaded by two shops gives neither any sign that the other has it.
- [ ] A test with two shops in one database walks every route of the application and is part of the suite; a new route without a shop check makes it fail.
- **Out of scope:** encryption of files at rest; deletion of one shop's data on request (done by the operator by hand until Phase 2).

## R-MULTI-SHOP-003 — One shop cannot use up what all share
- **Story:** As a shop owner, another shop's heavy day does not stop my posters.
- [ ] Each shop has its own daily ceiling of provider spend and its own daily limit of messages read. The service keeps one ceiling above them all.
- [ ] When the service's ceiling is reached, every shop is told the service is paused, and nothing is debited.
- [ ] Jobs are taken in turn between shops; a shop with many queued jobs does not delay another shop's first job behind all of them.
- **Out of scope:** paid priority; more provider slots (stays two until measured).

## R-MULTI-SHOP-004 — Two shops on one phone
- **Story:** As someone who signs out, I leave nothing of my shop for the next person on this phone.
- [ ] What the application keeps on the device (chat threads, unsent text, remembered style) is separated by shop.
- [ ] « Se déconnecter » deletes what the application kept on the device for this shop, and the next shop to sign in sees none of it. One exception: when an image the shop paid for still waits for its outcome, the owner is told and may sign out anyway; that card alone is kept, under the shop's own key, visible to no other shop, so that it can be resumed. Images the browser keeps in its own cache are not deleted; the conditions of use say so.
- [ ] A page shows one shop for its whole life. Whenever the server does not confirm that shop (a session ended, a suspension, another shop signed in, a page brought back with the Back button), nothing of the shop is shown and the sign-in screen comes.
- **Out of scope:** protecting a device that stays signed in.

## R-MULTI-SHOP-005 — The pilot shop keeps everything
- **Story:** As the pilot shop, I find all my posters, versions, styles and my spending history after the change.
- [ ] The existing shop becomes one shop among others, with an identifier and its current password, and loses nothing.
- [ ] The change of the database is forward-only. The release is gated by a rehearsal on a fresh copy of the hosted pilot's database, run in the release image: every table keeps all its rows and the three ledgers keep their sums, or the release stops before anything changes. A backup is taken before the change runs on the real database.
- [ ] The existing spend ledger is kept whole and is attributed to that shop.

## R-MULTI-SHOP-006 — A shop can be suspended
- **Story:** As the operator, I can stop a shop without destroying its work.
- [ ] A suspended shop cannot sign in, and its sessions stop working at once; they work again when the shop is enabled. Its queued generations are cancelled and no further provider call is sent for it; a call already sent finishes and its result is kept. Credits are released by the prepaid-balance feature.
- [ ] Its data and balance are kept and come back when it is enabled again.
- **Out of scope:** automatic suspension rules.
