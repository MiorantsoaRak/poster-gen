"""A Facebook post of one or several posters through the routes (D-FB-POST-003): the candidates, the admission and its
refusals, the uploads and the last call, the post that no task holds, start and shutdown, the owner's word. Facebook is
httpx2.MockTransport (`meta`) or the stand-in (`stub`): nothing leaves the machine. The confirmed posters are written
straight into the database, as the smokes do: their rows and their PNG, without a render."""
import asyncio
import hashlib
import io
import logging
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx2
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import SecretStr
from sqlalchemy import event, text
from sqlalchemy.exc import OperationalError

from affiche import assets
from affiche.api import MESSAGES, create_app
from affiche.db import utc_now, write_tx
from affiche.posters import auth, facebook, facebook_posts
from affiche.posters.facebook_posts import PostRequest
from affiche.posters.store import Refused
from test_api import HEADERS, ORIGIN, create_draft, credentials, login, password_hash, second_shop  # noqa: F401
from test_config import env  # noqa: F401
from test_db import credited, unaccepted
from test_facebook import fields, form
from test_facebook_api import APP, SECRET, settings_for

PAGE, TOKEN, OTHER_TOKEN = "111", "page-token-of-the-page-111", "page-token-reconnected-111"
EARLIER = "2026-11-20T08:00:00.000000+00:00"
PHOTO = "7770000"  # every photo id the mock makes starts so: none may reach an answer or a log line
SENSITIVE = (SECRET, TOKEN, OTHER_TOKEN, PHOTO)
NAME = "Original Phone Mada"
AUTO = object()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(client, sql, **values):
    with write_tx(client.app.state.engine) as conn:
        return conn.execute(text(sql), values)


def connected(client, page=PAGE, name="Original Phone Mada", token=TOKEN, at=EARLIER, shop=1):
    run(client, "INSERT OR REPLACE INTO facebook_pages VALUES (:shop,:page,:name,:token,'connected',:at)",
        shop=shop, page=page, name=name, token=token, at=at)


def png(colour="red") -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (12, 15), colour).save(out, "PNG")
    return out.getvalue()


def confirm(client, creation, data=None) -> tuple[str, bytes]:
    """A confirmation of the poster at its current revision, with its PNG stored: the rows a render and a confirmation
    leave. Returns its id and its bytes."""
    data = data or png()
    sha = assets.put(Path(client.app.state.engine.url.database).parent, data, "png")
    with write_tx(client.app.state.engine) as conn:
        revision, input_id = conn.execute(text(
            "SELECT c.current_revision, json_extract(v.document_json,'$.input_id') FROM creations c JOIN creation_versions v"
            " ON v.creation_id=c.id AND v.revision=c.current_revision WHERE c.id=:id"), {"id": creation}).one()
        shop = conn.execute(text("SELECT shop_id FROM creations WHERE id=:id"), {"id": creation}).scalar()
        job, render, confirmation, now = str(uuid4()), str(uuid4()), str(uuid4()), utc_now()
        conn.execute(text("INSERT INTO poster_jobs (id,shop_id,creation_id,origin_revision,input_id,kind,input_json,input_hash,"
                          "status,result_ref,created_at,finished_at) VALUES (:job,:shop,:id,:rev,:input,'render','{}','h',"
                          "'succeeded',:render,:now,:now)"),
                     {"job": job, "shop": shop, "id": creation, "rev": revision, "input": input_id, "render": render, "now": now})
        conn.execute(text("INSERT INTO poster_renders VALUES (:render,:id,:rev,:job,'feed',:hash,'b','f','{}',:sha,12,15,"
                          ":bytes,'[]',:now)"), {"render": render, "id": creation, "rev": revision, "job": job,
                                                 "hash": str(uuid4()), "sha": sha, "bytes": len(data), "now": now})
        conn.execute(text("INSERT INTO confirmations VALUES (:confirmation,:id,:rev,:rev,'feed','h',:render,:sha,'{}',:now)"),
                     {"confirmation": confirmation, "id": creation, "rev": revision, "render": render, "sha": sha, "now": now})
    return confirmation, data


def refused(answer, code, status=409):
    assert (answer.status_code, answer.json()["error"]["code"]) == (status, code), answer.text


def page_state(client, shop=1):
    with client.app.state.engine.connect() as conn:
        return conn.execute(text("SELECT state FROM facebook_pages WHERE shop_id=:shop"), {"shop": shop}).scalar()


class Graph:
    """Facebook's two calls of a post, recorded. `answers[kind]` ('photos', 'feed'): the answers given first, in order (a
    Response, an exception raised, or None for the success); then the success: a photo id, or a post id of the Page
    named in the address. `during(request)` runs inside each call, off the event loop: it may write to the database or
    call the routes."""
    def __init__(self):
        self.requests, self.answers, self.during, self.photo_ids = [], {"photos": [], "feed": []}, None, []

    async def __call__(self, request):
        kind = request.url.path.rsplit("/", 1)[1]
        self.requests.append(request)
        if self.during:
            await asyncio.to_thread(self.during, request)
        answer = self.answers[kind].pop(0) if self.answers[kind] else None
        if isinstance(answer, Exception):
            raise answer
        if answer is not None:
            return answer
        if kind == "photos":
            self.photo_ids.append(f"{PHOTO}{len(self.photo_ids) + 1}")
            return httpx2.Response(200, json={"id": self.photo_ids[-1]})
        page = request.url.path.split("/")[2]
        return httpx2.Response(200, json={"id": f"{page}_{len(self.of('feed'))}", "post_supports_client_mutation_id": True})

    def of(self, kind):
        return [request for request in self.requests if request.url.path.endswith(f"/{kind}")]


@pytest.fixture
def graph(monkeypatch):
    graph, real = Graph(), facebook.make_graph
    monkeypatch.setattr(facebook, "make_graph", lambda settings: real(settings, httpx2.MockTransport(graph)))
    monkeypatch.setattr(facebook_posts, "SETTLE_PAUSE_S", 0)
    return graph


@pytest.fixture
def client(env, tmp_path, password_hash, graph, caplog):
    caplog.set_level(logging.DEBUG)
    answers = []  # every answer of the test: no token, secret or photo id may reach the browser
    with TestClient(create_app(settings_for(env, tmp_path, password_hash, "meta"), prepare=credited), base_url=ORIGIN,
                    headers=HEADERS) as client:
        client.event_hooks["response"].append(answers.append)
        login(client)
        yield client
    for answer in answers:
        assert not any(value in answer.text for value in SENSITIVE), (answer.request.url.path, answer.text)
    assert not any(value in caplog.text for value in SENSITIVE)
    assert not facebook_posts._TASKS and not facebook_posts.CLOSING.is_set()


def posters(client, n) -> list[tuple[str, str, bytes]]:
    """N posters, each confirmed in `feed` at its current revision, each with its own bytes: (creation, confirmation,
    PNG)."""
    made = []
    for i in range(n):
        creation = create_draft(client)["id"]
        made.append((creation, *confirm(client, creation, png((40 * i, 120, 200)))))
    return made


def body(client, made, description="Promo de la semaine 🎧", page=PAGE, seen=AUTO) -> dict:
    """The request as the page sends it: `seen` read from the candidates, unless given (one for all, or one each)."""
    if seen is AUTO:
        found = {} if not made else {item["id"]: item.get("last") for item in client.get(
            "/api/facebook/posts/candidates", params={"ids": ",".join(creation for creation, *_ in made)}).json()["items"]}
        seen = [found.get(creation) for creation, *_ in made]
    elif not isinstance(seen, list):
        seen = [seen] * len(made)
    return {"page_id": page, "description": description, "items": [
        {"creation_id": creation, "confirmation_id": confirmation, "seen": mark}
        for (creation, confirmation, _), mark in zip(made, seen)]}


def send(client, made=(), key=None, request=None, **kwargs):
    return client.post("/api/facebook/posts", json=request or body(client, list(made), **kwargs),
                       headers={"Idempotency-Key": key or str(uuid4())})


