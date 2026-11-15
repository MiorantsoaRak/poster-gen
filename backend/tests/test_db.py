import hashlib
import queue
import sqlite3
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, event, exc, text

from affiche import db, rehearse
from affiche.config import BACKEND_DIR
from affiche.db import make_engine, migrate, write_tx

DESIGN_TABLES = {"meta", "assets", "runs", "run_products", "abandonments", "variant_cycles", "cutouts",
                 "generation_requests", "provider_calls", "candidates", "shop_profile", "asset_access",
                 "product_inputs", "creations", "creation_versions", "mutation_keys", "sessions", "login_failures",
                 "poster_jobs", "poster_calls", "scene_plans", "poster_visuals", "text_proposals", "text_effects", "poster_renders", "confirmations", "looks", "chat_reads"}
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
            assert conn.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one() == "0013"
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


def migrate_to(engine, revision, monkeypatch):
    """The real migrations up to `revision` only: a database as an older version of the application left it."""
    upgrade = command.upgrade
    with monkeypatch.context() as patch:
        patch.setattr(command, "upgrade", lambda config, _revision: upgrade(config, revision))
        migrate(engine)


T = "2026-11-02T10:00:00.000000+00:00"
# The pilot at 0012: a row in every table that references the shop, in `looks` (no foreign key), in the three ledgers,
# a session, a login failure and the fingerprint of the password last seen.
PILOT = [
    f"INSERT INTO assets VALUES ('a1','image/png',1,1,1,'{T}','original'), ('a2','image/png',1,1,1,'{T}','scene')",
    "UPDATE shop_profile SET revision=3, name='Original Phone Mada', contact='034 00 000 00', logo_asset='a1'",
    "INSERT INTO asset_access VALUES (1,'a1','original'), (1,'a1','logo')",
    f"INSERT INTO product_inputs VALUES ('in1',1,'P1','JBL','Bleu','[\"a1\"]','{{}}',NULL,'{T}')",
    f"INSERT INTO creations VALUES ('c1',1,NULL,1,'active','2026-11-01T09:00:00.000000+00:00','{T}')",
    f"INSERT INTO creation_versions VALUES ('c1',1,'{{\"offer\":{{\"price_ar\":899000}}}}','h1','{T}')",
    f"INSERT INTO mutation_keys VALUES (1,'k1','POST','/api/creations','s',201,'{{}}','{T}')",
    "INSERT INTO sessions VALUES ('t1',1,'2099-01-01T00:00:00.000000+00:00')",
    f"INSERT INTO login_failures (ip,attempted_at) VALUES ('192.0.2.1','{T}'), ('2001:db8::','{T}')",
    "INSERT INTO meta VALUES ('password_fingerprint','f')",
    *(f"INSERT INTO poster_jobs (id,shop_id,creation_id,origin_revision,input_id,kind,input_json,input_hash,status,"
      f"created_at,started_at) VALUES ('{id}',1,'c1',1,'in1','{kind}','{{}}','h','succeeded','{T}','{T}')"
      for id, kind in (("j1", "plan"), ("j2", "scene"), ("j3", "text_patch"), ("j4", "text_texture"), ("j5", "render"),
                       ("j6", "plan"))),
    "INSERT INTO poster_calls (id,job_id,call_no,provider,model,rate_card_json,status,cost_micros,cost_is_estimate,"
    f"created_at) VALUES ('pc1','j2',1,'openai','gpt-image-2','{{}}','succeeded',40000,0,'{T}')",
    f"INSERT INTO scene_plans VALUES ('p1',1,'c1',1,'in1','j1',NULL,'stub','feed','{{}}','{{}}','prompt','ph','{T}')",
    "INSERT INTO poster_visuals (id,shop_id,input_id,job_id,treatment,status,image_asset,source_assets_json,"
    "reference_roles_json,plan_id,prompt_text,prompt_hash,direction_json,model,quality,size,low_res_ack,created_at)"
    f" VALUES ('v1',1,'in1','j2','scene','approved','a2','[]','{{}}','p1','prompt','ph','{{}}','gpt-image-2','high',"
    f"'1024x1536',0,'{T}')",
    f"INSERT INTO text_proposals VALUES ('tp1',1,'c1',1,'feed','title','j3','{{}}','applied',1,'{T}')",
    f"INSERT INTO text_effects VALUES ('te1',1,'c1',1,'feed','title','tp1','j4','sh','a2','gold','[]','proposed',NULL,'{T}')",
    f"INSERT INTO poster_renders VALUES ('r1','c1',1,'j5','feed','fh','rb','fm','{{}}','png',1080,1350,100,'[]','{T}')",
    f"INSERT INTO confirmations VALUES ('cf1','c1',1,1,'feed','fh','r1','png','{{}}','{T}')",
    f"INSERT INTO looks VALUES ('l1',1,'j6','Néon','a2','{{}}','stub','{T}',NULL)",
    *(f"INSERT INTO chat_reads VALUES ('{id}',1,{creation},'{key}','s','succeeded','claude','m','{{}}',{cost},0,"
      f"'{{}}','req','{{}}','{T}','{T}')" for id, creation, key, cost in (("cr1", "'c1'", "key-1", 3600),
                                                                          ("cr2", "NULL", "key-2", 2900))),
    f"INSERT INTO runs VALUES ('old','gpt-image-2','high','1088x1920',3,'on','{T}')",
    "INSERT INTO generation_requests (id,payload_hash,purpose,variant_ref,cycle_no,run_label,request_json,"
    f"corrections_applied,owner,status,created_at) VALUES ('req','h','scene','P1',1,'old','{{}}',0,'cli','succeeded','{T}')",
    "INSERT INTO provider_calls (id,request_id,call_no,provider,model,status,cost_micros,cost_is_estimate,started_at)"
    f" VALUES ('paid','req',1,'openai','gpt-image-2','succeeded',512881,0,'{T}')",
]
CHILDREN = {"asset_access", "product_inputs", "creations", "mutation_keys", "sessions", "poster_jobs", "scene_plans",
            "poster_visuals", "text_proposals", "text_effects", "chat_reads"}


