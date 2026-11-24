"""Creation-bound planning, integrated scene admission and immutable fidelity decisions."""
import hashlib
import json
import math
import re
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import Field, StringConstraints, field_validator, model_validator
from sqlalchemy import text

from affiche import assets
from affiche.db import utc_now
from affiche.visuals.gateway import POSTER_SIZES, image_dimensions
from affiche.visuals.prompts import ReasonCode
from . import jobs, looks, store
from .models import FORMATS, Colour, Crop, Document, Format, Id, Model, Scene, Sha, canonical
from .plans import TITLE_STYLES, ArtDirection, Box, Headline, OverlayRegion, PlanContext, SceneDescription, ScenePlan, brand_in_title, compile_scene, screen_adjustment, seal_place, fixed_plan, screen_art, validate_plan

CHECKS = {"colour", "markings", "hardware", "shape", "extras_text", "integration"}
# Words drawn by the image model cannot be edited afterwards: the owner rereads each kind against what he typed.
TEXT_CHECKS = {"text_title", "text_price", "text_signature", "text_lines"}


def required_checks(baked: dict | None) -> set[str]:
    required = set(CHECKS)
    if baked:
        required.add("text_title")
        if "price_ar" in baked:
            required.add("text_price")
        if "shop_name" in baked or "contact" in baked:
            required.add("text_signature")
        if baked.get("shop_lines"):
            required.add("text_lines")
    return required


class PlanRequest(Model):
    mode: Literal["fixed", "claude"]
    direction: ArtDirection
    format: Format = "feed"

    _screen = field_validator("direction")(screen_art)


class SceneRequest(Model):
    plan_id: Id
    format: Format = "feed"
    style_reference_asset: Sha | None = None
    headline: Headline | None = None
    acknowledged_warnings: list[Literal["low_resolution"]] = Field(default_factory=list, max_length=1)
    # The version this scene replaces (a word change asked in the chat, ADR-101): the scene adjustments the owner
    # asked on it by message are kept. Left out when absent, so other requests keep their idempotency hash.
    keep_adjustments_of: Id | None = None
    # The owner's scene words of his first message (D-KIT-003): kept with the job like a refinement's instruction, so
    # the next refinements and word changes say them again. Left out when absent, as keep_adjustments_of.
    adjustment_fr: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)] | None = None

    _screen = field_validator("adjustment_fr")(lambda value: value if value is None else screen_adjustment(value))


def kept_adjustments(conn, shop, visual_id) -> list[str]:
    """The owner's scene adjustments that led to this version, oldest first: each refinement's instruction up to the
    scene it started from, and what that scene itself had kept. Refinements older than the kept instruction give none."""
    notes = []
    while visual_id:
        row = store._owned(conn, "poster_visuals", shop, visual_id)
        payload = json.loads(store._owned(conn, "poster_jobs", shop, row["job_id"])["input_json"])
        notes = payload.get("adjustments", []) + ([payload["instruction_fr"]] if payload.get("instruction_fr") else []) + notes
        visual_id = row["base_visual_id"]
    return notes


def checked_adjustments(conn, shop, visual_id, added: str | None = None) -> list[str]:
    """kept_adjustments within their limits, `added` last. Copies share their versions, so the twelve-scenes limit of
    one poster does not bound a chain. Refused, never cut: a prompt that silently lost an adjustment would be a poster
    the owner did not ask for."""
    notes = kept_adjustments(conn, shop, visual_id) + ([added] if added else [])
    if len(notes) > 12 or sum(map(len, notes)) > 3000:
        raise store.Refused("adjustments_limit")
    try:  # screened when asked; the screen may have grown since
        for note in notes:
            screen_adjustment(note)
    except ValueError:
        raise store.Refused("adjustment_refused") from None
    return notes


class PlanRevision(Model):
    scene: SceneDescription
    product_region: Box
    overlay_regions: list[OverlayRegion] = Field(min_length=2, max_length=5)
    palette: list[Colour] = Field(min_length=2, max_length=4)


class RefinementRequest(Model):
    base_visual_id: Id
    instruction_fr: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    format: Format = "feed"
    style_reference_asset: Sha | None = None

    @field_validator("instruction_fr")
    @classmethod
    def scene_adjustment(cls, value):
        return screen_adjustment(value)  # the one screen of this field, for the editor and the chat (ADR-102)


