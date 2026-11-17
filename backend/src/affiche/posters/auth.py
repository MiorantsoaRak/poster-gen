"""Shop credentials in the database, revocable opaque sessions, no client-supplied shop identity."""
import hashlib
import ipaddress
import logging
import re
import secrets
import threading
import unicodedata
from datetime import UTC, datetime, timedelta
from typing import NamedTuple
from urllib.parse import urlsplit

from pwdlib import PasswordHash
from pwdlib.exceptions import PwdlibError
from sqlalchemy import text

from affiche.config import ConfigError, Settings
from affiche.db import utc_now, write_tx
from affiche.posters.store import Refused

log = logging.getLogger(__name__)
PASSWORDS = PasswordHash.recommended()
COOKIE = "affiche_session"
# meta's key for the operator's Argon2 hash (D-ADMIN-001). Its only writer is shops.set_operator_password: no HTTP route.
OPERATOR_KEY = "operator_password_hash"
OPERATOR_COOKIE = "affiche_operator"  # Path=/api/admin: the browser sends it nowhere else, and only admin paths read it
OPERATOR_SECONDS = 12 * 60 * 60  # fixed from sign-in (owner decision 7)
OPERATOR_NAME = "#operator"  # its login_failures identifier: "#" is in no shop's ([a-z0-9]), so the counters never mix
# One Argon2 check takes tens of MiB. Forty worker threads verifying at once would pass the container's memory
# limit and restart it in the middle of a paid job; two at a time is plenty for one shop.
VERIFYING = threading.BoundedSemaphore(2)
SESSION_SECONDS = 90 * 24 * 60 * 60  # fixed from sign-in: no write on the path that reads a session (ADR-065)
# Failures in 15 minutes: one identifier from one address, and one address for every identifier (D-MULTI-SHOP-002).
PAIR_LIMIT, ADDRESS_LIMIT = 5, 20
# Verified when the shop is unknown or has no password, so that every sign-in costs one Argon2 verification.
DUMMY_HASH = PASSWORDS.hash(secrets.token_hex(16))


def identifier_key(identifier: str) -> str:
    """The stored identifier and the sign-in's lookup key: case, accents, spaces and punctuation do not count."""
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", identifier[:64]).lower())


def validate_config(settings: Settings):
    try:
        origin = urlsplit(settings.app_origin or "")
        hostname = origin.hostname
        loopback = hostname == "localhost"
        if hostname and not loopback:
            try:
                loopback = ipaddress.ip_address(hostname).is_loopback
            except ValueError:
                loopback = False
        valid = (hostname and not origin.username and not origin.password and not origin.path
                 and not origin.query and not origin.fragment and origin.port != 0
                 and (origin.scheme == "https" or origin.scheme == "http" and loopback)
                 and settings.app_origin == f"{origin.scheme}://{origin.netloc}")
        if not valid:
            raise ValueError()
    except ValueError:
        raise ConfigError("APP_ORIGIN must be an exact HTTPS origin (HTTP only on loopback).") from None
    secret = settings.shop_password_hash
    if secret is None:  # optional since 0013: shop 1's password is in the database (adopt_password_setting)
        return
    if not secret.get_secret_value().startswith("$argon2"):
        raise ConfigError("SHOP_PASSWORD_HASH must contain a valid Argon2 hash.")
    try:
        PASSWORDS.verify("configuration-validation-only", secret.get_secret_value())
    except (ValueError, PwdlibError):
        raise ConfigError("SHOP_PASSWORD_HASH must contain a valid Argon2 hash.") from None


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_shop(engine, token: str | None) -> int | None:
    if not token or len(token) > 128:
        return None
    with engine.connect() as conn:  # a suspended shop's sessions stop at once and work again when it is enabled
        return conn.execute(text("SELECT s.shop_id FROM sessions s JOIN shop_profile p ON p.id=s.shop_id "
                                 "WHERE s.token_hash=:hash AND s.expires_at>:now AND p.state='active'"),
                            {"hash": token_hash(token), "now": utc_now()}).scalar()


