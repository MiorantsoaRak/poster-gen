#!/bin/sh
# Nightly backup, run as root by /etc/cron.d/affiche-ia and by deploy.py after a release.
# Log: journalctl -t affiche-ia-daily. The command itself keeps 14 days of database copies (affiche/backup.py).
set -u
log() { logger -t affiche-ia-daily "$*"; }
exec 9>/opt/affiche-ia/.lock
flock -w 600 9 || { log "daily: lock busy"; exit 1; }

# Inside the running container: same user, same view of the data volume, no second copy of the code.
if out=$(docker exec affiche-ia-affiche-ia-1 python -m affiche.backup /backups 2>&1); then
  log "$out"
else
  log "backup FAILED: $out"
  exit 1
fi
