"""The operator's sign-in, sessions and request boundary (D-ADMIN-001, R-ADMIN-001) as tested properties: the rows of the
design's three security matrices for the routes that exist, the limits, the session checked again inside a write, the
journal line under the real launcher, and that no HTTP route writes the operator's password. Then the dashboard's
routes (D-ADMIN-003, D-ADMIN-004): each answer's HTTP body, the command line's refusals, and nothing written by a
refused write."""
import logging
import os
import re
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text

from affiche import api as affiche_api, shops
from affiche.api import create_app
from affiche.db import make_engine, utc_now, write_tx
from affiche.posters import auth, credits, jobs, store
from affiche.posters.auth import PASSWORDS
from affiche.posters.credits import MOST
from test_api import (HEADERS, IDENTIFIER, ORIGIN, PASSWORD, Counting, at_most_one_past_the_limit, client,  # noqa: F401
                      create_draft, credentials, failures, login, operator_client, password_hash, second_shop, settings,
                      slow_wrong)
from test_config import env  # noqa: F401

OPERATOR = os.urandom(13).hex()  # a throwaway operator password of 26 characters per test process
PUBLIC = {("GET", "/api/admin/session"), ("POST", "/api/admin/session"), ("DELETE", "/api/admin/session")}
# Every protected admin route, with a request the operator sends ({id}: shop 1) and the status of its answer. A route
# under /api/admin/ in neither set fails the tests. The move needs answerable()'s shop 2 and payment.
ANSWERS = {("DELETE", "/api/admin/sessions"): (None, 200),
           ("GET", "/api/admin/shops"): (None, 200),
           ("POST", "/api/admin/shops"): ({"identifier": "Boutique Trois", "name": None, "welcome": 5}, 201),
           ("GET", "/api/admin/shops/{id}"): (None, 200),
           ("POST", "/api/admin/shops/{id}/password"): (None, 200),
           ("DELETE", "/api/admin/shops/{id}/sessions"): (None, 200),
           ("POST", "/api/admin/shops/{id}/suspend"): (None, 200),
           ("POST", "/api/admin/shops/{id}/enable"): (None, 200),
           ("GET", "/api/admin/shops/{id}/history"): (None, 200),
           ("POST", "/api/admin/shops/{id}/grants"): ({"credits": 2, "origin": "offered", "ref": "geste-1"}, 201),
           ("POST", "/api/admin/shops/{id}/corrections"): ({"credits": -1, "ref": "retrait-1", "note": "erreur"}, 201),
           ("POST", "/api/admin/payments/move"): ({"ref": "MV-1", "from_shop": 1, "to_shop": 2, "note": "mauvaise boutique"},
                                                 201),
           ("GET", "/api/admin/payments"): (None, 200),
           ("GET", "/api/admin/service"): (None, 200),
           ("POST", "/api/admin/service/pause"): (None, 200),
           ("POST", "/api/admin/service/resume"): (None, 200),
           ("PUT", "/api/admin/service/purchase-text"): ({"text": "Pack 10 : 10 000 Ar par MVola."}, 200)}
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


def call(client, method, path, body=None, **headers):
    return client.request(method, re.sub(r"\{\w+\}", "1", path), json=body, headers=headers)


def answerable(engine):
    """What ANSWERS' requests need to succeed: shop 2, and a bought payment of shop 1 to move there."""
    second_shop(engine)
    with write_tx(engine) as conn:
        credits.grant(conn, 1, 10, origin="bought", ref="MV-1", actor="tests", amount_ar=10000, method="mvola")


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


def test_every_protected_admin_route_answers_a_live_operator(client, set_operator, never_logged):
    set_operator()
    answerable(client.app.state.engine)
    for method, path in protected_admin_routes(client.app):
        signed_in(client)
        body, status = ANSWERS[(method, path)]
        answer = call(client, method, path, body)
        assert (answer.status_code, "error" in answer.json()) == (status, False), (method, path, answer.text)
        never_logged.append(answer.json().get("password", OPERATOR))
        if (method, path) == ("DELETE", "/api/admin/sessions"):
            assert answer.json() == {"ended": 1}


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


# Shops (T-ADMIN-003, R-ADMIN-002): every write calls the command line's functions in operator_tx.
T = "2026-11-16T10:00:00.000000+00:00"
KEYS = {"code", "message_fr", "retryable"}


def posters(engine, shop, *rows):
    """Posters written by hand: (id, status, created_at, its job's status or None). A job takes a credit and is of a
    kind the API's scheduler never claims (background; service.KINDS), so it stays as written."""
    with write_tx(engine) as conn:
        conn.exec_driver_sql(f"INSERT OR IGNORE INTO product_inputs VALUES ('in1',1,'P1','JBL','Bleu','[]','{{}}',NULL,'{T}')")
        for id, status, at, job in rows:
            conn.exec_driver_sql("INSERT INTO creations VALUES (?,?,NULL,1,?,?,?)", (id, shop, status, at, at))
            conn.exec_driver_sql("INSERT INTO creation_versions VALUES (?,1,'{}','h',?)", (id, at))
            if job is not None:
                conn.exec_driver_sql("INSERT INTO poster_jobs (id,shop_id,creation_id,origin_revision,input_id,kind,input_json,"
                                     "input_hash,status,created_at,started_at,takes_credit)"
                                     " VALUES (?,?,?,1,'in1','background','{}','h',?,?,?,1)",
                                     (id, shop, id, job, at, None if job == "queued" else at))


def journal_lines(caplog):
    return [record.getMessage() for record in caplog.records if record.name == "affiche.admin"]


def snapshot(engine):
    """Everything an admin write may change, but the operator's own sessions."""
    with engine.connect() as conn:
        return {table: conn.exec_driver_sql(f"SELECT * FROM {table} ORDER BY rowid").all()
                for table in ("shop_profile", "sessions", "credit_grants", "poster_jobs", "meta")}


def operator_refused(detail):
    return {"code": "operator_refused", "message_fr": "Refusé : rien n’a été écrit.", "retryable": False, "detail": detail}


