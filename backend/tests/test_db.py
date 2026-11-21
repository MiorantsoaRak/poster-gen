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
from affiche.db import make_engine, migrate, utc_now, write_tx
from affiche.posters import credits, terms

FACEBOOK = ("facebook_pages", "facebook_connects", "facebook_publications")  # 0018, empty
ADDED_0018 = [f"0018 ADDED {table}: empty: as expected" for table in FACEBOOK]
POSTS = ("facebook_posts", "facebook_post_items")  # 0019, empty
ADDED_0019 = ["0019 ADDED shop_profile: no limit of images per post: as expected",
              *(f"0019 ADDED {table}: empty: as expected" for table in POSTS)]
DESIGN_TABLES = {"meta", "assets", "runs", "run_products", "abandonments", "variant_cycles", "cutouts",
                 "generation_requests", "provider_calls", "candidates", "shop_profile", "asset_access",
                 "product_inputs", "creations", "creation_versions", "mutation_keys", "sessions", "login_failures",
                 "poster_jobs", "poster_calls", "scene_plans", "poster_visuals", "text_proposals", "text_effects", "poster_renders", "confirmations", "looks", "chat_reads",
                 "credit_grants", "operator_sessions", *FACEBOOK, *POSTS}
GUARD_WHERE = {
    "req_one_revision": "WHERE parent_id IS NOT NULL AND status IN ('running','succeeded')",
    "req_one_initial": "WHERE parent_id IS NULL AND status IN ('running','succeeded')",
}
WORKER = Path(__file__).with_name("tx_worker.py")


def credited(engine, shop=1):
    """100 offered credits, as the operator grants them: a shop starts at zero, and every image job takes one
    (D-BALANCE-002); and the current conditions accepted, without which nothing new is asked of the AI (D-TERMS-003).
    Once per shop: a test's `client` and `engine` share one database."""
    with write_tx(engine) as conn:
        if conn.execute(text("SELECT 1 FROM credit_grants WHERE shop_id=:shop AND ref='tests'"), {"shop": shop}).first() is None:
            credits.grant(conn, shop, 100, origin="offered", ref="tests", actor="tests")
    accepted(engine, shop)


def accepted(engine, shop=1):
    """The current conditions of use accepted, as POST /api/terms writes it (D-TERMS-002)."""
    with write_tx(engine) as conn:
        conn.execute(text("UPDATE shop_profile SET terms_version=:version, terms_accepted_at=:now WHERE id=:shop"),
                     {"version": terms.VERSION, "now": utc_now(), "shop": shop})


def unaccepted(engine, shop=1):
    """Nothing accepted, as migration 0017 leaves every shop: the shop of the gate's refusal tests (D-TERMS-003)."""
    with write_tx(engine) as conn:
        conn.execute(text("UPDATE shop_profile SET terms_version=NULL, terms_accepted_at=NULL WHERE id=:shop"),
                     {"shop": shop})


@pytest.fixture
def engine(tmp_path):
    """Migrated, shop 1 funded and the conditions accepted."""
    engine = make_engine(tmp_path)
    migrate(engine)
    credited(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def bare_engine(tmp_path):
    """Migrated, shop 1 at zero credits, the conditions accepted: the balance's own tests."""
    engine = make_engine(tmp_path)
    migrate(engine)
    accepted(engine)
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
            assert conn.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one() == "0019"
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
    monkeypatch.setattr(db, "create_engine", lambda url, **options: create_engine(url, connect_args={"factory": KeysStayOff},
                                                                                   **options))
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
        assert conn.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one() == "0019"
        assert conn.exec_driver_sql("SELECT identifier, password_hash, state, created_at = updated_at, post_image_limit"
                                    " FROM shop_profile").all() == [("originalphone", None, "active", 1, None)]
        assert conn.exec_driver_sql("PRAGMA foreign_key_check").all() == []


def test_0013_keeps_the_pilot_whole_and_makes_room_for_other_shops(tmp_path, monkeypatch):
    path = pilot_0012(tmp_path, monkeypatch)
    (before, _), (whole, _) = read(path, preserved_0013()), read(path)
    assert all(whole["tables"][table][0] > 0 for table in CHILDREN | {"looks", "provider_calls", "poster_calls"})
    engine = make_engine(tmp_path)
    try:
        migrate_to(engine, "0013", monkeypatch)
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
                                       "CREATE INDEX chat_reads_created",  # right after the read ledger's swap
                                       "CREATE TRIGGER poster_jobs_final",  # 0014's last
                                       "CREATE TRIGGER shop_profile_same_shop"])  # 0015's: the release is one transaction