def pilot_0012(folder, monkeypatch) -> Path:
    engine = make_engine(folder)
    try:
        migrate_to(engine, "0012", monkeypatch)
        with write_tx(engine) as conn:
            for statement in PILOT:
                conn.exec_driver_sql(statement)
    finally:
        engine.dispose()
    return folder / "affiche.db"


def read(path, projections=None):
    connection = sqlite3.connect(path)
    try:
        return rehearse.snapshot(connection, projections or {}), {
            name: sql for name, sql in connection.execute("SELECT name, sql FROM sqlite_master")}
    finally:
        connection.close()


def preserved_0013():
    return ScriptDirectory.from_config(Config(BACKEND_DIR / "alembic.ini")).get_revision("0013").module.PRESERVED


def test_migrate_turns_the_keys_back_on_for_the_same_pooled_connection(tmp_path):
    engine = make_engine(tmp_path)
    opened = []
    event.listen(engine, "connect", lambda *_: opened.append(1))
    try:
        migrate(engine)
        migrate(engine)
        with engine.connect() as conn:
            assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        assert len(opened) == 1  # one DBAPI connection all along: the one the migrations ran on
    finally:
        engine.dispose()


def test_a_migration_that_breaks_a_reference_applies_nothing(tmp_path, monkeypatch):
    engine = make_engine(tmp_path)
    try:
        migrate_to(engine, "0012", monkeypatch)
        upgrade = command.upgrade

        def breaking(config, revision):
            upgrade(config, revision)
            config.attributes["connection"].exec_driver_sql("INSERT INTO sessions VALUES ('orphan',9,'2099')")

        monkeypatch.setattr(command, "upgrade", breaking)
        with pytest.raises(RuntimeError, match="reference to a missing row"):
            migrate(engine)
        with engine.connect() as conn:
            assert conn.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one() == "0012"
            assert conn.exec_driver_sql("SELECT count(*) FROM sessions").scalar_one() == 0
            assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
    finally:
        engine.dispose()


class KeysStayOff(sqlite3.Connection):
    def execute(self, sql, *args):
        if sql == "PRAGMA foreign_keys = ON":
            raise sqlite3.OperationalError("injected: the pragma fails")
        return super().execute(sql, *args)