def quiet(seconds=10):
    """Until no post task runs: each has settled its post, or ended."""
    deadline = time.monotonic() + seconds
    while facebook_posts._TASKS:
        assert time.monotonic() < deadline, "a post task did not end"
        time.sleep(0.01)


def settled(client, id) -> dict:
    """The post once its task has ended, as the page's polling reads it."""
    quiet()
    answer = client.get(f"/api/facebook/posts/{id}")
    assert answer.status_code == 200, answer.text
    return answer.json()


def posted(client, made, **kwargs) -> dict:
    answer = send(client, made, **kwargs)
    assert answer.status_code == 202, answer.text
    return settled(client, answer.json()["id"])


def rows(client, table="facebook_posts") -> list[dict]:
    with client.app.state.engine.connect() as conn:
        return [dict(row) for row in conn.execute(text(f"SELECT * FROM {table} ORDER BY rowid")).mappings()]


def written(client):
    """Everything an admission could write: the posts, their images, the Pages and the data folder's Facebook mode."""
    with client.app.state.engine.connect() as conn:
        return (rows(client), rows(client, "facebook_post_items"), rows(client, "facebook_pages"),
                conn.execute(text("SELECT value FROM meta WHERE key='facebook_mode'")).scalar())


def changed(client, creation):
    """A new revision saved: the poster's confirmation is now of an earlier one."""
    saved = client.get(f"/api/creations/{creation}").json()
    answer = client.put(f"/api/creations/{creation}", json=saved["document"] | {
        "offer": saved["document"]["offer"] | {"price_ar": saved["document"]["offer"]["price_ar"] + 1}},
        headers={"Idempotency-Key": str(uuid4()), "If-Match": f'"{saved["revision"]}"'})
    assert answer.status_code == 200, answer.text


def a_post(client, status, made, shop=1, key=None, page=PAGE, digest="x", **values) -> str:
    """A post written straight into the database, with no task to hold it."""
    id = str(uuid4())
    run(client, "INSERT INTO facebook_posts (id,shop_id,page_id,page_name,description,key,payload_sha,status,sent_at,"
        "error_code,post_id,link) VALUES (:id,:shop,:page,:name,'',:key,:sha,:status,:now,:code,:post,:link)",
        id=id, shop=shop, page=page, name=NAME, key=key or str(uuid4()), sha=digest, status=status, now=utc_now(),
        code=values.get("code"), post=values.get("post"), link=values.get("link"))
    for n, (creation, confirmation, _) in enumerate(made):
        run(client, "INSERT INTO facebook_post_items (post_id,position,creation_id,confirmation_id) VALUES (:id,:n,:c,:k)",
            id=id, n=n, c=creation, k=confirmation)
    return id


def test_a_post_of_three_posters_is_published_in_the_order_chosen_with_its_own_files(client, graph, monkeypatch):
    made = posters(client, 3)
    connected(client)
    order = [made[2], made[0], made[1]]
    engine, seen = client.app.state.engine, []

    def during(request):  # what the page's polling reads, call by call
        post = facebook_posts.read(engine, 1, rows(client)[0]["id"], MESSAGES)
        seen.append((post["status"], post["done"], post["message_fr"]))

    real = facebook_posts._posting

    def posting(*args):  # every image uploaded, the cutoff not yet made
        post = facebook_posts.read(engine, 1, args[2], MESSAGES)
        seen.append((post["status"], post["done"], post["message_fr"]))
        return real(*args)

    graph.during = during
    monkeypatch.setattr(facebook_posts, "_posting", posting)
    answer = send(client, order, description="Ligne 1\n\n\tLigne 2 ✨")
    assert answer.status_code == 202, answer.text
    first = answer.json()
    assert first == {"id": first["id"], "status": "uploading", "page_id": PAGE, "page_name": NAME, "sent_at": first["sent_at"],
                     "settled_at": None, "failed_position": None, "link": None, "error_code": None, "count": 3, "done": 0,
                     "said_by_owner": False, "stop_asked": False, "message_fr": "Envoi de l’image 1 sur 3…",
                     "items": [{"position": n, "creation_id": creation, "thumbnail_url": f"/api/thumbnails/{sha(data)}?v=1"}
                               for n, (creation, _, data) in enumerate(order)]}
    post = settled(client, first["id"])
    assert post == first | {"status": "published", "settled_at": post["settled_at"], "done": 3,
                            "link": f"https://www.facebook.com/{PAGE}_1", "message_fr": f"Publié sur {NAME}.",
                            "description": "Ligne 1\n\n\tLigne 2 ✨"}
    assert seen == [("uploading", 0, "Envoi de l’image 1 sur 3…"), ("uploading", 1, "Envoi de l’image 2 sur 3…"),
                    ("uploading", 2, "Envoi de l’image 3 sur 3…"), ("uploading", 3, "Images envoyées. Publication…"),
                    ("posting", 3, "Publication en cours…")]
    photos, [feed] = graph.of("photos"), graph.of("feed")
    for request, (_, _, data) in zip(photos, order, strict=True):  # each the confirmed file, unpublished
        assert data in request.content and fields(request) == {"published": "false", "access_token": TOKEN,
                                                               "appsecret_proof": fields(request)["appsecret_proof"]}
    assert form(feed) == {"message": "Ligne 1\n\n\tLigne 2 ✨", "access_token": TOKEN, "appsecret_proof": form(feed)["appsecret_proof"],
                          **{f"attached_media[{n}]": f'{{"media_fbid":"{photo}"}}' for n, photo in enumerate(graph.photo_ids)}}
    assert [item["photo_id"] for item in rows(client, "facebook_post_items")] == graph.photo_ids  # kept, never answered
    assert {request.method for request in graph.requests} == {"POST"}  # nothing deleted
    [row] = rows(client)
    assert (row["post_id"], row["description"]) == (f"{PAGE}_1", "Ligne 1\n\n\tLigne 2 ✨")
    with client.app.state.engine.connect() as conn:
        assert conn.execute(text("SELECT value FROM meta WHERE key='facebook_mode'")).scalar() == "meta"


@pytest.mark.parametrize("description", ["", "   \n\t "])
def test_an_empty_or_blank_description_is_published_without_one(client, graph, description):
    connected(client)
    assert posted(client, posters(client, 1), description=description)["status"] == "published"
    assert "message" not in form(graph.of("feed")[0]) and rows(client)[0]["description"] == ""


def test_the_key_is_answered_before_any_file_is_looked_at(client, graph, tmp_path):
    made = posters(client, 2)
    connected(client)
    key, request = str(uuid4()), body(client, made)
    first = posted(client, made, key=key, request=request)
    assets.path(tmp_path, sha(made[1][2]), "png").unlink()  # the file is gone since
    again = send(client, key=key, request=request)
    assert again.status_code == 202 and again.json() == {k: v for k, v in first.items() if k != "description"}
    refused(send(client, key=key, request=request | {"description": "Autre texte"}), "idempotency_reused")
    refused(send(client, made, key=str(uuid4())), "export_missing", 503)  # a new key: the file is looked at
    assert len(graph.of("feed")) == 1 and len(rows(client)) == 1


def test_the_same_key_with_another_seen_is_the_same_request_and_another_post_or_order_is_not(client, graph):
    """The page's key is its draft's stamp: the same draft sent again after the candidates were read again (another
    `seen`) is answered its post; another description or another order under that key is another request."""
    made = posters(client, 2)
    connected(client)
    key = str(uuid4())
    first = posted(client, made, key=key)
    again = body(client, made)  # read again: each poster's `seen` is now that post
    assert [item["seen"] for item in again["items"]] == [{"id": first["id"], "status": "published"}] * 2
    answer = send(client, key=key, request=again)
    assert answer.status_code == 202 and answer.json() == {k: v for k, v in first.items() if k != "description"}
    refused(send(client, key=key, request=again | {"description": "Autre texte"}), "idempotency_reused")
    refused(send(client, key=key, request=again | {"items": again["items"][::-1]}), "idempotency_reused")
    assert len(rows(client)) == 1 and len(graph.of("feed")) == 1


