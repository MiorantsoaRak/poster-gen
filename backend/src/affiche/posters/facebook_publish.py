"""Publishing a confirmed poster on the shop's Facebook Page (D-FB-PUBLISH-003): one request made by the route itself, as
a chat read is (reads.read): prepared, admitted in one write transaction, sent outside any, settled in another. Not a job,
and not through store.mutate, which would hold the write lock during the call: the key is kept in the table's own `key`
column with its `payload_sha`.

Nothing is published twice: the key, tied to its poster; the last publication the sheet saw (`seen`); one in flight per
poster and Page; no retry by the server; an unknown outcome closed by the owner before another send. Only Facebook's own
post id makes a row `published`, or the owner's word (`said_by_owner`). The Page's token leaves the database only for the
send: it is in no answer, no log line and no address. Nothing here logs but ids and kinds."""
import asyncio
import hashlib
import logging
import re
import time
from uuid import uuid4

from pydantic import Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from affiche.db import utc_now, write_tx
from . import exports, store, terms
from .facebook import LIMIT_CODES, RECONNECT_CODE, REFUSED_CODES, Outcome, check_mode
from .facebook_connect import _live
from .models import Id, Model, canonical
from .store import Refused, check_key, get_creation

log = logging.getLogger(__name__)
MAX_BYTES = 10_000_000  # Meta's 10 MB for a photo, read as the smaller of its two meanings
CAPTION_MAX = 2000  # code points, as « Partager » counts them (share.ts captionFault)
# A control character other than line feed and tab (C0 with NUL, DEL, C1), as share.ts; a lone surrogate is no text.
FORBIDDEN = re.compile(r"[\x00-\x08\x0B-\x1F\x7F-\x9F\ud800-\udfff]")
SEND_WINDOW_S = 30.0  # (r3) a handler held back longer since its admission does not send; counted on the monotonic clock
SETTLE_RETRIES, SETTLE_PAUSE_S = 3, 1.0
_RUNNING: set[asyncio.Task] = set()  # the sends on their way: a task the loop holds weakly must not be collected


class PublishRequest(Model):
    confirmation_id: Id
    page_id: str = Field(pattern=r"^[0-9]{1,32}$")
    caption: str  # its rules are checked at the admission, with their own sentence (caption_invalid)
    seen: Id | None  # the last publication of this poster on this Page that the sheet showed, or null


class OutcomeRequest(Model):
    present: bool


def said(row, messages: dict) -> str:
    """The owner's line for a publication, from the answers' table of D-FB-PUBLISH-003 §4 and §5."""
    status, code = row["status"], row["error_code"]
    if status == "published":
        return messages["publication_confirmed"] if row["said_by_owner"] else messages["publication_published"].format(row["page_name"])
    if status != "failed":
        return messages[f"publication_{status}"]  # sending, unknown
    if code == str(RECONNECT_CODE):
        return messages["publication_reconnect"]
    if code in {str(known) for known in LIMIT_CODES}:
        return messages["publication_limited"]
    if code in {str(known) for known in REFUSED_CODES}:
        return messages["publication_refused"].format(code)
    if code == "not_published":
        return messages["publication_not_published"]
    return messages["publication_not_sent"]  # not_sent, caption: nothing left


def view(row, messages: dict) -> dict:
    """What a route answers of a publication: no token, no caption, no key."""
    return {"id": row["id"], "status": row["status"], "page_id": row["page_id"], "page_name": row["page_name"],
            "sent_at": row["sent_at"], "settled_at": row["settled_at"], "link": row["link"], "error_code": row["error_code"],
            "said_by_owner": bool(row["said_by_owner"]), "message_fr": said(row, messages)}


def _row(conn, id: str):
    return conn.execute(text("SELECT * FROM facebook_publications WHERE id=:id"), {"id": id}).mappings().one()


def listed(conn, shop: int, id: str, messages: dict) -> dict:
    """GET /api/creations/{id}/publications: newest first, with the shop's Page as the final panel needs it (the card's
    own read, GET /api/facebook, takes the refusal kept for the card: the panel must not). It reads and changes nothing;
    a `sending` row is shown as it is."""
    get_creation(conn, shop, id)
    page = conn.execute(text("SELECT page_id AS id,page_name AS name,state FROM facebook_pages WHERE shop_id=:shop"),
                        {"shop": shop}).mappings().first()
    # rowid: the order the rows were written in. `sent_at` is the clock's, which may step back; it is shown, not sorted.
    rows = conn.execute(text("SELECT * FROM facebook_publications WHERE shop_id=:shop AND creation_id=:id"
                             " ORDER BY rowid DESC"), {"shop": shop, "id": id}).mappings()
    return {"page": dict(page) if page else None, "items": [view(row, messages) for row in rows]}


def recover(engine):
    """At start-up only: a `sending` row's handler is dead, and whether its request left nobody can say. Never by age."""
    with write_tx(engine) as conn:
        conn.execute(text("UPDATE facebook_publications SET status='unknown',settled_at=:now WHERE status='sending'"),
                     {"now": utc_now()})


