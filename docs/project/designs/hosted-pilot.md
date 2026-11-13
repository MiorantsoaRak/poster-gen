# DESIGN — hosted-pilot

## System overview

**Status:** v3.1 (2026-11-13). Phase A built. Phase B detailed for the real box, reviewed (round 2, APPROVE WITH FIXES, fixes applied as v3.1 and not reviewed again), built as far as a machine without Docker allows; never run on the box.
**Requirements file:** [../requirements/hosted-pilot.md](../requirements/hosted-pilot.md)
**Approval record:** approved by Claude under the user's autonomy grant (ADR-064, ADR-065) after round 1 and one devil's advocate ([review](../reviews/hosted-pilot-design-r1-2026-11-13.md)) and round 2 on phase B ([review](../reviews/hosted-pilot-design-r2-2026-11-13.md), ADR-069).

**The work is in two phases, in this order** (devil's advocate, accepted):

- **Phase A — the owner's first session, before any server.** The application runs on the administrator's machine, on the existing test data and its ledger, and is reached from the owner's phone through a temporary HTTPS tunnel. Only what that session needs, or what any exposure to the internet needs, is built first: D-001, D-002, D-006.
- **Phase B — the box `mx1`.** D-003, D-004, D-005 and the container part of D-001: one more compose project beside Maizina, Trap Duel and PPN Market. Started before the phone session (ADR-068).

```
Phase A   phone ──HTTPS──▶ tunnel provider ──▶ cloudflared on the administrator's machine
                                                   └─▶ vite preview 127.0.0.1:5173 ──/api──▶ uvicorn 127.0.0.1:8000 ──▶ backend/data-probe

Phase B   phone ──HTTPS 443──▶ Maizina's Caddy container ──affiche_ia_edge──▶ affiche-ia:8000 (API + built frontend + Chromium)
                                                                          └─▶ volume /data (affiche.db + assets) ──nightly──▶ /opt/affiche-ia/backups
```

Facts read in the code on 2026-11-13 (backend/src/affiche): sessions last a fixed 12 hours (`posters/auth.py`); the login limit is 5 failures per 15 minutes per `request.client.host`, and the Argon2 check runs inside the write transaction; `python -m affiche.api` starts uvicorn on loopback with `proxy_headers=False`; the cookie is HttpOnly, SameSite=Strict, Secure on an HTTPS origin; every mutating request must carry `Origin: <APP_ORIGIN>`; errors use the envelope `{"error":{"code","message_fr","retryable"}}`; `GET /api/usage` returns spend, cap and start date; the environment overrides `backend/.env`. In the installed uvicorn, `ProxyHeadersMiddleware` reads `X-Forwarded-For` only when the peer is a trusted host and takes the right-most address that is not trusted.

**Server (user, 2026-11-13, ADR-066): the pilot goes on the Hetzner box `mx1` that already runs Maizina, Trap Duel and PPN Market. Nothing is rented.** Facts, from `ppn-market/deploy/README.md` and a read-only look at the box on 2026-11-13: Ubuntu 26.04, 2 vCPU, 3.8 GB of memory with about 1.6 GB available and **no swap**, 13 GB of disk free (66 % used); everything runs in Docker; Maizina's Caddy container holds ports 80 and 443 and its site blocks live in the Maizina repository; DNS for `miorantsoa.app` is at Cloudflare ("DNS only" records); PPN Market is deployed with one pyinfra file from the administrator's checkout and backed up by a nightly script that keeps 14 dumps **on the box only**. Phase B below is rewritten for that box. The order does not change: the phone session through the tunnel is ready today and needs no server work.

Open questions of the requirements, as first closed by ADR-064 (the server part is replaced by the paragraph above): any provider's small Linux machine with 2 vCPU and 4 GB in Europe (a web search on 2026-11-13 gave about EUR 4.5 per month for one such plan, from third-party pages only: read the provider's own page when renting); a DNS name is required; **renting the server, the DNS record, the pilot's provider keys and running the tunnel are the administrator's actions.**

---

## D-HOSTED-PILOT-001 — Access from the internet (covers R-HOSTED-PILOT-001) — phase A for the application, phase B for Caddy

