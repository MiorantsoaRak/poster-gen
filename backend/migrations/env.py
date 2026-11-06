from alembic import context
from alembic.util import CommandError

connection = context.config.attributes.get("connection")
if connection is None:
    # A plain engine from the alembic CLI would skip the pragmas and BEGIN IMMEDIATE of affiche.db.
    raise CommandError("Migrations run only through affiche.db.migrate(engine); the app migrates at startup.")

# The schema is plain SQL (no ORM models), so there is no metadata to autogenerate from.
context.configure(connection=connection, target_metadata=None)
with context.begin_transaction():
    context.run_migrations()
