"""Review, cutout decisions, cycles, abandon and reuse (T-PV-008): D-PV-004, D-PV-005, D-PV-006 step 2, D-PV-007.
Rows are seeded with test_admission's helpers; requests go through the real admission path, and one candidate
through the real execution path with the stub."""
import pytest
from sqlalchemy import text

from affiche.db import write_tx
from affiche.visuals import gateway
from affiche.visuals.prompts import build_scene_prompt
from affiche.visuals.review import (
    abandon, approve, confirm_cutout, new_cycle, next_status, reject, reject_cutout, reusable,
)
from test_admission import (  # noqa: F401  (settings: fixture)
    NEON, SUBJECT, _background, _candidate, _cutout, _generated, _request, _revise, _scene, _seed, _sql, _stored,
    refused, settings,
)
from test_config import env  # noqa: F401  (fixture)
from test_db import engine  # noqa: F401  (fixture: a migrated engine on tmp_path)
from test_execution import Recorder, _admit_scene, _execute, seeded  # noqa: F401  (seeded: fixture)

TREATMENTS = ["scene", "photo_preserved"]
OTHER = {"scene": "photo_preserved", "photo_preserved": "scene"}


def _row(engine, table, row_id):
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT * FROM {table} WHERE id = :id"), {"id": row_id}).one()


def _count(engine, table):
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()


def _pending(engine, treatment, candidate_id="c1"):
    """A pending candidate of the treatment in scope (V1, r1, cycle 1); a photo_preserved one on cutout K1."""
    with write_tx(engine) as conn:
        _seed(conn)
        _cutout(conn, "K1")
        _generated(conn, candidate_id, status="pending_review",
                   cutout="K1" if treatment == "photo_preserved" else None)


def _abandon(engine, treatment="scene", **scope):
    return abandon(engine, **{"variant_ref": "V1", "run_label": "r1", "cycle_no": 1, "treatment": treatment} | scope)


# --- The state machine ----------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("current", "action", "expected"), [
    ("pending_review", "approve", "approved"), ("pending_review", "reject", "rejected"),
    ("approved", "approve", None), ("approved", "reject", None),
    ("rejected", "approve", None), ("rejected", "reject", None),
])
def test_only_pending_review_moves(current, action, expected):
    if expected is None:
        with refused(409, "invalid_transition"):
            next_status(current, action)
    else:
        assert next_status(current, action) == expected


# --- Approve --------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("treatment", TREATMENTS)
def test_approval_needs_the_framing_tick_and_is_final(engine, treatment):
    _pending(engine, treatment)
    before = _row(engine, "candidates", "c1")
    with refused(422, "framing_not_checked"):
        approve(engine, "c1", framing_checked=False)
    assert _row(engine, "candidates", "c1") == before
    assert approve(engine, "c1", framing_checked=True) == "applied"
    approved = _row(engine, "candidates", "c1")
    assert (approved.status, approved.framing_checked, approved.treatment) == ("approved", 1, treatment)
    assert approved.reviewed_at is not None
    assert approve(engine, "c1", framing_checked=True) == "already_applied"
    assert _row(engine, "candidates", "c1") == approved  # a replay writes nothing
    with refused(422, "framing_not_checked"):  # checked first, even on a replay
        approve(engine, "c1", framing_checked=False)
    with refused(409, "invalid_transition"):
        reject(engine, "c1", reasons=["cameras"], note=None)