def limit_key(ip: str) -> str:
    """The address the login limit counts. One IPv6 host can rotate inside its /64, so a /64 is one client."""
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return ip
    if address.version == 4:
        return ip
    if address.ipv4_mapped:
        return str(address.ipv4_mapped)
    return str(ipaddress.ip_network(f"{address}/64", strict=False).network_address)


def adopt_password_setting(engine, settings: Settings):
    """At start (D-MULTI-SHOP-001): SHOP_PASSWORD_HASH becomes shop 1's own password once, and is not read again."""
    secret = settings.shop_password_hash.get_secret_value() if settings.shop_password_hash else None
    with write_tx(engine) as conn:
        stored = conn.execute(text("SELECT password_hash FROM shop_profile WHERE id=1")).scalar()
        fingerprint = conn.execute(text("SELECT value FROM meta WHERE key='password_fingerprint'")).scalar()
        if stored is not None:
            if secret is not None:  # stale by design after a reset by the operator: never a reason to stop
                log.warning("SHOP_PASSWORD_HASH is no longer read: shop 1 has its own password since migration 0013 "
                            "(python -m affiche.shops set-password). Remove the setting.")
        elif secret is not None:
            # The rule of the versions before 0013, applied once more: a hash other than the one last seen ends
            # every session (a lost phone, a leaked password). Every session is shop 1's here.
            if fingerprint != hashlib.sha256(secret.encode("utf-8")).hexdigest():
                conn.execute(text("DELETE FROM sessions"))
            conn.execute(text("UPDATE shop_profile SET password_hash=:hash WHERE id=1 AND password_hash IS NULL"),
                         {"hash": secret})
            conn.execute(text("DELETE FROM meta WHERE key='password_fingerprint'"))
        elif fingerprint is not None or conn.execute(text(
                "SELECT EXISTS (SELECT 1 FROM product_inputs WHERE shop_id=1)")).scalar_one():
            raise ConfigError("Shop 1 has data but no password and SHOP_PASSWORD_HASH is not set: set it to the "
                              "pilot's hash for this start, or run python -m affiche.shops set-password originalphone.")
        else:
            log.warning("shop 1 has no password: python -m affiche.shops set-password originalphone")


def limited(conn, ip: str, name: str) -> bool:
    since = (datetime.now(UTC)-timedelta(minutes=15)).isoformat(timespec="microseconds")
    pair, address = conn.execute(text("SELECT count(*) FILTER (WHERE identifier=:name), count(*) FROM login_failures "
                                      "WHERE ip=:ip AND attempted_at>:since"),
                                 {"ip": ip, "name": name, "since": since}).one()
    return pair >= PAIR_LIMIT or address >= ADDRESS_LIMIT


def login(engine, identifier: str, password: str, ip: str, previous: str | None = None) -> tuple[str, int]:
    """Returns the new session's token and its shop. An unknown identifier, a wrong password and a shop without
    password get the same answer after the same work; a suspension is told only to whoever gave the right password."""
    ip, name = limit_key(ip), identifier_key(identifier)
    with engine.connect() as conn:
        if limited(conn, ip, name):
            raise Refused("rate_limited", 429)
    # Argon2 is slow on purpose. Verified outside the write transaction: inside it, a flood of logins would hold
    # the database's write lock and stall autosaves and job commits. The slot is held until the failure or the session
    # is committed and the limits are counted again once it is held, so a request that gets a slot sees the failures of
    # every request that held one before: a burst records at most one failure past each limit, even while another
    # writer holds the database.
    with VERIFYING:
        with engine.connect() as conn:
            if limited(conn, ip, name):
                raise Refused("rate_limited", 429)
            shop = conn.execute(text("SELECT id, password_hash FROM shop_profile WHERE identifier=:name"),
                                {"name": name}).first()
        stored = shop.password_hash if shop else None
        ok, upgraded = PASSWORDS.verify_and_update(password, stored or DUMMY_HASH)
        now = datetime.now(UTC)
        stamp = now.isoformat(timespec="microseconds")
        with write_tx(engine) as conn:
            conn.execute(text("DELETE FROM login_failures WHERE attempted_at<=:since"),
                         {"since": (now-timedelta(minutes=15)).isoformat(timespec="microseconds")})
            conn.execute(text("DELETE FROM sessions WHERE expires_at<=:now"), {"now": stamp})
            # Read again in the transaction that writes: a password changed during the verification gives no session.
            state = conn.execute(text("SELECT state FROM shop_profile WHERE id=:shop AND password_hash=:stored"),
                                 {"shop": shop.id, "stored": stored}).scalar() if ok and stored is not None else None
            if state == "active":
                token = secrets.token_urlsafe(32)
                if upgraded:  # made with other Argon2 parameters than the current ones (an adopted setting)
                    conn.execute(text("UPDATE shop_profile SET password_hash=:hash WHERE id=:shop"),
                                 {"hash": upgraded, "shop": shop.id})
                if previous:
                    conn.execute(text("DELETE FROM sessions WHERE token_hash=:hash"), {"hash": token_hash(previous)})
                conn.execute(text("INSERT INTO sessions VALUES (:hash,:shop,:expires)"),
                             {"hash": token_hash(token), "shop": shop.id,
                              "expires": (now+timedelta(seconds=SESSION_SECONDS)).isoformat(timespec="microseconds")})
            elif state is None:  # recorded for an unknown identifier too: the limit behaves the same
                conn.execute(text("INSERT INTO login_failures (ip,identifier,attempted_at) VALUES (:ip,:name,:now)"),
                             {"ip": ip, "name": name, "now": stamp})
    # The failed attempt is committed before the failure is reported.
    if state is None:
        raise Refused("wrong_credentials", 401)
    if state != "active":
        raise Refused("shop_suspended", 403)
    return token, shop.id