def test_each_refusal_of_the_admission_writes_and_sends_nothing(client, graph, tmp_path):
    engine = client.app.state.engine
    made, other_format, never = posters(client, 2), posters(client, 1), create_draft(client)["id"]
    connected(client)
    first = posted(client, made[:1])
    run(client, "UPDATE confirmations SET format='square' WHERE id=:id", id=other_format[0][1])
    graph.requests.clear()
    before = written(client)

    def nothing(answer, code, status=409, field=None):
        refused(answer, code, status)
        assert answer.json()["error"].get("field") == field and written(client) == before and graph.requests == []

    last = {"id": first["id"], "status": "published"}
    nothing(send(client, made, seen=[None, None]), "facebook_stale")  # the page did not see the first post
    nothing(send(client, made, seen=[{"id": str(uuid4()), "status": "published"}, None]), "facebook_stale")
    nothing(send(client, made, seen=[last | {"status": "unknown"}, None]), "facebook_stale")  # its status has changed
    nothing(send(client, made, page="333"), "facebook_stale")  # another Page than the shop's
    nothing(send(client, made + other_format), "facebook_stale")  # confirmed in another format
    nothing(send(client, [(never, str(uuid4()), b"")]), "facebook_stale")  # never confirmed
    nothing(send(client, [(made[0][0], made[1][1], b"")]), "facebook_stale")  # another poster's confirmation
    nothing(send(client, []), "facebook_items", 422, "items")
    nothing(send(client, [made[1], made[1]]), "facebook_items", 422, "items")  # a poster twice
    for description in ("é" * 2001, "a\x00b", "a\rb", "a\x7fb", "a\x85b", "🎧" * 2001):
        nothing(send(client, made, description=description), "caption_invalid", 422)
    # The files, looked at before the transaction: missing, then over Meta's 10 MB, each named by its place.
    path = assets.path(tmp_path, sha(made[1][2]), "png")
    kept = path.read_bytes()
    path.unlink()
    nothing(send(client, made), "export_missing", 503, "items.1")
    path.write_bytes(kept)
    big = create_draft(client)["id"]
    large, _ = confirm(client, big, b"\x89PNG" + bytes(10_000_000))
    nothing(send(client, [made[1], (big, large, b"")]), "facebook_too_large", 422, "items.1")
    # The conditions, the Page, the data folder's mode.
    unaccepted(engine)
    nothing(send(client, made), "terms_required", 403)
    credited(engine)
    run(client, "UPDATE facebook_pages SET state='reconnect'")
    before = written(client)
    nothing(send(client, made), "facebook_reconnect")
    run(client, "DELETE FROM facebook_pages")
    before = written(client)
    nothing(send(client, made), "facebook_not_connected")
    connected(client)
    run(client, "UPDATE meta SET value='stub' WHERE key='facebook_mode'")
    before = written(client)
    nothing(send(client, made), "provider_mode_mismatch")
    run(client, "UPDATE meta SET value='meta' WHERE key='facebook_mode'")
    # Another shop's poster, named with that shop's own confirmation: as a poster that exists nowhere.
    _shop_b, password = second_shop(engine)
    theirs = TestClient(client.app, base_url=ORIGIN, headers=HEADERS)
    theirs.event_hooks["response"].extend(client.event_hooks["response"])
    assert theirs.post("/api/session", json=credentials(password, "boutique-deux")).status_code == 200
    before = written(client)
    nothing(send(client, posters(theirs, 1)), "facebook_stale")
    # A poster changed since its confirmation.
    changed(client, made[1][0])
    before = written(client)
    nothing(send(client, made), "facebook_stale")
    made[1] = (made[1][0], *confirm(client, made[1][0], png("blue")))
    assert posted(client, made)["status"] == "published"  # all of it was refused, nothing else


def test_a_session_ended_or_a_shop_suspended_before_the_lock_was_taken_admits_nothing(client, graph):
    made = posters(client, 1)
    connected(client)
    token, engine = client.cookies[auth.COOKIE], client.app.state.engine
    request = PostRequest.model_validate(body(client, made))
    for change in ("UPDATE shop_profile SET state='suspended' WHERE id=1", "DELETE FROM sessions WHERE token_hash=:hash"):
        run(client, change, hash=auth.token_hash(token))
        with pytest.raises(Refused) as refusal:
            facebook_posts._admit(engine, facebook.StubGraph(), 1, token, str(uuid4()), request, "x", MESSAGES)
        assert (refusal.value.code, refusal.value.status) == ("unauthenticated", 401) and rows(client) == []
        run(client, "UPDATE shop_profile SET state='active' WHERE id=1")


def test_the_shops_limit_none_at_and_over_and_its_sentence(client, graph):
    made = posters(client, 3)
    connected(client)
    run(client, "UPDATE shop_profile SET post_image_limit=2 WHERE id=1")
    over = send(client, made)
    refused(over, "facebook_too_many", 422)
    assert over.json()["error"]["message_fr"] == "Votre boutique peut mettre 2 images au plus dans une publication."
    assert rows(client) == [] and graph.requests == []
    assert client.get("/api/facebook/posts/candidates").json()["post_image_limit"] == 2
    assert posted(client, made[:2])["count"] == 2  # at the limit
    run(client, "UPDATE shop_profile SET post_image_limit=NULL WHERE id=1")
    assert client.get("/api/facebook/posts/candidates").json()["post_image_limit"] is None
    assert posted(client, made)["count"] == 3  # no limit


def test_a_post_in_flight_holds_the_shop_and_an_unknown_post_holds_its_posters(client, graph, monkeypatch):
    made = posters(client, 3)
    connected(client)
    key = str(uuid4())
    flying = a_post(client, "uploading", made[:1], key=key)
    monkeypatch.setitem(facebook_posts._TASKS, (1, key), None)  # its task alive
    refused(send(client, made[1:], seen=None), "facebook_running")
    monkeypatch.delitem(facebook_posts._TASKS, (1, key))  # its task gone: the request's own read settles it (§7)
    lost = a_post(client, "unknown", made[1:2])
    refused(send(client, made[1:], seen=[{"id": lost, "status": "unknown"}, None]), "facebook_pending")
    assert [(row["status"], row["error_code"]) for row in rows(client)] == [("failed", "not_sent"), ("unknown", None)]
    assert graph.requests == []
    assert client.get(f"/api/facebook/posts/{flying}").json()["message_fr"] == "La publication n’est pas partie. Rien n’a été publié. Réessayez."
    assert posted(client, made[2:], seen=None)["status"] == "published"  # another poster is free
    # The admission's own rule, when no read came first: a dead task's post does not hold the shop.
    request = PostRequest.model_validate(body(client, made[2:]))
    dead = a_post(client, "uploading", made[:1])
    answer, _post = facebook_posts._admit(client.app.state.engine, SimpleNamespace(mode="meta"), 1, client.cookies[auth.COOKIE],
                                          str(uuid4()), request, "x", MESSAGES)
    assert answer["status"] == "uploading" and rows(client)[-2]["id"] == dead and rows(client)[-2]["status"] == "failed"
    run(client, "UPDATE facebook_posts SET status='failed' WHERE id=:id", id=answer["id"])  # no task will run it