def test_a_shop_created_from_the_dashboard_signs_in_at_once_with_its_password_shown_once(client, set_operator,
                                                                                       never_logged, caplog):
    engine = client.app.state.engine
    set_operator()
    actor = signed_in(client)
    answer = client.post("/api/admin/shops", json={"identifier": "Boutique Deux", "name": " Chez Deux ", "welcome": 5})
    assert answer.status_code == 201, answer.text
    body = answer.json()
    password = body["password"]
    never_logged.append(password)
    assert len(password) == 12 and set(password) <= set(shops.ALPHABET)
    assert body == {"password": password, "welcome_line": body["welcome_line"], "shop": {
        "id": 2, "identifier": "boutiquedeux", "name": "Chez Deux", "state": "active", "has_password": True,
        "created_at": body["shop"]["created_at"], "available": 5, "pending": 0, "posters": 0, "last_poster_at": None,
        "sessions": 0}}
    with engine.connect() as conn:  # the welcome grant is the dashboard session's
        line = conn.execute(text("SELECT shop_id, kind, origin, credits, ref, note, actor FROM credit_grants WHERE id=:id"),
                            {"id": body["welcome_line"]}).one()
    assert tuple(line) == (2, "grant", "offered", 5, "welcome", "Crédits de bienvenue", actor)
    assert device(client).post("/api/session", json=credentials(password, "boutique deux")).json() == {
        "authenticated": True, "shop_id": 2}
    bare = client.post("/api/admin/shops", json={"identifier": "Boutique Trois", "welcome": 0})
    never_logged.append(bare.json()["password"])
    assert (bare.status_code, bare.json()["welcome_line"], bare.json()["shop"]["available"]) == (201, None, 0)
    assert journal_lines(caplog)[-2:] == [f"operator action=shop_created shop=boutiquedeux actor={actor} welcome=5",
                                          f"operator action=shop_created shop=boutiquetrois actor={actor} welcome=0"]


def test_a_refused_creation_writes_nothing_and_says_why(client, set_operator, caplog):
    engine = client.app.state.engine
    set_operator()
    signed_in(client)
    before = snapshot(engine)
    for body, status, error in (
            ({"identifier": "Original-Phone", "welcome": 5}, 409,
             operator_refused("the identifier originalphone is already taken")),
            ({"identifier": "a-b", "welcome": 5}, 409, operator_refused("an identifier needs 3 to 32 letters or digits")),
            ({"identifier": "troisieme", "name": "x" * 161, "welcome": 5}, 422,  # the profile's own rule
             {"code": "validation_error", "message_fr": affiche_api.MESSAGES["validation_error"], "retryable": False,
              "field": "name"})):
        answer = client.post("/api/admin/shops", json=body)
        assert (answer.status_code, answer.json()["error"]) == (status, error), body
    for body in ({"identifier": "troisieme", "welcome": -1}, {"identifier": "troisieme", "welcome": credits.MOST + 1},
                 {"identifier": "troisieme"}, {"identifier": "troisieme", "welcome": "5"},
                 {"identifier": "troisieme", "welcome": 5, "password": "mine"}):
        assert refusal(client.post("/api/admin/shops", json=body)) == (422, "validation_error"), body
    assert snapshot(engine) == before
    assert not [line for line in journal_lines(caplog) if "shop_created" in line]


def test_the_list_and_one_shop_read_the_ledgers_and_todays_limits(client, settings, set_operator):
    engine = client.app.state.engine
    set_operator()
    signed_in(client)
    login(client)  # shop 1's one live session
    today, yesterday = utc_now()[:10], (datetime.now(UTC) - timedelta(days=1)).date().isoformat()
    posters(engine, 1, ("p1", "active", f"{yesterday}T08:00:00.000000+00:00", "queued"),
            ("p2", "abandoned", f"{today}T00:00:00.000000+00:00", None),
            ("p3", "active", f"{yesterday}T09:00:00.000000+00:00", "succeeded"))
    with write_tx(engine) as conn:
        conn.exec_driver_sql("INSERT INTO sessions VALUES (?,1,?)", (auth.token_hash("old"), PAST))  # expired
        for call_no, at, cost in ((1, f"{yesterday}T23:59:59.999999+00:00", 50000), (2, f"{today}T00:00:01.000000+00:00", 120000)):
            conn.exec_driver_sql("INSERT INTO poster_calls (id,job_id,call_no,provider,model,rate_card_json,status,"
                                 "cost_micros,cost_is_estimate,created_at) VALUES (?,'p3',?,'openai','m','{}','succeeded',?,0,?)",
                                 (f"c{call_no}", call_no, cost, at))
        for key, at in (("r1", f"{yesterday}T23:59:59.999999+00:00"), ("r2", f"{today}T00:00:00.000000+00:00")):
            conn.exec_driver_sql("INSERT INTO chat_reads (id,shop_id,creation_id,key,payload_sha,status,provider,model,"
                                 "rate_card_json,cost_micros,cost_is_estimate,created_at) VALUES (?,1,NULL,?,'h','succeeded',"
                                 "'claude','m','{}',3000,0,?)", (key, key, at))
        pilot = shops.find_shop(conn, IDENTIFIER)
        created_at = conn.exec_driver_sql("SELECT created_at FROM shop_profile WHERE id=1").scalar_one()
    assert client.post("/api/admin/shops", json={"identifier": "Boutique Deux", "welcome": 0}).status_code == 201
    items = client.get("/api/admin/shops").json()["items"]
    assert [item["identifier"] for item in items] == ["boutiquedeux", "originalphone"]  # by identifier, not by id
    assert items[1] == {"id": 1, "identifier": "originalphone", "name": pilot.name, "state": "active", "has_password": True,
                        "created_at": created_at, "available": 98, "pending": 1, "posters": 2,
                        "last_poster_at": f"{today}T00:00:00.000000+00:00", "sessions": 1}
    assert client.get("/api/admin/shops/1").json() == {"shop": items[1], "limits": {
        "day_spent_micros": 123000, "day_limit_micros": int(settings.shop_daily_spend_usd * 1_000_000),
        "reads_today": 1, "reads_limit": 100}}
    assert refusal(client.get("/api/admin/shops/99")) == (404, "not_found")
    for id in ("0", "x", str(credits.MOST + 1)):
        assert refusal(client.get(f"/api/admin/shops/{id}")) == (422, "validation_error"), id
    with write_tx(engine) as conn:  # a backup from before 0013 restored: shop 1 has no password
        conn.exec_driver_sql("UPDATE shop_profile SET password_hash=NULL WHERE id=1")
    assert client.get("/api/admin/shops").json()["items"][1]["has_password"] is False


