"""The Graph client (D-FB-PUBLISH-001 to 003): the proof, the answers' table, each call's shape, the stand-in and the
mode of a data folder. Facebook is httpx2.MockTransport: nothing leaves the machine."""
import asyncio
import hashlib
import hmac
import logging
import re
from urllib.parse import parse_qs

import httpx2
import pytest
from pydantic import SecretStr
from sqlalchemy import text

from affiche.config import load_settings
from affiche.db import make_engine, migrate, write_tx
from affiche.posters.facebook import (GraphFailure, MetaGraph, Outcome, Page, StubGraph, appsecret_proof, check_mode,
                                      classify, make_graph)
from affiche.posters.store import Refused
from test_config import env  # noqa: F401

APP, SECRET = "1234567890", "app-secret-never-printed"
CODE, USER_TOKEN, PAGE_TOKEN = "dialog-code-never-printed", "user-token-never-printed", "page-token-never-printed"
SENSITIVE = (SECRET, CODE, USER_TOKEN, PAGE_TOKEN)
PAGE = "1000000001"
PNG = b"\x89PNG\r\n\x1a\nthe confirmed file"
REDIRECT = "https://affiches.example/facebook.html"
# An error answer that carries every sensitive value in the text Facebook may send back, which is never read.
LEAKY = {"error": {"message": " ".join(SENSITIVE), "type": "OAuthException", "code": 190, "error_subcode": 463,
                   "fbtrace_id": "AbC_1-x"}}
DEEP = b"[" * 100000  # deeper than the JSON decoder recurses


def graph(answer):
    """The real client, its Facebook `answer`: a Response, an exception raised, or a function of the request."""
    requests = []

    def handle(request):
        requests.append(request)
        if isinstance(answer, Exception):
            raise answer
        return answer(request) if callable(answer) else answer

    return MetaGraph(APP, SecretStr(SECRET), transport=httpx2.MockTransport(handle)), requests


def publish(answer, caption="Promo du jour"):
    client, requests = graph(answer)
    return asyncio.run(client.publish_photo(PAGE, PAGE_TOKEN, PNG, caption)), requests


def fields(request) -> dict:
    """A multipart body's text fields, by name (the file apart)."""
    boundary = request.headers["content-type"].split("boundary=", 1)[1].encode()
    found = {}
    for part in request.content.split(b"--" + boundary)[1:-1]:
        head, _, value = part.strip(b"\r\n").partition(b"\r\n\r\n")
        if b"filename=" not in head:
            found[head.split(b'name="', 1)[1].split(b'"', 1)[0].decode()] = value.decode()
    return found


def test_the_proof_is_the_tokens_hmac_sha256_keyed_by_the_secret():
    expected = hmac.new(b"the-secret", b"the-token", hashlib.sha256).hexdigest()
    assert appsecret_proof("the-token", "the-secret") == expected and len(expected) == 64
    assert appsecret_proof("the-secret", "the-token") != expected  # keyed by the secret, not by the token


def answer(status, body):
    return httpx2.Response(status, json=body) if isinstance(body, (dict, list)) else httpx2.Response(status, content=body)


def error(code):
    return {"error": {"code": code, "message": "ignored", "fbtrace_id": "T1"}}


