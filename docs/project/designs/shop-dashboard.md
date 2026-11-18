# Shop dashboard

**Approved v3 (ADR-114), 2026-11-18.** The owner approved R-SHOP-DASH-001 through 004 for design (ADR-113). The existing Vue shop app renders three views. FastAPI reads shop-owned records from SQLite. All new operations are reads. Schema changes and migrations: none proposed.

## D-SHOP-DASH-001 — Home and navigation (R-001, R-004)

An ordinary sign-in lands on « Accueil ». Preserve intentional deep links, the editor’s unsaved-change handling, the conditions dialog, and the chat’s recovery of pending requests. Give Home its own hash, #accueil. Keep #message and existing poster, editor, library and style hashes. Give the steps composer an explicit route before repurposing an empty address. « Créer une affiche » opens chat by default, steps when saved or when chat is unavailable. Resolve capabilities on creator entry before choosing the fallback. Home navigation links to #credits and #compte even with a positive balance. Back, reload and install-launch must agree about the current view. A signed-out or replaced session discards all dashboard state.

On the home screen, show attention items first, followed by balance (available and pending), the creation button, and the latest five active posters using the library’s titles, states and thumbnails. Each poster opens through the existing shop navigation. Show the last five even when some also need attention. Reuse GET /api/creations?limit=5 and GET /api/balance. In chat and the editor, link the balance to Credits without covering a phone toolbar or trapping keyboard focus. Open Credits from a creator as a panel over its mounted view: keep drafts, uploads, photo object URLs, pending keys and polling alive. Back closes the panel and restores focus to the balance. Direct entry to #credits renders standalone. Finish or explicitly discard work before leaving the creator for another view.

GET /api/shop-dashboard returns {as_of, review, failed, usage}. Each attention group has {total, first_creation_id}, with null when empty. Count distinct active creations across the entire shop. Use the library’s pending-review predicate. For failure, use the latest image generation per active poster ordered by creation time and ID, including a failed or interrupted outcome and excluding a cancelled job. A later generation supersedes the earlier failure. Within each group choose the newest qualifying creation by created_at then ID. Cancellation of the latest generation supersedes a previous failure. Link to the affected poster and show how many others remain. For zero available credits, reuse the paid action’s blocker precedence. Surface outstanding terms or a service pause first. Credits always has purchase instructions. Multiple issues may coexist. No generation, retry or billing write follows navigation.

## D-SHOP-DASH-002 — Credits and the 30-day line (R-002, R-004)

Use the existing available, pending and purchase_fr from /api/balance. Available already excludes pending reservations. Preserve signed values after operator corrections. Show the operator’s instructions as plain text.

The summary uses one server UTC instant and the preceding 30 × 24 hours, start inclusive and end exclusive. Label it « Ces 30 derniers jours ». Approved definitions:

- « Affiches créées » counts creation rows by created_at, including duplicates and subsequently removed posters. One poster with several versions counts once.
- « Images générées » counts successful jobs in jobs.IMAGE_KINDS (including background) by finished_at, including successes before charging began. Reads, renders and failures produce no image for this count.
- « Crédits dépensés » counts successful jobs with takes_credit=1 by finished_at. This is gross consumption. A separate repayment is shown in history on its own date. The pending balance covers jobs still in flight.

GET /api/shop-credit-history?limit=20&before=… uses a shop-only projection of the same credit_grants and poster_jobs sources as credits.history. Keep the operator endpoint’s existing admission-time ordering. Return {items,next_cursor}. Allow 1–50, use the existing validated opaque cursor. Shop-facing rows expose a stable type/id, date, shop-facing category, signed grant/correction amount or job credit state, associated creation ID/title where available. Exact keys for line rows: {type,id,at,kind,origin,credits,creation_id,title,removed}; for jobs: {type,id,at,kind,credit,creation_id,title,removed}. Absent poster fields are null. Join repayment to job to creation with shop equality at every hop. Sort (at,type,id) descending. Lines use created_at, pending jobs use admission time, terminal jobs use finished_at. Use this event time for display and cursor comparisons. A settled job can move between pages: on refresh restart at page one, discard old cursors and deduplicate by type/id on append. Keep repayment as a separate line. Operator notes, actor names, payment references, other shops and provider spend stay out of this API. Reuse job credit states pending, spent and given_back. A successful job later repaid has one spend and one separate repayment line. A job which failed before producing an image shows its released reservation once. Explain zero-credit corrections as corrections. Associate links only through shop-scoped joins. An archived poster keeps its history and is labelled as removed. Use the same 20-second timeout for both initial history and pagination. Test a stalled second page leaves the first visible and retryable. Load older rows with « Voir plus », keep existing rows on retry, and reset pagination on refresh.

## D-SHOP-DASH-003 — Account (R-003, R-004)

