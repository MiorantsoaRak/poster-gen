import asyncio
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx2
import pytest
from alembic import command
from sqlalchemy import text

from affiche.api import MESSAGES
from affiche.config import load_settings
from affiche.db import make_engine, migrate, utc_now, write_tx
from affiche.posters import jobs, reads, store, visuals
from affiche.posters.models import CopyCreation, ProductInput
from affiche.posters.planner import MODEL
from affiche.posters.plans import Headline, wire_schema
from affiche.posters.store import Refused
from affiche.visuals.admission import spent_micros
from test_api import client, create_draft, login, password_hash, post, settings  # noqa: F401
from test_config import env  # noqa: F401
from test_admission import _ledger_call, _seed
from test_db import engine  # noqa: F401
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
              "instruction_fr": None} | (fields or {})
    return httpx2.Response(200, headers={"request-id": "req-read"}, json={
        "model": MODEL, "stop_reason": "end_turn", "content": [{"type": "text", "text": json.dumps(fields)}],
        "usage": {"input_tokens": 1200, "output_tokens": 150}} | updates)


THOUGHT = {"type": "thinking", "thinking": "", "signature": "sig"}
ANSWER = {"type": "text", "text": json.dumps({"intent": "describe", "product_name": "JBL Flip 7", "price_ar": 700000,
                                              "style": None, "instruction_fr": None})}


def ask(engine, settings, response, text="JBL Flip 7, 700 000 Ar", key=None, **draft):
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
        result = asyncio.run(reads.read(engine, settings, 1, key or str(uuid4()), reads.ReadRequest(**body(text, **draft)),
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
            assert conn.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one() == "0012"
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
    ("٧700 123 Ar", 123), ("Prix 1234 567 Ar", 567), ("700 000,00 Ar", 0), ("700k", 700000),
    ("(700 000 Ar)", 700000), ("Armani 700", 700), ("arrivage 700 000", 700000),
    ("Sony WH-1000XM6 noir", 1000), ("0 Ar", 0), ("000 Ar", 0), ("0", 0), ("700 000 Argent", 700000),
    ("1.5 000 Ar", 5000), ("700.00 Ar", 70000), ("700 000 A r", 700000),
    ("JBL Flip 7. 700 000 Ar", 700000), ("JBL (7) 700 000 Ar", 700000), ("JBL 7+ 700 000 Ar", 700000),
    ("2 350000", 350000),
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
])
def test_candidate_amounts(message, amounts):
    assert reads.candidate_amounts(message) == amounts


@pytest.mark.parametrize("message", ["0700000 Ar", "0700000"])
def test_a_leading_zero_does_not_hide_the_price(message):
    fields = reads.Fields(intent="describe", product_name=None, price_ar=700000, style=None, instruction_fr=None)
    answer = reads.build(fields, reads.ReadRequest(**body(message, name="JBL Flip 7")), MESSAGES)
    assert (answer["card"]["kind"], answer["card"]["price_ar"]) == ("recap", 700000)


@pytest.mark.parametrize(("message", "partial"), REJECTED)
def test_a_partial_amount_from_the_model_is_never_the_price(message, partial):
    fields = reads.Fields(intent="describe", product_name="JBL", price_ar=partial, style=None, instruction_fr=None)
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
    assert asked["kind"] == "ask_price" and "700 000 Ar" in asked["text_fr"] and draft["name"] == "JBL Flip 7"
    asked, draft = card("Sony WH-1000XM6 noir, 700 000 Ar", product_photos=0)
    assert asked == {"kind": "ask_photo", "text_fr": "Il me faut une photo du produit."}
    assert (draft["name"], draft["price_ar"]) == ("Sony WH-1000XM6 noir", 700000)
    recap, draft = card("JBL Flip 7, 700 000 Ar", style="clair", product_photos=2, inspiration=True)
    assert recap == {"kind": "recap", "text_fr": MESSAGES["card_recap"], "name": "JBL Flip 7", "price_ar": 700000,
                     "style": "clair"}
    assert draft == {"name": "JBL Flip 7", "price_ar": 700000, "style": "clair", "product_photos": 2, "inspiration": True}
    # An answer to a question changes only its own field.
    recap, _ = card("650 000 Ar", name="JBL Flip 7", price_ar=700000)
    assert (recap["kind"], recap["name"], recap["price_ar"]) == ("recap", "JBL Flip 7", 650000)
    recap, _ = card("JBL Flip 7 blanc", name="JBL Flip 7", price_ar=700000)
    assert (recap["name"], recap["price_ar"]) == ("JBL Flip 7 blanc", 700000)
    # The title rules of the scene route, with their existing sentences; the refused name is not kept.
    for name, code in (("x" * 61, "title_too_long"), ("JBL promo", "title_commercial_text"), ('TV 32"', "title_unsupported")):
        asked, draft = card(name)
        assert asked == {"kind": "ask_product", "text_fr": MESSAGES[code]} and draft["name"] is None

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
        "intent", "product_name", "price_ar", "style", "instruction_fr"}
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
    (lambda: reply({"intent": "other", "product_name": "JBL"}), "succeeded", REAL, 0, "unclear"),
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


