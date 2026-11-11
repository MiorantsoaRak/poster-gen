"""Selected-layer proposals and reviewed text material effects."""
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

STATEMENTS = [
    """CREATE TABLE text_proposals (
        id TEXT PRIMARY KEY, shop_id INTEGER NOT NULL REFERENCES shop_profile(id),
        creation_id TEXT NOT NULL, origin_revision INTEGER NOT NULL,
        format TEXT NOT NULL CHECK (format IN ('feed','square','story')), layer_id TEXT NOT NULL,
        job_id TEXT NOT NULL UNIQUE REFERENCES poster_jobs(id), patch_json TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('pending','applied','rejected')),
        applied_revision INTEGER, created_at TEXT NOT NULL,
        FOREIGN KEY (creation_id,origin_revision) REFERENCES creation_versions(creation_id,revision)
    )""",
    """CREATE TABLE text_effects (
        id TEXT PRIMARY KEY, shop_id INTEGER NOT NULL REFERENCES shop_profile(id),
        creation_id TEXT NOT NULL, origin_revision INTEGER NOT NULL,
        format TEXT NOT NULL CHECK (format IN ('feed','square','story')), layer_id TEXT NOT NULL,
        proposal_id TEXT NOT NULL REFERENCES text_proposals(id), job_id TEXT NOT NULL UNIQUE REFERENCES poster_jobs(id),
        input_layer_style_hash TEXT NOT NULL, texture_asset TEXT NOT NULL REFERENCES assets(sha256),
        material_prompt TEXT NOT NULL, palette_json TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('proposed','applied','rejected')),
        applied_revision INTEGER, created_at TEXT NOT NULL,
        FOREIGN KEY (creation_id,origin_revision) REFERENCES creation_versions(creation_id,revision)
    )""",
]


def upgrade():
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade():
    raise NotImplementedError("Migrations are forward-only.")