def test_keys_that_cannot_be_turned_on_again_discard_the_connection(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "create_engine", lambda url: create_engine(url, connect_args={"factory": KeysStayOff}))
    engine = make_engine(tmp_path)
    opened = []
    event.listen(engine, "connect", lambda *_: opened.append(1))
    try:
        with pytest.raises(RuntimeError, match="foreign keys could not be turned on again"):
            migrate(engine)
        with engine.connect() as conn:  # a new DBAPI connection, which gets the pragmas from make_engine
            assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        assert len(opened) == 2
    finally:
        engine.dispose()


def test_a_fresh_database_starts_with_shop_1_without_password(engine):
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one() == "0013"
        assert conn.exec_driver_sql("SELECT identifier, password_hash, state, created_at = updated_at FROM shop_profile"
                                    ).all() == [("originalphone", None, "active", 1)]
        assert conn.exec_driver_sql("PRAGMA foreign_key_check").all() == []


def test_0013_keeps_the_pilot_whole_and_makes_room_for_other_shops(tmp_path, monkeypatch):
    path = pilot_0012(tmp_path, monkeypatch)
    (before, _), (whole, _) = read(path, preserved_0013()), read(path)
    assert all(whole["tables"][table][0] > 0 for table in CHILDREN | {"looks", "provider_calls", "poster_calls"})
    engine = make_engine(tmp_path)
    try:
        migrate(engine)
        after, schema = read(path, preserved_0013())
        assert after["tables"] == before["tables"] and after["sums"] == before["sums"] == {
            "provider_calls": 512881, "poster_calls": 40000, "chat_reads": 6500}
        assert (after["version"], after["foreign_key_check"], after["integrity_check"]) == ("0013", 0, "ok")
        assert "shop_profile_new" not in schema and "chat_reads_new" not in schema and "keep_shop" in schema
        with engine.connect() as conn:
            assert conn.exec_driver_sql("SELECT identifier, password_hash, state, created_at FROM shop_profile").all() \
                == [("originalphone", None, "active", "2026-11-01T09:00:00.000000+00:00")]  # with its first poster
            assert conn.exec_driver_sql("SELECT identifier FROM login_failures").scalars().all() == [None, None]
            assert conn.exec_driver_sql("SELECT shop_id FROM looks").scalars().all() == [1]
            assert conn.exec_driver_sql("SELECT value FROM meta WHERE key='password_fingerprint'").scalar() == "f"
        with write_tx(engine) as conn:
            assert conn.exec_driver_sql("INSERT INTO shop_profile (revision,updated_at,identifier,state,created_at) "
                                        f"VALUES (1,'{T}','shopdeux','active','{T}') RETURNING id").scalar_one() == 2
            conn.exec_driver_sql("INSERT INTO chat_reads (id,shop_id,key,payload_sha,status,provider,model,rate_card_json,"
                                 f"cost_micros,cost_is_estimate,created_at) VALUES ('cr3',2,'key-1','s','running','claude',"
                                 f"'m','{{}}',0,1,'{T}')")  # shop 2 may use shop 1's key
        for refused, match in (
                ("INSERT INTO chat_reads (id,shop_id,key,payload_sha,status,provider,model,rate_card_json,cost_micros,"
                 f"cost_is_estimate,created_at) VALUES ('cr4',1,'key-1','s','running','claude','m','{{}}',0,1,'{T}')",
                 "UNIQUE"),  # shop 1 may not reuse its own
                (f"INSERT INTO creations VALUES ('c9',9,NULL,1,'active','{T}','{T}')", "FOREIGN KEY"),
                (f"INSERT INTO shop_profile (revision,updated_at,identifier,state,created_at) VALUES (1,'{T}','ShopDeux',"
                 f"'active','{T}')", "CHECK"),
                (f"INSERT INTO shop_profile (revision,updated_at,identifier,state,created_at) VALUES (1,'{T}','shopdeux',"
                 f"'active','{T}')", "UNIQUE"),
                (f"INSERT INTO shop_profile (revision,updated_at,identifier,state,created_at) VALUES (1,'{T}','ab',"
                 f"'active','{T}')", "CHECK"),
                ("UPDATE shop_profile SET password_hash='hunter2hunter2' WHERE id=1", "CHECK"),
                ("UPDATE shop_profile SET state='closed' WHERE id=2", "CHECK"),
                ("DELETE FROM shop_profile WHERE id=2", "shop cannot be deleted")):
            with pytest.raises(exc.IntegrityError, match=match), write_tx(engine) as conn:
                conn.exec_driver_sql(refused)
    finally:
        engine.dispose()


