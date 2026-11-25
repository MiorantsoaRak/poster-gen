import asyncio
import json
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import httpx2
import pytest
from alembic import command
from sqlalchemy import text

from affiche import shops
from affiche.api import MESSAGES
from affiche.config import load_settings
from affiche.db import make_engine, migrate, utc_now, write_tx
from affiche.posters import jobs, reads, store, visuals
from affiche.posters.models import CopyCreation, ProductInput
from affiche.posters.planner import MODEL
from affiche.posters.plans import Headline, wire_schema
from affiche.posters.store import Refused
from affiche.visuals.admission import spent_micros
from fastapi.testclient import TestClient

from test_api import ORIGIN, PASSWORD, client, create_draft, credentials, login, password_hash, post, second_shop, settings  # noqa: F401
from test_config import env  # noqa: F401
from test_admission import _ledger_call, _seed
from test_db import accepted, bare_engine, credited, engine, unaccepted  # noqa: F401
from test_poster_drafts import draft, input_id, key, photo  # noqa: F401
from test_poster_visuals import execute, fixed

ESTIMATE = 20_000  # ESTIMATE_READ_USD 0.02
REAL = 1200 * 2 + 150 * 10  # the usage of reply() at the pinned rate card


@pytest.fixture
def stub(env):
    env.setenv("PLANNER_PROVIDER", "stub")


@pytest.fixture
def claude(env, settings):
    env.setenv("PLANNER_PROVIDER", "claude")
    env.setenv("ANTHROPIC_API_KEY", "test-secret-not-real")
    return load_settings(env_file=None)


def body(text, creation_id=None, history=(), visual_id=None, **draft):
    return {"text": text, "draft": {"product_photos": 1, "inspiration": False} | draft, "history": list(history)} | (
        {"creation_id": creation_id} if creation_id else {}) | ({"visual_id": visual_id} if visual_id else {})


def reply(fields=None, **updates):
    fields = {"intent": "describe", "product_name": None, "price_ar": None, "style": None,
              "instruction_fr": None, "identity": None} | (fields or {})
    return httpx2.Response(200, headers={"request-id": "req-read"}, json={
        "model": MODEL, "stop_reason": "end_turn", "content": [{"type": "text", "text": json.dumps(fields)}],
        "usage": {"input_tokens": 1200, "output_tokens": 150}} | updates)


THOUGHT = {"type": "thinking", "thinking": "", "signature": "sig"}
ANSWER = {"type": "text", "text": json.dumps({"intent": "describe", "product_name": "JBL Flip 7", "price_ar": 700000,
                                              "style": None, "instruction_fr": None, "identity": None})}


def ask(engine, settings, response, text="JBL Flip 7, 700 000 Ar", key=None, shop=1, **draft):
    """One read through the real adapter and a mocked transport. Returns (answer or Refused, requests)."""
    requests = []

    def handle(request):
        requests.append(request)
        if callable(response):
            return response()
        if isinstance(response, Exception):
            raise response
        return response

    try:
        result = asyncio.run(reads.read(engine, settings, shop, key or str(uuid4()), reads.ReadRequest(**body(text, **draft)),
                                        MESSAGES, transport=httpx2.MockTransport(handle)))
    except Refused as refused:
        result = refused
    return result, requests


def rows(engine):
    with engine.connect() as conn:
        return [dict(row) for row in conn.exec_driver_sql("SELECT * FROM chat_reads ORDER BY created_at").mappings()]


def insert(engine, created_at, status="succeeded", cost=0, key=None):
    with write_tx(engine) as conn:
        conn.exec_driver_sql(
            "INSERT INTO chat_reads (id,shop_id,key,payload_sha,status,provider,model,rate_card_json,cost_micros,"
            "cost_is_estimate,created_at) VALUES (?,1,?,'sha',?,'claude','m','{}',?,1,?)",
            (str(uuid4()), key or str(uuid4()), status, cost, created_at))


def test_migration_0012_on_a_0011_database(tmp_path, monkeypatch):
    engine = make_engine(tmp_path)
    upgrade = command.upgrade
    try:
        with monkeypatch.context() as patch:
            patch.setattr(command, "upgrade", lambda config, _revision: upgrade(config, "0011"))
            migrate(engine)
        with write_tx(engine) as conn:
            conn.exec_driver_sql("INSERT INTO meta VALUES ('planner_mode', 'stub')")
        migrate(engine)
        migrate(engine)  # start-up replay
        with engine.connect() as conn:
            assert conn.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one() == "0021"
            assert conn.exec_driver_sql("SELECT value FROM meta WHERE key='planner_mode'").scalar_one() == "stub"
            columns = {row[1]: row[3] for row in conn.exec_driver_sql("PRAGMA table_info(chat_reads)")}
            assert conn.exec_driver_sql("SELECT sql FROM sqlite_master WHERE name='chat_reads_created'").scalar_one() \
                == "CREATE INDEX chat_reads_created ON chat_reads (created_at)"
        assert columns == {"id": 0, "shop_id": 1, "creation_id": 0, "key": 1, "payload_sha": 1, "status": 1,
                           "provider": 1, "model": 1, "rate_card_json": 1, "cost_micros": 1, "cost_is_estimate": 1,
                           "usage_json": 0, "provider_request_id": 0, "response_json": 0, "created_at": 1,
                           "finished_at": 0}
        with pytest.raises(Exception, match="CHECK"), write_tx(engine) as conn:
            conn.exec_driver_sql("INSERT INTO chat_reads (id,shop_id,key,payload_sha,status,provider,model,"
                                 "rate_card_json,cost_micros,cost_is_estimate,created_at) "
                                 "VALUES ('a',1,'k','s','queued','p','m','{}',0,0,'now')")
    finally:
        engine.dispose()


REJECTED = [  # (message, the partial value a model could return): no amount of the owner's, so no candidate
    ("JBL A55..123 Ar", 123), ("JBL 七700 123 Ar", 123), ("JBL ⁻700 000 Ar", 700000), ("JBL 700٫123 456 Ar", 123456),
    ("-700 123 Ar", 123), ("+700 000 Ar", 700000), ("−700 000 Ar", 700000), ("700,123 456 Ar", 456),
    ("٧700 123 Ar", 123), ("Prix 1234 567 Ar", 567), ("700 000,00 Ar", 0),
    ("(700 000 Ar)", 700000), ("Armani 700", 700),
    ("Sony WH-1000XM6 noir", 1000), ("0 Ar", 0), ("000 Ar", 0), ("0", 0),
    ("1.5 000 Ar", 5000), ("700.00 Ar", 70000),
    ("JBL Flip 7. 700 000 Ar", 700000), ("JBL (7) 700 000 Ar", 700000), ("JBL 7+ 700 000 Ar", 700000),
    # D-KIT-002: without a unit, under 10 000, from a 0, glued to more digits, or a decimal thousands.
    ("Batterie 5000 mAh", 5000), ("TV 4K", 4000), ("Appel 0341234567", 341234567), ("Tel 034 12 345 67", 3412),
    ("JBL 1 250 000,00", 1250000), ("JBL 1,5k", 1500), ("JBL -700 000", 700000), ("JBL (700 000)", 700000),
    ("JBL 05k", 5000), ("Prix 9999", 9999), ("JBL 7+ 700 000", 700000), ("500", 500),
    # T-KIT-016 (review r1 of T-KIT-003): a telephone number, whatever _cut keeps of it; another currency; a measure
    # after a number without an ariary unit (the lead's decision, 2026-11-23).
    ("Contact 034 1234567", 1234567), ("JBL 032 12 34567", 34567), ("Casque JBL, contact 034 1234567", 1234567),
    ("Casque 250000 €", 250000), ("Casque 250 000 $", 250000), ("Casque 1 250 000 Fmg", 1250000),
    ("Casque 250000 euros.", 250000), ("Casque 250k €", 250000), ("Casque 250 000 dollars", 250000),
    ("Powerbank Xiaomi 20000 mAh", 20000), ("Powerbank 20000mAh", 20000), ("Powerbank 20 000 MAH.", 20000),
    ("Powerbank 20k mAh", 20000), ("Disque 12000 rpm", 12000), ("Clé 64000 Mo", 64000),
    ("JBL 七 700 000 Ar", 700000), ("JBL \u2077 700 000 Ar", 700000),  # numeric, not decimal: still not a model code
]


@pytest.mark.parametrize(("message", "amounts"), [
    ("Sony WH-1000XM6 noir, 700 000 Ar", [700000]),  # review P1-2: 1000 is a model number, not an amount
    ("Redmi Note 13 700 000 Ar", [13700000, 700000]),  # the model chooses; both are what the owner wrote
    ("Galaxy A55 700 000 Ar", [700000]), ("Sony WH-1000 700 000 Ar", [700000]), ("Prix: 700 000 Ar", [700000]),
    ("700.000 Ar", [700000]), ("700000Ar", [700000]), ("700.000ar", [700000]), ("700 000 Ar.", [700000]),
    ("700 000 ariary", [700000]), ("700 000 MGA!", [700000]), ("2 050 000 ar", [2050000]),
    # A digit token ending with , ; or : closes the name; the amount after the space stands alone.
    ("JBL Flip 7, 700 000 Ar", [700000]), ("iPhone 15, 1 200 000 Ar", [1200000, 200000]),
    ("JBL Flip 7; 700 000 Ar", [700000]), ("Note 13: 700 000 Ar", [700000]),
    # Deliberate (user decision, review r3): a comma then a space separates two things, so 123 is an amount here.
    # A French decimal has no space, and "700,123 456 Ar" stays without candidate (REJECTED).
    ("700, 123 Ar", [123]),
    ("Prix 700\t000 Ar", [700000]),  # a tab is whitespace: two whole digit tokens, a valid grouping
    ("13.700.000 Ar", [13700000]),  # suffixes only for groups written with spaces
    ("avant 800 000 Ar, maintenant 700 000 Ar", [800000, 700000]),
    ("700 000", [700000]), (" 650000 ", [650000]), ("700.000", [700000]),  # the whole message, without a unit
    ("13 700 000", [13700000]), ("1234 567", []),
    # A leading zero on the whole amount is still that amount; only a suffix starting with 0 is not one.
    ("0700000 Ar", [700000]), ("0700000", [700000]), ("050 000 Ar", [50000]), ("2 050 000 Ar", [2050000]),
    *((message, []) for message, _partial in REJECTED),
    ("800000Ar 700 000 Ar", [800000, 700000]),
    # T-CHAT-002, everyday writing: a model code with a letter before the amount (5G, 256Go, 128GB, 13C).
    ("Samsung Galaxy A55 5G 256Go 1 450 000 Ariary", [1450000, 450000]), ("Redmi 13C 128GB 700 000 Ar", [700000]),
    ("Sony WH-1000XM6 700 000 Ar", [700000]), ("Galaxy S24+ 700 000 Ar", [700000]),
    # A token of four digits or more, or with a dot, is the amount alone: the digits before it are the name.
    ("airpods pro 2 350000ar fond clair", [350000]), ("airpods pro 2 350.000 Ar", [350000]),
    ("Redmi Note 13 700000 Ar", [700000]), ("12 3456 Ar", [3456]), ("2 350 000 Ar", [2350000, 350000]),
    # D-KIT-002, as sellers write them: each writing with each unit, and without (from 10 000).
    *((f"Casque {written}{unit}", [250000]) for written in ("250000", "250 000", "250.000", "250k", "250K")
      for unit in (" Ar", " ar", " ariary", " MGA", "Ar", "")),
    ("casque sony wh-ch720n noir 250000", [250000]), ("Casque 250k, noir", [250000]), ("Casque 250 000.", [250000]),
    ("Livraison 5k Ar", [5000]), ("Casque 10k", [10000]), ("Casque 10 000", [10000]),
    # Moved from REJECTED: a thousands token, and bare runs from 10 000.
    ("700k", [700000]), ("arrivage 700 000", [700000]), ("700 000 Argent", [700000]), ("700 000 A r", [700000]),
    ("2 350000", [350000]),
    # Beside an amount with its unit: both, the model or the owner chooses.
    ("250000, livraison 5000 Ar", [250000, 5000]), ("Redmi Note 13 700 000", [13700000, 700000]),
    ("SSD 1000 Go 350000", [350000]), ("Casque 2024 250000", [250000]), ("Batterie 5000 mAh 250000", [250000]),
    ("13 700 000 ou 700 000", [13700000, 700000]), ("JBL Flip 7, 700 000", [700000]),
    # The whole message alone: from 1 000 (the message says nothing else).
    ("5000", [5000]), ("2 350000", [350000]),
    # T-KIT-016: a group before a thousands token may be its millions: both readings.
    ("Prix 1 200k Ar", [1200000, 200000]), ("iPhone 13 250k", [13250000, 250000]), ("Casque 2 500k", [2500000, 500000]),
    ("Casque 1 050k", [1050000]), ("SSD 1000 250k", [250000]),
    # A measure ends a bare number, never an amount with its ariary unit; the price beside it stays.
    ("Powerbank 20000 mAh 85000", [85000]), ("Powerbank 20000 mAh, 20 000 Ar", [20000]),
    ("Powerbank 20000mAh 85 000 Ar", [85000]), ("Casque 250 000 Ar, 300 € ailleurs", [250000]),
])
def test_candidate_amounts(message, amounts):
    assert reads.candidate_amounts(message) == amounts


@pytest.mark.parametrize("message", ["0700000 Ar", "0700000"])
def test_a_leading_zero_does_not_hide_the_price(message):
    fields = reads.Fields(intent="describe", product_name=None, price_ar=700000, style=None, instruction_fr=None, identity=None)
    answer = reads.build(fields, reads.ReadRequest(**body(message, name="JBL Flip 7")), MESSAGES)
    assert (answer["card"]["kind"], answer["card"]["price_ar"]) == ("recap", 700000)


@pytest.mark.parametrize(("message", "partial"), REJECTED)
def test_a_partial_amount_from_the_model_is_never_the_price(message, partial):
    fields = reads.Fields(intent="describe", product_name="JBL", price_ar=partial, style=None, instruction_fr=None, identity=None)
    for draft in ({}, {"price_ar": 500000}):  # asked again even when the draft holds an earlier price
        answer = reads.build(fields, reads.ReadRequest(**body(message, **draft)), MESSAGES)
        assert answer["card"]["kind"] == "ask_price" and answer["draft"]["price_ar"] == draft.get("price_ar")
    # On a poster too: the change is refused with the price question, never offered with a price nobody wrote.
    assert change(message, words(DRAWN), price_ar=partial) == {"kind": "refused", "text_fr": MESSAGES["card_ask_price"]}


