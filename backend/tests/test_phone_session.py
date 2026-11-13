import importlib.util
import sys
from pathlib import Path

import pytest

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
