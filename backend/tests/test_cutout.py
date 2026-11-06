"""The cutout pipeline with injected masks (no model), the placement and the shadow. One test runs the real model.
Every image is drawn here: no shop photo."""

import io
import struct
import sys

import numpy as np
import pytest
from PIL import ExifTags, Image, ImageCms, ImageDraw, ImageOps

from affiche.config import Settings
from affiche.visuals.cutout import SAFE_SQUARE, Cutout, CutoutUnavailable, bake_shadow, make_cutout, place
from affiche.visuals.gateway import OUTPUT_SIZE
from test_gateway import encode, gama, gps_jpeg, linear_gray_profile, png_with, text_png

MODEL = Settings.model_fields["rembg_model"].default
SETUP = f"uv run python -c \"from rembg import new_session; new_session('{MODEL}')\""


# --- Samples ------------------------------------------------------------------------------------------------------

def noisy(scene: Image.Image, seed: int) -> Image.Image:
    """Sensor-like noise, so that any change to a pixel shows."""
    pixels = np.asarray(scene, dtype=np.int16)
    pixels = pixels + np.random.default_rng(seed).integers(-12, 13, pixels.shape)
    return Image.fromarray(pixels.clip(0, 255).astype(np.uint8))


def gradient(size: tuple[int, int], top: tuple[int, ...], bottom: tuple[int, ...]) -> Image.Image:
    width, height = size
    weight = np.linspace(0, 1, height)[:, None, None]
    rows = np.array(top) * (1 - weight) + np.array(bottom) * weight
    return Image.fromarray(np.broadcast_to(rows, (height, width, 3)).astype(np.uint8))


def phone() -> tuple[Image.Image, Image.Image]:
    """A tall phone: a rounded body with a camera bump, a lens and a glossy reflection, on a gradient."""
    scene, mask = gradient((600, 900), (235, 230, 220), (175, 170, 160)), Image.new("L", (600, 900), 0)
    body = (180, 120, 420, 780)
    ImageDraw.Draw(mask).rounded_rectangle(body, radius=40, fill=255)
    draw = ImageDraw.Draw(scene)
    draw.rounded_rectangle(body, radius=40, fill=(30, 32, 40))
    draw.rounded_rectangle((200, 140, 300, 260), radius=24, fill=(70, 72, 80))
    draw.ellipse((215, 155, 255, 195), fill=(10, 10, 15))
    draw.polygon([(200, 300), (400, 300), (200, 620)], fill=(95, 100, 115))
    return noisy(scene, 1), mask


def speaker() -> tuple[Image.Image, Image.Image]:
    """A wide speaker: a long red body with two grilles, on a flat light background."""
    scene, mask = Image.new("RGB", (1000, 600), (240, 240, 236)), Image.new("L", (1000, 600), 0)
    body = (100, 220, 900, 420)
    ImageDraw.Draw(mask).rounded_rectangle(body, radius=60, fill=255)
    draw = ImageDraw.Draw(scene)
    draw.rounded_rectangle(body, radius=60, fill=(150, 30, 40))
    for left in (160, 700):
        draw.ellipse((left, 250, left + 140, 390), fill=(60, 15, 20))
    return noisy(scene, 2), mask


