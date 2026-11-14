"""Find the empty white disc that a scene was asked to keep for the shop's logo (D-CATALOGUE-BRAND-006).

The image model draws the disc and composes around it; the real logo file is then printed on it by the renderer.
Nothing is guessed: no round white region near the planned place means no disc.
"""
import io
import logging

from PIL import Image, ImageChops, ImageDraw

log = logging.getLogger(__name__)
_MARK = (255, 0, 255)


def find_disc(image: bytes, centre: tuple[float, float], diameter: float) -> tuple[float, float, float] | None:
    """The disc's centre x, centre y and diameter in image pixels, or None.

    `centre` is (x as a fraction of the width, y as a fraction of the height); `diameter` is a fraction of the
    width. A failure here must never fail the paid job that produced the image, so every error means "not found".
    """
    try:
        with Image.open(io.BytesIO(image)) as source:
            picture = source.convert("RGB")
        width, height = picture.size
        asked, cx, cy = diameter * width, centre[0] * width, centre[1] * height
        left, top = max(0, round(cx - 1.5 * asked)), max(0, round(cy - 1.5 * asked))
        window = picture.crop((left, top, min(width, round(cx + 1.5 * asked)), min(height, round(cy + 1.5 * asked))))
        for dx in (0, -.03, .03):
            # Up to 6 % lower or higher: in the tall Story format the model drew the whole footer 5 % lower than
            # asked (first paid Story scene, 2026-11-14); the nearest offsets are tried first.
            for dy in (0, -.02, .02, .04, -.04, .06, -.06):
                seed = (round(cx + dx * width) - left, round(cy + dy * height) - top)
                if not (0 <= seed[0] < window.width and 0 <= seed[1] < window.height):
                    continue
                if min(window.getpixel(seed)) < 249:  # the disc is pure white; a tinted backdrop is not a seed
                    continue
                marked = window.copy()
                # The threshold is the summed channel difference from the seed: the soft shadow stays outside.
                ImageDraw.floodfill(marked, seed, _MARK, thresh=12)
                red, green, blue = marked.split()
                mask = ImageChops.darker(red.point(lambda v: 255 if v == 255 else 0),
                                         ImageChops.darker(green.point(lambda v: 255 if v == 0 else 0),
                                                           blue.point(lambda v: 255 if v == 255 else 0)))
                box = mask.getbbox()
                if box is None:
                    continue
                w, h = box[2] - box[0], box[3] - box[1]
                size = max(w, h)
                round_enough = abs(w - h) <= .06 * size and .70 <= mask.histogram()[255] / (w * h) <= .86
                inside = box[0] > 0 and box[1] > 0 and box[2] < window.width and box[3] < window.height
                # The model draws the disc where asked but often smaller: 81 % of the asked diameter on the first
                # paid scene through the application, 77 % in the study. The seal is printed at its own size anyway.
                if round_enough and inside and .6 * asked <= size <= 1.6 * asked:
                    return left + (box[0] + box[2]) / 2, top + (box[1] + box[3]) / 2, float(size)
        return None
    except Exception:  # noqa: BLE001 - see the docstring: not found, and the reason is kept in the log
        log.warning("logo disc search failed", exc_info=True)
        return None
