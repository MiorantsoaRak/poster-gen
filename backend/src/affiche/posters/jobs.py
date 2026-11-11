"""Durable queue transitions. Feature admission/finalisation share these same write transactions."""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

from sqlalchemy import bindparam, text

from affiche.db import utc_now, write_tx
from affiche.visuals.admission import spent_micros
from affiche.visuals.gateway import RATES, usd_to_micros
from .models import canonical
from .planner import MODEL, RATE_CARD
from .store import Refused, _owned, _revision, get_creation, mutate

IMAGE_KINDS = {"scene", "refine", "text_texture", "background"}
PROVIDER_KINDS = IMAGE_KINDS | {"plan", "text_patch"}
KINDS = PROVIDER_KINDS | {"render", "cutout"}
# A price drawn in the image (ADR-044) costs a scene per change, so three per poster blocked ordinary use.
# The spend cap stays the money guard; this only stops a runaway loop on one poster (ADR-045).
SCENE_LIMIT = 12


@dataclass(frozen=True)
class CallSpec:
    provider: str
    model: str
    rate_card: dict
    estimate_micros: int


def call_spec(settings, kind: str) -> CallSpec | None:
    if kind not in KINDS:
        raise ValueError("invalid_job_kind")
    if kind not in PROVIDER_KINDS:
        return None
    if kind in {"plan", "text_patch"}:
        if (settings.planner_provider == "disabled" or settings.claude_model != MODEL
                or settings.planner_provider == "claude" and settings.anthropic_api_key is None):
            raise Refused("planner_unavailable", 503)
        provider, model, rates = settings.planner_provider, MODEL, RATE_CARD
        estimate = settings.estimate_plan_usd
    else:
        provider, model = settings.image_provider, settings.openai_image_model or "gpt-image-2"
        if model not in RATES or provider == "openai" and settings.openai_api_key is None:
            raise Refused("provider_unavailable", 503)
        rates = {key: str(value) for key, value in vars(RATES[model]).items()}
        estimate = (settings.estimate_texture_usd if kind == "text_texture" else
                    settings.estimate_background_usd if kind == "background" else settings.estimate_scene_usd)
    return CallSpec(provider, model, dict(rates), 0 if provider == "stub" else usd_to_micros(estimate))


def _reserve(conn, settings, job_id, call_no, spec: CallSpec):
    if spent_micros(conn, settings) + spec.estimate_micros > usd_to_micros(settings.spend_cap_usd):
        raise Refused("budget_exhausted", 429)
    conn.execute(text("INSERT INTO poster_calls (id,job_id,call_no,provider,model,rate_card_json,status,cost_micros,"
                      "cost_is_estimate,created_at) VALUES (:id,:job,:n,:provider,:model,:rates,'reserved',:cost,1,:now)"),
                 {"id": str(uuid4()), "job": job_id, "n": call_no, "provider": spec.provider, "model": spec.model,
                  "rates": canonical(spec.rate_card | {"reservation_micros": spec.estimate_micros}),
                  "cost": spec.estimate_micros, "now": utc_now()})


def enqueue(conn, settings, shop, creation_id, revision, kind, payload) -> dict:
    """Called inside mutate, after feature-specific references are validated. Never dispatches."""
    spec = call_spec(settings, kind)
    creation = get_creation(conn, shop, creation_id)
    _revision(creation["revision"], revision)
    if creation["status"] != "active":
        raise Refused("creation_abandoned", 409)
    if kind in IMAGE_KINDS and conn.execute(text(
            "SELECT 1 FROM poster_jobs WHERE creation_id=:id AND kind IN ('scene','refine','text_texture','background')"
            " AND status IN ('queued','running')"), {"id": creation_id}).first():
        raise Refused("image_job_running", 409)
    if kind in {"scene", "refine"} and conn.execute(text(
            "SELECT COUNT(*) FROM poster_jobs WHERE creation_id=:id AND kind IN ('scene','refine')"
            " AND status IN ('queued','running','succeeded')"), {"id": creation_id}).scalar_one() >= SCENE_LIMIT:
        raise Refused("attempt_limit", 409)
    if spec:
        mode_key = "planner_mode" if kind in {"plan", "text_patch"} else "provider_mode"
        recorded = conn.execute(text("SELECT value FROM meta WHERE key=:key"), {"key": mode_key}).scalar()
        if recorded is None:
            conn.execute(text("INSERT INTO meta VALUES (:key,:mode)"), {"key": mode_key, "mode": spec.provider})
        elif recorded != spec.provider:
            raise Refused("provider_mode_mismatch", 409)
    body, id = canonical(payload), str(uuid4())
    conn.execute(text("INSERT INTO poster_jobs (id,shop_id,creation_id,origin_revision,input_id,kind,input_json,"
                      "input_hash,status,created_at) VALUES (:id,:shop,:creation,:revision,:input,:kind,:body,:hash,'queued',:now)"),
                 {"id": id, "shop": shop, "creation": creation_id, "revision": revision,
                  "input": creation["document"]["input_id"], "kind": kind, "body": body,
                  "hash": hashlib.sha256(body.encode()).hexdigest(), "now": utc_now()})
    if spec:
        _reserve(conn, settings, id, 1, spec)
    return {"job_id": id, "status_url": f"/api/jobs/{id}"}


