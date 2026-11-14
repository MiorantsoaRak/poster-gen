import asyncio
import itertools
import time

import pytest
from sqlalchemy import text

from affiche import assets
from affiche.db import write_tx
from affiche.visuals.gateway import prepare_provider_input
from affiche.posters import jobs, store, visuals
from affiche.posters.models import Document, PriceBadge, ProductInput, Profile
from affiche.posters.service import PosterService
from affiche.posters.worker import run_job
from test_api import client, create_draft, login, password_hash, post, settings  # noqa: F401
from test_db import engine  # noqa: F401
from test_config import env  # noqa: F401
from test_poster_drafts import draft, input_id, key, photo  # noqa: F401


def fixed(engine, settings, creation):
    return visuals.create_plan(engine, settings, 1, key(), creation["id"], creation["revision"],
                               visuals.PlanRequest(mode="fixed", direction="Terrasse tropicale"))[1]


def scene(engine, settings, creation, plan):
    return visuals.request_scene(engine, settings, 1, key(), creation["id"], creation["revision"],
                                 visuals.SceneRequest(plan_id=plan["id"], acknowledged_warnings=["low_resolution"]))[1]


def execute(engine, settings):
    service = PosterService(engine, settings)
    service.provider.delay = 0
    job = jobs.claim(engine, ("scene", "refine", "plan"))
    assert job
    return execute_claimed(engine, settings, job, service)


def execute_claimed(engine, settings, job, service=None):
    if service is None:
        service = PosterService(engine, settings)
        service.provider.delay = 0
    assert asyncio.run(run_job(engine, settings, job, prepare=service.prepare, send=service.send, finalise=service.finalise))
    with engine.connect() as conn:
        return jobs.get_job(conn, 1, job["id"])["result_ref"]


@pytest.mark.parametrize("flags", list(itertools.product((False, True), repeat=3)))
def test_actual_draft_dimensions_fit_plan_and_auto_selected_scene(engine, settings, input_id, flags):
    logo = store.upload(engine, settings.data_dir, 1, photo(), "logo")["asset"]
    store.save_profile(engine, settings.data_dir, 1, key(), Profile(name="Original Phone Mada",
                       contact="038 93 028 00 / 034 93 028 00", logo_asset=logo), 1)
    creation = draft(engine, settings.data_dir, input_id, dict(zip(("logo", "shop_name", "contact"), flags)))
    plan = fixed(engine, settings, creation)
    scene(engine, settings, creation, plan)
    visual_id = execute(engine, settings)
    with engine.connect() as conn:
        saved = store.get_creation(conn, 1, creation["id"])
        visual = visuals.get_visual(conn, 1, visual_id)
    assert saved["revision"] == 2 and saved["document"]["formats"]["feed"]["scene"]["visual_id"] == visual_id
    assert visual["status"] == "pending_review"
    assert saved["document"]["offer"] == creation["document"]["offer"]
    store.save_creation(engine, settings.data_dir, 1, key(), creation["id"], Document.model_validate(saved["document"]), 2)


@pytest.mark.parametrize("configured, used", [(None, "high"), ("medium", "medium")])
def test_scene_quality_follows_the_setting(engine, settings, input_id, configured, used):
    settings = settings.model_copy(update={"openai_image_quality": configured})
    creation = draft(engine, settings.data_dir, input_id, {})
    scene(engine, settings, creation, fixed(engine, settings, creation))
    job = jobs.claim(engine, ("scene",))
    with engine.connect() as conn:
        visual = visuals.get_visual(conn, 1, execute_claimed(engine, settings, job))
    assert visual["quality"] == used


def test_first_scene_keeps_a_styled_price_pill_size_and_centres_it(engine, settings, input_id):
    creation = draft(engine, settings.data_dir, input_id)
    document = Document.model_validate(creation["document"])
    price = next(layer for layer in document.formats["feed"].layers if layer.role == "price")
    price.width, price.height, price.x, price.y = 540, 112, 0, 0
    price.price_badge = PriceBadge(fill="#22262E", border_start="#22262E", border_end="#55585F")
    creation = store.save_creation(engine, settings.data_dir, 1, key(), creation["id"], document, creation["revision"])[1]
    plan = fixed(engine, settings, creation)
    scene(engine, settings, creation, plan)
    execute(engine, settings)
    with engine.connect() as conn:
        saved = store.get_creation(conn, 1, creation["id"])["document"]["formats"]["feed"]["layers"]
    pill = next(layer for layer in saved if layer["role"] == "price")
    box = next(region["box"] for region in plan["plan"]["overlay_regions"] if region["field"] == "price")
    assert (pill["width"], pill["height"]) == (540, 112)
    assert pill["x"] == pytest.approx(270) and pill["y"] + 56 == pytest.approx((box["y"] + box["h"] / 2) * 1350)
    title = next(layer for layer in saved if layer["role"] == "title")
    assert title["width"] == pytest.approx(.9 * 1080)  # plain layers still take their planned box


