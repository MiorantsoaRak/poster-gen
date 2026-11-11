"""Immutable scene plans and reviewable integrated visuals."""
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

STATEMENTS = [
    """CREATE TABLE scene_plans (
        id TEXT PRIMARY KEY, shop_id INTEGER NOT NULL REFERENCES shop_profile(id),
        creation_id TEXT NOT NULL, origin_revision INTEGER NOT NULL,
        input_id TEXT NOT NULL REFERENCES product_inputs(id), job_id TEXT UNIQUE REFERENCES poster_jobs(id),
        parent_plan_id TEXT REFERENCES scene_plans(id),
        source TEXT NOT NULL CHECK (source IN ('fixed','manual','claude','stub')),
        format TEXT NOT NULL CHECK (format IN ('feed','square','story')),
        context_json TEXT NOT NULL, plan_json TEXT NOT NULL, prompt_text TEXT NOT NULL, prompt_hash TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (creation_id,origin_revision) REFERENCES creation_versions(creation_id,revision)
    )""",
    """CREATE TABLE poster_visuals (
        id TEXT PRIMARY KEY, shop_id INTEGER NOT NULL REFERENCES shop_profile(id),
        input_id TEXT NOT NULL REFERENCES product_inputs(id), job_id TEXT NOT NULL UNIQUE REFERENCES poster_jobs(id),
        base_visual_id TEXT REFERENCES poster_visuals(id),
        treatment TEXT NOT NULL CHECK (treatment IN ('scene','photo_preserved')),
        status TEXT NOT NULL CHECK (status IN ('pending_review','approved','rejected')),
        image_asset TEXT REFERENCES assets(sha256), background_asset TEXT REFERENCES assets(sha256),
        cutout_asset TEXT REFERENCES assets(sha256), placement_json TEXT,
        source_assets_json TEXT NOT NULL, reference_roles_json TEXT NOT NULL,
        plan_id TEXT REFERENCES scene_plans(id), prompt_text TEXT NOT NULL, prompt_hash TEXT NOT NULL,
        direction_json TEXT NOT NULL, model TEXT NOT NULL, quality TEXT NOT NULL, size TEXT NOT NULL,
        low_res_ack INTEGER NOT NULL CHECK (low_res_ack IN (0,1)), checks_json TEXT NOT NULL DEFAULT '{}',
        rejection_reasons_json TEXT, rejection_note TEXT, created_at TEXT NOT NULL, decided_at TEXT,
        CHECK ((treatment='scene' AND image_asset IS NOT NULL) OR
               (treatment='photo_preserved' AND background_asset IS NOT NULL AND cutout_asset IS NOT NULL AND placement_json IS NOT NULL))
    )""",
    "CREATE INDEX poster_visual_input ON poster_visuals(shop_id,input_id,created_at)",
]


def upgrade():
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade():
    raise NotImplementedError("Migrations are forward-only.")
