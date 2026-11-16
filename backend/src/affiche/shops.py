"""The operator's actions on shops (D-MULTI-SHOP-003). Each function takes a connection and never commits: the caller
holds the transaction (write_tx), so that a later record of the action can join it. Passwords are hashed by the
caller, outside the transaction.

    python -m affiche.shops list
    python -m affiche.shops create <identifier> [--name "Nom affiché"]   prints the password once
    python -m affiche.shops set-password <identifier>                     prints the new password once; ends its sessions
    python -m affiche.shops end-sessions (<identifier> | --all)
    python -m affiche.shops suspend <identifier> --yes                    without --yes, only shows the shop
    python -m affiche.shops enable <identifier>

The command reads the data folder from the settings, as the other commands do, and never migrates: it refuses unless
the database is at this code's head. It takes no lock, so it runs beside the API. Exit 0 done, 1 refused (one line on
stderr, nothing written), 2 usage.
"""
import argparse
import secrets
import sys
from collections.abc import Sequence
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from pydantic import ValidationError
from sqlalchemy import Connection, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from affiche.config import BACKEND_DIR, ENV_FILE, ConfigError, load_settings
from affiche.db import make_engine, utc_now, write_tx
from affiche.posters import jobs
from affiche.posters.auth import PASSWORDS, identifier_key
from affiche.posters.models import Profile

# No 0/o, 1/l/i: read aloud and typed on a phone. Twelve of them: about 59 bits.
ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"


def new_password() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(12))


def find_shop(conn: Connection, identifier: str):
    """The shop of an identifier in any spelling (identifier_key), or None."""
    return conn.execute(text("SELECT id, identifier, name, state FROM shop_profile WHERE identifier=:key"),
                        {"key": identifier_key(identifier)}).first()


def list_shops(conn: Connection) -> list:
    """Whether a shop has a password, never its hash: shop 1 has none after a backup from before 0013 is restored."""
    return conn.execute(text("SELECT id, identifier, name, state, created_at, password_hash IS NOT NULL AS has_password"
                             " FROM shop_profile ORDER BY id")).all()


def create_shop(conn: Connection, identifier: str, name: str | None, password_hash: str) -> int:
    """An active shop; its identifier is stored normalised, so the UNIQUE column refuses one taken in any spelling
    (IntegrityError). Returns its id."""
    key = identifier_key(identifier)
    if not 3 <= len(key) <= 32:
        raise ValueError("an identifier needs 3 to 32 letters or digits")
    now = utc_now()
    return conn.execute(text("INSERT INTO shop_profile (revision,name,updated_at,identifier,password_hash,state,created_at)"
                             " VALUES (1,:name,:now,:identifier,:hash,'active',:now) RETURNING id"),
                        {"name": Profile(name=name).name, "now": now, "identifier": key, "hash": password_hash}).scalar_one()


def set_password(conn: Connection, shop_id: int, password_hash: str) -> None:
    """A new password ends every session of that shop, and no other shop's."""
    if conn.execute(text("UPDATE shop_profile SET password_hash=:hash WHERE id=:shop"),
                    {"hash": password_hash, "shop": shop_id}).rowcount != 1:
        raise LookupError(f"no shop {shop_id}")
    end_sessions(conn, shop_id)


def end_sessions(conn: Connection, shop_id: int | None = None) -> int:
    """One shop's sessions, or every shop's (after a backup is restored). Returns how many ended."""
    if shop_id is None:
        return conn.execute(text("DELETE FROM sessions")).rowcount
    return conn.execute(text("DELETE FROM sessions WHERE shop_id=:shop"), {"shop": shop_id}).rowcount


def _state(conn: Connection, shop_id: int) -> str:
    state = conn.execute(text("SELECT state FROM shop_profile WHERE id=:shop"), {"shop": shop_id}).scalar()
    if state is None:
        raise LookupError(f"no shop {shop_id}")
    return state


def suspend(conn: Connection, shop_id: int) -> int | None:
    """D-MULTI-SHOP-006: its queued jobs are cancelled, their reserved calls released at cost 0. Its sessions are kept:
    the session read requires an active shop, so they stop at once and work again after enable. A call already reserved
    by a running job is cut where it is sent (jobs.dispatch, reads._send). Returns how many jobs were cancelled, or None
    when the shop was already suspended (nothing changed)."""
    if _state(conn, shop_id) == "suspended":
        return None
    conn.execute(text("UPDATE shop_profile SET state='suspended' WHERE id=:shop"), {"shop": shop_id})
    queued = conn.execute(text("SELECT id FROM poster_jobs WHERE shop_id=:shop AND status='queued'"),
                          {"shop": shop_id}).scalars().all()
    now = utc_now()
    for id in queued:
        jobs.cancel_queued(conn, id, now, "shop_suspended")
    return len(queued)


def enable(conn: Connection, shop_id: int) -> bool:
    """Data, profile, ledger and sessions were never touched; cancelled jobs stay cancelled. False: it was active."""
    if _state(conn, shop_id) == "active":
        return False
    conn.execute(text("UPDATE shop_profile SET state='active' WHERE id=:shop"), {"shop": shop_id})
    return True


class Refusal(Exception):
    """One line for the operator; nothing was written."""


def _shop(engine, identifier: str):
    with engine.connect() as conn:
        shop = find_shop(conn, identifier)
    if shop is None:
        raise Refusal(f"no shop has the identifier {identifier_key(identifier) or repr(identifier)}")
    return shop