def test_every_card_from_the_stub_reader(stub, client, settings):
    login(client)
    assert client.get("/api/capabilities").json()["chat_available"] is True

    def card(text, creation_id=None, **draft):
        answer = post(client, "/api/reads", body(text, creation_id, **draft))
        assert answer.status_code == 201, answer.text
        assert answer.json()["card"]["text_fr"]
        return answer.json()["card"], answer.json()["draft"]

    assert card("???") == ({"kind": "unclear", "text_fr": "Écrivez le produit et son prix."},
                           {"name": None, "price_ar": None, "style": None, "product_photos": 1, "inspiration": False})
    asked, draft = card("700 000 Ar, sombre")
    assert asked == {"kind": "ask_product", "text_fr": "Quel est le produit ? Marque et modèle."}
    assert (draft["price_ar"], draft["style"]) == (700000, "sombre")
    asked, draft = card("JBL Flip 7")
    assert asked == {"kind": "ask_price", "text_fr": MESSAGES["card_ask_price"]} and draft["name"] == "JBL Flip 7"
    asked, draft = card("Sony WH-1000XM6 noir, 700 000 Ar", product_photos=0)
    assert asked == {"kind": "ask_photo", "text_fr": "Il me faut une photo du produit."}
    assert (draft["name"], draft["price_ar"]) == ("Sony WH-1000XM6 noir", 700000)
    recap, draft = card("JBL Flip 7, 700 000 Ar", style="clair", product_photos=2, inspiration=True)
    assert recap == {"kind": "recap", "text_fr": MESSAGES["card_recap"], "name": "JBL Flip 7", "price_ar": 700000,
                     "style": "clair"}
    assert draft == {"name": "JBL Flip 7", "price_ar": 700000, "style": "clair", "product_photos": 2, "inspiration": True}
    # D-TEXT-FIRST-006: the shop's logo and contact asked with the product; the words are not part of its name.
    for message in ("JBL Flip 7, 700 000 Ar, avec le logo et le contact de la boutique", "JBL Flip 7, 700 000 Ar avec le contact"):
        recap, draft = card(message)
        assert recap == {"kind": "recap", "text_fr": MESSAGES["card_recap"], "name": "JBL Flip 7", "price_ar": 700000,
                         "style": None, "identity": True} and draft["identity"] is True
    assert card("650 000 Ar", name="JBL Flip 7", identity=True)[0]["identity"] is True
    for message in ("JBL Flip 7, 700 000 Ar, sans logo ni contact", "JBL Flip 7, 700 000 Ar sans le logo de la boutique"):
        recap, draft = card(message, identity=True)
        assert (recap["name"], recap["identity"], draft["identity"]) == ("JBL Flip 7", False, False)
    # An answer to a question changes only its own field.
    recap, _ = card("650 000 Ar", name="JBL Flip 7", price_ar=700000)
    assert (recap["kind"], recap["name"], recap["price_ar"]) == ("recap", "JBL Flip 7", 650000)
    recap, _ = card("JBL Flip 7 blanc", name="JBL Flip 7", price_ar=700000)
    assert (recap["name"], recap["price_ar"]) == ("JBL Flip 7 blanc", 700000)
    # The title rules of the scene route, with their existing sentences; the refused name is not kept.
    for name, code in (("x" * 61, "title_too_long"), ("JBL promo", "title_commercial_text")):
        asked, draft = card(name)
        assert asked == {"kind": "ask_product", "text_fr": MESSAGES[code]} and draft["name"] is None
    # A straight quote is curled, not refused (D-KIT-007).
    assert card('TV 32"')[1]["name"] == "TV 32″"

    assert all(row["status"] == "succeeded" and row["cost_micros"] == 0 and row["provider"] == "stub"
               for row in rows(client.app.state.engine))
    # A poster without versions: a read needs the version the owner looks at, so there is none to change.
    creation, count = create_draft(client)["id"], len(rows(client.app.state.engine))
    answer = post(client, "/api/reads", body("Un fond plus chaud", creation, visual_id=str(uuid4())))
    assert answer.status_code == 404 and answer.json()["error"]["code"] == "not_found"
    answer = post(client, "/api/reads", body("Un fond plus chaud", creation))
    assert answer.status_code == 409 and answer.json()["error"] == {
        "code": "reload_required", "retryable": False, "message_fr": "Rechargez la page pour continuer."}
    assert len(rows(client.app.state.engine)) == count  # nothing reserved, nothing paid


def test_an_older_bundle_changes_nothing_and_pays_nothing(stub, client):
    """ADR-103: a tab from before a change that makes it unsafe is refused at the door, for every state-changing data
    route at once, its sign-in included (it has no identifier, D-MULTI-SHOP-002); it can still read and sign out, and
    signs in again after its reload."""
    login(client)
    creation = create_draft(client)
    id, engine = creation["id"], client.app.state.engine
    count = lambda table: engine.connect().exec_driver_sql(f"SELECT COUNT(*) FROM {table}").scalar_one()  # noqa: E731
    old = TestClient(client.app, base_url=ORIGIN, headers={"Origin": ORIGIN}, cookies=dict(client.cookies))  # no header
    refusal = {"code": "bundle_outdated", "retryable": False, "message_fr": "Cette page est une ancienne version de l’application : rien n’est enregistré depuis sa mise à jour. Notez vos dernières modifications, puis rechargez la page."}
    # The two sign-outs need no bundle; the operator's protected routes refuse a shop's tab (401) before it, and test_admin
    # checks their bundle rule with an operator session (D-ADMIN-001). The operator's sign-in stays in.
    routes = [(method.upper(), path) for path, methods in client.app.openapi()["paths"].items() for method in methods
              if method in ("post", "put", "patch", "delete")
              and (method, path) not in (("delete", "/api/session"), ("delete", "/api/admin/session"))
              and (path == "/api/admin/session" or not path.startswith("/api/admin/"))]
    assert ("POST", "/api/admin/session") in routes
    assert len(routes) > 25 and ("PUT", "/api/creations/{id}") in routes and ("POST", "/api/session") in routes, routes
    before = {table: count(table) for table in ("chat_reads", "poster_jobs", "scene_plans", "mutation_keys", "creations", "creation_versions", "assets", "looks")}
    for bundle in (None, "2", "1", "0", "", "deux", "3.0", "-3", "٣".encode(), "1" * 12):
        headers = {"Idempotency-Key": str(uuid4()), "If-Match": '"1"'} | ({} if bundle is None else {"X-Affiche-Bundle": bundle})
        for method, path in routes:
            answer = old.request(method, re.sub(r"\{\w+\}", id, path), json={}, headers=headers)
            assert (answer.status_code, answer.json()["error"]) == (409, refusal), (bundle, method, path, answer.text)
        # The requests an old tab would really send, whole and valid: nothing reserved, no job, the revision as it was.
        assert old.post("/api/reads", json=body("JBL Flip 7, 700 000 Ar"), headers=headers).status_code == 409
        assert old.post(f"/api/creations/{id}/plans", json={"mode": "fixed", "direction": "Studio clair", "format": "feed"},
                        headers=headers).status_code == 409
        assert old.post(f"/api/creations/{id}/scenes", json={"plan_id": str(uuid4()), "format": "feed"}, headers=headers).status_code == 409
        assert old.put(f"/api/creations/{id}", json=creation["document"] | {"offer": {"title": "JBL", "price_ar": 1}},
                       headers=headers).status_code == 409
        assert old.post("/api/assets", files={"file": ("a.png", photo(), "image/png")}, data={"role": "original"},
                        headers=headers).status_code == 409
    assert {table: count(table) for table in before} == before and rows(engine) == []
    assert old.get(f"/api/creations/{id}").json()["revision"] == creation["revision"] == 1
    # Reading, and the session's own routes, never ask for it: the reload and the sign-in after it always work.
    for path in ("/api/session", "/api/capabilities", "/api/creations", f"/api/creations/{id}/jobs"):
        assert old.get(path, headers={"X-Affiche-Bundle": "1"}).status_code == 200, path
    assert old.delete("/api/session").status_code == 200 and old.get("/api/creations").status_code == 401
    assert old.post("/api/reads", json=body("JBL"), headers={"Idempotency-Key": str(uuid4())}).status_code == 401  # as before
    for sign_in in ({"password": PASSWORD}, credentials()):  # what the older form sends, and a whole body
        assert old.post("/api/session", json=sign_in).json()["error"] == refusal
    assert old.post("/api/session", json=credentials(), headers={"X-Affiche-Bundle": "2"}).status_code == 409
    # The current bundle, and a later one, pass.
    login(client)  # the session above was the same one
    assert post(client, "/api/reads", body("JBL Flip 7, 700 000 Ar")).status_code == 201
    assert client.post("/api/reads", json=body("JBL Flip 7, 700 000 Ar"),
                       headers={"Idempotency-Key": str(uuid4()), "X-Affiche-Bundle": "4"}).status_code == 201
    changed = creation["document"] | {"offer": creation["document"]["offer"] | {"price_ar": 700000}}
    assert client.put(f"/api/creations/{id}", json=changed,
                      headers={"Idempotency-Key": str(uuid4()), "If-Match": '"1"'}).json()["revision"] == 2


def test_route_validation_ownership_and_replay(stub, client):
    assert client.post("/api/reads", json=body("JBL")).status_code == 401
    login(client)
    for bad in (body(""), body("   "), body("x" * 501), body("JBL", product_photos=4), body("JBL", style="néon"),
                body("JBL", name="x" * 161), body("JBL", history=[{"role": "owner", "text": "a"}] * 7),
                body("JBL", history=[{"role": "system", "text": "a"}]), body("JBL") | {"extra": 1},
                body("JBL", visual_id=str(uuid4())), body("JBL", str(uuid4()), visual_id="v1"),
                {"text": "JBL", "draft": {"inspiration": False}}):
        answer = post(client, "/api/reads", bad)
        assert answer.status_code == 422 and answer.json()["error"]["code"] == "validation_error", answer.text
    assert client.post("/api/reads", json=body("JBL")).status_code == 422  # no Idempotency-Key
    answer = post(client, "/api/reads", body("Un fond plus chaud", str(uuid4())))
    assert answer.status_code == 404 and answer.json()["error"]["code"] == "not_found"
    assert rows(client.app.state.engine) == []  # a refusal stores nothing

    key = {"Idempotency-Key": str(uuid4())}
    first = client.post("/api/reads", json=body("JBL Flip 7, 700 000 Ar", history=[{"role": "app", "text": "Bonjour"}]), headers=key)
    again = client.post("/api/reads", json=body("JBL Flip 7, 700 000 Ar", history=[{"role": "app", "text": "Bonjour"}]), headers=key)
    assert first.status_code == again.status_code == 201 and first.json() == again.json()
    assert len(rows(client.app.state.engine)) == 1
    other = client.post("/api/reads", json=body("JBL Flip 7, 650 000 Ar"), headers=key)
    assert other.status_code == 409 and other.json()["error"]["code"] == "idempotency_reused"


@pytest.fixture
def failing(env):
    env.setenv("STUB_FAIL", "timeout")


def test_stub_fail_is_the_failure_path(stub, failing, client):
    login(client)
    key = {"Idempotency-Key": str(uuid4())}
    for _ in range(2):  # the failure is the stored answer of this key: the second request makes no second read
        answer = client.post("/api/reads", json=body("JBL, 700 000 Ar"), headers=key)
        assert answer.status_code == 503 and answer.json()["error"] == {
            "code": "read_failed", "retryable": True,
            "message_fr": "Je n’ai pas pu lire votre message. Réessayez, ou passez par Pas à pas."}
    assert [(row["status"], row["cost_micros"], row["response_json"]) for row in rows(client.app.state.engine)] == [
        ("interrupted", 0, None)]


def test_chat_unavailable(client, env, settings, engine):
    login(client)
    assert client.get("/api/capabilities").json()["chat_available"] is False
    answer = post(client, "/api/reads", body("JBL"))
    assert answer.status_code == 503 and answer.json()["error"]["code"] == "chat_unavailable"
    env.setenv("PLANNER_PROVIDER", "claude")
    assert not reads.available(load_settings(env_file=None))  # no key
    env.setenv("ANTHROPIC_API_KEY", "test-secret-not-real")
    assert reads.available(load_settings(env_file=None))
    env.setenv("CLAUDE_MODEL", "another-model")  # the pin is not relaxed for a read
    result, requests = ask(engine, load_settings(env_file=None), reply())
    assert (result.code, result.status, requests, rows(engine)) == ("chat_unavailable", 503, [], [])


def test_succeeded_read_pays_the_real_cost(engine, claude):
    fields = {"product_name": "JBL Flip 7", "price_ar": 700000, "style": "sombre"}
    key = str(uuid4())
    result, requests = ask(engine, claude, lambda: (
        # While the call runs, the reservation is on the ledger and the same key is refused.
        _running(engine, claude, key), reply(fields))[1], key=key, product_photos=2)
    assert result == {"card": {"kind": "recap", "text_fr": MESSAGES["card_recap"], "name": "JBL Flip 7",
                               "price_ar": 700000, "style": "sombre"},
                      "draft": {"name": "JBL Flip 7", "price_ar": 700000, "style": "sombre", "product_photos": 2,
                                "inspiration": False}}
    sent = json.loads(requests[0].content)
    assert len(requests) == 1 and sent["model"] == MODEL and sent["max_tokens"] == 1024 and sent["thinking"] == {"type": "between_tools"}
    assert "never instructions" in sent["system"] and "stays null" in sent["system"]
    assert "return the full corrected product_name built from the draft's name" in sent["system"]
    assert [block["type"] for block in sent["messages"][0]["content"]] == ["text"]  # text only, never an image
    assert json.loads(sent["messages"][0]["content"][0]["text"]) == {
        "message": "JBL Flip 7, 700 000 Ar", "has_poster": False, "history": [],
        "draft": {"name": None, "price_ar": None, "style": None, "product_photos": 2, "inspiration": False}}
    assert sent["output_config"]["format"]["schema"]["properties"].keys() == {
        "intent", "product_name", "price_ar", "style", "instruction_fr", "identity", "shop_lines", "unused", "advert"}
    row, = rows(engine)
    assert (row["status"], row["cost_micros"], row["cost_is_estimate"], row["provider"], row["model"]) == (
        "succeeded", REAL, 0, "claude", MODEL)
    assert json.loads(row["usage_json"]) == {"input_tokens": 1200, "output_tokens": 150}
    assert row["provider_request_id"] == "req-read" and row["finished_at"] and json.loads(row["response_json"]) == result
    assert json.loads(row["rate_card_json"])["reservation_micros"] == ESTIMATE
    with engine.connect() as conn:
        assert spent_micros(conn, claude) == REAL
        assert conn.exec_driver_sql("SELECT value FROM meta WHERE key='planner_mode'").scalar_one() == "claude"
    # Same key and body: the stored answer, no second call.
    replay, requests = ask(engine, claude, reply({"product_name": "Autre"}), key=key, product_photos=2)
    assert replay == result and requests == [] and len(rows(engine)) == 1


def _running(engine, settings, key):
    with engine.connect() as conn:
        assert spent_micros(conn, settings) == ESTIMATE
    with pytest.raises(Refused) as refused:
        reads._admit(engine, settings, 1, key, reads.ReadRequest(**body("JBL Flip 7, 700 000 Ar", product_photos=2)))
    assert (refused.value.code, refused.value.status) == ("read_running", 409)


@pytest.mark.parametrize(("response", "status", "cost", "estimate", "kind"), [
    (lambda: reply({"product_name": "JBL"}, usage={}), "succeeded", ESTIMATE, 1, "ask_price"),  # usage unreadable
    (lambda: reply(content=[{"type": "text", "text": "not JSON"}]), "succeeded", REAL, 0, "unclear"),
    (lambda: reply({"intent": "greeting"}), "succeeded", REAL, 0, "unclear"),
    (lambda: reply({"intent": "other"}), "succeeded", REAL, 0, "unclear"),
    # « other » keeps what the read brings (T-KIT-016): a name, then the price question.
    (lambda: reply({"intent": "other", "product_name": "JBL"}), "succeeded", REAL, 0, "ask_price"),
    (lambda: reply({"price_ar": "700000"}), "succeeded", REAL, 0, "unclear"),
    # A price the owner did not write is dropped: 1000 is in the message, but not as an amount.
    (lambda: reply({"product_name": "JBL Flip 7", "price_ar": 7000000}), "succeeded", REAL, 0, "ask_price"),
    (lambda: reply({"product_name": "JBL Flip 7", "price_ar": 700000}), "succeeded", REAL, 0, "recap"),
    # T-CHAT-002: the model's reasoning blocks around the one text block are not a failure.
    (lambda: reply(content=[THOUGHT, ANSWER]), "succeeded", REAL, 0, "recap"),
    (lambda: reply(content=[{"type": "redacted_thinking", "data": "x"}, ANSWER]), "succeeded", REAL, 0, "recap"),
    (lambda: reply(content=[ANSWER, ANSWER]), "interrupted", REAL, 0, None),
    (lambda: reply(content=[{"type": "server_tool_use"}, ANSWER]), "interrupted", REAL, 0, None),
    (lambda: reply(content=[THOUGHT]), "interrupted", REAL, 0, None),
    (lambda: httpx2.Response(429), "failed", 0, 0, None),
    (lambda: httpx2.Response(500), "interrupted", ESTIMATE, 1, None),
    (lambda: httpx2.Response(401), "interrupted", ESTIMATE, 1, None),
    # A cut, refused or foreign answer is a failure, never an "unclear" card; readable usage is the real cost.
    (lambda: reply(stop_reason="max_tokens"), "interrupted", REAL, 0, None),
    (lambda: reply(stop_reason="refusal"), "interrupted", REAL, 0, None),
    (lambda: reply(content=[{"type": "tool_use"}]), "interrupted", REAL, 0, None),
    (lambda: reply(content=[{"type": "text"}]), "interrupted", REAL, 0, None),
    (lambda: reply(content=[{"type": "text", "text": None}]), "interrupted", REAL, 0, None),
    (lambda: reply(content=[{"type": "text", "text": 7}]), "interrupted", REAL, 0, None),
    (lambda: reply(model="unpriced-model"), "interrupted", ESTIMATE, 1, None),
    (lambda: httpx2.Response(200, text="not JSON"), "interrupted", ESTIMATE, 1, None),
    (lambda: (_ for _ in ()).throw(httpx2.ReadTimeout("test-secret-not-real")), "interrupted", ESTIMATE, 1, None),
    (lambda: (_ for _ in ()).throw(httpx2.ConnectError("test-secret-not-real")), "interrupted", ESTIMATE, 1, None),
])
def test_read_state_machine_and_ledger(engine, claude, response, status, cost, estimate, kind):
    key = str(uuid4())
    result, requests = ask(engine, claude, response, key=key)
    row, = rows(engine)
    assert len(requests) == 1  # never retried
    assert (row["status"], row["cost_micros"], row["cost_is_estimate"]) == (status, cost, estimate) and row["finished_at"]
    with engine.connect() as conn:
        assert spent_micros(conn, claude) == cost
    if kind:
        assert result["card"]["kind"] == kind and json.loads(row["response_json"]) == result
    else:
        assert (result.code, result.status, row["response_json"]) == ("read_failed", 503, None)
        replay, requests = ask(engine, claude, reply(), key=key)  # the failure is replayed, not paid again
        assert (replay.code, requests, len(rows(engine))) == ("read_failed", [], 1)


