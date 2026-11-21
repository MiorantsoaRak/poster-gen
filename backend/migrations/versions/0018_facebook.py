"""Publishing on the shop's Facebook Page (D-FB-PUBLISH-001): the shop's Page, its one attempt to connect, and its
publications. A Page's token is stored as Facebook gave it: every call carries appsecret_proof, so a copy of the
database cannot use it without the Meta app's secret, which is in the server's environment only.

No guard, and rehearse.GUARDS is unchanged: nothing here is money or a shop's identity. A publication is a row before
anything is sent; its status changes only by the route that sent it, by the owner's word or at the server's start.
"""
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None

STATEMENTS = [
    # One Page per shop. The token is never returned by a route.
    """CREATE TABLE facebook_pages (
  shop_id INTEGER PRIMARY KEY REFERENCES shop_profile(id),
  page_id TEXT NOT NULL, page_name TEXT NOT NULL, token TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('connected','reconnect')),
  connected_at TEXT NOT NULL
)""",
    # The shop's one attempt to connect, at most. state_sha: SHA-256 of the dialog's `state`, the value itself is stored
    # nowhere; session_sha: only the session that began it goes on with it; pages_json, at 'choice': the Pages allowed,
    # each with its token, gone with the row.
    """CREATE TABLE facebook_connects (
  shop_id INTEGER PRIMARY KEY REFERENCES shop_profile(id),
  state_sha TEXT NOT NULL,
  session_sha TEXT NOT NULL,
  step TEXT NOT NULL CHECK (step IN ('dialog','exchange','choice')),
  pages_json TEXT,
  created_at TEXT NOT NULL
)""",
    # The design's block has UNIQUE (shop_id, key) beside `key`: SQLite takes a table constraint only after the columns.
    # NOT NULL on id: SQLite lets a NULL into a primary key that is not an integer one.
    """CREATE TABLE facebook_publications (
  id TEXT PRIMARY KEY NOT NULL, shop_id INTEGER NOT NULL REFERENCES shop_profile(id),
  creation_id TEXT NOT NULL, confirmation_id TEXT NOT NULL,
  page_id TEXT NOT NULL, page_name TEXT NOT NULL, caption TEXT NOT NULL,
  key TEXT NOT NULL, payload_sha TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('sending','published','failed','unknown')),
  sent_at TEXT NOT NULL, settled_at TEXT,
  post_id TEXT, link TEXT, error_code TEXT, said_by_owner INTEGER NOT NULL DEFAULT 0,
  UNIQUE (shop_id, key)
)""",
]

# The rehearsal's contract (affiche.rehearse). PRESERVED: no table is rebuilt or widened.
PRESERVED = {}
ADDED = {
    "facebook_pages: empty": ("SELECT count(*) FROM facebook_pages", [(0,)]),
    "facebook_connects: empty": ("SELECT count(*) FROM facebook_connects", [(0,)]),
    "facebook_publications: empty": ("SELECT count(*) FROM facebook_publications", [(0,)]),
}


def upgrade():
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade():
    raise NotImplementedError("Migrations are forward-only.")