def _named(shop) -> str:
    return f"{shop.identifier} (shop {shop.id}, « {shop.name or 'sans nom'} »)"


def _list(engine, _args):
    with engine.connect() as conn:
        for shop in list_shops(conn):
            print(f"{shop.id}\t{shop.identifier}\t{shop.state}\t{'password' if shop.has_password else 'no password'}"
                  f"\t{shop.created_at[:10]}\t{shop.name or ''}")


def _create(engine, args):
    password = new_password()
    password_hash = PASSWORDS.hash(password)  # Argon2 is slow on purpose: never inside the write transaction
    try:
        with write_tx(engine) as conn:
            id = create_shop(conn, args.identifier, args.name, password_hash)
    except IntegrityError:
        raise Refusal(f"the identifier {identifier_key(args.identifier)} is already taken") from None
    print(f"shop {id} created: identifier {identifier_key(args.identifier)}, active\n"
          f"password (shown once, give it to the owner in person): {password}")


def _set_password(engine, args):
    shop = _shop(engine, args.identifier)
    password = new_password()
    password_hash = PASSWORDS.hash(password)
    with write_tx(engine) as conn:
        set_password(conn, shop.id, password_hash)
    print(f"new password for {_named(shop)}; every session of this shop ended\n"
          f"password (shown once, give it to the owner in person): {password}")


def _end_sessions(engine, args):
    shop = None if args.all else _shop(engine, args.identifier)
    with write_tx(engine) as conn:
        ended = end_sessions(conn, None if shop is None else shop.id)
    print(f"{ended} sessions ended ({'every shop' if shop is None else _named(shop)})")


def _suspend(engine, args):
    shop = _shop(engine, args.identifier)
    if not args.yes:
        print(f"{_named(shop)}: {shop.state}")
        raise Refusal(f"nothing done: to suspend {shop.identifier}, run again with --yes")
    with write_tx(engine) as conn:
        cancelled = suspend(conn, shop.id)
    if cancelled is None:
        print(f"{_named(shop)} was already suspended: nothing changed")
    else:
        print(f"{_named(shop)} suspended: its sessions stop working (kept, they work again after enable); "
              f"{cancelled} queued jobs cancelled at no cost")


def _enable(engine, args):
    shop = _shop(engine, args.identifier)
    with write_tx(engine) as conn:
        changed = enable(conn, shop.id)
    print(f"{_named(shop)} {'enabled: its sessions work again' if changed else 'was already active: nothing changed'}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m affiche.shops",
        description="The operator's shop commands (D-MULTI-SHOP-003). Never migrates: the database must be at this "
                    "code's head. Exit codes: 0 done; 1 refused, nothing written; 2 usage.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="every shop: id, identifier, state, password or not, created, name").set_defaults(
        handler=_list)
    create = commands.add_parser("create", help="a new active shop; prints its password once")
    create.add_argument("identifier", help="3 to 32 letters or digits once case, accents, spaces and punctuation go")
    create.add_argument("--name", help="the shop's displayed name (the owner can change it)")
    create.set_defaults(handler=_create)
    reset = commands.add_parser("set-password", help="a new password, printed once; ends that shop's sessions")
    reset.add_argument("identifier")
    reset.set_defaults(handler=_set_password)
    end = commands.add_parser("end-sessions", help="sign one shop, or every shop (after a restore), out everywhere")
    whom = end.add_mutually_exclusive_group(required=True)
    whom.add_argument("identifier", nargs="?")
    whom.add_argument("--all", action="store_true")
    end.set_defaults(handler=_end_sessions)
    stop = commands.add_parser("suspend", help="stop a shop; enable reverses it. Without --yes, only shows the shop")
    stop.add_argument("identifier")
    stop.add_argument("--yes", action="store_true")
    stop.set_defaults(handler=_suspend)
    start = commands.add_parser("enable", help="a suspended shop works again, with its sessions")
    start.add_argument("identifier")
    start.set_defaults(handler=_enable)
    return parser


def main(argv: Sequence[str] | None = None, env_file: Path | None = ENV_FILE) -> int:
    args = build_parser().parse_args(argv)  # a usage error exits 2 here
    engine = None
    try:
        database = load_settings(env_file).data_dir / "affiche.db"
        if not database.is_file():  # make_engine would create an empty one
            raise Refusal(f"no database at {database}: start the application once")
        engine = make_engine(database.parent)
        with engine.connect() as conn:
            version = MigrationContext.configure(conn).get_current_revision()
        head = ScriptDirectory.from_config(Config(BACKEND_DIR / "alembic.ini")).get_current_head()
        if version != head:
            raise Refusal(f"the database is at {version}, this code expects {head}: start the application of this "
                          "version once; this command never migrates")
        args.handler(engine, args)
        return 0
    except (Refusal, ConfigError, LookupError) as error:
        message = str(error)
    except ValidationError as error:  # the profile's own rule on the name
        message = f"name: {error.errors()[0]['msg']}"
    except ValueError as error:
        message = str(error)
    except SQLAlchemyError as error:  # the driver's message only: the statement's parameters may hold a hash
        message = str(getattr(error, "orig", None) or type(error).__name__)
    finally:
        if engine is not None:
            engine.dispose()
    print(f"refused: {message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
