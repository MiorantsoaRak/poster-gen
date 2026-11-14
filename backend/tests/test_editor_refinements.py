import asyncio
import copy
import io
import json
from pathlib import Path

import pytest
from PIL import Image, ImageChops
from sqlalchemy import text

from affiche.db import write_tx
from affiche.posters import exports, rendering, store, visuals
from affiche.posters.models import Document, FORMATS, NewCreation, Offer, Profile, canonical
from affiche.posters.plans import Headline, PlanContext, brand_in_title, compile_scene, fixed_plan, validate_plan
from test_api import settings, password_hash  # noqa: F401
from test_config import env  # noqa: F401
from test_db import engine  # noqa: F401
from test_poster_drafts import input_id, key, photo  # noqa: F401
from test_poster_visuals import fixed, execute


@pytest.mark.parametrize('brand,title,expected', json.loads((Path(__file__).parents[2]/'frontend/tests/fixtures/brand-title-cases.json').read_text()))
def test_brand_word_boundaries(brand, title, expected):
    assert brand_in_title(brand, title) is expected


def test_deduplicated_headline_keeps_title_and_legacy_prompt():
    context = PlanContext(name='Bose QuietComfort', variant='Noir', direction='Studio clair', format='feed',
                          field_sizes={'title': {'w': .8, 'h': .15}, 'price': {'w': .4, 'h': .09}})
    assert 'logo_corner' not in json.loads(canonical(context))
    assert canonical(context) == canonical({'name':'Bose QuietComfort','variant':'Noir','direction':'Studio clair','format':'feed',
        'field_sizes':{'title':{'w':.8,'h':.15},'price':{'w':.4,'h':.09}}})
    assert canonical(context) == canonical(PlanContext.model_validate_json(canonical(context)))
    args = dict(photo_count=1, headline=Headline(brand='Bose', price=True), title='Bose QuietComfort', price_ar=1150000)
    current = compile_scene(fixed_plan(context), context, deduplicate_brand=True, **args)
    old = compile_scene(fixed_plan(context), context, deduplicate_brand=False, **args)
    assert 'first the brand name "Bose"' not in current
    assert 'the product name "Bose QuietComfort"' in current
    assert 'exactly the 1 quoted string' in current
    assert 'first the brand name "Bose"' in old


