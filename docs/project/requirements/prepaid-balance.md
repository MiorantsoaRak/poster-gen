# REQUIREMENTS — Prepaid balance of generations

**Status:** Draft v1, 2026-11-15 (Claude), with working defaults marked **Default**. Part of Release 1 « Invitation » ([roadmap](../ROADMAP.md), ADR-105). Depends on [multi-shop](multi-shop.md). Source: Codex's wallet rules and the cost figures of the [review](../reviews/saas-review-claude-2026-11-15.md). No design yet.

**What exists:** provider spending is reserved and recorded in micro-dollars against one cap. There is no customer unit.

## Index

| ID | Title | Priority | Status |
|---|---|---|---|
| R-BALANCE-001 | What costs a credit | P0 | Draft |
| R-BALANCE-002 | Debit, release and waiting | P0 | Draft |
| R-BALANCE-003 | The ledger | P0 | Draft |
| R-BALANCE-004 | No credit left | P0 | Draft |
| R-BALANCE-005 | The service's own ceiling | P0 | Draft |
| R-BALANCE-006 | Credits given and credits bought | P1 | Draft |
| R-BALANCE-007 | Reading messages is bounded | P1 | Draft |

## R-BALANCE-001 — What costs a credit
- **Story:** As a shop owner, I know before I tap what a tap costs.
- [ ] One generated image costs one credit: a first poster, a whole new image, or an adjustment of the scene.
- [ ] Editing by hand, opening, checking, downloading, another format without a new image, and sharing cost nothing.
- [ ] Every paid button says « 1 crédit » and shows what is left; the provider's cost in dollars is not shown to a shop.
- [ ] A poster the owner dislikes still cost its credit. A technical defect is repaid by the operator, by hand, with a reason.
- **Out of scope:** dearer credits for a better model; credits for captions.

## R-BALANCE-002 — Debit, release and waiting
- **Story:** As a shop owner, I never pay twice for one tap and never pay for an image I did not get.
- [ ] The credit is taken at the moment the generation is accepted, in one step with it. Two tabs or two taps cannot spend the same credit, nor take the balance below zero.
- [ ] A generation that ends with no image and a known failure gives the credit back.
- [ ] While the outcome is not known, the credit is shown as « en attente », apart from what is available; it is settled when the outcome is known, and never debited a second time when the job is recovered.
- [ ] The same request sent again (a lost answer, « Reprendre ») costs nothing more.
- **Out of scope:** automatic refunds in money.

## R-BALANCE-003 — The ledger
- **Story:** As the operator, I can explain every credit of every shop.
- [ ] Each change of a balance is one line that is never edited or removed: a grant (who, when, how many, why, and the payment it answers), a debit (which poster and version), a release, a correction with its reason.
- [ ] The balance is the sum of the lines. Restoring a backup cannot grant twice.
- [ ] Credits are whole numbers. Amounts paid are whole ariary. Provider costs stay in micro-dollars on their own ledger; the three are never mixed.

## R-BALANCE-004 — No credit left
- **Story:** As a shop owner with no credit, I am told how to get more, and I lose nothing.
- [ ] A paid button with no credit left sends nothing and says how to buy: the text the operator wrote (packs, mobile money number, what to put as reference).
- [ ] Posters, versions, downloads and sharing stay available at zero.

## R-BALANCE-005 — The service's own ceiling
- **Story:** As the operator, a shop's credits never let the service spend more than I allowed.
- [ ] The provider cap stays above everything: a generation that would pass it is refused whatever the shop's balance, with a sentence that says the service is paused, and no credit is taken.
- [ ] The operator can stop new generations for the whole service, or for one shop, at once.

## R-BALANCE-006 — Credits given and credits bought
- **Story:** As the operator, I can welcome a shop with a few credits and tell them apart from what it paid for.
- [ ] A grant is marked « offert » or « acheté ». **Default:** five offered credits when a shop is created, set by the operator.
- [ ] Offered credits are spent first. **Default:** credits do not expire.
- **Out of scope:** online payment, packs bought in the application, subscriptions (Phase 2 and 3).

## R-BALANCE-007 — Reading messages is bounded
- **Story:** As the operator, a shop cannot run up reading costs without generating.
- [ ] Reading a message costs no credit, and has a daily limit per shop. **Default:** 100 a day with credits left, 20 a day at zero.
- [ ] At the limit the chat says so and the step editor stays usable.
