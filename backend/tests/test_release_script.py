"""deploy/release.sh, the release step on the box (multi-shop design, Release gate), run with a fake docker first on
PATH. The fake accepts only the calls the release makes, each with its exact arguments, and fails on any other. A
container's command really runs, with /data and /backups mapped to test folders and a stand-in for the image's
python, so that a failure inside the container's shell reaches the script as it would on the box. test_restore_script.py
runs deploy/restore.sh with the same fakes.
Docker is not on this machine; the real image's rehearsal is proven only by the evidence lines of the release."""
import io
import json
import os
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest

DEPLOY = Path(__file__).resolve().parents[2] / "deploy"
SCRIPT = DEPLOY / "release.sh"
REV = "a" * 40
OLD = "0123456789ab"  # the old container's id
FAKE_DOCKER = r"""#!/bin/sh
# Docker on the box as release.sh and restore.sh call it. FAKE_DOCKER_FAIL names the call that fails in docker
# itself, before any container runs, as <name> (exit 1) or <name>:<status>: inspect, build, stop, copy (restore.sh's
# docker run), run1, run2, run3, run4 (the compose runs, in order), up.
C=affiche-ia-affiche-ia-1
LABEL='{{index .Config.Labels "org.opencontainers.image.revision"}}'
log() { printf '%s\n' "$*" >> "$FAKE_LOG"; }
unexpected() { log "UNEXPECTED docker $*"; echo "fake docker: unexpected call: $*" >&2; exit 99; }
daemon() {
  case "${FAKE_DOCKER_FAIL:-}" in
    "$1") echo "Error response from daemon: fake failure of $1" >&2; exit 1 ;;
    "$1":*) exit "${FAKE_DOCKER_FAIL#*:}" ;;
  esac
}
# A container's command: its /data and /backups are the test's folders, its python the stand-in.
contained() {
  count=$#
  while [ "$count" -gt 0 ]; do
    mapped=$(printf '%s' "$1" | sed -e "s#/data#$FAKE_DATA#g" -e "s#/backups#$FAKE_BACKUPS#g")
    shift
    set -- "$@" "$mapped"
    count=$((count - 1))
  done
  PATH="$FAKE_IMAGE:/usr/bin:/bin" exec "$@"
}
case "$1" in
  inspect)
    [ "$#" = 4 ] && [ "$2" = -f ] && [ "$4" = "$C" ] || unexpected "$@"
    log inspect
    daemon inspect
    case "$3" in
      "{{.State.Status}} $LABEL") echo "running 0123456789abcdef" ;;
      "$LABEL") echo "$FAKE_REV" ;;
      *) unexpected "$@" ;;
    esac
    exit 0 ;;
  ps)
    case "$*" in
      "ps -q -f name=^$C\$") log ps; [ -z "${FAKE_OLD:-}" ] || echo "$FAKE_OLD" ;;
      "ps -aq -f name=^affiche-ia-backup\$") log left; daemon left; [ -z "${FAKE_LEFT:-}" ] || echo "$FAKE_LEFT" ;;
      *) unexpected "$@" ;;
    esac
    exit 0 ;;
  rm) [ "$*" = "rm -f affiche-ia-backup" ] || unexpected "$@"; log rm; daemon rm; exit 0 ;;
  stop) [ "$*" = "stop -t 300 $C" ] || unexpected "$@"; log stop; daemon stop; exit 0 ;;
  start) [ "$*" = "start $C" ] || unexpected "$@"; log start; exit 0 ;;
  logs) [ "$*" = "logs --tail=80 $C" ] || unexpected "$@"; log logs; exit 0 ;;
  image) [ "$*" = "image prune -af --filter label=app=affiche-ia --filter until=1h" ] || unexpected "$@"; log prune; exit 0 ;;
  run)
    shift
    [ "$1 $2 $3 $4 $5 $6 $7 $8 $9" = "--rm -u 10001:10001 -v affiche-ia_data:/data -v $FAKE_BOX/backups:/backups:ro --entrypoint sh" ] \
      || unexpected run "$@"
    shift 9
    [ "$#" = 6 ] && [ "$1" = "affiche-ia:$FAKE_REV" ] && [ "$2" = -c ] && [ "$4" = restore ] || unexpected run "$@"
    log copy
    daemon copy
    shift
    contained sh "$@" ;;
  compose) [ "$2" = -f ] || unexpected "$@" ;;
  *) unexpected "$@" ;;
esac
file=$3
shift 3
case "$file $*" in
  "app.new/deploy/compose.yml build") [ -f "$file" ] || unexpected compose build; log build; daemon build; exit 0 ;;
  "app/deploy/compose.yml up -d --wait --wait-timeout 180 affiche-ia")
    [ -f "$file" ] && [ ! -e app.new ] || unexpected compose up; log up; daemon up; exit 0 ;;
  "app.new/deploy/compose.yml run --rm --no-deps affiche-ia "?*) shift 4 ;;
  "app.new/deploy/compose.yml run --rm --no-deps --name affiche-ia-backup affiche-ia sh -c "*"affiche.backup"*) shift 6 ;;
  "app/deploy/compose.yml run --rm operator "?*) [ -f "$file" ] || unexpected compose run; shift 3 ;;
  *) unexpected compose -f "$file" "$@" ;;
esac
n=$(( $(grep -c '^run' "$FAKE_LOG") + 1 ))
log "run$n $1 $2 $3"
daemon "run$n"
[ "$REVISION" = "$FAKE_REV" ] || unexpected "run with REVISION=$REVISION"
contained "$@"
"""
# coreutils timeout, around the steps that keep the service down: recorded, then the command runs at once. A hung step
# is simulated by the fake docker returning the timeout's status, never by waiting.
FAKE_TIMEOUT = r"""#!/bin/sh
while case "$1" in -*) true ;; *) false ;; esac; do shift; done
printf 'timeout %s\n' "$1" >> "$FAKE_LOG"
shift
exec "$@"
"""
# The image's python, for the uses the two scripts make of it; any other call fails the test.
FAKE_PYTHON = r"""#!/bin/sh
if [ "$#" = 2 ] && [ "$1" = -c ]; then
  case "$2" in
    "from affiche.config import load_settings; "*'print("configuration ok")') echo "configuration ok"; exit 0 ;;
    'from affiche import runtime; from affiche.config import load_settings; runtime.start(load_settings(), "api"); '*)
      [ -f "$FAKE_DATA/affiche.db" ] || exit 98
      if [ "${FAKE_START:-ok}" = ok ]; then echo "the application started once"; exit 0; fi
      echo "RuntimeError: a migration left a reference to a missing row; nothing was applied" >&2
      exit 1 ;;
  esac
elif [ "$*" = "-m affiche.rehearse $FAKE_DATA/affiche.db" ] && [ -f "$3" ]; then
  echo "environment: SQLite 3.40.1, Python 3.12.13, revision $REVISION"
  if [ "${FAKE_REHEARSAL:-ok}" = ok ]; then echo "REHEARSAL OK"; exit 0; fi
  echo "REHEARSAL FAILED: poster_calls: 72 -> 71 rows, different content"
  exit 1
elif [ "$*" = "-m affiche.backup $FAKE_BACKUPS" ] && [ -f "$FAKE_DATA/affiche.db" ]; then
  if [ "${FAKE_BACKUP:-ok}" = ok ]; then cp "$FAKE_DATA/affiche.db" "$3/affiche-backup.db"; echo "backup ok"; exit 0; fi
  echo "backup FAILED: OSError: [Errno 28] No space left on device" >&2
  exit 1
elif [ "$*" = "-m affiche.shops end-sessions --all" ]; then
  echo "2 sessions ended (every shop); 1 operator sessions ended"
  exit 0
elif [ "$*" = "-m affiche.shops list" ]; then
  if [ -n "${FAKE_PRE0013:-}" ]; then printf '1\toriginalphone\tactive\tno password\t2026-11-13\tOriginal Phone Mada\n'; exit 0; fi
  printf '1\toriginalphone\tactive\tpassword\t2026-11-13\tOriginal Phone Mada\n2\tboutiquedeux\tsuspended\tpassword\t2026-11-15\tB\n'
  exit 0
elif [ "$#" = 4 ] && [ "$1 $2 $3" = "-m affiche.shops after-restore" ] \
    && case "$4" in "$FAKE_DATA"/affiche.db.before-restore-*Z) true ;; *) false ;; esac; then
  if [ ! -f "$4" ]; then echo "refused: no kept database at $4: nothing to copy: the restore's loss policy applies" >&2; exit 1; fi
  if [ "${FAKE_AFTER_RESTORE:-ok}" = ok ]; then echo "to copy: line 7 of the kept database (originalphone grant 'MV-1')"; exit 0; fi
  echo "refused: the kept database $4 cannot be read (file is not a database)" >&2
  exit 1
fi
printf 'UNEXPECTED python %s\n' "$*" >> "$FAKE_LOG"
exit 99
"""


