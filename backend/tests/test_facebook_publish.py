"""Publishing a confirmed poster on the shop's Facebook Page through the routes (D-FB-PUBLISH-003): prepared, admitted,
sent, settled; the answers' table; never twice; the owner's word on an unknown outcome; the start-up rule. Facebook is
httpx2.MockTransport (`meta`) or the stand-in (`stub`): nothing leaves the machine. The confirmed poster is written
straight into the database, as the smokes do: its rows and its PNG, without a render."""
import asyncio
import io
import json
import logging
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx2
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from affiche import assets
from affiche.api import MESSAGES, create_app
from affiche.db import utc_now, write_tx
from affiche.posters import auth, facebook, facebook_publish
from affiche.posters.facebook_publish import PublishRequest
from affiche.posters.store import Refused
from test_api import HEADERS, ORIGIN, create_draft, credentials, login, password_hash, second_shop  # noqa: F401
from test_config import env  # noqa: F401
from test_db import credited, unaccepted
from test_facebook import fields
from test_facebook_api import APP, SECRET, settings_for

PAGE, TOKEN, OTHER_TOKEN = "111", "page-token-of-the-page-111", "page-token-reconnected-111"
SENSITIVE = (SECRET, TOKEN, OTHER_TOKEN)
EARLIER = "2026-11-20T08:00:00.000000+00:00"


class Photos:
    """Facebook's photo endpoint. `answer`: a Response, an exception raised, or None for a published post of the Page
    named in the address. `during` runs inside the call, as Facebook takes its time."""
    def __init__(self):
        self.requests, self.answer, self.during = [], None, None

    def __call__(self, request):
        self.requests.append(request)
        if self.during:
            self.during(request)
        if isinstance(self.answer, Exception):
            raise self.answer
        page = request.url.path.split("/")[2]
        return self.answer or httpx2.Response(200, json={"id": "9", "post_id": f"{page}_{len(self.requests)}"})


@pytest.fixture
def photos(monkeypatch):
    photos, real = Photos(), facebook.make_graph
    monkeypatch.setattr(facebook, "make_graph", lambda settings: real(settings, httpx2.MockTransport(photos)))
    return photos


@pytest.fixture
def client(env, tmp_path, password_hash, photos, caplog):
    caplog.set_level(logging.DEBUG)
    answers = []  # every answer of the test: no token or secret may reach the browser
    with TestClient(create_app(settings_for(env, tmp_path, password_hash, "meta"), prepare=credited), base_url=ORIGIN,
                    headers=HEADERS) as client:
        client.event_hooks["response"].append(answers.append)
        login(client)
        yield client
        for answer in answers:
            assert not any(value in answer.text for value in SENSITIVE), (answer.request.url.path, answer.text)
    assert not any(value in caplog.text for value in SENSITIVE)


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


def poster(client, data=None) -> tuple[str, str, bytes]:
    creation = create_draft(client)["id"]
    return creation, *confirm(client, creation, data)


def publish(client, creation, confirmation, caption="Casque JBL, 899 000 Ar", seen=None, key=None, page=PAGE):
    return client.post(f"/api/creations/{creation}/publications",
                       json={"confirmation_id": confirmation, "page_id": page, "caption": caption, "seen": seen},
                       headers={"Idempotency-Key": key or str(uuid4())})


def outcome(client, creation, publication, present, key=None):
    return client.post(f"/api/creations/{creation}/publications/{publication}/outcome", json={"present": present},
                       headers={"Idempotency-Key": key or str(uuid4())})


def listed(client, creation):
    answer = client.get(f"/api/creations/{creation}/publications")
    assert answer.status_code == 200, answer.text
    return answer.json()["items"]


def test_the_list_carries_the_shops_page_without_its_token(client):
    """The final panel reads the Page here, not from the card's route, whose read takes the refusal kept for the card."""
    creation, _confirmation, _data = poster(client)
    assert client.get(f"/api/creations/{creation}/publications").json() == {"page": None, "items": []}
    connected(client)
    assert client.get(f"/api/creations/{creation}/publications").json() == {
        "page": {"id": PAGE, "name": "Original Phone Mada", "state": "connected"}, "items": []}