def test_whole_call_is_bounded(engine, claude, monkeypatch):
    async def slow(_settings, _spec, request, _transport):  # a good answer, too late
        await asyncio.sleep(.5)
        return reads.stub_read(request), None, 0, None
    monkeypatch.setattr(reads, "_ask", slow)
    monkeypatch.setattr(reads, "TIMEOUT_S", 0.05)
    result, _ = ask(engine, claude, reply())
    assert result.code == "read_failed"
    assert [(row["status"], row["cost_micros"], row["cost_is_estimate"]) for row in rows(engine)] == [("interrupted", ESTIMATE, 1)]


def test_late_answer_after_the_sweep_changes_nothing(engine, claude):
    def late():
        with write_tx(engine) as conn:
            conn.exec_driver_sql("UPDATE chat_reads SET created_at=?", (
                (datetime.now(UTC) - timedelta(seconds=61)).isoformat(timespec="microseconds"),))
        reads.recover(engine)  # the sweep of another request, or of a restart
        return reply({"product_name": "JBL Flip 7", "price_ar": 700000})

    result, _ = ask(engine, claude, late)
    row, = rows(engine)
    assert (result.code, result.status) == ("read_failed", 503)
    assert (row["status"], row["cost_micros"], row["cost_is_estimate"], row["response_json"]) == ("interrupted", ESTIMATE, 1, None)


def test_crash_between_the_two_transactions_is_closed_by_the_sweep(engine, claude):
    now, old, young = datetime.now(UTC), str(uuid4()), str(uuid4())
    insert(engine, (now - timedelta(seconds=61)).isoformat(timespec="microseconds"), "running", ESTIMATE, key=old)
    insert(engine, (now - timedelta(seconds=30)).isoformat(timespec="microseconds"), "running", ESTIMATE, key=young)
    reads.recover(engine)
    assert [(row["key"], row["status"], row["cost_micros"]) for row in rows(engine)] == [
        (old, "interrupted", ESTIMATE), (young, "running", ESTIMATE)]
    with engine.connect() as conn:
        assert spent_micros(conn, claude) == 2 * ESTIMATE  # a running read counts with its reservation
    # The sweep also runs with every read, and is kept even when that request is refused as a replay.
    with write_tx(engine) as conn:
        conn.exec_driver_sql("UPDATE chat_reads SET status='running', finished_at=NULL, shop_id=1, payload_sha=? "
                             "WHERE key=?", (reads._sha(reads.canonical(reads.ReadRequest(**body("JBL")))), old))
    result, requests = ask(engine, claude, reply(), text="JBL", key=old)
    assert (result.code, requests) == ("read_failed", [])
    assert rows(engine)[0]["status"] == "interrupted"


def test_cap_refusal_reserves_nothing(engine, env, claude):
    env.setenv("SPEND_CAP_USD", "0.03")
    capped = load_settings(env_file=None)
    insert(engine, utc_now(), "running", ESTIMATE)  # 0.02 reserved + 0.02 asked > 0.03
    result, requests = ask(engine, capped, reply())
    assert (result.code, result.status, requests, len(rows(engine))) == ("budget_exhausted", 429, [], 1)
    env.setenv("SPEND_CAP_USD", "0.04")  # exactly at the cap is allowed
    result, requests = ask(engine, load_settings(env_file=None), reply())
    assert result["card"]["kind"] == "ask_product" and len(requests) == 1


def test_daily_limit_at_the_day_edge(engine, claude, monkeypatch):
    monkeypatch.setattr(reads, "DAILY_LIMIT", 2)
    today = datetime.now(UTC).date()
    for _ in range(2):  # yesterday's last instant does not count
        insert(engine, f"{today - timedelta(days=1)}T23:59:59.999999+00:00")
    insert(engine, f"{today}T00:00:00.000000+00:00", "failed")  # today's first instant does, whatever its outcome
    result, _ = ask(engine, claude, reply())
    assert result["card"]["kind"] == "ask_product"
    result, requests = ask(engine, claude, reply())
    assert (result.code, result.status, requests, len(rows(engine))) == ("read_limit", 429, [], 4)
    assert MESSAGES["read_limit"] == "Limite de messages atteinte pour aujourd’hui. Continuez dans Pas à pas."


def test_reads_are_refused_in_the_designs_order(engine, claude, monkeypatch):
    """D-MULTI-SHOP-005: the provider guard (a suspension, the service's cap, the shop's day), then the day's read
    limit, then two reads of the shop in progress. A refusal reserves nothing and sends nothing."""
    shop_b, _ = second_shop(engine)
    monkeypatch.setattr(reads, "DAILY_LIMIT", 2)
    for _ in range(2):  # two reads of shop 1 in progress: 0.04 of its day
        insert(engine, utc_now(), "running", ESTIMATE)
    with write_tx(engine) as conn:
        conn.exec_driver_sql("UPDATE shop_profile SET state='suspended' WHERE id=1")
    claude.spend_cap_usd = claude.shop_daily_spend_usd = Decimal("0.05")  # 0.04 + 0.02 asked > 0.05

    def refused():
        result, requests = ask(engine, claude, reply())
        assert requests == [] and [row["shop_id"] for row in rows(engine)].count(1) == 2
        return result.code, result.status

    def admitted(shop):
        result, requests = ask(engine, claude, reply(), shop=shop)
        assert result["card"]["kind"] == "ask_product" and len(requests) == 1

    assert refused() == ("shop_suspended", 403)
    with write_tx(engine) as conn:
        conn.exec_driver_sql("UPDATE shop_profile SET state='active' WHERE id=1")
    assert refused() == ("budget_exhausted", 429)
    claude.spend_cap_usd = Decimal("20")
    assert refused() == ("shop_daily_limit", 429)
    claude.shop_daily_spend_usd = Decimal("2")
    assert refused() == ("read_limit", 429)
    admitted(shop_b)  # another shop's day of reads is its own
    monkeypatch.setattr(reads, "DAILY_LIMIT", 3)
    assert refused() == ("reads_busy", 429)
    admitted(shop_b)  # and so are its two places
    with write_tx(engine) as conn:  # one of the two ends: its place is free again
        conn.exec_driver_sql("UPDATE chat_reads SET status='succeeded' WHERE id=(SELECT MIN(id) FROM chat_reads "
                             "WHERE shop_id=1 AND status='running')")
    admitted(1)
    assert MESSAGES["reads_busy"].startswith("Deux messages de la boutique sont déjà en cours de lecture.")


@pytest.mark.parametrize(("between", "refusal"), [
    ("UPDATE shop_profile SET state='suspended' WHERE id=1", ("shop_suspended", 403, "failed", 0, 0)),
    ("UPDATE chat_reads SET status='interrupted', finished_at=created_at", ("read_failed", 503, "interrupted", ESTIMATE, 1)),
])
def test_a_read_is_not_sent_when_its_shop_was_suspended_after_its_admission(engine, claude, monkeypatch, between, refusal):
    """reads._send, between the admission and the provider call (D-MULTI-SHOP-006): a suspension committed in between
    closes the read 'failed' at cost 0 and sends nothing; a read the 60 s sweep closed meanwhile is not sent either."""
    admit, key = reads._admit, str(uuid4())

    def then(*args):
        admitted = admit(*args)
        with write_tx(engine) as conn:
            conn.exec_driver_sql(between)
        return admitted

    monkeypatch.setattr(reads, "_admit", then)
    result, requests = ask(engine, claude, lambda: pytest.fail("sent"), key=key)
    row, = rows(engine)
    assert (result.code, result.status, row["status"], row["cost_micros"], row["cost_is_estimate"]) == refusal
    assert requests == [] and row["finished_at"] and row["response_json"] is None
    with engine.connect() as conn:
        assert spent_micros(conn, claude) == refusal[3]
    monkeypatch.setattr(reads, "_admit", admit)
    replay, requests = ask(engine, claude, reply(), key=key)  # the same key later finds it closed: never paid
    assert (replay.code, requests, len(rows(engine))) == ("read_failed", [], 1)


def test_a_read_sent_before_the_suspension_finishes_and_records_its_cost(engine, claude):
    def answer():
        with write_tx(engine) as conn:  # committed after _send: this call was already sent
            conn.exec_driver_sql("UPDATE shop_profile SET state='suspended' WHERE id=1")
        return reply({"product_name": "JBL Flip 7", "price_ar": 700000})

    result, requests = ask(engine, claude, answer)
    row, = rows(engine)
    assert result["card"]["kind"] == "recap" and len(requests) == 1
    assert (row["status"], row["cost_micros"], row["cost_is_estimate"]) == ("succeeded", REAL, 0)


def test_one_shops_day_does_not_stop_anothers_reads_and_the_services_cap_stops_both(engine, claude):
    """R-MULTI-SHOP-003 for reads: each shop's own day of provider spend; at the service's cap every shop is told the
    service is paused, and nothing is reserved."""
    shop_b, _ = second_shop(engine)
    insert(engine, utc_now(), cost=40_000)  # shop 1's day so far
    claude.shop_daily_spend_usd = Decimal("0.05")  # 0.04 + 0.02 asked > 0.05
    mine, sent = ask(engine, claude, reply())
    assert (mine.code, mine.status, sent) == ("shop_daily_limit", 429, [])
    theirs, sent = ask(engine, claude, reply(), shop=shop_b)
    assert theirs["card"]["kind"] == "ask_product" and len(sent) == 1
    claude.spend_cap_usd = Decimal("0.06")  # 0.04 + B's real cost + 0.02 > 0.06
    for shop in (1, shop_b):
        result, sent = ask(engine, claude, reply(), shop=shop)
        assert (result.code, result.status, sent) == ("budget_exhausted", 429, [])
    assert len(rows(engine)) == 2
    with engine.connect() as conn:
        assert spent_micros(conn, claude) == 40_000 + REAL


def test_read_follows_the_planner_mode_lock(engine, env, claude):
    env.setenv("PLANNER_PROVIDER", "stub")
    result, _ = ask(engine, load_settings(env_file=None), reply())
    assert result["card"]["kind"] == "recap"
    result, requests = ask(engine, claude, reply())
    assert (result.code, result.status, requests, len(rows(engine))) == ("provider_mode_mismatch", 409, [], 1)


def test_spend_is_summed_over_the_three_ledgers(engine, env, claude, tmp_path, input_id):
    creation, old = draft(engine, tmp_path, input_id), "2000-01-01T00:00:00.000000+00:00"
    with write_tx(engine) as conn:
        _seed(conn)
        _ledger_call(conn, 111)
        _ledger_call(conn, 5000, started_at=old)  # before SPEND_CAP_SINCE: not counted, in any ledger
        job = jobs.enqueue(conn, claude, 1, creation["id"], 1, "plan", {"n": 1})["job_id"]
        conn.exec_driver_sql("UPDATE poster_calls SET cost_micros=20000 WHERE job_id=?", (job,))
        conn.exec_driver_sql("INSERT INTO poster_calls (id,job_id,call_no,provider,model,rate_card_json,status,"
                             "cost_micros,cost_is_estimate,created_at) SELECT 'old',job_id,2,provider,model,"
                             "rate_card_json,'failed',5000,0,? FROM poster_calls", (old,))
    insert(engine, utc_now(), cost=333)
    insert(engine, old, cost=5000)
    with engine.connect() as conn:
        assert spent_micros(conn, claude) == 111 + 20000 + 333
    # The poster call's 0.02 blocks a read's 0.02 reservation under a 0.03 cap.
    env.setenv("SPEND_CAP_USD", "0.03")
    result, requests = ask(engine, load_settings(env_file=None), reply())
    assert (result.code, result.status, requests, len(rows(engine))) == ("budget_exhausted", 429, [], 2)


def test_a_shop_with_no_credit_still_reads_its_messages(bare_engine, claude):
    """R-BALANCE-007: reading a message costs no credit; only the three image routes look at credits (D-BALANCE-004)."""
    result, requests = ask(bare_engine, claude, reply())
    assert not isinstance(result, Refused) and len(requests) == 1


@pytest.mark.parametrize("funded", [False, True])
def test_a_shop_reads_a_hundred_messages_a_day_whatever_its_credits(bare_engine, claude, funded):
    """R-BALANCE-007: one flat limit of 100 reads a day per shop, at zero credits or with some (D-BALANCE-004)."""
    if funded:
        credited(bare_engine)
    with write_tx(bare_engine) as conn:
        conn.exec_driver_sql(
            "INSERT INTO chat_reads (id,shop_id,key,payload_sha,status,provider,model,rate_card_json,cost_micros,"
            "cost_is_estimate,created_at) VALUES (?,1,?,'sha','succeeded','claude','m','{}',0,1,?)",
            [(str(uuid4()), str(uuid4()), utc_now()) for _ in range(99)])
    result, requests = ask(bare_engine, claude, reply())  # the 100th
    assert result["card"]["kind"] == "ask_product" and len(requests) == 1
    result, requests = ask(bare_engine, claude, reply())  # the 101st
    assert (result.code, result.status, requests, len(rows(bare_engine))) == ("read_limit", 429, [], 100)


def test_the_services_pause_stops_a_read_and_resume_lifts_it(engine, claude):
    """D-BALANCE-003: reading a message is a new request to the AI, so the operator's pause refuses it with the cap's
    code and sentence, before anything is reserved or sent."""
    with write_tx(engine) as conn:
        shops.pause(conn)
    result, requests = ask(engine, claude, reply())
    assert (result.code, result.status, requests, rows(engine)) == ("budget_exhausted", 429, [], [])
    assert "lecture des messages" in MESSAGES["budget_exhausted"]
    with write_tx(engine) as conn:
        shops.resume(conn)
    result, requests = ask(engine, claude, reply())
    assert result["card"]["kind"] == "ask_product" and len(requests) == 1