def test_a_failure_inside_0013_0014_or_0015_leaves_the_database_exactly_as_before(tmp_path, monkeypatch, statement):
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
    assert "pending migrations: 0013, 0014, 0015, 0016, 0017, 0018, 0019" in out and "schema version: 0012 -> 0019" in out
    assert "ledger provider_calls: 512881 -> 512881" in out and "(over id, ip, attempted_at)" in out
    # shop_profile from 0012: 0013's projection, the earliest pending one, over its six columns of then.
    assert "(over id, revision, name, contact, logo_asset, updated_at)" in out
    assert "(over id, shop_id, creation_id, origin_revision, input_id, kind," in out  # poster_jobs without takes_credit
    lines = out.splitlines()
    assert {line for line in lines if line.startswith("0014 ADDED")} == {
        "0014 ADDED poster_jobs: no job from before 0014 takes a credit: as expected",
        "0014 ADDED credit_grants: empty; no shop has a credit before the operator grants one: as expected"}
    # 0013's check of the shop's triggers is 0015's: it states it again with the two it adds.
    assert [line for line in lines if "ADDED shop_profile: its rows" in line] == [  # 0013's own is retired by name
        "0015 ADDED shop_profile: its rows cannot be deleted, replaced or made another shop: as expected"]
    assert [line for line in lines if line.startswith("0016 ")] == ["0016 ADDED operator_sessions: empty: as expected"]
    assert [line for line in lines if line.startswith("0017 ")] == ["0017 ADDED shop_profile: nothing accepted: as expected"]
    assert [line for line in lines if line.startswith("0018 ")] == ADDED_0018
    assert [line for line in lines if line.startswith("0019 ")] == ADDED_0019
    guards =[line for line in lines if line.startswith("guard ")]
    assert len(guards) == 14 and all(line.endswith(": as expected") for line in guards)  # a table, 12 triggers, a column
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


def test_0014_on_a_database_at_0013_counts_no_job_of_before_and_grants_nothing(tmp_path, monkeypatch):
    path = pilot_0012(tmp_path, monkeypatch)
    script = ScriptDirectory.from_config(Config(BACKEND_DIR / "alembic.ini"))
    # As the rehearsal hashes them: poster_jobs over 0014's projection, shop_profile over 0017's (it widens it).
    preserved = script.get_revision("0014").module.PRESERVED | script.get_revision("0017").module.PRESERVED
    engine = make_engine(tmp_path)
    try:
        migrate_to(engine, "0013", monkeypatch)
        before, _ = read(path, preserved)
        migrate(engine)
        after, _ = read(path, preserved)
        new = ("credit_grants", "operator_sessions", *FACEBOOK, *POSTS)
        assert {table: after["tables"].pop(table)[0] for table in new} == dict.fromkeys(new, 0)
        assert after["tables"] == before["tables"] and after["sums"] == before["sums"]
        assert (after["version"], after["foreign_key_check"], after["integrity_check"]) == ("0019", 0, "ok")
        with engine.connect() as conn:
            assert conn.exec_driver_sql("SELECT kind, takes_credit FROM poster_jobs ORDER BY id").all() == [
                ("plan", 0), ("scene", 0), ("text_patch", 0), ("text_texture", 0), ("render", 0), ("plan", 0)]
            assert credits.balance(conn, 1) == {"available": 0, "pending": 0}
            assert rehearse.guard_differences(conn.connection.dbapi_connection) == []
    finally:
        engine.dispose()