def refused(answer, code, status=409):
    assert (answer.status_code, answer.json()["error"]["code"]) == (status, code), answer.text


def written(client):
    """Everything an admission could write: the publications, the Pages and the data folder's Facebook mode."""
    with client.app.state.engine.connect() as conn:
        return ([dict(row) for row in conn.execute(text("SELECT * FROM facebook_publications ORDER BY sent_at")).mappings()],
                [dict(row) for row in conn.execute(text("SELECT * FROM facebook_pages ORDER BY shop_id")).mappings()],
                conn.execute(text("SELECT value FROM meta WHERE key='facebook_mode'")).scalar())


def rows(client):
    return written(client)[0]


def page_state(client, shop=1):
    with client.app.state.engine.connect() as conn:
        return conn.execute(text("SELECT state FROM facebook_pages WHERE shop_id=:shop"), {"shop": shop}).scalar()


def test_a_confirmed_poster_is_published_with_its_own_bytes_and_caption(client, photos):
    creation, confirmation, data = poster(client)
    connected(client)
    answer = publish(client, creation, confirmation, caption="Casque JBL\n\tà 899 000 Ar 🎧")
    assert answer.status_code == 201, answer.text
    body = answer.json()
    assert body == {"id": body["id"], "status": "published", "page_id": PAGE, "page_name": "Original Phone Mada",
                    "sent_at": body["sent_at"], "settled_at": body["settled_at"], "link": f"https://www.facebook.com/{PAGE}_1",
                    "error_code": None, "said_by_owner": False, "message_fr": "Publié sur Original Phone Mada."}
    [request] = photos.requests
    assert (request.method, request.url.path) == ("POST", f"/v27.0/{PAGE}/photos")
    assert fields(request)["caption"] == "Casque JBL\n\tà 899 000 Ar 🎧" and data in request.content  # the downloaded file
    assert fields(request)["access_token"] == TOKEN and fields(request)["appsecret_proof"]
    [row] = rows(client)
    assert (row["status"], row["post_id"], row["confirmation_id"], row["caption"]) == ("published", f"{PAGE}_1", confirmation,
                                                                                       "Casque JBL\n\tà 899 000 Ar 🎧")
    assert listed(client, creation) == [body]
    with client.app.state.engine.connect() as conn:
        assert conn.execute(text("SELECT value FROM meta WHERE key='facebook_mode'")).scalar() == "meta"


@pytest.mark.parametrize("caption", ["", "   \n\t "])
def test_an_empty_or_blank_caption_is_published_without_one(client, photos, caption):
    creation, confirmation, _ = poster(client)
    connected(client)
    assert publish(client, creation, confirmation, caption=caption).json()["status"] == "published"
    assert "caption" not in fields(photos.requests[0]) and rows(client)[0]["caption"] == ""