def test_a_new_password_ending_sessions_suspend_and_enable_change_one_shop_and_log_only_a_change(client, set_operator,
                                                                                               never_logged, caplog):
    engine = client.app.state.engine
    set_operator()
    actor = signed_in(client)
    login(client)  # shop 1, on the operator's browser: no write below touches it
    first = client.post("/api/admin/shops", json={"identifier": "Boutique Deux", "welcome": 5}).json()["password"]
    never_logged.append(first)
    owner, phone = device(client), device(client)
    for shop in (owner, phone):
        assert shop.post("/api/session", json=credentials(first, "boutiquedeux")).status_code == 200
    answer = client.post("/api/admin/shops/2/password")
    reset = answer.json()["password"]
    never_logged.append(reset)
    assert (answer.status_code, answer.json()) == (200, {"password": reset, "sessions_ended": 2}) and reset != first
    assert len(reset) == 12 and set(reset) <= set(shops.ALPHABET)
    assert refusal(owner.get("/api/shop-profile")) == refusal(phone.get("/api/shop-profile")) == (401, "unauthenticated")
    assert refusal(owner.post("/api/session", json=credentials(first, "boutiquedeux"))) == (401, "wrong_credentials")
    assert owner.post("/api/session", json=credentials(reset, "boutiquedeux")).status_code == 200
    assert client.delete("/api/admin/shops/2/sessions").json() == {"ended": 1}
    assert client.delete("/api/admin/shops/2/sessions").json() == {"ended": 0}  # nothing left: no line
    assert refusal(owner.get("/api/shop-profile")) == (401, "unauthenticated")
    assert owner.post("/api/session", json=credentials(reset, "boutiquedeux")).status_code == 200
    posters(engine, 2, ("q1", "active", T, "queued"), ("q2", "active", T, "queued"), ("r1", "active", T, "running"),
            ("d1", "active", T, "succeeded"))
    assert client.get("/api/admin/shops/2").json()["shop"]["available"] == 1
    assert client.post("/api/admin/shops/2/suspend").json() == {"changed": True, "cancelled_jobs": 2}
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT id, status, error_code FROM poster_jobs ORDER BY id").all() == [
            ("d1", "succeeded", None), ("q1", "cancelled", "shop_suspended"), ("q2", "cancelled", "shop_suspended"),
            ("r1", "running", None)]  # a running job finishes (D-MULTI-SHOP-006)
    shop = client.get("/api/admin/shops/2").json()["shop"]
    assert (shop["state"], shop["available"], shop["pending"], shop["sessions"]) == ("suspended", 3, 1, 1)  # credits back
    assert refusal(owner.get("/api/shop-profile")) == (401, "unauthenticated")  # its session kept, refused
    assert client.post("/api/admin/shops/2/suspend").json() == {"changed": False, "cancelled_jobs": 0}
    assert client.post("/api/admin/shops/2/enable").json() == {"changed": True}
    assert owner.get("/api/shop-profile").status_code == 200
    assert client.post("/api/admin/shops/2/enable").json() == {"changed": False}
    assert client.get("/api/shop-profile").status_code == 200  # shop 1's session, through all of it
    for method, path in (("POST", "password"), ("DELETE", "sessions"), ("POST", "suspend"), ("POST", "enable")):
        assert refusal(client.request(method, f"/api/admin/shops/99/{path}")) == (404, "not_found")
    assert journal_lines(caplog)[-5:] == [f"operator action={line} actor={actor}{extra}" for line, extra in (
        ("shop_created shop=boutiquedeux", " welcome=5"), ("password_set shop=boutiquedeux", ""),
        ("sessions_ended shop=boutiquedeux", " count=1"), ("shop_suspended shop=boutiquedeux", " cancelled=2"),
        ("shop_enabled shop=boutiquedeux", ""))]


@pytest.mark.parametrize("method, path", sorted(route for route in ANSWERS if route[0] != "GET"))
def test_every_write_finds_its_session_ended_after_the_boundary_and_writes_nothing(client, set_operator, monkeypatch,
                                                                                    method, path):
    """The session ends after the boundary read it and before the handler's write: 401, nothing written (mutation
    check 5)."""
    engine = client.app.state.engine
    set_operator()
    answerable(engine)  # every request below would succeed: what it would write is what the snapshot checks
    login(client)  # what a new password or an end of sessions would delete
    signed_in(device(client))  # what « End all » would delete
    signed_in(client)
    with write_tx(engine) as conn:
        if path.endswith("/enable"):
            shops.suspend(conn, 1)
        elif path.endswith("/resume"):
            shops.pause(conn)
    before, real = snapshot(engine), auth.operator_session

    def then_ended(engine, token):
        found = real(engine, token)
        with write_tx(engine) as conn:
            conn.execute(text("DELETE FROM operator_sessions WHERE token_hash=:hash"), {"hash": auth.token_hash(token)})
        return found

    monkeypatch.setattr(auth, "operator_session", then_ended)
    assert refusal(call(client, method, path, ANSWERS[(method, path)][0])) == (401, "unauthenticated")
    assert snapshot(engine) == before and len(sessions(engine)) == 1


