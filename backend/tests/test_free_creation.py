from hashlib import sha256
from uuid import uuid4

from affiche.posters import jobs
from affiche.posters.free_creation import prompt
from test_api import client, login, password_hash, settings
from test_config import env
from test_two_shops import send, wait


def test_direct_conversation_replay_polish_confirm_and_stale(client, monkeypatch):
    login(client)
    start = "/api/free-creations"
    headers = {"Idempotency-Key": str(uuid4())}
    words = {"words": "Écris Fety sambatra, fond bleu. Aucune offre."}
    first = client.post(start, json=words, headers=headers)
    assert first.status_code == 202, first.text
    assert client.post(start, json=words, headers=headers).json() == first.json()
    id = first.json()["creation_id"]
    render = wait(client, first.json()["status_url"])
    thread = f"{start}/{id}"
    state = client.get(thread).json()
    assert state["document"]["offer"]["price_ar"] is None
    assert state["turns"][0]["words"] == words["words"]
    assert state["turns"][0] | {"render_id": None, "png_sha256": None} == {
        "status": "succeeded", "error_code": None, "words": words["words"], "render_id": None, "png_sha256": None, "credit": "spent"}
    def confirm(render, revision):
        artifact = client.get(f"/api/renders/{render}").json()
        return send(client, "POST", f"/api/creations/{id}/confirmations", {
            "render_id": render, "png_sha256": artifact["png_sha256"],
            "checks": dict.fromkeys(("framing", "content", "identity", "readability"), True)}, revision)
    original = confirm(render, 2).json()["download_url"]
    assert sha256(client.get(original).content).hexdigest() == state["turns"][0]["png_sha256"]
    monkeypatch.setattr(jobs, "SCENE_LIMIT", 1)
    edit = send(client, "POST", thread + "/turns", {"words": "Change le fond en rose"}, 2)
    assert edit.status_code == 202, edit.text
    second = wait(client, edit.json()["status_url"])
    assert client.get(thread).json()["confirmation"] is None
    assert confirm(render, 3).status_code == 409
    assert confirm(second, 3).status_code == 201
    assert client.get(original).status_code == 200
    assert send(client, "POST", thread + "/turns", {"words": "Autre"}, 2).status_code == 409
    assert client.get("/api/balance").json()["available"] == 98


def test_attachment_numbers_and_style_precedence():
    result = prompt("Trois cartes et trois prix", 3, True, True, True)
    # A correction: the base, then the photos; the reference is not sent again (the base carries its layout).
    assert result.startswith("Edit image 1") and "2, 3, 4" in result and "visual reference" not in result
    assert "clear focal point" not in result
    assert "1, 2, 3" in (first := prompt("Trois cartes", 3, True, True, False)) and "Image 4 is the visual reference" in first
    assert "clear focal point" in prompt("Bonjour", 0, None, True, False)
    assert "clear focal point" not in prompt("Bonjour", 0, None, False, False)


def test_unfunded_request_rolls_back_creation_and_reservation(client):
    from affiche.db import write_tx
    from affiche.posters import credits

    login(client)
    engine = client.app.state.engine
    with write_tx(engine) as conn:
        credits.correct(conn, 1, -credits.balance(conn, 1)["available"], ref="empty", note="Test", actor="test")
    answer = send(client, "POST", "/api/free-creations", {"words": "Une composition sans photo"})
    assert answer.status_code == 402 and answer.json()["error"]["code"] == "no_credit"
    with engine.connect() as conn:
        for table in ("creations", "product_inputs", "poster_jobs", "poster_calls"):
            assert conn.exec_driver_sql(f"SELECT count(*) FROM {table}").scalar_one() == 0
