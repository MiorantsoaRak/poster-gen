from concurrent.futures import ThreadPoolExecutor
import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json

import pytest
from sqlalchemy import text

from affiche.config import load_settings
from affiche.db import utc_now, write_tx
from affiche.posters import jobs, store
from affiche.posters.worker import Outcome, run_job
from affiche.posters.models import Document, NewCreation, Offer, ProductInput
from affiche.visuals import admission
from affiche.visuals.gateway import ProviderError
from test_admission import _seed, _ledger_call
from test_api import second_shop
from test_config import env  # noqa: F401
from test_db import engine  # noqa: F401
from test_poster_drafts import input_id, draft, key, photo  # noqa: F401


@pytest.fixture
def settings(env, tmp_path):
    env.setenv("DATA_DIR", str(tmp_path))
    env.setenv("IMAGE_PROVIDER", "openai")
    env.setenv("OPENAI_API_KEY", "test-not-a-key")
    return load_settings(env_file=None)


@pytest.fixture
def creation(engine, tmp_path, input_id):
    return draft(engine, tmp_path, input_id)


def enqueue(engine, settings, creation, *, kind="scene", operation=None, payload=None, revision=1, shop=1):
    payload = payload or {"prompt": "test"}
    return store.mutate(engine, shop, operation or key(), "POST", f'/test/{creation["id"]}/{kind}', payload,
                        lambda conn: (202, jobs.enqueue(conn, settings, shop, creation["id"], revision, kind, payload)),
                        revision=revision)[1]["job_id"]


def poster_of(engine, tmp_path, shop):
    """A poster of another shop, from its own photo."""
    asset = store.upload(engine, tmp_path, shop, photo(colour="green"), "original")["asset"]
    source = store.create_input(engine, tmp_path, shop, key(), ProductInput(name="Sony", variant="v", photo_assets=[asset]))[1]["id"]
    return store.create_creation(engine, tmp_path, shop, key(), NewCreation(
        input_id=source, offer=Offer(title="Sony X", price_ar=1000),
        brand_selection={"logo": False, "shop_name": False, "contact": False}))[1]


def jobs_count(engine):
    with engine.connect() as conn:
        return conn.execute(text("SELECT COUNT(*) FROM poster_jobs")).scalar_one()


def view(engine, id):
    with engine.connect() as conn:
        return jobs.get_job(conn, 1, id)


def spent(engine, settings):
    with engine.connect() as conn:
        return admission.spent_micros(conn, settings)


def test_admission_reserves_once_and_replays_before_revision_checks(engine, settings, creation, tmp_path):
    operation = key()
    id = enqueue(engine, settings, creation, operation=operation)
    document = Document.model_validate(creation["document"])
    document.offer.price_ar += 1
    store.save_creation(engine, tmp_path, 1, key(), creation["id"], document, 1)
    assert enqueue(engine, settings, creation, operation=operation) == id
    assert spent(engine, settings) == 400000
    with pytest.raises(store.Refused, match="revision_conflict"):
        enqueue(engine, settings, creation)
    assert view(engine, id)["status"] == "queued"
    assert "input_json" not in view(engine, id)


def test_combined_budget_blocks_both_entry_points(engine, settings, creation):
    settings.spend_cap_usd = Decimal("0.5")
    with write_tx(engine) as conn:
        _seed(conn)
        _ledger_call(conn, 200000)
    with pytest.raises(store.Refused, match="budget_exhausted"):
        enqueue(engine, settings, creation)
    assert spent(engine, settings) == 200000
    settings.spend_cap_usd = Decimal("0.6")
    enqueue(engine, settings, creation)
    assert spent(engine, settings) == 600000
    with write_tx(engine) as conn, pytest.raises(admission.Refused) as caught:
        admission.reserve(conn, settings, model="gpt-image-2", purpose="scene")
    assert caught.value.code == "budget_exhausted"


