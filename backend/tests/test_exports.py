import asyncio
import copy

import pytest
from sqlalchemy import text

from affiche import assets
from affiche.posters import exports, jobs, store, visuals
from affiche.posters.models import Document, PriceBadge, Profile
from affiche.posters.plans import Headline
from affiche.posters.service import PosterService
from affiche.posters.worker import run_job
from test_api import settings, password_hash  # noqa: F401
from test_config import env  # noqa: F401
from test_db import engine  # noqa: F401
from test_poster_drafts import draft, input_id, key  # noqa: F401
from test_poster_visuals import fixed, scene, execute


@pytest.fixture
def creation(engine, settings, input_id):
    original = draft(engine, settings.data_dir, input_id)
    scene(engine, settings, original, fixed(engine, settings, original))
    visual = execute(engine, settings)
    visuals.decide(engine, 1, key(), visual, visuals.Decision(action="approve", checks={check: True for check in visuals.CHECKS | visuals.TEXT_CHECKS}))
    with engine.connect() as conn:
        return store.get_creation(conn, 1, original["id"])


def render(engine, settings, creation):
    request = exports.request_render(engine, settings, 1, key(), creation["id"], creation["revision"], exports.RenderRequest())[1]
    repeated = exports.request_render(engine, settings, 1, key(), creation["id"], creation["revision"], exports.RenderRequest())[1]
    assert request == repeated
    job = jobs.claim(engine, ("render",))
    service = PosterService(engine, settings)
    assert asyncio.run(run_job(engine, settings, job, prepare=service.prepare, send=service.send, finalise=service.finalise))
    with engine.connect() as conn:
        id = jobs.get_job(conn, 1, job["id"])["result_ref"]
        return exports.get_render(conn, 1, id)


def confirm_request(render):
    return exports.ConfirmRequest(render_id=render["id"], png_sha256=render["png_sha256"],
        checks={check: True for check in ("framing", "content", "identity", "readability")},
        acknowledged_warning_ids=[warning["id"] for warning in render["warnings"]])


def test_confirmed_bytes_survive_edits_and_corruption_is_explicit(engine, settings, creation):
    preview = render(engine, settings, creation)
    mutation_key = key()
    request = confirm_request(preview)
    confirmed = exports.confirm(engine, settings, 1, mutation_key, creation["id"], creation["revision"], request)
    assert confirmed == exports.confirm(engine, settings, 1, mutation_key, creation["id"], creation["revision"], request)
    with engine.connect() as conn:
        row, data = exports.download(conn, settings, 1, confirmed[1]["confirmation_id"])
        assert data == exports.read_png(settings, exports.render_row(conn, 1, preview["id"]))
        before_cost = conn.execute(text("SELECT count(*) FROM poster_calls")).scalar_one()
        with pytest.raises(store.Refused, match="not_found"):
            exports.render_row(conn, 999, preview["id"])
    document = Document.model_validate(creation["document"])
    document.offer.price_ar += 1
    updated = store.save_creation(engine, settings.data_dir, 1, key(), creation["id"], document, creation["revision"])[1]
    with pytest.raises(store.Refused, match="preview_stale"):
        exports.confirm(engine, settings, 1, key(), creation["id"], updated["revision"], request)
    with engine.connect() as conn:
        assert exports.download(conn, settings, 1, row["id"])[1] == data
        assert conn.execute(text("SELECT count(*) FROM poster_calls")).scalar_one() == before_cost == 1
    assets.path(settings.data_dir, row["png_sha256"], "png").write_bytes(b"corrupt")
    with engine.connect() as conn, pytest.raises(store.Refused, match="export_missing"):
        exports.download(conn, settings, 1, row["id"])


def test_older_render_confirms_only_when_effective_format_unchanged(engine, settings, creation):
    preview = render(engine, settings, creation)
    document = Document.model_validate(creation["document"])
    document.brand_snapshot.name = "Invisible profile change"
    updated = store.save_creation(engine, settings.data_dir, 1, key(), creation["id"], document, creation["revision"])[1]
    request = confirm_request(preview)
    request.checks["identity"] = False
    with pytest.raises(store.Refused, match="confirmation_incomplete"):
        exports.confirm(engine, settings, 1, key(), creation["id"], updated["revision"], request)
    request.checks["identity"] = True
    result = exports.confirm(engine, settings, 1, key(), creation["id"], updated["revision"], request)[1]
    with engine.connect() as conn:
        row, _ = exports.download(conn, settings, 1, result["confirmation_id"])
        assert row["source_revision"] == creation["revision"] and row["confirmed_revision"] == updated["revision"]


