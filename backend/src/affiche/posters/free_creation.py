"""Direct image conversations with immutable, publication-ready results."""
import io
from typing import Annotated, Literal
from uuid import uuid4

from PIL import Image
from pydantic import Field, StringConstraints
from sqlalchemy import text

from affiche import assets
from affiche.db import utc_now
from affiche.visuals.gateway import POSTER_SIZES
from . import exports, jobs, store
from .models import FORMATS, Id, Model, Sha, canonical

Words = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=6000)]


class Turn(Model):
    words: Words


class Start(Turn):
    photos: list[Sha] = Field(default_factory=list, max_length=3)
    reference: Sha | None = None
    default_style: bool = True


class FreeTitle(Model):
    title: str
    price_ar: None = None


class FreeDocument(Model):
    kind: Literal["free"] = "free"
    primary_format: Literal["feed"] = "feed"
    input_id: Id
    offer: FreeTitle
    reference: Sha | None
    default_style: bool
    render_id: Id | None = None
    # The image model's own files (1088 x 1360), kept beside the published 1080 x 1350 PNG: `source` is the current
    # version's and the base of the next correction; `first` is the first version's, the clean reference of every later
    # one (trial of 2026-11-25: nine corrections chained with nothing else turned the product to grain).
    source: Sha | None = None
    first: Sha | None = None


def document_of(creation):
    if creation["document"].get("kind") != "free":
        raise store.Refused("not_found", 404)
    return FreeDocument.model_validate(creation["document"])


def prompt(words, count, reference, default_style, editing, anchor=False):
    lines = [("Edit image 1. Make this change and preserve the rest:" if editing else
              "Create the requested image. The owner asks:"), words]
    start = 2 if editing else 1
    if count:
        numbers = ", ".join(str(n) for n in range(start, start + count))
        lines.append(f"Composition source photos in the owner's order: {numbers}. Preserve subject identity.")
    # A correction keeps image 1, which already carries the reference's layout: sent again with « match its
    # composition », the reference argues with « preserve the rest » (and costs one more input image).
    if reference and not editing:
        lines.append(f"Image {start + count} is the visual reference. Match its composition, framing, typography, "
                     "spacing and palette. Replace its subjects and wording with the requested content. "
                     "Explicit directions from the owner take priority.")
    if anchor:
        lines.append(f"Image {start + count} is an earlier version of this picture, given only as a reference for "
                     "rendering quality: how clean and smooth the product's surfaces, its materials and the backdrop "
                     "are. Render them that cleanly, with no grain, noise or blotches. Ignore everything else in it: "
                     "its texts, lettering, sizes and layout are out of date. Image 1 alone says what the picture "
                     "contains and where.")
    if default_style and not editing:
        lines.append("Only for visual decisions left open: use a clear focal point, balanced spacing, strong contrast "
                     "and legible lettering. Follow any supplied reference or explicit direction first.")
    lines.append("Keep supplied wording and amounts accurate. Do not invent prices, product claims, warranties or discounts.")
    return "\n\n".join(lines)


def enqueue(conn, settings, shop, creation, document, photos, words):
    if "feed" not in settings.formats_enabled:
        raise store.Refused("format_unavailable")
    editing = bool(document.render_id)
    # A creation made before `first` was kept: its first published PNG stands in. No reference for the correction of
    # the first version itself.
    anchor = document.first or conn.execute(text(
        "SELECT png_sha256 FROM poster_renders WHERE creation_id=:id ORDER BY source_revision LIMIT 1"), {"id": creation["id"]}).scalar()
    first_is_base = conn.execute(text("SELECT COUNT(*) FROM poster_renders WHERE creation_id=:id"), {"id": creation["id"]}).scalar_one() < 2
    anchor = anchor if editing and not first_is_base else None
    payload = {"free_words": words, "photo_assets": photos, "style_reference_asset": None if editing else document.reference,
               "base_render_id": document.render_id, "base_asset": document.source, "anchor_asset": anchor,
               "size": POSTER_SIZES["feed"], "quality": settings.openai_image_quality or "high",
               "prompt": prompt(words, len(photos), document.reference, document.default_style, editing, bool(anchor))}
    result = jobs.enqueue(conn, settings, shop, creation["id"], creation["revision"], "scene", payload)
    return 202, {**result, "creation_id": creation["id"]}


