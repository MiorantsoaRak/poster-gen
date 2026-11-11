"""Snapshot ordered original-photo hashes; NULL preserves unverified legacy provenance.

Revision ID: 0003
Revises: 0002
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE run_products ADD COLUMN photo_assets_json TEXT")


def downgrade() -> None:
    raise NotImplementedError("Migrations are forward-only.")
