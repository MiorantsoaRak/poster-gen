"""Request admission (T-PV-006): D-PV-003 rules 1-7 and the D-PV-005 admission tests. Rows are seeded with SQL, and
candidates are inserted directly: creating them is T-PV-007's job."""
import hashlib
import itertools
import json
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import exc, text

from affiche.config import load_settings
from affiche.db import write_tx
from affiche.visuals.admission import Admitted, Refused, request_background, request_revision, request_scene, reserve
from affiche.visuals.prompts import Direction, SceneSubject, build_background_prompt, build_scene_prompt
from test_config import TODAY, env  # noqa: F401  (fixture: a clean, valid environment, inherited by the workers)
from test_db import _stdout_lines, engine  # noqa: F401  (fixture: a migrated engine on tmp_path)
from test_store_lock import PIPES, _reap

WORKER = Path(__file__).with_name("admission_worker.py")
P1, P2, P3, P4, LOW, EDGE, FOREIGN, STYLE, IMAGE = (f"{n:064x}" for n in range(1, 10))
MISSING = "f" * 64  # a photo of the variant with no assets row
SIZES = {P1: (1200, 1600), P2: (1600, 1200), P3: (1200, 1600), P4: (1200, 1600), LOW: (799, 1600), EDGE: (800, 800),
         FOREIGN: (1200, 1600), STYLE: (1024, 1024), IMAGE: (1088, 1920)}
SUBJECT = SceneSubject(name="Samsung Galaxy A15", variant="Noir 128 Go")  # V1's subject in run_products
PHOTOS = {"V1": (P1, P2, P3, P4, LOW, EDGE, MISSING), "V2": (LOW,), "V3": (P1,)}  # V3 is not in the run
NEON = Direction(mood="neon")
STYLED = Direction(mood="minimal", style_ref=STYLE)
_clock = itertools.count(1)


@pytest.fixture
def settings(env, tmp_path):
    return _settings(env, DATA_DIR=str(tmp_path))


def _settings(env, **values):
    for name, value in values.items():
        env.setenv(name, value)
    return load_settings(env_file=None)


@contextmanager
def refused(status, code, details=None):
    with pytest.raises(Refused) as caught:
        yield
    assert (caught.value.status, caught.value.code, caught.value.details) == (status, code, details)


# --- Seeding --------------------------------------------------------------------------------------------------------

def _stamp():
    """A distinct time of today, increasing with each call."""
    return f"{TODAY}T00:00:00.{next(_clock):06d}+00:00"


def _seed(conn, *, model="gpt-image-2", attempt_limit=3, corrections_mode="on", arm=None):
    conn.execute(text("INSERT INTO runs VALUES ('r1', :model, 'high', '1088x1920', :limit, :mode, 't0')"),
                 {"model": model, "limit": attempt_limit, "mode": corrections_mode})
    conn.execute(text("INSERT INTO run_products (run_label, variant_ref, arm, fixture_row_sha256, name, variant)"
                      " VALUES ('r1', :ref, :arm, 'row-sha', :name, :variant)"),
                 [{"ref": "V1", "arm": arm, "name": SUBJECT.name, "variant": SUBJECT.variant},
                  {"ref": "V2", "arm": arm, "name": "Redmi 13", "variant": "Bleu 256 Go"}])
    conn.execute(text("INSERT INTO assets VALUES (:sha, 'image/png', :width, :height, 1, 't0', 'original')"),
                 [{"sha": sha, "width": width, "height": height} for sha, (width, height) in SIZES.items()])
    _cutout(conn, "K-LEDGER", variant="LEDGER", status="failed")  # for the ledger's background requests


def _cutout(conn, cutout_id, *, status="confirmed", direction=STYLED, source=P1, cycle=1, low_res=0, variant="V1"):
    conn.execute(text(
        "INSERT INTO cutouts (id, variant_ref, run_label, direction_json, source_asset, status, low_res_warning,"
        " rembg_model, created_at, cycle_no) VALUES (:id, :variant, 'r1', :direction, :source, :status, :low_res,"
        " 'birefnet-general-lite', 't0', :cycle)"),
        {"id": cutout_id, "variant": variant, "direction": direction.model_dump_json(), "source": source,
         "status": status, "low_res": low_res, "cycle": cycle})


