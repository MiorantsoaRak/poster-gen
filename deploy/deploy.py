"""Deploy Affiche IA to the Hetzner box mx1 (pyinfra 3.x). One file, no inventory:

    cd deploy; pyinfra 89.167.56.26 deploy.py --user deploy -y

Adapted from ../ppn-market/deploy/deploy.py (same box, same rules). Never add --diff or --debug: they print
uploaded file contents, including the first deploy's secrets.
Needs Maizina deployed with the affiche_ia_edge network and the affiches.miorantsoa.app Caddy block
(README.md, "First rollout"). In order:
  1. Refuse if a deploy input is modified or untracked, or if HEAD is not on origin/main.
     REV = last commit touching an image input.
  2. Secrets, created once on the box. The first deploy needs AFFICHE_SHOP_PASSWORD_HASH and
     AFFICHE_OPENAI_API_KEY in the local shell (AFFICHE_ANTHROPIC_API_KEY and AFFICHE_SPEND_CAP_USD are
     optional); later deploys ignore them.
  3. daily.sh, verify.sh (from HEAD) and the cron entry.
  4. affiche-ia already running REV: no upload, no build, no restart.
  5. Otherwise: prechecks -> upload git archive -> build -> configuration check in the new image ->
     stop the old container -> back up with the new image -> start (migrations run at start) -> prune.
     A failed build or check changes nothing. A failed backup starts the old container again.
  6. daily.sh once (a backup of the running revision), then verify.sh.
"""

import os
import subprocess
import uuid
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from io import StringIO
from pathlib import Path

from pyinfra import host
from pyinfra.facts.server import Command
from pyinfra.operations import files, server

REMOTE_DIR = "/opt/affiche-ia"
CONTAINER = "affiche-ia-affiche-ia-1"  # compose project "affiche-ia", service "affiche-ia"
# Everything the image is built from. REV and the archive use this list, so a docs or test edit neither
# rebuilds nor restarts the application.
IMAGE_PATHS = [
    "Dockerfile",
    ".dockerignore",
    "backend/pyproject.toml",
    "backend/uv.lock",
    "backend/.python-version",
    "backend/alembic.ini",
    "backend/migrations",
    "backend/src",
    "frontend",  # whole: the type check of the build reads tests/*.ts too (tsconfig.json)
    "deploy/compose.yml",
]
# The scripts run as root on the box, so they must be committed too.
GUARD_PATHS = [*IMAGE_PATHS, "deploy"]
CRON_LINE = f"40 0 * * * root /bin/sh {REMOTE_DIR}/daily.sh\n"  # 00:40 UTC, ten minutes after PPN Market's
LOCK = f"exec 9>{REMOTE_DIR}/.lock\nflock -w 600 9"  # shared with daily.sh
REPO = Path(__file__).resolve().parent.parent
RUN = uuid.uuid4().hex[:12]  # names this invocation's uploads, so concurrent deploys never share one
STAGING = "/home/deploy/.affiche-staging"  # first-deploy settings land here, never in /tmp
STAGED_ENV = f"{STAGING}/app.env.{RUN}"
COMPOSE_NEW = "docker compose -f app.new/deploy/compose.yml"
# Run in the new image before anything is stopped. The defaults are traps on a server: "stub" would be recorded
# as this data's provider mode for good, and the default data folder is on the read-only filesystem.
CHECK = (
    "from affiche.config import load_settings; from affiche.posters import auth; s = load_settings(); "
    'auth.validate_config(s); assert s.image_provider == "openai" and str(s.data_dir) == "/data" '
    'and str(s.backup_dir) == "/backups" and s.serve_frontend and s.api_host == "0.0.0.0", '
    '"deploy/compose.yml environment is not the hosted one"; print("configuration ok")'
)


def git(*args: str) -> subprocess.CompletedProcess:
    # List arguments: a space in the user's path needs no quoting, whatever the shell.
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, encoding="utf-8")


def committed(path: str) -> StringIO:
    shown = git("show", f"HEAD:{path}")
    assert shown.returncode == 0, shown.stderr
    return StringIO(shown.stdout)


def single_quoted(name: str, value: str) -> str:
    # Compose dotenv: single quotes are literal (the Argon2 hash keeps its $ signs); no escape exists.
    if "'" in value or "\n" in value or "\r" in value:
        raise SystemExit(f"{name} must be one line without a single quote")
    return f"{name}='{value}'"


