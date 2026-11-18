import hashlib
import io
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import os
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path
from uuid import uuid4

import httpx2
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pydantic import SecretStr
from sqlalchemy import exc

from affiche import api as affiche_api, assets, backup, shops
from affiche.api import create_app, uvicorn_options
from affiche.config import ConfigError, load_settings
from affiche.db import make_engine, utc_now, write_tx
from affiche.posters import auth, credits, jobs, rendering, store
from affiche.posters.models import canonical
from affiche.visuals.admission import spent_micros
from test_config import env  # noqa: F401
from test_db import accepted, credited, migrate_to, unaccepted
from test_poster_drafts import photo

ORIGIN = "https://shop.example"
# What the frontend sends with every request (api.ts): the test clients are a current bundle.
HEADERS = {"Origin": ORIGIN, "X-Affiche-Bundle": str(affiche_api.BUNDLE)}
PASSWORD = os.urandom(12).hex()  # a throwaway credential per test process; nothing is written literally
IDENTIFIER = "originalphone"  # the pilot shop's (migration 0013)


def credentials(password: str = PASSWORD, identifier: str = IDENTIFIER) -> dict:
    return {"identifier": identifier, "password": password}


@pytest.fixture(scope="module")
def password_hash():
    return auth.PASSWORDS.hash(PASSWORD)


@pytest.fixture
def settings(env, tmp_path, password_hash):
    env.setenv("DATA_DIR", str(tmp_path))
    env.setenv("APP_ORIGIN", ORIGIN)
    env.setenv("SHOP_PASSWORD_HASH", password_hash)
    return load_settings(env_file=None)


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings, prepare=credited), base_url=ORIGIN, headers=HEADERS) as client:
        yield client


def login(client):
    response = client.post("/api/session", json=credentials(PASSWORD))
    assert response.status_code == 200, response.text
    return response


def post(client, path, body):
    return client.post(path, json=body, headers={"Idempotency-Key": str(uuid4())})


def create_draft(client):
    upload = client.post("/api/assets", files={"file": ("source.png", photo(), "image/png")}, data={"role": "original"})
    assert upload.status_code == 201, upload.text
    source = post(client, "/api/product-inputs", {"name": "JBL", "variant": "Conforme à la photo",
                                                "photo_assets": [upload.json()["asset"]]})
    assert source.status_code == 201, source.text
    result = post(client, "/api/creations", {"input_id": source.json()["id"], "offer": {"title": "JBL Flip", "price_ar": 899000},
        "brand_selection": {"logo": False, "shop_name": False, "contact": False}})
    assert result.status_code == 201, result.text
    return result.json()


def test_owned_job_status_credit_and_cancel(client, settings):
    assert client.get("/api/balance").status_code == 401
    assert client.get("/api/capabilities").status_code == 401
    login(client)
    creation = create_draft(client)
    with write_tx(client.app.state.engine) as conn:
        result = jobs.enqueue(conn, settings, 1, creation["id"], 1, "render", {"prompt": "private prompt"})
    response = client.get(result["status_url"])
    assert response.status_code == 200 and response.json()["status"] == "queued"
    assert response.json()["credit"] is None and "usage" not in response.json()  # a render takes no credit, and no cost is shown
    assert "private prompt" not in response.text
    assert client.get(f"/api/creations/{creation['id']}/jobs").json()["items"] == [response.json()]
    assert client.get(f"/api/creations/{uuid4()}/jobs").status_code == 404
    # The planner's estimate (100000 here) is not given: no dollar figure reaches a shop (D-BALANCE-004).
    assert client.get("/api/capabilities").json() == {"image_mode": "stub", "planner_mode": "disabled",
        "planner_available": False, "formats_enabled": ["feed"], "chat_available": False}
    assert client.get("/api/jobs/" + str(uuid4())).status_code == 404
    assert client.get("/api/usage").status_code == 404  # removed: a shop reads credits, never dollars (D-BALANCE-004)
    with client.app.state.engine.connect() as conn:
        assert spent_micros(conn, settings, shop=1) == 0
    assert operator_client(client).get("/api/status").json()["spend"]["cap_micros"] == 20000000
    assert post(client, result["status_url"] + "/cancel", {}).json()["status"] == "cancelled"
    assert post(client, result["status_url"] + "/cancel", {}).status_code == 409


def old_cancellation(engine, job_id, shop=1) -> tuple[str, dict]:
    """A cancellation answered before migration 0014, stored under its key as the old code stored it: with the job's
    cost. Returns the key and the stored body."""
    stored = {"id": job_id, "status": "cancelled", "result_ref": None, "error_code": None, "created_at": utc_now(),
              "started_at": None, "finished_at": utc_now(), "kind": "scene", "usage": {"recorded_micros": 400000, "estimated": True}}
    operation = str(uuid4())
    with write_tx(engine) as conn:
        conn.exec_driver_sql("INSERT INTO mutation_keys VALUES (?,?,?,?,?,?,?,?)", (
            shop, operation, "POST", f"/api/jobs/{job_id}/cancel", store._sha(canonical({"body": {}, "revision": None})),
            200, canonical(stored), utc_now()))
    return operation, stored


def test_a_cancellation_answered_before_0014_is_replayed_without_its_cost(client):
    login(client)
    operation, stored = old_cancellation(client.app.state.engine, str(uuid4()))
    replayed = client.post(f"/api/jobs/{stored['id']}/cancel", json={}, headers={"Idempotency-Key": operation})
    assert replayed.status_code == 200 and replayed.json() == {key: value for key, value in stored.items() if key != "usage"}


def operator_client(client):
    """The operator's call from the machine that runs the API (D-MULTI-SHOP-004), as verify.sh makes it."""
    return TestClient(client.app, base_url="http://127.0.0.1:8000", client=("127.0.0.1", 50000))


def test_status_tells_the_administrator_what_runs_and_how_old_the_backup_is(client, settings, tmp_path, monkeypatch):
    local = operator_client(client)
    status = local.get("/api/status").json()
    assert status["commit"] == "dev" and status["migration"] and status["backup"] is None
    assert status["spend"] == {"recorded_micros": 0, "cap_micros": 20000000, "since": settings.spend_cap_since.isoformat()}
    assert status["failed_jobs_24h"] == 0 and datetime.fromisoformat(status["started_at"]) <= datetime.now(UTC)

    login(client)
    settings.backup_dir = tmp_path / "backups"
    assert local.get("/api/status").json()["backup"] is None  # no marker yet: not an error
    backup.run(settings.data_dir, settings.backup_dir)
    monkeypatch.setenv("REVISION", "abc123")
    creation = create_draft(client)
    with write_tx(client.app.state.engine) as conn:
        for finished, state in ((datetime.now(UTC), "failed"), (datetime.now(UTC)-timedelta(hours=30), "failed"),
                                (datetime.now(UTC), "interrupted"), (datetime.now(UTC), "succeeded")):
            job = jobs.enqueue(conn, settings, 1, creation["id"], 1, "render", {"n": str(uuid4())})
            conn.exec_driver_sql("UPDATE poster_jobs SET status=?, finished_at=? WHERE id=?",
                                 (state, finished.isoformat(timespec="microseconds"), job["status_url"].rsplit("/", 1)[1]))
    status = local.get("/api/status").json()
    assert status["commit"] == "abc123" and status["failed_jobs_24h"] == 2
    assert status["backup"]["late"] is False and status["backup"]["age_hours"] == 0.0

    marker = settings.backup_dir / "last-backup.json"
    old = (datetime.now(UTC)-timedelta(hours=49)).isoformat(timespec="seconds")
    marker.write_text('{"finished_at": "%s"}' % old, encoding="utf-8")
    assert local.get("/api/status").json()["backup"] == {"finished_at": old, "age_hours": 49.0, "late": True}
    marker.write_text("not json", encoding="utf-8")
    assert local.get("/api/status").json()["backup"] is None


