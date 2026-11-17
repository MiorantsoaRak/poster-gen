#!/bin/sh
# Restores one backup of the database on the box, as root (deploy/README.md, Restore); deploy.py installs it from
# HEAD beside daily.sh. Usage: sudo sh /opt/affiche-ia/restore.sh <file name in /opt/affiche-ia/backups/db>
# Under the lock that the release and daily.sh take, in order: stop the service; put the backup in place (each run
# keeps the database it replaces as affiche.db.before-restore-<time>, never overwritten); run the application's own
# start once in a one-off container (lock, migrations, checks; no server), which also brings a backup from before
# migration 0013 to this version; end every session, the operator's too; list the shops; report the credit lines of
# the database it replaced that the backup lacks (read only: the operator copies them with --apply). It NEVER starts
# the service: the repairs only the operator knows come first, the operator's password first of all. Any failed step
# stops it with what state the service and the data are in; a failed report does not, the database being restored by
# then (backend/tests/test_restore_script.py runs this file with a fake docker).
set -eu
[ "$#" = 1 ] || { echo "usage: sudo sh restore.sh <file name in backups/db, for example affiche-20261116T004000Z.db>"; exit 2; }
FILE="$1"
DIR="$(cd "$(dirname "$0")" && pwd)"
C=affiche-ia-affiche-ia-1
STATE="the service still runs; nothing was changed"
fail() { echo "RESTORE FAILED: $1. $STATE."; exit 1; }
# The operator's one-offs: the service's image, data and settings, with no container log (a password never reaches
# the journal) and no network (deploy/compose.yml).
op() { REVISION="$REV" docker compose -f app/deploy/compose.yml run --rm operator "$@"; }

case "$FILE" in */* | .* | "") fail "give the file name only, as listed by: sudo ls -lt $DIR/backups/db" ;; esac
exec 9>"$DIR/.lock"
flock -w 600 9 || fail "the lock is busy (a release or the nightly backup runs)"
# Named under the lock: two runs started in the same second must not share the name of what they set aside.
BEFORE="/data/affiche.db.before-restore-$(date -u +%Y%m%dT%H%M%SZ)"
cd "$DIR"
[ -f "backups/db/$FILE" ] || fail "no backup $DIR/backups/db/$FILE"
REV="$(docker inspect -f '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$C")" \
  || fail "no container $C to take the image from"
STATE="the service may be stopped (sudo docker ps -a); the database was not replaced"
docker stop -t 300 "$C" || fail "docker stop $C"
STATE="THE SERVICE IS STOPPED; the database may be partly replaced: the one before is $BEFORE (with its -wal file if it had one) in the volume affiche-ia_data"
# Exit 4: a database set aside earlier already has this name; it is never overwritten. An asset file is immutable and
# named by its hash: a missing one is copied beside its place, then renamed, so that a copy cut short is never taken
# for the file on the next run (.tmp is the suffix affiche.backup skips).
placed=0
docker run --rm -u 10001:10001 -v affiche-ia_data:/data -v "$DIR/backups:/backups:ro" --entrypoint sh "affiche-ia:$REV" -c '
  set -e
  if [ -e "$2" ] || [ -e "$2-wal" ]; then exit 4; fi
  if [ -e /data/affiche.db ]; then mv /data/affiche.db "$2"; fi
  if [ -e /data/affiche.db-wal ]; then mv /data/affiche.db-wal "$2-wal"; fi
  rm -f /data/affiche.db-shm
  cp "/backups/db/$1" /data/affiche.db
  cd /backups/assets
  find . -type f | while IFS= read -r file; do
    if [ -e "/data/assets/$file" ]; then continue; fi
    mkdir -p "/data/assets/$(dirname "$file")"
    cp "$file" "/data/assets/$file.tmp"
    mv "/data/assets/$file.tmp" "/data/assets/$file"
  done' restore "$FILE" "$BEFORE" || placed=$?
if [ "$placed" = 4 ]; then
  STATE="THE SERVICE IS STOPPED; the database was not replaced"
  fail "$BEFORE already exists (a restore made this same second): run the script again"
fi
[ "$placed" = 0 ] || fail "putting the backup in place"
STATE="THE SERVICE IS STOPPED; the database is the backup $FILE, not yet brought to this version; the one before is $BEFORE"
op python -c 'from affiche import runtime; from affiche.config import load_settings; runtime.start(load_settings(), "api"); print("the application started once on the backup: migrations and checks passed")' \
  || fail "the application's start on the backup (migrations, checks)"
STATE="THE SERVICE IS STOPPED; the database is the backup $FILE at this version, its sessions not yet ended"
op python -m affiche.shops end-sessions --all || fail "ending every session"
STATE="THE SERVICE IS STOPPED; the database is the backup $FILE at this version, with no session"
shops="$(op python -m affiche.shops list)" || fail "listing the shops"
printf '%s\n' "$shops"
# Read only, and the restore is done by now: a failure here is said, and changes nothing above.
op python -m affiche.shops after-restore "$BEFORE" \
  || echo "THE CREDIT REPORT FAILED (above); the restore itself is done and nothing was copied. Run after-restore again (below); if the database it replaced cannot be read, redo the grants and corrections made since the backup from your payment records."
echo "RESTORED: $FILE is in place, at this version, with every session ended. THE SERVICE IS STOPPED."
echo "The database it replaced is $BEFORE in the volume affiche-ia_data: remove it only when you are satisfied."
echo "Before you start it, redo by hand each change made after the time of this backup (this script cannot know them):"
echo "  the operator's password: operator-password (the restored database holds the backup's password; run it now, before the service starts)"
echo "  each shop created:     the line that after-restore printed for it (python -m affiche.shops create ... --welcome 0), else create <identifier> --name \"<name>\" --welcome 0"
echo "  then the credit lines: after-restore $BEFORE --apply (copies them back in their order, with their dates; nothing while a shop is missing)"
echo "  each password reset:   set-password <identifier>"
echo "  each suspension:       suspend <identifier> --yes"
echo "  a pause set since:     pause --yes; a purchase text set since: purchase-text \"<text>\""
# A backup from before migration 0013 has no password for shop 1: without one, the service refuses to start.
printf '%s\n' "$shops" | awk -F '\t' '$4 == "no password" { print "  " $2 " has no password (a backup from before migration 0013): set-password " $2 (($1 == 1) ? ", or put its hash back in /opt/affiche-ia/secrets/app.env as SHOP_PASSWORD_HASH; without either the service refuses to start" : "") }'
echo "Run each one as: sudo env REVISION=$REV docker compose -f $DIR/app/deploy/compose.yml run --rm operator python -m affiche.shops <command>"
echo "Check the shops with the command list. Then start the service: sudo docker start $C"
