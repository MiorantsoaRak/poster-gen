"""The operator's actions on shops (D-MULTI-SHOP-003). Each function takes a connection and never commits: the caller
holds the transaction (write_tx), so that a later record of the action can join it. Passwords are hashed by the
caller, outside the transaction."""
from sqlalchemy import Connection, text

from affiche.db import utc_now
from affiche.posters.auth import identifier_key
from affiche.posters.models import Profile


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