@pytest.mark.parametrize("key", ["not-a-uuid", "-" * 36, "A" * 8 + "-0000-0000-0000-" + "0" * 12, uuid4().hex])
def test_invalid_key_makes_no_call_and_no_reservation(engine, claude, key):
    result, requests = ask(engine, claude, reply(), key=key)
    assert (result.code, result.status, requests, rows(engine)) == ("invalid_idempotency_key", 422, [], [])


def test_creation_must_be_the_shops_and_active(engine, claude, tmp_path, input_id):
    creation = draft(engine, tmp_path, input_id)
    request = reads.ReadRequest(**body("Un fond plus chaud", creation["id"]))
    read = lambda shop: asyncio.run(reads.read(engine, claude, shop, str(uuid4()), request, MESSAGES,  # noqa: E731
                                               transport=httpx2.MockTransport(lambda _request: pytest.fail("called"))))
    with pytest.raises(Refused) as refused:
        read(2)  # shop_profile is CHECK (id = 1): no second shop can exist, so only the ownership filter is shown
    assert (refused.value.code, refused.value.status) == ("not_found", 404)
    store.abandon_creation(engine, 1, str(uuid4()), creation["id"], 1)
    with pytest.raises(Refused) as refused:
        read(1)
    assert (refused.value.code, refused.value.status, rows(engine)) == ("creation_abandoned", 409, [])


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


def words(image=None, title="Sony WH-CH720N", price_ar=450000, accent=None):
    """The poster words of reads.poster_words: the image's (empty: no drawn words) and the document's."""
    return {"visual_id": VISUAL, "accent_word": accent, "image": dict(image or {}),
            "document": {"title": title, "price_ar": price_ar}}


def change(message, poster, **fields):
    fields = {row.name: None for row in reads.FIELDS} | {"remove": []} | fields
    request = reads.ReadRequest(**body(message, CREATION, visual_id=VISUAL))
    return reads.build(reads.poster_fields()(**fields), request, MESSAGES, poster)["card"]


def scene(text_fr, **words):
    return {"kind": "change", "text_fr": text_fr, "visual_id": VISUAL, "effect": "scene", "words": words}


def refused(code, *values):
    return {"kind": "refused", "text_fr": MESSAGES[code].format(*values)}


SAME = {"kind": "same", "text_fr": "L’affiche a déjà ces textes."}
STEPS = {"kind": "steps", "text_fr": MESSAGES["card_steps"]}


def test_the_field_table_drives_the_schema_the_card_and_the_sentence(monkeypatch):
    schema = wire_schema(reads.poster_fields())
    assert schema["required"] == ["title", "brand", "subtitle", "price_ar", "instruction_fr", "remove"]
    assert schema["properties"]["remove"]["items"]["enum"] == ["brand", "subtitle"]
    assert all(schema["properties"][row.name]["description"] == row.rule for row in reads.FIELDS)
    assert change("Merci", words(DRAWN))["text_fr"] == ("Dites ce qu’il faut changer : le titre, la marque, le "
                                                        "sous-titre, le prix, le fond, la lumière. Le reste se change dans Pas à pas.")
    # One row added: it is in the model's schema, in the sentence and on the card.
    monkeypatch.setattr(reads, "FIELDS", (*reads.FIELDS, reads.Row(
        "accent_word", str, "The word of the title in colour.", "le mot en couleur", "Mot en couleur", reads._headline_text)))
    assert wire_schema(reads.poster_fields())["properties"]["accent_word"]["description"] == "The word of the title in colour."
    assert "la lumière, le mot en couleur. Le reste" in change("Merci", words(DRAWN))["text_fr"]
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
                  brand="Sony") == SAME
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
    assert card["text_fr"] == "Titre : WH-CH720N\nMarque : Sony\nLe mot en couleur est retiré."
    card = change("mets Sony en haut", words(DRAWN | {"accent_word": "WH"}, accent="WH"), brand="Sony")
    assert card["text_fr"] == "Titre : WH-CH720N\nMarque : Sony"


