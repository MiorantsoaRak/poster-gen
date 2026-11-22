"""One way to publish on a Page (ADR-129, D-FB-POST-001): every publication of one poster (0018's table) becomes a post
of one image, then the table goes. A drop in a new forward migration: 0018 is not edited. Released with 0018 and 0019,
so a released database converts nothing; the rehearsal refuses a database whose table holds rows (DROPS below).

The conversion loses nothing. Each publication keeps its id, shop, Page, key, dates and settlement; its caption is the
post's description; `sending` becomes `posting` (its last call may have left), which the API's start then makes
`unknown`, as it made a `sending` row: so a publication whose outcome nobody knows still blocks its poster on its Page
until the owner says. Its one image is at position 0; the left join keeps a publication whose confirmation is not here
(a restore can bring one), whose image then has no `png_sha256`: the only image without one. The migration counts the
posts and images it made against the rows before the drop, and raises when they differ: every migration runs in one
transaction (affiche.db.migrate), so nothing of it is then applied.

`payload_sha` is copied as the single poster's module made it, so it never equals what facebook_posts._digest makes:
the same key sent again with the same body would be refused (`idempotency_reused`) instead of answered. That cannot
happen: the key was a final panel's sheet's, and the release that applies this migration replaces that sheet.

No guard, and rehearse.GUARDS is unchanged: nothing here is money or a shop's identity.
"""
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None

STATEMENTS = [
    # In the written order (rowid): a post's order among posts is its rowid (D-FB-POST-001).
    """INSERT INTO facebook_posts (id, shop_id, page_id, page_name, description, key, payload_sha, status, sent_at,
                            settled_at, post_id, link, error_code, said_by_owner)
  SELECT id, shop_id, page_id, page_name, caption, key, payload_sha,
         CASE status WHEN 'sending' THEN 'posting' ELSE status END,
         sent_at, settled_at, post_id, link, error_code, said_by_owner FROM facebook_publications ORDER BY rowid""",
    """INSERT INTO facebook_post_items (post_id, position, creation_id, confirmation_id, png_sha256)
  SELECT p.id, 0, p.creation_id, p.confirmation_id, k.png_sha256 FROM facebook_publications p
  LEFT JOIN confirmations k ON k.id = p.confirmation_id ORDER BY p.rowid""",
]
COUNTS = """SELECT (SELECT count(*) FROM facebook_publications),
  (SELECT count(*) FROM facebook_posts WHERE id IN (SELECT id FROM facebook_publications)),
  (SELECT count(*) FROM facebook_post_items WHERE position = 0 AND post_id IN (SELECT id FROM facebook_publications))"""

# The rehearsal's contract (affiche.rehearse). PRESERVED: no table is rebuilt or widened. DROPS: the table this migration
# drops, which must be empty before it: 0018, 0019 and 0020 are released together, so no released database holds a
# publication; the conversion above is for development data only, which the rehearsal refuses. Every other table is
# compared as always, the posts' two included.
PRESERVED = {}
DROPS = ("facebook_publications",)
# 0018's check reads the table this migration drops, and is checked at the head, after every pending migration.
SUPERSEDES = {("0018", "facebook_publications: empty")}
ADDED = {
    "facebook_publications: gone": (
        "SELECT count(*) FROM sqlite_master WHERE name = 'facebook_publications'", [(0,)]),
}


def upgrade():
    for statement in STATEMENTS:
        op.execute(statement)
    rows, posts, items = op.get_bind().exec_driver_sql(COUNTS).one()
    if not rows == posts == items:
        raise RuntimeError(f"migration 0020: {rows} publications, {posts} posts and {items} images made of them; "
                           "nothing was applied")
    op.execute("DROP TABLE facebook_publications")


def downgrade():
    raise NotImplementedError("Migrations are forward-only.")