def test_concurrent_admissions_share_cap_and_leave_no_orphan_reservations(engine, settings, creation, tmp_path, input_id):
    other = draft(engine, tmp_path, input_id)
    settings.spend_cap_usd = Decimal("0.5")

    def submit(item):
        try:
            return enqueue(engine, settings, item)
        except store.Refused as error:
            return error.code

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(submit, [creation, other]))
    assert results.count("budget_exhausted") == 1
    assert spent(engine, settings) == 400000
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM poster_jobs")).scalar_one() == 1


def test_cancel_and_claim_race_has_one_winner(engine, settings, creation):
    id = enqueue(engine, settings, creation)

    def cancel():
        try:
            return jobs.cancel(engine, 1, key(), id)
        except store.Refused as error:
            return error.code

    with ThreadPoolExecutor(2) as pool:
        cancelled = pool.submit(cancel)
        claimed = pool.submit(jobs.claim, engine, ("scene",))
        cancelled, claimed = cancelled.result(), claimed.result()
    if claimed is None:
        assert view(engine, id)["status"] == "cancelled" and spent(engine, settings) == 0
    else:
        assert cancelled == "already_started" and spent(engine, settings) == 400000


def test_active_image_blocks_abandon_and_other_image_work(engine, settings, creation):
    id = enqueue(engine, settings, creation)
    with pytest.raises(store.Refused, match="image_job_running"):
        enqueue(engine, settings, creation, kind="text_texture")
    with pytest.raises(store.Refused, match="image_job_running"):
        store.abandon_creation(engine, 1, key(), creation["id"], 1)
    operation = key()
    first = jobs.cancel(engine, 1, operation, id)
    assert jobs.cancel(engine, 1, operation, id) == first
    store.abandon_creation(engine, 1, key(), creation["id"], 1)
    with pytest.raises(store.Refused, match="creation_abandoned"):
        enqueue(engine, settings, creation)


def test_scene_limit_and_failed_jobs_do_not_consume_slots(engine, settings, creation, tmp_path):
    settings.shop_daily_spend_usd = Decimal("20")  # twelve scenes cost more than a shop's day: the limit here is the count
    id = enqueue(engine, settings, creation)
    jobs.claim(engine, ("scene",))
    jobs.fail(engine, id, "preflight", unsent=True)
    assert spent(engine, settings) == 0
    assert jobs.SCENE_LIMIT == 12
    for _ in range(jobs.SCENE_LIMIT):
        id = enqueue(engine, settings, creation)
        job = jobs.claim(engine, ("scene",))
        jobs.dispatch(engine, id)
        jobs.spool(tmp_path, job, {"visual": key()}, cost_micros=170000)
        jobs.finish_spool(engine, tmp_path, id, lambda _conn, _job, result: result["visual"])
    assert spent(engine, settings) == 170000 * jobs.SCENE_LIMIT
    with pytest.raises(store.Refused, match="attempt_limit"):
        enqueue(engine, settings, creation)


def test_two_provider_slots_and_one_local_slot(engine, settings, creation, tmp_path, input_id):
    for _ in range(3):
        enqueue(engine, settings, draft(engine, tmp_path, input_id))
    assert jobs.claim(engine, ("scene",)) and jobs.claim(engine, ("scene",))
    assert jobs.claim(engine, ("scene",)) is None
    enqueue(engine, settings, creation, kind="render")
    enqueue(engine, settings, creation, kind="cutout")
    assert jobs.claim(engine, ("render", "cutout"))
    assert jobs.claim(engine, ("render", "cutout")) is None


