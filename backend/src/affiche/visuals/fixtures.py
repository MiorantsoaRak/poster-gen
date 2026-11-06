"""The evaluation's products CSV (D-PRODUCT-VISUALS-008): UTF-8 or UTF-8-BOM, ';'-separated. Every row is checked and
every error listed; nothing is returned if any row fails. `price_ar` and `facts` are only read: they exist for the
leak test, and never travel further."""

import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageOps
from pydantic import ValidationError

from affiche.visuals.cutout import check_source
from affiche.visuals.gateway import prepare_provider_input
from affiche.visuals.prompts import Direction, find_commercial_terms

COLUMNS = ("variant_ref", "name", "variant", "photos", "price_ar", "facts", "mood", "description", "arm", "notes")
REF = re.compile(r"[A-Za-z0-9_-]+")  # run labels too, so that scope ids parse
MAX_PHOTOS = 3  # the design's "<= 3 are used": more is an error, not a silent cut
ARMS = ("A", "B")
HEIF_MESSAGE = "HEIC/HEIF is not supported: export the photo as JPEG"
_HEIF_EXTENSIONS = (".heic", ".heif")
_HEIF_BRANDS = (b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"mif1", b"msf1")  # ISO BMFF ftyp brands


@dataclass(frozen=True)
class Photo:
    name: str
    data: bytes = field(repr=False)
    mime: str
    width: int  # EXIF-oriented
    height: int


@dataclass(frozen=True)
class Product:
    variant_ref: str
    name: str
    variant: str
    photos: tuple[Photo, ...]
    direction: Direction
    arm: str | None
    row_sha256: str  # of the raw row: `generate` compares it with the run's snapshot


class FixtureError(Exception):
    def __init__(self, errors: list[str]) -> None:
        super().__init__(f"{len(errors)} error(s) in the fixtures")
        self.errors = errors


def load_products(csv_path: Path, photos_dir: Path, *, arm_required: bool) -> list[Product]:
    """The products, in file order. Errors read "row N, field: message", N being the file line (the header is row 1).
    Raises FixtureError with every error."""
    # ponytail: every photo's bytes stay in memory (about 20 products x 3 photos); read them lazily if that grows.
    try:
        with csv_path.open(encoding="utf-8-sig", newline="") as file:
            # strict: an unclosed quote is an error, not a field that silently swallows the rows after it
            reader = csv.reader(file, delimiter=";", strict=True)
            rows = [(reader.line_num, values) for values in reader]
    except csv.Error as error:
        raise FixtureError([f"row {reader.line_num}: {error} (check the quotes)"]) from error
    except (OSError, UnicodeDecodeError) as error:
        raise FixtureError([f"{csv_path}: cannot be read as UTF-8: {error}"]) from error
    header = [name.strip() for name in rows[0][1]] if rows else []
    if sorted(header) != sorted(COLUMNS):
        raise FixtureError([f"row 1: the header must have exactly the columns {';'.join(COLUMNS)}"])
    errors: list[str] = []
    products: list[Product] = []
    seen: dict[str, int] = {}
    for line, values in rows[1:]:
        if not any(value.strip() for value in values):
            continue
        if len(values) != len(header):
            errors.append(f"row {line}: {len(values)} fields, expected {len(header)} (quote a value holding ';')")
            continue
        product, row_errors = _product(line, dict(zip(header, values)), photos_dir, seen, arm_required)
        errors += row_errors
        if product is not None:
            products.append(product)
    if errors:
        raise FixtureError(errors)
    return products


def _product(line: int, raw: dict[str, str], photos_dir: Path, seen: dict[str, int],
             arm_required: bool) -> tuple[Product | None, list[str]]:
    errors: list[str] = []
    value = {name: text.strip() for name, text in raw.items()}
    ref = value["variant_ref"]
    if not REF.fullmatch(ref):
        errors.append(f"variant_ref: {ref!r} must match {REF.pattern}")
    elif ref in seen:
        errors.append(f"variant_ref: {ref!r} is already on row {seen[ref]}")
    seen.setdefault(ref, line)
    errors += [f"{name}: required" for name in ("name", "variant") if not value[name]]
    names = [name.strip() for name in value["photos"].split("|") if name.strip()]
    if not 1 <= len(names) <= MAX_PHOTOS:
        errors.append(f"photos: {len(names)} photo(s), give 1 to {MAX_PHOTOS} separated by '|'")
    photos = [_photo(photos_dir / name) for name in names]
    errors += [f"photos: {name}: {photo}" for name, photo in zip(names, photos) if isinstance(photo, str)]
    direction, direction_errors = _direction(value)
    errors += direction_errors
    if value["arm"] not in ("", *ARMS) or arm_required and not value["arm"]:
        errors.append("arm: A or B" + (" (required with --corrections by_arm)" if arm_required else ""))
    if errors:
        return None, [f"row {line}, {error}" for error in errors]
    return Product(ref, value["name"], value["variant"], tuple(photos), direction, value["arm"] or None,
                   _row_sha256(raw)), []


def _direction(value: dict[str, str]) -> tuple[Direction | None, list[str]]:
    errors = []
    if terms := find_commercial_terms(value["description"]):
        errors.append(f"description: commercial terms {terms}: prices, warranties and offers stay out of the prompt")
    try:
        return Direction(mood=value["mood"] or None, description=value["description"] or None), errors
    except ValidationError as invalid:
        return None, [f"{error['loc'][0]}: {error['msg']}" for error in invalid.errors()] + errors


def _photo(path: Path) -> Photo | str:
    """The photo, or why it cannot be used: missing, HEIC, undecodable, or refused by the provider-input or the
    cutout colour rules (checked now, so that no product fails later for its photo)."""
    if path.suffix.lower() in _HEIF_EXTENSIONS:
        return HEIF_MESSAGE
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return f"not found in {path.parent}"
    except OSError as error:
        return f"cannot be read: {error}"
    if data[4:8] == b"ftyp" and data[8:12] in _HEIF_BRANDS:  # a HEIC renamed .jpg
        return HEIF_MESSAGE
    try:
        with Image.open(io.BytesIO(data)) as opened:
            image_format = opened.format
            oriented = ImageOps.exif_transpose(opened)  # returns a loaded copy: a full decode
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as error:
        return f"cannot be decoded: {error}"
    if image_format not in Image.MIME:
        return f"format {image_format} is not supported: export the photo as JPEG"
    try:
        check_source(oriented)
        prepare_provider_input(data)
    except ValueError as error:
        return str(error)
    return Photo(path.name, data, Image.MIME[image_format], *oriented.size)


def _row_sha256(raw: dict[str, str]) -> str:
    canonical = json.dumps(raw, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()
