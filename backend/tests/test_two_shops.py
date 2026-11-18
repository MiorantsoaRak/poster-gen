"""Isolation as a tested property (D-MULTI-SHOP-004, R-MULTI-SHOP-002). Two shops in one database, made as the operator
makes them and signed in through the real route, the workers running on the stub providers. Shop B sends every route
of the schema at shop A's objects and gets exactly what it gets for objects that exist nowhere; a route that no
attempt covers and no exemption names fails the test. mutant_two_shops.py, beside this file, shows the test failing
when the shop filter is removed from store._owned."""
import json
import re
import secrets
import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from starlette.routing import Mount

from affiche.api import create_app
from affiche.db import write_tx
from affiche.posters import credits, rendering, terms, visuals
from test_api import (HEADERS, ORIGIN, PASSWORD, client, create_draft, credentials, login, old_cancellation,  # noqa: F401
                      password_hash, post, second_shop, settings)
from test_config import env  # noqa: F401
from test_poster_drafts import key, photo

# Routes that hold no shop's objects. Every other route of the schema must be attempted below.
EXEMPT = {
    ("GET", "/api/session"), ("POST", "/api/session"),  # the session itself: sign-in by identifier is test_api's
    ("DELETE", "/api/session"),  # ends the caller's own session only; a stale tab's is refused below
    ("POST", "/api/session/password"),  # takes no id: always the session's own shop; another shop untouched in test_shops
    ("GET", "/api/capabilities"),  # the service's modes: nothing of any shop (walked for dollar figures below)
    ("GET", "/api/status"),  # the operator's: 404 to both shops below, its spoofing matrix in test_api
}
# A route that answers B with B's own data, checked by what it holds; it takes no id of A's.
OWN = {("GET", "/api/creations"), ("GET", "/api/looks"), ("GET", "/api/shop-profile"), ("GET", "/api/balance"),
       ("POST", "/api/assets"), ("GET", "/api/terms"), ("POST", "/api/terms")}
NO_BRAND = {"logo": False, "shop_name": False, "contact": False}
PLAN = {"mode": "fixed", "direction": "Terrasse tropicale", "format": "feed"}


@pytest.fixture
def planner_stub(env):
    env.setenv("PLANNER_PROVIDER", "stub")


def send(client, method, path, body=None, revision=None):
    headers = {"Idempotency-Key": key()} | ({"If-Match": f'"{revision}"'} if revision else {})
    return client.request(method, path, json=body, headers=headers)


def wait(client, job_url, seconds=90):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        job = client.get(job_url).json()
        if job["status"] in {"succeeded", "failed", "interrupted", "cancelled"}:
            assert job["status"] == "succeeded", job
            return job["result_ref"]
        time.sleep(.2)
    pytest.fail(f"job {job_url} did not finish")


def outcome(response):
    """Everything a caller learns from an answer but the request's own id: its status and its whole body."""
    try:
        body = response.json()
    except ValueError:  # not JSON (a PNG, say): never a refusal, so the assertion below fails with what came back
        return response.status_code, response.headers.get("content-type")
    return response.status_code, {k: v for k, v in body.items() if k != "request_id"} if isinstance(body, dict) else body


def application_routes(routes):
    """Every (method, path) the application answers, through the routers it includes. The schema's own route and the
    built frontend's mount (SERVE_FRONTEND: public files, no data, test_api) are the two the schema does not show."""
    for route in routes:
        if (included := getattr(route, "original_router", None)) is not None:  # this FastAPI keeps an included router whole
            yield from application_routes(included.routes)
        elif isinstance(route, Mount):
            assert (route.name, route.path) == ("frontend", ""), f"a mount the schema does not show: {route.path!r}"
        elif route.path != "/api/openapi.json":
            yield from ((method, route.path) for method in getattr(route, "methods", None) or {"WEBSOCKET"} if method != "HEAD")


def sign_in_second_shop(client):
    """Shop A on `client`, shop B on a second device: one client holds one session (signing B in there ends A's)."""
    login(client)
    shop_b, password_b = second_shop(client.app.state.engine)
    b = TestClient(client.app, base_url=ORIGIN, headers=HEADERS)
    assert b.post("/api/session", json=credentials(password_b, "boutique-deux")).json() == {"authenticated": True, "shop_id": shop_b}
    assert client.get("/api/session").json() == {"authenticated": True, "shop_id": 1}
    return b, shop_b


# Routes whose successful answer the dollar walk does not read, each for its reason.
NOT_WALKED = {
    ("GET", "/api/assets/{sha}"), ("GET", "/api/thumbnails/{sha}"),  # an image's bytes: no JSON, no key
    ("GET", "/api/renders/{id}/preview"), ("GET", "/api/confirmations/{id}/download"),  # a PNG's bytes: no key
    ("GET", "/api/status"),  # the operator's: 404 to every shop (asserted in the test)
}