# --- Reject ---------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("treatment", TREATMENTS)
def test_rejection_needs_a_known_reason_or_a_note_and_the_note_is_screened(engine, treatment):
    _pending(engine, treatment)
    before = _row(engine, "candidates", "c1")
    refusals = [
        ((422, "reason_or_note_required", None), {"reasons": [], "note": None}),
        ((422, "reason_or_note_required", None), {"reasons": [], "note": "  \t "}),
        ((422, "unknown_reason", {"reasons": ["zoom"]}), {"reasons": ["cameras", "zoom", "zoom"], "note": None}),
        ((422, "commercial_terms", {"field": "note", "matches": ["remise", "%"]}),
         {"reasons": ["cameras"], "note": "remise -20 %"}),
    ]
    for (status, code, details), arguments in refusals:
        with refused(status, code, details):
            reject(engine, "c1", **arguments)
    assert _row(engine, "candidates", "c1") == before
    assert reject(engine, "c1", reasons=["texte", "cameras", "texte", "coloris"],
                  note="  les caméras sont fausses ") == "applied"
    rejected = _row(engine, "candidates", "c1")
    assert (rejected.status, rejected.rejection_reasons_json, rejected.rejection_note) == (
        "rejected", '["coloris", "cameras", "texte"]', "les caméras sont fausses")
    assert rejected.reviewed_at is not None and rejected.framing_checked is None
    assert reject(engine, "c1", reasons=["cameras", "coloris", "texte"],
                  note="les caméras sont fausses") == "already_applied"
    assert _row(engine, "candidates", "c1") == rejected
    for other in ({"reasons": ["logo"], "note": "les caméras sont fausses"},
                  {"reasons": ["cameras", "coloris", "texte"], "note": "autre chose"}):
        with refused(409, "invalid_transition"):
            reject(engine, "c1", **other)
    with refused(409, "invalid_transition"):
        approve(engine, "c1", framing_checked=True)


def test_a_note_alone_is_enough_and_the_revision_carries_it(engine, settings):
    _pending(engine, "scene")
    assert reject(engine, "c1", reasons=(), note=" trop sombre ") == "applied"
    row = _row(engine, "candidates", "c1")
    assert (row.rejection_reasons_json, row.rejection_note) == ("[]", "trop sombre")
    _revise(engine, settings, "c1")
    request, stored, _ = _stored(engine, "rev")
    assert stored["prompt"] == build_scene_prompt(SUBJECT, NEON, [], "trop sombre")
    assert request.corrections_applied == 1


@pytest.mark.parametrize("first", ["approve", "reject"])
def test_two_devices_deciding_the_same_candidate_the_second_is_refused(engine, first):
    _pending(engine, "scene")
    decisions = {"approve": lambda: approve(engine, "c1", framing_checked=True),
                 "reject": lambda: reject(engine, "c1", reasons=["logo"], note=None)}
    assert decisions[first]() == "applied"
    with refused(409, "invalid_transition"):
        decisions["reject" if first == "approve" else "approve"]()
    assert _row(engine, "candidates", "c1").status == next_status("pending_review", first)


# --- Cutout decisions -----------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("decide", "other", "status"), [(confirm_cutout, reject_cutout, "confirmed"),
                                                         (reject_cutout, confirm_cutout, "rejected")])
def test_a_cutout_decision_is_conditional_and_replayable(engine, decide, other, status):
    with write_tx(engine) as conn:
        _seed(conn)
        _cutout(conn, "K1", status="proposed")
    assert decide(engine, "K1") == "applied"
    decided = _row(engine, "cutouts", "K1")
    assert decided.status == status and decided.decided_at is not None
    assert decide(engine, "K1") == "already_applied"
    assert _row(engine, "cutouts", "K1") == decided
    with refused(409, "invalid_transition"):
        other(engine, "K1")
    with refused(409, "invalid_transition"):  # K-LEDGER, seeded failed
        decide(engine, "K-LEDGER")


def test_an_unknown_target_is_refused(engine):
    for decide in (lambda: approve(engine, "nope", framing_checked=True),
                   lambda: reject(engine, "nope", reasons=["logo"], note=None),
                   lambda: confirm_cutout(engine, "nope"), lambda: reject_cutout(engine, "nope")):
        with refused(422, "unknown_target"):
            decide()


