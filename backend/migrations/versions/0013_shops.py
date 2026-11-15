"""Several shops (D-MULTI-SHOP-001): the shop table without its single-row rule and with each shop's identity, the
read ledger's key unique per shop, login failures that can name an identifier.

Both rebuilds follow SQLite's procedure for changing a table (new table, copy, drop, rename) with the foreign keys
off, which affiche.db.migrate does around every migration before checking every reference. The pilot stays shop 1
with every row of every table. Its password comes from SHOP_PASSWORD_HASH at the first start
(auth.adopt_password_setting): the migration reads no environment.
"""
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

STATEMENTS = [
    "DROP TRIGGER keep_shop",
    """CREATE TABLE shop_profile_new (
        id INTEGER PRIMARY KEY, revision INTEGER NOT NULL CHECK (revision >= 1),
        name TEXT, contact TEXT, logo_asset TEXT REFERENCES assets(sha256), updated_at TEXT NOT NULL,
        identifier TEXT NOT NULL UNIQUE CHECK (length(identifier) BETWEEN 3 AND 32 AND identifier NOT GLOB '*[^a-z0-9]*'),
        password_hash TEXT CHECK (password_hash IS NULL OR password_hash LIKE '$argon2%'),
        state TEXT NOT NULL CHECK (state IN ('active','suspended')),
        created_at TEXT NOT NULL
    )""",
    # The pilot's identifier; another one later is a new migration, never an edit of this one.
    """INSERT INTO shop_profile_new (id,revision,name,contact,logo_asset,updated_at,identifier,password_hash,state,created_at)
        SELECT id,revision,name,contact,logo_asset,updated_at,'originalphone',NULL,'active',
               COALESCE((SELECT min(created_at) FROM creations),updated_at) FROM shop_profile""",
    "DROP TABLE shop_profile",
    "ALTER TABLE shop_profile_new RENAME TO shop_profile",  # the children's REFERENCES shop_profile(id) hold again
    "CREATE TRIGGER keep_shop BEFORE DELETE ON shop_profile BEGIN SELECT RAISE(ABORT,'shop cannot be deleted'); END",
    """CREATE TABLE chat_reads_new (
        id TEXT PRIMARY KEY,
        shop_id INTEGER NOT NULL REFERENCES shop_profile(id),
        creation_id TEXT REFERENCES creations(id),
        key TEXT NOT NULL,
        payload_sha TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed', 'interrupted')),
        provider TEXT NOT NULL, model TEXT NOT NULL, rate_card_json TEXT NOT NULL,
        cost_micros INTEGER NOT NULL,
        cost_is_estimate INTEGER NOT NULL,
        usage_json TEXT, provider_request_id TEXT,
        response_json TEXT,
        created_at TEXT NOT NULL, finished_at TEXT,
        UNIQUE (shop_id, key)
    )""",
    """INSERT INTO chat_reads_new (id,shop_id,creation_id,key,payload_sha,status,provider,model,rate_card_json,
        cost_micros,cost_is_estimate,usage_json,provider_request_id,response_json,created_at,finished_at)
        SELECT id,shop_id,creation_id,key,payload_sha,status,provider,model,rate_card_json,
        cost_micros,cost_is_estimate,usage_json,provider_request_id,response_json,created_at,finished_at FROM chat_reads""",
    "DROP TABLE chat_reads",
    "ALTER TABLE chat_reads_new RENAME TO chat_reads",
    "CREATE INDEX chat_reads_created ON chat_reads (created_at)",
    "ALTER TABLE login_failures ADD COLUMN identifier TEXT",  # NULL on older rows: they count for the address only
    "CREATE INDEX login_failures_identifier ON login_failures(identifier,ip,attempted_at)",
    "CREATE INDEX poster_jobs_shop_started ON poster_jobs(shop_id,started_at)",  # the fair queue (D-MULTI-SHOP-005)
]

# The rehearsal's contract (affiche.rehearse). PRESERVED: the tables this migration rebuilds or widens, hashed over
# the columns they had before it; every other table keeps every column of every row.
PRESERVED = {
    "shop_profile": ("id", "revision", "name", "contact", "logo_asset", "updated_at"),
    "chat_reads": ("id", "shop_id", "creation_id", "key", "payload_sha", "status", "provider", "model", "rate_card_json",
                   "cost_micros", "cost_is_estimate", "usage_json", "provider_request_id", "response_json",
                   "created_at", "finished_at"),
    "login_failures": ("id", "ip", "attempted_at"),
}
# ADDED: what it changes on purpose, as a query and the exact rows it must give after it.
ADDED = {
    "shop_profile: shop 1 is originalphone, active, without password, created with its first poster": (
        "SELECT id, identifier, password_hash, state,"
        " created_at IS COALESCE((SELECT min(created_at) FROM creations), updated_at) FROM shop_profile",
        [(1, "originalphone", None, "active", 1)]),
    "shop_profile: its rows still cannot be deleted": (
        "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='shop_profile'", [("keep_shop",)]),
    "login_failures: no row of before names an identifier": (
        "SELECT count(*) FROM login_failures WHERE identifier IS NOT NULL", [(0,)]),
    "chat_reads: the key is unique per shop, not for the whole service": (
        "SELECT il.origin, ii.seqno, ii.name FROM pragma_index_list('chat_reads') il, pragma_index_info(il.name) ii"
        " WHERE il.\"unique\" ORDER BY il.origin, ii.seqno",
        [("pk", 0, "id"), ("u", 0, "shop_id"), ("u", 1, "key")]),
    "indexes: chat_reads_created, login_failures_identifier, poster_jobs_shop_started": (
        "SELECT m.name, ii.seqno, ii.name FROM sqlite_master m, pragma_index_info(m.name) ii WHERE m.type='index'"
        " AND m.name IN ('chat_reads_created','login_failures_identifier','poster_jobs_shop_started')"
        " ORDER BY m.name, ii.seqno",
        [("chat_reads_created", 0, "created_at"), ("login_failures_identifier", 0, "identifier"),
         ("login_failures_identifier", 1, "ip"), ("login_failures_identifier", 2, "attempted_at"),
         ("poster_jobs_shop_started", 0, "shop_id"), ("poster_jobs_shop_started", 1, "started_at")]),
}


def upgrade():
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade():
    raise NotImplementedError("Migrations are forward-only.")
