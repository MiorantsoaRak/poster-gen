import asyncio
import json
import time

import httpx2
import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy import text

from affiche.posters import jobs, store, typography as t
from affiche.posters.models import Document, canonical
from affiche.posters.planner import ClaudePlanner, MODEL, PlannerError
from affiche.posters.service import PosterService
from affiche.posters.worker import run_job
from test_api import client, create_draft, login, password_hash, post, settings  # noqa: F401
from test_config import env  # noqa: F401
from test_db import engine  # noqa: F401
from test_poster_drafts import draft, input_id, key  # noqa: F401


@pytest.fixture
def creation(engine, settings, input_id):
    settings.planner_provider = "stub"
    return draft(engine, settings.data_dir, input_id)


def layer(creation, role="title"):
    return next(node for node in creation["document"]["formats"]["feed"]["layers"] if node["role"] == role)


def request(engine, settings, creation, instruction="Une typographie dorée", role="title"):
    return t.request_proposal(engine, settings, 1, key(), creation["id"], creation["revision"],
        t.ProposalRequest(layer_id=layer(creation, role)["id"], instruction_fr=instruction))[1]


def execute(engine, settings, patch=None):
    service = PosterService(engine, settings)
    service.provider.delay = 0
    job = jobs.claim(engine, ("text_patch", "text_texture"))
    assert job
    if patch:
        from affiche.posters.worker import Outcome
        async def send(_):
            return Outcome({"patch": patch.model_dump(exclude_unset=True)}, cost_micros=0)
    else:
        send = service.send
    assert asyncio.run(run_job(engine, settings, job, prepare=service.prepare, send=send, finalise=service.finalise))
    with engine.connect() as conn:
        return jobs.get_job(conn, 1, job["id"])["result_ref"]


def proposal(engine, settings, creation, *, texture=False):
    request(engine, settings, creation)
    patch = t.TextPatch(layer_id=layer(creation)["id"], style=t.Style(fill="#FFCC66"), summary_fr="Titre doré",
                        texture_request=t.Texture(description="Métal doré brossé", palette=["#FFCC66"]) if texture else None)
    id = execute(engine, settings, patch)
    return id


def test_proposal_review_is_atomic_isolated_and_idempotent(engine, settings, creation):
    id = proposal(engine, settings, creation)
    with engine.connect() as conn:
        assert store.get_creation(conn, 1, creation["id"]) == creation
        view = t.get_proposal(conn, 1, id)
    assert view["before"] == creation["document"]
    mutation_key = key()
    result = t.decide_proposal(engine, settings, 1, mutation_key, id, 1, "apply", t.ApplyRequest())
    assert result == t.decide_proposal(engine, settings, 1, mutation_key, id, 1, "apply", t.ApplyRequest())
    after = result[1]["document"]
    before = json.loads(canonical(creation["document"]))
    layer({"document": before})["fill"] = "#FFCC66"
    assert after == before and result[1]["revision"] == 2
    with pytest.raises(store.Refused, match="proposal_decided"):
        t.decide_proposal(engine, settings, 1, key(), id, 2, "reject", t.ApplyRequest())


@pytest.mark.parametrize("price", ["90 000 Ar", "90000 ariary", "90\u202f000 Ar"])
def test_explicit_price_requires_content_acknowledgement(engine, settings, creation, price):
    instruction = f"Change le prix à {price}."
    request(engine, settings, creation, instruction, "price")
    patch = t.TextPatch(layer_id=layer(creation, "price")["id"], style=t.Style(),
                        content_change=t.PriceChange(field="price_ar", value=90000), summary_fr="Prix demandé")
    id = execute(engine, settings, patch)
    with pytest.raises(store.Refused, match="content_acknowledgement_required"):
        t.decide_proposal(engine, settings, 1, key(), id, 1, "apply", t.ApplyRequest())
    result = t.decide_proposal(engine, settings, 1, key(), id, 1, "apply", t.ApplyRequest(acknowledged_content_change=True))[1]
    expected = creation["document"] | {"offer": creation["document"]["offer"] | {"price_ar": 90000}}
    assert result["document"] == expected


@pytest.mark.parametrize(("instruction", "value"), [
    ("Baisse un peu le prix", 90000), ("Prix 1.500 Ar", 500), ("Prix 90 00 Ar", 0),
    ("Prix -500 Ar", 500), ("Prix - 500 Ar", 500), ("Prix 90 000 Ar ou 80 000 Ar", 90000), ("Prix 90000 Ar", 80000),
    ("Prix 1e3 Ar", 3), ("Prix 1,500 Ar", 500),
])
def test_ambiguous_or_invented_prices_refused(creation, instruction, value):
    patch = t.TextPatch(layer_id=layer(creation, "price")["id"], style=t.Style(),
        content_change=t.PriceChange(field="price_ar", value=value), summary_fr="Changement")
    with pytest.raises(ValueError):
        t.validate_patch(patch, Document.model_validate(creation["document"]), "feed", patch.layer_id, instruction)