# The table of D-FB-PUBLISH-003 §4, row by row in its reading order.
TABLE = [
    (answer(503, error(190)), Outcome("unknown")),  # a 5xx, whatever its body: even a 190
    (answer(500, error(4)), Outcome("unknown")),
    (answer(502, b"<html>Bad gateway</html>"), Outcome("unknown")),
    (httpx2.ReadTimeout("no answer"), Outcome("unknown")),
    (httpx2.WriteTimeout("sent in part"), Outcome("unknown")),
    (httpx2.ConnectTimeout("no answer"), Outcome("unknown")),
    (httpx2.ConnectError("no answer"), Outcome("unknown")),
    (httpx2.RemoteProtocolError("a cut connection"), Outcome("unknown")),
    (httpx2.ReadError("a cut connection"), Outcome("unknown")),
    (answer(503, DEEP), Outcome("unknown")),  # nesting too deep: nothing raised, even on the 5xx's logging path
    (answer(200, b"{not json"), Outcome("unknown")),  # an answer that cannot be read
    (answer(200, b"\xff\xfe"), Outcome("unknown")),
    (answer(200, f'{{"post_id": "{PAGE}_77", "views": NaN}}'.encode()), Outcome("unknown")),  # not JSON
    (answer(200, f'{{"post_id": "{PAGE}_77", "rate": -Infinity}}'.encode()), Outcome("unknown")),
    (answer(200, f'{{"post_id": "2000000002_77", "post_id": "{PAGE}_77"}}'.encode()), Outcome("unknown")),  # which?
    (answer(200, DEEP), Outcome("unknown")),
    (answer(400, b"<html>"), Outcome("unknown")),
    (answer(400, DEEP), Outcome("unknown")),
    (answer(400, b'{"error": {"code": 506, "rate": NaN}}'), Outcome("unknown")),
    (answer(400, b'{"error": {"code": 1, "code": 506}}'), Outcome("unknown")),
    (answer(200, {"id": "77", "post_id": f"{PAGE}_77"}),
     Outcome("published", f"{PAGE}_77", f"https://www.facebook.com/{PAGE}_77")),
    (answer(200, {"id": "77"}), Outcome("unknown")),  # the proof's unpublished photo: its id alone
    (answer(200, {"post_id": "2000000002_77"}), Outcome("unknown")),  # another Page's post
    (answer(200, {"post_id": f"{PAGE}0_77"}), Outcome("unknown")),
    (answer(200, {"post_id": f"{PAGE}_"}), Outcome("unknown")),
    (answer(200, {"post_id": f"{PAGE}_7a"}), Outcome("unknown")),
    (answer(200, {"post_id": f"{PAGE}_77_1"}), Outcome("unknown")),
    (answer(200, {"post_id": 77}), Outcome("unknown")),
    (answer(200, [f"{PAGE}_77"]), Outcome("unknown")),
    (answer(200, error(190)), Outcome("unknown")),  # a 200 is read before any error
    # Past the two 200 rows, only a 4xx with Graph's error is a refusal: any other status is unknown, whatever its body.
    (answer(201, {"id": "77", "post_id": f"{PAGE}_77"}), Outcome("unknown")),
    (answer(202, error(190)), Outcome("unknown")),
    (answer(307, error(506)), Outcome("unknown")),
    (answer(102, error(4)), Outcome("unknown")),
    (answer(400, error(190)), Outcome("failed", error_code="190", reconnect=True)),
    (answer(401, LEAKY), Outcome("failed", error_code="190", reconnect=True)),
    *((answer(400, error(code)), Outcome("failed", error_code=str(code))) for code in (4, 17, 32, 613, 80001, 368)),
    *((answer(403, error(code)), Outcome("failed", error_code=str(code)))
      for code in (10, 200, 230, 299, 100, 324, 506)),
    # A code that is not one of the module's own is not kept: the answer is unknown, and nothing of it is stored.
    *((answer(400, error(code)), Outcome("unknown")) for code in (1, 2, 9, 199, 300, 2500, 0, -190, 1234567, 10 ** 30)),
    (answer(400, {"error": {"code": "190"}}), Outcome("unknown")),  # no readable code
    (answer(400, {"error": {"code": True}}), Outcome("unknown")),
    (answer(400, {"error": "190"}), Outcome("unknown")),
    (answer(400, {"message": "no error object"}), Outcome("unknown")),
    (httpx2.Response(302, headers={"Location": "https://elsewhere.example/"}), Outcome("unknown")),  # not followed
]


@pytest.mark.parametrize("facebook, outcome", TABLE)
def test_each_answer_is_settled_as_the_table_says(facebook, outcome):
    settled, requests = publish(facebook)
    assert settled == outcome and len(requests) == 1  # one send, never a second
    if not isinstance(facebook, Exception):
        assert classify(facebook, PAGE) == outcome
    assert classify(None, PAGE) == Outcome("unknown")


def test_the_photo_is_one_multipart_post_of_the_file_with_the_proof(caplog):
    settled, [request] = publish(answer(200, {"id": "77", "post_id": f"{PAGE}_77"}), caption="Ligne 1\nLigne 2")
    assert settled.status == "published"
    assert (request.method, str(request.url)) == ("POST", f"https://graph.facebook.com/v27.0/{PAGE}/photos")
    assert request.extensions["timeout"] == {"connect": 60, "read": 60, "write": 60, "pool": 60}
    assert fields(request) == {"access_token": PAGE_TOKEN, "appsecret_proof": appsecret_proof(PAGE_TOKEN, SECRET),
                               "caption": "Ligne 1\nLigne 2"}
    assert (b'name="source"; filename="affiche.png"\r\nContent-Type: image/png\r\n\r\n' + PNG + b"\r\n"
            in request.content)  # the confirmed file itself, byte for byte
    assert "authorization" not in request.headers
    assert not any(value in str(request.url) for value in SENSITIVE)
    _, [request] = publish(answer(200, {"post_id": f"{PAGE}_78"}), caption="")
    assert "caption" not in fields(request)  # an empty caption is not sent


