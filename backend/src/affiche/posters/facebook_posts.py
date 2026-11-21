"""A Facebook post of one or several confirmed posters (D-FB-POST-003): N images uploaded unpublished, one at a time,
then one call that publishes them. Everything before that last call can fail, stop or be tried again without anything
public; only the last call can leave an unknown outcome. It keeps the proven parts of facebook_publish.py: the key and
its `payload_sha` in the table's own column (never store.mutate, which would hold the write lock during the calls),
`_live` inside the write, the 30 s rule on the monotonic clock, the settling write tried again with the outcome in hand,
the task shielded from the client's going. Its rules look at facebook_posts only (the single poster's table is ignored).

One task owns a post from its admission to its settlement, registered under (shop, key) before the admission: a post
'uploading' or 'posting' that no task of this process holds is settled as at a start (§7). Nothing uploaded is deleted
(D-FB-POST-002). Only Facebook's own post id makes a post 'published', or the owner's word. The Page's token and the
photos' ids are in no answer, no log line and no address; nothing here logs but post ids, positions and kinds."""
import asyncio
import functools
import hashlib
import json
import logging
import threading
import time
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import Field, TypeAdapter, ValidationError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from affiche import assets
from affiche.db import utc_now, write_tx
from . import exports, store, terms
from .facebook import LIMIT_CODES, RECONNECT_CODE, REFUSED_CODES, Outcome, Upload, check_mode
from .facebook_connect import _live
from .facebook_publish import MAX_BYTES, caption_fault
from .models import Id, Model, canonical
from .store import Refused, check_key

log = logging.getLogger(__name__)
SEND_WINDOW_S = 30.0  # from the commit of 'posting' to the last call, on the monotonic clock (§6)
SETTLE_RETRIES, SETTLE_PAUSE_S = 3, 1.0
PERMISSION_CODES = frozenset({10, *range(200, 300)})
IDS = TypeAdapter(Annotated[list[Id], Field(min_length=1, max_length=200)])  # GET …/candidates?ids=, not paged
# The task of each post on its way, by (shop, key), with the future of its admission: from before the admission to the
# settlement. A post in flight whose (shop_id, key) is not here has no task in this process (§7).
_TASKS: dict[tuple[int, str], tuple[asyncio.Task, asyncio.Future]] = {}
CLOSING = threading.Event()  # drain(): read by the checks, which run in threads
IN_FLIGHT = "status IN ('uploading','posting')"
# A post that holds a poster on a Page (`p`, `i`); its order among posts is its rowid: the clock may step back.
HOLDS = ("FROM facebook_posts p JOIN facebook_post_items i ON i.post_id=p.id WHERE p.shop_id=:shop AND p.page_id=:page"
         " AND i.creation_id=:creation")
# « A candidate »: an active poster of the shop (c) with a confirmation in `feed` at its current revision, the latest such.
CONFIRMED = ("SELECT k.id FROM confirmations k WHERE k.creation_id=c.id AND k.confirmed_revision=c.current_revision"
             " AND k.format='feed' ORDER BY k.confirmed_at DESC,k.id DESC LIMIT 1")
POSTERS = ("SELECT c.id,c.created_at,p.name,v.document_json,k.id AS confirmation_id,k.png_sha256 FROM creations c"
           " JOIN creation_versions v ON v.creation_id=c.id AND v.revision=c.current_revision"
           " JOIN product_inputs p ON p.id=json_extract(v.document_json,'$.input_id')"
           f" JOIN confirmations k ON k.id=({CONFIRMED}) WHERE c.shop_id=:shop AND c.status='active'")
# Why an active poster (c) is not a candidate; NULL when it is one.
REASON = ("CASE WHEN EXISTS(SELECT 1 FROM confirmations k WHERE k.creation_id=c.id"
          " AND k.confirmed_revision=c.current_revision AND k.format='feed') THEN NULL"
          " WHEN EXISTS(SELECT 1 FROM confirmations k WHERE k.creation_id=c.id"
          " AND k.confirmed_revision=c.current_revision) THEN 'other_format'"
          " WHEN EXISTS(SELECT 1 FROM confirmations k WHERE k.creation_id=c.id) THEN 'changed' ELSE 'unconfirmed' END")
LEFT_OUT = ("other_format", "changed", "unconfirmed")


