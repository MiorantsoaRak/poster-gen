**Ready for owner approval. All R2 findings are addressed in v3. No actionable design blockers remain.**

| R2 item | Verdict |
|---|---|
| Stale tab after a shop switch | **Closed.** A confirmed `409 shop_changed` clears dashboard data and requires explicit sign-in. Only an unreadable 409 triggers session revalidation. The release check covers the decisive case: even after a session read identifies shop B, the stale tab must show neither shop’s rows nor thumbnails. This matches the existing identity gate. [Recovery rule](docs/project/designs/shop-dashboard.md#L37) · [Release check](docs/project/designs/shop-dashboard.md#L44) · [Multi-shop contract](docs/project/designs/multi-shop.md#L533) |
| Creator fallback with deferred capabilities | **Closed.** On creator entry, the app resolves capabilities before choosing chat or steps. A pending capability read can no longer be interpreted as chat being unavailable under the design. [Navigation contract](docs/project/designs/shop-dashboard.md#L7) |
| Stalled credit-history pagination | **Closed.** The first page and « Voir plus » each have a 20-second timeout. The design explicitly tests that a stalled second page leaves the first page visible and allows retry. [History contract](docs/project/designs/shop-dashboard.md#L23) |

The earlier closures still hold, including independent Home reads, consistent credit-event dates, preservation of creator work while Credits is open, paid-action blocker precedence, account recovery, operator contact and attention-item ordering. [R2 findings](docs/project/reviews/shop-dashboard-design-r2.md) · [V3 design](docs/project/designs/shop-dashboard.md)

**Requirements alignment.** V3 covers all four approved requirements: Home actions and balance visibility, dated credit history and 30-day usage, account and access management, and phone accessibility with distinct empty and failed states. Owner approval still covers two explicit product choices: the definitions of the three 30-day figures and showing one actionable poster plus the remaining count per attention group. [Approved requirements](docs/project/requirements/shop-dashboard.md#L16) · [Approval scope](docs/project/designs/shop-dashboard.md#L46)

Static, read-only review. No edits, store-writing commands, device access or production access. Runtime isolation, phone layout and screen-reader behavior remain release checks.