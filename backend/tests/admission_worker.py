"""One side of the two-process admission test (test_admission.py), run as a script and driven over stdin/stdout.

admission_worker.py <request_id> <parent_id>: settings (DATA_DIR included) from the inherited environment; connects,
prints "ready"; once it reads a line, revises the parent and prints "admitted <attempt_no>" or "refused <code>".
"""
import sys

from affiche.config import load_settings
from affiche.db import make_engine
from affiche.visuals.admission import Refused, request_revision

request_id, parent_id = sys.argv[1], sys.argv[2]
settings = load_settings(env_file=None)
engine = make_engine(settings.data_dir)
engine.connect().close()  # start-up and pragmas done before "ready"
print("ready", flush=True)
sys.stdin.readline()
try:
    admitted = request_revision(engine, settings, id=request_id, parent_id=parent_id, owner="cli")
except Refused as refusal:
    print("refused", refusal.code, flush=True)
else:
    print("admitted", admitted.attempt_no, flush=True)