def test_seen_must_be_the_latest_post_with_its_status_and_the_owners_answer_makes_it_stale(client, graph):
    made = posters(client, 2)
    connected(client)
    graph.answers["feed"] = [httpx2.Response(502)]
    lost = posted(client, made[:1], seen=None)
    assert lost["status"] == "unknown" and lost["message_fr"] == MESSAGES["post_unknown"]
    old = {"id": lost["id"], "status": "unknown"}
    refused(send(client, made, seen=[old, None]), "facebook_pending")
    assert client.post(f"/api/facebook/posts/{lost['id']}/outcome", json={"present": True},
                       headers={"Idempotency-Key": str(uuid4())}).status_code == 200  # in another tab
    refused(send(client, made, seen=[old, None]), "facebook_stale")  # that tab had seen it unknown
    refused(send(client, made, seen=[None, None]), "facebook_stale")
    refused(send(client, made, seen=[old | {"id": str(uuid4())}, None]), "facebook_stale")
    again = posted(client, made, seen=[old | {"status": "published"}, None])
    assert again["status"] == "published" and len(graph.of("feed")) == 2
    # « Elle n’y est pas » makes a `seen` of it stale too.
    graph.answers["feed"] = [httpx2.Response(502)]
    lost = posted(client, made)
    old = [{"id": lost["id"], "status": "unknown"}] * 2
    assert client.post(f"/api/facebook/posts/{lost['id']}/outcome", json={"present": False},
                       headers={"Idempotency-Key": str(uuid4())}).json()["error_code"] == "not_published"
    refused(send(client, made, seen=old), "facebook_stale")
    assert posted(client, made, seen=[mark | {"status": "failed"} for mark in old])["status"] == "published"
    assert len(graph.of("feed")) == 4


def test_the_clock_stepping_back_does_not_hide_a_post_from_a_page_that_saw_the_one_before(client, graph):
    """Moved from the single poster's tests: a page saw post A. Post B, written after it, carries a time before A's: a
    page that saw A is still refused, and the candidate's `last` is B (the order is the rowid's, not the clock's)."""
    made = posters(client, 1)
    connected(client)
    a = posted(client, made)
    b = posted(client, made, seen={"id": a["id"], "status": "published"})
    run(client, "UPDATE facebook_posts SET sent_at='2020-01-01T00:00:00.000000+00:00' WHERE id=:id", id=b["id"])
    refused(send(client, made, seen={"id": a["id"], "status": "published"}), "facebook_stale")
    [candidate] = client.get("/api/facebook/posts/candidates", params={"ids": made[0][0]}).json()["items"]
    assert candidate["last"] == {"id": b["id"], "status": "published"} and len(graph.of("feed")) == 2


def test_the_same_key_twice_makes_one_post_whatever_the_moment(client, graph):
    made = posters(client, 2)
    connected(client)
    key, request, answers = str(uuid4()), body(client, made), []

    def during(_request):  # the same key sent again while its post uploads
        if not answers:
            answers.extend([send(client, key=key, request=request), len(facebook_posts._TASKS),
                            send(client, key=key, request=request | {"description": "x"})])

    graph.during = during
    first = send(client, key=key, request=request)
    assert first.status_code == 202
    post = settled(client, first.json()["id"])
    again, tasks, other = answers
    assert again.status_code == 202 and again.json()["id"] == post["id"] and again.json()["status"] == "uploading"
    assert tasks == 1 and other.json()["error"]["code"] == "idempotency_reused"
    replay = send(client, key=key, request=request)
    assert replay.json() == {k: v for k, v in post.items() if k != "description"}
    assert len(rows(client)) == 1 and len(graph.of("photos")) == 2 and len(graph.of("feed")) == 1


def test_the_same_key_sent_twice_at_once_makes_one_post_one_task_and_both_answer_its_row(client, graph, monkeypatch):
    """The second request arrives while the first's admission is held: it waits for it, then answers its row."""
    made = posters(client, 2)
    connected(client)
    key, request, admitted, prepared, answers = str(uuid4()), body(client, made), [], [], []
    go, twice, admit, prepare = threading.Event(), threading.Event(), facebook_posts._admit, facebook_posts._prepared

    def held(*args):
        admitted.append(1)
        assert go.wait(10)
        return admit(*args)

    def looked(*args):
        prepare(*args)
        prepared.append(1)
        if len(prepared) == 2:
            twice.set()

    monkeypatch.setattr(facebook_posts, "_admit", held)
    monkeypatch.setattr(facebook_posts, "_prepared", looked)
    sending = [threading.Thread(target=lambda: answers.append(send(client, key=key, request=request))) for _ in range(2)]
    sending[0].start()
    while not admitted:
        time.sleep(0.01)
    sending[1].start()
    assert twice.wait(10)  # the second has looked the key up and seen the files: now it finds the first's task
    time.sleep(0.2)
    go.set()
    for thread in sending:
        thread.join(10)
    quiet()
    assert len(admitted) == 1 and [answer.status_code for answer in answers] == [202, 202]
    assert len({answer.json()["id"] for answer in answers}) == 1 and len(rows(client)) == 1
    assert len(graph.of("photos")) == 2 and len(graph.of("feed")) == 1


def test_a_key_admitted_while_its_twin_looked_at_the_files_is_answered_with_its_row(client, graph, monkeypatch):
    """Both requests missed the first look-up; the first was admitted, then its file went: the second answers the row,
    not the preparation's refusal."""
    made = posters(client, 1)
    connected(client)
    key, request, twin = str(uuid4()), body(client, made), []

    def prepared(engine, settings, shop, post_request):
        if not twin:  # the twin's admission commits while this one looks at the files, which then fail
            twin.append(a_post(client, "published", made, key=key, digest=facebook_posts._digest(post_request)))
        raise Refused("export_missing", 503, field="items.0")

    monkeypatch.setattr(facebook_posts, "_prepared", prepared)
    answer = send(client, key=key, request=request)
    assert answer.status_code == 202 and answer.json()["id"] == twin[0] and answer.json()["status"] == "published"
    refused(send(client, made), "export_missing", 503)  # another key: the refusal, there is no row
    assert len(rows(client)) == 1 and graph.requests == []


@pytest.mark.parametrize("moment", ["before its commit", "after its commit"])
def test_a_client_that_goes_while_its_post_is_admitted_leaves_a_task_that_finishes(client, monkeypatch, moment):
    made = posters(client, 2)
    connected(client)
    engine, data = client.app.state.engine, SimpleNamespace(data_dir=Path(client.app.state.engine.url.database).parent)
    request = PostRequest.model_validate(body(client, made))
    entered, go, real = threading.Event(), threading.Event(), facebook_posts._admit

    def held(*args):
        if moment == "before its commit":
            entered.set()
            assert go.wait(10)
        answer = real(*args)
        held.read = facebook_posts.read(engine, 1, answer[0]["id"], MESSAGES)  # right after the commit
        if moment == "after its commit":  # the client goes now, before the route has its answer
            entered.set()
            assert go.wait(10)
        return answer

    monkeypatch.setattr(facebook_posts, "_admit", held)
    graph = Graph()

    async def gone():
        meta = facebook.MetaGraph(APP, SecretStr(SECRET), transport=httpx2.MockTransport(graph))
        route = asyncio.ensure_future(facebook_posts.publish(engine, data, meta, 1, client.cookies[auth.COOKIE],
                                                             str(uuid4()), request, MESSAGES))
        while not entered.is_set():
            await asyncio.sleep(0.01)
        route.cancel()  # the browser went
        with pytest.raises(asyncio.CancelledError):
            await route
        go.set()
        while facebook_posts._TASKS:
            await asyncio.sleep(0.01)

    asyncio.run(gone())
    assert (held.read["status"], held.read["message_fr"]) == ("uploading", "Envoi de l’image 1 sur 2…")  # not abandoned
    [row] = rows(client)
    assert (row["status"], row["post_id"]) == ("published", f"{PAGE}_1") and len(graph.of("photos")) == 2


def test_an_upload_without_an_answer_is_tried_once_more_and_only_once(client, graph):
    made = posters(client, 2)
    connected(client)
    graph.answers["photos"] = [httpx2.Response(503)]
    assert posted(client, made)["status"] == "published"
    assert len(graph.of("photos")) == 3 and len(graph.of("feed")) == 1  # two requests for the first image, one post
    assert made[0][2] in graph.of("photos")[1].content
    graph.requests.clear()
    graph.answers["photos"] = [None, httpx2.Response(500), httpx2.ConnectError("cut")]
    post = posted(client, made)
    assert (post["status"], post["error_code"], post["failed_position"], post["done"], post["message_fr"]) == (
        "failed", "no_answer", 1, 1, "Facebook n’a pas confirmé l’envoi de l’image 2. La publication n’a pas été envoyée. Réessayez.")
    assert len(graph.of("photos")) == 3 and graph.of("feed") == []


