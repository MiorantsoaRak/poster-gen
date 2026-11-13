# Affiche IA — deploy to affiches.miorantsoa.app

**State on 2026-11-13: written, never run.** Nothing is deployed. The image has not been built anywhere (the
development machine has no access to Docker), and the Caddy block below has not been validated. The first rollout
is where these files are proven; read "Not proven yet" at the end before it.

Box: Hetzner `mx1`, `89.167.56.26`, Ubuntu 26.04, 2 vCPU, 3.8 GB memory without swap, SSH user `deploy`. It
already runs Maizina, Trap Duel and PPN Market. Affiche IA is its own compose project (`affiche-ia`,
`/opt/affiche-ia`): one container with the API, the built frontend and Chromium, and one volume with the SQLite
database and the asset files. Maizina's Docker Caddy terminates HTTPS and reaches the application as
`affiche-ia:8000` over `affiche_ia_edge`, a network that Maizina's compose declares and only Caddy and the
application join. Nothing publishes a port. The pattern, and several sentences below, come from
`../ppn-market/deploy/README.md`. Design: `docs/project/designs/hosted-pilot.md` (phase B).

`deploy/phone_session.py` is something else: a temporary public address to a development machine for one
observed session. It does not touch the box.

## Prerequisites (control machine)

- pyinfra 3.x (`uv tool install pyinfra`), git, and the SSH key that reaches `deploy@89.167.56.26`.
- The release must be committed **and pushed**: the deploy refuses a `HEAD` that is not on `origin/main`.
- First deploy only, in the same shell. Use the pilot's own provider keys, made in a provider project that has
  its own budget limit; the development keys never go to the box.

  ```bash
  cd backend
  uv run python -c "from getpass import getpass; from pwdlib import PasswordHash; print(PasswordHash.recommended().hash(getpass('Shop password: ')))"
  cd ..
  export AFFICHE_SHOP_PASSWORD_HASH='<paste the hash; single quotes keep its $ signs>'
  export AFFICHE_OPENAI_API_KEY='<the pilot key>'
  export AFFICHE_ANTHROPIC_API_KEY='<the pilot key; leave unset to run without saved styles>'
  export AFFICHE_SPEND_CAP_USD='15'
  ```

  Choose a long random shop password (for example `python -c "import secrets; print(secrets.token_urlsafe(18))"`)
  and give it to the owner in person: it is the only thing between the internet and the provider budget.
  The deploy writes these once into the box's `secrets/app.env`, with today's UTC date as the day the cap counts
  from, then ignores them. Clear them afterwards (`unset AFFICHE_SHOP_PASSWORD_HASH AFFICHE_OPENAI_API_KEY
  AFFICHE_ANTHROPIC_API_KEY AFFICHE_SPEND_CAP_USD`).
- **Never add `--diff` or `--debug`** to the pyinfra command: they print uploaded file contents, which include
  the first deploy's secrets.

## First rollout (once, in this order)

1. **DNS (owner, Cloudflare):** `A` record, name `affiches`, value `89.167.56.26`, proxy status **DNS only**,
   **no AAAA** (with an AAAA record the login limit could not tell clients apart reliably).
   Check: `nslookup affiches.miorantsoa.app 1.1.1.1` returns `89.167.56.26`.
2. **Maizina change: two files, one commit (Maizina repository, Maizina's own workflow and deploy).**

   **2a. `deploy/compose.yml`**: attach Caddy to the new network.

   ```yaml
   # service caddy: add `affiche` to its networks
       networks: [default, duel, ppn, affiche]
   # top-level networks
     affiche:
       name: affiche_ia_edge          # Affiche IA's compose joins it as external
   ```

   **2b. `deploy/maizina.caddy`**: append the site block.

   ```caddy
   # Affiche IA: its own compose project on affiche_ia_edge. While it is down, the error block answers in French
   # and the other sites are unaffected. DNS: A affiches -> 89.167.56.26, DNS only (Cloudflare).
   affiches.miorantsoa.app {
   	encode zstd gzip
   	header Strict-Transport-Security "max-age=31536000"
   	reverse_proxy affiche-ia:8000
   	handle_errors 502 503 504 {
   		handle /api/* {
   			header Content-Type "application/json"
   			respond `{"error":{"code":"service_down","message_fr":"Le service est momentanément indisponible.","retryable":true}}` 503
   		}
   		handle {
   			header Content-Type "text/plain; charset=utf-8"
   			respond "Affiche Atelier est momentanément indisponible. Réessayez dans quelques minutes." 503
   		}
   	}
   }
   ```

   The box runs Caddy 2.11.4 (read on 2026-11-13), which accepts status codes on `handle_errors`. The block is
   written from the documentation's syntax as remembered and **has not been validated**: before recreating
   Caddy, run `sudo docker exec maizina-caddy-1 caddy validate --config /etc/caddy/Caddyfile` on a copy that
   holds the new block, or expect to correct it.

   As for PPN Market, a Caddyfile-only change is not picked up by Maizina's deploy; recreate Caddy after 2b (a
   few seconds of downtime for Maizina, Trap Duel and PPN Market; certificates persist):
   `sudo docker compose -f /opt/maizina/deploy/compose.yml up -d --force-recreate caddy`.

   Checks: `sudo docker network ls | grep affiche_ia_edge`; `curl -s https://affiches.miorantsoa.app/api/session`
   prints the `service_down` line with status 503 and a valid certificate (the application is not running yet);
   the three other sites still answer 200.
