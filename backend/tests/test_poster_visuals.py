import asyncio
import itertools
import time

import pytest
from pydantic import SecretStr
from sqlalchemy import text

from affiche import assets
from affiche.db import write_tx
from affiche.visuals.admission import spent_micros
from affiche.visuals.gateway import prepare_provider_input
from affiche.posters import exports, jobs, looks, store, typography, visuals
from affiche.posters.models import (
    FORMATS, CopyCreation, Crop, Document, NewCreation, Offer, PriceBadge, ProductInput, Profile, Scene,
)
from affiche.posters.service import PosterService
from affiche.posters.worker import run_job
from test_api import client, create_draft, login, password_hash, post, settings  # noqa: F401
from test_db import engine  # noqa: F401
from test_config import env  # noqa: F401
from test_gateway import KEY, USAGE, FakeApi, form_parts, image_reply, picture
from test_poster_drafts import draft, input_id, key, photo  # noqa: F401


def fixed(engine, settings, creation, format="feed"):
    return visuals.create_plan(engine, settings, 1, key(), creation["id"], creation["revision"],
                               visuals.PlanRequest(mode="fixed", direction="Terrasse tropicale", format=format))[1]


def scene(engine, settings, creation, plan, format="feed"):
    return visuals.request_scene(engine, settings, 1, key(), creation["id"], creation["revision"], visuals.SceneRequest(
        plan_id=plan["id"], format=format, acknowledged_warnings=["low_resolution"]))[1]


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


def wait_job(client, path, seconds=15):
    deadline = time.monotonic() + seconds
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


def reformat(creation, to):
    """The editor's format change before the first version: same layers, one layout, no scene."""
    document = Document.model_validate(creation["document"])
    layout = document.formats.pop(document.primary_format)
    document.primary_format, document.formats = to, {to: layout}
    return document


ALL = tuple(FORMATS)


def test_format_changes_only_before_the_first_version(engine, settings, input_id):
    settings.planner_provider, settings.formats_enabled = "stub", ALL
    def save(value, document):
        return store.save_creation(engine, settings.data_dir, 1, key(), value["id"], document, value["revision"],
                                   formats_enabled=ALL)[1]
    def current(value):
        with engine.connect() as conn:
            return store.get_creation(conn, 1, value["id"])
    creation = draft(engine, settings.data_dir, input_id)
    square = save(creation, reformat(creation, "square"))
    assert (square["revision"], square["document"]["primary_format"], list(square["document"]["formats"])) == (2, "square", ["square"])
    both = Document.model_validate(square["document"])
    both.formats["feed"] = both.formats["square"].model_copy(deep=True)
    with pytest.raises(store.Refused, match="format_locked"):  # one format per poster
        save(square, both)
    # A style brief is a plan job: it does not lock the format.
    reference = store.upload(engine, settings.data_dir, 1, photo(colour="gold"), "style")["asset"]
    looks.request_look(engine, settings, 1, key(), square["id"], square["revision"],
                       looks.LookRequest(name="Or", reference_asset=reference))
    story = save(square, reformat(square, "story"))
    execute(engine, settings)
    # A queued, then a running scene locks it.
    scene(engine, settings, story, fixed(engine, settings, story, "story"), "story")
    with pytest.raises(store.Refused, match="format_locked"):
        save(story, reformat(story, "feed"))
    job = jobs.claim(engine, ("scene",))
    with pytest.raises(store.Refused, match="format_locked"):
        save(story, reformat(story, "feed"))
    execute_claimed(engine, settings, job)
    placed = current(story)
    assert placed["document"]["formats"]["story"]["scene"]["visual_id"]
    # A version exists for this product input: removing the scene from the document does not free the format.
    cleared = Document.model_validate(placed["document"])
    cleared.formats["story"].scene = Scene()
    cleared = save(placed, cleared)
    with pytest.raises(store.Refused, match="format_locked"):
        save(cleared, reformat(cleared, "feed"))
    # The same rule holds for a copy that carries an unsaved document.
    with pytest.raises(store.Refused, match="format_locked"):
        store.copy_creation(engine, settings.data_dir, 1, key(), cleared["id"], CopyCreation(
            source_revision=cleared["revision"], reason="save_conflict", unsaved_document=reformat(cleared, "feed")),
            formats_enabled=ALL)
    kept = store.copy_creation(engine, settings.data_dir, 1, key(), cleared["id"], CopyCreation(
        source_revision=cleared["revision"], reason="save_conflict", unsaved_document=Document.model_validate(cleared["document"])))[1]
    assert kept["document"]["primary_format"] == "story"
    # The way out: a new input with the same body; the copy onto it has no version, so its format is free.
    with engine.connect() as conn:
        source = store.get_input(conn, 1, input_id)
    again = store.create_input(engine, settings.data_dir, 1, key(), ProductInput(
        name=source["name"], variant=source["variant"], photo_assets=source["photo_assets"]))[1]["id"]
    remade = store.copy_creation(engine, settings.data_dir, 1, key(), cleared["id"], CopyCreation(
        source_revision=cleared["revision"], reason="replace_input", new_input_id=again))[1]
    assert save(remade, reformat(remade, "feed"))["document"]["primary_format"] == "feed"


