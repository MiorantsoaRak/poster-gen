"""Transactions for intake, identity and versioned drafts; no provider calls."""
import hashlib
import io
import json
from pathlib import Path
from uuid import UUID, uuid4

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import Connection, Engine, text

from affiche import assets
from affiche.db import utc_now, write_tx
from affiche.posters.models import (
    FORMATS, BrandSnapshot, CopyCreation, Document, ImageLayer, Layout, NewCreation, ProductInput,
    Profile, Scene, TextLayer, canonical,
)
from affiche.visuals.gateway import prepare_provider_input

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_UPLOAD_PIXELS = 40_000_000


class Refused(Exception):
    def __init__(self, code: str, status: int = 422, *, field: str | None = None, current_revision: int | None = None):
        self.code, self.status, self.field, self.current_revision = code, status, field, current_revision
        super().__init__(code)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def mutate(engine: Engine, shop: int, key: str, method: str, path: str, payload: dict, apply,
           *, revision: int | None = None) -> tuple[int, dict]:
    try:
        valid_key = str(UUID(key)) == key
    except (ValueError, AttributeError):
        valid_key = False
    if not valid_key:
        raise Refused("invalid_idempotency_key")
    digest = _sha(canonical({"body": payload, "revision": revision}))
    with write_tx(engine) as conn:
        old = conn.execute(text("SELECT * FROM mutation_keys WHERE shop_id=:shop AND key=:key"),
                           {"shop": shop, "key": key}).mappings().first()
        if old:
            if (old["method"], old["path"], old["payload_sha"]) != (method, path, digest):
                raise Refused("idempotency_reused", 409)
            return old["status_code"], json.loads(old["response_json"])
        status, result = apply(conn)
        conn.execute(text("INSERT INTO mutation_keys VALUES (:shop,:key,:method,:path,:sha,:status,:response,:now)"),
                     {"shop": shop, "key": key, "method": method, "path": path, "sha": digest,
                      "status": status, "response": canonical(result), "now": utc_now()})
        return status, result


def _owned(conn: Connection, table: str, shop: int, id: str):
    # Table names are internal constants; all caller-controlled values are bound parameters.
    row = conn.execute(text(f"SELECT * FROM {table} WHERE id=:id AND shop_id=:shop"),
                       {"id": id, "shop": shop}).mappings().first()
    if row is None:
        raise Refused("not_found", 404)
    return row


def _revision(current: int, expected: int | None):
    if expected is None:
        raise Refused("precondition_required", 428)
    if type(expected) is not int or expected != current:
        raise Refused("revision_conflict", 409, current_revision=current)


def _asset(conn: Connection, data_dir: Path, shop: int, sha: str, role: str):
    access = conn.execute(text("SELECT 1 FROM asset_access WHERE shop_id=:shop AND asset_sha=:sha AND role=:role"),
                          {"shop": shop, "sha": sha, "role": role}).scalar()
    if not access:
        raise Refused("unknown_asset", field=role)
    try:
        data = assets.load(conn, data_dir, sha)
    except FileNotFoundError:
        raise Refused("asset_missing", 404) from None
    if hashlib.sha256(data).hexdigest() != sha:
        raise Refused("asset_corrupt", 409)
    return data


def upload(engine: Engine, data_dir: Path, shop: int, data: bytes, role: str, *, min_short_edge: int = 800) -> dict:
    if role not in ("original", "logo", "style"):
        raise Refused("invalid_role")
    if len(data) > MAX_UPLOAD_BYTES:
        raise Refused("too_large", 413)
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in ("JPEG", "PNG", "WEBP"):
                raise Refused("unsupported_type", 415)
            if image.width * image.height > MAX_UPLOAD_PIXELS:
                raise Refused("too_large", 413)
            if getattr(image, "n_frames", 1) != 1:
                raise Refused("animated_image")
            image.load()
            mime = Image.MIME[image.format]
            width, height = ImageOps.exif_transpose(image).size
        prepare_provider_input(data)  # Validate colours; only the unmodified original is stored here.
    except UnidentifiedImageError:
        raise Refused("unsupported_type", 415) from None
    except Image.DecompressionBombError:
        raise Refused("too_large", 413) from None
    except ValueError:
        raise Refused("unsupported_colour") from None
    except (OSError, SyntaxError):
        raise Refused("invalid_image") from None
    sha = assets.put(data_dir, data, assets.extension(mime))
    with write_tx(engine) as conn:
        assets.record(conn, sha=sha, kind="style_ref" if role == "style" else "original", mime=mime,
                      width=width, height=height, size=len(data))
        conn.execute(text("INSERT INTO asset_access VALUES (:shop,:sha,:role) ON CONFLICT DO NOTHING"),
                     {"shop": shop, "sha": sha, "role": role})
    return {"asset": sha, "mime": mime, "width": width, "height": height,
            "warnings": ["low_resolution"] if role == "original" and min(width, height) < min_short_edge else []}


