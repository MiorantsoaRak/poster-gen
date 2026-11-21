import os
import re
import shlex
import shutil
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, OperationalError

from affiche import backup, runtime, shops
from affiche.api import create_app
from affiche.config import load_settings
from affiche.db import make_engine, utc_now, write_tx
from affiche.posters import auth, credits, jobs
from affiche.posters.auth import PASSWORDS, identifier_key
from test_api import (HEADERS, IDENTIFIER, ORIGIN, PASSWORD, Counting, at_0012, client, credentials, failures, login,  # noqa: F401
                      password_hash, second_shop, settings, stored_password)
from test_config import TODAY, env  # noqa: F401
from test_credits import T, job
from test_db import engine, migrate_to  # noqa: F401

HASH = PASSWORDS.hash(os.urandom(12).hex())
NEW = os.urandom(12).hex()  # 24 characters


@pytest.mark.parametrize("typed, key", [
    ("originalphone", "originalphone"), ("Original Phone", "originalphone"), ("ORIGINAL-PHONE", "originalphone"),
    ("  original.phone ! ", "originalphone"), ("Óriginal Phöne", "originalphone"), ("ｏｒｉｇｉｎａｌｐｈｏｎｅ", "originalphone"),
    # A phone number in the written form the operator chose; another form is another identifier.
    ("034 12 345 67", "0341234567"), ("+261 34 12 345 67", "261341234567"),
    ("---", ""), ("", ""), ("ß", ""), ("a" * 70, "a" * 64)])
def test_case_accents_spaces_and_punctuation_do_not_count_in_an_identifier(typed, key):
    assert identifier_key(typed) == key


def test_a_shop_is_created_inside_the_callers_transaction_with_its_identifier_normalised(engine):
    with write_tx(engine) as conn:
        shop = shops.create_shop(conn, "Boutique Deux", " Boutique Deux ", HASH)
        assert tuple(conn.exec_driver_sql(
            "SELECT identifier, name, state, password_hash, revision, created_at = updated_at FROM shop_profile WHERE id=?",
            (shop,)).one()) == ("boutiquedeux", "Boutique Deux", "active", HASH, 1, 1)
    assert shop == 2
    for taken in ("boutique deux", "BOUTIQUE-DEUX", "Boutiqué Deux", "originalphone"):
        with pytest.raises(IntegrityError), write_tx(engine) as conn:
            shops.create_shop(conn, taken, None, HASH)
    for bad in ("ab", "x" * 33, "- -"):
        with pytest.raises(ValueError, match="3 to 32"), write_tx(engine) as conn:
            shops.create_shop(conn, bad, None, HASH)
    with pytest.raises(ValidationError), write_tx(engine) as conn:  # the profile form's own rule
        shops.create_shop(conn, "troisieme", "x" * 161, HASH)
    with pytest.raises(IntegrityError), write_tx(engine) as conn:  # never a password in plain text
        shops.create_shop(conn, "troisieme", None, "not-a-hash")
    with pytest.raises(RuntimeError), write_tx(engine) as conn:  # the caller's rollback undoes it
        shops.create_shop(conn, "troisieme", None, HASH)
        raise RuntimeError
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT id, identifier FROM shop_profile ORDER BY id").all() == [
            (1, "originalphone"), (2, "boutiquedeux")]


def change(client, current, new, headers=None):
    return client.post("/api/session/password", json={"current_password": current, "new_password": new}, headers=headers)


def refusal(answer):
    return answer.status_code, answer.json()["error"]["code"]


def device(client):
    return TestClient(client.app, base_url=ORIGIN, headers=HEADERS)


def test_the_owner_changes_his_password_and_only_his_other_devices_sign_in_again(client, monkeypatch, password_hash):
    """R-MULTI-SHOP-001: with the current password. This session is kept; the shop's other sessions end, no other shop's."""
    engine = client.app.state.engine
    login(client)
    login(desktop := device(client))
    shop_b, password_b = second_shop(engine)
    assert (b := device(client)).post("/api/session", json=credentials(password_b, "boutique-deux")).status_code == 200
    monkeypatch.setattr(auth, "PASSWORDS", counting := Counting(auth.PASSWORDS))
    short = change(client, PASSWORD, "x" * 9)
    assert (*refusal(short), short.json()["error"]["message_fr"]) == (
        422, "password_too_short", "Le nouveau mot de passe doit avoir au moins 10 caractères.")
    assert counting.calls == 0  # refused before any verification
    wrong = change(client, "wrong", NEW)
    assert (*refusal(wrong), wrong.json()["error"]["message_fr"]) == (403, "wrong_password", "Le mot de passe actuel n’est pas le bon.")
    assert counting.calls == 1 and failures(engine) == [IDENTIFIER]  # one verification; counted as a wrong sign-in
    assert stored_password(client.app) == password_hash and desktop.get("/api/session").json()["authenticated"] is True
    answer = change(client, PASSWORD, "x" * 10)
    assert (answer.status_code, answer.json()) == (200, {"changed": True}) and "set-cookie" not in answer.headers
    assert counting.calls == 2
    assert client.get("/api/session").json() == {"authenticated": True, "shop_id": 1}  # this device stays signed in
    assert desktop.get("/api/session").json() == {"authenticated": False}  # the shop's other device signs in again
    assert b.get("/api/session").json() == {"authenticated": True, "shop_id": shop_b}  # another shop untouched
    assert desktop.post("/api/session", json=credentials(PASSWORD)).status_code == 401
    assert desktop.post("/api/session", json=credentials("x" * 10)).status_code == 200
    assert device(client).post("/api/session", json=credentials(password_b, "boutique-deux")).status_code == 200


def test_wrong_current_passwords_share_the_sign_in_limits_and_are_verified_outside_any_write(client, monkeypatch):
    engine, real, calls = client.app.state.engine, auth.PASSWORDS, []
    login(client)
    _, password_b = second_shop(engine)

    class Probe:
        def verify_and_update(self, password, stored):
            # With the write lock held by the change, this second writer would wait 5 s and fail "database is locked".
            with write_tx(engine) as conn:
                conn.exec_driver_sql("INSERT INTO meta (key,value) VALUES ('probe','1') ON CONFLICT(key) DO NOTHING")
            calls.append(password)
            return False, None

    monkeypatch.setattr(auth, "PASSWORDS", Probe())
    for _ in range(auth.PAIR_LIMIT):
        assert refusal(change(client, "wrong", NEW)) == (403, "wrong_password")
    limited = change(client, PASSWORD, NEW)
    assert (*refusal(limited), limited.headers["retry-after"]) == (429, "rate_limited", "900")
    assert len(calls) == auth.PAIR_LIMIT  # not verified once limited
    # The pair counter of signing in: that shop from that address waits too; another shop does not.
    assert refusal(device(client).post("/api/session", json=credentials(PASSWORD))) == (429, "rate_limited")
    monkeypatch.setattr(auth, "PASSWORDS", real)
    assert device(client).post("/api/session", json=credentials(password_b, "boutique-deux")).status_code == 200
    assert client.get("/api/session").json() == {"authenticated": True, "shop_id": 1}  # still signed in


def test_a_reset_committed_during_the_verification_wins(client, monkeypatch):
    """The stored hash is read again in the transaction that would change it: the operator's reset is not overwritten."""
    engine, real = client.app.state.engine, auth.PASSWORDS
    login(client)
    reset = real.hash(os.urandom(12).hex())

    class Racing(Counting):
        def verify_and_update(self, password, stored):
            verified = super().verify_and_update(password, stored)
            with write_tx(engine) as conn:
                shops.set_password(conn, 1, reset)
            return verified

    monkeypatch.setattr(auth, "PASSWORDS", Racing(real))
    assert refusal(change(client, PASSWORD, NEW)) == (403, "wrong_password")
    assert stored_password(client.app) == reset


def test_the_change_follows_the_rules_of_any_change_and_a_suspended_shop_makes_none(client, password_hash):
    login(client)
    for headers, expected in (({"X-Affiche-Bundle": "2"}, (409, "bundle_outdated")),  # an older tab
                              ({"X-Affiche-Shop": "2"}, (409, "shop_changed")),  # a tab bound to another shop
                              ({"Origin": "https://evil.example"}, (403, "forbidden_origin"))):
        assert refusal(change(client, PASSWORD, NEW, headers)) == expected
    assert refusal(change(device(client), PASSWORD, NEW)) == (401, "unauthenticated")
    with write_tx(client.app.state.engine) as conn:
        conn.exec_driver_sql("UPDATE shop_profile SET state='suspended' WHERE id=1")
    assert refusal(change(client, PASSWORD, NEW)) == (401, "unauthenticated")  # its sessions stop at once
    assert stored_password(client.app) == password_hash


@pytest.fixture
def command(env, engine, tmp_path, capsys):
    """python -m affiche.shops on the test's data folder at head, never the developer's .env; (exit code, out, err)."""
    env.setenv("DATA_DIR", str(tmp_path))

    def run(*argv):
        code = shops.main(list(argv), env_file=None)
        out, err = capsys.readouterr()
        return code, out, err
    return run


def printed_password(out, label="password (shown once"):
    line, = [line for line in out.splitlines() if line.startswith(label)]
    return line.rsplit(": ", 1)[1]


