# REQUIREMENTS — hosted-pilot

**Status:** Approved on 2026-11-13 with the seven working defaults, by Claude under the user's autonomy grant ("if you have autonomy, you don't have to ask me for approval"; ADR-064). Written after the user's "go ahead" on Claude's end-user audit (ADR-063). The design has its own gate. **Amended the same day after the design review (ADR-065):** the phone session (R-006) comes first, through a temporary tunnel; 90-day session; no "posters left" figure here; profile and logo re-entered by hand; the copy outside the server is the provider's backup.

**Why now:** the application has only run on the developer's machines. The shop owner has never made a poster on his own phone. PROJECT.md says "access, deployment and backup decisions precede a hosted pilot" and leaves hosting "Not selected". This is a seventh feature beside the six of the approved split; PROJECT.md gets its row when this file is approved.

**Words used here:** the *owner* is the person at Original Phone Mada who makes posters. The *administrator* is the developer who deploys and watches the service.

Background, from the project documents (the code was not read for this draft): the API binds loopback and ignores forwarded headers; HTTPS and a trusted proxy policy are "deployment work" (AGENTS.md). Access is one shared shop password with sessions. The paid data now exists on two development machines, each with its own copy of the ledger.

| ID | Title | Priority | Status |
|---|---|---|---|
| R-HOSTED-PILOT-001 | Reach the application from the shop's phones | P0 | Approved |
| R-HOSTED-PILOT-002 | Stay signed in and open it from the home screen | P1 | Approved |
| R-HOSTED-PILOT-003 | One place for the shop's data and its spend | P0 | Approved |
| R-HOSTED-PILOT-004 | Backups that have been restored once | P0 | Approved |
| R-HOSTED-PILOT-005 | Deploy, update and see failures | P1 | Approved |
| R-HOSTED-PILOT-006 | The owner makes a poster on his own phone | P0 | Approved |

---

## R-HOSTED-PILOT-001 — Reach the application from the shop's phones

As the owner, I open one address on my phone, on mobile data, and I get the application.

Acceptance criteria:

- [ ] GIVEN a phone on mobile data WHEN the owner opens the service's address THEN the sign-in page loads over HTTPS with a valid certificate. Plain HTTP redirects to HTTPS.
- [ ] Without a shop session, only the sign-in page and its own files answer. Every data route, image and download is refused.
- [ ] The API process is not reachable from the internet except through the one front server. Forwarded headers are trusted from that server only, and the Origin check uses the public address.
- [ ] Provider keys, the password hash and the session secret are on the server only, in its environment or a secret store. None is in the repository or in the files sent to the browser.
- [ ] Repeated wrong passwords from the internet are slowed down or refused, and the limit counts the real client address, not the front server's.
- [ ] Error case: WHEN the application's own process is down or restarting THEN the phone shows a French message that says so, with a retry, not a blank screen. (When the whole machine is unreachable the browser's own page appears: accepted, because offline pages are out of scope.)
- [ ] Error case: WHEN the connection drops during a generation THEN the job continues on the server and the poster is there when the owner comes back (already promised by R-GENERATION-JOBS; to be proven on mobile data).

Out of scope: a public sign-up, several shops, a native application, offline use.

## R-HOSTED-PILOT-002 — Stay signed in and open it from the home screen

As the owner, I tap an icon on my phone and I am in the application, without typing the password each day.

Acceptance criteria:

- [ ] A phone that signed in stays signed in for 90 days. "Se déconnecter" ends the session on that phone at once.
- [ ] Changing the shop password ends every session on every phone.
- [ ] The application can be added to the phone's home screen with its own name and icon, and then opens without the browser's address bar.
- [ ] Error case: WHEN the session has ended THEN the owner is sent to the sign-in page and, after signing in, comes back to the poster he was on. Unsaved edits follow the existing autosave rules.

Out of scope: one account per staff member, a password reset by e-mail or SMS, working without a connection.

## R-HOSTED-PILOT-003 — One place for the shop's data and its spend

As the administrator, I know that every paid call of the pilot is counted in one ledger, and the owner cannot spend more than the agreed amount.

Acceptance criteria:

- [ ] The hosted service is the only place where the pilot's paid calls are made. Its ledger is the reference; the development copies are marked as test data and their caps do not add to it.
- [ ] The pilot has its own spend cap, agreed before the first day. WHEN it is reached THEN generation is refused before any provider call, with a French message that says the shop's budget is reached and who can raise it; editing, reopening and downloading keep working.
- [ ] The pilot starts without the test posters, whose photos and prices are not the shop's. The shop's profile and logo are entered once in the application; a saved style is made again from its reference poster.
- [ ] Error case: WHEN a second process starts on the same data folder THEN it refuses to start (the existing lock). The pilot's provider keys exist only on the server, in a provider project with its own budget limit, so no other copy of the data can spend the pilot's money.

