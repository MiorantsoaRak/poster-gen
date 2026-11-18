"""The conditions of use (D-TERMS-001, D-TERMS-002, T-TERMS-001): the text pinned to its version, the contact, GET and
POST /api/terms through the real boundary, the session checked again inside the acceptance's write, and one write for
two acceptances at once. The gate at admission (T-TERMS-002) is tested where each admission is: test_poster_jobs.py,
test_reads.py, test_api.py (the balance) and test_two_shops.py."""
import hashlib
import threading
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text

from affiche import api as affiche_api, shops
from affiche.api import create_app
from affiche.db import make_engine, write_tx
from affiche.posters import auth, terms
from test_api import HEADERS, ORIGIN, login, password_hash, settings  # noqa: F401
from test_config import env  # noqa: F401


@pytest.fixture
def client(settings):
    """test_api's client with shop 1 as migration 0017 leaves it, nothing accepted (credited() accepts)."""
    with TestClient(create_app(settings), base_url=ORIGIN, headers=HEADERS) as client:
        yield client


def stored(engine, shop=1):
    with engine.connect() as conn:
        return tuple(conn.execute(text("SELECT terms_version, terms_accepted_at FROM shop_profile WHERE id=:shop"),
                                  {"shop": shop}).one())


def writes(engine) -> list[int]:
    """The rows each acceptance's UPDATE changed, in order: 0 is an acceptance that wrote nothing."""
    changed = []

    def count(_conn, cursor, statement, *_rest):
        if statement.startswith("UPDATE shop_profile SET terms_version"):
            changed.append(cursor.rowcount)

    event.listen(engine, "after_cursor_execute", count)
    return changed


def accept(client, version, **headers):
    return client.post("/api/terms", json={"version": version}, headers=headers)


def attempting(monkeypatch, count) -> threading.Event:
    """Set when `count` acceptances are about to take the write lock: terms.write_tx is called, and BEGIN IMMEDIATE is
    what entering it sends. Wrapped there, not on the engine: the poster worker takes the same engine's lock too."""
    reached, seen, lock, real = threading.Event(), [], threading.Lock(), terms.write_tx

    def write_tx(engine):
        with lock:
            seen.append(engine)
            if len(seen) == count:
                reached.set()
        return real(engine)

    monkeypatch.setattr(terms, "write_tx", write_tx)
    return reached


def at(monkeypatch, stamp):
    """The acceptance's clock, in the schema's format (db.utc_now)."""
    monkeypatch.setattr(terms, "utc_now", lambda: stamp)
    return stamp


def refusal(answer):
    return answer.status_code, answer.json()["error"]["code"]


def test_a_word_changed_needs_a_new_version():
    """A word of the text changed without a new date fails here; the new date is the approved text's."""
    digest = hashlib.sha256("\n".join(terms.PARAGRAPHS_FR).encode("utf-8")).hexdigest()
    assert (terms.VERSION, digest) == ("2026-11-17", "1e61a82a05bc8681142c1e070dba96e744e0653669ad5716bf4640a78f3a0226")
    assert date.fromisoformat(terms.VERSION).isoformat() == terms.VERSION  # an ISO date: at most one version a day


@pytest.mark.parametrize("contact, shown", [
    ("Rado, à la boutique", "Rado, à la boutique"),
    (None, "l'opérateur qui vous a remis votre identifiant"),
    ("{} {contact} {0}", "{} {contact} {0}"),  # replace, never format: braces are shown as they are
])
def test_the_contact_is_the_support_setting_else_whoever_gave_the_identifier(settings, contact, shown):
    settings.support_contact_fr = contact
    paragraphs = terms.paragraphs(settings)
    assert paragraphs[:-1] == list(terms.PARAGRAPHS_FR[:-1])
    assert paragraphs[-1] == f"Une question, un problème, une demande sur vos données : contactez {shown}."


def test_a_shop_accepts_once_and_a_new_version_asks_again(client, settings, monkeypatch):
    engine, current = client.app.state.engine, terms.VERSION
    assert refusal(client.get("/api/terms")) == (401, "unauthenticated")
    login(client)
    unread = {"version": current, "paragraphs_fr": terms.paragraphs(settings), "accepted_at": None, "changed": False}
    assert client.get("/api/terms").json() == unread
    changed = writes(engine)
    first_at = at(monkeypatch, "2026-11-18T08:00:00.000000+00:00")
    first = accept(client, current)
    assert first.status_code == 200, first.text
    assert first.json() == {"version": current, "accepted_at": first_at} and stored(engine) == (current, first_at)
    assert client.get("/api/terms").json() == unread | {"accepted_at": first_at}
    later = at(monkeypatch, "2026-11-18T09:00:00.000000+00:00")
    again = accept(client, current)  # a lost answer sent again, a second tap: the first date, nothing written
    assert (again.status_code, again.json(), changed) == (200, first.json(), [1, 0])
    monkeypatch.setattr(terms, "VERSION", "2026-12-01")  # a release with a new text
    assert client.get("/api/terms").json() == unread | {"version": "2026-12-01", "changed": True}
    assert refusal(accept(client, current)) == (409, "terms_outdated") and stored(engine) == (current, first_at)
    newer = accept(client, "2026-12-01")
    assert (newer.status_code, newer.json(), changed) == (200, {"version": "2026-12-01", "accepted_at": later}, [1, 0, 1])
    assert stored(engine) == ("2026-12-01", later)
    assert client.get("/api/terms").json() == unread | {"version": "2026-12-01", "accepted_at": later}


