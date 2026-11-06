"""Request execution (T-PV-007) with the stub provider. Requests come from the real admission path, on rows seeded
with test_admission's helpers and real image files."""
import asyncio
import hashlib
import io
import json
import logging
import sqlite3
from dataclasses import replace
from typing import NamedTuple

import pytest
from PIL import ExifTags, Image
from sqlalchemy import exc, text

from affiche import assets
from affiche.db import write_tx
from affiche.runtime import recover
from affiche.visuals import execution
from affiche.visuals.admission import request_scene
from affiche.visuals.cutout import make_cutout, place
from affiche.visuals.gateway import OUTPUT_SIZE, PROVIDER_INPUT_LONG_EDGE, StubProvider, prepare_provider_input
from affiche.visuals.prompts import Direction
from test_admission import (  # noqa: F401  (settings: fixture, a valid environment with DATA_DIR = tmp_path)
    NEON, SUBJECT, _background, _cutout, _generated, _reject, _revise, _seed, _settings, refused, settings,
)
from test_config import env  # noqa: F401  (fixture)
from test_cutout import FakeMask, phone
from test_db import engine  # noqa: F401  (fixture: a migrated engine on tmp_path)
from test_gateway import USAGE, encode

NON_RETRYABLE = ["refused", "quota", "timeout", "invalid_request", "invalid_response", "auth"]


class Recorder(StubProvider):
    """The stub, recording the images of each call and the peak number of calls in flight."""

    def __init__(self, fail_kinds=(), delay=0.0, during=None):
        super().__init__(fail_kinds, delay)
        self.sent, self.active, self.peak, self.during = [], 0, 0, during

    async def generate(self, **request):
        self.sent.append(request["images"])
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            if self.during:
                self.during()
            return await super().generate(**request)
        finally:
            self.active -= 1


class Priced(Recorder):
    """The stub's image with the cost and usage a real adapter could report (None: no usable usage)."""

    def __init__(self, cost_micros, usage):
        super().__init__()
        self.cost_micros, self.usage = cost_micros, usage

    async def generate(self, **request):
        return replace(await super().generate(**request), cost_micros=self.cost_micros, usage=self.usage)


class FakeSleep:
    """Records the waits instead of waiting; `during` runs at each."""

    def __init__(self, during=lambda: None):
        self.calls, self.during = [], during

    async def __call__(self, seconds):
        self.calls.append(seconds)
        self.during()


class Seeded(NamedTuple):
    photos: list[str]  # V1's photos
    v2_photos: list[str]
    bbox: tuple[int, int, int, int]  # K1's


def _asset(conn, settings, data, kind="original"):
    row = execution._stage(settings.data_dir, data, kind)
    assets.record(conn, **row)
    return row["sha"]


@pytest.fixture
def seeded(engine, settings):
    """test_admission's rows, plus real files: V1's two photos, V2's photo and V1's confirmed cutout K1."""
    scene, mask = phone()
    cut = make_cutout(encode(scene), mask_fn=FakeMask(mask))
    with write_tx(engine) as conn:
        _seed(conn)
        photos = [_asset(conn, settings, encode(Image.new("RGB", (900, 1200), colour))) for colour in ("red", "green")]
        v2_photos = [_asset(conn, settings, encode(Image.new("RGB", (900, 1200), "blue")))]
        _cutout(conn, "K1", direction=NEON, source=_asset(conn, settings, encode(scene)))
        conn.execute(text("UPDATE cutouts SET cutout_asset = :asset, bbox_json = :bbox WHERE id = 'K1'"),
                     {"asset": _asset(conn, settings, cut.png, "cutout"), "bbox": json.dumps(cut.bbox)})
    return Seeded(photos, v2_photos, cut.bbox)


def _admit_scene(engine, settings, variant_photos, request_id="s1", **overrides):
    arguments = {"id": request_id, "variant_ref": "V1", "run_label": "r1", "owner": "cli", "direction": NEON}
    return request_scene(engine, settings, variant_photos=variant_photos, **arguments | overrides)


