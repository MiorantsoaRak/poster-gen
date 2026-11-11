"""Durable poster queue and shared-budget calls (ADR-034)."""
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

STATEMENTS = [
    """CREATE TABLE poster_jobs (
        id TEXT PRIMARY KEY, shop_id INTEGER NOT NULL REFERENCES shop_profile(id),
        creation_id TEXT NOT NULL, origin_revision INTEGER NOT NULL,
        input_id TEXT NOT NULL REFERENCES product_inputs(id),
        kind TEXT NOT NULL CHECK (kind IN ('plan','scene','refine','text_patch','text_texture','render','cutout','background')),
        input_json TEXT NOT NULL, input_hash TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('queued','running','succeeded','failed','interrupted','cancelled')),
        result_ref TEXT, error_code TEXT, created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT,
        recovery_count INTEGER NOT NULL DEFAULT 0 CHECK (recovery_count IN (0,1)),
        FOREIGN KEY (creation_id,origin_revision) REFERENCES creation_versions(creation_id,revision)
    )""",
    "CREATE INDEX poster_queue ON poster_jobs(status,created_at,id)",
    """CREATE UNIQUE INDEX poster_one_image ON poster_jobs(creation_id)
        WHERE kind IN ('scene','refine','text_texture','background') AND status IN ('queued','running')""",
    """CREATE TABLE poster_calls (
        id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES poster_jobs(id),
        call_no INTEGER NOT NULL CHECK (call_no IN (1,2)),
        provider TEXT NOT NULL CHECK (provider IN ('stub','openai','claude')), model TEXT NOT NULL,
        rate_card_json TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('reserved','running','succeeded','failed','interrupted','cancelled')),
        cost_micros INTEGER NOT NULL CHECK (cost_micros >= 0),
        cost_is_estimate INTEGER NOT NULL CHECK (cost_is_estimate IN (0,1)),
        usage_json TEXT, provider_request_id TEXT,
        created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT,
        UNIQUE(job_id,call_no)
    )""",
    "CREATE INDEX poster_call_spend ON poster_calls(created_at)",
]


def upgrade():
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade():
    raise NotImplementedError("Migrations are forward-only.")
