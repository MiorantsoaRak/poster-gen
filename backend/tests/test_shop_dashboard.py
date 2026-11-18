"""The shop's dashboard summary, GET /api/shop-dashboard (D-SHOP-DASH-001, 002, 004), through the real route. Jobs are
written straight into poster_jobs with the times each case needs; versions to review come from the stub workers."""
from uuid import uuid4

import pytest
from sqlalchemy import event, text

from affiche import api as affiche_api
from affiche.db import write_tx
from affiche.posters import credits, jobs, visuals
from test_api import client, create_draft, login, password_hash, post, settings  # noqa: F401
from test_config import env  # noqa: F401
from test_two_shops import PLAN, send, sign_in_second_shop, wait

NOW = "2026-11-18T12:00:00.000000+00:00"
SINCE = "2026-10-19T12:00:00.000000+00:00"  # 30 × 24 hours before NOW: the window's first instant
BEFORE = "2026-10-19T11:59:59.999999+00:00"  # the last instant outside it
LAST = "2026-11-18T11:59:59.999999+00:00"  # the window's last instant; NOW itself is outside
INSIDE = "2026-11-10T08:00:00.000000+00:00"
EMPTY = {"total": 0, "first_creation_id": None, "first_creation_title": None}


def attention(total, creation):
    return {"total": total, "first_creation_id": creation["id"], "first_creation_title": creation["document"]["offer"]["title"]}


def at(hour, minute=0):
    return f"2026-11-18T{hour:02d}:{minute:02d}:00.000000+00:00"


def usage(posters=0, images=0, spent=0):
    return {"posters_created": posters, "images_generated": images, "credits_spent": spent}


@pytest.fixture
def at_now(monkeypatch):
    monkeypatch.setattr(affiche_api, "utc_now", lambda: NOW)


def read(shop):
    answer = shop.get("/api/shop-dashboard")
    assert answer.status_code == 200 and answer.headers["cache-control"] == "no-store", answer.text
    return answer.json()


def poster(shop, created_at):
    """A poster made through the routes by the shop signed in on `shop`, then dated."""
    creation = create_draft(shop)
    with write_tx(shop.app.state.engine) as conn:
        conn.execute(text("UPDATE creations SET created_at=:at WHERE id=:id"), {"at": created_at, "id": creation["id"]})
    return creation


def job(engine, creation, status, admitted, *, kind="scene", finished=None, takes=None, shop=1, id=None):
    """A job as the worker leaves it: admitted at `admitted`, ended at `finished` (default: then). It takes a credit as
    jobs.enqueue decides, unless `takes` says otherwise."""
    id, takes = id or str(uuid4()), int(kind in jobs.IMAGE_KINDS) if takes is None else takes
    with write_tx(engine) as conn:
        conn.execute(text("INSERT INTO poster_jobs (id,shop_id,creation_id,origin_revision,input_id,kind,input_json,"
                          "input_hash,status,created_at,finished_at,takes_credit) VALUES (:id,:shop,:creation,1,:input,"
                          ":kind,'{}','h',:status,:admitted,:finished,:takes)"),
                     {"id": id, "shop": shop, "creation": creation["id"], "input": creation["document"]["input_id"],
                      "kind": kind, "status": status, "admitted": admitted, "finished": finished or admitted, "takes": takes})
    return id


def abandon(shop, creation):
    path = f"/api/creations/{creation['id']}"
    answer = send(shop, "POST", f"{path}/abandon", None, shop.get(path).json()["revision"])
    assert answer.status_code == 200, answer.text


def test_signed_out_stale_tab_and_an_empty_shop(client, at_now):
    """A protected read of the session's shop, never cached (AccessBoundary); an empty shop reads zeros and nulls, which
    only a successful read gives (D-SHOP-DASH-004: a failed one is an error, never a zero)."""
    answer = client.get("/api/shop-dashboard")
    assert (answer.status_code, answer.json()["error"]["code"]) == (401, "unauthenticated")
    login(client)
    assert read(client) == {"as_of": NOW, "review": EMPTY, "failed": EMPTY, "usage": usage()}
    stale = client.get("/api/shop-dashboard", headers={"X-Affiche-Shop": "2"})
    assert (stale.status_code, stale.json()["error"]["code"]) == (409, "shop_changed")