def test_a_session_that_expires_while_the_write_waits_for_the_lock_writes_nothing(client, settings, set_operator,
                                                                                 monkeypatch):
    """operator_live reads the time once BEGIN IMMEDIATE holds the lock: a session live at the boundary and expired when
    the lock comes is refused."""
    engine = client.app.state.engine
    set_operator()
    signed_in(client)
    writer, locked, read, real = make_engine(settings.data_dir), threading.Event(), [], auth.operator_session
    monkeypatch.setattr(auth, "operator_session", lambda engine, token: read.append(real(engine, token)) or read[-1])
    with write_tx(engine) as conn:
        conn.execute(text("UPDATE operator_sessions SET expires_at=:at"),
                     {"at": (datetime.now(UTC) + timedelta(seconds=1.5)).isoformat(timespec="microseconds")})

    def hold():
        with write_tx(writer) as conn:
            conn.exec_driver_sql("SELECT 1")
            locked.set()
            time.sleep(2.5)  # past the session's expiry, under the 5 s busy_timeout

    holder = threading.Thread(target=hold)
    holder.start()
    try:
        assert locked.wait(5)
        answer = client.post("/api/admin/shops/1/suspend")
    finally:
        holder.join(timeout=10)
        writer.dispose()
    assert read[0] is not None  # live at the boundary
    assert refusal(answer) == (401, "unauthenticated")
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT state FROM shop_profile WHERE id=1").scalar_one() == "active"


def test_a_defect_inside_a_write_is_a_500_without_its_text_and_writes_nothing(client, set_operator, monkeypatch):
    """A KeyError is a defect, never a refusal: not 409 with the exception's text (Codex, T-ADMIN-003 r1)."""
    set_operator()
    signed_in(client)

    def defect(conn, shop_id):
        conn.execute(text("UPDATE shop_profile SET state='suspended' WHERE id=:id"), {"id": shop_id})
        raise KeyError("secret-looking text")

    monkeypatch.setattr(shops, "suspend", defect)
    answer = client.post("/api/admin/shops/1/suspend")
    assert answer.status_code == 500 and "secret-looking" not in answer.text
    with client.app.state.engine.connect() as conn:
        assert conn.execute(text("SELECT state FROM shop_profile WHERE id=1")).scalar_one() == "active"


def test_a_write_that_cannot_take_the_lock_answers_503_and_writes_nothing(client, settings, set_operator):
    engine = client.app.state.engine
    set_operator()
    signed_in(client)

    def impatient(dbapi_conn, _record):  # 0.2 s in place of the 5 s busy_timeout: the same failure, sooner
        dbapi_conn.execute("PRAGMA busy_timeout = 200")

    event.listen(engine, "connect", impatient)
    engine.dispose()  # the pool's connections wait 5 s
    writer = make_engine(settings.data_dir)
    try:
        with write_tx(writer) as conn:
            conn.exec_driver_sql("SELECT 1")  # BEGIN IMMEDIATE: the lock is held
            answer = client.post("/api/admin/shops/1/suspend")
    finally:
        writer.dispose()
        event.remove(engine, "connect", impatient)
        engine.dispose()
    assert (answer.status_code, answer.json()["error"]) == (503, {
        "code": "storage_unavailable", "message_fr": affiche_api.MESSAGES["storage_unavailable"], "retryable": True})
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT state FROM shop_profile WHERE id=1").scalar_one() == "active"


def test_only_the_operators_refusals_carry_a_detail_or_an_existing_line(client):
    """store.Refused's two keys are written only when set, and only admin.py sets them: a shop's refusal is as before."""
    assert set(client.get("/api/balance").json()["error"]) == KEYS
    assert set(client.post("/api/session", json={"identifier": "", "password": "x"}).json()["error"]) == KEYS | {"field"}
    login(client)
    assert set(client.get("/api/creations?before=x").json()["error"]) == KEYS
    assert {"detail", "existing"} <= set(client.app.openapi()["components"]["schemas"]["ErrorDetail"]["properties"])


# Money (T-ADMIN-004, R-ADMIN-003): credits.grant, credits.correct and credits.move under the session's actor. A request
# sent again is written once and answered with the line that holds its place.
def lines(engine):
    with engine.connect() as conn:
        return conn.exec_driver_sql("SELECT id, shop_id, kind, origin, credits, amount_ar, method, ref, job_id, note, actor"
                                    " FROM credit_grants ORDER BY id").all()


def stored(engine, id):
    """A line as `existing` shows it."""
    with engine.connect() as conn:
        return dict(conn.exec_driver_sql(
            "SELECT g.id, g.shop_id, g.kind, g.origin, g.credits, g.amount_ar, g.method, g.ref, g.job_id, g.created_at,"
            " p.identifier FROM credit_grants g JOIN shop_profile p ON p.id = g.shop_id WHERE g.id=?", (id,)).mappings().one())


def recorded(answer, detail, line, moved_to=None):
    assert (answer.status_code, answer.json()["error"]) == (409, {
        "code": "already_recorded", "message_fr": "Déjà enregistré : rien n’a été écrit de plus.", "retryable": False,
        "detail": detail, "existing": line | {"moved_to": moved_to}}), answer.text


def new_shops(client, *identifiers):
    """Shops with no credit; their ids."""
    return [client.post("/api/admin/shops", json={"identifier": identifier, "welcome": 0}).json()["shop"]["id"]
            for identifier in identifiers]