def executable(path: Path, text: str):
    path.parent.mkdir(exist_ok=True)
    path.write_text(text)
    path.chmod(0o755)


def on_box(tmp_path, argv, *, old=OLD, **fake):
    """Runs a script with the fakes first on PATH; /opt is the box's folder, /data and /backups the container's.
    Returns (exit code, output, the docker and timeout calls in order, as names)."""
    executable(tmp_path / "bin" / "docker", FAKE_DOCKER)
    executable(tmp_path / "bin" / "timeout", FAKE_TIMEOUT)
    executable(tmp_path / "image" / "python", FAKE_PYTHON)
    log = tmp_path / "docker.log"
    env = {"PATH": f"{tmp_path / 'bin'}{os.pathsep}{os.environ['PATH']}", "FAKE_LOG": str(log), "FAKE_OLD": old,
           "FAKE_IMAGE": str(tmp_path / "image"), "FAKE_DATA": str(tmp_path / "data"), "FAKE_REV": REV,
           "FAKE_BACKUPS": str(tmp_path / "backups"), "FAKE_BOX": str(tmp_path / "opt")} | {
        f"FAKE_{name.upper()}": value for name, value in fake.items()}
    done = subprocess.run(["sh", *map(str, argv)], env=env, capture_output=True, text=True, timeout=60)
    calls = log.read_text().splitlines() if log.exists() else []
    assert not [call for call in calls if call.startswith("UNEXPECTED")], calls
    return done.returncode, done.stdout + done.stderr, [call.split()[0] for call in calls]


