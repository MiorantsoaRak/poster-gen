"""Immutable inputs, shop identity and versioned drafts (ADR-031).

Revision ID: 0004
Revises: 0003
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

STATEMENTS = [
    """CREATE TABLE shop_profile (
        id INTEGER PRIMARY KEY CHECK (id = 1), revision INTEGER NOT NULL CHECK (revision >= 1),
        name TEXT, contact TEXT, logo_asset TEXT REFERENCES assets(sha256), updated_at TEXT NOT NULL
    )""",
    "INSERT INTO shop_profile VALUES (1, 1, NULL, NULL, NULL, strftime('%Y-%m-%dT%H:%M:%f000+00:00','now'))",
    """CREATE TABLE asset_access (
        shop_id INTEGER NOT NULL REFERENCES shop_profile(id), asset_sha TEXT NOT NULL REFERENCES assets(sha256),
        role TEXT NOT NULL CHECK (role IN ('original','logo','style')), PRIMARY KEY (shop_id,asset_sha,role)
    )""",
    """CREATE TABLE product_inputs (
        id TEXT PRIMARY KEY, shop_id INTEGER NOT NULL REFERENCES shop_profile(id), product_ref TEXT NOT NULL,
        name TEXT NOT NULL, variant TEXT NOT NULL, photo_assets_json TEXT NOT NULL, facts_json TEXT NOT NULL,
        supersedes_id TEXT REFERENCES product_inputs(id), confirmed_at TEXT NOT NULL
    )""",
    """CREATE TABLE creations (
        id TEXT PRIMARY KEY, shop_id INTEGER NOT NULL REFERENCES shop_profile(id),
        parent_creation_id TEXT REFERENCES creations(id), current_revision INTEGER NOT NULL CHECK (current_revision >= 1),
        status TEXT NOT NULL CHECK (status IN ('active','abandoned')), created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    )""",
    "CREATE INDEX creations_shop_date ON creations(shop_id,created_at,id)",
    """CREATE TABLE creation_versions (
        creation_id TEXT NOT NULL REFERENCES creations(id), revision INTEGER NOT NULL CHECK (revision >= 1),
        document_json TEXT NOT NULL, document_hash TEXT NOT NULL, created_at TEXT NOT NULL,
        PRIMARY KEY (creation_id,revision)
    )""",
    """CREATE TABLE mutation_keys (
        shop_id INTEGER NOT NULL REFERENCES shop_profile(id), key TEXT NOT NULL, method TEXT NOT NULL,
        path TEXT NOT NULL, payload_sha TEXT NOT NULL, status_code INTEGER NOT NULL, response_json TEXT NOT NULL,
        created_at TEXT NOT NULL, PRIMARY KEY (shop_id,key)
    )""",
    "CREATE TRIGGER keep_shop BEFORE DELETE ON shop_profile BEGIN SELECT RAISE(ABORT,'shop cannot be deleted'); END",
]


def upgrade() -> None:
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    raise NotImplementedError("Migrations are forward-only.")