def route_of(schema, request):
    """The (method, path template) of the schema that a request was answered by."""
    found = [(method, template) for method, template in schema
             if method == request.method and re.fullmatch(re.sub(r"\{\w+\}", "[^/]+", template), request.url.path)]
    assert len(found) == 1, (request.method, request.url.path, found)
    return found[0]


def json_keys(value):
    """Every key of a JSON answer, at every depth."""
    if isinstance(value, dict):
        for name, item in value.items():
            yield name
            yield from json_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from json_keys(item)


def test_shop_b_gets_from_every_route_on_shop_as_objects_what_it_gets_for_nothing(planner_stub, client, settings,
                                                                                    monkeypatch):
    a, engine = client, client.app.state.engine
    answers = []  # every answer either shop receives, for the walk of dollar figures at the end
    a.event_hooks["response"].append(answers.append)
    b, shop_b = sign_in_second_shop(a)
    b.event_hooks["response"].append(answers.append)

    # Shop A: one object of every kind, through the routes (test_tenancy_audit.py:101-150).
    logo_a = a.post("/api/assets", files={"file": ("l.png", photo(colour="red"), "image/png")}, data={"role": "logo"}).json()["asset"]
    assert send(a, "PUT", "/api/shop-profile", {"name": "Original Phone", "contact": None, "logo_asset": logo_a}, 1).status_code == 200
    creation = create_draft(a)
    cid, input_a = creation["id"], creation["document"]["input_id"]
    original_a = a.get(f"/api/product-inputs/{input_a}").json()["photo_assets"][0]
    plan = send(a, "POST", f"/api/creations/{cid}/plans", PLAN, 1)
    assert plan.status_code == 201, plan.text
    plan_a = plan.json()
    style_a = a.post("/api/assets", files={"file": ("s.png", photo(colour="gold"), "image/png")}, data={"role": "style"}).json()["asset"]
    scene = send(a, "POST", f"/api/creations/{cid}/scenes", {"plan_id": plan_a["id"], "acknowledged_warnings": ["low_resolution"],
                                                            "style_reference_asset": style_a}, 1)
    assert scene.status_code == 202, scene.text
    scene_job_a = scene.json()["job_id"]
    visual_a = wait(a, scene.json()["status_url"])
    assert send(a, "POST", f"/api/visuals/{visual_a}/decision",
                {"action": "approve", "checks": {c: True for c in visuals.CHECKS}}).json()["status"] == "approved"
    scene_sha_a = a.get(f"/api/visuals/{visual_a}").json()["image_url"].rsplit("/", 1)[1]
    look = send(a, "POST", f"/api/creations/{cid}/looks", {"name": "Style A", "reference_asset": style_a}, 2)
    assert look.status_code == 202, look.text
    look_a = wait(a, look.json()["status_url"])
    doc_a = a.get(f"/api/creations/{cid}").json()["document"]
    title_a = next(layer["id"] for layer in doc_a["formats"]["feed"]["layers"] if layer["role"] == "title")
    proposal = send(a, "POST", f"/api/creations/{cid}/text-proposals", {"layer_id": title_a, "instruction_fr": "Titre en doré"}, 2)
    assert proposal.status_code == 202, proposal.text
    proposal_a = wait(a, proposal.json()["status_url"])
    assert send(a, "POST", f"/api/text-proposals/{proposal_a}/apply", {}, 2).status_code == 200
    effect = send(a, "POST", f"/api/creations/{cid}/text-effects", {"layer_id": title_a, "proposal_id": proposal_a}, 3)
    assert effect.status_code == 202, effect.text
    effect_a = wait(a, effect.json()["status_url"])
    texture_a = a.get(f"/api/text-effects/{effect_a}").json()["texture_asset"]
    render = send(a, "POST", f"/api/creations/{cid}/renders", {"format": "feed"}, 3)
    assert render.status_code == 202, render.text
    render_a = wait(a, render.json()["status_url"])
    render_row = a.get(f"/api/renders/{render_a}").json()
    confirm_body = {"render_id": render_a, "png_sha256": render_row["png_sha256"],
                    "checks": {c: True for c in ("framing", "content", "identity", "readability")},
                    "acknowledged_warning_ids": [w["id"] for w in render_row["warnings"]]}
    confirmed = send(a, "POST", f"/api/creations/{cid}/confirmations", confirm_body, 3)
    assert confirmed.status_code == 201, confirmed.text
    read_key, read_body = key(), {"text": "JBL Flip 7, 700 000 Ar", "draft": {"product_photos": 1, "inspiration": False}, "history": []}
    assert a.post("/api/reads", json=read_body, headers={"Idempotency-Key": read_key}).status_code == 201
    rev, doc_a = 3, a.get(f"/api/creations/{cid}").json()["document"]
    theirs = {"creation": cid, "input": input_a, "plan": plan_a["id"], "visual": visual_a, "job": scene_job_a,
              "look": look_a, "proposal": proposal_a, "effect": effect_a, "render": render_a,
              "confirmation": confirmed.json()["confirmation_id"], "original": original_a, "scene": scene_sha_a,
              "style": style_a, "logo": logo_a, "texture": texture_a, "png": render_row["png_sha256"]}
    # The same places, filled with ids of the same kinds that exist nowhere.
    nowhere = {name: secrets.token_hex(32) if len(value) == 64 else str(uuid4()) for name, value in theirs.items()}

    # Shop B: its own poster, plan and style, to point at A's objects from.
    up_b = b.post("/api/assets", files={"file": ("b.png", photo(colour="green"), "image/png")}, data={"role": "original"}).json()["asset"]
    style_b = b.post("/api/assets", files={"file": ("t.png", photo(colour="purple"), "image/png")}, data={"role": "style"}).json()["asset"]
    input_b = post(b, "/api/product-inputs", {"name": "Sony", "variant": "v", "photo_assets": [up_b]}).json()["id"]
    creation_b = post(b, "/api/creations", {"input_id": input_b, "offer": {"title": "Sony X", "price_ar": 1000},
                                            "brand_selection": NO_BRAND}).json()
    bid, doc_b = creation_b["id"], creation_b["document"]
    title_b = next(layer["id"] for layer in doc_b["formats"]["feed"]["layers"] if layer["role"] == "title")
    plan_b = send(b, "POST", f"/api/creations/{bid}/plans", PLAN, 1).json()["id"]

    def b_doc(change):
        document = json.loads(json.dumps(doc_b))
        change(document)
        return document

    def reading(template, name, query=""):
        return "GET", template, lambda x: (re.sub(r"\{(id|sha)\}", x[name], template).replace("{revision}", "1") + query, None, None)

    # (method, path template, the request built from an id map x: path, body, If-Match revision)
    attempts = [
        # A's objects, read by their address.
        *(reading(template, name) for template, name in (
            ("/api/creations/{id}", "creation"), ("/api/creations/{id}/versions", "creation"),
            ("/api/creations/{id}/versions/{revision}", "creation"), ("/api/creations/{id}/jobs", "creation"),
            ("/api/creations/{id}/visuals", "creation"), ("/api/jobs/{id}", "job"), ("/api/plans/{id}", "plan"),
            ("/api/visuals/{id}", "visual"), ("/api/looks/{id}", "look"), ("/api/text-proposals/{id}", "proposal"),
            ("/api/text-effects/{id}", "effect"), ("/api/product-inputs/{id}", "input"), ("/api/renders/{id}", "render"),
            ("/api/renders/{id}/preview", "render"), ("/api/confirmations/{id}/download", "confirmation"))),
        *(reading("/api/assets/{sha}", name, query) for name in ("original", "scene", "style", "logo", "texture", "png")
          for query in ("", "?prepared=true", "?prepared=true&display=true&v=1")),
        *(reading("/api/thumbnails/{sha}", name, "?v=1") for name in ("scene", "png", "original")),
        # A's objects, changed by their address, each with a body that passes validation.
        ("PUT", "/api/creations/{id}", lambda x: (f"/api/creations/{x['creation']}", doc_a, rev)),
        ("POST", "/api/creations/{id}/copies", lambda x: (f"/api/creations/{x['creation']}/copies",
                                                          {"source_revision": rev, "reason": "price_update"}, None)),
        ("POST", "/api/creations/{id}/abandon", lambda x: (f"/api/creations/{x['creation']}/abandon", None, rev)),
        ("POST", "/api/creations/{id}/restore", lambda x: (f"/api/creations/{x['creation']}/restore", None, rev)),
        ("POST", "/api/creations/{id}/plans", lambda x: (f"/api/creations/{x['creation']}/plans", PLAN, rev)),
        ("POST", "/api/plans/{id}/revisions", lambda x: (f"/api/plans/{x['plan']}/revisions", {
            k: plan_a["plan"][k] for k in ("scene", "product_region", "overlay_regions", "palette")}, rev)),
        ("POST", "/api/creations/{id}/scenes", lambda x: (f"/api/creations/{x['creation']}/scenes", {
            "plan_id": x["plan"], "acknowledged_warnings": ["low_resolution"]}, rev)),
        ("POST", "/api/creations/{id}/refinements", lambda x: (f"/api/creations/{x['creation']}/refinements", {
            "base_visual_id": x["visual"], "instruction_fr": "Plus de lumière"}, rev)),
        ("POST", "/api/creations/{id}/looks", lambda x: (f"/api/creations/{x['creation']}/looks",  # B's own style: the
                                                         {"name": "x", "reference_asset": style_b}, rev)),  # poster decides
        ("POST", "/api/creations/{id}/renders", lambda x: (f"/api/creations/{x['creation']}/renders", {"format": "feed"}, rev)),
        ("POST", "/api/creations/{id}/confirmations", lambda x: (f"/api/creations/{x['creation']}/confirmations",
                                                                 confirm_body | {"render_id": x["render"]}, rev)),
        ("POST", "/api/creations/{id}/text-proposals", lambda x: (f"/api/creations/{x['creation']}/text-proposals",
                                                                  {"layer_id": title_a, "instruction_fr": "Rouge"}, rev)),
        ("POST", "/api/creations/{id}/text-effects", lambda x: (f"/api/creations/{x['creation']}/text-effects",
                                                                {"layer_id": title_a, "proposal_id": x["proposal"]}, rev)),
        ("POST", "/api/visuals/{id}/decision", lambda x: (f"/api/visuals/{x['visual']}/decision", {"action": "reject", "note": "non"}, None)),
        ("PUT", "/api/looks/{id}", lambda x: (f"/api/looks/{x['look']}", {"name": "volé"}, None)),
        ("DELETE", "/api/looks/{id}", lambda x: (f"/api/looks/{x['look']}", None, None)),
        ("POST", "/api/jobs/{id}/cancel", lambda x: (f"/api/jobs/{x['job']}/cancel", None, None)),
        ("POST", "/api/text-proposals/{id}/apply", lambda x: (f"/api/text-proposals/{x['proposal']}/apply", {}, rev)),
        ("POST", "/api/text-proposals/{id}/reject", lambda x: (f"/api/text-proposals/{x['proposal']}/reject", None, None)),
        ("POST", "/api/text-effects/{id}/apply", lambda x: (f"/api/text-effects/{x['effect']}/apply", None, rev)),
        ("POST", "/api/text-effects/{id}/reject", lambda x: (f"/api/text-effects/{x['effect']}/reject", None, None)),
        # A's objects named in the body of B's own requests.
        ("POST", "/api/creations", lambda x: ("/api/creations", {"input_id": x["input"], "offer": {"title": "X", "price_ar": 1},
                                                                 "brand_selection": NO_BRAND}, None)),
        ("POST", "/api/product-inputs", lambda x: ("/api/product-inputs", {"name": "JBL", "variant": "v", "photo_assets": [x["original"]]}, None)),
        ("POST", "/api/product-inputs", lambda x: ("/api/product-inputs", {"name": "Sony", "variant": "v", "photo_assets": [up_b],
                                                                           "supersedes_id": x["input"]}, None)),
        ("PUT", "/api/shop-profile", lambda x: ("/api/shop-profile", {"name": "Boutique Deux", "contact": None, "logo_asset": x["logo"]}, 1)),
        ("POST", "/api/reads", lambda x: ("/api/reads", read_body | {"creation_id": x["creation"], "visual_id": x["visual"]}, None)),
        ("PUT", "/api/creations/{id}", lambda x: (f"/api/creations/{bid}", b_doc(lambda d: d["formats"]["feed"].update(
            scene=doc_a["formats"]["feed"]["scene"] | {"visual_id": x["visual"]})), 1)),
        ("PUT", "/api/creations/{id}", lambda x: (f"/api/creations/{bid}", b_doc(lambda d: next(
            layer for layer in d["formats"]["feed"]["layers"] if layer["id"] == title_b).update(texture_effect_id=x["effect"])), 1)),
        ("PUT", "/api/creations/{id}", lambda x: (f"/api/creations/{bid}", b_doc(lambda d: d["brand_snapshot"].update(logo_asset=x["logo"])), 1)),
        ("PUT", "/api/creations/{id}", lambda x: (f"/api/creations/{bid}", doc_b | {"input_id": x["input"]}, 1)),
        ("POST", "/api/creations/{id}/copies", lambda x: (f"/api/creations/{bid}/copies", {
            "source_revision": 1, "reason": "replace_input", "new_input_id": x["input"]}, None)),
        ("POST", "/api/creations/{id}/scenes", lambda x: (f"/api/creations/{bid}/scenes", {
            "plan_id": plan_b, "acknowledged_warnings": ["low_resolution"], "style_reference_asset": x["style"]}, 1)),
        ("POST", "/api/creations/{id}/scenes", lambda x: (f"/api/creations/{bid}/scenes", {
            "plan_id": plan_b, "acknowledged_warnings": ["low_resolution"], "headline": {"look_id": x["look"]}}, 1)),
        ("POST", "/api/creations/{id}/scenes", lambda x: (f"/api/creations/{bid}/scenes", {
            "plan_id": x["plan"], "acknowledged_warnings": ["low_resolution"]}, 1)),
        ("POST", "/api/creations/{id}/refinements", lambda x: (f"/api/creations/{bid}/refinements", {
            "base_visual_id": x["visual"], "instruction_fr": "Plus de lumière"}, 1)),
        ("POST", "/api/creations/{id}/text-effects", lambda x: (f"/api/creations/{bid}/text-effects",
                                                                {"layer_id": title_b, "proposal_id": x["proposal"]}, 1)),
        ("POST", "/api/creations/{id}/confirmations", lambda x: (f"/api/creations/{bid}/confirmations",
                                                                 confirm_body | {"render_id": x["render"]}, 1)),
        ("POST", "/api/creations/{id}/looks", lambda x: (f"/api/creations/{bid}/looks", {"name": "x", "reference_asset": x["style"]}, 1)),
        ("POST", "/api/creations/{id}/scenes", lambda x: (f"/api/creations/{bid}/scenes", {
            "plan_id": plan_b, "acknowledged_warnings": ["low_resolution"], "keep_adjustments_of": x["visual"]}, 1)),
        ("POST", "/api/reads", lambda x: ("/api/reads", read_body | {"creation_id": bid, "visual_id": x["visual"]}, None)),
        # A copy kept after a save conflict, its unsaved document naming A's visual, effect, logo or input.
        *(("POST", "/api/creations/{id}/copies", lambda x, change=change: (f"/api/creations/{bid}/copies", {
            "source_revision": 1, "reason": "save_conflict", "unsaved_document": change(x)}, None)) for change in (
            lambda x: b_doc(lambda d: d["formats"]["feed"].update(scene=doc_a["formats"]["feed"]["scene"] | {"visual_id": x["visual"]})),
            lambda x: b_doc(lambda d: next(layer for layer in d["formats"]["feed"]["layers"]
                                           if layer["id"] == title_b).update(texture_effect_id=x["effect"])),
            lambda x: b_doc(lambda d: d["brand_snapshot"].update(logo_asset=x["logo"])),
            lambda x: doc_b | {"input_id": x["input"]})),
    ]

    def refused_as_nothing(attempts):
        for method, template, build in attempts:
            path = build(theirs)[0]
            assert re.fullmatch(re.sub(r"\{\w+\}", "[^/?]+", template) + r"(\?.*)?", path), (template, path)
            mine, nothing = (outcome(send(b, method, *build(ids))) for ids in (theirs, nowhere))
            # Refused by an ownership check, not by the shape of the body, with the same whole answer as for nothing.
            assert (mine == nothing and mine[0] in (403, 404, 409, 422)
                    and mine[1]["error"]["code"] != "validation_error"), (method, path, mine, nothing)

    refused_as_nothing(attempts)
    assert b.get(f"/api/creations/{bid}").json()["revision"] == 1  # every attempt on B's own poster changed nothing

    # A chat read under the key A used is a fresh key for B (0013): a read of B's own, as with any new key.
    reused, fresh = (b.post("/api/reads", json=read_body, headers={"Idempotency-Key": k}) for k in (read_key, key()))
    assert reused.status_code == fresh.status_code == 201 and reused.json() == fresh.json()
    with engine.connect() as conn:
        assert sorted(conn.execute(text("SELECT shop_id FROM chat_reads WHERE key=:k"), {"k": read_key}).scalars()) == [1, shop_b]
    # The photos a read suggests for a product are the shop's own: A is offered its JBL photo, B is not.
    asking = {"text": "JBL, 700 000 Ar", "draft": {"product_photos": 0, "inspiration": False}, "history": []}
    assert [s["asset"] for s in post(a, "/api/reads", asking).json()["card"]["suggestions"]] == [original_a]
    assert original_a not in post(b, "/api/reads", asking).text

    # The worker carries the shop: B's scene lands in B's shop, and A gets nothing of it.
    scene_b = send(b, "POST", f"/api/creations/{bid}/scenes", {"plan_id": plan_b, "acknowledged_warnings": ["low_resolution"]}, 1)
    assert scene_b.status_code == 202, scene_b.text
    visual_b = wait(b, scene_b.json()["status_url"])
    with engine.connect() as conn:
        assert conn.execute(text("SELECT shop_id FROM poster_visuals WHERE id=:id"), {"id": visual_b}).scalar() == shop_b
    for path in (f"/api/visuals/{visual_b}", f"/api/creations/{bid}", scene_b.json()["status_url"]):
        assert a.get(path).json()["error"]["code"] == "not_found", path
    # Now that B's poster has a version of its own to adjust: a refinement of it with A's style.
    placed = b.get(f"/api/creations/{bid}").json()
    assert placed["document"]["formats"]["feed"]["scene"]["visual_id"] == visual_b
    after_scene = [("POST", "/api/creations/{id}/refinements", lambda x: (f"/api/creations/{bid}/refinements", {
        "base_visual_id": visual_b, "instruction_fr": "Plus de lumière", "style_reference_asset": x["style"]}, placed["revision"]))]
    refused_as_nothing(after_scene)
    assert b.get(f"/api/creations/{bid}").json()["revision"] == placed["revision"]

    # Lists and the profile hold the shop's own items only.
    leaked = lambda answer: [name for name, value in theirs.items() if value in answer.text]  # noqa: E731
    for path in ("/api/creations", "/api/creations?status=abandoned", "/api/looks", "/api/shop-profile",
                 f"/api/creations/{bid}/jobs", f"/api/creations/{bid}/visuals", f"/api/creations/{bid}/versions"):
        answer = b.get(path)
        assert answer.status_code == 200 and leaked(answer) == [], (path, leaked(answer))
    assert [item["id"] for item in b.get("/api/creations").json()["items"]] == [bid]
    assert [item["id"] for item in b.get(f"/api/creations/{bid}/visuals").json()["items"]] == [visual_b]
    assert b.get("/api/shop-profile").json() == {"revision": 1, "name": "Boutique Deux", "contact": None, "logo_asset": None}
    assert [item["id"] for item in a.get("/api/creations").json()["items"]] == [cid]
    assert [item["id"] for item in a.get("/api/looks").json()["items"]] == [look_a] and b.get("/api/looks").json()["items"] == []
    # The conditions (D-TERMS-002) take no id: A's acceptance is A's alone, and B's accepts for B without touching A's.
    accepted_a, accepted_b = "2026-11-18T08:00:00.000000+00:00", "2026-11-18T09:00:00.000000+00:00"  # the clock's
    monkeypatch.setattr(terms, "utc_now", lambda: accepted_a)
    assert a.post("/api/terms", json={"version": terms.VERSION}).json()["accepted_at"] == accepted_a
    assert [shop.get("/api/terms").json()["accepted_at"] for shop in (a, b)] == [accepted_a, None]
    monkeypatch.setattr(terms, "utc_now", lambda: accepted_b)
    assert b.post("/api/terms", json={"version": terms.VERSION}).json()["accepted_at"] == accepted_b
    assert [shop.get("/api/terms").json()["accepted_at"] for shop in (a, b)] == [accepted_a, accepted_b]

    # Credits (D-BALANCE-004): each shop reads its own. Both started with 100; A's scene and text material took two,
    # B's scene one. A's grant moves A's balance only; B at zero gets 402 while A has credits, and A's does not move.
    def balances(of_a, of_b):
        for shop, available in ((a, of_a), (b, of_b)):
            answer = shop.get("/api/balance")
            assert answer.status_code == 200 and answer.json() == {
                "available": available, "pending": 0, "purchase_fr": "Pour obtenir des crédits, contactez l’administrateur.",
                "blocked": {"scene": None, "text_texture": None}}, answer.text

    balances(98, 99)
    with write_tx(engine) as conn:
        credits.grant(conn, 1, 5, origin="offered", ref="a-only", actor="tests")
    balances(103, 99)
    with write_tx(engine) as conn:
        credits.correct(conn, shop_b, -99, ref="b-zero", note="test", actor="tests")
    plan_b2 = send(b, "POST", f"/api/creations/{bid}/plans", PLAN, placed["revision"])
    assert plan_b2.status_code == 201, plan_b2.text
    at_zero = send(b, "POST", f"/api/creations/{bid}/scenes", {"plan_id": plan_b2.json()["id"],
                                                               "acknowledged_warnings": ["low_resolution"]}, placed["revision"])
    assert (at_zero.status_code, at_zero.json()["error"]["code"]) == (402, "no_credit"), at_zero.text
    balances(103, 0)
    assert b.get(f"/api/jobs/{scene_job_a}").json()["error"]["code"] == "not_found"

    # Same bytes: B uploads A's original, then A's generated scene as a style. The answers are those of new bytes; B
    # reads the file it uploaded, and still nothing that is A's.
    fresh = b.post("/api/assets", files={"file": ("n.png", photo(colour="teal"), "image/png")}, data={"role": "original"})
    same = b.post("/api/assets", files={"file": ("o.png", photo(), "image/png")}, data={"role": "original"})
    assert same.status_code == fresh.status_code == 201 and same.json()["asset"] == original_a
    assert sorted(same.json()) == sorted(fresh.json()) and same.json()["warnings"] == fresh.json()["warnings"]
    scene_bytes = a.get(f"/api/assets/{scene_sha_a}").content
    as_style = b.post("/api/assets", files={"file": ("s.png", scene_bytes, "image/png")}, data={"role": "style"})
    assert as_style.status_code == 201 and as_style.json()["asset"] == scene_sha_a
    assert b.get(f"/api/assets/{original_a}").content == a.get(f"/api/assets/{original_a}").content
    assert b.get(f"/api/assets/{scene_sha_a}").status_code == 200
    for path in (f"/api/product-inputs/{input_a}", f"/api/visuals/{visual_a}", f"/api/thumbnails/{scene_sha_a}?v=1",
                 f"/api/thumbnails/{original_a}?v=1"):
        assert b.get(path).json()["error"]["code"] == "not_found", path

    # A's objects are as A left them.
    after = a.get(f"/api/creations/{cid}").json()
    assert (after["revision"], after["status"]) == (rev, "active")
    assert a.get(f"/api/looks/{look_a}").json()["name"] == "Style A"
    assert a.get(f"/api/visuals/{visual_a}").json()["status"] == "approved"
    assert a.get(f"/api/text-effects/{effect_a}").json()["status"] == "proposed"
    assert a.get("/api/shop-profile").json()["logo_asset"] == logo_a

    # The operator's view answers neither shop.
    assert a.get("/api/status").status_code == b.get("/api/status").status_code == 404
    # Nor do the operator's routes (D-ADMIN-001), held by their prefix: they hold no shop's objects; to each shop the
    # session read says nobody, and every one but the three public session operations is 401 (full matrix: test_admin).
    operator = {(method.upper(), path) for path, methods in a.app.openapi()["paths"].items() for method in methods
                if path.startswith("/api/admin/")}
    for shop in (a, b):
        assert shop.get("/api/admin/session").json() == {"authenticated": False, "configured": False}
        for method, path in sorted(operator - {(public, "/api/admin/session") for public in ("GET", "POST", "DELETE")}):
            answer = send(shop, method, re.sub(r"\{\w+\}", "1", path), {})
            assert (answer.status_code, answer.json()["error"]["code"]) == (401, "unauthenticated"), (method, path)

    # The routes the flow above reached only through a refusal, each answered once with success, so that the walk below
    # reads their own answers (T-BALANCE-006 review r1). A's objects change from here on.
    def current():
        return a.get(f"/api/creations/{cid}").json()["revision"]

    for path in (f"/api/plans/{plan_a['id']}", f"/api/creations/{cid}/versions/1", f"/api/text-proposals/{proposal_a}"):
        assert a.get(path).status_code == 200, path
    done = [send(a, "POST", f"/api/plans/{plan_a['id']}/revisions", {
                 k: plan_a["plan"][k] for k in ("scene", "product_region", "overlay_regions", "palette")}, current()),
            send(a, "POST", f"/api/text-effects/{effect_a}/apply", None, current())]
    done.append(send(a, "PUT", f"/api/creations/{cid}", a.get(f"/api/creations/{cid}").json()["document"], current()))

    def made(route, body):
        started = send(a, "POST", f"/api/creations/{cid}/{route}", body, current())
        assert started.status_code == 202, (route, started.text)
        return wait(a, started.json()["status_url"])

    made("refinements", {"base_visual_id": visual_a, "instruction_fr": "Plus de lumière"})
    asked = {"layer_id": title_a, "instruction_fr": "Rouge"}
    done.append(send(a, "POST", f"/api/text-proposals/{made('text-proposals', asked)}/reject"))
    applied = made("text-proposals", asked)
    done.append(send(a, "POST", f"/api/text-proposals/{applied}/apply", {}, current()))
    done.append(send(a, "POST", f"/api/text-effects/{made('text-effects', {'layer_id': title_a, 'proposal_id': applied})}/reject"))
    copied = send(a, "POST", f"/api/creations/{cid}/copies", {"source_revision": current(), "reason": "price_update"})
    abandoned = send(a, "POST", f"/api/creations/{copied.json()['id']}/abandon", None, copied.json()["revision"])
    done += [copied, abandoned, send(a, "POST", f"/api/creations/{copied.json()['id']}/restore", None, abandoned.json()["revision"]),
             send(a, "PUT", f"/api/looks/{look_a}", {"name": "Style A bis"}), send(a, "DELETE", f"/api/looks/{look_a}"),
             a.post("/api/session/password", json={"current_password": PASSWORD, "new_password": secrets.token_hex(8)})]
    assert all(answer.is_success for answer in done), [(answer.request.url.path, answer.text) for answer in done if not answer.is_success]
    # No dollar figure in any answer to a shop (D-BALANCE-004, R-BALANCE-001): every JSON answer of this test walked to
    # its last key, the service's capabilities and a cancellation stored before 0014 and replayed included. /api/status,
    # the operator's, gave both shops its 404 just above.
    assert a.get("/api/capabilities").status_code == b.get("/api/capabilities").status_code == 200
    operation, _ = old_cancellation(engine, scene_job_a)
    assert a.post(f"/api/jobs/{scene_job_a}/cancel", json={}, headers={"Idempotency-Key": operation}).status_code == 200
    assert b.delete("/api/session").json() == {"authenticated": False}  # B's last request: its session ends
    schema ={(method.upper(), path) for path, methods in a.get("/api/openapi.json").json()["paths"].items() for method in methods}
    json_answers = [answer for answer in answers if answer.headers.get("content-type", "").startswith("application/json")]
    walked = [answer.json() for answer in json_answers]
    dollars = {name for body in walked for name in json_keys(body) if re.search("micros|usage|cost|estimate|usd", name, re.I)}
    assert len(walked) > 100 and dollars == set(), (len(walked), dollars)
    # The walk sees a successful answer of every route a shop reads, apart from the refusals of the attempts above: a
    # dollar field added to a route's own answer could not hide behind its refusals.
    succeeded = {route_of(schema, answer.request) for answer in json_answers if answer.is_success
                 and answer.request.url.path != "/api/openapi.json"} - operator  # no shop reads the operator's
    assert succeeded == schema - NOT_WALKED - operator, f"no successful answer walked: {sorted(schema - NOT_WALKED - operator - succeeded)}"
    # Every route of the schema is attempted, answers with the shop's own data only, or is exempt for a stated reason.
    # What this does not see: a route hidden from the schema (include_in_schema=False) or a mount, which
    # test_every_route_the_application_answers_is_in_the_schema refuses below; and a route put in OWN or EXEMPT
    # without its check, which only a reader of those two sets can catch.
    covered = {(method, template) for method, template, _ in attempts + after_scene} | OWN | EXEMPT | operator
    assert covered == schema, f"not covered: {sorted(schema - covered)}; not in the schema: {sorted(covered - schema)}"