At #compte reuse the shop profile fields and save flow (GET/PUT /api/shop-profile, revision and idempotency key, existing logo upload). Preserve the editor’s explicit apply-to-poster operation. Changing the account profile alone leaves existing posters intact. Use POST /api/session/password and the existing sign-out confirmation. GET /api/terms supplies the current version and its accepted_at. Show the acceptance date when present and « Conditions à accepter » otherwise. The conditions link lets an accepted shop read the server’s text without accepting again. Also link to /donnees.html. For help display support_fr from the existing session response, or the same French fallback used by terms when unset. Escape it as text.

## D-SHOP-DASH-004 — Load states, isolation and verification (R-001–004)

Authenticated data comes only from the live shop session. Apply the existing stale-tab guard, protected-route conventions and private cache policy. Require shop predicates on creations, jobs and ledger records, including joins for labels. Read summary fields in a consistent snapshot. No browser-persistent dashboard cache. No external provider, analytics or checkout call.

| Event | User-visible result and recovery |
|---|---|
| First load or empty shop | Loading indicators precede values. A successful empty response shows « Aucune affiche pour le moment » and the creation button. |
| A read times out, database is busy, or network fails | Render Home immediately after successful session verification. Defer creator-only profile, capabilities, saved looks and 50-item library load until entering views that need them. Start Home’s five-item list, balance and summary independently, each with a bounded 20-second timeout. Continue the existing terms check independently. The affected section offers « Réessayer ». Keep other sections usable. On refresh failure, label retained data as last loaded. Never substitute zero. |
| Navigation, shop switch or logout overtakes a request | Discard the late response using the active session and request generation. A confirmed 409 shop_changed discards both views’ shop data and the existing gate requires explicit sign-in. An unreadable 409 uses the gate’s existing session check. A later session read identifying shop B must never unlock the stale shop A tab. A 401 follows the existing sign-in path and clears shop data. |
| Simultaneous jobs or credit corrections | Refresh on return, after observed job completion and through « Actualiser ». Display last-read time so an externally completed job cannot appear freshly checked. The server remains authoritative when confirming a paid action. |
| A linked poster was removed or became unavailable | Refresh the affected section, retain history, and explain the unavailable poster. |
| Profile conflict or lost write response | Preserve typed edits on 409 and offer to reload the server profile before explicitly reapplying them. Replay the same keyed save only for an uncertain response. Never apply the profile to a poster automatically. |
| Password response is lost | Clear sensitive fields and tell the owner the outcome is uncertain. Send passwords once through a bounded direct api() call, outside retained mutations. Keep no request signature. Show 403 wrong current password, 422 short replacement or 429 wait with the server’s text. Success keeps this device signed in and ends the shop’s other sessions. |
| History cursor refused | Keep displayed lines, offer refresh from page one. An empty final page hides « Voir plus ». |

Verify counts with two shops, empty data, identical timestamps, boundary instants, a pre-credit success, refunds, a cancelled request, a removed poster, and a failure older than five recent posters. Test a charge admitted before the 30-day boundary and completed inside it, with a grant between admission and completion. Across every history page assert the exact keys and shop-specific titles, no operator notes or foreign rows; switch shops during a delayed thumbnail/list fetch. Return a confirmed shop_changed and then a session read for B. Neither shop’s rows nor thumbnails may appear before explicit sign-in. Block saved looks or stall recent posters and verify Home still renders other sections, with no duplicate library fetch. Visit Credits and Back with a photo uploading. Check both a cancelled job after a failure and a zero balance during terms/service blocks. Exercise protected reads while signed out and with a stale tab. Check the response allowlist and missing-record behavior. Test real browser navigation at 360 px in both themes, with keyboard, long French labels and the on-screen keyboard. Confirm focus returns after dialogs and resets to the new view heading on navigation. Check heading order, announced loading/errors, readable numbers, accessible names and contrast; do one screen-reader pass before release. Run existing chat, editor, admin and terms regressions.

## Approved v4 mobile amendment · 2026-11-18 (ADR-119)

R-SHOP-DASH-005 through 009 are approved requirements. The following sections amend v3. The only wire change is one nullable response field per attention group. Storage, pricing and authentication use the existing model.

### D-SHOP-DASH-005 — Leaving an edited shop profile

ShopAccount owns the draft and saved baseline. Compare its editable name, contact and logo reference against that baseline. Expose the resulting dirty flag to App. Passwords stay inside the password form. Keep the Account instance mounted until the navigation decision is settled.

