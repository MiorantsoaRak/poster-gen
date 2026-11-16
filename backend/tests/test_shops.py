import os
import sqlite3

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from affiche import runtime, shops
from affiche.api import create_app
from affiche.config import load_settings
from affiche.db import make_engine, write_tx
from affiche.posters import auth
from affiche.posters.auth import PASSWORDS, identifier_key
from test_api import (HEADERS, IDENTIFIER, ORIGIN, PASSWORD, Counting, at_0012, client, credentials, failures, login,  # noqa: F401
                      password_hash, second_shop, settings, stored_password)
from test_config import env  # noqa: F401
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


def printed_password(out):
    line, = [line for line in out.splitlines() if line.startswith("password (shown once")]
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
    assert command("end-sessions", "--all")[:2] == (0, "1 sessions ended (every shop)\n")
    assert auth.session_shop(engine, b) is None
    assert command("enable", "nobody") == (1, "", "refused: no shop has the identifier nobody\n")


@pytest.mark.parametrize("argv", [[], ["suspend"], ["end-sessions"], ["end-sessions", "x", "--all"], ["delete", "x"]])
def test_a_wrong_command_line_is_a_usage_error(command, argv):
    with pytest.raises(SystemExit) as exited:
        command(*argv)
    assert exited.value.code == 2


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
    assert capsys.readouterr().out == "1 sessions ended (every shop)\n"
    assert shops.main(["set-password", "originalphone"], env_file=None) == 0
    password = printed_password(capsys.readouterr().out)
    settings.shop_password_hash = None  # removed from app.env after Release 1
    with TestClient(create_app(settings), base_url=ORIGIN, headers=HEADERS) as client:
        assert client.get("/api/session", headers=cookie).json()["authenticated"] is False
        assert client.post("/api/session", json=credentials(password)).status_code == 200