def _request(conn, request_id, *, status="succeeded", parent=None, cutout=None, variant="V1", cycle=1, run="r1"):
    conn.execute(text(
        "INSERT INTO generation_requests (id, payload_hash, purpose, variant_ref, cycle_no, run_label, parent_id,"
        " cutout_id, request_json, corrections_applied, owner, status, created_at) VALUES (:id, 'h', :purpose,"
        " :variant, :cycle, :run, :parent, :cutout, '{}', 0, 'cli', :status, :now)"),
        {"id": request_id, "purpose": "scene" if cutout is None else "background", "variant": variant,
         "cycle": cycle, "run": run, "parent": parent, "cutout": cutout, "status": status, "now": _stamp()})


def _candidate(conn, candidate_id, request_id, *, status, attempt, cutout=None, reasons=("cameras",), note=None,
               cycle=1, created_at=None):
    # The candidate's own subject columns differ from run_products on purpose: admission must read run_products.
    conn.execute(text(
        "INSERT INTO candidates (id, variant_ref, cycle_no, subject_name, subject_variant, treatment, status,"
        " request_id, attempt_no, direction_json, source_assets_json, prompt, corrections_applied, provider, model,"
        " quality, size, run_label, image_asset, cutout_id, low_res_warning, rejection_reasons_json, rejection_note,"
        " created_at) VALUES (:id, 'V1', :cycle, 'Ancien nom', 'Ancienne variante', :treatment, :status, :request_id,"
        " :attempt, :direction, :sources, 'p', 0, 'stub', 'gpt-image-2', 'high', '1088x1920', 'r1', :image, :cutout,"
        " 0, :reasons, :note, :now)"),
        {"id": candidate_id, "cycle": cycle, "treatment": "scene" if cutout is None else "photo_preserved",
         "status": status, "request_id": request_id, "attempt": attempt, "direction": NEON.model_dump_json(),
         "sources": json.dumps([P1, P2]), "image": IMAGE, "cutout": cutout,
         "reasons": json.dumps(list(reasons)) if status == "rejected" else None, "note": note,
         "now": created_at or _stamp()})


def _generated(conn, candidate_id, *, status, attempt=1, parent=None, cutout=None, reasons=("cameras",), note=None,
               cycle=1, created_at=None):
    """A succeeded request and its candidate."""
    _request(conn, f"req-{candidate_id}", parent=parent, cutout=cutout, cycle=cycle)
    _candidate(conn, candidate_id, f"req-{candidate_id}", status=status, attempt=attempt, cutout=cutout,
               reasons=reasons, note=note, cycle=cycle, created_at=created_at)


def _ledger_call(conn, cost, *, estimate=1, model="gpt-image-2", purpose="scene", started_at=None):
    """A finished call on a failed request outside every tested scope."""
    request_id = f"ledger-{next(_clock)}"
    _request(conn, request_id, status="failed", variant="LEDGER",
             cutout="K-LEDGER" if purpose == "background" else None)
    conn.execute(text(
        "INSERT INTO provider_calls (id, request_id, call_no, provider, model, status, cost_micros, cost_is_estimate,"
        " started_at) VALUES (:id, :id, 1, 'openai', :model, 'failed', :cost, :estimate, :started_at)"),
        {"id": request_id, "model": model, "cost": cost, "estimate": estimate, "started_at": started_at or _stamp()})


def _sql(engine, statement, **params):
    with write_tx(engine) as conn:
        conn.execute(text(statement), params)


def _reject(engine, candidate_id, reasons='["cameras"]', note=None):
    _sql(engine, "UPDATE candidates SET status = 'rejected', rejection_reasons_json = :reasons,"
         " rejection_note = :note WHERE id = :id", id=candidate_id, reasons=reasons, note=note)


def _succeed(engine, request_id, candidate_id, *, status, cutout=None):
    """What T-PV-007 will do: the request succeeds with a candidate numbered from the request."""
    with write_tx(engine) as conn:
        request_json = conn.execute(text(
            "UPDATE generation_requests SET status = 'succeeded' WHERE id = :id RETURNING request_json"),
            {"id": request_id}).scalar_one()
        _candidate(conn, candidate_id, request_id, status=status, attempt=json.loads(request_json)["attempt_no"],
                   cutout=cutout)


# --- Reading back ---------------------------------------------------------------------------------------------------

def _counts(engine):
    with engine.connect() as conn:
        return tuple(conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
                     for table in ("generation_requests", "provider_calls"))


def _stored(engine, request_id):
    with engine.connect() as conn:
        request = conn.execute(text("SELECT * FROM generation_requests WHERE id = :id"), {"id": request_id}).one()
        call = conn.execute(text("SELECT * FROM provider_calls WHERE request_id = :id"), {"id": request_id}).one()
    return request, json.loads(request.request_json), call