| Event | Transition |
|---|---|
| Leave a clean or successfully saved profile | Follow the destination normally. Restoring the original values makes the profile clean. |
| Follow an app link, select a tab or use Back/Forward with edits | Before switching view, retain the intended destination and show one modal. Keep the initiating control for focus recovery. Intercept ordinary link activation before changing history where possible. For history traversal, reconcile the URL and visible view on either decision. |
| Continue editing or press Escape | Keep the draft, stay at Account and focus the last edited profile field, with the profile heading as fallback. |
| Choose « Abandonner » | Release the draft and follow the intended destination exactly once. Returning to Account reads the saved profile. Repeated taps must neither stack dialogs nor replay a destination. |
| A save or logo upload is in flight | Hold the attempted departure until the bounded operation settles, then reassess. A confirmed save can proceed. A failed or uncertain save preserves the draft and existing retry/conflict recovery. Discarding local edits cannot undo a write already accepted by the server. |
| Session ends or is replaced | The existing session gate takes precedence. Clear the draft, password fields, pending destination and dialog. An explicit sign-out confirmation should disclose pending shop edits before ending the session. |

Use the existing modal focus and inert-background behavior. « Continuer la modification » receives initial focus. Protect same-tab departures such as the data-page link and full-document Back with the browser’s native unload warning when supported. Browsers control that wording. Never restore a discarded form from persistent browser storage.

### D-SHOP-DASH-006 — Reading the balance

Use the same ShopCredits rendering for the standalone view and creator panel. Show signed available and pending counts from the same balance response. For pending above zero add « Les crédits en attente sont déjà déduits du solde disponible. » With available ≤ 0 add « Un crédit disponible est nécessaire pour générer une nouvelle image. Vos affiches restent accessibles. » Then display the operator’s existing purchase instructions once. Use the existing blocker priority for paused service and outstanding terms. A positive amount alone does not guarantee generation.

On initial read failure show the error and retry. After refresh failure, label the retained figures with their last successful read time and avoid presenting a current generation decision from stale figures. The server continues to decide admission.

### D-SHOP-DASH-007 — Identifying the poster in Home alerts

Extend both review and failed in the authenticated GET /api/shop-dashboard response. Example group: `{"total":2,"first_creation_id":"p1","first_creation_title":"Galaxy A15"}`. An empty group returns 0 and two nulls. Select the saved offer title from the current version already joined by attention(), on the same shop-filtered row as the selected ID. A missing or blank title becomes null. Keep the existing ordering, counts, scope and transaction. A client reading an older response treats an absent title as null. This also works when the separate recent-posters request fails.

Show the title in the action, for example « Vérifier Galaxy A15 » or « Génération échouée · Galaxy A15 ». Render it as text, allow wrapping, retain the remaining count and navigate by ID. With an unidentified title, use the existing generic action. On a settled successful summary with both counts zero, show « Aucune affiche à vérifier ». While refreshing or after failure, distinguish the previous result from a current all-clear. Place the check time after the outcome. Keep independent terms, pause and credit alerts visible and preserve one-tap access to creation. If the linked poster disappears, use the existing unavailable-poster recovery.

### D-SHOP-DASH-008 — Shared shop header

Use one home link in App’s existing header, with the accessible name « Doka Studio — Accueil » and decorative artwork. At narrow widths use the approved compact D symbol with the visible product name as ordinary interface text. Use the approved horizontal artwork only where its 220 px minimum and clear space fit alongside the controls. Follow the [Signal asset guide](../brand/doka-studio-signal/USAGE.md) for both themes. The header is shared across shop routes, including the creator and sign-in. Check those layouts as well as the three dashboard views. Keep the separately supplied shop logo in its existing profile role.

### D-SHOP-DASH-009 — Shop contact and support

Label the profile textarea « Contact de la boutique ». Associate visible help text with it: « Ces coordonnées peuvent apparaître sur vos affiches si vous choisissez de les inclure. » Label the service contact « Assistance Doka Studio » and reuse the session’s operator contact or existing fallback. Saving a profile remains a profile-only operation. French wording in this amendment is proposed for the owner’s copy reading.

### Verification for the amendment

- Exercise a changed name, contact and logo, clean/reverted values, failed save, uncertain save, delayed upload and session replacement. Test both dialog choices via touch and keyboard, Back/Forward followed by another Back, repeated taps, and the data-page link. Confirm the URL, focused element, actual view, saved profile and number of writes after each decision.
- Run credit fixtures with available/pending of 2/1, 0/0 and −2/1, plus paused service, outstanding terms and failed reads with and without prior data. Check both standalone and creator-panel rendering.
- Verify the exact attention response keys on an empty shop, a title outside the five most recent, an untitled poster, tied timestamps and a second shop. Stall the recent list, fail a refresh after an empty success and remove a linked poster before tapping.
- At 360 px in both themes check long poster and shop names, visible creation action, header controls, the home link’s accessible name, and contact help announced with the field. Include a real phone and screen reader in release verification.