class Seen(Model):
    id: Id
    status: Literal["uploading", "posting", "published", "failed", "unknown"]


class Item(Model):
    creation_id: Id
    confirmation_id: Id
    seen: Seen | None  # the latest post that holds this poster on this Page, as the page showed it, or null


class PostRequest(Model):
    page_id: str = Field(pattern=r"^[0-9]{1,32}$")
    description: str  # its rules are checked at the admission, with their own sentence (caption_invalid)
    items: list[Item]  # in the post's order; at least one, each poster once: at the admission (§3.4), after the key


class OutcomeRequest(Model):
    present: bool


# The failures that name their image, by the key of their sentence; and those said alike wherever they came.
AT_IMAGE = {"poster_changed": "post_poster_changed", "export_missing": "post_export_missing", "no_answer": "post_no_answer",
            "published": "post_photo_public", "unexpected": "post_unexpected"}
PLAIN = ("not_sent", "stopped", "page_changed", "limit_lowered", "not_published")


def said(row, done: int, count: int, messages: dict) -> str:
    """The owner's line for a post, from the design's table of sentences. A failure at an upload has its position: the
    190, permission and limit sentences then start with the image (r3)."""
    status, code, at = row["status"], row["error_code"], row["failed_position"]
    n = None if at is None else at + 1
    if status == "uploading":
        return messages["post_uploading"].format(n=done + 1, count=count) if done < count else messages["post_uploaded"]
    if status == "published":
        return messages["post_confirmed"] if row["said_by_owner"] else messages["post_published"].format(row["page_name"])
    if status != "failed":
        return messages[f"post_{status}"]  # posting, unknown
    if code in AT_IMAGE and n is not None:
        return messages[AT_IMAGE[code]].format(n=n)
    if code in PLAIN:
        return messages[f"post_{code}"]
    known = int(code) if isinstance(code, str) and code.isdigit() else None
    if known in REFUSED_CODES and known not in PERMISSION_CODES:
        return messages["post_image_refused" if n else "post_refused"].format(n=n, code=code)
    if known == RECONNECT_CODE:
        line = messages["post_reconnect"]
    elif known in LIMIT_CODES:
        line = messages["post_limited"]
    elif known in PERMISSION_CODES:
        line = messages["post_permission"].format(code=code)
    else:
        return messages["post_not_sent"]  # a call refused by the client before it left (not_sent, caption): nothing left
    return messages["post_at_image"].format(n=n, said=line) if n else line


def _thumbnail(sha: str | None) -> str | None:
    from affiche.api import THUMBNAIL_VERSION  # api imports this module
    return f"/api/thumbnails/{sha}?v={THUMBNAIL_VERSION}" if sha else None


def view(conn, row, messages: dict, *, description: bool = False) -> dict:
    """A post as a route answers it: no token, no key, no photo id; `done`, the images that have their photo."""
    items = conn.execute(text("SELECT position,creation_id,png_sha256,photo_id IS NOT NULL AS done"
                              " FROM facebook_post_items WHERE post_id=:id ORDER BY position"),
                         {"id": row["id"]}).mappings().all()
    done = sum(item["done"] for item in items)
    answer = {name: row[name] for name in ("id", "status", "page_id", "page_name", "sent_at", "settled_at", "failed_position",
                                           "link", "error_code")}
    answer |= {"count": len(items), "done": done, "said_by_owner": bool(row["said_by_owner"]),
               "stop_asked": bool(row["stop_asked"]), "message_fr": said(row, done, len(items), messages),
               "items": [{"position": item["position"], "creation_id": item["creation_id"],
                          "thumbnail_url": _thumbnail(item["png_sha256"])} for item in items]}
    return answer | ({"description": row["description"]} if description else {})


def _owned(conn, shop: int, id: str):
    row = conn.execute(text("SELECT * FROM facebook_posts WHERE id=:id AND shop_id=:shop"),
                       {"id": id, "shop": shop}).mappings().first()
    if row is None:
        raise Refused("not_found", 404)
    return row


def _in_flight(conn, shop: int | None = None):
    where = "" if shop is None else " AND shop_id=:shop"
    return conn.execute(text(f"SELECT id,shop_id,key,status FROM facebook_posts WHERE {IN_FLIGHT}{where}"),
                        {"shop": shop}).mappings().all()