# Read from 0014 itself, never from rehearse.GUARDS: a guard removed from GUARDS must fail an assertion here.
STATEMENTS_0014 = ScriptDirectory.from_config(Config(BACKEND_DIR / "alembic.ini")).get_revision("0014").module.STATEMENTS
TAKES_CREDIT = STATEMENTS_0014[0].split(" ADD COLUMN ", 1)[1]
JOB_TRIGGERS = [statement for statement in STATEMENTS_0014 if statement.startswith("CREATE TRIGGER poster_jobs_")]
TRIGGERS = ("credit_grants_never_changed", "credit_grants_never_removed", "credit_grants_never_replaced",
            "credit_grants_one_payment", "credit_grants_payment_total", "poster_jobs_final", "poster_jobs_never_removed",
            "poster_jobs_never_replaced", "poster_jobs_same_job")
WEAKER_FINAL = """CREATE TRIGGER poster_jobs_final BEFORE UPDATE OF status ON poster_jobs
  WHEN OLD.status IN ('succeeded', 'failed', 'interrupted', 'cancelled') AND NEW.status IS NOT OLD.status
  BEGIN SELECT RAISE(ABORT, 'a finished job never changes status'); END"""


def rebuild_poster_jobs(conn, column):
    """SQLite's procedure for changing a table, as a later migration adding a job kind would run it: the old table's
    triggers are dropped with it, without a word."""
    table = conn.exec_driver_sql("SELECT sql FROM sqlite_master WHERE type='table' AND name='poster_jobs'").scalar_one()
    indexes = conn.exec_driver_sql("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='poster_jobs'"
                                   " AND sql IS NOT NULL").scalars().all()
    conn.exec_driver_sql(table.replace("CREATE TABLE poster_jobs", "CREATE TABLE poster_jobs_new", 1)
                         .replace("'background')", "'background','video')", 1).replace(TAKES_CREDIT, column))
    conn.exec_driver_sql("INSERT INTO poster_jobs_new SELECT * FROM poster_jobs")
    conn.exec_driver_sql("DROP TABLE poster_jobs")
    conn.exec_driver_sql("ALTER TABLE poster_jobs_new RENAME TO poster_jobs")
    for index in indexes:
        conn.exec_driver_sql(index)


@pytest.mark.parametrize("rebuild, statements, last", [
    (TAKES_CREDIT, [], "REHEARSAL FAILED: " + "; ".join(  # the table's four triggers go with it
        f"guard trigger {name}: missing" for name in TRIGGERS if name.startswith("poster_jobs_"))),
    (TAKES_CREDIT, JOB_TRIGGERS, "REHEARSAL OK"),  # the same rebuild, its triggers recreated as 0014 wrote them
    (None, ["DROP TRIGGER poster_jobs_final", WEAKER_FINAL], "REHEARSAL FAILED: guard trigger poster_jobs_final: different"),
    ("takes_credit INTEGER NOT NULL DEFAULT 0", JOB_TRIGGERS,
     "REHEARSAL FAILED: guard column poster_jobs.takes_credit: different"),
    (None, ["ALTER TABLE credit_grants ADD COLUMN receipt TEXT"], "REHEARSAL FAILED: guard table credit_grants: different"),
    *((None, [f"DROP TRIGGER {name}"], f"REHEARSAL FAILED: guard trigger {name}: missing") for name in TRIGGERS),
])
def test_a_later_migration_that_loses_or_weakens_a_guard_fails_the_rehearsal(tmp_path, monkeypatch, capsys, rebuild,
                                                                              statements, last):
    path = pilot_0012(tmp_path, monkeypatch)
    upgrade = command.upgrade

    def later(config, revision):  # a later migration of the repository, run by migrate after the real ones
        upgrade(config, revision)
        conn = config.attributes["connection"]
        if rebuild:
            rebuild_poster_jobs(conn, rebuild)
        for statement in statements:
            conn.exec_driver_sql(statement)

    monkeypatch.setattr(command, "upgrade", later)
    assert rehearse.main(["rehearse", str(path)]) == (0 if last == "REHEARSAL OK" else 1)
    assert capsys.readouterr().out.splitlines()[-1] == last  # nothing else differs