def test_a_grant_answers_its_line_the_balance_after_it_and_the_headroom(client, set_operator):
    engine = client.app.state.engine
    set_operator()
    actor = signed_in(client)
    two, = new_shops(client, "Boutique Deux")
    posters(engine, two, ("q1", "active", T, "queued"))  # an image waiting: a balance is not the sum of the lines
    taken = client.post("/api/admin/shops/1/corrections", json={"credits": -100, "ref": "retrait", "note": "tests"})
    assert (taken.status_code, taken.json()["balance"]) == (201, {"available": 0, "pending": 0})
    room = {"cap": 20_000_000, "spent": 0, "left": 20_000_000, "images": 0, "unit": 400_000}  # ESTIMATE_SCENE_USD
    offered = client.post(f"/api/admin/shops/{two}/grants",
                          json={"credits": 5, "origin": "offered", "ref": "geste-1", "note": "bienvenue"})
    assert (offered.status_code, offered.json()) == (201, {"line": 3, "balance": {"available": 4, "pending": 1},
                                                           "headroom": room | {"outstanding": 4, "cost": 1_600_000,
                                                                               "warning": False}})
    bought = client.post(f"/api/admin/shops/{two}/grants", json={"credits": 60, "origin": "bought", "ref": "MV-123",
                                                                 "amount_ar": 120000, "method": "MVola"})
    assert (bought.status_code, bought.json()) == (201, {"line": 4, "balance": {"available": 64, "pending": 1},
                                                         "headroom": room | {"outstanding": 64, "cost": 25_600_000,
                                                                             "warning": True}})
    assert lines(engine)[1:] == [(2, 1, "correction", None, -100, None, None, "retrait", None, "tests", actor),
                                 (3, two, "grant", "offered", 5, None, None, "geste-1", None, "bienvenue", actor),
                                 (4, two, "grant", "bought", 60, 120000, "mvola", "MV-123", None, None, actor)]
    for body, status, code in (({"credits": 1, "origin": "bought", "ref": "x", "amount_ar": 100}, 409, "operator_refused"),
                               ({"credits": 1, "origin": "offered", "ref": "x", "method": "cash"}, 409, "operator_refused"),
                               ({"credits": 1, "origin": "offered", "ref": "x" * 101}, 422, "validation_error"),
                               ({"credits": 1, "origin": "gift", "ref": "x"}, 422, "validation_error"),
                               ({"credits": 0, "origin": "offered", "ref": "x"}, 422, "validation_error"),
                               ({"credits": MOST + 1, "origin": "offered", "ref": "x"}, 422, "validation_error"),
                               ({"credits": 1, "origin": "offered", "ref": "x", "actor": "operator"}, 422, "validation_error")):
        assert refusal(client.post(f"/api/admin/shops/{two}/grants", json=body)) == (status, code), body
    assert client.post(f"/api/admin/shops/{two}/grants", json={"credits": 1, "origin": "bought", "ref": "x",
                                                                "amount_ar": 100}).json()["error"]["detail"] == (
        "a bought grant needs its amount in ariary and its payment method")
    assert refusal(client.post("/api/admin/shops/99/grants", json={"credits": 1, "origin": "offered", "ref": "x"})) == (
        404, "not_found")
    assert len(lines(engine)) == 4


def test_a_grant_sent_again_is_written_once_and_answered_with_the_line_that_holds_it(client, set_operator):
    engine = client.app.state.engine
    set_operator()
    signed_in(client)
    two, three = new_shops(client, "Boutique Deux", "Boutique Trois")
    bought = {"credits": 10, "origin": "bought", "ref": "MV-123", "amount_ar": 20000, "method": "mvola", "note": "pack"}
    line = client.post(f"/api/admin/shops/{two}/grants", json=bought).json()["line"]
    gift = {"credits": 2, "origin": "offered", "ref": "offered-20261117-101500-abcdef"}
    given = client.post(f"/api/admin/shops/{two}/grants", json=gift).json()["line"]
    count = len(lines(engine))
    for sent in (bought, bought | {"ref": " mv-123 "}):  # the reference as the server compares it
        recorded(client.post(f"/api/admin/shops/{two}/grants", json=sent),
                 f"this shop already has a grant with the reference 'MV-123' (line {line})", stored(engine, line))
    recorded(client.post(f"/api/admin/shops/{two}/grants", json=gift),
             f"this shop already has a grant with the reference '{gift['ref']}' (line {given})", stored(engine, given))
    # Another shop's line: the payment is boutiquedeux's, and only a move changes that.
    recorded(client.post(f"/api/admin/shops/{three}/grants", json=bought),
             f"the payment 'MV-123' is already recorded in shop boutiquedeux (line {line}): a payment changes shop only "
             "by move-payment", stored(engine, line))
    assert stored(engine, line)["shop_id"] == two and len(lines(engine)) == count
    assert client.get(f"/api/admin/shops/{two}").json()["shop"]["available"] == 12


def test_corrections_repayments_and_amount_fixes_keep_the_command_lines_rules(client, set_operator):
    engine = client.app.state.engine
    set_operator()
    actor = signed_in(client)
    two, = new_shops(client, "Boutique Deux")
    done, lost = str(uuid4()), str(uuid4())
    posters(engine, two, (done, "active", T, "succeeded"), (lost, "active", T, "failed"))
    client.post(f"/api/admin/shops/{two}/grants", json={"credits": 3, "origin": "offered", "ref": "geste"})
    path, count = f"/api/admin/shops/{two}/corrections", len(lines(engine))
    below = client.post(path, json={"credits": -3, "ref": "retrait", "note": "trop"})
    assert (below.status_code, below.json()["error"]) == (409, operator_refused("the balance would go below zero (available 2)"))
    repay = {"credits": 1, "ref": f"repay-{done}", "note": "image défectueuse", "job_id": done}
    first = client.post(path, json=repay)
    assert (first.status_code, first.json()["balance"]) == (201, {"available": 3, "pending": 0})
    repaid = first.json()["line"]
    recorded(client.post(path, json=repay), f"this job was already repaid (line {repaid})", stored(engine, repaid))
    recorded(client.post(path, json=repay | {"ref": "autre"}), f"this job was already repaid (line {repaid})",
             stored(engine, repaid))  # one repayment per job, whatever its reference
    failed = client.post(path, json={"credits": 1, "ref": f"repay-{lost}", "note": "x", "job_id": lost})
    assert (failed.status_code, failed.json()["error"]) == (
        409, operator_refused("only a succeeded job of this shop that took a credit can be repaid"))
    taken = {"credits": -1, "ref": "retrait", "note": "erreur"}
    line = client.post(path, json=taken).json()["line"]
    recorded(client.post(path, json=taken), f"this shop already has a correction with the reference 'retrait' (line {line})",
             stored(engine, line))
    client.post(f"/api/admin/shops/{two}/grants", json={"credits": 10, "origin": "bought", "ref": "MV-9",
                                                         "amount_ar": 10000, "method": "cash"})
    fix = {"credits": 0, "ref": "mv-9", "note": "montant", "amount_ar": -1000}
    fixed = client.post(path, json=fix)
    assert (fixed.status_code, fixed.json()["balance"]) == (201, {"available": 12, "pending": 0})
    recorded(client.post(path, json=fix), "the payment 'MV-9' was already moved or corrected in this shop",
             stored(engine, fixed.json()["line"]))  # an amount fix sent again
    for body in ({"credits": 1, "ref": "x"}, {"credits": 1, "ref": "x", "note": "n", "job_id": "not-a-uuid"},
                 {"credits": -MOST - 1, "ref": "x", "note": "n"}):
        assert refusal(client.post(path, json=body)) == (422, "validation_error"), body
    assert lines(engine)[count:] == [
        (repaid, two, "correction", None, 1, None, None, f"repay-{done}", done, "image défectueuse", actor),
        (line, two, "correction", None, -1, None, None, "retrait", None, "erreur", actor),
        (line + 1, two, "grant", "bought", 10, 10000, "cash", "MV-9", None, None, actor),
        (line + 2, two, "correction", None, 0, -1000, None, "MV-9", None, "montant", actor)]