def test_each_refusal_of_the_admission_writes_and_sends_nothing(client, photos, tmp_path):
    engine = client.app.state.engine
    creation, confirmation, _ = poster(client)
    _, others, _ = poster(client)
    connected(client)
    assert publish(client, creation, confirmation).status_code == 201  # one publication already: `seen` is its id
    first = rows(client)[0]["id"]
    photos.requests.clear()
    before = written(client)

    def nothing(answer, code, status=409):
        refused(answer, code, status)
        assert written(client) == before and photos.requests == []

    nothing(publish(client, creation, confirmation, seen=None), "facebook_stale")  # the sheet did not see the first
    nothing(publish(client, creation, confirmation, seen=str(uuid4()), page=PAGE), "facebook_stale")
    nothing(publish(client, creation, confirmation, seen=first, page="333"), "facebook_stale")  # another Page than the shop's
    nothing(publish(client, creation, others, seen=first), "facebook_stale")  # another poster's confirmation
    nothing(publish(client, creation, str(uuid4()), seen=first), "not_found", 404)  # no such confirmation
    for caption in ("é" * 2001, "a\x00b", "a\rb", "a\x7fb", "a\x85b", "🎧" * 2001):
        nothing(publish(client, creation, confirmation, caption=caption, seen=first), "caption_invalid", 422)
    assert publish(client, creation, confirmation, caption="🎧" * 2000, seen=str(uuid4())).json()["error"]["code"] == "facebook_stale"
    # The file: missing or damaged, then over Meta's 10 MB. Read before the transaction.
    path = assets.path(tmp_path, _sha_of(client, confirmation), "png")
    kept = path.read_bytes()
    path.write_bytes(b"damaged")
    nothing(publish(client, creation, confirmation, seen=first), "export_missing", 503)
    path.unlink()
    nothing(publish(client, creation, confirmation, seen=first), "export_missing", 503)
    path.write_bytes(kept)
    big, large, _ = poster(client, b"\x89PNG" + bytes(10_000_000))
    nothing(publish(client, big, large), "facebook_too_large", 422)
    # The conditions, the Page, the data folder's mode.
    unaccepted(engine)
    nothing(publish(client, creation, confirmation, seen=first), "terms_required", 403)
    credited(engine)
    run(client, "UPDATE facebook_pages SET state='reconnect'")
    before = written(client)
    nothing(publish(client, creation, confirmation, seen=first), "facebook_reconnect")
    run(client, "DELETE FROM facebook_pages")
    before = written(client)
    nothing(publish(client, creation, confirmation, seen=first), "facebook_not_connected")
    connected(client)
    run(client, "UPDATE meta SET value='stub' WHERE key='facebook_mode'")
    before = written(client)
    nothing(publish(client, creation, confirmation, seen=first), "provider_mode_mismatch")
    run(client, "UPDATE meta SET value='meta' WHERE key='facebook_mode'")
    # Another shop's poster, named with that shop's own confirmation: as a poster that exists nowhere.
    shop_b, password = second_shop(engine)
    theirs = TestClient(client.app, base_url=ORIGIN, headers=HEADERS)
    theirs.event_hooks["response"].extend(client.event_hooks["response"])
    assert theirs.post("/api/session", json=credentials(password, "boutique-deux")).status_code == 200
    their_poster, their_confirmation, _ = poster(theirs)
    connected(client, shop=shop_b)
    before = written(client)
    nothing(publish(theirs, creation, their_confirmation), "not_found", 404)
    nothing(publish(theirs, str(uuid4()), their_confirmation), "not_found", 404)
    nothing(publish(theirs, their_poster, confirmation), "not_found", 404)  # this shop's file, named by the other
    assert publish(client, creation, confirmation, seen=first).status_code == 201  # all of it was refused, nothing else


def _sha_of(client, confirmation):
    with client.app.state.engine.connect() as conn:
        return conn.execute(text("SELECT png_sha256 FROM confirmations WHERE id=:id"), {"id": confirmation}).scalar()


def test_a_session_that_ended_before_the_lock_was_taken_publishes_nothing(client, photos):
    """The boundary saw the session before the admission took the write lock: a sign-out in between wins."""
    creation, confirmation, _ = poster(client)
    connected(client)
    token = client.cookies[auth.COOKIE]
    run(client, "DELETE FROM sessions WHERE token_hash=:hash", hash=auth.token_hash(token))
    request = PublishRequest(confirmation_id=confirmation, page_id=PAGE, caption="", seen=None)
    with pytest.raises(Refused) as refusal:
        facebook_publish._admit(client.app.state.engine, facebook.StubGraph(), 1, token, str(uuid4()), creation, request,
                                _sha_of(client, confirmation))
    assert (refusal.value.code, refusal.value.status) == ("unauthenticated", 401) and rows(client) == []


def test_a_shop_suspended_before_the_lock_was_taken_publishes_nothing(client, photos):
    """Its session row is still there: a suspended shop's sessions are not live."""
    creation, confirmation, _ = poster(client)
    connected(client)
    run(client, "UPDATE shop_profile SET state='suspended' WHERE id=1")
    request = PublishRequest(confirmation_id=confirmation, page_id=PAGE, caption="", seen=None)
    with pytest.raises(Refused) as refusal:
        facebook_publish._admit(client.app.state.engine, facebook.StubGraph(), 1, client.cookies[auth.COOKIE], str(uuid4()),
                                creation, request, _sha_of(client, confirmation))
    assert (refusal.value.code, refusal.value.status) == ("unauthenticated", 401) and rows(client) == []
    refused(publish(client, creation, confirmation), "unauthenticated", 401)  # and the boundary, through the route
    assert rows(client) == [] and photos.requests == []


