# Social publishing and SaaS research

**Date:** 2026-11-15. **Status:** Research and proposed scope, with targeted verification below; not approved requirements or design. **User confirmations:** the selling business is in Madagascar; ordinary posts first, paid advertising later; no provider accounts have been set up yet.

Affiche IA can grow into a service where a customer generates posters, prepares an ordered selection with a caption, publishes to connected business accounts, and buys more generations. Start with prepaid packs and a small publishing flow; add recurring plans after measuring repeat use and cost per accepted poster. The difficult boundaries are customer isolation, credit accounting, payment confirmation and uncertain publishing outcomes.

## What the current project can reuse

The project documents describe a single-shop pilot with a shared shop session, durable generation jobs, idempotent mutations, provider-cost reservations, immutable versions, confirmed server exports and a Vue editor/chat. The existing `shop_id` association helps, but does not establish that arbitrary customers are isolated. SaaS, billing and publishing are currently explicit non-goals in PROJECT.md; this research proposes their future scope without changing that charter.

Keep Vue, FastAPI, the editor, the job admission safeguards and the historical provider ledger. Avoid a rewrite or microservices. The stored export is the right source for publication: the current format-export design already binds confirmation to an exact rendered file and hash. A new caption or publication must not ask the image model to regenerate an approved poster.

References: [PROJECT](../PROJECT.md), [generation jobs](../designs/generation-jobs.md), [creation library](../designs/creation-library.md), [format export](../designs/format-export.md), [hosted pilot](../designs/hosted-pilot.md). These establish the intended existing boundaries; this session did not audit their current implementations.

## Facebook and Instagram capabilities

### Connection and developer credentials

Affiche IA should own its Meta developer application and server credentials. Customers choose **Connect Facebook** or **Connect Instagram**, authorize access with Meta, and select eligible assets. Import the authorized account IDs, names and granted capabilities. A manually entered Page name, URL or ID is display information, not proof of publishing authority. No customer developer app or pasted token should be required in the ordinary flow.