def test_a_payment_moves_whole_while_unspent_and_a_move_sent_again_says_where_it_went(client, set_operator):
    engine = client.app.state.engine
    set_operator()
    actor = signed_in(client)
    a, b, c = new_shops(client, "Boutique A", "Boutique B", "Boutique C")

    def pay(shop, ref):
        answer = client.post(f"/api/admin/shops/{shop}/grants", json={"credits": 10, "origin": "bought", "ref": ref,
                                                                      "amount_ar": 20000, "method": "mvola"})
        assert answer.status_code == 201, answer.text
        return answer.json()["line"]

    def move(ref, source, destination):
        return client.post("/api/admin/payments/move", json={"ref": ref, "from_shop": source, "to_shop": destination,
                                                              "note": "mauvaise boutique"})

    def received():
        with engine.connect() as conn:
            return conn.exec_driver_sql("SELECT SUM(amount_ar) FROM credit_grants").scalar()

    pay(a, "MV-1")
    moved = move("mv-1", a, b)
    reversal, grant = moved.json()["lines"]
    assert (moved.status_code, moved.json()) == (201, {"lines": [reversal, grant], "balances": {
        "from": {"available": 0, "pending": 0}, "to": {"available": 10, "pending": 0}}})
    assert received() == 20000 and lines(engine)[-2:] == [
        (reversal, a, "correction", None, -10, -20000, None, "MV-1", None, "mauvaise boutique", actor),
        (grant, b, "grant", "bought", 10, 20000, "mvola", "MV-1", None, "mauvaise boutique", actor)]
    went = {"id": grant, "shop_id": b, "identifier": "boutiqueb"}
    already = f"the payment 'MV-1' was already moved or corrected in the source shop (line {reversal})"
    count = len(lines(engine))
    for destination in (b, c):  # sent again; then sent to another shop after the first: both name B's grant
        recorded(move("MV-1", a, destination), already, stored(engine, reversal), went)
    assert move("MV-1", b, c).status_code == 201  # on to C: A→B sent again still says where it went from A
    recorded(move("MV-1", a, b), already, stored(engine, reversal), went)
    pay(a, "MV-2")
    fix = client.post(f"/api/admin/shops/{a}/corrections", json={"credits": 0, "ref": "MV-2", "note": "montant",
                                                                 "amount_ar": -2000}).json()["line"]
    count = len(lines(engine))
    recorded(move("MV-2", a, b), f"the payment 'MV-2' was already moved or corrected in the source shop (line {fix})",
             stored(engine, fix))  # corrected, not moved: an amount fix holds 0 credits and went nowhere
    assert stored(engine, fix)["credits"] == 0
    pay(b, "MV-3")
    posters(engine, b, (str(uuid4()), "active", T, "succeeded"))  # one of its credits spent
    spent = move("MV-3", b, c)
    assert (spent.status_code, spent.json()["error"]) == (
        409, operator_refused("the source shop has 9 credits left of the payment's 10: it stays where it is"))
    for body in ({"ref": "MV-3", "from_shop": b, "to_shop": b, "note": "n"}, {"ref": "MV-9", "from_shop": b, "to_shop": c,
                                                                                "note": "n"}):
        assert refusal(client.post("/api/admin/payments/move", json=body)) == (409, "operator_refused"), body
    assert refusal(move("MV-3", b, 99)) == (404, "not_found")
    assert refusal(client.post("/api/admin/payments/move", json={"ref": "MV-3", "from_shop": b, "to_shop": c})) == (
        422, "validation_error")  # a move needs its reason
    assert len(lines(engine)) == count + 1 and received() == 60000 - 2000  # MV-3's grant only; each payment once


def test_a_rule_of_the_database_refuses_with_the_drivers_message_and_writes_nothing(client, set_operator, monkeypatch):
    """A line that the module let through and migration 0014 refuses (credits.grant replaced by a plain INSERT)."""
    engine = client.app.state.engine
    set_operator()
    signed_in(client)
    real, count = credits._line, len(lines(engine))
    monkeypatch.setattr(credits, "grant", lambda conn, shop, number, **kwargs: real(conn, shop, "grant", number, "tests",
                                                                                     "x", None, origin="offered"))
    answer = client.post("/api/admin/shops/1/grants", json={"credits": 1, "origin": "offered", "ref": "autre"})
    assert (answer.status_code, answer.json()["error"]) == (409, operator_refused("a credit line is never replaced"))
    assert len(lines(engine)) == count


