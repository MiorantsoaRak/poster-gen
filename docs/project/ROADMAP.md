# ROADMAP — from the pilot to an invite-only service

**Status:** written 2026-11-15 on the user's request, from [Codex's research](reviews/social-publishing-saas-research-2026-11-15.md) and [Claude's review](reviews/saas-review-claude-2026-11-15.md). Decided by the user the same day (ADR-105): the service is invite-only first; **nothing is deployed again until the invite-only release is ready, with a dashboard for each shop and an administration dashboard.** The requirements of that release are drafts with working defaults; each still needs its design.

## The release rule

The pilot stays on the version deployed on 2026-11-14 until Release 1 below is complete. Work goes to `main` and is pushed; it is not deployed. This includes the chat work of 2026-11-15, which is pushed and not deployed.

Release 1 is complete when all six requirement files below are built, reviewed, and seen working together with two real shops in one database, on a real phone.

## Release 1 — « Invitation » (the next deploy)

In order of importance. The last column is the order I would build in, with the reason.

| # | Feature | Requirements | Why it matters | Build order |
|---|---|---|---|---|
| 1 | Several shops, each with its own sign-in | [multi-shop.md](requirements/multi-shop.md) R-MULTI-SHOP-001 … 006 | Nothing else can exist without it. The audit found the data already separated; sign-in, limits and two small leaks are not. | **First.** Every other feature hangs on "which shop". About 6 to 8 days by the audit. |
| 2 | Prepaid balance of generations | [prepaid-balance.md](requirements/prepaid-balance.md) R-BALANCE-001 … 007 | It is what is sold, and it bounds what a shop can cost us. Money rules are the hardest to change after shops have balances. | **Second.** Needs shops. Its ledger is what both dashboards show. |
| 3 | Administration dashboard | [admin-dashboard.md](requirements/admin-dashboard.md) R-ADMIN-001 … 006 | Without it no shop can be created or credited, so no shop can be invited. | **Third.** Needs shops and the ledger. Start with shops and credits, then costs and health. |
| 4 | Conditions of use and the owner's check | [service-terms.md](requirements/service-terms.md) R-TERMS-001 … 003 | Other people's adverts will carry what the image model writes. Must be settled before a second shop signs in. | **Fourth.** Small. Its one product decision (invented features) is the user's. |
| 5 | The shop's dashboard | [shop-dashboard.md](requirements/shop-dashboard.md) R-SHOP-DASH-001 … 004 | A shop must see what it has left and what it spent, and manage its own password. | **Fifth.** Mostly a view of what 1 and 2 hold. |
| 6 | « Partager » | [share-poster.md](requirements/share-poster.md) R-SHARE-001 … 005 | The way a poster reaches Facebook and WhatsApp without Meta's approval. | **Last, or in parallel.** It depends on nothing above; its risk is on real phones, not in the code. |

**The product's name and look (user, 2026-11-15):** the service is « Doka Studio », identity direction « Signal ». It is applied when the screens are built (T-BRAND-DOKA in TODO.md): the sign-in screen once multi-shop is finished, each dashboard as it is made. It is part of Release 1; it is not a seventh feature with its own gate.

**Importance and build order differ in one place:** the shop's dashboard is more visible than the conditions of use, but the conditions gate inviting anyone, so they come first.

## Beside Release 1 — things only the user can do, free

| What | Why now |
|---|---|
| Start Meta's Business Verification for the Madagascar business, and read Meta's document list while signed in | It decides whether direct publishing is possible at all. Nobody could establish it from outside; it takes weeks; it costs nothing. |
| Create a Meta app in Development mode, post to his own Page, look from another account | Settles whether a small pilot of direct publishing can be public without review. |
| One observed session on a real phone | Never done. The pilot's deployed version can be used; the new chat needs a temporary public address (`deploy/phone_session.py`, real money, on his word). |
| Ask MVola what a merchant account needs, and whether a sole proprietor can sign | Decides between collecting by hand, Direct, and Transit later. |

## Phase 2 — after five shops pay (requirements to write when it opens)

| Feature | Scope in one line | What opens it |
|---|---|---|
| Self-service sign-up | One identity method chosen from what the first shops actually use (phone number or Facebook); a lifetime welcome grant; a global daily free budget with a stop switch | Five paying shops, and more asking than the operator can create by hand |
| Online payment of packs | A hosted checkout for mobile money; credits granted only from a verified payment state; reconciliation of missed callbacks | Payments by hand taking real time each week; a provider's terms confirmed |
| Prices and packs in the application | Pack list, receipts, purchase history | Prices tested by hand first |

## Phase 3 — later (not specified yet)

| Feature | Depends on |
|---|---|
| Direct publishing to a Facebook Page and Instagram (publish, edit, delete, list, unknown outcomes) | Meta's verification passing; App Review |
| Malagasy interface and captions | PROJECT.md already plans it after the pilot |
| Monthly plans | A payment provider that supports recurring debits, proven |
| Several people per shop; several brands per account | A customer asking for it |

## Not planned

Rows of settings for the coloured word and the brand's lettering (they already work as scene adjustments, measured on 2026-11-15); a bot challenge, device signals and disposable-email detection (needed only with a public sign-up form); an operator form for every parameter.

## Open decisions that change a requirement

1. **Invented features** (service-terms, R-TERMS-002): the working default is that the owner is told and checks; the alternative is that the image may write only features the owner listed.
2. **What identifies a shop at sign-in** (multi-shop, R-MULTI-SHOP-001): the working default is an identifier the operator chooses; the alternative is the shop's phone number.
3. **Welcome credits** (prepaid-balance, R-BALANCE-006): the working default is five, granted by the operator when he creates the shop.
4. **A first price to test**: not in any requirement. The review suggests 500 to 1,000 Ar a generation; the operator types the pack text the shops see.
