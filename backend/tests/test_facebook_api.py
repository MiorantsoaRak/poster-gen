"""Connecting a shop's Facebook Page through the routes (D-FB-PUBLISH-002): the attempt, the code's three steps, the choice,
the disconnection, and what the card is told. Facebook is httpx2.MockTransport (`meta`) or the stand-in (`stub`): nothing
leaves the machine."""
import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import httpx2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from affiche.api import create_app
from affiche.config import load_settings
from affiche.db import write_tx
from affiche.posters import auth, facebook, facebook_connect
from affiche.posters.facebook_connect import STUB_CODE
from affiche.posters.store import Refused
from test_api import HEADERS, ORIGIN, credentials, login, password_hash, second_shop  # noqa: F401
from test_config import env  # noqa: F401
from test_db import credited

APP, SECRET = "1234567890", "app-secret-never-printed"
CODE, USER_TOKEN, LONG_TOKEN = "dialog-code-never-printed", "user-token-never-printed", "long-lived-token-never-printed"
TOKENS = ("page-token-of-the-page-111", "page-token-of-the-page-333", "page-token-of-the-page-222")
SENSITIVE = (SECRET, CODE, USER_TOKEN, LONG_TOKEN, *TOKENS)
ACCOUNTS = {"data": [
    {"id": "111", "name": "Original Phone Mada", "tasks": ["ANALYZE", "CREATE_CONTENT"], "access_token": TOKENS[0]},
    {"id": "222", "name": "Messages only", "tasks": ["MESSAGING"], "access_token": TOKENS[2]},
    {"id": "333", "name": "Boutique Deux", "tasks": ["CREATE_CONTENT", "MODERATE"], "access_token": TOKENS[1]}]}
CHOICE = [{"id": "111", "name": "Original Phone Mada"}, {"id": "333", "name": "Boutique Deux"}]
ROUTES = [("GET", "/api/facebook"), ("POST", "/api/facebook/connect"), ("POST", "/api/facebook/code"),
          ("POST", "/api/facebook/page"), ("DELETE", "/api/facebook/page")]


class Graph:
    """Facebook, call by call: the exchange, the long-lived token, the Pages. `during` runs inside a call, as Facebook
    takes its time: the request's own transactions must all be closed by then."""
    def __init__(self):
        self.requests, self.answers, self.during = [], {}, None

    def __call__(self, request):
        self.requests.append(request)
        if self.during:
            self.during(request)
        if request.url.path == "/v27.0/me/accounts":
            return self.answers.get("pages", httpx2.Response(200, json=ACCOUNTS))
        exchange = b"fb_exchange_token" in request.content
        token = LONG_TOKEN if exchange else USER_TOKEN
        return self.answers.get("long_lived" if exchange else "code", httpx2.Response(200, json={"access_token": token}))


@pytest.fixture
def graph(monkeypatch):
    graph, real = Graph(), facebook.make_graph
    monkeypatch.setattr(facebook, "make_graph", lambda settings: real(settings, httpx2.MockTransport(graph)))
    return graph


def settings_for(env, tmp_path, password_hash, provider):
    env.setenv("DATA_DIR", str(tmp_path))
    env.setenv("APP_ORIGIN", ORIGIN)
    env.setenv("SHOP_PASSWORD_HASH", password_hash)
    if provider:
        env.setenv("FACEBOOK_PROVIDER", provider)
    if provider == "meta":
        env.setenv("FACEBOOK_APP_ID", APP)
        env.setenv("FACEBOOK_APP_SECRET", SECRET)
    return load_settings(env_file=None)


@pytest.fixture
def client(env, tmp_path, password_hash, graph, caplog):
    caplog.set_level(logging.DEBUG)
    answers = []  # every answer of the test, for the check that no credential reaches the browser
    with TestClient(create_app(settings_for(env, tmp_path, password_hash, "meta"), prepare=credited), base_url=ORIGIN,
                    headers=HEADERS) as client:
        client.event_hooks["response"].append(answers.append)
        login(client)
        yield client
        for answer in answers:
            assert not any(value in answer.text for value in SENSITIVE), (answer.request.url.path, answer.text)
    assert not any(value in caplog.text for value in SENSITIVE)


