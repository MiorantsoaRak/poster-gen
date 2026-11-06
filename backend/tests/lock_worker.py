"""The lock holder of the lock tests (test_store_lock.py), run as a script. It waits on stdin: the test kills it
(a crash) or sends a line (a clean exit).

lock <data_dir>: takes the cli lock, prints "locked".
crash: start(settings from the inherited environment, "cli"), commits one run, a running cli request with a running
       call (cost 400000), a running api request with a running call and a succeeded cli request, prints "ready".
"""
import sys
from pathlib import Path

from sqlalchemy import text

from affiche.config import load_settings
from affiche.db import write_tx
from affiche.runtime import acquire_lock, start

REQUEST = ("INSERT INTO generation_requests (id, payload_hash, purpose, variant_ref, cycle_no, run_label, request_json,"
           " corrections_applied, owner, status, created_at) VALUES (:id, 'h', 'scene', :id, 1, 'r1', '{}', 0, :owner,"
           " :status, 't0')")
CALL = ("INSERT INTO provider_calls (id, request_id, call_no, provider, model, status, cost_micros, cost_is_estimate,"
        " started_at) VALUES (:id, :request_id, 1, 'stub', 'm', 'running', :cost, 1, 't0')")

role = sys.argv[1]
if role == "lock":
    lock_file = acquire_lock(Path(sys.argv[2]), "cli")
    print("locked", flush=True)
elif role == "crash":
    runtime = start(load_settings(env_file=None), "cli")
    with write_tx(runtime.engine) as conn:
        conn.execute(text("INSERT INTO runs VALUES ('r1', 'm', 'high', '1024x1536', 3, 'on', 't0')"))
        conn.execute(text(REQUEST), [{"id": "cli-running", "owner": "cli", "status": "running"},
                                     {"id": "api-running", "owner": "api", "status": "running"},
                                     {"id": "cli-succeeded", "owner": "cli", "status": "succeeded"}])
        conn.execute(text(CALL), [{"id": "cli-call", "request_id": "cli-running", "cost": 400000},
                                  {"id": "api-call", "request_id": "api-running", "cost": 300000}])
    print("ready", flush=True)
else:
    sys.exit(f"unknown role {role!r}")
sys.stdin.readline()
