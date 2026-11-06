"""Process startup (D-PV-001): one process per owner and data folder, crash recovery, the provider-mode guard."""
import logging
import sys
import time
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Literal

from sqlalchemy import Engine, text

from affiche.config import Settings
from affiche.db import make_engine, migrate, utc_now, write_tx

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl

Owner = Literal["api", "cli"]
log = logging.getLogger(__name__)
_LOCK_RETRY_S = 0.05


class AlreadyRunning(Exception):
    """Another process of the same owner holds the lock on this data folder."""


class ProviderModeMismatch(Exception):
    """The data folder was first used with the other IMAGE_PROVIDER: stub and paid data never mix."""


@dataclass(frozen=True)
class Runtime:
    settings: Settings
    engine: Engine
    lock_file: BinaryIO  # keep it open for the process lifetime: closing it releases the lock


def acquire_lock(data_dir: Path, owner: Owner, *, wait: float = 2.0) -> BinaryIO:
    """Takes the OS lock on data_dir/<owner>.lock, retrying a held lock for `wait` seconds. The OS releases it when
    the process exits or crashes, so a stale file never blocks a restart."""
    data_dir.mkdir(parents=True, exist_ok=True)
    lock_file = (data_dir / f"{owner}.lock").open("ab")  # "ab": never truncates a file another process holds
    # Windows can free an ended process's lock a few ms after the process is gone (seen: 12 ms). LockFile docs: "the
    # time it takes for the operating system to unlock these locks depends upon available system resources".
    deadline = time.monotonic() + wait
    try:
        while True:
            try:
                _lock_exclusive(lock_file)
                return lock_file
            # msvcrt reports a held lock as EACCES (PermissionError), flock as EWOULDBLOCK (BlockingIOError).
            except (PermissionError, BlockingIOError) as error:
                if time.monotonic() >= deadline:
                    raise AlreadyRunning(
                        f"another {owner!r} process is running on the data folder {data_dir}") from error
            time.sleep(_LOCK_RETRY_S)
    except BaseException:
        lock_file.close()
        raise


def _lock_exclusive(lock_file: BinaryIO) -> None:
    if sys.platform == "win32":
        # msvcrt locks from the current position; every process must lock the same byte (beyond EOF is allowed).
        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def check_provider_mode(engine: Engine, mode: str) -> None:
    """Records the provider mode on first use; refuses the other mode afterwards."""
    with write_tx(engine) as conn:
        recorded = conn.execute(text("SELECT value FROM meta WHERE key = 'provider_mode'")).scalar()
        if recorded is None:
            conn.execute(text("INSERT INTO meta (key, value) VALUES ('provider_mode', :mode)"), {"mode": mode})
        elif recorded != mode:
            raise ProviderModeMismatch(
                f"this data was made with IMAGE_PROVIDER={recorded!r}, not {mode!r}: use another DATA_DIR")


def recover(engine: Engine, owner: Owner) -> tuple[int, int]:
    """Marks the owner's running requests and their running calls interrupted; returns (requests, calls).

    Call it only while holding the owner's lock: then no live process of this owner can have running rows.
    cost_micros is left as is: the reserved estimate stays the cost of a call that may have been billed.
    """
    params = {"owner": owner, "now": utc_now()}
    with write_tx(engine) as conn:
        calls = conn.execute(text(
            "UPDATE provider_calls SET status = 'interrupted', error_kind = 'interrupted', finished_at = :now"
            " WHERE status = 'running'"
            " AND request_id IN (SELECT id FROM generation_requests WHERE owner = :owner)"), params).rowcount
        requests = conn.execute(text(
            "UPDATE generation_requests SET status = 'interrupted', error_kind = 'interrupted', finished_at = :now"
            " WHERE owner = :owner AND status = 'running'"), params).rowcount
    return requests, calls


def start(settings: Settings, owner: Owner) -> Runtime:
    """The startup of every process: lock, migrate, provider-mode guard, recovery. On a failure after the lock,
    the lock is released and the engine disposed before the error propagates."""
    with ExitStack() as undo:
        lock_file = acquire_lock(settings.data_dir, owner)
        undo.callback(lock_file.close)
        engine = make_engine(settings.data_dir)
        undo.callback(engine.dispose)
        migrate(engine)
        check_provider_mode(engine, settings.image_provider)
        requests, calls = recover(engine, owner)
        if requests or calls:  # a handler can raise here too (a delayed FileHandler opens its file in emit)
            log.info("marked interrupted after a crash: %d %s request(s), %d provider call(s)",
                     requests, owner, calls)
        started = Runtime(settings, engine, lock_file)
        undo.pop_all()
        return started