def _scene(engine, settings, request_id="s1", **overrides):
    arguments = {"id": request_id, "variant_ref": "V1", "run_label": "r1", "owner": "cli", "direction": NEON}
    arguments |= overrides
    return request_scene(engine, settings, variant_photos=PHOTOS[arguments["variant_ref"]], **arguments)


def _revise(engine, settings, parent_id, request_id="rev"):
    return request_revision(engine, settings, id=request_id, parent_id=parent_id, owner="cli")


def _background(engine, settings, cutout_id, request_id="bg"):
    return request_background(engine, settings, id=request_id, cutout_id=cutout_id, owner="cli")


# --- Admitted requests ----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["scene", "background", "revision"])
def test_commercial_descriptions_are_refused_before_reserving_spend(engine, settings, kind):
    direction = Direction(description="Prix 899000 Ar, garantie 6 mois")
    with write_tx(engine) as conn:
        _seed(conn)
        if kind == "background":
            _cutout(conn, "K1", direction=direction)
        elif kind == "revision":
            _generated(conn, "C1", status="rejected")
            conn.execute(text("UPDATE candidates SET direction_json = :direction WHERE id = 'C1'"),
                         {"direction": direction.model_dump_json()})
    before = _counts(engine)
    with refused(422, "commercial_terms",
                 {"field": "description", "matches": ["Prix", "899000", "Ar", "garantie"]}):
        if kind == "scene":
            _scene(engine, settings, direction=direction)
        elif kind == "background":
            _background(engine, settings, "K1")
        else:
            _revise(engine, settings, "C1")
    assert _counts(engine) == before


def test_an_initial_scene_is_inserted_running_with_call_1_reserved(engine, settings):
    with write_tx(engine) as conn:
        _seed(conn)
    assert _scene(engine, settings) == Admitted("s1", attempt_no=1, existing=False, reservation=400_000,
                                                spent=400_000, cap=20_000_000)
    request, stored, call = _stored(engine, "s1")
    assert (request.purpose, request.variant_ref, request.cycle_no, request.run_label, request.parent_id,
            request.cutout_id, request.owner, request.status, request.corrections_applied) == (
        "scene", "V1", 1, "r1", None, None, "cli", "running", 0)
    payload = {"purpose": "scene", "variant_ref": "V1", "run_label": "r1", "photo_assets": None,
               "direction": NEON.model_dump(mode="json"), "acknowledged_warnings": []}
    assert request.payload_hash == hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    assert stored == {"prompt": build_scene_prompt(SUBJECT, NEON, None, None), "images": [P1, P2, P3],
                      "model": "gpt-image-2", "quality": "high", "size": "1088x1920",
                      "subject": {"name": SUBJECT.name, "variant": SUBJECT.variant},
                      "direction": NEON.model_dump(mode="json"), "attempt_no": 1, "treatment": "scene",
                      "source_assets": [P1, P2, P3], "low_res_warning": 0}
    assert (call.call_no, call.provider, call.model, call.status, call.cost_micros, call.cost_is_estimate,
            call.started_at) == (1, "stub", "gpt-image-2", "running", 400_000, 1, request.created_at)


def test_chosen_photos_then_the_style_reference_are_the_images(engine, settings):
    with write_tx(engine) as conn:
        _seed(conn)
    _scene(engine, settings, photo_assets=(P4, P2), direction=STYLED)
    _, stored, _ = _stored(engine, "s1")
    assert (stored["images"], stored["source_assets"]) == ([P4, P2, STYLE], [P4, P2])
    assert stored["prompt"] == build_scene_prompt(SUBJECT, STYLED, None, None)


def test_an_initial_background_takes_the_cutouts_direction_and_only_its_style_reference(engine, settings):
    with write_tx(engine) as conn:
        _seed(conn)
        _cutout(conn, "K1", source=P2, low_res=1)
    assert _background(engine, settings, "K1") == Admitted("bg", attempt_no=1, existing=False, reservation=300_000,
                                                           spent=300_000, cap=20_000_000)
    request, stored, call = _stored(engine, "bg")
    assert (request.purpose, request.cutout_id, request.parent_id, request.corrections_applied) == (
        "background", "K1", None, 0)
    assert stored == {"prompt": build_background_prompt(STYLED, None, None), "images": [STYLE],
                      "model": "gpt-image-2", "quality": "high", "size": "1088x1920",
                      "subject": {"name": SUBJECT.name, "variant": SUBJECT.variant},
                      "direction": STYLED.model_dump(mode="json"), "attempt_no": 1, "treatment": "photo_preserved",
                      "source_assets": [P2], "low_res_warning": 1}
    assert call.cost_micros == 300_000


