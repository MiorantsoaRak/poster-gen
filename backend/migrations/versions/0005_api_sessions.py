"""Shared-shop opaque sessions and persistent failed-login limits.

Revision ID: 0005
Revises: 0004
"""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE sessions (
        token_hash TEXT PRIMARY KEY, shop_id INTEGER NOT NULL REFERENCES shop_profile(id), expires_at TEXT NOT NULL
    )""")
    op.execute("CREATE TABLE login_failures (id INTEGER PRIMARY KEY, ip TEXT NOT NULL, attempted_at TEXT NOT NULL)")
    op.execute("CREATE INDEX login_failures_ip_date ON login_failures(ip,attempted_at)")


def downgrade() -> None:
    raise NotImplementedError("Migrations are forward-only.")
