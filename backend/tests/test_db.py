import queue
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import exc, text

from affiche.db import make_engine, migrate, write_tx

DESIGN_TABLES = {"meta", "assets", "runs", "run_products", "abandonments", "variant_cycles", "cutouts",
                 "generation_requests", "provider_calls", "candidates", "shop_profile", "asset_access",
                 "product_inputs", "creations", "creation_versions", "mutation_keys", "sessions", "login_failures",
                 "poster_jobs", "poster_calls", "scene_plans", "poster_visuals", "text_proposals", "text_effects", "poster_renders", "confirmations", "looks"}
GUARD_WHERE = {
    "req_one_revision": "WHERE parent_id IS NOT NULL AND status IN ('running','succeeded')",
    "req_one_initial": "WHERE parent_id IS NULL AND status IN ('running','succeeded')",
}
WORKER = Path(__file__).with_name("tx_worker.py")


@pytest.fixture
def engine(tmp_path):
    engine = make_engine(tmp_path)
    migrate(engine)
    yield engine
    engine.dispose()


def test_migrate_creates_every_table_and_both_guards(engine):
    with engine.connect() as conn:
        tables = set(conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type = 'table'").scalars())
        guards = dict(conn.exec_driver_sql(
            "SELECT name, sql FROM sqlite_master WHERE type = 'index' AND name LIKE 'req_one_%'").all())
        product_columns = {name: notnull for _cid, name, _type, notnull, *_rest in
                           conn.exec_driver_sql("PRAGMA table_info(run_products)")}
    assert tables == DESIGN_TABLES | {"alembic_version"}
    assert {"name": 1, "variant": 1}.items() <= product_columns.items()  # 0002: the subject snapshot
    assert product_columns["photo_assets_json"] == 0  # 0003: NULL is unverified legacy provenance
    assert set(guards) == set(GUARD_WHERE)
    for name, where in GUARD_WHERE.items():
        sql = " ".join(guards[name].split())
        assert sql.startswith(f"CREATE UNIQUE INDEX {name} ") and sql.endswith(where)


def test_new_connection_has_wal_and_foreign_keys(engine):
    engine.dispose()  # the next connect opens a fresh DBAPI connection
    with engine.connect() as conn:
        assert conn.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
        assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1


def test_photo_snapshot_migration_preserves_legacy_rows_without_inventing_hashes(tmp_path, monkeypatch):
    engine = make_engine(tmp_path)
    upgrade = command.upgrade
    try:
        with monkeypatch.context() as patch:
            patch.setattr(command, "upgrade", lambda config, _revision: upgrade(config, "0002"))
            migrate(engine)
        with write_tx(engine) as conn:
            conn.exec_driver_sql("INSERT INTO runs VALUES ('old', 'model', 'high', '1088x1920', 3, 'on', 'now')")
            conn.exec_driver_sql("INSERT INTO run_products VALUES ('old', 'P1', 'A', 'old-sha', 'JBL', 'Blue')")
        migrate(engine)
        migrate(engine)  # startup replay
        with engine.connect() as conn:
            assert conn.exec_driver_sql("SELECT * FROM run_products").one() == (
                "old", "P1", "A", "old-sha", "JBL", "Blue", None)
            assert conn.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one() == "0011"
    finally:
        engine.dispose()


def _insert_initial_scene_request(conn, request_id):
    conn.execute(text(
        "INSERT INTO generation_requests (id, payload_hash, purpose, variant_ref, cycle_no, run_label,"
        " request_json, corrections_applied, owner, status, created_at)"
        " VALUES (:id, 'h', 'scene', 'v1', 1, 'r1', '{}', 0, 'cli', 'running', 'now')"), {"id": request_id})


def test_req_one_initial_allows_one_live_initial_request(engine):
    with write_tx(engine) as conn:
        conn.exec_driver_sql("INSERT INTO runs VALUES ('r1', 'model', 'high', '1024x1536', 3, 'on', 'now')")
        _insert_initial_scene_request(conn, "first")
    with pytest.raises(exc.IntegrityError, match="UNIQUE"), write_tx(engine) as conn:
        _insert_initial_scene_request(conn, "second")
    with write_tx(engine) as conn:
        conn.exec_driver_sql("UPDATE generation_requests SET status = 'failed' WHERE id = 'first'")
        _insert_initial_scene_request(conn, "second")


def _stdout_lines(proc):
    """The child's stdout lines, then None at EOF. Windows pipes cannot be select()ed, so a thread
    reads them and every get() in the test has a timeout."""
    lines = queue.Queue()

    def pump():
        for line in proc.stdout:
            lines.put(line.strip())
        lines.put(None)

    threading.Thread(target=pump, daemon=True).start()
    return lines


def test_write_tx_waits_for_the_other_process_to_commit(engine, tmp_path):
    engine.dispose()
    pipes = {"stdin": subprocess.PIPE, "stdout": subprocess.PIPE, "text": True}
    with (
        subprocess.Popen([sys.executable, str(WORKER), "holder", str(tmp_path)], **pipes) as holder,
        subprocess.Popen([sys.executable, str(WORKER), "waiter", str(tmp_path)], **pipes) as waiter,
    ):
        try:
            holder_out, waiter_out = _stdout_lines(holder), _stdout_lines(waiter)
            assert holder_out.get(timeout=15) == "locked"
            assert waiter_out.get(timeout=15) == "ready"
            waiter.stdin.write("go\n")
            waiter.stdin.flush()
            # The waiter's lock wait (1 s + at most 2 s) stays well inside busy_timeout (5 s).
            with pytest.raises(queue.Empty):  # silent: blocked on the holder's write lock
                waiter_out.get(timeout=1)
            holder.stdin.write("commit\n")
            holder.stdin.flush()
            assert waiter_out.get(timeout=2) == "entered A"
            assert [holder_out.get(timeout=5), waiter_out.get(timeout=5)] == [None, None]
            assert holder.wait(timeout=5) == 0 and waiter.wait(timeout=5) == 0
        finally:
            holder.kill()
            waiter.kill()