def _abandoned(conn, rows):
    """§7, inside a write transaction: a post in flight that no task of this process holds is settled as at a start, by
    an update that names the status it read, so that a task's own write is never overwritten. 'uploading' never made its
    last call ('posting' is committed before it): failed; 'posting' may have: unknown. The table of tasks is read after
    the rows: a task is registered before its admission writes its row."""
    for row in rows:
        if (row["shop_id"], row["key"]) not in _TASKS:
            status, code = ("failed", "not_sent") if row["status"] == "uploading" else ("unknown", None)
            conn.execute(text("UPDATE facebook_posts SET status=:status,error_code=:code,settled_at=:now"
                              " WHERE id=:id AND status=:was"),
                         {"status": status, "code": code, "now": utc_now(), "id": row["id"], "was": row["status"]})


def free(engine, shop: int | None = None):
    """§7 for every route that reads posts: the shop's posts in flight whose task is gone (every shop's at a start). A
    write transaction only when there is one: a shop has one post in flight at most, outside a restore."""
    with engine.connect() as conn:
        rows = _in_flight(conn, shop)
    if any((row["shop_id"], row["key"]) not in _TASKS for row in rows):
        with write_tx(engine) as conn:
            _abandoned(conn, rows)


def recover(engine):
    """At start-up, beside facebook_connect.recover, never in the shared runtime start: restore.sh runs after-restore
    before the service starts, and must find the rows as the backup left them."""
    free(engine)


def _candidate(conn, shop: int, creation: str):
    """The confirmation that makes this poster a candidate (its id and its file's hash), or None."""
    return conn.execute(text(f"SELECT k.id,k.png_sha256 FROM creations c JOIN confirmations k ON k.id=({CONFIRMED})"
                             " WHERE c.id=:id AND c.shop_id=:shop AND c.status='active'"),
                        {"id": creation, "shop": shop}).mappings().first()


def _last(conn, shop: int, page: str, creation: str) -> dict | None:
    """The id and the status of the latest post that holds this poster on this Page: what `seen` must be (§3.8)."""
    row = conn.execute(text(f"SELECT p.id,p.status {HOLDS} ORDER BY p.rowid DESC LIMIT 1"),
                       {"shop": shop, "page": page, "creation": creation}).mappings().first()
    return dict(row) if row else None


def _offered(conn, shop: int, page: str | None, row) -> dict:
    offer = json.loads(row["document_json"])["offer"]
    last = published = None
    if page is not None:
        mine = {"shop": shop, "page": page, "creation": row["id"]}
        last = _last(conn, shop, page, row["id"])
        published = conn.execute(text(f"SELECT p.sent_at {HOLDS} AND p.status='published' ORDER BY p.rowid DESC LIMIT 1"),
                                 mine).scalar()
    return {"id": row["id"], "name": row["name"], "title": offer["title"], "price_ar": offer["price_ar"],
            "confirmation_id": row["confirmation_id"], "thumbnail_url": _thumbnail(row["png_sha256"]),
            "download_url": f"/api/confirmations/{row['confirmation_id']}/download", "last": last, "published_at": published}


