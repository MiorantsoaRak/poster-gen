"""Rehearses the pending migrations on a copy of a database, before they run on it (multi-shop design, Release gate):

    python -m affiche.rehearse <database file>

The file is only read: SQLite's online backup copies it into a temporary folder, and the copy is migrated, then
deleted. On the copy, before and after: each data table's row count and SHA-256 of its rows, the three ledgers'
sums, foreign_key_check and integrity_check. A table that a pending migration rebuilds or widens is hashed over the
columns it had before (the migration's PRESERVED); what the migration changes on purpose is checked apart (its
ADDED), and so is the schema version. Prints REHEARSAL OK, or REHEARSAL FAILED and every difference; exits 0, 1, or
2 for a wrong command line. Reads no settings and no .env.
"""
import hashlib
import json
import os
import platform
import sqlite3
import sys
import tempfile
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.script.revision import RevisionError
from alembic.util import CommandError
from sqlalchemy.exc import SQLAlchemyError

from affiche.config import BACKEND_DIR
from affiche.db import make_engine, migrate

LEDGERS = ("provider_calls", "poster_calls", "chat_reads")


def _quoted(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _version(db: sqlite3.Connection) -> str | None:
    if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='alembic_version'").fetchone() is None:
        return None
    return db.execute("SELECT version_num FROM alembic_version").fetchone()[0]


def snapshot(db: sqlite3.Connection, projections: dict[str, tuple[str, ...]]) -> dict:
    """Every data table's (row count, SHA-256 of its rows), the ledger sums, the version and both checks. A row is
    the canonical JSON (blobs as hex) of the table's projected columns, else of all of them, read in primary-key
    order (else rowid order). alembic_version is schema metadata, not data."""
    tables = {}
    for (table,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                               " AND name<>'alembic_version' ORDER BY name").fetchall():
        info = db.execute("SELECT name, pk FROM pragma_table_info(?)", (table,)).fetchall()
        columns = projections.get(table) or tuple(name for name, _pk in info)
        order = [name for _pk, name in sorted((pk, name) for name, pk in info if pk)] or ["rowid"]
        digest, count = hashlib.sha256(), 0
        for row in db.execute(f"SELECT {', '.join(map(_quoted, columns))} FROM {_quoted(table)}"
                              f" ORDER BY {', '.join(map(_quoted, order))}"):
            values = [value.hex() if isinstance(value, bytes) else value for value in row]
            digest.update(json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n")
            count += 1
        tables[table] = (count, digest.hexdigest())
    return {"tables": tables, "version": _version(db),
            "sums": {ledger: db.execute(f"SELECT COALESCE(SUM(cost_micros),0) FROM {ledger}").fetchone()[0]
                     for ledger in LEDGERS if ledger in tables},
            "foreign_key_check": len(db.execute("PRAGMA foreign_key_check").fetchall()),
            "integrity_check": db.execute("PRAGMA integrity_check").fetchone()[0]}


def _open(path: Path, read):
    db = sqlite3.connect(path)
    try:
        return read(db)
    finally:
        db.close()


def rehearse(source: Path) -> tuple[list[str], list[str]]:
    """(report lines, differences): the rehearsal passed when there is no difference."""
    script = ScriptDirectory.from_config(Config(BACKEND_DIR / "alembic.ini"))
    head = script.get_current_head()
    with tempfile.TemporaryDirectory(prefix="affiche-rehearse-") as folder:
        copy = Path(folder) / "affiche.db"
        reader = sqlite3.connect(f"{source.resolve().as_uri()}?mode=ro", uri=True)  # never creates, never writes
        try:
            writer = sqlite3.connect(copy)
            try:
                reader.backup(writer)  # one consistent snapshot, whatever the source's own writer does meanwhile
            finally:
                writer.close()
        finally:
            reader.close()
        pending = [revision.module for revision in reversed(list(script.iterate_revisions("head", _open(copy, _version))))]
        report = [f"pending migrations: {', '.join(module.revision for module in pending) or 'none'} (code head {head})"]
        unstated = [module.revision for module in pending if not isinstance(getattr(module, "PRESERVED", None), dict)
                    or not isinstance(getattr(module, "ADDED", None), dict)]
        if unstated:
            return report, [f"pending migration {revision} states no PRESERVED and ADDED" for revision in unstated]
        projections = {}
        for module in pending:  # a table takes the projection of the earliest pending migration that names it
            for table, columns in module.PRESERVED.items():
                projections.setdefault(table, tuple(columns))
        before = _open(copy, lambda db: snapshot(db, projections))
        engine = make_engine(Path(folder))
        try:
            migrate(engine)
        finally:
            engine.dispose()
        after = _open(copy, lambda db: snapshot(db, projections))
        added = {(module.revision, name): (expected, _open(copy, lambda db: [tuple(row) for row in db.execute(query)]))
                 for module in pending for name, (query, expected) in module.ADDED.items()}

    differences = []
    report.append(f"{'table':<22} {'rows before':>11} {'rows after':>10}  sha256 before | sha256 after")
    for table in sorted(before["tables"].keys() | after["tables"].keys()):
        (rows_before, hash_before), (rows_after, hash_after) = (side["tables"].get(table, (None, None))
                                                                for side in (before, after))
        over = f"  (over {', '.join(projections[table])})" if table in projections else ""
        report.append(f"{table:<22} {rows_before!s:>11} {rows_after!s:>10}  {hash_before} | {hash_after}{over}")
        if table not in after["tables"]:
            differences.append(f"{table}: missing after the migration")
        elif table in before["tables"] and (rows_before, hash_before) != (rows_after, hash_after):
            differences.append(f"{table}: {rows_before} -> {rows_after} rows, "
                               f"{'same' if hash_before == hash_after else 'different'} content")
    for ledger in LEDGERS:
        report.append(f"ledger {ledger}: {before['sums'].get(ledger)} -> {after['sums'].get(ledger)} micro-USD")
        if before["sums"].get(ledger) != after["sums"].get(ledger):
            differences.append(f"ledger {ledger}: {before['sums'].get(ledger)} -> {after['sums'].get(ledger)}")
    for check in ("foreign_key_check", "integrity_check"):
        report.append(f"{check}: {before[check]} -> {after[check]}")
    if after["foreign_key_check"]:
        differences.append(f"foreign_key_check: {after['foreign_key_check']} rows after the migration")
    if after["integrity_check"] != "ok":
        differences.append(f"integrity_check after the migration: {after['integrity_check']}")
    report.append(f"schema version: {before['version']} -> {after['version']}")
    if after["version"] != head:
        differences.append(f"schema version after the migration: {after['version']}, expected {head}")
    for (revision, name), (expected, got) in added.items():
        report.append(f"{revision} ADDED {name}: {'as expected' if got == expected else got}")
        if got != expected:
            differences.append(f"{revision} ADDED {name}: expected {expected}, got {got}")
    return report, differences


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    # The environment first: the report is the release's evidence of where it ran (SQLite of the release image).
    print(f"environment: SQLite {sqlite3.sqlite_version}, Python {platform.python_version()}, "
          f"revision {os.environ.get('REVISION') or 'dev'}\nsource: {argv[1]} (only read; rehearsed on a copy)")
    try:
        report, differences = rehearse(Path(argv[1]))
    except (OSError, sqlite3.Error, SQLAlchemyError, CommandError, RevisionError, RuntimeError) as error:
        print(f"REHEARSAL FAILED: {type(error).__name__}: {error}")
        return 1
    print("\n".join(report))
    if differences:
        print("REHEARSAL FAILED: " + "; ".join(differences))
        return 1
    print("REHEARSAL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