def release(tmp_path, *, database=True, **fake):
    """release.sh as deploy.py runs it, on a box with a running release in app/ and the new one's archive."""
    box, data, backups = tmp_path / "opt", tmp_path / "data", tmp_path / "backups"
    for folder in (box / "app" / "deploy", data, backups):
        folder.mkdir(parents=True)
    (box / "app" / "deploy" / "compose.yml").write_text("the running release\n")
    if database:
        (data / "affiche.db").write_bytes(b"live database")
    with tarfile.open(box / "build.tar.gz", "w:gz") as archive:
        compose = b"the new release\n"
        entry = tarfile.TarInfo("deploy/compose.yml")
        entry.size = len(compose)
        archive.addfile(entry, io.BytesIO(compose))
    return on_box(tmp_path, [SCRIPT, REV, "build.tar.gz", box], **fake)


def running_release(tmp_path):
    return (tmp_path / "opt" / "app" / "deploy" / "compose.yml").read_text()


def test_a_passing_rehearsal_comes_before_the_stop_the_backup_and_the_start(tmp_path):
    code, output, calls = release(tmp_path)
    assert code == 0, output
    # inspect (already running?), build, configuration check, rehearsal, ps, stop, check and backup under its deadline,
    # up, prune.
    assert calls == ["inspect", "build", "run1", "run2", "ps", "stop", "timeout", "run3", "up", "prune"], output
    assert f"revision {REV}" in output and "configuration ok" in output  # REVISION is exported for compose
    report = (tmp_path / "opt" / "last-rehearsal.txt").read_text()  # pyinfra hides the output of a command that passes
    assert "environment: SQLite 3.40.1" in report and "REHEARSAL OK" in report
    assert (tmp_path / "backups" / "affiche-backup.db").read_bytes() == b"live database"  # backed up before up
    assert running_release(tmp_path) == "the new release\n" and not (tmp_path / "opt" / "build.tar.gz").exists()