def test_an_unaccepted_shop_gets_no_new_read_and_is_told_before_the_read_limits(engine, claude, monkeypatch):
    """D-TERMS-003: a new read of a shop that has not accepted the current conditions is refused before any row or
    reservation, and nothing is sent; it is told before the day's read limit and before its reads in progress, which
    the same read meets once accepted. A read admitted before is still answered from its row, free."""
    admitted = str(uuid4())
    first, sent = ask(engine, claude, reply(), key=admitted)
    assert len(sent) == 1
    unaccepted(engine)

    def told(limit):
        before = rows(engine)
        result, sent = ask(engine, claude, reply())
        assert (result.code, result.status, sent, rows(engine)) == ("terms_required", 403, [], before)
        accepted(engine)
        result, sent = ask(engine, claude, reply())
        assert (getattr(result, "code", result), sent, rows(engine)) == (limit, [], before)
        unaccepted(engine)

    again, sent = ask(engine, claude, reply(), key=admitted)
    assert again == first and sent == [] and len(rows(engine)) == 1
    monkeypatch.setattr(reads, "DAILY_LIMIT", 1)  # the read above is today's one
    told("read_limit")
    monkeypatch.setattr(reads, "DAILY_LIMIT", 10)
    for _ in range(2):
        insert(engine, utc_now(), "running", ESTIMATE)
    told("reads_busy")


@pytest.mark.parametrize("key",["not-a-uuid", "-" * 36, "A" * 8 + "-0000-0000-0000-" + "0" * 12, uuid4().hex])
def test_invalid_key_makes_no_call_and_no_reservation(engine, claude, key):
    result, requests = ask(engine, claude, reply(), key=key)
    assert (result.code, result.status, requests, rows(engine)) == ("invalid_idempotency_key", 422, [], [])


def test_creation_must_be_the_shops_and_active(engine, claude, tmp_path, input_id):
    creation = draft(engine, tmp_path, input_id)
    request = reads.ReadRequest(**body("Un fond plus chaud", creation["id"]))
    read = lambda shop: asyncio.run(reads.read(engine, claude, shop, str(uuid4()), request, MESSAGES,  # noqa: E731
                                               transport=httpx2.MockTransport(lambda _request: pytest.fail("called"))))
    with pytest.raises(Refused) as refused:
        read(2)  # shop 2 does not even exist here: only the ownership filter is shown
    assert (refused.value.code, refused.value.status) == ("not_found", 404)
    store.abandon_creation(engine, 1, str(uuid4()), creation["id"], 1)
    with pytest.raises(Refused) as refused:
        read(1)
    assert (refused.value.code, refused.value.status, rows(engine)) == ("creation_abandoned", 409, [])


def test_a_key_is_the_shops_own(engine, claude):
    with write_tx(engine) as conn:
        conn.exec_driver_sql("INSERT INTO shop_profile (revision,updated_at,identifier,state,created_at) "
                             "VALUES (1,'now','shopdeux','active','now')")
    accepted(engine, 2)
    key = str(uuid4())
    first, sent = ask(engine, claude, reply(), key=key)
    assert len(sent) == 1
    # Shop 2 with shop 1's key and another message: a new read of its own, never shop 1's answer nor a refusal.
    other, sent = ask(engine, claude, reply({"product_name": "Galaxy A55"}), text="Galaxy A55", key=key, shop=2)
    assert len(sent) == 1 and other["draft"]["name"] == "Galaxy A55" != first["draft"]["name"]
    assert sorted((row["shop_id"], row["key"]) for row in rows(engine)) == [(1, key), (2, key)]
    again, sent = ask(engine, claude, reply(), key=key)  # shop 1's own key still replays, free
    assert again == first and sent == []
    reused, sent = ask(engine, claude, reply(), text="Galaxy A55", key=key)
    assert (reused.code, sent) == ("idempotency_reused", [])


def test_photos_already_used_are_offered_for_the_same_product(stub, client, monkeypatch):
    login(client)
    engine = client.app.state.engine

    def used(name, colour):
        upload = client.post("/api/assets", files={"file": ("p.png", photo(colour=colour), "image/png")}, data={"role": "original"})
        source = post(client, "/api/product-inputs", {"name": name, "variant": "-", "photo_assets": [upload.json()["asset"]]})
        assert source.status_code == 201, source.text
        return upload.json()["asset"], source.json()["id"]

    def ask(message, **draft):
        answer = post(client, "/api/reads", body(message, **{"product_photos": 0} | draft))
        assert answer.status_code == 201, answer.text
        return answer.json()["card"]

    assert ask("Casque Été, 700 000 Ar") == {"kind": "ask_photo", "text_fr": MESSAGES["card_ask_photo"]}  # nothing used yet
    first, input_id = used("Casque Été", "navy")
    used("Autre produit", "red")
    # The same name, case and accents ignored; another product's photo is not offered.
    assert ask("casque ete, 700 000 Ar")["suggestions"] == [{"asset": first, "name": "Casque Été"}]
    assert "suggestions" not in ask("Casque Hiver, 700 000 Ar")
    assert "suggestions" not in ask("Casque Été, 700 000 Ar", product_photos=1)  # a photo is there: the recap
    # A removed poster's photo is still the shop's.
    creation = post(client, "/api/creations", {"input_id": input_id, "offer": {"title": "Casque Été", "price_ar": 700000},
                                               "brand_selection": {"logo": False, "shop_name": False, "contact": False}}).json()
    store.abandon_creation(engine, 1, str(uuid4()), creation["id"], creation["revision"])
    assert ask("CASQUE ÉTÉ 700 000 Ar")["suggestions"] == [{"asset": first, "name": "Casque Été"}]
    # Three at most, newest first.
    newer = [used("casque été", colour)[0] for colour in ("green", "gold", "purple")]
    assert [item["asset"] for item in ask("Casque Été, 700 000 Ar")["suggestions"]] == newer[::-1]
    # Only what the shop may read.
    with write_tx(engine) as conn:
        conn.execute(text("DELETE FROM asset_access WHERE asset_sha=:sha"), {"sha": newer[2]})
    assert [item["asset"] for item in ask("Casque Été, 700 000 Ar")["suggestions"]] == [newer[1], newer[0], first]
    # A failed lookup costs the owner nothing: the card comes without suggestions and the read is kept.
    monkeypatch.setattr(reads, "suggestions", lambda *_: 1 / 0)
    assert ask("Casque Été, 700 000 Ar") == {"kind": "ask_photo", "text_fr": MESSAGES["card_ask_photo"]}
    assert all(row["status"] == "succeeded" for row in rows(engine))


# D-TEXT-FIRST-005: a change on a poster is a set of the editor's fields, checked against the words the server reads.
CREATION, VISUAL = str(uuid4()), str(uuid4())
DRAWN = {"title": "Sony WH-CH720N", "brand": None, "subtitle": None}  # drawn words, the price laid over the image


def words(image=None, title="Sony WH-CH720N", price_ar=450000, accent=None, model_image=False, adjusted=False, lines=()):
    """The poster words of reads.poster_words: the image's (empty: no drawn words) and the document's."""
    return {"visual_id": VISUAL, "accent_word": accent, "model_image": model_image, "adjusted": adjusted,
            "lines": list(lines), "image": dict(image or {}),
            "document": {"title": title, "price_ar": price_ar}}


def change(message, poster, profile=(), **fields):
    """The card of a poster's read; `profile`: the shop's lines (D-KIT-005)."""
    fields = {row.name: None for row in reads.FIELDS} | {"remove": [], "format": None, "identity": None,
                                                         "commercial": False, "shop_lines": [], "advert": True} | fields
    request = reads.ReadRequest(**body(message, CREATION, visual_id=VISUAL))
    return reads.build(reads.poster_fields()(**fields), request, MESSAGES, poster, list(profile))["card"]


def scene(text_fr, **words):
    """A new image from changed words: its cost is said after what changes (D-KIT-007)."""
    return {"kind": "change", "text_fr": f"{text_fr}\n{MESSAGES['card_redraw']}", "visual_id": VISUAL,
            "effect": "scene", "words": words}


def refused(code, *values):
    return {"kind": "refused", "text_fr": MESSAGES[code].format(*values)}


SAME = {"kind": "same", "text_fr": "L’affiche a déjà ces textes."}
REDRAW = MESSAGES["card_redraw"]
STEPS = {"kind": "steps", "text_fr": MESSAGES["card_steps"]}


def refine(message):
    return {"kind": "change", "text_fr": f"Scène : « {message} »", "visual_id": VISUAL, "effect": "refine",
            "instruction_fr": message}


def test_the_owners_own_message_is_the_scene_adjustment():
    """ADR-102: on a poster, a message that changes no word goes whole to the scene adjustment, as typed in « Réglages »."""
    apart = words(DRAWN | {"title": "WH-CH720N", "brand": "Sony"}, title="WH-CH720N")
    # The user's report: the reader hears "brand: Sony", which the poster has; the message still asks for a drawing.
    assert change("Use sony logo", apart, brand="Sony") == refine("Use sony logo")
    assert change("Use sony logo", apart, instruction_fr="utiliser le logo Sony") == refine("Use sony logo")
    # A list of features with icons: his words, not the reader's. A feature the reader adds is not sent.
    features = "ajoute à droite des icônes : réduction de bruit, autonomie longue durée, Bluetooth 5.2"
    card = change(features, apart, instruction_fr="ajouter des icônes : réduction de bruit, garantie 2 ans, Wi-Fi 7")
    assert card == refine(features) and "Wi-Fi" not in json.dumps(card)
    # Also on a version without drawn words, and with no word at all in the reader's answer but the signal.
    assert change("agrandis le produit", words(), instruction_fr="produit plus grand") == refine("agrandis le produit")
    # Words that do change keep their own path; the scene is asked after.
    both = change("mets Samsung en marque et un logo plus grand", apart, brand="Samsung", instruction_fr="logo plus grand")
    assert both["effect"] == "scene" and both["text_fr"].endswith(MESSAGES["card_words_first"])
    # A promotion or a price in the message: refused when the message is about the picture, never sent.
    assert change("ajoute un badge promo -50%", apart, instruction_fr="badge") == refused("card_refused")
    # Nothing asked of the words or of the picture: the sentence of what can be changed.
    assert change("merci", apart)["kind"] == "unclear"
    # The reader's judgement is the second screen (ADR-102): a wording the list of phrasings does not know is refused
    # when the reader says it asks for an offer. It only refuses: it cannot let through what the list refuses.
    offer = "ajoute la mention deux pour le tarif d'un"
    assert change(offer, apart, instruction_fr="mention") == refine(offer)  # the list alone does not see it
    assert change(offer, apart, instruction_fr="mention", commercial=True) == refused("card_refused")
    assert change("ajoute un badge promo -50%", apart, instruction_fr="badge", commercial=False) == refused("card_refused")
    # It does not stop a change of the words: a new price given in its field is not an offer in the picture.
    assert change("le prix c'est 420 000 Ar", apart, price_ar=420000, commercial=True)["words"]["price_ar"] == 420000
    # A new price and an offer in one message: the price change alone, the scene to ask after; the offer is not sent.
    mixed = change("prix 420 000 Ar et ajoute promo", apart, price_ar=420000, instruction_fr="promo", commercial=True)
    assert mixed["effect"] == "free" and mixed["words"] == {"price_ar": 420000}  # the price is a layer on this poster
    assert "instruction_fr" not in mixed and mixed["text_fr"].endswith(MESSAGES["card_words_first"])
    # An answer without the judgement, or with something else than true or false, is not read as "false".
    answer = {row.name: None for row in reads.FIELDS} | {"remove": [], "format": None, "identity": None}
    for bad in (answer, answer | {"commercial": None}, answer | {"commercial": "false"}, answer | {"commercial": 0}):
        with pytest.raises(ValueError):
            reads.poster_fields().model_validate_json(json.dumps(bad))
    # A price already there, judged commercial: the plain answer, nothing offered.
    assert change("le prix est 450 000 Ar", apart, price_ar=450000, commercial=True) == SAME


def test_the_field_table_drives_the_schema_the_card_and_the_sentence(monkeypatch):
    schema = wire_schema(reads.poster_fields())
    assert schema["required"] == ["title", "brand", "subtitle", "price_ar", "instruction_fr", "style", "remove",
                                  "format", "identity", "commercial", "shop_lines", "advert"]
    assert schema["properties"]["style"]["anyOf"][0]["enum"] == ["clair", "couleur", "sombre"]
    assert schema["properties"]["remove"]["items"]["enum"] == ["brand", "subtitle"]
    assert all(schema["properties"][row.name]["description"] == row.rule for row in reads.FIELDS)
    assert change("Merci", words(DRAWN))["text_fr"] == ("Dites ce qu’il faut changer : le titre, la marque, le "
                                                        "sous-titre, le prix, l’image (fond, lumière, logo, caractéristiques, "
                                                        "mise en scène), le style. Le reste se change dans Pas à pas.")
    # One row added: it is in the model's schema, in the sentence and on the card.
    monkeypatch.setattr(reads, "FIELDS", (*reads.FIELDS, reads.Row(
        "accent_word", str, "The word of the title in colour.", "le mot en couleur", "Mot en couleur", reads._headline_text)))
    assert wire_schema(reads.poster_fields())["properties"]["accent_word"]["description"] == "The word of the title in colour."
    assert "mise en scène), le style, le mot en couleur. Le reste" in change("Merci", words(DRAWN))["text_fr"]
    card = change("mets WH en couleur", words(DRAWN | {"accent_word": "Sony"}), accent_word="WH")
    assert card == scene("Mot en couleur : WH", title="Sony WH-CH720N", brand=None, subtitle=None, price_ar=450000,
                         accent_word="WH")


def test_the_report_message_sets_the_brand_apart():
    message = "Sony c’est la marque, mets-la en haut, et le titre du produit en deuxième ligne"
    expected = scene("Titre : WH-CH720N\nMarque : Sony", title="WH-CH720N", brand="Sony", subtitle=None, price_ar=450000)
    assert change(message, words(DRAWN), brand="Sony", title="WH-CH720N") == expected
    assert change(message, words(DRAWN), brand="Sony") == expected  # the title is cut by the server all the same
    # A brand already stored and inside the title, asked again: taking it out of the title is the change.
    assert change("mets Sony en haut", words(DRAWN | {"brand": "Sony"}), brand="Sony") == scene(
        "Titre : WH-CH720N", title="WH-CH720N", brand="Sony", subtitle=None, price_ar=450000)
    assert change("mets Sony en haut", words(DRAWN | {"title": "WH-CH720N", "brand": "Sony"}, title="WH-CH720N"),
                  brand="Sony") == refine("mets Sony en haut")  # no word changes: his message adjusts the scene
    # Nothing left of the title, or the brand only inside a token: the owner writes the title.
    assert change("Sony en marque", words(DRAWN | {"title": "Sony"}, title="Sony"), brand="Sony") == refused("card_title_without_brand")
    assert change("Sony en marque", words(DRAWN | {"title": "Sony-WH CH720N"}, title="Sony-WH CH720N"), brand="Sony") == refused(
        "card_title_without_brand")


@pytest.mark.parametrize(("title", "brand", "rest"), [
    ("Sony WH-CH720N", "Sony", "WH-CH720N"), ("sony WH-CH720N", "SONY", "WH-CH720N"),
    ("Sony - WH-CH720N", "Sony", "WH-CH720N"), ("Sony : WH-CH720N", "Sony", "WH-CH720N"),
    ("WH-CH720N | Sony", "Sony", "WH-CH720N"), ("WH-CH720N (Sony)", "Sony", "WH-CH720N"),
    ("WH-CH720N ( Sony )", "Sony", "WH-CH720N"), ("WH-CH720N [ Sony ]", "Sony", "WH-CH720N"),
    ("Casque Sony WH-CH720N", "Sony", "Casque WH-CH720N"), ("Écouteurs Été · Sony,", "Sony", "Écouteurs Été"),
    ("Samsung Galaxy A55", "Samsung Galaxy", "A55"), ("JBL Flip 7", "Sony", "JBL Flip 7"),
    ("Sony WH Sony", "Sony", "WH"), ("Sony", "Sony", None), ("Sony - ()", "Sony", None), ("Sony-WH", "Sony", None),
])
def test_brand_set_apart_token_rule_and_separators(title, brand, rest):
    assert reads._set_apart(brand, title) == rest