def test_the_clock_stepping_back_does_not_hide_a_publication_from_the_second_sheet(client, photos):
    """Two sheets saw publication A. The first publishes B, whose time is before A's: the second, which saw A, is still
    refused, and the list still gives B first."""
    creation, confirmation, _ = poster(client)
    connected(client)
    a = publish(client, creation, confirmation).json()["id"]
    b = publish(client, creation, confirmation, seen=a).json()["id"]
    run(client, "UPDATE facebook_publications SET sent_at='2020-01-01T00:00:00.000000+00:00' WHERE id=:id", id=b)
    refused(publish(client, creation, confirmation, seen=a), "facebook_stale")
    assert [item["id"] for item in listed(client, creation)] == [b, a] and len(photos.requests) == 2


def test_two_sheets_one_after_the_other_the_second_must_have_seen_the_first(client, photos):
    creation, confirmation, _ = poster(client)
    connected(client)
    first = publish(client, creation, confirmation, seen=None)  # both sheets opened on no publication
    assert first.json()["status"] == "published"
    refused(publish(client, creation, confirmation, seen=None), "facebook_stale")
    again = publish(client, creation, confirmation, seen=first.json()["id"])  # read again: published knowingly
    assert again.status_code == 201 and len(photos.requests) == 2
    assert [item["id"] for item in listed(client, creation)] == [again.json()["id"], first.json()["id"]]  # newest first
    # Other posters are free, and `seen` counts on this Page only.
    other, other_confirmation, _ = poster(client)
    assert publish(client, other, other_confirmation, seen=None).status_code == 201
    connected(client, page="333", name="Boutique Deux", token="page-token-of-the-page-333", at=utc_now())
    assert publish(client, creation, confirmation, page="333", seen=None).status_code == 201


def test_a_page_or_a_confirmation_changed_after_the_sheet_is_stale(client, photos):
    creation, confirmation, _ = poster(client)
    connected(client)
    connected(client, page="333", name="Boutique Deux", token="page-token-of-the-page-333", at=utc_now())  # since the sheet
    refused(publish(client, creation, confirmation), "facebook_stale")
    connected(client)
    saved = client.get(f"/api/creations/{creation}").json()
    assert client.put(f"/api/creations/{creation}", json=saved["document"] | {"offer": saved["document"]["offer"] | {"price_ar": 1}},
                      headers={"Idempotency-Key": str(uuid4()), "If-Match": f'"{saved["revision"]}"'}).status_code == 200
    refused(publish(client, creation, confirmation), "facebook_stale")  # confirmed at an earlier revision
    newer, _ = confirm(client, creation, png("blue"))
    assert publish(client, creation, newer).status_code == 201 and rows(client)[0]["confirmation_id"] == newer
    assert len(photos.requests) == 1


OTHER = {"error": {"code": 9999, "message": " ".join(SENSITIVE)}}


@pytest.mark.parametrize("answer, status, code, message", [
    (httpx2.Response(500, json={"error": {"code": 190}}), "unknown", None, MESSAGES["publication_unknown"]),
    (httpx2.Response(503, content=b"down"), "unknown", None, MESSAGES["publication_unknown"]),
    (httpx2.ConnectError("cut"), "unknown", None, MESSAGES["publication_unknown"]),
    (httpx2.ReadTimeout("slow"), "unknown", None, MESSAGES["publication_unknown"]),
    (httpx2.Response(200, content=b"{not json"), "unknown", None, MESSAGES["publication_unknown"]),
    (httpx2.Response(200, json={"id": "9"}), "unknown", None, MESSAGES["publication_unknown"]),  # the unpublished photo
    (httpx2.Response(200, json={"post_id": "222_9"}), "unknown", None, MESSAGES["publication_unknown"]),  # not this Page's
    (httpx2.Response(400, json={"error": {"code": 190, "message": " ".join(SENSITIVE)}}), "failed", "190", "Reconnectez votre Page."),
    *((httpx2.Response(400, json={"error": {"code": limit}}), "failed", str(limit),
       "Facebook limite les publications pour le moment. Réessayez plus tard.") for limit in (4, 17, 32, 613, 80001, 368)),
    *((httpx2.Response(403, json={"error": {"code": refusal}}), "failed", str(refusal),
       f"Facebook a refusé la publication (code {refusal}).") for refusal in (10, 200, 250, 299, 100, 324, 506)),
    (httpx2.Response(400, json=OTHER), "unknown", None, MESSAGES["publication_unknown"]),
])
def test_each_answer_of_facebook_is_settled_and_said_as_the_table_says(client, photos, answer, status, code, message):
    creation, confirmation, _ = poster(client)
    connected(client)
    photos.answer = answer
    body = publish(client, creation, confirmation).json()
    assert (body["status"], body["error_code"], body["message_fr"], body["link"]) == (status, code, message, None)
    assert page_state(client) == ("reconnect" if code == "190" else "connected")
    assert listed(client, creation)[0] == body and len(photos.requests) == 1
    assert MESSAGES["publication_unknown"] == "Je ne sais pas si l’affiche est publiée. Ouvrez votre Page et dites-le-moi."