def caption_fault(caption: str) -> bool:
    """The rules of « Partager » (D-SHARE-003): a forbidden character, then more than 2 000 code points."""
    return FORBIDDEN.search(caption) is not None or len(caption) > CAPTION_MAX


def _digest(id: str, request: PublishRequest) -> str:
    # surrogatepass: a lone surrogate gets its refusal from the caption's rules, not an error from the hash.
    value = canonical({"creation_id": id, "body": request.model_dump()})
    return hashlib.sha256(value.encode("utf-8", "surrogatepass")).hexdigest()


def _prepared(engine, settings, shop: int, confirmation_id: str) -> tuple[bytes, str]:
    """1. No transaction, nothing written: the confirmation's PNG, read and checked as the download does."""
    with engine.connect() as conn:
        row, png = exports.download(conn, settings, shop, confirmation_id)
    if len(png) > MAX_BYTES:
        raise Refused("facebook_too_large", 422)
    return png, row["png_sha256"]


def _admit(engine, graph, shop: int, token: str, key: str, id: str, request: PublishRequest, sha: str):
    """2. The send's boundary, one write transaction in the design's order; a refusal raises inside it, so nothing is
    written. Returns the row of this key as it is now, or what the send needs of a new 'sending' row, with the moment of
    its admission on the monotonic clock (the wall clock, `sent_at`, may step back while the handler is held)."""
    digest = _digest(id, request)
    with write_tx(engine) as conn:
        old = conn.execute(text("SELECT * FROM facebook_publications WHERE shop_id=:shop AND key=:key"),
                           {"shop": shop, "key": key}).mappings().first()
        if old is not None:
            if old["creation_id"] != id or old["payload_sha"] != digest:
                raise Refused("idempotency_reused", 409)
            if old["status"] == "sending":
                raise Refused("facebook_running", 409)
            return dict(old)
        _live(conn, shop, token)
        get_creation(conn, shop, id)  # ownership, before the conditions (terms.require)
        terms.require(conn, shop)
        page = conn.execute(text("SELECT page_id,page_name,token,state,connected_at FROM facebook_pages WHERE shop_id=:shop"),
                            {"shop": shop}).mappings().first()
        if page is None:
            raise Refused("facebook_not_connected", 409)
        if page["state"] != "connected":
            raise Refused("facebook_reconnect", 409)
        if page["page_id"] != request.page_id:
            raise Refused("facebook_stale", 409)
        current = conn.execute(text(
            "SELECT k.png_sha256 FROM confirmations k JOIN creations c ON c.id=k.creation_id WHERE k.id=:confirmation"
            " AND c.id=:id AND c.shop_id=:shop AND k.confirmed_revision=c.current_revision"),
            {"confirmation": request.confirmation_id, "id": id, "shop": shop}).scalar()
        if current is None or current != sha:  # another revision saved since the sheet, or another poster's file
            raise Refused("facebook_stale", 409)
        if caption_fault(request.caption):
            raise Refused("caption_invalid", 422)
        caption = request.caption if request.caption.strip() else ""  # only blanks is empty; empty is allowed
        mine = {"shop": shop, "id": id, "page": page["page_id"]}
        if conn.execute(text("SELECT 1 FROM facebook_publications WHERE shop_id=:shop AND creation_id=:id"
                             " AND page_id=:page AND status IN ('sending','unknown')"), mine).first():
            raise Refused("facebook_pending", 409)
        last = conn.execute(text("SELECT id FROM facebook_publications WHERE shop_id=:shop AND creation_id=:id"
                                 " AND page_id=:page ORDER BY rowid DESC LIMIT 1"), mine).scalar()  # as `listed`
        if last != request.seen:  # two sheets opened before either published: the second has not seen the first
            raise Refused("facebook_stale", 409)
        check_mode(conn, graph)
        publication, sent_at = str(uuid4()), utc_now()
        conn.execute(text("INSERT INTO facebook_publications (id,shop_id,creation_id,confirmation_id,page_id,page_name,"
                          "caption,key,payload_sha,status,sent_at) VALUES (:pid,:shop,:id,:confirmation,:page,:name,"
                          ":caption,:key,:sha,'sending',:sent)"),
                     mine | {"pid": publication, "confirmation": request.confirmation_id, "name": page["page_name"],
                             "caption": caption, "key": key, "sha": digest, "sent": sent_at})
        return publication, dict(page), time.monotonic(), caption