def test_an_older_version_is_refused_and_nothing_is_written(client):
    """T-TERMS-001's mutation: an acceptance that writes whatever version it is sent fails here."""
    login(client)
    answer = accept(client, "2026-11-16")
    assert answer.status_code == 409 and answer.json()["error"] == {
        "code": "terms_outdated", "retryable": False,
        "message_fr": "Les conditions viennent de changer : lisez la nouvelle version avant de l'accepter."}
    assert stored(client.app.state.engine) == (None, None) and client.get("/api/terms").json()["accepted_at"] is None


def test_the_boundary_and_the_body_refuse_before_anything_is_written(client):
    engine = client.app.state.engine
    assert refusal(accept(client, terms.VERSION)) == (401, "unauthenticated")  # signed out
    login(client)
    cookie = {"Cookie": f"{auth.COOKIE}={client.cookies.get(auth.COOKIE)}"}
    no_origin = TestClient(client.app, base_url=ORIGIN, headers={"X-Affiche-Bundle": str(affiche_api.BUNDLE)} | cookie)
    assert refusal(accept(no_origin, terms.VERSION)) == (403, "forbidden_origin")
    assert refusal(accept(client, terms.VERSION, Origin="https://evil.example")) == (403, "forbidden_origin")
    for bundle in ("", str(affiche_api.BUNDLE - 1)):  # an older open tab
        assert refusal(accept(client, terms.VERSION, **{"X-Affiche-Bundle": bundle})) == (409, "bundle_outdated")
    for body in ({}, {"version": ""}, {"version": "9" * 33}, {"version": 20261117}, {"version": terms.VERSION, "shop": 2}):
        assert refusal(client.post("/api/terms", json=body)) == (422, "validation_error"), body
    assert stored(engine) == (None, None)


@pytest.mark.parametrize("meanwhile", [lambda conn: shops.suspend(conn, 1), lambda conn: shops.end_sessions(conn, 1)],
                         ids=["suspended", "sessions ended"])
def test_a_session_that_stops_while_the_acceptance_waits_for_the_lock_accepts_nothing(client, settings, monkeypatch,
                                                                                     meanwhile):
    """The holder stops the session in a write transaction it has not committed: the boundary's read still sees it live.
    It commits once the acceptance is about to take the lock, so only a check made under that lock sees it stopped."""
    engine, answers = client.app.state.engine, []
    login(client)
    reached, holder = attempting(monkeypatch, 1), make_engine(settings.data_dir)
    try:
        with write_tx(holder) as conn:
            meanwhile(conn)
            sender = threading.Thread(target=lambda: answers.append(accept(client, terms.VERSION)))
            sender.start()
            assert reached.wait(10)
        sender.join(timeout=20)
    finally:
        holder.dispose()
    assert [refusal(answer) for answer in answers] == [(401, "unauthenticated")]
    assert stored(engine) == (None, None)


def test_two_devices_accepting_at_once_write_once_and_get_one_date(client, settings, monkeypatch):
    engine = client.app.state.engine
    phone, laptop = (TestClient(client.app, base_url=ORIGIN, headers=HEADERS) for _ in range(2))
    login(phone)
    login(laptop)
    changed, answers = writes(engine), []
    reached, holder = attempting(monkeypatch, 2), make_engine(settings.data_dir)
    try:
        with write_tx(holder) as conn:  # released once both acceptances are about to wait for its lock
            conn.exec_driver_sql("SELECT 1")
            devices = [threading.Thread(target=lambda device=device: answers.append(accept(device, terms.VERSION)))
                       for device in (phone, laptop)]
            [device.start() for device in devices]
            assert reached.wait(10)
        [device.join(timeout=20) for device in devices]
    finally:
        holder.dispose()
    assert [answer.status_code for answer in answers] == [200, 200] and answers[0].json() == answers[1].json()
    assert changed == [1, 0] and stored(engine) == (terms.VERSION, answers[0].json()["accepted_at"])