def test_a_190_leaves_alone_a_page_connected_again_during_the_call(client, photos):
    creation, confirmation, _ = poster(client)
    connected(client)
    photos.answer = httpx2.Response(400, json={"error": {"code": 190}})
    photos.during = lambda request: connected(client, token=OTHER_TOKEN, at=utc_now())  # the owner reconnected meanwhile
    assert publish(client, creation, confirmation).json()["message_fr"] == "Reconnectez votre Page."
    assert page_state(client) == "connected"
    photos.during = None
    assert publish(client, creation, confirmation, seen=rows(client)[0]["id"]).status_code == 201
    assert fields(photos.requests[-1])["access_token"] == OTHER_TOKEN and page_state(client) == "reconnect"


def test_the_same_key_sends_once_replays_its_answer_and_is_refused_for_another_poster_or_body(client, photos):
    creation, confirmation, _ = poster(client)
    other, other_confirmation, _ = poster(client)
    connected(client)
    key = str(uuid4())
    first = publish(client, creation, confirmation, key=key)
    assert first.status_code == 201 and publish(client, creation, confirmation, key=key).json() == first.json()
    assert len(photos.requests) == 1 and len(rows(client)) == 1
    refused(publish(client, other, other_confirmation, key=key), "idempotency_reused")  # another poster
    refused(publish(client, creation, confirmation, key=key, caption="Autre texte"), "idempotency_reused")  # another body
    # The row as it is now: after the owner's word, the replay says it.
    run(client, "UPDATE facebook_publications SET status='unknown',post_id=NULL,link=NULL")
    assert outcome(client, creation, first.json()["id"], True).status_code == 200
    assert publish(client, creation, confirmation, key=key).json()["message_fr"] == "Présence confirmée par vous"
    assert len(photos.requests) == 1


def test_a_key_whose_row_is_sending_is_running_and_a_second_publication_is_pending(client, photos):
    creation, confirmation, _ = poster(client)
    connected(client)
    key = str(uuid4())
    first = publish(client, creation, confirmation, key=key).json()
    for status in ("sending", "unknown"):
        run(client, "UPDATE facebook_publications SET status=:status", status=status)
        refused(publish(client, creation, confirmation, seen=first["id"]), "facebook_pending")  # another key
    run(client, "UPDATE facebook_publications SET status='sending'")
    refused(publish(client, creation, confirmation, key=key), "facebook_running")  # the same key
    assert len(photos.requests) == 1
    other, other_confirmation, _ = poster(client)
    assert publish(client, other, other_confirmation).status_code == 201  # another poster is free


def test_while_facebook_takes_its_time_the_row_is_sending_and_no_lock_is_held(client, photos):
    """During the call another connection writes at once (busy_timeout would make it wait 5 s, then fail), and the
    poster's publications read the row 'sending'."""
    creation, confirmation, _ = poster(client)
    connected(client)
    seen = []

    def during(request):
        with write_tx(client.app.state.engine) as conn:
            conn.execute(text("INSERT OR REPLACE INTO meta VALUES ('probe','x')"))
            seen.append(conn.execute(text("SELECT status FROM facebook_publications")).scalar())

    photos.during = during
    assert publish(client, creation, confirmation).json()["status"] == "published" and seen == ["sending"]