def get_job(conn, shop, id):
    job = _owned(conn, "poster_jobs", shop, id)
    cost = conn.execute(text("SELECT COALESCE(SUM(cost_micros),0), COALESCE(MAX(cost_is_estimate),0)"
                             " FROM poster_calls WHERE job_id=:id"), {"id": id}).one()
    # A style brief runs as a planner job (the kinds are fixed by migration 0006), but its result is a look,
    # not a plan: clients must not load it as one. The canonical payload of such a job has the single key "look".
    kind = "look" if job["kind"] == "plan" and job["input_json"].startswith('{"look":') else job["kind"]
    return {key: job[key] for key in ("id", "status", "result_ref", "error_code", "created_at", "started_at", "finished_at")} | {
        "kind": kind, "usage": {"recorded_micros": cost[0], "estimated": bool(cost[1])}}


def cancel(engine, shop, key, id):
    def apply(conn):
        job = _owned(conn, "poster_jobs", shop, id)
        if job["status"] != "queued":
            raise Refused("already_started", 409)
        now = utc_now()
        conn.execute(text("UPDATE poster_jobs SET status='cancelled',finished_at=:now WHERE id=:id"), {"id": id, "now": now})
        conn.execute(text("UPDATE poster_calls SET status='cancelled',cost_micros=0,cost_is_estimate=0,finished_at=:now"
                          " WHERE job_id=:id AND status='reserved'"), {"id": id, "now": now})
        return 200, get_job(conn, shop, id)
    return mutate(engine, shop, key, "POST", f"/api/jobs/{id}/cancel", {}, apply)


def claim(engine, kinds: tuple[str, ...]):
    if not kinds or not set(kinds) <= KINDS:
        raise ValueError("invalid_job_kinds")
    with write_tx(engine) as conn:
        running = conn.execute(text("SELECT COUNT(c.id),COUNT(*)-COUNT(c.id) FROM poster_jobs j LEFT JOIN poster_calls c"
                                    " ON c.job_id=j.id AND c.call_no=(SELECT MAX(call_no) FROM poster_calls WHERE job_id=j.id)"
                                    " WHERE j.status='running'")).one()
        rows = conn.execute(text("SELECT * FROM poster_jobs WHERE status='queued' AND kind IN :kinds ORDER BY created_at,id")
                            .bindparams(bindparam("kinds", expanding=True)), {"kinds": kinds}).mappings()
        for row in rows:
            if running[0 if row["kind"] in PROVIDER_KINDS else 1] >= (2 if row["kind"] in PROVIDER_KINDS else 1):
                continue
            conn.execute(text("UPDATE poster_jobs SET status='running',started_at=:now WHERE id=:id"),
                         {"id": row["id"], "now": utc_now()})
            return dict(row) | {"status": "running"}
    return None


def current_call(conn, id):
    return conn.execute(text("SELECT * FROM poster_calls WHERE job_id=:id ORDER BY call_no DESC LIMIT 1"),
                        {"id": id}).mappings().first()


def dispatch(engine, id):
    with write_tx(engine) as conn:
        job = conn.execute(text("SELECT status FROM poster_jobs WHERE id=:id"), {"id": id}).scalar()
        call = current_call(conn, id)
        if job != "running" or call is None or call["status"] != "reserved":
            raise Refused("invalid_job_state", 409)
        conn.execute(text("UPDATE poster_calls SET status='running',started_at=:now WHERE id=:id"),
                     {"id": call["id"], "now": utc_now()})
        return dict(call) | {"status": "running"}


def fail(engine, id, code, *, ambiguous=False, unsent=False, usage=None, cost_micros=None):
    with write_tx(engine) as conn:
        job = conn.execute(text("SELECT status FROM poster_jobs WHERE id=:id"), {"id": id}).scalar()
        if job != "running":
            raise Refused("invalid_job_state", 409)
        call = current_call(conn, id)
        if unsent and call and call["status"] != "reserved":
            raise Refused("call_already_dispatched", 409)
        if cost_micros is not None and (type(cost_micros) is not int or cost_micros < 0):
            raise ValueError("invalid_cost")
        status, now = ("interrupted" if ambiguous else "failed"), utc_now()
        conn.execute(text("UPDATE poster_jobs SET status=:status,error_code=:code,finished_at=:now WHERE id=:id"),
                     {"id": id, "status": status, "code": code, "now": now})
        if call:
            cost = 0 if unsent else cost_micros
            conn.execute(text("UPDATE poster_calls SET status=:status,cost_micros=:cost,cost_is_estimate=:estimate,"
                              "usage_json=:usage,finished_at=:now WHERE id=:id"),
                         {"id": call["id"], "status": status, "cost": call["cost_micros"] if cost is None else cost,
                          "estimate": int(cost is None), "usage": canonical(usage) if usage is not None else None, "now": now})


