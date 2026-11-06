"""Photo-preserving cutout (D-PRODUCT-VISUALS-006, steps 1 and 3): the product mask, the RGBA cutout built from the
source pixels, the component check, the default placement and the baked shadow (ADR-011). CPU-bound and sync: the
thread pool and its semaphore of 1 belong to the callers."""

import functools
import io
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
from PIL import Image, ImageFilter, ImageOps
from scipy import ndimage

from affiche.visuals.gateway import OUTPUT_SIZE, refuse_undeclared_colours

FailureReason = Literal["no_product", "multiple_products"]
MaskFn = Callable[[Image.Image], Image.Image]
BBox = tuple[int, int, int, int]  # x, y, w, h in source pixels
Box = tuple[float, float, float, float]  # x, y, w, h in the 1088x1920 master

# Calibration knobs (D-PV-006). The operator sees every cutout before any spend.
MASK_LONG_EDGE = 2048  # bounds the inference input, so the CPU cost
MASK_THRESHOLD = 128
CHECK_LONG_EDGE = 256
MIN_PRODUCT_RATIO = 0.02  # of the check copy's area
MAX_MASK_RATIO = 0.95
SECOND_PRODUCT_RATIO = 0.30  # of the largest component
# 8-connectivity for the product: parts that touch only at a corner in the 256 px copy (a strap, a cable) stay one
# product, so the check errs towards a cutout the operator can still reject. Holes then use 4-connectivity.
EIGHT_CONNECTED = np.ones((3, 3), dtype=bool)

# Default placement (D-PV-006). The safe square [4, 1084) x [420, 1500) is in all three crops (D-PV-002).
MAX_PRODUCT_HEIGHT = 0.45 * OUTPUT_SIZE[1]
MAX_PRODUCT_WIDTH = 1000
PRODUCT_CENTRE_X = 544
PRODUCT_BOTTOM_Y = 1440
SAFE_SQUARE = (4, 420, 1084, 1500)  # left, top, right, bottom; right and bottom exclusive

SHADOW_HEIGHT_RATIO = 0.12
SHADOW_BLUR_RADIUS = 24
SHADOW_OPACITY = 0.35


class CutoutUnavailable(Exception):
    """The rembg session cannot be created: the model is not downloaded and the download fails, or the model name is
    unknown or remote. The caller maps it to `cutout_unavailable`."""


@dataclass(frozen=True)
class Cutout:
    """Either `failure_reason`, or the cutout PNG with the tight box of its alpha."""

    png: bytes | None = field(default=None, repr=False)
    bbox: BBox | None = None
    failure_reason: FailureReason | None = None


def make_cutout(source: bytes, *, mask_fn: MaskFn | None = None, rembg_model: str = "birefnet-general-lite",
                max_hole_ratio: float = 0.05) -> Cutout:
    """The cutout of an uploaded photo: the EXIF-oriented source pixels, unconverted, with a binary alpha.

    `mask_fn(image)` returns an L mask of the image's size; the default runs rembg with `rembg_model`.
    Raises CutoutUnavailable when the rembg session cannot be created; anything raised during inference (MemoryError
    included) propagates, for the caller to map to `cutout_error`. Raises ValueError for colours that RGB pixels
    cannot keep (below) or a mask of the wrong size, and Pillow's errors for an undecodable image.
    """
    with Image.open(io.BytesIO(source)) as opened:
        oriented = ImageOps.exif_transpose(opened)
    icc_profile = check_source(oriented)
    image = oriented.convert("RGB")
    alpha = _alpha(image, mask_fn or _rembg_mask(rembg_model), max_hole_ratio)
    if (failure := _check_components(alpha)) is not None:
        return Cutout(failure_reason=failure)
    left, top, right, bottom = alpha.getbbox()
    image.putalpha(alpha)
    image.info.clear()  # PNG save takes the ICC profile and transparency from info; EXIF and text come only from kwargs
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", **({"icc_profile": icc_profile} if icc_profile else {}))
    return Cutout(png=buffer.getvalue(), bbox=(left, top, right - left, bottom - top))


def check_source(oriented: Image.Image) -> bytes | None:
    """The colour rules of a cutout source (EXIF-oriented), public so that a caller can list refusals before any work:
    ValueError for colours that RGB pixels cannot keep; else the ICC profile the cutout keeps (None without one)."""
    refuse_undeclared_colours(oriented.info)
    return _rgb_profile(oriented)


def _rgb_profile(image: Image.Image) -> bytes | None:
    """The ICC profile to keep with the RGB pixels. R-006 forbids changing their appearance, and converting is not
    allowed here, so a source whose colours RGB pixels cannot carry is refused. RGB and palette (RGB entries) sources
    keep their RGB profile; an unprofiled gray source is fine, as R = G = B looks the same."""
    icc_profile = image.info.get("icc_profile")
    if image.mode == "CMYK" or icc_profile and icc_profile[16:20] != b"RGB ":  # the ICC header's colour space
        raise ValueError("the photo is CMYK or has a gray or CMYK colour profile: re-export the photo as sRGB")
    return icc_profile or None


