"""Request admission (D-PRODUCT-VISUALS-003 rules 1-7, D-PV-005): every rule and the call-1 reservation of a new
logical request run in one BEGIN IMMEDIATE transaction, so two processes can never both pass a guard. A refusal
raises inside the transaction, so nothing is written."""

import hashlib
import json
import uuid
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from functools import partial
from typing import NamedTuple

from sqlalchemy import Connection, Engine, Row, bindparam, text

from affiche.config import Settings
from affiche.db import utc_now, write_tx
from affiche.runtime import Owner
from affiche.visuals.gateway import RATES, Purpose, usd_to_micros
from affiche.visuals.prompts import (
    Direction, SceneSubject, build_background_prompt, build_scene_prompt, find_commercial_terms,
)

MAX_PHOTOS = 3
LOW_RESOLUTION = "low_resolution"
TREATMENTS: dict[Purpose, str] = {"scene": "scene", "background": "photo_preserved"}
_IN_SCOPE = "variant_ref = :variant_ref AND cycle_no = :cycle_no AND run_label = :run_label"
_LIVE = "status IN ('running','succeeded')"  # what the guard indexes and the allowance count


@dataclass(frozen=True)
class Admitted:
    request_id: str
    attempt_no: int
    existing: bool  # an earlier call with this id and payload made the request; nothing was reserved now
    reservation: int  # micro-USD reserved for call 1 by this call (0 when existing)
    spent: int  # micro-USD on the ledger since SPEND_CAP_SINCE, this reservation included
    cap: int


class Refused(Exception):
    """A request the rules refuse: the HTTP status, a stable code for the UI and the CLI, optional details."""

    def __init__(self, status: int, code: str, details: dict | None = None) -> None:
        super().__init__(f"{status} {code}" if details is None else f"{status} {code} {details}")
        self.status = status
        self.code = code
        self.details = details


class _Scope(NamedTuple):
    variant_ref: str
    cycle_no: int
    run_label: str


@dataclass(frozen=True)
class _Plan:
    """What an entry point resolved for the shared rules."""

    purpose: Purpose
    scope: _Scope
    run: Row
    arm: str | None
    subject: SceneSubject
    direction: Direction
    source_assets: list[str]  # scene: the photos sent; background: the cutout's source photo
    low_res: bool
    parent: Row | None = None
    cutout: Row | None = None
    latest: bool = False  # the parent is the scope's latest candidate, not one the caller named (rule 5)


def request_scene(engine: Engine, settings: Settings, *, id: str, variant_ref: str, run_label: str, owner: Owner,
                  variant_photos: Sequence[str], photo_assets: Sequence[str] | None = None, direction: Direction,
                  acknowledged_warnings: Collection[str] = ()) -> Admitted:
    """An initial scene request. variant_photos: the variant's photos in the catalogue (asset sha256s, in order), the
    set the photos must belong to; photo_assets defaults to its first 3."""
    payload = {"purpose": "scene", "variant_ref": variant_ref, "run_label": run_label,
               "photo_assets": None if photo_assets is None else list(photo_assets),
               "direction": direction.model_dump(mode="json"),
               "acknowledged_warnings": sorted(set(acknowledged_warnings))}

    def resolve(conn: Connection) -> _Plan:
        scope, run, arm, subject = _product(conn, variant_ref, run_label)
        photos = list(variant_photos[:MAX_PHOTOS] if photo_assets is None else photo_assets)
        if not 1 <= len(photos) <= MAX_PHOTOS:
            raise ValueError(f"a scene takes 1 to {MAX_PHOTOS} photos, not {len(photos)}")
        if foreign := [sha for sha in photos if sha not in variant_photos]:
            raise Refused(422, "photo_not_in_variant", {"assets": foreign})
        short_edges = _short_edges(conn, [*photos, *([direction.style_ref] if direction.style_ref else [])])
        low_res = [sha for sha in photos if short_edges[sha] < settings.min_source_short_edge]
        if low_res and LOW_RESOLUTION not in acknowledged_warnings:
            raise Refused(409, "warning_not_acknowledged", {"warnings": [LOW_RESOLUTION], "assets": low_res})
        return _Plan("scene", scope, run, arm, subject, direction, photos, bool(low_res))

    return _admit(engine, settings, id, owner, payload, resolve)