def device(client, password=None, identifier="originalphone"):
    """Another browser: another session, of this shop or another."""
    other = TestClient(client.app, base_url=ORIGIN, headers=HEADERS)
    other.event_hooks["response"].extend(client.event_hooks["response"])  # its answers are checked too
    assert other.post("/api/session", json=credentials(*((password, identifier) if password else ()))).status_code == 200
    return other


def connect(client) -> str:
    answer = client.post("/api/facebook/connect")
    assert answer.status_code == 200, answer.text
    return parse_qs(urlsplit(answer.json()["url"]).query)["state"][0]


def send(client, state, code=CODE, **body):
    return client.post("/api/facebook/code", json={"state": state, **({"code": code} if code else {}), **body})


def refused(answer, code, status=409):
    assert (answer.status_code, answer.json()["error"]["code"]) == (status, code), answer.text


def attempts(client):
    with client.app.state.engine.connect() as conn:
        return [dict(row) for row in conn.execute(text("SELECT * FROM facebook_connects ORDER BY shop_id")).mappings()]


def pages(client):
    with client.app.state.engine.connect() as conn:
        return [dict(row) for row in conn.execute(text("SELECT * FROM facebook_pages ORDER BY shop_id")).mappings()]


def run(client, sql, **values):
    with write_tx(client.app.state.engine) as conn:
        conn.execute(text(sql), values)


OLD = (datetime.now(UTC) - timedelta(minutes=10, seconds=1)).isoformat(timespec="microseconds")


def test_off_answers_not_found_on_every_route_and_says_so_in_the_capabilities(env, tmp_path, password_hash):
    with TestClient(create_app(settings_for(env, tmp_path, password_hash, None), prepare=credited), base_url=ORIGIN,
                    headers=HEADERS) as client:
        login(client)
        assert client.get("/api/capabilities").json()["facebook"] is False
        for method, path in ROUTES:
            answer = client.request(method, path, json={"state": "s", "code": CODE} if path.endswith("code") else
                                    {"page_id": "111"} if method == "POST" and path.endswith("page") else None)
            refused(answer, "not_found", 404)
        # The routes do not exist: a body that no route would take is not_found too, not a validation error.
        for path, body in (("/api/facebook/code", {"state": ""}), ("/api/facebook/code", {}), ("/api/facebook/page", {"page_id": 5})):
            refused(client.post(path, json=body), "not_found", 404)
        assert attempts(client) == [] and pages(client) == []


def test_connect_writes_the_shops_one_attempt_and_the_dialogs_address(client, graph):
    first = connect(client)
    second = connect(client)  # replaces the first, whatever its step
    token = client.cookies.get(auth.COOKIE)
    [row] = attempts(client)
    assert row["state_sha"] == hashlib.sha256(second.encode()).hexdigest() and row["session_sha"] == auth.token_hash(token)
    assert (row["shop_id"], row["step"], row["pages_json"]) == (1, "dialog", None)
    assert first != second and len(second) == 43 and not any(second in str(value) for value in row.values())  # its hash only
    url = urlsplit(client.post("/api/facebook/connect").json()["url"])
    assert (url.scheme, url.netloc, url.path) == ("https", "www.facebook.com", "/v27.0/dialog/oauth")
    query = parse_qs(url.query, strict_parsing=True)
    assert {name: values for name, values in query.items() if name != "state"} == {
        "client_id": [APP], "redirect_uri": [f"{ORIGIN}/facebook.html"],
        "scope": ["pages_show_list,pages_manage_posts,pages_read_engagement,business_management"]}
    assert client.get("/api/capabilities").json()["facebook"] is True and graph.requests == []


def test_the_stand_in_sends_the_owner_back_to_the_return_page_with_a_code_and_walks_the_flow(env, tmp_path, password_hash):
    with TestClient(create_app(settings_for(env, tmp_path, password_hash, "stub"), prepare=credited), base_url=ORIGIN,
                    headers=HEADERS) as client:
        login(client)
        url = urlsplit(client.post("/api/facebook/connect").json()["url"])
        assert f"{url.scheme}://{url.netloc}{url.path}" == f"{ORIGIN}/facebook.html"
        query = {name: values[0] for name, values in parse_qs(url.query, strict_parsing=True).items()}
        assert set(query) == {"code", "state"} and query["code"] == STUB_CODE and facebook.credential(STUB_CODE)
        assert [page["name"] for page in send(client, query["state"], query["code"]).json()["choice"]] == ["Page d’essai 1", "Page d’essai 2"]
        assert client.post("/api/facebook/page", json={"page_id": "100000000000002"}).json()["page"] == {
            "id": "100000000000002", "name": "Page d’essai 2", "state": "connected"}
        with client.app.state.engine.connect() as conn:
            assert conn.execute(text("SELECT value FROM meta WHERE key='facebook_mode'")).scalar() == "stub"


