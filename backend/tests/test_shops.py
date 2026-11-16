import os
import sqlite3

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, OperationalError

from affiche import runtime, shops
from affiche.api import create_app
from affiche.config import load_settings
from affiche.db import make_engine, write_tx
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


@pytest.mark.parametrize("argv", [[], ["suspend"], ["end-sessions"], ["end-sessions", "x", "--all"], ["delete", "x"],
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
    assert capsys.readouterr().out == "1 sessions ended (every shop)\n"
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
        assert shops.headroom(conn, settings) == {"cap": 20_000_000, "spent": 0, "outstanding": 100, "images": 0,
                                                  "unit": 400_000, "cost": 40_000_000}
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
        assert shops.headroom(conn, settings) == {"cap": 20_000_000, "spent": 4_805_000, "outstanding": 100,
                                                  "images": 50, "unit": 40_000, "cost": 4_000_000}


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
        1, "", "refused: the payment 'MV-2' was already moved or corrected in the source shop\n")
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