# --- Rule 1: idempotency --------------------------------------------------------------------------------------------

def test_the_same_id_returns_the_request_only_for_the_same_payload(engine, settings):
    with write_tx(engine) as conn:
        _seed(conn)
    warnings = ["low_resolution", "x"]
    first = _scene(engine, settings, acknowledged_warnings=warnings)
    # The warnings are a set: order and repeats do not change the payload.
    assert _scene(engine, settings, acknowledged_warnings=["x", "low_resolution", "x"]) == replace(
        first, existing=True, reservation=0)
    _sql(engine, "INSERT INTO abandonments VALUES ('V1', 'r1', 1, 'scene', NULL, 't0')")
    assert _scene(engine, settings, acknowledged_warnings=warnings).existing  # rule 1 comes first
    other_payloads = [  # each changes exactly one field of the first payload
        lambda: _scene(engine, settings, acknowledged_warnings=warnings, direction=STYLED),
        # The caller's fields, not the derived ones: the default photos, given explicitly, are another payload.
        lambda: _scene(engine, settings, acknowledged_warnings=warnings, photo_assets=[P1, P2, P3]),
        lambda: _scene(engine, settings, acknowledged_warnings=["x"]),
        lambda: _revise(engine, settings, "no-such-candidate", "s1"),
        lambda: _background(engine, settings, "no-such-cutout", "s1"),
    ]
    for other_payload in other_payloads:
        with refused(409, "request_id_reused"):
            other_payload()
    assert _counts(engine) == (1, 1)


# --- Rule 3: scope, initial request, allowance ----------------------------------------------------------------------

def test_the_allowance_counts_the_scopes_running_and_succeeded_scene_requests(engine, settings):
    with write_tx(engine) as conn:
        _seed(conn, attempt_limit=2)  # the run's limit, not ATTEMPT_LIMIT (3)
        conn.execute(text("INSERT INTO runs VALUES ('r2', 'gpt-image-2.5-flare', 'high', '1088x1920', 3, 'on', 't0')"))
        _cutout(conn, "K1")
        _generated(conn, "c1", status="rejected")
        _generated(conn, "p1", status="rejected", cutout="K1")  # a background: never a scene slot
        _request(conn, "other-variant", variant="V2")
        _request(conn, "other-run", run="r2")
        _request(conn, "other-cycle", cycle=2)
    assert _revise(engine, settings, "c1", "rev1").attempt_no == 2
    with refused(409, "attempt_limit_reached", {"fallback": "photo_preserved"}):  # rev1 is running: it counts
        _revise(engine, settings, "c1", "rev2")
    for status in ("failed", "interrupted"):  # they do not count
        _sql(engine, "UPDATE generation_requests SET status = :status WHERE status = 'running'", status=status)
        assert _revise(engine, settings, "c1", f"rev-after-{status}").attempt_no == 2
    _succeed(engine, "rev-after-interrupted", "c2", status="rejected")
    with refused(409, "attempt_limit_reached", {"fallback": "photo_preserved"}):  # succeeded counts
        _revise(engine, settings, "c2", "rev3")


def test_two_processes_revising_at_used_2_admit_exactly_one(engine, settings):
    with write_tx(engine) as conn:
        _seed(conn)
        _generated(conn, "c1", status="rejected")
        _generated(conn, "c2", status="rejected", attempt=2, parent="c1")  # used = 2 of 3
    engine.dispose()
    commands = [[sys.executable, str(WORKER), request_id, "c2"] for request_id in ("w1", "w2")]
    with subprocess.Popen(commands[0], **PIPES) as first, subprocess.Popen(commands[1], **PIPES) as second:
        workers = [(first, _stdout_lines(first)), (second, _stdout_lines(second))]
        try:
            assert [lines.get(timeout=30) for _, lines in workers] == ["ready", "ready"]
            for proc, _ in workers:
                proc.stdin.write("go\n")
            for proc, _ in workers:  # released together: one waits on the other's BEGIN IMMEDIATE
                proc.stdin.flush()
            results = sorted(lines.get(timeout=30) for _, lines in workers)
            assert [proc.wait(timeout=10) for proc, _ in workers] == [0, 0]
        finally:
            for proc, lines in workers:
                _reap(proc, lines)
    # The loser sees the winner's committed request at the allowance, which runs before the revision rules.
    assert results == ["admitted 3", "refused attempt_limit_reached"]
    assert _counts(engine) == (3, 1)  # the 2 seeded requests and exactly one new one, with its call
    with engine.connect() as conn:
        assert conn.execute(text("SELECT status FROM generation_requests WHERE parent_id = 'c2'")).all() == [
            ("running",)]