@pytest.mark.parametrize("page_id", ["", "12a", "../me", "1/feed", None])
def test_a_page_id_that_is_not_digits_sends_nothing(page_id):
    client, requests = graph(answer(200, {"post_id": "1_1"}))
    for stand_in in (client, StubGraph()):  # a definite failure, raised from no frame that holds the token
        assert asyncio.run(stand_in.publish_photo(page_id, PAGE_TOKEN, PNG, "")) == Outcome("failed", error_code="not_sent")
    assert requests == []


@pytest.mark.parametrize("token", ["", "with space in a long token", "a-long-token-with\ud800-a-surrogate", None, "t" * 19,
                                   "7" * 24])  # digits only: not a credential's shape, so an id can never be one
def test_a_page_token_of_the_wrong_shape_sends_nothing_and_raises_nothing(token):
    client, requests = graph(answer(200, {"post_id": f"{PAGE}_1"}))
    assert asyncio.run(client.publish_photo(PAGE, token, PNG, "")) == Outcome("failed", error_code="not_sent")
    assert requests == []


def test_a_page_id_too_long_for_an_address_sends_nothing_and_raises_nothing():
    client, requests = graph(answer(200, {"post_id": "1_1"}))
    assert asyncio.run(client.publish_photo("9" * 65536, PAGE_TOKEN, PNG, "")) == Outcome("failed", error_code="not_sent")
    assert asyncio.run(client.publish_photo("9" * 33, PAGE_TOKEN, PNG, "")) == Outcome("failed", error_code="not_sent")
    assert requests == []


# An answer in which every field gives a credential back, as text and as numbers: the module says only its own words.
def hostile(*credentials):
    text = " ".join(credentials)
    return {"error": {"code": 190, "error_subcode": 10 ** 40, "fbtrace_id": text, "message": text, "type": text,
                      "error_user_title": text, text: text, "error_data": [text, {"x": text}]}, "post_id": text, text: 1}


OWN_WORDS = re.compile(r"facebook (code|long_lived|pages|photo): [a-z0-9 ]+(without a post id of this Page)?")
said = lambda caplog: [record.getMessage() for record in caplog.records if record.name == "affiche.posters.facebook"]


def test_the_photo_says_only_its_own_words_whatever_the_answer_gives_back(caplog):
    caplog.set_level(logging.DEBUG)
    proof = appsecret_proof(PAGE_TOKEN, SECRET)
    for status in (200, 400, 401, 500, 302):
        outcome, _requests = publish(answer(status, hostile(PAGE_TOKEN, proof, SECRET)))
        assert outcome in (Outcome("unknown"), Outcome("failed", error_code="190", reconnect=True))
        assert not any(secret in repr(outcome) for secret in (PAGE_TOKEN, proof, SECRET))
    assert said(caplog) and all(OWN_WORDS.fullmatch(line) for line in said(caplog)), said(caplog)
    assert not any(secret in caplog.text for secret in (PAGE_TOKEN, proof, SECRET, str(10 ** 40)))


def test_a_post_id_that_is_a_credential_whole_is_unknown_and_makes_no_link():
    token = f"{PAGE}_{'7' * 20}"  # a credential's shape (its underscore is not a digit) that is also a post id's
    client, _requests = graph(answer(200, {"post_id": token}))
    assert asyncio.run(client.publish_photo(PAGE, token, PNG, "")) == Outcome("unknown")


@pytest.mark.parametrize("png, caption", [(None, ""), ("text", ""), (PNG, None), (PNG, 5)])
def test_a_file_or_caption_of_the_wrong_type_sends_nothing_and_raises_nothing(png, caption):
    client, requests = graph(answer(200, {"post_id": f"{PAGE}_1"}))
    assert asyncio.run(client.publish_photo(PAGE, PAGE_TOKEN, png, caption)) == Outcome("failed", error_code="not_sent")
    assert requests == []