def first_deploy_env() -> str:
    password_hash = os.environ.get("AFFICHE_SHOP_PASSWORD_HASH", "").strip()
    openai_key = os.environ.get("AFFICHE_OPENAI_API_KEY", "").strip()
    anthropic_key = os.environ.get("AFFICHE_ANTHROPIC_API_KEY", "").strip()
    cap = os.environ.get("AFFICHE_SPEND_CAP_USD", "15").strip()
    missing = [name for name, value in (("AFFICHE_SHOP_PASSWORD_HASH", password_hash),
                                        ("AFFICHE_OPENAI_API_KEY", openai_key)) if not value]
    if missing:
        raise SystemExit("First deploy: set " + ", ".join(missing) + " in this shell (deploy/README.md)")
    if not password_hash.startswith("$argon2"):
        raise SystemExit("AFFICHE_SHOP_PASSWORD_HASH must be an Argon2 hash (deploy/README.md), never a password")
    try:
        if not Decimal(cap) > 0:
            raise InvalidOperation
    except InvalidOperation:
        raise SystemExit("AFFICHE_SPEND_CAP_USD must be a positive number of dollars") from None
    lines = [single_quoted("SHOP_PASSWORD_HASH", password_hash), single_quoted("OPENAI_API_KEY", openai_key)]
    if anthropic_key:  # without it the planner is off: no saved style can be made from a reference poster
        lines.append(single_quoted("ANTHROPIC_API_KEY", anthropic_key))
    # The cap counts from the first deploy's UTC day. A later day is refused by the application (config.py).
    lines += [single_quoted("SPEND_CAP_USD", cap),
              single_quoted("SPEND_CAP_SINCE", datetime.now(UTC).date().isoformat())]
    return "\n".join(lines) + "\n"


status = git("status", "--porcelain", "--untracked-files=all", "--", *GUARD_PATHS)
assert status.returncode == 0, status.stderr
if status.stdout.strip():
    raise SystemExit("Uncommitted or untracked deploy inputs; commit them first (the deploy ships HEAD only):\n"
                     + status.stdout)
fetched = git("fetch", "origin", "main")
if fetched.returncode != 0:
    raise SystemExit("git fetch origin main failed; the deploy ships only what is on origin/main:\n" + fetched.stderr)
if git("merge-base", "--is-ancestor", "HEAD", "origin/main").returncode != 0:
    raise SystemExit("HEAD is not on origin/main: push it first (the box must run what the repository holds).")

rev = git("log", "-1", "--format=%H", "--", *IMAGE_PATHS)
assert rev.returncode == 0 and rev.stdout.strip(), rev.stderr
REV = rev.stdout.strip()

server.shell(
    name="Directories: app root, secrets (root only), backups (the container's user)",
    commands=[
        f"""install -d -m 755 {REMOTE_DIR}
install -d -m 700 {REMOTE_DIR}/secrets
install -d -m 700 -o 10001 -g 10001 {REMOTE_DIR}/backups"""
    ],
    _sudo=True,
)

has_secrets = host.get_fact(
    Command, command=f"test -f {REMOTE_DIR}/secrets/app.env && echo yes || echo no", _sudo=True
)
if (has_secrets or "").strip() != "yes":
    server.shell(
        name="First-deploy staging directory (deploy user only)",
        commands=[f"install -d -m 700 {STAGING}"],
    )
    # No _sudo: with sudo, pyinfra uploads through a default-mode file in /tmp, then copies it.
    # As the deploy user, SFTP writes straight into the 700 staging directory.
    files.put(
        name="Upload first-deploy settings (from the local shell, never on a command line)",
        src=StringIO(first_deploy_env()),
        dest=STAGED_ENV,
    )
server.shell(
    name="Secrets: create once, never replace",
    commands=[
        f"""set -e
{LOCK}
cd {REMOTE_DIR}/secrets
umask 077
if [ -f app.env ]; then rm -f {STAGED_ENV}; exit 0; fi
cp {STAGED_ENV} app.env.tmp
mv app.env.tmp app.env
rm -f {STAGED_ENV}"""
    ],
    _sudo=True,
)

# pyinfra's sudo upload ends with `cp`, which truncates the target in place: stage under per-run
# names, then promote with `mv` under the lock, so cron never runs a half-written script.
# Cron ignores /etc/cron.d names that contain a dot, so the staged entry is inert.
STAGED = {
    f"{REMOTE_DIR}/daily.sh": (committed("deploy/daily.sh"), "700"),
    f"{REMOTE_DIR}/verify.sh": (committed("deploy/verify.sh"), "700"),
    "/etc/cron.d/affiche-ia": (StringIO(CRON_LINE), "644"),
}
for dest, (src, mode) in STAGED.items():
    files.put(
        name=f"Stage {dest} (from HEAD)",
        src=src,
        dest=f"{dest}.{RUN}",
        user="root",
        group="root",
        mode=mode,
        _sudo=True,
    )
server.shell(
    name="Promote daily.sh, verify.sh and the cron entry",
    commands=[f"set -e\n{LOCK}\n" + "\n".join(f"mv -f {dest}.{RUN} {dest}" for dest in STAGED)],
    _sudo=True,
)