3. **Affiche IA deploy** (below), with the first-deploy variables set. Deploy at a quiet time, and keep
   `ssh deploy@89.167.56.26 'watch -n 5 free -m'` open in another window: the image build is the heaviest thing
   this box has been asked to do (the frontend's type check alone peaks near 480 MB), and there is no swap.
   All verification checks must pass.
4. **In the application, once:** sign in, enter the shop's name and contact, upload the logo. Make the saved
   styles again from their reference posters (about one cent each).
5. **Memory under a real render:** make one poster to the final preview while `free -m` is open. The container
   is limited to 1 GB; the renderer's tests peak at 457 MB. If the container is killed (`docker inspect -f
   '{{.State.OOMKilled}}' affiche-ia-affiche-ia-1`), stop and raise it in the design before the owner uses it.
6. **Service-down page:** `sudo docker stop affiche-ia-affiche-ia-1`, then fetch `/` and `/api/session`: the
   French line and the `service_down` envelope, both 503; the neighbours answer 200. Start it again.
7. **Forged header:** from another network, `curl -s -X POST https://affiches.miorantsoa.app/api/session -H
   "Origin: https://affiches.miorantsoa.app" -H "Content-Type: application/json" -H "X-Forwarded-For:
   203.0.113.9" -d '{"password":"wrong"}'`, then `sudo docker exec affiche-ia-affiche-ia-1 python -c "import
   sqlite3; print(sqlite3.connect('/data/affiche.db').execute('SELECT ip FROM login_failures').fetchall())"`:
   the caller's real public address, not `203.0.113.9` and not a `172.` address.
8. **Restore proof** ("Restore" below), on a development machine.
9. **The owner's phone** (docs/project/reviews/phone-session-TEMPLATE.md, with this address).

## Each release

```bash
git status                    # deploy inputs must be committed and pushed
cd deploy; pyinfra 89.167.56.26 deploy.py --user deploy -y
```

What it does: refuses uncommitted deploy inputs or a `HEAD` that is not on `origin/main` → creates secrets once →
installs `daily.sh`, `verify.sh` and the cron entry → if the running container already carries the revision,
skips to verification → otherwise checks the network and 5 GB of free disk, uploads a `git archive`, builds,
checks the configuration in the new image → **stops the old container** (it first finishes a paid generation
that is running, up to 5 minutes) → backs the data up with the new image → starts the new container, which
applies its migrations at start → prunes old images → takes a backup → runs `verify.sh`.

The service is down from the stop to the start: under a minute when no generation is running. A failed build or
configuration check changes nothing. A failed backup starts the old container again and stops the release.

**Migrations** are forward-only and run when the container starts. A release that adds one cannot be rolled
back by deploying older code; see "Rollback".

## Operate (on the box)

```bash
sudo docker compose -p affiche-ia ps                       # status
journalctl -t affiche-ia --since today                     # application log (journald, kept across releases)
journalctl -t affiche-ia-daily --since today               # nightly backup results
sudo docker restart affiche-ia-affiche-ia-1                # restart (waits for a running generation)
# Recreate on the current revision (after editing secrets, or after Maizina recreated affiche_ia_edge):
sudo env REVISION=$(sudo docker inspect -f '{{index .Config.Labels "org.opencontainers.image.revision"}}' affiche-ia-affiche-ia-1) \
  docker compose -f /opt/affiche-ia/app/deploy/compose.yml up -d --force-recreate --no-build affiche-ia
```

`https://affiches.miorantsoa.app/api/status`, after signing in, tells which commit runs, when the last backup
finished and whether it is late, the spend against the cap, and the failed jobs of the last 24 hours.
For a warning that reaches you without looking: point a free uptime check at
`https://affiches.miorantsoa.app/api/session` (it answers 200 without a session).

Logs: check once that the box's journal keeps at least 14 days (`journalctl --disk-usage`,
`/etc/systemd/journald.conf`); it is shared with the other projects, so change it only knowingly.

## Secrets (on the box, never in git)