def test_the_operator_creates_a_shop_and_resets_its_password_each_printed_once(command, engine, caplog):
    code, out, err = command("create", "Boutique Deux", "--name", "Boutique Deux")
    password = printed_password(out)
    assert (code, err) == (0, "") and len(password) == 12 and set(password) <= set(shops.ALPHABET)
    assert out.count(password) == 1 and password not in caplog.text  # printed once, never logged
    with engine.connect() as conn:
        shop = shops.find_shop(conn, "BOUTIQUE-DEUX")
        assert (shop.identifier, shop.name, shop.state) == ("boutiquedeux", "Boutique Deux", "active")
        assert conn.exec_driver_sql("SELECT password_hash FROM shop_profile WHERE id=?", (shop.id,)).scalar_one() not in out
    mine, _ = auth.login(engine, "boutique deux", password, "203.0.113.1")
    code, out, err = command("create", "boutique-deux")
    assert (code, out, err) == (1, "", "refused: the identifier boutiquedeux is already taken\n")
    assert command("create", "a-b") == (1, "", "refused: an identifier needs 3 to 32 letters or digits\n")
    assert command("create", "troisieme", "--name", "x" * 161) == (
        1, "", "refused: name: String should have at most 160 characters\n")
    code, out, err = command("set-password", "Boutique Deux")
    reset = printed_password(out)
    assert code == 0 and reset != password and out.count(reset) == 1 and reset not in caplog.text
    assert auth.session_shop(engine, mine) is None  # that shop's sessions ended
    with pytest.raises(auth.Refused, match="wrong_credentials"):
        auth.login(engine, "boutiquedeux", password, "203.0.113.1")
    auth.login(engine, "boutiquedeux", reset, "203.0.113.1")
    with engine.connect() as conn:
        assert [tuple(row)[:4] for row in shops.list_shops(conn)] == [
            (1, "originalphone", None, "active"), (shop.id, "boutiquedeux", "Boutique Deux", "active")]
    code, out, _ = command("list")
    assert code == 0 and out.splitlines()[1].startswith(f"{shop.id}\tboutiquedeux\tactive\tpassword\t")


def test_the_operator_ends_sessions_suspends_and_enables(command, engine, password_hash):
    shop_b, password_b = second_shop(engine)
    with write_tx(engine) as conn:
        shops.set_password(conn, 1, password_hash)
    a, _ = auth.login(engine, IDENTIFIER, PASSWORD, "203.0.113.1")
    b, _ = auth.login(engine, "boutique-deux", password_b, "203.0.113.1")
    code, out, err = command("suspend", "Boutique Deux")  # without --yes: shown, nothing done
    assert (code, out, err) == (1, f"boutiquedeux (shop {shop_b}, « Boutique Deux »): active\n",
                                "refused: nothing done: to suspend boutiquedeux, run again with --yes\n")
    assert auth.session_shop(engine, b) == shop_b
    code, out, _ = command("suspend", "Boutique Deux", "--yes")
    assert code == 0 and "suspended" in out and "0 queued jobs cancelled" in out
    assert auth.session_shop(engine, b) is None and auth.session_shop(engine, a) == 1
    with pytest.raises(auth.Refused, match="shop_suspended"):
        auth.login(engine, "boutiquedeux", password_b, "203.0.113.1")
    assert command("suspend", "boutiquedeux", "--yes")[:2] == (0, f"boutiquedeux (shop {shop_b}, « Boutique Deux ») was "
                                                                  "already suspended: nothing changed\n")
    assert command("enable", "boutiquedeux")[:2] == (0, f"boutiquedeux (shop {shop_b}, « Boutique Deux ») enabled: its "
                                                         "sessions work again\n")
    assert auth.session_shop(engine, b) == shop_b  # the same session, kept through the suspension
    assert "already active" in command("enable", "boutiquedeux")[1]
    assert command("end-sessions", "originalphone")[:2] == (0, "1 sessions ended (originalphone (shop 1, « sans nom »))\n")
    assert auth.session_shop(engine, a) is None and auth.session_shop(engine, b) == shop_b
    assert command("end-sessions", "--all")[:2] == (0, "1 sessions ended (every shop); 0 operator sessions ended\n")
    assert auth.session_shop(engine, b) is None
    assert command("enable", "nobody") == (1, "", "refused: no shop has the identifier nobody\n")


def operator_session(engine, token):
    """An operator session row, as the dashboard's sign-in writes it (D-ADMIN-001)."""
    with write_tx(engine) as conn:
        conn.exec_driver_sql("INSERT INTO operator_sessions VALUES (?,?,'2099-01-01T00:00:00.000000+00:00','203.0.113.1',"
                             "NULL)", (auth.token_hash(token), utc_now()))


def operator_state(engine):
    """(the stored operator hash, how many operator sessions)."""
    with engine.connect() as conn:
        return (conn.exec_driver_sql("SELECT value FROM meta WHERE key=?", (auth.OPERATOR_KEY,)).scalar(),
                conn.exec_driver_sql("SELECT count(*) FROM operator_sessions").scalar_one())


def test_the_operator_password_is_printed_once_stored_hashed_and_ends_every_operator_session(command, engine, caplog,
                                                                                            password_hash):
    with write_tx(engine) as conn:
        shops.set_password(conn, 1, password_hash)
    shop, _ = auth.login(engine, IDENTIFIER, PASSWORD, "203.0.113.1")
    operator_session(engine, "phone")
    operator_session(engine, "laptop")
    code, out, err = command("operator-password")
    password = printed_password(out, "operator password (shown once")
    assert (code, err, out) == (0, "", "new operator password; 2 operator sessions ended\noperator password (shown once; "
                                       f"keep it in your password manager): {password}\n")
    assert len(password) == 26 and set(password) <= set(shops.ALPHABET) and password not in caplog.text
    stored, sessions = operator_state(engine)
    assert sessions == 0 and stored.startswith("$argon2") and PASSWORDS.verify(password, stored) and stored not in out
    assert auth.session_shop(engine, shop) == 1  # no shop's session ends
    assert len(shops.new_password()) == 12  # a shop's password is unchanged
    operator_session(engine, "phone")
    code, out, _ = command("operator-password")  # run again: the hash is replaced
    again = printed_password(out, "operator password (shown once")
    assert code == 0 and again != password and out.startswith("new operator password; 1 operator sessions ended\n")
    replaced, sessions = operator_state(engine)
    assert sessions == 0 and PASSWORDS.verify(again, replaced) and not PASSWORDS.verify(password, replaced)
    # One transaction: when the sessions cannot be ended, the new hash is not written either.
    operator_session(engine, "phone")
    with write_tx(engine) as conn:
        conn.exec_driver_sql("CREATE TRIGGER stuck BEFORE DELETE ON operator_sessions BEGIN SELECT RAISE(ABORT, 'stuck'); "
                             "END")
    assert command("operator-password") == (1, "", "refused: stuck\n")
    assert operator_state(engine) == (replaced, 1)


def test_end_sessions_operator_ends_only_the_operators_and_all_ends_both(command, engine, password_hash):
    with write_tx(engine) as conn:
        shops.set_password(conn, 1, password_hash)
    shop, _ = auth.login(engine, IDENTIFIER, PASSWORD, "203.0.113.1")
    operator_session(engine, "phone")
    operator_session(engine, "laptop")
    assert command("end-sessions", "--operator") == (0, "2 operator sessions ended\n", "")
    assert operator_state(engine)[1] == 0 and auth.session_shop(engine, shop) == 1
    operator_session(engine, "phone")
    assert command("end-sessions", "originalphone")[:2] == (0, "1 sessions ended (originalphone (shop 1, « sans nom »))\n")
    assert operator_state(engine)[1] == 1  # one shop's sessions: never the operator's
    shop, _ = auth.login(engine, IDENTIFIER, PASSWORD, "203.0.113.1")
    assert command("end-sessions", "--all") == (0, "1 sessions ended (every shop); 1 operator sessions ended\n", "")
    assert operator_state(engine)[1] == 0 and auth.session_shop(engine, shop) is None


@pytest.mark.parametrize("argv", [[], ["suspend"], ["end-sessions"], ["end-sessions", "x", "--all"], ["delete", "x"],
                                  ["end-sessions", "x", "--operator"], ["end-sessions", "--all", "--operator"],
                                  ["operator-password", "x"],
                                  ["grant", "x", "1", "--ref", "r"], ["grant", "x", "1", "--offered", "--bought", "--ref", "r"],
                                  ["grant", "x", "1.5", "--offered", "--ref", "r"], ["grant", "x", "1", "--offered"],
                                  ["correct", "x", "1", "--ref", "r"], ["move-payment", "r", "a", "--note", "n"],
                                  # Past a billion: SQLite's integers or the balance's SUM would overflow.
                                  ["grant", "x", "9223372036854775808", "--offered", "--ref", "r"],
                                  ["grant", "x", "1", "--bought", "--amount-ar", "1000000001", "--method", "m", "--ref", "r"],
                                  ["create", "x", "--welcome", "9223372036854775808"],
                                  ["correct", "x", "-1000000001", "--ref", "r", "--note", "n"],
                                  ["correct", "x", "0", "--ref", "r", "--note", "n", "--amount-ar", "-9223372036854775808"]])
def test_a_wrong_command_line_is_a_usage_error(command, argv):
    with pytest.raises(SystemExit) as exited:
        command(*argv)
    assert exited.value.code == 2


def test_a_number_past_a_billion_is_a_usage_error_that_says_so(command, capsys):
    with pytest.raises(SystemExit) as exited:
        command("grant", "originalphone", "9223372036854775808", "--offered", "--ref", "x")
    assert exited.value.code == 2 and capsys.readouterr().err.endswith(
        "python -m affiche.shops grant: error: argument credits: a whole number from -1,000,000,000 to 1,000,000,000: "
        "'9223372036854775808'\n")


