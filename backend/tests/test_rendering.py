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