def _two_rejected_scenes(engine, seeded):
    """used = 2 of the run's 3 scene slots. c2's photos are real files, for its revision."""
    with write_tx(engine) as conn:
        _generated(conn, "c1", status="rejected")
        _generated(conn, "c2", status="rejected", attempt=2, parent="c1")
        conn.execute(text("UPDATE candidates SET source_assets_json = :photos WHERE id = 'c2'"),
                     {"photos": json.dumps(seeded.photos)})


def _execute(engine, settings, provider, request_id, sleep=None):
    async def main():
        return await execution.execute(engine, settings, provider, request_id, slots=asyncio.Semaphore(2),
                                       sleep=sleep or FakeSleep())
    return asyncio.run(main())


def _select(engine, statement, **params):
    with engine.connect() as conn:
        return conn.execute(text(statement), params).all()


def _calls(engine, request_id):
    return _select(engine, "SELECT call_no, status, error_kind, cost_micros, cost_is_estimate FROM provider_calls"
                   " WHERE request_id = :id ORDER BY call_no", id=request_id)


def _request(engine, request_id):
    return _select(engine, "SELECT status, error_kind, candidate_id FROM generation_requests WHERE id = :id",
                   id=request_id)[0]


def _candidates(engine, request_id):
    return _select(engine, "SELECT * FROM candidates WHERE request_id = :id", id=request_id)


def _kind(engine, sha):
    return _select(engine, "SELECT kind FROM assets WHERE sha256 = :sha", sha=sha)[0].kind


# --- Success --------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("cost_micros", "usage", "stored"), [
    (0, None, (0, 0, None)),  # the plain stub: a usage-based cost of 0 replaces the reservation
    (123_457, USAGE, (123_457, 0, USAGE)),  # a usage-based cost replaces it, and the usage is kept
    (None, None, (400_000, 1, None)),  # no usable usage: the reserved estimate stays the cost
], ids=["stub", "usage", "no-usage"])
def test_a_scene_success_stores_the_raw_image_the_cost_and_a_pending_candidate(engine, settings, seeded,
                                                                                cost_micros, usage, stored):
    assert _admit_scene(engine, settings, seeded.photos).reservation == 400_000
    assert _execute(engine, settings, Priced(cost_micros, usage), "s1") == "succeeded"
    (call,) = _select(engine, "SELECT * FROM provider_calls WHERE request_id = 's1'")
    assert (call.status, call.error_kind) == ("succeeded", None)
    assert (call.cost_micros, call.cost_is_estimate, call.usage_json and json.loads(call.usage_json)) == stored
    assert call.finished_at is not None
    assert _select(engine, "SELECT kind, mime, width, height FROM assets WHERE sha256 = :sha", sha=call.raw_asset) == [
        ("scene", "image/png", 1088, 1920)]
    assert assets.path(settings.data_dir, call.raw_asset, "png").is_file()
    (candidate,) = _candidates(engine, "s1")
    (stored,) = _select(engine, "SELECT * FROM generation_requests WHERE id = 's1'")
    spec = json.loads(stored.request_json)
    assert (candidate.status, candidate.treatment, candidate.attempt_no, candidate.subject_name,
            candidate.subject_variant, candidate.image_asset, candidate.parent_id, candidate.cutout_id,
            candidate.product_box_json) == ("pending_review", "scene", 1, SUBJECT.name, SUBJECT.variant,
                                            call.raw_asset, None, None, None)
    assert (candidate.variant_ref, candidate.cycle_no, candidate.run_label, candidate.prompt,
            json.loads(candidate.source_assets_json), json.loads(candidate.direction_json),
            candidate.corrections_applied, candidate.provider, candidate.model, candidate.quality, candidate.size,
            candidate.low_res_warning) == ("V1", 1, "r1", spec["prompt"], seeded.photos, NEON.model_dump(mode="json"),
                                           0, "stub", "gpt-image-2", "high", "1088x1920", 0)
    assert (stored.status, stored.error_kind, stored.candidate_id) == ("succeeded", None, candidate.id)
    assert stored.finished_at is not None