def test_the_history_route_pages_one_shops_lines_and_jobs_newest_first(client, set_operator):
    engine = client.app.state.engine
    set_operator()
    actor = signed_in(client)
    second_shop(engine)  # its own line: never in shop 1's history
    done = str(uuid4())
    posters(engine, 1, (done, "active", T, "succeeded"), (str(uuid4()), "active", T, None))
    repaid = client.post("/api/admin/shops/1/corrections", json={"credits": 1, "ref": f"repay-{done}", "note": "défaut",
                                                                 "job_id": done}).json()["line"]
    whole = client.get("/api/admin/shops/1/history").json()
    assert whole["next_cursor"] is None and [(item["type"], item["id"]) for item in whole["items"]] == [
        ("line", repaid), ("line", 1), ("job", done)]
    assert whole["items"][0] == {"type": "line", "id": repaid, "kind": "correction", "origin": None, "credits": 1,
                                 "amount_ar": None, "method": None, "ref": f"repay-{done}", "job_id": done,
                                 "note": "défaut", "actor": actor, "at": stored(engine, repaid)["created_at"]}
    assert whole["items"][2] == {"type": "job", "id": done, "kind": "background", "status": "succeeded",
                                 "credit": "spent", "creation_id": done, "result_ref": None, "error_code": None,
                                 "at": T, "finished_at": None, "repaid_by": repaid}
    pages, cursor = [], None
    while True:
        page = client.get("/api/admin/shops/1/history", params={"limit": 1} | ({"before": cursor} if cursor else {})).json()
        pages += page["items"]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert pages == whole["items"]
    for params in ({"before": "x"}, {"before": f"{T}|line|abc"}, {"before": f"{T}|job|1"}):
        assert refusal(client.get("/api/admin/shops/1/history", params=params)) == (422, "invalid_cursor"), params
    for limit in (0, 51):
        assert refusal(client.get("/api/admin/shops/1/history", params={"limit": limit})) == (422, "validation_error")
    assert refusal(client.get("/api/admin/shops/99/history")) == (404, "not_found")


def test_payments_of_a_period_count_whole_utc_days_and_a_moved_payment_once(client, set_operator):
    engine = client.app.state.engine
    set_operator()
    signed_in(client)
    with write_tx(engine) as conn:  # lines at instants no route chooses
        for ref, origin, amount, at in (("before", "bought", 1000, "2025-09-30T23:59:59.999999+00:00"),
                                        ("first", "bought", 1000, "2025-10-01T00:00:00.000000+00:00"),
                                        ("gift", "offered", None, "2025-10-15T00:00:00.000000+00:00"),
                                        ("last", "bought", 3000, "2025-10-31T23:59:59.999999+00:00"),
                                        ("after", "bought", 1000, "2025-11-01T00:00:00.000000+00:00")):
            conn.exec_driver_sql("INSERT INTO credit_grants (shop_id,kind,origin,credits,amount_ar,method,ref,job_id,note,"
                                 "actor,created_at) VALUES (1,'grant',?,1,?,?,?,NULL,NULL,'operator',?)",
                                 (origin, amount, amount and "cash", ref, at))
    october = client.get("/api/admin/payments", params={"start": "2025-10-01", "end": "2025-10-31"}).json()
    item = {"shop_id": 1, "identifier": "originalphone", "kind": "grant", "origin": "bought", "credits": 1,
            "method": "cash", "note": None, "actor": "operator"}
    assert october == {"start": "2025-10-01", "end": "2025-10-31", "received_ar": 4000, "items": [
        item | {"line": 3, "amount_ar": 1000, "ref": "first", "at": "2025-10-01T00:00:00.000000+00:00"},
        item | {"line": 5, "amount_ar": 3000, "ref": "last", "at": "2025-10-31T23:59:59.999999+00:00"}]}
    two, = new_shops(client, "Boutique Deux")
    client.post("/api/admin/shops/1/grants", json={"credits": 10, "origin": "bought", "ref": "MV-1", "amount_ar": 5000,
                                                   "method": "mvola"})
    assert client.post("/api/admin/payments/move", json={"ref": "MV-1", "from_shop": 1, "to_shop": two,
                                                         "note": "mauvaise boutique"}).status_code == 201
    month = client.get("/api/admin/payments").json()  # the current UTC month by default
    today = datetime.now(UTC).date()
    assert (month["start"], month["end"]) == (today.replace(day=1).isoformat(), (
        (today.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)).isoformat())
    assert [(item["shop_id"], item["kind"], item["amount_ar"]) for item in month["items"]] == [
        (1, "grant", 5000), (1, "correction", -5000), (two, "grant", 5000)] and month["received_ar"] == 5000
    for params in ({"start": "2025-10-02", "end": "2025-10-01"}, {"start": "2025-13-01"}, {"end": "hier"},
                   {"end": "9999-12-31"}):  # the last day has no next day to bound the period
        assert refusal(client.get("/api/admin/payments", params=params)) == (422, "validation_error"), params
    assert client.get("/api/admin/payments", params={"start": "2025-10-02", "end": "2025-10-01"}).json()["error"][
        "field"] == "start"


# The service (T-ADMIN-007, R-ADMIN-005, R-ADMIN-006): /api/status's view shared, the pause, the purchase text, the
# operator's sessions.
FALLBACK = "Pour obtenir des crédits, contactez l’administrateur."


def test_the_service_holds_status_views_fields_and_api_status_answers_as_before(client, settings, set_operator, tmp_path,
                                                                                monkeypatch):
    """status_view moved out of /api/status (D-ADMIN-004): /api/status answers its six fields and nothing else, with
    the values it gave before; the service answer holds the same, then what the operator acts on."""
    engine = client.app.state.engine
    set_operator()
    signed_in(client)
    monkeypatch.setenv("REVISION", "abc123")
    settings.backup_dir = tmp_path / "backups"
    settings.backup_dir.mkdir()
    finished = datetime.now(UTC).isoformat(timespec="seconds")
    (settings.backup_dir / "last-backup.json").write_text('{"finished_at": "%s"}' % finished, encoding="utf-8")
    posters(engine, 1, ("f1", "active", T, "failed"))
    with write_tx(engine) as conn:
        conn.execute(text("UPDATE poster_jobs SET finished_at=:now"), {"now": utc_now()})
        migration = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    before = {"commit": "abc123", "migration": migration, "started_at": client.app.state.started_at,
              "backup": {"finished_at": finished, "age_hours": 0.0, "late": False},
              "spend": {"recorded_micros": 0, "cap_micros": 20_000_000, "since": settings.spend_cap_since.isoformat()},
              "failed_jobs_24h": 1}
    assert operator_client(client).get("/api/status").json() == before
    service = client.get("/api/admin/service").json()
    with engine.connect() as conn:
        headroom = shops.headroom(conn, settings)
    assert service == before | {
        "paused_since": None, "purchase_text": {"stored": None, "shown": FALLBACK}, "headroom": headroom,
        "limits": {"shop_daily_spend_micros": int(settings.shop_daily_spend_usd * 1_000_000), "reads_per_day": 100},
        "operator_sessions": service["operator_sessions"]}
    assert refusal(client.get("/api/status")) == (404, "not_found")  # the operator's cookie opens no shop route


