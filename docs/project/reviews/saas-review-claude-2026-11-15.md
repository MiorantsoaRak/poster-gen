# Review of the publishing and SaaS research — Claude, 2026-11-15

**What this is:** a review of Codex's [research report](social-publishing-saas-research-2026-11-15.md), asked by the user: check it, push back where a decision is not the best, add findings, and say what to begin with. **Status:** research and a proposal. Not requirements, not a design; PROJECT.md still lists SaaS, billing and publishing as non-goals.

**In one paragraph:** the report is careful and its facts mostly hold. Its plan is too large for where the product is. It proposes six features (accounts and workspaces, credits and billing, trial abuse, social publishing, two dashboards) before a second shop has used the tool, and one of them (direct publishing) depends on a Meta verification nobody knows a Madagascar business can pass. The code is closer to a small paid service than the report assumes: an audit run for this review found shop data already isolated, and an invite-only service for several shops about a week of work away. Start there, sell prepaid generations by hand, add a « Partager » button instead of the Meta API, and probe Meta's verification now because it costs nothing and takes calendar time.

## How this review was made

| Source | What it gave | Limits |
|---|---|---|
| Web check of the Meta claims (an Opus subagent; Meta's developer documentation, MDN data, WebKit bug tracker) | Verdicts on the report's four Meta claims, and six questions it left open | Meta's business help pages cannot be fetched by a tool; quotes came through a summarising fetch |
| Web check of payments and the Madagascar market (an Opus subagent; Papi, MVola, Orange, Stripe, Paddle, DataReportal, GSMA, official tax pages) | Verdicts on the payment claims; fees; price anchors; market size | Several pages returned 403; Facebook pages cannot be fetched, so local designer prices are thin |
| Audit of the code for several shops (an Opus subagent; reading plus a throwaway two-shop test) | What is isolated, what assumes one shop, and a size for the work | Stub providers only; no browser run; the test is in the scratchpad, not in the suite |
| The spend ledger of `backend/data-probe` (read by Claude) | Real cost and time per call | One shop's test data, one image model, a few dozen calls per kind |

Nothing in the application was changed for this review. No paid call was made for it.

## What holds in the report

- **Meta's API facts.** « Unified Login » exists and is the route Meta recommends for new Instagram integrations (no Page needed, a business portfolio needed). The Instagram carousel steps, the 20-image limit, JPEG only, and media fetched by Meta from a public address are all as written. Serving accounts that have no role on the app needs Advanced Access, so App Review and Business Verification.
- **The contradictory Instagram quota** (100 and 50 per 24 hours on the same page) is real; reading the limit at run time is the right answer.
- **Papi's published fees and mechanics** match the report exactly: Direct 1.20% plus operator fees; Transit 3.80% MVola, 3.60% Orange and Airtel, 4.20% cards; a hosted checkout; a callback signed with `X-Papi-Signature` and sent once; a status read-back.
- **Stripe does not onboard a Madagascar seller.** Paddle does not list Madagascar among excluded countries; nothing confirms payouts there.
- **Its engineering instincts.** Keep Vue, FastAPI and SQLite. Publish the confirmed export, never regenerate for a caption. Never retry a publication whose outcome is unknown. Credits on a ledger, never floating point. Fulfil a pack from a verified payment state, not from a return page. Append an adjustment, never edit the ledger. These are right and should survive into any design.

## Corrections and additions to its facts

**Meta**
1. **A pilot in Development mode is not a pilot.** Posts made by an app in Development mode are visible only to people who have a role on the app. Up to 50 testers can be added without any review, but their customers would not see the posts. Going Live with a business-login app appears to need Advanced Access to `public_profile`, hence Business Verification. So "a private pilot with no review" is at best "a pilot with verification and no App Review". The report's "testing only with accounts that have app roles" understates this.
2. **An individual cannot be verified.** Since 2023 Meta accepts only a business for the verification that Advanced Access needs. Whether a business registered in Madagascar passes, and with which documents, could not be established by either review: Meta's help pages are not readable by a tool. This is the largest unknown of the publishing feature, and it can be probed for free.
3. **App Review asks for more than the report scopes.** The recording for `pages_manage_posts` must show the user creating, editing and deleting a post. The feature is therefore publish, edit and delete, not publish and list.
4. **Multi-photo posts on a Page** through `attached_media` are not in Meta's current Page documentation; only community reports say they work. The report already says to validate it; treat it as unproven.
5. **AI labels.** Meta requires disclosure for photorealistic video and realistic audio, not for still images. But OpenAI's images carry provenance markers, and Meta labels images when it detects them. A poster may get an « AI info » label on its own. Instagram has an `is_ai_generated` field on the carousel parent; the Page photo endpoint has none.

**Payments**
6. **Who Papi is.** Its legal notice names the publisher as an IT services company and names no central-bank licence and no partner bank. Its earliest blog post is from September 2026; its usage figures are its own. Transit mode routes the customer's money through that company. No independent report on its reliability was found, in either direction.
7. **Direct is about half the cost of Transit on MVola**: 1.20% plus MVola's 1% merchant fee, against 3.80%. Direct needs a merchant contract with the operator; MVola publishes no list of documents and does not say whether a sole proprietor can sign.
8. **The manual way.** A customer who sends mobile money to a merchant number pays 250 Ar on 10,001 to 25,000 Ar and 500 Ar on 25,001 to 50,000 Ar. No integration and no contract are needed.

## What the report did not have

### The code is closer than it assumes
The report says the `shop_id` association "does not establish that arbitrary customers are isolated" and that it did not audit the implementation. The audit:

- **Data is isolated.** Every data query is scoped to the session's shop. In a test with two shops in one database, shop B made 67 attempts through the real routes on shop A's posters, versions, images, plans, jobs, styles and exports; all were refused. With the shop filter removed, the same test failed, so the test proves something.
- **Two leaks, both small:** `/api/usage` shows the service's total spend to any shop; `/api/status` is an operator's view open to any shop.
- **What assumes one shop:** the schema allows one shop row; one password for everyone; sign-in always opens shop 1; one spend cap for the whole service (one shop can exhaust it for all, shown in the test); one job queue, first in first out; the failed-login limit counts the address only, and many mobile users share one; a new password ends every session; browser storage is not separated by shop (read from the code, not run).
- **Size:** about 6 to 8 days for "several shops, each with its own password, created by the operator", in nine items of a day or less each.

### What a poster costs us
From the ledger of the test data, with the pilot's image model at medium quality, at 4,588 Ar to the dollar:

| Call | Cost | Time |
|---|---|---|
| Reading one chat message | USD 0.003 to 0.004 (about 15 Ar) | 2 to 3 s |
| A first image, or a whole new one | USD 0.028 (about 130 Ar) | 16 s typical, 19 s slow |
| An adjustment from an image | USD 0.040 (about 185 Ar) | 16 to 20 s |

A poster accepted first time costs about 145 Ar; with five adjustments about 1,150 Ar. Three consequences the report could not see:
- **An adjustment costs 40% more than a first image.** "One generation, one credit" is still fine, if a credit is priced several times above cost.
- **The older image model cost USD 0.21 an image**, seven times more. Prices follow the deployed model; changing model is a pricing event.
- **Reading is not free.** The limit is 200 reads a day for a shop, about USD 0.80 a day. For a paying shop that is noise; for a free account it is the main cost, larger than its five images. The report says to bound it; the number matters.
- One interrupted image call sits on the ledger at its USD 0.75 reservation, 27 times a real image. A customer's credit must not be held the same way by an unknown outcome.

### The market sets the size of the thing
- 14.3% of people in Madagascar use mobile internet (GSMA, 2025 data); Facebook reaches 4 to 5.5 million people; Instagram about 260,000. Facebook is where shops sell; Instagram is a tenth of it.
- 6.1 million mobile money accounts are active; 19.4% of adults own one.
- Anchors: a community-management package is 500,000 to 1,500,000 Ar a month; one poster from a freelancer is listed at about 81,500 Ar (a listing with no sales); the minimum wage is about 315,000 Ar a month; Canva Pro is about 82,600 Ar a month and needs an international card.
- No local service that makes a poster in French and takes mobile money was found. Google's Pomelli is not available in Madagascar.
- **Not established:** how many shop owners use email at all. This matters for the sign-in choice below.

A realistic first market is tens of shops, perhaps a few hundred. That is a reason to build small, not a reason not to build.

### The route without Meta's API
A phone can hand a file to another app through the browser's share sheet. For this product: the owner taps « Partager », picks Facebook or WhatsApp, and posts. What the check found:
- It works in Chrome on Android and Safari on iOS. It does not work inside the Facebook or Messenger in-app browser on Android.
- Meta's own rule and behaviour: the receiving app does not take a pre-filled caption. On iOS, sending text with files can drop the files. So: share the images alone, and copy the caption to the clipboard for the owner to paste.
- Instagram takes one image this way. Facebook posts as whichever profile is active; the owner switches to the Page first.
- **Not verified, needs a real phone:** Facebook Lite, WhatsApp Business, several images at once.

It is three more taps than a « Publier » button, it needs no approval from anyone, and it also reaches WhatsApp, which the Meta publishing API does not.

## Where I push back

**1. The order.** Six features before a second customer is the wrong order. The handoff still says "never verified: a real phone". The report's own first precondition is a shop that reliably creates and downloads a poster on a real phone; nothing after it should start before that is seen.

**2. Accounts, workspaces, brand profiles and channels.** Four levels of vocabulary are designed for the agency plan the report itself marks "later". A phone shop is one shop with one Page. Start with shop = account, as the code already has it, and add a level when a customer needs it.

**3. Three ways to sign in.** Google, Facebook and email, with linking rules between them, is weeks of careful work and the place where account takeovers happen. For an invite-only service the existing password, made per shop, is enough. When self-service comes, pick one method from evidence: the phone number and Facebook are the plausible identities here; email is unproven.

**4. The trial and its defences.** Five free generations cost us about 700 Ar. The report's own worst case, five thousand fake accounts, is about USD 700 to 1,000, and its item 8 (a global daily free budget with a stop switch) bounds that alone. Turnstile, device signals, disposable-email detection, selective phone verification and abuse-signal retention are the right list for a public launch and are not needed for an invite-only one, where there is no sign-up form to attack.

**5. Papi first.** The fees are real, the company behind them is unverified and recent. For a pilot, take payment by hand: mobile money to a merchant number, credit the shop from the command line. For self-service later, compare Direct on MVola (about 2.2%, needs a merchant contract) with Transit (3.8%, money held by Papi), and in Transit keep balances small with frequent payouts. No subscriptions until a provider is proven to support recurring debits; the report says this too.

**6. Direct publishing as a first feature.** It needs Business Verification of unknown outcome, an App Review, edit and delete of posts, a public address for media, token storage and a reconciliation of unknown outcomes. « Partager » gives most of the value this month. Keep direct publishing as a later feature, gated by the verification probe.

**7. Two dashboards.** A customer dashboard with seven menus and an operator dashboard with ten are a product of their own. The customer's product is a chat; it needs a line that shows remaining credits and the existing « Mes affiches ». The operator, for up to a few dozen shops, needs a command line (create a shop, set a password, add credits, disable) and the existing status view restricted to him.

**8. A risk the report underweights.** On 2026-11-15 the user noted that the image model writes product features nobody verified when asked for "4 lines of features", and chose to leave it ("just noted"). For one shop that is the owner's own risk. For a service it is the service's: an invented battery life on a paying customer's advert. Decide before selling to others: either the image request allows only features the owner listed, or the terms say plainly that the owner checks every text. The same goes for manufacturer marks drawn by the model.

## What to begin with

**Step 0 — see it on a phone (days, no new platform).**
- One real session with the pilot shop on a real phone, start to download. This has never been observed.
- A « Partager » button on the confirmed poster: images through the share sheet, caption copied. Test it on real devices with Facebook, Facebook Lite and WhatsApp Business. A caption field the owner writes; no generated caption yet.

**Step 1 — probe Meta for free (an hour of work, weeks of waiting).**
- Create the business portfolio for the Madagascar entity and start Business Verification, to learn whether its documents are accepted. Open Meta's help page for the document list while signed in; a tool cannot read it.
- Create an app in Development mode, post to the user's own Page, and look from another account: is the post public? This settles the largest unknown of direct publishing before any code.

**Step 2 — several shops, by invitation (about two weeks).**
- The nine items of the audit (6 to 8 days): shops with their own name and password, sessions and limits per shop, a spend cap per shop under the service's ceiling, a fair queue, the two leaks closed, storage keys per shop, the two-shop test in the suite.
- A prepaid balance per shop, in generations, debited when a generation is admitted and released on a definite failure; credited by the operator from the command line after a mobile money payment (2 to 3 days). This is the report's wallet with one grant category and no payment provider.
- Onboard five shops. Measure what the report rightly asks for before any price is fixed: generations per accepted poster, adjustments per poster, reads per poster, and what a shop will pay.

**Step 3 — only after five shops pay.** Self-service sign-up with one identity method and a global free budget; a payment provider; then, if the probe of step 1 passed, direct publishing with its App Review.

**A first price to test, not a decision:** at about 130 to 185 Ar of cost per generation, a generation sold at 500 to 1,000 Ar leaves three to seven times the model's cost before fees, failed calls and support, and a pack of twenty is 10,000 to 20,000 Ar, about an eighth to a quarter of one freelance poster. Whether shops pay that is exactly what step 2 measures.

## Decisions for the user

1. **The order:** invite-only with payment by hand first, as proposed here, or the report's fuller platform first.
2. **Sharing before publishing:** « Partager » now and Meta's API later, or the API first.
3. **Invented features**, before other shops use it: restrict the image request to features the owner listed, or state the owner's responsibility in the terms.
4. **The Meta probe:** start the business verification now (it needs the business's documents and the user's own Meta account).
5. **PROJECT.md:** the charter excludes all of this. Any of the above needs the scope changed there first, then requirements per feature.

## Not verified

- Whether a Madagascar business passes Meta's Business Verification, and whether an app can go Live without it.
- Whether posts made through Instagram's own login are public in Development mode.
- How the share sheet behaves with Facebook Lite, WhatsApp Business and several images. Needs phones.
- Papi's licence, payout delays and reliability; MVola's and Orange's merchant requirements.
- How common email is among shop owners; what designers who sell through Facebook really charge per poster.
- The audit's size estimate is an estimate; its browser-storage finding is from reading the code.
- The 2026 finance law's turnover thresholds (the sources disagree between 200 and 400 million Ar).
- Costs are from one shop's test data with one image model.

## Evidence

- Audit test (git-ignored, not in the suite): `outputs/saas-review-2026-11-15/test_tenancy_audit.py`, seven tests, and `mutant_check.py`. It was run from `backend/` with `uv run pytest <path> -q -p no:cacheprovider -s`. To count, it must be moved into `backend/tests/` as part of step 2.
- Cost figures: `backend/data-probe/affiche.db`, tables `poster_calls` and `chat_reads`, read on 2026-11-15.
- Web sources used by the two checks, by topic. Meta: developers.facebook.com pages on the Instagram platform overview, Unified Login, content publishing, the Page photos and posts references, access levels, app roles, app modes, App Review submission, Business Verification, the `pages_manage_posts` permission reference, the platform terms and developer policies; MDN browser-compat data for `navigator.share`; WebKit bug 251500. Payments and market: papi.mg (pricing, how it works, legal notice) and docs.papi.mg; mvola.mg (business portal, tariffs of 2025-02-17); developer.orange.com; stripe.com/global; Paddle's supported-countries page; DataReportal "Digital 2026: Madagascar"; GSMA's Madagascar digital economy report (October 2026); torolalana.gov.mg and EDBM on taxes; xe.com for the exchange rate (2026-11-15).
