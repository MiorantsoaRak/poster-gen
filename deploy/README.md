# Affiche IA — deploy to affiches.miorantsoa.app

**State on 2026-11-13: deployed.** `https://affiches.miorantsoa.app` runs revision `7f4fa6d` since 15:24 UTC:
container healthy, no restart, no published port, 222 MiB of its 1 GiB at rest, image 2.26 GB, first backup
taken, Chromium starts in the container, the three neighbours answer 200, and the administrator signed in from
a browser. What is still open is under "Not proven yet" at the end.

Box: Hetzner `mx1`, `89.167.56.26`, Ubuntu 26.04, 2 vCPU, 3.8 GB memory without swap, SSH user `deploy`. It
already runs Maizina, Trap Duel and PPN Market. Affiche IA is its own compose project (`affiche-ia`,
`/opt/affiche-ia`): one container with the API, the built frontend and Chromium, and one volume with the SQLite
database and the asset files. Maizina's Docker Caddy terminates HTTPS and reaches the application as
`affiche-ia:8000` over `affiche_ia_edge`, a network that Maizina's compose declares and only Caddy and the
application join. Nothing publishes a port. The pattern, and several sentences below, come from
`../ppn-market/deploy/README.md`. Design: `docs/project/designs/hosted-pilot.md` (phase B).

