"""The operator's sign-in, sessions and request boundary (D-ADMIN-001, R-ADMIN-001) as tested properties: the rows of the
design's three security matrices for the routes that exist, the limits, the session checked again inside a write, the
journal line under the real launcher, and that no HTTP route writes the operator's password."""
import logging
import os
import re
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from affiche import api as affiche_api, shops
from affiche.api import create_app
from affiche.db import write_tx
from affiche.posters import auth, store
from affiche.posters.auth import PASSWORDS
from test_api import (HEADERS, IDENTIFIER, ORIGIN, PASSWORD, Counting, at_most_one_past_the_limit, client,  # noqa: F401
                      credentials, failures, login, operator_client, password_hash, settings, slow_wrong)
from test_config import env  # noqa: F401

OPERATOR = os.urandom(13).hex()  # a throwaway operator password of 26 characters per test process
PUBLIC = {("GET", "/api/admin/session"), ("POST", "/api/admin/session"), ("DELETE", "/api/admin/session")}
# Every protected admin route, with the operator's own answer. A route under /api/admin/ in neither set fails the tests.
ANSWERS = {("DELETE", "/api/admin/sessions"): {"ended": 1}}
NOBODY = {"authenticated": False, "configured": True}
PAST = "2000-01-01T00:00:00.000000+00:00"


@pytest.fixture(autouse=True)
def never_logged(caplog):
    """Every record the application's loggers emit in these tests, at every level: none holds a password, a stored hash
    or a token (D-ADMIN-002). A test adds the secrets it meets."""
    caplog.set_level(logging.DEBUG, logger="affiche")
    secrets = [OPERATOR, PASSWORD]
    yield secrets
    emitted = "\n".join(record.getMessage() for record in caplog.records)
    assert all(secret not in emitted for secret in secrets)


@pytest.fixture
def set_operator(client, never_logged):
    """Sets the operator's password through the function `operator-password` calls. After the test meta holds the hash
    it wrote last, or none: no HTTP route writes the key (D-ADMIN-001)."""
    engine, written = client.app.state.engine, [None]

    def set_password(password=OPERATOR):
        password_hash = PASSWORDS.hash(password)
        with write_tx(engine) as conn:
            shops.set_operator_password(conn, password_hash)
        written.append(password_hash)
        never_logged.extend((password, password_hash))

    yield set_password
    assert stored_hash(engine) == written[-1]


def stored_hash(engine):
    with engine.connect() as conn:
        return conn.execute(text("SELECT value FROM meta WHERE key=:key"), {"key": auth.OPERATOR_KEY}).scalar()


def sign_in(client, password=OPERATOR, **headers):
    return client.post("/api/admin/session", json={"password": password}, headers=headers)


def signed_in(client, password=OPERATOR) -> str:
    answer = sign_in(client, password)
    assert answer.status_code == 200, answer.text
    return answer.json()["actor"]


def device(client, **headers):
    """Another browser on the same application, with its own cookies."""
    return TestClient(client.app, base_url=ORIGIN, headers=HEADERS | headers)


def refusal(answer):
    return answer.status_code, answer.json()["error"]["code"]


def sessions(engine):
    with engine.connect() as conn:
        return conn.execute(text("SELECT * FROM operator_sessions ORDER BY created_at")).all()


def flags(set_cookie):
    """A Set-Cookie's name and the attributes a deletion must repeat, or the browser keeps the cookie."""
    name, *attributes = [part.strip() for part in set_cookie.split(";")]
    return name.split("=")[0], {a for a in attributes if a.split("=")[0].lower() in ("path", "secure", "httponly", "samesite")}


OPERATOR_FLAGS = (auth.OPERATOR_COOKIE, {"Path=/api/admin", "Secure", "HttpOnly", "SameSite=strict"})


