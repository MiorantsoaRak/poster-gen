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


def test_a_correction_edits_the_models_own_file_with_the_first_version_as_clean_reference(client):
    """Nine corrections chained from one another turned the product to grain (the owner's trial, 2026-11-25)."""
    import json
    login(client)
    first = client.post("/api/free-creations", json={"words": "Une affiche"}, headers={"Idempotency-Key": str(uuid4())})
    id = first.json()["creation_id"]
    wait(client, first.json()["status_url"])
    for revision, words in ((2, "Prix plus grand"), (3, "Nom en gras")):
        wait(client, send(client, "POST", f"/api/free-creations/{id}/turns", {"words": words}, revision).json()["status_url"])
    with client.app.state.engine.connect() as conn:
        jobs_ = [json.loads(row[0]) for row in conn.exec_driver_sql("SELECT input_json FROM poster_jobs ORDER BY rowid")]
        versions = [json.loads(row[0]) for row in conn.exec_driver_sql("SELECT document_json FROM creation_versions ORDER BY revision")]
    sources = [version["source"] for version in versions[1:]]
    assert len(set(sources)) == 3 and {version["first"] for version in versions[1:]} == {sources[0]}
    # The first image has no base; the correction of the first version has no other reference than itself.
    assert [(job["base_asset"], job["anchor_asset"]) for job in jobs_] == [(None, None), (sources[0], None), (sources[1], sources[0])]
    assert "Image 2 is an earlier version" in jobs_[2]["prompt"] and "earlier version" not in jobs_[1]["prompt"]
    # A creation made before the files were kept: the published PNGs stand in.
    with client.app.state.engine.begin() as conn:
        conn.exec_driver_sql("UPDATE creation_versions SET document_json=json_remove(document_json,'$.source','$.first')")
        renders = [row[0] for row in conn.exec_driver_sql("SELECT png_sha256 FROM poster_renders ORDER BY source_revision")]
    wait(client, send(client, "POST", f"/api/free-creations/{id}/turns", {"words": "Fond plus sombre"}, 4).json()["status_url"])
    with client.app.state.engine.connect() as conn:
        last = json.loads(conn.exec_driver_sql("SELECT input_json FROM poster_jobs ORDER BY rowid DESC LIMIT 1").scalar())
    assert (last["base_asset"], last["anchor_asset"]) == (None, renders[0])
    with client.app.state.engine.connect() as conn:  # and its later versions never become the reference
        assert json.loads(conn.exec_driver_sql("SELECT document_json FROM creation_versions ORDER BY revision DESC LIMIT 1").scalar())["first"] is None
    assert client.get(f"/api/free-creations/{id}").json()["turns"][-1]["status"] == "succeeded"


def test_attachment_numbers_and_style_precedence():
    result = prompt("Trois cartes et trois prix", 3, True, True, True)
    # A correction: the base, then the photos; the reference is not sent again (the base carries its layout).
    assert result.startswith("Edit image 1") and "2, 3, 4" in result and "visual reference" not in result
    assert "clear focal point" not in result
    assert "1, 2, 3" in (first := prompt("Trois cartes", 3, True, True, False)) and "Image 4 is the visual reference" in first
    # The clean reference of a correction comes last, after the photos.
    assert "Image 5 is an earlier version" in prompt("Plus grand", 3, True, True, True, True)
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
