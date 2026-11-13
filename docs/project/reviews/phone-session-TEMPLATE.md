# Phone session — <date>

> Copy to `phone-session-<YYYY-MM-DD>.md` and fill in during the session (R-HOSTED-PILOT-006, D-HOSTED-PILOT-006). Write what happened, not what should have happened. Do not help the owner unless he is stuck for more than a minute; when you help, write it down.

## Before

- [ ] `cloudflared` installed; frontend built (`corepack npm@10 run build` on Linux, `npm.cmd run build` on Windows).
- [ ] Ledger read before the session (USD): ______ (budget 100 in all since 2026-11-13, of which 5.28 is outside the ledger; each poster is about 0.21).
- [ ] From `backend/`: `uv run python ../deploy/phone_session.py ../outputs/phone-session-password.txt`
- [ ] This machine will not sleep during the session.
- [ ] The address and the password were sent to the owner by: ______

## Context

| | |
|---|---|
| Owner's phone (model, Android version) | |
| Browser and version | |
| Network (operator, 3G/4G, signal) | |
| Observed by, and how (in the shop / call with shared screen) | |

## The run

| Step | Clock time | What he did, where he stopped or asked, any error shown (exact words) |
|---|---|---|
| Opens the address | | |
| Signs in | | |
| Takes or picks a photo (file size: ____ MB, upload time: ____ s) | | |
| Types name and price | | |
| Chooses a style, starts the generation | | |
| Waits (did he leave the page? did the poster come back?) | | |
| Reviews the poster | | |
| Final preview and confirmation | | |
| Downloads the file (where did it go on the phone?) | | |

**Time from the first tap to the downloaded file:** ______ **Finished without help:** yes / no

## Checks

- [ ] "Ajouter à l’écran d’accueil": offered by the browser? Icon and name right? Opens without the address bar? Still signed in there?
- [ ] Closed the browser, opened it again an hour later: still signed in?
- [ ] A generation left in the middle (screen locked or page closed) was found again.
- [ ] Forged-header check (administrator, from another network): `curl -s -X POST <address>/api/session -H "Origin: <address>" -H "Content-Type: application/json" -H "X-Forwarded-For: 203.0.113.9" -d '{"password":"wrong"}'`, then read `login_failures.ip` in the database: it must be the caller's real public address, not `203.0.113.9` and not `127.0.0.1`. Result: ______
- [ ] What he said about the result (his words): ______
- [ ] Would he post this poster? If not, why: ______

## After

- Ledger after the session (USD): ______
- The script was stopped (Ctrl-C) and the address no longer answers: yes / no

## Findings

| # | Severity (P0 could not finish / P1 slowed or confused / P2 remark) | What happened | TODO entry or decision not to act |
|---|---|---|---|
| 1 | | | |
