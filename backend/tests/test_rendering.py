import asyncio
import io

import pytest
from PIL import Image, ImageChops

from affiche.posters import rendering
from affiche.posters.store import Refused
from test_api import settings, password_hash  # noqa: F401
from test_config import env  # noqa: F401
from test_db import engine  # noqa: F401
from test_poster_drafts import draft, input_id  # noqa: F401


def test_canvas_preparation_keeps_alpha_and_bounds():
    image = Image.new("RGBA", (4200, 2), (10, 80, 160, 100))
    source = io.BytesIO()
    image.save(source, format="PNG")
    prepared = Image.open(io.BytesIO(rendering.canvas_image(source.getvalue())))
    assert prepared.width == 4096 and prepared.mode == "RGBA"
    assert prepared.getpixel((10, 0))[3] == 100


def test_missing_bundle_is_explicit(tmp_path):
    with pytest.raises(Refused, match="renderer_unavailable"):
        rendering.bundle(tmp_path)


def test_actual_offline_shared_canvas_is_repeatable_and_rejects_overflow(engine, settings, input_id):
    document = draft(engine, settings.data_dir, input_id)["document"]
    build = rendering.bundle()
    first = asyncio.run(rendering.render(document, "feed", {}, build))
    second = asyncio.run(rendering.render(document, "feed", {}, build))
    assert rendering.png_bytes(first["png"], "feed") == rendering.png_bytes(second["png"], "feed")
    assert Image.open(io.BytesIO(rendering.png_bytes(first["png"], "feed"))).size == (1080, 1350)
    document["offer"]["title"] = "Écouteurs " * 23
    with pytest.raises(Refused, match="layout_invalid"):
        asyncio.run(rendering.render(document, "feed", {}, build))


def test_offline_shared_canvas_fails_on_missing_or_untrusted_image(engine, settings, input_id):
    document = draft(engine, settings.data_dir, input_id)["document"]
    scene = document["formats"]["feed"]["scene"]
    scene.update(visual_id=input_id, crop={"x": 0, "y": 0, "w": 1088, "h": 1360})
    with pytest.raises(Refused, match="render_unavailable"):
        asyncio.run(rendering.render(document, "feed", {f"scene:{input_id}": "https://untrusted.invalid/image.png"}, rendering.bundle()))


def test_compact_contact_is_one_line_with_a_handset_at_a_readable_size(engine, settings, input_id):
    document = draft(engine, settings.data_dir, input_id)["document"]
    layers = document["formats"]["feed"]["layers"]
    title = next(layer for layer in layers if layer["role"] == "title")
    contact = dict(title, id="11111111-1111-4111-8111-111111111111", role="contact", visible=False, z=title["z"] + 5,
                   x=200, y=1250, width=800, height=48, font_id="noto-sans", weight=700, font_size=32,
                   fill="#FFFFFF", align="left", outline=None, shadow=None, texture_effect_id=None, icon="phone")
    layers.append(contact)
    document["include"]["contact"] = True
    document["brand_snapshot"]["contact"] = "038 93 028 00"  # digits only, so the ink height is the digit height
    build = rendering.bundle()

    def image():
        result = asyncio.run(rendering.render(document, "feed", {}, build))
        return Image.open(io.BytesIO(rendering.png_bytes(result["png"], "feed"))).convert("RGB")

    empty = image()
    contact["visible"] = True
    boxes = {}
    for align in ("left", "center", "right"):
        contact["align"] = align
        boxes[align] = ImageChops.difference(empty, image()).getbbox()
    left, centre, right = boxes["left"], boxes["center"], boxes["right"]
    for box in boxes.values():
        assert box and 22 <= box[3] - box[1] <= 30, box  # R-CATALOGUE-BRAND-003: digits at least 22 px on 1350
        assert box[0] >= 199 and box[2] <= 1001 and box[1] >= 1250 and box[3] <= 1298, box
    assert left[0] <= 202 and right[2] >= 998, boxes
    assert abs((centre[0] + centre[2]) / 2 - 600) <= 2, boxes
    widths = {box[2] - box[0] for box in boxes.values()}
    assert max(widths) - min(widths) <= 2, boxes
    # The handset is drawn, not a glyph: without the icon the same text is narrower by the icon and its gap.
    contact.pop("icon")
    contact["align"] = "left"
    plain = ImageChops.difference(empty, image()).getbbox()
    assert 25 <= (left[2] - left[0]) - (plain[2] - plain[0]) <= 45, (left, plain)
    # A contact too long for one line is refused, never cut or wrapped.
    contact["icon"] = "phone"
    document["brand_snapshot"]["contact"] = "038 93 028 00 / 034 93 028 00 / 032 93 028 00 / 033 93 028 00 / 020 22 028 00"
    with pytest.raises(Refused, match="layout_invalid"):
        image()