def test_a_failure_inside_the_success_transaction_writes_none_of_it(engine, settings, seeded, monkeypatch):
    def failing_insert(*_args):
        raise RuntimeError("insert failed")

    monkeypatch.setattr(execution, "_insert_candidate", failing_insert)
    _admit_scene(engine, settings, seeded.photos)
    with pytest.raises(RuntimeError, match="insert failed"):
        _execute(engine, settings, Recorder(), "s1")
    assert _candidates(engine, "s1") == []
    # The call's success, written before the insert, was rolled back; it is failed, with the billed (stub) cost.
    assert _select(engine, "SELECT status, error_kind, error_detail, raw_asset, cost_micros, cost_is_estimate"
                   " FROM provider_calls") == [("failed", "invalid_request", "RuntimeError: insert failed", None, 0, 0)]
    assert _request(engine, "s1") == ("failed", "invalid_request", None)
    assert _select(engine, "SELECT * FROM assets WHERE kind = 'scene'") == []  # the file is a harmless orphan


def test_a_background_success_is_a_photo_preserved_candidate_with_the_shadow_baked(engine, settings, seeded):
    _background(engine, settings, "K1")
    provider = Recorder()
    assert _execute(engine, settings, provider, "bg") == "succeeded"
    assert provider.sent == [[]]  # no style reference: images.generate
    (call,) = _select(engine, "SELECT * FROM provider_calls WHERE request_id = 'bg'")
    (candidate,) = _candidates(engine, "bg")
    assert (candidate.treatment, candidate.status, candidate.cutout_id, candidate.attempt_no) == (
        "photo_preserved", "pending_review", "K1", 1)
    assert json.loads(candidate.product_box_json) == list(place(seeded.bbox))
    assert candidate.image_asset != call.raw_asset
    assert (_kind(engine, candidate.image_asset), _kind(engine, call.raw_asset)) == ("background", "background_raw")
    with engine.connect() as conn:
        baked = assets.load(conn, settings.data_dir, candidate.image_asset)
    assert Image.open(io.BytesIO(baked)).size == OUTPUT_SIZE
    assert _request(engine, "bg") == ("succeeded", None, candidate.id)


def test_the_provider_gets_stored_provider_input_copies_in_order(engine, settings, seeded):
    exif = Image.Exif()
    exif[ExifTags.Base.Orientation] = 6
    exif[ExifTags.Base.Make] = "PhoneMaker"
    # Not PNG: a PNG without metadata would give a byte-identical copy, the same asset as its original.
    with write_tx(engine) as conn:
        photos = [_asset(conn, settings, encode(Image.new("RGB", (3000, 2000), "orange"), "JPEG", exif=exif)),
                  _asset(conn, settings, encode(Image.new("RGB", (900, 1200), "teal"), "JPEG"))]
        style = _asset(conn, settings, encode(Image.new("RGB", (1024, 1024), "purple"), "WEBP"), "style_ref")
    _admit_scene(engine, settings, photos, direction=Direction(mood="minimal", style_ref=style))
    provider = Recorder()
    assert _execute(engine, settings, provider, "s1") == "succeeded"
    with engine.connect() as conn:
        originals = [assets.load(conn, settings.data_dir, sha) for sha in (*photos, style)]
    (sent,) = provider.sent
    assert sent == [prepare_provider_input(data) for data in originals]  # the photos, then the style reference
    for data in sent:
        image = Image.open(io.BytesIO(data))
        assert image.format == "PNG" and image.info == {} and not image.getexif()
        assert max(image.size) <= PROVIDER_INPUT_LONG_EDGE
        assert _kind(engine, hashlib.sha256(data).hexdigest()) == "provider_input"
    assert Image.open(io.BytesIO(sent[0])).size == (1024, 1536)  # upright (EXIF 6), then downscaled