def test_pause_and_resume_stop_and_free_a_shops_next_scene_and_log_only_a_change(client, set_operator, caplog):
    engine = client.app.state.engine
    set_operator()
    actor = signed_in(client)
    login(client)  # the pilot shop, on the same browser
    creation = create_draft(client)
    plan = client.post(f'/api/creations/{creation["id"]}/plans', headers={"If-Match": '"1"', "Idempotency-Key": str(uuid4())},
                       json={"mode": "fixed", "direction": "Studio clair", "format": "feed"})
    assert plan.status_code == 201, plan.text

    def scene():
        return client.post(f'/api/creations/{creation["id"]}/scenes', json={"plan_id": plan.json()["id"],
                           "acknowledged_warnings": ["low_resolution"]}, headers={"If-Match": '"1"', "Idempotency-Key": str(uuid4())})

    def made():
        with engine.connect() as conn:
            return conn.execute(text("SELECT COUNT(*) FROM poster_jobs")).scalar_one()

    paused = client.post("/api/admin/service/pause")
    with engine.connect() as conn:
        since = jobs.paused(conn)
    assert (paused.status_code, paused.json()) == (200, {"changed": True, "paused_since": since}) and since
    assert client.get("/api/admin/service").json()["paused_since"] == since
    count = made()
    assert refusal(scene()) == (429, "budget_exhausted")  # the shop is told the pause's sentence; nothing is admitted
    assert made() == count
    assert client.post("/api/admin/service/pause").json() == {"changed": False, "paused_since": since}
    assert client.post("/api/admin/service/resume").json() == {"changed": True}
    assert client.post("/api/admin/service/resume").json() == {"changed": False}
    assert client.get("/api/admin/service").json()["paused_since"] is None
    assert scene().status_code == 202 and made() == count + 1
    assert [line for line in journal_lines(caplog) if "service_" in line] == [
        f"operator action=service_paused shop=- actor={actor}", f"operator action=service_resumed shop=- actor={actor}"]


def test_the_purchase_text_is_set_and_read_back_and_a_blank_one_is_refused(client, set_operator, caplog):
    engine = client.app.state.engine
    set_operator()
    actor = signed_in(client)
    login(client)
    sentence = "Pack 10 : 10 000 Ar par MVola au 034 00 000 00, référence : votre identifiant."

    def put(body):
        return client.put("/api/admin/service/purchase-text", json=body)

    answer = put({"text": f"  {sentence}\n"})
    assert (answer.status_code, answer.json()) == (200, {"stored": sentence, "shown": sentence})  # stripped, as stored
    assert client.get("/api/admin/service").json()["purchase_text"] == {"stored": sentence, "shown": sentence}
    assert client.get("/api/balance").json()["purchase_fr"] == sentence  # what every shop reads
    longest = "é" * 500
    assert put({"text": longest}).json() == {"stored": longest, "shown": longest}
    before = snapshot(engine)
    blank = put({"text": " \n\t "})
    assert (blank.status_code, blank.json()["error"]) == (409, operator_refused("a purchase text has 1 to 500 characters"))
    # Blank or too long: the command line's own rule and sentence (D-ADMIN-004), counted once stripped, in characters.
    for body in ({"text": ""}, {"text": "x" * 501}):
        again = put(body)
        assert (again.status_code, again.json()["error"]) == (409, operator_refused("a purchase text has 1 to 500 characters")), body
    for body in ({"text": 5}, {}, {"text": "x", "stored": "y"}, {"text": "x" * 2001}):
        assert refusal(put(body)) == (422, "validation_error"), body
    assert snapshot(engine) == before
    assert put({"text": longest}).status_code == 200  # sent again: written again, as the design says
    edge = "é" * 499 + "😀"  # 500 characters to the server, 501 UTF-16 units to a browser's maxlength
    assert put({"text": f"{edge} "}).json() == {"stored": edge, "shown": edge}
    assert put({"text": longest}).status_code == 200
    assert [line for line in journal_lines(caplog) if "purchase_text" in line] == [
        f"operator action=purchase_text_set shop=- actor={actor}"] * 5  # never the text itself


def test_the_service_lists_the_live_operator_sessions_and_marks_the_callers(client, set_operator):
    engine = client.app.state.engine
    set_operator()
    other = sign_in(laptop := device(client), **{"User-Agent": "Laptop/1.0"}).json()["actor"]
    agent = "Phone/2.0 " + "x" * 300
    mine = sign_in(client, **{"User-Agent": agent}).json()["actor"]
    signed_in(old := device(client))
    with write_tx(engine) as conn:  # expired: kept until the next sign-in, never listed
        conn.execute(text("UPDATE operator_sessions SET expires_at=:past WHERE token_hash=:hash"),
                     {"past": PAST, "hash": auth.token_hash(old.cookies.get(auth.OPERATOR_COOKIE))})
    rows = sessions(engine)
    assert len(rows) == 3
    answer = client.get("/api/admin/service")
    assert answer.json()["operator_sessions"] == [
        {"actor": other, "created_at": rows[0].created_at, "expires_at": rows[0].expires_at, "address": "testclient",
         "agent": "Laptop/1.0", "current": False},
        {"actor": mine, "created_at": rows[1].created_at, "expires_at": rows[1].expires_at, "address": "testclient",
         "agent": agent[:200], "current": True}]
    assert not any(row.token_hash in answer.text for row in rows)  # the actor names a session; no hash leaves
    assert [row["current"] for row in laptop.get("/api/admin/service").json()["operator_sessions"]] == [True, False]
    assert laptop.delete("/api/admin/sessions").json() == {"ended": 3}  # « End all »: this device's too
    assert refusal(client.get("/api/admin/service")) == refusal(laptop.get("/api/admin/service")) == (401, "unauthenticated")