def test_a_failure_counts_while_it_is_the_posters_latest_image_generation(client, at_now):
    """D-SHOP-DASH-001: per active poster, its latest image generation by admission then id; failed or interrupted is a
    failure, a later one (cancelled included) supersedes it, a render or a plan is no image generation. The group links
    the newest poster by created_at then id, however old, and counts each poster once."""
    login(client)
    engine = client.app.state.engine
    old = poster(client, "2026-11-01T09:00:00.000000+00:00")
    job(engine, old, "failed", at(8))
    job(engine, old, "failed", at(8, 1))  # twice: one poster
    for _ in range(5):
        poster(client, at(9))
    assert old["id"] not in {item["id"] for item in client.get("/api/creations?limit=5").json()["items"]}
    assert read(client)["failed"] == attention(1, old)  # older than the five recent posters

    def failing(*history):
        """A poster at 10:00 whose image jobs ended so, one minute apart: (status, kind) pairs."""
        creation = poster(client, at(10))
        for minute, (status, kind) in enumerate(history):
            job(engine, creation, status, at(10, minute), kind=kind)
        return creation

    failing(("interrupted", "scene"))
    failing(("succeeded", "scene"), ("failed", "text_texture"))  # a text's material is an image
    failing(("failed", "scene"), ("succeeded", "render"), ("failed", "plan"))  # neither supersedes the scene
    failing(("failed", "scene"), ("succeeded", "refine"))  # superseded by a later success
    failing(("failed", "scene"), ("cancelled", "scene"))  # and by a later cancellation
    failing(("succeeded", "scene"), ("failed", "render"))  # a failed render is no failed generation
    abandon(client, failing(("failed", "scene")))  # removed from the list
    # Two jobs admitted at one instant: the greater id is the later.
    same = [poster(client, at(10)) for _ in range(2)]
    for creation, statuses in zip(same, (("failed", "succeeded"), ("succeeded", "failed"))):
        for status, last in zip(statuses, "12"):
            job(engine, creation, status, at(10), id=f"{creation['id'][:-1]}{last}")
    # Two posters created at one instant, the newest of all: the greater id is linked.
    tied = [poster(client, at(11)) for _ in range(2)]
    for index, creation in enumerate(tied):
        creation["document"]["offer"]["title"] = f"Offre {index}"
        saved = send(client, "PUT", f"/api/creations/{creation['id']}", creation["document"], creation["revision"])
        assert saved.status_code == 200, saved.text
        job(engine, creation, "failed", at(11))
    # old, interrupted, material, rendered, same[1] and both tied: not the five newer clean ones, nor the others
    newest, other = sorted(tied, key=lambda creation: creation["id"], reverse=True)
    summary = read(client)
    assert (summary["review"], summary["failed"]) == (EMPTY, attention(7, newest))
    # The linked one fixed by a later image: the other one is linked, the rest still counted.
    job(engine, newest, "succeeded", at(11, 30))
    assert read(client)["failed"] == attention(6, other)


@pytest.mark.parametrize("title", [None, "  \t "])
def test_legacy_blank_title_keeps_the_link(client, title):
    login(client)
    engine = client.app.state.engine
    creation = poster(client, INSIDE)
    job(engine, creation, "failed", INSIDE)
    with write_tx(engine) as conn:
        conn.execute(text("UPDATE creation_versions SET document_json=json_set(document_json,'$.offer.title',:title)"
                          " WHERE creation_id=:id"), {"id": creation["id"], "title": title})
    assert read(client)["failed"] == {"total": 1, "first_creation_id": creation["id"], "first_creation_title": None}


def scene(client, creation):
    """A scene made for the poster by the stub workers, through the routes; its visual's id."""
    revision = client.get(f"/api/creations/{creation['id']}").json()["revision"]
    plan = send(client, "POST", f"/api/creations/{creation['id']}/plans", PLAN, revision)
    assert plan.status_code == 201, plan.text
    started = send(client, "POST", f"/api/creations/{creation['id']}/scenes",
                   {"plan_id": plan.json()["id"], "acknowledged_warnings": ["low_resolution"]}, revision)
    assert started.status_code == 202, started.text
    return wait(client, started.json()["status_url"])


def states(client):
    """The library's state of each active poster."""
    return {item["id"]: item["state"] for item in client.get("/api/creations").json()["items"]}


