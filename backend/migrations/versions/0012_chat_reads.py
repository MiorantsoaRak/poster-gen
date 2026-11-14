"""The ledger of the chat's reading calls: one paid text call per message (D-TEXT-FIRST-002).

The conversation itself stays in the browser; a row keeps the answer only so that a repeated request replays.
"""
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

STATEMENTS = [
    """CREATE TABLE chat_reads (
        id TEXT PRIMARY KEY,
        shop_id INTEGER NOT NULL REFERENCES shop_profile(id),
        creation_id TEXT REFERENCES creations(id),
        key TEXT NOT NULL UNIQUE,
        payload_sha TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed', 'interrupted')),
        provider TEXT NOT NULL, model TEXT NOT NULL, rate_card_json TEXT NOT NULL,
        cost_micros INTEGER NOT NULL,
        cost_is_estimate INTEGER NOT NULL,
        usage_json TEXT, provider_request_id TEXT,
        response_json TEXT,
        created_at TEXT NOT NULL, finished_at TEXT
    )""",
    "CREATE INDEX chat_reads_created ON chat_reads (created_at)",
]


def upgrade():
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade():
    raise NotImplementedError("Migrations are forward-only.")