STATEMENTS_0015 = ScriptDirectory.from_config(Config(BACKEND_DIR / "alembic.ini")).get_revision("0015").module.STATEMENTS
SHOP_TRIGGERS = ("keep_shop", *(statement.split()[2] for statement in STATEMENTS_0015))
WEAKER_SAME_SHOP = """CREATE TRIGGER shop_profile_same_shop BEFORE UPDATE ON shop_profile
  WHEN NEW.id IS NOT OLD.id
  BEGIN SELECT RAISE(ABORT, 'a shop stays the same shop: its id never changes'); END"""


@pytest.mark.parametrize("statements, guard", [
    (["DROP TRIGGER poster_jobs_final"], "guard trigger poster_jobs_final: missing"),
    *(([f"DROP TRIGGER {name}"], f"guard trigger {name}: missing") for name in SHOP_TRIGGERS),
    (["DROP TRIGGER shop_profile_same_shop", WEAKER_SAME_SHOP], "guard trigger shop_profile_same_shop: different"),
])
def test_a_database_at_head_changed_by_hand_fails_the_rehearsal_with_nothing_pending(engine, capsys, statements, guard):
    with write_tx(engine) as conn:
        for statement in statements:
            conn.exec_driver_sql(statement)
    assert rehearse.main(["rehearse", engine.url.database]) == 1
    out = capsys.readouterr().out
    assert "pending migrations: none (code head 0019)" in out
    assert out.splitlines()[-1] == f"REHEARSAL FAILED: {guard}"


def test_0015_on_a_database_at_0014_keeps_every_row_and_adds_only_its_two_triggers(tmp_path, monkeypatch):
    path = pilot_0012(tmp_path, monkeypatch)
    engine = make_engine(tmp_path)
    try:
        migrate_to(engine, "0014", monkeypatch)
        with write_tx(engine) as conn:
            conn.exec_driver_sql("INSERT INTO shop_profile (revision,updated_at,identifier,state,created_at) "
                                 f"VALUES (1,'{T}','shopdeux','suspended','{T}')")
            credits.grant(conn, 1, 5, origin="offered", ref="welcome", actor="tests")
            credits.grant(conn, 2, 3, origin="offered", ref="welcome", actor="tests")
        before, schema_before = read(path)
        migrate_to(engine, "0015", monkeypatch)
        after, schema = read(path)
        assert after["tables"] == before["tables"] and after["sums"] == before["sums"]  # every column of every row
        assert (before["version"], after["version"], after["foreign_key_check"], after["integrity_check"]) == (
            "0014", "0015", 0, "ok")
        assert {name: schema[name] for name in schema_before} == schema_before
        assert schema.keys() - schema_before.keys() == {"shop_profile_never_replaced", "shop_profile_same_shop"}
        with engine.connect() as conn:
            assert [credits.balance(conn, shop)["available"] for shop in (1, 2)] == [5, 3]
            assert rehearse.guard_differences(conn.connection.dbapi_connection) == []
    finally:
        engine.dispose()


STATEMENTS_0017 = ScriptDirectory.from_config(Config(BACKEND_DIR / "alembic.ini")).get_revision("0017").module.STATEMENTS
LATER = "2099-01-01T00:00:00.000000+00:00"