def test_nothing_the_client_raises_leaves_the_module():
    """A `Location` the client cannot join, or any other error of its own: unknown for the photo, a failure for a call."""
    far = httpx2.Response(302, headers={"Location": "/" + "a" * 70000})
    assert publish(far)[0] == Outcome("unknown")
    assert publish(RuntimeError(PAGE_TOKEN))[0] == Outcome("unknown")
    for call in CALLS.values():
        for facebook in (far, RuntimeError(SECRET)):
            client, _requests = graph(facebook)
            assert asyncio.run(call(client)) in (GraphFailure("network"), GraphFailure("http"))


def test_an_answer_that_is_not_utf8_is_unknown_even_with_a_matching_post_id():
    body = b'{"post_id": "' + f"{PAGE}_1".encode() + b'", "x": "\xed\xa0\x80"}'  # a lone surrogate's bytes
    outcome, _requests = publish(httpx2.Response(200, content=body))
    assert outcome == Outcome("unknown")


def test_a_caption_that_cannot_be_encoded_sends_nothing_and_raises_nothing():
    outcome, requests = publish(answer(200, {"post_id": f"{PAGE}_1"}), caption="Promo \ud800")
    assert outcome == Outcome("failed", error_code="caption") and not requests


def form(request) -> dict:
    return {name: values[0] for name, values in parse_qs(request.content.decode(), strict_parsing=True).items()}


def test_the_code_exchange_posts_a_form_and_puts_nothing_in_the_address():
    client, requests = graph(answer(200, {"access_token": USER_TOKEN, "token_type": "bearer", "expires_in": 5183}))
    assert asyncio.run(client.exchange_code(CODE, REDIRECT)) == USER_TOKEN
    [request] = requests
    assert (request.method, str(request.url)) == ("POST", "https://graph.facebook.com/v27.0/oauth/access_token")
    assert request.headers["content-type"] == "application/x-www-form-urlencoded"
    assert form(request) == {"client_id": APP, "client_secret": SECRET, "redirect_uri": REDIRECT, "code": CODE}
    assert request.extensions["timeout"]["read"] == 20 and "authorization" not in request.headers


def test_the_long_lived_exchange_posts_the_token_with_its_proof():
    client, requests = graph(answer(200, {"access_token": "long-lived-token-of-the-user", "token_type": "bearer"}))
    assert asyncio.run(client.long_lived(USER_TOKEN)) == "long-lived-token-of-the-user"
    [request] = requests
    assert (request.method, str(request.url)) == ("POST", "https://graph.facebook.com/v27.0/oauth/access_token")
    assert form(request) == {"client_id": APP, "client_secret": SECRET, "grant_type": "fb_exchange_token",
                             "fb_exchange_token": USER_TOKEN, "appsecret_proof": appsecret_proof(USER_TOKEN, SECRET)}
    assert request.extensions["timeout"]["read"] == 20


ACCOUNTS = {"data": [
    {"id": "111", "name": "Original Phone Mada", "tasks": ["ADVERTISE", "ANALYZE", "CREATE_CONTENT", "MODERATE"],
     "access_token": "page-token-of-the-page-111"},
    {"id": "222", "name": "Messages only", "tasks": ["MESSAGING", "ANALYZE"]},  # no token asked of a Page not kept
    {"id": "333", "name": "Boutique Deux", "tasks": ["CREATE_CONTENT"], "access_token": "page-token-of-the-page-333"},
], "paging": {"cursors": {"before": "a", "after": "b"}}}


def test_the_pages_are_those_the_person_can_post_on_each_with_its_token():
    client, requests = graph(answer(200, ACCOUNTS))
    pages = asyncio.run(client.pages(USER_TOKEN))
    assert pages == [Page("111", "Original Phone Mada", "page-token-of-the-page-111"), Page("333", "Boutique Deux", "page-token-of-the-page-333")]
    assert "page-token" not in repr(pages)
    [request] = requests
    assert (request.method, request.url.host, request.url.path) == ("GET", "graph.facebook.com", "/v27.0/me/accounts")
    assert {name: values[0] for name, values in parse_qs(request.url.query.decode()).items()} == {
        "fields": "id,name,tasks,access_token", "limit": "100", "appsecret_proof": appsecret_proof(USER_TOKEN, SECRET)}
    assert request.headers["authorization"] == f"Bearer {USER_TOKEN}" and request.content == b""
    assert not any(value in str(request.url) for value in SENSITIVE)
    assert request.extensions["timeout"]["read"] == 20