def test_every_route_the_application_answers_is_in_the_schema(settings, tmp_path, monkeypatch):
    """The test above counts the schema's routes: a route hidden from it would escape it. The application as deployed,
    the built frontend served, answers the schema's routes and two more, named: the schema's own and the frontend."""
    (tmp_path / "dist").mkdir()
    monkeypatch.setattr(rendering, "BUILD_DIR", tmp_path / "dist")
    settings.serve_frontend = True
    app = create_app(settings)
    assert any(isinstance(route, Mount) for route in app.routes)  # the mount is there, and named in application_routes
    schema = {(method.upper(), path) for path, methods in app.openapi()["paths"].items() for method in methods}
    answered = set(application_routes(app.routes))
    assert answered == schema, f"hidden from the schema: {sorted(answered - schema)}; not answered: {sorted(schema - answered)}"


def test_a_tab_bound_to_another_shop_reads_changes_and_ends_nothing(client):
    """X-Affiche-Shop (D-MULTI-SHOP-002) is a stale-tab guard, not authentication: a value that is not the session's
    shop gets the request refused before anything is done, sign-out included; an absent one passes."""
    b, shop_b = sign_in_second_shop(client)
    stale = {"X-Affiche-Shop": "1"}  # B's cookie, from a tab still bound to A
    refused = {"code": "shop_changed", "retryable": False,
               "message_fr": "Une autre boutique est connectée dans ce navigateur. Connectez-vous pour continuer."}
    for answer in (b.get("/api/shop-profile", headers=stale), b.get("/api/creations", headers=stale),
                   b.put("/api/shop-profile", json={"name": "Volé", "contact": None, "logo_asset": None},
                         headers=stale | {"Idempotency-Key": key(), "If-Match": '"1"'}),
                   b.post("/api/assets", files={"file": ("a.png", photo(), "image/png")}, data={"role": "original"}, headers=stale),
                   b.delete("/api/session", headers=stale)):
        assert (answer.status_code, answer.json()["error"]) == (409, refused), answer.text
    with client.app.state.engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM asset_access")).scalar_one() == 0
    assert b.get("/api/shop-profile").json() == {"revision": 1, "name": "Boutique Deux", "contact": None, "logo_asset": None}
    for forged in ("", "0", "B", f"{shop_b}0", f"{shop_b}.0", f"1, {shop_b}"):  # a forged value gains nothing
        assert b.get("/api/creations", headers={"X-Affiche-Shop": forged}).status_code == 409, forged
    # The session's own shop passes, and so does no header at all (an <img>, a bundle that does not send it).
    assert b.get("/api/creations", headers={"X-Affiche-Shop": str(shop_b)}).status_code == 200
    assert b.get("/api/creations").status_code == 200
    # Asking who is signed in, and signing in, never check it: that is how a tab learns its shop.
    assert b.get("/api/session", headers=stale).json() == {"authenticated": True, "shop_id": shop_b}
    assert b.delete("/api/session", headers={"X-Affiche-Shop": str(shop_b)}).json() == {"authenticated": False}
    assert b.delete("/api/session", headers=stale).status_code == 409  # signed out: nothing of A's to end here either
    signing_in = b.post("/api/session", json=credentials("wrong", "boutique-deux"), headers=stale)
    assert signing_in.json()["error"]["code"] == "wrong_credentials"  # its own answer, not shop_changed
    assert client.get("/api/session").json() == {"authenticated": True, "shop_id": 1}  # A's own session, untouched
