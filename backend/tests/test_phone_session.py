import hashlib
import importlib.util
import os
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from affiche import rehearse
from affiche.api import create_app
from affiche.runtime import AlreadyRunning, acquire_lock
from test_api import HEADERS, ORIGIN, at_0012, credentials, password_hash, settings  # noqa: F401
from test_config import env  # noqa: F401

ONE_OFF = os.urandom(12).hex()  # the session's one-off credential; nothing is written literally
SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "phone_session.py"
spec = importlib.util.spec_from_file_location("phone_session", SCRIPT)
phone_session = importlib.util.module_from_spec(spec)
spec.loader.exec_module(phone_session)


def test_the_public_address_is_read_from_the_tunnel_output_only():
    line = "2026-11-13T10:00:00Z INF |  https://quiet-river-12ab.trycloudflare.com                |"
    assert phone_session.find_address(line) == "https://quiet-river-12ab.trycloudflare.com"
    assert phone_session.find_address("INF Requesting new quick Tunnel on trycloudflare.com...") is None
    assert phone_session.find_address("see https://developers.cloudflare.com/cloudflare-one/") is None
    assert phone_session.find_address("http://plain.trycloudflare.com") is None


def test_nothing_starts_without_the_tunnel_program_or_a_password_file(monkeypatch, tmp_path):
    started = []
    monkeypatch.setattr(phone_session.subprocess, "Popen", lambda *a, **k: started.append(a))
    monkeypatch.setattr(phone_session.shutil, "which", lambda name: None)
    with pytest.raises(SystemExit, match="cloudflared is not installed"):
        phone_session.main(["phone_session.py", str(tmp_path / "password.txt")])
    with pytest.raises(SystemExit, match="Run from backend/"):
        phone_session.main(["phone_session.py"])
    assert not started and not (tmp_path / "password.txt").exists()


def test_a_tunnel_that_gives_no_address_is_stopped(monkeypatch):
    silent = phone_session.subprocess.Popen(
        [sys.executable, "-c", "import sys, time; print('no address here', file=sys.stderr, flush=True); time.sleep(30)"],
        stdout=phone_session.subprocess.DEVNULL, stderr=phone_session.subprocess.PIPE, text=True)
    monkeypatch.setattr(phone_session.subprocess, "Popen", lambda *a, **k: silent)
    with pytest.raises(SystemExit, match="nothing was exposed"):
        phone_session.open_tunnel(wait_seconds=1)
    assert silent.wait(timeout=10) is not None


def folder_state(settings):
    with closing(sqlite3.connect(settings.data_dir / "affiche.db")) as db:
        return rehearse.snapshot(db, {}), db.execute("SELECT * FROM sessions").fetchall()


@pytest.mark.parametrize("adopted", [False, True])
def test_a_folder_another_api_holds_is_left_exactly_as_it_was(settings, password_hash, monkeypatch, adopted):
    # Stub providers and a temporary folder, never data-probe: the pilot's phone signed in, the hash last seen.
    at_0012(settings, monkeypatch, hashlib.sha256(password_hash.encode()).hexdigest())
    if adopted:  # as this version's application leaves it: at head, shop 1's own password
        with TestClient(create_app(settings)):
            pass
    settings.shop_password_hash = None  # as main() passes it
    before = folder_state(settings)
    assert before[0]["version"] == ("0021" if adopted else "0012") and len(before[1]) == 1
    held = acquire_lock(settings.data_dir, "api")  # another API serves this folder
    try:
        with pytest.raises(AlreadyRunning), TestClient(phone_session.application(settings, ONE_OFF)):
            pass
    finally:
        held.close()
    assert folder_state(settings) == before  # the schema version, shop 1's password hash, the sessions, every row


def test_the_one_off_password_is_set_at_start_and_ends_the_other_sessions(settings, monkeypatch):
    phone = at_0012(settings, monkeypatch, "0" * 64)  # without the reset: an upgraded pilot with no password at all
    settings.shop_password_hash = None
    with TestClient(phone_session.application(settings, ONE_OFF), base_url=ORIGIN, headers=HEADERS) as client:
        assert not client.get("/api/session", headers=phone).json()["authenticated"]
        assert client.post("/api/session", json=credentials(ONE_OFF)).status_code == 200
        with client.app.state.engine.connect() as conn:
            assert conn.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one() == "0021"