# --- The retry ------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["provider_error", "rate_limited"])
def test_a_retry_keeps_its_slot_and_makes_no_fourth_candidate(engine, settings, seeded, kind):
    _two_rejected_scenes(engine, seeded)
    assert _revise(engine, settings, "c2").attempt_no == 3
    def admit_another():  # during the 5 s wait the running request still holds slot 3
        with refused(409, "attempt_limit_reached", {"fallback": "photo_preserved"}):
            _revise(engine, settings, "c2", "other")

    sleep = FakeSleep(admit_another)
    assert _execute(engine, settings, Recorder([kind]), "rev", sleep) == "succeeded"
    assert sleep.calls == [5]
    assert _calls(engine, "rev") == [(1, "failed", kind, 400_000, 1), (2, "succeeded", None, 0, 0)]
    (candidate,) = _candidates(engine, "rev")
    assert (candidate.attempt_no, candidate.parent_id, candidate.subject_name, candidate.corrections_applied) == (
        3, "c2", SUBJECT.name, 1)
    assert _select(engine, "SELECT COUNT(*) FROM candidates WHERE treatment = 'scene'") == [(3,)]
    _reject(engine, candidate.id)
    with refused(409, "attempt_limit_reached", {"fallback": "photo_preserved"}):
        _revise(engine, settings, candidate.id, "rev-4")


def test_when_both_calls_fail_the_request_fails_with_call_2s_kind(engine, settings, seeded):
    _admit_scene(engine, settings, seeded.photos)
    sleep = FakeSleep()
    assert _execute(engine, settings, Recorder(["rate_limited", "provider_error"]), "s1", sleep) == "failed"
    assert sleep.calls == [5]
    assert _calls(engine, "s1") == [(1, "failed", "rate_limited", 400_000, 1),
                                    (2, "failed", "provider_error", 400_000, 1)]
    assert _request(engine, "s1") == ("failed", "provider_error", None)
    assert _candidates(engine, "s1") == []


def test_a_retry_refused_by_the_budget_fails_the_request_and_frees_its_slot(engine, env, settings, seeded):
    _two_rejected_scenes(engine, seeded)
    tight = _settings(env, SPEND_CAP_USD="0.5")  # call 1's 0.40 fits, call 2's does not
    _revise(engine, tight, "c2")
    sleep = FakeSleep()
    assert _execute(engine, tight, Recorder(["provider_error"]), "rev", sleep) == "failed"
    assert sleep.calls == [5]
    assert _calls(engine, "rev") == [(1, "failed", "provider_error", 400_000, 1)]  # no call 2; call 1 keeps its cost
    assert _request(engine, "rev") == ("failed", "budget_exhausted", None)
    assert _candidates(engine, "rev") == []
    assert _revise(engine, settings, "c2", "again").attempt_no == 3  # slot 3 is free again (under a larger cap)


@pytest.mark.parametrize("kind", NON_RETRYABLE)
def test_a_non_retryable_kind_never_gets_call_2(engine, settings, seeded, kind):
    _admit_scene(engine, settings, seeded.photos)
    sleep, provider = FakeSleep(), Recorder([kind])
    assert _execute(engine, settings, provider, "s1", sleep) == "failed"
    assert (sleep.calls, len(provider.sent)) == ([], 1)
    assert _select(engine, "SELECT call_no, status, error_kind, error_detail, cost_micros, cost_is_estimate"
                   " FROM provider_calls") == [(1, "failed", kind, "stub failure", 400_000, 1)]
    assert _request(engine, "s1") == ("failed", kind, None)


def test_an_unexpected_error_during_the_retry_wait_fails_the_request_and_propagates(engine, settings, seeded):
    def crash():
        raise RuntimeError("boom")

    _admit_scene(engine, settings, seeded.photos)
    with pytest.raises(RuntimeError, match="boom"):
        _execute(engine, settings, Recorder(["provider_error"]), "s1", FakeSleep(crash))
    assert _calls(engine, "s1") == [(1, "failed", "provider_error", 400_000, 1)]  # a finished call is not rewritten
    assert _request(engine, "s1") == ("failed", "invalid_request", None)


