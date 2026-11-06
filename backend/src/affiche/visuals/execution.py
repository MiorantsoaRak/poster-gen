"""Request execution (D-PRODUCT-VISUALS-003 "The provider call", D-PV-006 step 3): call 1, the one retry (call 2)
inside a budget transaction, and the success and failure transactions of a request that `admission` inserted
running. Files are written before each transaction and their rows recorded inside it (ADR-017)."""

import asyncio
import io
import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from sqlalchemy import Connection, Engine, Row, exc, text

from affiche import assets
from affiche.config import Settings
from affiche.db import utc_now, write_tx
from affiche.visuals.admission import Refused, reserve
from affiche.visuals.cutout import BBox, bake_shadow, place
from affiche.visuals.gateway import (
    MAX_DETAIL_CHARS, OpenAIProvider, ProviderError, ProviderResult, StubProvider, prepare_provider_input,
)

log = logging.getLogger(__name__)

RETRY_DELAY_S = 5
BUSY_RETRY_S = 2  # design line 249: wait 2 s, try once more
RAW_KINDS = {"scene": "scene", "background": "background_raw"}
Sleep = Callable[[float], Awaitable[object]]
_executing: set[str] = set()


class _NotRunning(Exception):
    """The request left 'running' under us (owner recovery, another process): nothing more is written."""


@dataclass
class _Job:
    engine: Engine
    settings: Settings
    request: Row
    spec: dict  # request_json, as admission wrote it
    call_id: str  # the running call
    call_no: int


async def execute(engine: Engine, settings: Settings, provider: OpenAIProvider | StubProvider, request_id: str, *,
                  slots: asyncio.Semaphore, sleep: Sleep = asyncio.sleep) -> str:
    """Runs an admitted request to its end and returns its status: 'succeeded' or 'failed'; the status someone else
    gave it ('interrupted', ...), with nothing written; or 'running' when the busy fallback could not write either
    (owner recovery ends it). `slots`: one Semaphore(2) per event loop. An unexpected error marks the call and the
    request failed (invalid_request) and propagates."""
    # ponytail: DB, file and image work run on the event loop; the phase-2 API should run them in a thread.
    if request_id in _executing:  # ponytail: in-process guard; enough under the one-process-per-owner lock
        raise RuntimeError(f"request {request_id} is already executing in this process")
    _executing.add(request_id)
    try:
        return await _run(engine, settings, provider, request_id, slots, sleep)
    except _NotRunning:
        with engine.connect() as conn:
            status = _status(conn, request_id)
        log.warning("request %s is %s, not running: no provider call or candidate", request_id, status)
        return status
    finally:
        _executing.discard(request_id)


async def _run(engine: Engine, settings: Settings, provider: OpenAIProvider | StubProvider, request_id: str,
               slots: asyncio.Semaphore, sleep: Sleep) -> str:
    with engine.connect() as conn:
        request = conn.execute(text("SELECT * FROM generation_requests WHERE id = :id"), {"id": request_id}).one()
        if request.status != "running":
            raise _NotRunning
        call = conn.execute(text(
            "SELECT id, call_no FROM provider_calls WHERE request_id = :id AND status = 'running'"),
            {"id": request_id}).one()
    job = _Job(engine, settings, request, json.loads(request.request_json), call.id, call.call_no)
    result = None
    try:
        try:
            images, cutout = _load_inputs(job)
        except OSError as error:  # nothing was sent: the reservation stays the cost
            return _fail(job, "storage", error)
        while True:
            try:
                async with slots:
                    result = await provider.generate(purpose=request.purpose, model=job.spec["model"],
                                                     quality=job.spec["quality"], prompt=job.spec["prompt"],
                                                     images=images)
                break
            except ProviderError as error:
                if not await _after_failure(job, error, sleep):
                    with engine.connect() as conn:
                        return _status(conn, request_id)
        try:
            return _succeed(job, result, cutout)
        except OSError as error:  # the call was billed: it keeps its usage-based cost
            return _fail(job, "storage", error, result)
    except _NotRunning:
        raise
    except Exception as error:
        _fail(job, "invalid_request", error, result)
        raise