def test_a_stop_asked_while_a_first_try_was_out_ends_the_post_stopped_without_a_second_try(client, graph):
    made = posters(client, 2)
    connected(client)
    stops = []
    graph.during = lambda request: stops.append(client.post(f"/api/facebook/posts/{rows(client)[0]['id']}/stop"))
    graph.answers["photos"] = [httpx2.Response(503)]  # the first try of the first image: no answer
    post = posted(client, made)
    assert stops[0].json()["stop_asked"] is True
    assert (post["status"], post["error_code"], post["failed_position"], post["message_fr"]) == (
        "failed", "stopped", 0, "Envoi arrêté. Rien n’a été publié.")
    assert len(graph.of("photos")) == 1 and graph.of("feed") == []


@pytest.mark.parametrize("code, message, state", [
    (100, "L’image 2 n’a pas pu être envoyée (code 100). Rien n’a été publié. Retirez l’image 2 ou remplacez-la, puis réessayez.", "connected"),
    (190, "Image 2 : Reconnectez votre Page. Rien n’a été publié.", "reconnect"),
    (200, "Image 2 : Facebook a refusé la publication (code 200) : l’autorisation manque. Rien n’a été publié. Reconnectez votre Page en l’autorisant ; si cela se répète, contactez l’opérateur.", "connected"),
    (4, "Image 2 : Facebook limite les publications pour le moment. Rien n’a été publié. Réessayez plus tard.", "connected"),
])
def test_a_refused_upload_names_its_image_and_publishes_nothing(client, graph, code, message, state):
    made = posters(client, 3)
    connected(client)
    graph.answers["photos"] = [None, httpx2.Response(400, json={"error": {"code": code, "message": " ".join(SENSITIVE)}})]
    post = posted(client, made)
    assert (post["status"], post["error_code"], post["failed_position"], post["message_fr"]) == ("failed", str(code), 1, message)
    assert len(graph.of("photos")) == 2 and graph.of("feed") == [] and page_state(client) == state  # never tried again


def test_an_upload_answered_with_a_post_stops_the_post_and_says_the_photo_is_public(client, graph):
    made = posters(client, 2)
    connected(client)
    graph.answers["photos"] = [httpx2.Response(200, json={"id": "9", "post_id": f"{PAGE}_5"})]
    post = posted(client, made)
    assert (post["error_code"], post["message_fr"]) == ("published", MESSAGES["post_photo_public"].format(n=1))
    graph.answers["photos"] = [httpx2.Response(200, json={"id": "9", "post_id": "222_5"})]
    post = posted(client, made)
    assert (post["error_code"], post["message_fr"]) == ("unexpected", MESSAGES["post_unexpected"].format(n=1))
    assert len(graph.of("photos")) == 2 and graph.of("feed") == []


def test_a_poster_changed_before_the_first_upload_stops_the_post_and_after_it_its_confirmed_file_goes(client, graph,
                                                                                                    monkeypatch):
    made = posters(client, 2)
    connected(client)
    real = facebook_posts._admit

    def admitted(*args):  # a newer confirmation of the second poster, right after the admission
        answer = real(*args)
        confirm(client, made[1][0], png("blue"))
        return answer

    monkeypatch.setattr(facebook_posts, "_admit", admitted)
    post = posted(client, made)
    assert (post["status"], post["error_code"], post["failed_position"], post["message_fr"]) == (
        "failed", "poster_changed", 1, "L’affiche 2 a changé avant l’envoi. Rien n’a été publié. Vérifiez-la à nouveau.")
    assert graph.requests == []
    monkeypatch.setattr(facebook_posts, "_admit", real)
    made = posters(client, 2)
    graph.during = lambda request: confirm(client, made[1][0], png("green")) if len(graph.requests) == 1 else None
    assert posted(client, made)["status"] == "published"
    assert made[1][2] in graph.of("photos")[1].content  # the file confirmed when the post was admitted


def test_a_damaged_file_fails_the_post_and_names_its_image(client, graph, tmp_path):
    made = posters(client, 2)
    connected(client)
    path = assets.path(tmp_path, sha(made[1][2]), "png")
    graph.during = lambda request: path.write_bytes(b"damaged")
    post = posted(client, made)
    assert (post["status"], post["error_code"], post["failed_position"], post["message_fr"]) == (
        "failed", "export_missing", 1, "Le fichier de l’image 2 est introuvable ou abîmé. Rien n’a été publié. Vérifiez cette affiche à nouveau.")
    assert len(graph.of("photos")) == 1 and graph.of("feed") == []


def test_stop_during_the_uploads_publishes_nothing_and_a_settled_post_is_answered_as_it_is(client, graph):
    made = posters(client, 3)
    connected(client)
    stops = []
    graph.during = lambda request: stops.append(client.post(f"/api/facebook/posts/{rows(client)[0]['id']}/stop")) if not stops else None
    post = posted(client, made)
    assert (stops[0].status_code, stops[0].json()["status"], stops[0].json()["stop_asked"]) == (200, "uploading", True)
    assert (post["status"], post["error_code"], post["failed_position"], post["message_fr"], post["stop_asked"]) == (
        "failed", "stopped", 1, "Envoi arrêté. Rien n’a été publié.", True)
    assert len(graph.of("photos")) == 1 and graph.of("feed") == []
    graph.during = None
    done = posted(client, made)
    again = client.post(f"/api/facebook/posts/{done['id']}/stop")
    assert again.json() == {k: v for k, v in done.items() if k != "description"} and rows(client)[1]["stop_asked"] == 0
    refused(client.post(f"/api/facebook/posts/{uuid4()}/stop"), "not_found", 404)


CHANGES = {
    "disconnected": ("DELETE FROM facebook_pages WHERE shop_id=1", "page_changed"),
    "replaced": ("UPDATE facebook_pages SET connected_at='2026-11-21T09:00:00.000000+00:00' WHERE shop_id=1", "page_changed"),
    "suspended": ("UPDATE shop_profile SET state='suspended' WHERE id=1", "not_sent"),
    "limit lowered": ("UPDATE shop_profile SET post_image_limit=1 WHERE id=1", "limit_lowered"),
}


@pytest.mark.parametrize("moment", ["after the admission", "before an upload", "at the last check"])
@pytest.mark.parametrize("change", list(CHANGES))
def test_a_page_changed_a_shop_suspended_or_a_limit_lowered_stops_the_post_before_its_last_call(client, graph, monkeypatch,
                                                                                               change, moment):
    made = posters(client, 2)
    connected(client)
    sql, code = CHANGES[change]
    if moment == "after the admission":
        real = facebook_posts._admit
        monkeypatch.setattr(facebook_posts, "_admit", lambda *args: (real(*args), run(client, sql))[0])
    else:
        graph.during = lambda request: run(client, sql) if len(graph.requests) == (1 if moment == "before an upload" else 2) else None
    send(client, made)
    quiet()
    run(client, "UPDATE shop_profile SET state='active' WHERE id=1")  # to read it through the routes
    [post] = client.get("/api/facebook/posts").json()["items"]
    position = {"after the admission": 0, "before an upload": 1, "at the last check": None}[moment]
    assert (post["status"], post["error_code"], post["failed_position"]) == ("failed", code, position)
    assert post["message_fr"] == MESSAGES[f"post_{code}"] and graph.of("feed") == []
    assert len(graph.of("photos")) == {"after the admission": 0, "before an upload": 1, "at the last check": 2}[moment]