FidelityChecks = dict[Literal["colour", "markings", "hardware", "shape", "extras_text", "integration",
                              "text_title", "text_price", "text_signature", "text_lines"], bool]


class Decision(Model):
    action: Literal["approve", "reject"]
    checks: FidelityChecks = Field(default_factory=dict)
    reasons: list[ReasonCode] = Field(default_factory=list, max_length=9)
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None

    @model_validator(mode="after")
    def review(self):
        if self.action == "approve" and (not CHECKS <= self.checks.keys() or not all(self.checks.values()) or self.reasons):
            raise ValueError("all_fidelity_checks_required")
        if self.action == "reject" and not (self.reasons or self.note):
            raise ValueError("rejection_reason_required")
        if len(set(self.reasons)) != len(self.reasons):
            raise ValueError("duplicate_reason")
        return self


def _snapshot(conn, shop, id, revision, format, enabled):
    # Every format-bound request, paid or not, starts here: a poster left in a format switched off since
    # (FORMATS_ENABLED) gets no plan, scene, text job or export, so nothing is paid for that cannot be exported.
    if format not in enabled:
        raise store.Refused("format_unavailable")
    creation = store.get_creation(conn, shop, id)
    store._revision(creation["revision"], revision)
    if creation["status"] != "active":
        raise store.Refused("creation_abandoned", 409)
    document = Document.model_validate(creation["document"])
    if format not in document.formats:
        raise store.Refused("format_missing")
    product = store.get_input(conn, shop, document.input_id)
    return creation, document, product


def context_for(document, product, direction, format):
    width, height = FORMATS[format]
    sizes = {layer.role: {"w": layer.width / width, "h": layer.height / height}
             for layer in document.formats[format].layers
             if (layer.visible or layer.role in ("title", "price") or getattr(document.include, layer.role, False))
             and layer.role != "product"
             # A seal is printed on a disc of the scene, outside the plan (ADR-057).
             and not (layer.role == "logo" and getattr(layer, "shape", None) == "circle")}
    try:
        logo = next((layer for layer in document.formats[format].layers if layer.role == "logo" and layer.visible
                     and getattr(layer, "shape", None) != "circle" and layer.y < height / 2), None)
        return PlanContext(name=product["name"], variant=product["variant"], direction=direction,
                           format=format, field_sizes=sizes,
                           logo_corner=("left" if logo.x < width / 2 else "right") if logo else None)
    except ValueError:
        raise store.Refused("layout_not_plannable") from None


def get_plan(conn, shop, id):
    row = store._owned(conn, "scene_plans", shop, id)
    return {key: row[key] for key in ("id", "creation_id", "origin_revision", "input_id", "source", "format", "parent_plan_id")} | {
        "plan": json.loads(row["plan_json"])}


def insert_plan(conn, *, shop, creation_id, revision, input_id, context, plan, photo_count,
                source, job_id=None, parent=None):
    try:
        plan = validate_plan(plan, context)
        prompt = compile_scene(plan, context, photo_count=photo_count)
    except ValueError:
        raise store.Refused("invalid_plan") from None
    id = str(uuid4())
    conn.execute(text("INSERT INTO scene_plans VALUES (:id,:shop,:creation,:revision,:input,:job,:parent,:source,:format,"
                      ":context,:plan,:prompt,:hash,:now)"),
                 {"id": id, "shop": shop, "creation": creation_id, "revision": revision, "input": input_id,
                  "job": job_id, "parent": parent, "source": source, "format": context.format,
                  "context": canonical(context), "plan": canonical(plan), "prompt": prompt,
                  "hash": store._sha(prompt), "now": utc_now()})
    return id


def create_plan(engine, settings, shop, key, id, revision, request: PlanRequest):
    def apply(conn):
        _, document, product = _snapshot(conn, shop, id, revision, request.format, settings.formats_enabled)
        store._source_files(conn, settings.data_dir, shop, product["id"])
        context = context_for(document, product, request.direction, request.format)
        if request.mode == "claude":
            result = jobs.enqueue(conn, settings, shop, id, revision, "plan",
                                  {"context": context.model_dump(), "photo_assets": product["photo_assets"]})
            return 202, result
        try:
            plan = fixed_plan(context)
        except ValueError:
            raise store.Refused("layout_not_plannable") from None
        plan_id = insert_plan(conn, shop=shop, creation_id=id, revision=revision, input_id=product["id"],
                              context=context, plan=plan, photo_count=len(product["photo_assets"]), source="fixed")
        return 201, get_plan(conn, shop, plan_id)
    return store.mutate(engine, shop, key, "POST", f"/api/creations/{id}/plans", request.model_dump(), apply, revision=revision)