def change_password(engine, shop: int, token: str, current: str, new: str, ip: str):
    """The owner's own change, signed in (D-MULTI-SHOP-002). The current password is verified under the sign-in's limits
    and slots, keyed by the shop's identifier, so a stolen session cannot guess it here either. This session is kept;
    the shop's other sessions end, and no other shop's."""
    if len(new) < 10:
        raise Refused("password_too_short", 422)
    ip = limit_key(ip)
    with engine.connect() as conn:
        name = conn.execute(text("SELECT identifier FROM shop_profile WHERE id=:shop"), {"shop": shop}).scalar_one()
        if limited(conn, ip, name):
            raise Refused("rate_limited", 429)
    with VERIFYING:  # as login: held until the failure or the change is committed, Argon2 outside the write
        with engine.connect() as conn:
            if limited(conn, ip, name):
                raise Refused("rate_limited", 429)
            stored = conn.execute(text("SELECT password_hash FROM shop_profile WHERE id=:shop"), {"shop": shop}).scalar()
        ok, _ = PASSWORDS.verify_and_update(current, stored or DUMMY_HASH)
        replacement = PASSWORDS.hash(new) if ok and stored is not None else None
        with write_tx(engine) as conn:
            # Only over the hash that was verified: a change made meanwhile (the operator, another device) wins.
            changed = replacement is not None and conn.execute(text(
                "UPDATE shop_profile SET password_hash=:new WHERE id=:shop AND password_hash=:stored"),
                {"new": replacement, "shop": shop, "stored": stored}).rowcount == 1
            if changed:
                conn.execute(text("DELETE FROM sessions WHERE shop_id=:shop AND token_hash<>:mine"),
                             {"shop": shop, "mine": token_hash(token)})
            else:
                conn.execute(text("INSERT INTO login_failures (ip,identifier,attempted_at) VALUES (:ip,:name,:now)"),
                             {"ip": ip, "name": name, "now": datetime.now(UTC).isoformat(timespec="microseconds")})
    if not changed:
        raise Refused("wrong_password", 403)


def logout(engine, token: str | None):
    if token:
        with write_tx(engine) as conn:
            conn.execute(text("DELETE FROM sessions WHERE token_hash=:hash"), {"hash": token_hash(token)})


class Operator(NamedTuple):
    """A live operator session (D-ADMIN-001). It holds no shop."""
    actor: str  # dashboard:<first 8 hex of the token's hash>: names a session, not a person, and tells nothing of the token
    token_hash: str
    expires_at: str


def operator_actor(digest: str) -> str:
    return f"dashboard:{digest[:8]}"