@pytest.mark.parametrize("statement", ["CREATE TABLE chat_reads_new",  # between the two rebuilds
                                       "CREATE INDEX chat_reads_created"])  # right after the read ledger's swap
def test_a_failure_inside_0013_leaves_the_database_exactly_as_before(tmp_path, monkeypatch, statement):
    path = pilot_0012(tmp_path, monkeypatch)
    before = read(path)
    engine = make_engine(tmp_path)

    def fail(_conn, _cursor, sql, *_args):
        if sql.lstrip().startswith(statement):
            raise RuntimeError("injected fault")

    event.listen(engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError, match="injected fault"):
            migrate(engine)
        after = read(path)
        assert after == before  # every table's rows and hash, the version 0012, the schema's text
        assert after[0]["version"] == "0012" and "CHECK (id = 1)" in after[1]["shop_profile"]
        assert "key TEXT NOT NULL UNIQUE" in after[1]["chat_reads"] and "keep_shop" in after[1]
        with engine.connect() as conn:
            assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
    finally:
        engine.dispose()


def test_the_rehearsal_passes_on_the_pilot_and_never_writes_the_file_it_is_given(tmp_path, monkeypatch, capsys):
    path = pilot_0012(tmp_path / "data", monkeypatch)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert rehearse.main(["rehearse", str(path)]) == 0
    out = capsys.readouterr().out
    assert out.endswith("REHEARSAL OK\n") and f"environment: SQLite {sqlite3.sqlite_version}, Python " in out
    assert "pending migrations: 0013" in out and "schema version: 0012 -> 0013" in out
    assert "ledger provider_calls: 512881 -> 512881" in out and "(over id, ip, attempted_at)" in out
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest and read(path)[0]["version"] == "0012"
    assert rehearse.main(["rehearse", str(tmp_path / "missing.db")]) == 1
    assert "REHEARSAL FAILED" in capsys.readouterr().out and not (tmp_path / "missing.db").exists()
    assert rehearse.main(["rehearse"]) == 2


@pytest.mark.parametrize("damage, named", [
    ("DELETE FROM confirmations", "confirmations: 1 -> 0 rows"),
    ("UPDATE creation_versions SET document_json='{\"offer\":{\"price_ar\":1}}'",  # counts and sums intact
     "creation_versions: 1 -> 1 rows, different content"),
    ("UPDATE login_failures SET ip='203.0.113.9' WHERE ip='192.0.2.1'", "login_failures: 2 -> 2 rows, different content"),
    ("UPDATE poster_calls SET cost_micros=cost_micros+1", "ledger poster_calls: 40000 -> 40001"),
    ("UPDATE shop_profile SET state='suspended'", "0013 ADDED shop_profile: shop 1 is originalphone"),
    ("UPDATE login_failures SET identifier='originalphone'", "0013 ADDED login_failures"),
])
def test_the_rehearsal_fails_on_a_damaged_copy_and_names_what_differs(tmp_path, monkeypatch, capsys, damage, named):
    path = pilot_0012(tmp_path, monkeypatch)

    def damaging(engine):
        migrate(engine)
        with write_tx(engine) as conn:
            conn.exec_driver_sql(damage)

    monkeypatch.setattr(rehearse, "migrate", damaging)
    assert rehearse.main(["rehearse", str(path)]) == 1
    failed = capsys.readouterr().out.splitlines()[-1]
    assert failed.startswith("REHEARSAL FAILED: ") and named in failed


def test_the_rehearsal_refuses_a_pending_migration_without_its_contract(tmp_path, monkeypatch, capsys):
    engine = make_engine(tmp_path)
    try:
        migrate_to(engine, "0011", monkeypatch)
    finally:
        engine.dispose()
    assert rehearse.main(["rehearse", str(tmp_path / "affiche.db")]) == 1
    assert capsys.readouterr().out.splitlines()[-1] == "REHEARSAL FAILED: pending migration 0012 states no PRESERVED and ADDED"