def test_review_counts_what_the_library_shows_to_review(client, at_now):
    """The library's predicate (D-SHOP-DASH-001): the scene a poster shows waits for review, or a later version waits
    outside the document; a removed poster is not counted."""
    login(client)
    client.app.state.poster_service.provider.delay = 0

    def to_review():
        return {id for id, state in states(client).items() if state == "to_review"}

    first, second = create_draft(client), create_draft(client)
    shown = scene(client, first)
    assert read(client)["review"] == attention(1, first) and to_review() == {first["id"]}
    decided = send(client, "POST", f"/api/visuals/{shown}/decision", {"action": "approve", "checks": {c: True for c in visuals.CHECKS}})
    assert decided.json()["status"] == "approved", decided.text
    assert read(client)["review"] == EMPTY and to_review() == set()
    waiting = scene(client, first)
    assert client.get(f"/api/creations/{first['id']}").json()["document"]["formats"]["feed"]["scene"]["visual_id"] == shown != waiting
    scene(client, second)
    assert read(client)["review"] == attention(2, second)
    assert to_review() == {first["id"], second["id"]}
    abandon(client, second)
    assert read(client)["review"] == attention(1, first) and to_review() == {first["id"]}


def test_a_copy_showing_a_pending_scene_needs_review_through_that_scene_alone(client, at_now):
    """The shown-scene half of the predicate on its own (code review r2): a copy made while the original's scene awaits
    review shows that scene and owns no job. Both posters are to review, in the dashboard and in the library; the
    original's decision on that one version settles both."""
    login(client)
    client.app.state.poster_service.provider.delay = 0
    original = create_draft(client)
    shown = scene(client, original)
    revision = client.get(f"/api/creations/{original['id']}").json()["revision"]
    copied = post(client, f"/api/creations/{original['id']}/copies", {"source_revision": revision, "reason": "new_campaign"})
    assert copied.status_code == 201, copied.text
    copy = copied.json()
    assert copy["document"]["formats"]["feed"]["scene"]["visual_id"] == shown and copy["parent_creation_id"] == original["id"]
    assert client.get(f"/api/creations/{copy['id']}/jobs").json()["items"] == []  # the job is the original's alone
    assert read(client)["review"] == attention(2, copy)  # the copy is the newer
    assert states(client) == {original["id"]: "to_review", copy["id"]: "to_review"}
    decided = send(client, "POST", f"/api/visuals/{shown}/decision", {"action": "approve", "checks": {c: True for c in visuals.CHECKS}})
    assert decided.json()["status"] == "approved", decided.text
    assert read(client)["review"] == EMPTY
    assert states(client) == {original["id"]: "approved", copy["id"]: "approved"}


def test_the_30_days_count_posters_by_creation_and_images_and_credits_by_completion(client, at_now, monkeypatch):
    """D-SHOP-DASH-002: [NOW - 30 × 24 h, NOW). Posters by created_at, copies and removed ones included, each once
    whatever its versions; images: succeeded image jobs by finished_at, a success from before credits included; credits:
    succeeded jobs that took one, by finished_at, gross of a repayment. A grant is no spend."""
    login(client)
    engine = client.app.state.engine
    kept = poster(client, SINCE)
    for created in (BEFORE, NOW, LAST):
        poster(client, created)
    copy = post(client, f"/api/creations/{kept['id']}/copies", {"source_revision": 1, "reason": "price_update"})
    assert copy.status_code == 201, copy.text
    with write_tx(engine) as conn:
        conn.execute(text("UPDATE creations SET created_at=:at WHERE id=:id"), {"at": INSIDE, "id": copy.json()["id"]})
    document = kept["document"]
    document["offer"]["price_ar"] += 1000
    saved = client.put(f"/api/creations/{kept['id']}", json=document, headers={"Idempotency-Key": str(uuid4()), "If-Match": '"1"'})
    assert saved.status_code == 200 and saved.json()["revision"] == 2, saved.text  # a second version: still one poster
    abandon(client, poster(client, INSIDE))
    assert read(client)["usage"] == usage(posters=4)  # SINCE, LAST, the copy, the removed one

    job(engine, kept, "succeeded", SINCE)  # the first instant: in
    job(engine, kept, "succeeded", BEFORE)  # out
    job(engine, kept, "succeeded", NOW)  # the end: out
    job(engine, kept, "succeeded", BEFORE, finished=INSIDE)  # admitted before the window, completed in it
    repaid = job(engine, kept, "succeeded", INSIDE, kind="refine")
    job(engine, kept, "succeeded", INSIDE, kind="background")
    job(engine, kept, "succeeded", INSIDE, kind="text_texture", takes=0)  # before credits began: an image, no credit
    for status in ("failed", "interrupted", "cancelled"):
        job(engine, kept, status, INSIDE)
    for kind in ("render", "plan"):
        job(engine, kept, "succeeded", INSIDE, kind=kind)
    with write_tx(engine) as conn:
        with monkeypatch.context() as clock:
            clock.setattr(credits, "utc_now", lambda: SINCE)  # BEFORE < grant < INSIDE
            credits.grant(conn, 1, 5, origin="offered", ref="between", actor="tests")
        credits.correct(conn, 1, 1, ref="repay", note="test", actor="tests", job_id=repaid)
    assert read(client)["usage"] == usage(posters=4, images=5, spent=4)