def test_late_scene_never_overwrites_edits_and_stale_plan_refused(engine, settings, input_id):
    creation = draft(engine, settings.data_dir, input_id)
    plan = fixed(engine, settings, creation)
    scene(engine, settings, creation, plan)
    document = Document.model_validate(creation["document"])
    document.offer.price_ar = 123000
    updated = store.save_creation(engine, settings.data_dir, 1, key(), creation["id"], document, 1)[1]
    visual_id = execute(engine, settings)
    with engine.connect() as conn:
        current = store.get_creation(conn, 1, creation["id"])
        assert visuals.get_visual(conn, 1, visual_id)["status"] == "pending_review"
    assert current == updated
    with pytest.raises(store.Refused, match="plan_stale"):
        scene(engine, settings, updated, plan)


def test_approved_base_survives_rejected_refinement_and_identity_roles(engine, settings, input_id):
    creation = draft(engine, settings.data_dir, input_id)
    plan = fixed(engine, settings, creation)
    scene(engine, settings, creation, plan)
    base_id = execute(engine, settings)
    approval = visuals.Decision(action="approve", checks={check: True for check in visuals.CHECKS})
    visuals.decide(engine, 1, key(), base_id, approval)
    with engine.connect() as conn:
        before = store.get_creation(conn, 1, creation["id"])
        base = visuals.get_visual(conn, 1, base_id)
    request = visuals.RefinementRequest(base_visual_id=base_id, instruction_fr="Une lumière plus chaude")
    result = visuals.request_refinement(engine, settings, 1, key(), creation["id"], 2, request)[1]
    service = PosterService(engine, settings)
    with engine.connect() as conn:
        job = dict(conn.execute(text("SELECT * FROM poster_jobs WHERE id=:id"), {"id": result["job_id"]}).mappings().one())
        call = dict(jobs.current_call(conn, job["id"]))
    prepared = service.prepare(job, call)
    assert prepared["payload"]["reference_roles"] == ["base", "original"]
    assert "Images 2 are the original" in prepared["payload"]["prompt"]
    assert len(prepared["images"]) == 2
    revised_id = execute(engine, settings)
    visuals.decide(engine, 1, key(), revised_id, visuals.Decision(action="reject", reasons=["coloris"]))
    with engine.connect() as conn:
        assert visuals.get_visual(conn, 1, base_id) == base
        assert store.get_creation(conn, 1, creation["id"]) == before
    with pytest.raises(store.Refused, match="review_decided"):
        visuals.decide(engine, 1, key(), revised_id, approval)


def test_low_resolution_and_missing_source_refused_before_reservation(engine, settings, input_id):
    creation = draft(engine, settings.data_dir, input_id)
    plan = fixed(engine, settings, creation)
    with pytest.raises(store.Refused, match="acknowledgement_required"):
        visuals.request_scene(engine, settings, 1, key(), creation["id"], 1, visuals.SceneRequest(plan_id=plan["id"]))
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM poster_jobs")).scalar_one() == 0


def test_stub_planner_and_manual_rebase_are_explicit(engine, settings, input_id):
    settings.planner_provider = "stub"
    creation = draft(engine, settings.data_dir, input_id)
    response = visuals.create_plan(engine, settings, 1, key(), creation["id"], 1,
                                   visuals.PlanRequest(mode="claude", direction="Terrasse tropicale"))
    assert response[0] == 202
    plan_id = execute(engine, settings)
    with engine.connect() as conn:
        plan = visuals.get_plan(conn, 1, plan_id)
    assert plan["source"] == "stub"
    doc = Document.model_validate(creation["document"])
    doc.offer.price_ar += 1
    store.save_creation(engine, settings.data_dir, 1, key(), creation["id"], doc, 1)
    edit = visuals.PlanRevision.model_validate({k: v for k, v in plan["plan"].items() if k not in {"schema_version", "summary_fr"}})
    revised = visuals.revise_plan(engine, settings, 1, key(), plan_id, 2, edit)[1]
    assert revised["source"] == "manual" and revised["origin_revision"] == 2 and revised["parent_plan_id"] == plan_id
    with engine.connect() as conn:
        assert visuals.get_plan(conn, 1, plan_id)["origin_revision"] == 1
        assert jobs.get_job(conn, 1, response[1]["job_id"])["usage"]["recorded_micros"] == 0