@pytest.mark.parametrize("fake", [{"rehearsal": "failed"}, {"docker_fail": "run2"}, {"docker_fail": "build"},
                                  {"docker_fail": "run1"}],
                         ids=["the rehearsal fails", "docker fails to run it", "the build fails", "the check fails"])
def test_a_failed_rehearsal_build_or_check_stops_before_anything_is_stopped(tmp_path, fake):
    code, output, calls = release(tmp_path, **fake)
    assert code == 1, output
    assert "ps" not in calls and "stop" not in calls and "run3" not in calls and "up" not in calls
    assert "start" not in calls and running_release(tmp_path) == "the running release\n"
    assert not list((tmp_path / "backups").iterdir())
    if "rehearsal" in fake:  # Python's failure inside the container's shell reached the script
        assert "REHEARSAL FAILED: poster_calls: 72 -> 71 rows" in output  # the report itself is shown by pyinfra
    if "rehearsal" in fake or fake["docker_fail"] == "run2":
        assert "Rehearsal FAILED: nothing was changed, the service still runs." in output


@pytest.mark.parametrize("fake", [{"docker_fail": "run3"}, {"backup": "failed"}],
                         ids=["docker fails to run the check and backup", "the backup fails"])
def test_a_failed_backup_starts_the_old_container_again_and_never_the_new_one(tmp_path, fake):
    """R-MULTI-SHOP-005: a backup is taken before the migration runs on the real database. No failure of the check and
    backup, docker's own included, passes for a first deploy: the new container, which migrates, is never started."""
    code, output, calls = release(tmp_path, **fake)
    assert code == 1, output
    assert calls == ["inspect", "build", "run1", "run2", "ps", "stop", "timeout", "run3", "rm", "left", "timeout", "start"], output
    assert "Backup before the release FAILED (exit 1). Nothing was changed: the new version was not started." in output
    assert "The previous container is started again." in output and "No database yet" not in output
    assert "timeout" not in output and running_release(tmp_path) == "the running release\n"


@pytest.mark.parametrize("fake", [{"left": "f00d"}, {"docker_fail": "left"}, {"docker_fail": "rm", "left": "f00d"}],
                         ids=["it survives", "docker cannot say", "docker cannot remove it"])
def test_a_backup_container_that_outlives_its_deadline_keeps_everything_stopped(tmp_path, fake):
    """The deadline ends the docker client, not always the container: while one may still read the database or write
    backup files, nothing is started and the operator is told the two commands."""
    code, output, calls = release(tmp_path, backup="failed", **fake)
    assert code == 1, output
    assert calls[-2:] == ["rm", "left"] and "start" not in calls and "up" not in calls, output
    assert ("THE SERVICE IS DOWN: the backup container affiche-ia-backup could not be removed. Remove it (sudo docker "
            "rm -f affiche-ia-backup), then: sudo docker start affiche-ia-affiche-ia-1") in output
    assert running_release(tmp_path) == "the running release\n"


@pytest.mark.parametrize("status", ["124", "137"])
def test_a_hung_backup_ends_at_its_deadline_and_starts_the_old_container_again(tmp_path, status):
    """The downtime after the stop is bounded: coreutils timeout ends the check and backup (124, or 137 once killed)."""
    code, output, calls = release(tmp_path, docker_fail=f"run3:{status}")
    assert code == 1, output
    assert calls == ["inspect", "build", "run1", "run2", "ps", "stop", "timeout", "run3", "rm", "left", "timeout", "start"], output
    assert "Backup before the release FAILED: no answer within 900 s (timeout)." in output
    assert f"Backup before the release FAILED (exit {status})." in output and "The previous container is started again." in output
    assert running_release(tmp_path) == "the running release\n"