def test_each_shop_reads_its_own_posters_jobs_and_counts(client, at_now):
    """D-SHOP-DASH-004: shop predicates at every hop. A job of B's written on A's poster (no route makes one) is
    neither shop's failure."""
    b, shop_b = sign_in_second_shop(client)
    engine = client.app.state.engine
    failed_a, clean_a = poster(client, INSIDE), poster(client, INSIDE)
    failed_a["document"]["offer"]["title"] = "Offre privée A"
    saved = send(client, "PUT", f"/api/creations/{failed_a['id']}", failed_a["document"], failed_a["revision"])
    assert saved.status_code == 200, saved.text
    job(engine, failed_a, "failed", INSIDE)
    job(engine, clean_a, "succeeded", INSIDE)
    job(engine, clean_a, "failed", at(9), shop=shop_b)
    job(engine, poster(b, INSIDE), "succeeded", INSIDE, shop=shop_b)
    assert read(client) == {"as_of": NOW, "review": EMPTY, "failed": attention(1, failed_a),
                            "usage": usage(posters=2, images=1, spent=1)}
    answer = b.get("/api/shop-dashboard")
    assert answer.json() == {"as_of": NOW, "review": EMPTY, "failed": EMPTY, "usage": usage(posters=1, images=1, spent=1)}
    assert failed_a["id"] not in answer.text and clean_a["id"] not in answer.text and "Offre privée A" not in answer.text


def test_every_figure_is_read_from_one_snapshot(client, at_now):
    """D-SHOP-DASH-004: a scene that succeeds between the route's reads shows in none of its figures, then in all."""
    login(client)
    engine = client.app.state.engine
    creation = poster(client, at(9))
    job(engine, creation, "failed", at(9))
    written = []

    def between(conn, cursor, statement, *_):
        if "credits_spent" in statement and not written:  # the route's last read: the attention groups are read
            written.append(job(engine, creation, "succeeded", at(10)))

    event.listen(engine, "before_cursor_execute", between)
    try:
        first = read(client)
    finally:
        event.remove(engine, "before_cursor_execute", between)
    assert written and (first["failed"], first["usage"]) == (attention(1, creation), usage(posters=1))
    second = read(client)
    assert (second["failed"], second["usage"]) == (EMPTY, usage(posters=1, images=1, spent=1))