def test_two_pages_are_offered_by_name_and_the_choice_connects_one(client, graph):
    answer = send(client, connect(client))
    assert answer.status_code == 200 and answer.json() == {"page": None, "choice": CHOICE}
    assert [request.url.path for request in graph.requests] == ["/v27.0/oauth/access_token"] * 2 + ["/v27.0/me/accounts"]
    [row] = attempts(client)
    assert row["step"] == "choice" and [page["token"] for page in json.loads(row["pages_json"])] == list(TOKENS[:2])
    assert client.get("/api/facebook").json() == {"page": None, "choice": CHOICE, "last_error": None}
    chosen = client.post("/api/facebook/page", json={"page_id": "333"})
    assert chosen.json() == {"page": {"id": "333", "name": "Boutique Deux", "state": "connected"}, "choice": None}
    assert attempts(client) == []  # with it, the other Page's token
    [page] = pages(client)
    assert (page["page_id"], page["page_name"], page["token"], page["state"]) == ("333", "Boutique Deux", TOKENS[1], "connected")
    assert client.get("/api/facebook").json() == {"page": chosen.json()["page"], "choice": None, "last_error": None}
    with client.app.state.engine.connect() as conn:
        assert conn.execute(text("SELECT value FROM meta WHERE key='facebook_mode'")).scalar() == "meta"


def test_a_session_that_ended_before_the_lock_was_taken_starts_chooses_and_removes_nothing(client, graph):
    """The boundary sees the session before the route takes the write lock: a sign-out in between must win. The functions
    are called as the routes call them, with a token whose session is gone."""
    engine, token = client.app.state.engine, client.cookies[auth.COOKIE]
    assert send(client, connect(client)).json()["choice"] == CHOICE
    chosen = device(client)
    assert send(chosen, connect(chosen)).status_code == 200 and chosen.post("/api/facebook/page", json={"page_id": "111"}).status_code == 200
    assert send(client, connect(client)).json()["choice"] == CHOICE  # this session's choice waits again
    before = attempts(client), pages(client)
    run(client, "DELETE FROM sessions WHERE token_hash=:hash", hash=auth.token_hash(token))  # signed out, after the boundary
    for call in (lambda: facebook_connect.choose(engine, 1, token, "333"),
                 lambda: facebook_connect.connect(engine, None, None, 1, token),  # refused before either is used
                 lambda: facebook_connect.disconnect(engine, 1, token)):
        with pytest.raises(Refused) as refusal:
            call()
        assert (refusal.value.code, refusal.value.status) == ("unauthenticated", 401)
    assert (attempts(client), pages(client)) == before  # the other session's Page and this one's attempt are as they were


def test_a_page_outside_the_choice_changes_nothing(client, graph):
    send(client, connect(client))
    before = attempts(client)
    for page_id in ("222", "999", "1" * 32):  # allowed without CREATE_CONTENT, unknown
        refused(client.post("/api/facebook/page", json={"page_id": page_id}), "facebook_state")
    assert attempts(client) == before and pages(client) == []
    refused(device(client).post("/api/facebook/page", json={"page_id": "111"}), "facebook_state")  # another session's choice
    run(client, "UPDATE facebook_connects SET created_at=:old", old=OLD)
    refused(client.post("/api/facebook/page", json={"page_id": "111"}), "facebook_state")  # too old
    assert pages(client) == []