def test_a_190_marks_the_page_to_reconnect_only_if_it_is_still_the_page_that_gave_the_token(client, graph):
    made = posters(client, 2)
    connected(client)
    graph.answers["feed"] = [httpx2.Response(400, json={"error": {"code": 190}})]
    post = posted(client, made)
    assert (post["error_code"], post["failed_position"], post["message_fr"]) == ("190", None, "Reconnectez votre Page. Rien n’a été publié.")
    assert page_state(client) == "reconnect"
    connected(client)
    graph.answers["photos"] = [httpx2.Response(400, json={"error": {"code": 190}})]
    graph.during = lambda request: connected(client, token=OTHER_TOKEN, at=utc_now())  # the owner reconnected meanwhile
    assert posted(client, made)["message_fr"] == "Image 1 : Reconnectez votre Page. Rien n’a été publié."
    assert page_state(client) == "connected"
    graph.during, graph.answers["feed"] = None, [httpx2.Response(400, json={"error": {"code": 190}})]
    posted(client, made)
    assert fields(graph.of("photos")[-1])["access_token"] == OTHER_TOKEN and page_state(client) == "reconnect"


@pytest.mark.parametrize("answer", [httpx2.Response(500, json={"error": {"code": 190}}), httpx2.Response(503, content=b"down"),
                                    httpx2.ConnectError("cut"), httpx2.ReadTimeout("slow"),
                                    httpx2.Response(200, json={"id": "9"}), httpx2.Response(400, json={"error": {"code": 9999}})])
def test_a_last_call_without_a_clear_answer_is_unknown_and_nothing_is_sent_again_or_deleted(client, graph, answer):
    made = posters(client, 2)
    connected(client)
    graph.answers["feed"] = [answer]
    post = posted(client, made)
    assert (post["status"], post["error_code"], post["link"], post["message_fr"]) == ("unknown", None, None, MESSAGES["post_unknown"])
    assert MESSAGES["post_unknown"] == "Je ne sais pas si la publication est sur votre Page. Ouvrez votre Page et dites-le-moi."
    assert len(graph.of("feed")) == 1 and [request.method for request in graph.requests] == ["POST"] * 3


@pytest.mark.parametrize("code, message", [
    (506, "Facebook a refusé la publication (code 506). Rien n’a été publié."),
    (10, "Facebook a refusé la publication (code 10) : l’autorisation manque. Rien n’a été publié. Reconnectez votre Page en l’autorisant ; si cela se répète, contactez l’opérateur."),
    (368, "Facebook limite les publications pour le moment. Rien n’a été publié. Réessayez plus tard."),
])
def test_a_post_refused_by_facebook_says_so_without_an_image(client, graph, code, message):
    connected(client)
    graph.answers["feed"] = [httpx2.Response(400, json={"error": {"code": code}})]
    post = posted(client, posters(client, 1))
    assert (post["status"], post["error_code"], post["failed_position"], post["message_fr"]) == ("failed", str(code), None, message)


def test_while_facebook_takes_its_time_no_lock_is_held(client, graph):
    """During each call another connection writes at once (busy_timeout would make it wait 5 s, then fail)."""
    made = posters(client, 2)
    connected(client)
    seen = []

    def during(request):
        with write_tx(client.app.state.engine) as conn:
            conn.execute(text("INSERT OR REPLACE INTO meta VALUES ('probe','x')"))
            seen.append(conn.execute(text("SELECT status FROM facebook_posts")).scalar())

    graph.during = during
    assert posted(client, made)["status"] == "published" and seen == ["uploading", "uploading", "posting"]