def test_shop_credit_history_uses_completion_dates_and_shop_only_fields(client, monkeypatch):
    route = "/api/shop-credit-history"
    assert client.get(route).status_code == 401
    other, shop_b = sign_in_second_shop(client)
    assert client.get(route, headers={"X-Affiche-Shop": str(shop_b)}).status_code == 409
    for params, code in (({"limit": 0}, "validation_error"), ({"limit": 51}, "validation_error"),
                         ({"before": "broken"}, "invalid_cursor")):
        invalid = client.get(route, params=params)
        assert (invalid.status_code, invalid.json()["error"]["code"]) == (422, code)

    a, b = create_draft(client), create_draft(other)
    document = b["document"]
    document["offer"]["title"] = "Titre privé B"
    saved = send(other, "PUT", f"/api/creations/{b['id']}", document, b["revision"])
    assert saved.status_code == 200, saved.text
    engine = client.app.state.engine
    spent = job(engine, a, "succeeded", BEFORE, finished=at(10))
    released = job(engine, a, "failed", at(8), finished=at(10))
    active = create_draft(client)
    pending = job(engine, active, "running", at(9), finished=NOW)
    free = job(engine, a, "succeeded", at(8), takes=0)
    foreign = job(engine, b, "succeeded", at(9), shop=shop_b)
    # A job whose creation belongs to B can contribute a credit entry to A, but no title or link.
    malformed = job(engine, b, "succeeded", at(8), shop=1)
    # A historical line pointing at B's job must never follow it, even when that job points back at A.
    foreign_link = job(engine, a, "succeeded", at(8), shop=shop_b)
    with write_tx(engine) as conn:
        seeded_a = set(conn.exec_driver_sql("SELECT id FROM credit_grants WHERE shop_id=1").scalars())
        seeded_b = set(conn.exec_driver_sql("SELECT id FROM credit_grants WHERE shop_id=?", (shop_b,)).scalars())
        malformed_repay = conn.execute(text(
            "INSERT INTO credit_grants(shop_id,kind,credits,ref,actor,note,job_id,created_at)"
            " VALUES (1,'correction',1,'broken association','ops','legacy',:job,:at) RETURNING id"),
            {"job": foreign_link, "at": at(8)}).scalar_one()
        monkeypatch.setattr(credits, "utc_now", lambda: at(9))
        grant = credits.grant(conn, 1, 3, origin="bought", ref="hidden reference", amount_ar=8000,
                              method="mvola", actor="private operator", note="internal note")
        grant_b = credits.grant(conn, shop_b, 4, origin="offered", ref="B opening", actor="ops")
        monkeypatch.setattr(credits, "utc_now", lambda: at(11))
        repayment = credits.correct(conn, 1, 1, ref="hidden repayment", job_id=spent, note="internal refund", actor="ops")
        fix = credits.correct(conn, 1, 0, ref="hidden reference", amount_ar=1, note="internal amount", actor="ops")
    abandon(client, a)

    answer = client.get(route)
    assert answer.status_code == 200 and answer.headers["cache-control"] == "no-store"
    result = answer.json()
    assert result.keys() == {"items", "next_cursor"} and result["next_cursor"] is None
    items = result["items"]
    by_id = {item["id"]: item for item in items}
    common = {"id", "type", "kind", "at", "creation_id", "title", "removed"}
    for item in items:
        assert set(item) == common | ({"origin", "credits"} if item["type"] == "line" else {"credit"})
    assert free not in by_id and foreign not in by_id and b["id"] not in answer.text and "Titre privé B" not in answer.text
    assert (by_id[grant]["origin"], by_id[grant]["credits"], by_id[grant]["at"]) == ("bought", 3, at(9))
    assert (by_id[fix]["kind"], by_id[fix]["credits"]) == ("correction", 0)
    assert (by_id[repayment]["kind"], by_id[repayment]["credits"], by_id[repayment]["at"]) == ("correction", 1, at(11))
    assert (by_id[spent]["at"], by_id[spent]["credit"]) == (at(10), "spent")
    assert (by_id[released]["at"], by_id[released]["credit"]) == (at(10), "given_back")
    assert (by_id[pending]["at"], by_id[pending]["credit"]) == (at(9), "pending")
    assert by_id[pending]["creation_id"] == active["id"] and by_id[pending]["removed"] is False
    for id in (spent, released, repayment):
        row = by_id[id]
        assert (row["creation_id"], row["title"], row["removed"]) == (a["id"], "JBL Flip", True)
    for id in (malformed, malformed_repay, grant, fix):
        assert all(by_id[id][key] is None for key in ("creation_id", "title", "removed"))
    assert items == sorted(items, key=lambda row: (row["at"], row["type"], row["id"]), reverse=True)

    def one_row_pages(device):
        rows, cursor = [], None
        while True:
            page = device.get(route, params={"limit": 1} | ({"before": cursor} if cursor else {})).json()
            assert len(page["items"]) == 1 and page["items"][0] not in rows
            rows.extend(page["items"])
            cursor = page["next_cursor"]
            if cursor is None:
                return rows

    rows_a = one_row_pages(client)
    assert rows_a == items
    assert {r["id"] for r in rows_a if r["type"] == "line"} == seeded_a | {malformed_repay, grant, repayment, fix}
    assert rows_a.index(by_id[repayment]) < rows_a.index(by_id[spent])
    rows_b = one_row_pages(other)
    assert {r["id"] for r in rows_b if r["type"] == "line"} == seeded_b | {grant_b}
    assert [row for row in rows_b if row["type"] == "job"] == [
        {"type": "job", "id": foreign, "at": at(9), "kind": "scene", "credit": "spent",
         "creation_id": b["id"], "title": "Titre privé B", "removed": False},
        {"type": "job", "id": foreign_link, "at": at(8), "kind": "scene", "credit": "spent",
         "creation_id": None, "title": None, "removed": None}]