def test_a_second_initial_scene_is_refused_by_the_state_of_the_chain(engine, settings):
    with write_tx(engine) as conn:
        _seed(conn)
    _scene(engine, settings, "s1")
    with refused(409, "review_pending"):  # its request is running
        _scene(engine, settings, "s2")
    _succeed(engine, "s1", "c1", status="pending_review")
    with refused(409, "review_pending"):  # its candidate is pending
        _scene(engine, settings, "s3")
    _reject(engine, "c1")
    with refused(409, "use_revision"):
        _scene(engine, settings, "s4")
    _revise(engine, settings, "c1")
    with refused(409, "review_pending"):  # a revision is running
        _scene(engine, settings, "s5")
    assert _counts(engine) == (2, 2)


def test_a_second_initial_background_is_refused_and_after_a_rejection_it_is_a_linked_revision(engine, settings):
    with write_tx(engine) as conn:
        _seed(conn)
        _cutout(conn, "K1")
    _background(engine, settings, "K1", "b1")
    with refused(409, "review_pending"):  # its request is running
        _background(engine, settings, "K1", "b2")
    _succeed(engine, "b1", "p1", status="pending_review", cutout="K1")
    with refused(409, "review_pending"):  # the latest fallback candidate is pending
        _background(engine, settings, "K1", "b3")
    _reject(engine, "p1")
    # D-PV-003 rule 5: with a photo_preserved candidate in the scope, a background is a revision of the latest one,
    # so use_revision cannot arise for this purpose.
    assert _background(engine, settings, "K1", "b4").attempt_no == 2
    assert _stored(engine, "b4")[0].parent_id == "p1"


def test_a_fallback_revision_does_not_use_a_scene_slot(engine, settings):
    with write_tx(engine) as conn:
        _seed(conn)
        _cutout(conn, "K1")
        _generated(conn, "c1", status="rejected")
        _generated(conn, "c2", status="rejected", attempt=2, parent="c1")  # 2 of 3 scene slots used
        _generated(conn, "p1", status="rejected", cutout="K1")
    assert _revise(engine, settings, "p1", "bg-rev").attempt_no == 2
    request, stored, _ = _stored(engine, "bg-rev")
    assert (request.purpose, request.parent_id, request.cutout_id, stored["treatment"], stored["images"]) == (
        "background", "p1", "K1", "photo_preserved", [STYLE])
    assert _revise(engine, settings, "c2", "scene-rev").attempt_no == 3  # the last scene slot is still free
    _succeed(engine, "bg-rev", "p2", status="rejected", cutout="K1")
    assert _revise(engine, settings, "p2", "bg-rev-2").attempt_no == 3  # all scene slots used: backgrounds go on
    _succeed(engine, "bg-rev-2", "p3", status="rejected", cutout="K1")
    assert _revise(engine, settings, "p3", "bg-rev-3").attempt_no == 4  # the run's limit (3) is for scenes only


def test_a_background_on_a_second_cutout_is_a_linked_revision_of_the_latest_fallback(engine, settings):
    with write_tx(engine) as conn:
        _seed(conn)
        _cutout(conn, "K1", direction=NEON)
        _cutout(conn, "K2", direction=STYLED, source=P2)
        # The latest is p2 by attempt number, though the clock stepped back between the two candidates.
        _generated(conn, "p1", status="rejected", cutout="K1", created_at=f"{TODAY}T12:00:00.000000+00:00")
        _generated(conn, "p2", status="pending_review", attempt=2, parent="p1", cutout="K1",
                   created_at=f"{TODAY}T11:00:00.000000+00:00")
    with refused(409, "review_pending"):
        _background(engine, settings, "K2", "b1")
    _reject(engine, "p2", reasons='["integration"]', note="trop sombre")
    assert _background(engine, settings, "K2", "b2").attempt_no == 3
    request, stored, _ = _stored(engine, "b2")
    assert (request.parent_id, request.cutout_id, request.corrections_applied) == ("p2", "K2", 1)
    assert stored["prompt"] == build_background_prompt(STYLED, ["integration"], "trop sombre")
    assert (stored["images"], stored["source_assets"]) == ([STYLE], [P2])