def test_without_a_database_the_release_starts_without_a_backup_and_says_so(tmp_path):
    code, output, calls = release(tmp_path, database=False, old="")  # a first deploy: no container, no database
    assert code == 0, output
    assert calls == ["inspect", "build", "run1", "run2", "ps", "timeout", "run3", "up", "prune"], output
    assert "No database yet (first deploy): nothing to rehearse." in output
    assert "No database yet (first deploy): nothing to back up." in output
    assert not list((tmp_path / "backups").iterdir()) and running_release(tmp_path) == "the new release\n"


def test_the_box_runs_the_committed_scripts():
    """deploy.py uploads deploy/release.sh from HEAD (committed(), as daily.sh and verify.sh) under this run's own name,
    and installs restore.sh the same way. deploy/ is a guarded input, so an uncommitted change stops the deploy."""
    source = (DEPLOY / "deploy.py").read_text(encoding="utf-8")
    assert 'GUARD_PATHS = [*IMAGE_PATHS, "deploy"]' in source
    assert 'src=committed("deploy/release.sh"),\n        dest=RELEASE,' in source
    assert 'RELEASE = f"{REMOTE_DIR}/release.sh.{RUN}"' in source
    assert """commands=[f'sh {RELEASE} {REV} {archive_name} {REMOTE_DIR}; rc=$?; rm -f {RELEASE}; exit "$rc"'],""" in source
    assert 'f"{REMOTE_DIR}/restore.sh": (committed("deploy/restore.sh"), "700"),' in source


def test_a_wrong_command_line_does_nothing(tmp_path):
    done = subprocess.run(["sh", str(SCRIPT), REV], capture_output=True, text=True, timeout=10, cwd=tmp_path)
    assert done.returncode == 2 and "usage" in done.stdout and list(tmp_path.iterdir()) == []


def compose_file():
    """deploy/compose.yml as data. PyYAML is not a dependency of the backend: the system's python3 reads it when it has
    PyYAML (6.0.3 on the Linux development machine), else the test is skipped and says so."""
    text = (DEPLOY / "compose.yml").read_text(encoding="utf-8")
    try:
        import yaml
        return yaml.safe_load(text)
    except ImportError:
        pass
    system = shutil.which("python3", path="/usr/bin:/bin")
    done = system and subprocess.run([system, "-I", "-c", "import json, sys, yaml; print(json.dumps(yaml.safe_load("
                                      "sys.stdin.read())))"], input=text, capture_output=True, text=True, timeout=30)
    if not done or done.returncode != 0:
        pytest.skip("no PyYAML here: deploy/compose.yml could not be read as YAML")
    return json.loads(done.stdout)


def test_the_operator_service_is_the_service_without_its_log_network_or_start():
    """The operator's one-offs (python -m affiche.shops, restore.sh): the same image (so the same user), data and
    settings as the service; no container log, so a printed password never reaches the journal; no network; a profile,
    so `up` never starts it; no build, so a release never builds it."""
    services = compose_file()["services"]
    service, operator = services["affiche-ia"], services["operator"]
    assert operator["logging"] == {"driver": "none"} and service["logging"]["driver"] == "journald"
    assert operator["profiles"] == ["operator"] and "profiles" not in service
    assert operator["network_mode"] == "none" and "build" not in operator and "restart" not in operator
    shared = {key: value for key, value in service.items()
              if key not in ("build", "restart", "stop_grace_period", "logging", "networks")}
    assert shared == {key: value for key, value in operator.items() if key not in ("profiles", "logging", "network_mode")}
    assert {"image", "volumes", "env_file", "environment", "read_only"} <= shared.keys() and "user" not in shared