**Approach:** the API never listens on anything but loopback; one front process on the same machine is the only door (the tunnel client and `vite preview` in phase A, Caddy in phase B). The API trusts forwarding headers from loopback only.

**Data model changes:** none.

**Application changes (phase A):**

- `python -m affiche.api` starts uvicorn with `proxy_headers=True, forwarded_allow_ips="127.0.0.1"`, always. No setting: a setting that is forgotten on the server would put every phone behind one address and lock the shop out after five failures. In development nothing sends the header, so nothing changes; a local process could forge it, which is accepted (it is already on the machine).
- `auth.login`: the password is verified **before** the write transaction. Today a slow login flood holds `BEGIN IMMEDIATE` during each Argon2 check and stalls autosaves and job commits. The transaction then only counts, records the failure or inserts the session. A request arriving when the address is already at 5 failures is refused without verifying the password.
- The limit's key: an IPv4 address as it is; an IPv6 address by its /64 (one phone or one host can rotate inside its /64).
- Editor: when `/api/session` cannot be reached, or answers 502, 503 or 504 at start, the page shows "Le service est momentanément indisponible. Réessayez dans quelques minutes." and a "Réessayer" button instead of the sign-in form.
- `budget_exhausted` message (`api.py`): "Le budget d’images de la boutique est atteint. Vous pouvez encore modifier et télécharger vos affiches. Pour créer de nouvelles images, contactez l’administrateur."

**Phase B:** see "D-HOSTED-PILOT-001 (container part)" below: the application sits behind Maizina's Caddy container, not behind a Caddy of its own.

**Failure modes & handling:**