def protected_admin_routes(app):
    """Every protected route under /api/admin/, read from the schema."""
    admin = {(method.upper(), path) for path, methods in app.openapi()["paths"].items() for method in methods
             if path.startswith("/api/admin/")}
    assert PUBLIC <= admin and admin - PUBLIC == set(ANSWERS), f"an admin route in no list: {sorted(admin - PUBLIC - set(ANSWERS))}"
    return sorted(admin - PUBLIC)


def call(client, method, path, **headers):
    return client.request(method, re.sub(r"\{\w+\}", "1", path), headers=headers)


def test_without_a_password_sign_in_names_the_command_and_nothing_is_verified_or_counted(client, set_operator, monkeypatch):
    monkeypatch.setattr(auth, "PASSWORDS", counting := Counting(PASSWORDS))
    assert client.get("/api/admin/session").text == '{"authenticated":false,"configured":false}'  # verify.sh's bytes
    for _ in range(auth.PAIR_LIMIT + 1):
        answer = sign_in(client)
        assert refusal(answer) == (409, "operator_not_set")
    assert "python -m affiche.shops operator-password" in answer.json()["error"]["message_fr"]
    assert counting.calls == 0 and failures(client.app.state.engine) == [] and "set-cookie" not in answer.headers
    for method, path in protected_admin_routes(client.app):  # no session can exist
        assert refusal(call(client, method, path)) == (401, "unauthenticated")
    set_operator()
    assert client.get("/api/admin/session").text == '{"authenticated":false,"configured":true}'  # verify.sh's bytes


def test_the_shops_failures_from_this_address_never_hide_that_no_password_is_set(client, set_operator):
    """The address limit is shared with the shops: checked first, it answered 429 where the operator must read the
    command to run (Codex, T-ADMIN-002 r1)."""
    with write_tx(client.app.state.engine) as conn:
        for _ in range(auth.ADDRESS_LIMIT):
            conn.execute(text("INSERT INTO login_failures (ip,identifier,attempted_at) VALUES (:ip,'boutique',:now)"),
                         {"ip": auth.limit_key("testclient"),
                          "now": datetime.now().astimezone().isoformat(timespec="microseconds")})
    assert refusal(sign_in(client)) == (409, "operator_not_set")
    set_operator()
    assert refusal(sign_in(client)) == (429, "rate_limited")  # the same rows do count once a password exists


def test_sign_in_gives_a_12_hour_session_stored_as_a_hash_under_a_cookie_for_the_admin_paths_only(client, set_operator,
                                                                                                never_logged):
    set_operator()
    agent = "Phone/1.0 " + "x" * 300
    answer = sign_in(client, **{"User-Agent": agent})
    assert answer.status_code == 200, answer.text
    token = client.cookies.get(auth.OPERATOR_COOKIE)
    digest = auth.token_hash(token)
    never_logged.extend((token, digest))
    body = answer.json()
    assert body == {"authenticated": True, "actor": f"dashboard:{digest[:8]}", "expires_at": body["expires_at"]}
    assert flags(answer.headers["set-cookie"]) == OPERATOR_FLAGS and "Max-Age=43200" in answer.headers["set-cookie"]
    (row,) = sessions(client.app.state.engine)
    assert (row.token_hash, row.expires_at, row.address, row.agent) == (digest, body["expires_at"], "testclient", agent[:200])
    assert datetime.fromisoformat(row.expires_at) - datetime.fromisoformat(row.created_at) == timedelta(hours=12)
    assert client.get("/api/admin/session").json() == body
    # Its Path: a browser sends it to the admin paths and nowhere else.
    assert auth.OPERATOR_COOKIE in client.get("/api/admin/session").request.headers["cookie"]
    assert "cookie" not in client.get("/api/session").request.headers


