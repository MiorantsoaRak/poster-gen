"""The operator's actions on shops (D-MULTI-SHOP-003). Each function takes a connection and never commits: the caller
holds the transaction (write_tx), so that a later record of the action can join it. Passwords are hashed by the
caller, outside the transaction."""
from sqlalchemy import Connection, text


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