def candidates(engine, shop: int, limit: int, cursor: tuple[str, str], ids: str | None) -> dict:
    """GET /api/facebook/posts/candidates: the Page, the shop's limit, a page of candidates (as GET /api/creations: by
    created_at then id, newest first), or with `ids` those posters whatever their state, each a candidate or its reason;
    and how many of the shop's active posters cannot go, by reason. `last` and `published_at` are on the connected Page:
    null with none, or one to reconnect (whose state is still answered)."""
    chosen = None
    if ids is not None:
        try:
            chosen = list(dict.fromkeys(IDS.validate_python(ids.split(","))))
        except ValidationError:
            raise Refused("validation_error", field="ids") from None
    free(engine, shop)  # `last` carries a status: as it is, not as a dead task left it
    with engine.connect() as conn:
        page = conn.execute(text("SELECT page_id AS id,page_name AS name,state FROM facebook_pages WHERE shop_id=:shop"),
                            {"shop": shop}).mappings().first()
        on = page["id"] if page and page["state"] == "connected" else None  # the marks are the connected Page's
        mine = {"shop": shop}
        if chosen is None:
            rows = conn.execute(text(f"{POSTERS} AND (c.created_at,c.id)<(:stamp,:id) ORDER BY c.created_at DESC,c.id DESC"
                                     " LIMIT :limit"),
                                mine | {"stamp": cursor[0], "id": cursor[1], "limit": limit + 1}).mappings().all()
            items = [_offered(conn, shop, on, row) for row in rows[:limit]]
            after = f'{rows[limit - 1]["created_at"]}|{rows[limit - 1]["id"]}' if len(rows) > limit else None
        else:
            items, after = [], None
            for id in chosen:
                row = conn.execute(text(f"{POSTERS} AND c.id=:creation"), mine | {"creation": id}).mappings().first()
                reason = None if row else conn.execute(text(
                    f"SELECT {REASON} FROM creations c WHERE c.id=:creation AND c.shop_id=:shop AND c.status='active'"),
                    mine | {"creation": id}).scalar()
                items.append(_offered(conn, shop, on, row) if row else {"id": id, "reason": reason or "gone"})
        counts = dict(conn.execute(text(f"SELECT {REASON} AS reason,COUNT(*) FROM creations c WHERE c.shop_id=:shop"
                                        " AND c.status='active' GROUP BY reason"), mine).all())
        return {"page": dict(page) if page else None,
                "post_image_limit": conn.execute(text("SELECT post_image_limit FROM shop_profile WHERE id=:shop"), mine).scalar(),
                "items": items, "next_cursor": after, "left_out": {reason: counts.get(reason, 0) for reason in LEFT_OUT}}


def listed(engine, shop: int, limit: int, before: str | None, creation: str | None, messages: dict) -> dict:
    """GET /api/facebook/posts: newest first by rowid; the cursor is the last post's id. With `creation`, the posts that
    hold that poster, which must be the shop's."""
    free(engine, shop)
    with engine.connect() as conn:
        if creation is not None:
            store.get_creation(conn, shop, creation)
        start = 2 ** 63 - 1
        if before is not None:
            start = conn.execute(text("SELECT rowid FROM facebook_posts WHERE id=:id AND shop_id=:shop"),
                                 {"id": before, "shop": shop}).scalar()
            if start is None:
                raise Refused("invalid_cursor")
        holds = "" if creation is None else (" AND EXISTS(SELECT 1 FROM facebook_post_items i WHERE i.post_id=p.id"
                                             " AND i.creation_id=:creation)")
        rows = conn.execute(text(f"SELECT p.* FROM facebook_posts p WHERE p.shop_id=:shop AND p.rowid<:start{holds}"
                                 " ORDER BY p.rowid DESC LIMIT :limit"),
                            {"shop": shop, "start": start, "creation": creation, "limit": limit + 1}).mappings().all()
        return {"items": [view(conn, row, messages) for row in rows[:limit]],
                "next_cursor": rows[limit - 1]["id"] if len(rows) > limit else None}


def read(engine, shop: int, id: str, messages: dict) -> dict:
    """GET /api/facebook/posts/{id}, with its description: the page's polling."""
    free(engine, shop)
    with engine.connect() as conn:
        return view(conn, _owned(conn, shop, id), messages, description=True)


def _digest(request: PostRequest) -> str:
    """The request's `payload_sha`: the Page, the description and each item's poster and confirmation in order, without
    `seen` (T-FB-010's review): the page's key is its draft's stamp, so the same draft sent again after the page read
    the candidates again is the same request, answered its post."""
    sent = {"page_id": request.page_id, "description": request.description,
            "items": [[item.creation_id, item.confirmation_id] for item in request.items]}
    # surrogatepass: a lone surrogate gets its refusal from the description's rules, not an error from the hash.
    return hashlib.sha256(canonical(sent).encode("utf-8", "surrogatepass")).hexdigest()


def _replayed(engine, shop: int, key: str, digest: str, messages: dict) -> dict | None:
    """§1, one read: a post of this shop with this key, as it is now. No file is looked at before it."""
    free(engine, shop)
    with engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM facebook_posts WHERE shop_id=:shop AND key=:key"),
                           {"shop": shop, "key": key}).mappings().first()
        if row is None:
            return None
        if row["payload_sha"] != digest:
            raise Refused("idempotency_reused", 409)
        return view(conn, row, messages)