def revise_plan(engine, settings, shop, key, id, revision, request: PlanRevision):
    def apply(conn):
        old = store._owned(conn, "scene_plans", shop, id)
        _, document, product = _snapshot(conn, shop, old["creation_id"], revision, old["format"], settings.formats_enabled)
        if document.input_id != old["input_id"]:
            raise store.Refused("plan_stale", 409)
        context = context_for(document, product, json.loads(old["context_json"])["direction"], old["format"])
        try:
            plan = ScenePlan(summary_fr=json.loads(old["plan_json"])["summary_fr"], **request.model_dump())
        except ValueError:
            raise store.Refused("invalid_plan") from None
        result = insert_plan(conn, shop=shop, creation_id=old["creation_id"], revision=revision, input_id=product["id"],
                             context=context, plan=plan, photo_count=len(product["photo_assets"]), source="manual", parent=id)
        return 201, get_plan(conn, shop, result)
    return store.mutate(engine, shop, key, "POST", f"/api/plans/{id}/revisions", request.model_dump(), apply, revision=revision)


def _low_resolution(conn, settings, product):
    return any(min(conn.execute(text("SELECT width,height FROM assets WHERE sha256=:sha"), {"sha": sha}).one())
               < settings.min_source_short_edge for sha in product["photo_assets"])


def read_visual_bytes(conn, data_dir, shop, visual_id, input_id=None):
    visual = store._owned(conn, "poster_visuals", shop, visual_id)
    if input_id and visual["input_id"] != input_id:
        raise store.Refused("invalid_reference")
    if visual["treatment"] != "scene":
        raise store.Refused("unsupported_visual")
    try:
        data = assets.load(conn, data_dir, visual["image_asset"])
    except FileNotFoundError:
        raise store.Refused("asset_missing", 503) from None
    if hashlib.sha256(data).hexdigest() != visual["image_asset"]:
        raise store.Refused("asset_corrupt", 409)
    return visual, data


