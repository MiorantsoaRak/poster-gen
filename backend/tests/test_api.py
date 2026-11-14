import hashlib
import re
from datetime import UTC, datetime, timedelta
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
from pydantic import SecretStr

from affiche import api as affiche_api, assets, backup
from affiche.api import create_app, uvicorn_options
from affiche.config import ConfigError, load_settings
from affiche.db import write_tx
from affiche.posters import auth, jobs, rendering, store
from test_config import env  # noqa: F401
from test_poster_drafts import photo

ORIGIN = "https://shop.example"
PASSWORD = os.urandom(12).hex()  # a throwaway credential per test process; nothing is written literally


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
    with TestClient(create_app(settings), base_url=ORIGIN, headers={"Origin": ORIGIN}) as client:
        yield client


def login(client):
    response = client.post("/api/session", json={"password": PASSWORD})
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


def test_owned_job_status_usage_and_cancel(client, settings):
    assert client.get("/api/usage").status_code == 401
    assert client.get("/api/capabilities").status_code == 401
    login(client)
    creation = create_draft(client)
    with write_tx(client.app.state.engine) as conn:
        result = jobs.enqueue(conn, settings, 1, creation["id"], 1, "render", {"prompt": "private prompt"})
    response = client.get(result["status_url"])
    assert response.status_code == 200 and response.json()["status"] == "queued"
    assert "private prompt" not in response.text
    assert client.get(f"/api/creations/{creation['id']}/jobs").json()["items"] == [response.json()]
    assert client.get(f"/api/creations/{uuid4()}/jobs").status_code == 404
    assert client.get("/api/capabilities").json() == {"image_mode": "stub", "planner_mode": "disabled",
        "planner_available": False, "scene_estimate_micros": 0, "plan_estimate_micros": 100000, "texture_estimate_micros": 0,
        "formats_enabled": ["feed"]}
    assert client.get("/api/jobs/" + str(uuid4())).status_code == 404
    usage = client.get("/api/usage").json()
    assert usage["recorded_micros"] == 0 and usage["cap_micros"] == 20000000
    assert post(client, result["status_url"] + "/cancel", {}).json()["status"] == "cancelled"
    assert post(client, result["status_url"] + "/cancel", {}).status_code == 409


def test_status_tells_the_administrator_what_runs_and_how_old_the_backup_is(client, settings, tmp_path, monkeypatch):
    assert client.get("/api/status").status_code == 401
    login(client)
    status = client.get("/api/status").json()
    assert status["commit"] == "dev" and status["migration"] and status["backup"] is None
    assert status["spend"] == {"recorded_micros": 0, "cap_micros": 20000000, "since": settings.spend_cap_since.isoformat()}
    assert status["failed_jobs_24h"] == 0 and datetime.fromisoformat(status["started_at"]) <= datetime.now(UTC)

    settings.backup_dir = tmp_path / "backups"
    assert client.get("/api/status").json()["backup"] is None  # no marker yet: not an error
    backup.run(settings.data_dir, settings.backup_dir)
    monkeypatch.setenv("REVISION", "abc123")
    creation = create_draft(client)
    with write_tx(client.app.state.engine) as conn:
        for finished, state in ((datetime.now(UTC), "failed"), (datetime.now(UTC)-timedelta(hours=30), "failed"),
                                (datetime.now(UTC), "interrupted"), (datetime.now(UTC), "succeeded")):
            job = jobs.enqueue(conn, settings, 1, creation["id"], 1, "render", {"n": str(uuid4())})
            conn.exec_driver_sql("UPDATE poster_jobs SET status=?, finished_at=? WHERE id=?",
                                 (state, finished.isoformat(timespec="microseconds"), job["status_url"].rsplit("/", 1)[1]))
    status = client.get("/api/status").json()
    assert status["commit"] == "abc123" and status["failed_jobs_24h"] == 2
    assert status["backup"]["late"] is False and status["backup"]["age_hours"] == 0.0

    marker = settings.backup_dir / "last-backup.json"
    old = (datetime.now(UTC)-timedelta(hours=49)).isoformat(timespec="seconds")
    marker.write_text('{"finished_at": "%s"}' % old, encoding="utf-8")
    assert client.get("/api/status").json()["backup"] == {"finished_at": old, "age_hours": 49.0, "late": True}
    marker.write_text("not json", encoding="utf-8")
    assert client.get("/api/status").json()["backup"] is None


# Refusals that only a programming error in the editor can produce: the owner cannot cause them by what he types
# or taps. Each of them answers with the fallback sentence, which carries the code for the administrator.
DEVELOPER_ONLY = {"call_already_dispatched", "format_missing", "generated_reference_unavailable", "input_immutable",
                  "invalid_cursor", "invalid_idempotency_key", "invalid_job_state", "invalid_revision", "invalid_role",
                  "provider_mode_mismatch", "replacement_identity_mismatch", "replacement_requires_new_input",
                  "unknown_asset"}