`deploy/phone_session.py` is something else: a temporary public address to a development machine for one
observed session. It does not touch the box. Since migration 0014 its shop in `backend/data-probe` has no credit.
When the session has started (it migrates the folder at its start), and before you give the address, grant credits
in a second terminal, from `backend/`:
`DATA_DIR=data-probe uv run python -m affiche.shops grant originalphone 20 --offered --ref phone-session-<date> --note "Session observée"`.
If it says that the database is at an older version, the session has not started yet: wait, then run it again. Its
headroom line reads the cap of `backend/.env`, not the lower cap of the session (94.72).

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
  from, then ignores them. At its first start the application copies the hash into shop 1 (`originalphone`) as
  its password ("The first start after migration 0013"). Clear them afterwards (`unset AFFICHE_SHOP_PASSWORD_HASH AFFICHE_OPENAI_API_KEY
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

   **Validated on 2026-11-13:** the whole file (Maizina, Trap Duel, PPN Market and this block) answers "Valid
   configuration" to `caddy validate` in a throwaway `caddy:2` container on the box (2.11.4, the version that
   runs there; no network, no image pull). What the error block actually answers is checked in step 6.

   **Both changes are committed in the Maizina repository on the Linux machine** (`../maizina`, branch
   `master`: T-086 and ADR-051 there) and pushed on 2026-11-13. They are not deployed. The remote's `master` had neither the `ppn` network nor the `buy.miorantsoa.app` block, although
   both run on the box (edited there, never committed): **a deploy from the old `master` would have taken PPN
   Market offline.** The commit makes the repository equal to the box, then adds Affiche IA.

   Because the list of Caddy's networks changes, Maizina's `docker compose up -d` recreates Caddy by itself
   (a few seconds of downtime for the four sites); the manual recreate below is only needed after a change of
   the Caddy file alone.

   As for PPN Market, a Caddyfile-only change is not picked up by Maizina's deploy; recreate Caddy after 2b (a
   few seconds of downtime for Maizina, Trap Duel and PPN Market; certificates persist):
   `sudo docker compose -f /opt/maizina/deploy/compose.yml up -d --force-recreate caddy`.

   Checks: `sudo docker network ls | grep affiche_ia_edge`; `curl -s https://affiches.miorantsoa.app/api/session`
   prints the `service_down` line with status 503 and a valid certificate (the application is not running yet);
   the three other sites still answer 200.
3. **Affiche IA deploy** (below), with the first-deploy variables set. Deploy at a quiet time, and keep
   `ssh -t deploy@89.167.56.26 'TERM=xterm watch -n 5 free -m'` open in another window (`-t` gives `watch` a terminal; without it: "cannot initialize terminal type"): the image build is the heaviest thing
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
   203.0.113.9" -H "X-Affiche-Bundle: 3" -d '{"identifier":"originalphone","password":"wrong"}'`, then `sudo docker exec affiche-ia-affiche-ia-1 python -c "import
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
installs `daily.sh`, `verify.sh`, `restore.sh` and the cron entry → if the running container already carries the revision,
skips to verification → otherwise checks the network and 5 GB of free disk, uploads a `git archive` and
`deploy/release.sh` (both from `HEAD`), and runs `release.sh` under the lock that `daily.sh` also takes: it
builds, checks the configuration in the new image, **rehearses the pending migrations** in the new image →
**stops the old container** (it first finishes a paid generation that is running, up to 5 minutes) → backs the
data up with the new image → starts the new container, which applies its migrations at start → prunes old
images → takes a backup → runs `verify.sh`.

The service is down from the stop to the start: under a minute when no generation is running. The worst case is
bounded: the stop waits 5 minutes at most for a running generation, the check and backup 15 minutes
(`BACKUP_DEADLINE`, 900 s), then the new container has 3 minutes to become healthy, or, after a failed backup, the
old container 2 minutes to start again (`START_DEADLINE`): about 23 minutes in all. These deadlines end the
docker command; if the backup container itself then cannot be removed, the release says so and the service stays
down until you remove it. A failed build, configuration
check or rehearsal changes nothing. A failed backup starts the old container again and stops the release ("When
the backup before the release fails").

**Migrations** are forward-only and run when the container starts. A release that adds one cannot be rolled
back by deploying older code; see "Rollback".

### The rehearsal: the gate before the stop

Before it stops the old container, `release.sh` makes a fresh copy of the live database and runs the pending
migrations on the copy, in the new image and with its SQLite (`python -m affiche.rehearse /data/affiche.db`). The
live database is only read. The rehearsal compares, before and after, the row count and a content hash of each
table, and the sums of the three spend ledgers. It runs at every release. A release without a migration has
nothing to rehearse and passes.

The report is kept on the box in `/opt/affiche-ia/last-rehearsal.txt`. pyinfra shows the report only when the
release stops. To read it after a release that passed:
`ssh deploy@89.167.56.26 sudo cat /opt/affiche-ia/last-rehearsal.txt`. Its first line gives the SQLite version,
the Python version and the revision of the image that ran it.

**When the rehearsal stops the release**, pyinfra prints the report, then `Rehearsal FAILED: nothing was changed,
the service still runs.`, and fails. The old container still serves. There is nothing to undo.
1. Read the `REHEARSAL FAILED:` line. It names each table, ledger or check that differs.
2. Do not release again. Copy the last backup (`/opt/affiche-ia/backups/db/`) to the development machine.
3. From `backend/`, run `uv run python -m affiche.rehearse <copy>` and fix the migration forward in a new commit.
4. Release again.

### When the backup before the release fails

After the stop, one container checks for the database and backs it up. Any failure there stops the release before
the new container starts, so nothing is migrated without a backup. A failure of docker itself also stops it: it
never passes for a first deploy. pyinfra prints the error (for example `backup FAILED: OSError: [Errno 28] No
space left on device`, or a line of docker), then:

```
Backup before the release FAILED (exit 1). Nothing was changed: the new version was not started.
The previous container is started again.
```

The old version serves again after its start (a few seconds). Then:
1. Check that it runs: `sudo docker compose -p affiche-ia ps`.
2. Read the error above. Check the free disk (`df -h /opt/affiche-ia/backups`) and that `/opt/affiche-ia/backups`
   belongs to the user 10001.
3. Correct the cause, then release again with the same command.

If the backup gave no answer within 900 s, the release first prints `Backup before the release FAILED: no answer
within 900 s (timeout).` After any failed backup the release removes the backup container (`affiche-ia-backup`)
before it starts the old one. If it cannot, it prints `THE SERVICE IS DOWN: the backup container affiche-ia-backup
could not be removed.` and starts nothing: run `sudo docker rm -f affiche-ia-backup`, then
`sudo docker start affiche-ia-affiche-ia-1`.

If the release prints `THE SERVICE IS DOWN: the previous container did not start again`, start it at once with
`sudo docker start affiche-ia-affiche-ia-1`, then do steps 1 to 3.

### Release 1 (migrations 0013 to 0016: several shops, credits, the operator dashboard)

The first release with migrations 0013, 0014, 0015 and 0016 (designs: `docs/project/designs/multi-shop.md` and
`prepaid-balance.md`, "Release gate"; 0015 only adds the two triggers that stop a shop's row being replaced; 0016
only adds the empty table of the operator's sessions, `admin-dashboard.md`). Do also the credit steps and the
dashboard steps of the next two sections. In this order:
1. On mx1, run `sudo sh /opt/affiche-ia/daily.sh`. Check that `/opt/affiche-ia/backups/last-backup.json` has
   today's time.
2. Optional, the day before: copy that backup's `db/affiche-<stamp>.db` to the development machine. From
   `backend/`, run `uv run python -m affiche.rehearse <copy>`. It shows the counts early, with the development SQLite.
3. Run the release command as usual. Its rehearsal runs 0013 to 0016 on a fresh copy of the live database, in
   the release image, before anything is stopped.
4. Read the report. Its first line must show SQLite 3.40.1 (the image's Debian) and the release's revision.
5. Check the report: each table that existed before has the same rows and hash before and after (a table the
   migrations add shows `None` before; a line that ends with `(over …)` compares only the columns it names); the
   version goes from `0012` to `0016`; each `0013 ADDED`, `0014 ADDED`, `0015 ADDED` and `0016 ADDED` line says
   `as expected` (0015 checks the shop's triggers in place of 0013, so 0013 has no line for them); each of the fourteen
   `guard …` lines says `as expected`; `integrity_check` is `ok`; `foreign_key_check` is 0.
6. Check that the three ledger sums are the same before and after. Save the whole report as
   `docs/project/reviews/release-1-rehearsal-<date>.md`.
7. If the report says `FAILED`, the release stopped before the stop and the old version still serves.
8. After the release, sign in on the pilot's phone with the identifier `originalphone` and the current password.
   « Mes affiches » shows the same number of posters as before.
9. Remove the `SHOP_PASSWORD_HASH` line from `/opt/affiche-ia/secrets/app.env`, then run the recreate command
   ("Operate").

### Release 1: the pilot's credits (migration 0014)

Release 1 also adds credits ("Credits" under "Shops"). Migration 0014 grants nothing: after it, every shop has 0
credits. The new container serves as soon as it starts, so the pilot has no credit for a minute or two, until you
grant his opening balance. In that time he can still edit, open « Mes affiches », preview and download; a new image
is refused before anything is sent, and costs nothing. Around the steps above:
1. **Before the release**, warn the pilot in French, for example: « Ce soir vers <heure>, Doka Studio est mis à
   jour. Pendant une ou deux minutes après la mise à jour, l’application peut dire qu’il ne reste plus de crédit :
   rien n’est envoyé ni perdu. Attendez mon message « C’est prêt » avant de créer une affiche. »
2. Run the release (step 3 above).
3. **As soon as it ends**, grant the pilot's opening balance (the owner's decision of 2026-11-16: 30 offered
   credits):

   ```bash
   sudo docker exec -it affiche-ia-affiche-ia-1 python -m affiche.shops grant originalphone 30 --offered --ref pilot-opening --note "Solde d’ouverture du pilote"
   ```

   It prints `granted 30 offered credits to originalphone (line 1): available 30, en attente 0`, then the cap's
   headroom. Read the headroom line: if a `WARNING` line follows it, raise `SPEND_CAP_USD` ("Secrets"). If you type
   the command twice, the second is refused by its reference: nothing doubles.
4. Set the purchase text: `sudo docker exec -it affiche-ia-affiche-ia-1 python -m affiche.shops purchase-text "…"`.
   It states the packs, the mobile money number, the reference to write, and when the credits arrive.
5. Tell the pilot « C’est prêt ».

### Release 1: the operator dashboard (migration 0016)

Release 1 also adds the operator dashboard ("Operator dashboard"). No password exists for it until you set one, so
the first deploy takes four steps:
1. Run this one release with `OPERATOR_BOOTSTRAP=1` in front of the pyinfra command. Its `verify.sh` run checks
   that `/api/admin/shops` answers 401 without a session (this proves that nobody enters, not that a route exists),
   and only warns: "no operator password yet". Without that variable, a release fails while no password is set.
2. Set the password in the running container, and keep it in your password manager:
   `sudo docker exec -it affiche-ia-affiche-ia-1 python -m affiche.shops operator-password`.
3. The readiness check, by hand: `sudo sh /opt/affiche-ia/verify.sh <revision>`. It must find the password set.
   Never set `OPERATOR_BOOTSTRAP` again: from now on every release fails while the password is unset.
4. Sign in at `https://affiches.miorantsoa.app/admin/` from your phone.

The pilot's opening grant stays the command line's (step 3 of the previous section). Then check that the dashboard
shows 30 credits available for `originalphone`.

### The first start after migration 0013

Since 0013, each shop has its own password in the database. `SHOP_PASSWORD_HASH` is read at one start only:
- At the first start after 0013, the application copies it into shop 1 (`originalphone`). If it is the hash that
  the old version saw last, the sessions stay and the pilot's phone stays signed in. If it changed, every session
  ends.
- At each later start, the application ignores it and logs "SHOP_PASSWORD_HASH is no longer read". Remove it
  (step 9 above). Change a password with `set-password` ("Shops").

**If the new container does not start after the migration** (the release prints "THE SERVICE IS DOWN" and the
container's last lines): a failure inside the migrations leaves the database at 0012, because 0013 to 0016 run in
one transaction; the previous commit can then be deployed again ("Rollback"). A failure after the migrations, as
below, leaves it at 0016: fix forward.
- The log says "Shop 1 has data but no password and SHOP_PASSWORD_HASH is not set". Give shop 1 a password with
  the new image, through the operator service (no container log: "Shops"), then start it:

  ```bash
  REV="$(sudo docker inspect -f '{{index .Config.Labels "org.opencontainers.image.revision"}}' affiche-ia-affiche-ia-1)"
  sudo env REVISION="$REV" docker compose -f /opt/affiche-ia/app/deploy/compose.yml run --rm operator python -m affiche.shops set-password originalphone
  sudo env REVISION="$REV" docker compose -f /opt/affiche-ia/app/deploy/compose.yml up -d --force-recreate --no-build affiche-ia
  ```

  Give the printed password to the owner in person. Another way: put the pilot's hash back in `app.env` as
  `SHOP_PASSWORD_HASH`, then run the last command only.
- Any other error: fix it in a new commit and release again, or restore the backup that the release took just
  before the start ("Restore").

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

`/api/status` answers the operator only: a caller on the loopback address that also names a loopback host,
that is, a process inside the container. Through the public address it answers 404 to everyone, signed in or
not. It tells which commit runs, when the last backup finished and whether it is late, the service's spend
against the cap, and the failed jobs of the last 24 hours:

```bash
sudo docker exec affiche-ia-affiche-ia-1 python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/api/status').read().decode())"
```

For a warning that reaches you without looking: point a free uptime check at
`https://affiches.miorantsoa.app/api/session` (it answers 200 without a session).

Logs: check once that the box's journal keeps at least 14 days (`journalctl --disk-usage`,
`/etc/systemd/journald.conf`); it is shared with the other projects, so change it only knowingly.

## Shops (on the box)

Each shop signs in with its identifier and its own password. The operator manages the shops with
`python -m affiche.shops`. While the service runs, run it inside the running container:

```bash
sudo docker exec -it affiche-ia-affiche-ia-1 python -m affiche.shops list
sudo docker exec -it affiche-ia-affiche-ia-1 python -m affiche.shops create <identifier> --name "Nom affiché" [--welcome 5]
sudo docker exec -it affiche-ia-affiche-ia-1 python -m affiche.shops set-password <identifier>
sudo docker exec -it affiche-ia-affiche-ia-1 python -m affiche.shops suspend <identifier> --yes
sudo docker exec -it affiche-ia-affiche-ia-1 python -m affiche.shops enable <identifier>
sudo docker exec -it affiche-ia-affiche-ia-1 python -m affiche.shops end-sessions <identifier>   # or --all, or --operator
```

- **create** makes an active shop and prints its password once. In the same step it grants the shop 5 offered
  welcome credits (reference `welcome`); `--welcome 10` grants 10, `--welcome 0` none. Give the identifier and the
  password to the owner in person. An identifier has 3 to 32 letters or digits; case, accents, spaces and punctuation do not
  count. A phone number is possible in one written form: `034 12 345 67` gives `0341234567`, and
  `+261 34 12 345 67` gives another identifier. Tell the owner the form you chose.
- **set-password** prints a new password once and ends every session of that shop, and of no other shop. Use
  it when the owner forgot his password or lost a phone. If the output of `create` is lost, use it too.
- **suspend** without `--yes` shows the shop and changes nothing. With `--yes`, the shop cannot sign in and its
  sessions stop working at once. Its queued jobs are cancelled at no cost, and no further provider call is sent
  for it. A call already sent finishes, and its result stays in the shop. The sessions are kept, so **enable**
  reverses a suspension. If the reason is a leaked password, also run `set-password`.
- **enable** makes the shop and its sessions work again. Its data was never touched. Cancelled jobs stay
  cancelled.
- **end-sessions** signs one shop out on every device. `--all` signs out every shop and the operator's dashboard
  (after a restore); `--operator` signs out the operator's dashboard only ("Operator dashboard").
- **list** shows each shop's id, identifier, state, `password` or `no password` (never the password itself),
  creation day and name.

Exit codes: 0 done; 1 refused (one line on stderr, nothing written); 2 wrong command line. The command never
migrates: it refuses when the database is not at the version of the image.

**Where a printed password goes.** `docker exec` gives the command's output to your terminal only. Docker's log
driver (journald here) records the output of the container's main process, not the output of a command run with
`docker exec`: that is Docker's documented behaviour, not tried on the box. While the service is stopped (a
restore, a start that failed), use the **operator** service of `deploy/compose.yml` instead. It runs the same
image on the same data with the same settings, with no container log and no network, and `up` never starts it:

```bash
REV="$(sudo docker inspect -f '{{index .Config.Labels "org.opencontainers.image.revision"}}' affiche-ia-affiche-ia-1)"
sudo env REVISION="$REV" docker compose -f /opt/affiche-ia/app/deploy/compose.yml run --rm operator python -m affiche.shops <command>
```

Never run `create` or `set-password` with `docker compose run … affiche-ia`: the output of that service goes to
the journal. If a password reached a log or a screen it must not reach, run `set-password` for that shop: the old
password stops working, and the shop's sessions end.

### Credits

One credit is one image: a scene, an adjustment of the scene, or a text material. A shop's balance is its grants
and corrections minus its images that wait, run or were made. An image that ends without a result gives its credit
back by itself. You write each grant and correction with the same command, in the running container:

```bash
sudo docker exec -it affiche-ia-affiche-ia-1 python -m affiche.shops grant <identifier> <credits> --offered --ref <reference> [--note "…"]
sudo docker exec -it affiche-ia-affiche-ia-1 python -m affiche.shops grant <identifier> <credits> --bought --amount-ar <ariary> --method <mvola|orange|airtel|cash|…> --ref <payment reference> [--note "…"]
sudo docker exec -it affiche-ia-affiche-ia-1 python -m affiche.shops move-payment <payment reference> <from identifier> <to identifier> --note "<why>"
sudo docker exec -it affiche-ia-affiche-ia-1 python -m affiche.shops correct <identifier> <+n|-n> --ref <reference> --note "<reason>"
sudo docker exec -it affiche-ia-affiche-ia-1 python -m affiche.shops correct <identifier> +1 --ref <short reason> --job <job id> --note "<what was wrong>"
sudo docker exec -it affiche-ia-affiche-ia-1 python -m affiche.shops correct <identifier> 0 --ref <its payment reference> --amount-ar <±ariary> --note "<reason>"
sudo docker exec -it affiche-ia-affiche-ia-1 python -m affiche.shops pause --yes
sudo docker exec -it affiche-ia-affiche-ia-1 python -m affiche.shops resume
sudo docker exec -it affiche-ia-affiche-ia-1 python -m affiche.shops purchase-text "…"
```

- **A line is never changed or removed.** To undo a line, write a correction.
- **grant** adds credits: `--offered` is a gift; `--bought` is a payment, with its amount in whole ariary, its method
  and its reference. It prints the line, the shop's balance and the cap's headroom (below).
- **References.** Each grant and each correction has a reference. In one shop, a reference is used once for a grant
  and once for a correction. A grant or a correction typed twice is refused, with the line that has it: nothing
  doubles. To compare references, the command ignores case and extra spaces: ` mv-123 ` and `MV-123` are the same
  reference. It keeps the spelling typed first, and it writes a move or an amount fix under the payment's own
  spelling. Other differences count: `MV123` and `MV-123` are two references, so type a payment's reference exactly
  as the payment shows it. Only this command makes the comparison: a line written into the database another way is
  not compared, and a later migration is necessary to hold the rule for every writer. If the command finds one
  reference written in two spellings, it refuses and names the lines.
- **A payment is in one shop at a time.** A bought grant whose reference any shop holds is refused, and no option
  forces it.
- **A payment credited to the wrong shop:** `move-payment <reference> <wrong shop> <right shop> --note "…"`. It moves
  the whole payment, its credits and its ariary, in one step. It is refused when the wrong shop has spent some of
  those credits: the payment then stays where it is. To serve the right shop anyway, give it an offered grant:
  `grant <right shop> <n> --offered --ref <reference>-geste --note "paiement <reference> crédité par erreur à <wrong shop>"`.
  It shows as offered and counts no money.
- **correct** adds (`+n`) or takes back (`-n`) credits, with a reason. It is refused when the balance would go below
  zero. **Do not give a plain correction a payment's reference.** A shop has one correction per reference: after a
  plain correction under a payment's reference, a move or an amount fix of that payment is refused. Give the
  correction its own reference, for example `geste-2026-11-20`.
- **A defective image:** `correct <identifier> +1 --ref <short reason> --job <job id> --note "<what was wrong>"`. Only
  for an image of that shop that was made and took a credit, and only once. The job's id comes from the
  administration dashboard. Until it exists, take it from the database: `/api/status` lists only failed jobs, and a
  failed job has its credit back already.
- **Numbers.** A credit count or an amount in ariary is a whole number from -1,000,000,000 to 1,000,000,000. The
  command refuses any other number as a wrong command line (exit 2).
- **A mistyped amount:** `correct <identifier> 0 --ref <payment reference> --amount-ar <±ariary> --note "…"`, in the
  shop that holds the payment, once. The payment's total must stay above zero. If the payment must also move, move
  it first, then fix the amount in the right shop.
- **The cap's headroom.** The cap counts from `SPEND_CAP_SINCE` and does not reset. Each grant prints a line such as
  `service cap 15.00 USD: 6.20 spent since 2026-11-01, 8.80 left; credits outstanding in all shops 280 × 0.035 USD
  (average of the last 50 images) = 9.80 USD`. The price of one image is the average real cost of the last 50
  images, or `ESTIMATE_SCENE_USD` before the first one. When the credits of all shops would cost more than what is
  left, a `WARNING` line follows: raise `SPEND_CAP_USD` ("Secrets") before the shops reach the cap.
- **pause --yes** stops new requests to the AI for every shop: images, styles, text proposals and the reading of
  messages. Requests already admitted finish. The shops can still edit and download. Without `--yes`, the command
  only says whether the service is paused. **resume** lifts the pause. To stop one shop, use `suspend`.
- **purchase-text "…"** sets the text that a shop reads when it has three credits or fewer. Write the packs and
  their prices, the mobile money number, the reference to write with the payment, and when the credits arrive
  (your hours): 1 to 500 characters. Without a text, the command prints the current one. Until you set it, the shops
  read « Pour obtenir des crédits, contactez » followed by `SUPPORT_CONTACT_FR`, or « l’administrateur ».

## Operator dashboard

**State on 2026-11-17: being built for Release 1** (`docs/project/designs/admin-dashboard.md`). The two commands of
this section exist, and so do the dashboard's sign-in, sign-out and « End all operator sessions » over HTTP, their
journal lines and the checks of `verify.sh`. The page and the dashboard's other actions come with the rest of the
release.

The dashboard is at `https://affiches.miorantsoa.app/admin/`. It does what `python -m affiche.shops` does, from a
phone or a laptop, with one operator password and sessions of its own: a shop's session never opens it, and an
operator session is never a shop's. The command line stays: it does everything the dashboard does, also when nobody
can sign in.

**The password.** Only the command sets it, in the running container:

```bash
sudo docker exec -it affiche-ia-affiche-ia-1 python -m affiche.shops operator-password
```

It prints a new password of 26 characters once (about 129 bits), keeps only its Argon2 hash in the database, and
ends every operator session in the same step. Keep it in your password manager: it controls every shop and has no
second factor. While the service is stopped, run it through the operator service ("Where a printed password goes"),
never with `docker compose run … affiche-ia`. To change the password, run the command again: the old password and
every operator session stop at once. Until a password is set, the dashboard's sign-in names the command.

**A lost phone or laptop that you know nobody opened** (locked, and found again): `end-sessions --operator` (every
operator session ends, no shop's), then `operator-password`. In every other case, follow the next paragraph.

**A suspected compromise** (a session you did not open, a line or a journal line you did not make). Over SSH, in
this order, each with `sudo docker exec -it affiche-ia-affiche-ia-1 python -m affiche.shops <command>`:
1. `pause --yes`: no new request reaches the AI.
2. `operator-password`: every operator session ends, the stolen one too; keep the new password.
3. `purchase-text`: read it; set it again if it is not yours.
4. `end-sessions --all`: every shop session and every operator session ends; the shops sign in again.
5. `set-password` for every shop whose password was set from the dashboard in that time
   (`journalctl -t affiche-ia | grep "action=password_set"`). The journal is best effort and keeps about 14 days:
   when in doubt, every shop. Give each new password to its owner in person.
6. `suspend --yes` every shop you did not create (`list` shows each creation day; the journal's `shop_created`).
7. Check every credit line with the suspect actor (`dashboard:<8 hex>`, in each shop's history) against your payment
   records. Take back unjustified credits with `correct -n`. Move a payment back with `move-payment` while its
   credits are unspent.
8. `resume`.

The journal cannot prove that a stolen session was never used: a line is missing when the process stopped after the action. Do the whole procedure unless you know the session was never out of your hands.

**What the dashboard leaves behind.** Its credit lines carry the actor `dashboard:<8 hex>`, which names a session,
not a person; the command line's carry `operator`. Each of its other actions is one journal line, written after the
action, best effort: `journalctl -t affiche-ia | grep "operator action"`. A line is missing when the process stopped
between the two, and the journal keeps about 14 days ("Operate", Logs). The command line's own actions write no
journal line: their output goes to your terminal only. The Service screen lists the live operator sessions, with
their address and browser.

**`verify.sh` and the operator password.** Each release's `verify.sh` asks the dashboard whether an operator
password is set, and fails when it is not (for example after a restore of an older database): run
`operator-password`, then `verify.sh` again. The only exception is the release run with `OPERATOR_BOOTSTRAP=1`
("Release 1: the operator dashboard"), which warns.

## Secrets (on the box, never in git)

`/opt/affiche-ia/secrets/app.env` (root, 600): `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `SPEND_CAP_USD`,
`SPEND_CAP_SINCE`; `SHOP_PASSWORD_HASH` until step 9 of Release 1 removes it. Optional: `SUPPORT_CONTACT_FR`
(the contact shown under the sign-in form for a forgotten password) and `SHOP_DAILY_SPEND_USD` (each shop's
provider spend per UTC day, default 2.00). Every value in single quotes.

- Edit with `sudo nano /opt/affiche-ia/secrets/app.env`, then run the recreate command above.
- **New shop password** (also when a phone is lost): `python -m affiche.shops set-password <identifier>`
  ("Shops"). Since migration 0013 a new `SHOP_PASSWORD_HASH` has no effect.
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

**A restore rolls back every shop.** Passwords, suspensions and sessions go back to the time of the backup: a
password reset made after that time is undone, the session of a lost phone works again, a suspended shop can send
provider calls again, and a shop created after that time is gone. The operator's dashboard password goes back too,
maybe to one you replaced since. So the service stays stopped until the repairs are done.
`/opt/affiche-ia/restore.sh` does the part that can be checked, and never starts the service.

1. Choose a copy: `sudo ls -lt /opt/affiche-ia/backups/db`.
2. Run `sudo sh /opt/affiche-ia/restore.sh <file>`, with the file name only (for example
   `affiche-20261116T004000Z.db`). Under the lock that the releases and the nightly backup take, it stops the
   service, puts the copy in place, runs the application's start once in a one-off container (migrations and
   checks, no server; this brings a backup from before migration 0013 to this version), ends every session (the
   operator's too) and lists the shops. Each run keeps the database it replaces as
   `/data/affiche.db.before-restore-<time>` (with its `-wal` file) in the volume `affiche-ia_data`, and never
   overwrites one. A missing asset file is copied beside its place and then renamed, so a copy cut short is done
   again by the next run. Last, it runs `after-restore` on the
   database it replaced: a report of the credit lines that the backup lacks ("Credits after a restore", below). The
   report writes nothing.
3. If a step fails, the script stops with `RESTORE FAILED: <step>. <state>.`: the state says whether the service
   is stopped and which database is in place. Correct the cause and run the script again, or, if the database was
   not replaced, start the service again with `sudo docker start affiche-ia-affiche-ia-1`. A failed report is not a
   failed restore: the script says `THE CREDIT REPORT FAILED`, and continues to `RESTORED`. Run `after-restore`
   yourself.
4. On success it ends with `RESTORED: <file> is in place, at this version, with every session ended. THE SERVICE IS
   STOPPED.`, the list of the repairs and the exact command to run them with the operator service ("Shops"). Do
   them in this order:
   - The operator's password, always and first: `operator-password`, now, before the service starts. The restored
     database holds the backup's password; ending the sessions alone does not stop it. Keep the new one in your
     password manager.
   - Each shop created after the time of the backup: the `create … --welcome 0` line that the report printed for it.
     The line is quoted for the shell: type it after `sudo env REVISION=… docker compose … run --rm operator`. The
     shop's own welcome credits come back with the copy. If there is no report, `create <identifier> --name "<name>"
     --welcome 0`.
   - The credit lines: `after-restore /data/affiche.db.before-restore-<time> --apply`, with the path that the
     script printed. It copies them in one transaction, in the order they were written, with their dates. It copies
     nothing while a shop it needs is missing. After each correction, run it again: it skips a line that is already
     here.
   - Each `set-password` and `suspend --yes` made after the time of the backup; `pause --yes` and `purchase-text` if
     they were set since.
5. If it says `originalphone has no password (a backup from before migration 0013)`, run `set-password
   originalphone`, or put the pilot's hash back in `/opt/affiche-ia/secrets/app.env` as `SHOP_PASSWORD_HASH`. With
   neither, the service refuses to start.
6. Check with the operator service's `list` that each shop has the state it must have now.
7. Start the service: `sudo docker start affiche-ia-affiche-ia-1`. Check `journalctl -t affiche-ia --since "10 min
   ago"`, then sign in.
8. Give each owner whose password changed after the time of the backup the new password that `set-password` printed.

**Credits after a restore** (`python -m affiche.shops after-restore <kept database> [--apply]`). The grants,
corrections and generations go back to the time of the backup. The images made after that time are gone, so they
are not charged: the report gives their number for each shop. The grants and corrections made after that time are
copied back from the database that the restore replaced, which the command only reads.

- **Already here.** A line is here when this database has a line of the same shop (by identifier), kind and
  reference. Case and extra spaces do not count, so a payment that you typed again after the restore is not copied
  a second time. The copy keeps each reference as it was written.
- **A repayment** (`correct … --job`) is copied only when its job here made its image and took a credit. If the job
  still waits or runs, run `after-restore` again after it ends. If the job ended without an image, or is not here
  (made after the backup), the line is skipped with its reason. If another correction of that shop has taken its
  reference since the restore, the line is skipped and named: repay that job by hand under a reference not used yet.
- **A payment whose history here departs from the kept one** (typed again in another shop, with another amount or number of
  credits, or moved or corrected in another way) is not
  copied: its lines are skipped and named, and the history of this database stands. The other lines are copied.
  Check that payment by hand: `grant` it if no shop has it, `move-payment` if the wrong shop has it.
- **Refused, nothing copied, the lines named:** one reference written two ways in one shop; a line that the
  database refuses (for example, a job that you repaid again after the restore).
- **A balance below zero after the copy** is said, with the number of generations that wait or run. Each of them
  that ends without an image gives one credit back. What stays below zero is yours to settle.
- **No kept database, or one that cannot be read:** the loss policy applies. Do the grants and corrections made
  since the backup again from your payment records. A kept database from before migration 0014 has nothing to copy.

Never mount `/data` read-only for any of this: a database in write-ahead mode cannot be opened on a read-only
volume. After a restore, **the ledger has lost the spend made since that backup**, and a generation that was
reserved at backup time runs again: compare `/api/status` with the provider's dashboard and lower
`SPEND_CAP_USD` by the difference. Remove `/data/affiche.db.before-restore-<time>` and its `-wal` and `-shm` files
only when you are satisfied (`after-restore` reads it through SQLite, which makes the `-shm` file).

**Proof before the first pilot day (development machine):** copy one `db/affiche-*.db` and `assets/` from the
box, put them in a new folder as `affiche.db` and `assets/`, start the API on it with `DATA_DIR` set to that
folder, `IMAGE_PROVIDER=openai` and **`OPENAI_API_KEY=not-a-real-key`** in the environment (the environment
wins over `backend/.env`, so this copy cannot spend), sign in, and download a confirmed poster: its SHA-256 must
equal the one shown when it was confirmed.

## Rollback

Code-only releases: `git checkout <previous commit>`, deploy, then `git checkout -` (the previous commit is on
`origin/main`, so the deploy accepts it). After a release that added a migration: fix forward, or restore the
backup that the release took just before starting. A deploy of code older than the database's last migration
stops at the rehearsal (`No such revision`) and changes nothing.

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

## Not proven yet (2026-11-13, after the first deploy)

- **Memory during a final render** (step 5). About four scenes were generated on the box on 2026-11-13 (ledger USD 0.82) without a restart or an out-of-memory kill, 263 MiB at rest afterwards; a generation does not start Chromium, the final preview does, and nobody watched one yet.
- **The restore** (step 8), on the box or on a development machine. The backup and a restore are tested on
  temporary data only (`backend/tests/test_backup.py`).
- **Backups off the box:** not decided. Everything is on `mx1` only.
- **The owner's phone** (step 9), and the home-screen icon on a real phone.
- **A rollback** has never run. (The second release ran on 2026-11-13 at 15:53 UTC: old container stopped, backup with the new image, new container healthy 9 seconds later, second backup; the poster, the profile, the ledger and both sessions were kept.)
- Disk: 7.9 GB free after the first build (13 GB before). The deploy needs 5 GB; watch it before each release.
- **The rehearsal step and `release.sh` on the box.** `backend/tests/test_release_script.py` runs `release.sh`
  with a fake `docker` only (no Docker on the development machine). The real image, its SQLite 3.40.1 and the
  copy of the live database are proven by the report of the first release that runs it (Release 1, step 4).
- **`restore.sh`, the operator service and the deadlines**, also with the fake `docker` only
  (`backend/tests/test_restore_script.py`): that `docker compose run --rm operator` writes nothing to the journal,
  that `up` and `build` leave the operator service alone (its profile), the real `timeout` around a hung backup, and the removal of a backup container that outlived it.
  `after-restore` read the kept database read-only, with and without its `-wal`, on SQLite 3.46.1 and 3.53.1 on the
  development machine, not on the image's 3.40.1 in the operator container.

Proven on 2026-11-13: the image builds on the box; the hardened container starts and stays healthy; Chromium
starts in it; the Caddy block (valid, and the French 503 answers while no container existed); HTTP redirects to
HTTPS; HSTS is sent; the page and its manifest are public and `/api/*` answers 401 without a session; a foreign
Origin is refused (403); **a forged `X-Forwarded-For` does not fool the sign-in limit** (a wrong password sent
with `X-Forwarded-For: 203.0.113.9` was recorded under the caller's real public address); the settings in the
container are the hosted ones (`openai`, `/data`, cap 15 since 2026-11-13, planner key present).