@pytest.mark.parametrize('format', FORMATS)
@pytest.mark.parametrize('corner', ['left', 'right'])
def test_corner_plan_and_stale_guards(engine, settings, input_id, format, corner):
    settings = settings.model_copy(update={'formats_enabled': tuple(FORMATS)})
    asset = store.upload(engine, settings.data_dir, 1, photo(colour=(0, 0, 0, 90)), 'logo')['asset']
    store.save_profile(engine, settings.data_dir, 1, key(), Profile(name='Boutique', logo_asset=asset), 1)
    poster = store.create_creation(engine, settings.data_dir, 1, key(), NewCreation(input_id=input_id,
        offer=Offer(title='Bose QuietComfort', price_ar=1150000), brand_selection={'logo': True, 'shop_name': False, 'contact': False},
        primary_format=format), formats_enabled=tuple(FORMATS))[1]
    document = Document.model_validate(poster['document'])
    width, height = FORMATS[format]
    logo = next(item for item in document.formats[format].layers if item.role == 'logo')
    logo.x, logo.y = (.05*width if corner == 'left' else .95*width-logo.width), (.13 if format == 'story' else .05)*height
    poster = store.save_creation(engine, settings.data_dir, 1, key(), poster['id'], document, poster['revision'], formats_enabled=tuple(FORMATS))[1]
    plan = fixed(engine, settings, poster, format)
    boxes = {item['field']:item['box'] for item in plan['plan']['overlay_regions']}
    assert boxes['title']['y'] >= boxes['logo']['y'] + boxes['logo']['h']
    assert boxes['logo']['x'] == pytest.approx(logo.x/width)
    visuals.request_scene(engine, settings, 1, key(), poster['id'], poster['revision'], visuals.SceneRequest(
        plan_id=plan['id'], format=format, acknowledged_warnings=['low_resolution'], headline=Headline(brand='Bose', price=True)))
    visual_id = execute(engine, settings)
    visuals.decide(engine, 1, key(), visual_id, visuals.Decision(action='approve', checks={c:True for c in visuals.CHECKS|visuals.TEXT_CHECKS}))
    with engine.connect() as conn:
        current = store.get_creation(conn, 1, poster['id'])
        raw = store._owned(conn, 'poster_visuals', 1, visual_id)
        view = visuals.get_visual(conn, 1, visual_id)
        assert view['headline']['brand_in_title'] is True
        document = Document.model_validate(current['document'])
        visuals.check_logo_placement(conn, 1, raw, document, format)
        build = rendering.bundle()
        snapshot = exports.effective_snapshot(conn, settings, 1, document, format, build)
        count = conn.execute(text('SELECT COUNT(*) FROM poster_calls')).scalar_one()
        crop = document.formats[format].scene.crop
        crop.x += 30
        with pytest.raises(store.Refused, match='logo_placement_stale'):
            visuals.check_logo_placement(conn, 1, raw, document, format)
        crop.x -= 30
    # Both corners in every format render the original narrow, translucent logo without stretching.
    def rendered(value):
        result = asyncio.run(rendering.render(value, format, snapshot['sources'], build))
        return Image.open(io.BytesIO(rendering.png_bytes(result['png'], format))).convert('RGB')
    composite = rendered(snapshot['document'])
    without = copy.deepcopy(snapshot['document'])
    without['include']['logo'] = False
    next(item for item in without['formats'][format]['layers'] if item['role'] == 'logo')['visible'] = False
    background = rendered(without)
    box = view['logo_box']
    changed = ImageChops.difference(composite, background).getbbox()
    assert changed and changed[0] >= box['x']-1 and changed[2] <= box['x']+box['width']+1
    assert changed[1] >= box['y']-1 and changed[3] <= box['y']+box['height']+1
    assert changed[2]-changed[0] <= box['width']*.55+2
    centre = (round(box['x']+box['width']/2), round(box['y']+box['height']/2))
    assert all(abs(actual-round(base*(1-90/255))) <= 2 for actual, base in zip(composite.getpixel(centre), background.getpixel(centre)))
    logo = next(item for item in document.formats[format].layers if item.role == 'logo')
    logo.x += 30
    changed = store.save_creation(engine, settings.data_dir, 1, key(), poster['id'], document, current['revision'], formats_enabled=tuple(FORMATS))[1]
    with pytest.raises(store.Refused, match='logo_placement_stale'):
        visuals.request_refinement(engine, settings, 1, key(), poster['id'], changed['revision'],
            visuals.RefinementRequest(base_visual_id=visual_id, format=format, instruction_fr='Lumière douce'))
    with engine.connect() as conn:
        assert conn.execute(text('SELECT COUNT(*) FROM poster_calls')).scalar_one() == count
        with pytest.raises(store.Refused, match='logo_placement_stale'):
            exports.effective_snapshot(conn, settings, 1, document, format, {})


def test_revised_plan_cannot_move_reserved_corner():
    context = PlanContext(name='Bose', variant='Noir', direction='Studio clair', format='feed', logo_corner='right',
        field_sizes={'title':{'w':.8,'h':.15},'price':{'w':.4,'h':.09},'logo':{'w':.12,'h':.1}})
    plan = fixed_plan(context)
    next(item.box for item in plan.overlay_regions if item.field=='logo').x=.05
    with pytest.raises(ValueError, match='logo_corner_mismatch'):
        validate_plan(plan, context)