def request_scene(engine, settings, shop, key, id, revision, request: SceneRequest):
    def apply(conn):
        _, document, product = _snapshot(conn, shop, id, revision, request.format, settings.formats_enabled)
        plan = store._owned(conn, "scene_plans", shop, request.plan_id)
        if (plan["creation_id"], plan["origin_revision"], plan["input_id"], plan["format"]) != (id, revision, product["id"], request.format):
            raise store.Refused("plan_stale", 409)
        context = context_for(document, product, json.loads(plan["context_json"])["direction"], request.format)
        if canonical(context) != plan["context_json"]:
            raise store.Refused("plan_stale", 409)
        store._source_files(conn, settings.data_dir, shop, product["id"])
        low_res = _low_resolution(conn, settings, product)
        if low_res and "low_resolution" not in request.acknowledged_warnings:
            raise store.Refused("acknowledgement_required")
        reference = request.style_reference_asset
        if reference:
            store._asset(conn, settings.data_dir, shop, reference, "style")
        elif request.headline and request.headline.look_id:
            # A saved model goes with the poster it was read from: its words carry the colours and the lettering, but a
            # layout said in words was not built (three products each in its own card, the owner's reference of
            # 2026-11-24). The image model sees it and decides. The job reads the file, and refuses a missing one.
            reference = looks.get_look(conn, shop, request.headline.look_id)["reference_asset"]
        title = document.offer.title if request.headline else None
        signature = {}
        if request.headline and request.headline.signature:
            # A new scene draws the contact only, as one compact line (ADR-055); the shop name is never drawn.
            if not request.headline.signature_align:
                raise store.Refused("invalid_headline")
            signature = {role: value for role, value in profile_signature(document).items() if role == "contact"}
        price = {"price_ar": document.offer.price_ar} if request.headline and request.headline.price else {}
        seal = bool(request.headline and request.headline.logo_seal)
        if seal:
            logo = next((layer for layer in document.formats[request.format].layers if layer.role == "logo"), None)
            if not (logo and logo.shape == "circle" and document.include.logo) or document.include.shop_name:
                raise store.Refused("invalid_headline")
        style = lettering(conn, shop, request.headline and request.headline.model_dump())
        adjustments = []
        if request.keep_adjustments_of:
            if request.keep_adjustments_of not in listed_visuals(conn, shop, document.model_dump()):
                raise store.Refused("not_found", 404)
        if request.keep_adjustments_of or request.adjustment_fr:
            adjustments = checked_adjustments(conn, shop, request.keep_adjustments_of, request.adjustment_fr)
        lines = {}
        if request.headline and request.headline.lines is not None:
            # The shop's lines, read in this transaction (D-KIT-005): drawn only when they are the ones the owner was
            # shown, in order. The job keeps them: they are this version's snapshot, as the drawn title is.
            kept = store.get_profile(conn, shop)["lines"]
            if not kept:
                raise store.Refused("shop_lines_missing", 409)
            if request.headline.lines != kept:
                raise store.Refused("shop_lines_changed", 409)
            lines = {"shop_lines": kept}
        try:
            compiled = compile_scene(ScenePlan.model_validate_json(plan["plan_json"]), context,
                                     photo_count=len(product["photo_assets"]), style_reference=bool(reference),
                                     headline=request.headline, title=title, signature=signature, deduplicate_brand=True,
                                     adjustments=adjustments, **price, **style, **lines)
        except ValueError as refusal:
            # The owner can cause these four by what he typed: each gets its own sentence and its field. The shop's lines
            # cannot fail here: Headline.lines passed today's rule and equals them.
            code, field = {"headline_title_too_long": ("title_too_long", "offer.title"),
                           "headline_title_unsupported": ("title_unsupported", "offer.title"),
                           "headline_contains_commercial_or_instruction_text": ("title_commercial_text", "offer.title"),
                           "signature_unsupported": ("contact_unsupported", "contact")}.get(str(refusal), ("invalid_headline", None))
            raise store.Refused(code, field=field) from None
        payload = {"plan_id": plan["id"], "format": request.format, "size": POSTER_SIZES[request.format],
                   "quality": settings.openai_image_quality or "high", "prompt": compiled, "photo_assets": product["photo_assets"],
                   "base_visual_id": None, "low_res_ack": low_res,
                   "style_reference_asset": reference,
                   "reference_roles": ["original"] * len(product["photo_assets"]) + (["style"] if reference else [])}
        if reference and not request.style_reference_asset:
            # The model's poster is the server's addition: the page is not told (it would send it again with a correction,
            # whose base image carries the layout already, and say a model image was lost at a change of style).
            payload["style_reference_from_look"] = True
        if request.headline:
            payload["headline"] = request.headline.model_dump(exclude={"lines"}) | {"title": title} | signature | price | lines
            if brand_in_title(request.headline.brand, title):
                payload["headline"]["brand_in_title"] = True
        if seal:
            payload["logo_seal"] = seal_place(ScenePlan.model_validate_json(plan["plan_json"]), style.get("align", "centre"))
        if adjustments:  # kept with the job, so the next word change carries them on
            payload["adjustments"] = adjustments
        if request.keep_adjustments_of:  # the list of modifications says what changed against this version
            payload["replaces_visual_id"] = request.keep_adjustments_of
        return 202, jobs.enqueue(conn, settings, shop, id, revision, "scene", payload)
    # Omitted optional references must preserve pre-style idempotency hashes.
    return store.mutate(engine, shop, key, "POST", f"/api/creations/{id}/scenes", request.model_dump(exclude_none=True), apply, revision=revision)