def test_a_state_that_is_not_this_sessions_live_dialog_is_refused_before_any_call(client, graph):
    other_shop, password = second_shop(client.app.state.engine)
    theirs = device(client, password, "boutique-deux")
    foreign = connect(theirs)
    mine = connect(client)
    same_shop = device(client)
    cases = [(client, foreign), (client, "never-given"), (same_shop, mine)]  # a foreign shop's, a forged, another session's
    before = attempts(client)
    for who, state in cases:
        refused(send(who, state), "facebook_state")
    assert attempts(client) == before and graph.requests == []
    replaced = mine
    mine = connect(client)
    refused(send(client, replaced), "facebook_state")  # an older attempt of this session, replaced by « Connecter »
    run(client, "UPDATE facebook_connects SET created_at=:old WHERE shop_id=1", old=OLD)
    refused(send(client, mine), "facebook_state")  # over 10 minutes
    assert graph.requests == []
    mine = connect(client)
    assert send(client, mine).status_code == 200 and len(graph.requests) == 3
    refused(send(client, mine), "facebook_state")  # the same code again: no longer at 'dialog'
    run(client, "UPDATE facebook_connects SET step='exchange' WHERE shop_id=1")
    refused(send(client, mine), "facebook_state")  # an exchange on its way
    assert len(graph.requests) == 3
    assert [row["shop_id"] for row in attempts(client)] == [1, other_shop]
    assert send(theirs, foreign).status_code == 200  # the other shop's attempt was never touched


def test_the_first_code_request_claims_the_attempt_and_holds_no_lock_during_the_calls(client, graph):
    """Each call, while Facebook takes its time: the attempt is at 'exchange', so a second request with the same code is
    refused, and another connection writes at once (busy_timeout would make it wait 5 s, then fail)."""
    seen = []

    def during(request):
        with write_tx(client.app.state.engine) as conn:
            conn.execute(text("INSERT OR REPLACE INTO meta VALUES ('probe', :path)"), {"path": request.url.path})
            seen.append(conn.execute(text("SELECT step FROM facebook_connects WHERE shop_id=1")).scalar())

    graph.during = during
    assert send(client, connect(client)).status_code == 200 and seen == ["exchange"] * 3


@pytest.mark.parametrize("call", ["code", "long_lived", "pages"])
@pytest.mark.parametrize("status, body", [(500, {"error": {"code": 2}}), (200, b"{not json"),
                                          (400, {"error": {"code": 190, "message": " ".join(SENSITIVE)}})])
def test_a_failed_call_deletes_the_attempt_and_leaves_the_earlier_page(client, graph, call, status, body):
    run(client, "INSERT INTO facebook_pages VALUES (1,'777','Ancienne Page','page-token-of-the-page-777','connected',:now)",
        now=OLD)
    before = pages(client)
    graph.answers[call] = httpx2.Response(status, **({"json": body} if isinstance(body, dict) else {"content": body}))
    refused(send(client, connect(client)), "facebook_failed", 502)
    assert attempts(client) == [] and pages(client) == before
    said = client.get("/api/facebook").json()
    assert said == {"page": {"id": "777", "name": "Ancienne Page", "state": "connected"}, "choice": None,
                    "last_error": {"code": "facebook_failed", "message_fr": "La connexion à Facebook n’a pas abouti. Réessayez."}}
    assert client.get("/api/facebook").json()["last_error"] is None  # said once


def test_no_page_with_create_content_is_said_and_stores_nothing(client, graph):
    graph.answers["pages"] = httpx2.Response(200, json={"data": [ACCOUNTS["data"][1]]})
    refused(send(client, connect(client)), "facebook_no_page", 422)
    assert attempts(client) == [] and pages(client) == []
    assert client.get("/api/facebook").json()["last_error"]["code"] == "facebook_no_page"


@pytest.mark.parametrize("meanwhile, kept", [
    ("UPDATE facebook_connects SET state_sha='newer', step='dialog'", 1),  # a new « Connecter » (another device)
    ("DELETE FROM facebook_connects", 0),  # « Déconnecter »
    ("DELETE FROM sessions", 0),  # a sign-out: the attempt, still this one, goes
    ("UPDATE facebook_connects SET created_at='2026-01-01T00:00:00.000000+00:00'", 0),  # the clock
])
def test_what_happens_during_the_calls_wins_over_their_result(client, graph, meanwhile, kept):
    graph.during = lambda request: run(client, meanwhile) if request.url.path == "/v27.0/me/accounts" else None
    refused(send(client, connect(client)), "facebook_state")
    assert pages(client) == [] and [row["state_sha"] for row in attempts(client)] == ["newer"] * kept