def _prepared(engine, settings, shop: int, request: PostRequest):
    """§2, no transaction: each item's confirmed file exists and is at most 10 MB (a stat; the bytes are read and their
    hash checked before their upload). A confirmation that is not this shop's is the admission's (facebook_stale), so no
    other shop's file is looked at. The refusal names its item (`field`)."""
    with engine.connect() as conn:
        files = [conn.execute(text("SELECT k.png_sha256 FROM confirmations k JOIN creations c ON c.id=k.creation_id"
                                   " WHERE k.id=:id AND c.shop_id=:shop"), {"id": item.confirmation_id, "shop": shop}).scalar()
                 for item in request.items]
    for n, sha in enumerate(files):
        if sha is None:
            continue
        try:
            size = assets.path(settings.data_dir, sha, "png").stat().st_size
        except OSError:
            raise Refused("export_missing", 503, field=f"items.{n}") from None
        if size > MAX_BYTES:
            raise Refused("facebook_too_large", 422, field=f"items.{n}")


def _admit(engine, graph, shop: int, token: str, key: str, request: PostRequest, digest: str, messages: dict):
    """§3, one write transaction, its nine checks in the design's order; a refusal raises inside it, so nothing is
    written. Returns the post as a route answers it, and what the task needs of a new 'uploading' post (None when the
    key's post was admitted meanwhile)."""
    with write_tx(engine) as conn:
        old = conn.execute(text("SELECT * FROM facebook_posts WHERE shop_id=:shop AND key=:key"),
                           {"shop": shop, "key": key}).mappings().first()
        if old is not None:  # 1. another request of this key, admitted since its read
            if old["payload_sha"] != digest:
                raise Refused("idempotency_reused", 409)
            return view(conn, old, messages), None
        _live(conn, shop, token)  # 2.
        terms.require(conn, shop)
        page = conn.execute(text("SELECT page_id,page_name,token,state,connected_at FROM facebook_pages WHERE shop_id=:shop"),
                            {"shop": shop}).mappings().first()  # 3.
        if page is None:
            raise Refused("facebook_not_connected", 409)
        if page["state"] != "connected":
            raise Refused("facebook_reconnect", 409)
        if page["page_id"] != request.page_id:
            raise Refused("facebook_stale", 409)
        posters = [item.creation_id for item in request.items]  # 4.
        if not posters or len(set(posters)) != len(posters):
            raise Refused("facebook_items", field="items")
        limit = conn.execute(text("SELECT post_image_limit FROM shop_profile WHERE id=:shop"), {"shop": shop}).scalar()
        if limit is not None and len(posters) > limit:
            refusal = Refused("facebook_too_many", 422)
            refusal.limit = limit  # its sentence names it (api.refusal)
            raise refusal
        files = []  # 5.
        for item in request.items:
            current = _candidate(conn, shop, item.creation_id)
            if current is None or current["id"] != item.confirmation_id:
                raise Refused("facebook_stale", 409)
            files.append(current["png_sha256"])
        if caption_fault(request.description):  # 6.
            raise Refused("caption_invalid", 422)
        description = request.description if request.description.strip() else ""  # only blanks is empty
        _abandoned(conn, _in_flight(conn, shop))  # 7. (§7: a dead task's post does not hold the shop)
        if _in_flight(conn, shop):
            raise Refused("facebook_running", 409)
        mine = {"shop": shop, "page": page["page_id"]}
        if any(conn.execute(text(f"SELECT 1 {HOLDS} AND p.status='unknown'"), mine | {"creation": poster}).first()
               for poster in posters):
            raise Refused("facebook_pending", 409)
        for item in request.items:  # 8. what the page showed is still true
            if _last(conn, shop, page["page_id"], item.creation_id) != (item.seen.model_dump() if item.seen else None):
                raise Refused("facebook_stale", 409)
        check_mode(conn, graph)  # 9.
        post = str(uuid4())
        conn.execute(text("INSERT INTO facebook_posts (id,shop_id,page_id,page_name,description,key,payload_sha,status,sent_at)"
                          " VALUES (:id,:shop,:page,:name,:description,:key,:sha,'uploading',:now)"),
                     mine | {"id": post, "name": page["page_name"], "description": description, "key": key, "sha": digest,
                             "now": utc_now()})
        items = [{"position": n, "creation_id": item.creation_id, "confirmation_id": item.confirmation_id, "png_sha256": sha}
                 for n, (item, sha) in enumerate(zip(request.items, files))]
        for item in items:
            conn.execute(text("INSERT INTO facebook_post_items (post_id,position,creation_id,confirmation_id,png_sha256)"
                              " VALUES (:post,:position,:creation_id,:confirmation_id,:png_sha256)"), item | {"post": post})
        return view(conn, _owned(conn, shop, post), messages), {"id": post, "page": dict(page), "items": items,
                                                                "description": description}