def test_hidden_title_requires_scene_headline_with_the_current_title(engine, settings, creation, input_id):
    def hide_title(value, title=None):
        document = Document.model_validate(value["document"])
        next(layer for layer in document.formats["feed"].layers if layer.role == "title").visible = False
        document.offer.title = title or document.offer.title
        return store.save_creation(engine, settings.data_dir, 1, key(), value["id"], document, value["revision"])[1]

    plain = hide_title(creation)  # this scene has no integrated headline: the poster would have no title
    with pytest.raises(store.Refused, match="title_missing"):
        exports.request_render(engine, settings, 1, key(), plain["id"], plain["revision"], exports.RenderRequest())

    original = draft(engine, settings.data_dir, input_id)
    plan = fixed(engine, settings, original)
    visuals.request_scene(engine, settings, 1, key(), original["id"], original["revision"], visuals.SceneRequest(
        plan_id=plan["id"], acknowledged_warnings=["low_resolution"], headline=Headline(brand="JBL")))
    visual = execute(engine, settings)
    visuals.decide(engine, 1, key(), visual, visuals.Decision(action="approve", checks={check: True for check in visuals.CHECKS | visuals.TEXT_CHECKS}))
    with engine.connect() as conn:
        assert visuals.get_visual(conn, 1, visual)["headline"] == {
            "brand": "JBL", "subtitle": None, "accent_word": None, "accent_colour": None, "signature": False,
            "price": False, "look_id": None, "title": "Une enceinte"}
        job = conn.execute(text("SELECT input_json FROM poster_jobs WHERE result_ref=:id"), {"id": visual}).scalar_one()
        assert '\\"Une enceinte\\"' in job and "899" not in job
        current = store.get_creation(conn, 1, original["id"])
    hidden = hide_title(current)
    assert render(engine, settings, hidden)["png_sha256"]
    # Hidden titles still plan: a second scene for the same draft keeps the headline area.
    visuals.request_scene(engine, settings, 1, key(), hidden["id"], hidden["revision"], visuals.SceneRequest(
        plan_id=fixed(engine, settings, hidden)["id"], acknowledged_warnings=["low_resolution"], headline=Headline()))
    execute(engine, settings)
    with engine.connect() as conn:
        latest = store.get_creation(conn, 1, original["id"])
    renamed = hide_title(latest, "Autre nom")
    with pytest.raises(store.Refused, match="scene_unapproved|title_missing"):
        exports.request_render(engine, settings, 1, key(), renamed["id"], renamed["revision"], exports.RenderRequest())
    with pytest.raises(store.Refused, match="headline_stale"):
        visuals.request_refinement(engine, settings, 1, key(), renamed["id"], renamed["revision"], visuals.RefinementRequest(
            base_visual_id=renamed["document"]["formats"]["feed"]["scene"]["visual_id"], instruction_fr="Plus de lumière"))


