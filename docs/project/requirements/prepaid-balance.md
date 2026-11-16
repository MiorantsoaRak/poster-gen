# REQUIREMENTS — Prepaid balance of generations

**Status:** Approved 2026-11-16 under the autonomy grant, with the amendments of the prepaid-balance design v4. Draft v1 by Claude, 2026-11-15, with working defaults marked **Default**. Part of Release 1 « Invitation » ([roadmap](../ROADMAP.md), ADR-105). Depends on [multi-shop](multi-shop.md). Source: Codex's wallet rules and the cost figures of the [review](../reviews/saas-review-claude-2026-11-15.md). Design: [prepaid-balance](../designs/prepaid-balance.md) v4.

**What exists:** provider spending is reserved and recorded in micro-dollars against one cap. There is no customer unit.

## Index

| ID | Title | Priority | Status |
|---|---|---|---|
| R-BALANCE-001 | What costs a credit | P0 | Approved |
| R-BALANCE-002 | Debit, release and waiting | P0 | Approved |
| R-BALANCE-003 | The ledger | P0 | Approved |
| R-BALANCE-004 | No credit left | P0 | Approved |
| R-BALANCE-005 | The service's own ceiling | P0 | Approved |
| R-BALANCE-006 | Credits given and credits bought | P1 | Approved |
| R-BALANCE-007 | Reading messages is bounded | P1 | Approved |

## R-BALANCE-001 — What costs a credit
- **Story:** As a shop owner, I know before I tap what a tap costs.
- [ ] One generated image costs one credit: a first poster, a whole new image, or an adjustment of the scene.
- [ ] Editing by hand, opening, checking, downloading, another format without a new image, and sharing cost nothing.
- [ ] Every button that makes an image says « 1 crédit » and shows what is left; a button that costs no credit says so. No dollar figure reaches a shop.
- [ ] The material of a text (« Générer la matière du texte ») is an image and costs one credit.
- [ ] A poster the owner dislikes still cost its credit. A technical defect is repaid by the operator, by hand, with a reason.
- **Out of scope:** dearer credits for a better model; credits for captions.

## R-BALANCE-002 — Debit, release and waiting
- **Story:** As a shop owner, I never pay twice for one tap and never pay for an image I did not get.
- [ ] The credit is taken at the moment the generation is accepted, in one step with it. Two tabs or two taps cannot spend the same credit, nor take the balance below zero.
- [ ] A generation that ends with no image gives the credit back at once, also when the provider's outcome is unknown; what the provider may have charged stays the service's cost.
- [ ] While the generation waits or runs, its credit is shown as « en attente », apart from what is available. It is spent when the version arrives and given back when the generation ends without one; it is never taken a second time when the job is recovered.
- [ ] The same request sent again (a lost answer, « Reprendre ») costs nothing more.
- **Out of scope:** automatic refunds in money.

## R-BALANCE-003 — The ledger
- **Story:** As the operator, I can explain every credit of every shop.
- [ ] Every grant and correction is a line that is never edited or removed: who, when, how many, why, the payment it answers (a correction may carry a signed amount), and for a correction its reason. Each generation is its own record: it holds its credit while it waits, runs or has made its image, and gives it back by ending without one; no generation is ever deleted.
- [ ] The balance is the sum of the lines minus the generations that hold a credit. A grant or correction carries a reference its shop cannot use twice, so one typed twice, or brought back twice after a restore, is refused. A restore returns grants and generations to the backup's time; images made after it are gone and not charged; the grants and corrections made since are copied back from the database the restore replaced, in their order and with their dates.
- [ ] Money received is the sum of the amounts of the lines: a payment moved from one shop to another is counted once.
- [ ] Credits are whole numbers. Amounts paid are whole ariary. Provider costs stay in micro-dollars on their own ledger; the three are never mixed.

## R-BALANCE-004 — No credit left
- **Story:** As a shop owner with no credit, I am told how to get more, and I lose nothing.
- [ ] A paid button with no credit left sends nothing and says how to buy: the text the operator wrote (packs, mobile money number, what to put as reference).
- [ ] Posters, versions, downloads and sharing stay available at zero.
- [ ] Before the tap, the button says what blocks: a paused service or the shop's day reached come before the lack of credit. A shop with three credits or fewer is shown how to buy. « Reprendre » and « Réessayer » are not new requests: they stay available at zero and while blocked, and the server answers what it stored or refuses with its own sentence.

## R-BALANCE-005 — The service's own ceiling
- **Story:** As the operator, a shop's credits never let the service spend more than I allowed.
- [ ] The provider cap stays above everything: a generation that would pass it is refused whatever the shop's balance, with a sentence that says the service is paused, and no credit is taken.
- [ ] A shop's daily ceiling of provider spend (multi-shop) can also refuse a generation while credits are left; it says « Réessayez demain » and takes no credit.
- [ ] The operator can stop new requests to the AI for the whole service at once (images, styles, text proposals, reading messages); requests already admitted finish. One shop is stopped by suspending it, which also stops its sign-in.

## R-BALANCE-006 — Credits given and credits bought
- **Story:** As the operator, I can welcome a shop with a few credits and tell them apart from what it paid for.
- [ ] A grant is marked « offert » or « acheté ». **Default:** five offered credits when a shop is created, set by the operator.
- [ ] Which credits a generation used is not recorded; it can be computed from the lines if an expiry or a refund in money is ever built. **Default:** credits do not expire.
- **Out of scope:** online payment, packs bought in the application, subscriptions (Phase 2 and 3).

## R-BALANCE-007 — Reading messages is bounded
- **Story:** As the operator, a shop cannot run up reading costs without generating.
- [ ] Reading a message costs no credit, and has a daily limit per shop. **Default:** 100 a day per shop, whatever its balance. A lower limit for a shop with no credit waits for self-service sign-up (Phase 2).
- [ ] At the limit the chat says so and the step editor stays usable.