| Failure | Detection | Behaviour |
|---|---|---|
| API down or restarting, front process up | 502/503/504 or no answer on `/api/session` | The French message with a retry. Open editors keep their state; autosave retries as today |
| Whole machine or tunnel down | — | The browser's own error page. Not avoidable without a service worker, which the requirements exclude; R-001 says so |
| Forged `X-Forwarded-For` from the internet | — | uvicorn takes the right-most untrusted address, which is the one the front process appended. Phase A: checked once through the tunnel with a forged header and a wrong password (`login_failures.ip` must be the phone's public address). Phase B: same check behind Caddy |
| Login flood | `login_failures` | Each address (or /64) is refused after 5 failures without an Argon2 check; other addresses cost one check each, outside any lock |
| Strangers on the owner's mobile operator share his address and fail 5 times | 429 for the owner | He waits 15 minutes; rare with a 90-day session. Accepted |

**Tests:** `tests/test_api.py`: a wrong password does not hold a write transaction during verification (the verify function is called with no transaction open); the sixth attempt is refused without calling verify; two addresses of one IPv6 /64 share the limit, two IPv4 addresses do not; the real-uvicorn test sends `X-Forwarded-For` from loopback and the failure is recorded under the forwarded address. Smoke: `/api/session` answered 503 shows the message, "Réessayer" recovers.

---

## D-HOSTED-PILOT-002 — Long session and home-screen icon (covers R-HOSTED-PILOT-002) — phase A

**Approach:** the smallest change that keeps the owner signed in for the pilot: one constant. A session lasts 90 days from sign-in (requirement amended from "30 days after the last use", ADR-065): no write is added to the path that reads the session on every request.

**Data model changes:** none. One new `meta` row, `password_fingerprint`.

**Behaviour:**

- `SESSION_SECONDS` = 90 days; the cookie's `max_age` is the same value.
- At API start, after `runtime.start`: the SHA-256 of the configured password hash is compared with `meta.password_fingerprint`. When it differs or is missing, all sessions are deleted and the row is written, in one transaction. A new password takes effect at a restart anyway, so it ends every session at that restart.
- Sign-out unchanged. Return after sign-in: the view is in the address hash (ADR-059) and the sign-in screen must leave it alone; checked in the smoke.
- Home screen: `frontend/public/manifest.webmanifest` (`name` "Affiche Atelier", `short_name` "Affiches", `lang` "fr", `display` "standalone", `start_url` "/", dark theme colours), icons of 192 and 512 px, a maskable 512 px, an `apple-touch-icon` of 180 px, `<link rel="manifest">`. A neutral mark drawn once with the bundled Noto Sans Bold; the shop's logo is shop data and is not in the repository. **No service worker.**

**Failure modes & handling:**

| Failure | Detection | Behaviour |
|---|---|---|
| Phone lost or stolen | The owner tells the administrator | New `SHOP_PASSWORD_HASH`, restart: every session ends. The exposure until then is bounded by the spend cap |
| Session ended while editing | 401 | Existing sign-in screen; the hash keeps the poster |
| The browser does not offer installation without a service worker | Seen in the phone session | "Ajouter à l’écran d’accueil" in the browser menu is expected to work with a manifest alone (not verified here). If it does not, a minimal service worker becomes a task |
| Fingerprint row cannot be written at start | Exception | Start fails, as for any other start-up database error; nothing is half done (one transaction) |

**Edge cases:** the first start after this change deletes the existing sessions once (no fingerprint yet). On iOS a home-screen application has its own cookies: one more sign-in there.

**Tests:** `tests/test_api.py`: the cookie's `Max-Age` is 90 days; a session row expires 90 days after sign-in; a restart with the same hash keeps a session, with another hash ends it. Smoke: open a poster's address without a session, sign in, land on that poster; the manifest and icons are served.

---

## D-HOSTED-PILOT-006 — The first phone session (covers R-HOSTED-PILOT-006) — phase A

**Approach:** one observed session through a temporary tunnel, on the existing test data and its ledger (`backend/data-probe`, test budget raised to USD 100 on 2026-11-13, ADR-067, about USD 89.9 left; the script caps the ledger at 94.72 because 5.28 was spent outside it). No new paid data folder is created (standing rule). The owner sees the test posters in "Mes affiches"; the administrator tells him they are tests.

**`deploy/phone_session.py <password-file>`** (run from `backend/` by the administrator, who must be present for the whole session):

1. Refuses to start unless `cloudflared` is on the PATH and `frontend/dist` exists.
2. Starts `cloudflared tunnel --url http://127.0.0.1:5173` and reads the public `https://….trycloudflare.com` address from its output (60 seconds at most, else it stops everything and says why).
3. Starts the API on loopback with the settings of `backend/.env`, overridden by: `APP_ORIGIN` = the tunnel address, a one-off random shop password written to the password file, `DATA_DIR` = `data-probe`. Starts `vite preview` with `--host 127.0.0.1` and the tunnel host allowed.
4. Prints the address. On Ctrl-C or any child's exit it stops the tunnel, the preview and the API, in that order, and reports which one ended first.

The one-off password and the address die with the process: nothing stays exposed after the session.

**Contrast (the open part of T-UI-PHONE-CHECK):** the browser smoke, at phone width, computes the contrast of the text of the screens it already visits and fails under 4.5:1 (3:1 from 24 px). Disabled controls and text over the poster are exempt.

**Record:** `docs/project/reviews/phone-session-<date>.md`, from the tracked template `docs/project/reviews/phone-session-TEMPLATE.md`: phone, browser, network; time from first tap to downloaded file; photo size and upload time; each stop or question with its screen; each error; home-screen icon added and opened full screen or not; a generation left and found again or not; the forged-header check. Each finding becomes a TODO entry or a decision not to act; a failure to finish is P0.

**Failure modes & handling:**

| Failure | Detection | Behaviour |
|---|---|---|
| Tunnel address not obtained | 60-second wait | Everything stopped, reason printed; nothing was exposed |
| Tunnel drops during the session | The phone shows the provider's or the browser's error | Restart the script: the address and the password change, the owner signs in again; drafts and running jobs are in the database |
| A stranger finds the address | — | Random address, 24-character one-off password, login limit, spend cap; the administrator is watching and can stop the script |
| The administrator's machine sleeps | — | Runbook line: keep it awake; jobs resume or are reported interrupted by the existing recovery |
| Provider budget runs out during the session | Existing refusal | The new French message; the session's record notes it |

**Tests:** the script's pure parts (address parsing from sample tunnel output, refusal without `cloudflared`) in `tests/test_phone_session.py`; the whole script cannot be proven here because it needs the tunnel program and the administrator's go to expose the application.

---

## Phase B — the box `mx1` (v3 detail, 2026-11-13; started before the phone session, ADR-068)

**Shape: one more compose project on `mx1`, copied from PPN Market's pattern** (`../ppn-market/deploy/`: `compose.yml`, `deploy.py`, `daily.sh`, `verify.sh`, `README.md`). One container, `affiche-ia`, holds the API, the built frontend and Chromium. Maizina's Caddy reaches it as `affiche-ia:8000` over a network that only the two join; nothing publishes a port.

```
/opt/affiche-ia/app/        the released tree (git archive of HEAD), compose file in app/deploy/
/opt/affiche-ia/secrets/    app.env (root, 600): password hash, provider keys, spend cap and its start date
/opt/affiche-ia/backups/    assets/, db/affiche-<stamp>.db, last-backup.json   (owned by the container's user)
/opt/affiche-ia/daily.sh, verify.sh, .lock
volume affiche-ia_data  →  /data in the container (affiche.db and assets)
```

### D-HOSTED-PILOT-001 (container part) — reaching the application through Maizina's Caddy

**Changes in the application:**

- Three settings, all with today's behaviour as default: `API_HOST` (`127.0.0.1`), `FORWARDED_ALLOW_IPS` (`127.0.0.1`), `SERVE_FRONTEND` (false; a boolean, because the renderer already knows where the build is). `python -m affiche.api` passes the first two to uvicorn. In the container: `0.0.0.0`, Docker's private ranges (`10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,fc00::/7`, as PPN Market does) and true. The settings refuse a host off loopback with the default trust list. This is safe only because the compose file publishes no port; the compose file says so in a comment.
- With `SERVE_FRONTEND` on, the application serves the built frontend itself at `/` (Starlette `StaticFiles`, `html=True`), because Maizina's Caddy cannot see this project's files. The access boundary (`AccessBoundary` in `api.py`) today refuses every path without a session; only its session test is narrowed to paths under `/api/` (the Origin check and the size limits stay on every path, and the mount comes after every route). `no-store` applies under `/api/` only; hashed files under `/assets/` are cached for a year and the rest is revalidated. A test asserts that every route the application declares is under `/api/`, so no data route can fall outside the boundary by accident; the static files hold no secret and no shop data.
- `GET /api/session` stays the public liveness answer (it reads the database).

**Changes in the Maizina repository (its own workflow; a Caddy recreate; a few seconds of downtime for Maizina, Trap Duel and PPN Market):** a network `affiche_ia_edge` declared in its compose and joined by Caddy, and this site block:

```caddy
affiches.miorantsoa.app {
	encode zstd gzip
	reverse_proxy affiche-ia:8000
	handle_errors 502 503 504 {
		@api path /api/*
		header @api Content-Type application/json
		respond @api `{"error":{"code":"service_down","message_fr":"Le service est momentanément indisponible.","retryable":true}}` 503
		respond "Affiche Atelier est momentanément indisponible. Réessayez dans quelques minutes." 503
	}
}
```

The block is written from memory of Caddy's syntax and is not validated here: `caddy validate` in the Maizina deploy is a step of the first rollout. DNS: `A affiches → 89.167.56.26`, "DNS only", no AAAA, at Cloudflare (owner). The name is a proposal.

| Failure | Detection | Behaviour |
|---|---|---|
| Container down or restarting | Caddy gets no upstream | The French line for a page, the `service_down` envelope for `/api/*` (the editor already shows its retry screen) |
| A port is published by mistake | Review of `deploy/compose.yml`; `verify.sh` checks that `docker port` is empty | The forwarded-header trust would become forgeable: `verify.sh` fails the release |
| The edge network is missing (Maizina recreated it) | Deploy precheck `docker network inspect affiche_ia_edge` | Deploy stops before building; redeploy Maizina, never create the network by hand (PPN Market's landmine) |
| Static file missing from the image | `verify.sh` fetches `/` and `/manifest.webmanifest` | Release fails verification |

### D-HOSTED-PILOT-003 — The pilot's data and spend (covers R-HOSTED-PILOT-003)

A new, empty data folder in the named volume. First deploy only, from variables in the administrator's shell, written once into `secrets/app.env` and then ignored (PPN Market's mechanism): `AFFICHE_SHOP_PASSWORD_HASH` (must start with `$argon2`), `AFFICHE_OPENAI_API_KEY`, `AFFICHE_ANTHROPIC_API_KEY` (may be empty: the planner is then disabled and saved styles cannot be made), `AFFICHE_SPEND_CAP_USD` (default 15). `SPEND_CAP_SINCE` is the day of that first deploy. The keys are the pilot's own, in a provider project with its own budget limit. No seed command: profile and logo are entered once in the application; a saved style is made again from its reference poster. The development copies are test data and never receive the pilot's keys.

| Failure | Detection | Behaviour |
|---|---|---|
| A first-deploy variable is missing or malformed | `deploy.py` before anything is sent | Stops, names the variable |
| Cap reached | Existing admission check | Existing refusal with the owner-facing message; nothing else stops |
| `app.env` deleted | — | The next deploy would ask for the first-deploy variables again; the data volume is untouched. Runbook: never delete it |

### D-HOSTED-PILOT-004 — Backups (covers R-HOSTED-PILOT-004)

`python -m affiche.backup <folder>`: (1) copy asset files that the folder does not have yet (skip `*.tmp`; never delete or overwrite); (2) one `sqlite3.Connection.backup()` of `affiche.db` to `db/affiche-<UTC stamp>.db.partial`, `PRAGMA integrity_check` on the copy, rename; (3) delete database copies older than 14 days, always keeping the newest; (4) write `last-backup.json` (`finished_at`, `db_file`, `db_bytes`, `asset_files`) by write-then-rename. It needs neither the process lock nor `runtime.start`, and runs while the API serves. Assets go first so that every asset a database copy names is in the backup. Any failure: exit 1 with the reason, `last-backup.json` untouched.

`daily.sh` (cron, 00:40 UTC, ten minutes after PPN Market's): under the project's lock, `docker exec affiche-ia-affiche-ia-1 python -m affiche.backup /backups`, result to `logger -t affiche-ia`. `/opt/affiche-ia/backups` is mounted at `/backups` and owned by the container's user.

**Off the box (open, the user's choice):** these backups and PPN Market's dumps live on `mx1` only. R-004 asks for Hetzner's backup option on `mx1`, or a regular pull, before the first pilot day.

**Restore (runbook):** stop the container; in a one-off container on the same volume, copy one `db/affiche-*.db` to `/data/affiche.db`, remove `affiche.db-wal` and `affiche.db-shm`, copy `assets/` back; start. After a restore the ledger misses the spend made since that backup, and jobs still `reserved` run again: compare with the provider's dashboard. The proof before the first pilot day is run on a development machine with a dummy provider key in the environment.

| Failure | Detection | Behaviour |
|---|---|---|
| Disk full, copy error | Exception | Exit 1; partial file removed at the next run; earlier backups untouched |
| Integrity check fails | Result other than `ok` | Exit 1; the `.partial` file is kept for inspection and never counted |
| Cron did not run, or the container was down at 00:40 | Age of `last-backup.json` | `GET /api/status` flags it over 48 hours; `verify.sh` requires one younger than 26 hours at each release |

### D-HOSTED-PILOT-005 — Deploy, roll back, status (covers R-HOSTED-PILOT-005)

**Image** (`Dockerfile` at the repository root): a Node stage builds the frontend (`npm ci`, `npm run build`); the final stage, `python:3.12-slim-bookworm`, installs the backend with `uv sync --frozen --no-dev` **in place** (`/app/backend`, not as a wheel: `BACKEND_DIR` locates `alembic.ini`, the migrations and `../frontend/dist` from the source tree), then `playwright install --with-deps chromium` into `/ms-playwright`, and copies the built frontend to `/app/frontend/dist`. User 10001, `HOME=/tmp`. Expected size about 2 GB (750 MB of Python packages and up to 680 MB of browser files measured locally); `rembg` stays in, because removing it means changing the lock file for a path the pilot does not use.

**Compose** (`deploy/compose.yml`, project `affiche-ia`): `mem_limit: 1g` (the renderer's tests peak at 457 MB for the whole process tree; 1.6 GB is available on a box without swap; Playwright puts Chromium's shared memory and profile in `/tmp`, a tmpfs counted in that limit; one browser at a time, and at most two password verifications at a time), `init: true`, `stop_grace_period: 5m` (shutdown waits for a running paid job), `read_only` with a `/tmp` tmpfs, no capabilities, `no-new-privileges`, healthcheck on `/api/session`, the journald log driver (logs survive a release), the full non-secret environment written in the file (`IMAGE_PROVIDER=openai`, `DATA_DIR=/data`: the defaults are traps on a server), the `affiche_ia_edge` network as external, the `data` volume, the backups bind mount, `REVISION` as build argument, label and environment variable.

**`deploy/deploy.py`** (pyinfra, adapted from PPN Market's): refuse uncommitted deploy inputs or a `HEAD` that is not on `origin/main` → first-deploy secrets → `daily.sh`, `verify.sh`, cron → skip if the running container carries the revision → prechecks (edge network, 5 GB free) → upload `git archive` → build → configuration check in the new image (`load_settings` and `auth.validate_config`) → **stop the old container, back up with the new image (skipped when there is no database yet; on failure the old container is started again and the release stops), start the new container and wait for it to be healthy** (migrations run at start, through `affiche.db.migrate`, as everywhere) → `daily.sh` once → prune old images → `verify.sh`: same container and restart count over 10 s, revision label, no published port, `/api/session` in the container, one Chromium launch in the container, Maizina, PPN Market and Trap Duel still answering, the public address and its static files, HTTP→HTTPS, cron, a backup younger than 26 h.

**Rollback:** code-only releases, by deploying the previous commit (PPN Market's way). After a release with a migration: fix forward, or restore the backup taken at that release.

**Status:** `GET /api/status` behind the shop session: `commit` (the `REVISION` environment variable, else "dev"), `migration`, `started_at`, `backup` (`finished_at`, `age_hours`, `late` over 48 h; null without `BACKUP_DIR` or when the file is missing or unreadable), `spend` (as `/api/usage`), `failed_jobs_24h`. It reads one file and two counts.

| Failure | Detection | Behaviour |
|---|---|---|
| Build or configuration check fails | Exit code | Nothing running is touched |
| New container does not become healthy (bad setting, failed migration, lock) | `verify.sh` | Release fails with the container's last log lines and the rollback text. Downtime lasts until the administrator redeploys the previous commit; if a migration was applied, the restore procedure applies with the backup taken minutes before |
| Out of memory during a render | Container killed at 1 GB, restarted by Docker | The render job is reported interrupted by the existing recovery; the other projects are not affected. First real render: watch `free -m` |
| Build starves the box (2 vCPU) | — | Deploy at a quiet time (PPN Market's rule); the image build is the heaviest step |
| Chromium cannot start in the hardened container | `verify.sh` launch | Release fails verification before the owner meets it. **Not provable on the development machine today: Docker is not accessible to Claude there** |

**Tests:** `tests/test_api.py` (settings reach uvicorn; static files served without a session while `/api/*` stays closed; every declared route is under `/api/`; `/api/status` with and without a backup file, late flag, 401 without a session); `tests/test_backup.py` (consistent copy while a write transaction is open, restore serves the same bytes, 14-day pruning keeps the newest, second run copies nothing, failure leaves `last-backup.json` and exits 1); `docker compose config`, `sh -n`, `py_compile` on the deploy files. The image build and the scripts are proven only with Docker access and on the box.

---

## Traceability

| Requirement | Design | Phase |
|---|---|---|
| R-HOSTED-PILOT-001 | D-001 | A (application), B (Caddy) |
| R-HOSTED-PILOT-002 | D-002 | A |
| R-HOSTED-PILOT-003 | D-003; D-001 for the budget message | B; A |
| R-HOSTED-PILOT-004 | D-004 | B |
| R-HOSTED-PILOT-005 | D-005 | B |
| R-HOSTED-PILOT-006 | D-006 | A |

## Not built, on purpose

A seed command, a pull of backups to the administrator's machine, a sliding session, a Caddy and systemd of its own, CI deployment, alerts by message, a service worker, one account per person, a global login limit. Reasons are in the review file and in ADR-065.