def request_refinement(engine, settings, shop, key, id, revision, request: RefinementRequest):
    def apply(conn):
        _, document, product = _snapshot(conn, shop, id, revision, request.format, settings.formats_enabled)
        if document.formats[request.format].scene.visual_id != request.base_visual_id:
            raise store.Refused("base_not_selected", 409)
        base, _ = read_visual_bytes(conn, settings.data_dir, shop, request.base_visual_id, product["id"])
        check_logo_placement(conn, shop, base, document, request.format)
        plan = store._owned(conn, "scene_plans", shop, base["plan_id"])
        if plan["format"] != request.format:  # a paid refinement at another size would cut the drawn words
            raise store.Refused("scene_format_mismatch", 409)
        context = context_for(document, product, json.loads(plan["context_json"])["direction"], request.format)
        store._source_files(conn, settings.data_dir, shop, product["id"])
        if request.style_reference_asset:
            store._asset(conn, settings.data_dir, shop, request.style_reference_asset, "style")
        # A refinement keeps the base scene's integrated headline; a renamed offer needs a new scene instead.
        baked = baked_headline(conn, shop, base)
        signature = {role: baked[role] for role in ("shop_name", "contact") if baked and role in baked}
        if baked and (baked["title"] != document.offer.title or signature != {
                role: value for role, value in profile_signature(document).items() if role in signature}
                or baked.get("price_ar", document.offer.price_ar) != document.offer.price_ar):
            raise store.Refused("headline_stale", 409)
        try:
            compiled = compile_scene(ScenePlan.model_validate_json(plan["plan_json"]), context,
                                     photo_count=len(product["photo_assets"]), refinement=True, refinement_note=request.instruction_fr,
                                     # What was asked before on this chain is said again (paid test of ADR-102: a
                                     # list of features asked in one adjustment was dropped by the next one).
                                     adjustments=checked_adjustments(conn, shop, base["id"]),
                                     style_reference=bool(request.style_reference_asset),
                                     headline=Headline(**{k: v for k, v in baked.items() if k in Headline.model_fields}) if baked else None,
                                     title=baked["title"] if baked else None, signature=signature,
                                     price_ar=baked.get("price_ar") if baked else None,
                                     # Its base's lines, not the profile's: the words this poster already shows.
                                     shop_lines=baked.get("shop_lines", ()) if baked else (),
                                     deduplicate_brand=bool(baked and baked.get("brand_in_title")),
                                     **lettering(conn, shop, baked))  # its base's title style and look
        except ValueError:
            raise store.Refused("invalid_plan") from None
        payload = {"plan_id": plan["id"], "format": request.format, "size": POSTER_SIZES[request.format],
                   "quality": settings.openai_image_quality or "high", "prompt": compiled, "photo_assets": product["photo_assets"],
                   "base_visual_id": base["id"], "low_res_ack": bool(base["low_res_ack"]),
                   "instruction_fr": request.instruction_fr,  # shown in the chat's list of modifications
                   "style_reference_asset": request.style_reference_asset,
                   "reference_roles": ["base"] + ["original"] * len(product["photo_assets"]) + (["style"] if request.style_reference_asset else [])}
        if baked:
            payload["headline"] = baked
            if baked.get("logo_seal"):
                payload["logo_seal"] = seal_place(ScenePlan.model_validate_json(plan["plan_json"]),
                                                  lettering(conn, shop, baked).get("align", "centre"))
        return 202, jobs.enqueue(conn, settings, shop, id, revision, "refine", payload)
    return store.mutate(engine, shop, key, "POST", f"/api/creations/{id}/refinements", request.model_dump(exclude_none=True), apply, revision=revision)


def lettering(conn, shop, headline: dict | None) -> dict:
    """The drawn title's lettering and alignment (D-KIT-012): its title style wins, else the lettering of the shop's own
    saved look, else none (the default); the alignment is the look's. An unknown or foreign look is refused (404)."""
    headline = headline or {}
    brief = looks.get_look(conn, shop, headline["look_id"])["brief"] if headline.get("look_id") else None
    style = (TITLE_STYLES[headline["title_style"]] if headline.get("title_style")
             else brief["headline_style_en"] if brief else None)
    return ({"headline_style": style} if style else {}) | ({"align": brief["alignment"]} if brief else {})


def profile_signature(document) -> dict[str, str]:
    """The selected shop name/contact exactly as the poster's profile snapshot holds them."""
    return {role: getattr(document.brand_snapshot, "name" if role == "shop_name" else role)
            for role in ("shop_name", "contact") if getattr(document.include, role)}


def baked_headline(conn, shop, visual) -> dict | None:
    """The headline the image model set in this scene (with the exact title it was given), if any."""
    return json.loads(store._owned(conn, "poster_jobs", shop, visual["job_id"])["input_json"]).get("headline")


def logo_region(conn, shop, visual):
    plan = store._owned(conn, "scene_plans", shop, visual["plan_id"])
    box = next((item["box"] for item in json.loads(plan["plan_json"])["overlay_regions"] if item["field"] == "logo"), None)
    if box is None:
        return {}
    field = "logo_box" if json.loads(plan["context_json"]).get("logo_corner") else "logo_footer_box"
    width, height = FORMATS[plan["format"]]
    return {field: dict(x=box["x"]*width, y=box["y"]*height, width=box["w"]*width, height=box["h"]*height)}


