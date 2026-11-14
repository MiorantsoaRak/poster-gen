"""Saved revision -> authoritative PNG -> immutable confirmation and exact download."""
import json
from typing import Literal
from uuid import uuid4

from pydantic import Field
from sqlalchemy import text

from affiche import assets
from affiche.db import utc_now
from . import jobs, rendering, store, typography, visuals
from .models import Document, Format, Id, Model, Sha, TextLayer, canonical, format_price


class RenderRequest(Model):
    format: Format = "feed"


class ConfirmRequest(Model):
    render_id: Id
    png_sha256: Sha
    checks: dict[Literal["framing", "content", "identity", "readability"], bool]
    acknowledged_warning_ids: list[str] = Field(default_factory=list, max_length=200)


def snapshot(conn, settings, shop, id, revision, format, build):
    _, document, _ = visuals._snapshot(conn, shop, id, revision, format, settings.formats_enabled)
    return effective_snapshot(conn, settings, shop, document, format, build)


def effective_snapshot(conn, settings, shop, document, format, build):
    store._references(conn, settings.data_dir, shop, document)
    layout = document.formats[format]
    if layout.scene.visual_id is None:
        raise store.Refused("scene_unapproved", 409)
    visual, image = visuals.read_visual_bytes(conn, settings.data_dir, shop, layout.scene.visual_id, document.input_id)
    if visual["status"] != "approved":
        raise store.Refused("scene_unapproved", 409)
    # Words the image model drew cannot be edited: they must still say what the poster says, and a hidden
    # layer must be replaced by them. Showing the layer again never excuses stale words in the image.
    baked = visuals.baked_headline(conn, shop, visual) or {}
    visuals.check_logo_placement(conn, shop, visual, document, format)
    shown = {layer.role: layer.visible for layer in layout.layers}
    if baked.get("title", document.offer.title) != document.offer.title or not (shown["title"] or "title" in baked):
        raise store.Refused("title_missing", 409)
    if baked.get("price_ar", document.offer.price_ar) != document.offer.price_ar or not (
            shown["price"] or "price_ar" in baked):
        raise store.Refused("price_stale", 409)
    signature = visuals.profile_signature(document)
    for role in ("shop_name", "contact"):
        if role in baked and signature.get(role) != baked[role] or (
                role in signature and role not in baked and not shown[role]):
            raise store.Refused("signature_missing", 409)
    manifest, sources, layers, fonts = {}, {}, [], {}
    def source(key, sha, data):
        prepared = rendering.canvas_image(data)
        sources[key] = rendering.data_url(prepared)
        manifest[key] = {"source_sha256": sha, "prepared_sha256": rendering.sha(prepared)}
    source(f"scene:{visual['id']}", visual["image_asset"], image)
    for layer in sorted((layer for layer in layout.layers if layer.visible), key=lambda layer: layer.z):
        value = layer.model_dump()
        if isinstance(layer, TextLayer):
            value["text"] = (document.offer.title if layer.role == "title" else format_price(document.offer.price_ar)
                             if layer.role == "price" else document.brand_snapshot.name if layer.role == "shop_name"
                             else document.brand_snapshot.contact)
            font = next((entry for entry in build["manifest"]["fonts"] if (entry["id"], entry["weight"]) == (layer.font_id, layer.weight)), None)
            if font is None:
                raise store.Refused("unsupported_font")
            fonts[font["file"]] = font["sha256"]
            if layer.price_badge:
                currency_font = next((entry for entry in build["manifest"]["fonts"]
                                      if (entry["id"], entry["weight"]) == ("noto-sans", 400)), None)
                if currency_font is None:
                    raise store.Refused("unsupported_font")
                fonts[currency_font["file"]] = currency_font["sha256"]
            if layer.texture_effect_id:
                effect, image = typography.read_effect(conn, settings.data_dir, shop, layer.texture_effect_id)
                source(f"effect:{effect['id']}", effect["texture_asset"], image)
        elif layer.kind == "logo":
            source(layer.asset, layer.asset, store._asset(conn, settings.data_dir, shop, layer.asset, "logo"))
        else:
            raise store.Refused("unsupported_visual")
        layers.append(value)
    effective = {"input_id": document.input_id, "format": format, "scene": layout.scene.model_dump(),
                 "layers": layers, "sources": manifest, "fonts": fonts}
    return {"document": document.model_dump(), "format": format, "format_hash": store._sha(canonical(effective)),
            "asset_manifest": manifest, "sources": sources, "renderer_build_hash": build["build_hash"],
            "font_manifest_hash": build["font_manifest_hash"]}


def request_render(engine, settings, shop, key, id, revision, request):
    def apply(conn):
        build = rendering.bundle()
        value = snapshot(conn, settings, shop, id, revision, request.format, build)
        # The queue snapshot contains hashes; prepare resolves bytes again before the local render.
        payload = {name: value[name] for name in ("format", "format_hash", "asset_manifest", "renderer_build_hash", "font_manifest_hash")}
        digest = store._sha(canonical(payload))
        previous = conn.execute(text("SELECT id,result_ref FROM poster_jobs WHERE creation_id=:id AND origin_revision=:revision "
                                     "AND kind='render' AND input_hash=:hash AND status IN ('queued','running','succeeded') ORDER BY created_at DESC LIMIT 1"),
                                {"id": id, "revision": revision, "hash": digest}).mappings().first()
        if previous:
            return 202, {"job_id": previous["id"], "status_url": f"/api/jobs/{previous['id']}"}
        return 202, jobs.enqueue(conn, settings, shop, id, revision, "render", payload)
    return store.mutate(engine, shop, key, "POST", f"/api/creations/{id}/renders", request.model_dump(), apply, revision=revision)