def request_revision(engine: Engine, settings: Settings, *, id: str, parent_id: str, owner: Owner) -> Admitted:
    """A revision of a rejected candidate (D-PV-005). A scene parent gets a scene with its photos and direction; a
    photo_preserved parent gets a new background for the same cutout."""

    def resolve(conn: Connection) -> _Plan:
        parent = _row(conn, "candidates", parent_id)
        scope, run, arm, subject = _product(conn, parent.variant_ref, parent.run_label)
        if parent.treatment == "scene":
            return _Plan("scene", scope, run, arm, subject, Direction.model_validate_json(parent.direction_json),
                         json.loads(parent.source_assets_json), bool(parent.low_res_warning), parent=parent)
        cutout = _row(conn, "cutouts", parent.cutout_id)
        return _Plan("background", scope, run, arm, subject, Direction.model_validate_json(cutout.direction_json),
                     [cutout.source_asset], bool(cutout.low_res_warning), parent=parent, cutout=cutout)

    return _admit(engine, settings, id, owner, {"purpose": "revision", "parent_id": parent_id}, resolve)


def request_background(engine: Engine, settings: Settings, *, id: str, cutout_id: str, owner: Owner) -> Admitted:
    """A background on a confirmed cutout (D-PV-003 rule 5): the scope's initial background, or else a revision of
    its latest photo_preserved candidate, which replaces a wrong cutout without a new cycle."""

    def resolve(conn: Connection) -> _Plan:
        cutout = _row(conn, "cutouts", cutout_id)
        scope, run, arm, subject = _product(conn, cutout.variant_ref, cutout.run_label)
        # The chain is linear, so its tip has the highest attempt number. Not the clock, which can step back.
        latest = conn.execute(text(
            f"SELECT * FROM candidates WHERE {_IN_SCOPE} AND treatment = 'photo_preserved'"
            " ORDER BY attempt_no DESC LIMIT 1"), scope._asdict()).first()
        return _Plan("background", scope, run, arm, subject, Direction.model_validate_json(cutout.direction_json),
                     [cutout.source_asset], bool(cutout.low_res_warning), parent=latest, cutout=cutout, latest=True)

    return _admit(engine, settings, id, owner, {"purpose": "background", "cutout_id": cutout_id}, resolve)


def reserve(conn: Connection, settings: Settings, *, model: str, purpose: Purpose) -> int:
    """Rule 6, for call 1 here and for call 2 (the retry, T-PV-007): the micro-USD to reserve, or Refused
    budget_exhausted. r = max(the purpose's estimate, ceil(1.25 x the highest usage-based cost of an earlier call
    with this model and purpose)); refused when spent + r > cap. Past calls are never rewritten."""
    estimate = settings.estimate_scene_usd if purpose == "scene" else settings.estimate_background_usd
    highest = conn.execute(text(
        "SELECT MAX(c.cost_micros) FROM provider_calls c JOIN generation_requests r ON r.id = c.request_id"
        " WHERE c.cost_is_estimate = 0 AND c.model = :model AND r.purpose = :purpose"),
        {"model": model, "purpose": purpose}).scalar()
    floor = 0 if highest is None else (5 * highest + 3) // 4  # ceil(1.25 x highest) in integers
    reservation = max(usd_to_micros(estimate), floor)
    spent, cap = spent_micros(conn, settings), usd_to_micros(settings.spend_cap_usd)
    if spent + reservation > cap:
        raise Refused(409, "budget_exhausted", {"spent": spent, "cap": cap, "reservation": reservation})
    return reservation


