#!/bin/sh
# Post-deploy checks, run on the box by deploy.py under `timeout 300`. Usage: sh verify.sh <revision>
set -u
REV=$1
C=affiche-ia-affiche-ia-1
PUBLIC=https://affiches.miorantsoa.app
CRON_FILE=/etc/cron.d/affiche-ia
CRON_LINE="40 0 * * * root /bin/sh /opt/affiche-ia/daily.sh"

fail() {
  echo "FAIL: $1"
  docker logs --tail=80 "$C" 2>&1
  echo "Rollback (code-only releases): git checkout <previous commit>; cd deploy; pyinfra 89.167.56.26 deploy.py --user deploy -y; then git checkout -"
  exit 1
}
state() { docker inspect -f '{{.State.Status}} {{.RestartCount}} {{index .Config.Labels "org.opencontainers.image.revision"}} {{.Id}}' "$C" 2>/dev/null; }
answers() { curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$1"; }

set -- $(state)
[ "${1:-missing}" = running ] || fail "container $C is ${1:-missing}"
[ "${3:-}" = "$REV" ] || fail "container runs revision ${3:-none}, expected $REV"
first="$2 $3 $4"
# A crash-looping container can be up for a moment; the same container, revision and restart count after 10 s
# rules that out.
sleep 10
set -- $(state)
[ "${1:-missing}" = running ] && [ "$2 $3 ${4:-}" = "$first" ] || fail "container restarted or was replaced within 10 s (crash loop?)"
echo "ok: $C running $REV, same container and restart count over 10 s"

# The forwarded-header trust is safe only while no port is published.
[ -z "$(docker port "$C" 2>/dev/null)" ] || fail "a port is published: remove ports: from deploy/compose.yml"
echo "ok: no published port"

docker exec "$C" python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/session', timeout=5)" \
  || fail "in-container /api/session (database and migrations)"
echo "ok: in-container /api/session"

# The renderer: Chromium must start inside the hardened container, before the owner needs a poster.
docker exec "$C" python -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(); page = browser.new_page(); page.set_content('<p>ok</p>'); browser.close()
" || fail "Chromium does not start in the container"
echo "ok: Chromium starts in the container"

# The neighbours on the box still answer.
for url in https://maizina.89-167-56-26.sslip.io/api/v1/health https://buy.miorantsoa.app/ready https://duel.miorantsoa.app; do
  code=$(answers "$url")
  [ "$code" = 200 ] || fail "$url answered $code"
done
echo "ok: Maizina, PPN Market and Trap Duel answer 200"

code=000
for _ in 1 2 3 4 5 6 7 8 9 10; do
  code=$(answers "$PUBLIC/")
  [ "$code" = 200 ] && break
  sleep 6
done
[ "$code" = 200 ] || fail "$PUBLIC/ answered $code"
[ "$(answers "$PUBLIC/manifest.webmanifest")" = 200 ] || fail "$PUBLIC/manifest.webmanifest is not served"
body=$(curl -s --max-time 10 "$PUBLIC/api/session")
[ "$body" = '{"authenticated":false}' ] || fail "$PUBLIC/api/session through Caddy answered: $body"
[ "$(answers "$PUBLIC/api/creations")" = 401 ] || fail "$PUBLIC/api/creations is not closed without a session"
echo "ok: $PUBLIC serves the page and its manifest, the API answers through Caddy and is closed without a session"

redirect=$(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' --max-time 10 "http://affiches.miorantsoa.app/")
[ "$redirect" = "308 $PUBLIC/" ] || fail "HTTP did not redirect to HTTPS: $redirect"
echo "ok: HTTP redirects to HTTPS"

systemctl is-active --quiet cron || fail "cron is not active"
[ "$(stat -c '%U %a' "$CRON_FILE" 2>/dev/null)" = "root 644" ] || fail "$CRON_FILE missing or not root 644"
[ "$(cat "$CRON_FILE")" = "$CRON_LINE" ] || fail "$CRON_FILE does not hold the expected line"
marker=/opt/affiche-ia/backups/last-backup.json
[ -s "$marker" ] && [ -n "$(find "$marker" -mmin -1560)" ] || fail "no backup younger than 26 h ($marker)"
echo "ok: cron active and installed, last backup: $(cat "$marker")"