@pytest.mark.parametrize('legacy', [False, True])
def test_refinement_inherits_brand_behavior_across_generations(engine, settings, input_id, legacy):
    poster = store.create_creation(engine, settings.data_dir, 1, key(), NewCreation(input_id=input_id,
        offer=Offer(title='Bose QuietComfort', price_ar=1150000),
        brand_selection={'logo': False, 'shop_name': False, 'contact': False}))[1]
    plan = fixed(engine, settings, poster)
    visuals.request_scene(engine, settings, 1, key(), poster['id'], poster['revision'], visuals.SceneRequest(
        plan_id=plan['id'], format='feed', acknowledged_warnings=['low_resolution'], headline=Headline(brand='Bose', price=True)))
    visual_id = execute(engine, settings)
    if legacy:
        # Historical payloads predate the server-owned compatibility marker.
        with write_tx(engine) as conn:
            visual = store._owned(conn, 'poster_visuals', 1, visual_id)
            job = store._owned(conn, 'poster_jobs', 1, visual['job_id'])
            payload = json.loads(job['input_json'])
            del payload['headline']['brand_in_title']
            conn.execute(text('UPDATE poster_jobs SET input_json=:payload WHERE id=:id'), {'payload':json.dumps(payload), 'id':job['id']})
    for _ in range(2):
        visuals.decide(engine, 1, key(), visual_id, visuals.Decision(action='approve', checks={c:True for c in visuals.CHECKS|visuals.TEXT_CHECKS}))
        with engine.connect() as conn:
            saved = store.get_creation(conn, 1, poster['id'])
        document = Document.model_validate(saved['document'])
        if document.formats['feed'].scene.visual_id != visual_id:
            document.formats['feed'].scene.visual_id = visual_id
            saved = store.save_creation(engine, settings.data_dir, 1, key(), poster['id'], document, saved['revision'])[1]
        visuals.request_refinement(engine, settings, 1, key(), poster['id'], saved['revision'],
            visuals.RefinementRequest(base_visual_id=visual_id, format='feed', instruction_fr='Lumière douce'))
        visual_id = execute(engine, settings)
        with engine.connect() as conn:
            visual = store._owned(conn, 'poster_visuals', 1, visual_id)
            payload = json.loads(store._owned(conn, 'poster_jobs', 1, visual['job_id'])['input_json'])
            assert payload['headline'].get('brand_in_title', False) is not legacy
            assert ('first the brand name "Bose"' in payload['prompt']) is legacy
            assert payload['headline']['title'] == 'Bose QuietComfort'
            assert payload['headline']['price_ar'] == 1150000


def test_footer_scene_logo_moved_up_is_restored_free(engine, settings, input_id):
    asset = store.upload(engine, settings.data_dir, 1, photo(colour=(0, 0, 0, 90)), 'logo')['asset']
    store.save_profile(engine, settings.data_dir, 1, key(), Profile(name='Boutique', logo_asset=asset), 1)
    poster = store.create_creation(engine, settings.data_dir, 1, key(), NewCreation(input_id=input_id,
        offer=Offer(title='Bose QuietComfort', price_ar=1150000), brand_selection={'logo': True, 'shop_name': False, 'contact': False}))[1]
    plan = fixed(engine, settings, poster)
    visuals.request_scene(engine, settings, 1, key(), poster['id'], poster['revision'], visuals.SceneRequest(
        plan_id=plan['id'], format='feed', acknowledged_warnings=['low_resolution'], headline=Headline(price=True)))
    visual_id = execute(engine, settings)
    visuals.decide(engine, 1, key(), visual_id, visuals.Decision(action='approve', checks={c:True for c in visuals.CHECKS|visuals.TEXT_CHECKS}))
    with engine.connect() as conn:
        raw = store._owned(conn, 'poster_visuals', 1, visual_id)
        view = visuals.get_visual(conn, 1, visual_id)
        document = Document.model_validate(store.get_creation(conn, 1, poster['id'])['document'])
        assert 'logo_box' not in view and view['logo_footer_box']['y'] >= FORMATS['feed'][1]/2
        logo = next(item for item in document.formats['feed'].layers if item.role == 'logo')
        logo.y = .05*FORMATS['feed'][1]
        with pytest.raises(store.Refused, match='logo_placement_stale'):
            visuals.check_logo_placement(conn, 1, raw, document, 'feed')
        # What « Remettre le logo en bas » does: the footer box back, the crop left as it is.
        for name, value in view['logo_footer_box'].items():
            setattr(logo, name, value)
        document.formats['feed'].scene.crop.x += 30
        visuals.check_logo_placement(conn, 1, raw, document, 'feed')