# --- Cycles ---------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("approved", ["c3", "p1", "x1"], ids=["scene", "photo_preserved", "other-run"])
def test_a_cycle_needs_an_approval_and_gives_a_fresh_allowance(engine, settings, approved):
    with write_tx(engine) as conn:
        _seed(conn)
        conn.execute(text("INSERT INTO runs VALUES ('r2', 'gpt-image-2.5-flare', 'high', '1088x1920', 3, 'on', 't0')"))
        _cutout(conn, "K1")
        _generated(conn, "c1", status="rejected")
        _generated(conn, "c2", status="rejected", attempt=2, parent="c1")
        _generated(conn, "c3", status="pending_review", attempt=3, parent="c2")  # all 3 scene slots used
        _generated(conn, "p1", status="pending_review", cutout="K1")
        _request(conn, "req-x1", run="r2")
        _candidate(conn, "x1", "req-x1", status="pending_review", attempt=1)
        conn.execute(text("UPDATE candidates SET run_label = 'r2' WHERE id = 'x1'"))
    with refused(409, "cycle_not_approved"):
        new_cycle(engine, "V1")
    approve(engine, approved, framing_checked=True)
    assert new_cycle(engine, "V1") == 2
    with refused(409, "cycle_not_approved"):  # cycle 2 has no approval yet: a replay refuses too
        new_cycle(engine, "V1")
    assert _scene(engine, settings).attempt_no == 1
    assert _stored(engine, "s1")[0].cycle_no == 2


def test_a_really_executed_candidate_once_approved_is_reusable_and_opens_a_new_cycle(engine, settings, seeded):
    _admit_scene(engine, settings, seeded.photos)
    assert _execute(engine, settings, Recorder(), "s1") == "succeeded"
    candidate_id = _stored(engine, "s1")[0].candidate_id
    assert reusable(engine, "V1") == []
    assert approve(engine, candidate_id, framing_checked=True) == "applied"
    row = _row(engine, "candidates", candidate_id)
    assert reusable(engine, "V1") == [
        {"id": candidate_id, "treatment": "scene", "image_asset": row.image_asset, "cutout_id": None,
         "product_box_json": None, "cycle_no": 1, "run_label": "r1", "attempt_no": 1, "reviewed_at": row.reviewed_at}]
    assert new_cycle(engine, "V1") == 2
    assert _admit_scene(engine, settings, seeded.photos, "s2").attempt_no == 1


# --- Abandon --------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("treatment", TREATMENTS)
def test_abandon_writes_the_scope_once_and_blocks_new_requests_of_that_treatment(engine, settings, treatment):
    with write_tx(engine) as conn:
        _seed(conn)
        _cutout(conn, "K1")
    assert _abandon(engine, treatment, note="le produit ne convient pas") == "applied"
    assert _abandon(engine, treatment, note="autre") == "already_applied"
    with engine.connect() as conn:
        (row,) = conn.execute(text("SELECT * FROM abandonments")).all()
    assert (row.variant_ref, row.run_label, row.cycle_no, row.treatment, row.note) == (
        "V1", "r1", 1, treatment, "le produit ne convient pas")
    assert row.created_at is not None
    requests = {"scene": lambda: _scene(engine, settings),
                "photo_preserved": lambda: _background(engine, settings, "K1")}
    with refused(409, "abandoned"):
        requests[treatment]()
    assert not requests[OTHER[treatment]]().existing


def test_abandon_refuses_an_unknown_run_or_variant_and_a_cycle_that_is_not_one(engine):
    with write_tx(engine) as conn:
        _seed(conn)
    for scope, code in [({"run_label": "r9"}, (422, "unknown_run")),
                        ({"variant_ref": "V3"}, (422, "variant_not_in_run")),
                        ({"cycle_no": 2}, (409, "wrong_scope")), ({"cycle_no": 0}, (409, "wrong_scope"))]:
        with refused(*code):
            _abandon(engine, **scope)
    assert _count(engine, "abandonments") == 0


@pytest.mark.parametrize("purpose", ["scene", "background"])
def test_abandon_is_refused_while_any_request_of_the_scope_runs(engine, settings, purpose):
    with write_tx(engine) as conn:
        _seed(conn)
        _cutout(conn, "K1")
    admitted = _scene(engine, settings) if purpose == "scene" else _background(engine, settings, "K1")
    for treatment in TREATMENTS:  # whatever the running request's purpose
        with refused(409, "request_running"):
            _abandon(engine, treatment)
    _sql(engine, "UPDATE generation_requests SET status = 'interrupted' WHERE id = :id", id=admitted.request_id)
    for treatment in TREATMENTS:
        assert _abandon(engine, treatment) == "applied"