def _admit(engine: Engine, settings: Settings, request_id: str, owner: Owner, payload: dict,
           resolve: Callable[[Connection], _Plan]) -> Admitted:
    payload_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    cap = usd_to_micros(settings.spend_cap_usd)
    with write_tx(engine) as conn:
        known = conn.execute(text("SELECT payload_hash, request_json FROM generation_requests WHERE id = :id"),
                             {"id": request_id}).first()
        if known is not None:  # rule 1 comes first: a replay is never refused by what happened since
            if known.payload_hash != payload_hash:
                raise Refused(409, "request_id_reused")
            return Admitted(request_id, json.loads(known.request_json)["attempt_no"], True, 0,
                            spent_micros(conn, settings), cap)
        plan = resolve(conn)
        if matches := find_commercial_terms(plan.direction.description or ""):
            raise Refused(422, "commercial_terms", {"field": "description", "matches": matches})
        # A stale target (an earlier cycle) is refused as such, before the current scope's rules can mask it.
        for target in (plan.parent, plan.cutout):
            if target is not None and _Scope(target.variant_ref, target.cycle_no, target.run_label) != plan.scope:
                raise Refused(409, "wrong_scope")
        attempt_no = _check_scope(conn, plan)
        if plan.parent is not None:
            _check_parent(conn, plan)
        if plan.cutout is not None and plan.cutout.status != "confirmed":  # rule 5
            raise Refused(409, "cutout_not_confirmed")
        prompt, corrections_applied = _prompt(plan)
        if plan.run.model not in RATES:  # ADR-015: a configuration error, refused before any reservation
            raise ValueError(f"no token rates for model {plan.run.model!r}: add them to gateway.RATES first")
        reservation = reserve(conn, settings, model=plan.run.model, purpose=plan.purpose)
        _insert(conn, settings, plan, request_id=request_id, owner=owner, payload_hash=payload_hash,
                attempt_no=attempt_no, prompt=prompt, corrections_applied=corrections_applied,
                reservation=reservation)
        return Admitted(request_id, attempt_no, False, reservation, spent_micros(conn, settings), cap)


def _check_scope(conn: Connection, plan: _Plan) -> int:
    """Rule 3: the abandoned scope, one live initial request per purpose, the scene allowance. Returns attempt_no."""
    params = {**plan.scope._asdict(), "purpose": plan.purpose, "treatment": TREATMENTS[plan.purpose]}
    if conn.execute(text(f"SELECT 1 FROM abandonments WHERE {_IN_SCOPE} AND treatment = :treatment"),
                    params).first():
        raise Refused(409, "abandoned")
    requests = f"FROM generation_requests WHERE {_IN_SCOPE} AND purpose = :purpose"
    if plan.parent is None and conn.execute(
            text(f"SELECT 1 {requests} AND parent_id IS NULL AND {_LIVE}"), params).first():
        pending = conn.execute(text(
            f"SELECT EXISTS (SELECT 1 FROM candidates WHERE {_IN_SCOPE} AND treatment = :treatment"
            f" AND status = 'pending_review') OR EXISTS (SELECT 1 {requests} AND status = 'running')"),
            params).scalar_one()
        raise Refused(409, "review_pending" if pending else "use_revision")
    used = conn.execute(text(f"SELECT COUNT(*) {requests} AND {_LIVE}"), params).scalar_one()
    if plan.purpose == "scene" and used >= plan.run.attempt_limit:
        raise Refused(409, "attempt_limit_reached", {"fallback": "photo_preserved"})
    return used + 1  # a background's number counts the scope's backgrounds: it never takes a scene slot


def _check_parent(conn: Connection, plan: _Plan) -> None:
    """Rule 4: the parent is rejected and has no live revision yet."""
    parent = plan.parent
    if parent.status != "rejected":
        # Rule 5: the scope's latest candidate, still under review, must be reviewed first.
        raise Refused(409, "review_pending" if plan.latest and parent.status == "pending_review" else "not_rejected")
    # Authoritative under BEGIN IMMEDIATE; req_one_revision is only the backstop (its IntegrityError means a bug).
    if conn.execute(text(f"SELECT 1 FROM generation_requests WHERE parent_id = :id AND {_LIVE}"),
                    {"id": parent.id}).first():
        raise Refused(409, "revision_already_requested")


def _prompt(plan: _Plan) -> tuple[str, int]:
    """A revision carries the parent's reasons and note, except for an arm-B product of a by_arm run: a plain re-roll
    (ADR-011). corrections_applied means a line was actually added (ADR-014)."""
    build = (partial(build_scene_prompt, plan.subject, plan.direction) if plan.purpose == "scene"
             else partial(build_background_prompt, plan.direction))
    plain = build(None, None)
    parent = plan.parent
    if parent is None or (plan.run.corrections_mode == "by_arm" and plan.arm == "B"):
        return plain, 0
    reasons = json.loads(parent.rejection_reasons_json) if parent.rejection_reasons_json else None
    prompt = build(reasons, parent.rejection_note)
    return prompt, int(prompt != plain)


