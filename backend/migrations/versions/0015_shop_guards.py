"""A shop is never replaced (T-SHOP-REPLACE): only keep_shop guarded shop_profile, and a REPLACE's implicit delete fires
no DELETE trigger while recursive_triggers is off. INSERT OR REPLACE at an existing id gave a new identifier the old
shop's posters, jobs and credits, with foreign keys on; an UPDATE of the id moved them away with foreign keys off.

A shop's id never changes. Its identifier may (multi-shop design: the pilot's, by a later migration), never to one that
another shop holds. The two triggers are rehearse.GUARDS, with keep_shop; their SQL holds no comment, so that the text
SQLite keeps is the guard's text.
"""
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

STATEMENTS = [
    # A BEFORE INSERT trigger runs before REPLACE's delete and before an upsert's DO UPDATE: refuse the collision there,
    # on every unique key (a new one must join). id is the rowid; an automatic one reads -1 here, so a shop written by hand
    # at id -1 would refuse every later creation (failed closed, as 0014's job rowid -1): no code writes an id.
    """CREATE TRIGGER shop_profile_never_replaced BEFORE INSERT ON shop_profile
  WHEN EXISTS (SELECT 1 FROM shop_profile WHERE id = NEW.id OR identifier = NEW.identifier)
  BEGIN SELECT RAISE(ABORT, 'a shop is never replaced'); END""",
    # With the id fixed and no identifier taken from another row, an UPDATE OR REPLACE collides with nothing.
    """CREATE TRIGGER shop_profile_same_shop BEFORE UPDATE ON shop_profile
  WHEN NEW.id IS NOT OLD.id
    OR (NEW.identifier IS NOT OLD.identifier AND EXISTS (SELECT 1 FROM shop_profile WHERE identifier = NEW.identifier))
  BEGIN SELECT RAISE(ABORT, 'a shop stays the same shop: its id never changes and it never takes another shop''s identifier'); END""",
]

# The rehearsal's contract (affiche.rehearse). PRESERVED: no table is rebuilt or widened.
PRESERVED = {}
# ADDED, and the one check of 0013 it retires: that one counted keep_shop alone, and a release from 0012 runs both
# migrations before any check.
SUPERSEDES = {("0013", "shop_profile: its rows still cannot be deleted")}
ADDED = {
    "shop_profile: its rows cannot be deleted, replaced or made another shop": (
        "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='shop_profile' ORDER BY name",
        [("keep_shop",), ("shop_profile_never_replaced",), ("shop_profile_same_shop",)]),
}


def upgrade():
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade():
    raise NotImplementedError("Migrations are forward-only.")