`/opt/affiche-ia/secrets/app.env` (root, 600): `SHOP_PASSWORD_HASH`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`,
`SPEND_CAP_USD`, `SPEND_CAP_SINCE`. Every value in single quotes.

- Edit with `sudo nano /opt/affiche-ia/secrets/app.env`, then run the recreate command above.
- **New shop password** (also when a phone is lost): make a new hash as in "Prerequisites", replace the line,
  recreate. Every session on every phone ends at that restart.
- **Raising the cap:** change `SPEND_CAP_USD`, recreate. `SPEND_CAP_SINCE` must not be after today (UTC), or
  the application refuses to start.
- Do not delete `app.env`: the next deploy would ask for the first-deploy variables again.

## Backups

Cron runs `/opt/affiche-ia/daily.sh` at 00:40 UTC, and every release runs it once. Inside the running
container it copies new asset files, then one consistent copy of the database, into `/opt/affiche-ia/backups`
(`assets/`, `db/affiche-<stamp>.db`, `last-backup.json`), and keeps 14 days of database copies. A failure is in
`journalctl -t affiche-ia-daily`, leaves `last-backup.json` untouched, and shows as "late" on `/api/status`
after 48 hours.

**The backups share the box: losing the box loses them, and PPN Market's dumps with them.** Before the first
pilot day, either switch on Hetzner's backup option for `mx1`, or pull `/opt/affiche-ia/backups` to another
machine regularly. This is still to be decided.

### Restore

```bash
sudo -i
exec 9>/opt/affiche-ia/.lock; flock 9                     # keep the nightly backup out of the way
docker stop affiche-ia-affiche-ia-1                       # stop writes
ls -lt /opt/affiche-ia/backups/db                         # choose one copy
docker run --rm -u 10001:10001 -v affiche-ia_data:/data -v /opt/affiche-ia/backups:/backups:ro \
  --entrypoint sh affiche-ia:$(docker inspect -f '{{index .Config.Labels "org.opencontainers.image.revision"}}' affiche-ia-affiche-ia-1) -c '
  set -e
  mv /data/affiche.db /data/affiche.db.replaced
  rm -f /data/affiche.db-wal /data/affiche.db-shm
  cp /backups/db/<file>.db /data/affiche.db
  cp -rn /backups/assets/. /data/assets/'
docker start affiche-ia-affiche-ia-1
exec 9>&-
exit
```

Never mount `/data` read-only for any of this: a database in write-ahead mode cannot be opened on a read-only
volume. After a restore, **the ledger has lost the spend made since that backup**, and a generation that was
reserved at backup time runs again: compare `/api/status` with the provider's dashboard and lower
`SPEND_CAP_USD` by the difference. Remove `/data/affiche.db.replaced` only when you are satisfied.

**Proof before the first pilot day (development machine):** copy one `db/affiche-*.db` and `assets/` from the
box, put them in a new folder as `affiche.db` and `assets/`, start the API on it with `DATA_DIR` set to that
folder, `IMAGE_PROVIDER=openai` and **`OPENAI_API_KEY=not-a-real-key`** in the environment (the environment
wins over `backend/.env`, so this copy cannot spend), sign in, and download a confirmed poster: its SHA-256 must
equal the one shown when it was confirmed.

## Rollback

Code-only releases: `git checkout <previous commit>`, deploy, then `git checkout -` (the previous commit is on
`origin/main`, so the deploy accepts it). After a release that added a migration: fix forward, or restore the
backup that the release took just before starting.

## Landmines

- **Never add `ports:` to `deploy/compose.yml`.** The application believes forwarding headers from Docker's
  private ranges; that is safe only while nothing but Caddy can reach it. `verify.sh` fails a release that
  publishes a port.
- Never create `affiche_ia_edge` by hand (`docker network create`): it would lack Compose's labels and break
  Maizina's next deploy. If it is missing, redeploy Maizina, then run the recreate command.
- `IMAGE_PROVIDER` is recorded in the data at the first start and cannot change afterwards. It is set in
  `deploy/compose.yml`; the deploy checks it before the first start.
- One SQLite file, one writer: never start a second container on the `affiche-ia_data` volume while the
  application runs (the application's own lock would refuse it, and a backup needs no second container).
- The box has no swap. The container is limited to 1 GB so that a runaway render is killed alone instead of
  taking Maizina or PPN Market with it.
- Builder cache is shared with the other projects and is not pruned; the 5 GB precheck fails first.

## Not proven yet (2026-11-13)

- The image build, its size, and Chromium starting inside the hardened container (`verify.sh` checks the last).
- `deploy.py` itself: its Python compiles and its shell text parses, but pyinfra has not run it.
- The Caddy block.
- Memory on the box during a build and during a real render.
- The restore procedure on the box (the backup and a restore are tested on temporary data in
  `backend/tests/test_backup.py`).