def test_a_post_held_back_over_thirty_seconds_after_its_cutoff_does_not_send(client, graph, monkeypatch):
    """The module's monotonic clock jumps 31 s at every commit: the window counts from before the commit of 'posting',
    so the time a commit takes counts in it (sampled after the commit, the call would leave)."""
    made = posters(client, 2)
    connected(client)
    clock = [1000.0]
    monkeypatch.setattr(facebook_posts, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    jump = lambda conn: clock.__setitem__(0, clock[0] + 31)  # noqa: E731
    event.listen(client.app.state.engine, "commit", jump)
    try:
        post = posted(client, made)
    finally:
        event.remove(client.app.state.engine, "commit", jump)
    assert (post["status"], post["error_code"], post["failed_position"], post["message_fr"]) == (
        "failed", "not_sent", None, "La publication n’est pas partie. Rien n’a été publié. Réessayez.")
    assert len(graph.of("photos")) == 2 and graph.of("feed") == []


def test_the_settling_write_that_fails_is_tried_again_and_the_last_call_is_never_sent_twice(client, graph, monkeypatch):
    made = posters(client, 2)
    connected(client)
    real, failures = facebook_posts._settled, []

    def flaky(*args):
        if len(failures) < facebook_posts.SETTLE_RETRIES:
            failures.append(1)
            raise OperationalError("UPDATE", {}, Exception("database is locked"))
        return real(*args)

    monkeypatch.setattr(facebook_posts, "_settled", flaky)
    assert posted(client, made)["status"] == "published" and len(failures) == 3 and len(graph.of("feed")) == 1
    # Failing every time: the task ends with the post 'posting'; its next read makes it unknown, never sends again.
    monkeypatch.setattr(facebook_posts, "_settled", lambda *args: (_ for _ in ()).throw(OSError("disk")))
    post = posted(client, made)
    assert (post["status"], post["message_fr"]) == ("unknown", MESSAGES["post_unknown"]) and len(graph.of("feed")) == 2


def test_a_post_that_no_task_holds_is_settled_by_the_routes_read_without_overwriting_a_task(client, graph):
    made = posters(client, 2)
    connected(client)
    uploading, posting = a_post(client, "uploading", made[:1]), a_post(client, "posting", made[1:])
    assert client.get(f"/api/facebook/posts/{uploading}").json()["status"] == "failed"  # one read settles the shop's
    [newest, oldest] = client.get("/api/facebook/posts").json()["items"]
    assert (newest["id"], newest["status"], newest["error_code"]) == (posting, "unknown", None)
    assert (oldest["id"], oldest["status"], oldest["error_code"], oldest["settled_at"] is not None) == (
        uploading, "failed", "not_sent", True)
    # A row read 'uploading' whose task settled it meanwhile: the update names the status it read.
    done = a_post(client, "published", made[:1], post=f"{PAGE}_9", link=f"https://www.facebook.com/{PAGE}_9")
    with write_tx(client.app.state.engine) as conn:
        facebook_posts._abandoned(conn, [{"id": done, "shop_id": 1, "key": str(uuid4()), "status": "uploading"}])
    assert rows(client)[-1]["status"] == "published"


def test_at_start_a_post_in_flight_is_settled_and_a_settled_one_is_left(env, tmp_path, password_hash, graph):
    settings = settings_for(env, tmp_path, password_hash, "meta")
    with TestClient(create_app(settings, prepare=credited), base_url=ORIGIN, headers=HEADERS) as client:
        login(client)
        made = posters(client, 3)
        for n, status in enumerate(("uploading", "posting", "published")):
            a_post(client, status, made[n:n + 1])
    with TestClient(create_app(settings), base_url=ORIGIN, headers=HEADERS) as again:  # the server starts again
        assert [(row["status"], row["error_code"]) for row in rows(again)] == [
            ("failed", "not_sent"), ("unknown", None), ("published", None)]


def test_shutdown_stops_a_post_uploading_and_lets_a_last_call_on_its_way_finish(env, tmp_path, password_hash, graph):
    settings = settings_for(env, tmp_path, password_hash, "meta")
    with TestClient(create_app(settings, prepare=credited), base_url=ORIGIN, headers=HEADERS) as client:
        login(client)
        engine = client.app.state.engine
        shop_b, password = second_shop(engine)
        b = TestClient(client.app, base_url=ORIGIN, headers=HEADERS)  # B's own requests; its post goes through the
        assert b.post("/api/session", json=credentials(password, "boutique-deux")).status_code == 200  # app's loop
        connected(client)
        connected(client, page="333", name="Boutique Deux", token="page-token-of-the-page-333", shop=shop_b)
        mine, theirs = posters(client, 1), posters(b, 1)

        def during(request):  # both wait for the shutdown: A's last call, B's first image
            if request.url.path.endswith(f"/{PAGE}/feed") or request.url.path.endswith("/333/photos"):
                while not facebook_posts.CLOSING.is_set():
                    time.sleep(0.01)

        graph.during = during
        graph.answers["photos"] = [None, httpx2.Response(503)]
        assert send(client, mine).status_code == 202
        while not graph.of("feed"):
            time.sleep(0.01)
        answer = client.post("/api/facebook/posts", json=body(b, theirs, page="333"),
                             headers={"Idempotency-Key": str(uuid4()), "Cookie": f"{auth.COOKIE}={b.cookies[auth.COOKIE]}"})
        assert answer.status_code == 202, answer.text
        while len(graph.of("photos")) < 2:
            time.sleep(0.01)
    # The lifespan drained both before the data folder's lock went.
    assert not facebook_posts._TASKS and not facebook_posts.CLOSING.is_set()
    assert [(row["shop_id"], row["status"], row["error_code"], row["failed_position"]) for row in rows(client)] == [
        (1, "published", None, None), (shop_b, "failed", "not_sent", 0)]
    assert len(graph.of("photos")) == 2 and len(graph.of("feed")) == 1  # B's image was not tried again


def test_the_owners_two_answers_close_an_unknown_post_and_replay(client, graph, monkeypatch):
    made = posters(client, 2)
    connected(client)
    graph.answers["feed"] = [httpx2.Response(502)]
    lost = posted(client, made)

    def outcome(id, present, key=None):
        return client.post(f"/api/facebook/posts/{id}/outcome", json={"present": present},
                           headers={"Idempotency-Key": key or str(uuid4())})

    key = str(uuid4())
    there = outcome(lost["id"], True, key)
    assert there.status_code == 200 and there.json() | {"settled_at": None} == {
        k: v for k, v in lost.items() if k != "description"} | {
        "status": "published", "said_by_owner": True, "link": f"https://www.facebook.com/{PAGE}", "settled_at": None,
        "message_fr": "Présence confirmée par vous"}
    assert outcome(lost["id"], True, key).json() == there.json()  # the stored answer, replayed
    refused(outcome(lost["id"], False, key), "idempotency_reused")
    refused(outcome(lost["id"], False), "facebook_settled")  # a new key: the post has its result
    assert len(graph.of("feed")) == 1  # the app never looks on the Page, never sends again by itself
    graph.answers["feed"] = [httpx2.Response(502)]
    lost = posted(client, made)
    absent = outcome(lost["id"], False).json()
    assert (absent["status"], absent["error_code"], absent["said_by_owner"], absent["message_fr"]) == (
        "failed", "not_published", False, "Vous avez dit qu’elle n’est pas sur votre Page.")
    assert posted(client, made)["status"] == "published"  # a new post is admitted, after the warning
    key = str(uuid4())
    flying = a_post(client, "posting", made[:1], key=key)
    monkeypatch.setitem(facebook_posts._TASKS, (1, key), None)  # its task alive
    refused(outcome(flying, True), "facebook_running")
    monkeypatch.delitem(facebook_posts._TASKS, (1, key))  # its task gone: the next read makes it unknown, then he says
    assert outcome(flying, False).json()["status"] == "failed"
    refused(outcome(str(uuid4()), True), "not_found", 404)


def test_excluded_lists_only_this_shops_active_missing_files(client):
    path = "/api/facebook/posts/excluded"
    other = TestClient(client.app, base_url=ORIGIN, headers=HEADERS)
    assert other.get(path).status_code == 401
    _, password = second_shop(client.app.state.engine)
    assert other.post("/api/session", json=credentials(password, "boutique-deux")).is_success
    theirs = create_draft(other)["id"]
    assert client.get(path).json() == {"items": [], "next_cursor": None}

    never, archived = (create_draft(client)["id"] for _ in range(2))
    wrong, stale, eligible = posters(client, 3)
    also_square, _ = confirm(client, eligible[0])
    run(client, "UPDATE confirmations SET format='square' WHERE id=:id", id=also_square)
    run(client, "UPDATE confirmations SET format='square' WHERE id=:id", id=wrong[1])
    changed(client, stale[0])
    run(client, "UPDATE creations SET status='abandoned' WHERE id=:id", id=archived)
    run(client, "UPDATE creations SET created_at='2026-01-01T00:00:00+00:00'")

    # The exclusions read must leave an interrupted send for the normal post-recovery route.
    a_post(client, "posting", [eligible])
    before = written(client)
    reasons = {never: "unconfirmed", wrong[0]: "other_format", stale[0]: "changed"}
    first = client.get(path, params={"limit": 2}).json()
    assert len(first["items"]) == 2 and first["next_cursor"]
    last = client.get(path, params={"limit": 2, "before": first["next_cursor"]}).json()
    assert last["next_cursor"] is None
    items = first["items"] + last["items"]
    assert [item["id"] for item in items] == sorted(reasons, reverse=True)
    for item in items:
        assert item == {"id": item["id"], "reason": reasons[item["id"]], "primary_format": "feed",
                        "name": "JBL", "title": "JBL Flip"}
    assert [item["id"] for item in other.get(path).json()["items"]] == [theirs]
    refused(client.get(path, params={"before": "broken"}), "invalid_cursor", 422)
    for limit in (0, 51):
        assert client.get(path, params={"limit": limit}).status_code == 422
    assert written(client) == before
    candidates = client.get("/api/facebook/posts/candidates").json()
    assert [(item["id"], item["confirmation_id"]) for item in candidates["items"]] == [(eligible[0], eligible[1])]
    assert candidates["left_out"] == {reason: 1 for reason in reasons.values()}
    resolved = client.get("/api/facebook/posts/candidates", params={"ids": ",".join(reasons)}).json()
    assert {item["id"]: item["reason"] for item in resolved["items"]} == reasons


def test_pending_alternative_keeps_current_feed_file_in_facebook_picker(client, graph):
    from affiche.posters import visuals
    from test_poster_visuals import fixed, scene, wait_job

    engine = client.app.state.engine
    service = client.app.state.poster_service
    service.provider.delay = 0
    creation = create_draft(client)

    def generate(poster):
        plan = fixed(engine, service.settings, poster)
        job = scene(engine, service.settings, poster, plan)
        return wait_job(client, job["status_url"])

    first = generate(creation)
    visuals.decide(engine, 1, str(uuid4()), first, visuals.Decision(
        action="approve", checks={key: True for key in visuals.CHECKS | visuals.TEXT_CHECKS}))
    current = client.get(f'/api/creations/{creation["id"]}').json()
    confirmation, data = confirm(client, creation["id"])
    alternative = generate(current)
    assert alternative != first
    assert client.get(f"/api/visuals/{alternative}").json()["status"] == "pending_review"
    assert client.get("/api/creations").json()["items"][0]["state"] == "to_review"

    assert client.get("/api/facebook/posts/excluded").json() == {"items": [], "next_cursor": None}
    picker = client.get("/api/facebook/posts/candidates").json()
    assert picker["left_out"] == {"other_format": 0, "changed": 0, "unconfirmed": 0}
    [item] = picker["items"]
    assert (item["id"], item["confirmation_id"]) == (creation["id"], confirmation)
    assert client.get(item["download_url"]).content == data
    assert not graph.requests


def test_the_candidates_their_pages_their_marks_and_the_posters_left_out(client, graph):
    made = posters(client, 3)
    never, other, abandoned = (create_draft(client)["id"] for _ in range(3))
    shifted, _ = confirm(client, other)
    run(client, "UPDATE confirmations SET format='square' WHERE id=:id", id=shifted)
    later = posters(client, 1)[0]
    changed(client, later[0])
    run(client, "UPDATE creations SET status='abandoned' WHERE id=:id", id=abandoned)
    first = client.get("/api/facebook/posts/candidates", params={"limit": 2}).json()
    assert first["page"] is None and first["post_image_limit"] is None
    assert first["left_out"] == {"other_format": 1, "changed": 1, "unconfirmed": 1}
    rest = client.get("/api/facebook/posts/candidates", params={"limit": 2, "before": first["next_cursor"]}).json()
    assert rest["next_cursor"] is None and [item["id"] for item in first["items"] + rest["items"]] == [m[0] for m in made[::-1]]
    creation, confirmation, data = made[0]
    poster = client.get(f"/api/creations/{creation}").json()["document"]["offer"]
    assert rest["items"][0] == {"id": creation, "name": "JBL", "title": poster["title"], "price_ar": poster["price_ar"],
                                "confirmation_id": confirmation, "thumbnail_url": f"/api/thumbnails/{sha(data)}?v=1",
                                "download_url": f"/api/confirmations/{confirmation}/download", "last": None, "published_at": None,
                                "pending": False}
    assert client.get(rest["items"][0]["thumbnail_url"]).status_code == 200
    assert client.get(rest["items"][0]["download_url"]).content == data
    # With ids: each a candidate or its reason, in the order asked, whatever page it is on.
    gone = str(uuid4())
    asked = client.get("/api/facebook/posts/candidates", params={"ids": ",".join(
        [made[0][0], other, later[0], never, abandoned, gone, made[0][0]])}).json()
    assert asked["next_cursor"] is None and asked["items"] == [rest["items"][0], {"id": other, "reason": "other_format"},
        {"id": later[0], "reason": "changed"}, {"id": never, "reason": "unconfirmed"},
        {"id": abandoned, "reason": "gone"}, {"id": gone, "reason": "gone"}]
    for ids in ("x", ",".join(str(uuid4()) for _ in range(201)), ""):
        refused(client.get("/api/facebook/posts/candidates", params={"ids": ids}), "validation_error", 422)
    # `last` and `published_at`, on the connected Page.
    connected(client)
    published = posted(client, made[:2])
    graph.answers["feed"] = [httpx2.Response(502)]
    lost = posted(client, made[1:])
    marks = {item["id"]: (item["last"], item["published_at"], item["pending"])
             for item in client.get("/api/facebook/posts/candidates").json()["items"]}
    assert marks == {made[0][0]: ({"id": published["id"], "status": "published"}, published["sent_at"], False),
                     made[1][0]: ({"id": lost["id"], "status": "unknown"}, published["sent_at"], True),
                     made[2][0]: ({"id": lost["id"], "status": "unknown"}, None, True)}
    assert client.get("/api/facebook/posts/candidates").json()["page"] == {"id": PAGE, "name": NAME, "state": "connected"}
    run(client, "UPDATE facebook_pages SET state='reconnect'")  # the same Page, to reconnect: no marks, its state said
    reconnect = client.get("/api/facebook/posts/candidates").json()
    assert reconnect["page"] == {"id": PAGE, "name": NAME, "state": "reconnect"}
    assert all(item["last"] is item["published_at"] is None and not item["pending"] for item in reconnect["items"])
    run(client, "DELETE FROM facebook_pages")
    none = client.get("/api/facebook/posts/candidates").json()
    assert none["page"] is None and all(item["last"] is item["published_at"] is None for item in none["items"])
    connected(client, page="333", name="Boutique Deux", at=utc_now())  # another Page: nothing posted there
    assert all(item["last"] is item["published_at"] is None for item in client.get("/api/facebook/posts/candidates").json()["items"])


def test_an_older_unknown_post_beside_a_later_settled_one_holds_its_poster(client, graph):
    """After a restore (D-FB-POST-006), an older post can be unknown while a later post of the same poster is settled:
    `last` says settled, `pending` says what the admission refuses, with the admission's own rule."""
    made = posters(client, 1)
    connected(client)
    older = a_post(client, "published", made)
    later = posted(client, made)
    run(client, "UPDATE facebook_posts SET status='unknown' WHERE id=:id", id=older)  # brought back unknown by a restore
    [candidate] = client.get("/api/facebook/posts/candidates", params={"ids": made[0][0]}).json()["items"]
    assert candidate["last"] == {"id": later["id"], "status": "published"} and candidate["pending"] is True
    refused(send(client, made, seen=candidate["last"]), "facebook_pending")
    assert len(graph.of("feed")) == 1
    [listed] = client.get("/api/facebook/posts/candidates").json()["items"]
    assert listed["pending"] is True


def test_the_list_newest_first_by_page_and_by_poster(client, graph):
    made = posters(client, 2)
    connected(client)
    first, second = posted(client, made[:1]), posted(client, made)
    run(client, "UPDATE facebook_posts SET sent_at='2020-01-01T00:00:00.000000+00:00' WHERE id=:id", id=second["id"])
    answer = client.get("/api/facebook/posts", params={"limit": 1}).json()  # by rowid, not by the clock's sent_at
    assert [item["id"] for item in answer["items"]] == [second["id"]] and answer["next_cursor"] == second["id"]
    rest = client.get("/api/facebook/posts", params={"limit": 1, "before": answer["next_cursor"]}).json()
    assert [item["id"] for item in rest["items"]] == [first["id"]] and rest["next_cursor"] is None
    assert "description" not in rest["items"][0] and rest["items"][0]["count"] == 1
    holding = client.get("/api/facebook/posts", params={"creation": made[1][0]}).json()["items"]
    assert [item["id"] for item in holding] == [second["id"]]
    assert len(client.get("/api/facebook/posts", params={"creation": made[0][0]}).json()["items"]) == 2
    refused(client.get("/api/facebook/posts", params={"creation": str(uuid4())}), "not_found", 404)
    refused(client.get("/api/facebook/posts", params={"before": str(uuid4())}), "invalid_cursor", 422)
    refused(client.get(f"/api/facebook/posts/{uuid4()}"), "not_found", 404)


def test_off_answers_not_found_on_the_post_routes(env, tmp_path, password_hash):
    with TestClient(create_app(settings_for(env, tmp_path, password_hash, None), prepare=credited), base_url=ORIGIN,
                    headers=HEADERS) as client:
        login(client)
        id, key = str(uuid4()), {"Idempotency-Key": str(uuid4())}
        for answer in (client.get("/api/facebook/posts/candidates"), client.get("/api/facebook/posts/excluded"),
                       client.get("/api/facebook/posts"),
                       client.post("/api/facebook/posts", json={}, headers=key), client.get(f"/api/facebook/posts/{id}"),
                       client.post(f"/api/facebook/posts/{id}/stop"),
                       client.post(f"/api/facebook/posts/{id}/outcome", json={"present": True}, headers=key)):
            refused(answer, "not_found", 404)


def test_the_stand_in_walks_a_refused_image_an_unknown_post_and_a_stop_through_the_routes(env, tmp_path, password_hash):
    with TestClient(create_app(settings_for(env, tmp_path, password_hash, "stub"), prepare=credited), base_url=ORIGIN,
                    headers=HEADERS) as client:
        login(client)
        page = facebook.StubGraph.PAGES[0]
        connected(client, page=page.id, name=page.name, token=page.token)
        made = posters(client, 3)
        published = posted(client, made, page=page.id, description="Promo")
        assert published["status"] == "published" and published["link"].startswith(f"https://www.facebook.com/{page.id}_")
        refusal = posted(client, made, page=page.id, description="Promo [stub:image:2]")
        assert (refusal["failed_position"], refusal["message_fr"]) == (
            1, "L’image 2 n’a pas pu être envoyée (code 100). Rien n’a été publié. Retirez l’image 2 ou remplacez-la, puis réessayez.")
        unknown = posted(client, made, page=page.id, description="[stub:unknown]")
        assert unknown["status"] == "unknown"
        assert client.post(f"/api/facebook/posts/{unknown['id']}/outcome", json={"present": False},
                           headers={"Idempotency-Key": str(uuid4())}).json()["status"] == "failed"
        slow = send(client, made, page=page.id, description="[stub:slow]").json()
        assert client.post(f"/api/facebook/posts/{slow['id']}/stop").json()["stop_asked"] is True
        stopped = settled(client, slow["id"])
        assert (stopped["status"], stopped["error_code"], stopped["failed_position"], stopped["done"]) == ("failed", "stopped", 1, 1)
        listed = client.get("/api/facebook/posts").text
        assert page.token not in listed and all(item["photo_id"] not in listed for item in rows(client, "facebook_post_items")
                                                if item["photo_id"])
