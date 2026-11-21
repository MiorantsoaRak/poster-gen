"""Connecting the shop's Facebook Page (D-FB-PUBLISH-002): its one attempt, the code's three steps, the owner's choice
and the disconnection. None of these goes through store.mutate, which holds the write lock for its whole body, and none
takes an Idempotency-Key: the single-use `state` is the guard against a replay. Every transaction is short, and no call
to Facebook is made inside one.

Of a credential, an attempt keeps the SHA-256 of the dialog's `state` and of the session's token (sessions.token_hash: only
that session goes on with it), and at 'choice' the allowed Pages' tokens, gone with the row. Nothing here logs: the Graph
client says its own words (posters/facebook.py)."""
import asyncio
import json
import secrets
import time
from datetime import datetime, timedelta
from urllib.parse import urlencode

from pydantic import Field, model_validator
from sqlalchemy import text

from affiche.db import utc_now, write_tx
from . import auth
from .facebook import GraphFailure, check_mode
from .models import Model
from .store import Refused, _sha

TTL = timedelta(minutes=10)  # an attempt's life from « Connecter », and a return page's refusal's (remember)
DIALOG = "https://www.facebook.com/v27.0/dialog/oauth"
SCOPE = "pages_show_list,pages_manage_posts,pages_read_engagement,business_management"
# The stand-in's dialog code, of a real one's shape (facebook.CREDENTIAL: 20 printable characters at least, not digits only).
STUB_CODE = "stub-dialog-code-0000000001"
# The return page's refusals: the code of a failed step, or what Facebook sent back in place of a code.
STATUS = {"facebook_state": 409, "facebook_no_page": 422, "facebook_failed": 502, "facebook_cancelled": 409,
          "facebook_dialog_failed": 502}


