"""The operator's dashboard over HTTP (D-ADMIN-001, D-ADMIN-003): its own sign-in, sessions and cookie, apart from every
shop's. AccessBoundary (api.py) gives these routes request.state.operator and never a shop. Every write runs in
operator_tx, which finds the session still live once the write lock is held, and logs one line after its commit."""
import logging
from contextlib import contextmanager

from fastapi import APIRouter, Depends, Request
from fastapi.security import APIKeyCookie
from pydantic import Field, SecretStr
from starlette.responses import JSONResponse

from affiche import shops
from affiche.config import Settings
from affiche.db import write_tx
from affiche.posters import auth
from affiche.posters.models import Model
from affiche.posters.store import Refused

log = logging.getLogger(__name__)


class OperatorLogin(Model):
    password: SecretStr = Field(min_length=1, max_length=1024)


@contextmanager
def operator_tx(engine, request: Request):
    """D-ADMIN-003's frame for every write: auth.operator_live first, inside the write_tx, so that a session ended or
    expired while the write waited for the lock writes nothing (401). A lock not obtained is 503 (AccessBoundary)."""
    with write_tx(engine) as conn:
        if auth.operator_live(conn, request.state.operator.token_hash) is None:
            raise Refused("unauthenticated", 401)
        yield conn


def journal(action: str, actor: str, shop: str = "-", **counts):
    """The one line of a committed write, best effort (D-ADMIN-002): never a password, a hash, a token or a reference."""
    log.info("operator action=%s shop=%s actor=%s%s", action, shop, actor,
             "".join(f" {name}={value}" for name, value in counts.items()))


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

    routes.include_router(protected)
    return routes