def square_draft(engine, settings, input_id):
    return store.create_creation(engine, settings.data_dir, 1, key(), NewCreation(
        input_id=input_id, offer=Offer(title="Une enceinte", price_ar=899000),
        brand_selection={"logo": False, "shop_name": False, "contact": False}, primary_format="square"),
        formats_enabled=ALL)[1]


def test_a_scene_belongs_to_the_format_it_was_made_for(engine, settings, input_id):
    settings.formats_enabled = ALL
    feed = draft(engine, settings.data_dir, input_id)
    scene(engine, settings, feed, fixed(engine, settings, feed))
    visual_id = execute(engine, settings)
    # A second poster of the same product input, made in another format, meets that feed version.
    square = square_draft(engine, settings, input_id)
    mixed = Document.model_validate(square["document"])
    mixed.formats["square"].scene = Scene(visual_id=visual_id, crop=Crop(x=0, y=0, w=1088, h=1088))
    with pytest.raises(store.Refused, match="scene_format_mismatch"):
        store.save_creation(engine, settings.data_dir, 1, key(), square["id"], mixed, square["revision"])
    # A draft saved in that state before the check: no paid refinement at the wrong size, no export.
    with write_tx(engine) as conn:
        store._insert_version(conn, square["id"], 2, mixed)
        conn.execute(text("UPDATE creations SET current_revision=2 WHERE id=:id"), {"id": square["id"]})
    with pytest.raises(store.Refused, match="scene_format_mismatch"):
        visuals.request_refinement(engine, settings, 1, key(), square["id"], 2, visuals.RefinementRequest(
            base_visual_id=visual_id, format="square", instruction_fr="Plus de lumière"))
    with pytest.raises(store.Refused, match="scene_format_mismatch"):
        exports.request_render(engine, settings, 1, key(), square["id"], 2, exports.RenderRequest(format="square"))
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM poster_jobs WHERE kind IN ('refine','render')")).scalar_one() == 0


def test_a_format_not_enabled_is_refused_wherever_a_poster_gets_it(engine, settings, input_id):
    assert settings.formats_enabled == ("feed",)  # the default: Square and Story wait for a paid check
    with pytest.raises(store.Refused, match="format_unavailable"):
        store.create_creation(engine, settings.data_dir, 1, key(), NewCreation(
            input_id=input_id, offer=Offer(title="Une enceinte", price_ar=899000),
            brand_selection={"logo": False, "shop_name": False, "contact": False}, primary_format="story"),
            formats_enabled=settings.formats_enabled)
    creation = draft(engine, settings.data_dir, input_id)
    with pytest.raises(store.Refused, match="format_unavailable"):
        store.save_creation(engine, settings.data_dir, 1, key(), creation["id"], reformat(creation, "story"), 1,
                            formats_enabled=settings.formats_enabled)
    with pytest.raises(store.Refused, match="format_unavailable"):
        store.copy_creation(engine, settings.data_dir, 1, key(), creation["id"], CopyCreation(
            source_revision=1, reason="save_conflict", unsaved_document=reformat(creation, "square")),
            formats_enabled=settings.formats_enabled)
    # A poster made while Square was on keeps its format, but is not exported once Square is off again.
    square = square_draft(engine, settings, input_id)
    with pytest.raises(store.Refused, match="format_unavailable"):
        exports.request_render(engine, settings, 1, key(), square["id"], 1, exports.RenderRequest(format="square"))
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM creations")).scalar_one() == 2
        assert conn.execute(text("SELECT COUNT(*) FROM poster_jobs")).scalar_one() == 0


def test_nothing_is_paid_for_in_a_format_switched_off(engine, settings, input_id):
    """A Square poster made while Square was on: once it is off again, no request in that format makes a job."""
    settings.formats_enabled, settings.planner_provider = ALL, "stub"
    square = square_draft(engine, settings, input_id)
    plan = fixed(engine, settings, square, "square")
    scene(engine, settings, square, plan, "square")
    base = execute(engine, settings)
    with engine.connect() as conn:
        current = store.get_creation(conn, 1, square["id"])
    id, revision = current["id"], current["revision"]
    title = next(layer["id"] for layer in current["document"]["formats"]["square"]["layers"] if layer["role"] == "title")
    settings.formats_enabled = ("feed",)
    requests = {
        "claude plan": lambda: visuals.create_plan(engine, settings, 1, key(), id, revision, visuals.PlanRequest(
            mode="claude", direction="Studio clair", format="square")),
        "fixed plan": lambda: fixed(engine, settings, current, "square"),
        "plan revision": lambda: visuals.revise_plan(engine, settings, 1, key(), plan["id"], revision,
            visuals.PlanRevision.model_validate({k: v for k, v in plan["plan"].items() if k not in {"schema_version", "summary_fr"}})),
        "scene": lambda: scene(engine, settings, current, plan, "square"),
        "refinement": lambda: visuals.request_refinement(engine, settings, 1, key(), id, revision, visuals.RefinementRequest(
            base_visual_id=base, format="square", instruction_fr="Plus de lumière")),
        "text proposal": lambda: typography.request_proposal(engine, settings, 1, key(), id, revision, typography.ProposalRequest(
            format="square", layer_id=title, instruction_fr="Plus gras")),
        "text effect": lambda: typography.request_effect(engine, settings, 1, key(), id, revision, typography.EffectRequest(
            format="square", layer_id=title, proposal_id=key())),
    }
    def counts():
        with engine.connect() as conn:
            return [conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
                    for table in ("poster_jobs", "poster_calls", "scene_plans")]
    before = counts()
    for name, request in requests.items():
        with pytest.raises(store.Refused, match="format_unavailable"):
            request()
        assert counts() == before, name  # no job, no reservation, no plan
    settings.formats_enabled = ALL  # the same scene request is accepted while Square is on
    scene(engine, settings, current, fixed(engine, settings, current, "square"), "square")