Out of scope: billing, subscriptions, a cap per staff member, a "posters left" figure for the owner (later requirement on the owner's vocabulary).

## R-HOSTED-PILOT-004 — Backups that have been restored once

As the administrator, I can bring the shop's posters back after a lost disk or a bad update.

Acceptance criteria:

- [ ] Every day the database and its image files are saved together, as one consistent set (the database through the SQLite backup call, because it is in write-ahead mode).
- [ ] Backups are kept 14 days on the server, and a copy exists outside the server's disk (the hosting provider's daily backup).
- [ ] A backup is taken before every migration.
- [ ] Before the first pilot day, one backup is restored on another machine and a confirmed poster downloads from it with the same bytes.
- [ ] Error case: WHEN a backup fails or is older than 48 hours THEN the administrator can see it without opening the server (see R-HOSTED-PILOT-005).

Out of scope: restoring one poster alone, encryption choices and storage provider (design).

## R-HOSTED-PILOT-005 — Deploy, update and see failures

As the administrator, I put a new version in service with one documented command, and I learn about failures before the owner tells me.

Acceptance criteria:

- [ ] The administrator deploys from his own checkout, with one documented command, a commit that is on `origin/main`. Migrations run at start through `affiche.db.migrate` only.
- [ ] The previous version can be put back with one documented command while no migration separates the two.
- [ ] One protected address tells whether the service is up, which commit runs, the age of the last backup, the spend against the cap and the number of failed jobs of the last 24 hours.
- [ ] Logs are kept 14 days and contain no password, key, session value or photo.
- [ ] Error case: WHEN the service does not start after a deployment (bad configuration, failed migration, lock held) THEN the command fails with the reason and the previous version keeps serving, or the downtime page of R-HOSTED-PILOT-001 is shown.

Out of scope: automatic deployment on push, alerts by e-mail or message, several servers.

## R-HOSTED-PILOT-006 — The owner makes a poster on his own phone

As the owner, I go from a photo taken in the shop to a poster file on my phone, without help.

Acceptance criteria:

- [ ] The first session happens before the server is rented, through a temporary HTTPS address to the administrator's machine, on the test data and its remaining budget.
- [ ] On the agreed phones and browsers, on mobile data, the owner takes or picks a photo, types name and price, generates, reviews, confirms and downloads one poster, with nobody touching his phone.
- [ ] The session is observed. The record gives: the time from the first tap to the downloaded file, each point where he stopped or asked, each error shown, and the size of the photo upload.
- [ ] No text of the owner's path is under a 4.5:1 contrast ratio, measured with a tool (the open part of T-UI-PHONE-CHECK).
- [ ] The findings are written to `docs/project/reviews/` and each becomes a TODO entry or a recorded decision not to act.
- [ ] Error case: WHEN the owner cannot finish THEN the point of failure is recorded as a P0 finding and the pilot does not go on until it is fixed or explained.

Out of scope: thresholds for the whole pilot (PROJECT.md: agreed from an observed baseline; this session is the first observation), square and story formats (T-POSTER-009), sharing to Facebook or WhatsApp (a later requirement).

---

## Open questions, closed with their working defaults (ADR-064; the user can change any of them)

1. **Where does it run, and who pays?** Answered by the user on 2026-11-13: on the Hetzner VPS he already rents, beside `ppn-market` (ADR-066). Earlier default: one small rented Linux server in the administrator's name, sized for the Chromium renderer; provider and price are chosen in the design from checked prices.
2. **Which address?** Default: a sub-domain of a domain the administrator already owns. If he owns none, the design proposes the cheapest stable option.
3. **Pilot spend cap.** The development budget is test money; the user raised it from USD 12 to USD 100 on 2026-11-13 (ADR-067), which leaves about USD 89.9. Default: a separate pilot cap of USD 15 for the first month (about 70 scenes at the measured USD 0.21), to be changed by the administrator only.
4. **Which phones and browsers?** Default: the owner's own Android phone with Chrome. An iPhone is checked only if somebody at the shop uses one.
5. **How many people sign in?** (Session length amended to a fixed 90 days, ADR-065.) Default: the one shared shop password, on the owner's phone and at most two more.
6. **Start empty?** Yes. The profile and the logo are entered by hand, styles are made again (amended, ADR-065).
7. **Who observes the first session?** Default: the administrator, in the shop or on a call with the screen shared.