def prepare(conn, settings, job):
    payload, build = json.loads(job["input_json"]), rendering.bundle()
    # Render the immutable submitted revision even if another edit was saved meanwhile.
    current = store.get_creation(conn, job["shop_id"], job["creation_id"])
    original = store.get_creation(conn, job["shop_id"], job["creation_id"], job["origin_revision"])
    if current["status"] != "active":
        raise store.Refused("creation_abandoned", 409)
    value = effective_snapshot(conn, settings, job["shop_id"], Document.model_validate(original["document"]), payload["format"], build)
    for name in ("format_hash", "asset_manifest", "renderer_build_hash", "font_manifest_hash"):
        if value[name] != payload[name]:
            raise store.Refused("render_inputs_changed", 409)
    return {"snapshot": value, "build": build}


def insert_render(conn, settings, job, result):
    payload = json.loads(job["input_json"])
    data = rendering.png_bytes(result["png"], payload["format"])
    sha = assets.put(settings.data_dir, data, "png")
    id = str(uuid4())
    from .models import FORMATS
    width, height = FORMATS[payload["format"]]
    conn.execute(text("INSERT INTO poster_renders VALUES (:id,:creation,:revision,:job,:format,:hash,:build,:fonts,:assets,:png,:width,:height,:bytes,:warnings,:now)"),
                 {"id": id, "creation": job["creation_id"], "revision": job["origin_revision"], "job": job["id"],
                  "format": payload["format"], "hash": payload["format_hash"], "build": payload["renderer_build_hash"],
                  "fonts": payload["font_manifest_hash"], "assets": canonical(payload["asset_manifest"]), "png": sha,
                  "width": width, "height": height, "bytes": len(data), "warnings": canonical(result["warnings"]), "now": utc_now()})
    return id


def render_row(conn, shop, id):
    row = conn.execute(text("SELECT r.* FROM poster_renders r JOIN creations c ON c.id=r.creation_id WHERE r.id=:id AND c.shop_id=:shop"),
                       {"id": id, "shop": shop}).mappings().first()
    if row is None:
        raise store.Refused("not_found", 404)
    return row


def get_render(conn, shop, id):
    row = render_row(conn, shop, id)
    confirmation = conn.execute(text("SELECT id FROM confirmations WHERE render_id=:id"), {"id": id}).scalar()
    return {name: row[name] for name in ("id", "creation_id", "source_revision", "format", "format_hash", "png_sha256", "width", "height")} | {
        "warnings": json.loads(row["warnings_json"]), "preview_url": f"/api/renders/{id}/preview",
        "download_url": f"/api/confirmations/{confirmation}/download" if confirmation else None}


def read_png(settings, row):
    try:
        data = assets.path(settings.data_dir, row["png_sha256"], "png").read_bytes()
        if rendering.sha(data) != row["png_sha256"]:
            raise ValueError("hash_mismatch")
        return data
    except (OSError, ValueError):
        raise store.Refused("export_missing", 503) from None


def confirm(engine, settings, shop, key, id, revision, request):
    def apply(conn):
        row = render_row(conn, shop, request.render_id)
        if row["creation_id"] != id:
            raise store.Refused("not_found", 404)
        if set(request.checks) != {"framing", "content", "identity", "readability"} or not all(request.checks.values()):
            raise store.Refused("confirmation_incomplete")
        value = snapshot(conn, settings, shop, id, revision, row["format"], rendering.bundle())
        if value["format_hash"] != row["format_hash"] or request.png_sha256 != row["png_sha256"]:
            raise store.Refused("preview_stale", 409)
        warnings = {warning["id"] for warning in json.loads(row["warnings_json"])}
        if set(request.acknowledged_warning_ids) != warnings:
            raise store.Refused("confirmation_incomplete")
        read_png(settings, row)
        existing = conn.execute(text("SELECT id FROM confirmations WHERE render_id=:id"), {"id": row["id"]}).scalar()
        confirmation = existing or str(uuid4())
        if not existing:
            conn.execute(text("INSERT INTO confirmations VALUES (:id,:creation,:source,:revision,:format,:hash,:render,:png,:checks,:now)"),
                         {"id": confirmation, "creation": id, "source": row["source_revision"], "revision": revision,
                          "format": row["format"], "hash": row["format_hash"], "render": row["id"], "png": row["png_sha256"],
                          "checks": canonical(request.model_dump()), "now": utc_now()})
        return 201, {"confirmation_id": confirmation, "download_url": f"/api/confirmations/{confirmation}/download"}
    return store.mutate(engine, shop, key, "POST", f"/api/creations/{id}/confirmations", request.model_dump(), apply, revision=revision)


def download(conn, settings, shop, id):
    row = conn.execute(text("SELECT v.* FROM confirmations v JOIN creations c ON c.id=v.creation_id WHERE v.id=:id AND c.shop_id=:shop"),
                       {"id": id, "shop": shop}).mappings().first()
    if row is None:
        raise store.Refused("not_found", 404)
    return row, read_png(settings, row)