def test_the_coloured_word_that_leaves_the_title_is_said():
    card = change("mets Sony en haut", words(DRAWN | {"accent_word": "Sony"}, accent="Sony"), brand="Sony")
    assert card["text_fr"] == f"Titre : WH-CH720N\nMarque : Sony\nLe mot en couleur est retiré.\n{REDRAW}"
    card = change("mets Sony en haut", words(DRAWN | {"accent_word": "WH"}, accent="WH"), brand="Sony")
    assert card["text_fr"] == f"Titre : WH-CH720N\nMarque : Sony\n{REDRAW}"


def test_words_first_drop_the_instruction():
    # The instruction holds « titre », which the refinement screen refuses: dropped before it is screened.
    card = change("marque Sony, et mets le titre sur un fond sombre", words(DRAWN), brand="Sony",
                  instruction_fr="mets le titre sur un fond sombre")
    assert card == scene("Titre : WH-CH720N\nMarque : Sony", title="WH-CH720N", brand="Sony", subtitle=None,
                         price_ar=450000) | {"text_fr": f"Titre : WH-CH720N\nMarque : Sony\n{REDRAW}\n"
                                                        + MESSAGES["card_words_first"]}
    assert change("un fond sombre", words(DRAWN), instruction_fr=" un fond sombre ") == {
        "kind": "change", "text_fr": "Scène : « un fond sombre »", "visual_id": VISUAL, "effect": "refine",
        "instruction_fr": "un fond sombre"}
    assert change("mets le titre sur un fond", words(DRAWN), instruction_fr="x") == refine("mets le titre sur un fond")
    assert change("mets le prix en rouge", words(DRAWN), instruction_fr="x") == refused("card_refused")
    assert change("fond", words(DRAWN), instruction_fr="x" * 501) == refine("fond")  # the reader's text is never sent
    assert change("fond", words(DRAWN), instruction_fr="  ", title="")["kind"] == "unclear"  # blank is no answer


def test_the_checks_run_in_the_designs_order():
    # On a version without drawn words, a brand is not offered, whatever else is wrong with the message.
    assert change("marque Sony, fond sombre", words(), brand="Sony", instruction_fr="fond sombre") == STEPS
    assert change("Sony", words(title="Sony"), brand="Sony") == STEPS
    # The brand is set apart before the title's own check, which sees the shorter title.
    long = "Sony " + "x" * 58
    assert change(long, words(DRAWN | {"title": long}, title=long), brand="Sony")["words"]["title"] == "x" * 58
    # The field's own rule before the word guard: a warranty nobody wrote is refused by the rule's sentence.
    for message in ("mets un sous-titre", "sous-titre garantie 2 ans"):
        assert change(message, words(DRAWN), subtitle="garantie 2 ans") == refused("validation_error")
    # A change is whole or not offered: one refused field refuses the whole card.
    # A misread price names the amount read, never « Je ne vois pas de prix » (T-KIT-016).
    assert change("marque Sony, 650 000 Ar", words(DRAWN), brand="Sony", price_ar=700000) == refused(
        "card_ask_price_one", reads.format_price(650000))
    assert change("marque Sony, mets 1 200k", words(DRAWN), brand="Sony", price_ar=650000) == refused(
        "card_ask_price_which", f"{reads.format_price(1200000)} ou {reads.format_price(200000)}")


def test_the_word_guard_names_the_word_nobody_wrote():
    assert change("ajoute le sous-titre casque", words(DRAWN), subtitle="Casque Bluetooth") == refused(
        "card_word_unknown", "bluetooth")
    assert MESSAGES["card_word_unknown"].format("Bluetooth") == (
        "Je ne peux pas écrire « Bluetooth » : ce mot n’est ni dans votre message ni sur l’affiche.")
    # Case and accents ignored; a word of the current title, brand or subtitle, or of the document's title, passes.
    assert change("sous-titre ÉCOUTEURS ete", words(DRAWN), subtitle="Écouteurs Été")["effect"] == "scene"
    assert change("mets la marque en haut", words(DRAWN), brand="Sony")["words"]["brand"] == "Sony"
    assert change("le titre en haut", words(DRAWN | {"subtitle": "Casque"}, title="WH bleu"), title="Casque WH bleu")[
        "effect"] == "scene"
    # Documented limit: a wrong arrangement of the owner's own words passes; the card shows the text whole.
    card = change("sous-titre RAM 8 Go, stockage 128 Go", words(DRAWN), subtitle="RAM 128 Go")
    assert card["text_fr"] == f"Sous-titre : RAM 128 Go\n{REDRAW}"


def test_remove_and_same():
    stored = words({"title": "WH-CH720N", "brand": "Sony", "subtitle": "Casque"}, title="WH-CH720N")
    assert change("sans sous-titre", stored, remove=["subtitle"]) == scene(
        "Sous-titre : retiré", title="WH-CH720N", brand="Sony", subtitle=None, price_ar=450000)
    assert change("sans marque ni sous-titre", stored, remove=["brand", "subtitle"])["text_fr"] == (
        f"Marque : retiré\nSous-titre : retiré\n{REDRAW}")
    # No brand to take off among the words: the message goes to the scene (a mark drawn on the image, perhaps).
    assert change("enlève la marque", words(DRAWN), remove=["brand"]) == refine("enlève la marque")
    # A price already there: nothing for the words, and a price is never a scene adjustment.
    assert change("le prix est 450 000 Ar", words(DRAWN), price_ar=450000) == SAME
    assert change("le prix est 450 000 Ar", words(), price_ar=450000) == SAME
    assert change("450000", words(DRAWN), price_ar=450000) == SAME  # a bare amount is a price too, never an adjustment
    assert change("sans marque", words(), remove=["brand"]) == STEPS
    assert change("sans sous-titre", words(), remove=["subtitle"]) == STEPS


def test_the_effect_of_each_field():
    drawn_price = words(DRAWN | {"price_ar": 450000})
    free = lambda text_fr, **words: {"kind": "change", "text_fr": text_fr, "visual_id": VISUAL,  # noqa: E731
                                     "effect": "free", "words": words}
    # A drawn title or price: a new image, with the four words whole.
    assert change("titre WH-CH720N noir", words(DRAWN), title="WH-CH720N noir") == scene(
        "Titre : WH-CH720N noir", title="WH-CH720N noir", brand=None, subtitle=None, price_ar=450000)
    assert change("650 000 Ar", drawn_price, price_ar=650000) == scene(
        "Prix : 650 000 Ar", title="Sony WH-CH720N", brand=None, subtitle=None, price_ar=650000)
    # A price laid over the image: free, the image is kept.
    assert change("650 000 Ar", words(DRAWN), price_ar=650000) == free("Prix : 650 000 Ar", price_ar=650000)
    # A version without drawn words: title and price are layers, free.
    assert change("titre Casque WH", words(), title="Casque WH") == free("Titre : Casque WH", title="Casque WH")
    assert change("650 000 Ar", words(), price_ar=650000) == free("Prix : 650 000 Ar", price_ar=650000)
    assert change("sous-titre Casque", words(), subtitle="Casque") == STEPS
    # A drawn brand and a layer price in one message: one card, one image, the new price with it.
    assert change("marque Sony, 650 000 Ar", words(DRAWN), brand="Sony", price_ar=650000) == scene(
        "Titre : WH-CH720N\nMarque : Sony\nPrix : 650 000 Ar", title="WH-CH720N", brand="Sony", subtitle=None,
        price_ar=650000)


def test_going_back_to_the_images_words_is_free():
    edited = words(DRAWN | {"price_ar": 450000}, price_ar=500000)
    assert change("remets 450 000 Ar", edited, price_ar=450000) == {
        "kind": "change", "text_fr": "Prix : 450\u202f000 Ar", "visual_id": VISUAL, "effect": "free",
        "words": {"price_ar": 450000}}
    retitled = words(DRAWN | {"price_ar": 450000}, title="Sony WH-CH720N bleu")
    assert change("remets Sony WH-CH720N", retitled, title="Sony WH-CH720N")["words"] == {"title": "Sony WH-CH720N"}
    # The document's title is the owner's latest word: a price put back beside a title edited and never drawn is a
    # whole new image with that title, and the card says the title line (as \u00ab Nouvelle version \u00bb would draw it).
    both = words(DRAWN | {"price_ar": 450000}, title="Sony WH-CH720N bleu", price_ar=500000)
    card = change("remets 450 000 Ar", both, price_ar=450000)
    assert (card["effect"], card["text_fr"]) == ("scene", f"Titre : Sony WH-CH720N bleu\n{REDRAW}")
    assert card["words"]["price_ar"] == 450000
    # A new price beside that edited title: both lines, one image.
    assert change("mets 480 000 Ar", both, price_ar=480000)["text_fr"] == (
        f"Titre : Sony WH-CH720N bleu\nPrix : 480\u202f000 Ar\n{REDRAW}")


@pytest.mark.parametrize(("message", "amounts"), [
    # T-CHAT-PRICE-NO-COMMA: a number of the name stands right before the price, with no comma. The whole run of
    # digits is not one amount; its ending of two groups or more is.
    ("iPhone 15 1 200 000 Ar", [1200000, 200000]), ("Galaxy S24 256 1 450 000 Ar", [1450000, 450000]),
    ("Tecno 20 20 000 Ar", [20000]), ("A55 5 1 000 Ar", [1000]), ("Note 13 5 700 000 Ar", [5700000, 700000]),
    # Still nothing: a lone last group is a piece of a badly written amount.
    ("Prix 1234 567 Ar", []), ("x 1 2 3 Ar", []), ("700 00 Ar", []), ("20 00 000 Ar", []),
    # D-KIT-002: without a unit, the same span rules from 10 000.
    ("15 1 200 000", [1200000, 200000]),
    # Unchanged: a whole run that is one amount, with its endings.
    ("Redmi Note 13 700 000 Ar", [13700000, 700000]),
])
def test_a_price_after_a_number_of_the_name_without_a_comma(message, amounts):
    assert reads.candidate_amounts(message) == amounts


def test_code_review_r1_regressions():
    # The guard reads both sides alike: circled letters are a word nobody wrote; a decomposed accent is the same word.
    assert change("ajoute le sous-titre", words(DRAWN), subtitle="ⓑⓛⓤⓔⓣⓞⓞⓣⓗ")["kind"] == "refused"
    assert change("sous-titre écouteurs", words(DRAWN), subtitle="e\u0301couteurs")["effect"] == "scene"
    # A bracket that would lose its other half: the owner writes the title.
    bracketed = words(DRAWN | {"title": "(Sony WH-CH720N)"}, title="(Sony WH-CH720N)")
    assert change("Sony en marque", bracketed, brand="Sony") == refused("card_title_without_brand")
    # A kept brand and a new title that holds it: the title is cut, or the scene route would drop the brand.
    apart = words(DRAWN | {"title": "WH-CH720N", "brand": "Sony"}, title="WH-CH720N")
    assert change("titre Sony WH-CH720N noir", apart, title="Sony WH-CH720N noir")["words"] == {
        "title": "WH-CH720N noir", "brand": "Sony", "subtitle": None, "price_ar": 450000}
    # A document title too long to draw, beside a price request: refused here, not at the paid request.
    long = "Sony WH-CH720N " + "x" * 50
    stale = words(DRAWN | {"price_ar": 450000}, title=long)
    assert change("650 000 Ar", stale, price_ar=650000) == refused("title_too_long")


def test_code_review_r2_probes():
    # A price alone leaves the title and a brand set apart as they are.
    apart = words(DRAWN | {"title": "WH-CH720N", "brand": "Sony"}, title="WH-CH720N", price_ar=450000)
    assert change("500 000 Ar", apart, price_ar=500000) == {
        "kind": "change", "text_fr": "Prix : 500\u202f000 Ar", "visual_id": VISUAL, "effect": "free",
        "words": {"price_ar": 500000}}
    # The guard: other digits, another model number, one word glued from two known ones.
    for message, subtitle in (("sous-titre 128 Go", "256 Go"), ("sous-titre WH-CH720N", "WH-CH520N"),
                              ("sous-titre blue tooth", "bluetooth")):
        assert change(message, words(DRAWN), subtitle=subtitle)["kind"] == "refused"


def test_a_style_change_is_its_own_card():
    """D-TEXT-FIRST-006: another style is a whole new image on a fresh plan; the card says what is not carried."""
    kept = {"title": "Sony WH-CH720N", "brand": None, "subtitle": None, "price_ar": 450000}

    def restyle(text_fr, style="sombre", **words):
        return {"kind": "restyle", "text_fr": text_fr, "visual_id": VISUAL, "style": style, "words": kept | words}

    assert change("mets le style luxe sombre", words(DRAWN), style="sombre") == restyle("Style : Luxe sombre")
    assert change("studio clair", words(DRAWN), style="clair") == restyle("Style : Studio clair", "clair")
    assert change("aux couleurs du produit", words(DRAWN), style="couleur")["text_fr"] == "Style : Couleurs du produit"
    # What the fresh plan does not carry, each said only when the version has it.
    assert change("luxe sombre", words(DRAWN, model_image=True), style="sombre")["text_fr"] == (
        "Style : Luxe sombre\nL’affiche modèle n’est plus suivie.")
    assert change("luxe sombre", words(DRAWN, model_image=True, adjusted=True), style="sombre")["text_fr"] == (
        "Style : Luxe sombre\nL’affiche modèle n’est plus suivie.\nLes ajustements de scène demandés avant ne sont pas "
        "repris.")
    # A word change in the same message: in the words, with its line, through its own checks.
    both = change("Sony c’est la marque, en luxe sombre", words(DRAWN, adjusted=True), brand="Sony", style="sombre")
    assert both == restyle("Style : Luxe sombre\nTitre : WH-CH720N\nMarque : Sony\nLes ajustements de scène demandés "
                           "avant ne sont pas repris.", title="WH-CH720N", brand="Sony")
    assert change("luxe sombre, marque Bose", words(DRAWN), brand="Samsung", style="sombre") == refused(
        "card_word_unknown", "samsung")
    assert change("luxe sombre à 300 000 Ar", words(DRAWN), price_ar=350000, style="sombre") == refused(
        "card_ask_price_one", reads.format_price(300000))
    # A scene adjustment in the same message is asked after, as with a word change.
    assert change("luxe sombre avec un fond bleu", words(DRAWN), style="sombre", instruction_fr="fond bleu") == restyle(
        "Style : Luxe sombre\n" + MESSAGES["card_words_first"])
    # The document's words that the image does not show yet are drawn too, as on a scene card.
    assert change("luxe sombre", words(DRAWN, title="Sony WH-CH720N noir"), style="sombre") == restyle(
        "Style : Luxe sombre\nTitre : Sony WH-CH720N noir", title="Sony WH-CH720N noir")
    # A version without drawn words: the editor's matter, with or without a word asked.
    steps = {"kind": "steps", "text_fr": MESSAGES["card_steps_style"]}
    assert change("luxe sombre", words(), style="sombre") == steps
    assert change("luxe sombre, marque Sony", words(), style="sombre", brand="Sony") == steps


def test_format_and_identity_are_one_sentence_to_the_steps():
    """D-TEXT-FIRST-006: alone, whatever else the reader found; the format first, then the shop's identity, then the style."""
    form = {"kind": "steps", "text_fr": "Un autre format est une nouvelle affiche : dans Pas à pas, « Style », « Refaire en … »."}
    shop = {"kind": "steps", "text_fr": "Le logo et le contact de la boutique se règlent dans Pas à pas, « Boutique »."}
    everything = {"style": "sombre", "brand": "Sony", "instruction_fr": "logo", "price_ar": 1}
    for poster in (words(DRAWN), words()):
        assert change("en story", poster, format=True) == form
        assert change("en story avec le logo de la boutique Sony", poster, format=True, identity=True, **everything) == form
        assert change("mets le logo de la boutique Sony", poster, identity=True, **everything) == shop
        assert change("enlève le contact de la boutique", poster, identity=False) == shop
    # false is "no other format"; the shop's identity not asked is null.
    assert change("luxe sombre", words(DRAWN), format=False, style="sombre")["kind"] == "restyle"
    assert change("Use sony logo", words(DRAWN), instruction_fr="logo Sony") == refine("Use sony logo")