def test_a_request_running_in_another_scope_does_not_block_abandon(engine):
    with write_tx(engine) as conn:
        _seed(conn)
        conn.execute(text("INSERT INTO runs VALUES ('r2', 'gpt-image-2.5-flare', 'high', '1088x1920', 3, 'on', 't0')"))
        conn.execute(text("INSERT INTO variant_cycles VALUES ('V1', 2)"))
        _request(conn, "other-run", status="running", run="r2")
        _request(conn, "other-cycle", status="running", cycle=2)
        _request(conn, "other-variant", status="running", variant="V2")
    for treatment in TREATMENTS:  # scope (V1, r1, cycle 1)
        assert _abandon(engine, treatment) == "applied"


@pytest.mark.parametrize("treatment", TREATMENTS)
def test_abandon_is_refused_after_an_approval_of_that_treatment(engine, treatment):
    _pending(engine, treatment)
    approve(engine, "c1", framing_checked=True)
    with refused(409, "already_approved"):
        _abandon(engine, treatment)
    assert _abandon(engine, OTHER[treatment]) == "applied"


def test_an_abandon_replayed_after_a_new_cycle_still_addresses_the_original_scope(engine, settings):
    _pending(engine, "scene")
    assert _abandon(engine) == "applied"
    approve(engine, "c1", framing_checked=True)
    assert new_cycle(engine, "V1") == 2
    assert _abandon(engine) == "already_applied"  # checked first: not already_approved
    assert _count(engine, "abandonments") == 1
    _scene(engine, settings)  # cycle 2 is not abandoned
    assert _stored(engine, "s1")[0].cycle_no == 2


# --- Reuse ----------------------------------------------------------------------------------------------------------

def test_reuse_returns_only_the_approved_candidates_of_exactly_that_variant_newest_first(engine):
    with write_tx(engine) as conn:
        _seed(conn)
        _cutout(conn, "K1")
        # One cycle each, so the seeded requests never share a scope; reuse spans the variant's cycles.
        rows = [("A1", "OPM-A15", "approved", "T2"), ("A2", "OPM-A15", "approved", "T3"),
                ("A3", "OPM-A15", "approved", "T1"), ("A4", "OPM-A15", "approved", "T3"),  # A2's time, created later
                ("P1", "OPM-A15", "pending_review", None), ("R1", "OPM-A15", "rejected", "T9"),
                ("N1", "OPM-A15-NOIR", "approved", "T9")]
        for cycle, (candidate_id, variant, status, reviewed_at) in enumerate(rows, 1):
            _generated(conn, candidate_id, status=status, cycle=cycle, cutout="K1" if candidate_id == "A2" else None)
            conn.execute(text("UPDATE candidates SET variant_ref = :variant, reviewed_at = :reviewed WHERE id = :id"),
                         {"id": candidate_id, "variant": variant, "reviewed": reviewed_at})
    assert [row["id"] for row in reusable(engine, "OPM-A15")] == ["A4", "A2", "A1", "A3"]
    assert [row["id"] for row in reusable(engine, "OPM-A15-NOIR")] == ["N1"]
    assert reusable(engine, "OPM") == [] and reusable(engine, "OPM-A15%") == []
    a2 = next(row for row in reusable(engine, "OPM-A15") if row["id"] == "A2")
    assert (a2["treatment"], a2["cutout_id"], a2["cycle_no"], a2["reviewed_at"]) == ("photo_preserved", "K1", 2, "T3")


def test_reuse_makes_no_gateway_call(engine, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("the reuse path must not reach the gateway")

    monkeypatch.setattr(gateway, "make_provider", forbidden)
    monkeypatch.setattr(gateway.OpenAIProvider, "generate", forbidden)
    monkeypatch.setattr(gateway.StubProvider, "generate", forbidden)
    _pending(engine, "scene")
    approve(engine, "c1", framing_checked=True)
    assert [row["id"] for row in reusable(engine, "V1")] == ["c1"]
    assert (_count(engine, "generation_requests"), _count(engine, "provider_calls")) == (1, 0)