def reserve_rate_limit_retry(engine, settings, id) -> bool:
    """Only an explicit provider 429 may use this. Caller applies a bounded delay before dispatch."""
    with write_tx(engine) as conn:
        job = conn.execute(text("SELECT status FROM poster_jobs WHERE id=:id"), {"id": id}).scalar()
        call = current_call(conn, id)
        if job != "running" or call is None or call["status"] != "running":
            raise Refused("invalid_job_state", 409)
        if call["call_no"] != 1:
            return False
        rates = json.loads(call["rate_card_json"])
        reservation = rates.pop("reservation_micros")
        # A definite rejection is unbilled; update and replacement reservation commit together.
        conn.execute(text("UPDATE poster_calls SET status='failed',cost_micros=0,cost_is_estimate=0,finished_at=:now WHERE id=:id"),
                     {"id": call["id"], "now": utc_now()})
        _reserve(conn, settings, id, 2, CallSpec(call["provider"], call["model"], rates, reservation))
        return True


def spool_path(data_dir: Path, id: str):
    from uuid import UUID
    if str(UUID(id)) != id:
        raise ValueError("invalid_job_id")
    return data_dir / "poster-spool" / f"{id}.json"


def spool(data_dir, job, result: dict, *, usage=None, cost_micros=None, request_id=None):
    if cost_micros is not None and (type(cost_micros) is not int or cost_micros < 0):
        raise ValueError("invalid_cost")
    envelope = {"job_id": job["id"], "input_hash": job["input_hash"], "result": result,
                "usage": usage, "cost_micros": cost_micros, "request_id": request_id}
    encoded = canonical(envelope).encode()
    path = spool_path(data_dir, job["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != encoded:
            raise ValueError("spool_conflict")
        return
    temporary = path.with_suffix(f".{uuid4().hex}.tmp")
    with temporary.open("xb") as file:
        file.write(encoded)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temporary, path)


def finish_spool(engine, data_dir, id, finalise):
    """Local-only retry: finalise(conn, job, result) validates/persists the feature result and returns its ID."""
    envelope = json.loads(spool_path(data_dir, id).read_bytes())
    with write_tx(engine) as conn:
        job = conn.execute(text("SELECT * FROM poster_jobs WHERE id=:id"), {"id": id}).mappings().one()
        if job["status"] == "succeeded":
            return job["result_ref"]
        if (job["status"] != "running" or envelope["job_id"] != id or envelope["input_hash"] != job["input_hash"]):
            raise Refused("invalid_job_state", 409)
        call = current_call(conn, id)
        if call and call["status"] != "running":
            raise Refused("invalid_job_state", 409)
        cost = envelope["cost_micros"]
        if cost is not None and (type(cost) is not int or cost < 0):
            raise ValueError("invalid_cost")
        result_ref = finalise(conn, dict(job), envelope["result"])
        now = utc_now()
        conn.execute(text("UPDATE poster_jobs SET status='succeeded',result_ref=:ref,error_code=NULL,finished_at=:now WHERE id=:id"),
                     {"id": id, "ref": result_ref, "now": now})
        if call:
            conn.execute(text("UPDATE poster_calls SET status='succeeded',cost_micros=:cost,cost_is_estimate=:estimate,"
                              "usage_json=:usage,provider_request_id=:request,finished_at=:now WHERE id=:id"),
                         {"id": call["id"], "cost": call["cost_micros"] if cost is None else cost, "estimate": int(cost is None),
                          "usage": canonical(envelope["usage"]) if envelope["usage"] is not None else None,
                          "request": envelope["request_id"], "now": now})
        return result_ref


def recover(engine, data_dir):
    """Only under the API owner lock. Return spooled running IDs for local finalisation before workers start."""
    ready = []
    with write_tx(engine) as conn:
        for job in conn.execute(text("SELECT * FROM poster_jobs WHERE status='running'")).mappings().all():
            call = current_call(conn, job["id"])
            if spool_path(data_dir, job["id"]).exists():
                ready.append(job["id"])
                continue
            if call is None and job["recovery_count"] == 1:
                conn.execute(text("UPDATE poster_jobs SET status='failed',error_code='local_job_interrupted',finished_at=:now WHERE id=:id"),
                             {"id": job["id"], "now": utc_now()})
            elif call is None or call["status"] == "reserved":
                conn.execute(text("UPDATE poster_jobs SET status='queued',started_at=NULL WHERE id=:id"), {"id": job["id"]})
                if call is None:
                    conn.execute(text("UPDATE poster_jobs SET recovery_count=1 WHERE id=:id"), {"id": job["id"]})
            else:
                now = utc_now()
                conn.execute(text("UPDATE poster_jobs SET status='interrupted',error_code='outcome_unknown',finished_at=:now WHERE id=:id"),
                             {"id": job["id"], "now": now})
                conn.execute(text("UPDATE poster_calls SET status='interrupted',finished_at=:now WHERE id=:id"),
                             {"id": call["id"], "now": now})
    return ready
