"""deploy/restore.sh with the strict fake docker of test_release_script.py: every step in order, a failure at any step
stops it before the next with the state the service and the data are in, and it never starts the service."""
import shutil

import pytest

from test_release_script import DEPLOY, REV, executable, on_box

FILE = "affiche-20261116T004000Z.db"
# image, stop, backup in place, start once, sessions, list, the credit report
STEPS = ["inspect", "stop", "copy", "run1", "run2", "run3", "run4"]
START = "sudo docker start affiche-ia-affiche-ia-1"


def restore(tmp_path, file=FILE, prepare=None, **fake):
    """The script as deploy.py installs it, beside backups/ and app/ on the box, which the container sees as /backups;
    the volume holds a live database with its write-ahead file."""
    box, data = tmp_path / "opt", tmp_path / "data"
    backups = box / "backups"
    for folder in (box / "app" / "deploy", data / "assets", backups / "db", backups / "assets"):
        folder.mkdir(parents=True)
    (box / "app" / "deploy" / "compose.yml").write_text("the running release\n")
    shutil.copy(DEPLOY / "restore.sh", box / "restore.sh")
    (backups / "db" / FILE).write_bytes(b"the backup")
    (backups / "assets" / "new.png").write_bytes(b"png")
    (data / "affiche.db").write_bytes(b"live database")
    (data / "affiche.db-wal").write_bytes(b"live wal")
    if prepare:
        prepare(tmp_path)
    return on_box(tmp_path, [box / "restore.sh", file], backups=str(backups), **fake)


def test_a_restore_runs_every_step_in_order_and_leaves_the_service_stopped(tmp_path):
    code, output, calls = restore(tmp_path)
    assert code == 0, output
    assert calls == STEPS, output  # never a start
    data = tmp_path / "data"
    assert (data / "affiche.db").read_bytes() == b"the backup" and (data / "assets" / "new.png").exists()
    # The database it replaced is kept whole under this run's own name, its write-ahead file with it.
    before, = data.glob("affiche.db.before-restore-*Z")
    assert before.read_bytes() == b"live database" and f"The database it replaced is /data/{before.name} in the volume" in output
    assert (data / f"{before.name}-wal").read_bytes() == b"live wal" and not (data / "affiche.db-wal").exists()
    assert "2 sessions ended (every shop)" in output and "2\tboutiquedeux\tsuspended\tpassword" in output
    # The report reads the database set aside, by the path the operator service sees, after the shops list.
    assert ("2\tboutiquedeux\tsuspended\tpassword\t2026-11-15\tB\nto copy: line 7 of the kept database (originalphone "
            f"grant 'MV-1')\nRESTORED: {FILE} is in place, at this version, with every session ended. THE SERVICE IS "
            "STOPPED.") in output
    for repair in ("create <identifier>", "set-password <identifier>", "suspend <identifier> --yes"):
        assert repair in output
    assert ("  each shop created:     the line that after-restore printed for it (python -m affiche.shops create ... "
            "--welcome 0), else create <identifier> --name \"<name>\" --welcome 0\n"
            f"  then the credit lines: after-restore /data/{before.name} --apply (copies them back in their order, with "
            "their dates; nothing while a shop is missing)\n") in output
    assert "  a pause set since:     pause --yes; a purchase text set since: purchase-text \"<text>\"\n" in output
    assert "THE CREDIT REPORT FAILED" not in output
    assert (f"sudo env REVISION={REV} docker compose -f {tmp_path / 'opt'}/app/deploy/compose.yml run --rm operator "
            "python -m affiche.shops <command>") in output
    assert f"Then start the service: {START}" in output and "has no password" not in output


def test_a_backup_from_before_0013_names_the_password_of_shop_1_among_the_repairs(tmp_path):
    code, output, calls = restore(tmp_path, pre0013="1")
    assert code == 0 and calls == STEPS, output
    assert ("originalphone has no password (a backup from before migration 0013): set-password originalphone, or put "
            "its hash back in /opt/affiche-ia/secrets/app.env as SHOP_PASSWORD_HASH; without either the service "
            "refuses to start") in output