def test_the_shops_identity_asked_for_a_new_poster_is_in_the_draft():
    def answer(found, **draft):
        fields = reads.Fields(intent="describe", product_name="JBL Flip 7", price_ar=700000, style=None,
                              instruction_fr=None, identity=found)
        return reads.build(fields, reads.ReadRequest(**body("JBL Flip 7, 700 000 Ar", **draft)), MESSAGES)

    plain = answer(None)
    assert "identity" not in plain["draft"] and "identity" not in plain["card"]
    asked = answer(True)
    assert asked["draft"]["identity"] is True and asked["card"] == {
        "kind": "recap", "text_fr": MESSAGES["card_recap"], "name": "JBL Flip 7", "price_ar": 700000, "style": None,
        "identity": True}
    assert answer(None, identity=True)["card"]["identity"] is True  # kept from an earlier message
    # « Sans logo ni contact » is an answer too, not the absence of one: it is kept, and a later message that says
    # nothing of it keeps it.
    for before in ({}, {"identity": True}):
        taken_off = answer(False, **before)
        assert taken_off["draft"]["identity"] is False and taken_off["card"]["identity"] is False
    assert answer(None, identity=False)["card"]["identity"] is False
    assert answer(True, identity=False)["card"]["identity"] is True
    # Asked before the photo: it waits in the draft.
    assert answer(True, product_photos=0) == {"card": {"kind": "ask_photo", "text_fr": MESSAGES["card_ask_photo"]}, "draft": {
        "name": "JBL Flip 7", "price_ar": 700000, "style": None, "product_photos": 0, "inspiration": False, "identity": True}}
    # A body without the field has the hash it had before the field existed (the literal of the visual_id test below);
    # false is the same body, true is another.
    old = {"text": "Mets la marque Sony", "creation_id": "00000000-0000-4000-8000-000000000001",
           "history": [{"role": "app", "text": "Bonjour"}]}
    sha = lambda **draft: reads._sha(reads.canonical(reads.ReadRequest(  # noqa: E731
        **old, draft={"product_photos": 1, "inspiration": False} | draft)))
    assert sha() == sha(identity=None) == "152398624c19856d4be7be49fcfdd2f57b6917181344150f5425f2a0775f8515"
    assert len({sha(), sha(identity=True), sha(identity=False)}) == 3
    # The model sees the draft as it was sent: no new key unless the owner asked.
    assert "identity" not in reads.ReadRequest(**body("JBL")).draft.model_dump()
    assert "identity: true when the owner asks for the shop's logo or contact" in reads.SYSTEM
    assert wire_schema(reads.Fields)["required"] == ["intent", "product_name", "price_ar", "style", "instruction_fr",
                                                     "identity", "shop_lines", "unused", "advert"]


def test_the_title_limit_is_60_when_drawn_and_240_as_a_layer():
    for size, drawn, card in ((61, DRAWN, refused("title_too_long")), (61, {}, "free"), (240, {}, "free"),
                              (241, {}, refused("card_title_too_long"))):
        result = change(f"titre {'x' * size}", words(drawn), title="x" * size)
        assert (result["effect"] if card == "free" else result) == card
    assert change('titre TV 32"', words(DRAWN), title='TV 32"') == refused("title_unsupported")
    assert change("titre JBL promo", words(DRAWN), title="JBL promo") == refused("title_commercial_text")


@pytest.fixture
def poster(stub, engine, settings, input_id):
    """A poster with one version that draws its title, brand JBL and price (the stub image provider)."""
    creation = draft(engine, settings.data_dir, input_id)
    visuals.request_scene(engine, settings, 1, key(), creation["id"], creation["revision"], visuals.SceneRequest(
        plan_id=fixed(engine, settings, creation)["id"], acknowledged_warnings=["low_resolution"],
        headline=Headline(brand="JBL", price=True)))
    return creation["id"], execute(engine, settings)


def test_a_new_scene_keeps_the_adjustments_asked_by_message(poster, engine, settings):
    """ADR-101: a refinement's instruction is carried into the whole new scene that replaces its version, and on."""
    creation_id, first = poster
    def scene(**more):
        creation = store.get_creation(engine.connect(), 1, creation_id)
        visuals.request_scene(engine, settings, 1, key(), creation_id, creation["revision"], visuals.SceneRequest(
            plan_id=fixed(engine, settings, creation)["id"], acknowledged_warnings=["low_resolution"],
            headline=Headline(brand="JBL", price=True), **more))
        return execute(engine, settings)
    def payload(visual):
        with engine.connect() as conn:
            return json.loads(conn.execute(text("SELECT input_json FROM poster_jobs WHERE id=(SELECT job_id FROM "
                                                "poster_visuals WHERE id=:id)"), {"id": visual}).scalar_one())
    creation = store.get_creation(engine.connect(), 1, creation_id)
    visuals.request_refinement(engine, settings, 1, key(), creation_id, creation["revision"], visuals.RefinementRequest(
        base_visual_id=first, instruction_fr="fond bleu nuit avec des reflets"))
    refined = execute(engine, settings)
    kept = payload(scene(keep_adjustments_of=refined))
    assert kept["adjustments"] == ["fond bleu nuit avec des reflets"] and kept["replaces_visual_id"] == refined
    with engine.connect() as conn:  # the list of modifications reads it from the version
        newest = visuals.listed_visuals(conn, 1, store.get_creation(conn, 1, creation_id)["document"])[0]
        assert visuals.get_visual(conn, 1, newest)["replaces_visual_id"] == refined
        assert visuals.get_visual(conn, 1, first)["replaces_visual_id"] is None
    assert '"kept_adjustments":["fond bleu nuit avec des reflets"]' in kept["prompt"] and "the kept adjustment wins" in kept["prompt"]
    # Without the field nothing changes; a version of the first scene alone has nothing to keep.
    plain = payload(scene())
    assert "adjustments" not in plain and "kept_adjustments" not in plain["prompt"]
    assert "adjustments" not in payload(scene(keep_adjustments_of=first))
    # The next word change starts from the scene that kept them: they go on.
    with engine.connect() as conn:
        newest = visuals.listed_visuals(conn, 1, store.get_creation(conn, 1, creation_id)["document"])
    carried = next(visual for visual in newest if payload(visual).get("adjustments"))
    assert payload(scene(keep_adjustments_of=carried))["adjustments"] == ["fond bleu nuit avec des reflets"]
    # A version that is not this poster's is refused before anything is queued.
    with pytest.raises(Refused) as refusal:
        scene(keep_adjustments_of=str(uuid4()))
    assert refusal.value.code == "not_found"
    # A refinement says again what its chain was asked before, and that its own adjustment wins (ADR-102 paid test).
    with engine.connect() as conn:
        again = json.loads(conn.execute(text("SELECT input_json FROM poster_jobs WHERE kind='refine' ORDER BY rowid")).scalars().all()[0])
    assert "kept_adjustments" not in again["prompt"]  # the first refinement has nothing before it
    # Two adjustments in the order asked, and the model is told that the later one wins.
    creation = store.get_creation(engine.connect(), 1, creation_id)
    visuals.request_refinement(engine, settings, 1, key(), creation_id, creation["revision"], visuals.RefinementRequest(
        base_visual_id=creation["document"]["formats"]["feed"]["scene"]["visual_id"], instruction_fr="fond rouge"))
    red = payload(scene(keep_adjustments_of=execute(engine, settings)))
    assert red["adjustments"][-1] == "fond rouge" and "the later one wins" in red["prompt"]
    # (That refinement starts from the poster's selected version, the first scene, so it has nothing to say again;
    # a refinement's own prompt with adjustments before it is in test_plans.)
    # A chain too long, or a stored adjustment the screen no longer accepts: refused by name, nothing queued.
    def queued():
        with engine.connect() as conn:
            return conn.execute(text("SELECT COUNT(*) FROM poster_jobs")).scalar_one()
    before = queued()
    for notes, code in ((["fond bleu"] * 13, "adjustments_limit"), (["x" * 500] * 7, "adjustments_limit"),
                        (["fond bleu, promo -50%"], "adjustment_refused")):
        with pytest.MonkeyPatch.context() as patched, pytest.raises(Refused) as refusal:
            patched.setattr(visuals, "kept_adjustments", lambda conn, shop, visual_id, notes=notes: notes)
            scene(keep_adjustments_of=first)
        assert refusal.value.code == code and queued() == before


def test_a_chain_too_long_is_refused_before_the_conditions_are_told(poster, engine, settings):
    """D-TERMS-003, accepted in round 2: adjustments_limit is the scene route's own check, before jobs.enqueue and its
    gate; each refusal queues nothing. Within the limit, the unaccepted shop is told the conditions."""
    creation_id, first = poster
    unaccepted(engine)

    def refused():
        with engine.connect() as conn:
            creation, before = store.get_creation(conn, 1, creation_id), conn.execute(text("SELECT COUNT(*) FROM poster_jobs")).scalar_one()
        with pytest.raises(Refused) as refusal:
            visuals.request_scene(engine, settings, 1, key(), creation_id, creation["revision"], visuals.SceneRequest(
                plan_id=fixed(engine, settings, creation)["id"], acknowledged_warnings=["low_resolution"],
                headline=Headline(brand="JBL", price=True), keep_adjustments_of=first))
        with engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM poster_jobs")).scalar_one() == before
        return refusal.value.code, refusal.value.status

    with pytest.MonkeyPatch.context() as patched:
        patched.setattr(visuals, "kept_adjustments", lambda *_: ["fond bleu"] * 13)
        assert refused() == ("adjustments_limit", 422)
    assert refused() == ("terms_required", 403)


def test_a_refinement_says_again_what_its_chain_was_asked(poster, engine, settings):
    """ADR-102, found by the paid test: an adjustment told the image only its own request, and the next one lost what
    the one before had added. Through the service: the second refinement of a chain carries the first."""
    from affiche.posters.models import Document
    creation_id, first = poster
    def refine(base, instruction):
        with engine.connect() as conn:
            saved = store.get_creation(conn, 1, creation_id)
        document = Document.model_validate(saved["document"])
        if document.formats["feed"].scene.visual_id != base:  # as the chat does: the new version becomes the poster's
            document.formats["feed"].scene.visual_id = base
            saved = store.save_creation(engine, settings.data_dir, 1, key(), creation_id, document, saved["revision"])[1]
        visuals.request_refinement(engine, settings, 1, key(), creation_id, saved["revision"], visuals.RefinementRequest(
            base_visual_id=base, instruction_fr=instruction))
        made = execute(engine, settings)
        with engine.connect() as conn:
            return made, json.loads(conn.execute(text("SELECT input_json FROM poster_jobs WHERE id=(SELECT job_id FROM "
                                                      "poster_visuals WHERE id=:id)"), {"id": made}).scalar_one())["prompt"]
    second, prompt = refine(first, "icônes : réduction de bruit, Bluetooth 5.2")
    assert "kept_adjustments" not in prompt
    _third, prompt = refine(second, "produit plus grand")
    assert '"kept_adjustments":["icônes : réduction de bruit, Bluetooth 5.2"]' in prompt
    assert '"requested_adjustment":"produit plus grand"' in prompt and "the requested adjustment wins over all of them" in prompt


def test_a_copy_inherits_the_adjustments_and_its_chain_is_bounded(poster, engine, settings):
    """ADR-101 across copies (T-CHAT-D005-TESTS): a copy shares its original's versions, so a scene made on the copy
    carries the adjustments asked on the original; the twelve-scenes limit is per poster, the chain's limit is not."""
    original, first = poster
    def latest(id):
        with engine.connect() as conn:
            return store.get_creation(conn, 1, id)
    def refine(id, instruction):
        creation = latest(id)
        visuals.request_refinement(engine, settings, 1, key(), id, creation["revision"], visuals.RefinementRequest(
            base_visual_id=creation["document"]["formats"]["feed"]["scene"]["visual_id"], instruction_fr=instruction))
        return execute(engine, settings)
    def scene(id, keep):
        creation = latest(id)
        visuals.request_scene(engine, settings, 1, key(), id, creation["revision"], visuals.SceneRequest(
            plan_id=fixed(engine, settings, creation)["id"], acknowledged_warnings=["low_resolution"],
            headline=Headline(brand="JBL", price=True), keep_adjustments_of=keep))
        return execute(engine, settings)
    def adjustments(visual):
        with engine.connect() as conn:
            return json.loads(conn.execute(text("SELECT input_json FROM poster_jobs WHERE id=(SELECT job_id FROM "
                                                "poster_visuals WHERE id=:id)"), {"id": visual}).scalar_one()).get("adjustments")
    refined = refine(original, "fond bleu nuit")
    copy = store.copy_creation(engine, settings.data_dir, 1, key(), original, CopyCreation(
        source_revision=latest(original)["revision"], reason="new_campaign"))[1]["id"]
    on_copy = scene(copy, refined)
    assert adjustments(on_copy) == ["fond bleu nuit"]
    # Carried on from the copy's own scene: the next word change on the copy still has them.
    assert adjustments(scene(copy, on_copy)) == ["fond bleu nuit"]
    # Each copy starts a new count of twelve scenes, the chain goes on: at thirteen notes the scene is refused by name.
    with engine.connect() as conn:
        jobs_before = conn.execute(text("SELECT COUNT(*) FROM poster_jobs")).scalar_one()
    with pytest.MonkeyPatch.context() as patched, pytest.raises(Refused) as refusal:
        real = visuals.kept_adjustments
        patched.setattr(visuals, "kept_adjustments", lambda conn, shop, id: real(conn, shop, id) + ["lumière douce"] * 12)
        scene(copy, on_copy)
    with engine.connect() as conn:
        assert refusal.value.code == "adjustments_limit"
        assert conn.execute(text("SELECT COUNT(*) FROM poster_jobs")).scalar_one() == jobs_before


def read(engine, settings, message, creation, visual=None, key=None):
    try:
        return asyncio.run(reads.read(engine, settings, 1, key or str(uuid4()),
                                      reads.ReadRequest(**body(message, creation, visual_id=visual)), MESSAGES))
    except Refused as refused:
        return refused