def test_shops_take_turns_in_the_queue(engine, settings, creation, tmp_path, input_id):
    """R-MULTI-SHOP-003: A's long queue does not hold B's first job behind all of it (the audit's FIFO test inverted)."""
    shop_b, _ = second_shop(engine)
    first, second, third = (enqueue(engine, settings, item) for item in (
        creation, draft(engine, tmp_path, input_id), draft(engine, tmp_path, input_id)))
    poster_b = poster_of(engine, tmp_path, shop_b)
    b_job = enqueue(engine, settings, poster_b, shop=shop_b)  # queued after all of A's
    assert jobs.claim(engine, ("scene",))["id"] == first
    assert jobs.claim(engine, ("scene",))["id"] == b_job  # B never had a job started; A a moment ago
    assert jobs.claim(engine, ("scene",)) is None  # still two provider slots for the whole service
    jobs.fail(engine, first, "test", unsent=True)
    assert jobs.claim(engine, ("scene",))["id"] == second
    jobs.fail(engine, b_job, "test", unsent=True)
    b_again = enqueue(engine, settings, poster_b, shop=shop_b)
    assert jobs.claim(engine, ("scene",))["id"] == b_again != third  # B was served longer ago than A


def test_the_guard_tells_a_suspension_then_the_services_pause_then_the_shops_day(engine, settings, creation):
    """D-MULTI-SHOP-005's order: the service's cap before the shop's own day, so that every shop is told the service is
    paused. A refusal reserves and writes nothing."""
    with write_tx(engine) as conn:
        _seed(conn)
        _ledger_call(conn, 200000)  # the evaluation CLI's: the service's spend, no shop's
        conn.exec_driver_sql("UPDATE shop_profile SET state='suspended' WHERE id=1")
    settings.spend_cap_usd, settings.shop_daily_spend_usd = Decimal("0.5"), Decimal("0.3")

    def refused():
        with pytest.raises(store.Refused) as caught:
            enqueue(engine, settings, creation)
        assert spent(engine, settings) == 200000 and jobs_count(engine) == 0
        return caught.value.code, caught.value.status

    assert refused() == ("shop_suspended", 403)
    with write_tx(engine) as conn:
        conn.exec_driver_sql("UPDATE shop_profile SET state='active' WHERE id=1")
    assert refused() == ("budget_exhausted", 429)  # 0.20 + 0.40 > 0.50
    settings.spend_cap_usd = Decimal("20")
    assert refused() == ("shop_daily_limit", 429)  # 0.40 > 0.30
    settings.shop_daily_spend_usd = Decimal("0.4")  # exactly the day's ceiling; the CLI's 0.20 is no shop's
    enqueue(engine, settings, creation)
    assert spent(engine, settings) == 600000


def test_one_shops_day_does_not_stop_another_and_the_services_cap_stops_both(engine, settings, creation, tmp_path, input_id):
    """R-MULTI-SHOP-003: each shop has its own day of provider spend; at the service's cap every shop is told the
    service is paused, and nothing is reserved."""
    shop_b, _ = second_shop(engine)
    other = draft(engine, tmp_path, input_id)
    settings.shop_daily_spend_usd = Decimal("0.5")
    enqueue(engine, settings, creation)  # A's day: 0.40
    with pytest.raises(store.Refused, match="shop_daily_limit"):
        enqueue(engine, settings, other)
    enqueue(engine, settings, poster_of(engine, tmp_path, shop_b), shop=shop_b)  # B's day is B's own
    with engine.connect() as conn:
        assert [admission.spent_micros(conn, settings, shop=shop) for shop in (1, shop_b)] == [400000, 400000]
    settings.spend_cap_usd, settings.shop_daily_spend_usd = Decimal("1.1"), Decimal("2")  # 0.80 + 0.40 > 1.10
    for shop, item in ((1, other), (shop_b, poster_of(engine, tmp_path, shop_b))):
        with pytest.raises(store.Refused) as caught:
            enqueue(engine, settings, item, shop=shop)
        assert (caught.value.code, caught.value.status) == ("budget_exhausted", 429)
    assert spent(engine, settings) == 800000 and jobs_count(engine) == 2