def test_a_cutout_or_a_candidate_of_an_earlier_cycle_is_refused(engine, settings):
    with write_tx(engine) as conn:
        _seed(conn)
        _cutout(conn, "K-old")
        _cutout(conn, "K-new", cycle=2)
        _generated(conn, "c-old", status="rejected")
        conn.execute(text("INSERT INTO variant_cycles VALUES ('V1', 2)"))
    with refused(409, "wrong_scope"):
        _background(engine, settings, "K-old")
    with refused(409, "wrong_scope"):
        _revise(engine, settings, "c-old")
    assert _counts(engine) == (1, 0)
    _background(engine, settings, "K-new")
    _scene(engine, settings)
    assert [_stored(engine, request_id)[0].cycle_no for request_id in ("bg", "s1")] == [2, 2]


def test_a_stale_target_is_refused_as_such_when_the_current_scope_is_full_or_abandoned(engine, settings):
    with write_tx(engine) as conn:
        _seed(conn)
        _cutout(conn, "K-old")
        _generated(conn, "c-old", status="rejected")
        conn.execute(text("INSERT INTO variant_cycles VALUES ('V1', 2)"))
        _generated(conn, "c2-1", status="rejected", cycle=2)
        _generated(conn, "c2-2", status="rejected", attempt=2, parent="c2-1", cycle=2)
        _generated(conn, "c2-3", status="rejected", attempt=3, parent="c2-2", cycle=2)  # cycle 2 is full
    with refused(409, "wrong_scope"):  # not attempt_limit_reached
        _revise(engine, settings, "c-old")
    _sql(engine, "INSERT INTO abandonments VALUES ('V1', 'r1', 2, 'scene', NULL, 't0'),"
         " ('V1', 'r1', 2, 'photo_preserved', NULL, 't0')")
    with refused(409, "wrong_scope"):  # not abandoned
        _revise(engine, settings, "c-old")
    with refused(409, "wrong_scope"):
        _background(engine, settings, "K-old")


@pytest.mark.parametrize("treatment", ["scene", "photo_preserved"])
def test_an_abandoned_scope_refuses_new_requests_of_that_treatment_only(engine, settings, treatment):
    with write_tx(engine) as conn:
        _seed(conn)
        _cutout(conn, "K1")
        _generated(conn, "c1", status="rejected")
        _generated(conn, "p1", status="rejected", cutout="K1")
        conn.execute(text("INSERT INTO abandonments VALUES ('V1', 'r1', 1, :treatment, NULL, 't0')"),
                     {"treatment": treatment})
    requests = {"scene": [lambda: _revise(engine, settings, "c1", "a")],
                "photo_preserved": [lambda: _revise(engine, settings, "p1", "b"),
                                    lambda: _background(engine, settings, "K1", "c")]}
    for request in requests[treatment]:
        with refused(409, "abandoned"):
            request()
    requests["photo_preserved" if treatment == "scene" else "scene"][0]()  # the other treatment is not abandoned


# --- Rules 2 and 4-5: photos, revisions, cutouts --------------------------------------------------------------------

def test_a_low_resolution_photo_needs_the_acknowledgement(engine, settings):
    with write_tx(engine) as conn:
        _seed(conn)
    with refused(409, "warning_not_acknowledged", {"warnings": ["low_resolution"], "assets": [LOW]}):
        _scene(engine, settings, photo_assets=[EDGE, LOW], acknowledged_warnings=["other"])
    assert _counts(engine) == (0, 0)
    _scene(engine, settings, "s1", photo_assets=[EDGE])  # a short edge of exactly 800 is not low
    _scene(engine, settings, "s2", variant_ref="V2", acknowledged_warnings=["low_resolution"])
    assert [_stored(engine, request_id)[1]["low_res_warning"] for request_id in ("s1", "s2")] == [0, 1]


def test_photos_must_belong_to_the_variant_and_every_image_must_be_a_known_asset(engine, settings):
    with write_tx(engine) as conn:
        _seed(conn)
    with refused(422, "photo_not_in_variant", {"assets": [FOREIGN]}):
        _scene(engine, settings, photo_assets=[P1, FOREIGN])
    with refused(422, "unknown_asset", {"assets": [MISSING]}):
        _scene(engine, settings, photo_assets=[P1, MISSING])
    with refused(422, "unknown_asset", {"assets": ["e" * 64]}):
        _scene(engine, settings, direction=Direction(style_ref="e" * 64))
    assert _counts(engine) == (0, 0)