def test_0017_on_a_populated_0016_database_keeps_every_shop_column_and_accepts_nothing(tmp_path, monkeypatch, capsys):
    """D-TERMS-002: shops, sessions, an operator session, credit lines and jobs at 0016. The rehearsal hashes the ten
    shop columns; 0017 keeps every row of every table and adds two columns, empty for every shop."""
    path = pilot_0012(tmp_path, monkeypatch)
    preserved = ScriptDirectory.from_config(Config(BACKEND_DIR / "alembic.ini")).get_revision("0017").module.PRESERVED
    engine = make_engine(tmp_path)
    try:
        migrate_to(engine, "0016", monkeypatch)
        with write_tx(engine) as conn:
            conn.exec_driver_sql("INSERT INTO shop_profile (revision,name,updated_at,identifier,password_hash,state,"
                                 f"created_at) VALUES (1,'Boutique Deux','{T}','shopdeux','$argon2id$tests','suspended','{T}')")
            conn.exec_driver_sql(f"INSERT INTO sessions VALUES ('t2',2,'{LATER}')")
            conn.exec_driver_sql(f"INSERT INTO operator_sessions VALUES ('{'0' * 64}','{T}','{LATER}','127.0.0.1',NULL)")
            credits.grant(conn, 1, 5, origin="offered", ref="welcome", actor="tests")
            credits.grant(conn, 2, 3, origin="offered", ref="welcome", actor="tests")
        assert rehearse.main(["rehearse", str(path)]) == 0
        out = capsys.readouterr().out
        assert "pending migrations: 0017, 0018, 0019 (code head 0019)" in out and out.endswith("REHEARSAL OK\n")
        assert ("(over id, revision, name, contact, logo_asset, updated_at, identifier, password_hash, state, created_at)"
                in out)
        before, schema_before = read(path, preserved)
        migrate_to(engine, "0017", monkeypatch)
        after, schema = read(path, preserved)
        assert after["tables"] == before["tables"] and after["sums"] == before["sums"]  # every other table: every column
        assert (before["version"], after["version"], after["foreign_key_check"], after["integrity_check"]) == (
            "0016", "0017", 0, "ok")
        assert schema.keys() == schema_before.keys()
        assert {name: sql for name, sql in schema.items() if name != "shop_profile"} == {
            name: sql for name, sql in schema_before.items() if name != "shop_profile"}
        assert all(statement.split(" ADD COLUMN ", 1)[1] in schema["shop_profile"] for statement in STATEMENTS_0017)
        with engine.connect() as conn:
            assert conn.exec_driver_sql("SELECT id, terms_version, terms_accepted_at FROM shop_profile ORDER BY id").all() \
                == [(1, None, None), (2, None, None)]
            assert [credits.balance(conn, shop)["available"] for shop in (1, 2)] == [5, 3]
            assert rehearse.guard_differences(conn.connection.dbapi_connection) == []
        for refused in ("UPDATE shop_profile SET terms_version='2026-11-17' WHERE id=1",  # a half-NULL pair, both ways
                        f"UPDATE shop_profile SET terms_accepted_at='{T}' WHERE id=1",
                        f"UPDATE shop_profile SET terms_version='', terms_accepted_at='{T}' WHERE id=1",  # an empty version
                        "UPDATE shop_profile SET terms_version='2026-11-17', terms_accepted_at='' WHERE id=1",  # empty date
                        f"UPDATE shop_profile SET terms_version='{'9' * 33}', terms_accepted_at='{T}' WHERE id=1"):
            with pytest.raises(exc.IntegrityError, match="CHECK"), write_tx(engine) as conn:
                conn.exec_driver_sql(refused)
        with write_tx(engine) as conn:  # both together, neither empty
            conn.exec_driver_sql(f"UPDATE shop_profile SET terms_version='2026-11-17', terms_accepted_at='{T}' WHERE id=1")
    finally:
        engine.dispose()