def test_shop_signature_drawn_by_the_scene_must_match_the_poster_profile(engine, settings, input_id):
    contact = "038 93 028 00 / 034 93 028 00"
    store.save_profile(engine, settings.data_dir, 1, key(), Profile(name="Original Phone Mada", contact=contact), 1)
    original = draft(engine, settings.data_dir, input_id, {"logo": False, "shop_name": True, "contact": True})
    plan = fixed(engine, settings, original)
    visuals.request_scene(engine, settings, 1, key(), original["id"], original["revision"], visuals.SceneRequest(
        plan_id=plan["id"], acknowledged_warnings=["low_resolution"], headline=Headline(signature=True)))
    visual = execute(engine, settings)
    visuals.decide(engine, 1, key(), visual, visuals.Decision(action="approve", checks={check: True for check in visuals.CHECKS | visuals.TEXT_CHECKS}))
    with engine.connect() as conn:
        baked = visuals.get_visual(conn, 1, visual)["headline"]
        prompt = conn.execute(text("SELECT prompt_text FROM poster_visuals WHERE id=:id"), {"id": visual}).scalar_one()
        current = store.get_creation(conn, 1, original["id"])
    assert (baked["shop_name"], baked["contact"]) == ("Original Phone Mada", contact)
    assert f'"{contact}"' in prompt and "shop_name: the" not in prompt and "899" not in prompt
    layers = {layer["role"]: layer for layer in current["document"]["formats"]["feed"]["layers"]}
    assert not layers["shop_name"]["visible"] and not layers["contact"]["visible"] and layers["price"]["visible"]
    assert render(engine, settings, current)["png_sha256"]
    # The poster's own contact changes: the image no longer says what the poster claims.
    document = Document.model_validate(current["document"])
    document.brand_snapshot.contact = "034 00 000 00"
    changed = store.save_creation(engine, settings.data_dir, 1, key(), current["id"], document, current["revision"])[1]
    with pytest.raises(store.Refused, match="signature_missing"):
        exports.request_render(engine, settings, 1, key(), changed["id"], changed["revision"], exports.RenderRequest())
    with pytest.raises(store.Refused, match="headline_stale"):
        visuals.request_refinement(engine, settings, 1, key(), changed["id"], changed["revision"], visuals.RefinementRequest(
            base_visual_id=visual, instruction_fr="Plus de lumière"))
    # Showing the layer again does not excuse the old number still drawn in the image; nor does unticking it.
    next(layer for layer in document.formats["feed"].layers if layer.role == "contact").visible = True
    shown = store.save_creation(engine, settings.data_dir, 1, key(), changed["id"], document, changed["revision"])[1]
    with pytest.raises(store.Refused, match="signature_missing"):
        exports.request_render(engine, settings, 1, key(), shown["id"], shown["revision"], exports.RenderRequest())
    document.include.contact = False
    next(layer for layer in document.formats["feed"].layers if layer.role == "contact").visible = False
    removed = store.save_creation(engine, settings.data_dir, 1, key(), shown["id"], document, shown["revision"])[1]
    with pytest.raises(store.Refused, match="signature_missing"):
        exports.request_render(engine, settings, 1, key(), removed["id"], removed["revision"], exports.RenderRequest())


def test_price_drawn_by_the_scene_must_equal_the_offer_and_a_change_needs_a_new_scene(engine, settings, creation, input_id):
    def edit(value, **changes):
        document = Document.model_validate(value["document"])
        price = next(layer for layer in document.formats["feed"].layers if layer.role == "price")
        price.visible = changes.get("visible", price.visible)
        document.offer.price_ar = changes.get("price_ar", document.offer.price_ar)
        return store.save_creation(engine, settings.data_dir, 1, key(), value["id"], document, value["revision"])[1]

    hidden = edit(creation, visible=False)  # this scene drew no price: the poster would have none
    with pytest.raises(store.Refused, match="price_stale"):
        exports.request_render(engine, settings, 1, key(), hidden["id"], hidden["revision"], exports.RenderRequest())

    original = draft(engine, settings.data_dir, input_id)
    # The editor styles the price as a pill before the first scene; a live run showed that this branch
    # skipped hiding the layer, which doubled the price on the poster.
    styled = Document.model_validate(original["document"])
    pill = next(layer for layer in styled.formats["feed"].layers if layer.role == "price")
    pill.width, pill.height, pill.price_badge = 540, 112, PriceBadge()
    original = store.save_creation(engine, settings.data_dir, 1, key(), original["id"], styled, original["revision"])[1]
    visuals.request_scene(engine, settings, 1, key(), original["id"], original["revision"], visuals.SceneRequest(
        plan_id=fixed(engine, settings, original)["id"], acknowledged_warnings=["low_resolution"], headline=Headline(price=True)))
    visual = execute(engine, settings)
    with pytest.raises(store.Refused, match="fidelity_incomplete"):  # the drawn title and price must be reread too
        visuals.decide(engine, 1, key(), visual, visuals.Decision(action="approve", checks={check: True for check in visuals.CHECKS}))
    visuals.decide(engine, 1, key(), visual, visuals.Decision(action="approve", checks={check: True for check in visuals.CHECKS | visuals.TEXT_CHECKS}))
    with engine.connect() as conn:
        assert visuals.get_visual(conn, 1, visual)["headline"]["price_ar"] == 899000
        prompt = conn.execute(text("SELECT prompt_text FROM poster_visuals WHERE id=:id"), {"id": visual}).scalar_one()
        current = store.get_creation(conn, 1, original["id"])
    assert '"899 000"' in prompt and 'smaller upright "AR"' in prompt and "price: the" not in prompt
    assert not next(layer for layer in current["document"]["formats"]["feed"]["layers"] if layer["role"] == "price")["visible"]
    with engine.connect() as conn:
        assert visuals.required_checks(visuals.baked_headline(conn, 1, store._owned(conn, "poster_visuals", 1, visual))) == visuals.CHECKS | {"text_title", "text_price"}
    assert visuals.required_checks(None) == visuals.CHECKS
    assert visuals.required_checks({"title": "x", "contact": "034"}) == visuals.CHECKS | {"text_title", "text_signature"}
    assert render(engine, settings, current)["png_sha256"]
    for changed in (edit(current, price_ar=799000), ):
        with pytest.raises(store.Refused, match="price_stale"):
            exports.request_render(engine, settings, 1, key(), changed["id"], changed["revision"], exports.RenderRequest())
        with pytest.raises(store.Refused, match="headline_stale"):
            visuals.request_refinement(engine, settings, 1, key(), changed["id"], changed["revision"], visuals.RefinementRequest(
                base_visual_id=visual, instruction_fr="Plus de lumière"))
        # Showing the price layer again does not excuse the old amount still drawn in the image.
        shown = edit(changed, visible=True)
        with pytest.raises(store.Refused, match="price_stale"):
            exports.request_render(engine, settings, 1, key(), shown["id"], shown["revision"], exports.RenderRequest())
        # The way out is a new scene with the new amount.
        visuals.request_scene(engine, settings, 1, key(), shown["id"], shown["revision"], visuals.SceneRequest(
            plan_id=fixed(engine, settings, shown)["id"], acknowledged_warnings=["low_resolution"], headline=Headline(price=True)))
        with engine.connect() as conn:
            queued = conn.execute(text("SELECT input_json FROM poster_jobs ORDER BY created_at DESC LIMIT 1")).scalar_one()
            assert '"price_ar":799000' in queued and "799 000" in queued and "899 000" not in queued