def get_profile(conn: Connection, shop: int) -> dict:
    row = conn.execute(text("SELECT * FROM shop_profile WHERE id=:shop"), {"shop": shop}).mappings().first()
    if row is None:
        raise Refused("not_found", 404)
    return {k: row[k] for k in ("revision", "name", "contact", "logo_asset")}


def save_profile(engine, data_dir, shop, key, profile: Profile, revision):
    def apply(conn):
        _revision(get_profile(conn, shop)["revision"], revision)
        if profile.logo_asset:
            _asset(conn, data_dir, shop, profile.logo_asset, "logo")
        conn.execute(text("UPDATE shop_profile SET revision=revision+1,name=:name,contact=:contact,"
                          "logo_asset=:logo_asset,updated_at=:now WHERE id=:shop"),
                     profile.model_dump() | {"shop": shop, "now": utc_now()})
        return 200, get_profile(conn, shop)
    return mutate(engine, shop, key, "PUT", "/api/shop-profile", profile.model_dump(), apply, revision=revision)


def get_input(conn: Connection, shop: int, id: str) -> dict:
    row = dict(_owned(conn, "product_inputs", shop, id))
    row.pop("shop_id")
    row["photo_assets"] = json.loads(row.pop("photo_assets_json"))
    row["facts"] = json.loads(row.pop("facts_json"))
    return row


def create_input(engine, data_dir, shop, key, product: ProductInput):
    def apply(conn):
        ref = product.product_ref
        if product.supersedes_id:
            source = get_input(conn, shop, product.supersedes_id)
            if ref is not None and ref != source["product_ref"]:
                raise Refused("replacement_identity_mismatch")
            ref = source["product_ref"]
        for sha in product.photo_assets:
            _asset(conn, data_dir, shop, sha, "original")
        id = str(uuid4())
        conn.execute(text("INSERT INTO product_inputs VALUES (:id,:shop,:ref,:name,:variant,:photos,:facts,:old,:now)"),
                     {"id": id, "shop": shop, "ref": ref or str(uuid4()), "name": product.name,
                      "variant": product.variant, "photos": canonical(product.photo_assets),
                      "facts": canonical(product.facts), "old": product.supersedes_id, "now": utc_now()})
        return 201, get_input(conn, shop, id)
    return mutate(engine, shop, key, "POST", "/api/product-inputs", product.model_dump(), apply)


def initial_document(request: NewCreation, profile: dict) -> Document:
    profile = dict(profile)
    profile["profile_revision"] = profile.pop("revision")
    width, height = FORMATS[request.primary_format]
    layers = []
    for role, y, h, size in (("title", 64, 192, 72), ("price", height-380, 120, 88),
                             ("shop_name", height-240, 64, 36), ("contact", height-164, 132, 24)):
        if role in ("title", "price") or getattr(request.brand_selection, role):
            layers.append(TextLayer(id=str(uuid4()), role=role, x=64, y=y, width=width-128,
                                    height=h, font_size=size, z=len(layers)))
    if request.brand_selection.logo:
        layers.append(ImageLayer(id=str(uuid4()), kind="logo", role="logo", asset=profile["logo_asset"],
                                 x=width-192, y=height-240, width=128, height=128, z=len(layers)))
        for layer in layers:
            if layer.role in ("shop_name", "contact"):
                layer.width -= 160
    return Document(input_id=request.input_id, offer=request.offer, brand_snapshot=BrandSnapshot(**profile),
                    include=request.brand_selection, primary_format=request.primary_format,
                    formats={request.primary_format: Layout(layers=layers)})


def _references(conn, data_dir, shop, document: Document):
    get_input(conn, shop, document.input_id)
    if document.brand_snapshot.logo_asset:
        _asset(conn, data_dir, shop, document.brand_snapshot.logo_asset, "logo")
    for format, layout in document.formats.items():
        if layout.scene.visual_id:
            from .visuals import read_visual_bytes
            from affiche.visuals.gateway import image_dimensions
            visual, _ = read_visual_bytes(conn, data_dir, shop, layout.scene.visual_id, document.input_id)
            width, height = image_dimensions(visual["size"])
            crop = layout.scene.crop
            if (crop.x + crop.w > width or crop.y + crop.h > height
                    or abs(crop.w / crop.h - FORMATS[format][0] / FORMATS[format][1]) > 1e-6):
                raise Refused("invalid_crop")
        for layer in layout.layers:
            if isinstance(layer, TextLayer) and layer.texture_effect_id:
                from .typography import read_effect
                read_effect(conn, data_dir, shop, layer.texture_effect_id)
            # shortcut: optional cutouts need their own reviewed records in T-010.
            if layer.kind == "product_cutout":
                raise Refused("generated_reference_unavailable")