def test_a_page_name_that_holds_another_pages_token_is_not_kept():
    other = "page-token-of-the-page-222"
    for tasks in (["CREATE_CONTENT"], ["MESSAGING"]):  # the other Page kept, or left out: its token is a credential all the same
        data = [ACCOUNTS["data"][0] | {"name": f"Boutique {other}"}, {"id": "222", "name": "Autre", "tasks": tasks, "access_token": other}]
        client, _requests = graph(answer(200, {"data": data}))
        assert asyncio.run(client.pages(USER_TOKEN)) == GraphFailure("invalid")


def test_with_no_page_to_post_on_the_list_is_empty():
    client, _ = graph(answer(200, {"data": [ACCOUNTS["data"][1]]}))
    assert asyncio.run(client.pages(USER_TOKEN)) == []


CALLS = {"exchange_code": lambda client: client.exchange_code(CODE, REDIRECT),
         "long_lived": lambda client: client.long_lived(USER_TOKEN),
         "pages": lambda client: client.pages(USER_TOKEN)}
FAILURES = [
    (httpx2.ConnectTimeout("t"), ("timeout", None)),
    (httpx2.ReadTimeout("t"), ("timeout", None)),
    (httpx2.ConnectError("c"), ("network", None)),
    (httpx2.RemoteProtocolError("cut"), ("network", None)),
    (answer(400, LEAKY), ("graph", 190)),
    (answer(500, error(2)), ("graph", None)),  # a code that is not one of the module's own is not kept
    (answer(400, error(10 ** 30)), ("graph", None)),
    (answer(400, {"error": {"code": 100, "fbtrace_id": "line\nbreak"}}), ("graph", 100)),
    (answer(400, hostile(SECRET, CODE, USER_TOKEN)), ("graph", 190)),
    (answer(502, b"<html>Bad gateway</html>"), ("http", None)),
    (httpx2.Response(302, headers={"Location": "https://elsewhere.example/"}), ("http", None)),
    (answer(200, b"{not json"), ("invalid", None)),
    (answer(200, ["a list"]), ("invalid", None)),
    # A success that cannot be read: NaN, a key twice, nesting too deep.
    (answer(200, b'{"access_token": "t", "data": [], "expires_in": NaN}'), ("invalid", None)),
    (answer(200, b'{"access_token": "t", "access_token": "u", "data": []}'), ("invalid", None)),
    (answer(200, DEEP), ("invalid", None)),
]


@pytest.mark.parametrize("call", CALLS)
@pytest.mark.parametrize("facebook, expected", FAILURES)
def test_a_connection_call_that_fails_returns_its_failure_without_a_secret(call, facebook, expected, caplog):
    caplog.set_level(logging.DEBUG)
    client, requests = graph(facebook)
    failure = asyncio.run(CALLS[call](client))
    assert failure == GraphFailure(*expected) and len(requests) == 1
    for shown in (str(failure), repr(failure), caplog.text):
        assert not any(value in shown for value in SENSITIVE) and "OAuthException" not in shown
    assert said(caplog) and all(OWN_WORDS.fullmatch(line) for line in said(caplog)), said(caplog)  # only its own words
    if expected[1] is not None:
        assert str(expected[1]) in caplog.text


def test_an_expected_failure_raises_nothing():
    """Returned, not raised: no traceback keeps the frames that hold the secret, the code, a token or the Pages."""
    for facebook, call in ((httpx2.ReadTimeout("t"), "exchange_code"), (httpx2.ConnectTimeout("t"), "pages"),
                           (answer(200, {"data": [{"id": "1", "name": "P", "tasks": ["CREATE_CONTENT"]}]}), "pages")):
        client, _ = graph(facebook)
        assert isinstance(asyncio.run(CALLS[call](client)), GraphFailure)


