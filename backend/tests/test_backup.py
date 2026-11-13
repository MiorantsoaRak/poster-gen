import json
import shutil
import sqlite3
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from affiche import assets, backup
from affiche.db import make_engine, migrate, write_tx


@pytest.fixture
def data(tmp_path):
    data_dir = tmp_path / "data"
    engine = make_engine(data_dir)
    migrate(engine)
    sha = assets.put(data_dir, b"poster bytes", "png")
    with write_tx(engine) as conn:
        assets.record(conn, sha=sha, kind="original", mime="image/png", width=1, height=1, size=12)
    yield data_dir, engine, sha
    engine.dispose()


def test_a_backup_taken_during_a_write_is_consistent_and_restores_the_same_bytes(data, tmp_path):
    data_dir, engine, sha = data
    folder = tmp_path / "backups"
    (data_dir / "assets" / sha[:2] / "half-written.tmp").write_bytes(b"x")
    with write_tx(engine) as conn:  # an open write transaction: its row must not be in the copy
        conn.exec_driver_sql("INSERT INTO meta (key,value) VALUES ('uncommitted','1')")
        summary = backup.run(data_dir, folder)
    assert summary["asset_files"] == 1 and summary["assets_copied"] == 1
    assert json.loads((folder / "last-backup.json").read_text(encoding="utf-8")) == summary
    assert not list(folder.rglob("*.tmp")) and not list(folder.rglob("*.partial"))

    # Restore as the runbook says: one database copy as affiche.db, the assets back.
    restored = tmp_path / "restored"
    restored.mkdir()
    shutil.copyfile(folder / "db" / summary["db_file"], restored / "affiche.db")
    shutil.copytree(folder / "assets", restored / "assets")
    engine_2 = make_engine(restored)
    try:
        with engine_2.connect() as conn:
            assert conn.exec_driver_sql("PRAGMA integrity_check").scalar_one() == "ok"
            assert conn.exec_driver_sql("SELECT count(*) FROM meta WHERE key='uncommitted'").scalar_one() == 0
            assert assets.load(conn, restored, sha) == b"poster bytes"
            assert (conn.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one()
                    == engine.connect().exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one())
    finally:
        engine_2.dispose()


def test_assets_are_copied_once_and_never_overwritten(data, tmp_path):
    data_dir, _, sha = data
    folder = tmp_path / "backups"
    backup.run(data_dir, folder, now=datetime(2026, 11, 1, tzinfo=UTC))
    saved = folder / "assets" / sha[:2] / f"{sha}.png"
    assets.path(data_dir, sha, "png").write_bytes(b"damaged on the live disk")
    again = backup.run(data_dir, folder, now=datetime(2026, 11, 2, tzinfo=UTC))
    assert again["assets_copied"] == 0 and saved.read_bytes() == b"poster bytes"


def test_database_copies_are_kept_14_days_and_the_newest_always_stays(data, tmp_path):
    data_dir, _, _ = data
    folder = tmp_path / "backups"
    first = datetime(2026, 10, 1, 0, 40, tzinfo=UTC)
    for day in (0, 1, 13, 14, 15):
        backup.run(data_dir, folder, now=first + timedelta(days=day))
    names = sorted(file.name for file in (folder / "db").iterdir())
    assert names == ["affiche-20261002T004000Z.db", "affiche-20261014T004000Z.db", "affiche-20261015T004000Z.db",
                     "affiche-20261016T004000Z.db"]
    # A long silence: the next run deletes the old copies but its own copy remains.
    backup.run(data_dir, folder, now=first + timedelta(days=90))
    assert [file.name for file in (folder / "db").iterdir()] == ["affiche-20261230T004000Z.db"]


def test_a_failure_exits_1_and_leaves_the_last_backup_marker_untouched(data, tmp_path, monkeypatch, capsys):
    data_dir, _, _ = data
    folder = tmp_path / "backups"
    # The command reads DATA_DIR through the settings; the real backend/.env must not be read by a test.
    monkeypatch.setattr("affiche.config.load_settings", lambda: SimpleNamespace(data_dir=data_dir))
    assert backup.main(["backup", str(folder)]) == 0
    marker = (folder / "last-backup.json").read_text(encoding="utf-8")

    class Broken:
        def backup(self, target):
            raise sqlite3.OperationalError("disk I/O error")

        def close(self):
            pass

    real = sqlite3.connect
    monkeypatch.setattr(backup.sqlite3, "connect", lambda target, **kw: Broken() if kw.get("uri") else real(target, **kw))
    assert backup.main(["backup", str(folder)]) == 1
    assert "backup FAILED: OperationalError: disk I/O error" in capsys.readouterr().err
    assert (folder / "last-backup.json").read_text(encoding="utf-8") == marker
    # The failed copy is not a backup, and the next good run clears it.
    assert len(list((folder / "db").glob("affiche-*.db"))) == 1
    monkeypatch.setattr(backup.sqlite3, "connect", real)
    assert backup.main(["backup", str(folder)]) == 0
    assert not list(folder.rglob("*.partial*"))


def test_no_database_is_an_error_not_an_empty_backup(tmp_path):
    with pytest.raises(FileNotFoundError):
        backup.run(tmp_path / "nothing", tmp_path / "backups")
    assert not (tmp_path / "backups").exists()
