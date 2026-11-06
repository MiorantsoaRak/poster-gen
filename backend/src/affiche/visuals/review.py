"""Candidate review (D-PRODUCT-VISUALS-004), cutout decisions (D-PV-006 step 2), cycles and abandon (D-PV-005), and
the reuse query (D-PV-007). Each write runs in one BEGIN IMMEDIATE transaction. A decision replayed with the same
payload returns "already_applied", so `apply` can run the same file again; the returned strings go to its
apply-result.csv."""

import json
from collections.abc import Mapping, Sequence
from typing import Literal

from sqlalchemy import Connection, Engine, text

from affiche.db import utc_now, write_tx
from affiche.visuals.admission import Refused
from affiche.visuals.prompts import REASON_CODES, find_commercial_terms

Status = Literal["pending_review", "approved", "rejected"]
Action = Literal["approve", "reject"]
Treatment = Literal["scene", "photo_preserved"]
Outcome = Literal["applied", "already_applied"]
_TARGETS: dict[Action, Status] = {"approve": "approved", "reject": "rejected"}
_IN_SCOPE = "variant_ref = :variant_ref AND run_label = :run_label AND cycle_no = :cycle_no"
_REUSABLE = ("id, treatment, image_asset, cutout_id, product_box_json, cycle_no, run_label, attempt_no,"
             " reviewed_at")


def next_status(current: Status, action: Action) -> Status:
    """Pure, for `apply`'s whole-file validation (design line 460). Only pending_review moves; both ends are final."""
    if current != "pending_review":
        raise Refused(409, "invalid_transition")
    return _TARGETS[action]


def approve(engine: Engine, candidate_id: str, *, framing_checked: bool) -> Outcome:
    """Both treatments need the framing tick (R-002 c.4, R-004 c.2), checked before anything else."""
    if framing_checked is not True:
        raise Refused(422, "framing_not_checked")
    return _decide(engine, "candidates", candidate_id, "pending_review", "approved", "reviewed_at",
                   {"framing_checked": 1})


def reject(engine: Engine, candidate_id: str, *, reasons: Sequence[str], note: str | None) -> Outcome:
    """At least one known reason or a non-blank note; the note is sent to the model in a revision, so it is
    screened. Stored canonical (reasons deduplicated in REASON_CODES order, the note stripped), which is also what a
    replay is compared with."""
    given = set(reasons)
    if unknown := sorted(given.difference(REASON_CODES)):
        raise Refused(422, "unknown_reason", {"reasons": unknown})
    codes = [code for code in REASON_CODES if code in given]
    note = (note or "").strip() or None
    if not codes and note is None:
        raise Refused(422, "reason_or_note_required")
    if note is not None and (matches := find_commercial_terms(note)):
        raise Refused(422, "commercial_terms", {"field": "note", "matches": matches})
    return _decide(engine, "candidates", candidate_id, "pending_review", "rejected", "reviewed_at",
                   {"rejection_reasons_json": json.dumps(codes), "rejection_note": note})


def confirm_cutout(engine: Engine, cutout_id: str) -> Outcome:
    return _decide(engine, "cutouts", cutout_id, "proposed", "confirmed", "decided_at")


def reject_cutout(engine: Engine, cutout_id: str) -> Outcome:
    """No spend: a cutout costs nothing, and a rejected one can never get a background."""
    return _decide(engine, "cutouts", cutout_id, "proposed", "rejected", "decided_at")


def new_cycle(engine: Engine, variant_ref: str) -> int:
    """Starts cycle n+1 ("Nouvelle campagne", ADR-011) only once cycle n has an approved candidate (any treatment,
    any run). A replay is refused (cycle_not_approved): the new cycle has no approval yet."""
    with write_tx(engine) as conn:
        current = _current_cycle(conn, variant_ref)
        if not conn.execute(text(
                "SELECT 1 FROM candidates WHERE variant_ref = :ref AND cycle_no = :cycle AND status = 'approved'"),
                {"ref": variant_ref, "cycle": current}).first():
            raise Refused(409, "cycle_not_approved")
        conn.execute(text(
            "INSERT INTO variant_cycles (variant_ref, cycle_no) VALUES (:ref, :cycle)"
            " ON CONFLICT (variant_ref) DO UPDATE SET cycle_no = excluded.cycle_no"),
            {"ref": variant_ref, "cycle": current + 1})
        return current + 1