def test_the_stub_reader_on_a_poster(poster, engine, settings):
    creation, visual = poster
    card = lambda message: read(engine, settings, message, creation, visual)["card"]  # noqa: E731
    stored = {"title": "Une enceinte", "brand": "JBL", "subtitle": None, "price_ar": 899000}
    assert card("marque Sony") == {"kind": "change", "text_fr": f"Marque : Sony\n{REDRAW}", "visual_id": visual,
                                   "effect": "scene", "words": stored | {"brand": "Sony"}}
    assert card("titre Grande enceinte")["words"] == stored | {"title": "Grande enceinte"}
    assert card("sous-titre Son puissant")["words"] == stored | {"subtitle": "Son puissant"}
    assert card("sans marque")["words"] == stored | {"brand": None}
    assert card("sans sous-titre")["effect"] == "refine"  # no subtitle among the words: the scene's business
    assert card("non, 650 000 Ar")["words"] == stored | {"price_ar": 650000}
    assert card("Un fond plus chaud") == {"kind": "change", "text_fr": "Scène : « Un fond plus chaud »",
                                          "visual_id": visual, "effect": "refine", "instruction_fr": "Un fond plus chaud"}
    assert card("Ajoute le texte promo sur le fond") == refused("card_refused")
    for message in ("Change le prix", "Merci", "JBL Flip 8"):
        assert card(message)["kind"] == "unclear"
    # D-TEXT-FIRST-006: the style, and the two sentences to « Pas à pas ».
    assert card("mets le style sombre") == {"kind": "restyle", "text_fr": "Style : Luxe sombre", "visual_id": visual,
                                            "style": "sombre", "words": stored}
    assert (card("Studio clair")["style"], card("style couleur")["style"], card("en luxe sombre")["style"]) == (
        "clair", "couleur", "sombre")
    assert card("luxe sombre, marque Sony") == {
        "kind": "restyle", "text_fr": "Style : Luxe sombre\nMarque : Sony", "visual_id": visual, "style": "sombre",
        "words": stored | {"brand": "Sony"}}
    assert card("Un fond plus sombre")["effect"] == "refine"  # a word of a style alone is the scene's
    assert card("un autre format, style sombre") == {"kind": "steps", "text_fr": MESSAGES["card_format"]}
    for message in ("mets le logo de la boutique", "ajoute le contact de la boutique en style sombre"):
        assert card(message) == {"kind": "steps", "text_fr": MESSAGES["card_identity"]}
    # The two warnings come from the version: its model image, and the adjustments on its chain.
    with engine.connect() as conn:
        document = store.get_creation(conn, 1, creation)["document"]
        found = reads.poster_words(conn, 1, document, visual)
    assert (found["model_image"], found["adjusted"]) == (False, False)
    revision = store.get_creation(engine.connect(), 1, creation)["revision"]
    visuals.request_refinement(engine, settings, 1, key(), creation, revision, visuals.RefinementRequest(
        base_visual_id=visual, instruction_fr="fond bleu nuit"))
    refined = execute(engine, settings)
    assert read(engine, settings, "style clair", creation, refined)["card"]["text_fr"] == (
        "Style : Studio clair\nLes ajustements de scène demandés avant ne sont pas repris.")
    with write_tx(engine) as conn:  # a version made with a model image
        conn.execute(text("UPDATE poster_jobs SET input_json=json_set(input_json,'$.style_reference_asset',:sha) WHERE id="
                          "(SELECT job_id FROM poster_visuals WHERE id=:id)"), {"sha": "a" * 64, "id": visual})
    assert card("style clair")["text_fr"] == "Style : Studio clair\nL’affiche modèle n’est plus suivie."
    assert {row["creation_id"] for row in rows(engine)} == {creation}
    assert all(row["status"] == "succeeded" and row["cost_micros"] == 0 for row in rows(engine))


def test_the_version_must_be_listed_for_this_poster(poster, engine, settings, tmp_path):
    creation, visual = poster
    # A copy shares the versions of its product input at its size.
    with engine.connect() as conn:
        revision = store.get_creation(conn, 1, creation)["revision"]
    copy = store.copy_creation(engine, settings.data_dir, 1, key(), creation, CopyCreation(
        source_revision=revision, reason="new_campaign"))[1]["id"]
    assert read(engine, settings, "marque Sony", copy, visual)["card"]["effect"] == "scene"
    # Another poster's version is not this poster's, even of the same shop.
    other_input = store.create_input(engine, tmp_path, 1, key(), ProductInput(
        name="Sony", variant="Noir", photo_assets=[store.upload(engine, tmp_path, 1, photo(colour="red"), "original")["asset"]]))[1]
    other = draft(engine, tmp_path, other_input["id"])
    visuals.request_scene(engine, settings, 1, key(), other["id"], other["revision"], visuals.SceneRequest(
        plan_id=fixed(engine, settings, other)["id"], acknowledged_warnings=["low_resolution"], headline=Headline()))
    foreign = execute(engine, settings)
    count = len(rows(engine))
    for visual_id in (foreign, str(uuid4())):
        result = read(engine, settings, "marque Sony", creation, visual_id)
        assert (result.code, result.status, len(rows(engine))) == ("not_found", 404, count)
    assert read(engine, settings, "marque Sony", other["id"], foreign)["card"]["words"] == {
        "title": "Une enceinte", "brand": "Sony", "subtitle": None, "price_ar": 899000}


def test_a_body_without_visual_id_keeps_its_hash_and_is_refused_before_any_row(poster, engine, settings):
    old = reads.ReadRequest(text="Mets la marque Sony", creation_id="00000000-0000-4000-8000-000000000001",
                            draft={"product_photos": 1, "inspiration": False}, history=[{"role": "app", "text": "Bonjour"}])
    # The hash this body had before visual_id existed (computed with the code of T-CHAT-005).
    assert reads._sha(reads.canonical(old)) == "152398624c19856d4be7be49fcfdd2f57b6917181344150f5425f2a0775f8515"
    creation, visual = poster
    result = read(engine, settings, "Mets la marque Sony", creation)
    assert (result.code, result.status, rows(engine)) == ("reload_required", 409, [])
    # A key known from before replays its stored answer, old card shape included; a new key is refused.
    known, stored = str(uuid4()), {"card": {"kind": "change", "change": "price", "price_ar": 650000, "text_fr": "…"},
                                   "draft": {"name": None, "price_ar": None, "style": None, "product_photos": 1,
                                             "inspiration": False}}
    with write_tx(engine) as conn:
        conn.exec_driver_sql(
            "INSERT INTO chat_reads (id,shop_id,creation_id,key,payload_sha,status,provider,model,rate_card_json,"
            "cost_micros,cost_is_estimate,response_json,created_at) VALUES (?,1,?,?,?,'succeeded','stub','m','{}',0,0,?,?)",
            (str(uuid4()), creation, known, reads._sha(reads.canonical(reads.ReadRequest(**body("non, 650 000 Ar", creation)))),
             json.dumps(stored), utc_now()))
    assert read(engine, settings, "non, 650 000 Ar", creation, key=known) == stored
    result = read(engine, settings, "non, 650 000 Ar", creation)
    assert (result.code, len(rows(engine))) == ("reload_required", 1)
    assert read(engine, settings, "non, 650 000 Ar", creation, visual)["card"]["effect"] == "scene"


def test_a_poster_read_sends_its_own_prompt_and_the_servers_words(engine, claude, tmp_path, input_id, monkeypatch):
    poster_words = words(DRAWN | {"brand": "Sony"})
    monkeypatch.setattr(reads, "poster_words", lambda *_: poster_words)
    creation = draft(engine, tmp_path, input_id)["id"]  # it must exist and be active; its words are patched above
    answer = {row.name: None for row in reads.FIELDS} | {"remove": ["brand"], "format": None, "identity": None,
                                                         "commercial": False, "shop_lines": [], "advert": True}
    requests = []

    def handle(request):
        requests.append(request)
        return reply(content=[{"type": "text", "text": json.dumps(answer)}])
    result = asyncio.run(reads.read(engine, claude, 1, str(uuid4()), reads.ReadRequest(**body(
        "sans marque", creation, history=[{"role": "app", "text": "Bonjour"}], visual_id=VISUAL)), MESSAGES,
        transport=httpx2.MockTransport(handle)))
    assert result["card"]["words"]["brand"] is None and result["card"]["effect"] == "scene"
    sent = json.loads(requests[0].content)
    assert sent["system"] == reads.POSTER_SYSTEM and sent["output_config"]["format"]["schema"] == wire_schema(reads.poster_fields())
    assert json.loads(sent["messages"][0]["content"][0]["text"]) == {
        "message": "sans marque", "history": [{"role": "app", "text": "Bonjour"}],
        "poster_words": {"title": "Sony WH-CH720N", "brand": "Sony", "subtitle": None, "price_ar": 450000}}
    assert rows(engine)[0]["status"] == "succeeded"


# The seller's kit (T-KIT-003): a new poster's read, from the reader's fields.
GUARD = ("affiche.posters.reads", 30)  # the logger and level of the word guard's drops (counted in T-KIT-010)


def new(message, found=None, profile=(), **draft):
    """A new poster's answer; `found`: what the reader returned; `profile`: the shop's lines (D-KIT-005)."""
    found = {"intent": "describe", "product_name": None, "price_ar": None, "style": None, "instruction_fr": None,
             "identity": None} | (found or {})
    return reads.build(reads.Fields(**found), reads.ReadRequest(**body(message, **draft)), MESSAGES, None, list(profile))


def guarded(caplog):
    return [record.getMessage() for record in caplog.records if (record.name, record.levelno) == GUARD]


def test_the_price_question_names_what_it_read():
    """D-KIT-002: no price set, the card says the amounts read, one button each; never the same question again."""
    ask = lambda message, **found: new(message, {"product_name": "Redmi Note 13"} | found)["card"]  # noqa: E731
    assert ask("Redmi Note 13") == {"kind": "ask_price", "text_fr": MESSAGES["card_ask_price"]}
    assert MESSAGES["card_ask_price"] == ("Je ne vois pas de prix dans votre message. Écrivez-le en chiffres, par "
                                          "exemple 250 000 Ar.")
    assert ask("Redmi Note 13 250000") == {"kind": "ask_price", "text_fr": "Le prix est-il 250 000 Ar ?",
                                           "amounts": [250000]}
    assert ask("Redmi Note 13 700 000") == {
        "kind": "ask_price", "text_fr": "J’ai lu 13 700 000 Ar ou 700 000 Ar : lequel est le prix ?",
        "amounts": [13700000, 700000]}
    assert ask("Redmi Note 13, 20 000 Ar ou 30 000 Ar ou 40 000 Ar")["text_fr"] == (
        "J’ai lu 20 000 Ar, 30 000 Ar ou 40 000 Ar : lequel est le prix ?")
    many = "Redmi 20 000 Ar, 30 000 Ar, 40 000 Ar, 50 000 Ar, 60 000 Ar"
    assert ask(many) == {"kind": "ask_price", "text_fr": "J’ai lu plusieurs montants. Écrivez le prix seul, par "
                                                         "exemple 250 000 Ar."}
    assert len(ask("Redmi 20 000 Ar, 30 000 Ar, 40 000 Ar, 50 000 Ar")["amounts"]) == 4
    # A price nobody wrote is still dropped; the question names what was written.
    assert ask("Redmi Note 13 250000", price_ar=999000)["amounts"] == [250000]
    # The model chose one of two: the recap shows it large before any credit.
    recap = ask("Redmi Note 13 700 000", price_ar=700000)
    assert (recap["kind"], recap["price_ar"]) == ("recap", 700000)
    # The draft's price stays when this message writes none.
    assert new("Redmi Note 13", {"product_name": "Redmi Note 13"}, price_ar=250000)["card"]["kind"] == "recap"
    # The poster reader is given the same rule (T-KIT-016).
    rule = "only when written in digits in this message, with or without a unit (250000, 250 000, 250.000, 250k); null"
    assert rule in reads.SYSTEM and rule in next(row.rule for row in reads.FIELDS if row.name == "price_ar")


def test_scene_words_of_the_first_message_reach_the_draft(caplog):
    """D-KIT-003: the owner's own words, in his language; the word guard, then the refinement's screen."""
    found = {"product_name": "JBL Flip 7", "price_ar": 250000}
    message = "JBL Flip 7 250000, fond rouge avec des reflets"
    answer = new(message, found | {"instruction_fr": "fond rouge avec des reflets"})
    assert answer["draft"]["scene_fr"] == "fond rouge avec des reflets" and answer["card"]["kind"] == "recap"
    assert "unused_fr" not in answer["card"] and "scene_fr" not in answer["card"]  # the client fills its recap
    malagasy = "JBL Flip 7 250000 lamosina mena"
    assert new(malagasy, found | {"instruction_fr": "lamosina mena"})["draft"]["scene_fr"] == "lamosina mena"
    # The guard: translated, or completed with a feature nobody wrote. Dropped, logged, said as a part not used.
    for scene in ("fond rouge", "lamosina mena, bluetooth 5.3"):
        caplog.clear()
        dropped = new(malagasy, found | {"instruction_fr": scene})
        assert "scene_fr" not in dropped["draft"] and guarded(caplog) == ["word guard: scene dropped"]
        assert dropped["card"]["unused_fr"] == [MESSAGES["card_unused_other"].format(malagasy)]
    # The screen: a price or a promotion is not a scene.
    screened = new("JBL Flip 7 250000, fond rouge promo -20%", found | {"instruction_fr": "fond rouge promo -20%"})
    assert "scene_fr" not in screened["draft"] and screened["card"]["unused_fr"] == [
        MESSAGES["card_unused_commercial"].format("fond rouge promo -20%")]
    # A later message replaces the draft's scene (the reader returns the whole wanted scene), or leaves it.
    replaced = new("plutôt un fond bleu", {"instruction_fr": "fond bleu"}, name="JBL Flip 7", price_ar=250000,
                   scene_fr="fond rouge")
    assert replaced["draft"]["scene_fr"] == "fond bleu"
    assert replaced["card"]["text_fr"].endswith("J’ai changé : la scène (avant : « fond rouge »).")
    kept = new("avec des reflets", {"instruction_fr": "fond rouge avec des reflets"}, name="JBL", price_ar=250000,
               scene_fr="fond rouge")  # the draft's own words count for the guard
    assert kept["draft"]["scene_fr"] == "fond rouge avec des reflets"
    assert new("250000", {"price_ar": 250000}, name="JBL", scene_fr="fond rouge")["draft"]["scene_fr"] == "fond rouge"
    # A body without the field has the hash it had before; the reader sees the draft's words.
    old = {"text": "Mets la marque Sony", "creation_id": "00000000-0000-4000-8000-000000000001",
           "history": [{"role": "app", "text": "Bonjour"}]}
    sha = lambda **draft: reads._sha(reads.canonical(reads.ReadRequest(  # noqa: E731
        **old, draft={"product_photos": 1, "inspiration": False} | draft)))
    assert sha() == sha(scene_fr=None) == "152398624c19856d4be7be49fcfdd2f57b6917181344150f5425f2a0775f8515"
    assert sha(scene_fr="fond rouge") != sha()
    assert reads.ReadRequest(**body("JBL", scene_fr="fond rouge")).draft.model_dump()["scene_fr"] == "fond rouge"
    for bad in ("", " ", "x" * 501):
        with pytest.raises(ValueError):
            reads.ReadRequest(**body("JBL", scene_fr=bad))


def test_unused_parts_are_said_with_their_reason():
    """D-KIT-004: each part not used, on its own line after the card's sentence and in unused_fr, byte for byte."""
    message = ("Casque JBL 250000 promo -20% avec une enceinte, en story, la 2e photo est le style, publie-la "
               "sur Facebook")
    parts = [{"text": "promo -20%", "reason": "commercial"}, {"text": "avec une enceinte", "reason": "product"},
             {"text": "en story", "reason": "format"}, {"text": "la 2e photo est le style", "reason": "photo"}]
    card = new(message, {"product_name": "Casque JBL", "price_ar": 250000, "unused": parts})["card"]
    said = [MESSAGES[f"card_unused_{part['reason']}"].format(part["text"]) for part in parts[:3]]
    assert card["unused_fr"] == said and card["text_fr"] == "\n".join([MESSAGES["card_recap"], *said])
    assert said[0] == ("« promo -20% » : un prix, une remise ou une promotion ne va pas dans l’image. Le prix a son "
                       "champ ; le reste va dans la description de la publication.")
    # The fourth is not said: the first three are kept, whatever the reader sent.
    assert MESSAGES["card_unused_photo"].format(parts[3]["text"]) not in card["text_fr"]
    other = new(message, {"intent": "other", "unused": [{"text": "publie-la sur Facebook", "reason": "other"}]})
    assert other["card"] == {"kind": "unclear", "text_fr": MESSAGES["card_unclear"] + "\n« publie-la sur Facebook » : "
                             "je ne sais pas le mettre sur l’affiche. Dites-le autrement.",
                             "unused_fr": ["« publie-la sur Facebook » : je ne sais pas le mettre sur l’affiche. "
                                           "Dites-le autrement."]}
    # On a question too, said there once; a quote is one line, cut to 80 characters.
    asked = new("JBL\nen  story " + "x" * 90, {"product_name": "JBL", "unused": [
        {"text": "en\n story " + "x" * 90, "reason": "format"}]})["card"]
    assert asked["kind"] == "ask_price" and asked["unused_fr"] == [MESSAGES["card_unused_format"].format(
        ("en story " + "x" * 90)[:80])]
    assert asked["text_fr"].split("\n")[1:] == asked["unused_fr"]
    # The wire has no bounds: four parts and four lines are a whole answer, never a failed read (r1 fix 3).
    answer = reads.Fields.model_validate_json(json.dumps({
        "intent": "describe", "product_name": "JBL", "price_ar": None, "style": None, "instruction_fr": None,
        "identity": None, "shop_lines": ["a", "b", "c", "d" * 41], "unused": parts + [{"text": "y" * 200, "reason": "other"}],
        "advert": True}))
    assert len(answer.unused) == 5 and len(answer.shop_lines) == 4
    schema = json.dumps(wire_schema(reads.Fields))
    assert "maxItems" not in schema and "maxLength" not in schema and "Constraints" not in schema


