import hashlib
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from sqlalchemy import Engine, text

from affiche import assets, runtime
from affiche.config import load_settings
from affiche.db import make_engine, migrate, write_tx
from affiche.runtime import AlreadyRunning, ProviderModeMismatch, acquire_lock, recover, start
from test_config import env  # noqa: F401  (fixture: a clean, valid environment, inherited by the workers)
from test_db import _stdout_lines

WORKER = Path(__file__).with_name("lock_worker.py")
PIPES = {"stdin": subprocess.PIPE, "stdout": subprocess.PIPE, "text": True}


def _settings(env, data_dir, mode="stub"):
    env.setenv("DATA_DIR", str(data_dir))
    env.setenv("IMAGE_PROVIDER", mode)
    if mode == "openai":
        env.setenv("OPENAI_API_KEY", "sk-test-fake-key")  # start() makes no provider call
    return load_settings(env_file=None)


def _stop(started):
    started.engine.dispose()
    started.lock_file.close()


def _reap(proc, lines):
    """Ends the worker and waits for the reader's EOF (None): leaving Popen closes stdout, which must not happen
    under the reader thread."""
    proc.kill()
    proc.wait(timeout=10)
    while lines.get(timeout=10) is not None:
        pass


def _asset_files(data_dir):
    return sorted(p for p in (data_dir / "assets").rglob("*") if p.is_file())


def test_put_stores_the_bytes_under_their_sha(tmp_path):
    data = b"\x89PNG not really"
    sha = assets.put(tmp_path, data, "png")
    stored = tmp_path / "assets" / sha[:2] / f"{sha}.png"
    assert sha == hashlib.sha256(data).hexdigest()
    assert assets.path(tmp_path, sha, "png") == stored
    assert _asset_files(tmp_path) == [stored]  # no temp file left
    assert hashlib.sha256(stored.read_bytes()).hexdigest() == stored.stem


def test_put_of_the_same_bytes_does_not_rewrite_the_file(tmp_path, monkeypatch):
    sha = assets.put(tmp_path, b"same", "png")

    def no_replace(*_args):
        raise AssertionError("an existing asset was rewritten")

    monkeypatch.setattr(os, "replace", no_replace)
    assert assets.put(tmp_path, b"same", "png") == sha
    assert _asset_files(tmp_path) == [assets.path(tmp_path, sha, "png")]


def test_put_of_other_bytes_makes_another_file(tmp_path):
    first, second = assets.put(tmp_path, b"one", "png"), assets.put(tmp_path, b"two", "png")
    assert first != second
    assert _asset_files(tmp_path) == sorted([assets.path(tmp_path, first, "png"), assets.path(tmp_path, second, "png")])


@pytest.mark.parametrize("failing", ["fsync", "replace"])
def test_a_failed_put_leaves_no_file_and_propagates(tmp_path, monkeypatch, failing):
    def fail(*_args):
        raise OSError("disk full")

    monkeypatch.setattr(os, failing, fail)
    with pytest.raises(OSError, match="disk full"):
        assets.put(tmp_path, b"data", "png")
    assert _asset_files(tmp_path) == []


def test_record_inserts_one_row_and_the_first_kind_wins(tmp_path):
    engine = make_engine(tmp_path)
    try:
        migrate(engine)
        for kind in ("original", "scene"):
            with write_tx(engine) as conn:
                assets.record(conn, sha="ab" * 32, kind=kind, mime="image/png", width=2, height=3, size=10)
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT sha256, kind, mime, width, height, bytes FROM assets")).all()
    finally:
        engine.dispose()
    assert rows == [("ab" * 32, "original", "image/png", 2, 3, 10)]


def test_a_second_lock_in_the_same_process_is_refused(tmp_path):
    held = acquire_lock(tmp_path, "cli")
    try:
        with pytest.raises(AlreadyRunning):
            acquire_lock(tmp_path, "cli", wait=0)
    finally:
        held.close()
    acquire_lock(tmp_path, "cli").close()  # closing released it


def test_a_held_lock_refuses_the_same_owner_until_its_process_dies(tmp_path):
    with subprocess.Popen([sys.executable, str(WORKER), "lock", str(tmp_path)], **PIPES) as holder:
        lines = _stdout_lines(holder)
        try:
            assert lines.get(timeout=15) == "locked"
            began = time.monotonic()
            with pytest.raises(AlreadyRunning, match="another 'cli' process is running"):
                acquire_lock(tmp_path, "cli", wait=0.2)
            assert time.monotonic() - began >= 0.2  # it retried for the whole wait before refusing
            acquire_lock(tmp_path, "api").close()  # the owners are independent
            holder.kill()  # a crash: no clean exit, no unlock call
            holder.wait(timeout=10)
            acquire_lock(tmp_path, "cli").close()
        finally:
            _reap(holder, lines)


