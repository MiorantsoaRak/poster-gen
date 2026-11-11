"""Saved looks: a style brief written from a reference poster, reusable on later posters (ADR-046)."""
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

STATEMENTS = [
    """CREATE TABLE looks (
        id TEXT PRIMARY KEY, shop_id INTEGER NOT NULL,
        job_id TEXT NOT NULL UNIQUE REFERENCES poster_jobs(id),
        name TEXT NOT NULL, reference_asset TEXT NOT NULL REFERENCES assets(sha256),
        brief_json TEXT NOT NULL, source TEXT NOT NULL CHECK (source IN ('stub','claude')),
        created_at TEXT NOT NULL
    )""",
    "CREATE INDEX looks_shop ON looks (shop_id, created_at)",
]


def upgrade():
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade():
    raise NotImplementedError("Migrations are forward-only.")