def test_cross_input_visual_and_outside_crop_rejected(engine, settings, input_id):
    creation = draft(engine, settings.data_dir, input_id)
    scene(engine, settings, creation, fixed(engine, settings, creation))
    execute(engine, settings)
    with engine.connect() as conn:
        saved = store.get_creation(conn, 1, creation["id"])
        product = store.get_input(conn, 1, input_id)
    doc = Document.model_validate(saved["document"])
    doc.formats["feed"].scene.crop.x = 1
    with pytest.raises(store.Refused, match="invalid_crop"):
        store.save_creation(engine, settings.data_dir, 1, key(), creation["id"], doc, 2)
    another_input = store.create_input(engine, settings.data_dir, 1, key(),
        ProductInput(name="Other model", variant="Other", photo_assets=product["photo_assets"]))[1]["id"]
    another = draft(engine, settings.data_dir, another_input)
    other_doc = Document.model_validate(another["document"])
    other_doc.formats["feed"].scene = Document.model_validate(saved["document"]).formats["feed"].scene
    with pytest.raises(store.Refused, match="invalid_reference"):
        store.save_creation(engine, settings.data_dir, 1, key(), another["id"], other_doc, 1)


def test_price_only_edit_reuses_exact_approved_visual_without_job(engine, settings, input_id):
    creation = draft(engine, settings.data_dir, input_id)
    scene(engine, settings, creation, fixed(engine, settings, creation))
    id = execute(engine, settings)
    visuals.decide(engine, 1, key(), id, visuals.Decision(action="approve", checks={check: True for check in visuals.CHECKS}))
    with engine.connect() as conn:
        saved = store.get_creation(conn, 1, creation["id"])
        _, before = visuals.read_visual_bytes(conn, settings.data_dir, 1, id)
    doc = Document.model_validate(saved["document"])
    doc.offer.price_ar = 250000
    store.save_creation(engine, settings.data_dir, 1, key(), creation["id"], doc, 2)
    with engine.connect() as conn:
        assert visuals.read_visual_bytes(conn, settings.data_dir, 1, id)[1] == before
        assert visuals.get_visual(conn, 1, id)["status"] == "approved"
        assert conn.execute(text("SELECT COUNT(*) FROM poster_jobs")).scalar_one() == 1


@pytest.mark.parametrize("instruction", ["Change le titre", "Make the font larger", "Prix 300000 Ar"])
def test_text_only_requests_cannot_regenerate_the_scene(instruction):
    with pytest.raises(ValueError):
        visuals.RefinementRequest(base_visual_id=key(), instruction_fr=instruction)


def wait_job(client, path):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        response = client.get(path)
        assert response.status_code == 200, response.text
        job = response.json()
        if job["status"] in {"succeeded", "failed", "interrupted"}:
            assert job["status"] == "succeeded", job
            return job["result_ref"]
        time.sleep(.1)
    pytest.fail("job did not finish")


def test_http_original_to_plan_scene_review_and_asset(client):
    login(client)
    creation = create_draft(client)
    headers = {"If-Match": '"1"', "Idempotency-Key": key()}
    planned = client.post(f'/api/creations/{creation["id"]}/plans', headers=headers,
                          json={"mode": "fixed", "direction": "Terrasse tropicale", "format": "feed"})
    assert planned.status_code == 201, planned.text
    style = client.post("/api/assets", files={"file": ("style.png", photo(colour="gold"), "image/png")},
                        data={"role": "style"})
    assert style.status_code == 201
    style_sha = style.json()["asset"]
    headers["Idempotency-Key"] = key()
    response = client.post(f'/api/creations/{creation["id"]}/scenes', headers=headers,
                           json={"plan_id": planned.json()["id"], "acknowledged_warnings": ["low_resolution"],
                                 "style_reference_asset": style_sha})
    assert response.status_code == 202, response.text
    visual_id = wait_job(client, response.json()["status_url"])
    visual = client.get(f"/api/visuals/{visual_id}").json()
    assert visual["style_reference_asset"] == style_sha
    assert f"/api/assets/{style_sha}" not in visual["original_urls"]
    image = client.get(visual["image_url"])
    assert image.status_code == 200 and image.headers["content-type"] == "image/png"
    assert image.content.startswith(b"\x89PNG")
    assert post(client, f"/api/visuals/{visual_id}/decision", {"action": "approve"}).status_code == 422
    approved = post(client, f"/api/visuals/{visual_id}/decision",
                    {"action": "approve", "checks": {check: True for check in visuals.CHECKS}})
    assert approved.json()["status"] == "approved"
    assert client.get(f'/api/creations/{creation["id"]}').json()["revision"] == 2
    assert len(client.get(f'/api/creations/{creation["id"]}/visuals').json()["items"]) == 1