def test_on_a_loopback_http_origin_the_cookie_is_set_and_deleted_without_secure(settings):
    settings.app_origin = "http://localhost:5173"
    with TestClient(create_app(settings), base_url=settings.app_origin, headers={**HEADERS, "Origin": settings.app_origin}) as local:
        engine, password_hash = local.app.state.engine, PASSWORDS.hash(OPERATOR)
        with write_tx(engine) as conn:
            shops.set_operator_password(conn, password_hash)
        made = sign_in(local)
        gone = local.delete("/api/admin/session")
        assert made.status_code == gone.status_code == 200
        assert flags(made.headers["set-cookie"]) == flags(gone.headers["set-cookie"]) == (
            auth.OPERATOR_COOKIE, {"Path=/api/admin", "HttpOnly", "SameSite=strict"})
        assert stored_hash(engine) == password_hash


def test_a_new_sign_in_replaces_this_browsers_session_and_removes_expired_ones(client, set_operator):
    engine = client.app.state.engine
    set_operator()
    signed_in(client)
    first = client.cookies.get(auth.OPERATOR_COOKIE)
    signed_in(laptop := device(client))
    signed_in(old := device(client))
    with write_tx(engine) as conn:
        conn.execute(text("UPDATE operator_sessions SET expires_at=:past WHERE token_hash=:hash"),
                     {"past": PAST, "hash": auth.token_hash(old.cookies.get(auth.OPERATOR_COOKIE))})
    signed_in(client)
    second = client.cookies.get(auth.OPERATOR_COOKIE)
    assert second != first
    assert {row.token_hash for row in sessions(engine)} == {auth.token_hash(second),
                                                           auth.token_hash(laptop.cookies.get(auth.OPERATOR_COOKIE))}
    assert laptop.get("/api/admin/session").json()["authenticated"] is True
    assert device(client).get("/api/admin/session", headers={"Cookie": f"{auth.OPERATOR_COOKIE}={first}"}).json() == NOBODY


def test_sign_in_sign_out_and_writes_need_the_origin_and_writes_the_current_bundle(client, set_operator):
    engine = client.app.state.engine
    set_operator()
    no_origin = TestClient(client.app, base_url=ORIGIN, headers={"X-Affiche-Bundle": str(affiche_api.BUNDLE)})
    assert refusal(sign_in(no_origin)) == (403, "forbidden_origin")
    for origin in ("", "https://evil.example", "null", ORIGIN + "/", "http://shop.example"):
        assert refusal(sign_in(client, Origin=origin)) == (403, "forbidden_origin")
    for bundle in ("", "1", str(affiche_api.BUNDLE - 1), "abc"):
        assert refusal(sign_in(client, **{"X-Affiche-Bundle": bundle})) == (409, "bundle_outdated")
    assert sessions(engine) == [] and failures(engine) == []
    signed_in(client)
    token = client.cookies.get(auth.OPERATOR_COOKIE)
    writes = [(method, path) for method, path in protected_admin_routes(client.app) if method != "GET"]
    for origin in (None, "https://evil.example"):
        holder = TestClient(client.app, base_url=ORIGIN, headers={"X-Affiche-Bundle": str(affiche_api.BUNDLE),
                                                                  "Cookie": f"{auth.OPERATOR_COOKIE}={token}"}
                            | ({"Origin": origin} if origin else {}))
        assert refusal(holder.delete("/api/admin/session")) == (403, "forbidden_origin")
        for method, path in writes:
            assert refusal(call(holder, method, path)) == (403, "forbidden_origin"), (method, path)
    for method, path in writes:
        assert refusal(call(client, method, path, **{"X-Affiche-Bundle": "1"})) == (409, "bundle_outdated")
    assert len(sessions(engine)) == 1
    # Signing out needs no current bundle, as the shops' sign-out: an older tab can always end its session.
    assert client.delete("/api/admin/session", headers={"X-Affiche-Bundle": "1"}).json() == {"authenticated": False}
    assert sessions(engine) == []