def test_every_refusal_the_owner_can_meet_has_its_own_french_sentence(client):
    source = Path(affiche_api.__file__).parent
    raised = set()
    for file in [*(source / "posters").glob("*.py"), source / "api.py"]:
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
    assert response.json() == {"authenticated": True}
    cookie = response.headers["set-cookie"]
    assert all(flag in cookie for flag in ("HttpOnly", "Secure", "SameSite=strict", "Max-Age=7776000", "Path=/"))
    token = client.cookies.get(auth.COOKIE)
    with client.app.state.engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT token_hash FROM sessions").scalar_one() == hashlib.sha256(token.encode()).hexdigest()
    assert client.get("/api/shop-profile").status_code == 200
    assert client.delete("/api/session").status_code == 200
    assert client.get("/api/shop-profile", headers={"Cookie": f"{auth.COOKIE}={token}"}).status_code == 401


def test_origin_required_even_for_login_and_logout(client):
    for origin in ("", "https://evil.example", "null", ORIGIN+"/"):
        assert client.post("/api/session", json={"password": PASSWORD}, headers={"Origin": origin}).status_code == 403
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
        response = client.post("/api/session", json={"password": "wrong"}, headers={"X-Forwarded-For": f"192.0.2.{i}"})
        assert response.status_code == 401
    assert client.post("/api/session", json={"password": PASSWORD}).status_code == 429
    with client.app.state.engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT count(*) FROM login_failures").scalar_one() == 5
    assert response.json()["error"]["code"] == "unauthenticated"


def test_password_is_verified_outside_the_write_transaction_and_not_at_all_once_limited(client, settings, monkeypatch):
    engine, calls = client.app.state.engine, []

    class Probe:
        def verify(self, password, stored):
            # With the write lock held by the login, this second writer would wait 5 s and fail "database is locked".
            with write_tx(engine) as conn:
                conn.exec_driver_sql("INSERT INTO meta (key,value) VALUES ('probe','1') ON CONFLICT(key) DO NOTHING")
            calls.append(password)
            return False

    monkeypatch.setattr(auth, "PASSWORDS", Probe())
    for _ in range(5):
        assert client.post("/api/session", json={"password": "wrong"}).status_code == 401
    assert client.post("/api/session", json={"password": "wrong"}).status_code == 429
    assert len(calls) == 5


def test_at_most_two_passwords_are_verified_at_once(client, settings, monkeypatch):
    engine, lock, state = client.app.state.engine, threading.Lock(), {"now": 0, "peak": 0}

    class Slow:
        def verify(self, password, stored):
            with lock:
                state["now"] += 1
                state["peak"] = max(state["peak"], state["now"])
            time.sleep(.15)
            with lock:
                state["now"] -= 1
            return False

    monkeypatch.setattr(auth, "PASSWORDS", Slow())

    def attempt(i):
        with pytest.raises(store.Refused):
            auth.login(engine, settings, "wrong", f"198.51.100.{i}")

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
    with TestClient(app, base_url=ORIGIN, headers={"Origin": ORIGIN}) as client:
        page = client.get("/")
        assert page.status_code == 200 and "Atelier" in page.text and page.headers["cache-control"] == "no-cache"
        script = client.get("/assets/app-abc123.js")
        assert script.status_code == 200 and script.headers["cache-control"] == "public, max-age=31536000, immutable"
        assert script.headers["x-content-type-options"] == "nosniff"
        missing = client.get("/assets/gone.js")
        assert missing.status_code == 404 and missing.json()["error"]["code"] == "not_found"
        assert missing.headers["cache-control"] == "no-cache"
        assert client.get("/../backend/pyproject.toml").status_code == 404
        for path in ("/api/shop-profile", "/api/creations", "/api/openapi.json", "/api/status", "/api/nothing"):
            closed = client.get(path)
            assert closed.status_code == 401 and closed.headers["cache-control"] == "no-store", path
        assert client.post("/", headers={"Origin": "https://evil.example"}).status_code == 403
        assert client.post("/").status_code in (404, 405)
        login(client)
        assert client.get("/api/shop-profile").status_code == 200


def test_login_limit_counts_an_ipv6_64_as_one_client(client, settings):
    engine = client.app.state.engine
    assert auth.limit_key("2001:db8:1:2:aaaa::1") == auth.limit_key("2001:db8:1:2:bbbb::9") == "2001:db8:1:2::"
    assert auth.limit_key("2001:db8:1:3::1") != auth.limit_key("2001:db8:1:2::1")
    assert auth.limit_key("::ffff:192.0.2.7") == auth.limit_key("192.0.2.7") == "192.0.2.7"
    assert auth.limit_key("unknown") == "unknown"
    for i in range(5):
        with pytest.raises(store.Refused, match="unauthenticated"):
            auth.login(engine, settings, "wrong", f"2001:db8:1:2:{i}::1")
    with pytest.raises(store.Refused, match="rate_limited"):
        auth.login(engine, settings, PASSWORD, "2001:db8:1:2:ffff::1")
    assert auth.login(engine, settings, PASSWORD, "2001:db8:1:3::1")
    assert auth.login(engine, settings, PASSWORD, "192.0.2.8")


