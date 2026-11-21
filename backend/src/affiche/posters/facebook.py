"""The Graph API client of the Facebook publishing (D-FB-PUBLISH-001 to 003): the connection's three calls and the photo's
send, to Meta (`meta`) or to a local stand-in (`stub`). No database here but the mode guard: the routes admit, store
and settle.

Nothing is retried: a send without an answer is the owner's to judge (D-FB-PUBLISH-003 §5). The module logs, returns
and stores only its own words and its own known codes; of an answer it keeps a Page's id, a Page's name and a post's
id, each through one gate (see « What this module keeps and says »). No token, code, `state` or secret is put in an
exception or a log line, and none in an address. An expected failure of a connection call is returned as a
GraphFailure, never raised: a traceback would keep the frames that hold the secret, the code, a token or the Pages'
answer."""
import hashlib
import hmac
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Literal
from uuid import uuid4

import httpx2
from pydantic import SecretStr
from sqlalchemy import text

from .store import Refused

log = logging.getLogger(__name__)
GRAPH = "https://graph.facebook.com/v27.0"
CONNECT_TIMEOUT_S = 20  # each call of the connection (D-FB-PUBLISH-002 step 2)
PHOTO_TIMEOUT_S = 60
RECONNECT_CODE = 190  # the access is cancelled, or its owner lost his role
LIMIT_CODES = frozenset({4, 17, 32, 613, 80001, 368})  # limits, and 368: blocked
REFUSED_CODES = frozenset({10, *range(200, 300), 100, 324, 506})  # a permission, a parameter, the image, a duplicate
KNOWN_CODES = frozenset({RECONNECT_CODE}) | LIMIT_CODES | REFUSED_CODES

# ── What this module keeps and says (reviews r1 to r4) ──────────────────────────────────────────────────────────────
# It logs, returns and stores only its own words: the names below and the codes of KNOWN_CODES, which are this file's
# constants. An answer of Facebook is only compared with them; nothing of it is copied into a log line, a failure or an
# error code. Three values of an answer are kept, because the feature is made of them: a Page's id, a Page's name and a
# post's id. Each passes one gate, `_kept`: its own bounded shape, and no credential of the call inside it.
# A credential (a token, the dialog's code, the Meta app's secret) has one shape, CREDENTIAL: printable ASCII, 20
# characters at least, not digits only. So an id, which is digits only, can never be one.
CREDENTIAL = re.compile(r"[!-~]{20,4096}")
DIGITS = re.compile(r"[0-9]{1,32}")  # a Page's id
POST_ID = re.compile(r"[0-9]{1,32}_[0-9]{1,32}")  # a post's id: its Page's id, then its number
NAME = re.compile(r"[^\x00-\x1f\x7f-\x9f]{1,200}")  # a Page's name: one line, no control character
ADDRESS = re.compile(r"https?://[!-~]{1,500}")  # the return address, this application's own


def credential(value: object, longest: int = 4096) -> bool:
    return isinstance(value, str) and len(value) <= longest and CREDENTIAL.fullmatch(value) is not None and not value.isdigit()


def _kept(value: object, shape: re.Pattern, sent: tuple[str, ...]) -> bool:
    """The one gate of the three values kept from an answer."""
    return isinstance(value, str) and shape.fullmatch(value) is not None and not any(secret in value for secret in sent)