def test_sign_out_ends_this_session_alone_and_deletes_the_cookie_as_it_was_set(client, set_operator, caplog):
    set_operator()
    made = sign_in(client)
    actor = made.json()["actor"]
    signed_in(phone := device(client))
    gone = client.delete("/api/admin/session")
    assert gone.json() == {"authenticated": False}
    assert flags(gone.headers["set-cookie"]) == flags(made.headers["set-cookie"]) == OPERATOR_FLAGS
    assert "Max-Age=0" in gone.headers["set-cookie"] and client.cookies.get(auth.OPERATOR_COOKIE) is None
    assert client.get("/api/admin/session").json() == NOBODY
    assert phone.get("/api/admin/session").json()["authenticated"] is True
    assert client.delete("/api/admin/session").json() == {"authenticated": False}  # nothing left: the same answer
    lines = [record.getMessage() for record in caplog.records if record.name == "affiche.admin"]
    assert lines.count(f"operator action=sign_out shop=- actor={actor}") == 1
    assert len([line for line in lines if "action=sign_out" in line]) == 1  # none for the second, which ended nothing


def test_the_operators_cookie_changes_nothing_on_the_shops_session_operations(client, set_operator):
    """Public shop session operations with only the operator's cookie, which no browser sends there (its Path) and the
    server never reads there: each answers as with no cookie, and the operator stays signed in."""
    set_operator()
    signed_in(client)
    only = device(client, Cookie=f"{auth.OPERATOR_COOKIE}={client.cookies.get(auth.OPERATOR_COOKIE)}")
    assert only.get("/api/session").json() == device(client).get("/api/session").json() == {"authenticated": False}
    ended = only.delete("/api/session")
    assert ended.json() == {"authenticated": False} and auth.OPERATOR_COOKIE not in ended.headers["set-cookie"]
    signed = only.post("/api/session", json=credentials())
    assert signed.json() == {"authenticated": True, "shop_id": 1} and auth.OPERATOR_COOKIE not in signed.headers["set-cookie"]
    assert client.get("/api/admin/session").json()["authenticated"] is True


def test_every_protected_admin_route_refuses_whoever_is_not_a_live_operator(client, set_operator):
    set_operator()
    routes = protected_admin_routes(client.app)
    login(client)
    shop_token = client.cookies.get(auth.COOKIE)
    signed_in(operator := device(client))
    operator_token = operator.cookies.get(auth.OPERATOR_COOKIE)
    anonymous = device(client)

    def refused(caller, **headers):
        for method, path in routes:
            assert refusal(call(caller, method, path, **headers)) == (401, "unauthenticated"), (method, path, headers)

    refused(anonymous)
    refused(client)  # a shop's session
    refused(client, **{"X-Affiche-Shop": "1"})  # and its stale-tab header: never read here
    refused(anonymous, Cookie=f"{auth.COOKIE}={operator_token}")  # the operator's token as a shop's cookie
    refused(anonymous, Cookie=f"{auth.OPERATOR_COOKIE}={shop_token}")  # a shop's token as the operator's cookie
    refused(operator_client(client), **HEADERS)  # a loopback client and Host: loopback grants nothing here
    for cookie in (f"{auth.OPERATOR_COOKIE}={shop_token}", f"{auth.COOKIE}={operator_token}", f"{auth.COOKIE}={shop_token}"):
        assert anonymous.get("/api/admin/session", headers={"Cookie": cookie}).json() == NOBODY, cookie
    assert operator.get("/api/admin/session").json()["authenticated"] is True  # all of this ended nothing