def test_the_command_never_migrates_and_needs_a_database_at_head(env, tmp_path, monkeypatch, capsys):
    env.setenv("DATA_DIR", str(tmp_path / "none"))
    assert shops.main(["list"], env_file=None) == 1
    assert capsys.readouterr().err.startswith("refused: no database at ") and not (tmp_path / "none").exists()
    env.setenv("DATA_DIR", str(tmp_path))
    old = make_engine(tmp_path)
    migrate_to(old, "0012", monkeypatch)
    old.dispose()
    assert shops.main(["create", "boutique"], env_file=None) == 1
    err = capsys.readouterr().err
    assert err.startswith("refused: the database is at 0012, this code expects 0") and err.endswith(
        ": start the application of this version once; this command never migrates\n")
    with sqlite3.connect(tmp_path / "affiche.db") as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchall() == [("0012",)]


def test_a_backup_from_before_0013_is_migrated_and_repaired_before_the_service_starts(settings, monkeypatch, capsys):
    """deploy/README.md, Restore: the command refuses a 0012 database; the application's own start, run once in a
    one-off container, migrates it; the repairs follow while the service is stopped; then the service starts without
    SHOP_PASSWORD_HASH, and the restored session of a lost phone no longer works."""
    cookie = at_0012(settings, monkeypatch, product=True)
    assert shops.main(["list"], env_file=None) == 1
    assert "the database is at 0012" in capsys.readouterr().err
    started = runtime.start(load_settings(env_file=None), "api")  # the runbook's one-off: start, no server
    started.lock_file.close()
    started.engine.dispose()
    assert shops.main(["list"], env_file=None) == 0
    assert capsys.readouterr().out.startswith("1\toriginalphone\tactive\tno password\t")  # restore.sh names it
    assert shops.main(["end-sessions", "--all"], env_file=None) == 0
    assert capsys.readouterr().out == "1 sessions ended (every shop); 0 operator sessions ended\n"
    assert shops.main(["set-password", "originalphone"], env_file=None) == 0
    password = printed_password(capsys.readouterr().out)
    settings.shop_password_hash = None  # removed from app.env after Release 1
    with TestClient(create_app(settings), base_url=ORIGIN, headers=HEADERS) as client:
        assert client.get("/api/session", headers=cookie).json()["authenticated"] is False
        assert client.post("/api/session", json=credentials(password)).status_code == 200


# --- Credits (D-BALANCE-005): the `engine` fixture's shop 1 holds 100 offered credits, line 1, reference `tests` -------

WARNING = ("WARNING: the outstanding credits would cost more than what is left of the cap: raise SPEND_CAP_USD "
           "(deploy/README.md)\n")


def lines(engine):
    with engine.connect() as conn:
        return conn.exec_driver_sql("SELECT shop_id, kind, origin, credits, amount_ar, method, ref, job_id, note, actor"
                                    " FROM credit_grants WHERE ref <> 'tests' ORDER BY id").all()


def available(engine, shop=1):
    with engine.connect() as conn:
        return credits.balance(conn, shop)["available"]


def product(conn):
    conn.exec_driver_sql("INSERT OR IGNORE INTO product_inputs VALUES ('in1',1,'P1','JBL','Bleu','[]','{}',NULL,?)", (T,))


def image_calls(engine, *costs, kind="scene", provider="openai", status="succeeded", estimate=0,
                at=f"{TODAY}T00:00:01.000000+00:00"):
    """Calls as the worker records them, each on a finished job of its own that takes no credit."""
    with write_tx(engine) as conn:
        product(conn)
        for cost in costs:
            id = os.urandom(6).hex()
            conn.exec_driver_sql("INSERT INTO creations VALUES (?,1,NULL,1,'active',?,?)", (id, T, T))
            conn.exec_driver_sql("INSERT INTO creation_versions VALUES (?,1,'{}','h',?)", (id, T))
            conn.exec_driver_sql("INSERT INTO poster_jobs (id,shop_id,creation_id,origin_revision,input_id,kind,input_json,"
                                 "input_hash,status,created_at) VALUES (?,1,?,1,'in1',?,'{}','h','succeeded',?)",
                                 (id, id, kind, T))
            conn.exec_driver_sql("INSERT INTO poster_calls (id,job_id,call_no,provider,model,rate_card_json,status,"
                                 "cost_micros,cost_is_estimate,created_at) VALUES (?,?,1,?,'m','{}',?,?,?,?)",
                                 (id, id, provider, status, cost, estimate, at))


def test_create_grants_the_welcome_credits_in_the_shops_own_transaction(command, engine, monkeypatch):
    code, out, err = command("create", "Boutique Deux")
    assert (code, err) == (0, "") and out.startswith(
        "shop 2 created: identifier boutiquedeux, active, 5 offered welcome credits (line 2)\npassword (shown once")
    code, out, _ = command("create", "Boutique Trois", "--welcome", "0")
    assert code == 0 and out.startswith("shop 3 created: identifier boutiquetrois, active, no welcome credits\n")
    assert command("create", "Boutique Quatre", "--welcome", "-1") == (1, "", "refused: a grant is 1 credit or more\n")
    real = credits.grant

    def failing(*args, **kwargs):  # the welcome line is written, then its transaction fails
        real(*args, **kwargs)
        raise ValueError("fault after the welcome line")
    monkeypatch.setattr(credits, "grant", failing)
    assert command("create", "Boutique Cinq") == (1, "", "refused: fault after the welcome line\n")
    with engine.connect() as conn:  # neither refused shop exists
        assert conn.exec_driver_sql("SELECT id, identifier FROM shop_profile ORDER BY id").all() == [
            (1, "originalphone"), (2, "boutiquedeux"), (3, "boutiquetrois")]
    assert lines(engine) == [(2, "grant", "offered", 5, None, None, "welcome", None, "Crédits de bienvenue", "operator")]
    assert [available(engine, shop) for shop in (2, 3)] == [5, 0]


def test_the_headroom_prices_the_outstanding_credits_at_the_last_50_real_image_costs(engine, env):
    settings = load_settings(env_file=None)  # a cap of 20 USD since today; ESTIMATE_SCENE_USD 0.40
    with engine.connect() as conn:  # no real image cost yet: the estimate
        assert shops.headroom(conn, settings) == {"cap": 20_000_000, "spent": 0, "left": 20_000_000, "outstanding": 100,
                                                  "images": 0, "unit": 400_000, "cost": 40_000_000, "warning": True}
    image_calls(engine, 1_000_000, at=f"{TODAY}T00:00:00.000000+00:00")  # older than the last 50
    image_calls(engine, *[40_000] * 50)
    image_calls(engine, 900_000, estimate=1)  # a reservation kept as an estimate
    image_calls(engine, 0, provider="stub")
    image_calls(engine, 900_000, status="failed")
    image_calls(engine, 5_000, kind="plan", provider="claude")  # not an image
    with write_tx(engine) as conn:  # a shop below zero takes nothing off the others
        shops.create_shop(conn, "boutiquedeux", None, HASH)
        job(conn, "late", shop=2)
    with engine.connect() as conn:
        assert credits.balance(conn, 2)["available"] == -1
        assert shops.headroom(conn, settings) == {"cap": 20_000_000, "spent": 4_805_000, "left": 15_195_000,
                                                  "outstanding": 100, "images": 50, "unit": 40_000, "cost": 4_000_000,
                                                  "warning": False}


def test_the_headroom_rounds_up_only_at_the_end_so_a_short_cap_always_warns(command, engine, env):
    """The review's case: 40,000.5 µUSD an image on average, 1,000 credits outstanding, 40,000,250 µUSD left. Rounding
    the average first (40,000) priced them at 40,000,000 and gave no warning."""
    image_calls(engine, *[40_000] * 49, 40_025, at="2000-01-01T00:00:00.000000+00:00")  # before SPEND_CAP_SINCE
    env.setenv("SPEND_CAP_USD", "40.00025")
    code, out, _ = command("grant", "originalphone", "900", "--offered", "--ref", "pack")
    assert code == 0 and out.endswith(
        f"service cap 40.00 USD: 0.00 spent since {TODAY}, 40.00 left; credits outstanding in all shops 1000 × 0.040 USD "
        "(average of the last 50 images) = 40.01 USD\n" + WARNING)  # left rounded down, cost up, as the warning sees


def test_grant_prints_its_line_the_balance_and_the_headroom_and_refuses_a_reference_twice(command, engine, env):
    code, out, err = command("grant", "Original Phone", "5", "--offered", "--ref", "Geste-1", "--note", "geste")
    assert (code, err) == (0, "") and out == (
        "granted 5 offered credits to originalphone (line 2): available 105, en attente 0\n"
        f"service cap 20.00 USD: 0.00 spent since {TODAY}, 20.00 left; credits outstanding in all shops 105 × 0.400 USD "
        "(ESTIMATE_SCENE_USD: no image cost yet) = 42.00 USD\n" + WARNING)
    image_calls(engine, *[40_000] * 50)
    env.setenv("SPEND_CAP_USD", "6.60")  # 4.60 left after the 2.00 spent: what 115 credits would cost, no more
    code, out, err = command("grant", "originalphone", "10", "--bought", "--amount-ar", "10000", "--method", "MVola",
                             "--ref", "MV-1")
    assert (code, err) == (0, "") and out == (
        "granted 10 bought credits to originalphone (line 3): available 115, en attente 0\n"
        f"service cap 6.60 USD: 2.00 spent since {TODAY}, 4.60 left; credits outstanding in all shops 115 × 0.040 USD "
        "(average of the last 50 images) = 4.60 USD\n")
    code, out, _ = command("grant", "originalphone", "1", "--offered", "--ref", "geste-2")
    assert code == 0 and out.endswith("116 × 0.040 USD (average of the last 50 images) = 4.64 USD\n" + WARNING)
    second_shop(engine)
    for argv, refused in (
            (("originalphone", "5", "--offered", "--ref", " GESTE-1 "),  # typed again, in another spelling
             "this shop already has a grant with the reference 'Geste-1' (line 2)"),
            (("boutiquedeux", "10", "--bought", "--amount-ar", "10000", "--method", "mvola", "--ref", "mv-1"),
             "the payment 'MV-1' is already recorded in shop originalphone (line 3): a payment changes shop only by "
             "move-payment"),
            (("originalphone", "1", "--offered", "--amount-ar", "5", "--ref", "x"),
             "a grant is offered (no amount, no method) or bought"),
            (("originalphone", "1", "--bought", "--ref", "x"), "a bought grant needs its amount in ariary and its payment "
                                                               "method"),
            (("originalphone", "1", "--offered", "--ref", "  "), "a reference has 1 to 100 characters"),
            (("nobody", "1", "--offered", "--ref", "x"), "no shop has the identifier nobody")):
        assert command("grant", *argv) == (1, "", f"refused: {refused}\n")
    assert lines(engine) == [(1, "grant", "offered", 5, None, None, "Geste-1", None, "geste", "operator"),
                             (1, "grant", "bought", 10, 10000, "mvola", "MV-1", None, None, "operator"),
                             (1, "grant", "offered", 1, None, None, "geste-2", None, None, "operator")]
    assert available(engine) == 116


