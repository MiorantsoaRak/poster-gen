# T-DEPLOY-DOCKER-RUN — release and restore scripts on real Docker (2026-11-19)

Run by Claude on the user's word ("you can use the pc docker for the run") on the user's laptop: Docker 29.9.3,
reached through `sg docker` (the user is in the `docker` group; the session's shell started before that). Never the
shared box. Zero spend: the provider keys were placeholders and no generation was asked.

## Setup (a throwaway "box" in the session scratchpad, deleted after the run)

- `$D` = a scratchpad folder that stands for `/opt/affiche-ia`: `secrets/app.env`, `backups/`, the archives.
- `secrets/app.env` written as `deploy.py` writes it (each value in single quotes): `SHOP_PASSWORD_HASH` (Argon2 of a
  random password), placeholder `OPENAI_API_KEY` and `ANTHROPIC_API_KEY`, `SPEND_CAP_USD=1`, `SPEND_CAP_SINCE`.
- Archives made like `deploy.py` (git archive of `IMAGE_PATHS`) for `0e5fa64` (the pilot's live revision, migrations to
  0012) and for HEAD; release revision `2944ea0` (`git log -1 -- IMAGE_PATHS`, as `deploy.py` computes `REV`).
- `docker network create affiche_ia_edge` (Maizina's network on the box).

Deviations from the box, each the smallest that lets the scripts run off it:

| What | Box | Here | Why |
| --- | --- | --- | --- |
| `compose.yml` backups mount | `/opt/affiche-ia/backups` | `$D/backups` (one replacement, in the archive copy only) | no `/opt/affiche-ia` on the laptop |
| `daily.sh` lock | `/opt/affiche-ia/.lock` | `$D/.lock` (one replacement, copy) | same |
| `backups/` mode | 700, scripts as root | 755, owner 10001, scripts as the user | no sudo; the scripts' `[ -f backups/db/… ]` must see the files |
| `release.sh` backup deadline | 900 s | 30 s, in a copy used for the timeout case and for the first upgrade (step 3) only | a 15-minute wait for one case |
| `affiche-ia:local` (an old local image, label `app=affiche-ia`) | none | held by a stopped container for the run | the release's `image prune --filter label=app=affiche-ia` would have deleted it |

Steps 4 and 5 ran the files of HEAD unchanged: `deploy/release.sh`, `deploy/restore.sh`.

## Results

| # | Check (TODO.md T-DEPLOY-DOCKER-RUN) | Result |
| --- | --- | --- |
| 1 | Old pilot `0e5fa64` built and started as its `deploy.py` did (`compose build`, `up -d --wait`) | healthy; one sign-in made a session row |
| 2 | `daily.sh` (`docker exec … python -m affiche.backup`): output stays out of the service's journal | `backup ok: affiche-20261119T162207Z.db` only under `affiche-ia-daily`; 0 lines under `affiche-ia` (which does receive the service's own logs: uvicorn's start lines). Same result again on `2944ea0` after the release |
| 3 | Release `2944ea0` over the 0012 database: build, configuration check, rehearsal, stop, backup, start | `REHEARSAL OK` on **SQLite 3.40.1**, Python 3.12.16: `pending migrations: 0013, 0014, 0015, 0016, 0017`, every table's rows and hash equal before and after, the 0013–0017 additions and the 14 guards "as expected", `integrity_check ok`; backup, then healthy at `2944ea0`; lock free |
| 3b | Hung backup: the backup container paused (`POST /containers/affiche-ia-backup/pause`, polled from the release's start), 30 s deadline | `Backup before the release FAILED: no answer within 30 s (timeout).` `(exit 124). Nothing was changed: the new version was not started.` `The previous container is started again.` → release exit 1; **no `affiche-ia-backup` left** (a paused container was removed); the previous container healthy, restart count 0; lock free; no backup file and no `.tmp` written |
| 4 | Unchanged `release.sh` over a running service; then again with the same revision | release exit 0, healthy at `2944ea0`, `Total reclaimed space: 0B`; the rerun prints `2944ea02e3c5 already running`, exit 0, and removes its archive |
| 4b | `up` and `build` leave the operator service alone | after every release: no operator container (`docker ps -a`) |
| 4c | `verify.sh`, the part that needs no box (cut before "The neighbours") | crash-loop check over 10 s, no published port, in-container `/api/session`, **Chromium starts in the hardened container**: all ok |
| 4d | The operator writes nothing to the journal | `create journaltest`, `set-password originalphone`, `operator-password`, `list` (each printed password once): 0 of the 4 printed secrets in the whole journal since the start (55 lines of every tag); 0 lines under `affiche-ia`; their containers removed (`--rm`) |
| 4e | Operator bootstrap state | `/api/admin/session` → `{"authenticated":false,"configured":false}` after the release, `configured:true` after `operator-password` |
| 5 | `restore.sh` with the backup **taken by the old pilot code before migration 0013** | exit 0: started once (migrations and checks passed), `1 sessions ended`, `originalphone … no password`, `after-restore` names the missing shop with its `create journaltest … --welcome 0` line, the replaced database kept as `affiche.db.before-restore-<time>`, service left stopped |
| 5b | Start after the restore, `app.env` unchanged (hash still in it, as on the box until README step 9) | healthy; shop 1 adopts the hash at start (`list` → `password`; log warns `SHOP_PASSWORD_HASH is no longer read … Remove the setting.`); the pilot's password signs in (200, `shop_id 1`), a wrong one gets 401 |

## Observations, no defect found

- The restore prints "originalphone has no password … or put its hash back in app.env" even while the hash is still
  there: correct, since adoption happens at the API's start (`api.py`, `adopt_password_setting`) and not in the
  restore's one start (`runtime.start`). After README step 9 removes the line, `set-password` is the way, as printed.
- `docker logs` works with the journald driver (verify.sh's `fail()` uses it): it returned the service's warning above.
- The release's `docker image prune -af --filter label=app=affiche-ia --filter until=1h` deletes any unused image with
  that label older than an hour. Intended on the box; on another machine it takes local builds too.

## Not covered by this run

- The pilot's real rows: this database had one shop and one session. The release gate rehearses on a copy of the live
  database on the box at release time, so the real data is still checked before any change.
- verify.sh's second half (neighbours, Caddy, HTTPS redirect, cron, backup marker): box only.
- `deploy.py` itself (pyinfra, uploads, the secrets step): box only.

## Cleanup

Removed: the container `affiche-ia-affiche-ia-1`, the volume `affiche-ia_data`, the network `affiche_ia_edge`, the
images `affiche-ia:0e5fa64…`, `:2944ea0…`, `:hungtest`, `:hungtest2`, the hold container and the scratch folder.
Left as found: `affiche-ia:local`, the two other projects' containers. Docker's build cache was not pruned (shared).
