"""A Facebook post of one or several posters (D-FB-POST-001): the operator's limit of images per post, the posts and
their images. Beside 0018's facebook_publications, which this migration leaves as it is: 0020 turns its rows into posts
and drops it, with the code that replaces it.

A post's images are uploaded unpublished, one by one (`photo_id`), then one call publishes them. An image holds no
foreign key to its poster or its confirmation: a post keeps its line when a poster is gone, and a restore can bring a
post whose poster it lacks. `png_sha256` is NULL only on an image converted by 0020 from a publication whose confirmation
was not there; a new image always has it. A post's order among posts is its rowid.

No guard, and rehearse.GUARDS is unchanged: nothing here is money or a shop's identity. A later rebuild of shop_profile
must carry post_image_limit with its CHECK; that migration's own rehearsal contract is the check.
"""
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None

STATEMENTS = [
    # NULL is no limit, the default (R-FB-POST-003).
    "ALTER TABLE shop_profile ADD COLUMN post_image_limit INTEGER"
    " CHECK (post_image_limit IS NULL OR post_image_limit >= 1)",
    """CREATE TABLE facebook_posts (
  id TEXT PRIMARY KEY NOT NULL,
  shop_id INTEGER NOT NULL REFERENCES shop_profile(id),
  page_id TEXT NOT NULL, page_name TEXT NOT NULL,
  description TEXT NOT NULL,
  key TEXT NOT NULL, payload_sha TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('uploading','posting','published','failed','unknown')),
  stop_asked INTEGER NOT NULL DEFAULT 0,
  sent_at TEXT NOT NULL, settled_at TEXT,
  post_id TEXT, link TEXT, error_code TEXT, failed_position INTEGER,
  said_by_owner INTEGER NOT NULL DEFAULT 0,
  UNIQUE (shop_id, key)
)""",
    """CREATE TABLE facebook_post_items (
  post_id TEXT NOT NULL REFERENCES facebook_posts(id),
  position INTEGER NOT NULL CHECK (position >= 0),
  creation_id TEXT NOT NULL, confirmation_id TEXT NOT NULL, png_sha256 TEXT,
  photo_id TEXT,
  PRIMARY KEY (post_id, position),
  UNIQUE (post_id, creation_id)
)""",
    "CREATE INDEX facebook_post_items_creation ON facebook_post_items (creation_id)",
]

# The rehearsal's contract (affiche.rehearse). PRESERVED: shop_profile is widened, hashed over its columns of 0018.
PRESERVED = {"shop_profile": ("id", "revision", "name", "contact", "logo_asset", "updated_at", "identifier", "password_hash",
                              "state", "created_at", "terms_version", "terms_accepted_at")}
ADDED = {
    "shop_profile: no limit of images per post": (
        "SELECT count(*) FROM shop_profile WHERE post_image_limit IS NOT NULL", [(0,)]),
    "facebook_posts: empty": ("SELECT count(*) FROM facebook_posts", [(0,)]),
    "facebook_post_items: empty": ("SELECT count(*) FROM facebook_post_items", [(0,)]),
}


def upgrade():
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade():
    raise NotImplementedError("Migrations are forward-only.")