def test_session_lasts_90_days_and_a_new_password_ends_every_session(settings):
    with TestClient(create_app(settings), base_url=ORIGIN, headers={"Origin": ORIGIN}) as first:
        login(first)
        token = first.cookies.get(auth.COOKIE)
        with first.app.state.engine.connect() as conn:
            expires = datetime.fromisoformat(conn.exec_driver_sql("SELECT expires_at FROM sessions").scalar_one())
        assert timedelta(days=90)-timedelta(minutes=1) < expires-datetime.now(UTC) <= timedelta(days=90)
    cookie = {"Cookie": f"{auth.COOKIE}={token}"}
    with TestClient(create_app(settings), base_url=ORIGIN, headers={"Origin": ORIGIN}) as same:
        assert same.get("/api/session", headers=cookie).json()["authenticated"]
    settings.shop_password_hash = SecretStr(auth.PASSWORDS.hash(os.urandom(12).hex()))
    with TestClient(create_app(settings), base_url=ORIGIN, headers={"Origin": ORIGIN}) as changed:
        assert not changed.get("/api/session", headers=cookie).json()["authenticated"]
        with changed.app.state.engine.connect() as conn:
            assert conn.exec_driver_sql("SELECT count(*) FROM sessions").scalar_one() == 0


@pytest.mark.parametrize("origin", [None, "http://shop.example", "https://user@shop.example", "https://shop.example/", "https://shop.example?x=1"])
def test_bad_origin_refuses_startup(settings, origin):
    settings.app_origin = origin
    with pytest.raises(ConfigError, match="APP_ORIGIN"), TestClient(create_app(settings)):
        pass


@pytest.mark.parametrize("secret", [None, "plaintext-secret", "$argon2id$invalid"])
def test_bad_hash_refuses_startup_without_leaking(settings, secret):
    settings.shop_password_hash = SecretStr(secret) if secret else None
    with pytest.raises(ConfigError, match="SHOP_PASSWORD_HASH") as error, TestClient(create_app(settings)):
        pass
    if secret:
        assert secret not in str(error.value)


def test_local_http_cookie_and_server_restart(settings):
    settings.app_origin = "http://localhost:5173"
    with TestClient(create_app(settings), base_url=settings.app_origin, headers={"Origin": settings.app_origin}) as first:
        response = login(first)
        assert "; Secure" not in response.headers["set-cookie"]
        token = first.cookies.get(auth.COOKIE)
        for _ in range(5):
            first.post("/api/session", json={"password": "wrong"})
    with TestClient(create_app(settings), base_url=settings.app_origin, headers={"Origin": settings.app_origin}) as second:
        assert second.get("/api/session", headers={"Cookie": f"{auth.COOKIE}={token}"}).json()["authenticated"]
        assert second.post("/api/session", json={"password": PASSWORD}).status_code == 429


def test_validation_never_echoes_password(client):
    response = client.post("/api/session", json={"password": PASSWORD, "unexpected": "private"})
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
    assert client.get("/api/thumbnails/" + "0" * 64).status_code == 404  # not a preview or scene of this shop
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
    assert response.headers["cache-control"] == "no-store"
    assets.path(settings.data_dir, sha, "png").write_bytes(b"corrupt")
    assert client.get(f"/api/assets/{sha}").status_code == 409
    assets.path(settings.data_dir, sha, "png").unlink()
    assert client.get(f"/api/assets/{sha}").status_code == 404


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
        with httpx2.Client(base_url=origin, headers={"Origin": origin}, timeout=2, trust_env=False) as remote:
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
            assert remote.post("/api/session", json={"password": PASSWORD}).status_code == 200
            assert remote.get("/api/shop-profile").json()["revision"] == 1
            assert remote.delete("/api/session").status_code == 200
            assert remote.get("/api/shop-profile").status_code == 401
            # The front process on loopback is believed: the failure is counted for the phone, not for the proxy.
            assert remote.post("/api/session", json={"password": "wrong"},
                               headers={"X-Forwarded-For": "198.51.100.7, 203.0.113.9"}).status_code == 401
    finally:
        proc.kill()
        proc.communicate(timeout=10)
    with sqlite3.connect(settings.data_dir / "affiche.db") as conn:
        assert conn.execute("SELECT ip FROM login_failures").fetchall() == [("203.0.113.9",)]
