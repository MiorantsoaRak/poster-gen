"""A saved look can be removed from the lists without deleting it (D-CREATION-LIBRARY-004).

Old scenes name the look they were made with, and their refinements still read its brief: the row stays.
"""
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE looks ADD COLUMN removed_at TEXT")


def downgrade():
    raise NotImplementedError("Migrations are forward-only.")
