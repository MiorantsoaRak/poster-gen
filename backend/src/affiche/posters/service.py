"""Registered poster operations and the single-process queue scheduler."""
import asyncio
import base64
from decimal import Decimal
import json
import logging
import math

from sqlalchemy import text

from affiche import assets
from affiche.db import utc_now
from affiche.visuals.gateway import OpenAIProvider, image_dimensions, make_provider, prepare_provider_input, validate_image
from . import exports, jobs, looks, rendering, store, typography, visuals
from .models import FORMATS, Crop, Document, Scene, canonical
from .planner import ClaudePlanner
from .plans import PlanContext, ScenePlan, fixed_plan
from .worker import Outcome, run_job

log = logging.getLogger(__name__)
KINDS = ("plan", "scene", "refine", "text_patch", "text_texture", "render")


class PosterService:
    def __init__(self, engine, settings):
        self.engine, self.settings = engine, settings
        self.provider = make_provider(settings)
        self.running = {}
        self.stopping = False

    def prepare(self, job, call):
        payload = json.loads(job["input_json"])
        with self.engine.connect() as conn:
            if job["kind"] == "render":
                return {"job": job, **exports.prepare(conn, self.settings, job)}
            product = store.get_input(conn, job["shop_id"], job["input_id"])
            photos = []
            if "look" in payload:  # a style brief reads the reference poster only
                photos = [prepare_provider_input(store._asset(conn, self.settings.data_dir, job["shop_id"],
                                                              payload["look"]["reference_asset"], "style"))]
            elif job["kind"] in {"plan", "scene", "refine"}:
                if payload["photo_assets"] != product["photo_assets"]:
                    raise store.Refused("input_changed")
                photos = [prepare_provider_input(store._asset(conn, self.settings.data_dir, job["shop_id"], sha, "original"))
                          for sha in payload["photo_assets"]]
            elif job["kind"] == "text_patch":
                typography.selected(Document.model_validate(payload["document"]), payload["format"], payload["layer_id"])
            if job["kind"] == "refine":
                _, base = visuals.read_visual_bytes(conn, self.settings.data_dir, job["shop_id"], payload["base_visual_id"], job["input_id"])
                photos.insert(0, prepare_provider_input(base))
            if job["kind"] in {"scene", "refine"} and payload.get("style_reference_asset"):
                photos.append(prepare_provider_input(store._asset(
                    conn, self.settings.data_dir, job["shop_id"], payload["style_reference_asset"], "style")))
        expected = self.settings.planner_provider if job["kind"] in {"plan", "text_patch"} else self.settings.image_provider
        if call["provider"] != expected:
            raise store.Refused("provider_mode_mismatch")
        if job["kind"] in {"plan", "text_patch"} and call["provider"] == "claude" and self.settings.anthropic_api_key is None:
            raise store.Refused("planner_unavailable")
        return {"job": job, "call": call, "payload": payload, "images": photos}

    async def send(self, prepared):
        if prepared["job"]["kind"] == "render":
            value = prepared["snapshot"]
            for attempt in range(2):
                try:
                    result = await rendering.render(value["document"], value["format"], value["sources"], prepared["build"])
                    return Outcome(result, cost_micros=0)
                except store.Refused as error:
                    if error.code != "render_unavailable" or attempt:
                        raise
        job, call, payload = (prepared[key] for key in ("job", "call", "payload"))
        rates = json.loads(call["rate_card_json"])
        if job["kind"] == "text_patch":
            if call["provider"] == "stub":
                return Outcome({"patch": typography.stub_patch(payload).model_dump(exclude_unset=True)}, cost_micros=0)
            patch, usage, cost, request_id = await typography.propose(ClaudePlanner(self.settings.anthropic_api_key, model=call["model"]), payload)
            if usage:
                cost = usage["input_tokens"] * rates["input_micros_per_token"] + usage["output_tokens"] * rates["output_micros_per_token"]
            return Outcome({"patch": patch.model_dump(exclude_unset=True)}, usage, cost, request_id)
        if "look" in payload:
            if call["provider"] == "stub":
                return Outcome({"brief": looks.stub_brief().model_dump(), "source": "stub"}, cost_micros=0)
            brief, usage, cost, request_id = await looks.propose(
                ClaudePlanner(self.settings.anthropic_api_key, model=call["model"]), prepared["images"][0])
            if usage:
                cost = usage["input_tokens"] * rates["input_micros_per_token"] + usage["output_tokens"] * rates["output_micros_per_token"]
            return Outcome({"brief": brief.model_dump(), "source": "claude"}, usage, cost, request_id)
        if job["kind"] == "plan":
            context = PlanContext.model_validate(payload["context"])
            if call["provider"] == "stub":
                return Outcome({"plan": fixed_plan(context).model_dump(), "source": "stub"}, cost_micros=0)
            planner = ClaudePlanner(self.settings.anthropic_api_key, model=call["model"])
            response = await planner.plan(context, prepared["images"])
            cost = (response.usage["input_tokens"] * rates["input_micros_per_token"]
                    + response.usage["output_tokens"] * rates["output_micros_per_token"]) if response.usage else None
            return Outcome({"plan": response.plan.model_dump(), "source": "claude"}, response.usage, cost, response.request_id)
        response = await self.provider.generate(purpose="background" if job["kind"] == "text_texture" else "scene", model=call["model"], quality=payload["quality"],
                                                prompt=payload["prompt"], images=prepared["images"], size=payload["size"])
        cost = response.cost_micros
        if response.usage:
            usage = response.usage
            text_tokens = usage.get("input_tokens_details", {}).get("text_tokens", 0)
            cost = math.ceil(text_tokens * Decimal(rates["text_input"])
                             + (usage["input_tokens"] - text_tokens) * Decimal(rates["image_input"])
                             + usage["output_tokens"] * Decimal(rates["image_output"]))
        return Outcome({"image_b64": base64.b64encode(response.image).decode("ascii")}, response.usage, cost)

    def finalise(self, conn, job, result):
        payload = json.loads(job["input_json"])
        if job["kind"] == "render":
            return exports.insert_render(conn, self.settings, job, result)
        if job["kind"] == "text_patch":
            return typography.insert_proposal(conn, job, result)
        if "look" in payload:
            return looks.insert_look(conn, job, payload, result)
        if job["kind"] == "plan":
            return visuals.insert_plan(conn, shop=job["shop_id"], creation_id=job["creation_id"], revision=job["origin_revision"],
                                       input_id=job["input_id"], context=PlanContext.model_validate(payload["context"]),
                                       plan=ScenePlan.model_validate(result["plan"]), photo_count=len(payload["photo_assets"]),
                                       source=result["source"], job_id=job["id"])
        image, mime = validate_image(result["image_b64"], size=payload["size"])
        sha = assets.put(self.settings.data_dir, image, assets.extension(mime))
        width, height = image_dimensions(payload["size"])
        assets.record(conn, sha=sha, kind="background_raw" if job["kind"] == "text_texture" else "scene", mime=mime, width=width, height=height, size=len(image))
        if job["kind"] == "text_texture":
            return typography.insert_effect(conn, job, sha)
        from uuid import uuid4
        id = str(uuid4())
        call = jobs.current_call(conn, job["id"])
        conn.execute(text("INSERT INTO poster_visuals (id,shop_id,input_id,job_id,base_visual_id,treatment,status,image_asset,"
                          "source_assets_json,reference_roles_json,plan_id,prompt_text,prompt_hash,direction_json,model,quality,size,"
                          "low_res_ack,created_at) VALUES (:id,:shop,:input,:job,:base,'scene','pending_review',:asset,:sources,"
                          ":roles,:plan,:prompt,:hash,:direction,:model,:quality,:size,:ack,:now)"),
                     {"id": id, "shop": job["shop_id"], "input": job["input_id"], "job": job["id"], "base": payload["base_visual_id"],
                      "asset": sha, "sources": canonical(payload["photo_assets"]), "roles": canonical(payload["reference_roles"]),
                      "plan": payload["plan_id"], "prompt": payload["prompt"], "hash": store._sha(payload["prompt"]),
                      "direction": canonical({"plan_id": payload["plan_id"]}), "model": call["model"], "quality": payload["quality"],
                      "size": payload["size"], "ack": int(payload["low_res_ack"]), "now": utc_now()})
        creation = store.get_creation(conn, job["shop_id"], job["creation_id"])
        document = Document.model_validate(creation["document"])
        layout = document.formats.get(payload["format"])
        count = conn.execute(text("SELECT COUNT(*) FROM poster_visuals v JOIN poster_jobs j ON j.id=v.job_id WHERE j.creation_id=:id"),
                             {"id": job["creation_id"]}).scalar_one()
        if (job["kind"] == "scene" and count == 1 and creation["status"] == "active" and layout is not None
                and creation["revision"] == job["origin_revision"] and layout.scene.visual_id is None):
            layout.scene = Scene(visual_id=id, crop=Crop(x=0, y=0, w=width, h=height))
            plan = ScenePlan.model_validate_json(store._owned(conn, "scene_plans", job["shop_id"], payload["plan_id"])["plan_json"])
            canvas_w, canvas_h = FORMATS[payload["format"]]
            boxes = {region.field: region.box for region in plan.overlay_regions}
            for layer in layout.layers:
                if layer.role in boxes:
                    box = boxes[layer.role]
                    if getattr(layer, "price_badge", None):
                        # A styled price pill keeps its size and sits centred in its reserved band.
                        layer.x = (box.x + box.w / 2) * canvas_w - layer.width / 2
                        layer.y = (box.y + box.h / 2) * canvas_h - layer.height / 2
                    else:
                        layer.x, layer.y = box.x * canvas_w, box.y * canvas_h
                        layer.width, layer.height = box.w * canvas_w, box.h * canvas_h
                drawn = payload.get("headline")
                if drawn and (layer.role == "title" or layer.role == "price" and "price_ar" in drawn
                              or layer.role in ("shop_name", "contact") and layer.role in drawn):
                    layer.visible = False  # the scene already carries this exact title / price / shop name / contact
            store._insert_version(conn, creation["id"], creation["revision"]+1, document)
            conn.execute(text("UPDATE creations SET current_revision=current_revision+1,updated_at=:now WHERE id=:id"),
                         {"id": creation["id"], "now": utc_now()})
        return id

    def _pending(self):
        with self.engine.connect() as conn:
            return [dict(row) for row in conn.execute(text("SELECT * FROM poster_jobs WHERE status='running'"
                                                          " AND kind IN ('plan','scene','refine') ORDER BY created_at")).mappings()
                    if jobs.spool_path(self.settings.data_dir, row["id"]).exists()]

    async def _execute(self, job):
        try:
            await run_job(self.engine, self.settings, job, prepare=self.prepare, send=self.send, finalise=self.finalise)
        except Exception as error:
            # A dispatch/DB failure must remain recoverable; never replace it with another provider call.
            log.error("poster %s needs local recovery: %s", job["id"], type(error).__name__)
            try:
                with self.engine.connect() as conn:
                    call = jobs.current_call(conn, job["id"])
                unsent = call is None or call["status"] == "reserved"
                await asyncio.to_thread(jobs.fail, self.engine, job["id"], "reconciliation_required",
                                        unsent=unsent, ambiguous=not unsent)
            except Exception as failure:
                log.error("poster %s recovery record unavailable: %s", job["id"], type(failure).__name__)

    async def serve(self):
        while not self.stopping:
            self.running = {id: task for id, task in self.running.items() if not task.done()}
            try:
                for job in await asyncio.to_thread(self._pending):
                    if len(self.running) < 2 and job["id"] not in self.running:
                        self.running[job["id"]] = asyncio.create_task(self._execute(job))
                while len(self.running) < 2:
                    job = await asyncio.to_thread(jobs.claim, self.engine, KINDS)
                    if job is None:
                        break
                    self.running[job["id"]] = asyncio.create_task(self._execute(job))
            except Exception as error:
                log.error("poster scheduler unavailable: %s", type(error).__name__)
            await asyncio.sleep(1)

    async def close(self):
        self.stopping = True
        await self.task
        if self.running:
            await asyncio.gather(*self.running.values())
        if isinstance(self.provider, OpenAIProvider):
            await self.provider.close()

    def start(self):
        self.task = asyncio.create_task(self.serve())