def _stopped(conn, shop: int, post: str, page: dict, count: int) -> str | None:
    """What stops a post before an upload (§4) and at the last check (§5), in the design's order; None: it goes on. The
    Page must still be the one that gave the token: its id, its connection's time, connected."""
    if CLOSING.is_set():
        return "not_sent"
    if conn.execute(text("SELECT stop_asked FROM facebook_posts WHERE id=:id"), {"id": post}).scalar():
        return "stopped"
    state, limit = conn.execute(text("SELECT state,post_image_limit FROM shop_profile WHERE id=:shop"), {"shop": shop}).one()
    if state != "active":
        return "not_sent"
    if not conn.execute(text("SELECT 1 FROM facebook_pages WHERE shop_id=:shop AND page_id=:page AND connected_at=:at"
                             " AND state='connected'"),
                        {"shop": shop, "page": page["page_id"], "at": page["connected_at"]}).first():
        return "page_changed"
    if limit is not None and limit < count:
        return "limit_lowered"
    return None


def _check(engine, shop: int, post: str, page: dict, count: int, n: int, items: list) -> tuple[str, int] | None:
    """§4, one short read before an upload. (r3) Before the first, every item again as at the admission: a poster
    changed before anything is sent stops the post; after it, the files that were confirmed are sent."""
    with engine.connect() as conn:
        for item in items:
            current = _candidate(conn, shop, item["creation_id"])
            if current is None or current["id"] != item["confirmation_id"]:
                return "poster_changed", item["position"]
        code = _stopped(conn, shop, post, page, count)
        return None if code is None else (code, n)


def _photo(engine, post: str, position: int, photo: str):
    with write_tx(engine) as conn:
        conn.execute(text("UPDATE facebook_post_items SET photo_id=:photo WHERE post_id=:post AND position=:position"),
                     {"photo": photo, "post": post, "position": position})


def _posting(engine, shop: int, post: str, page: dict, count: int) -> float | None:
    """§5, the cutoff: the last check and 'posting' in one write transaction, no call inside it; a check that fails
    settles the post failed in that same transaction. Returns the moment of the commit on the monotonic clock, or None
    when the last call must not be made."""
    with write_tx(engine) as conn:
        code = _stopped(conn, shop, post, page, count)
        if code is not None:
            conn.execute(text("UPDATE facebook_posts SET status='failed',error_code=:code,settled_at=:now"
                              " WHERE id=:id AND status='uploading'"), {"code": code, "now": utc_now(), "id": post})
            return None
        moved = conn.execute(text("UPDATE facebook_posts SET status='posting' WHERE id=:id AND status='uploading'"),
                             {"id": post}).rowcount
        at = time.monotonic()  # before the commit, so that the window never starts late; returned once it is kept
    return at if moved else None


def _settled(engine, shop: int, post: str, was: str, outcome: Outcome, page: dict, position: int | None):
    """Only while the post is still `was`. A 190 marks the Page 'reconnect' only if its row is still the one that gave
    the token: a Page connected again in between is left alone."""
    with write_tx(engine) as conn:
        settled = conn.execute(text(
            "UPDATE facebook_posts SET status=:status,post_id=:post_id,link=:link,error_code=:code,failed_position=:position,"
            "settled_at=:now WHERE id=:id AND status=:was"),
            {"status": outcome.status, "post_id": outcome.post_id, "link": outcome.link, "code": outcome.error_code,
             "position": position, "now": utc_now(), "id": post, "was": was}).rowcount
        if settled and outcome.reconnect:
            conn.execute(text("UPDATE facebook_pages SET state='reconnect' WHERE shop_id=:shop AND page_id=:page"
                              " AND connected_at=:at"), {"shop": shop, "page": page["page_id"], "at": page["connected_at"]})


