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
    assert {k: v for k, v in state["turns"][0].items() if k not in ("context", "base_render_id", "job_id")} | {"render_id": None, "png_sha256": None} == {
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


def test_a_correction_edits_the_models_own_file_with_the_first_version_as_clean_reference(client, monkeypatch):
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
    # Missing anchor bytes must not shift the numbered reference/logo images in the provider request.
    import time
    from affiche.posters import free_creation
    before = client.get('/api/balance').json()['available']
    monkeypatch.setattr(free_creation, 'stored', lambda *args: None)
    failed = send(client, 'POST', f'/api/free-creations/{id}/turns', {'words': 'Fond vert'}, 5)
    assert failed.status_code == 202
    for _ in range(100):
        job = client.get(failed.json()['status_url']).json()
        if job['status'] == 'failed': break
        time.sleep(.05)
    assert job['status'] == 'failed' and job['error_code'] == 'preflight_failed'
    assert client.get('/api/balance').json()['available'] == before



def test_attachment_numbers_and_style_precedence():
    result = prompt("Trois cartes et trois prix", 3, True, True, True)
    # A correction: the base, then the photos; the reference is not sent again (the base carries its layout).
    assert result.startswith("Edit image 1") and "2, 3, 4" in result and "is the visual reference" not in result
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


def test_identity_reference_and_anchor_roles():
    from affiche.posters.free_creation import Identity
    result = prompt("Une affiche", 3, True, True, True, True,
                    identity=Identity(name="Boutique", contact="034 00 000 00", logo="a" * 64),
                    reference_mode="style", new_reference=True)
    assert "Image 5 is an earlier version" in result
    assert "Image 6 is the visual reference" in result
    assert "Image 7 is the supplied shop logo" in result
    assert "do not copy its cards" in result and "034 00 000 00" in result
    absent = prompt("Boutique Tana", 0, True, True, False)
    assert "Do not invent any shop logo" in absent and "shop logos" in absent
    assert "plain readable text only" in absent
    assert "print ONLY that list" in absent
    removed = prompt("Fond bleu", 0, None, True, True, removed_text=["Boutique Tana"])
    assert "now deselected" in removed and "Boutique Tana" in removed
    edited = prompt("Fond bleu", 1, None, True, True, True, history=["Prix 85 000 Ar", "Prix 95 000 Ar"])
    assert "NEVER restore superseded amounts" in edited and "Prix 95 000 Ar" in edited


def test_context_changes_commit_only_after_success_and_branch_uses_own_sources(client):
    import json
    from test_api import photo
    login(client)
    def upload(role):
        response = client.post("/api/assets", files={"file": ("p.png", photo(), "image/png")}, data={"role": role})
        assert response.status_code == 201
        return response.json()["asset"]
    original, logo, reference = upload("original"), upload("logo"), upload("style")
    first = send(client, "POST", "/api/free-creations", {"words": "Produit 10 000 Ar", "photos": [original], "logo": logo})
    id = first.json()["creation_id"]
    base = wait(client, first.json()["status_url"])
    route = f"/api/free-creations/{id}"
    state = client.get(route).json()
    assert state["document"]["identity"]["logo"] == logo
    second = send(client, "POST", route + "/turns", {"words": "Sans photo ni logo, nouveau style", "photos": [],
                  "logo": None, "reference": reference, "reference_mode": "style"}, state["revision"])
    wait(client, second.json()["status_url"])
    state = client.get(route).json()
    assert state["photos"] == [] and state["document"]["identity"]["logo"] is None
    branch = send(client, "POST", route + "/turns", {"words": "Fond bleu", "base_render_id": base}, state["revision"])
    wait(client, branch.json()["status_url"])
    state = client.get(route).json()
    assert state["photos"] == [original] and state["document"]["identity"]["logo"] == logo
    assert state["document"]["reference"] is None
    with client.app.state.engine.connect() as conn:
        payload = json.loads(conn.exec_driver_sql("SELECT input_json FROM poster_jobs ORDER BY rowid DESC LIMIT 1").scalar_one())
    assert payload["base_render_id"] == base
    assert state["document"]["history"] == ["Produit 10 000 Ar", "Fond bleu"]
    assert "Sans photo ni logo" not in payload["prompt"]
    # An unrelated render cannot be used as the base, even by the same shop.
    other = send(client, "POST", "/api/free-creations", {"words": "Autre affiche"})
    other_base = wait(client, other.json()["status_url"])
    before = client.get("/api/balance").json()["available"]
    assert send(client, "POST", route + "/turns", {"words": "Copier", "base_render_id": other_base}, state["revision"]).status_code == 404
    assert client.get("/api/balance").json()["available"] == before
    assert client.get(route).json()["revision"] == state["revision"]


def test_profile_snapshot_and_asset_role_validated_before_spend(client):
    from affiche.db import write_tx
    from sqlalchemy import text
    login(client)
    with write_tx(client.app.state.engine) as conn:
        conn.execute(text("UPDATE shop_profile SET name='Boutique Tana',contact='034 00 000 00',lines_json='[\"Bienvenue\"]' WHERE id=1"))
    first = send(client, "POST", "/api/free-creations", {"words": "Ouverture", "use_shop": True})
    wait(client, first.json()["status_url"])
    state = client.get('/api/free-creations/' + first.json()['creation_id']).json()
    assert state['document']['identity'] == {'name': 'Boutique Tana', 'contact': '034 00 000 00', 'lines': ['Bienvenue'], 'logo': None}
    before = client.get('/api/balance').json()['available']
    response = send(client, 'POST', '/api/free-creations', {'words': 'Affiche', 'logo': 'a' * 64})
    assert response.status_code == 422
    assert client.get('/api/balance').json()['available'] == before


def test_failed_context_retry_keeps_snapshot_and_successful_state(client):
    import time
    from affiche.db import write_tx
    from affiche.visuals.gateway import StubProvider
    login(client)
    first = send(client, 'POST', '/api/free-creations', {'words': 'Première affiche'})
    wait(client, first.json()['status_url'])
    route = '/api/free-creations/' + first.json()['creation_id']
    original = client.get(route).json()
    with write_tx(client.app.state.engine) as conn:
        conn.exec_driver_sql("UPDATE shop_profile SET name='Boutique Tana' WHERE id=1")
    client.app.state.poster_service.provider = StubProvider(['refused'], delay=0)
    failed = send(client, 'POST', route + '/turns', {'words': 'Ajoute ma boutique', 'use_shop': True}, original['revision'])
    assert failed.status_code == 202
    for _ in range(100):
        state = client.get(route).json()
        if state['turns'][-1]['status'] == 'failed':
            break
        time.sleep(.05)
    assert state['turns'][-1]['status'] == 'failed'
    assert state['document'] == original['document'] and state['revision'] == original['revision']
    with write_tx(client.app.state.engine) as conn:
        conn.exec_driver_sql("UPDATE shop_profile SET name='Autre boutique' WHERE id=1")
    retry = send(client, 'POST', route + '/turns', {'words': 'Ajoute ma boutique', 'retry_job_id': state['turns'][-1]['job_id']}, state['revision'])
    wait(client, retry.json()['status_url'])
    final = client.get(route).json()
    assert final['document']['identity']['name'] == 'Boutique Tana'
    before = client.get('/api/balance').json()['available']
    for job in (str(uuid4()), final['turns'][-1]['job_id']):
        assert send(client, 'POST', route + '/turns', {'words': 'Retry', 'retry_job_id': job}, final['revision']).status_code == 404
    assert client.get('/api/balance').json()['available'] == before


def test_retry_key_distinguishes_omitted_reference_from_explicit_removal(client):
    login(client)
    first = send(client, 'POST', '/api/free-creations', {'words': 'Une affiche'})
    wait(client, first.json()['status_url'])
    route = '/api/free-creations/' + first.json()['creation_id'] + '/turns'
    headers = {'Idempotency-Key': str(uuid4()), 'If-Match': '"2"'}
    body = {'words': 'Fond vert'}
    edit = client.post(route, json=body, headers=headers)
    assert edit.status_code == 202
    assert client.post(route, json=body, headers=headers).json() == edit.json()
    different = client.post(route, json=body | {'reference': None}, headers=headers)
    assert different.status_code == 409
    wait(client, edit.json()['status_url'])
    assert client.get('/api/balance').json()['available'] == 98
