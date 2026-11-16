"""Rehearses the pending migrations on a copy of a database, before they run on it (multi-shop design, Release gate):

    python -m affiche.rehearse <database file>

The file is only read: SQLite's online backup copies it into a temporary folder, and the copy is migrated, then
deleted. On the copy, before and after: each data table's row count and SHA-256 of its rows, the three ledgers'
sums, foreign_key_check and integrity_check. A table that a pending migration rebuilds or widens is hashed over the
columns it had before (the migration's PRESERVED); what the migration changes on purpose is checked apart (its
ADDED), and so is the schema version. On every rehearsal, pending migrations or not, the migrated copy must still hold
the GUARDS. Prints REHEARSAL OK, or REHEARSAL FAILED and every difference; exits 0, 1, or
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
# Schema objects every later migration must keep, checked after every rehearsal whatever is pending: rebuilding a
# table by SQLite's procedure drops its triggers without a word. A migration that changes one updates it here.
GUARDS = {  # (type, name): the CREATE statement as 0014 wrote it
    ("table", "credit_grants"): """CREATE TABLE credit_grants (
  id INTEGER PRIMARY KEY,
  shop_id INTEGER NOT NULL REFERENCES shop_profile(id),
  kind TEXT NOT NULL CHECK (kind IN ('grant', 'correction')),
  origin TEXT CHECK (origin IN ('offered', 'bought')),
  credits INTEGER NOT NULL CHECK (typeof(credits) = 'integer'),
  amount_ar INTEGER CHECK (amount_ar IS NULL OR (typeof(amount_ar) = 'integer' AND amount_ar <> 0)),
  method TEXT CHECK (method IS NULL OR length(method) BETWEEN 1 AND 40),
  ref TEXT NOT NULL CHECK (length(ref) BETWEEN 1 AND 100),
  job_id TEXT UNIQUE REFERENCES poster_jobs(id),
  note TEXT CHECK (note IS NULL OR length(note) BETWEEN 1 AND 500),
  actor TEXT NOT NULL CHECK (length(actor) BETWEEN 1 AND 64),
  created_at TEXT NOT NULL,
  CHECK (COALESCE(CASE kind
    WHEN 'grant' THEN credits > 0 AND job_id IS NULL AND (
         (origin = 'bought' AND amount_ar > 0 AND method IS NOT NULL)
      OR (origin = 'offered' AND amount_ar IS NULL AND method IS NULL))
    ELSE origin IS NULL AND method IS NULL AND note IS NOT NULL
      AND (credits <> 0 OR amount_ar IS NOT NULL)
      AND (job_id IS NULL OR (credits = 1 AND amount_ar IS NULL)) END, 0)),
  UNIQUE (shop_id, kind, ref)
)""",
    ("trigger", "credit_grants_never_changed"): """CREATE TRIGGER credit_grants_never_changed BEFORE UPDATE ON credit_grants
  BEGIN SELECT RAISE(ABORT, 'a credit line is never changed'); END""",
    ("trigger", "credit_grants_never_removed"): """CREATE TRIGGER credit_grants_never_removed BEFORE DELETE ON credit_grants
  BEGIN SELECT RAISE(ABORT, 'a credit line is never removed'); END""",
    ("trigger", "credit_grants_never_replaced"): """CREATE TRIGGER credit_grants_never_replaced BEFORE INSERT ON credit_grants
  WHEN EXISTS (SELECT 1 FROM credit_grants WHERE id = NEW.id OR job_id = NEW.job_id
               OR (shop_id = NEW.shop_id AND kind = NEW.kind AND ref = NEW.ref))
  BEGIN SELECT RAISE(ABORT, 'a credit line is never replaced'); END""",
    ("trigger", "credit_grants_one_payment"): """CREATE TRIGGER credit_grants_one_payment BEFORE INSERT ON credit_grants
  WHEN NEW.amount_ar > 0 AND EXISTS (SELECT 1 FROM credit_grants WHERE ref = NEW.ref AND shop_id <> NEW.shop_id
       GROUP BY shop_id HAVING SUM(amount_ar) > 0)
  BEGIN SELECT RAISE(ABORT, 'this payment is already counted in another shop'); END""",
    ("trigger", "credit_grants_payment_total"): """CREATE TRIGGER credit_grants_payment_total BEFORE INSERT ON credit_grants
  WHEN NEW.kind = 'correction' AND NEW.amount_ar IS NOT NULL AND (
       (SELECT COALESCE(SUM(amount_ar), 0) FROM credit_grants WHERE shop_id = NEW.shop_id AND ref = NEW.ref) <= 0
    OR (NEW.credits = 0 AND (SELECT COALESCE(SUM(amount_ar), 0) FROM credit_grants
                             WHERE shop_id = NEW.shop_id AND ref = NEW.ref) + NEW.amount_ar <= 0)
    OR (NEW.credits <> 0 AND (SELECT COALESCE(SUM(amount_ar), 0) FROM credit_grants
                              WHERE shop_id = NEW.shop_id AND ref = NEW.ref) + NEW.amount_ar <> 0))
  BEGIN SELECT RAISE(ABORT, 'a payment''s corrected total must stay positive, or a reversal must bring it to zero'); END""",
    ("trigger", "poster_jobs_final"): """CREATE TRIGGER poster_jobs_final BEFORE UPDATE OF status, takes_credit ON poster_jobs
  WHEN NEW.takes_credit IS NOT OLD.takes_credit
    OR (OLD.status IN ('succeeded', 'failed', 'interrupted', 'cancelled') AND NEW.status IS NOT OLD.status)
  BEGIN SELECT RAISE(ABORT, 'a finished job never changes status, and no job changes what it costs'); END""",
    ("trigger", "poster_jobs_never_removed"): """CREATE TRIGGER poster_jobs_never_removed BEFORE DELETE ON poster_jobs
  BEGIN SELECT RAISE(ABORT, 'a job is never removed'); END""",
    ("trigger", "poster_jobs_never_replaced"): """CREATE TRIGGER poster_jobs_never_replaced BEFORE INSERT ON poster_jobs
  WHEN EXISTS (SELECT 1 FROM poster_jobs WHERE id = NEW.id OR rowid = NEW.rowid)
    OR (NEW.kind IN ('scene', 'refine', 'text_texture', 'background') AND NEW.status IN ('queued', 'running')
        AND EXISTS (SELECT 1 FROM poster_jobs WHERE creation_id = NEW.creation_id
                    AND kind IN ('scene', 'refine', 'text_texture', 'background') AND status IN ('queued', 'running')))
  BEGIN SELECT RAISE(ABORT, 'a job is never replaced'); END""",
    ("trigger", "poster_jobs_same_job"): """CREATE TRIGGER poster_jobs_same_job BEFORE UPDATE ON poster_jobs
  WHEN NEW.rowid IS NOT OLD.rowid OR NEW.id IS NOT OLD.id OR NEW.shop_id IS NOT OLD.shop_id
    OR NEW.creation_id IS NOT OLD.creation_id OR NEW.kind IS NOT OLD.kind
  BEGIN SELECT RAISE(ABORT, 'a job stays the same job: its id, shop, poster and kind never change'); END""",
}
# A column's text inside its table's statement: ALTER TABLE ADD COLUMN writes it there, and a rebuild must keep it.
GUARDED_COLUMNS = {"poster_jobs": "takes_credit INTEGER NOT NULL DEFAULT 0 CHECK (takes_credit IN (0, 1))"}


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


def guards(db: sqlite3.Connection) -> dict[str, str]:
    """Each guard's state on this database: 'as expected', 'missing' or 'different'. Runs of whitespace are collapsed on
    both sides; the SQL is otherwise compared exactly, so a harmless rewording fails too until GUARDS follows it."""
    def collapsed(sql: str) -> str:
        return " ".join(sql.split())

    states = {}
    for (kind, name), expected in GUARDS.items():
        row = db.execute("SELECT sql FROM sqlite_master WHERE type=? AND name=?", (kind, name)).fetchone()
        states[f"guard {kind} {name}"] = ("missing" if row is None else
                                          "as expected" if collapsed(row[0]) == collapsed(expected) else "different")
    for table, column in GUARDED_COLUMNS.items():
        row = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
        named = db.execute("SELECT 1 FROM pragma_table_info(?) WHERE name=?", (table, column.split()[0])).fetchone()
        states[f"guard column {table}.{column.split()[0]}"] = (
            "missing" if row is None or named is None else
            "as expected" if collapsed(column) in collapsed(row[0]) else "different")
    return states


def guard_differences(db: sqlite3.Connection) -> list[str]:
    return [f"{guard}: {state}" for guard, state in guards(db).items() if state != "as expected"]


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
        guarded = _open(copy, guards)  # also when nothing is pending: a database changed by hand

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
    for guard, state in guarded.items():
        report.append(f"{guard}: {state}")
        if state != "as expected":
            differences.append(f"{guard}: {state}")
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