def test_the_run_the_variant_and_the_target_must_exist(engine, settings):
    with write_tx(engine) as conn:
        _seed(conn)
    with refused(422, "unknown_run"):
        _scene(engine, settings, run_label="r9")
    with refused(422, "variant_not_in_run"):
        _scene(engine, settings, variant_ref="V3")
    with refused(422, "unknown_target"):
        _revise(engine, settings, "no-such-candidate")
    with refused(422, "unknown_target"):
        _background(engine, settings, "no-such-cutout")
    assert _counts(engine) == (0, 0)


def test_only_a_rejected_candidate_can_be_revised(engine, settings):
    with write_tx(engine) as conn:
        _seed(conn)
        _cutout(conn, "K1")
        _generated(conn, "c1", status="pending_review")
        _generated(conn, "c2", status="approved", attempt=2, parent="c1")
        _generated(conn, "p1", status="approved", cutout="K1")
    for parent_id in ("c1", "c2", "p1"):
        with refused(409, "not_rejected"):
            _revise(engine, settings, parent_id)
    with refused(409, "not_rejected"):  # the latest fallback is approved, not pending: nothing to review first
        _background(engine, settings, "K1")


def test_a_second_live_revision_of_a_parent_is_refused_until_the_first_fails(engine, settings):
    with write_tx(engine) as conn:
        _seed(conn)
        _generated(conn, "c1", status="rejected")
    _revise(engine, settings, "c1", "rev1")
    with refused(409, "revision_already_requested"):
        _revise(engine, settings, "c1", "rev2")
    _sql(engine, "UPDATE generation_requests SET status = 'failed' WHERE id = 'rev1'")
    assert _revise(engine, settings, "c1", "rev3").attempt_no == 2


@pytest.mark.parametrize("status", ["proposed", "rejected", "failed"])
def test_a_background_needs_a_confirmed_cutout(engine, settings, status):
    with write_tx(engine) as conn:
        _seed(conn)
        _cutout(conn, "K1", status=status)
    with refused(409, "cutout_not_confirmed"):
        _background(engine, settings, "K1")
    assert _counts(engine) == (0, 0)


# --- Prompts: corrections and the arm rule --------------------------------------------------------------------------

@pytest.mark.parametrize(("mode", "arm", "corrected"), [("by_arm", "B", False), ("by_arm", "A", True),
                                                         ("on", "B", True)])
def test_every_revision_of_an_arm_b_product_in_a_by_arm_run_is_a_plain_reroll(engine, settings, mode, arm,
                                                                               corrected):
    with write_tx(engine) as conn:
        _seed(conn, corrections_mode=mode, arm=arm)
        _cutout(conn, "K1")
        _generated(conn, "c1", status="rejected", reasons=("cameras",), note="les caméras sont fausses")
        _generated(conn, "p1", status="rejected", cutout="K1", reasons=("integration",), note="trop sombre")
    _revise(engine, settings, "c1", "scene-rev")
    _revise(engine, settings, "p1", "bg-rev")
    revisions = {"scene-rev": (lambda c, n: build_scene_prompt(SUBJECT, NEON, c, n), ["cameras"],
                               "les caméras sont fausses"),
                 "bg-rev": (lambda c, n: build_background_prompt(STYLED, c, n), ["integration"], "trop sombre")}
    for request_id, (build, reasons, note) in revisions.items():
        request, stored, _ = _stored(engine, request_id)
        expected = build(reasons, note) if corrected else build(None, None)
        assert stored["prompt"] == expected
        assert request.corrections_applied == int(corrected)
        assert ("Corrections to the previous attempt:" in expected, note in expected) == (corrected, corrected)


def test_a_background_revision_for_product_only_reasons_applies_no_correction(engine, settings):
    with write_tx(engine) as conn:
        _seed(conn)
        _cutout(conn, "K1")
        _generated(conn, "p1", status="rejected", cutout="K1", reasons=("coloris", "logo"))
    _revise(engine, settings, "p1")
    request, stored, _ = _stored(engine, "rev")
    assert (stored["prompt"], request.corrections_applied) == (build_background_prompt(STYLED, None, None), 0)