def appsecret_proof(token: str, secret: str) -> str:
    """Meta's « app secret proof »: the hex HMAC-SHA256 of the token keyed by the Meta app's secret."""
    return hmac.new(secret.encode("utf-8"), token.encode("utf-8"), hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class GraphFailure:
    """A connection call that did not give what it should, returned, never raised. kind: timeout, network, http (an
    answer that is not Graph's error), graph (Graph's error; `code` only when it is one of KNOWN_CODES) or invalid (a
    value sent or received that is not of its shape)."""
    kind: Literal["timeout", "network", "http", "graph", "invalid"]
    code: int | None = None


@dataclass(frozen=True)
class Page:
    id: str
    name: str
    token: str = field(repr=False)  # in no log line and no repr


@dataclass(frozen=True)
class Outcome:
    """A send's settlement, as facebook_publications keeps it. error_code: one of KNOWN_CODES, or this module's
    `not_sent` and `caption`. reconnect: the Page becomes 'reconnect' (the route checks that its row is still the one
    that gave the token)."""
    status: Literal["published", "failed", "unknown"]
    post_id: str | None = None
    link: str | None = None
    error_code: str | None = None
    reconnect: bool = False


def _unique(pairs: list) -> dict:
    keys = [key for key, _value in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate_key")  # two post_id: which one would be Facebook's?
    return dict(pairs)


def _no_constant(_name: str):
    raise ValueError("not_json")  # NaN, Infinity, -Infinity


def _json(response: httpx2.Response) -> object | None:
    """The answer's JSON, strictly; None when it cannot be read: bytes that are not UTF-8 (json.loads would let a
    lone surrogate through), a key twice, NaN or Infinity, nesting too deep."""
    try:
        return json.loads(response.content.decode("utf-8"), object_pairs_hook=_unique, parse_constant=_no_constant)
    except (ValueError, RecursionError):  # UnicodeDecodeError and JSONDecodeError are ValueErrors
        return None


def _status(response: httpx2.Response) -> Literal["200", "4xx", "5xx", "other"]:
    status = response.status_code
    return "200" if status == 200 else "4xx" if 400 <= status < 500 else "5xx" if status >= 500 else "other"


def _known_code(payload: object) -> int | Literal["other"] | None:
    """Graph's error code when it is one of this file's own (KNOWN_CODES); "other" for an error with any other code;
    None when the answer holds no error with an integer code. Nothing else of the error is read."""
    error = payload.get("error") if isinstance(payload, dict) else None
    code = error.get("code") if isinstance(error, dict) else None
    if type(code) is not int:
        return None
    return next((known for known in KNOWN_CODES if known == code), "other")  # this file's constant, not the answer's


def _said(what: str, *words: object) -> None:
    """The module's one log line. Every word is one of its own: a call's name, a kind, a status class, a known code."""
    log.warning("facebook %s: %s", what, " ".join(str(word) for word in words))


def _failed(what: str, kind: str, *words: object) -> GraphFailure:
    _said(what, kind, *words)
    return GraphFailure(kind, next((word for word in words if type(word) is int), None))


def classify(response: httpx2.Response | None, page_id: str, sent: tuple[str, ...] = ()) -> Outcome:
    """The answers' table of D-FB-PUBLISH-003 §4, read in its order. None: no answer, or a cut connection. `sent`: the
    credentials of the call, which a post id must not hold."""
    if response is None:
        return Outcome("unknown")
    status, payload = _status(response), _json(response)
    if status == "5xx":  # whatever its body
        _said("photo", status)
        return Outcome("unknown")
    if status == "200":
        post_id = payload.get("post_id") if isinstance(payload, dict) else None
        # The gate takes the value that is kept, whole: an id with its underscore could be a credential's shape.
        if _kept(post_id, POST_ID, sent) and post_id.partition("_")[0] == page_id:
            return Outcome("published", post_id, f"https://www.facebook.com/{post_id}")
        _said("photo", status, "without a post id of this Page")  # unreadable, or the unpublished photo's `id` alone
        return Outcome("unknown")
    code = _known_code(payload)
    _said("photo", status, "no code" if code is None else code)
    # Only Facebook's own refusal of this request (a 4xx with one of the known codes) says that nothing was posted.
    if status != "4xx" or code is None or code == "other":
        return Outcome("unknown")
    return Outcome("failed", error_code=str(code), reconnect=code == RECONNECT_CODE)


class MetaGraph:
    mode = "meta"

    def __init__(self, app_id: str, secret: SecretStr, *, transport: httpx2.AsyncBaseTransport | None = None):
        self._app_id, self._secret, self._transport = app_id, secret, transport
        for name in ("httpx2", "httpcore2"):  # their debug logs carry request details (as in the image gateway)
            logging.getLogger(name).setLevel(logging.WARNING)

    def _proof(self, token: str) -> str:
        return appsecret_proof(token, self._secret.get_secret_value())

    async def _request(self, method: str, url: str, timeout: float, **request) -> httpx2.Response:
        # trust_env=False: no proxy from the environment; the server calls Facebook directly (D-FB-PUBLISH-001 « Logs »).
        async with httpx2.AsyncClient(transport=self._transport, timeout=timeout, follow_redirects=False,
                                      trust_env=False) as client:
            return await client.request(method, url, **request)

    async def _call(self, what: str, method: str, url: str, **request) -> dict | GraphFailure:
        """A connection call: its 200 answer, an object, or the failure."""
        try:
            response = await self._request(method, url, CONNECT_TIMEOUT_S, **request)
        except httpx2.TimeoutException:
            return _failed(what, "timeout")
        except Exception:  # noqa: BLE001 — whatever the client raises (a `Location` it cannot join, a protocol error): its
            return _failed(what, "network")  # traceback would keep this frame's credentials, so none leaves the module
        status, payload = _status(response), _json(response)
        if status == "200":
            return payload if isinstance(payload, dict) else _failed(what, "invalid", status)
        code = _known_code(payload)
        return _failed(what, "http", status) if code is None else _failed(what, "graph", status, code)

    async def _exchange(self, what: str, form: dict) -> str | GraphFailure:
        # Meta documents both exchanges as GET with the secret in the address. A POST form keeps it out of any address;
        # that Meta takes it is to be confirmed at the first real connection (the design's task 5). A change to GET would
        # be its own reviewed change.
        secret = self._secret.get_secret_value()
        payload = await self._call(what, "POST", f"{GRAPH}/oauth/access_token",
                                   data={"client_id": self._app_id, "client_secret": secret, **form})
        if isinstance(payload, GraphFailure):
            return payload
        token = payload.get("access_token")
        return token if credential(token) else _failed(what, "invalid")

    async def exchange_code(self, code: str, redirect_uri: str) -> str | GraphFailure:
        """The dialog's code for a user token. Both arguments are checked before anything encodes them."""
        if not credential(code, 2000) or not isinstance(redirect_uri, str) or not ADDRESS.fullmatch(redirect_uri):
            return _failed("code", "invalid")
        return await self._exchange("code", {"redirect_uri": redirect_uri, "code": code})

    async def long_lived(self, user_token: str) -> str | GraphFailure:
        """A long-lived user token: a Page's token made from it has no expiry date."""
        if not credential(user_token):
            return _failed("long_lived", "invalid")
        return await self._exchange("long_lived", {"grant_type": "fb_exchange_token", "fb_exchange_token": user_token,
                                                   "appsecret_proof": self._proof(user_token)})

    async def pages(self, user_token: str) -> list[Page] | GraphFailure:
        """The Pages the owner allowed on which this person can post (`CREATE_CONTENT`), each with its own token. The
        tasks of every Page are checked; the other fields only of the Pages kept."""
        if not credential(user_token):
            return _failed("pages", "invalid")
        # The proof is in the address, where a GET's parameters go: alone it opens nothing (it is the HMAC of a token
        # that travels in the header and is dropped after this call).
        proof = self._proof(user_token)
        payload = await self._call("pages", "GET", f"{GRAPH}/me/accounts",
                                   params={"fields": "id,name,tasks,access_token", "limit": 100, "appsecret_proof": proof},
                                   headers={"Authorization": f"Bearer {user_token}"})
        if isinstance(payload, GraphFailure):
            return payload
        data = payload.get("data")
        if not isinstance(data, list) or not all(isinstance(item, dict) and isinstance(item.get("tasks"), list)
                                                 and all(isinstance(task, str) for task in item["tasks"])
                                                 for item in data):
            return _failed("pages", "invalid")
        # The gate of what is kept: no id or name that holds a credential of this call or of this answer, the tokens of
        # the other Pages included, kept or not.
        sent = (user_token, proof, self._secret.get_secret_value(),
                *(item["access_token"] for item in data if credential(item.get("access_token"))))
        pages = []
        for item in data:
            if "CREATE_CONTENT" not in item["tasks"]:
                continue
            id, name, token = item.get("id"), item.get("name"), item.get("access_token")
            if (not credential(token) or not _kept(id, DIGITS, sent) or not _kept(name, NAME, sent) or not name.strip()):
                return _failed("pages", "invalid")
            pages.append(Page(id, name, token))
        return pages

    async def publish_photo(self, page_id: str, page_token: str, png: bytes, caption: str) -> Outcome:
        """D-FB-PUBLISH-003 §3: one multipart POST of the file itself, never retried, settled by `classify`. An empty
        caption is not sent."""
        # Checked before the proof or the request is built: an argument of the wrong shape would raise from a frame that
        # holds the token. Nothing was sent, so the failure is definite. (The route's own rules refuse these first.)
        if (not isinstance(page_id, str) or not DIGITS.fullmatch(page_id) or not credential(page_token)
                or not isinstance(png, bytes) or not isinstance(caption, str)):
            return Outcome("failed", error_code="not_sent")
        try:
            caption.encode("utf-8")
        except UnicodeEncodeError:  # a lone surrogate
            return Outcome("failed", error_code="caption")
        proof = self._proof(page_token)
        form = {"access_token": page_token, "appsecret_proof": proof} | ({"caption": caption} if caption else {})
        try:
            response = await self._request("POST", f"{GRAPH}/{page_id}/photos", PHOTO_TIMEOUT_S, data=form,
                                           files={"source": ("affiche.png", png, "image/png")})
        except httpx2.TimeoutException:  # sent or not, nobody can say
            _said("photo", "timeout")
            response = None
        except Exception:  # noqa: BLE001 — as in `_call`: nothing the client raises leaves with this frame's token
            _said("photo", "network")
            response = None
        return classify(response, page_id, (page_token, proof, self._secret.get_secret_value()))


class StubGraph:
    """FACEBOOK_PROVIDER=stub, for tests, smokes and the dev server: the same calls, no network. Two Pages, so that a
    smoke chooses one; every photo is published, with a new post id of its Page's shape."""
    mode = "stub"
    PAGES = (Page("100000000000001", "Page d’essai 1", "stub-page-token-000000001"),
             Page("100000000000002", "Page d’essai 2", "stub-page-token-000000002"))

    async def exchange_code(self, code: str, redirect_uri: str) -> str | GraphFailure:
        return "stub-user-token-00000001"

    async def long_lived(self, user_token: str) -> str | GraphFailure:
        return "stub-long-lived-token-01"

    async def pages(self, user_token: str) -> list[Page] | GraphFailure:
        return list(self.PAGES)

    async def publish_photo(self, page_id: str, page_token: str, png: bytes, caption: str) -> Outcome:
        if not isinstance(page_id, str) or not DIGITS.fullmatch(page_id):
            return Outcome("failed", error_code="not_sent")
        post_id = f"{page_id}_{uuid4().int % 10 ** 15}"
        return Outcome("published", post_id, f"https://www.facebook.com/{post_id}")


def make_graph(settings, transport: httpx2.AsyncBaseTransport | None = None) -> MetaGraph | StubGraph:
    """FACEBOOK_PROVIDER's client. With `off` the feature does not exist: the routes answer not_found."""
    if settings.facebook_provider == "meta":
        return MetaGraph(settings.facebook_app_id, settings.facebook_app_secret, transport=transport)
    if settings.facebook_provider == "stub":
        return StubGraph()
    raise Refused("not_found", 404)


def check_mode(conn, graph: MetaGraph | StubGraph):
    """Inside the caller's write transaction, before a call: the first Facebook call of a data folder records its mode,
    and the other mode is refused, as the planner's reads do (reads.py, planner_mode). A publication made by the
    stand-in never sits beside real ones."""
    recorded = conn.execute(text("SELECT value FROM meta WHERE key='facebook_mode'")).scalar()
    if recorded is None:
        conn.execute(text("INSERT INTO meta VALUES ('facebook_mode',:mode)"), {"mode": graph.mode})
    elif recorded != graph.mode:
        raise Refused("provider_mode_mismatch", 409)