def test_admin_paths_never_read_a_shop_session_and_shop_paths_never_read_the_operators(client, set_operator, monkeypatch):
    set_operator()
    login(client)
    signed_in(client)
    shop, operator = client.cookies.get(auth.COOKIE), client.cookies.get(auth.OPERATOR_COOKIE)
    both = device(client, Cookie=f"{auth.COOKIE}={shop}; {auth.OPERATOR_COOKIE}={operator}")  # no browser sends both
    reads = []
    for name in ("session_shop", "operator_session"):
        real = getattr(auth, name)
        monkeypatch.setattr(auth, name, lambda engine, token, real=real, name=name: reads.append((name, token)) or real(engine, token))
    assert both.get("/api/admin/session").json()["authenticated"] is True
    assert refusal(both.get("/api/admin/nothing")) == (404, "not_found")  # past the boundary: the operator is live
    assert reads == [("operator_session", operator)] * 2
    reads.clear()
    assert both.get("/api/session").json() == {"authenticated": True, "shop_id": 1}
    assert both.get("/api/shop-profile").status_code == 200
    assert reads == [("session_shop", shop)] * 2


def test_the_operators_session_is_refused_on_every_protected_shop_route(client, set_operator):
    set_operator()
    signed_in(client)
    holder = device(client, Cookie=f"{auth.OPERATOR_COOKIE}={client.cookies.get(auth.OPERATOR_COOKIE)}")
    routes = {(method.upper(), path) for path, methods in client.app.openapi()["paths"].items() for method in methods
              if not path.startswith("/api/admin/")} - {("GET", "/api/session"), ("POST", "/api/session"),
                                                        ("DELETE", "/api/session"), ("GET", "/api/status")}
    assert len(routes) > 40
    for method, path in sorted(routes):
        concrete = path.replace("{id}", str(uuid4())).replace("{sha}", "0" * 64).replace("{revision}", "1")
        answer = holder.request(method, concrete, headers={"Idempotency-Key": str(uuid4())})
        assert refusal(answer) == (401, "unauthenticated"), (method, path)
    assert refusal(holder.get("/api/status")) == (404, "not_found")  # still the machine's alone (D-MULTI-SHOP-004)
    assert refusal(holder.get("/api/openapi.json")) == (401, "unauthenticated")


def test_a_browser_with_both_sessions_answers_each_side_as_its_own_and_signs_out_one_alone(client, set_operator):
    set_operator()
    login(client)
    actor = signed_in(client)
    assert client.get("/api/session").json() == {"authenticated": True, "shop_id": 1}
    assert client.get("/api/shop-profile").status_code == 200
    assert client.get("/api/admin/session").json()["actor"] == actor
    assert client.delete("/api/session").json() == {"authenticated": False}
    assert client.get("/api/shop-profile").status_code == 401
    assert client.get("/api/admin/session").json()["actor"] == actor
    login(client)
    assert client.delete("/api/admin/session").json() == {"authenticated": False}
    assert client.get("/api/admin/session").json() == NOBODY
    assert client.get("/api/session").json() == {"authenticated": True, "shop_id": 1}
    assert client.get("/api/shop-profile").status_code == 200


def test_wrong_passwords_are_limited_per_address_under_their_own_name_and_count_for_the_address(client, set_operator):
    engine = client.app.state.engine
    set_operator()
    for _ in range(auth.PAIR_LIMIT):
        assert refusal(sign_in(client, "wrong")) == (401, "wrong_credentials")
    limited = sign_in(client)  # even the right password, without verifying it
    assert refusal(limited) == (429, "rate_limited") and limited.headers["retry-after"] == "900"
    assert failures(engine) == [auth.OPERATOR_NAME] * auth.PAIR_LIMIT
    assert auth.operator_login(engine, OPERATOR, "192.0.2.2", None)[1].actor.startswith("dashboard:")  # another address
    assert auth.login(engine, IDENTIFIER, PASSWORD, "testclient")[1] == 1  # a shop from the same address: its own count
    # The address-wide limit is the shops' own: the operator's failures count in it.
    for i in range(auth.ADDRESS_LIMIT - auth.PAIR_LIMIT):
        with pytest.raises(store.Refused, match="wrong_credentials"):
            auth.login(engine, f"inconnue{i}", "wrong", "testclient")
    with pytest.raises(store.Refused, match="rate_limited"):
        auth.login(engine, IDENTIFIER, PASSWORD, "testclient")