def test_the_price_pill_stays_in_front_of_a_layer_with_a_higher_z(engine, settings, input_id):
    document = draft(engine, settings.data_dir, input_id)["document"]
    layers = document["formats"]["feed"]["layers"]
    price = next(layer for layer in layers if layer["role"] == "price")
    price.update(font_id="montserrat-black-italic", weight=900, font_size=96, fill="#15171A",
                 x=240, y=900, width=600, height=150, align="center",
                 price_badge={"fill": "#FFFFFF", "border_start": "#009FE3", "border_end": "#1853BD"})
    document["offer"]["price_ar"] = 90000
    # A red contact line crossing the pill, with a z above it (added after the price, as a ticked box does).
    contact = dict(price, id="22222222-2222-4222-8222-222222222222", role="contact", z=price["z"] + 5, visible=False,
                   x=60, y=950, width=960, height=48, font_id="noto-sans", weight=700, font_size=32, fill="#FF0000",
                   align="left", price_badge=None, icon=None)
    layers.append(contact)
    document["include"]["contact"] = True
    document["brand_snapshot"]["contact"] = "038 93 028 00 038 93 028 00 038 93 028 00"
    build = rendering.bundle()

    def image():
        result = asyncio.run(rendering.render(document, "feed", {}, build))
        return Image.open(io.BytesIO(rendering.png_bytes(result["png"], "feed"))).convert("RGB")

    without = image()
    contact["visible"] = True
    crossing = image()
    changed = ImageChops.difference(without, crossing)
    assert changed.crop((60, 950, 230, 998)).getbbox(), "the contact line must be drawn where it is clear of the pill"
    assert changed.crop((320, 920, 760, 1030)).getbbox() is None, "the contact line was drawn over the price pill"


def test_reference_price_capsule_is_isolated_exact_and_checks_overflow(engine, settings, input_id):
    document = draft(engine, settings.data_dir, input_id)["document"]
    price = next(layer for layer in document["formats"]["feed"]["layers"] if layer["role"] == "price")
    price.update(font_id="montserrat-black-italic", weight=900, font_size=96, fill="#15171A",
                 x=240, y=900, width=600, height=150, align="center")
    document["offer"]["price_ar"] = 90000
    build = rendering.bundle()
    def image():
        result = asyncio.run(rendering.render(document, "feed", {}, build))
        return Image.open(io.BytesIO(rendering.png_bytes(result["png"], "feed"))).convert("RGB")
    plain = image()
    price["price_badge"] = {"fill": "#FFFFFF", "border_start": "#009FE3", "border_end": "#1853BD"}
    badge = image()
    bounds = ImageChops.difference(plain, badge).getbbox()
    assert bounds and bounds[0] >= 240 and bounds[1] >= 900 and bounds[2] <= 840 and bounds[3] <= 1050
    assert badge.getpixel((540, 910)) == (255, 255, 255)
    document["offer"]["price_ar"] = 95000
    changed = image()
    bounds = ImageChops.difference(badge, changed).getbbox()
    assert bounds and bounds[0] >= 240 and bounds[1] >= 900 and bounds[2] <= 840 and bounds[3] <= 1050
    document["offer"]["price_ar"] = 0
    assert image().size == (1080, 1350)
    document["offer"]["price_ar"] = 9_007_199_254_740_991
    with pytest.raises(Refused, match="layout_invalid"):
        image()
    document["offer"]["price_ar"] = 90000
    price["height"] = 40
    with pytest.raises(Refused, match="layout_invalid"):
        image()
    price["height"] = 150
    title = next(layer for layer in document["formats"]["feed"]["layers"] if layer["role"] == "title")
    title.update(font_id="montserrat-black-italic", weight=900, x=0, width=200, height=200, font_size=140)
    document["offer"]["title"] = "J"
    with pytest.raises(Refused, match="layout_invalid"):
        image()