@pytest.mark.parametrize("call, value", [
    ("exchange_code", "code-of-the-dialog\ud800surrogate"), ("exchange_code", "two words in a long code"), ("exchange_code", ""),
    ("exchange_code", "c" * 2001), ("exchange_code", None), ("exchange_code", "a-long-code-with-a-line\nbreak"),
    ("exchange_code", "123456"), ("exchange_code", "c" * 19),  # shorter than any real code
    ("exchange_code", "1" * 30), ("long_lived", "1" * 30), ("pages", "1" * 30),  # digits only: an id could be it
    ("long_lived", "token-of-the-user-long\ud800"), ("long_lived", "two words in a long token"), ("long_lived", ""),
    ("long_lived", "t" * 19), ("pages", "token-of-the-user-long\ud800"), ("pages", "two words in a long token"), ("pages", None),
])
def test_a_code_or_token_of_the_wrong_shape_sends_nothing(call, value, caplog):
    caplog.set_level(logging.DEBUG)
    client, requests = graph(answer(200, {"access_token": "t" * 20, "data": []}))
    failure = asyncio.run(getattr(client, call)(*((value, REDIRECT) if call == "exchange_code" else (value,))))
    assert failure == GraphFailure("invalid") and requests == []
    for shown in (str(failure), repr(failure), caplog.text):
        assert value is None or not value or value not in shown
    assert asyncio.run(client.exchange_code("c" * 2000, REDIRECT)) == "t" * 20  # the cap's own length passes
    assert asyncio.run(client.exchange_code("c" * 20, REDIRECT)) == "t" * 20  # and the floor's


@pytest.mark.parametrize("address", ["https://affiches.example/\ud800", "not an address", "", None, "https://" + "a" * 501])
def test_a_return_address_of_the_wrong_shape_sends_nothing_and_raises_nothing(address):
    client, requests = graph(answer(200, {"access_token": USER_TOKEN}))
    assert asyncio.run(client.exchange_code(CODE, address)) == GraphFailure("invalid") and requests == []


@pytest.mark.parametrize("change", [
    {"name": f"Boutique {USER_TOKEN}"}, {"name": "page-token-of-the-page-111"}, {"name": SECRET},
    {"name": appsecret_proof(USER_TOKEN, SECRET)}, {"name": "x" * 201}, {"name": "two\nlines"}, {"name": "   "},
    {"id": "1" * 33}, {"id": "12a"}, {"access_token": "7" * 24}, {"access_token": "short"},
])
def test_a_page_whose_id_or_name_is_not_of_its_shape_or_holds_a_credential_is_not_kept(change, caplog):
    caplog.set_level(logging.DEBUG)
    page = ACCOUNTS["data"][0] | change
    client, _requests = graph(answer(200, {"data": [page]}))
    assert asyncio.run(client.pages(USER_TOKEN)) == GraphFailure("invalid")
    assert not any(secret in caplog.text for secret in (USER_TOKEN, SECRET, "page-token-of-the-page-111"))


def test_every_client_ignores_the_environments_proxy(monkeypatch):
    """trust_env=False, read from the client's options: a MockTransport would bypass a proxy, so no request can show it."""
    options, real = [], httpx2.AsyncClient
    monkeypatch.setattr(httpx2, "AsyncClient", lambda **kwargs: options.append(kwargs) or real(**kwargs))
    client, _ = graph(answer(200, {"access_token": "t" * 20, "data": [], "post_id": f"{PAGE}_1"}))
    for call in (*CALLS.values(), lambda client: client.publish_photo(PAGE, PAGE_TOKEN, PNG, "")):
        asyncio.run(call(client))
    assert len(options) == 4 and all(kwargs["trust_env"] is False and kwargs["follow_redirects"] is False
                                     for kwargs in options)
    assert [kwargs["timeout"] for kwargs in options] == [20, 20, 20, 60]


