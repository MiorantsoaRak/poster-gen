#!/bin/sh
# One release on the box, run as root by deploy.py, which uploads this file from HEAD for this run only.
# Usage: sh release.sh <revision> <archive name> <remote folder>
# Under the lock shared with daily.sh: build, configuration check and rehearsal of the pending migrations, all in the
# new image while the old container still serves; then stop, backup, start. Any failure before the stop changes
# nothing; a failed backup starts the old container again (backend/tests/test_release_script.py runs this file with
# a fake docker).
set -eu
[ "$#" = 3 ] || { echo "usage: sh release.sh <revision> <archive name> <remote folder>"; exit 2; }
REV="$1"
ARCHIVE="$2"
DIR="$3"
C=affiche-ia-affiche-ia-1
B=affiche-ia-backup                         # the check-and-backup container, named so that it can be removed
REPORT="$DIR/last-rehearsal.txt"
# The service is down from the stop: the check and backup, then the restart after a failure, end by these deadlines
# (seconds). The backup copies the database and the asset files new since the last one, which takes seconds.
BACKUP_DEADLINE=900
START_DEADLINE=120
new() { docker compose -f app.new/deploy/compose.yml "$@"; }

exec 9>"$DIR/.lock"
flock -w 600 9
cd "$DIR"
export REVISION="$REV"
# Recheck under the lock: a concurrent deploy may have released this revision meanwhile.
if [ "$(docker inspect -f '{{.State.Status}} {{index .Config.Labels "org.opencontainers.image.revision"}}' "$C" 2>/dev/null || true)" = "running $REV" ]; then
  rm -f "$ARCHIVE"
  printf '%.12s already running\n' "$REV"
  exit 0
fi
rm -rf app.new
mkdir app.new
tar -xzf "$ARCHIVE" -C app.new
new build
# The defaults are traps on a server: "stub" would be recorded as this data's provider mode for good, and the default
# data folder is on the read-only filesystem.
new run --rm --no-deps affiche-ia python -c 'from affiche.config import load_settings; from affiche.posters import auth; s = load_settings(); auth.validate_config(s); assert s.image_provider == "openai" and str(s.data_dir) == "/data" and str(s.backup_dir) == "/backups" and s.serve_frontend and s.api_host == "0.0.0.0", "deploy/compose.yml environment is not the hosted one"; print("configuration ok")'
# The release gate (multi-shop design): the pending migrations run on a fresh copy of the live database, in this
# image and with its SQLite, while the old container still serves. One container checks and rehearses, so that a
# failure of docker itself also stops here. The report is kept for the release record: pyinfra shows a command's
# output only when it fails.
rehearsed=0
new run --rm --no-deps affiche-ia sh -c 'if [ -f /data/affiche.db ]; then exec python -m affiche.rehearse /data/affiche.db; else echo "No database yet (first deploy): nothing to rehearse."; fi' >"$REPORT" 2>&1 || rehearsed=$?
cat "$REPORT"
if [ "$rehearsed" != 0 ]; then
  echo "Rehearsal FAILED: nothing was changed, the service still runs. The report is in $REPORT."
  exit 1
fi
# From here the service is down until the new container is up. SQLite has one writer: the old container is
# stopped (it finishes a running paid generation first, 5 minutes at most), then the data is backed up
# with the new code, then the new container starts and applies its migrations.
old=$(docker ps -q -f "name=^$C\$")
if [ -n "$old" ]; then docker stop -t 300 "$C"; fi
# One container checks for the database and backs it up, so that no failure, of docker itself included, can pass for
# a first deploy: the new container migrates at start. Exit 0: backed up; 3: no database yet (neither docker, nor
# Python, nor affiche.backup exits 3); 124 or 137: no answer before the deadline (timeout); anything else: failed.
backed=0
timeout --kill-after=10s "$BACKUP_DEADLINE" docker compose -f app.new/deploy/compose.yml run --rm --no-deps --name "$B" affiche-ia \
  sh -c '[ -f /data/affiche.db ] || exit 3; exec python -m affiche.backup /backups' || backed=$?
if [ "$backed" = 3 ]; then
  echo "No database yet (first deploy): nothing to back up."
elif [ "$backed" != 0 ]; then
  if [ "$backed" = 124 ] || [ "$backed" = 137 ]; then
    echo "Backup before the release FAILED: no answer within $BACKUP_DEADLINE s (timeout)."
  fi
  echo "Backup before the release FAILED (exit $backed). Nothing was changed: the new version was not started."
  # The deadline ends the docker client, not always its container: nothing else may start, and the lock is not
  # released, while a backup container can still read the database or write backup files.
  docker rm -f "$B" >/dev/null 2>&1 || true
  left=$(docker ps -aq -f "name=^$B\$") || left=unknown
  if [ -n "$left" ]; then
    echo "THE SERVICE IS DOWN: the backup container $B could not be removed. Remove it (sudo docker rm -f $B), then: sudo docker start $C"
    exit 1
  fi
  if [ -n "$old" ]; then
    echo "The previous container is started again."
    timeout --kill-after=10s "$START_DEADLINE" docker start "$C" \
      || { echo "THE SERVICE IS DOWN: the previous container did not start again (sudo docker start $C)."; exit 1; }
  fi
  exit 1
fi
rm -rf app
mv app.new app
if ! docker compose -f app/deploy/compose.yml up -d --wait --wait-timeout 180 affiche-ia; then
  echo "The new container did not become healthy. THE SERVICE IS DOWN. Its last lines:"
  docker logs --tail=80 "$C" 2>&1 || true
  echo "Code-only release: git checkout <previous commit>; cd deploy; pyinfra 89.167.56.26 deploy.py --user deploy -y; git checkout -"
  echo "Release with a migration: fix forward, or restore the backup taken just before (deploy/README.md, Restore)."
  exit 1
fi
rm -f "$ARCHIVE"
docker image prune -af --filter label=app=affiche-ia --filter until=1h