def test_a_burst_of_wrong_operator_passwords_records_at_most_one_failure_past_the_limit(client, set_operator, monkeypatch):
    engine = client.app.state.engine
    set_operator()
    calls, outcomes, lock = slow_wrong(monkeypatch, .15), [], threading.Lock()

    def attempt():
        try:
            auth.operator_login(engine, "wrong", "198.51.100.7", None)
        except store.Refused as refused:
            with lock:
                outcomes.append(refused.code)

    threads = [threading.Thread(target=attempt) for _ in range(10)]
    [thread.start() for thread in threads]
    [thread.join(timeout=30) for thread in threads]
    at_most_one_past_the_limit(engine, calls, sorted(outcomes))


def test_a_password_set_during_the_verification_gives_no_session(client, set_operator, monkeypatch):
    """`operator-password` committed while a sign-in verifies the old password: the hash is read again in the transaction
    that would write the session, so no session outlives the password it was opened with."""
    engine = client.app.state.engine
    set_operator()

    class Racing:
        def verify(self, password, stored):
            verified = PASSWORDS.verify(password, stored)
            set_operator(os.urandom(13).hex())
            return verified

    monkeypatch.setattr(auth, "PASSWORDS", Racing())
    assert refusal(sign_in(client)) == (401, "wrong_credentials")
    assert failures(engine) == [auth.OPERATOR_NAME] and sessions(engine) == []


def test_end_all_ends_every_operator_session_this_one_included_and_no_shops(client, set_operator, caplog):
    set_operator()
    login(client)
    signed_in(laptop := device(client))
    actor = signed_in(client)
    answer = client.delete("/api/admin/sessions")
    assert answer.json() == {"ended": 2}
    assert flags(answer.headers["set-cookie"]) == OPERATOR_FLAGS and "Max-Age=0" in answer.headers["set-cookie"]
    assert client.cookies.get(auth.OPERATOR_COOKIE) is None and sessions(client.app.state.engine) == []
    assert laptop.get("/api/admin/session").json() == client.get("/api/admin/session").json() == NOBODY
    assert client.get("/api/session").json() == {"authenticated": True, "shop_id": 1}  # no shop's session ends
    lines = [record.getMessage() for record in caplog.records if record.name == "affiche.admin"]
    assert f"operator action=operator_sessions_ended shop=- actor={actor} count=2" in lines


@pytest.mark.parametrize("how", ["expired", "operator-password", "end-sessions --operator", "end-sessions --all"])
def test_an_ended_or_expired_session_reads_as_nobody_and_is_refused(client, set_operator, how):
    engine = client.app.state.engine
    set_operator()
    signed_in(client)
    if how == "expired":
        with write_tx(engine) as conn:
            conn.execute(text("UPDATE operator_sessions SET expires_at=:past"), {"past": PAST})
    elif how == "operator-password":
        set_operator(os.urandom(13).hex())  # the command's own function (test_shops runs the command)
    else:
        assert shops.main(how.split(), env_file=None) == 0
    assert client.get("/api/admin/session").json() == NOBODY
    for method, path in protected_admin_routes(client.app):
        assert refusal(call(client, method, path)) == (401, "unauthenticated")
    if how == "expired":  # kept until the next sign-in removes it
        assert len(sessions(engine)) == 1
        signed_in(device(client))
        assert len(sessions(engine)) == 1 and sessions(engine)[0].expires_at != PAST


def test_end_all_checks_the_session_again_inside_its_write(client, set_operator, monkeypatch):
    """The session ends after the boundary read it and before the handler's write: 401, nothing written."""
    set_operator()
    signed_in(client)
    signed_in(laptop := device(client))
    real = auth.operator_session

    def then_ended(engine, token):
        found = real(engine, token)
        with write_tx(engine) as conn:
            conn.execute(text("DELETE FROM operator_sessions WHERE token_hash=:hash"), {"hash": auth.token_hash(token)})
        return found

    monkeypatch.setattr(auth, "operator_session", then_ended)
    assert refusal(client.delete("/api/admin/sessions")) == (401, "unauthenticated")
    monkeypatch.setattr(auth, "operator_session", real)
    assert laptop.get("/api/admin/session").json()["authenticated"] is True and len(sessions(client.app.state.engine)) == 1