def test_status_answers_only_a_caller_on_the_machine_that_names_a_local_host(client):
    """D-MULTI-SHOP-004: both the client address (after the forwarding headers) and the Host must be local; either
    alone is refused like a route that does not exist, a shop's session changing nothing. Real forwarding through
    uvicorn: test_actual_uvicorn_http_session."""
    def status(peer, host, headers=None):
        answer = TestClient(client.app, base_url=f"http://{host}", client=peer).get("/api/status", headers=headers)
        return answer.status_code, answer.json().get("error", {}).get("code")

    local = ("127.0.0.1", 50000)
    for peer, host in ((local, "127.0.0.1:8000"), (local, "127.0.0.1"), (local, "localhost:5173"), (local, "LOCALHOST"),
                       (local, "[::1]:8000"), (("::1", 50000), "[::1]"), (("127.0.0.9", 50000), "127.0.0.1:8000")):
        assert status(peer, host) == (200, None), (peer, host)
    for peer, host in ((local, "shop.example"), (local, "affiches.miorantsoa.app"), (local, "127.0.0.1.shop.example"),
                       (local, "localhost.shop.example"), (local, "127.0.0.2:8000"), (("203.0.113.9", 50000), "127.0.0.1"),
                       (("203.0.113.9", 50000), "localhost:8000"), (("testclient", 50000), "127.0.0.1"),
                       (("10.0.0.5", 50000), "[::1]:8000")):
        assert status(peer, host) == (404, "not_found"), (peer, host)
    for spoofed in ("127.0.0.1@shop.example", "shop.example#@127.0.0.1", "[::1", ""):  # a Host httpx would not build
        assert status(local, "127.0.0.1:8000", {"Host": spoofed}) == (404, "not_found"), spoofed
    # Whatever else it sends: the stale-tab header, another method, no Origin, an older bundle.
    for answer in (client.get("/api/status"), client.get("/api/status", headers={"X-Affiche-Shop": "1"}),
                   client.post("/api/status", headers={"Origin": "https://evil.example", "X-Affiche-Bundle": "1"})):
        assert (answer.status_code, answer.json()["error"]["code"]) == (404, "not_found")  # a public caller with no session
    login(client)  # a shop's session through the front process, with its own header, another shop's, or none
    for headers in ({}, {"X-Affiche-Shop": "1"}, {"X-Affiche-Shop": "2"}):
        answer = client.get("/api/status", headers=headers)
        assert (answer.status_code, answer.json()["error"]["code"]) == (404, "not_found"), headers


# Refusals that only a programming error in the editor can produce: the owner cannot cause them by what he types
# or taps. Each of them answers with the fallback sentence, which carries the code for the administrator.
DEVELOPER_ONLY = {"call_already_dispatched", "format_missing", "generated_reference_unavailable", "input_immutable",
                  "invalid_cursor", "invalid_idempotency_key", "invalid_job_state", "invalid_revision", "invalid_role",
                  "provider_mode_mismatch", "replacement_identity_mismatch", "replacement_requires_new_input",
                  "unknown_asset"}


def test_every_refusal_the_owner_can_meet_has_its_own_french_sentence(client):
    source = Path(affiche_api.__file__).parent
    raised = set()
    for file in [*(source / "posters").glob("*.py"), source / "api.py", source / "admin.py"]:
        raised |= set(re.findall(r'Refused\(\s*"([a-z_]+)"', file.read_text(encoding="utf-8")))
    assert len(raised) > 70
    unexplained = raised - set(affiche_api.MESSAGES) - DEVELOPER_ONLY
    assert not unexplained, f"add a sentence to MESSAGES in api.py (or to DEVELOPER_ONLY here) for: {sorted(unexplained)}"
    assert not DEVELOPER_ONLY & set(affiche_api.MESSAGES)
    # A small product photo: the refusal says what is wrong and what to do (first finding of the live pilot).
    assert "petite" in affiche_api.MESSAGES["acknowledgement_required"]
    # The fallback names the code; it never blames the form.
    answer = client.get("/api/creations?before=not-a-cursor")
    login(client)
    answer = client.get("/api/creations?before=not-a-cursor")
    assert answer.status_code == 422 and "invalid_cursor" in answer.json()["error"]["message_fr"]


def test_cookie_is_opaque_hash_only_and_logout_revokes(client):
    assert client.get("/api/shop-profile").status_code == 401
    assert client.get("/api/session").json() == {"authenticated": False}
    response = login(client)
    assert response.json() == {"authenticated": True, "shop_id": 1}
    assert client.get("/api/session").json() == {"authenticated": True, "shop_id": 1}
    cookie = response.headers["set-cookie"]
    assert all(flag in cookie for flag in ("HttpOnly", "Secure", "SameSite=strict", "Max-Age=7776000", "Path=/"))
    token = client.cookies.get(auth.COOKIE)
    with client.app.state.engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT token_hash FROM sessions").scalar_one() == hashlib.sha256(token.encode()).hexdigest()
    assert client.get("/api/shop-profile").status_code == 200
    assert client.delete("/api/session").status_code == 200
    assert client.get("/api/shop-profile", headers={"Cookie": f"{auth.COOKIE}={token}"}).status_code == 401


def test_a_paid_request_that_arrives_after_the_sign_out_gets_401_and_creates_nothing(client):
    """ADR-108: the server is the authority for a paid request. A scene request that still carries the session's cookie
    after DELETE /api/session (held on its way, or sent by a late tab) is refused before its handler: no job, no
    idempotency key, no reservation in the ledger. The same request with the session alive makes all three."""
    login(client)
    first, second = create_draft(client), create_draft(client)

    def plan(creation):
        planned = client.post(f'/api/creations/{creation["id"]}/plans', headers={"If-Match": '"1"', "Idempotency-Key": str(uuid4())},
                              json={"mode": "fixed", "direction": "Studio clair", "format": "feed"})
        assert planned.status_code == 201, planned.text
        return planned.json()["id"]

    def scene(creation, plan_id, cookie=None):
        return client.post(f'/api/creations/{creation["id"]}/scenes', json={"plan_id": plan_id, "acknowledged_warnings": ["low_resolution"]},
                           headers={"If-Match": '"1"', "Idempotency-Key": str(uuid4()), **({"Cookie": cookie} if cookie else {})})

    def rows():
        with client.app.state.engine.connect() as conn:
            return [conn.exec_driver_sql(f"SELECT COUNT(*) FROM {table}").scalar_one() for table in ("poster_jobs", "mutation_keys", "poster_calls")]

    token, plans = client.cookies.get(auth.COOKIE), (plan(first), plan(second))
    before = rows()
    assert scene(first, plans[0]).status_code == 202
    alive = rows()
    assert [now - was for now, was in zip(alive, before)] == [1, 1, 1]  # a job, its key, its reservation
    assert client.delete("/api/session").status_code == 200
    late = scene(second, plans[1], f"{auth.COOKIE}={token}")
    assert (late.status_code, late.json()["error"]["code"]) == (401, "unauthenticated")
    assert rows() == alive


def test_no_credit_is_402_with_how_to_get_credits(client, monkeypatch, caplog):
    """D-BALANCE-004: the refusal's sentence, then the purchase text read on a connection of its own (the admission has
    rolled back); unreadable, the sentence goes alone and the failure is logged. Not retryable: nothing changes until a
    grant. Nothing of the request is written."""
    login(client)
    creation, engine = create_draft(client), client.app.state.engine
    plan = client.post(f'/api/creations/{creation["id"]}/plans', headers={"If-Match": '"1"', "Idempotency-Key": str(uuid4())},
                       json={"mode": "fixed", "direction": "Studio clair", "format": "feed"})
    assert plan.status_code == 201, plan.text
    with write_tx(engine) as conn:
        credits.correct(conn, 1, -100, ref="zero", note="test", actor="tests")

    def scene():
        return client.post(f'/api/creations/{creation["id"]}/scenes', json={"plan_id": plan.json()["id"],
                           "acknowledged_warnings": ["low_resolution"]}, headers={"If-Match": '"1"', "Idempotency-Key": str(uuid4())})

    def written():
        with engine.connect() as conn:
            return [conn.exec_driver_sql(f"SELECT COUNT(*) FROM {table}").scalar_one() for table in ("poster_jobs", "poster_calls", "mutation_keys")]

    sentence, before = affiche_api.MESSAGES["no_credit"], written()
    answer = scene()
    assert answer.status_code == 402 and answer.json()["error"] == {
        "code": "no_credit", "retryable": False, "message_fr": f"{sentence} Pour obtenir des crédits, contactez l’administrateur."}
    with write_tx(engine) as conn:
        conn.exec_driver_sql("INSERT INTO meta VALUES ('purchase_text_fr', 'Pack 10 : 10 000 Ar par MVola.')")
    assert scene().json()["error"]["message_fr"] == f"{sentence} Pack 10 : 10 000 Ar par MVola."

    def unreadable(*_):
        raise exc.OperationalError("SELECT", {}, sqlite3.OperationalError("disk I/O error"))
    monkeypatch.setattr(credits, "purchase_text", unreadable)
    answer = scene()
    assert (answer.status_code, answer.json()["error"]["message_fr"]) == (402, sentence)
    assert "purchase text unreadable: OperationalError" in caplog.text
    assert written() == before
    responses = client.get("/api/openapi.json").json()["paths"]["/api/creations/{id}/scenes"]["post"]["responses"]
    assert "402" in responses