def _source_files(conn, data_dir, shop, input_id):
    for sha in get_input(conn, shop, input_id)["photo_assets"]:
        _asset(conn, data_dir, shop, sha, "original")


def _insert_version(conn, id, revision, document):
    encoded = canonical(document)
    conn.execute(text("INSERT INTO creation_versions VALUES (:id,:revision,:doc,:sha,:now)"),
                 {"id": id, "revision": revision, "doc": encoded, "sha": _sha(encoded), "now": utc_now()})


def get_creation(conn: Connection, shop: int, id: str, revision: int | None = None) -> dict:
    row = _owned(conn, "creations", shop, id)
    revision = row["current_revision"] if revision is None else revision
    document = conn.execute(text("SELECT document_json FROM creation_versions WHERE creation_id=:id AND revision=:rev"),
                            {"id": id, "rev": revision}).scalar()
    if document is None:
        raise Refused("not_found", 404)
    return {"id": id, "revision": revision, "status": row["status"], "parent_creation_id": row["parent_creation_id"],
            "document": json.loads(document)}


def _new_creation(conn, shop, document, parent=None):
    id, now = str(uuid4()), utc_now()
    conn.execute(text("INSERT INTO creations VALUES (:id,:shop,:parent,1,'active',:now,:now)"),
                 {"id": id, "shop": shop, "parent": parent, "now": now})
    _insert_version(conn, id, 1, document)
    return 201, get_creation(conn, shop, id)


def create_creation(engine, data_dir, shop, key, request: NewCreation):
    def apply(conn):
        profile = get_profile(conn, shop)
        for role, field in (("logo", "logo_asset"), ("shop_name", "name"), ("contact", "contact")):
            if getattr(request.brand_selection, role) and profile[field] is None:
                raise Refused("missing_brand_field", field=role)
        document = initial_document(request, profile)
        _references(conn, data_dir, shop, document)
        _source_files(conn, data_dir, shop, document.input_id)
        return _new_creation(conn, shop, document)
    return mutate(engine, shop, key, "POST", "/api/creations", request.model_dump(), apply)


def save_creation(engine, data_dir, shop, key, id, document: Document, revision):
    def apply(conn):
        old = get_creation(conn, shop, id)
        _revision(old["revision"], revision)
        if old["status"] != "active":
            raise Refused("creation_abandoned", 409)
        if document.input_id != old["document"]["input_id"]:
            raise Refused("input_immutable")
        _references(conn, data_dir, shop, document)
        if canonical(document) == canonical(Document.model_validate(old["document"])):
            return 200, old
        _insert_version(conn, id, revision+1, document)
        conn.execute(text("UPDATE creations SET current_revision=:rev,updated_at=:now WHERE id=:id"),
                     {"id": id, "rev": revision+1, "now": utc_now()})
        return 200, get_creation(conn, shop, id)
    return mutate(engine, shop, key, "PUT", f"/api/creations/{id}", document.model_dump(), apply, revision=revision)


def copy_creation(engine, data_dir, shop, key, id, request: CopyCreation):
    def apply(conn):
        source = get_creation(conn, shop, id, request.source_revision)
        document = request.unsaved_document or Document.model_validate(source["document"])
        if document.input_id != source["document"]["input_id"]:
            raise Refused("input_immutable")
        document = document.model_copy(deep=True)
        if request.new_input_id:
            if request.new_input_id == document.input_id:
                raise Refused("replacement_requires_new_input")
            document.input_id = request.new_input_id
            for layout in document.formats.values():
                layout.scene = Scene()
                layout.layers = [layer for layer in layout.layers if layer.kind != "product_cutout"]
        _references(conn, data_dir, shop, document)
        _source_files(conn, data_dir, shop, document.input_id)
        return _new_creation(conn, shop, document, parent=id)
    return mutate(engine, shop, key, "POST", f"/api/creations/{id}/copies", request.model_dump(), apply)


def abandon_creation(engine, shop, key, id, revision):
    def apply(conn):
        old = get_creation(conn, shop, id)
        _revision(old["revision"], revision)
        if conn.execute(text("SELECT 1 FROM poster_jobs WHERE creation_id=:id AND status IN ('queued','running')"
                             " AND kind IN ('scene','refine','text_texture','background')"), {"id": id}).first():
            raise Refused("image_job_running", 409)
        conn.execute(text("UPDATE creations SET status='abandoned',updated_at=:now WHERE id=:id"),
                     {"id": id, "now": utc_now()})
        return 200, get_creation(conn, shop, id)
    return mutate(engine, shop, key, "POST", f"/api/creations/{id}/abandon", {}, apply, revision=revision)