def test_the_send_and_its_settlement_run_to_their_end_when_the_client_goes(client):
    """The request cancelled while Facebook takes its time (the browser went): the send goes on and is settled."""
    creation, confirmation, _ = poster(client)
    connected(client)
    engine, data = client.app.state.engine, SimpleNamespace(data_dir=Path(client.app.state.engine.url.database).parent)
    request = PublishRequest(confirmation_id=confirmation, page_id=PAGE, caption="", seen=None)

    async def gone():
        arrived, release = asyncio.Event(), asyncio.Event()

        async def slow(_request):
            arrived.set()
            await release.wait()
            return httpx2.Response(200, json={"post_id": f"{PAGE}_7"})

        graph = facebook.MetaGraph(APP, SecretStr(SECRET), transport=httpx2.MockTransport(slow))
        route = asyncio.ensure_future(facebook_publish.publish(engine, data, graph, 1, client.cookies[auth.COOKIE],
                                                               str(uuid4()), creation, request, MESSAGES))
        await arrived.wait()
        route.cancel()
        with pytest.raises(asyncio.CancelledError):
            await route
        assert rows(client)[0]["status"] == "sending"
        release.set()
        await facebook_publish.drain()  # what the shutdown awaits before giving up the data folder
        assert not facebook_publish._RUNNING

    asyncio.run(gone())
    [row] = rows(client)
    assert (row["status"], row["post_id"]) == ("published", f"{PAGE}_7")


def test_a_handler_held_back_over_thirty_seconds_does_not_send(client, photos, monkeypatch):
    creation, confirmation, _ = poster(client)
    connected(client)
    real = facebook_publish._admit

    def held(*args):
        publication, page, admitted_at, caption = real(*args)
        return publication, page, admitted_at - 31, caption  # the monotonic clock: a wall clock stepping back changes nothing

    monkeypatch.setattr(facebook_publish, "_admit", held)
    body = publish(client, creation, confirmation).json()
    assert (body["status"], body["error_code"], body["message_fr"]) == ("failed", "not_sent", "La publication n’est pas partie. Réessayez.")
    assert photos.requests == []
    assert publish(client, creation, confirmation, seen=body["id"]).json()["status"] == "failed"  # a failed one frees the place


def test_the_settling_write_that_fails_is_tried_again_without_a_second_send(client, photos, monkeypatch):
    creation, confirmation, _ = poster(client)
    connected(client)
    real, failures = facebook_publish._settled, []

    def flaky(*args):
        if len(failures) < facebook_publish.SETTLE_RETRIES:
            failures.append(1)
            raise OperationalError("UPDATE", {}, Exception("database is locked"))
        return real(*args)

    monkeypatch.setattr(facebook_publish, "SETTLE_PAUSE_S", 0)
    monkeypatch.setattr(facebook_publish, "_settled", flaky)
    assert publish(client, creation, confirmation).json()["status"] == "published"
    assert len(failures) == 3 and len(photos.requests) == 1
    # Failing every time: the answer is a storage refusal, the row stays 'sending', no outcome is offered for it.
    monkeypatch.setattr(facebook_publish, "_settled", lambda *args: (_ for _ in ()).throw(OSError("disk")))
    refused(publish(client, creation, confirmation, seen=rows(client)[0]["id"]), "storage_unavailable", 503)
    assert len(photos.requests) == 2 and rows(client)[1]["status"] == "sending"


def test_a_sending_row_offers_no_outcome_whatever_its_age_and_is_unknown_only_after_a_start(env, tmp_path, password_hash,
                                                                                              photos, caplog):
    settings = settings_for(env, tmp_path, password_hash, "meta")
    with TestClient(create_app(settings, prepare=credited), base_url=ORIGIN, headers=HEADERS) as client:
        login(client)
        creation, confirmation, _ = poster(client)
        connected(client)
        first = publish(client, creation, confirmation).json()
        run(client, "UPDATE facebook_publications SET status='sending',sent_at='2020-01-01T00:00:00.000000+00:00'")
        refused(outcome(client, creation, first["id"], False), "facebook_running")
        refused(publish(client, creation, confirmation, seen=first["id"]), "facebook_pending")
        assert listed(client, creation)[0]["message_fr"] == "Publication en cours…" and rows(client)[0]["status"] == "sending"
    with TestClient(create_app(settings), base_url=ORIGIN, headers=HEADERS) as again:  # the server starts again
        login(again)
        [item] = listed(again, creation)
        assert (item["status"], item["message_fr"]) == ("unknown", MESSAGES["publication_unknown"])
        assert outcome(again, creation, first["id"], False).status_code == 200


