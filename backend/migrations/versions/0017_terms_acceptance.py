"""The conditions of use, accepted by a shop (D-TERMS-002): the version of the text it last accepted and when. One record
per shop, the last acceptance (owner decision 1). The text and its version are in the code (posters/terms.py), never
here. Nothing is accepted on anyone's behalf: the pilot accepts like every shop.

Both columns are set together or not at all, never empty. No guard, and rehearse.GUARDS is unchanged: nothing here is
money or a shop's identity. A later rebuild of shop_profile must carry both columns; that migration's own rehearsal
contract is the check.
"""
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

STATEMENTS = [
    "ALTER TABLE shop_profile ADD COLUMN terms_version TEXT"
    " CHECK (terms_version IS NULL OR length(terms_version) BETWEEN 1 AND 32)",
    "ALTER TABLE shop_profile ADD COLUMN terms_accepted_at TEXT"
    " CHECK ((terms_accepted_at IS NULL) = (terms_version IS NULL) AND (terms_accepted_at IS NULL OR length(terms_accepted_at) > 0))",
]

# The rehearsal's contract (affiche.rehearse). PRESERVED: shop_profile is widened, hashed over its columns of 0013.
PRESERVED = {"shop_profile": ("id", "revision", "name", "contact", "logo_asset", "updated_at", "identifier", "password_hash",
                              "state", "created_at")}
ADDED = {
    "shop_profile: nothing accepted": (
        "SELECT count(*) FROM shop_profile WHERE terms_version IS NOT NULL OR terms_accepted_at IS NOT NULL", [(0,)]),
}


def upgrade():
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade():
    raise NotImplementedError("Migrations are forward-only.")