class CodeRequest(Model):
    """What the return page read in its address: the `state`, and Facebook's code or the error it sent instead."""
    state: str = Field(min_length=1, max_length=200)
    code: str | None = Field(None, min_length=1, max_length=2000)
    error: str | None = Field(None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def code_or_error(self):
        if (self.code is None) == (self.error is None):
            raise ValueError("code_or_error")
        return self


class Choice(Model):
    page_id: str = Field(min_length=1, max_length=32)


def _cutoff() -> str:
    return (datetime.fromisoformat(utc_now()) - TTL).isoformat(timespec="microseconds")


def _live(conn, shop: int, token: str):
    """Inside the write transaction: the boundary saw this session before the lock was taken, and a sign-out in between
    must win. An ended session starts, chooses and removes nothing."""
    if auth.live_shop(conn, token) != shop:
        raise Refused("unauthenticated", 401)


def sweep(conn):
    """Every attempt older than 10 minutes goes, with the tokens it holds."""
    conn.execute(text("DELETE FROM facebook_connects WHERE created_at<:cutoff"), {"cutoff": _cutoff()})


def recover(engine):
    """At start-up, as the reads' and the jobs' recoveries."""
    with write_tx(engine) as conn:
        sweep(conn)


def view(conn, shop: int, session: str) -> dict:
    """The shop's Page, and the choice waiting for this session only, while it is under 10 minutes old. No token."""
    page = conn.execute(text("SELECT page_id AS id,page_name AS name,state FROM facebook_pages WHERE shop_id=:shop"),
                        {"shop": shop}).mappings().first()
    waiting = conn.execute(text("SELECT pages_json FROM facebook_connects WHERE shop_id=:shop AND session_sha=:session"
                                " AND step='choice' AND created_at>=:cutoff"),
                           {"shop": shop, "session": session, "cutoff": _cutoff()}).scalar()
    return {"page": dict(page) if page else None,
            "choice": [{"id": item["id"], "name": item["name"]} for item in json.loads(waiting)] if waiting else None}


def read(engine, shop: int, token: str) -> dict:
    """GET /api/facebook, without its last_error (recall)."""
    with write_tx(engine) as conn:
        sweep(conn)
        return view(conn, shop, auth.token_hash(token))


def connect(engine, settings, graph, shop: int, token: str) -> dict:
    """POST /api/facebook/connect: the shop's one attempt, whatever an older one's step, bound to this session. The
    dialog's address carries the `state`; it is stored nowhere, the state by its hash only."""
    state = secrets.token_urlsafe(32)
    with write_tx(engine) as conn:
        _live(conn, shop, token)
        sweep(conn)
        conn.execute(text("INSERT OR REPLACE INTO facebook_connects (shop_id,state_sha,session_sha,step,pages_json,created_at)"
                          " VALUES (:shop,:state,:session,'dialog',NULL,:now)"),
                     {"shop": shop, "state": _sha(state), "session": auth.token_hash(token), "now": utc_now()})
    back = f"{settings.app_origin}/facebook.html"
    if graph.mode == "stub":  # the return page stands in for Facebook's dialog: the whole flow runs without a network
        return {"url": f"{back}?{urlencode({'code': STUB_CODE, 'state': state})}"}
    return {"url": f"{DIALOG}?{urlencode({'client_id': settings.facebook_app_id, 'redirect_uri': back, 'state': state, 'scope': SCOPE})}"}


async def code(engine, settings, graph, shop: int, token: str, request: CodeRequest) -> dict:
    """POST /api/facebook/code: claimed, the calls, stored (D-FB-PUBLISH-002), the write lock never held during a call."""
    state, session = _sha(request.state), auth.token_hash(token)
    await asyncio.to_thread(_claim, engine, graph if request.code else None, shop, session, state)
    if request.code is None:  # Facebook sent the owner back without a code: nothing to call
        result = "facebook_cancelled" if request.error == "access_denied" else "facebook_dialog_failed"
    else:
        result = await _pages(graph, request.code, f"{settings.app_origin}/facebook.html")
    return await asyncio.to_thread(_store, engine, shop, token, session, state, result)


def _claim(engine, graph, shop: int, session: str, state: str):
    """Step 1: this shop's attempt at 'dialog', this session's, under 10 minutes, with this state's hash, goes to
    'exchange'. Anything else is refused and changes nothing; a second request with the same code finds 'exchange'."""
    with write_tx(engine) as conn:
        if not conn.execute(text("UPDATE facebook_connects SET step='exchange' WHERE shop_id=:shop AND session_sha=:session"
                                 " AND state_sha=:state AND step='dialog' AND created_at>=:cutoff"),
                            {"shop": shop, "session": session, "state": state, "cutoff": _cutoff()}).rowcount:
            raise Refused("facebook_state", 409)
        if graph is not None:
            check_mode(conn, graph)  # before a data folder's first call; its refusal rolls the claim back


async def _pages(graph, code: str, back: str):
    """Step 2, outside any transaction: the code for a user token, that one for a long-lived one, then the Pages the owner
    allowed. The user tokens end here."""
    user = await graph.exchange_code(code, back)
    if not isinstance(user, GraphFailure):
        user = await graph.long_lived(user)
    return user if isinstance(user, GraphFailure) else await graph.pages(user)


def _store(engine, shop: int, token: str, session: str, state: str, result) -> dict:
    """Step 3: the Pages are kept at 'choice' only while the attempt is still this one at 'exchange', under 10 minutes,
    and its session live: a new « Connecter », a « Déconnecter », a sign-out or the clock wins. Otherwise the attempt is
    deleted only if it is still this one: a newer attempt is never touched, nor the shop's Page."""
    this, mine = ("shop_id=:shop AND session_sha=:session AND state_sha=:state AND step='exchange'",
                  {"shop": shop, "session": session, "state": state})
    with write_tx(engine) as conn:
        still = auth.live_shop(conn, token) == shop and conn.execute(text(
            f"SELECT 1 FROM facebook_connects WHERE {this} AND created_at>=:cutoff"), mine | {"cutoff": _cutoff()}).first()
        if isinstance(result, list) and result and still:
            conn.execute(text(f"UPDATE facebook_connects SET step='choice',pages_json=:pages WHERE {this}"), mine | {
                "pages": json.dumps([{"id": page.id, "name": page.name, "token": page.token} for page in result])})
            return view(conn, shop, session)
        conn.execute(text(f"DELETE FROM facebook_connects WHERE {this}"), mine)
    # After the commit, so that the deletion is kept.
    refusal = (result if isinstance(result, str) else "facebook_failed" if isinstance(result, GraphFailure)
               else "facebook_no_page" if not result else "facebook_state")
    raise Refused(refusal, STATUS[refusal])


def choose(engine, shop: int, token: str, page_id: str) -> dict:
    """POST /api/facebook/page: one of the attempt's Pages becomes the shop's, replacing its earlier Page only now; the
    attempt goes, and with it the other Pages' tokens. A Page outside the choice changes nothing."""
    session = auth.token_hash(token)
    with write_tx(engine) as conn:
        _live(conn, shop, token)
        waiting = conn.execute(text("SELECT pages_json FROM facebook_connects WHERE shop_id=:shop AND session_sha=:session"
                                    " AND step='choice' AND created_at>=:cutoff"),
                               {"shop": shop, "session": session, "cutoff": _cutoff()}).scalar()
        page = next((item for item in json.loads(waiting or "[]") if item["id"] == page_id), None)
        if page is None:
            raise Refused("facebook_state", 409)
        conn.execute(text("INSERT OR REPLACE INTO facebook_pages (shop_id,page_id,page_name,token,state,connected_at)"
                          " VALUES (:shop,:id,:name,:token,'connected',:now)"), {"shop": shop, "now": utc_now(), **page})
        conn.execute(text("DELETE FROM facebook_connects WHERE shop_id=:shop"), {"shop": shop})
        return view(conn, shop, session)


def disconnect(engine, shop: int, token: str) -> dict:
    """DELETE /api/facebook/page: the shop's Page and its attempt go. Sent twice, it answers the same."""
    with write_tx(engine) as conn:
        _live(conn, shop, token)
        conn.execute(text("DELETE FROM facebook_pages WHERE shop_id=:shop"), {"shop": shop})
        conn.execute(text("DELETE FROM facebook_connects WHERE shop_id=:shop"), {"shop": shop})
    return {"page": None, "choice": None}


def remember(said: dict, token: str, code: str):
    """The refusal answered to the return page, for the card it opens next: that page keeps nothing in the browser, and
    the attempt is gone. Held in the server's memory for this session until its next read of the card, ten minutes at
    most. A restart forgets it, and the card then shows the state as it is (one API process per data folder: the lock)."""
    now = time.monotonic()
    for session, (_code, at) in list(said.items()):
        if now - at > TTL.total_seconds():
            said.pop(session, None)
    said[auth.token_hash(token)] = (code, now)


def recall(said: dict, token: str) -> str | None:
    code, at = said.pop(auth.token_hash(token), (None, 0.0))
    return code if code is not None and time.monotonic() - at <= TTL.total_seconds() else None