def test_pending_scene_blocks_render_without_local_job(engine, settings, input_id):
    original = draft(engine, settings.data_dir, input_id)
    scene(engine, settings, original, fixed(engine, settings, original))
    execute(engine, settings)
    with engine.connect() as conn:
        current = store.get_creation(conn, 1, original["id"])
    with pytest.raises(store.Refused, match="scene_unapproved"):
        exports.request_render(engine, settings, 1, key(), current["id"], current["revision"], exports.RenderRequest())
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM poster_jobs WHERE kind='render'")).scalar_one() == 0


def test_reference_typography_fingerprints_currency_font_and_preserves_old_format_hash(engine, settings, creation):
    from affiche.posters.models import PriceBadge
    from affiche.posters import rendering
    doc = Document.model_validate(creation["document"])
    build = rendering.bundle()
    legacy_build = copy.deepcopy(build)
    legacy_build["manifest"]["fonts"] = [font for font in legacy_build["manifest"]["fonts"] if font["id"] != "montserrat-black-italic"]
    with engine.connect() as conn:
        def snapshot(bundle):
            return exports.effective_snapshot(conn, settings, 1, doc, "feed", bundle)["format_hash"]
        assert snapshot(build) == snapshot(legacy_build)
        price = next(layer for layer in doc.formats["feed"].layers if layer.role == "price")
        price.font_id, price.weight, price.price_badge = "montserrat-black-italic", 900, PriceBadge()
        before = snapshot(build)
        for font in build["manifest"]["fonts"]:
            if font["id"] == "noto-sans" and font["weight"] == 400:
                font["sha256"] = "a" * 64
        assert snapshot(build) != before


def test_edit_during_render_keeps_old_preview_without_replacing_current(engine, settings, creation):
    exports.request_render(engine, settings, 1, key(), creation["id"], creation["revision"], exports.RenderRequest())
    document = Document.model_validate(creation["document"])
    document.offer.title = "Titre plus récent"
    current = store.save_creation(engine, settings.data_dir, 1, key(), creation["id"], document, creation["revision"])[1]
    job = jobs.claim(engine, ("render",))
    service = PosterService(engine, settings)
    assert asyncio.run(run_job(engine, settings, job, prepare=service.prepare, send=service.send, finalise=service.finalise))
    with engine.connect() as conn:
        assert store.get_creation(conn, 1, creation["id"]) == current
        preview = exports.get_render(conn, 1, jobs.get_job(conn, 1, job["id"])["result_ref"])
    with pytest.raises(store.Refused, match="preview_stale"):
        exports.confirm(engine, settings, 1, key(), current["id"], current["revision"], confirm_request(preview))