@pytest.mark.parametrize("call, body", [
    ("exchange_code", {}), ("exchange_code", {"access_token": ""}), ("exchange_code", {"access_token": 5}),
    ("exchange_code", {"access_token": "two words"}), ("exchange_code", {"access_token": "t​"}),
    ("long_lived", {"token_type": "bearer"}), ("long_lived", {"access_token": None}),
    ("pages", {}), ("pages", {"data": "111"}), ("pages", {"data": ["111"]}),
    ("pages", {"data": [{"id": "111", "name": "P", "access_token": "t"}]}),  # no tasks
    ("pages", {"data": [{"id": "111", "name": "P", "tasks": "CREATE_CONTENT", "access_token": "t"}]}),
    ("pages", {"data": [{"id": "111", "name": "P", "tasks": [None], "access_token": "t"}]}),  # unread, not "no Page"
    ("pages", {"data": [{"id": "111", "name": "P", "tasks": ["CREATE_CONTENT", None], "access_token": "t"}]}),
    ("pages", {"data": [ACCOUNTS["data"][0], {"id": "222", "name": "M", "tasks": [7]}]}),  # even on a Page not kept
    ("pages", {"data": [{"id": 111, "name": "P", "tasks": ["CREATE_CONTENT"], "access_token": "t"}]}),
    ("pages", {"data": [{"id": "11a", "name": "P", "tasks": ["CREATE_CONTENT"], "access_token": "t"}]}),
    ("pages", {"data": [{"id": "111", "name": " ", "tasks": ["CREATE_CONTENT"], "access_token": "t"}]}),
    ("pages", {"data": [{"id": "111", "name": "P", "tasks": ["CREATE_CONTENT"]}]}),
    ("pages", {"data": [{"id": "111", "name": "P", "tasks": ["CREATE_CONTENT"], "access_token": ""}]}),
])
def test_a_malformed_success_is_a_failure_not_a_guess(call, body, caplog):
    caplog.set_level(logging.DEBUG)
    client, _ = graph(answer(200, body))
    assert asyncio.run(CALLS[call](client)) == GraphFailure("invalid")
    assert not any(value in caplog.text for value in SENSITIVE)


def test_the_photo_logs_codes_never_the_message_or_a_token(caplog):
    caplog.set_level(logging.DEBUG)
    for facebook in (answer(401, LEAKY), answer(503, LEAKY), httpx2.ReadTimeout(PAGE_TOKEN), answer(200, b"x")):
        publish(facebook, caption=CODE)
    assert said(caplog) == ["facebook photo: 4xx 190", "facebook photo: 5xx", "facebook photo: timeout",
                            "facebook photo: 200 without a post id of this Page"]  # its own words, and no other
    assert not any(value in caplog.text for value in SENSITIVE) and "OAuthException" not in caplog.text


def test_the_stand_in_has_two_pages_and_publishes_with_its_pages_post_id():
    stub = StubGraph()
    assert asyncio.run(stub.exchange_code(CODE, REDIRECT)) and asyncio.run(stub.long_lived("t"))
    pages = asyncio.run(stub.pages("t"))
    assert len(pages) == 2 and len({page.id for page in pages}) == 2 and pages == asyncio.run(stub.pages("t"))
    assert all(page.id.isdigit() and page.name and page.token for page in pages)
    first, second = (asyncio.run(stub.publish_photo(pages[0].id, pages[0].token, PNG, "")) for _ in range(2))
    assert first.status == "published" and first.post_id != second.post_id
    assert first == classify(httpx2.Response(200, json={"post_id": first.post_id}), pages[0].id)  # the real shape


def test_the_client_follows_the_setting(env):
    with pytest.raises(Refused) as caught:
        make_graph(load_settings(env_file=None))  # off, the default
    assert (caught.value.code, caught.value.status) == ("not_found", 404)
    env.setenv("FACEBOOK_PROVIDER", "stub")
    assert isinstance(make_graph(load_settings(env_file=None)), StubGraph)
    env.setenv("FACEBOOK_PROVIDER", "meta")
    env.setenv("FACEBOOK_APP_ID", APP)
    env.setenv("FACEBOOK_APP_SECRET", SECRET)
    requests = []
    transport = httpx2.MockTransport(lambda request: requests.append(request) or answer(200, {"post_id": f"{PAGE}_1"}))
    real = make_graph(load_settings(env_file=None), transport)
    assert isinstance(real, MetaGraph) and asyncio.run(real.publish_photo(PAGE, PAGE_TOKEN, PNG, "")).status == "published"
    assert fields(requests[0])["appsecret_proof"] == appsecret_proof(PAGE_TOKEN, SECRET)


def test_a_data_folder_keeps_the_mode_of_its_first_facebook_call(tmp_path):
    engine = make_engine(tmp_path)
    try:
        migrate(engine)
        for _ in range(2):  # recorded, then the same mode passes
            with write_tx(engine) as conn:
                check_mode(conn, StubGraph())
        with pytest.raises(Refused) as caught, write_tx(engine) as conn:
            check_mode(conn, MetaGraph(APP, SecretStr(SECRET)))
        assert (caught.value.code, caught.value.status) == ("provider_mode_mismatch", 409)
        with engine.connect() as conn:
            assert conn.execute(text("SELECT value FROM meta WHERE key='facebook_mode'")).scalars().all() == ["stub"]
    finally:
        engine.dispose()