def test_move_payment_moves_a_whole_unspent_payment_and_a_correction_under_its_reference_blocks_it(command, engine):
    second_shop(engine)
    second_shop(engine, "Boutique Trois", "Boutique Trois")  # lines 2 and 3: their 100 credits each
    command("grant", "originalphone", "10", "--bought", "--amount-ar", "10000", "--method", "mvola", "--ref", "MV-1")
    assert command("move-payment", "mv-1", "Original Phone", "boutiquedeux", "--note", "mauvaise boutique") == (
        0, "payment moved from originalphone (line 5: available 100, en attente 0) to boutiquedeux (line 6: available "
           "110, en attente 0)\n", "")
    with engine.connect() as conn:  # typed in another spelling, moved under the payment's own
        assert conn.exec_driver_sql("SELECT DISTINCT ref FROM credit_grants WHERE id BETWEEN 4 AND 6").all() == [("MV-1",)]
    assert command("move-payment", "MV-1", "boutiquedeux", "originalphone", "--note", "retour") == (
        1, "", "refused: the destination shop already has a line with the reference 'MV-1' (line 4)\n")
    command("correct", "boutiquedeux", "-101", "--ref", "retrait", "--note", "crédits dépensés")
    assert command("move-payment", "MV-1", "boutiquedeux", "boutiquetrois", "--note", "encore") == (
        1, "", "refused: the source shop has 9 credits left of the payment's 10: it stays where it is\n")
    # The runbook's concession when the payment cannot move: offered, so it counts no money.
    assert command("grant", "boutiquetrois", "10", "--offered", "--ref", "MV-1-geste", "--note",
                   "paiement MV-1 crédité par erreur à boutiquedeux")[0] == 0
    # A plain correction under a payment's reference, in any spelling, takes the shop's one correction under it.
    command("grant", "originalphone", "10", "--bought", "--amount-ar", "5000", "--method", "cash", "--ref", "MV-2")
    assert command("correct", "originalphone", "+1", "--ref", "mv-2", "--note", "geste")[0] == 0
    assert command("move-payment", "MV-2", "originalphone", "boutiquetrois", "--note", "mauvaise boutique") == (
        1, "", "refused: the payment 'MV-2' was already moved or corrected in the source shop (line 10)\n")
    assert command("correct", "originalphone", "0", "--ref", "MV-2", "--amount-ar", "500", "--note", "montant") == (
        1, "", "refused: the payment 'MV-2' was already moved or corrected in this shop\n")
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT shop_id, SUM(amount_ar) FROM credit_grants WHERE amount_ar IS NOT NULL"
                                    " GROUP BY shop_id").all() == [(1, 5000), (2, 10000)]  # each payment once


def test_correct_repays_a_job_once_fixes_an_amount_and_never_goes_below_zero(command, engine):
    with write_tx(engine) as conn:
        product(conn)
        job(conn, "made", "succeeded")
        job(conn, "lost", "failed")
    assert command("correct", "originalphone", "+1", "--ref", "defaut-1", "--job", "made", "--note", "produit déformé") == (
        0, "corrected originalphone (line 2): +1 credits, job made repaid; available 100, en attente 0\n", "")
    for argv, refused in ((("+1", "--ref", "defaut-2", "--job", "made"), "this job was already repaid (line 2)"),
                          (("+1", "--ref", "defaut-3", "--job", "lost"),
                           "only a succeeded job of this shop that took a credit can be repaid"),
                          (("+2", "--ref", "defaut-4", "--job", "made"), "a job is repaid with exactly 1 credit and no amount")):
        assert command("correct", "originalphone", *argv, "--note", "encore") == (1, "", f"refused: {refused}\n")
    command("grant", "originalphone", "10", "--bought", "--amount-ar", "1000", "--method", "mvola", "--ref", "MV-1")
    assert command("correct", "originalphone", "0", "--ref", "MV-1", "--amount-ar", "-1000", "--note", "montant") == (
        1, "", "refused: the payment's total would be 0 Ar: it must stay above zero\n")
    assert command("correct", "originalphone", "0", "--ref", "MV-1", "--amount-ar", "-400", "--note", "montant") == (
        0, "corrected originalphone (line 4): -400 Ar; available 110, en attente 0\n", "")
    assert command("correct", "originalphone", "-111", "--ref", "retrait", "--note", "trop") == (
        1, "", "refused: the balance would go below zero (available 110)\n")
    assert command("correct", "originalphone", "-10", "--ref", "retrait", "--note", "trop") == (
        0, "corrected originalphone (line 5): -10 credits; available 100, en attente 0\n", "")
    assert command("correct", "originalphone", "-10", "--ref", "Retrait", "--note", "trop") == (  # typed again
        1, "", "refused: this shop already has a correction with the reference 'retrait' (line 5)\n")
    assert lines(engine)[-3:] == [(1, "grant", "bought", 10, 1000, "mvola", "MV-1", None, None, "operator"),
                                  (1, "correction", None, 0, -400, None, "MV-1", None, "montant", "operator"),
                                  (1, "correction", None, -10, None, None, "retrait", None, "trop", "operator")]


def test_pause_without_yes_only_says_whether_the_service_is_paused(command, engine):
    def paused():
        with engine.connect() as conn:
            return jobs.paused(conn)
    nothing = "refused: nothing done: to pause new requests to the AI for every shop, run again with --yes\n"
    assert command("pause") == (1, "the service is not paused\n", nothing)
    assert paused() is None
    code, out, err = command("pause", "--yes")
    assert (code, err) == (0, "") and (since := paused()) and out == (
        f"the service is paused since {since}: no new request reaches the AI for any shop (images, styles, text "
        "proposals, reads); what was admitted finishes; resume lifts it\n")
    assert command("pause", "--yes") == (0, f"the service was already paused since {since}: nothing changed\n", "")
    assert command("pause") == (1, f"the service is paused since {since}\n", nothing)
    assert command("resume") == (0, "the service resumed: new requests reach the AI again\n", "")
    assert paused() is None
    assert command("resume") == (0, "the service was not paused: nothing changed\n", "")


def test_the_purchase_text_is_set_and_read_back_never_blank(command, engine, env):
    assert command("purchase-text") == (0, "purchase text: « Pour obtenir des crédits, contactez l’administrateur. » "
                                           "(not set: the fallback every shop reads)\n", "")
    sentence = ("Pack de 10 crédits : 10 000 Ar par MVola au 034 00 000 00, avec votre identifiant en référence. "
                "Crédits ajoutés le jour même, de 8 h à 18 h.")
    assert command("purchase-text", f"  {sentence}\n") == (0, f"purchase text set: « {sentence} »\n", "")
    for blank in ("  ", "x" * 501):
        assert command("purchase-text", blank) == (1, "", "refused: a purchase text has 1 to 500 characters\n")
    assert command("purchase-text") == (0, f"purchase text: « {sentence} »\n", "")
    with engine.connect() as conn:
        assert credits.purchase_text(conn, load_settings(env_file=None)) == sentence


def test_a_purchase_text_whose_read_back_fails_is_not_saved(command, engine, monkeypatch):
    """A refusal means nothing written: the text is read back in the transaction that writes it."""
    def unreadable(conn, settings):
        raise OperationalError("SELECT value FROM meta", {}, sqlite3.OperationalError("disk I/O error"))
    monkeypatch.setattr(credits, "purchase_text", unreadable)
    assert command("purchase-text", "Pack de 10 crédits : 10 000 Ar.") == (1, "", "refused: disk I/O error\n")
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT value FROM meta WHERE key='purchase_text_fr'").first() is None


# --- The restore's copy (D-BALANCE-005): a backup by affiche.backup, lines written after it, then the backup put back
# as restore.sh puts it, the database it replaced kept beside it -------------------------------------------------------

KEPT = "affiche.db.before-restore-20261117T090000Z"
LEDGER = ("SELECT p.identifier, g.kind, g.origin, g.credits, g.amount_ar, g.method, g.ref, g.job_id, g.note, g.actor,"
          " g.created_at FROM credit_grants g JOIN shop_profile p ON p.id = g.shop_id ORDER BY g.id")
NAME = 'Chez "Rado"\n$(touch pwned)'