STATEMENTS_0018 = ScriptDirectory.from_config(Config(BACKEND_DIR / "alembic.ini")).get_revision("0018").module.STATEMENTS


def publication(id, shop, key, status="sending"):
    return ("INSERT INTO facebook_publications (id,shop_id,creation_id,confirmation_id,page_id,page_name,caption,key,"
            f"payload_sha,status,sent_at) VALUES ('{id}',{shop},'c1','cf1','111','Page','','{key}','s','{status}','{T}')")


def test_0018_on_a_populated_0017_database_keeps_every_row_and_adds_three_empty_tables(tmp_path, monkeypatch, capsys):
    """D-FB-PUBLISH-001: the pilot at 0017 and a second shop. 0018 adds the Facebook tables, empty, and changes nothing
    else; their checks refuse a state, a step or a status the design does not have, a shop that does not exist, a
    second Page or attempt for a shop, a key used twice by one shop and a publication without an id."""
    path = pilot_0012(tmp_path, monkeypatch)
    engine = make_engine(tmp_path)
    try:
        migrate_to(engine, "0017", monkeypatch)
        with write_tx(engine) as conn:
            conn.exec_driver_sql("INSERT INTO shop_profile (revision,updated_at,identifier,state,created_at) "
                                 f"VALUES (1,'{T}','shopdeux','active','{T}')")
        assert rehearse.main(["rehearse", str(path)]) == 0
        out = capsys.readouterr().out
        assert "pending migrations: 0018, 0019 (code head 0019)" in out and out.endswith("REHEARSAL OK\n")
        assert [line for line in out.splitlines() if line.startswith("0018 ")] == ADDED_0018
        before, schema_before = read(path)
        migrate_to(engine, "0018", monkeypatch)
        after, schema = read(path)
        assert {table: after["tables"].pop(table)[0] for table in FACEBOOK} == dict.fromkeys(FACEBOOK, 0)
        assert after["tables"] == before["tables"] and after["sums"] == before["sums"]  # every column of every row
        assert (before["version"], after["version"], after["foreign_key_check"], after["integrity_check"]) == (
            "0017", "0018", 0, "ok")
        assert {name: schema[name] for name in schema_before} == schema_before
        assert {name for name in schema.keys() - schema_before.keys() if not name.startswith("sqlite_autoindex_")} \
            == set(FACEBOOK)
        assert [schema[table] for table in FACEBOOK] == STATEMENTS_0018
        with write_tx(engine) as conn:  # what the routes will write, for each shop: shop 2 may use shop 1's key
            for shop in (1, 2):
                conn.exec_driver_sql(f"INSERT INTO facebook_pages VALUES ({shop},'111','Page','t','connected','{T}')")
                conn.exec_driver_sql(f"INSERT INTO facebook_connects VALUES ({shop},'s','x','dialog',NULL,'{T}')")
                conn.exec_driver_sql(publication(f"p{shop}", shop, "key-1"))
        with engine.connect() as conn:
            assert conn.exec_driver_sql("SELECT said_by_owner FROM facebook_publications").scalars().all() == [0, 0]
            assert rehearse.guard_differences(conn.connection.dbapi_connection) == []
        for refused, match in (
                (f"INSERT INTO facebook_pages VALUES (9,'111','Page','t','connected','{T}')", "FOREIGN KEY"),
                (f"INSERT INTO facebook_pages VALUES (1,'222','Page','t','connected','{T}')", "UNIQUE"),  # one per shop
                ("UPDATE facebook_pages SET state='disconnected' WHERE shop_id=1", "CHECK"),
                (f"INSERT INTO facebook_connects VALUES (9,'s','x','dialog',NULL,'{T}')", "FOREIGN KEY"),
                (f"INSERT INTO facebook_connects VALUES (1,'s','x','dialog',NULL,'{T}')", "UNIQUE"),  # one attempt
                ("UPDATE facebook_connects SET step='done' WHERE shop_id=1", "CHECK"),
                (publication("p3", 9, "key-2"), "FOREIGN KEY"),
                (publication("p3", 1, "key-1"), "UNIQUE"),
                (publication("p1", 1, "key-2"), "UNIQUE"),
                (publication("p3", 1, "key-2", "admitted"), "CHECK"),  # v2's state, removed by v3
                (publication("p3", 1, "key-2").replace("(id,", "(").replace("('p3',", "("), "NOT NULL"),  # no id
                ("UPDATE facebook_publications SET status='removed' WHERE id='p1'", "CHECK")):
            with pytest.raises(exc.IntegrityError, match=match), write_tx(engine) as conn:
                conn.exec_driver_sql(refused)
    finally:
        engine.dispose()