@pytest.mark.parametrize(("fake", "reached", "message"), [
    ({"docker_fail": "inspect"}, "inspect",
     "no container affiche-ia-affiche-ia-1 to take the image from. the service still runs; nothing was changed."),
    ({"docker_fail": "stop"}, "stop", "docker stop affiche-ia-affiche-ia-1. the service may be stopped (sudo docker ps -a); "
                                      "the database was not replaced."),
    ({"docker_fail": "copy"}, "copy", "putting the backup in place. THE SERVICE IS STOPPED; the database may be partly "
                                      "replaced: the one before is /data/affiche.db.before-restore-"),
    ({"docker_fail": "run1"}, "run1", f"the application's start on the backup (migrations, checks). THE SERVICE IS "
                                      f"STOPPED; the database is the backup {FILE}, not yet brought to this version"),
    ({"start": "failed"}, "run1", f"the application's start on the backup (migrations, checks). THE SERVICE IS STOPPED; "
                                  f"the database is the backup {FILE}, not yet brought to this version"),
    ({"docker_fail": "run2"}, "run2", f"ending every session. THE SERVICE IS STOPPED; the database is the backup {FILE} at "
                                      "this version, its sessions not yet ended."),
    ({"docker_fail": "run3"}, "run3", f"listing the shops. THE SERVICE IS STOPPED; the database is the backup {FILE} at "
                                      "this version, with no session."),
], ids=["no container", "stop", "copy", "docker fails the start", "the migration fails", "sessions", "list"])
def test_a_failed_step_stops_the_restore_before_the_next_and_never_starts_the_service(tmp_path, fake, reached, message):
    code, output, calls = restore(tmp_path, **fake)
    assert code == 1, output
    assert calls == STEPS[:STEPS.index(reached) + 1], output  # nothing after the failed step, never a start
    assert f"RESTORE FAILED: {message}" in output and "RESTORED" not in output and START not in output


def no_database_before(tmp_path):
    for file in ("affiche.db", "affiche.db-wal"):
        (tmp_path / "data" / file).unlink()


@pytest.mark.parametrize("fake", [{"docker_fail": "run4"}, {"after_restore": "failed"}, {"prepare": no_database_before}],
                         ids=["docker fails to run it", "the kept database cannot be read", "nothing was replaced"])
def test_a_failed_credit_report_is_said_and_the_restore_still_ends_restored_and_stopped(tmp_path, fake):
    """The report only reads, and comes after the restore is done: its failure stops nothing and the closing list
    follows, with what to do about the credit lines."""
    code, output, calls = restore(tmp_path, **fake)
    assert code == 0 and calls == STEPS, output  # never a start
    assert ("THE CREDIT REPORT FAILED (above); the restore itself is done and nothing was copied. Run after-restore "
            "again (below); if the database it replaced cannot be read, redo the grants and corrections made since the "
            f"backup from your payment records.\nRESTORED: {FILE} is in place") in output
    assert "RESTORE FAILED" not in output and "then the credit lines: after-restore /data/affiche.db.before-restore-" in output
    assert (tmp_path / "data" / "affiche.db").read_bytes() == b"the backup"


def test_a_database_set_aside_earlier_is_never_overwritten(tmp_path):
    """Two restores in the same second would give what they set aside the same name: the second replaces nothing."""
    def same_second(tmp_path):
        executable(tmp_path / "bin" / "date", "#!/bin/sh\necho 20261116T010203Z\n")
        (tmp_path / "data" / "affiche.db.before-restore-20261116T010203Z").write_bytes(b"the first live database")
    code, output, calls = restore(tmp_path, prepare=same_second)
    assert code == 1 and calls == ["inspect", "stop", "copy"], output
    assert ("RESTORE FAILED: /data/affiche.db.before-restore-20261116T010203Z already exists (a restore made this same "
            "second): run the script again. THE SERVICE IS STOPPED; the database was not replaced.") in output
    data = tmp_path / "data"
    assert (data / "affiche.db.before-restore-20261116T010203Z").read_bytes() == b"the first live database"
    assert (data / "affiche.db").read_bytes() == b"live database" and (data / "affiche.db-wal").exists()


def test_an_asset_copy_cut_short_is_done_again_and_a_present_asset_is_left_alone(tmp_path):
    def cut_short(tmp_path):
        (tmp_path / "opt" / "backups" / "assets" / "ab").mkdir()
        (tmp_path / "opt" / "backups" / "assets" / "ab" / "deep.png").write_bytes(b"deep")
        (tmp_path / "opt" / "backups" / "assets" / "kept.png").write_bytes(b"from the backup")
        (tmp_path / "data" / "assets" / "new.png.tmp").write_bytes(b"p")  # what an interrupted run leaves
        (tmp_path / "data" / "assets" / "kept.png").write_bytes(b"already there")
    code, output, calls = restore(tmp_path, prepare=cut_short)
    assert code == 0 and calls == STEPS, output
    assets = tmp_path / "data" / "assets"
    assert (assets / "new.png").read_bytes() == b"png" and (assets / "ab" / "deep.png").read_bytes() == b"deep"
    assert (assets / "kept.png").read_bytes() == b"already there" and not list(assets.rglob("*.tmp"))


@pytest.mark.parametrize("file", ["../secrets/app.env", ".hidden", "affiche-missing.db"])
def test_a_wrong_backup_name_changes_nothing(tmp_path, file):
    code, output, calls = restore(tmp_path, file)
    assert (code, calls) == (1, []), output
    assert "RESTORE FAILED: " in output and output.rstrip().endswith("the service still runs; nothing was changed.")
    assert (tmp_path / "data" / "affiche.db").read_bytes() == b"live database"