@pytest.mark.parametrize("quoted", ['"Nouveau titre"', '« Nouveau titre »', '“Nouveau titre”'])
def test_title_requires_exact_quoted_literal(creation, quoted):
    patch = t.TextPatch(layer_id=layer(creation)["id"], style=t.Style(),
        content_change=t.TitleChange(field="title", value="Nouveau titre"), summary_fr="Titre demandé")
    doc = Document.model_validate(creation["document"])
    assert t.validate_patch(patch, doc, "feed", patch.layer_id, f"Remplace le titre par {quoted}") == patch
    with pytest.raises(ValueError, match="content_not_explicit"):
        t.validate_patch(patch, doc, "feed", patch.layer_id, "Un titre plus vendeur")


def test_unknown_style_and_wrong_layer_refused(creation):
    with pytest.raises(ValidationError):
        t.Style.model_validate({"scene": "replace"})
    with pytest.raises(ValidationError):
        t.Style(font_id="unregistered")
    with pytest.raises(ValidationError):
        t.PriceChange(field="price_ar", value=True)
    patch = t.TextPatch(layer_id=key(), style=t.Style(fill="#112233"), summary_fr="Changement")
    with pytest.raises(ValueError, match="unsupported_target"):
        t.validate_patch(patch, Document.model_validate(creation["document"]), "feed", layer(creation)["id"], "Une autre couleur")


def test_reference_typography_patch_and_removal_only_change_price(creation):
    from affiche.posters.models import PriceBadge
    original = Document.model_validate(creation["document"])
    price = layer(creation, "price")
    patch = t.TextPatch(layer_id=price["id"], style=t.Style(font_id="montserrat-black-italic", weight=900,
                       price_badge=PriceBadge()), summary_fr="Prix en capsule, très gras italique")
    t.validate_patch(patch, original, "feed", price["id"], "Le style du prix de la référence")
    result = t.patched(original, "feed", patch)
    expected = json.loads(canonical(original))
    layer({"document": expected}, "price").update(font_id="montserrat-black-italic", weight=900,
                                                  price_badge=PriceBadge().model_dump())
    assert result.model_dump() == expected
    remove = t.TextPatch(layer_id=price["id"], style=t.Style(price_badge=None), summary_fr="Retirer la capsule")
    t.validate_patch(remove, result, "feed", price["id"], "Retirer la capsule")
    assert t.selected(t.patched(result, "feed", remove), "feed", price["id"]).price_badge is None
    assert original.model_dump() == creation["document"]


@pytest.mark.parametrize("style", [
    {"font_id": "montserrat-black-italic", "weight": 700}, {"font_id": "noto-sans", "weight": 900},
    {"font_id": "noto-serif", "weight": 900}, {"price_badge": {}},
    {"price_badge": {"fill": "url(https://untrusted.invalid)"}},
])
def test_invalid_reference_typography_is_rejected(creation, style):
    with pytest.raises(ValidationError):
        patch = t.TextPatch(layer_id=layer(creation)["id"], style=t.Style.model_validate(style), summary_fr="Style")
        t.validate_patch(patch, Document.model_validate(creation["document"]), "feed", patch.layer_id, "Style")


def test_legacy_document_hashes_and_default_badge_are_unchanged(creation):
    old = creation["document"]
    assert all("price_badge" not in node for node in old["formats"]["feed"]["layers"])
    document = Document.model_validate(old)
    assert canonical(document) == canonical(old)
    explicit_null = json.loads(canonical(old))
    layer({"document": explicit_null}, "price")["price_badge"] = None
    assert canonical(Document.model_validate(explicit_null)) == canonical(old)


def test_stale_proposal_and_rejection_leave_newer_draft_untouched(engine, settings, creation):
    id = proposal(engine, settings, creation)
    doc = Document.model_validate(creation["document"])
    doc.offer.price_ar += 1
    current = store.save_creation(engine, settings.data_dir, 1, key(), creation["id"], doc, 1)[1]
    with pytest.raises(store.Refused, match="stale_proposal"):
        t.decide_proposal(engine, settings, 1, key(), id, 2, "apply", t.ApplyRequest())
    t.decide_proposal(engine, settings, 1, key(), id, None, "reject", t.ApplyRequest())
    with engine.connect() as conn:
        assert store.get_creation(conn, 1, creation["id"]) == current


def effect(engine, settings, creation):
    id = proposal(engine, settings, creation, texture=True)
    request = t.EffectRequest(layer_id=layer(creation)["id"], proposal_id=id)
    with pytest.raises(store.Refused, match="stale_proposal"):
        t.request_effect(engine, settings, 1, key(), creation["id"], 1, request)
    applied = t.decide_proposal(engine, settings, 1, key(), id, 1, "apply", t.ApplyRequest())[1]
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM poster_jobs")).scalar_one() == 1
    t.request_effect(engine, settings, 1, key(), creation["id"], 2, request)
    return execute(engine, settings), applied