INSPECT = (
    "docker inspect -f '{{.State.Status}} "
    '{{index .Config.Labels "org.opencontainers.image.revision"}}\' '
    + CONTAINER
    + " 2>/dev/null || true"
)
running = host.get_fact(Command, command=INSPECT, _sudo=True) or ""

if running.strip() == f"running {REV}":
    print(f"affiche-ia {REV[:12]} already running: no upload, no build, no restart.")
else:
    archive_name = f"build-{REV}-{RUN}.tar.gz"  # per invocation: no concurrent deploy touches it
    archive = REPO / "deploy" / archive_name
    # core.autocrlf=false: LF files on the box whatever this machine's git setting.
    archived = git("-c", "core.autocrlf=false", "archive", "--format=tar.gz", "-o", str(archive), "HEAD", "--",
                   *IMAGE_PATHS)
    assert archived.returncode == 0, archived.stderr

    server.shell(
        name="Prechecks: affiche_ia_edge network and 5 GB free for the build",
        commands=[
            """set -e
if ! docker network inspect affiche_ia_edge >/dev/null 2>&1; then
  echo "affiche_ia_edge missing: deploy Maizina with it first."
  echo "Never create it by hand (deploy/README.md)."
  exit 1
fi
avail=$(df --output=avail -k /var/lib/docker | tail -1)
if [ "$avail" -lt 5242880 ]; then
  echo "Only $((avail / 1024)) MB free under /var/lib/docker; 5 GB needed (the image is about 2 GB)"
  exit 1
fi"""
        ],
        _sudo=True,
    )
    files.put(
        name="Upload build context (git archive of the image inputs at HEAD)",
        src=str(archive),
        dest=f"{REMOTE_DIR}/{archive_name}",
        _sudo=True,
    )
    archive.unlink()
    server.shell(
        name=f"Build, check, back up and start revision {REV[:12]}",
        commands=[
            f"""set -e
{LOCK}
cd {REMOTE_DIR}
export REVISION={REV}
# Recheck under the lock: a concurrent deploy may have released this revision meanwhile.
if [ "$({INSPECT})" = "running {REV}" ]; then
  rm -f {archive_name}
  echo "{REV[:12]} already running"
  exit 0
fi
rm -rf app.new
mkdir app.new
tar -xzf {archive_name} -C app.new
{COMPOSE_NEW} build
{COMPOSE_NEW} run --rm --no-deps affiche-ia python -c '{CHECK}'
# From here the service is down until the new container is up. SQLite has one writer: the old container is
# stopped (it finishes a running paid generation first, 5 minutes at most), then the data is backed up
# with the new code, then the new container starts and applies its migrations.
old=$(docker ps -q -f name=^{CONTAINER}$)
if [ -n "$old" ]; then docker stop -t 300 {CONTAINER}; fi
if {COMPOSE_NEW} run --rm --no-deps affiche-ia test -f /data/affiche.db; then
  if ! {COMPOSE_NEW} run --rm --no-deps affiche-ia python -m affiche.backup /backups; then
    echo "Backup before the release FAILED. Nothing was changed; the previous container is started again."
    if [ -n "$old" ]; then docker start {CONTAINER}; fi
    exit 1
  fi
else
  echo "No database yet (first deploy): nothing to back up."
fi
rm -rf app
mv app.new app
if ! docker compose -f app/deploy/compose.yml up -d --wait --wait-timeout 180 affiche-ia; then
  echo "The new container did not become healthy. THE SERVICE IS DOWN. Its last lines:"
  docker logs --tail=80 {CONTAINER} 2>&1 || true
  echo "Code-only release: git checkout <previous commit>; cd deploy; pyinfra 89.167.56.26 deploy.py --user deploy -y; git checkout -"
  echo "Release with a migration: fix forward, or restore the backup taken just before (deploy/README.md, Restore)."
  exit 1
fi
rm -f {archive_name}
docker image prune -af --filter label=app=affiche-ia --filter until=1h"""
        ],
        _sudo=True,
    )
    server.shell(
        name="Back up the running revision (daily.sh)",
        commands=[f"sh {REMOTE_DIR}/daily.sh"],
        _sudo=True,
    )

server.shell(
    name="Verify container, renderer, neighbours, public URL, cron and backup (300 s limit)",
    commands=[
        f"""timeout --kill-after=10s 300 sh {REMOTE_DIR}/verify.sh {REV}; rc=$?
if [ "$rc" = 124 ] || [ "$rc" = 137 ]; then
  echo "Verification timed out after 300 s"
  docker logs --tail=80 {CONTAINER} 2>&1
  echo "Rollback (code-only releases): git checkout <previous commit>; cd deploy;"
  echo "  pyinfra 89.167.56.26 deploy.py --user deploy -y; then git checkout -"
fi
exit $rc"""
    ],
    _sudo=True,
)