def test_after_a_clean_exit_the_next_process_takes_the_lock_at_once(tmp_path):
    with subprocess.Popen([sys.executable, str(WORKER), "lock", str(tmp_path)], **PIPES) as holder:
        lines = _stdout_lines(holder)
        try:
            assert lines.get(timeout=15) == "locked"
            holder.stdin.write("exit\n")
            holder.stdin.flush()
            assert holder.wait(timeout=10) == 0
            acquire_lock(tmp_path, "cli").close()  # back-to-back commands, e.g. generate then sheet
        finally:
            _reap(holder, lines)


def test_start_after_a_crash_interrupts_only_the_owners_running_work(env, tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="affiche.runtime")
    settings = _settings(env, tmp_path)
    with subprocess.Popen([sys.executable, str(WORKER), "crash"], **PIPES) as worker:
        lines = _stdout_lines(worker)
        try:
            assert lines.get(timeout=30) == "ready"
        finally:
            _reap(worker, lines)  # the crash: killed while it waits

    started = start(settings, "cli")
    try:
        with started.engine.connect() as conn:
            requests = {id_: rest for id_, *rest in conn.execute(text(
                "SELECT id, status, error_kind, finished_at IS NOT NULL FROM generation_requests"))}
            calls = {id_: rest for id_, *rest in conn.execute(text(
                "SELECT id, status, error_kind, finished_at IS NOT NULL, cost_micros FROM provider_calls"))}
        assert recover(started.engine, "cli") == (0, 0)  # nothing left to recover
    finally:
        _stop(started)
    assert requests == {"cli-running": ["interrupted", "interrupted", 1],
                        "api-running": ["running", None, 0],
                        "cli-succeeded": ["succeeded", None, 0]}
    assert calls == {"cli-call": ["interrupted", "interrupted", 1, 400000],  # the reserved estimate stays the cost
                     "api-call": ["running", None, 0, 300000]}
    assert [r.getMessage() for r in caplog.records] == [
        "marked interrupted after a crash: 1 cli request(s), 1 provider call(s)"]


def test_the_other_provider_mode_is_refused_and_the_lock_released(env, tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="affiche.runtime")
    for _ in range(2):  # the same mode twice is fine
        started = start(_settings(env, tmp_path, "stub"), "cli")
        try:
            with pytest.raises(AlreadyRunning):  # start keeps the lock
                acquire_lock(tmp_path, "cli", wait=0)
        finally:
            _stop(started)
    refusal = "IMAGE_PROVIDER='stub', not 'openai': use another DATA_DIR"
    # "as _caught" keeps start's frame, so its lock file, alive: the lock must be released by start, not by GC.
    with pytest.raises(ProviderModeMismatch, match=refusal) as _caught:
        start(_settings(env, tmp_path, "openai"), "cli")
    acquire_lock(tmp_path, "cli").close()
    engine = make_engine(tmp_path)
    try:
        with engine.connect() as conn:
            assert conn.execute(text("SELECT value FROM meta WHERE key = 'provider_mode'")).scalar() == "stub"
    finally:
        engine.dispose()
    assert caplog.records == []  # nothing recovered, nothing logged


def test_a_failure_after_the_lock_releases_it_and_disposes_the_engine(env, tmp_path, monkeypatch):
    def failing_migrate(_engine):
        raise RuntimeError("migration failed")

    disposed = []
    monkeypatch.setattr(runtime, "migrate", failing_migrate)
    monkeypatch.setattr(Engine, "dispose", lambda engine, close=True: disposed.append(engine))
    with pytest.raises(RuntimeError, match="migration failed") as _caught:  # keeps the frame alive, as above
        start(_settings(env, tmp_path), "cli")
    assert len(disposed) == 1
    acquire_lock(tmp_path, "cli").close()


def test_a_failing_recovery_log_releases_the_lock_and_disposes_the_engine(env, tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="affiche.runtime")
    # A delayed FileHandler opens its file in emit(), outside the handler's own error handling: log.info raises.
    unopenable = logging.FileHandler(tmp_path / "missing" / "start.log", delay=True)
    disposed, real_dispose = [], Engine.dispose

    def spy_dispose(engine, close=True):
        disposed.append(engine)
        real_dispose(engine, close)

    monkeypatch.setattr(Engine, "dispose", spy_dispose)
    monkeypatch.setattr(runtime, "recover", lambda _engine, _owner: (1, 0))  # something to log
    logging.getLogger("affiche.runtime").addHandler(unopenable)
    try:
        with pytest.raises(FileNotFoundError) as _caught:  # keeps the frame alive, as above
            start(_settings(env, tmp_path), "cli")
    finally:
        logging.getLogger("affiche.runtime").removeHandler(unopenable)
    assert len(disposed) == 1
    acquire_lock(tmp_path, "cli", wait=0).close()