@pytest.mark.parametrize(("locked_writes", "status"), [(2, "failed"), (3, "running")])
def test_a_locked_database_at_the_retry_waits_2_s_once_then_fails_with_call_1s_kind(
        engine, settings, seeded, monkeypatch, caplog, locked_writes, status):
    caplog.set_level(logging.WARNING, logger="affiche.visuals.execution")
    sleep, real_write_tx, locks = FakeSleep(), execution.write_tx, list(range(locked_writes))

    def write_tx(engine_):  # SQLITE_BUSY after the busy timeout, for the writes after the 5 s wait
        if sleep.calls and locks:
            locks.pop()
            raise exc.OperationalError("BEGIN IMMEDIATE", {}, sqlite3.OperationalError("database is locked"))
        return real_write_tx(engine_)

    monkeypatch.setattr(execution, "write_tx", write_tx)
    _admit_scene(engine, settings, seeded.photos)
    assert _execute(engine, settings, Recorder(["provider_error"]), "s1", sleep) == status
    assert sleep.calls == [5, 2]
    assert _calls(engine, "s1") == [(1, "failed", "provider_error", 400_000, 1)]
    # The last write failing too leaves the request running, for owner recovery at the next start.
    assert _request(engine, "s1") == (status, "provider_error" if status == "failed" else None, None)
    assert [record.levelname for record in caplog.records] == (
        ["WARNING", "WARNING"] + (["ERROR"] if status == "running" else []))


# --- Storage, state, concurrency ------------------------------------------------------------------------------------

def test_a_storage_failure_after_the_provider_call_fails_the_call_and_the_request(
        engine, settings, seeded, monkeypatch):
    real_put = assets.put

    def put(data_dir, data, ext):
        if Image.open(io.BytesIO(data)).size == OUTPUT_SIZE:  # the provider's image
            raise OSError("disk full")
        return real_put(data_dir, data, ext)

    monkeypatch.setattr(assets, "put", put)
    _admit_scene(engine, settings, seeded.photos)
    assert _execute(engine, settings, Priced(123_457, USAGE), "s1") == "failed"
    # Billed: the call keeps its usage-based cost and usage, not the 400 000 reservation.
    (call,) = _select(engine, "SELECT status, error_kind, error_detail, cost_micros, cost_is_estimate, raw_asset,"
                      " usage_json FROM provider_calls")
    assert call[:-1] == ("failed", "storage", "OSError: disk full", 123_457, 0, None)
    assert json.loads(call.usage_json) == USAGE
    assert _request(engine, "s1") == ("failed", "storage", None)
    assert _candidates(engine, "s1") == []


def test_a_missing_input_file_fails_the_call_as_storage_before_any_spend(engine, settings, seeded):
    _admit_scene(engine, settings, seeded.photos)
    assets.path(settings.data_dir, seeded.photos[1], "png").unlink()
    provider = Recorder()
    assert _execute(engine, settings, provider, "s1") == "failed"
    assert provider.sent == []
    assert _calls(engine, "s1") == [(1, "failed", "storage", 400_000, 1)]
    assert _request(engine, "s1") == ("failed", "storage", None)


@pytest.mark.parametrize("when", ["before", "during"])
def test_a_request_no_longer_running_gets_no_call_and_no_candidate(engine, settings, seeded, when):
    _admit_scene(engine, settings, seeded.photos)
    provider = Recorder(during=(lambda: recover(engine, "cli")) if when == "during" else None)  # owner recovery
    if when == "before":
        recover(engine, "cli")
    assert _execute(engine, settings, provider, "s1") == "interrupted"
    assert len(provider.sent) == (0 if when == "before" else 1)
    assert _candidates(engine, "s1") == []
    assert _calls(engine, "s1") == [(1, "interrupted", "interrupted", 400_000, 1)]
    assert _request(engine, "s1") == ("interrupted", "interrupted", None)
    assert _select(engine, "SELECT * FROM assets WHERE kind = 'scene'") == []


def test_at_most_two_provider_calls_run_at_once(engine, settings, seeded):
    _admit_scene(engine, settings, seeded.photos, "a")
    _admit_scene(engine, settings, seeded.v2_photos, "b", variant_ref="V2")
    _background(engine, settings, "K1", "c")
    provider = Recorder(delay=0.05)

    async def main():
        slots = asyncio.Semaphore(2)
        return await asyncio.gather(*(execution.execute(engine, settings, provider, request_id, slots=slots,
                                                        sleep=FakeSleep()) for request_id in "abc"))

    assert asyncio.run(main()) == ["succeeded"] * 3
    assert (len(provider.sent), provider.peak) == (3, 2)
