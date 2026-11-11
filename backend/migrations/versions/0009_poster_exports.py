"""Immutable authoritative renders and confirmations."""
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

STATEMENTS = [
    """CREATE TABLE poster_renders (
        id TEXT PRIMARY KEY, creation_id TEXT NOT NULL, source_revision INTEGER NOT NULL,
        job_id TEXT NOT NULL UNIQUE REFERENCES poster_jobs(id), format TEXT NOT NULL,
        format_hash TEXT NOT NULL, renderer_build_hash TEXT NOT NULL, font_manifest_hash TEXT NOT NULL,
        asset_manifest_json TEXT NOT NULL, png_sha256 TEXT NOT NULL, width INTEGER NOT NULL,
        height INTEGER NOT NULL, bytes INTEGER NOT NULL, warnings_json TEXT NOT NULL, created_at TEXT NOT NULL,
        FOREIGN KEY (creation_id,source_revision) REFERENCES creation_versions(creation_id,revision),
        UNIQUE (creation_id,source_revision,format,renderer_build_hash,format_hash)
    )""",
    """CREATE TABLE confirmations (
        id TEXT PRIMARY KEY, creation_id TEXT NOT NULL, source_revision INTEGER NOT NULL,
        confirmed_revision INTEGER NOT NULL, format TEXT NOT NULL, format_hash TEXT NOT NULL,
        render_id TEXT NOT NULL UNIQUE REFERENCES poster_renders(id), png_sha256 TEXT NOT NULL,
        checklist_json TEXT NOT NULL, confirmed_at TEXT NOT NULL,
        FOREIGN KEY (creation_id,confirmed_revision) REFERENCES creation_versions(creation_id,revision)
    )""",
]


def upgrade():
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade():
    raise NotImplementedError("Migrations are forward-only.")