@pytest.mark.parametrize("refine", [False, True])
def test_style_reference_order_bytes_and_immutable_provenance(engine, settings, input_id, refine):
    creation = draft(engine, settings.data_dir, input_id)
    plan = fixed(engine, settings, creation)
    style_bytes = photo(colour="gold")
    style = store.upload(engine, settings.data_dir, 1, style_bytes, "style")["asset"]
    if refine:
        scene(engine, settings, creation, plan)
        base_id = execute(engine, settings)
        result = visuals.request_refinement(engine, settings, 1, key(), creation["id"], 2,
            visuals.RefinementRequest(base_visual_id=base_id, instruction_fr="Warm lighting",
                                      style_reference_asset=style))[1]
    else:
        result = visuals.request_scene(engine, settings, 1, key(), creation["id"], 1,
            visuals.SceneRequest(plan_id=plan["id"], acknowledged_warnings=["low_resolution"],
                                 style_reference_asset=style))[1]
    service = PosterService(engine, settings)
    with engine.connect() as conn:
        job = dict(conn.execute(text("SELECT * FROM poster_jobs WHERE id=:id"), {"id": result["job_id"]}).mappings().one())
        call = dict(jobs.current_call(conn, job["id"]))
    prepared = service.prepare(job, call)
    assert prepared["payload"]["reference_roles"] == (["base"] if refine else []) + ["original", "style"]
    assert prepared["images"][-1] == prepare_provider_input(style_bytes)
    assert prepared["images"][-2] == prepare_provider_input(photo())
    assert len(prepared["images"]) == (3 if refine else 2)
    assert f"Image {3 if refine else 2} is a style reference only" in prepared["payload"]["prompt"]
    assert "Ignore its product, every word and number in it" in prepared["payload"]["prompt"]
    result_id = execute(engine, settings)
    with engine.connect() as conn:
        visual = visuals.get_visual(conn, 1, result_id)
        assert visual["style_reference_asset"] == style
        assert len(visual["original_urls"]) == 1
        assert store._asset(conn, settings.data_dir, 1, style, "style") == style_bytes


@pytest.mark.parametrize("failure", ["wrong_role", "cross_shop", "missing", "corrupt"])
def test_invalid_style_refused_before_spend(engine, settings, input_id, failure):
    creation = draft(engine, settings.data_dir, input_id)
    plan = fixed(engine, settings, creation)
    style = store.upload(engine, settings.data_dir, 1, photo(colour="gold"),
                         "original" if failure == "wrong_role" else "style")["asset"]
    if failure == "cross_shop":
        with engine.connect() as conn:
            with pytest.raises(store.Refused, match="unknown_asset"):
                store._asset(conn, settings.data_dir, 2, style, "style")
        # The pilot schema permits only shop 1; an ungranted asset exercises admission without changing it.
        with write_tx(engine) as conn:
            conn.execute(text("DELETE FROM asset_access WHERE asset_sha=:sha"), {"sha": style})
    if failure == "missing":
        assets.path(settings.data_dir, style, "png").unlink()
    if failure == "corrupt":
        assets.path(settings.data_dir, style, "png").write_bytes(b"corrupt")
    expected = {"wrong_role": "unknown_asset", "cross_shop": "unknown_asset", "missing": "asset_missing", "corrupt": "asset_corrupt"}[failure]
    with pytest.raises(store.Refused, match=expected):
        visuals.request_scene(engine, settings, 1, key(), creation["id"], 1,
            visuals.SceneRequest(plan_id=plan["id"], acknowledged_warnings=["low_resolution"], style_reference_asset=style))
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM poster_jobs")).scalar_one() == 0
        assert conn.execute(text("SELECT COUNT(*) FROM poster_calls")).scalar_one() == 0


def test_style_rechecked_at_dispatch_and_absent_style_replays_legacy_hash(engine, settings, input_id):
    creation = draft(engine, settings.data_dir, input_id)
    plan = fixed(engine, settings, creation)
    legacy_key = key()
    body = {"plan_id": plan["id"], "format": "feed", "acknowledged_warnings": ["low_resolution"]}
    prior = store.mutate(engine, 1, legacy_key, "POST", f"/api/creations/{creation['id']}/scenes", body,
                         lambda conn: (202, {"job_id": "legacy-response"}), revision=1)
    assert visuals.request_scene(engine, settings, 1, legacy_key, creation["id"], 1,
                                 visuals.SceneRequest(**body, style_reference_asset=None)) == prior
    style = store.upload(engine, settings.data_dir, 1, photo(colour="gold"), "style")["asset"]
    visuals.request_scene(engine, settings, 1, key(), creation["id"], 1,
                          visuals.SceneRequest(**body, style_reference_asset=style))
    job = jobs.claim(engine, ("scene",))
    with engine.connect() as conn:
        call = dict(jobs.current_call(conn, job["id"]))
    assets.path(settings.data_dir, style, "png").write_bytes(b"corrupt after admission")
    with pytest.raises(store.Refused, match="asset_corrupt"):
        PosterService(engine, settings).prepare(job, call)