def _settled(engine, shop: int, publication: str, page: dict, outcome: Outcome, messages: dict) -> dict:
    """4. Only while the row is 'sending'. A 190 marks the Page 'reconnect' only if its row is still the one that gave
    the token: a Page connected again in between is left alone."""
    with write_tx(engine) as conn:
        settled = conn.execute(text(
            "UPDATE facebook_publications SET status=:status,post_id=:post,link=:link,error_code=:code,settled_at=:now"
            " WHERE id=:id AND status='sending'"),
            {"id": publication, "status": outcome.status, "post": outcome.post_id, "link": outcome.link,
             "code": outcome.error_code, "now": utc_now()}).rowcount
        if settled and outcome.reconnect:
            conn.execute(text("UPDATE facebook_pages SET state='reconnect' WHERE shop_id=:shop AND page_id=:page"
                              " AND connected_at=:at"), {"shop": shop, "page": page["page_id"], "at": page["connected_at"]})
        return view(_row(conn, publication), messages)


async def _settle(engine, shop: int, publication: str, page: dict, outcome: Outcome, messages: dict) -> dict:
    """The settling write, tried again with the outcome in hand when it fails, never by sending again. Failing every
    time, the row stays 'sending' until the server starts again, then is unknown: the owner says."""
    for attempt in range(SETTLE_RETRIES + 1):
        try:
            return await asyncio.to_thread(_settled, engine, shop, publication, page, outcome, messages)
        except (OSError, SQLAlchemyError) as error:
            log.warning("publication %s: settling failed (%s), attempt %d", publication, type(error).__name__, attempt + 1)
            if attempt == SETTLE_RETRIES:
                raise
            await asyncio.sleep(SETTLE_PAUSE_S)


async def _run(engine, graph, shop: int, token: str, key: str, id: str, request: PublishRequest, png: bytes, sha: str,
               messages: dict) -> dict:
    admitted = await asyncio.to_thread(_admit, engine, graph, shop, token, key, id, request, sha)
    if isinstance(admitted, dict):
        return view(admitted, messages)
    publication, page, admitted_at, caption = admitted
    # 3. No transaction. (r3) Right before the request leaves: too long since the admission, and it does not leave.
    try:
        if time.monotonic() - admitted_at > SEND_WINDOW_S:
            outcome = Outcome("failed", error_code="not_sent")
        else:
            outcome = await graph.publish_photo(page["page_id"], page["token"], png, caption)
    except Exception as error:  # noqa: BLE001 — the request may have left: nobody can say. Every path ends in a status.
        log.warning("publication %s: the send ended with %s", publication, type(error).__name__)
        outcome = Outcome("unknown")
    return await _settle(engine, shop, publication, page, outcome, messages)


async def drain():
    """At shutdown, before the data folder's lock is given up: a send whose client went is still on its way, and the next
    process would call its row unknown while it can still leave. Each ends by itself (the client's timeouts, then the
    settling's tries)."""
    await asyncio.gather(*list(_RUNNING), return_exceptions=True)


def _held(task: asyncio.Task):
    _RUNNING.discard(task)
    if not task.cancelled():
        task.exception()  # retrieved: a refusal nobody waits for any more (the client went) is not reported as lost


async def publish(engine, settings, graph, shop: int, token: str, key: str, id: str, request: PublishRequest,
                  messages: dict) -> dict:
    """POST /api/creations/{id}/publications. From the admission on, the request runs to its settlement even when the
    client has gone: the route awaits it shielded, so a cancelled request does not cancel the send."""
    check_key(key)
    png, sha = await asyncio.to_thread(_prepared, engine, settings, shop, request.confirmation_id)
    task = asyncio.ensure_future(_run(engine, graph, shop, token, key, id, request, png, sha, messages))
    _RUNNING.add(task)
    task.add_done_callback(_held)
    return await asyncio.shield(task)


def outcome(engine, shop: int, token: str, key: str, id: str, publication: str, request: OutcomeRequest,
            messages: dict) -> tuple[int, dict]:
    """POST /api/creations/{id}/publications/{pid}/outcome (§5): the owner's word on an unknown publication only, never
    on a 'sending' one whatever its age. No call: through store.mutate, whose key replays the stored answer."""
    def apply(conn):
        _live(conn, shop, token)
        row = conn.execute(text("SELECT * FROM facebook_publications WHERE id=:pid AND shop_id=:shop AND creation_id=:id"),
                           {"pid": publication, "shop": shop, "id": id}).mappings().first()
        if row is None:
            raise Refused("not_found", 404)
        if row["status"] == "sending":
            raise Refused("facebook_running", 409)
        if row["status"] != "unknown":
            raise Refused("facebook_settled", 409)
        values = ({"status": "published", "link": f"https://www.facebook.com/{row['page_id']}", "code": None, "owner": 1}
                  if request.present else {"status": "failed", "link": None, "code": "not_published", "owner": 0})
        conn.execute(text("UPDATE facebook_publications SET status=:status,link=:link,error_code=:code,said_by_owner=:owner,"
                          "settled_at=:now WHERE id=:pid AND status='unknown'"), values | {"pid": publication, "now": utc_now()})
        return 200, view(_row(conn, publication), messages)
    return store.mutate(engine, shop, key, "POST", f"/api/creations/{id}/publications/{publication}/outcome",
                        request.model_dump(), apply)
