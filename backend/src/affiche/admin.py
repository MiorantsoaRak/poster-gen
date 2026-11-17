"""The operator's dashboard over HTTP (D-ADMIN-001, D-ADMIN-003): its own sign-in, sessions and cookie, apart from every
shop's. AccessBoundary (api.py) gives these routes request.state.operator and never a shop. Every write runs in
operator_tx, which finds the session still live once the write lock is held, calls the command line's own functions
(shops.*, credits.*) and logs one line after its commit."""
import logging
from contextlib import contextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request
from fastapi.security import APIKeyCookie
from pydantic import Field, SecretStr, ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from starlette.responses import JSONResponse

from affiche import shops
from affiche.config import Settings
from affiche.db import utc_now, write_tx
from affiche.posters import auth, credits, reads
from affiche.posters.models import Model
from affiche.posters.store import Refused
from affiche.visuals.admission import spent_micros
from affiche.visuals.gateway import usd_to_micros

log = logging.getLogger(__name__)
ShopId = Annotated[int, Path(ge=1, le=credits.MOST)]


class OperatorLogin(Model):
    password: SecretStr = Field(min_length=1, max_length=1024)


class NewShop(Model):
    identifier: str = Field(min_length=1, max_length=64)  # create_shop's own rule refuses what is not 3 to 32
    name: str | None = None  # the profile's own rule (Profile) judges it
    welcome: int = Field(ge=0, le=credits.MOST)  # typed at each creation (R-ADMIN-006): no default


@contextmanager
def operator_tx(engine, request: Request):
    """D-ADMIN-003's frame for every write: auth.operator_live first, inside the write_tx, so that a session ended or
    expired while the write waited for the lock writes nothing (401). A lock not obtained is 503 (AccessBoundary). The
    command line's refusals are answered after the rollback, with the module's own sentence as `detail`."""
    try:
        with write_tx(engine) as conn:
            if auth.operator_live(conn, request.state.operator.token_hash) is None:
                raise Refused("unauthenticated", 401)
            yield conn
    except ValidationError:  # a ValueError, so first; only the shop's name meets a model's rule in shops.py
        raise Refused("validation_error", field="name") from None
    except (ValueError, LookupError) as error:
        raise Refused("operator_refused", 409, detail=str(error)) from None
    except IntegrityError as error:  # a rule of 0014 or 0015: the driver's message, never the statement's parameters
        raise Refused("operator_refused", 409, detail=str(error.orig)) from None


def journal(action: str, actor: str, shop: str = "-", **counts):
    """The one line of a committed write, best effort (D-ADMIN-002): never a password, a hash, a token or a reference."""
    log.info("operator action=%s shop=%s actor=%s%s", action, shop, actor,
             "".join(f" {name}={value}" for name, value in counts.items()))


def new_password() -> tuple[str, str]:
    """A shop's password and its hash, made as the command line makes them, outside the write transaction and in one of
    the sign-in's Argon2 slots."""
    password = shops.new_password()
    with auth.VERIFYING:
        return password, auth.PASSWORDS.hash(password)


def find(conn, id: int):
    """A shop as shops.list_shops reads it, else 404. ponytail: scans every shop, tens of rows in Release 1."""
    shop = next((shop for shop in shops.list_shops(conn) if shop.id == id), None)
    if shop is None:
        raise Refused("not_found", 404)
    return shop


COUNTS = text("SELECT (SELECT COUNT(*) FROM creations WHERE shop_id=:shop AND status='active') AS posters,"
              " (SELECT MAX(created_at) FROM creations WHERE shop_id=:shop) AS last_poster_at,"
              " (SELECT COUNT(*) FROM sessions WHERE shop_id=:shop AND expires_at>:now) AS sessions")


def item(conn, shop) -> dict:
    """One shop of the list (R-ADMIN-002): never its hash."""
    return {"id": shop.id, "identifier": shop.identifier, "name": shop.name, "state": shop.state,
            "has_password": bool(shop.has_password), "created_at": shop.created_at, **credits.balance(conn, shop.id),
            **conn.execute(COUNTS, {"shop": shop.id, "now": utc_now()}).one()._asdict()}


