import io
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFilter

from affiche.posters.seal import find_disc

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "seal"
SIZE = (1088, 1360)


def scene(disc=(.50, .905, .12), *, backdrop=(214, 228, 244), shadow=True, extra=None, oval=1.0) -> bytes:
    """A light gradient backdrop with a white disc: centre x, centre y, diameter as fractions (width, height, width)."""
    image = Image.new("RGB", SIZE, backdrop)
    pixels = image.load()
    for y in range(0, SIZE[1], 2):  # a soft vertical gradient, as the real backdrops have
        for x in range(0, SIZE[0], 2):
            tone = tuple(min(255, c + (y * 8) // SIZE[1]) for c in backdrop)
            pixels[x, y] = pixels[x + 1, y] = pixels[x, y + 1] = pixels[x + 1, y + 1] = tone
    if disc:
        cx, cy, radius = disc[0] * SIZE[0], disc[1] * SIZE[1], disc[2] * SIZE[0] / 2
        box = (cx - radius, cy - radius * oval, cx + radius, cy + radius * oval)
        if shadow:
            under = Image.new("L", SIZE, 0)
            ImageDraw.Draw(under).ellipse((box[0] - 2, box[1] + 4, box[2] + 2, box[3] + 10), fill=90)
            image.paste((150, 165, 190), mask=under.filter(ImageFilter.GaussianBlur(8)))
        ImageDraw.Draw(image).ellipse(box, fill=(255, 255, 255))
    if extra:
        extra(ImageDraw.Draw(image))
    data = io.BytesIO()
    image.save(data, "PNG")
    return data.getvalue()


def test_disc_is_found_where_it_is_not_where_it_was_asked():
    found = find_disc(scene(), (.50, .905), .12)
    assert found and abs(found[0] - 544) <= 2 and abs(found[1] - 1230.8) <= 2 and abs(found[2] - 130.6) <= 3
    # Drawn 3 % to the right, 1.5 % higher and smaller than asked, as the image model does.
    moved = find_disc(scene((.53, .89, .107)), (.50, .905), .12)
    assert moved and abs(moved[0] - .53 * 1088) <= 2 and abs(moved[1] - .89 * 1360) <= 2 and abs(moved[2] - 116.4) <= 3


def test_a_footer_drawn_lower_than_asked_is_still_found():
    # The first paid Story scene (2026-11-14): asked at 83.5 % of the height, drawn at 88.7 %, 77 % of the diameter.
    low = find_disc(scene((.50, .887, .092)), (.50, .835), .12)
    assert low and abs(low[0] - 544) <= 2 and abs(low[1] - .887 * 1360) <= 2 and abs(low[2] - 100) <= 3
    assert find_disc(scene((.50, .96, .092)), (.50, .835), .12) is None  # 12.5 % away is another object


@pytest.mark.parametrize("case", ["none", "oval", "tiny", "huge", "touched", "far"])
def test_nothing_is_guessed(case):
    def pill(draw):  # a white price pill running into the disc: the region is no longer round
        draw.rounded_rectangle((300, 1195, 560, 1265), radius=35, fill=(255, 255, 255))
    image = {"none": lambda: scene(None), "oval": lambda: scene(oval=.7),
             "tiny": lambda: scene((.50, .905, .06)), "huge": lambda: scene((.50, .905, .25)),
             "touched": lambda: scene(extra=pill), "far": lambda: scene((.80, .905, .12))}[case]()
    assert find_disc(image, (.50, .905), .12) is None


def test_white_backdrop_needs_a_visible_edge():
    white = (255, 255, 255)
    assert find_disc(scene(backdrop=white, shadow=False), (.50, .905), .12) is None  # the disc cannot be told apart
    # With the asked shadow the disc may be found; what matters is that a wrong region is never returned.
    found = find_disc(scene(backdrop=white), (.50, .905), .12)
    assert found is None or abs(found[2] - 130.6) <= 6


def test_any_failure_means_not_found(caplog):
    assert find_disc(b"not an image", (.5, .9), .12) is None
    assert "logo disc search failed" in caplog.text


@pytest.mark.parametrize("name,asked,expected", [
    # Two real scenes from the logo study (reviews/logo-study-2026-11-12.md), reduced to half size.
    # Asked at 19 %, the model drew this one at 14.6 % (77 % of the request): still the disc.
    ("study-disc-19.png", (.50, .895, .19), (.503, .887, .146)),
    # The first paid scene through the application: asked at 12 %, drawn at 9.7 %, exactly where asked.
    ("app-disc-12.png", (.50, .904, .12), (.502, .904, .097)),
    ("study-disc-10.png", (.50, .905, .10), (.500, .909, .107)),
])
def test_real_scenes_from_the_study(name, asked, expected):
    data = (FIXTURES / name).read_bytes()
    width, height = Image.open(io.BytesIO(data)).size
    found = find_disc(data, asked[:2], asked[2])
    if expected is None:
        assert found is None
        return
    assert found, name
    assert abs(found[0] / width - expected[0]) < .006 and abs(found[1] / height - expected[1]) < .006
    assert abs(found[2] / width - expected[2]) < .008