def operator_live(conn, digest: str) -> str | None:
    """The expiry of a live operator session, else None. A write calls it first inside its write_tx, where BEGIN IMMEDIATE
    already holds the lock: the time is read now, so a session ended or expired while the write waited is not live."""
    return conn.execute(text("SELECT expires_at FROM operator_sessions WHERE token_hash=:hash AND expires_at>:now"),
                        {"hash": digest, "now": utc_now()}).scalar()


def operator_session(engine, token: str | None) -> Operator | None:
    """Read on every /api/admin/ request, with no write on the read (ADR-065's rule for shops)."""
    if not token or len(token) > 128:
        return None
    digest = token_hash(token)
    with engine.connect() as conn:
        expires = operator_live(conn, digest)
    return None if expires is None else Operator(operator_actor(digest), digest, expires)


def operator_configured(engine) -> bool:
    with engine.connect() as conn:
        return conn.execute(text("SELECT EXISTS (SELECT 1 FROM meta WHERE key=:key)"), {"key": OPERATOR_KEY}).scalar_one() == 1


def operator_login(engine, password: str, ip: str, agent: str | None, previous: str | None = None) -> tuple[str, Operator]:
    """D-ADMIN-001, in the shape of login: the shops' limits under OPERATOR_NAME, Argon2 outside the write transaction in
    one of the shops' two slots, and the hash read again in the transaction that writes. Unset, the password is refused
    before any verification and nothing is counted: there is nothing to guess."""
    key = limit_key(ip)
    with engine.connect() as conn:
        stored = conn.execute(text("SELECT value FROM meta WHERE key=:key"), {"key": OPERATOR_KEY}).scalar()
        if stored is None:  # before the limits: the shops' failures from this address must not hide it
            raise Refused("operator_not_set", 409)
        if limited(conn, key, OPERATOR_NAME):
            raise Refused("rate_limited", 429)
    with VERIFYING:  # held until the failure or the session is committed, as login's
        with engine.connect() as conn:
            if limited(conn, key, OPERATOR_NAME):
                raise Refused("rate_limited", 429)
        ok = PASSWORDS.verify(password, stored)
        now = datetime.now(UTC)
        stamp = now.isoformat(timespec="microseconds")
        with write_tx(engine) as conn:
            conn.execute(text("DELETE FROM login_failures WHERE attempted_at<=:since"),
                         {"since": (now-timedelta(minutes=15)).isoformat(timespec="microseconds")})
            conn.execute(text("DELETE FROM operator_sessions WHERE expires_at<=:now"), {"now": stamp})
            # Read again in the transaction that writes: a password set during the verification gives no session.
            ok = ok and conn.execute(text("SELECT 1 FROM meta WHERE key=:key AND value=:stored"),
                                     {"key": OPERATOR_KEY, "stored": stored}).first() is not None
            if ok:
                token = secrets.token_urlsafe(32)
                expires = (now+timedelta(seconds=OPERATOR_SECONDS)).isoformat(timespec="microseconds")
                if previous:  # this browser's earlier session: a new sign-in replaces it
                    conn.execute(text("DELETE FROM operator_sessions WHERE token_hash=:hash"), {"hash": token_hash(previous)})
                conn.execute(text("INSERT INTO operator_sessions VALUES (:hash,:now,:expires,:address,:agent)"),
                             {"hash": token_hash(token), "now": stamp, "expires": expires,
                              "address": (ip or "unknown")[:64], "agent": (agent or "")[:200] or None})
            else:
                conn.execute(text("INSERT INTO login_failures (ip,identifier,attempted_at) VALUES (:ip,:name,:now)"),
                             {"ip": key, "name": OPERATOR_NAME, "now": stamp})
    if not ok:  # the failure is committed before it is reported
        raise Refused("wrong_credentials", 401)
    digest = token_hash(token)
    return token, Operator(operator_actor(digest), digest, expires)


def operator_logout(engine, token: str | None) -> str | None:
    """This browser's operator session ends; returns its actor when there was one to end."""
    if not token:
        return None
    digest = token_hash(token)
    with write_tx(engine) as conn:
        ended = conn.execute(text("DELETE FROM operator_sessions WHERE token_hash=:hash"), {"hash": digest}).rowcount
    return operator_actor(digest) if ended else None
