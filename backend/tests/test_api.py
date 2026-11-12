import hashlib
import os
import socket
import subprocess
import sys
import time
from uuid import uuid4

import httpx2
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from affiche import assets
from affiche.api import create_app
from affiche.config import ConfigError, load_settings
from affiche.db import write_tx
from affiche.posters import auth, jobs, store
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
        "planner_available": False, "scene_estimate_micros": 0, "plan_estimate_micros": 100000, "texture_estimate_micros": 0}
    assert client.get("/api/jobs/" + str(uuid4())).status_code == 404
    usage = client.get("/api/usage").json()
    assert usage["recorded_micros"] == 0 and usage["cap_micros"] == 20000000
    assert post(client, result["status_url"] + "/cancel", {}).json()["status"] == "cancelled"
    assert post(client, result["status_url"] + "/cancel", {}).status_code == 409


def test_cookie_is_opaque_hash_only_and_logout_revokes(client):
    assert client.get("/api/shop-profile").status_code == 401
    assert client.get("/api/session").json() == {"authenticated": False}
    response = login(client)
    assert response.json() == {"authenticated": True}
    cookie = response.headers["set-cookie"]
    assert all(flag in cookie for flag in ("HttpOnly", "Secure", "SameSite=strict", "Max-Age=43200", "Path=/"))
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
    assert listed["items"][0]["thumbnail_url"] is None  # no scene and no final preview yet: nothing is invented
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
    code = ("import uvicorn; from affiche.api import create_app; from affiche.config import load_settings; "
            f"uvicorn.run(create_app(load_settings(env_file=None)), host='127.0.0.1', port={port}, "
            "proxy_headers=False, access_log=False, log_level='warning')")
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
    finally:
        proc.kill()
        proc.communicate(timeout=10)