async def _tried(post: str, write, *args):
    """A write of the task tried again with what it holds in hand, never by calling Facebook again. Failing every time,
    the task ends, and the post's next read settles it (§7)."""
    for attempt in range(SETTLE_RETRIES + 1):
        try:
            return await asyncio.to_thread(write, *args)
        except (OSError, SQLAlchemyError) as error:
            log.warning("post %s: a write failed (%s), attempt %d", post, type(error).__name__, attempt + 1)
            if attempt == SETTLE_RETRIES:
                raise
            await asyncio.sleep(SETTLE_PAUSE_S)


async def _settle(engine, shop: int, post: str, was: str, outcome: Outcome, page: dict, position: int | None = None):
    await _tried(post, _settled, engine, shop, post, was, outcome, page, position)


async def _upload(graph, post: str, page: dict, png: bytes, description: str, n: int) -> Upload:
    try:
        return await graph.upload_photo(page["page_id"], page["token"], png, hint=description, position=n)
    except Exception as error:  # noqa: BLE001 — sent or not, nobody can say; an upload shows nothing
        log.warning("post %s: upload %d ended with %s", post, n, type(error).__name__)
        return Upload("unknown")


async def _send(engine, settings, graph, shop: int, post: dict):
    """§4 to §6, outside any transaction: the uploads one at a time, the cutoff, then the last call, never sent twice."""
    id, page, items, description = post["id"], post["page"], post["items"], post["description"]
    photos = []
    for item in items:
        n = item["position"]
        stop = await asyncio.to_thread(_check, engine, shop, id, page, len(items), n, items if n == 0 else [])
        if stop is not None:
            return await _settle(engine, shop, id, "uploading", Outcome("failed", error_code=stop[0]), page, stop[1])
        try:
            png = await asyncio.to_thread(exports.read_png, settings, item)  # its hash, the one confirmed
        except Refused:
            return await _settle(engine, shop, id, "uploading", Outcome("failed", error_code="export_missing"), page, n)
        upload = await _upload(graph, id, page, png, description, n)
        if upload.status == "unknown":
            # The checks again before the second try: a stop asked, a Page changed or the shutdown (§8) while the
            # first was out ends the post here, with its own code.
            stop = await asyncio.to_thread(_check, engine, shop, id, page, len(items), n, [])
            if stop is not None:
                return await _settle(engine, shop, id, "uploading", Outcome("failed", error_code=stop[0]), page, n)
            upload = await _upload(graph, id, page, png, description, n)  # an upload shows nothing: once more only
        if upload.status != "uploaded":
            failed = Outcome("failed", error_code=upload.error_code if upload.status == "failed" else "no_answer",
                             reconnect=upload.reconnect)
            return await _settle(engine, shop, id, "uploading", failed, page, n)
        await _tried(id, _photo, engine, id, n, upload.photo_id)
        photos.append(upload.photo_id)
    posted_at = await asyncio.to_thread(_posting, engine, shop, id, page, len(items))
    if posted_at is None:
        return
    # §6. What changes after the cutoff does not stop the post; a task held back too long since it does not send.
    try:
        if time.monotonic() - posted_at > SEND_WINDOW_S:
            outcome = Outcome("failed", error_code="not_sent")
        else:
            outcome = await graph.create_post(page["page_id"], page["token"], description, photos)
    except Exception as error:  # noqa: BLE001 — the request may have left: nobody can say. Every path ends in a status.
        log.warning("post %s: the last call ended with %s", id, type(error).__name__)
        outcome = Outcome("unknown")
    await _settle(engine, shop, id, "posting", outcome, page)


async def _run(engine, settings, graph, shop: int, token: str, key: str, request: PostRequest, digest: str,
               messages: dict, admitted: asyncio.Future):
    """The post's one task: its admission, whose answer the route awaits, then the post to its settlement."""
    try:
        answer, post = await asyncio.to_thread(_admit, engine, graph, shop, token, key, request, digest, messages)
    except Exception as error:  # noqa: BLE001 — the route raises it; nothing was written
        admitted.set_exception(error)
        return
    except BaseException:  # cancelled with its loop: the route must not wait for it
        admitted.cancel()
        raise
    admitted.set_result(answer)
    if post is None:
        return
    try:
        await _send(engine, settings, graph, shop, post)
    except Exception as error:  # noqa: BLE001 — a write that kept failing, or a fault: its next read settles the post (§7)
        log.warning("post %s: its task ended with %s", post["id"], type(error).__name__)