def test_a_cancelled_or_failed_dialog_is_said_on_the_card_without_a_call(client, graph):
    refused(send(client, connect(client), code=None, error="access_denied"), "facebook_cancelled")
    assert attempts(client) == [] and graph.requests == []
    assert client.get("/api/facebook").json()["last_error"] == {"code": "facebook_cancelled", "message_fr": "Connexion annulée."}
    refused(send(client, connect(client), code=None, error="server_error"), "facebook_dialog_failed", 502)
    assert client.get("/api/facebook").json()["last_error"]["message_fr"] == "La connexion n’a pas abouti."
    refused(send(client, "never-given", code=None, error="access_denied"), "facebook_state")
    for body in ({"state": "s"}, {"state": "s", "code": CODE, "error": "access_denied"}, {"code": CODE}):
        refused(client.post("/api/facebook/code", json=body), "validation_error", 422)
    with client.app.state.engine.connect() as conn:
        assert conn.execute(text("SELECT value FROM meta WHERE key='facebook_mode'")).scalar() is None  # no call: no mode


def test_a_refusal_is_said_to_the_session_that_met_it_only(client, graph):
    other = device(client)
    refused(send(client, "never-given"), "facebook_state")
    assert other.get("/api/facebook").json()["last_error"] is None
    assert client.get("/api/facebook").json()["last_error"] == {"code": "facebook_state", "message_fr": "Recommencez la connexion."}


def test_a_choice_is_listed_for_its_session_only_and_for_ten_minutes(client, graph):
    send(client, connect(client))
    assert device(client).get("/api/facebook").json()["choice"] is None
    assert client.get("/api/facebook").json()["choice"] == CHOICE
    run(client, "UPDATE facebook_connects SET created_at=:old", old=OLD)
    assert client.get("/api/facebook").json()["choice"] is None and attempts(client) == []  # and deleted by the read


def test_disconnect_removes_the_page_and_the_attempt_and_can_be_sent_twice(client, graph):
    send(client, connect(client))
    client.post("/api/facebook/page", json={"page_id": "111"})
    connect(client)
    for _ in range(2):
        answer = client.delete("/api/facebook/page")
        assert answer.status_code == 200 and answer.json() == {"page": None, "choice": None}
    assert attempts(client) == [] and pages(client) == []


def old_attempt(client, shop):
    run(client, "INSERT OR REPLACE INTO facebook_connects VALUES (:shop,'s','t','choice','[]',:old)", shop=shop, old=OLD)


def test_attempts_older_than_ten_minutes_go_at_connect_and_at_read(client, graph):
    other_shop, _password = second_shop(client.app.state.engine)
    old_attempt(client, other_shop)
    connect(client)
    assert [row["shop_id"] for row in attempts(client)] == [1]
    old_attempt(client, other_shop)
    client.get("/api/facebook")
    assert [row["shop_id"] for row in attempts(client)] == [1]


def test_attempts_older_than_ten_minutes_go_at_start(env, tmp_path, password_hash, graph):
    settings = settings_for(env, tmp_path, password_hash, "meta")
    with TestClient(create_app(settings, prepare=credited), base_url=ORIGIN, headers=HEADERS) as client:
        login(client)
        connect(client)
        old_attempt(client, second_shop(client.app.state.engine)[0])
    with TestClient(create_app(settings), base_url=ORIGIN, headers=HEADERS) as again:  # the server starts again
        assert [row["shop_id"] for row in attempts(again)] == [1]


def test_the_routes_are_changes_of_the_shops_own_tab(client, graph):
    """No Idempotency-Key, but every rule of the boundary: an Origin, a current bundle, a session."""
    state = connect(client)
    for headers, code, status in (({"Origin": "https://evil.example"}, "forbidden_origin", 403),
                                  ({"X-Affiche-Bundle": "2"}, "bundle_outdated", 409)):
        refused(client.post("/api/facebook/code", json={"state": state, "code": CODE}, headers=headers), code, status)
    refused(TestClient(client.app, base_url=ORIGIN, headers=HEADERS).post("/api/facebook/connect"), "unauthenticated", 401)
    assert send(client, state).status_code == 200  # none of these reached the attempt


def test_another_mode_on_the_same_data_folder_is_refused_and_leaves_the_attempt(client, graph):
    run(client, "INSERT INTO meta VALUES ('facebook_mode','stub')")
    state = connect(client)
    before = attempts(client)
    refused(send(client, state), "provider_mode_mismatch")
    assert attempts(client) == before and graph.requests == []