def earbuds_case() -> tuple[Image.Image, Image.Image]:
    """A small white earbuds case on a checkered (textured) background."""
    rows, columns = np.indices((700, 700))
    checks = ((rows // 35 + columns // 35) % 2).astype(bool)[..., None]
    scene = Image.fromarray(np.where(checks, (200, 190, 170), (165, 155, 135)).astype(np.uint8))
    mask, case = Image.new("L", (700, 700), 0), (250, 260, 450, 420)
    ImageDraw.Draw(mask).ellipse(case, fill=255)
    draw = ImageDraw.Draw(scene)
    draw.ellipse(case, fill=(245, 245, 242))
    draw.line((255, 330, 445, 330), fill=(200, 200, 198), width=3)  # the lid seam
    return noisy(scene, 3), mask


SAMPLES = [phone, speaker, earbuds_case]


def centred_ellipse(size: tuple[int, int]) -> Image.Image:
    width, height = size
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).ellipse((width // 4, height // 4, 3 * width // 4, 3 * height // 4), fill=255)
    return mask


def plain(size: tuple[int, int] = (200, 200)) -> bytes:
    return encode(noisy(Image.new("RGB", size, (120, 140, 160)), 5))


def linear_rgb_profile() -> bytes:
    """A minimal ICC v2 RGB display profile: sRGB primaries (D50) with gamma 1.0, so not sRGB."""
    def xyz(*values: float) -> bytes:
        return b"".join(struct.pack(">i", round(value * 65536)) for value in values)

    d50, linear = xyz(0.9642, 1.0, 0.8249), b"curv" + bytes(4) + struct.pack(">IH", 1, 256) + bytes(2)
    tags = [(b"wtpt", b"XYZ " + bytes(4) + d50), (b"rXYZ", b"XYZ " + bytes(4) + xyz(0.4361, 0.2225, 0.0139)),
            (b"gXYZ", b"XYZ " + bytes(4) + xyz(0.3851, 0.7169, 0.0971)),
            (b"bXYZ", b"XYZ " + bytes(4) + xyz(0.1431, 0.0606, 0.7141)),
            (b"rTRC", linear), (b"gTRC", linear), (b"bTRC", linear)]
    offset, table, data = 128 + 4 + 12 * len(tags), b"", b""
    for signature, tag in tags:
        table += signature + struct.pack(">II", offset + len(data), len(tag))
        data += tag
    header = (struct.pack(">I", offset + len(data)) + bytes(4) + struct.pack(">I", 0x02100000) + b"mntrRGB XYZ "
              + bytes(12) + b"acsp" + bytes(28) + d50 + bytes(48))
    return header + struct.pack(">I", len(tags)) + table + data


class FakeMask:
    """A mask_fn: the drawn mask at the size it is asked for. It records the images it receives."""

    def __init__(self, drawn: Image.Image) -> None:
        self.drawn = drawn
        self.received: list[Image.Image] = []

    def __call__(self, image: Image.Image) -> Image.Image:
        self.received.append(image)
        return self.drawn.resize(image.size, Image.Resampling.BILINEAR)


def open_cutout(result: Cutout) -> Image.Image:
    assert result.failure_reason is None and result.png is not None
    image = Image.open(io.BytesIO(result.png))
    assert image.format == "PNG" and image.mode == "RGBA"
    return image


def assert_preserves(result: Cutout, source: Image.Image) -> np.ndarray:
    """R-006 c.3: same size, A in {0, 255}, every opaque pixel equals the oriented source. Returns the alpha."""
    cutout = open_cutout(result)
    assert cutout.size == source.size
    pixels = np.asarray(cutout)
    alpha = pixels[..., 3]
    opaque = alpha == 255
    assert set(np.unique(alpha)) <= {0, 255} and opaque.any()
    assert np.array_equal(pixels[..., :3][opaque], np.asarray(source.convert("RGB"))[opaque])
    x, y, width, height = result.bbox
    assert cutout.getchannel("A").getbbox() == (x, y, x + width, y + height)
    return alpha


# --- Pixel test (R-006 c.3) -----------------------------------------------------------------------------------------

@pytest.mark.parametrize("sample", SAMPLES)
def test_cutout_keeps_the_source_pixels(sample):
    image, drawn = sample()
    alpha = assert_preserves(make_cutout(encode(image), mask_fn=FakeMask(drawn)), image)
    product = np.asarray(drawn) == 255
    assert (alpha[product] == 255).mean() > 0.97 and not alpha[~product].any()  # only the 1 px erosion is lost


def test_exif_orientation_6_is_applied_before_the_mask():
    stored, _ = speaker()
    exif = Image.Exif()
    exif[ExifTags.Base.Orientation] = 6  # shown rotated 90° clockwise
    data = encode(stored, "JPEG", exif=exif, quality=95)
    oriented = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
    assert oriented.size == (600, 1000)
    fake = FakeMask(centred_ellipse(oriented.size))
    result = make_cutout(data, mask_fn=fake)
    assert fake.received[0].size == oriented.size and not fake.received[0].getexif()
    assert_preserves(result, oriented)


def test_the_mask_is_computed_on_a_copy_of_at_most_2048_px():
    source = noisy(gradient((2100, 1400), (90, 120, 150), (20, 30, 40)), 4)
    fake = FakeMask(centred_ellipse(source.size))
    result = make_cutout(encode(source, compress_level=1), mask_fn=fake)
    assert max(fake.received[0].size) == 2048
    assert_preserves(result, source)


def test_the_icc_profile_is_kept_and_the_pixels_are_not_converted():
    image, drawn = phone()
    profile = linear_rgb_profile()
    srgb = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
    converted = ImageCms.profileToProfile(image, ImageCms.ImageCmsProfile(io.BytesIO(profile)), srgb)
    assert converted.tobytes() != image.tobytes()  # the fixture really is not sRGB
    result = make_cutout(encode(image, icc_profile=profile), mask_fn=FakeMask(drawn))
    assert open_cutout(result).info.get("icc_profile") == profile
    assert_preserves(result, image)


def test_a_palette_photo_keeps_its_rgb_profile_and_its_pixels():
    image, drawn = phone()
    profile = linear_rgb_profile()
    data = encode(image.quantize(64), icc_profile=profile)
    source = Image.open(io.BytesIO(data))
    assert source.mode == "P" and source.info.get("icc_profile") == profile  # the fixture really is one
    result = make_cutout(data, mask_fn=FakeMask(drawn))
    assert open_cutout(result).info.get("icc_profile") == profile
    assert_preserves(result, source)


def gray_with_gray_profile() -> bytes:
    return encode(noisy(Image.new("L", (200, 200), 128), 6), icc_profile=linear_gray_profile())


def cmyk_jpeg() -> bytes:
    return encode(Image.new("CMYK", (200, 200), (0, 60, 90, 10)), "JPEG")


def linear_gamma_png() -> bytes:
    return png_with(gama(1.0))  # no ICC profile or sRGB chunk


@pytest.mark.parametrize(("source", "match"), [
    (gray_with_gray_profile, "re-export the photo as sRGB"),
    (cmyk_jpeg, "re-export the photo as sRGB"),
    (linear_gamma_png, "non-sRGB colours"),
])
def test_colours_that_rgb_pixels_cannot_keep_are_refused(source, match):
    fake = FakeMask(centred_ellipse((200, 200)))
    with pytest.raises(ValueError, match=match):
        make_cutout(source(), mask_fn=fake)
    assert not fake.received  # refused before any mask work


@pytest.mark.parametrize("source", [gps_jpeg, text_png])
def test_the_cutout_has_no_exif_or_text(source):
    data = source()
    cutout = open_cutout(make_cutout(data, mask_fn=FakeMask(centred_ellipse(Image.open(io.BytesIO(data)).size))))
    cutout.load()
    assert cutout.info.keys() <= {"icc_profile"} and cutout.text == {} and not cutout.getexif()


# --- Mask steps ---------------------------------------------------------------------------------------------------

def square(hole: tuple[int, int, int, int] | None = None) -> Image.Image:
    mask = Image.new("L", (200, 200), 0)
    draw = ImageDraw.Draw(mask)
    draw.rectangle((50, 50, 149, 149), fill=255)
    if hole:
        draw.rectangle(hole, fill=0)
    return mask


def alpha_for(drawn: Image.Image, **options) -> np.ndarray:
    result = make_cutout(plain(drawn.size), mask_fn=FakeMask(drawn), **options)
    return np.asarray(open_cutout(result).getchannel("A"))


@pytest.mark.parametrize(("hole", "max_hole_ratio", "filled"), [
    ((95, 95, 99, 99), 0.05, True),  # 25 px, 0.3 % of the product: lens glass
    ((80, 80, 119, 119), 0.05, False),  # 1600 px, 19 %: a real opening
    ((80, 80, 119, 119), 0.25, True),
])
def test_small_holes_are_filled_and_large_ones_stay(hole, max_hole_ratio, filled):
    alpha = alpha_for(square(hole), max_hole_ratio=max_hole_ratio)
    assert alpha[97, 97] == (255 if filled else 0) and alpha[60, 60] == 255


def test_a_small_background_region_on_the_border_is_outside_not_a_hole():
    mask = Image.new("L", (200, 200), 0)
    draw = ImageDraw.Draw(mask)
    draw.rectangle((0, 0, 119, 119), fill=255)  # a phone filling the frame up to the top and left edges
    draw.rectangle((0, 0, 9, 9), fill=0)  # its corner leaves 100 px of background, 0.7 % of the product
    alpha = alpha_for(mask)
    assert alpha[3, 3] == 0 and alpha[60, 60] == 255


def test_the_mask_is_eroded_by_1_px():
    assert make_cutout(plain(), mask_fn=FakeMask(square())).bbox == (51, 51, 98, 98)


def test_the_threshold_is_128():
    mask = Image.new("L", (200, 100), 0)
    draw = ImageDraw.Draw(mask)
    draw.rectangle((10, 10, 89, 89), fill=128)
    draw.rectangle((110, 10, 189, 89), fill=127)
    alpha = alpha_for(mask)
    assert alpha[50, 50] == 255 and alpha[50, 150] == 0


# --- Component check ----------------------------------------------------------------------------------------------

def blobs(*boxes: tuple[int, int, int, int]) -> Image.Image:
    mask = Image.new("L", (200, 200), 0)
    for box in boxes:
        ImageDraw.Draw(mask).rectangle(box, fill=255)
    return mask


SPECKS = [(x, 10, x + 2, 12) for x in range(10, 190, 20)]


@pytest.mark.parametrize(("drawn", "reason"), [
    (blobs(), "no_product"),
    (blobs((0, 0, 199, 199)), "no_product"),  # the whole photo: no background found
    (blobs(*SPECKS), "no_product"),  # nothing reaches 2 % of the photo
    (blobs((20, 60, 79, 139), (120, 60, 179, 139)), "multiple_products"),  # two views
    (blobs((20, 40, 119, 159), (140, 80, 179, 119), *SPECKS), None),  # a second part at 13 % of the first, specks
])
def test_component_check(drawn, reason):
    result = make_cutout(plain(), mask_fn=FakeMask(drawn))
    assert result.failure_reason == reason
    assert (result.png is None and result.bbox is None) == (reason is not None)


# --- Placement and shadow -----------------------------------------------------------------------------------------

@pytest.mark.parametrize(("bbox", "size"), [
    ((0, 0, 500, 2000), (216, 864)),  # tall: the height limit binds
    ((10, 20, 2000, 500), (1000, 250)),  # wide: the width limit binds
    ((0, 0, 1000, 1000), (864, 864)),  # square: the height limit binds
    ((0, 0, 1200, 1000), (1000, 1000 / 1.2)),  # just wide enough for the width limit to bind
    ((0, 0, 40, 50), (691.2, 864)),  # a small product is shown larger
])
def test_placement_stays_in_the_safe_square(bbox, size):
    x, y, width, height = place(bbox)
    assert (width, height) == pytest.approx(size)
    assert x + width / 2 == pytest.approx(544) and y + height == pytest.approx(1440)
    left, top, right, bottom = SAFE_SQUARE
    assert left <= x and x + width <= right and top <= y and y + height <= bottom


def baked_phone_shadow(colour: tuple[int, int, int]) -> tuple[Image.Image, tuple[float, float, float, float]]:
    image, drawn = phone()
    result = make_cutout(encode(image), mask_fn=FakeMask(drawn))
    box = place(result.bbox)
    background = encode(Image.new("RGB", OUTPUT_SIZE, colour))
    return Image.open(io.BytesIO(bake_shadow(background, result.png, result.bbox, box))), box


def test_the_shadow_is_baked_under_the_box():
    colour = (200, 180, 160)
    baked, box = baked_phone_shadow(colour)
    assert baked.format == "PNG" and baked.size == OUTPUT_SIZE
    x, y, width, height = box
    centre, bottom = round(x + width / 2), round(y + height)
    assert all(after < before - 30 for after, before in zip(baked.getpixel((centre, bottom)), colour, strict=True))
    for far in [(0, 0), (1087, 1919), (centre, round(y)), (round(x) - 100, bottom), (centre, bottom + 150)]:
        assert baked.getpixel(far) == colour


def test_the_shadow_is_at_most_35_percent_black():
    darkest = int(np.asarray(baked_phone_shadow((255, 255, 255))[0]).min())
    assert round(0.65 * 255) - 1 <= darkest < 255  # 1 below 166 for rounding


def test_the_background_must_be_1088x1920():
    with pytest.raises(ValueError, match="1088x1920"):
        bake_shadow(encode(Image.new("RGB", (1080, 1920))), b"", (0, 0, 1, 1), (0, 0, 1, 1))


# --- rembg --------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("model", "match"), [("no-such-model", "unavailable"), ("withoutbg", "remote service")])
def test_a_session_that_cannot_be_created_is_cutout_unavailable(model, match):
    with pytest.raises(CutoutUnavailable, match=match):
        make_cutout(plain(), rembg_model=model)


class ExitOnRembgImport:
    """A meta path finder: `import rembg` raises SystemExit(1), as rembg/bg.py does when onnxruntime cannot load."""

    def find_spec(self, name, path, target=None):
        if name == "rembg":
            raise SystemExit(1)
        return None


def test_rembg_exiting_on_import_is_cutout_unavailable(monkeypatch):
    monkeypatch.delitem(sys.modules, "rembg", raising=False)
    monkeypatch.setattr(sys, "meta_path", [ExitOnRembgImport(), *sys.meta_path])
    with pytest.raises(CutoutUnavailable, match="SystemExit"):
        make_cutout(plain(), rembg_model="a-model-never-loaded")


@pytest.mark.rembg
@pytest.mark.parametrize("sample", SAMPLES)
def test_the_real_model_cuts_out_the_samples(sample):
    from rembg.sessions import sessions

    if sessions[MODEL].resolve_existing(f"{MODEL}.onnx") is None:
        pytest.skip(f"rembg model {MODEL} not downloaded; run once in backend/: {SETUP}")
    image, drawn = sample()
    alpha = assert_preserves(make_cutout(encode(image), rembg_model=MODEL), image)
    product = np.asarray(drawn) == 255
    assert (alpha[product] == 255).mean() > 0.9
