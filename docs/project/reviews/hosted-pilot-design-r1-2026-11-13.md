# Hosted pilot — design review round 1 and devil's advocate (2026-11-13)

Subject: designs/hosted-pilot.md draft v1. Two fresh subagents, read-only, nothing run. Their points about Caddy, systemd and browsers are from memory and are marked as such where it matters. Claude's decision on each point is in the last column; the changes are design v2 and ADR-065.

## Fresh reviewer — verdict: APPROVE WITH FIXES (one P1)

| # | Sev. | Finding | Decision |
|---|---|---|---|
| 1 | P1 | Seed: a saved style cannot be imported, `looks.job_id` is `NOT NULL UNIQUE REFERENCES poster_jobs(id)` (migration 0010) and a job needs a creation version; asset ownership is an `asset_access` row; profile row 1 already exists | Seed command dropped. Profile and logo are entered by hand; styles are made again from their reference posters. R-003 amended |
| 2 | P2 | Service-down body must use the application's envelope `{"error":{"code","message_fr","retryable"}}` (`api.py:81`, `frontend/src/api.ts:12`) | Fixed in v2 |
| 3 | P2 | Caddy cannot read `/etc/affiche/env`; an unset `{$APP_HOST}` changes the site block | Literal host in `/etc/caddy/Caddyfile`, `caddy validate` in the runbook |
| 4 | P2 | `ExecStart=uv run` may re-sync at start; shutdown waits for running jobs and systemd kills after 90 s | `.venv/bin/python`, `TimeoutStopSec=300`, `RestartSec=5` |
| 5 | P2 | Backup "with the current release" fails on the first deployment; writes between backup and switch are lost on restore | Stop, back up with the new code, switch, start |
| 6 | P2 | Polling `/api/session` does not prove the renderer; Chromium needs OS libraries | One-time `playwright install-deps chromium` as root; the deploy check launches Chromium |
| 7 | P2 | `SPEND_CAP_SINCE` in the future refuses to start (`config.py:51-56`) | Runbook: use the deployment day |
| 8 | P2 | Argon2 verification runs inside `BEGIN IMMEDIATE` (`posters/auth.py:63-69`): a login flood holds the write lock; IPv6 /64 rotation bypasses the limit | Verify before the transaction; key IPv6 on its /64. Built now (T-HOST-001) |
| 9 | P2 | R-003 criteria without an answer: "left in posters", "names the limit", "development copies marked", "second copy refuses"; R-001 French page covers the API only | Requirements amended (ADR-065) |
| 10 | P3 | Sliding session write is safe (threadpool) | Moot: fixed 90-day session chosen |
| 11 | P3 | Backup: single-step `Connection.backup()`, skip `*.tmp`, a restore loses spend since the backup and re-queues `reserved` jobs | Kept for phase B |
| 12 | P3 | Restart limits may need `systemctl reset-failed` | To verify on the server (phase B) |
| 13 | P3 | Install without a service worker believed true since Chrome 108; iOS standalone has its own cookie jar; `.webmanifest` type; HSTS and free DNS names | Checked in the phone session |
| — | — | Over-engineering: `TRUSTED_PROXY` setting, `try_files`, the pull age, the contrast walker over every screen | Setting dropped (always trust loopback), `try_files` dropped, pull dropped, contrast check kept small |

Checked and found correct: 12-hour sessions, the login limit and its key, uvicorn flags, cookie attributes, Origin check, `/api/usage`, the `meta` table, environment over `.env`, hashed tokens, assets written before their row, confirmed PNGs in the asset store.

## Devil's advocate — points that change a decision

| # | Their judgment | Point | Decision |
|---|---|---|---|
| 1 | CHANGE | Six requirements of server work come before the owner's first touch. Run one observed session through an HTTPS tunnel from the developer's machine first; R-002, R-004 and R-005 are premature before it | **Accepted.** It is the audit's own argument. The phone session comes first (phase A); the server (phase B) is built after it |
| 2 | CHANGE | A pull by rsync from a laptop will go stale; use the provider's daily server backup | Accepted: pull script and its status field dropped; R-004 amended. The nightly `affiche.backup` stays (it is also the pre-migration step) |
| 3 | CHANGE | Sliding session adds a write on the read path; a fixed 90 days is one constant | Accepted; R-002 amended |
| 4 | KEEP BUT NOTE | Shared password: IPv6 /64, Argon2 inside the write transaction, the password must be generated | Same as reviewer 8; runbook generates the password |
| 5 | KEEP BUT NOTE | Seed only earns its place for styles | Dropped (reviewer 1) |
| 6 | KEEP BUT NOTE | The restore proof starts a second paid-capable copy; start it with a dummy key; set a provider-side budget | Runbook (phase B) |
| 7 | KEEP BUT NOTE | A status page that must be polled does not warn anyone; a free external uptime check on `GET /api/session` does | Runbook (phase B); the status route stays small |
| 8 | KEEP | VPS + Caddy over a PaaS; add unattended upgrades and key-only SSH | Runbook (phase B) |
| 9 | KEEP | No service worker; if the whole server is down the owner gets the browser's page | R-001 reworded |
| 10 | KEEP | SQLite on one server | — |

Design v2 was not reviewed again. Phase B gets a fresh round when it is re-scoped after the phone session.