def test_a_reservation_counts_on_the_day_it_was_admitted(engine, settings, creation, tmp_path, input_id):
    """The shop's ceiling is an admission-day budget: a job admitted at 23:59 UTC and finished after midnight stays in
    the first day's sum, and the next day's ceiling does not see it."""
    settings.spend_cap_since = datetime.now(UTC).date() - timedelta(days=7)
    settings.shop_daily_spend_usd = Decimal("0.4")
    id = enqueue(engine, settings, creation)
    late = f"{datetime.now(UTC).date() - timedelta(days=1)}T23:59:59.999999+00:00"
    with write_tx(engine) as conn:
        conn.exec_driver_sql("UPDATE poster_calls SET created_at=? WHERE job_id=?", (late, id))
    job = jobs.claim(engine, ("scene",))
    jobs.dispatch(engine, id)
    jobs.spool(tmp_path, job, {"visual": "v"}, cost_micros=170000)
    jobs.finish_spool(engine, tmp_path, id, lambda *_: "v")
    with engine.connect() as conn:
        assert admission.spent_micros(conn, settings, shop=1, since=late[:10]) == 170000
        assert admission.spent_micros(conn, settings, shop=1, since=utc_now()[:10]) == 0
    enqueue(engine, settings, draft(engine, tmp_path, input_id))  # today's 0.40 fits today's 0.40


@pytest.mark.parametrize("refusal", ["shop_daily_limit", "shop_suspended"])
def test_a_rate_limit_retry_refused_by_the_guard_fails_at_no_cost(engine, settings, creation, refusal):
    """worker.py: a 429 retry's reservation refused by any of the guard's checks fails the job with the provider's code
    at cost 0, call 2 never reserved, instead of escaping to reconciliation_required."""
    id = enqueue(engine, settings, creation)
    job = jobs.claim(engine, ("scene",))
    sent = []

    async def send(_):
        sent.append(1)
        if refusal == "shop_daily_limit":
            settings.shop_daily_spend_usd = Decimal("0.3")
        else:
            with write_tx(engine) as conn:
                conn.exec_driver_sql("UPDATE shop_profile SET state='suspended' WHERE id=1")
        raise ProviderError("rate_limited", "secret provider body")

    asyncio.run(run_job(engine, settings, job, prepare=lambda *_: {}, send=send, finalise=lambda *_: pytest.fail("finalised")))
    assert len(sent) == 1 and (view(engine, id)["status"], view(engine, id)["error_code"]) == ("failed", "rate_limited")
    assert spent(engine, settings) == 0
    with engine.connect() as conn:
        assert conn.execute(text("SELECT call_no FROM poster_calls WHERE job_id=:id"), {"id": id}).scalars().all() == [1]


def test_dispatch_crash_never_replays_and_unsent_crash_requeues(engine, settings, creation, tmp_path):
    id = enqueue(engine, settings, creation)
    jobs.claim(engine, ("scene",))
    assert jobs.recover(engine, tmp_path) == []
    assert view(engine, id)["status"] == "queued"
    jobs.claim(engine, ("scene",))
    jobs.dispatch(engine, id)
    with pytest.raises(store.Refused, match="call_already_dispatched"):
        jobs.fail(engine, id, "bad", unsent=True)
    jobs.recover(engine, tmp_path)
    assert view(engine, id)["status"] == "interrupted"
    assert spent(engine, settings) == 400000 and jobs.claim(engine, ("scene",)) is None