def start(engine, settings, shop, key, body):
    def apply(conn):
        for sha in body.photos:
            store._asset(conn, settings.data_dir, shop, sha, "original")
        if body.reference:
            store._asset(conn, settings.data_dir, shop, body.reference, "style")
        id, title = str(uuid4()), body.words[:100]
        conn.execute(text("INSERT INTO product_inputs VALUES (:id,:shop,:id,:title,'Création libre',:photos,'[]',NULL,:now)"),
                     {"id": id, "shop": shop, "title": title, "photos": canonical(body.photos), "now": utc_now()})
        document = FreeDocument(input_id=id, offer=FreeTitle(title=title), reference=body.reference,
                                default_style=body.default_style)
        _, creation = store._new_creation(conn, shop, document)
        return enqueue(conn, settings, shop, creation, document, body.photos, body.words)
    return store.mutate(engine, shop, key, "POST", "/api/free-creations", body.model_dump(), apply)


def turn(engine, settings, shop, key, id, revision, body):
    def apply(conn):
        creation = store.get_creation(conn, shop, id)
        store._revision(creation["revision"], revision)
        document = document_of(creation)
        photos = store.get_input(conn, shop, document.input_id)["photo_assets"]
        return enqueue(conn, settings, shop, creation, document, photos, body.words)
    return store.mutate(engine, shop, key, "POST", f"/api/free-creations/{id}/turns", body.model_dump(), apply, revision=revision)


def finish(conn, settings, job, image, mime="image/png"):
    creation = store.get_creation(conn, job["shop_id"], job["creation_id"])
    store._revision(creation["revision"], job["origin_revision"])
    document = document_of(creation)
    width, height = FORMATS["feed"]
    with Image.open(io.BytesIO(image)) as source:
        output = io.BytesIO()
        source.convert("RGB").resize((width, height), Image.Resampling.LANCZOS).save(output, "PNG")
    data = output.getvalue()
    sha = assets.put(settings.data_dir, data, "png")
    if mime == "image/png":  # what `stored` reads back
        document.source = assets.put(settings.data_dir, image, "png")
        # Only the first version is the clean reference: a creation made before this was kept goes on with its first
        # published PNG (enqueue), never with a later version's file.
        if not conn.execute(text("SELECT 1 FROM poster_renders WHERE creation_id=:id"), {"id": creation["id"]}).first():
            document.first = document.source
    document.render_id = str(uuid4())
    revision = creation["revision"] + 1
    store._insert_version(conn, creation["id"], revision, document)
    params = {"id": document.render_id, "creation": creation["id"], "revision": revision, "job": job["id"],
              "hash": sha, "width": width, "height": height, "bytes": len(data), "now": utc_now()}
    conn.execute(text("UPDATE creations SET current_revision=:revision,updated_at=:now WHERE id=:creation"), params)
    conn.execute(text("INSERT INTO poster_renders VALUES (:id,:creation,:revision,:job,'feed',:hash,'free-png-v1',"
                      "'none','{}',:hash,:width,:height,:bytes,'[]',:now)"), params)
    return document.render_id


def stored(settings, sha):
    """A kept image of the image model, or None when its file is not there: the caller has a published PNG to fall back on."""
    try:
        return assets.path(settings.data_dir, sha, "png").read_bytes() if sha else None
    except OSError:
        return None


def transcript(conn, shop, id):
    creation = store.get_creation(conn, shop, id)
    document = document_of(creation)
    # A turn is its job as GET /api/jobs/{id} tells it (status, error_code, credit): the page says a failure with the
    # same sentences as every other image of the app (generation.ts), not with a refusal code's.
    rows = conn.execute(text("SELECT j.status,j.error_code,j.takes_credit,json_extract(j.input_json,'$.free_words') AS words,"
                             "r.id AS render_id,r.png_sha256 FROM poster_jobs j LEFT JOIN poster_renders r ON r.job_id=j.id "
                             "WHERE j.creation_id=:id AND j.shop_id=:shop AND j.kind='scene' ORDER BY j.rowid"),
                        {"id": id, "shop": shop}).mappings()
    return {"revision": creation["revision"], "status": creation["status"], "document": document.model_dump(),
            "photos": store.get_input(conn, shop, document.input_id)["photo_assets"],
            "turns": [{key: row[key] for key in ("status", "error_code", "words", "render_id", "png_sha256")}
                      | {"credit": jobs.CREDIT.get(row["status"], "given_back") if row["takes_credit"] else None} for row in rows],
            "confirmation": exports.current_confirmation(conn, shop, id, "feed")}
