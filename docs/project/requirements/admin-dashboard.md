# REQUIREMENTS — Administration dashboard

**Status:** Draft v1, 2026-11-15 (Claude), with working defaults marked **Default**. Part of Release 1 « Invitation » ([roadmap](../ROADMAP.md), ADR-105; the user asked for it as a condition of the next deploy). Depends on [multi-shop](multi-shop.md) and [prepaid-balance](prepaid-balance.md). No design yet.

**What exists:** `/api/status` and `/api/usage`, readable by the shop session. No operator account.

## Index

| ID | Title | Priority | Status |
|---|---|---|---|
| R-ADMIN-001 | The operator's own access | P0 | Draft |
| R-ADMIN-002 | Shops | P0 | Draft |
| R-ADMIN-003 | Credits and payments received | P0 | Draft |
| R-ADMIN-004 | Usage and costs | P1 | Draft |
| R-ADMIN-005 | Health and the stop switches | P1 | Draft |
| R-ADMIN-006 | The few settings | P2 | Draft |

## R-ADMIN-001 — The operator's own access
- **Story:** As the operator, I reach the administration with my own sign-in, and no shop can.
- [ ] The administration has its own sign-in and its own session. A shop's session is refused on every administration route, whatever address is typed.
- [ ] Every action that changes something (a shop created, a password set, credits changed, a switch flipped) is recorded with its time and what changed, and can be listed.
- [ ] **Default:** one operator. His password is set outside the application, like the shop password today.
- **Out of scope:** several operators with roles; two-factor sign-in (wanted before Phase 2).

## R-ADMIN-002 — Shops
- **Story:** As the operator, I invite a shop in a minute and see all shops at a glance.
- [ ] A list of shops: name, identifier, state (active, suspended), credits left and waiting, date of the last poster, number of posters.
- [ ] Create a shop: name, identifier, a first password shown once, welcome credits. The shop can sign in at once.
- [ ] Set a new password for a shop; suspend it; enable it again.
- [ ] Open one shop: its ledger, its recent generations with their outcome, its limits.
- **Out of scope:** signing in as a shop; seeing a shop's images (not needed to operate; **Default:** the operator sees counts and outcomes, not pictures).

## R-ADMIN-003 — Credits and payments received
- **Story:** As the operator, when a shop pays me by mobile money I credit it and keep the trace.
- [ ] Add credits to a shop with: how many, offered or bought, the amount received in ariary, the method, the payment's reference, a note.
- [ ] Remove or correct credits only by a new line with a reason; a balance cannot be typed over.
- [ ] Granting credits is usable at 360 px on a phone (added 2026-11-16 from the prepaid-balance design: a shop out of credits on a Sunday must not wait for the operator's laptop).
- [ ] A list of payments received, by period, with their total.
- **Out of scope:** payment providers, receipts sent to the shop, refunds in money.

## R-ADMIN-004 — Usage and costs
- **Story:** As the operator, I know what each shop costs me and whether a price holds.
- [ ] For a period, for each shop and for the service: generations (first images, adjustments), messages read, what the providers charged, credits spent, ariary received.
- [ ] The figures the price depends on: provider cost per generation, generations per confirmed poster, adjustments per poster.
- [ ] Every figure is computed from the ledgers; an empty period shows zero, never an example.
- **Out of scope:** charts beyond one simple view per period; accounting; taxes.

## R-ADMIN-005 — Health and the stop switches
- **Story:** As the operator, I see when something is stuck and can stop spending at once.
- [ ] What `/api/status` gives today, for the operator only: queue, failed and unknown jobs, spend against the cap, version, schema, age of the last backup.
- [ ] A switch that stops new generations for the whole service, and one per shop. Both say so to the shop in one sentence and take no credit.
- [ ] Jobs whose outcome is unknown are listed with the shop, the poster and what the shop's credit is doing.
- **Out of scope:** retrying a job from here; changing models or prompts.

## R-ADMIN-006 — The few settings
- **Story:** As the operator, I change the few numbers of the business without a release.
- [ ] Welcome credits; daily limits per shop; the text shops see about buying credits (packs, mobile money number, reference).
- [ ] A change applies from then on and is recorded.
- **Out of scope:** secrets, provider keys, model choice, anything that is a release today.