def test_http_versions_are_listed_for_the_poster_format_only(client, settings):
    settings.formats_enabled = ALL
    login(client)
    creation = create_draft(client)
    headers = {"If-Match": '"1"', "Idempotency-Key": key()}
    planned = client.post(f'/api/creations/{creation["id"]}/plans', headers=headers,
                          json={"mode": "fixed", "direction": "Terrasse tropicale", "format": "feed"})
    response = post_scene(client, creation["id"], 1, planned.json()["id"])
    visual_id = wait_job(client, response.json()["status_url"])
    square = post(client, "/api/creations", {"input_id": creation["document"]["input_id"], "primary_format": "square",
                                             "offer": {"title": "JBL Flip", "price_ar": 899000},
                                             "brand_selection": {"logo": False, "shop_name": False, "contact": False}})
    assert square.status_code == 201, square.text
    assert [item["id"] for item in client.get(f'/api/creations/{creation["id"]}/visuals').json()["items"]] == [visual_id]
    assert client.get(f'/api/creations/{square.json()["id"]}/visuals').json()["items"] == []
    # The lock reaches the owner with its own sentence.
    document = client.get(f'/api/creations/{creation["id"]}').json()
    document["document"]["formats"] = {"story": document["document"]["formats"]["feed"]}
    document["document"]["primary_format"] = "story"
    document["document"]["formats"]["story"]["scene"] = {"visual_id": None, "crop": None}
    locked = client.put(f'/api/creations/{creation["id"]}', json=document["document"],
                        headers={"If-Match": f'"{document["revision"]}"', "Idempotency-Key": key()})
    assert locked.status_code == 409 and locked.json()["error"]["code"] == "format_locked"
    assert "première version" in locked.json()["error"]["message_fr"]


def test_a_scene_of_the_wrong_size_fails_the_job_and_keeps_its_cost(engine, settings, input_id):
    """D-POSTER-FORMAT-001 v2 point 12: a provider that answers another size than the format's (Story asked here)."""
    settings = settings.model_copy(update={"image_provider": "openai", "openai_api_key": SecretStr(KEY), "formats_enabled": ALL})
    story = store.create_creation(engine, settings.data_dir, 1, key(), NewCreation(
        input_id=input_id, offer=Offer(title="Une enceinte", price_ar=899000),
        brand_selection={"logo": False, "shop_name": False, "contact": False}, primary_format="story"),
        formats_enabled=ALL)[1]
    scene(engine, settings, story, fixed(engine, settings, story, "story"), "story")
    service = PosterService(engine, settings)
    api = FakeApi(image_reply(picture(size=(1088, 1360)), usage=USAGE))  # a feed-sized image, billed
    service.provider = api.provider()
    job = jobs.claim(engine, ("scene",))
    assert not asyncio.run(run_job(engine, settings, job, prepare=service.prepare, send=service.send, finalise=service.finalise))
    assert ("size", None, b"1152x2048") in form_parts(api.requests[0])
    with engine.connect() as conn:
        failed = jobs.get_job(conn, 1, job["id"])
        assert (failed["status"], failed["error_code"]) == ("failed", "invalid_response")
        # The answer's usage is not read once its size is wrong: the reservation stays in the ledger, marked estimated.
        assert failed["usage"] == {"recorded_micros": 400_000, "estimated": True}
        assert spent_micros(conn, settings) == 400_000
        assert conn.execute(text("SELECT COUNT(*) FROM poster_visuals")).scalar_one() == 0
        assert store.get_creation(conn, 1, story["id"])["revision"] == 1


def post_scene(client, id, revision, plan_id, format="feed"):
    response = client.post(f"/api/creations/{id}/scenes", headers={"If-Match": f'"{revision}"', "Idempotency-Key": key()},
                           json={"plan_id": plan_id, "format": format, "acknowledged_warnings": ["low_resolution"]})
    assert response.status_code == 202, response.text
    return response