def test_every_protected_admin_route_answers_a_live_operator(client, set_operator):
    set_operator()
    for method, path in protected_admin_routes(client.app):
        signed_in(client)
        answer = call(client, method, path)
        assert (answer.status_code, answer.json()) == (200, ANSWERS[(method, path)]), (method, path)


def test_only_the_command_line_writes_the_operators_password():
    """No HTTP route can set or read the hash: its key's constant lives in auth.py, which only reads it, and shops.py,
    whose set_operator_password is the one writer and is called by the command alone. The fixture set_operator checks
    the stored row after every test of this file."""
    source = Path(affiche_api.__file__).parent
    files = {file.relative_to(source).as_posix(): file.read_text(encoding="utf-8") for file in source.rglob("*.py")}
    assert {name for name, code in files.items() if "OPERATOR_KEY" in code or auth.OPERATOR_KEY in code} == {
        "posters/auth.py", "shops.py"}
    assert {name for name, code in files.items() if "set_operator_password(" in code} == {"shops.py"}
    on_meta = re.findall(r'text\("([^"]*\bmeta\b[^"]*)"\)', files["posters/auth.py"])
    assert all(statement.startswith("SELECT") for statement in on_meta if ":key" in statement) and len(on_meta) >= 3


def test_the_launcher_logs_the_operators_sign_in_on_stderr_and_no_secret(env, tmp_path, capsys):
    """D-ADMIN-002: serve(), which python -m affiche.api runs in the container, gives the application's loggers their
    handler under uvicorn's own logging configuration. Run in a subprocess on a temporary folder, with no env file."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    env.setenv("DATA_DIR", str(tmp_path))
    env.setenv("APP_ORIGIN", origin)
    code = f"from affiche import api; api.UVICORN['port'] = {port}; api.serve(None)"
    proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    try:
        with httpx2.Client(base_url=origin, headers={**HEADERS, "Origin": origin}, timeout=5, trust_env=False) as remote:
            deadline = time.monotonic() + 20
            while True:
                assert proc.poll() is None, "the server exited before it started"
                try:
                    state = remote.get("/api/admin/session")
                    break
                except (httpx2.ConnectError, httpx2.ConnectTimeout):
                    assert time.monotonic() < deadline, "the server did not start in 20 s"
                    time.sleep(.1)
            assert state.json() == {"authenticated": False, "configured": False}
            capsys.readouterr()
            assert shops.main(["operator-password"], env_file=None) == 0
            password = capsys.readouterr().out.rsplit(": ", 1)[1].strip()
            answer = remote.post("/api/admin/session", json={"password": password})
            assert answer.status_code == 200, answer.text
            token, actor = remote.cookies.get(auth.OPERATOR_COOKIE), answer.json()["actor"]
    finally:
        proc.kill()
        _, err = proc.communicate(timeout=10)
    stderr = err.decode("utf-8")
    assert stderr.count(f"INFO affiche.admin: operator action=sign_in shop=- actor={actor} address=127.0.0.1\n") == 1, stderr
    # The warnings of before go through the same handler, once: no second copy from Python's last resort.
    assert stderr.count("WARNING affiche.posters.auth: shop 1 has no password") == 1, stderr
    with sqlite3.connect(tmp_path / "affiche.db") as conn:
        stored = conn.execute("SELECT value FROM meta WHERE key=?", (auth.OPERATOR_KEY,)).fetchone()[0]
    assert all(secret not in stderr for secret in (password, token, auth.token_hash(token), stored))