def written(monkeypatch, day):
    """The lines that follow carry this date (credits stamps each one with utc_now)."""
    monkeypatch.setattr(credits, "utc_now", lambda: f"{day}T10:00:00.000000+00:00")


def done(command, *argv):
    code, out, err = command(*argv)
    assert (code, err) == (0, ""), err
    return out


def backed_up(folder):
    """The nightly backup of the test's data folder: one consistent copy of the database as it is now."""
    return folder / "backups" / "db" / backup.run(folder, folder / "backups")["db_file"]


def put_back(engine, folder, copy):
    """restore.sh: the live database set aside under its kept name with its -wal (taken while a connection is open, so
    its last lines are still in the -wal), the backup in its place, started once. Returns the kept file."""
    kept = folder / KEPT
    shutil.copy(folder / "affiche.db", kept)
    shutil.copy(folder / "affiche.db-wal", f"{kept}-wal")
    engine.dispose()  # the service stops
    shutil.copy(copy, folder / "affiche.db")
    with engine.connect():  # the application's start, once
        pass
    engine.dispose()
    return kept


def read(database, sql):
    db = sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True)
    try:
        return db.execute(sql).fetchall()
    finally:
        db.close()


def kept_bytes(kept):
    return kept.read_bytes(), Path(f"{kept}-wal").read_bytes()


def test_the_copy_brings_a_chain_of_moves_back_in_its_order_with_its_dates_and_a_rerun_copies_nothing(
        command, engine, tmp_path, monkeypatch):
    """A→B→C with A created last: the shops' ids run against the movement, so a copy shop by shop would bring B's grant
    before A's reversal, and be refused."""
    with write_tx(engine) as conn:
        for identifier in ("boutiquec", "boutiqueb", "boutiquea"):  # shops 2, 3, 4
            shops.create_shop(conn, identifier, None, HASH)
    written(monkeypatch, "2026-09-01")
    done(command, "grant", "originalphone", "10", "--bought", "--amount-ar", "5000", "--method", "cash", "--ref", "P-1")
    copy = backed_up(tmp_path)
    written(monkeypatch, "2026-10-02")
    done(command, "grant", "boutiquea", "10", "--bought", "--amount-ar", "10000", "--method", "mvola", "--ref", "MV-1",
         "--note", "pack de 10")
    done(command, "move-payment", "mv-1", "boutiquea", "boutiqueb", "--note", "mauvaise boutique")
    written(monkeypatch, "2026-11-03")
    done(command, "move-payment", "MV-1", "boutiqueb", "boutiquec", "--note", "encore la mauvaise")
    done(command, "grant", "boutiqueb", "2", "--offered", "--ref", "geste")
    kept = put_back(engine, tmp_path, copy)
    monkeypatch.setattr(credits, "utc_now", utc_now)  # today's clock again: a copied line keeps its own date
    live, unchanged = tmp_path / "affiche.db", (tmp_path / "affiche.db").read_bytes()
    original = kept_bytes(kept)
    lines_to_copy = (
        "line 3 of the kept database (boutiquea grant 'MV-1'), +10 credits, +10000 Ar, written "
        "2026-10-02T10:00:00.000000+00:00 by operator\n"
        "{0}: line 4 of the kept database (boutiquea correction 'MV-1'), -10 credits, -10000 Ar, written "
        "2026-10-02T10:00:00.000000+00:00 by operator\n"
        "{0}: line 5 of the kept database (boutiqueb grant 'MV-1'), +10 credits, +10000 Ar, written "
        "2026-10-02T10:00:00.000000+00:00 by operator\n"
        "{0}: line 6 of the kept database (boutiqueb correction 'MV-1'), -10 credits, -10000 Ar, written "
        "2026-11-03T10:00:00.000000+00:00 by operator\n"
        "{0}: line 7 of the kept database (boutiquec grant 'MV-1'), +10 credits, +10000 Ar, written "
        "2026-11-03T10:00:00.000000+00:00 by operator\n"
        "{0}: line 8 of the kept database (boutiqueb grant 'geste'), +2 credits, written 2026-11-03T10:00:00.000000+00:00 "
        "by operator\n")
    header = f"the kept database {kept} holds 8 credit lines: 2 here already, 6 to copy, 0 skipped\n"
    assert command("after-restore", str(kept)) == (0, header + "to copy: " + lines_to_copy.format("to copy")
                                                   + "report only, nothing written: run again with --apply to copy\n", "")
    assert live.read_bytes() == unchanged and kept_bytes(kept) == original  # read only, the kept -wal never folded in
    assert command("after-restore", str(kept), "--apply") == (
        0, header + "copied: " + lines_to_copy.format("copied") + "copied 6 lines\n", "")
    assert kept_bytes(kept) == original
    # Every line, in its order, with its shop by identifier, its date, actor, note, amounts and reference as stored.
    assert read(live, LEDGER) == read(kept, LEDGER)
    by_month = ("SELECT substr(created_at, 1, 7), SUM(amount_ar) FROM credit_grants WHERE amount_ar IS NOT NULL"
                " GROUP BY 1 ORDER BY 1")
    assert read(live, by_month) == read(kept, by_month) == [("2026-09", 5000), ("2026-10", 10000), ("2026-11", 0)]
    assert read(live, "SELECT p.identifier, SUM(g.amount_ar) FROM credit_grants g JOIN shop_profile p ON p.id = g.shop_id"
                      " WHERE g.ref = 'MV-1' GROUP BY 1 ORDER BY 1") == [
        ("boutiquea", 0), ("boutiqueb", 0), ("boutiquec", 10000)]  # the payment's money in C only
    assert [available(engine, shop) for shop in (2, 3, 4)] == [10, 2, 0]
    ledger = read(live, LEDGER)
    assert command("after-restore", str(kept), "--apply") == (
        0, f"the kept database {kept} holds 8 credit lines: 8 here already, 0 to copy, 0 skipped\nnothing to copy\n", "")
    assert read(live, LEDGER) == ledger


def test_a_shop_created_after_the_backup_blocks_the_whole_copy_until_its_printed_command_creates_it(
        command, engine, tmp_path, monkeypatch):
    """Mapped by identifier: chezrado was shop 3 in the kept database and is shop 2 once created again."""
    copy = backed_up(tmp_path)
    written(monkeypatch, "2026-11-10")
    done(command, "create", "Autre", "--welcome", "0")
    done(command, "create", "Chez Rado", "--name", NAME, "--welcome", "3")  # not the default welcome
    done(command, "grant", "chezrado", "10", "--bought", "--amount-ar", "10000", "--method", "mvola", "--ref", "MV-3")
    done(command, "grant", "originalphone", "4", "--offered", "--ref", "geste")
    kept = put_back(engine, tmp_path, copy)
    code, out, err = command("after-restore", str(kept), "--apply")
    assert (code, err) == (1, "refused: nothing copied: chezrado missing here; create each with the command above, then "
                              "run after-restore again\n")
    assert lines(engine) == []  # not even the line of the shop that is here
    printed = re.search(r"^  (python -m affiche\.shops create chezrado .*? --welcome 0)$", out, re.M | re.S).group(1)
    assert shlex.split(printed) == ["python", "-m", "affiche.shops", "create", "chezrado", "--name", NAME, "--welcome", "0"]
    assert out == (
        f"the kept database {kept} holds 4 credit lines: 1 here already, 3 to copy, 0 skipped\n"
        "to copy: line 2 of the kept database (chezrado grant 'welcome'), +3 credits, written "
        "2026-11-10T10:00:00.000000+00:00 by operator\n"
        "to copy: line 3 of the kept database (chezrado grant 'MV-3'), +10 credits, +10000 Ar, written "
        "2026-11-10T10:00:00.000000+00:00 by operator\n"
        "to copy: line 4 of the kept database (originalphone grant 'geste'), +4 credits, written "
        "2026-11-10T10:00:00.000000+00:00 by operator\n"
        "shops of the kept database missing here: create each with this command, then run after-restore again\n"
        "  python -m affiche.shops create autre --welcome 0\n"
        f"  {printed}\n")
    code, out, _ = command("after-restore", str(kept))
    assert code == 0 and out.endswith(f"  {printed}\nreport only, nothing written: create the missing shops first, then "
                                      "run again with --apply\n")
    assert lines(engine) == [] and not list(tmp_path.rglob("pwned")) and not Path("pwned").exists()  # printed, never run
    # The operator runs it: the shell gives the command exactly these arguments.
    assert done(command, *shlex.split(printed)[3:]).startswith("shop 2 created: identifier chezrado, active, no welcome")
    code, out, _ = command("after-restore", str(kept), "--apply")
    assert code == 0 and out.endswith("\n  python -m affiche.shops create autre --welcome 0\ncopied 3 lines\n")
    assert lines(engine) == [(2, "grant", "offered", 3, None, None, "welcome", None, "Crédits de bienvenue", "operator"),
                             (2, "grant", "bought", 10, 10000, "mvola", "MV-3", None, None, "operator"),
                             (1, "grant", "offered", 4, None, None, "geste", None, None, "operator")]
    with engine.connect() as conn:
        assert shops.find_shop(conn, "chezrado").name == NAME
    assert not list(tmp_path.rglob("pwned")) and not Path("pwned").exists()


