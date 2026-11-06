"""One side of the two-process write_tx test (test_db.py), run as a script and driven over stdin/stdout.

holder: inside write_tx, inserts a row, prints "locked", commits once it reads a line.
waiter: connects (start-up and pragmas done), prints "ready"; once it reads a line, enters write_tx
        and prints "entered <value it reads>".
"""
import sys
from pathlib import Path

from sqlalchemy import text

from affiche.db import make_engine, write_tx

role, data_dir = sys.argv[1], Path(sys.argv[2])
engine = make_engine(data_dir)

if role == "holder":
    with write_tx(engine) as conn:
        conn.execute(text("INSERT INTO meta (key, value) VALUES ('holder', 'A')"))
        print("locked", flush=True)
        sys.stdin.readline()
elif role == "waiter":
    engine.connect().close()
    print("ready", flush=True)
    sys.stdin.readline()
    with write_tx(engine) as conn:
        print("entered", conn.execute(text("SELECT value FROM meta WHERE key = 'holder'")).scalar(), flush=True)
else:
    sys.exit(f"unknown role {role!r}")