Meta exposes the Pages a person can access through `GET /{user-id}/accounts`. Actual Facebook Page creation through that API is restricted to test users or apps allowlisted by Meta. Interpret “several pages” as several app brand profiles and connected existing channels; offer a link to Meta for creating the actual Page. [Meta User Accounts](https://developers.facebook.com/docs/graph-api/reference/user/accounts/)

Facebook publishing uses a Page access token and the relevant Page tasks. The Page Feed reference lists `pages_manage_posts`, `pages_read_engagement` and `pages_show_list` for publishing. Request capabilities needed for the chosen actions; avoid requesting comments, messaging or advertising permissions merely for possible future features. [Meta Page Feed](https://developers.facebook.com/docs/graph-api/reference/page/feed/)

Instagram supports professional accounts, including business and creator accounts. Meta now recommends **Unified Login** for new integrations: login with Instagram or Facebook, no linked Facebook Page required, but a business portfolio is required. Instagram Login is another route without a Page or portfolio required by its login flow. A Page-linked Facebook Login route also exists. Prefer Unified Login if pilot customers satisfy its onboarding requirements; evaluate Instagram Login if the portfolio step blocks the target shops. Confirm the route and permissions in the actual app before committing to one. [Meta platform overview](https://developers.facebook.com/documentation/instagram-platform/overview), [Unified Login](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-unified-login)

**Verification refinement:** Unified Login's setup guide also requires an app owned by a business portfolio, HTTPS callbacks and a real professional test account (synthetic Meta test users are not supported). Its default configuration includes messaging, comment and ads scopes; the guide marks basic and messaging permissions as required. Do not assume a publishing-only configuration has no messaging-related onboarding. Compare the actual minimum consent and app-review burden with Instagram Login before selecting the route. [Unified Login setup](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-unified-login/get-started), [Permission configuration](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-unified-login/permissions)

The login used to enter Affiche IA and the authorization to publish are separate grants. A Google user can connect Facebook; Facebook sign-in alone does not authorize Page publishing. Connection tokens stay encrypted on the backend, with encryption keys outside the database, redacted logs, revocation and a reconnect path.

### Creating and listing publications

| Operation | Provider capability and proposed use |
| --- | --- |
| Facebook single photo | `POST /{page-id}/photos`; keep the returned photo/post identity. |
| Facebook multiple photos | Upload unpublished photos and then create one Page feed post with their `attached_media` references. Meta’s SDK exposes both `published` on photo creation and `attached_media` on feed creation. This is the integration approach to validate against the chosen API version. |
| Facebook published list | Query the Page’s published-post edge for authored publications; the feed edge is also available but includes broader activity. Store app-created history locally and paginate provider imports. |
| Instagram carousel | Create child media containers, then a parent carousel, then publish the parent. |
| Instagram list | `GET /{ig-id}/media`; request caption, timestamp, permalink and available media fields. |

Sources: [Meta Pages posts guide](https://developers.facebook.com/documentation/pages-api/posts), [Meta’s Page SDK source](https://github.com/facebook/facebook-python-business-sdk/blob/main/facebook_business/adobjects/page.py), [Meta Page edges](https://developers.facebook.com/docs/graph-api/reference/page/), [Instagram media reference](https://developers.facebook.com/documentation/instagram-platform/instagram-graph-api/reference/ig-user/media).

**Ordering:** store the customer’s selection and send references in that order. For Instagram, the current guide documents carousels of up to 20 items and cropping based on the first image. Facebook may present a multi-photo post as a grid; promise the submitted order, not an identical layout across devices. Verify both destinations with numbered test images before promising cover/order behavior. Do not confuse a Facebook multi-photo post with a paid carousel ad. [Instagram publishing guide](https://developers.facebook.com/documentation/instagram-platform/content-publishing)

**Media preparation:** Instagram’s image reference requires JPEG, sRGB, at most 8 MB and a feed aspect ratio between 4:5 and 1.91:1. Current 1080×1350 feed and square exports fit those proportions; the existing PNG needs a JPEG publishing derivative and a preview of that derivative. Story assets need a separate workflow. Container creation is not publication. [Instagram media specifications](https://developers.facebook.com/documentation/instagram-platform/instagram-graph-api/reference/ig-user/media)

Meta must be able to fetch the media from a public server. Use temporary, unguessable URLs restricted to the exact publishing derivatives; do not expose the private image library. Their lifetime must cover processing and recovery, not expire immediately after the browser submits. The current guide also exposes an AI-disclosure parameter on the parent publication. [Instagram content publishing](https://developers.facebook.com/documentation/instagram-platform/content-publishing)

**Provider limits need a probe:** the current publishing guide gives 100 posts per rolling day in one section and 50 in its carousel section. Do not promise either quota as a product entitlement. Query the provider’s publishing-limit endpoint, enforce a conservative app quota and verify the selected API version. Likewise, validate Facebook multi-image limits rather than borrowing Instagram’s limit. [Instagram publishing limits](https://developers.facebook.com/documentation/instagram-platform/content-publishing)

### Recommended customer flow

1. Choose a brand profile and destination accounts.
2. Select exact approved poster versions from the library, showing price and date so an old offer is not selected accidentally.
3. Reorder numbered thumbnails by drag or **Move earlier / Move later** buttons, usable with keyboard and touch.
4. Write the caption in a multiline text editor with line breaks, emoji and a destination-specific counter. Ordinary posts do not need an HTML rich-text editor. Allow optional per-network caption overrides.
5. Preview each destination’s actual media/caption combination. Add alternative text where supported. Normalize image proportions only with an explicit preview; do not silently crop the price, logo or contact line.
6. Save a draft or explicitly confirm **Publish now** with the account names visible. Scheduling is a later increment.
7. Show delivery results per destination, provider permalink and recoverable next action.

The **Publications** screen should offer Drafts, In progress, Published and Needs attention, with account/date/status filters. List app publications first; add a clearly marked “From Facebook/Instagram” import for recent externally created posts. Show last synchronization time. A provider outage must leave local history readable and marked stale; never invent a publication success.

Caption assistance is useful later, provided it uses only verified product facts. Human review remains necessary before publication: the handoff already records that image generation can invent product features.

### Failure behavior that must enter the design

| Situation | Required product behavior |
| --- | --- |
| Token revoked, role removed, permission declined | Mark the connection as needing attention; explain reconnect or Page-role action. Do not repeatedly retry authorization failures. |
| Facebook succeeds, Instagram fails | Show partial success and the Facebook link. Retry only the unresolved destination. |
| Meta accepts a post but the response is lost | Keep an unknown outcome. Reconcile using stored provider IDs/status where possible; require review if uncertainty remains. No blind second publish. |
| Double tap or browser reconnect | Return the existing app publication operation, rather than create another one. App idempotency does not imply provider exactly-once delivery. |
| Upload fails partway | Keep uploaded IDs and resume safely where supported; expire/clean abandoned uploads. Do not publish an incomplete selection silently. |
| Poster edited after draft or queue admission | Publication keeps its frozen media/caption snapshot. Replacing it is an explicit action requiring another preview. |
| Account disconnected or workspace suspended before execution | Recheck authorization before dispatch. Stop pending delivery according to the explicit suspension policy. |
| Provider rate limit or transient read failure | Bounded backoff; distinguish safe reads from mutations whose outcome may be unknown. |

### Public SaaS launch dependency

Testing only with accounts that have app roles is different from serving arbitrary customers. Meta’s Advanced Access requires App Review and Business Verification for outside professional accounts. Prepare the working connection/publishing/listing flow, reviewer instructions and screencasts, privacy/data-deletion handling, business documentation and continuing Data Use Checkup obligations. Approval and timing cannot be guaranteed. [Meta access levels](https://developers.facebook.com/documentation/instagram-platform/overview), [App Review](https://developers.facebook.com/docs/resp-plat-initiatives/individual-processes/app-review/), [Data handling tutorial](https://developers.facebook.com/docs/resp-plat-initiatives/individual-processes/data-handling-questions/tutorial)

## SaaS account boundaries

The customer-facing vocabulary should distinguish:

- **Account:** a person and their sign-in methods.
- **Workspace:** a business/customer boundary with one payer, wallet and plan.
- **Brand profile:** shop name, verified contacts, logo and brand defaults.
- **Social channel:** an authorized Facebook Page or Instagram professional account attached to a brand profile.

A person can access multiple workspaces; a workspace can have multiple profiles and channels. Start with one owner per workspace, leaving team invitation as a later capability. A Page and its Instagram account are two publishing destinations; explain clearly whether a plan limits destinations or brand profiles. Do not award a new trial for every workspace, profile or connection.

Before public access, review every route and background operation for ownership: originals, thumbnails, drafts, scenes, exports, chat, style references, provider tokens, jobs and usage. Content-addressed storage or unguessable UUIDs are not authorization. Cross-workspace guessing, cache hits and queued jobs need isolation tests. [OWASP multi-tenant security](https://cheatsheetseries.owasp.org/cheatsheets/Multi_Tenant_Security_Cheat_Sheet.html)

Keep the existing architecture initially. PostgreSQL and private object storage are reasonable candidates before broader concurrent use, but their adoption needs a measured capacity and operational decision. A database switch alone does not provide isolation. Do not increase worker/process count while the current single-process lock and SQLite job ownership assumptions remain unchanged. Any approved migration must preserve existing poster history, confirmed assets and the complete spend ledger.

## Credits and commercial tiers

### Sell understandable operations

Recommend **one standard image generation = one credit**, including an image-model revision. This is a proposed customer unit, not a currency balance or a promise of an accepted poster. Price premium models/quality separately only if the measured cost requires it. Show the debit before confirmation.

Manual edits, reopening, downloads and format rendering without a paid model remain free. A price correction is free only when it is a text-layer change; with the price drawn into the scene it requires a new paid generation, as the project already documents. Charge no image credit for publishing existing files. Bound caption/chat reading separately so a zero-image-credit account cannot run unlimited paid text calls.

**Pushback on five free posters:** define the trial as **five lifetime image generations, revisions included**, rather than five documents with unlimited regeneration. Label it “5 générations offertes.” A trial user who gets each result first time can make five posters. Do not promise five accepted posters without funding their retries.

| Offer | Suggested behavior, quantities to validate |
| --- | --- |
| Free trial | Five lifetime standard generations; one brand profile; downloads and drafts; no direct social publication. No monthly refill. |
| Prepaid | Packs such as 20/50/100 credits, no mandatory recurring subscription. Customers can keep generating until their purchased credits run out. |
| Regular shop plan | Monthly allowance and several channels; optional prepaid top-ups; unused-period policy explicit. |
| Agency plan, later | More brands/channels, team approval, higher concurrency and exports. Build only after actual demand. |

Treat the proposed pack sizes as packaging examples, not prices or commitments. Define publishing entitlements separately from credit balance: a prepaid buyer is a paid customer. Recommended policy: packs enable bounded direct publishing for that customer's approved posters, with explicit channel and fair-use limits, even after the last generation credit is spent. Avoid silently treating them as Free when their wallet reaches zero. Set storage retention and ongoing publication limits before making a lifetime promise.

### Wallet rules to settle before sales

- Keep trial, subscription-period and purchased credit grants distinguishable. Use expiring allowances first; purchased credits survive subscription cancellation. Proposed purchased credits have no routine expiry while the service operates; publish termination/refund terms.
- A renewed subscription grants once for the paid billing period, not on every webhook or calendar-month reset. Annual billing needs an explicit monthly allocation policy if advertised that way.
- Reserve credits atomically before queuing a generation. Concurrent tabs must not overdraw. Record consumption, releases, refunds and support adjustments in an auditable ledger.
- Definite failure with no deliverable: release/refund the customer credit. An uncertain provider outcome remains pending until reconciled; show it separately from available credits. A recovered job must not cause a second customer debit.
- A subjective dislike consumes a generation; a documented technical defect can receive a support credit. Otherwise an unlimited “reject” button becomes unlimited paid compute. The business must budget provider-charged failures separately.
- Limit revisions per poster family as a usability/safety control, while the wallet and per-account/provider spend caps bound cost. Copying, branching or deleting must not restore trial credits. A counted new paid poster may be permitted without pretending it is a free revision reset.
- Plan downgrades preserve data. Over-limit channels can be paused/read-only until the customer chooses which remain active. No automatic deletion of posters or bought credits.
- Keep provider USD/micro-dollar costs, customer credits and collected payment amounts separate. Never use floating-point arithmetic for money or credit ledgers.

The existing provider reservations remain a second, independent safeguard. Customer credits cannot permit a job that would break the application's global provider cap.

## Reducing trial abuse

No inexpensive control can prove “one natural person forever” across email, Google and Facebook. Aim to make repeated trials costly while bounding total exposure.

Recommended layers:

1. Verify email before email-signup activation; grant trial credits once with an atomic, durable record. No grant on every login, linked identity or new workspace.
2. Add a bot challenge to suspicious signups and trial grants. Turnstile requires backend verification; its tokens are short-lived and single-use. It reduces automation, not human multi-accounting. [Cloudflare validation](https://developers.cloudflare.com/turnstile/get-started/server-side-validation/)
3. Rate-limit signups, verification email, chat reads and generation by account and network; use a first-party device/session signal as another risk signal. Shared mobile IPs are common: IP alone must not permanently ban a shop.
4. Use suspicious signup bursts and disposable email as risk signals with a review path. Do not strip dots and plus suffixes from every email domain as though all providers used Gmail rules. [OWASP email handling](https://cheatsheetseries.owasp.org/cheatsheets/Email_Validation_and_Verification_Cheat_Sheet.html)
5. For elevated risk, require a verified phone or payment before releasing additional trial usage. Phone verification has its own cost and bypasses; apply it selectively.
6. Optional risk signal: repeated connections of the same provider-owned Page/account. It is not a universal identity check and should not force Free users to grant publishing permission.
7. Keep short, disclosed retention for abuse signals. Account deletion must not trivially recreate the trial, but any retained deduplication record needs a documented lawful retention basis. Hashing personal data does not remove privacy obligations.
8. Enforce a global daily free-generation spend cap and a stop switch. This bounds loss when attackers evade every other signal.

Five thousand fake trial accounts would otherwise offer 25,000 image generations. If the daily free budget is B, admissions must reserve within B regardless of signup volume. A waitlist is a valid fallback when the free budget is exhausted.

## Sign in and recovery

Offer Google, Facebook and email. Use established authentication/OAuth libraries or a managed identity provider after checking Vue/FastAPI compatibility, account-linking controls, cost and data location; this research does not select a vendor.

For email/password, create a pending account and activate only through a single-use expiring verification link. Expired links can be resent with rate limits; password recovery must not reveal account existence. An email magic-link approach is another option, but choose one primary email journey rather than implement both immediately. [OWASP email verification](https://cheatsheetseries.owasp.org/cheatsheets/Email_Validation_and_Verification_Cheat_Sheet.html)

Identify Google users with the provider subject, not email. Verify the token signature, audience, issuer and expiry on the backend. Google's treatment of email ownership differs between Gmail/Workspace and third-party email addresses; do not assume every returned address is currently controlled just because an old verification claim exists. [Google token verification](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token), [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect)

Link Google/Facebook/email to an existing account only through an authenticated linking flow proving control of both sides. Matching email alone must not merge wallets or grant access. Facebook may not provide a usable email: allow an explicit contact-verification path. Protect admin accounts with MFA and require reauthentication for sensitive account changes. [OWASP account linking](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html#secure-federated-account-linking)

## Payments for a Madagascar business

| Option | Evidence and recommendation |
| --- | --- |
| Papi, added after the user's suggestion | Evaluate first for local prepaid packs: hosted checkout covers mobile money and cards, with direct or transit collection. Detailed findings and limits are in the Papi addendum below. No merchant account or production approval yet. |
| MVola | Its official business portal documents website/app payment integration and a developer sandbox. Strong first candidate for local prepaid packs without requiring customers to hold a bank card. Obtain merchant terms, fees, settlement details and the actual API contract before selecting it. Public material reviewed here does not establish recurring debit support. |
| Paddle | Madagascar is absent from the official unsupported-supplier policy returned by search, but direct retrieval of that policy returned HTTP 404. Treat this as indexed evidence for a candidate, not current verified seller eligibility or an approved merchant account. Confirm seller onboarding, payout availability, the AI product and proposed credits with Paddle. Useful candidate for cards/international sales. |
| Stripe directly | Madagascar is absent from its published supported merchant-country list. Do not make it the default for the confirmed Madagascar entity. Selling to Malagasy customers and onboarding a Malagasy seller are different questions. |

Sources: [MVola business portal](https://www.mvola.mg/portail-business/), [Paddle supplier-country policy](https://www.paddle.com/help/start/account-verification/which-countries-are-supported-by-paddle), [Stripe global availability](https://stripe.com/global).

Paddle models a non-recurring price with `billing_cycle: null`, suitable for a one-time pack, and markets support for AI credit packs. Its native metered usage-balances feature is currently early-access/beta. Do not make the local MVola-compatible wallet depend on admission to that beta. [Paddle prices](https://developer.paddle.com/api-reference/prices/create-price/), [Paddle for AI companies](https://developer.paddle.com/get-started/how-paddle-works/ai-companies/), [Usage billing availability](https://developer.paddle.com/build/usage-based-billing/)

Updated recommendation after the Papi suggestion: evaluate Papi hosted checkout for the first local prepaid packs, comparing its settlement terms and total fees with direct MVola. Paddle remains an optional international billing candidate, subject to onboarding. Offer manual repeat purchases of packs or prepaid access periods before requiring automatic renewal. A customer should see the exact amount/currency, credited units and whether a purchase renews. Never present MGA checkout or local settlement support for a provider until verified.

Credit fulfillment must follow a verified provider payment state, not a return-page URL, screenshot or browser claim. For Paddle, authenticate the raw webhook using its destination secret; events can repeat and arrive out of order, so deduplicate durable event IDs and reconcile transaction state before granting units. For MVola, implement its own documented callback authentication/status confirmation once obtained; do not assume Paddle's signature scheme applies. [Paddle signatures](https://developer.paddle.com/webhooks/about/signature-verification/), [Paddle delivery guarantees](https://developer.paddle.com/webhooks/about/how-webhooks-work/)

Refunds, reversed payments and disputes need explicit policies for unspent credits, spent credits and suspended new spending. A payment reconciliation screen and replay-safe support adjustment are required before taking money. Local business, tax and consumer terms need jurisdiction-specific validation; this report does not establish legal compliance.

## Customer dashboard

Recommended navigation in French:

| Menu | Primary contents |
| --- | --- |
| **Accueil** | “Créer une affiche”, available/pending credits, allowance renewal date, recent posters, publication problems and account connection status. |
| **Créer** | Existing chat as the primary action; keep the step editor available. |
| **Mes affiches** | Search, brand/status/format filters, exact versions, review and export; “Créer une publication” from selected posters. |
| **Publications** | Drafts, in progress, published, needs attention; destination filters, previews and permalinks. Calendar follows scheduling. |
| **Marques et comptes** | Brand profiles, logo/contact defaults, Facebook/Instagram connections and reconnect actions. |
| **Crédits et facturation** | Three grant categories, usage history, packs, plan, invoices, receipts, renewal/cancellation and support refunds. |
| **Paramètres** | Profile, linked sign-ins, contact verification, active sessions, notifications, data export/deletion; team access later. |

Limit home to a few useful cards. A 30-day generation/credit chart and publication success counts help; show an empty state for a new shop. Reach/engagement require a separate insights integration and permission review. Do not invent sales ROI from post count or show charts with mock numbers.

Use the app's current neutral surfaces and restrained glass accents, with poster thumbnails as the main color. Desktop: compact sidebar, workspace switcher, clear content area. Phone: simple navigation for Create, Posters, Publications and Account; a persistent primary action when relevant. Composer: caption and numbered media beside a destination preview on desktop, stacked on mobile. Use native text, visible labels, meaningful empty states, accessible contrast and reduced motion. Avoid making a shop owner navigate a financial control panel just to generate a poster.

## Operator dashboard

This is a separate privileged application area. Workspace owners must never gain platform access by changing a route or client-side role.

| Menu | Views, cards and actionable parameters |
| --- | --- |
| **Overview** | Paying workspaces, trial activation, collected revenue, provider cost, credit liability, errors and queue health. Date/environment filters and visible freshness. |
| **Customers** | Users/workspaces, verification and suspension states, plan, channels, credit ledger and support history; attributable manual credit adjustments. |
| **Payments** | Transactions, webhook failures, reconciliation, refunds, reversals and payouts; subscriptions when enabled. Separate recurring revenue from pack sales. |
| **Usage and costs** | Cost by provider/model/quality/workspace; cost per generation and accepted poster; revision distribution; actual versus estimated cost; spend reservations. |
| **Jobs and publishing** | Pending/failed/unknown operations, queue age, per-destination results, revoked connections and safe recovery actions. Never a universal blind retry button. |
| **Plans and limits** | Versioned prices/credit grants, page/brand/seat limits, trial allowance, revision safety cap, storage/publication quotas, notification thresholds. New settings apply prospectively. |
| **AI configuration** | Allowlisted models/quality, versioned prompts, estimates and rate cards, timeouts/concurrency, rollout flags, provider health and global spend caps. |
| **Abuse and security** | Signup bursts, challenge results, trial spending, false-positive reviews, account linking and access audit. Restrict access to personal signals. |
| **System and releases** | Deployed frontend/backend commit, schema version, renderer/fonts build, prompt/config version, build time, current feature flags, provider API version, backup/restore result, disk and job health. |
| **Settings and audit** | Integration connection health, secret rotation metadata, mail delivery, notification templates, retention policy and attributable admin changes. |

Useful charts: daily generation/revision volume; daily revenue versus provider expenditure; signup → verified → first generation → accepted export → paid conversion; median and p95 generation latency; failure/unknown-outcome rate; publication success by destination. Measure gross margin with fees, storage, support and retries included. Do not call pack revenue MRR or confuse cash collected, revenue recognition and unspent-credit obligations.

**Pushback on “every parameter”:** business parameters can be editable, validated, permission-controlled and audited. Infrastructure changes, arbitrary environment variables and raw secrets should not be a general form. Secret values are write-only/masked with rotation metadata; migrations, encryption roots and host configuration remain controlled release operations. Never edit the original financial ledger to fix a balance: append an adjustment with a reason.

## What must precede paid subscriptions

1. A shop can reliably create, review, download and reopen an accepted poster on a real phone. Address the known invented-product-features gap before encouraging automatic distribution.
2. Account isolation and asset/job ownership verified with at least two unrelated workspaces; secure signup, verification, recovery and identity linking.
3. Published credit semantics, measured accepted-output costs and conservative margin under revisions, failures and free usage. Price packs from measured cost distributions, not one lucky model call.
4. Concurrent credit reservations, payment replay/reversal cases, unknown provider outcomes and restore reconciliation verified. Test real-provider sandbox contracts in addition to local mocks.
5. A complete receipt, refund, contact/support, data-retention and account-closure journey. Cancellation does not silently destroy paid credits.
6. Observable spend caps, a free-budget stop switch, durable backups and a tested restore. Restoring old data must not regrant spent credits, refulfill paid transactions or republish posts.
7. Meta approval before selling public direct publishing. While pending, explicitly sell generation/export only; customers can post downloaded files manually.

Recommended commercial sequence: paid private pilot → prepaid credit packs → optional shop subscription → agency/team features. Begin the Meta approval preparation early because it is independent of subscription demand.

## Proposed feature split and next gate

| Proposed slug | Requirement scope |
| --- | --- |
| accounts-workspaces | Google/Facebook/email identities, verification/recovery, isolation, profiles/channels and ownership. |
| credits-billing | Wallet semantics, pack checkout, verified fulfillment, refunds, entitlements; recurring allowance later. |
| trial-abuse | Lifetime grant, risk controls, rate limits, privacy retention and global free budget. |
| social-publishing | Meta connections, ordered approved images, captions, publish/list/reconcile; scheduling and insights later. |
| customer-dashboard | Customer navigation, creation/library integration, usage and billing visibility. |
| platform-operations | Operator access, costs, failures, adjustments, safe configuration and release visibility. |

These are proposed boundaries, not implementation tasks. The next gate is approval of the scope expansion and priorities, then one draft requirements file per selected feature with testable acceptance criteria. Only approved requirements lead to designs, and only approved designs lead to implementation tasks.

Decisions remaining for that requirements step: trial generation wording; initial pack sizes/prices after margin measurement; publication/channel entitlement for prepaid buyers; retention and credit-expiry promises; Meta login route for target shops; payment-provider acceptance. The confirmed country and ordinary-post scope are already settled.

## Research verification and limits

Official Meta, Google, Cloudflare, OWASP, MVola, Stripe and Paddle documentation was consulted. Meta's own SDK was used to corroborate the multi-photo parameter surface because the photo reference returned HTTP 429. Numbered-image ordering, provider approval and actual account capabilities still require a controlled integration probe.

Postman's API-engineer and API-discovery guidance was read. Orbit search and integrate returned Page-listing and Instagram publish-container resources, but their brief was only a partial fit and contained obsolete v17 examples and inconsistent version placeholders. Current Meta documentation takes precedence. The Postman CLI is unavailable in this shell; no workspace initialization, collection import, remote publication or endpoint execution was performed.

The original checkpoint was documentation research only, without application tests. The subsequent user-authorized verification is recorded next. No application implementation, production access, real payment, paid model call or social post occurred in either step. Claude's concurrent chat audit/implementation remains independent.

## Verification addendum of 2026-11-15

The user authorized necessary verification, then confirmed that no provider accounts are set up. Credential-presence checks found no Meta, MVola or Paddle credentials in the process environment; no secret values or `backend/.env` were read. This permits existing local checks and public-document verification, but not authenticated provider transactions or posts.

### Local regression evidence

Command from `backend/`:

```sh
uv run pytest tests/test_admission.py tests/test_poster_jobs.py tests/test_exports.py tests/test_api.py tests/test_backup.py -q --junitxml=../outputs/saas-verification-2026-11-15/regressions.xml
```

**Result: 125 passed in 81.16 seconds; exit 0; zero failures, errors or skips.**

| Existing suite | Passed | What this verifies |
| --- | ---: | --- |
| Admission | 39 | Provider spending caps, reservation boundaries, duplicate requests, concurrent admission and existing generation-chain limits. |
| Poster jobs | 25 | Shared budget reservations, cancellation/claim races, dispatch/crash recovery, ambiguous errors, bounded retry and persisted response recovery. |
| Exports | 22 | Real local renderer integration, approved bytes surviving later edits, stale/corrupt export refusals and supported-format export behavior. Includes wrong-shop render access refusal. |
| API | 34 | Existing shared-shop authentication, protected routes, session expiry, request validation and real loopback HTTP session behavior. |
| Backup | 5 | Consistent local backup/restore, retained asset bytes and explicit backup failure behavior. |

These tests use isolated temporary data, test configuration with `env_file=None` and fake/stub provider behavior. They do not touch the running app on 8000/5173. The checkout was `63dee20527caaf2e341e88850cdb97e64a11d019` plus concurrent uncommitted work; this is not a production-release certification.

### Local media evidence

An assert-based probe using installed **Pillow 13.0.0** encoded synthetic transparent PNG fixtures as RGB JPEGs with an embedded sRGB profile. It checked dimensions, profile round-trip, white alpha flattening, byte size below 8 MB and unchanged input bytes. Feed 1080×1350 encoded to 24,355 bytes; square 1080×1080 to 19,731 bytes. Both passed the documented feed aspect-range check. Story 1080×1920 encoded successfully but correctly failed that feed-range check.

This is conversion feasibility evidence only: the fixtures are uniform synthetic images, not real product posters. It does not establish compression readability, color fidelity on devices, a completed publishing adapter or acceptance by Meta. JPEG processing must be a separate derivative path from the confirmed PNG.

Local evidence files are git-ignored under `outputs/saas-verification-2026-11-15/`: `regressions.xml`, `summary.json`, `jpeg-probe.json` and three synthetic JPEGs.

### Provider evidence and remaining prerequisites

| Check | Result | Required next evidence |
| --- | --- | --- |
| Meta route/consent eligibility | Current setup and permissions documentation checked; additional Unified Login conditions recorded above. | App dashboard availability, configured consent, role-authorized test Page and real professional Instagram account. |
| Image counts, conversion and quotas | Documentation and local encoding evidence only; conflicting daily quota examples remain. | Numbered-image post and listing on both networks, returned limit/status values and provider-visible order/crop. |
| MVola | Official site confirms developer onboarding and sandbox; public developer portal needs its interactive/account flow. | Register a developer app, obtain sandbox credentials and contract, run success/pending/failure plus callback/status reconciliation. |
| Paddle pack capability | Official AI-business docs explicitly describe pay-as-you-go credit packs; native metering remains beta. | Sandbox account/product/price and verified payment completion; duplicate/out-of-order webhook fulfillment; separately, production seller and payout approval. |
| Paddle Madagascar seller eligibility | Indexed official policy suggests candidacy; direct policy fetch returns 404. Buyer-country coverage cannot settle seller eligibility. | Current confirmation from Paddle during business onboarding, with payout method acceptance. |
| Customer credits, OAuth/email signup, anti-abuse and multi-tenancy | Proposed features; no corresponding implementation was added. | Approved requirements/design, implementation and dedicated concurrent-wallet, signup/linking and two-workspace isolation tests. |

Paddle's current public developer guide confirms one-time credit-pack packaging; that does not establish seller acceptance. [Paddle for AI companies](https://developer.paddle.com/get-started/how-paddle-works/ai-companies/)

Do not infer SaaS readiness from the 125 passing pilot tests. In particular, the current backup tests do not prove that a future wallet/payment/publication recovery avoids duplicate credits or posts. Those invariants need their own tests once implemented. Frontend build/smokes were not rerun: this track changed no application source and the live local ports/build are shared with Claude's work. The unavailable Postman CLI was not installed merely to call unauthenticated provider endpoints; an authentication error would not validate publishing or payment behavior.

## Papi assessment added on 2026-11-15

**Recommendation:** evaluate **Papi hosted checkout** as the first local prepaid-payment integration. It could replace separate MVola/Orange/Airtel integrations and potentially the need for a second local card checkout. This updates the earlier MVola-first recommendation; it is not a provider-selection approval or merchant acceptance.

### Coverage and collection model

Papi documents MVola, Airtel Money and Orange Money, plus cards through its hosted checkout. Its direct Payment API serves mobile money only. Hosted checkout is the smaller first integration: Affiche IA creates an order and redirects to Papi, without collecting card details. The merchant API key stays on our backend. [Papi payment modes](https://docs.papi.mg/docs/developper-guide/payment-api/)

Two collection modes are documented. **Direct** requires the merchant's own operator/bank contracts; **Transit** collects through Papi before settlement and does not require a separate merchant account with each operator. The modes can be mixed per provider. Transit settlement is periodic subject to a minimum, or on request; exact schedule, threshold, payout fees, verification documents and reserves must be confirmed with Papi. It is not a promise of immediate access to funds or automatic production approval. [Collection and settlement](https://papi.mg/how-it-works/), [Application setup](https://docs.papi.mg/docs/developper-guide/application-management/)

Published rates checked on 2026-11-15:

| Collection mode/method | Published fee |
| --- | ---: |
| Direct, all listed methods | 1.20% including tax, plus separate operator/bank fees |
| Transit, MVola | 3.80% including tax |
| Transit, Orange Money / Airtel Money | 3.60% including tax |
| Transit, cards | 4.20% including tax |

Papi advertises no fixed fees; Transit collection rates include operator fees. The merchant can allocate fees between itself and the payer, so checkout must disclose the actual payer total. These rates do not establish payout charges or contract-specific terms. [Pricing](https://papi.mg/pricing/), [Fee quotation API](https://docs.papi.mg/fr/docs/api/direct-mobile-money/get-payment-fees/)

### Integration details that affect credit fulfillment

- The hosted flow creates links with `POST https://app.papi.mg/engine/api/payment-links` and shop `Token` authentication. A status read-back by merchant reference is documented. The purchase must bind the authenticated workspace, exact pack, original MGA amount and an immutable order identity on our server. [Integration guide](https://docs.papi.mg/fr/docs/developper-guide/integration-guide/)
- Authenticate raw callback bytes using `X-Papi-Signature`, then match the stored reference and notification token. Validate amount, currency and payment success before fulfilling a pack. Signature verification is necessary but does not replace order validation. [Notification security](https://docs.papi.mg/docs/developper-guide/securing-notifications/)
- Automatic notification delivery is **one attempt**; manual resend and status read-back are the documented recovery paths. Add bounded reconciliation for pending orders. Grant credits once even when both a callback and a status check report success. [Callback recovery](https://docs.papi.mg/docs/developper-guide/securing-notifications/)
- Provider link creation deduplicates an active reference. After payment, expiry or disabling, the same reference can create another link. Our order/fulfillment ledger must therefore remain the permanent boundary: do not recreate checkout for an already paid order. [Link idempotency](https://docs.papi.mg/fr/docs/developper-guide/integration-guide/)
- Read-back distinguishes link status from payment-attempt status. Use the successful attempt's provider identity and check both; a failed attempt on an active link does not necessarily end the purchase. [Payment status reference](https://docs.papi.mg/fr/docs/api/payment-link/get-payment-link-status/)

### What was actually checked

1. Official pricing, direct/transit setup, hosted-versus-direct payment flow, signature, read-back and sandbox documents were inspected.
2. The published HMAC-SHA256 test vector was reproduced with Python's standard library and matched exactly. Altering the raw body changed the signature. This verifies the documented formula, not an implemented Affiche IA webhook. Evidence: `outputs/papi-research-2026-11-15/signature-vector.json` (git-ignored). The key was the provider's public example, not a real merchant secret.
3. Papi's public demo returned HTTP 200 in local Chromium and displayed its catalogue. A demo add-to-cart request returned HTTP 200. Cart navigation automation did not complete; no checkout success, payment result or merchant callback was observed. The demo documentation identifies it as sandbox, but this does not verify our own future integration. [Public demo instructions](https://docs.papi.mg/docs/demoshop/)
4. Orbit returned an unrelated PayU result for the Papi query; it was discarded. Papi's own documentation is the source. No API key was acquired, merchant account created, callback endpoint exposed, production payment made or application code changed. No application regression rerun was necessary for this documentation addition.

### What still needs confirmation

- Merchant verification, acceptance of AI-generation credit packs, activated card brands and all transit settlement/withdrawal conditions.
- Automatic recurring debits, payment mandates and saved payment methods. The reviewed public documentation establishes one-time payments, not a recurring subscription engine. The Odoo plugin's lack of subscriptions is only a plugin limitation and cannot prove platform-wide absence.
- Refund/dispute operations, reserve handling, service reliability and support response commitments.
- A dedicated Affiche IA sandbox shop: successful/failed/pending/expired attempts, callback authentication and missed callbacks, duplicate fulfillment, checkout retries after payment, and actual card/mobile-money behavior. Our existing 125 pilot tests do not cover any of these new paths.

Prepaid packs can work with one-time checkout regardless of automatic-debit support. Monthly access can initially be a manually renewed period if that is stated clearly; it must not be advertised as automatic renewal until confirmed and implemented.