def test_spool_survives_failed_commit_and_recovers_without_provider(engine, settings, creation, tmp_path):
    id = enqueue(engine, settings, creation)
    job = jobs.claim(engine, ("scene",))
    jobs.dispatch(engine, id)
    jobs.spool(tmp_path, job, {"visual": "kept-result"}, usage={"input_tokens": 1}, cost_micros=170000)

    def failing(conn, _job, _result):
        conn.execute(text("UPDATE creations SET status='abandoned' WHERE id=:id"), {"id": creation["id"]})
        raise OSError("disk full")

    with pytest.raises(OSError):
        jobs.finish_spool(engine, tmp_path, id, failing)
    assert spent(engine, settings) == 400000 and jobs.recover(engine, tmp_path) == [id]
    with engine.connect() as conn:
        assert store.get_creation(conn, 1, creation["id"])["status"] == "active"
    assert jobs.finish_spool(engine, tmp_path, id, lambda *_: "kept-result") == "kept-result"
    assert spent(engine, settings) == 170000
    assert jobs.finish_spool(engine, tmp_path, id, lambda *_: pytest.fail("replayed")) == "kept-result"


def test_spool_mismatch_and_unknown_cost_are_not_trusted(engine, settings, creation, tmp_path):
    id = enqueue(engine, settings, creation)
    job = jobs.claim(engine, ("scene",))
    jobs.dispatch(engine, id)
    jobs.spool(tmp_path, job, {"visual": "ok"})
    with pytest.raises(ValueError, match="spool_conflict"):
        jobs.spool(tmp_path, job, {"visual": "different"})
    envelope = json.loads(jobs.spool_path(tmp_path, id).read_bytes())
    envelope["input_hash"] = "wrong"
    jobs.spool_path(tmp_path, id).write_text(json.dumps(envelope), encoding="utf-8")
    with pytest.raises(store.Refused):
        jobs.finish_spool(engine, tmp_path, id, lambda *_: pytest.fail("invalid result"))
    envelope["input_hash"] = job["input_hash"]
    jobs.spool_path(tmp_path, id).write_text(json.dumps(envelope), encoding="utf-8")
    jobs.finish_spool(engine, tmp_path, id, lambda *_: "ok")
    assert spent(engine, settings) == 400000 and view(engine, id)["usage"]["estimated"] is True


def test_only_one_rate_limit_retry_replaces_rejected_reservation(engine, settings, creation):
    id = enqueue(engine, settings, creation)
    jobs.claim(engine, ("scene",))
    jobs.dispatch(engine, id)
    assert jobs.reserve_rate_limit_retry(engine, settings, id)
    assert spent(engine, settings) == 400000
    assert jobs.dispatch(engine, id)["call_no"] == 2
    assert not jobs.reserve_rate_limit_retry(engine, settings, id)
    jobs.fail(engine, id, "rate_limited", cost_micros=0)
    assert spent(engine, settings) == 0


@pytest.mark.parametrize("code", ["timeout", "provider_error"])
def test_ambiguous_error_retains_estimate_and_never_requeues(engine, settings, creation, tmp_path, code):
    id = enqueue(engine, settings, creation)
    jobs.claim(engine, ("scene",))
    jobs.dispatch(engine, id)
    jobs.fail(engine, id, code, ambiguous=True)
    jobs.recover(engine, tmp_path)
    assert view(engine, id)["status"] == "interrupted" and spent(engine, settings) == 400000
    assert jobs.claim(engine, ("scene",)) is None


def test_local_crash_retries_once_without_provider(engine, settings, creation, tmp_path):
    id = enqueue(engine, settings, creation, kind="render")
    for _ in range(2):
        assert jobs.claim(engine, ("render",))
        jobs.recover(engine, tmp_path)
    assert view(engine, id)["status"] == "failed" and spent(engine, settings) == 0


def test_planner_config_and_mode_lock(engine, settings, creation):
    with pytest.raises(store.Refused, match="planner_unavailable"):
        enqueue(engine, settings, creation, kind="plan")
    settings.planner_provider = "stub"
    enqueue(engine, settings, creation, kind="plan")
    assert spent(engine, settings) == 0
    from pydantic import SecretStr
    settings.planner_provider, settings.anthropic_api_key = "claude", SecretStr("test")
    with pytest.raises(store.Refused, match="provider_mode_mismatch"):
        enqueue(engine, settings, creation, kind="plan")


