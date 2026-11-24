"""The shop's own lines (D-KIT-005): up to three conditions of sale (« Garantie 6 mois », « Paiement Mvola ») that a
scene may draw. A JSON array of strings, empty for every shop until its owner types them; their rule is the API's
(plans.screen_shop_line), the column only refuses what is not an array. A line exists only as words drawn by the image
model: a version keeps the lines it drew in its job's payload, never here.

No guard, and rehearse.GUARDS is unchanged: nothing here is money or a shop's identity. A later rebuild of shop_profile
must carry lines_json with its CHECK; that migration's own rehearsal contract is the check.
"""
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None

STATEMENTS = [
    "ALTER TABLE shop_profile ADD COLUMN lines_json TEXT NOT NULL DEFAULT '[]'"
    " CHECK (json_valid(lines_json) AND json_type(lines_json) = 'array')",
]

# The rehearsal's contract (affiche.rehearse). PRESERVED: shop_profile is widened, hashed over its columns of 0020.
PRESERVED = {"shop_profile": ("id", "revision", "name", "contact", "logo_asset", "updated_at", "identifier", "password_hash",
                              "state", "created_at", "terms_version", "terms_accepted_at", "post_image_limit")}
ADDED = {
    "shop_profile: no line yet": ("SELECT count(*) FROM shop_profile WHERE lines_json <> '[]'", [(0,)]),
}


def upgrade():
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade():
    raise NotImplementedError("Migrations are forward-only.")