def test_the_owners_two_answers_close_an_unknown_publication_and_replay(client, photos):
    creation, confirmation, _ = poster(client)
    connected(client)
    photos.answer = httpx2.Response(502)
    lost = publish(client, creation, confirmation).json()
    assert lost["status"] == "unknown"
    refused(publish(client, creation, confirmation, seen=lost["id"]), "facebook_pending")  # until the owner says
    key = str(uuid4())
    there = outcome(client, creation, lost["id"], True, key)
    assert there.status_code == 200 and there.json() | {"settled_at": None} == lost | {
        "status": "published", "said_by_owner": True, "link": f"https://www.facebook.com/{PAGE}", "settled_at": None,
        "message_fr": "Présence confirmée par vous"}
    assert outcome(client, creation, lost["id"], True, key).json() == there.json()  # the stored answer, replayed
    refused(outcome(client, creation, lost["id"], False, key), "idempotency_reused")
    refused(outcome(client, creation, lost["id"], False), "facebook_settled")  # a new key: the row has its result
    assert len(photos.requests) == 1  # the app never looks on the Page, never sends again by itself
    # « Elle n’y est pas »: failed, and a new publication is admitted (the owner's word, after the warning).
    lost = publish(client, creation, confirmation, seen=lost["id"]).json()
    absent = outcome(client, creation, lost["id"], False).json()
    assert (absent["status"], absent["error_code"], absent["said_by_owner"], absent["message_fr"]) == (
        "failed", "not_published", False, "Vous avez dit qu’elle n’est pas sur votre Page.")
    photos.answer = None
    assert publish(client, creation, confirmation, seen=lost["id"]).json()["status"] == "published"
    refused(outcome(client, creation, str(uuid4()), True), "not_found", 404)
    refused(outcome(client, str(uuid4()), lost["id"], True), "not_found", 404)  # another poster's address


def test_off_answers_not_found_on_the_three_routes(env, tmp_path, password_hash):
    with TestClient(create_app(settings_for(env, tmp_path, password_hash, None), prepare=credited), base_url=ORIGIN,
                    headers=HEADERS) as client:
        login(client)
        creation, confirmation, _ = poster(client)
        refused(client.get(f"/api/creations/{creation}/publications"), "not_found", 404)
        refused(publish(client, creation, confirmation), "not_found", 404)
        refused(outcome(client, creation, str(uuid4()), True), "not_found", 404)
        refused(client.post(f"/api/creations/{creation}/publications", json={}), "not_found", 404)  # before any body is read


def test_the_stand_in_walks_publish_unknown_and_refused_through_the_routes(env, tmp_path, password_hash):
    with TestClient(create_app(settings_for(env, tmp_path, password_hash, "stub"), prepare=credited), base_url=ORIGIN,
                    headers=HEADERS) as client:
        login(client)
        creation, confirmation, _ = poster(client)
        page = facebook.StubGraph.PAGES[0]
        connected(client, page=page.id, name=page.name, token=page.token)
        published = publish(client, creation, confirmation, page=page.id).json()
        assert published["status"] == "published" and published["link"].startswith(f"https://www.facebook.com/{page.id}_")
        unknown = publish(client, creation, confirmation, "Promo [stub:unknown]", published["id"], page=page.id).json()
        assert unknown["status"] == "unknown"
        outcome(client, creation, unknown["id"], False)
        refusal = publish(client, creation, confirmation, "[stub:refused]", unknown["id"], page=page.id).json()
        assert refusal["message_fr"] == "Facebook a refusé la publication (code 506)."
        assert publish(client, creation, confirmation, "[stub:reconnect]", refusal["id"], page=page.id).json()["message_fr"] == "Reconnectez votre Page."
        assert page_state(client) == "reconnect"
        assert json.dumps(listed(client, creation)).count(page.token) == 0