def test_words_first_drop_the_instruction():
    # The instruction holds « titre », which the refinement screen refuses: dropped before it is screened.
    card = change("marque Sony, et mets le titre sur un fond sombre", words(DRAWN), brand="Sony",
                  instruction_fr="mets le titre sur un fond sombre")
    assert card == scene("Titre : WH-CH720N\nMarque : Sony\n" + MESSAGES["card_words_first"], title="WH-CH720N",
                         brand="Sony", subtitle=None, price_ar=450000)
    assert change("un fond sombre", words(DRAWN), instruction_fr=" un fond sombre ") == {
        "kind": "change", "text_fr": "Scène : « un fond sombre »", "visual_id": VISUAL, "effect": "refine",
        "instruction_fr": "un fond sombre"}
    assert change("mets le titre sur un fond", words(DRAWN), instruction_fr="mets le titre sur un fond") == refused("card_refused")
    assert change("fond", words(DRAWN), instruction_fr="x" * 501) == refused("card_refused")
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
    assert change("marque Sony, 650 000 Ar", words(DRAWN), brand="Sony", price_ar=700000) == refused("card_ask_price")


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
    assert card["text_fr"] == "Sous-titre : RAM 128 Go"


def test_remove_and_same():
    stored = words({"title": "WH-CH720N", "brand": "Sony", "subtitle": "Casque"}, title="WH-CH720N")
    assert change("sans sous-titre", stored, remove=["subtitle"]) == scene(
        "Sous-titre : retiré", title="WH-CH720N", brand="Sony", subtitle=None, price_ar=450000)
    assert change("sans marque ni sous-titre", stored, remove=["brand", "subtitle"])["text_fr"] == (
        "Marque : retiré\nSous-titre : retiré")
    assert change("enlève la marque", words(DRAWN), remove=["brand"]) == SAME  # no brand to take off
    assert change("le prix est 450 000 Ar", words(DRAWN), price_ar=450000) == SAME
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
    assert (card["effect"], card["text_fr"]) == ("scene", "Titre : Sony WH-CH720N bleu")
    assert card["words"]["price_ar"] == 450000
    # A new price beside that edited title: both lines, one image.
    assert change("mets 480 000 Ar", both, price_ar=480000)["text_fr"] == "Titre : Sony WH-CH720N bleu\nPrix : 480\u202f000 Ar"


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
    # Two adjustments in the order asked, and the model is told that the later one wins.
    creation = store.get_creation(engine.connect(), 1, creation_id)
    visuals.request_refinement(engine, settings, 1, key(), creation_id, creation["revision"], visuals.RefinementRequest(
        base_visual_id=creation["document"]["formats"]["feed"]["scene"]["visual_id"], instruction_fr="fond rouge"))
    red = payload(scene(keep_adjustments_of=execute(engine, settings)))
    assert red["adjustments"][-1] == "fond rouge" and "the later one wins" in red["prompt"]
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
    assert card("marque Sony") == {"kind": "change", "text_fr": "Marque : Sony", "visual_id": visual,
                                   "effect": "scene", "words": stored | {"brand": "Sony"}}
    assert card("titre Grande enceinte")["words"] == stored | {"title": "Grande enceinte"}
    assert card("sous-titre Son puissant")["words"] == stored | {"subtitle": "Son puissant"}
    assert card("sans marque")["words"] == stored | {"brand": None}
    assert card("sans sous-titre") == SAME
    assert card("non, 650 000 Ar")["words"] == stored | {"price_ar": 650000}
    assert card("Un fond plus chaud") == {"kind": "change", "text_fr": "Scène : « Un fond plus chaud »",
                                          "visual_id": visual, "effect": "refine", "instruction_fr": "Un fond plus chaud"}
    assert card("Ajoute le texte promo sur le fond") == refused("card_refused")
    for message in ("Change le prix", "Merci", "JBL Flip 8"):
        assert card(message)["kind"] == "unclear"
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
    answer = {row.name: None for row in reads.FIELDS} | {"remove": ["brand"]}
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
