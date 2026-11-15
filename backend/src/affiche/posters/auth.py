"""Shop credentials in the database, revocable opaque sessions, no client-supplied shop identity."""
import hashlib
import ipaddress
import logging
import secrets
import threading
from datetime import UTC, datetime, timedelta
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
# One Argon2 check takes tens of MiB. Forty worker threads verifying at once would pass the container's memory
# limit and restart it in the middle of a paid job; two at a time is plenty for one shop.
VERIFYING = threading.BoundedSemaphore(2)
SESSION_SECONDS = 90 * 24 * 60 * 60  # fixed from sign-in: no write on the path that reads a session (ADR-065)


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
    with engine.connect() as conn:
        return conn.execute(text("SELECT shop_id FROM sessions WHERE token_hash=:hash AND expires_at>:now"),
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


def login(engine, password: str, ip: str, previous: str | None = None) -> str:
    now = datetime.now(UTC)
    since = (now-timedelta(minutes=15)).isoformat(timespec="microseconds")
    ip = limit_key(ip)
    with engine.connect() as conn:
        failures = conn.execute(text("SELECT count(*) FROM login_failures WHERE ip=:ip AND attempted_at>:since"),
                                {"ip": ip, "since": since}).scalar_one()
        stored = conn.execute(text("SELECT password_hash FROM shop_profile WHERE id=1")).scalar()
    if failures >= 5:
        raise Refused("rate_limited", 429)
    # Argon2 is slow on purpose. Verified outside the write transaction: inside it, a flood of logins would hold
    # the database's write lock and stall autosaves and job commits. Parallel wrong attempts can therefore pass
    # the count together; they are bounded by the worker threads and each one is recorded.
    with VERIFYING:
        valid = stored is not None and PASSWORDS.verify(password, stored)  # no password yet: nobody signs in
    with write_tx(engine) as conn:
        conn.execute(text("DELETE FROM login_failures WHERE attempted_at<=:since"), {"since": since})
        conn.execute(text("DELETE FROM sessions WHERE expires_at<=:now"), {"now": now.isoformat(timespec="microseconds")})
        if valid:
            token = secrets.token_urlsafe(32)
            if previous:
                conn.execute(text("DELETE FROM sessions WHERE token_hash=:hash"), {"hash": token_hash(previous)})
            conn.execute(text("INSERT INTO sessions VALUES (:hash,1,:expires)"),
                         {"hash": token_hash(token), "expires": (now+timedelta(seconds=SESSION_SECONDS)).isoformat(timespec="microseconds")})
        else:
            conn.execute(text("INSERT INTO login_failures (ip,attempted_at) VALUES (:ip,:now)"),
                         {"ip": ip, "now": now.isoformat(timespec="microseconds")})
    # The failed attempt is committed before the failure is reported.
    if not valid:
        raise Refused("unauthenticated", 401)
    return token


def logout(engine, token: str | None):
    if token:
        with write_tx(engine) as conn:
            conn.execute(text("DELETE FROM sessions WHERE token_hash=:hash"), {"hash": token_hash(token)})