def _alpha(image: Image.Image, mask_fn: MaskFn, max_hole_ratio: float) -> Image.Image:
    copy = image.copy()
    copy.thumbnail((MASK_LONG_EDGE, MASK_LONG_EDGE), Image.Resampling.LANCZOS)
    copy.info.clear()  # rembg.remove() applies exif_transpose again: with no metadata it cannot rotate the copy twice
    mask = mask_fn(copy)
    if mask.size != copy.size:
        raise ValueError(f"mask size {mask.size}, expected {copy.size}")
    mask = mask.convert("L").resize(image.size, Image.Resampling.BILINEAR)
    product = _fill_small_holes(np.asarray(mask) >= MASK_THRESHOLD, max_hole_ratio)
    return Image.fromarray(product.astype(np.uint8) * 255).filter(ImageFilter.MinFilter(3))


def _fill_small_holes(product: np.ndarray, max_hole_ratio: float) -> np.ndarray:
    """Fills the background regions that do not reach the image border and are smaller than max_hole_ratio x the
    product area (lens glass, a glossy screen). Bigger openings stay transparent."""
    regions, _ = ndimage.label(~product)  # 4-connected
    fill = np.bincount(regions.ravel()) < max_hole_ratio * np.count_nonzero(product)
    fill[0] = False  # label 0 is the product itself
    fill[np.concatenate([regions[0], regions[-1], regions[:, 0], regions[:, -1]])] = False  # the outside
    return product | fill[regions]


def _check_components(alpha: Image.Image) -> FailureReason | None:
    small = alpha.copy()
    small.thumbnail((CHECK_LONG_EDGE, CHECK_LONG_EDGE), Image.Resampling.BOX)
    product = np.asarray(small) >= MASK_THRESHOLD
    labels, count = ndimage.label(product, structure=EIGHT_CONNECTED)
    sizes = np.bincount(labels.ravel())[1:]
    if count == 0 or sizes.max() < MIN_PRODUCT_RATIO * product.size or product.mean() > MAX_MASK_RATIO:
        return "no_product"
    if np.count_nonzero(sizes >= SECOND_PRODUCT_RATIO * sizes.max()) >= 2:
        return "multiple_products"
    return None


@functools.cache  # one session per model; a failed creation raises, so it is not cached and the next call retries
def _rembg_mask(model: str) -> MaskFn:
    try:
        # Imported here: rembg pulls in onnxruntime and numba (about 5 s), which only the real mask needs. When
        # onnxruntime cannot load, rembg's import calls sys.exit(1) (rembg/bg.py), hence SystemExit below.
        from rembg import new_session, remove
        from rembg.sessions import sessions

        if model in sessions and not sessions[model].is_local():  # withoutbg, atlascloud: paid, and the photo leaves
            raise ValueError("it sends the photo to a remote service: choose a local model")
        session = new_session(model)
    # Unknown name (ValueError), failed download (requests, an OSError), checksum (ValueError), unreadable model file
    # (onnxruntime errors, which derive from Exception only): no narrower common base.
    except (Exception, SystemExit) as error:
        raise CutoutUnavailable(f"rembg model {model!r} is unavailable: {type(error).__name__}: {error}") from error
    return lambda image: remove(image, only_mask=True, session=session)


def place(bbox: BBox) -> Box:
    """The default product box in the master: as large as 45 % of the height and 1000 px of width allow, centred on
    x = 544 with its bottom at y = 1440. Only the display is scaled; the cutout asset is never resampled."""
    _, _, width, height = bbox
    scale = min(MAX_PRODUCT_HEIGHT / height, MAX_PRODUCT_WIDTH / width)
    box_width, box_height = width * scale, height * scale
    x, y = PRODUCT_CENTRE_X - box_width / 2, PRODUCT_BOTTOM_Y - box_height
    left, top, right, bottom = SAFE_SQUARE
    assert left <= x and x + box_width <= right and top <= y and y + box_height <= bottom, (x, y, box_width, box_height)
    return x, y, box_width, box_height


def bake_shadow(background: bytes, cutout_png: bytes, bbox: BBox, box: Box) -> bytes:
    """The background PNG with the synthetic shadow (ADR-011) at the default box: the product's alpha squashed to 12 %
    of the box height, blurred (radius 24) at 35 % black, centred on the box's bottom edge. It does not follow a moved
    product.

    Raises ValueError unless the background is exactly 1088x1920.
    """
    with Image.open(io.BytesIO(background)) as opened:
        if opened.size != OUTPUT_SIZE:
            raise ValueError(f"background size {opened.size[0]}x{opened.size[1]}, expected 1088x1920")
        canvas = opened.convert("RGB")
    x, y, width, height = bbox
    with Image.open(io.BytesIO(cutout_png)) as cutout:
        silhouette = cutout.getchannel("A").crop((x, y, x + width, y + height))
    box_x, box_y, box_width, box_height = box
    squashed = silhouette.resize((max(1, round(box_width)), max(1, round(box_height * SHADOW_HEIGHT_RATIO))),
                                 Image.Resampling.BILINEAR)
    shade = Image.new("L", OUTPUT_SIZE, 0)
    shade.paste(squashed, (round(box_x + (box_width - squashed.width) / 2),
                           round(box_y + box_height - squashed.height / 2)))
    shade = shade.filter(ImageFilter.GaussianBlur(SHADOW_BLUR_RADIUS)).point(lambda v: round(v * SHADOW_OPACITY))
    shadowed = Image.composite(Image.new("RGB", OUTPUT_SIZE, "black"), canvas, shade)
    buffer = io.BytesIO()
    shadowed.save(buffer, format="PNG")
    return buffer.getvalue()