def _ended(entry: tuple[int, str], admitted: asyncio.Future, _task: asyncio.Task):
    _TASKS.pop(entry, None)
    if admitted.done() and not admitted.cancelled():
        admitted.exception()  # retrieved: a refusal nobody waits for any more (the client went) is not reported as lost


async def publish(engine, settings, graph, shop: int, token: str, key: str, request: PostRequest, messages: dict) -> dict:
    """POST /api/facebook/posts: the key (§1), the files (§2), then one task registered under (shop, key) before its
    admission (§3), which owns the post to its settlement. The route awaits only the admission, shielded: a client that
    goes after the commit cannot leave a row without its task. A request of a key whose admission is on its way waits
    for it, then answers its row: never a second task for one key."""
    check_key(key)
    digest = _digest(request)
    while True:
        answer = await asyncio.to_thread(_replayed, engine, shop, key, digest, messages)
        if answer is not None:
            return answer
        try:
            await asyncio.to_thread(_prepared, engine, settings, shop, request)
        except Refused:  # the same key admitted since the read above, its file gone since: its row, not the refusal
            if (held := _TASKS.get((shop, key))) is not None:
                await asyncio.wait([held[1]])
            if (answer := await asyncio.to_thread(_replayed, engine, shop, key, digest, messages)) is not None:
                return answer
            raise
        held = _TASKS.get((shop, key))
        if held is None:
            break
        await asyncio.wait([held[1]])  # then its row, or nothing when it was refused
    admitted = asyncio.get_running_loop().create_future()
    task = asyncio.ensure_future(_run(engine, settings, graph, shop, token, key, request, digest, messages, admitted))
    _TASKS[(shop, key)] = task, admitted  # no await since the look above: nothing came in between
    task.add_done_callback(functools.partial(_ended, (shop, key), admitted))
    return await asyncio.shield(admitted)


async def drain():
    """At shutdown, before the data folder's lock is given up (§8): a post still uploading ends at its next check
    ('not_sent'), without the second try of an upload; a post whose last call is on its way finishes and settles. The
    wait is one call's deadline and the settling's tries."""
    CLOSING.set()
    try:
        await asyncio.gather(*(task for task, _admitted in list(_TASKS.values())), return_exceptions=True)
    finally:
        CLOSING.clear()  # the next application of this process (the tests) starts open


def stop(engine, shop: int, token: str, id: str, messages: dict) -> dict:
    """POST /api/facebook/posts/{id}/stop: an 'uploading' post stops at its next check (§4); any other is answered as it
    is."""
    free(engine, shop)
    with write_tx(engine) as conn:
        _live(conn, shop, token)
        conn.execute(text("UPDATE facebook_posts SET stop_asked=1 WHERE id=:id AND shop_id=:shop AND status='uploading'"),
                     {"id": id, "shop": shop})
        return view(conn, _owned(conn, shop, id), messages)


def outcome(engine, shop: int, token: str, key: str, id: str, request: OutcomeRequest, messages: dict) -> tuple[int, dict]:
    """POST /api/facebook/posts/{id}/outcome (§9): the owner's word on an unknown post only. No call: through
    store.mutate, whose key replays the stored answer. It changes the post's status, so a `seen` of it is stale (§3.8)."""
    free(engine, shop)

    def apply(conn):
        _live(conn, shop, token)
        row = _owned(conn, shop, id)
        if row["status"] in ("uploading", "posting"):
            raise Refused("facebook_running", 409)
        if row["status"] != "unknown":
            raise Refused("facebook_settled", 409)
        values = ({"status": "published", "link": f"https://www.facebook.com/{row['page_id']}", "code": None, "owner": 1}
                  if request.present else {"status": "failed", "link": None, "code": "not_published", "owner": 0})
        conn.execute(text("UPDATE facebook_posts SET status=:status,link=:link,error_code=:code,said_by_owner=:owner,"
                          "settled_at=:now WHERE id=:id AND status='unknown'"), values | {"id": id, "now": utc_now()})
        return 200, view(conn, _owned(conn, shop, id), messages)
    return store.mutate(engine, shop, key, "POST", f"/api/facebook/posts/{id}/outcome", request.model_dump(), apply)