def _load_inputs(job: _Job) -> tuple[list[bytes], tuple[bytes, BBox] | None]:
    """Everything the request needs, read before any spend: the provider_input copies to send (stored and recorded)
    and, for a background, the cutout PNG and its bbox."""
    data_dir, cutout = job.settings.data_dir, None
    with job.engine.connect() as conn:
        originals = [assets.load(conn, data_dir, sha) for sha in job.spec["images"]]
        if job.request.cutout_id is not None:
            row = conn.execute(text("SELECT cutout_asset, bbox_json FROM cutouts WHERE id = :id"),
                               {"id": job.request.cutout_id}).one()
            cutout = assets.load(conn, data_dir, row.cutout_asset), tuple(json.loads(row.bbox_json))
    images = [prepare_provider_input(data) for data in originals]
    staged = [_stage(data_dir, data, "provider_input") for data in images]
    with write_tx(job.engine) as conn:
        for row in staged:
            assets.record(conn, **row)
    return images, cutout


async def _after_failure(job: _Job, error: ProviderError, sleep: Sleep) -> bool:
    """Fails call n; the request too unless call 1 failed retryably. True when call 2 is then running."""
    retry = error.retryable and job.call_no == 1
    with write_tx(job.engine) as conn:
        _finish_call(conn, job.call_id, "failed", kind=error.kind, detail=error.detail)
        if not retry:
            _finish_request(conn, job.request.id, "failed", kind=error.kind)
    if not retry:
        return False
    await sleep(RETRY_DELAY_S)
    return await _retry(job, error.kind, sleep)


async def _retry(job: _Job, call_1_kind: str, sleep: Sleep) -> bool:
    for wait in (0, BUSY_RETRY_S):
        if wait:
            await sleep(wait)
        try:
            call_id = _start_call_2(job)
        except exc.OperationalError as error:
            if not _locked(error):
                raise
            log.warning("request %s: database locked when starting call 2 (%s)", job.request.id, error.orig)
            continue
        if call_id is None:
            return False
        job.call_id, job.call_no = call_id, 2
        return True
    try:  # still locked (design line 249): the request fails with call 1's kind
        with write_tx(job.engine) as conn:
            _finish_request(conn, job.request.id, "failed", kind=call_1_kind)
    except exc.OperationalError as error:
        if not _locked(error):
            raise
        log.error("request %s stays running until owner recovery: database locked (%s)", job.request.id, error.orig)
    return False


def _start_call_2(job: _Job) -> str | None:
    """Rules 6-7 for call 2 in one transaction (ADR-018): the new call's id, or None when the budget refuses it, in
    which case the same transaction fails the request (budget_exhausted). Call 1 keeps its cost either way."""
    call_id = str(uuid.uuid4())
    with write_tx(job.engine) as conn:
        _require_running(conn, job.request.id)
        try:
            cost = reserve(conn, job.settings, model=job.spec["model"], purpose=job.request.purpose)
        except Refused:
            _finish_request(conn, job.request.id, "failed", kind="budget_exhausted")
            return None
        conn.execute(text(
            "INSERT INTO provider_calls (id, request_id, call_no, provider, model, status, cost_micros,"
            " cost_is_estimate, started_at) VALUES (:id, :request_id, 2, :provider, :model, 'running', :cost, 1, :now)"),
            {"id": call_id, "request_id": job.request.id, "provider": job.settings.image_provider,
             "model": job.spec["model"], "cost": cost, "now": utc_now()})
    return call_id


def _succeed(job: _Job, result: ProviderResult, cutout: tuple[bytes, BBox] | None) -> str:
    """The success transaction: the raw image, the call's cost, the pending_review candidate, the request."""
    data_dir = job.settings.data_dir
    raw = _stage(data_dir, result.image, RAW_KINDS[job.request.purpose])
    image, box = raw, None
    if cutout is not None:  # the candidate's image has the baked shadow; the call's raw_asset stays without it
        cutout_png, bbox = cutout
        box = place(bbox)
        image = _stage(data_dir, bake_shadow(result.image, cutout_png, bbox, box), "background")
    candidate_id = str(uuid.uuid4())
    with write_tx(job.engine) as conn:
        _require_running(conn, job.request.id)
        assets.record(conn, **raw)
        assets.record(conn, **image)  # the same row for a scene: a no-op
        _finish_call(conn, job.call_id, "succeeded", result=result, raw_asset=raw["sha"])
        _insert_candidate(conn, job, candidate_id, image["sha"], box)
        _finish_request(conn, job.request.id, "succeeded", candidate_id=candidate_id)
    return "succeeded"


