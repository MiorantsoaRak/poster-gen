from contextlib import AbstractContextManager
from pathlib import Path
from sqlite3 import Connection as SqliteConnection
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, Engine, create_engine, event

from affiche.config import BACKEND_DIR

_WRITE_OPTION = "affiche_write_tx"


def make_engine(data_dir: Path) -> Engine:
    data_dir.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{data_dir / 'affiche.db'}")
    event.listen(engine, "connect", _on_connect)
    event.listen(engine, "begin", _on_begin)
    return engine


def _on_connect(dbapi_conn: SqliteConnection, _record: Any) -> None:
    # pysqlite's own implicit BEGIN is always DEFERRED; switch it off so _on_begin decides.
    # (Recipe of the SQLAlchemy 2.1 SQLite dialect docs, "Using SQLAlchemy to emit BEGIN".)
    dbapi_conn.isolation_level = None
    cursor = dbapi_conn.cursor()
    try:
        cursor.execute("PRAGMA busy_timeout = 5000")
        mode = cursor.execute("PRAGMA journal_mode = WAL").fetchone()[0]
        if mode != "wal":
            raise RuntimeError(f"SQLite refused WAL journal mode (got {mode!r})")
        cursor.execute("PRAGMA foreign_keys = ON")
    finally:
        cursor.close()


def _on_begin(conn: Connection) -> None:
    write = conn.get_execution_options().get(_WRITE_OPTION, False)
    conn.exec_driver_sql("BEGIN IMMEDIATE" if write else "BEGIN")


def write_tx(engine: Engine) -> AbstractContextManager[Connection]:
    """A transaction holding SQLite's write lock from BEGIN: another writer waits (busy_timeout)
    instead of failing when a deferred read transaction tries to upgrade. Commits on success,
    rolls back on exception."""
    return engine.execution_options(**{_WRITE_OPTION: True}).begin()


def migrate(engine: Engine) -> None:
    """Upgrade to head on a connection of this engine, so the pragmas and BEGIN IMMEDIATE apply."""
    config = Config(BACKEND_DIR / "alembic.ini")
    with write_tx(engine) as conn:
        config.attributes["connection"] = conn
        command.upgrade(config, "head")