def _insert(conn: Connection, settings: Settings, plan: _Plan, *, request_id: str, owner: Owner, payload_hash: str,
            attempt_no: int, prompt: str, corrections_applied: int, reservation: int) -> None:
    """Rule 7: the request (running) and call 1 (running, cost = the reservation, an estimate)."""
    images = list(plan.source_assets) if plan.purpose == "scene" else []
    if plan.direction.style_ref:
        images.append(plan.direction.style_ref)
    # Everything T-PV-007 needs to call the provider and create the candidate without re-deriving it.
    request_json = {"prompt": prompt, "images": images, "model": plan.run.model, "quality": plan.run.quality,
                    "size": plan.run.size, "subject": plan.subject.model_dump(),
                    "direction": plan.direction.model_dump(mode="json"), "attempt_no": attempt_no,
                    "treatment": TREATMENTS[plan.purpose], "source_assets": plan.source_assets,
                    "low_res_warning": int(plan.low_res)}
    now = utc_now()
    conn.execute(text(
        "INSERT INTO generation_requests (id, payload_hash, purpose, variant_ref, cycle_no, run_label, parent_id,"
        " cutout_id, request_json, corrections_applied, owner, status, created_at) VALUES (:id, :payload_hash,"
        " :purpose, :variant_ref, :cycle_no, :run_label, :parent_id, :cutout_id, :request_json,"
        " :corrections_applied, :owner, 'running', :now)"),
        {"id": request_id, "payload_hash": payload_hash, "purpose": plan.purpose, **plan.scope._asdict(),
         "parent_id": None if plan.parent is None else plan.parent.id,
         "cutout_id": None if plan.cutout is None else plan.cutout.id,
         "request_json": json.dumps(request_json, ensure_ascii=False), "corrections_applied": corrections_applied,
         "owner": owner, "now": now})
    conn.execute(text(
        "INSERT INTO provider_calls (id, request_id, call_no, provider, model, status, cost_micros, cost_is_estimate,"
        " started_at) VALUES (:id, :request_id, 1, :provider, :model, 'running', :cost, 1, :now)"),
        {"id": str(uuid.uuid4()), "request_id": request_id, "provider": settings.image_provider,
         "model": plan.run.model, "cost": reservation, "now": now})


def _product(conn: Connection, variant_ref: str, run_label: str) -> tuple[_Scope, Row, str | None, SceneSubject]:
    """Rule 2: the scope in the variant's current cycle, the run, and the variant's arm and subject. Both come from
    the run_products snapshot only, never from the CSV (D-PV-005; `apply` runs without it)."""
    run = conn.execute(text("SELECT * FROM runs WHERE label = :label"), {"label": run_label}).first()
    if run is None:
        raise Refused(422, "unknown_run")
    product = conn.execute(text(
        "SELECT arm, name, variant FROM run_products WHERE run_label = :run_label AND variant_ref = :ref"),
        {"run_label": run_label, "ref": variant_ref}).first()
    if product is None:
        raise Refused(422, "variant_not_in_run")
    cycle_no = conn.execute(text(  # no row = cycle 1
        "SELECT COALESCE((SELECT cycle_no FROM variant_cycles WHERE variant_ref = :ref), 1)"),
        {"ref": variant_ref}).scalar_one()
    return (_Scope(variant_ref, cycle_no, run_label), run, product.arm,
            SceneSubject(name=product.name, variant=product.variant))


def _row(conn: Connection, table: str, row_id: str) -> Row:
    row = conn.execute(text(f"SELECT * FROM {table} WHERE id = :id"), {"id": row_id}).first()
    if row is None:
        raise Refused(422, "unknown_target")
    return row


def _short_edges(conn: Connection, shas: list[str]) -> dict[str, int]:
    edges = dict(conn.execute(
        text("SELECT sha256, MIN(width, height) FROM assets WHERE sha256 IN :shas").bindparams(
            bindparam("shas", expanding=True)), {"shas": shas}).all())
    if missing := [sha for sha in shas if sha not in edges]:
        raise Refused(422, "unknown_asset", {"assets": missing})
    return edges


def spent_micros(conn: Connection, settings: Settings) -> int:
    """Micro-USD on the ledger since SPEND_CAP_SINCE: what the cap is checked against."""
    # ISO text comparison: utc_now() text order is time order, and the date is a prefix of its first instant.
    return conn.execute(text("SELECT (SELECT COALESCE(SUM(cost_micros), 0) FROM provider_calls WHERE started_at >= :since)"
                             " + (SELECT COALESCE(SUM(cost_micros), 0) FROM poster_calls WHERE created_at >= :since)"),
                        {"since": settings.spend_cap_since.isoformat()}).scalar_one()