def _insert_candidate(conn: Connection, job: _Job, candidate_id: str, image_asset: str,
                      box: tuple[float, ...] | None) -> None:
    spec, request = job.spec, job.request
    conn.execute(text(
        "INSERT INTO candidates (id, variant_ref, cycle_no, subject_name, subject_variant, treatment, status,"
        " request_id, parent_id, attempt_no, direction_json, source_assets_json, prompt, corrections_applied,"
        " provider, model, quality, size, run_label, image_asset, cutout_id, product_box_json, low_res_warning,"
        " created_at) VALUES (:id, :variant_ref, :cycle_no, :subject_name, :subject_variant, :treatment,"
        " 'pending_review', :request_id, :parent_id, :attempt_no, :direction, :sources, :prompt,"
        " :corrections_applied, :provider, :model, :quality, :size, :run_label, :image, :cutout_id, :box,"
        " :low_res, :now)"),
        {"id": candidate_id, "variant_ref": request.variant_ref, "cycle_no": request.cycle_no,
         "subject_name": spec["subject"]["name"], "subject_variant": spec["subject"]["variant"],
         "treatment": spec["treatment"], "request_id": request.id, "parent_id": request.parent_id,
         "attempt_no": spec["attempt_no"], "direction": json.dumps(spec["direction"], ensure_ascii=False),
         "sources": json.dumps(spec["source_assets"]), "prompt": spec["prompt"],
         "corrections_applied": request.corrections_applied, "provider": job.settings.image_provider,
         "model": spec["model"], "quality": spec["quality"], "size": spec["size"], "run_label": request.run_label,
         "image": image_asset, "cutout_id": request.cutout_id, "box": None if box is None else json.dumps(box),
         "low_res": spec["low_res_warning"], "now": utc_now()})


def _fail(job: _Job, kind: str, error: Exception, result: ProviderResult | None = None) -> str:
    """Fails the running call and the request with `kind`; a billed result keeps its usage-based cost."""
    detail = f"{type(error).__name__}: {error}"[:MAX_DETAIL_CHARS]
    with write_tx(job.engine) as conn:
        _finish_call(conn, job.call_id, "failed", kind=kind, detail=detail, result=result)
        _finish_request(conn, job.request.id, "failed", kind=kind)
        return _status(conn, job.request.id)


def _finish_call(conn: Connection, call_id: str, status: str, *, kind: str | None = None, detail: str | None = None,
                 result: ProviderResult | None = None, raw_asset: str | None = None) -> None:
    """Without a usage-based cost the reserved estimate stays (ADR-015)."""
    conn.execute(text(
        "UPDATE provider_calls SET status = :status, error_kind = :kind, error_detail = :detail, raw_asset = :raw,"
        " usage_json = :usage, cost_micros = COALESCE(:cost, cost_micros),"
        " cost_is_estimate = CASE WHEN :cost IS NULL THEN cost_is_estimate ELSE 0 END, finished_at = :now"
        " WHERE id = :id AND status = 'running'"),
        {"id": call_id, "status": status, "kind": kind, "detail": detail, "raw": raw_asset,
         "usage": None if result is None or result.usage is None else json.dumps(result.usage),
         "cost": None if result is None else result.cost_micros, "now": utc_now()})


def _finish_request(conn: Connection, request_id: str, status: str, *, kind: str | None = None,
                    candidate_id: str | None = None) -> None:
    conn.execute(text(
        "UPDATE generation_requests SET status = :status, error_kind = :kind, candidate_id = :candidate,"
        " finished_at = :now WHERE id = :id AND status = 'running'"),
        {"id": request_id, "status": status, "kind": kind, "candidate": candidate_id, "now": utc_now()})


def _stage(data_dir: Path, data: bytes, kind: str) -> dict:
    """Writes the file now and returns its row, to record inside the caller's transaction (ADR-017)."""
    with Image.open(io.BytesIO(data)) as image:
        mime, (width, height) = Image.MIME[image.format], image.size
    sha = assets.put(data_dir, data, assets.extension(mime))
    return {"sha": sha, "kind": kind, "mime": mime, "width": width, "height": height, "size": len(data)}


def _status(conn: Connection, request_id: str) -> str:
    return conn.execute(text("SELECT status FROM generation_requests WHERE id = :id"), {"id": request_id}).scalar_one()


def _require_running(conn: Connection, request_id: str) -> None:
    # Under BEGIN IMMEDIATE nobody can change the status between this read and the transaction's writes.
    if _status(conn, request_id) != "running":
        raise _NotRunning


def _locked(error: exc.OperationalError) -> bool:
    return "database is locked" in str(error.orig)  # SQLITE_BUSY after the busy timeout
