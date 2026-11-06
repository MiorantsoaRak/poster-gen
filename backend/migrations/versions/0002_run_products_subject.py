"""run_products keeps the product's name and variant (T-PV-006, Codex r1; user decision).

`apply` runs without the fixture CSV, so the scene subject is snapshotted at `generate`, like the arm, and admission
reads it from here for every request.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-06

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# SQLite's ADD COLUMN documents that NOT NULL needs a non-null default. The CHECK makes that default unusable, so a
# value is required; SQLite (3.37+) tests it against existing rows, so this fails loudly on a table with rows.
STATEMENTS = [
    "ALTER TABLE run_products ADD COLUMN name TEXT NOT NULL DEFAULT '' CHECK (trim(name) <> '')",
    "ALTER TABLE run_products ADD COLUMN variant TEXT NOT NULL DEFAULT '' CHECK (trim(variant) <> '')",
]


def upgrade() -> None:
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    raise NotImplementedError("Migrations are forward-only.")