def test_balance_says_what_is_left_and_what_would_refuse_each_image_whatever_the_credits(client, settings):
    """D-BALANCE-004: the session's shop's credits and how to get more; per charged operation, what the admission's own
    guard would refuse now with that operation's own estimate (the pause, the cap, no image provider: service; the
    shop's day: day), with that refusal's sentence. The credits themselves never block: the 402 tells them."""
    login(client)
    engine, clear = client.app.state.engine, {"scene": None, "text_texture": None}
    service, day, unavailable = ({"reason": reason, "message_fr": affiche_api.MESSAGES[code]} for reason, code in (
        ("service", "budget_exhausted"), ("day", "shop_daily_limit"), ("service", "provider_unavailable")))

    def balance(available, blocked, purchase="Pour obtenir des crédits, contactez l’administrateur."):
        answer = client.get("/api/balance")
        assert answer.status_code == 200, answer.text
        assert answer.json() == {"available": available, "pending": 0, "purchase_fr": purchase, "blocked": blocked}

    def spend(micros):  # a read of the shop's, today: its day and the service's cap both count it
        with write_tx(engine) as conn:
            conn.exec_driver_sql("INSERT INTO chat_reads (id,shop_id,key,payload_sha,status,provider,model,rate_card_json,"
                                 "cost_micros,cost_is_estimate,created_at) VALUES (?,1,?,'x','succeeded','stub','m','{}',?,0,?)",
                                 (str(uuid4()), str(uuid4()), micros, utc_now()))

    balance(100, clear)
    with write_tx(engine) as conn:
        shops.pause(conn)
    balance(100, {"scene": service, "text_texture": service})
    with write_tx(engine) as conn:
        shops.resume(conn)
        credits.correct(conn, 1, -100, ref="zero", note="test", actor="tests")
    balance(0, clear)
    # A paid provider's estimates (scene 0.40, material 0.30 USD); no job is admitted here, so nothing is sent.
    settings.image_provider, settings.openai_api_key = "openai", SecretStr("test-not-a-key")
    spend(650_000)
    settings.spend_cap_usd = Decimal("1")
    balance(0, {"scene": service, "text_texture": None})  # 0.35 USD left of the cap
    settings.spend_cap_usd, settings.shop_daily_spend_usd = Decimal("20"), Decimal("1")
    balance(0, {"scene": day, "text_texture": None})  # 0.35 USD left of the shop's day
    spend(350_000)
    balance(0, {"scene": day, "text_texture": day})
    settings.spend_cap_usd = Decimal("1")  # the service's cap is told before the shop's day
    balance(0, {"scene": service, "text_texture": service})
    settings.openai_api_key = None
    balance(0, {"scene": unavailable, "text_texture": unavailable})
    with write_tx(engine) as conn:
        conn.exec_driver_sql("INSERT INTO meta VALUES ('purchase_text_fr', 'Pack 10 : 10 000 Ar par MVola.')")
    balance(0, {"scene": unavailable, "text_texture": unavailable}, "Pack 10 : 10 000 Ar par MVola.")


def test_the_conditions_not_accepted_are_a_balance_reason_and_a_403_that_writes_nothing(client):
    """D-TERMS-003: a shop that has not accepted the current conditions still reads its balance (200), and each charged
    operation says `terms`, before the service's pause, with the gate's sentence. Its scene is refused with 403 and that
    sentence, not retryable, and writes nothing; accepted, the pause is told again, then nothing blocks."""
    login(client)
    creation, engine = create_draft(client), client.app.state.engine
    plan = client.post(f'/api/creations/{creation["id"]}/plans', headers={"If-Match": '"1"', "Idempotency-Key": str(uuid4())},
                       json={"mode": "fixed", "direction": "Studio clair", "format": "feed"})
    assert plan.status_code == 201, plan.text
    sentence = "Acceptez d'abord les conditions d'utilisation : rien n'a été envoyé, et aucun crédit n'a été pris."
    conditions = {"reason": "terms", "message_fr": sentence}

    def blocked():
        answer = client.get("/api/balance")
        assert answer.status_code == 200 and answer.json()["available"] == 100, answer.text
        return answer.json()["blocked"]

    def written():
        with engine.connect() as conn:
            return [conn.exec_driver_sql(f"SELECT COUNT(*) FROM {table}").scalar_one() for table in ("poster_jobs", "poster_calls", "mutation_keys")]

    unaccepted(engine)
    assert blocked() == {"scene": conditions, "text_texture": conditions}
    before = written()
    answer = client.post(f'/api/creations/{creation["id"]}/scenes', json={"plan_id": plan.json()["id"],
                         "acknowledged_warnings": ["low_resolution"]}, headers={"If-Match": '"1"', "Idempotency-Key": str(uuid4())})
    assert answer.status_code == 403 and answer.json()["error"] == {
        "code": "terms_required", "retryable": False, "message_fr": sentence}
    assert written() == before
    with write_tx(engine) as conn:
        shops.pause(conn)
    assert blocked() == {"scene": conditions, "text_texture": conditions}
    accepted(engine)
    service = {"reason": "service", "message_fr": affiche_api.MESSAGES["budget_exhausted"]}
    assert blocked() == {"scene": service, "text_texture": service}
    with write_tx(engine) as conn:
        shops.resume(conn)
    assert blocked() == {"scene": None, "text_texture": None}