def test_explicit_texture_generation_review_reuse_and_no_bypass(engine, settings, creation):
    id, current = effect(engine, settings, creation)
    doc = Document.model_validate(current["document"])
    t.selected(doc, "feed", layer(creation)["id"]).texture_effect_id = id
    with pytest.raises(store.Refused, match="effect_unapproved"):
        store.save_creation(engine, settings.data_dir, 1, key(), creation["id"], doc, 2)
    mutation_key = key()
    applied = t.decide_effect(engine, settings, 1, mutation_key, id, 2, "apply")
    assert applied == t.decide_effect(engine, settings, 1, mutation_key, id, 2, "apply")
    assert applied[1]["document"] == doc.model_dump()
    doc.offer.price_ar = 123000
    saved = store.save_creation(engine, settings.data_dir, 1, key(), creation["id"], doc, 3)[1]
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM poster_calls")).scalar_one() == 2
        assert t.get_effect(conn, 1, id)["status"] == "applied"
        with pytest.raises(store.Refused, match="not_found"):
            t.read_effect(conn, settings.data_dir, 999, id)
    assert saved["document"]["formats"]["feed"]["scene"] == creation["document"]["formats"]["feed"]["scene"]


def test_effect_stale_after_manual_change_can_be_rejected(engine, settings, creation):
    id, current = effect(engine, settings, creation)
    doc = Document.model_validate(current["document"])
    t.selected(doc, "feed", layer(creation)["id"]).font_size += 1
    store.save_creation(engine, settings.data_dir, 1, key(), creation["id"], doc, 2)
    with pytest.raises(store.Refused, match="stale_effect"):
        t.decide_effect(engine, settings, 1, key(), id, 3, "apply")
    assert t.decide_effect(engine, settings, 1, key(), id, None, "reject")[1]["status"] == "rejected"


def test_claude_transport_is_structured_selected_only_and_costs_invalid_output(engine, settings, creation):
    request(engine, settings, creation)
    with engine.connect() as conn:
        payload = json.loads(conn.execute(text("SELECT input_json FROM poster_jobs")).scalar_one())
    requests = []
    response_patch = {"layer_id": layer(creation)["id"], "style": {"font_id": "noto-serif"}, "summary_fr": "Police serif"}
    def handle(request):
        requests.append(json.loads(request.content))
        return httpx2.Response(200, json={"model": MODEL, "stop_reason": "end_turn", "usage": {"input_tokens": 10, "output_tokens": 20},
            "content": [{"type": "text", "text": json.dumps(response_patch)}]})
    planner = ClaudePlanner(SecretStr("fake-local-key"), transport=httpx2.MockTransport(handle))
    result = asyncio.run(t.propose(planner, payload))
    assert result[0].style.font_id == "noto-serif" and result[2] == 220
    sent = requests[0]
    assert sent["output_config"]["format"]["type"] == "json_schema"
    assert "brand_snapshot" not in json.dumps(sent) and "photo_assets" not in json.dumps(sent)
    response_patch["style"] = {"scene": "replace everything"}
    with pytest.raises(PlannerError) as caught:
        asyncio.run(t.propose(planner, payload))
    assert caught.value.code == "invalid_text_patch" and caught.value.cost_micros == 220
    assert len(requests) == 2


def test_http_text_proposal_preview_apply_replay_and_ownership(client, settings):
    settings.planner_provider = "stub"
    login(client)
    creation = create_draft(client)
    body = {"layer_id": layer(creation)["id"], "format": "feed", "instruction_fr": "Une couleur dorée"}
    url = f"/api/creations/{creation['id']}/text-proposals"
    assert post(client, url, body).status_code == 428
    response = client.post(url, json=body, headers={"If-Match": '"1"', "Idempotency-Key": key()})
    assert response.status_code == 202, response.text
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        job = client.get(response.json()["status_url"]).json()
        if job["status"] not in {"queued", "running"}:
            break
        time.sleep(.1)
    assert job["status"] == "succeeded", job
    id = job["result_ref"]
    view = client.get(f"/api/text-proposals/{id}").json()
    assert view["before"] == creation["document"]
    assert view["status"] == "pending" and view["after"] != view["before"]
    headers = {"If-Match": '"1"', "Idempotency-Key": key()}
    result = client.post(f"/api/text-proposals/{id}/apply", json={}, headers=headers)
    assert result.status_code == 200 and result.json()["document"] == view["after"]
    assert client.post(f"/api/text-proposals/{id}/apply", json={}, headers=headers).json() == result.json()
    assert client.get(f"/api/text-proposals/{key()}").status_code == 404
    assert client.get(f"/api/text-effects/{key()}").status_code == 404
    assert client.get("/api/usage").json()["recorded_micros"] == 0