def abandon(engine: Engine, *, variant_ref: str, run_label: str, cycle_no: int, treatment: Treatment,
            note: str | None = None) -> Outcome:
    """The explicit "abandoned" outcome of one scope and treatment (R-008 c.2). The note stays internal: it is never
    sent to the model, so it is not screened."""
    scope = {"variant_ref": variant_ref, "run_label": run_label, "cycle_no": cycle_no}
    with write_tx(engine) as conn:
        # First, so a replay after new-cycle still addresses the original scope (D-PV-005).
        if conn.execute(text(f"SELECT 1 FROM abandonments WHERE {_IN_SCOPE} AND treatment = :treatment"),
                        {**scope, "treatment": treatment}).first():
            return "already_applied"
        if not conn.execute(text("SELECT 1 FROM runs WHERE label = :label"), {"label": run_label}).first():
            raise Refused(422, "unknown_run")
        if not conn.execute(text("SELECT 1 FROM run_products WHERE run_label = :run_label AND variant_ref = :ref"),
                            {"run_label": run_label, "ref": variant_ref}).first():
            raise Refused(422, "variant_not_in_run")
        if not 1 <= cycle_no <= _current_cycle(conn, variant_ref):
            raise Refused(409, "wrong_scope")
        # Any purpose: the design refuses while a request in the scope runs, whatever its treatment (line 357).
        if conn.execute(text(f"SELECT 1 FROM generation_requests WHERE {_IN_SCOPE} AND status = 'running'"),
                        scope).first():
            raise Refused(409, "request_running")
        if conn.execute(text(
                f"SELECT 1 FROM candidates WHERE {_IN_SCOPE} AND treatment = :treatment AND status = 'approved'"),
                {**scope, "treatment": treatment}).first():
            raise Refused(409, "already_approved")
        conn.execute(text(
            "INSERT INTO abandonments (variant_ref, run_label, cycle_no, treatment, note, created_at)"
            " VALUES (:variant_ref, :run_label, :cycle_no, :treatment, :note, :now)"),
            {**scope, "treatment": treatment, "note": note, "now": utc_now()})
    return "applied"


def reusable(engine: Engine, variant_ref: str) -> list[dict]:
    """The approved candidates of exactly this variant, newest first. A read only: a price change makes no
    generation (D-PV-007)."""
    with engine.connect() as conn:
        rows = conn.execute(text(
            f"SELECT {_REUSABLE} FROM candidates WHERE variant_ref = :ref AND status = 'approved'"
            " ORDER BY reviewed_at DESC, created_at DESC"), {"ref": variant_ref}).mappings()
        return [dict(row) for row in rows]


def _decide(engine: Engine, table: str, row_id: str, source: str, target: str, stamp: str,
            payload: Mapping[str, object] | None = None) -> Outcome:
    """The conditional source -> target UPDATE. Rowcount 0: the row is already in the target state with the same
    payload (a replay), or the transition is refused."""
    payload = dict(payload or {})
    assignments = "".join(f", {column} = :{column}" for column in payload)
    with write_tx(engine) as conn:
        updated = conn.execute(text(
            f"UPDATE {table} SET status = :target, {stamp} = :now{assignments} WHERE id = :id AND status = :source"),
            {"id": row_id, "source": source, "target": target, "now": utc_now(), **payload}).rowcount
        if updated:
            return "applied"
        row = conn.execute(text(f"SELECT * FROM {table} WHERE id = :id"), {"id": row_id}).first()
    if row is None:
        raise Refused(422, "unknown_target")
    if row.status == target and all(getattr(row, column) == value for column, value in payload.items()):
        return "already_applied"
    raise Refused(409, "invalid_transition")


def _current_cycle(conn: Connection, variant_ref: str) -> int:
    return conn.execute(text(  # no row = cycle 1
        "SELECT COALESCE((SELECT cycle_no FROM variant_cycles WHERE variant_ref = :ref), 1)"),
        {"ref": variant_ref}).scalar_one()