@pytest.mark.parametrize(("errors", "expected", "calls"), [
    ([], "succeeded", 1), (["rate_limited"], "succeeded", 2),
    (["rate_limited", "rate_limited"], "failed", 2),
    (["timeout"], "interrupted", 1), (["provider_error"], "interrupted", 1),
    (["auth"], "failed", 1), (["invalid_response"], "failed", 1),
])
def test_worker_dispatch_failure_policy(engine, settings, creation, errors, expected, calls):
    id = enqueue(engine, settings, creation)
    job = jobs.claim(engine, ("scene",))
    sent = []

    async def send(prepared):
        with engine.connect() as conn:
            assert jobs.current_call(conn, id)["status"] == "running"
        sent.append(prepared)
        if len(sent) <= len(errors):
            raise ProviderError(errors[len(sent)-1], "secret provider body")
        return Outcome({"visual": "saved"}, cost_micros=170000)

    asyncio.run(run_job(engine, settings, job, prepare=lambda *_: "validated input", send=send,
                        finalise=lambda *_: "saved"))
    assert len(sent) == calls and view(engine, id)["status"] == expected
    expected_cost = 170000 if expected == "succeeded" else 0 if errors == ["rate_limited", "rate_limited"] else 400000
    assert spent(engine, settings) == expected_cost


def test_worker_preflight_and_spool_recovery_do_not_dispatch(engine, settings, creation, tmp_path):
    id = enqueue(engine, settings, creation)
    job = jobs.claim(engine, ("scene",))

    def prepare(*_):
        raise OSError("missing original")

    async def send(_):
        pytest.fail("must not dispatch")

    asyncio.run(run_job(engine, settings, job, prepare=prepare, send=send, finalise=lambda *_: "bad"))
    assert view(engine, id)["status"] == "failed" and spent(engine, settings) == 0
    id = enqueue(engine, settings, creation)
    job = jobs.claim(engine, ("scene",))
    jobs.dispatch(engine, id)
    jobs.spool(tmp_path, job, {"visual": "kept"}, cost_micros=170000)
    asyncio.run(run_job(engine, settings, job, prepare=prepare, send=send, finalise=lambda *_: "kept"))
    assert view(engine, id)["status"] == "succeeded" and spent(engine, settings) == 170000


def test_worker_retains_spool_after_local_failures_without_resending(engine, settings, creation, tmp_path):
    id = enqueue(engine, settings, creation)
    job = jobs.claim(engine, ("scene",))
    sent = []

    async def send(_):
        sent.append(1)
        return Outcome({"visual": "kept"}, cost_micros=170000)

    def fail_finalise(*_):
        raise OSError("disk full")

    assert asyncio.run(run_job(engine, settings, job, prepare=lambda *_: {}, send=send, finalise=fail_finalise)) is False
    assert jobs.spool_path(tmp_path, id).exists() and view(engine, id)["status"] == "running"
    assert asyncio.run(run_job(engine, settings, job, prepare=lambda *_: {}, send=send, finalise=lambda *_: "kept"))
    assert len(sent) == 1 and spent(engine, settings) == 170000


def test_spool_disk_failure_records_known_cost_without_resending(engine, settings, creation, monkeypatch):
    id = enqueue(engine, settings, creation)
    job = jobs.claim(engine, ("scene",))
    sent = []

    async def send(_):
        sent.append(1)
        return Outcome({"visual": "cannot-save"}, cost_micros=170000)

    def no_disk(*_, **__):
        raise OSError("disk full")

    monkeypatch.setattr(jobs, "spool", no_disk)
    asyncio.run(run_job(engine, settings, job, prepare=lambda *_: {}, send=send, finalise=lambda *_: "bad"))
    assert len(sent) == 1 and spent(engine, settings) == 170000
    assert view(engine, id)["status"] == "interrupted"
    assert view(engine, id)["error_code"] == "reconciliation_required"