def test_a_repayment_is_copied_only_once_its_job_is_here_an_image_that_took_a_credit(
        command, engine, tmp_path, monkeypatch):
    """D-BALANCE-005's table: succeeded and counted here, copied; ended without an image, skipped; still running,
    decided after it ends; absent, skipped (its charge went with it). The images made after the backup are counted, and
    a balance a copied line takes below zero is said."""
    with write_tx(engine) as conn:
        product(conn)
        job(conn, "made", "succeeded")
        job(conn, "ended", "running")
        job(conn, "waiting", "running")
    copy = backed_up(tmp_path)
    with write_tx(engine) as conn:
        conn.exec_driver_sql("UPDATE poster_jobs SET status='succeeded' WHERE id IN ('ended', 'waiting')")
        job(conn, "new", "succeeded")
    written(monkeypatch, "2026-11-12")
    for id in ("made", "ended", "waiting", "new"):
        done(command, "correct", "originalphone", "+1", "--ref", f"defaut-{id}", "--job", id, "--note", "produit déformé")
    done(command, "correct", "originalphone", "-100", "--ref", "retrait", "--note", "remboursé")
    kept = put_back(engine, tmp_path, copy)
    with write_tx(engine) as conn:  # after the restart, one ended without an image; one still runs
        conn.exec_driver_sql("UPDATE poster_jobs SET status='failed' WHERE id='ended'")
    skipped = (
        "skipped line 3 of the kept database (originalphone correction 'defaut-ended'): its job is failed here and holds "
        "no credit\n"
        "skipped line 4 of the kept database (originalphone correction 'defaut-waiting'): its job is still running here: "
        "decide after it ends, by running after-restore again\n"
        "skipped line 5 of the kept database (originalphone correction 'defaut-new'): its job is not here (made after "
        "the backup): the restore removed that image and its charge\n")
    to_copy = (
        "{0}: line 2 of the kept database (originalphone correction 'defaut-made'), +1 credits, written "
        "2026-11-12T10:00:00.000000+00:00 by operator\n"
        "{0}: line 6 of the kept database (originalphone correction 'retrait'), -100 credits, written "
        "2026-11-12T10:00:00.000000+00:00 by operator\n")
    after = ("originalphone: 1 images made after the backup are gone and are not charged\n"
             "originalphone: available -1 after the copy, below zero, with 1 generations waiting or running: each of "
             "them that ends without an image gives one credit back; what stays below zero is yours to settle\n")
    header = f"the kept database {kept} holds 6 credit lines: 1 here already, 2 to copy, 3 skipped\n"
    assert command("after-restore", str(kept)) == (
        0, header + skipped + to_copy.format("to copy") + after
        + "report only, nothing written: run again with --apply to copy\n", "")
    assert command("after-restore", str(kept), "--apply") == (
        0, header + skipped + to_copy.format("copied") + after + "copied 2 lines\n", "")
    assert available(engine) == -1
    with write_tx(engine) as conn:  # the generation that ran succeeds: its repayment comes on the next run
        conn.exec_driver_sql("UPDATE poster_jobs SET status='succeeded' WHERE id='waiting'")
    assert command("after-restore", str(kept), "--apply") == (
        0, f"the kept database {kept} holds 6 credit lines: 3 here already, 1 to copy, 2 skipped\n"
           + skipped.split("\n", 1)[0] + "\n" + skipped.split("\n")[2] + "\n"
           "copied: line 4 of the kept database (originalphone correction 'defaut-waiting'), +1 credits, written "
           "2026-11-12T10:00:00.000000+00:00 by operator\n"
           "originalphone: 1 images made after the backup are gone and are not charged\ncopied 1 lines\n", "")
    assert [(line.credits, line.ref, line.job_id) for line in lines(engine)] == [
        (1, "defaut-made", "made"), (-100, "retrait", None), (1, "defaut-waiting", "waiting")]
    assert available(engine) == 0


def test_a_payment_typed_again_is_here_in_any_spelling_and_one_typed_into_another_shop_is_skipped(
        command, engine, tmp_path):
    second_shop(engine)  # boutiquedeux, its credits at line 2
    copy = backed_up(tmp_path)
    done(command, "grant", "originalphone", "10", "--bought", "--amount-ar", "7000", "--method", "mvola", "--ref", "MV-7")
    done(command, "grant", "originalphone", "10", "--bought", "--amount-ar", "8000", "--method", "mvola", "--ref", "MV-8")
    kept = put_back(engine, tmp_path, copy)
    # From his payment records, the operator types both again after the restore: one in its shop, one in another.
    done(command, "grant", "originalphone", "10", "--bought", "--amount-ar", "7000", "--method", "mvola", "--ref", "mv-7")
    done(command, "grant", "boutiquedeux", "10", "--bought", "--amount-ar", "8000", "--method", "mvola", "--ref", "mv-8")
    skipped = (0, f"the kept database {kept} holds 4 credit lines: 3 here already, 0 to copy, 1 skipped\n"
                  "here already: line 3 of the kept database (originalphone grant 'MV-7'), typed as 'mv-7' (line 3 here)\n"
                  "skipped line 4 of the kept database (originalphone grant 'MV-8'): this payment's lines here (line 4 "
                  "here 'mv-8') are not the first ones of its kept history: this database's history stands; check this "
                  "payment by hand (grant, move-payment)\nnothing to copy\n", "")
    assert command("after-restore", str(kept)) == skipped
    assert command("after-restore", str(kept), "--apply") == skipped
    ledger = lines(engine)
    done(command, "move-payment", "MV-8", "boutiquedeux", "originalphone", "--note", "mauvaise boutique")
    assert command("after-restore", str(kept), "--apply") == (
        0, f"the kept database {kept} holds 4 credit lines: 4 here already, 0 to copy, 0 skipped\n"
           "here already: line 3 of the kept database (originalphone grant 'MV-7'), typed as 'mv-7' (line 3 here)\n"
           "here already: line 4 of the kept database (originalphone grant 'MV-8'), typed as 'mv-8' (line 6 here)\n"
           "nothing to copy\n", "")
    assert lines(engine)[:2] == ledger[:2] and len(lines(engine)) == 4  # the two typed again and the move, no more
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT SUM(amount_ar) FROM credit_grants").scalar() == 15000  # each payment once


def test_a_reference_the_copy_would_write_two_ways_in_one_shop_is_refused_and_both_lines_named(command, engine, tmp_path):
    copy = backed_up(tmp_path)
    done(command, "grant", "originalphone", "10", "--offered", "--ref", "MV-9")
    kept = put_back(engine, tmp_path, copy)
    done(command, "correct", "originalphone", "+1", "--ref", "mv-9", "--note", "geste")  # under the grant's reference
    refused = (1, "", "refused: line 2 of the kept database (originalphone grant 'MV-9') and line 2 here 'mv-9' write one "
                      "reference two ways in originalphone: nothing copied, nothing guessed\n")
    assert command("after-restore", str(kept)) == refused
    assert command("after-restore", str(kept), "--apply") == refused
    assert [line.ref for line in lines(engine)] == ["mv-9"]


def test_a_line_the_database_refuses_rolls_the_whole_copy_back_and_is_named(command, engine, tmp_path):
    with write_tx(engine) as conn:
        product(conn)
        job(conn, "made", "succeeded")
    copy = backed_up(tmp_path)
    done(command, "grant", "originalphone", "1", "--offered", "--ref", "geste-1")
    done(command, "correct", "originalphone", "+1", "--ref", "defaut-1", "--job", "made", "--note", "produit déformé")
    done(command, "grant", "originalphone", "1", "--offered", "--ref", "geste-2")
    kept = put_back(engine, tmp_path, copy)
    with write_tx(engine) as conn:  # no operator command leads here any more: a rule of the database stands in for one
        conn.exec_driver_sql("CREATE TRIGGER refuses BEFORE INSERT ON credit_grants WHEN NEW.ref = 'defaut-1' "
                             "BEGIN SELECT RAISE(ABORT, 'not this one'); END")
    assert command("after-restore", str(kept), "--apply") == (
        1, "", "refused: line 3 of the kept database (originalphone correction 'defaut-1') is refused here (not this "
               "one): nothing copied\n")
    assert lines(engine) == []  # geste-1, written before it, rolled back with it


def test_a_kept_database_missing_unreadable_or_older_than_0014_gives_nothing_to_copy(command, engine, tmp_path, monkeypatch):
    kept, live = tmp_path / KEPT, tmp_path / "affiche.db"
    engine.dispose()  # its -wal folded in: the bytes below stay as they are unless something writes
    unchanged = live.read_bytes()
    assert command("after-restore", str(kept), "--apply") == (1, "", f"refused: no kept database at {kept}: {shops.LOSS}\n")
    kept.write_bytes(b"not a database")
    assert command("after-restore", str(kept), "--apply") == (
        1, "", f"refused: the kept database {kept} cannot be read (file is not a database): {shops.LOSS}\n")
    if os.name == "posix" and os.geteuid():  # root reads it anyway
        kept.chmod(0)
        assert command("after-restore", str(kept)) == (
            1, "", f"refused: the kept database {kept} cannot be read (unable to open database file): {shops.LOSS}\n")
    old = make_engine(tmp_path / "old")
    migrate_to(old, "0013", monkeypatch)
    old.dispose()
    older = tmp_path / "old" / "affiche.db"
    assert command("after-restore", str(older), "--apply") == (
        0, f"the kept database {older} is older than migration 0014: no credit was ever granted there; nothing to copy\n"
           "facebook: the kept database is older than migration 0018: no publication to bring\n", "")
    assert live.read_bytes() == unchanged