STATEMENTS_0019 = ScriptDirectory.from_config(Config(BACKEND_DIR / "alembic.ini")).get_revision("0019").module.STATEMENTS


def post(id, shop, key, status="uploading"):
    return ("INSERT INTO facebook_posts (id,shop_id,page_id,page_name,description,key,payload_sha,status,sent_at) "
            f"VALUES ('{id}',{shop},'111','Page','','{key}','s','{status}','{T}')")


def item(post, position, creation="c1"):
    return ("INSERT INTO facebook_post_items (post_id,position,creation_id,confirmation_id,png_sha256) "
            f"VALUES ('{post}',{position},'{creation}','cf1','h')")


def test_0019_on_a_populated_0018_database_keeps_the_publications_and_adds_the_limit_and_two_empty_tables(
        tmp_path, monkeypatch, capsys):
    """D-FB-POST-001: the pilot at 0018 with a second shop and a publication. 0019 widens shop_profile with the limit, no
    shop having one, adds the posts and their images, empty, and leaves facebook_publications and its row as they were
    (0020 converts them). Its checks refuse a limit below 1, a status the design does not have, a shop or a post that
    does not exist, a key used twice by one shop, a poster or a position twice in one post; an image's poster and
    confirmation are not foreign keys."""
    path = pilot_0012(tmp_path, monkeypatch)
    preserved = ScriptDirectory.from_config(Config(BACKEND_DIR / "alembic.ini")).get_revision("0019").module.PRESERVED
    engine = make_engine(tmp_path)
    try:
        migrate_to(engine, "0018", monkeypatch)
        with write_tx(engine) as conn:
            conn.exec_driver_sql("INSERT INTO shop_profile (revision,updated_at,identifier,state,created_at) "
                                 f"VALUES (1,'{T}','shopdeux','active','{T}')")
            conn.exec_driver_sql(publication("p1", 1, "key-1", "unknown"))
        assert rehearse.main(["rehearse", str(path)]) == 0
        out = capsys.readouterr().out
        assert "pending migrations: 0019 (code head 0019)" in out and out.endswith("REHEARSAL OK\n")
        assert ("(over id, revision, name, contact, logo_asset, updated_at, identifier, password_hash, state, created_at,"
                " terms_version, terms_accepted_at)" in out)
        assert [line for line in out.splitlines() if line.startswith("0019 ")] == ADDED_0019
        before, schema_before = read(path, preserved)
        migrate(engine)
        after, schema = read(path, preserved)
        assert {table: after["tables"].pop(table)[0] for table in POSTS} == dict.fromkeys(POSTS, 0)
        assert after["tables"] == before["tables"] and after["sums"] == before["sums"]  # facebook_publications included
        assert before["tables"]["facebook_publications"][0] == 1
        assert (before["version"], after["version"], after["foreign_key_check"], after["integrity_check"]) == (
            "0018", "0019", 0, "ok")
        assert {name: schema[name] for name in schema_before if name != "shop_profile"} == {
            name: sql for name, sql in schema_before.items() if name != "shop_profile"}
        assert STATEMENTS_0019[0].split(" ADD COLUMN ", 1)[1] in schema["shop_profile"]
        assert {name for name in schema.keys() - schema_before.keys() if not name.startswith("sqlite_autoindex_")} \
            == {*POSTS, "facebook_post_items_creation"}
        assert [schema[name] for name in (*POSTS, "facebook_post_items_creation")] == STATEMENTS_0019[1:]
        with engine.connect() as conn:
            assert conn.exec_driver_sql("SELECT id, post_image_limit FROM shop_profile ORDER BY id").all() == [
                (1, None), (2, None)]
            assert rehearse.guard_differences(conn.connection.dbapi_connection) == []
        with write_tx(engine) as conn:  # what the routes will write: shop 2 may use shop 1's key
            conn.exec_driver_sql("UPDATE shop_profile SET post_image_limit=1 WHERE id=1")
            conn.exec_driver_sql("UPDATE shop_profile SET post_image_limit=NULL WHERE id=1")
            for shop in (1, 2):
                conn.exec_driver_sql(post(f"post{shop}", shop, "key-1"))
            conn.exec_driver_sql(item("post1", 0))
            conn.exec_driver_sql(item("post1", 1, "gone"))  # a poster that is not here: no foreign key
            conn.exec_driver_sql("INSERT INTO facebook_post_items VALUES ('post2',0,'c1','missing',NULL,NULL)")
        with engine.connect() as conn:
            assert conn.exec_driver_sql("SELECT stop_asked, said_by_owner FROM facebook_posts").all() == [(0, 0), (0, 0)]
            assert conn.exec_driver_sql("SELECT count(*) FROM facebook_post_items").scalar() == 3
            assert conn.exec_driver_sql("SELECT id, status FROM facebook_publications").all() == [("p1", "unknown")]
            assert conn.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        for refused, match in (
                ("UPDATE shop_profile SET post_image_limit=0 WHERE id=1", "CHECK"),
                ("UPDATE shop_profile SET post_image_limit=-1 WHERE id=1", "CHECK"),
                (post("post3", 9, "key-2"), "FOREIGN KEY"),
                (post("post3", 1, "key-1"), "UNIQUE"),  # one shop, one key
                (post("post1", 1, "key-2"), "UNIQUE"),
                (post("post3", 1, "key-2", "sending"), "CHECK"),  # 0018's status, not a post's
                (post("post3", 1, "key-2").replace("(id,", "(").replace("('post3',", "("), "NOT NULL"),  # no id
                ("UPDATE facebook_posts SET status='removed' WHERE id='post1'", "CHECK"),
                (item("nopost", 0), "FOREIGN KEY"),
                (item("post1", 2), "UNIQUE"),  # the same poster twice in one post
                (item("post1", 1, "c2"), "UNIQUE"),  # the same position twice
                (item("post1", -1, "c2"), "CHECK")):
            with pytest.raises(exc.IntegrityError, match=match), write_tx(engine) as conn:
                conn.exec_driver_sql(refused)
    finally:
        engine.dispose()


def test_a_failed_statement_never_says_its_values(engine):
    """hide_parameters: the text of a write that fails (a task logs its type, a traceback its text) holds no value bound
    to it, so neither a photo's id nor a Page's token."""
    photo, token = "77700012345", "page-token-never-in-an-error"
    for statement, values in (
            ("INSERT INTO facebook_post_items (post_id,position,creation_id,confirmation_id,photo_id)"
             " VALUES ('no-post',0,'c','k',:value)", {"value": photo}),
            ("INSERT INTO facebook_pages VALUES (99,'111','Page',:value,'connected','2026-11-21')", {"value": token})):
        with pytest.raises(exc.IntegrityError) as failure, write_tx(engine) as conn:
            conn.execute(text(statement), values)
        assert "FOREIGN KEY" in str(failure.value) and values["value"] not in str(failure.value)
        assert "hidden" in str(failure.value)
