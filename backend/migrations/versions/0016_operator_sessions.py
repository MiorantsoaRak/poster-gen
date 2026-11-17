"""The operator's sessions (D-ADMIN-001, D-ADMIN-002): a table with no shop in it, so that an operator session is never a
shop session by the schema itself. The operator's password needs no migration: its Argon2 hash is a row of meta
(auth.OPERATOR_KEY), written only by python -m affiche.shops operator-password.

No guard, and rehearse.GUARDS is unchanged: there is no shop identity here to reassign, and nothing here is money or
history. A REPLACE could extend a session's expiry and an UPDATE could rekey one; no code does either (it inserts a
fresh token's hash, reads and deletes), and whoever can write the database file can insert a session anyway.
"""
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

STATEMENTS = [
    # address: the client as uvicorn gives it; agent: the browser's User-Agent, cut at 200.
    """CREATE TABLE operator_sessions (
  token_hash TEXT PRIMARY KEY CHECK (length(token_hash) = 64),
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  address TEXT NOT NULL CHECK (length(address) BETWEEN 1 AND 64),
  agent TEXT CHECK (agent IS NULL OR length(agent) BETWEEN 1 AND 200)
)""",
]

# The rehearsal's contract (affiche.rehearse). PRESERVED: no table is rebuilt or widened.
PRESERVED = {}
ADDED = {"operator_sessions: empty": ("SELECT count(*) FROM operator_sessions", [(0,)])}


def upgrade():
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade():
    raise NotImplementedError("Migrations are forward-only.")