def test_a_payment_moved_in_another_order_after_the_restore_is_never_taken_out_of_every_shop(command, engine, tmp_path):
    """Kept: A→B→C. After the restore: A→C→B. B's reversal alone is missing here, and the database would accept it:
    the payment would then be in no shop (Codex, T-BALANCE-005 r1). This database's history stands."""
    second_shop(engine)
    done(command, "create", "troisieme", "--welcome", "0")
    done(command, "grant", "originalphone", "10", "--bought", "--amount-ar", "10000", "--method", "mvola", "--ref", "MV-1")
    copy = backed_up(tmp_path)
    done(command, "move-payment", "MV-1", "originalphone", "boutiquedeux", "--note", "erreur")
    done(command, "move-payment", "MV-1", "boutiquedeux", "troisieme", "--note", "erreur")
    done(command, "grant", "originalphone", "2", "--offered", "--ref", "geste")
    kept = put_back(engine, tmp_path, copy)
    done(command, "move-payment", "MV-1", "originalphone", "troisieme", "--note", "erreur")
    done(command, "move-payment", "MV-1", "troisieme", "boutiquedeux", "--note", "erreur")
    code, out, err = command("after-restore", str(kept), "--apply")
    assert (code, err) == (0, "") and "skipped line" in out and "(boutiquedeux correction 'MV-1')" in out, out
    assert out.endswith("copied 1 lines\n")  # the offered grant, not held back by the payment
    with engine.connect() as conn:
        assert conn.exec_driver_sql(
            "SELECT p.identifier, SUM(g.credits), SUM(g.amount_ar) FROM credit_grants g JOIN shop_profile p"
            " ON p.id = g.shop_id WHERE g.ref = 'MV-1' GROUP BY p.identifier HAVING SUM(g.amount_ar) > 0").all() == [
                ("boutiquedeux", 10, 10000)]


def paid(engine):
    with engine.connect() as conn:
        return [tuple(row) for row in conn.exec_driver_sql(
            "SELECT p.identifier, SUM(g.credits), SUM(g.amount_ar) FROM credit_grants g JOIN shop_profile p"
            " ON p.id = g.shop_id WHERE g.amount_ar IS NOT NULL GROUP BY p.identifier HAVING SUM(g.amount_ar) > 0"
            " ORDER BY 1")]


def test_a_payment_typed_again_with_other_figures_is_not_completed_from_the_kept_history(command, engine, tmp_path):
    """Same shops and kinds, other contents (Codex, T-BALANCE-005 r2): a move against an amount fix; an amount fix
    against a grant typed again with the right amount. Neither kept line is copied over them."""
    second_shop(engine)
    copy = backed_up(tmp_path)
    done(command, "grant", "originalphone", "10", "--bought", "--amount-ar", "10000", "--method", "mvola", "--ref", "MV-1")
    done(command, "move-payment", "MV-1", "originalphone", "boutiquedeux", "--note", "erreur")
    done(command, "grant", "originalphone", "10", "--bought", "--amount-ar", "10000", "--method", "mvola", "--ref", "MV-2")
    done(command, "correct", "originalphone", "0", "--ref", "MV-2", "--amount-ar", "+1000", "--note", "faute de frappe")
    kept = put_back(engine, tmp_path, copy)
    done(command, "grant", "originalphone", "10", "--bought", "--amount-ar", "10000", "--method", "mvola", "--ref", "mv-1")
    done(command, "correct", "originalphone", "0", "--ref", "mv-1", "--amount-ar", "+1000", "--note", "faute de frappe")
    done(command, "grant", "originalphone", "10", "--bought", "--amount-ar", "11000", "--method", "mvola", "--ref", "MV-2")
    before = lines(engine)
    code, out, err = command("after-restore", str(kept), "--apply")
    assert (code, err) == (0, "") and out.endswith("nothing to copy\n") and out.count("skipped line") == 2, out
    assert lines(engine) == before and paid(engine) == [("originalphone", 20, 22000)]


def test_a_repayment_under_a_payments_reference_is_copied_once_its_job_succeeds_after_the_payment_moved(
        command, engine, tmp_path):
    """Skipped while its job runs, it leaves a gap in the payment's history here: the next run must not read its own
    earlier copy as another history (Codex, T-BALANCE-005 r2)."""
    second_shop(engine)
    done(command, "create", "troisieme", "--welcome", "0")
    with write_tx(engine) as conn:
        product(conn)
        job(conn, "waiting", "running")
    done(command, "grant", "boutiquedeux", "10", "--bought", "--amount-ar", "10000", "--method", "mvola", "--ref", "MV-1")
    copy = backed_up(tmp_path)
    with write_tx(engine) as conn:
        conn.exec_driver_sql("UPDATE poster_jobs SET status='succeeded' WHERE id='waiting'")
    done(command, "correct", "originalphone", "+1", "--ref", "MV-1", "--job", "waiting", "--note", "produit déformé")
    done(command, "move-payment", "MV-1", "boutiquedeux", "troisieme", "--note", "erreur")
    kept = put_back(engine, tmp_path, copy)
    assert done(command, "after-restore", str(kept), "--apply").endswith("copied 2 lines\n")  # the move
    with write_tx(engine) as conn:
        conn.exec_driver_sql("UPDATE poster_jobs SET status='succeeded' WHERE id='waiting'")
    assert done(command, "after-restore", str(kept), "--apply").endswith("copied 1 lines\n")
    assert [line.job_id for line in lines(engine) if line.job_id] == ["waiting"]
    assert paid(engine) == [("troisieme", 10, 10000)]


def test_a_repayment_typed_under_a_payments_reference_never_passes_for_its_reversal(command, engine, tmp_path):
    """Kept: A's payment moved to B. Here: the grant typed again, then a job repaid under its reference, in the place
    of the reversal. B's grant alone would be copied: the payment in two shops (Codex, T-BALANCE-005 r3)."""
    second_shop(engine)
    with write_tx(engine) as conn:
        product(conn)
        job(conn, "made", "succeeded")
    copy = backed_up(tmp_path)
    done(command, "grant", "originalphone", "10", "--bought", "--amount-ar", "10000", "--method", "mvola", "--ref", "MV-1")
    done(command, "move-payment", "MV-1", "originalphone", "boutiquedeux", "--note", "erreur")
    kept = put_back(engine, tmp_path, copy)
    done(command, "grant", "originalphone", "10", "--bought", "--amount-ar", "10000", "--method", "mvola", "--ref", "mv-1")
    done(command, "correct", "originalphone", "+1", "--ref", "mv-1", "--job", "made", "--note", "produit déformé")
    out = done(command, "after-restore", str(kept), "--apply")
    assert out.endswith("nothing to copy\n") and "skipped line" in out and "(boutiquedeux grant 'MV-1')" in out, out
    assert paid(engine) == [("originalphone", 10, 10000)]


def test_a_repayment_is_here_only_by_its_job_whatever_took_its_reference(command, engine, tmp_path):
    """Deferred while its job ran, then its place (shop, correction, reference) taken by the payment's reversal, or by
    another job's repayment: neither passes for it (Codex, T-BALANCE-005 r4). It is named for a repayment by hand."""
    second_shop(engine)
    with write_tx(engine) as conn:
        product(conn)
        job(conn, "made", "running")
        job(conn, "other", "succeeded")
        job(conn, "third", "succeeded")
    done(command, "grant", "originalphone", "10", "--bought", "--amount-ar", "10000", "--method", "mvola", "--ref", "MV-1")
    done(command, "grant", "originalphone", "1", "--offered", "--ref", "geste")
    copy = backed_up(tmp_path)
    with write_tx(engine) as conn:
        conn.exec_driver_sql("UPDATE poster_jobs SET status='succeeded' WHERE id='made'")
    done(command, "correct", "originalphone", "+1", "--ref", "MV-1", "--job", "made", "--note", "produit déformé")
    done(command, "correct", "originalphone", "+1", "--ref", "geste", "--job", "other", "--note", "produit déformé")
    kept = put_back(engine, tmp_path, copy)
    with write_tx(engine) as conn:
        conn.exec_driver_sql("UPDATE poster_jobs SET status='succeeded' WHERE id='made'")
    done(command, "move-payment", "MV-1", "originalphone", "boutiquedeux", "--note", "erreur")
    done(command, "correct", "originalphone", "+1", "--ref", "geste", "--job", "third", "--note", "refait")
    before = lines(engine)
    out = done(command, "after-restore", str(kept), "--apply")
    assert "0 to copy, 2 skipped" in out and "repay job made by hand" in out and "repay job other by hand" in out, out
    assert lines(engine) == before
    done(command, "correct", "originalphone", "+1", "--ref", "defaut-made", "--job", "made", "--note", "à la main")
    assert "1 skipped" in done(command, "after-restore", str(kept), "--apply")  # made is here by its job, under any name


# --- The restore's Facebook steps (facebook-publishing.md, Failure modes, « A restore of the database ») ---------------

PUBLICATIONS = ("SELECT p.identifier, f.id, f.creation_id, f.confirmation_id, f.page_id, f.page_name, f.caption, f.key,"
                " f.payload_sha, f.status, f.sent_at, f.settled_at, f.post_id, f.link, f.error_code, f.said_by_owner"
                " FROM facebook_publications f JOIN shop_profile p ON p.id = f.shop_id ORDER BY f.rowid")
LATER = "2026-11-18T09:00:00.000000+00:00"


def facebook(out):
    return [line for line in out.splitlines() if line.startswith("facebook: ")]


def poster(conn, id, shop=1):
    conn.exec_driver_sql("INSERT INTO creations VALUES (?,?,NULL,1,'active',?,?)", (id, shop, T, T))


def settle(conn, id, status, owner=0):
    """As the route settles a row (facebook_publish._settled), the start (recover) or the owner's word (owner)."""
    post = "100_123" if status == "published" and not owner else None
    link = "https://www.facebook.com/100" if owner else post and f"https://www.facebook.com/{post}"
    conn.exec_driver_sql("UPDATE facebook_publications SET status=?, post_id=?, link=?, error_code=?, said_by_owner=?,"
                         " settled_at=? WHERE id=?", (status, post, link, "506" if status == "failed" else None, owner,
                                                       None if status == "sending" else LATER, id))