def check_logo_placement(conn, shop, visual, document, format):
    layout = document.formats[format]
    logo = next((layer for layer in layout.layers if layer.role == "logo" and layer.visible), None)
    disc = (json.loads(visual["placement_json"]) if visual["placement_json"] else {}).get("logo_disc")
    if disc and (logo is None or math.hypot(logo.x+logo.width/2-disc["x"], logo.y+logo.height/2-disc["y"])
                 + disc["d"]/2 > min(logo.width, logo.height)/2+2):
        raise store.Refused("logo_disc_uncovered", 409)
    reserved = logo_region(conn, shop, visual).get("logo_box")
    if logo and (reserved or (logo.shape != "circle" and logo.y < FORMATS[format][1]/2)):
        width, height = map(int, visual["size"].split("x"))
        crop = layout.scene.crop
        if (not reserved or logo.shape == "circle" or any(abs(getattr(logo, key)-value) > 2 for key, value in reserved.items())
                or (crop and any(abs(a-b) > 2 for a, b in zip((crop.x, crop.y, crop.w, crop.h), (0, 0, width, height))))):
            raise store.Refused("logo_placement_stale", 409)


def listed_visuals(conn, shop, document: dict) -> list[str]:
    """The versions of a poster, newest first: those of its product input at its size. A copy shares them; a copy in
    another format does not."""
    return conn.execute(text("SELECT id FROM poster_visuals WHERE shop_id=:shop AND input_id=:input AND size=:size "
                             "ORDER BY created_at DESC"),
                        {"shop": shop, "input": document["input_id"],
                         "size": POSTER_SIZES[document["primary_format"]]}).scalars().all()


def get_visual(conn, shop, id):
    row = store._owned(conn, "poster_visuals", shop, id)
    payload = json.loads(store._owned(conn, "poster_jobs", shop, row["job_id"])["input_json"])
    return {key: row[key] for key in ("id", "input_id", "base_visual_id", "status", "model", "quality", "size", "created_at", "decided_at")} | {
        "image_url": f'/api/assets/{row["image_asset"]}',
        "replaces_visual_id": payload.get("replaces_visual_id"),  # the version a chat card redrew, if any
        "plan_id": row["plan_id"],  # its style lives there: a new image of the same poster starts from it (ADR-100)
        "style_reference_asset": None if payload.get("style_reference_from_look") else payload.get("style_reference_asset"),
        "headline": payload.get("headline"),
        # The owner's words for a refinement; null for a scene, and for a refinement older than this field.
        "instruction_fr": payload.get("instruction_fr"),
        "original_urls": [f"/api/assets/{sha}" for sha in json.loads(row["source_assets_json"])],
        "checks": json.loads(row["checks_json"]), "reasons": json.loads(row["rejection_reasons_json"] or "[]"),
        "note": row["rejection_note"]} | logo_region(conn, shop, row) | (
        # Present only when a disc was asked for the logo seal: its place in poster pixels, or null if not found.
        {"logo_disc": json.loads(row["placement_json"])["logo_disc"]} if row["placement_json"] else {})


def record_decision(conn, shop, id, action, checks, reasons, note):
    old = store._owned(conn, "poster_visuals", shop, id)
    status = "approved" if action == "approve" else "rejected"
    if old["status"] not in ("pending_review", status):
        raise store.Refused("review_decided", 409)
    if action == "approve" and (not required_checks(baked_headline(conn, shop, old)) <= checks.keys()
                                or not all(checks.values())):
        raise store.Refused("fidelity_incomplete")
    if old["status"] == status:
        return
    conn.execute(text("UPDATE poster_visuals SET status=:status,checks_json=:checks,rejection_reasons_json=:reasons,"
                      "rejection_note=:note,decided_at=:now WHERE id=:id"),
                 {"id": id, "status": status, "checks": canonical(checks), "reasons": canonical(reasons),
                  "note": note, "now": utc_now()})


def decide(engine, shop, key, id, request: Decision):
    def apply(conn):
        record_decision(conn, shop, id, request.action, request.checks, request.reasons, request.note)
        return 200, get_visual(conn, shop, id)
    return store.mutate(engine, shop, key, "POST", f"/api/visuals/{id}/decision", request.model_dump(), apply)