def test_an_unused_quote_nobody_wrote_is_dropped(caplog):
    card = new("Casque JBL 250000", {"product_name": "Casque JBL", "price_ar": 250000, "unused": [
        {"text": "livraison gratuite", "reason": "commercial"}, {"text": "JBL 250000", "reason": "other"}]})["card"]
    assert card["unused_fr"] == [MESSAGES["card_unused_other"].format("JBL 250000")]
    assert guarded(caplog) == ["word guard: unused dropped"]


def test_a_changed_recap_field_is_said():
    """R-KIT-004: a choice the recap already had, changed by this read, is said with what it was."""
    draft = {"name": "JBL Flip 7", "price_ar": 700000, "style": "clair", "scene_fr": "fond rouge", "identity": True}
    card = new("JBL Flip 7 blanc, 650 000 Ar, luxe sombre, fond noir, sans logo", {
        "product_name": "JBL Flip 7 blanc", "price_ar": 650000, "style": "sombre", "instruction_fr": "fond noir",
        "identity": False}, **draft)["card"]
    assert card["text_fr"] == (
        "Voici l’affiche que je vais créer.\nJ’ai changé : le nom (avant : JBL Flip 7), le prix (avant : 700 000 "
        "Ar), le style (avant : Studio clair), la scène (avant : « fond rouge ») et le logo et le contact de la "
        "boutique (avant : avec).")
    assert new("avec le logo", {"identity": True}, **draft | {"identity": False})["card"]["text_fr"].endswith(
        "J’ai changé : le logo et le contact de la boutique (avant : sans).")
    # The same value, or a field the recap did not have yet: nothing to say.
    assert new("JBL Flip 7, 700 000 Ar", {"product_name": "JBL Flip 7", "price_ar": 700000, "style": "clair"},
               **draft)["card"]["text_fr"] == MESSAGES["card_recap"]
    assert new("JBL Flip 7, 700 000 Ar", {"product_name": "JBL Flip 7", "price_ar": 700000, "identity": True})[
        "card"]["text_fr"] == MESSAGES["card_recap"]


def test_a_warranty_by_message_is_an_offer_not_a_refusal(caplog):
    """D-KIT-005, R-KIT-005: a line asked by message is offered to keep and draw, never refused for its words."""
    found = {"product_name": "JBL Flip 7", "price_ar": 250000}
    message = "JBL Flip 7 250000, ajoute Garantie 6 mois et Paiement Mvola"
    offered = new(message, found | {"shop_lines": ["Garantie 6 mois", "garantie 6 MOIS", "Paiement Mvola"]})["card"]
    assert offered["offer_lines"] == ["Garantie 6 mois", "Paiement Mvola"] and offered["text_fr"] == MESSAGES["card_recap"]
    # Already kept; no room left; a line with an amount or too long: each said, none offered.
    kept = new(message, found | {"shop_lines": ["garantie 6 mois"]}, ["Garantie 6 mois"])["card"]
    assert "offer_lines" not in kept and kept["text_fr"].endswith("« garantie 6 mois » est déjà dans les lignes de la boutique.")
    full = new(message, found | {"shop_lines": ["Paiement Mvola"]}, ["A", "B", "C"])["card"]
    assert "offer_lines" not in full and full["text_fr"].endswith(
        "La boutique a déjà trois lignes : remplacez-en une dans Mon compte.")
    two = new(message, found | {"shop_lines": ["Garantie 6 mois", "Paiement Mvola"]}, ["A", "B"])["card"]
    assert two["offer_lines"] == ["Garantie 6 mois"] and two["text_fr"].endswith(MESSAGES["card_lines_full"])
    long = "Livraison gratuite partout à Antananarivo et en province"
    rejected = new(f"JBL Flip 7 250000, Livraison 5 000 Ar, {long}",
                   found | {"shop_lines": ["Livraison 5 000 Ar", long]})["card"]
    assert "offer_lines" not in rejected and rejected["unused_fr"] == [
        "« Livraison 5 000 Ar » : une ligne de la boutique ne contient ni montant, ni remise, ni numéro.",
        f"« {long} » : une ligne de la boutique fait 40 caractères au plus."]
    # A telephone number is said as what it is, not as a price or a promotion (T-KIT-016).
    phone = new("JBL Flip 7 250000, ligne Tél 034 12 345 67", found | {"shop_lines": ["Tél 034 12 345 67"]})["card"]
    assert phone["unused_fr"] == [MESSAGES["card_line_refused"].format("Tél 034 12 345 67")]
    caplog.clear()
    invented = new(message, found | {"shop_lines": ["Garantie 12 mois"]})["card"]
    assert "offer_lines" not in invented and guarded(caplog) == ["word guard: shop_line dropped"]
    # On a poster: a card of its own, paid, that keeps the line and redraws; before the commercial refusal.
    kept_words = {"title": "Sony WH-CH720N", "brand": None, "subtitle": None, "price_ar": 450000}
    line = change("ajoute garantie 6 mois", words(DRAWN), ["Paiement Mvola"], shop_lines=["Garantie 6 mois"],
                  commercial=True)
    assert line == {"kind": "line", "visual_id": VISUAL, "lines": ["Garantie 6 mois"], "words": kept_words,
                    "effect": "scene", "text_fr": "Je garde « Garantie 6 mois » dans les lignes de la boutique et je "
                                                  f"refais l’affiche avec.\n{REDRAW}"}
    both = change("ajoute garantie 6 mois et paiement mvola, marque Sony", words(DRAWN),
                  shop_lines=["Garantie 6 mois", "Paiement Mvola"], brand="Sony")
    assert both["text_fr"] == (f"Je garde « Garantie 6 mois » et « Paiement Mvola » dans les lignes de la boutique et "
                               f"je refais l’affiche avec.\n{REDRAW}\nDemandez le reste ensuite.")
    assert both["words"] == kept_words  # the brand is asked after, from the new version
    # A version without drawn words; every line already drawn; no room; a word nobody wrote; an amount.
    assert change("ajoute garantie 6 mois", words(), shop_lines=["Garantie 6 mois"]) == {
        "kind": "steps", "text_fr": "Les lignes de la boutique sont dessinées dans l’image : cette affiche n’a pas de "
                                    "textes dessinés."}
    assert change("ajoute garantie 6 mois", words(DRAWN, lines=["Garantie 6 mois"]), ["Garantie 6 mois"],
                  shop_lines=["garantie 6 mois"]) == SAME
    assert change("ajoute garantie 6 mois", words(DRAWN), ["A", "B", "C"], shop_lines=["Garantie 6 mois"]) == refused(
        "card_lines_full") | {"account": True}  # with the way to « Mon compte »
    assert change("ajoute garantie 6 mois", words(DRAWN, lines=["Garantie 6 mois"]), ["Garantie 6 mois", "B", "C"],
                  shop_lines=["Garantie 6 mois", "B"])["kind"] == "line"  # kept, not drawn by this version yet
    assert change("ajoute la garantie", words(DRAWN), shop_lines=["Garantie 2 ans"]) == refused("card_word_unknown", "2")
    assert change("ajoute livraison 5 000 Ar", words(DRAWN), shop_lines=["Livraison 5 000 Ar"]) == refused(
        "card_line_refused", "Livraison 5 000 Ar")
    assert change("ajoute Tél 034-12-345-67", words(DRAWN), shop_lines=["Tél 034-12-345-67"]) == refused(
        "card_line_refused", "Tél 034-12-345-67")
    assert change(f"ajoute {long}", words(DRAWN), shop_lines=[long]) == refused("card_line_too_long", long)
    # card_refused no longer asks the owner to remove his words; it says where a warranty goes.
    assert "retirez" not in MESSAGES["card_refused"] and "lignes de la boutique" in MESSAGES["card_refused"]


def test_a_word_change_that_redraws_says_so():
    """D-KIT-007: a scene card made from words says it redraws the whole image for one credit; nothing else does."""
    assert REDRAW == "Le texte est dessiné dans l’image : cette correction refait toute l’image, pour 1 crédit."
    assert change("titre WH-CH720N noir", words(DRAWN), title="WH-CH720N noir")["text_fr"].endswith(REDRAW)
    assert REDRAW not in change("650 000 Ar", words(DRAWN), price_ar=650000)["text_fr"]  # free: the image stays
    assert REDRAW not in change("un fond sombre", words(DRAWN), instruction_fr="fond")["text_fr"]  # an adjustment
    assert REDRAW not in change("luxe sombre", words(DRAWN), style="sombre")["text_fr"]  # restyle: its own card


def test_quotes_in_a_name_are_curled():
    assert [reads.curl_quotes(name) for name in ('TV 55"', 'Casque "Pro" noir', 'TV "Smart" 55"', "JBL")] == [
        "TV 55″", "Casque « Pro » noir", "TV « Smart » 55″", "JBL"]
    answer = new('Casque "Pro" 250000', {"product_name": 'Casque "Pro"', "price_ar": 250000})
    assert answer["draft"]["name"] == "Casque « Pro »" and answer["card"]["name"] == "Casque « Pro »"
    # A line break is still refused, with its sentence.
    assert new("TV", {"product_name": "TV\n32"})["card"] == {"kind": "ask_product",
                                                             "text_fr": MESSAGES["title_unsupported"]}


def test_the_name_guard_lets_capitals_pass(caplog):
    """D-KIT-007: letters and digits only; a name that fails is kept as the reader gave it, logged, no question."""
    answer = new("redmi note13 250000", {"product_name": "Redmi Note 13", "price_ar": 250000})
    assert (answer["card"]["kind"], answer["draft"]["name"], guarded(caplog)) == ("recap", "Redmi Note 13", [])
    assert new("sony wh-ch720n 250000", {"product_name": "Sony WH-CH720N", "price_ar": 250000})["draft"]["name"] == (
        "Sony WH-CH720N")
    # The draft's name is the owner's too: a corrected product is built from it.
    assert new("en blanc", {"product_name": "JBL Flip 7 blanc"}, name="JBL Flip 7", price_ar=250000)["card"][
        "kind"] == "recap" and guarded(caplog) == []
    invented = new("redmi note13 250000", {"product_name": "Redmi Note 13 Pro", "price_ar": 250000})
    assert (invented["card"]["kind"], invented["draft"]["name"]) == ("recap", "Redmi Note 13 Pro")
    assert guarded(caplog) == ["word guard: product_name kept"]
    # A new word inside a written one is still new (T-KIT-016): « Pro » is not in « produit », « Air » not in « chair ».
    for message, name in (("mon produit redmi note13 250000", "Redmi Note 13 Pro"), ("housse chair 250000", "Air")):
        caplog.clear()
        assert new(message, {"product_name": name, "price_ar": 250000})["draft"]["name"] == name
        assert guarded(caplog) == ["word guard: product_name kept"]
    assert "with their usual capitals (Sony WH-CH720N, iPhone 15 Pro, JBL Flip 7)" in reads.SYSTEM


def test_a_message_that_is_no_advert_keeps_nothing():
    """R-KIT-013: one sentence, nothing kept from that message, no paid card; in every doubt an advert."""
    draft = {"name": "JBL Flip 7", "price_ar": 250000}
    answer = new("fais un portrait de ma fille 250000", {"product_name": "Portrait", "price_ar": 250000,
                                                         "instruction_fr": "portrait", "shop_lines": ["Garantie"],
                                                         "advert": False}, **draft)
    assert answer == {"card": {"kind": "unclear", "text_fr": MESSAGES["card_not_advert"]},
                      "draft": {"name": "JBL Flip 7", "price_ar": 250000, "style": None, "product_photos": 1,
                                "inspiration": False}}
    assert MESSAGES["card_not_advert"] == ("Je fais des affiches pour ce que votre boutique vend. Envoyez la photo "
                                           "d’un produit, son nom et son prix.")
    assert change("fais un portrait", words(DRAWN), title="Portrait", advert=False) == {
        "kind": "unclear", "text_fr": MESSAGES["card_not_advert"]}
    assert reads.Fields(intent="describe", product_name=None, price_ar=None, style=None, instruction_fr=None,
                        identity=None).advert is True
    assert "advert: false only when the message plainly asks" in reads.SYSTEM
    assert wire_schema(reads.poster_fields())["properties"]["advert"]["description"].startswith("False only when")


def test_the_stub_reader_reads_the_kits_markers(stub, client):
    """The stub's deterministic markers (D-KIT-004 "Tests") drive the new paths without a paid call."""
    login(client)
    with write_tx(client.app.state.engine) as conn:
        conn.exec_driver_sql("""UPDATE shop_profile SET lines_json='["Paiement Mvola"]' WHERE id=1""")

    def read(text, **draft):
        answer = post(client, "/api/reads", body(text, **draft))
        assert answer.status_code == 201, answer.text
        return answer.json()

    answer = read("JBL Flip 7 250000 scène : fond rouge, ligne : Garantie 6 mois pas utilisé : en story")
    assert answer["draft"] == {"name": "JBL Flip 7", "price_ar": 250000, "style": None, "product_photos": 1,
                               "inspiration": False, "scene_fr": "fond rouge"}
    assert answer["card"] == {"kind": "recap", "text_fr": MESSAGES["card_recap"] + "\n" + MESSAGES[
        "card_unused_other"].format("en story"), "name": "JBL Flip 7", "price_ar": 250000, "style": None,
        "offer_lines": ["Garantie 6 mois"], "unused_fr": [MESSAGES["card_unused_other"].format("en story")]}
    assert read("JBL 250000 ligne : Paiement Mvola")["card"]["text_fr"].endswith(
        "« Paiement Mvola » est déjà dans les lignes de la boutique.")
    assert read("casque sony wh-ch720n noir 250000")["card"]["name"] == "casque sony wh-ch720n noir"
    assert read("Casque JBL 250k")["draft"]["price_ar"] == 250000
    two = read("13 700 000 ou 700 000", name="Redmi Note 13")["card"]
    assert (two["kind"], two["amounts"]) == ("ask_price", [13700000, 700000])
    assert read("pas utilisé : publie-la sur Facebook")["card"]["kind"] == "unclear"


def test_a_follow_up_read_as_other_keeps_its_scene_words_and_lines(stub, client):
    """T-KIT-016 (review r1 of T-KIT-003, finding 5): a follow-up on a draft that the reader calls « other » keeps its
    line and its scene words; the draft's product and price are not asked again."""
    draft = {"name": "JBL Flip 7", "price_ar": 250000}
    answer = new("ajoute Garantie 6 mois, fond rouge", {"intent": "other", "instruction_fr": "fond rouge",
                                                        "shop_lines": ["Garantie 6 mois"]}, **draft)
    assert answer["card"] == {"kind": "recap", "text_fr": MESSAGES["card_recap"], "name": "JBL Flip 7",
                              "price_ar": 250000, "style": None, "offer_lines": ["Garantie 6 mois"]}
    assert answer["draft"]["scene_fr"] == "fond rouge"
    assert new("merci", {"intent": "other", "shop_lines": [" "]}, **draft)["card"] == {
        "kind": "unclear", "text_fr": MESSAGES["card_unclear"]}  # nothing usable
    assert "intent: describe = product, price, style, scene or shop lines of a new poster;" in reads.SYSTEM
    # The stub says « other » for markers alone, as a paid reader may: the same recap through the route.
    login(client)
    request = body("scène : fond rouge ligne : Garantie 6 mois", **draft)
    assert reads.stub_read(reads.ReadRequest(**request)).intent == "other"
    answer = post(client, "/api/reads", request)
    assert answer.status_code == 201, answer.text
    assert answer.json()["card"]["offer_lines"] == ["Garantie 6 mois"] and answer.json()["draft"]["scene_fr"] == "fond rouge"