def publication(conn, id, status, poster="p1", shop=1):
    """A row as the route admits it, then settled."""
    conn.exec_driver_sql("INSERT INTO facebook_publications (id, shop_id, creation_id, confirmation_id, page_id, page_name,"
                         " caption, key, payload_sha, status, sent_at) VALUES (?, ?, ?, 'k1', '100', 'Ma Page', 'Promo !',"
                         " ?, 'sha', 'sending', ?)", (id, shop, poster, f"key-{id}", T))
    settle(conn, id, status)


def connected(conn, shop=1, attempt=False):
    conn.exec_driver_sql("INSERT INTO facebook_pages VALUES (?, '100', 'Ma Page', 'page-token-of-the-backup-1', "
                         "'connected', ?)", (shop, T))
    if attempt:
        conn.exec_driver_sql("INSERT INTO facebook_connects VALUES (?, 'state', 'session', 'choice', '[]', ?)", (shop, T))


def facebook_state(engine):
    with engine.connect() as conn:
        return (conn.exec_driver_sql("SELECT count(*) FROM facebook_pages").scalar(),
                conn.exec_driver_sql("SELECT count(*) FROM facebook_connects").scalar(),
                conn.exec_driver_sql("SELECT value FROM meta WHERE key='facebook_mode'").scalar())


def test_after_a_restore_the_connections_go_and_the_publications_take_what_the_kept_database_knows(
        command, engine, tmp_path):
    """A row the backup lacks is copied whole; a row both hold takes the kept settlement only while it is sending or
    unknown here; one settled in both, or here only, stays as it is; a row of a poster or a shop made after the backup
    is said and skipped. The report writes nothing; a second run changes nothing."""
    second_shop(engine)
    with write_tx(engine) as conn:
        poster(conn, "p1")
        poster(conn, "p2")
        publication(conn, "sent", "sending")  # its answer came after the backup
        publication(conn, "lost", "unknown")  # the owner said « Elle n’y est pas » after the backup
        publication(conn, "said", "unknown")  # … and « Elle est sur ma Page »
        publication(conn, "open", "unknown", poster="p2")  # unknown in both
        publication(conn, "both", "published")  # settled in both
        publication(conn, "mine", "failed")  # settled here only
        conn.exec_driver_sql("INSERT INTO meta VALUES ('facebook_mode', 'meta')")
        connected(conn)
        connected(conn, shop=2, attempt=True)
    copy = backed_up(tmp_path)
    done(command, "create", "Chez Rado", "--welcome", "0")  # shop 3
    with write_tx(engine) as conn:
        settle(conn, "sent", "published")
        settle(conn, "lost", "failed")
        settle(conn, "said", "published", owner=1)
        settle(conn, "both", "failed")  # no route does these two: the test's way to tell the settlements apart
        settle(conn, "mine", "unknown")
        poster(conn, "p3")
        poster(conn, "p4", shop=3)
        publication(conn, "new", "published")
        publication(conn, "gone", "published", poster="p3")
        publication(conn, "rado", "unknown", poster="p4", shop=3)
        conn.exec_driver_sql("DELETE FROM facebook_pages WHERE shop_id=1")  # « Déconnecter » after the backup
    kept = put_back(engine, tmp_path, copy)
    live, unchanged = tmp_path / "affiche.db", (tmp_path / "affiche.db").read_bytes()
    restored = {row[1]: row for row in read(live, PUBLICATIONS)}
    report = [
        "facebook: the kept database holds 9 publications: 3 here already, 1 to copy, 3 to settle, 2 skipped",
        "facebook: {settle}: publication sent (originalphone, poster p1), sending here, published in the kept database",
        "facebook: {settle}: publication lost (originalphone, poster p1), unknown here, failed in the kept database",
        "facebook: {settle}: publication said (originalphone, poster p1), unknown here, published in the kept database",
        f"facebook: {{copy}}: publication new (originalphone, poster p1), published on the Page 'Ma Page', sent {T}",
        "facebook: skipped publication gone (originalphone, poster p3): its poster is not here (made after the backup)",
        "facebook: skipped publication rado (chezrado, poster p4): its shop is not here (made after the backup)",
        "facebook: {delete}: the Page of 2 shops (boutiquedeux, originalphone) and 1 attempts to connect; each shop "
        "connects its Page again"]
    assert facebook(done(command, "after-restore", str(kept))) == [
        line.format(settle="to settle", copy="to copy", delete="to delete") for line in report] + [
        "facebook: report only, nothing written: run again with --apply"]
    assert live.read_bytes() == unchanged
    assert facebook(done(command, "after-restore", str(kept), "--apply")) == [
        line.format(settle="settled", copy="copied", delete="deleted") for line in report]
    # Every column of the kept rows, in the kept order, but the two settled here, and the two whose poster is gone.
    assert read(live, PUBLICATIONS) == [restored[row[1]] if row[1] in ("both", "mine") else row
                                        for row in read(kept, PUBLICATIONS) if row[1] not in ("gone", "rado")]
    assert facebook_state(engine) == (0, 0, "meta")
    after = read(live, PUBLICATIONS)
    assert facebook(done(command, "after-restore", str(kept), "--apply")) == [
        "facebook: the kept database holds 9 publications: 7 here already, 0 to copy, 0 to settle, 2 skipped",
        report[5], report[6]]
    assert read(live, PUBLICATIONS) == after


def test_the_facebook_mode_is_carried_when_this_database_has_none(command, engine, tmp_path):
    copy = backed_up(tmp_path)  # before any Facebook call
    with write_tx(engine) as conn:
        conn.exec_driver_sql("INSERT INTO meta VALUES ('facebook_mode', 'meta')")
    kept = put_back(engine, tmp_path, copy)
    assert facebook(done(command, "after-restore", str(kept))) == [
        "facebook: to carry: facebook_mode 'meta' from the kept database",
        "facebook: report only, nothing written: run again with --apply"]
    assert facebook_state(engine) == (0, 0, None)
    assert facebook(done(command, "after-restore", str(kept), "--apply")) == [
        "facebook: carried: facebook_mode 'meta' from the kept database"]
    assert facebook_state(engine) == (0, 0, "meta")
    assert facebook(done(command, "after-restore", str(kept), "--apply")) == []


def test_two_facebook_modes_block_the_whole_copy(command, engine, tmp_path):
    """The stand-in's publications never sit beside real ones: nothing is written, the credit lines neither."""
    with write_tx(engine) as conn:
        conn.exec_driver_sql("INSERT INTO meta VALUES ('facebook_mode', 'stub')")
        connected(conn)
    copy = backed_up(tmp_path)
    done(command, "grant", "originalphone", "4", "--offered", "--ref", "geste")
    with write_tx(engine) as conn:
        conn.exec_driver_sql("UPDATE meta SET value='meta' WHERE key='facebook_mode'")
    kept = put_back(engine, tmp_path, copy)
    differ = ("facebook_mode is 'stub' here and 'meta' in the kept database: the stand-in's publications and real ones "
              "never mix (deploy/README.md, Restore)")
    out = done(command, "after-restore", str(kept))
    assert "\nreport only, nothing written: the Facebook modes differ (below)\n" in out, out
    assert facebook(out) == ["facebook: to delete: the Page of 1 shops (originalphone) and 0 attempts to connect; each "
                             "shop connects its Page again", f"facebook: {differ}", "facebook: report only, nothing written"]
    code, out, err = command("after-restore", str(kept), "--apply")
    assert (code, err) == (1, f"refused: nothing copied: {differ}\n") and "to copy: line 2 of the kept database" in out
    assert lines(engine) == [] and facebook_state(engine) == (1, 0, "stub")


def test_a_kept_database_older_than_0018_brings_nothing_and_the_connections_still_go(
        command, engine, tmp_path, monkeypatch):
    old = make_engine(tmp_path / "old")
    migrate_to(old, "0017", monkeypatch)
    old.dispose()
    with write_tx(engine) as conn:
        connected(conn, attempt=True)
    gone = ["facebook: the kept database is older than migration 0018: no publication to bring",
            "facebook: {}: the Page of 1 shops (originalphone) and 1 attempts to connect; each shop connects its Page again"]
    older = str(tmp_path / "old" / "affiche.db")
    assert facebook(done(command, "after-restore", older)) == [
        gone[0], gone[1].format("to delete"), "facebook: report only, nothing written: run again with --apply"]
    assert facebook_state(engine) == (1, 1, None)
    assert facebook(done(command, "after-restore", older, "--apply")) == [gone[0], gone[1].format("deleted")]
    assert facebook_state(engine) == (0, 0, None)


def test_without_a_kept_database_the_restored_one_as_its_own_only_deletes_the_connections(command, engine, tmp_path):
    """deploy/README.md, Restore: the kept database is lost; the connections of the copy must still go."""
    with write_tx(engine) as conn:
        poster(conn, "p1")
        publication(conn, "open", "unknown")
        conn.exec_driver_sql("INSERT INTO meta VALUES ('facebook_mode', 'meta')")
        connected(conn, attempt=True)
    live = tmp_path / "affiche.db"
    before = read(live, PUBLICATIONS)
    assert facebook(done(command, "after-restore", str(live), "--apply")) == [
        "facebook: the kept database holds 1 publications: 1 here already, 0 to copy, 0 to settle, 0 skipped",
        "facebook: deleted: the Page of 1 shops (originalphone) and 1 attempts to connect; each shop connects its Page "
        "again"]
    assert read(live, PUBLICATIONS) == before and facebook_state(engine) == (0, 0, "meta")