def router(settings: Settings) -> APIRouter:
    routes = APIRouter()
    # Documents the operator's cookie in the schema; the session itself is read by AccessBoundary.
    protected = APIRouter(dependencies=[Depends(APIKeyCookie(name=auth.OPERATOR_COOKIE, scheme_name="OperatorCookie",
                                                             auto_error=False))])

    def cookie() -> dict:
        # Set and deleted with the same Path and Secure flag, or the browser keeps the cookie.
        return {"path": "/api/admin", "secure": settings.app_origin.startswith("https://"), "httponly": True,
                "samesite": "strict"}

    @routes.get("/api/admin/session", openapi_extra={"security": []})
    def session(request: Request):
        operator = request.state.operator
        if operator is None:
            return {"authenticated": False, "configured": auth.operator_configured(request.app.state.engine)}
        return {"authenticated": True, "actor": operator.actor, "expires_at": operator.expires_at}

    @routes.post("/api/admin/session", openapi_extra={"security": []})
    def sign_in(body: OperatorLogin, request: Request):
        address = request.client.host if request.client else "unknown"
        token, operator = auth.operator_login(request.app.state.engine, body.password.get_secret_value(), address,
                                              request.headers.get("user-agent"), request.cookies.get(auth.OPERATOR_COOKIE))
        journal("sign_in", operator.actor, address=address)
        response = JSONResponse({"authenticated": True, "actor": operator.actor, "expires_at": operator.expires_at})
        response.set_cookie(auth.OPERATOR_COOKIE, token, max_age=auth.OPERATOR_SECONDS, **cookie())
        return response

    @routes.delete("/api/admin/session", openapi_extra={"security": []})
    def sign_out(request: Request):
        actor = auth.operator_logout(request.app.state.engine, request.cookies.get(auth.OPERATOR_COOKIE))
        if actor is not None:
            journal("sign_out", actor)
        response = JSONResponse({"authenticated": False})
        response.delete_cookie(auth.OPERATOR_COOKIE, **cookie())
        return response

    @protected.delete("/api/admin/sessions")
    def end_all(request: Request):
        """Every operator session, this one included (« End all operator sessions »)."""
        with operator_tx(request.app.state.engine, request) as conn:
            ended = shops.end_operator_sessions(conn)
        journal("operator_sessions_ended", request.state.operator.actor, count=ended)
        response = JSONResponse({"ended": ended})
        response.delete_cookie(auth.OPERATOR_COOKIE, **cookie())
        return response

    @protected.get("/api/admin/shops")
    def shop_list(request: Request):
        with request.app.state.engine.connect() as conn:
            return {"items": sorted((item(conn, shop) for shop in shops.list_shops(conn)), key=lambda shop: shop["identifier"])}

    @protected.post("/api/admin/shops", status_code=201)
    def create_shop(body: NewShop, request: Request):
        """The password is in this answer only (AccessBoundary: no-store), and in no log line."""
        password, password_hash = new_password()
        actor = request.state.operator.actor
        with operator_tx(request.app.state.engine, request) as conn:
            id, line = shops.open_shop(conn, body.identifier, body.name, password_hash, body.welcome, actor)
            shop = item(conn, find(conn, id))
        journal("shop_created", actor, shop["identifier"], welcome=body.welcome)
        return {"shop": shop, "password": password, "welcome_line": line}

    @protected.get("/api/admin/shops/{id}")
    def one_shop(id: ShopId, request: Request):
        """Its limits on the UTC day, as the admission counts them (jobs.provider_guard, reads.read)."""
        now = utc_now()
        with request.app.state.engine.connect() as conn:
            return {"shop": item(conn, find(conn, id)),
                    "limits": {"day_spent_micros": spent_micros(conn, settings, shop=id, since=now[:10]),
                               "day_limit_micros": usd_to_micros(settings.shop_daily_spend_usd),
                               "reads_today": reads.today(conn, id, now), "reads_limit": reads.DAILY_LIMIT}}

    @protected.post("/api/admin/shops/{id}/password")
    def set_password(id: ShopId, request: Request):
        password, password_hash = new_password()
        with operator_tx(request.app.state.engine, request) as conn:
            shop = find(conn, id)
            ended = shops.set_password(conn, id, password_hash)
        journal("password_set", request.state.operator.actor, shop.identifier)
        return {"password": password, "sessions_ended": ended}

    @protected.delete("/api/admin/shops/{id}/sessions")
    def end_sessions(id: ShopId, request: Request):
        with operator_tx(request.app.state.engine, request) as conn:
            shop = find(conn, id)
            ended = shops.end_sessions(conn, id)
        if ended:
            journal("sessions_ended", request.state.operator.actor, shop.identifier, count=ended)
        return {"ended": ended}

    @protected.post("/api/admin/shops/{id}/suspend")
    def suspend(id: ShopId, request: Request):
        """Its queued jobs cancelled, their credits back (ADR-109); a running job finishes (D-MULTI-SHOP-006)."""
        with operator_tx(request.app.state.engine, request) as conn:
            shop = find(conn, id)
            cancelled = shops.suspend(conn, id)
        if cancelled is not None:
            journal("shop_suspended", request.state.operator.actor, shop.identifier, cancelled=cancelled)
        return {"changed": cancelled is not None, "cancelled_jobs": cancelled or 0}

    @protected.post("/api/admin/shops/{id}/enable")
    def enable(id: ShopId, request: Request):
        with operator_tx(request.app.state.engine, request) as conn:
            shop = find(conn, id)
            changed = shops.enable(conn, id)
        if changed:
            journal("shop_enabled", request.state.operator.actor, shop.identifier)
        return {"changed": changed}

    routes.include_router(protected)
    return routes