# --- Rule 6: the budget ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("spent", "admitted"), [(600_000, True), (600_001, False)])
def test_the_cap_admits_spent_plus_reservation_equal_to_it_and_not_one_micro_more(engine, env, spent, admitted):
    settings = _settings(env, SPEND_CAP_USD="1")
    with write_tx(engine) as conn:
        _seed(conn)
        _ledger_call(conn, spent)
    if admitted:
        assert _scene(engine, settings).spent == 1_000_000
    else:
        with refused(409, "budget_exhausted", {"spent": 600_001, "cap": 1_000_000, "reservation": 400_000}):
            _scene(engine, settings)
        assert _counts(engine) == (1, 1)  # the ledger's own rows only


def test_an_empty_ledger_sums_to_zero(engine, env):
    settings = _settings(env, SPEND_CAP_USD="0.3")
    with write_tx(engine) as conn:
        _seed(conn)
    with refused(409, "budget_exhausted", {"spent": 0, "cap": 300_000, "reservation": 400_000}):
        _scene(engine, settings)
    with engine.connect() as conn:
        assert reserve(conn, settings, model="gpt-image-2", purpose="background") == 300_000  # == cap: allowed


def test_calls_started_before_spend_cap_since_do_not_count(engine, env):
    settings = _settings(env, SPEND_CAP_USD="1")
    with write_tx(engine) as conn:
        _seed(conn)
        _ledger_call(conn, 900_000, started_at=f"{TODAY - timedelta(days=1)}T23:59:59.999999+00:00")
        _ledger_call(conn, 100_000, started_at=f"{TODAY}T00:00:00.000000+00:00")  # the first instant counts
    assert _scene(engine, settings).spent == 500_000


def test_the_reservation_floor_follows_the_highest_usage_based_cost_of_the_model_and_purpose(engine, settings):
    with write_tx(engine) as conn:
        _seed(conn)
        _ledger_call(conn, 400_000, estimate=0)
        _ledger_call(conn, 100_000, estimate=0)
        _ledger_call(conn, 3_000_000)  # an estimate: ignored
        _ledger_call(conn, 3_000_000, estimate=0, model="gpt-image-2.5-flare")
        _ledger_call(conn, 100_000, estimate=0, model="gpt-image-2.5-sunburst")
        _ledger_call(conn, 300_001, estimate=0, purpose="background")
    with engine.connect() as conn:
        assert reserve(conn, settings, model="gpt-image-2", purpose="scene") == 500_000  # ceil(1.25 x 400 000)
        assert reserve(conn, settings, model="gpt-image-2", purpose="background") == 375_002  # ceil(375 001.25)
        assert reserve(conn, settings, model="gpt-image-2.5-flare", purpose="scene") == 3_750_000
        assert reserve(conn, settings, model="gpt-image-2.5-sunburst", purpose="scene") == 400_000  # floor 125 000
    assert _scene(engine, settings).reservation == 500_000
    assert _stored(engine, "s1")[2].cost_micros == 500_000


# --- Configuration and caller errors --------------------------------------------------------------------------------

def test_a_model_without_rates_is_refused_before_any_row_and_before_the_budget(engine, env):
    settings = _settings(env, SPEND_CAP_USD="0.1")  # the budget would refuse too
    with write_tx(engine) as conn:
        _seed(conn, model="gpt-image-9")
    with pytest.raises(ValueError, match="no token rates for model 'gpt-image-9'"):
        _scene(engine, settings)
    assert _counts(engine) == (0, 0)


@pytest.mark.parametrize(("columns", "values"), [("", ""), (", name, variant", ", '', 'Noir'"),
                                                 (", name, variant", ", 'Redmi', '  '")])
def test_run_products_refuses_a_missing_or_blank_subject(engine, columns, values):
    # Migration 0002's CHECK: admission can rely on a subject being there.
    with write_tx(engine) as conn:
        _seed(conn)
    with pytest.raises(exc.IntegrityError, match="CHECK constraint failed"):
        _sql(engine, f"INSERT INTO run_products (run_label, variant_ref, arm, fixture_row_sha256{columns})"
             f" VALUES ('r1', 'V5', NULL, 'row-sha'{values})")


def test_caller_errors_raise_before_any_row(engine, settings):
    with write_tx(engine) as conn:
        _seed(conn)
    for photos in ([], [P1, P2, P3, P4]):
        with pytest.raises(ValueError, match="a scene takes 1 to 3 photos"):
            _scene(engine, settings, photo_assets=photos)
    assert _counts(engine) == (0, 0)