def test_origin_required_even_for_login_and_logout(client):
    for origin in ("", "https://evil.example", "null", ORIGIN+"/"):
        assert client.post("/api/session", json=credentials(PASSWORD), headers={"Origin": origin}).status_code == 403
    login(client)
    assert client.delete("/api/session", headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.get("/api/session").json()["authenticated"] is True


def test_expired_session_fails_closed(client):
    login(client)
    with write_tx(client.app.state.engine) as conn:
        conn.exec_driver_sql("UPDATE sessions SET expires_at='2000-01-01T00:00:00.000000+00:00'")
    assert client.get("/api/shop-profile").status_code == 401


def test_failed_logins_are_persistent_and_forwarded_ip_cannot_bypass(client, settings):
    for i in range(5):
        response = client.post("/api/session", json=credentials("wrong"), headers={"X-Forwarded-For": f"192.0.2.{i}"})
        assert response.status_code == 401
    assert client.post("/api/session", json=credentials(PASSWORD)).status_code == 429
    with client.app.state.engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT count(*) FROM login_failures").scalar_one() == 5
    assert response.json()["error"]["code"] == "wrong_credentials"


def test_password_is_verified_outside_the_write_transaction_and_not_at_all_once_limited(client, settings, monkeypatch):
    engine, calls = client.app.state.engine, []

    class Probe:
        def verify_and_update(self, password, stored):
            # With the write lock held by the login, this second writer would wait 5 s and fail "database is locked".
            with write_tx(engine) as conn:
                conn.exec_driver_sql("INSERT INTO meta (key,value) VALUES ('probe','1') ON CONFLICT(key) DO NOTHING")
            calls.append(password)
            return False, None

    monkeypatch.setattr(auth, "PASSWORDS", Probe())
    for _ in range(5):
        assert client.post("/api/session", json=credentials("wrong")).status_code == 401
    assert client.post("/api/session", json=credentials("wrong")).status_code == 429
    assert len(calls) == 5


def test_at_most_two_passwords_are_verified_at_once(client, settings, monkeypatch):
    engine, lock, state = client.app.state.engine, threading.Lock(), {"now": 0, "peak": 0}

    class Slow:
        def verify_and_update(self, password, stored):
            with lock:
                state["now"] += 1
                state["peak"] = max(state["peak"], state["now"])
            time.sleep(.15)
            with lock:
                state["now"] -= 1
            return False, None

    monkeypatch.setattr(auth, "PASSWORDS", Slow())

    def attempt(i):
        with pytest.raises(store.Refused):
            auth.login(engine, IDENTIFIER, "wrong", f"198.51.100.{i}")

    threads = [threading.Thread(target=attempt, args=(i,)) for i in range(8)]
    [thread.start() for thread in threads]
    [thread.join(timeout=20) for thread in threads]
    assert state["peak"] == 2 and state["now"] == 0


def test_container_settings_reach_uvicorn_and_a_proxy_must_be_named_off_loopback(settings, env):
    assert uvicorn_options(settings)["host"] == "127.0.0.1" and uvicorn_options(settings)["forwarded_allow_ips"] == "127.0.0.1"
    env.setenv("API_HOST", "0.0.0.0")
    with pytest.raises(ConfigError, match="FORWARDED_ALLOW_IPS"):
        load_settings(env_file=None)
    env.setenv("FORWARDED_ALLOW_IPS", "10.0.0.0/8,172.16.0.0/12")
    options = uvicorn_options(load_settings(env_file=None))
    assert options["host"] == "0.0.0.0" and options["forwarded_allow_ips"] == "10.0.0.0/8,172.16.0.0/12"
    assert options["proxy_headers"] is True and options["access_log"] is False


def test_the_built_frontend_is_public_and_everything_under_api_stays_closed(settings, tmp_path, monkeypatch):
    build = tmp_path / "dist"
    (build / "assets").mkdir(parents=True)
    (build / "index.html").write_text("<!doctype html><title>Atelier</title>", encoding="utf-8")
    (build / "assets" / "app-abc123.js").write_text("console.log(1)", encoding="utf-8")
    monkeypatch.setattr(rendering, "BUILD_DIR", build)
    settings.serve_frontend = True
    app = create_app(settings)
    # No data route may live outside the boundary: every declared route is under /api/, only the mount is not.
    def paths(routes):
        for route in routes:
            included = getattr(route, "original_router", None)  # this FastAPI keeps an included router whole
            yield from paths(included.routes) if included is not None else [route.path]

    declared = list(paths(app.routes))
    assert len(declared) > 40 and [path for path in declared if not path.startswith("/api/")] == [""]
    with TestClient(app, base_url=ORIGIN, headers=HEADERS) as client:
        page = client.get("/")
        assert page.status_code == 200 and "Atelier" in page.text and page.headers["cache-control"] == "no-cache"
        script = client.get("/assets/app-abc123.js")
        assert script.status_code == 200 and script.headers["cache-control"] == "public, max-age=31536000, immutable"
        assert script.headers["x-content-type-options"] == "nosniff"
        missing = client.get("/assets/gone.js")
        assert missing.status_code == 404 and missing.json()["error"]["code"] == "not_found"
        assert missing.headers["cache-control"] == "no-cache"
        assert client.get("/../backend/pyproject.toml").status_code == 404
        for path in ("/api/shop-profile", "/api/creations", "/api/openapi.json", "/api/nothing"):
            closed = client.get(path)
            assert closed.status_code == 401 and closed.headers["cache-control"] == "no-store", path
        closed = client.get("/api/status")  # the operator's, from the machine only (D-MULTI-SHOP-004)
        assert closed.status_code == 404 and closed.headers["cache-control"] == "no-store"
        assert client.post("/", headers={"Origin": "https://evil.example"}).status_code == 403
        assert client.post("/").status_code in (404, 405)
        login(client)
        assert client.get("/api/shop-profile").status_code == 200


def test_the_data_page_is_served_without_a_session_and_revalidated(settings, tmp_path, monkeypatch):
    """D-TERMS-007: frontend/public/donnees.html, copied by Vite into dist, is public like the page itself: no session,
    no-cache. It holds no data and runs nothing, and loads nothing from another site."""
    source = Path(__file__).resolve().parents[2] / "frontend/public/donnees.html"
    build = tmp_path / "dist"
    build.mkdir()
    (build / "index.html").write_text("<!doctype html><title>Atelier</title>", encoding="utf-8")
    (build / "donnees.html").write_bytes(source.read_bytes())
    monkeypatch.setattr(rendering, "BUILD_DIR", build)
    settings.serve_frontend = True
    with TestClient(create_app(settings), base_url=ORIGIN, headers=HEADERS) as client:
        page = client.get("/donnees.html")
        assert page.status_code == 200 and page.headers["content-type"].startswith("text/html")
        assert page.headers["cache-control"] == "no-cache" and page.headers["x-content-type-options"] == "nosniff"
        assert "<h1>Vos données</h1>" in page.text and "Retour à l’atelier" in page.text
        assert "<script" not in page.text.lower() and not re.search(r"(https?:)?//[a-z]", page.text, re.I)
        assert "set-cookie" not in page.headers


def test_the_operators_page_is_served_at_admin_by_the_same_mount(settings, tmp_path, monkeypatch):
    """D-ADMIN-005: the second build pass writes dist/admin/; the one static mount serves it, public like the shops' page."""
    build = tmp_path / "dist"
    (build / "admin" / "assets").mkdir(parents=True)
    (build / "index.html").write_text("<!doctype html><title>Atelier</title>", encoding="utf-8")
    (build / "admin" / "index.html").write_text("<!doctype html><title>Doka Studio · Operator</title>", encoding="utf-8")
    (build / "admin" / "assets" / "index-abc123.js").write_text("console.log(2)", encoding="utf-8")
    monkeypatch.setattr(rendering, "BUILD_DIR", build)
    settings.serve_frontend = True
    with TestClient(create_app(settings), base_url=ORIGIN, headers=HEADERS) as client:
        page = client.get("/admin/")
        assert page.status_code == 200 and "Operator" in page.text and page.headers["cache-control"] == "no-cache"
        assert client.get("/admin/index.html").text == page.text
        # Without the slash Starlette's StaticFiles (html=True) redirects to it: a directory's address ends in "/".
        bare = client.get("/admin", follow_redirects=False)
        assert bare.status_code == 307 and bare.headers["location"] == f"{ORIGIN}/admin/"
        script = client.get("/admin/assets/index-abc123.js")
        assert script.status_code == 200 and script.text == "console.log(2)"
        assert "Atelier" in client.get("/").text  # the shops' page stays at /
        missing = client.get("/admin/assets/gone.js")
        assert missing.status_code == 404 and missing.json()["error"]["code"] == "not_found"


def test_login_limit_counts_an_ipv6_64_as_one_client(client, settings):
    engine = client.app.state.engine
    assert auth.limit_key("2001:db8:1:2:aaaa::1") == auth.limit_key("2001:db8:1:2:bbbb::9") == "2001:db8:1:2::"
    assert auth.limit_key("2001:db8:1:3::1") != auth.limit_key("2001:db8:1:2::1")
    assert auth.limit_key("::ffff:192.0.2.7") == auth.limit_key("192.0.2.7") == "192.0.2.7"
    assert auth.limit_key("unknown") == "unknown"
    for i in range(5):
        with pytest.raises(store.Refused, match="wrong_credentials"):
            auth.login(engine, IDENTIFIER, "wrong", f"2001:db8:1:2:{i}::1")
    with pytest.raises(store.Refused, match="rate_limited"):
        auth.login(engine, IDENTIFIER, PASSWORD, "2001:db8:1:2:ffff::1")
    assert auth.login(engine, IDENTIFIER, PASSWORD, "2001:db8:1:3::1")[1] == 1
    assert auth.login(engine, IDENTIFIER, PASSWORD, "192.0.2.8")[1] == 1


def second_shop(engine, identifier="Boutique Deux", name="Boutique Deux"):
    """Another shop, made as the operator makes one (D-MULTI-SHOP-003), with credits and the conditions accepted
    (credited); returns its id and its password."""
    password = os.urandom(12).hex()
    password_hash = auth.PASSWORDS.hash(password)  # Argon2 outside the transaction, as the operator's command does
    with write_tx(engine) as conn:
        shop = shops.create_shop(conn, identifier, name, password_hash)
    credited(engine, shop)
    return shop, password


def failures(engine):
    with engine.connect() as conn:
        return conn.exec_driver_sql("SELECT identifier FROM login_failures ORDER BY id").scalars().all()


class Counting:
    """The real Argon2, with the number of verifications."""
    def __init__(self, real):
        self.real, self.calls = real, 0

    def verify_and_update(self, password, stored):
        self.calls += 1
        return self.real.verify_and_update(password, stored)

    def verify(self, password, stored):  # the operator's sign-in (test_admin)
        self.calls += 1
        return self.real.verify(password, stored)

    def hash(self, password):  # a password change hashes the new one: not a verification
        return self.real.hash(password)


def test_an_unknown_shop_a_wrong_password_and_a_shop_without_one_get_one_answer_after_one_verification(client, monkeypatch):
    engine = client.app.state.engine
    _, other_password = second_shop(engine)
    bare, _ = second_shop(engine, "sans-mot-de-passe", None)
    with write_tx(engine) as conn:
        conn.exec_driver_sql("UPDATE shop_profile SET password_hash=NULL WHERE id=?", (bare,))
    monkeypatch.setattr(auth, "PASSWORDS", counting := Counting(auth.PASSWORDS))
    answers = set()
    tried = (("inconnue", PASSWORD), (IDENTIFIER, "wrong"), ("Sans mot de passe", PASSWORD),
             (IDENTIFIER, other_password), ("boutique deux", PASSWORD), ("- -", PASSWORD), ("x" * 40, PASSWORD))
    for identifier, password in tried:
        before = counting.calls
        answer = client.post("/api/session", json=credentials(password, identifier))
        assert counting.calls == before+1, identifier  # the same work, a dummy hash when there is nothing to verify
        body = answer.json()
        assert body.pop("request_id") == answer.headers["x-request-id"]
        answers.add((answer.status_code, repr(body), answer.headers.get("retry-after")))
        assert answer.headers.get("set-cookie") is None
    assert answers == {(401, repr({"error": {"code": "wrong_credentials", "message_fr": "Identifiant ou mot de passe incorrect.",
                                             "retryable": False}}), None)}
    # Recorded for an unknown identifier too, under the key it was looked up by: the limit behaves the same.
    assert failures(engine) == ["inconnue", IDENTIFIER, "sansmotdepasse", IDENTIFIER, "boutiquedeux", "", "x" * 40]
    for spelling in ("Original Phone", "ORIGINAL-PHONE", "Óriginal phöne"):
        before = counting.calls
        assert client.post("/api/session", json=credentials(PASSWORD, spelling)).json() == {"authenticated": True, "shop_id": 1}
        assert counting.calls == before+1


def test_each_shop_signs_in_with_its_own_identifier_and_a_device_holds_one_session(client):
    engine = client.app.state.engine
    other, other_password = second_shop(engine)
    assert client.post("/api/session", json=credentials(other_password)).status_code == 401  # B's password, A's identifier
    assert client.post("/api/session", json=credentials(PASSWORD, "boutique-deux")).status_code == 401
    login(client)
    mine = client.cookies.get(auth.COOKIE)
    assert client.get("/api/shop-profile").json()["name"] is None
    answer = client.post("/api/session", json=credentials(other_password, "Boutique Deux"))
    assert answer.json() == {"authenticated": True, "shop_id": other}
    assert client.get("/api/session").json() == {"authenticated": True, "shop_id": other}
    assert client.get("/api/shop-profile").json()["name"] == "Boutique Deux"
    # Shop B signing in on shop A's device ends A's session there.
    assert client.get("/api/session", headers={"Cookie": f"{auth.COOKIE}={mine}"}).json() == {"authenticated": False}
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT shop_id FROM sessions").scalars().all() == [other]


def test_wrong_attempts_are_limited_per_identifier_from_an_address_and_more_loosely_per_address(client):
    engine = client.app.state.engine
    other, other_password = second_shop(engine)
    for spelling in ("originalphone", "Original Phone", "ORIGINAL-PHONE", "original.phone", "Originalphone"):
        with pytest.raises(store.Refused, match="wrong_credentials"):
            auth.login(engine, spelling, "wrong", "192.0.2.1")
    with pytest.raises(store.Refused, match="rate_limited"):  # even the right password, without verifying it
        auth.login(engine, IDENTIFIER, PASSWORD, "192.0.2.1")
    # One owner's mistakes lock only his shop from that address.
    assert auth.login(engine, "boutique-deux", other_password, "192.0.2.1")[1] == other
    assert auth.login(engine, IDENTIFIER, PASSWORD, "192.0.2.2")[1] == 1
    for i in range(auth.ADDRESS_LIMIT-auth.PAIR_LIMIT):  # many identifiers guessed from one place
        with pytest.raises(store.Refused, match="wrong_credentials"):
            auth.login(engine, f"inconnue{i}", "wrong", "192.0.2.1")
    with pytest.raises(store.Refused, match="rate_limited"):
        auth.login(engine, "boutique-deux", other_password, "192.0.2.1")
    assert auth.login(engine, "boutique-deux", other_password, "192.0.2.2")[1] == other
    assert len(failures(engine)) == auth.ADDRESS_LIMIT


def slow_wrong(monkeypatch, seconds):
    calls = []

    class Slow:
        def verify_and_update(self, password, stored):
            calls.append(password)
            time.sleep(seconds)
            return False, None

        def verify(self, password, stored):  # the operator's sign-in (test_admin)
            return self.verify_and_update(password, stored)[0]

    monkeypatch.setattr(auth, "PASSWORDS", Slow())
    return calls


def burst(engine, count):
    outcomes, lock = [], threading.Lock()

    def attempt():
        try:
            auth.login(engine, IDENTIFIER, "wrong", "198.51.100.7")
        except store.Refused as refused:
            with lock:
                outcomes.append(refused.code)

    threads = [threading.Thread(target=attempt) for _ in range(count)]
    [thread.start() for thread in threads]
    [thread.join(timeout=30) for thread in threads]
    return sorted(outcomes)


def at_most_one_past_the_limit(engine, calls, outcomes):
    recorded = len(failures(engine))
    assert auth.PAIR_LIMIT <= recorded <= auth.PAIR_LIMIT+1 and len(calls) == recorded, (recorded, len(calls))
    assert outcomes == sorted(["rate_limited"] * (10-recorded) + ["wrong_credentials"] * recorded)


def test_a_burst_of_wrong_attempts_records_at_most_one_failure_past_the_limit(client, monkeypatch):
    calls = slow_wrong(monkeypatch, .15)
    outcomes = burst(client.app.state.engine, 10)
    at_most_one_past_the_limit(client.app.state.engine, calls, outcomes)


def test_while_another_writer_holds_the_database_the_slots_wait_with_their_failures(client, settings, monkeypatch):
    """The slot is held until the failure is committed: requests queued behind it count it, they never verify
    beside a failure that waits for SQLite's lock (round 2, finding 3)."""
    engine, calls = client.app.state.engine, slow_wrong(monkeypatch, .1)
    writer, locked, seen = make_engine(settings.data_dir), threading.Event(), {}

    def hold():
        with write_tx(writer) as conn:
            conn.exec_driver_sql("INSERT INTO meta (key,value) VALUES ('writer','1')")
            locked.set()
            time.sleep(2)  # under the 5 s busy_timeout
            seen["verified"] = len(calls)

    holder = threading.Thread(target=hold)
    holder.start()
    try:
        assert locked.wait(5)
        outcomes = burst(engine, 10)
    finally:
        holder.join(timeout=10)
        writer.dispose()
    assert seen["verified"] == 2  # the two slots, waiting for the writer with their failures
    at_most_one_past_the_limit(engine, calls, outcomes)


def test_an_adopted_hash_with_other_parameters_is_upgraded_at_its_first_sign_in(settings):
    older = PasswordHash((Argon2Hasher(time_cost=1, memory_cost=8192, parallelism=1),)).hash(PASSWORD)
    settings.shop_password_hash = SecretStr(older)
    with TestClient(create_app(settings), base_url=ORIGIN, headers=HEADERS) as client:
        assert stored_password(client.app) == older
        login(client)
        upgraded = stored_password(client.app)
        assert upgraded != older and not auth.PASSWORDS.current_hasher.check_needs_rehash(upgraded)
        assert auth.PASSWORDS.verify(PASSWORD, upgraded)
        login(client)
        assert stored_password(client.app) == upgraded


def test_a_suspended_shop_does_not_sign_in_and_its_sessions_wait_until_it_is_enabled(client, monkeypatch):
    engine = client.app.state.engine

    def state(value):
        with write_tx(engine) as conn:
            conn.exec_driver_sql("UPDATE shop_profile SET state=? WHERE id=1", (value,))

    login(client)
    state("suspended")
    assert client.get("/api/session").json() == {"authenticated": False}
    assert client.get("/api/shop-profile").status_code == 401
    monkeypatch.setattr(auth, "PASSWORDS", counting := Counting(auth.PASSWORDS))
    right = client.post("/api/session", json=credentials())
    assert right.status_code == 403 and right.json()["error"]["message_fr"] == "Cette boutique est suspendue. Contactez l’administrateur."
    wrong = client.post("/api/session", json=credentials("wrong"))
    assert wrong.status_code == 401 and wrong.json()["error"]["code"] == "wrong_credentials"  # told only to the right password
    assert counting.calls == 2 and failures(engine) == [IDENTIFIER]
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT count(*) FROM sessions").scalar_one() == 1  # kept, not usable
    state("active")
    assert client.get("/api/session").json() == {"authenticated": True, "shop_id": 1}


@pytest.mark.parametrize("change", ["password", "suspension"])
def test_a_change_committed_during_the_verification_gives_no_session(client, monkeypatch, password_hash, change):
    """The stored hash and the state are read again in the transaction that would create the session
    (T-MULTI-SHOP-001 review, P3): a reset by the operator, or by the owner elsewhere, wins over a sign-in in flight."""
    engine, real = client.app.state.engine, auth.PASSWORDS
    newer = real.hash(os.urandom(12).hex())

    class Racing:
        def verify_and_update(self, password, stored):
            verified = real.verify_and_update(password, stored)
            with write_tx(engine) as conn:
                if change == "password":
                    shops.set_password(conn, 1, newer)
                else:
                    conn.exec_driver_sql("UPDATE shop_profile SET state='suspended' WHERE id=1")
            return verified

    monkeypatch.setattr(auth, "PASSWORDS", Racing())
    answer = client.post("/api/session", json=credentials())
    assert (answer.status_code, answer.json()["error"]["code"]) == (
        (401, "wrong_credentials") if change == "password" else (403, "shop_suspended"))
    assert failures(engine) == ([IDENTIFIER] if change == "password" else [])
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT count(*) FROM sessions").scalar_one() == 0
    assert stored_password(client.app) == (newer if change == "password" else password_hash)


def test_every_session_answer_says_whom_to_contact_only_when_it_is_set(settings, env):
    for contact in (None, "l’administrateur au 034 00 000 00"):
        settings.support_contact_fr = contact
        support = {"support_fr": contact} if contact else {}
        with TestClient(create_app(settings), base_url=ORIGIN, headers=HEADERS) as client:
            assert client.get("/api/session").json() == {"authenticated": False} | support
            login(client)
            # Signed in too: another tab of the device shows the form while this shop is signed in.
            assert client.get("/api/session").json() == {"authenticated": True, "shop_id": 1} | support
    env.setenv("SUPPORT_CONTACT_FR", "x" * 201)
    with pytest.raises(ConfigError, match="support_contact_fr"):
        load_settings(env_file=None)


def stored_password(app):
    with app.state.engine.connect() as conn:
        return conn.exec_driver_sql("SELECT password_hash FROM shop_profile WHERE id=1").scalar_one()


def at_0012(settings, monkeypatch, fingerprint=None, product=False):
    """A data folder as the version before 0013 left it, with one session of the pilot's phone; returns its cookie."""
    engine = make_engine(settings.data_dir)
    try:
        migrate_to(engine, "0012", monkeypatch)
        with write_tx(engine) as conn:
            conn.exec_driver_sql("INSERT INTO sessions VALUES (?,1,'2099-01-01T00:00:00.000000+00:00')",
                                 (auth.token_hash("pilot-phone"),))
            if fingerprint:
                conn.exec_driver_sql("INSERT INTO meta VALUES ('password_fingerprint',?)", (fingerprint,))
            if product:
                conn.exec_driver_sql("INSERT INTO product_inputs VALUES ('in1',1,'P1','JBL','Bleu','[]','{}',NULL,'t')")
    finally:
        engine.dispose()
    return {"Cookie": f"{auth.COOKIE}=pilot-phone"}


@pytest.mark.parametrize("last_seen, kept", [("this", True), ("another", False), (None, False)])
def test_the_first_start_after_0013_adopts_the_setting_with_the_rule_of_before(settings, monkeypatch, password_hash,
                                                                              last_seen, kept):
    fingerprints = {"this": hashlib.sha256(password_hash.encode()).hexdigest(), "another": "0" * 64, None: None}
    cookie = at_0012(settings, monkeypatch, fingerprints[last_seen])
    with TestClient(create_app(settings), base_url=ORIGIN, headers=HEADERS) as client:
        # The pilot's phone stays signed in across the release unless the password changed while the old version ran.
        assert client.get("/api/session", headers=cookie).json()["authenticated"] is kept
        assert stored_password(client.app) == password_hash
        with client.app.state.engine.connect() as conn:
            assert conn.exec_driver_sql("SELECT count(*) FROM meta WHERE key='password_fingerprint'").scalar_one() == 0
        login(client)  # the same password, now read from shop 1's row


def test_after_adoption_the_setting_is_not_read_again(settings, password_hash, caplog):
    with TestClient(create_app(settings), base_url=ORIGIN, headers=HEADERS) as first:  # a new installation, given it
        login(first)
        token = first.cookies.get(auth.COOKIE)
        with first.app.state.engine.connect() as conn:
            expires = datetime.fromisoformat(conn.exec_driver_sql("SELECT expires_at FROM sessions").scalar_one())
        assert timedelta(days=90)-timedelta(minutes=1) < expires-datetime.now(UTC) <= timedelta(days=90)
    assert "no longer read" not in caplog.text
    cookie = {"Cookie": f"{auth.COOKIE}={token}"}
    with TestClient(create_app(settings), base_url=ORIGIN, headers=HEADERS) as same:  # a restart, the setting kept
        assert same.get("/api/session", headers=cookie).json()["authenticated"]
    assert "SHOP_PASSWORD_HASH is no longer read" in caplog.text
    caplog.clear()
    # Stale by design after an operator's reset: a warning, never a revocation nor a refusal to start.
    newer = os.urandom(12).hex()
    settings.shop_password_hash = SecretStr(auth.PASSWORDS.hash(newer))
    with TestClient(create_app(settings), base_url=ORIGIN, headers=HEADERS) as changed:
        assert changed.get("/api/session", headers=cookie).json()["authenticated"]
        assert stored_password(changed.app) == password_hash
        assert changed.post("/api/session", json=credentials(newer)).status_code == 401
        login(changed)
    assert "SHOP_PASSWORD_HASH is no longer read" in caplog.text
    caplog.clear()
    settings.shop_password_hash = None
    with TestClient(create_app(settings), base_url=ORIGIN, headers=HEADERS) as removed:
        assert removed.get("/api/session", headers=cookie).json()["authenticated"]
        login(removed)
    assert "SHOP_PASSWORD_HASH" not in caplog.text


@pytest.mark.parametrize("evidence", [{"fingerprint": "0" * 64}, {"product": True}])
def test_an_upgraded_pilot_with_no_password_anywhere_refuses_to_start(settings, monkeypatch, evidence):
    at_0012(settings, monkeypatch, **evidence)
    settings.shop_password_hash = None
    with pytest.raises(ConfigError, match="Shop 1 has data but no password and SHOP_PASSWORD_HASH is not set"), \
            TestClient(create_app(settings)):
        pass
    with sqlite3.connect(settings.data_dir / "affiche.db") as conn:  # migrated, nothing else: fixed forward
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone() == ("0017",)
        assert conn.execute("SELECT password_hash FROM shop_profile").fetchall() == [(None,)]
        assert conn.execute("SELECT count(*) FROM sessions").fetchone() == (1,)


def test_a_new_installation_without_the_setting_starts_and_waits_for_set_password(settings, password_hash, caplog):
    settings.shop_password_hash = None
    with TestClient(create_app(settings), base_url=ORIGIN, headers=HEADERS) as client:
        assert "shop 1 has no password: python -m affiche.shops set-password originalphone" in caplog.text
        assert client.post("/api/session", json=credentials(PASSWORD)).status_code == 401
        engine = client.app.state.engine
        with write_tx(engine) as conn:
            shops.set_password(conn, 1, password_hash)
        login(client)
        mine, reset = client.cookies.get(auth.COOKIE), os.urandom(12).hex()
        with write_tx(engine) as conn:  # the operator's reset ends that shop's sessions
            shops.set_password(conn, 1, auth.PASSWORDS.hash(reset))
            with pytest.raises(LookupError):
                shops.set_password(conn, 2, password_hash)
        assert not client.get("/api/session", headers={"Cookie": f"{auth.COOKIE}={mine}"}).json()["authenticated"]
        assert client.post("/api/session", json=credentials(reset)).status_code == 200
        with write_tx(engine) as conn:
            assert shops.end_sessions(conn) == 1 and shops.end_sessions(conn, 1) == 0


@pytest.mark.parametrize("origin", [None, "http://shop.example", "https://user@shop.example", "https://shop.example/", "https://shop.example?x=1"])
def test_bad_origin_refuses_startup(settings, origin):
    settings.app_origin = origin
    with pytest.raises(ConfigError, match="APP_ORIGIN"), TestClient(create_app(settings)):
        pass


@pytest.mark.parametrize("secret", ["plaintext-secret", "$argon2id$invalid"])
def test_bad_hash_refuses_startup_without_leaking(settings, secret):
    settings.shop_password_hash = SecretStr(secret)
    with pytest.raises(ConfigError, match="SHOP_PASSWORD_HASH") as error, TestClient(create_app(settings)):
        pass
    assert secret not in str(error.value)


def test_local_http_cookie_and_server_restart(settings):
    settings.app_origin = "http://localhost:5173"
    with TestClient(create_app(settings), base_url=settings.app_origin, headers={**HEADERS, "Origin": settings.app_origin}) as first:
        response = login(first)
        assert "; Secure" not in response.headers["set-cookie"]
        token = first.cookies.get(auth.COOKIE)
        for _ in range(5):
            first.post("/api/session", json=credentials("wrong"))
    with TestClient(create_app(settings), base_url=settings.app_origin, headers={**HEADERS, "Origin": settings.app_origin}) as second:
        assert second.get("/api/session", headers={"Cookie": f"{auth.COOKIE}={token}"}).json()["authenticated"]
        assert second.post("/api/session", json=credentials(PASSWORD)).status_code == 429


def test_validation_never_echoes_password(client):
    response = client.post("/api/session", json=credentials() | {"unexpected": "private"})
    assert response.status_code == 422
    assert PASSWORD not in response.text and "private" not in response.text
    assert response.json()["request_id"] == response.headers["x-request-id"]


def test_http_draft_roundtrip_replay_conflict_history_and_copy(client):
    login(client)
    first = create_draft(client)
    id, document = first["id"], first["document"]
    assert client.get(f"/api/creations/{id}").headers["etag"] == '"1"'
    document["offer"]["price_ar"] = 799000
    path = f"/api/creations/{id}"
    headers = {"Idempotency-Key": str(uuid4()), "If-Match": '"1"'}
    saved = client.put(path, json=document, headers=headers)
    assert saved.status_code == 200, saved.text
    assert saved.json()["revision"] == 2 and saved.headers["etag"] == '"2"'
    assert client.put(path, json=document, headers=headers).json() == saved.json()
    headers["Idempotency-Key"] = str(uuid4())
    assert client.put(path, json=document, headers=headers).status_code == 409
    assert client.put(path, json=document, headers={"Idempotency-Key": str(uuid4())}).status_code == 428
    assert client.get(path+"/versions/1").json()["document"]["offer"]["price_ar"] == 899000
    assert [r["revision"] for r in client.get(path+"/versions").json()["items"]] == [2, 1]
    copied = post(client, path+"/copies", {"source_revision": 2, "reason": "price_update"})
    assert copied.status_code == 201 and copied.json()["parent_creation_id"] == id
    assert copied.json()["document"] == saved.json()["document"]
    listed = client.get("/api/creations?limit=1").json()
    assert len(listed["items"]) == 1 and listed["items"][0]["name"] == "JBL"
    assert isinstance(listed["items"][0]["price_ar"], int) and listed["items"][0]["title"]
    assert listed["items"][0]["thumbnail_url"] is None  # no scene and no final preview yet: nothing is invented
    unknown = client.get("/api/thumbnails/" + "0" * 64)
    assert unknown.status_code == 404 and unknown.headers["cache-control"] == "no-store"  # not a preview or scene of this shop
    next_page = client.get("/api/creations", params={"limit": 1, "before": listed["next_cursor"]}).json()
    assert next_page["items"][0]["id"] != listed["items"][0]["id"]
    with client.app.state.engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT count(*) FROM provider_calls").scalar_one() == 0


def test_profile_revision_and_role_access(client):
    login(client)
    original = client.post("/api/assets", files={"file": ("pic.png", photo())}, data={"role": "original"}).json()
    body = {"name": "Boutique", "contact": "034 00 000 00", "logo_asset": original["asset"]}
    headers = {"Idempotency-Key": str(uuid4()), "If-Match": '"1"'}
    assert client.put("/api/shop-profile", json=body, headers=headers).status_code == 422
    client.post("/api/assets", files={"file": ("pic.png", photo())}, data={"role": "logo"})
    response = client.put("/api/shop-profile", json=body, headers=headers)
    assert response.status_code == 200 and response.json()["revision"] == 2
    assert client.put("/api/shop-profile", json=body, headers=headers).json() == response.json()


def test_private_assets_and_corruption(client, settings):
    login(client)
    sha = assets.put(settings.data_dir, photo(), "png")
    with write_tx(client.app.state.engine) as conn:
        assets.record(conn, sha=sha, kind="original", mime="image/png", width=40, height=80, size=len(photo()))
    assert client.get(f"/api/assets/{sha}").status_code == 404  # knowing an existing hash grants no access
    client.post("/api/assets", files={"file": ("photo.png", photo())}, data={"role": "original"})
    response = client.get(f"/api/assets/{sha}")
    assert response.content == photo() and response.headers["x-content-type-options"] == "nosniff"
    # Its address is its content (ADR-087): kept by this browser only; access is still checked on each request.
    assert response.headers["cache-control"] == "private, max-age=31536000, immutable"
    assets.path(settings.data_dir, sha, "png").write_bytes(b"corrupt")
    corrupt = client.get(f"/api/assets/{sha}")
    assert corrupt.status_code == 409 and corrupt.headers["cache-control"] == "no-store"
    assets.path(settings.data_dir, sha, "png").unlink()
    missing = client.get(f"/api/assets/{sha}")
    assert missing.status_code == 404 and missing.headers["cache-control"] == "no-store"
    assert client.get("/api/creations").headers["cache-control"] == "no-store"  # JSON is never kept


def test_display_copy_is_a_jpeg_of_opaque_images_encoded_once_with_fallback(client, settings, monkeypatch, caplog):
    """D-POSTER-EDITOR-007 6c: the editor's lighter copy; the prepared PNG and the original stay as they were."""
    login(client)
    noisy = io.BytesIO()  # like a photographed scene: a flat test image is smaller as PNG and would stay PNG
    Image.merge("RGB", [Image.effect_noise((40, 80), 40)] * 3).save(noisy, "PNG")
    opaque = client.post("/api/assets", files={"file": ("photo.png", noisy.getvalue())}, data={"role": "original"}).json()["asset"]
    see_through = io.BytesIO()
    image = Image.new("RGBA", (40, 80), "navy")
    image.putpixel((0, 0), (0, 0, 0, 0))
    image.save(see_through, "PNG")
    logo = client.post("/api/assets", files={"file": ("logo.png", see_through.getvalue())}, data={"role": "logo"}).json()["asset"]
    encoded = []
    real = affiche_api.rendering.canvas_image
    monkeypatch.setattr(affiche_api.rendering, "canvas_image", lambda data: encoded.append(1) or real(data))
    immutable = "private, max-age=31536000, immutable"
    prepared = client.get(f"/api/assets/{opaque}?prepared=true&v=1")
    assert prepared.headers["content-type"] == "image/png" and prepared.headers["cache-control"] == immutable
    encoded.clear()
    first = client.get(f"/api/assets/{opaque}?prepared=true&display=true&v=1")
    assert first.headers["content-type"] == "image/jpeg" and first.headers["cache-control"] == immutable
    assert Image.open(io.BytesIO(first.content)).size == (40, 80) and len(encoded) == 1
    assert (settings.data_dir / "display" / "v1" / opaque[:2] / f"{opaque}.jpeg").read_bytes() == first.content
    second = client.get(f"/api/assets/{opaque}?prepared=true&display=true&v=1")
    assert second.content == first.content and len(encoded) == 1  # kept on disk: not encoded again
    # Another encoder version: the current encoding, never kept (a later change of encoding must reach the browser).
    for other in ("?prepared=true", "?prepared=true&v=0", "?prepared=true&display=true&v=0"):
        assert client.get(f"/api/assets/{opaque}{other}").headers["cache-control"] == "no-store", other
    kept = client.get(f"/api/assets/{logo}?prepared=true&display=true&v=1")
    assert kept.headers["content-type"] == "image/png" and Image.open(io.BytesIO(kept.content)).getpixel((0, 0))[3] == 0
    # The copy cannot be made: the prepared PNG is sent, and the next request tries again.
    fresh = client.post("/api/assets", files={"file": ("other.png", photo(colour="teal"))}, data={"role": "original"}).json()["asset"]
    real_copy = affiche_api._display_copy
    monkeypatch.setattr(affiche_api, "_display_copy", lambda png: (_ for _ in ()).throw(OSError("disk")))
    fallback = client.get(f"/api/assets/{fresh}?prepared=true&display=true&v=1")
    assert fallback.status_code == 200 and fallback.headers["content-type"] == "image/png"
    assert not list((settings.data_dir / "display").rglob(f"{fresh}.*"))
    # The copy cannot be kept (its folder is a file): it is still sent, the failure is logged, nothing is left behind.
    monkeypatch.setattr(affiche_api, "_display_copy", real_copy)
    other = io.BytesIO()
    Image.merge("RGB", [Image.effect_noise((40, 80), 50)] * 3).save(other, "PNG")
    unkept = client.post("/api/assets", files={"file": ("noisy.png", other.getvalue())}, data={"role": "original"}).json()["asset"]
    (settings.data_dir / "display" / "v1" / unkept[:2]).write_bytes(b"not a folder")
    caplog.clear()
    sent = client.get(f"/api/assets/{unkept}?prepared=true&display=true&v=1")
    assert sent.status_code == 200 and sent.headers["content-type"] == "image/jpeg"
    assert any("could not be kept" in record.getMessage() for record in caplog.records)


def test_abandon_readonly_can_copy_and_replay_prior_save(client):
    login(client)
    first = create_draft(client)
    path = f'/api/creations/{first["id"]}'
    headers = {"Idempotency-Key": str(uuid4()), "If-Match": '"1"'}
    abandoned = client.post(path+"/abandon", headers=headers)
    assert abandoned.status_code == 200 and abandoned.json()["status"] == "abandoned"
    assert client.post(path+"/abandon", headers=headers).json() == abandoned.json()
    headers["Idempotency-Key"] = str(uuid4())
    assert client.put(path, json=first["document"], headers=headers).status_code == 409
    assert post(client, path+"/copies", {"source_revision": 1, "reason": "new_campaign"}).json()["status"] == "active"


def test_list_states_removed_view_restore_and_stale_copy(client, settings):
    # The scene, review and export helpers live in modules that import this one: import them late.
    from affiche.posters import exports, visuals
    from affiche.posters.models import Document
    from test_exports import confirm_request, render
    from test_poster_visuals import execute, fixed, scene
    login(client)
    engine = client.app.state.engine
    poster = create_draft(client)
    path = f'/api/creations/{poster["id"]}'

    def listed(status="active"):
        return client.get("/api/creations", params={"status": status}).json()

    def state():
        return {item["id"]: item["state"] for item in listed()["items"]}[poster["id"]]

    def current():
        return client.get(path).json()

    def act(action, revision):
        return client.post(f"{path}/{action}", headers={"Idempotency-Key": str(uuid4()), "If-Match": f'"{revision}"'})

    assert state() == "draft" and listed()["total"] == 1
    scene(engine, settings, poster, fixed(engine, settings, poster))
    first = execute(engine, settings)
    assert state() == "to_review"
    visuals.decide(engine, 1, str(uuid4()), first, visuals.Decision(action="approve", checks={check: True for check in visuals.CHECKS | visuals.TEXT_CHECKS}))
    assert state() == "approved"
    approved = current()
    preview = render(engine, settings, approved)
    exports.confirm(engine, settings, 1, str(uuid4()), poster["id"], approved["revision"], confirm_request(preview))
    assert state() == "confirmed"
    # Edited after the confirmation: the confirmed file is no longer the poster as it is now (ADR-061).
    document = Document.model_validate(approved["document"])
    document.offer.price_ar += 1000
    edited = store.save_creation(engine, settings.data_dir, 1, str(uuid4()), poster["id"], document, approved["revision"])[1]
    assert state() == "approved"
    # A second version waits for the review without being the one the document shows.
    scene(engine, settings, edited, fixed(engine, settings, edited))
    second = execute(engine, settings)
    assert current()["document"]["formats"]["feed"]["scene"]["visual_id"] == first != second
    assert state() == "to_review"

    with engine.connect() as conn:
        calls = conn.exec_driver_sql("SELECT count(*) FROM poster_calls").scalar_one()
    # A copy asked from a stale row is refused; from the current revision it is made.
    stale =post(client, path+"/copies", {"source_revision": 1, "reason": "new_campaign"})
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "revision_conflict"
    copied = post(client, path+"/copies", {"source_revision": current()["revision"], "reason": "new_campaign"})
    assert copied.status_code == 201 and listed()["total"] == 2
    # The copy shows the approved first version; the waiting one was made in the source and is not the copy's.
    assert {item["id"]: item["state"] for item in listed()["items"]}[copied.json()["id"]] == "approved"

    revision = current()["revision"]
    assert act("abandon", revision-1).status_code == 409
    assert act("abandon", revision).json()["status"] == "abandoned"
    assert poster["id"] not in [item["id"] for item in listed()["items"]] and listed()["total"] == 1
    removed = listed("abandoned")
    assert [item["id"] for item in removed["items"]] == [poster["id"]] and removed["total"] == 1
    assert act("abandon", revision).status_code == 200  # a new key: removing twice is not an error
    assert act("restore", revision).json()["status"] == "active"
    assert act("restore", revision).json()["status"] == "active"
    assert listed()["total"] == 2 and listed("abandoned")["items"] == []
    assert client.get("/api/creations", params={"status": "deleted"}).status_code == 422
    with engine.connect() as conn:
        # Copying, removing and restoring never reach a provider.
        assert conn.exec_driver_sql("SELECT count(*) FROM poster_calls").scalar_one() == calls


def test_storage_error_is_safe_and_no_partial_creation(client, monkeypatch, caplog):
    login(client)
    def fail(*args, **kwargs):
        raise OSError("sensitive local path and private details")
    monkeypatch.setattr(store, "upload", fail)
    response = client.post("/api/assets", files={"file": ("image.png", photo())}, data={"role": "original"})
    assert response.status_code == 503 and response.json()["error"]["retryable"]
    assert "sensitive" not in response.text + caplog.text


def test_body_limits_and_auth_before_upload(client):
    assert client.post("/api/assets", content=b"x" * 200000).status_code == 401
    login(client)
    response = client.post("/api/product-inputs", content=iter([b"x" * 70000, b"x" * 70000]),
                           headers={"Content-Type": "application/json", "Idempotency-Key": str(uuid4())})
    assert response.status_code == 413, response.text
    assert client.post("/api/assets", content=b"", headers={"Content-Length": str(store.MAX_UPLOAD_BYTES+65537)}).status_code == 413


def test_openapi_describes_strict_documents_and_is_private(client):
    assert client.get("/api/openapi.json").status_code == 401
    login(client)
    spec = client.get("/api/openapi.json").json()
    assert spec["components"]["schemas"]["Offer"]["properties"]["price_ar"]["type"] == "integer"
    assert spec["components"]["schemas"]["Document"]["additionalProperties"] is False
    assert spec["components"]["securitySchemes"]["APIKeyCookie"]["in"] == "cookie"
    assert spec["paths"]["/api/session"]["post"]["security"] == []
    assert spec["paths"]["/api/assets"]["post"]["requestBody"]["content"]["multipart/form-data"]


def test_actual_uvicorn_http_session(settings, env):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    env.setenv("APP_ORIGIN", origin)
    code = ("import uvicorn; from affiche.api import UVICORN, create_app; from affiche.config import load_settings; "
            f"uvicorn.run(create_app(load_settings(env_file=None)), **{{**UVICORN, 'port': {port}, 'log_level': 'warning'}})")
    proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    try:
        with httpx2.Client(base_url=origin, headers={**HEADERS, "Origin": origin}, timeout=2, trust_env=False) as remote:
            deadline = time.monotonic()+20
            while True:
                assert proc.poll() is None, "HTTP server exited before startup"
                try:
                    state = remote.get("/api/session")
                    break
                except (httpx2.ConnectError, httpx2.ConnectTimeout):
                    if time.monotonic() >= deadline:
                        raise AssertionError("HTTP server startup timed out") from None
                    time.sleep(0.1)
            assert state.json() == {"authenticated": False}
            assert remote.get("/api/shop-profile").status_code == 401
            # /api/status (D-MULTI-SHOP-004): the forwarded client and the Host each refuse it; the plain local call is answered.
            assert remote.get("/api/status", headers={"X-Forwarded-For": "203.0.113.9"}).status_code == 404
            assert remote.get("/api/status", headers={"X-Forwarded-For": "127.0.0.1",
                                                      "Host": "affiches.miorantsoa.app"}).status_code == 404
            assert remote.get("/api/status").json()["commit"] == "dev"
            assert remote.post("/api/session", json=credentials(PASSWORD)).status_code == 200
            assert remote.get("/api/shop-profile").json()["revision"] == 1
            assert remote.delete("/api/session").status_code == 200
            assert remote.get("/api/shop-profile").status_code == 401
            # The front process on loopback is believed: the failure is counted for the phone, not for the proxy.
            assert remote.post("/api/session", json=credentials("wrong"),
                               headers={"X-Forwarded-For": "198.51.100.7, 203.0.113.9"}).status_code == 401
    finally:
        proc.kill()
        proc.communicate(timeout=10)
    with sqlite3.connect(settings.data_dir / "affiche.db") as conn:
        assert conn.execute("SELECT ip FROM login_failures").fetchall() == [("203.0.113.9",)]


def test_the_frontend_builds_image_addresses_at_the_encoders_versions():
    """A version bumped on one side only would keep old images a year (ADR-087), or never keep new ones."""
    source = (Path(__file__).resolve().parents[2] / "frontend/src/api.ts").read_text(encoding="utf-8")
    assert (f"{{ prepared: '{rendering.CANVAS_IMAGE_VERSION}', display: '{affiche_api.DISPLAY_VERSION}', "
            f"thumbnail: '{affiche_api.THUMBNAIL_VERSION}' }}") in source
