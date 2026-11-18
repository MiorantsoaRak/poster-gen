from concurrent.futures import ThreadPoolExecutor
import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from affiche.config import load_settings
from affiche.db import utc_now, write_tx
from affiche import shops
from affiche.posters import auth, credits, jobs, looks, store, terms, worker
from affiche.posters.worker import Outcome, run_job
from affiche.posters.models import Document, NewCreation, Offer, ProductInput
from affiche.visuals import admission
from affiche.visuals.gateway import ProviderError
from test_admission import _seed, _ledger_call
from test_api import second_shop
from test_config import env  # noqa: F401
from test_db import accepted, engine, unaccepted  # noqa: F401
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


# --- The prepaid balance at admission (D-BALANCE-002). The engine fixture's shop 1 starts with 100 credits. ----------

def balance(engine, shop=1):
    with engine.connect() as conn:
        return credits.balance(conn, shop)


def leave(engine, available, shop=1):
    """The operator's correction that leaves the shop exactly `available` credits."""
    with write_tx(engine) as conn:
        credits.correct(conn, shop, available - credits.balance(conn, shop)["available"], ref=key(), note="test",
                        actor="tests")


def written(engine):
    """What an admission writes (jobs, calls, idempotency keys) and the shop's credits."""
    with engine.connect() as conn:
        return [conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
                for table in ("poster_jobs", "poster_calls", "mutation_keys")] + [credits.balance(conn, 1)]


def test_an_image_takes_one_credit_and_no_other_job_takes_any(engine, settings, creation, tmp_path, input_id):
    """Owner decision 2: a scene, a refinement and a text's material each take a credit; a plan, a style, a text
    proposal, a render and a cutout take none, and are admitted at zero."""
    settings.planner_provider = "stub"
    images = [enqueue(engine, settings, draft(engine, tmp_path, input_id), kind=kind)
              for kind in ("scene", "refine", "text_texture")]
    assert balance(engine) == {"available": 97, "pending": 3}
    leave(engine, 0)
    others = [enqueue(engine, settings, creation, kind=kind, payload=payload) for kind, payload in (
        ("plan", None), ("plan", {"look": "Style"}), ("text_patch", None), ("render", None), ("cutout", None))]
    assert balance(engine) == {"available": 0, "pending": 3}
    with engine.connect() as conn:
        taken = dict(conn.execute(text("SELECT id, takes_credit FROM poster_jobs")).all())
    assert taken == {id: 1 for id in images} | {id: 0 for id in others}
    assert [view(engine, id)["credit"] for id in images + others] == ["pending"] * 3 + [None] * 5


def test_no_credit_is_said_last_and_no_refusal_takes_anything(engine, settings, creation, tmp_path, input_id):
    """D-BALANCE-002's order, at zero credits: every other refusal comes first (buying would not help), and none leaves
    a job, a call, a key or a credit taken."""
    enqueue(engine, settings, creation)  # the poster's one image, and 0.40 USD of the cap and of the shop's day
    leave(engine, 0)
    other, before = draft(engine, tmp_path, input_id), written(engine)

    def refused(item=None, **options):
        with pytest.raises(store.Refused) as caught:
            enqueue(engine, settings, item or other, **options)
        assert written(engine) == before
        return caught.value.code, caught.value.status

    api_key, settings.openai_api_key = settings.openai_api_key, None
    assert refused() == ("provider_unavailable", 503)
    settings.openai_api_key, settings.image_provider = api_key, "stub"
    assert refused() == ("provider_mode_mismatch", 409)
    settings.image_provider = "openai"
    assert refused(creation) == ("image_job_running", 409)
    assert refused(revision=2) == ("revision_conflict", 409)
    with write_tx(engine) as conn:
        conn.exec_driver_sql("UPDATE shop_profile SET state='suspended' WHERE id=1")
    assert refused() == ("shop_suspended", 403)
    with write_tx(engine) as conn:
        conn.exec_driver_sql("UPDATE shop_profile SET state='active' WHERE id=1")
    settings.spend_cap_usd = Decimal("0.5")  # 0.40 + 0.40 > 0.50
    assert refused() == ("budget_exhausted", 429)
    settings.spend_cap_usd, settings.shop_daily_spend_usd = Decimal("20"), Decimal("0.5")
    assert refused() == ("shop_daily_limit", 429)
    settings.shop_daily_spend_usd = Decimal("2")
    assert refused() == ("no_credit", 402)


def test_a_refusal_for_want_of_credit_leaves_meta_and_the_credit_lines_as_they_were(engine, settings, creation):
    """Review r1 of T-BALANCE-002: the first image of a data folder writes meta.provider_mode before the credit check;
    the refusal rolls it back with the job, its call and its key, and writes no credit line."""
    leave(engine, 0)

    def state():
        with engine.connect() as conn:
            return [conn.execute(text(f"SELECT * FROM {table} ORDER BY 1")).all()
                    for table in ("meta", "credit_grants", "poster_jobs", "poster_calls", "mutation_keys")]

    before = state()
    assert "provider_mode" not in dict(before[0])
    with pytest.raises(store.Refused, match="no_credit"):
        enqueue(engine, settings, creation)
    assert state() == before


def test_a_shop_at_zero_is_refused_while_a_funded_shop_is_admitted_each_on_its_own_balance(engine, settings, creation, tmp_path):
    """Review r1 of T-BALANCE-002: A (shop 1) funded, B at zero. B's scene gets 402, so B's admission did not read A's
    credits, and A's balance does not move; A's scene is admitted beside B's zero. (An admission reading another shop at
    zero would pass anyway: the new job counts in its own shop, and only a balance below zero refuses.)"""
    shop_b, _ = second_shop(engine)
    leave(engine, 0, shop=shop_b)
    with pytest.raises(store.Refused) as caught:
        enqueue(engine, settings, poster_of(engine, tmp_path, shop_b), shop=shop_b)
    assert (caught.value.code, caught.value.status) == ("no_credit", 402)
    assert balance(engine) == {"available": 100, "pending": 0}
    enqueue(engine, settings, creation)
    assert (balance(engine), balance(engine, shop_b)) == ({"available": 99, "pending": 1}, {"available": 0, "pending": 0})


def test_two_admissions_for_the_last_credit_admit_one(engine, settings, creation, tmp_path, input_id):
    """R-BALANCE-002: two posters, one credit. BEGIN IMMEDIATE serialises the admissions, and the second one counts
    the first one's job."""
    other = draft(engine, tmp_path, input_id)
    leave(engine, 1)
    before = written(engine)[:3]

    def submit(item):
        try:
            return enqueue(engine, settings, item)
        except store.Refused as error:
            return error.code

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(submit, [creation, other]))
    assert results.count("no_credit") == 1
    assert balance(engine) == {"available": 0, "pending": 1}
    assert [now - was for now, was in zip(written(engine), before)] == [1, 1, 1]  # one job, its call, its key
    assert spent(engine, settings) == 400000


def test_a_replayed_admission_gets_its_job_back_at_zero_and_takes_nothing_more(engine, settings, creation):
    """Round-3 fix 4: a request that took the last credit and lost its answer, sent again with its key, gets its stored
    answer before any admission check: the same job, no second credit, no 402."""
    leave(engine, 1)
    operation = key()
    id = enqueue(engine, settings, creation, operation=operation)
    assert balance(engine) == {"available": 0, "pending": 1}
    assert enqueue(engine, settings, creation, operation=operation) == id
    assert balance(engine) == {"available": 0, "pending": 1} and jobs_count(engine) == 1


def test_a_request_refused_for_want_of_credit_is_admitted_with_its_key_after_a_grant(engine, settings, creation):
    """A refusal stores nothing under its key (store.mutate): sent again after a grant, it is a first admission."""
    leave(engine, 0)
    operation = key()
    with pytest.raises(store.Refused, match="no_credit"):
        enqueue(engine, settings, creation, operation=operation)
    with write_tx(engine) as conn:
        credits.grant(conn, 1, 1, origin="offered", ref="later", actor="tests")
    id = enqueue(engine, settings, creation, operation=operation)
    assert enqueue(engine, settings, creation, operation=operation) == id
    assert balance(engine) == {"available": 0, "pending": 1} and jobs_count(engine) == 1


def test_a_job_ending_without_an_image_gives_its_credit_back_and_a_version_spends_it(engine, settings, creation, tmp_path):
    """The credit's states, one to one with the job's: it counts while the job waits or runs; a cancellation by the owner,
    by a suspension, at dispatch or at recovery, and an unknown outcome at recovery, give it back with nothing written;
    a requeue is the same job, counted once; its version spends it. Failures by the worker: the parametrised policy test."""
    def admitted():
        id = enqueue(engine, settings, creation)
        assert balance(engine) == {"available": 99, "pending": 1} and view(engine, id)["credit"] == "pending"
        return id

    def given_back(id, status):
        assert view(engine, id)["status"] == status and balance(engine) == {"available": 100, "pending": 0}
        assert view(engine, id)["credit"] == "given_back"  # what the browser says it with (D-BALANCE-006)
        with write_tx(engine) as conn:
            shops.enable(conn, 1)

    id = admitted()
    jobs.cancel(engine, 1, key(), id)
    given_back(id, "cancelled")
    id = admitted()
    suspended(engine)  # its queued jobs are cancelled
    given_back(id, "cancelled")
    id = admitted()
    jobs.claim(engine, ("scene",))
    suspended(engine)
    assert jobs.dispatch(engine, id) is None  # the cutoff
    given_back(id, "cancelled")
    id = admitted()
    jobs.claim(engine, ("scene",))
    suspended(engine)
    jobs.recover(engine, tmp_path)  # a suspended shop's unsent call
    given_back(id, "cancelled")
    id = admitted()
    jobs.claim(engine, ("scene",))
    jobs.dispatch(engine, id)
    jobs.recover(engine, tmp_path)  # sent, outcome unknown
    given_back(id, "interrupted")

    id = admitted()
    jobs.claim(engine, ("scene",))
    assert jobs.recover(engine, tmp_path) == [] and view(engine, id)["status"] == "queued"  # never sent: requeued
    assert balance(engine) == {"available": 99, "pending": 1}
    job = jobs.claim(engine, ("scene",))
    jobs.dispatch(engine, id)
    jobs.spool(tmp_path, job, {"visual": "v"}, cost_micros=170000)
    jobs.finish_spool(engine, tmp_path, id, lambda *_: "v")
    assert balance(engine) == {"available": 99, "pending": 0} and view(engine, id)["credit"] == "spent"
    with engine.connect() as conn:  # the operator's grant of the fixture: a credit back is never a line
        assert conn.execute(text("SELECT COUNT(*) FROM credit_grants")).scalar_one() == 1


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


@pytest.mark.parametrize("refusal", ["shop_daily_limit", "budget_exhausted", "shop_suspended"])
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
        elif refusal == "budget_exhausted":  # the cap; the pause does not stop a retry (the test below)
            settings.spend_cap_usd = Decimal("0.3")
        else:
            with write_tx(engine) as conn:
                conn.exec_driver_sql("UPDATE shop_profile SET state='suspended' WHERE id=1")
        raise ProviderError("rate_limited", "secret provider body")

    asyncio.run(run_job(engine, settings, job, prepare=lambda *_: {}, send=send, finalise=lambda *_: pytest.fail("finalised")))
    assert len(sent) == 1 and (view(engine, id)["status"], view(engine, id)["error_code"]) == ("failed", "rate_limited")
    assert spent(engine, settings) == 0
    with engine.connect() as conn:
        assert conn.execute(text("SELECT call_no FROM poster_calls WHERE job_id=:id"), {"id": id}).scalars().all() == [1]


def test_the_pause_refuses_every_new_request_to_the_ai_before_the_credits_and_resume_lifts_it(engine, settings, creation):
    """D-BALANCE-003, owner decision 7: paused, an image of each kind, a plan, a style and a text proposal are refused as
    the service's pause, before the credits (buying would not help), and nothing is written; a render calls no AI.
    Resume lifts it, and the credits decide again."""
    settings.planner_provider = "stub"  # estimate 0: only the pause can refuse these
    leave(engine, 0)
    with write_tx(engine) as conn:
        assert shops.pause(conn) and not shops.pause(conn)  # the second changes nothing
        assert jobs.paused(conn)
    before = written(engine)
    for kind, payload in (("scene", None), ("refine", None), ("text_texture", None), ("plan", None),
                          ("plan", {"look": "Style"}), ("text_patch", None)):
        with pytest.raises(store.Refused) as caught:
            enqueue(engine, settings, creation, kind=kind, payload=payload)
        assert (caught.value.code, caught.value.status) == ("budget_exhausted", 429), kind
    assert written(engine) == before
    enqueue(engine, settings, creation, kind="render")
    with write_tx(engine) as conn:
        assert shops.resume(conn) and not shops.resume(conn)
        assert jobs.paused(conn) is None
    with pytest.raises(store.Refused, match="no_credit"):
        enqueue(engine, settings, creation)
    leave(engine, 1)
    enqueue(engine, settings, creation)
    enqueue(engine, settings, creation, kind="plan")


def test_a_rate_limit_retry_is_reserved_and_sent_while_the_service_is_paused(engine, settings, creation):
    """D-BALANCE-003: the pause stops new requests only. A job admitted before it gets its 429 retry reserved as call 2
    and sent, and ends with its version; its one credit is spent once."""
    id = enqueue(engine, settings, creation)
    job = jobs.claim(engine, ("scene",))
    sent = []

    async def send(_):
        sent.append(1)
        if len(sent) == 1:
            with write_tx(engine) as conn:
                shops.pause(conn)
            raise ProviderError("rate_limited", "secret provider body")
        return Outcome({"visual": "saved"}, cost_micros=170000)

    asyncio.run(run_job(engine, settings, job, prepare=lambda *_: {}, send=send, finalise=lambda *_: "saved"))
    assert len(sent) == 2 and view(engine, id)["status"] == "succeeded"
    assert [call[:2] for call in calls(engine, id)] == [(1, "failed"), (2, "succeeded")]
    assert spent(engine, settings) == 170000 and balance(engine) == {"available": 99, "pending": 0}
    with pytest.raises(store.Refused, match="budget_exhausted"):  # and a new request is still refused
        enqueue(engine, settings, creation)


def test_blocked_asks_the_admissions_guard_with_each_charged_operations_own_estimate(engine, settings, creation, tmp_path, input_id):
    """D-BALANCE-003: read-only, whatever the credits. With 0.35 USD left of the shop's day, a scene (0.40) is blocked
    by the day and a text's material (0.30) is not, and is admitted; the same near the service's cap; the pause, a cap
    reached and no image provider block both."""
    def codes():
        before = written(engine)
        with engine.connect() as conn:
            answer = {kind: getattr(jobs.blocked(conn, settings, 1, kind), "code", None) for kind in jobs.CHARGED}
        assert written(engine) == before
        return answer

    assert jobs.CHARGED == ("scene", "text_texture") and codes() == {"scene": None, "text_texture": None}
    leave(engine, 0)
    assert codes() == {"scene": None, "text_texture": None}  # the credits are not blocked's to tell
    leave(engine, 2)
    settings.shop_daily_spend_usd = Decimal("0.75")
    enqueue(engine, settings, creation)  # 0.40 of the day
    assert codes() == {"scene": "shop_daily_limit", "text_texture": None}
    texture = enqueue(engine, settings, draft(engine, tmp_path, input_id), kind="text_texture")
    assert codes() == {"scene": "shop_daily_limit", "text_texture": "shop_daily_limit"}  # 0.05 left
    settings.shop_daily_spend_usd, settings.spend_cap_usd = Decimal("20"), Decimal("1.05")  # 0.70 spent
    assert codes() == {"scene": "budget_exhausted", "text_texture": None}
    settings.spend_cap_usd = Decimal("0.9")
    assert codes() == {"scene": "budget_exhausted", "text_texture": "budget_exhausted"}
    settings.spend_cap_usd = Decimal("20")
    jobs.cancel(engine, 1, key(), texture)
    with write_tx(engine) as conn:
        shops.pause(conn)
    assert codes() == {"scene": "budget_exhausted", "text_texture": "budget_exhausted"}
    with write_tx(engine) as conn:
        shops.resume(conn)
    settings.openai_api_key = None
    assert codes() == {"scene": "provider_unavailable", "text_texture": "provider_unavailable"}
    unaccepted(engine)  # the conditions first (D-TERMS-003), whatever else blocks
    assert codes() == {"scene": "terms_required", "text_texture": "terms_required"}


# --- The conditions of use at admission (D-TERMS-003). The engine fixture's shop 1 has accepted the current version. --

def test_an_unaccepted_shop_gets_no_new_request_to_the_ai_and_nothing_is_taken(engine, settings, creation):
    """R-TERMS-001: a scene, a refinement, a text's material, a background, a Claude plan, a style and a text proposal of
    a shop that has not accepted the current conditions are each refused with 403 before anything is written: no job,
    call, key, mode lock or credit line, the balance unchanged, nothing for a worker to send. A render asks no AI and is
    admitted. Accepted, the same requests are admitted, the refused key included (a refusal stores nothing under it)."""
    settings.planner_provider = "stub"
    unaccepted(engine)

    def state():
        with engine.connect() as conn:
            return [conn.execute(text(f"SELECT * FROM {table} ORDER BY 1")).all() for table in (
                "meta", "credit_grants", "poster_jobs", "poster_calls", "mutation_keys")] + [credits.balance(conn, 1)]

    before, operation = state(), key()
    for kind, payload in (("scene", None), ("refine", None), ("text_texture", None), ("background", None),
                          ("plan", None), ("plan", {"look": "Style"}), ("text_patch", None)):
        with pytest.raises(store.Refused) as caught:
            enqueue(engine, settings, creation, kind=kind, payload=payload, operation=operation if kind == "scene" else None)
        assert (caught.value.code, caught.value.status) == ("terms_required", 403), kind
    for item, revision, refusal in (({"id": key()}, 1, "not_found"), (creation, 2, "revision_conflict")):
        with pytest.raises(store.Refused) as caught:  # ownership and the revision are checked before the gate
            enqueue(engine, settings, item, revision=revision)
        assert caught.value.code == refusal
    assert state() == before and jobs.claim(engine, tuple(jobs.PROVIDER_KINDS)) is None
    enqueue(engine, settings, creation, kind="render")
    accepted(engine)
    scene = enqueue(engine, settings, creation, operation=operation)
    assert enqueue(engine, settings, creation, operation=operation) == scene
    enqueue(engine, settings, creation, kind="plan")
    assert balance(engine) == {"available": 99, "pending": 1}


def test_the_conditions_are_told_before_every_limit_and_the_credit(engine, settings, creation, tmp_path, input_id,
                                                                    monkeypatch):
    """D-TERMS-003's order: a shop that has not accepted and also meets an image running, the twelve scenes, the pause,
    the service's cap, its day or zero credit is told the conditions; accepted, the same request meets that limit.
    Nothing is written either way. A style beyond the limit is refused by its route before the gate (accepted in
    round 2), and nothing is written either."""
    settings.shop_daily_spend_usd = Decimal("20")
    full = draft(engine, tmp_path, input_id)
    for _ in range(jobs.SCENE_LIMIT):
        id = enqueue(engine, settings, full)
        job = jobs.claim(engine, ("scene",))
        jobs.dispatch(engine, id)
        jobs.spool(tmp_path, job, {"visual": key()}, cost_micros=170000)
        jobs.finish_spool(engine, tmp_path, id, lambda _conn, _job, result: result["visual"])
    enqueue(engine, settings, creation)  # an image waiting on this poster
    other = draft(engine, tmp_path, input_id)

    def told(limit, item=other):
        before = written(engine)
        for answer, expected in ((unaccepted, "terms_required"), (accepted, limit)):
            answer(engine)
            with pytest.raises(store.Refused) as caught:
                enqueue(engine, settings, item)
            assert caught.value.code == expected and written(engine) == before

    told("image_job_running", creation)
    told("attempt_limit", full)
    with write_tx(engine) as conn:
        shops.pause(conn)
    told("budget_exhausted")
    with write_tx(engine) as conn:
        shops.resume(conn)
    left = Decimal(spent(engine, settings) + 300_000) / 1_000_000  # 0.30 USD more: a scene's 0.40 does not fit
    settings.spend_cap_usd = left
    told("budget_exhausted")
    settings.spend_cap_usd, settings.shop_daily_spend_usd = Decimal("20"), left  # every call so far is shop 1's, today
    told("shop_daily_limit")
    settings.shop_daily_spend_usd = Decimal("20")
    leave(engine, 0)
    told("no_credit")

    settings.planner_provider = "stub"
    request = looks.LookRequest(name="Seul", reference_asset=store.upload(engine, tmp_path, 1, photo(), "style")["asset"])
    unaccepted(engine)
    before, limit = written(engine), looks.LOOK_LIMIT

    def style():
        with pytest.raises(store.Refused) as caught:
            looks.request_look(engine, settings, 1, key(), other["id"], other["revision"], request)
        assert written(engine) == before
        return caught.value.code, caught.value.status

    monkeypatch.setattr(looks, "LOOK_LIMIT", 0)
    assert style() == ("look_limit", 409)
    monkeypatch.setattr(looks, "LOOK_LIMIT", limit)
    assert style() == ("terms_required", 403)


def test_a_key_admitted_before_a_new_version_is_replayed_and_a_new_attempt_is_refused(engine, settings, creation,
                                                                                      monkeypatch):
    """D-TERMS-003's three cases, two of them: a key admitted before a new version of the conditions gets its stored 202
    (store.mutate replays before apply), and no new job; once that job failed, a new attempt is a new key and a new
    admission, refused until the shop accepts the new version, with nothing written and its credit back."""
    operation = key()
    id = enqueue(engine, settings, creation, operation=operation)
    monkeypatch.setattr(terms, "VERSION", "2099-01-01")  # a release with a new text: shop 1 accepted the one before
    assert enqueue(engine, settings, creation, operation=operation) == id and jobs_count(engine) == 1
    jobs.claim(engine, ("scene",))
    jobs.fail(engine, id, "provider_error", unsent=True)
    before = written(engine)
    assert before[3] == {"available": 100, "pending": 0}
    with pytest.raises(store.Refused) as caught:
        enqueue(engine, settings, creation)
    assert (caught.value.code, caught.value.status) == ("terms_required", 403) and written(engine) == before
    accepted(engine)  # the new version
    enqueue(engine, settings, creation)
    assert balance(engine) == {"available": 99, "pending": 1}


def test_a_rate_limit_retry_of_a_job_admitted_before_a_new_version_is_reserved_and_sent(engine, settings, creation,
                                                                                         monkeypatch):
    """D-TERMS-003's third case: the gate admits new requests only. A job admitted before a new version of the
    conditions gets its 429 retry reserved as call 2 (jobs._reserve: the provider's guard alone) and sent, and ends
    with its version; a new request is refused."""
    id = enqueue(engine, settings, creation)
    job = jobs.claim(engine, ("scene",))
    sent = []

    async def send(_):
        sent.append(1)
        if len(sent) == 1:
            monkeypatch.setattr(terms, "VERSION", "2099-01-01")
            raise ProviderError("rate_limited", "secret provider body")
        return Outcome({"visual": "saved"}, cost_micros=170000)

    asyncio.run(run_job(engine, settings, job, prepare=lambda *_: {}, send=send, finalise=lambda *_: "saved"))
    assert len(sent) == 2 and view(engine, id)["status"] == "succeeded"
    assert [call[:2] for call in calls(engine, id)] == [(1, "failed"), (2, "succeeded")]
    with pytest.raises(store.Refused, match="terms_required"):
        enqueue(engine, settings, creation)


def calls(engine, id):
    with engine.connect() as conn:
        return [tuple(row) for row in conn.execute(text(
            "SELECT call_no, status, cost_micros, cost_is_estimate FROM poster_calls WHERE job_id=:id ORDER BY call_no"),
            {"id": id})]


def suspended(engine, shop=1):
    with write_tx(engine) as conn:
        return shops.suspend(conn, shop)


def test_suspension_cancels_queued_jobs_at_no_cost_keeps_sessions_and_enable_reverses_it(
        engine, settings, creation, tmp_path, input_id):
    """D-MULTI-SHOP-006: the queued jobs and their reserved calls end at cost 0; a running job is left to the cutoff at
    dispatch; another shop is untouched; the sessions are kept and stop working, then work again after enable."""
    shop_b, _ = second_shop(engine)
    running = enqueue(engine, settings, creation)
    assert jobs.claim(engine, ("scene",))["id"] == running
    queued = enqueue(engine, settings, draft(engine, tmp_path, input_id))
    theirs = enqueue(engine, settings, poster_of(engine, tmp_path, shop_b), shop=shop_b)
    with write_tx(engine) as conn:
        conn.exec_driver_sql("INSERT INTO sessions VALUES (?,1,'2099-01-01T00:00:00.000000+00:00')", (auth.token_hash("t"),))
    with pytest.raises(RuntimeError), write_tx(engine) as conn:  # inside the caller's transaction: a rollback undoes it
        shops.suspend(conn, 1)
        raise RuntimeError
    assert view(engine, queued)["status"] == "queued" and auth.session_shop(engine, "t") == 1
    assert suspended(engine) == 1
    assert (view(engine, queued)["status"], view(engine, queued)["error_code"]) == ("cancelled", "shop_suspended")
    assert calls(engine, queued) == [(1, "cancelled", 0, 0)]
    assert view(engine, running)["status"] == "running" and calls(engine, running) == [(1, "reserved", 400000, 1)]
    with engine.connect() as conn:
        assert jobs.get_job(conn, shop_b, theirs)["status"] == "queued"
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM sessions").scalar_one() == 1  # kept
    assert auth.session_shop(engine, "t") is None  # but refused while suspended
    assert suspended(engine) is None  # already suspended: nothing changes
    with write_tx(engine) as conn:
        assert shops.enable(conn, 1) is True and shops.enable(conn, 1) is False
        with pytest.raises(LookupError):
            shops.suspend(conn, 99)
    assert auth.session_shop(engine, "t") == 1 and view(engine, queued)["status"] == "cancelled"  # stays cancelled


def test_a_call_reserved_before_the_suspension_is_never_sent(engine, settings, creation, monkeypatch):
    """dispatch is the cutoff: call 2 of a 429 retry, reserved before the suspension and waiting its 2 s, is released at
    cost 0 in the transaction that refuses it, and the job ends cancelled. Call 1, already sent, keeps its outcome."""
    id = enqueue(engine, settings, creation)
    job = jobs.claim(engine, ("scene",))
    sent = []

    async def send(_):
        sent.append(1)
        raise ProviderError("rate_limited", "secret provider body")

    async def wait(_seconds):
        assert calls(engine, id) == [(1, "failed", 0, 0), (2, "reserved", 400000, 1)]
        assert suspended(engine) == 0  # the job is running, not queued
    monkeypatch.setattr(worker, "asyncio", SimpleNamespace(to_thread=asyncio.to_thread, sleep=wait))
    asyncio.run(run_job(engine, settings, job, prepare=lambda *_: {}, send=send, finalise=lambda *_: pytest.fail("finalised")))
    assert len(sent) == 1
    assert (view(engine, id)["status"], view(engine, id)["error_code"]) == ("cancelled", "shop_suspended")
    assert calls(engine, id) == [(1, "failed", 0, 0), (2, "cancelled", 0, 0)] and spent(engine, settings) == 0
    with pytest.raises(store.Refused, match="invalid_job_state"):  # released once: nothing left to dispatch
        jobs.dispatch(engine, id)


def test_a_call_sent_before_the_suspension_finishes_and_its_result_is_kept(engine, settings, creation, tmp_path):
    id = enqueue(engine, settings, creation)
    job = jobs.claim(engine, ("scene",))

    async def send(_):
        suspended(engine)  # committed after dispatch: this call was already sent
        return Outcome({"visual": "kept"}, cost_micros=170000)

    asyncio.run(run_job(engine, settings, job, prepare=lambda *_: {}, send=send, finalise=lambda *_: "kept"))
    assert (view(engine, id)["status"], view(engine, id)["result_ref"]) == ("succeeded", "kept")
    assert spent(engine, settings) == 170000


def test_recovery_never_requeues_a_suspended_shops_unsent_call(engine, settings, creation, tmp_path):
    """At start-up: a running job of a suspended shop whose call was never sent is cancelled at cost 0, not requeued; an
    active shop's is requeued as before; a call already sent is interrupted as before (its outcome is unknown)."""
    shop_b, _ = second_shop(engine)
    mine = enqueue(engine, settings, creation)
    theirs = enqueue(engine, settings, poster_of(engine, tmp_path, shop_b), shop=shop_b)
    assert {jobs.claim(engine, ("scene",))["id"], jobs.claim(engine, ("scene",))["id"]} == {mine, theirs}
    suspended(engine)
    assert jobs.recover(engine, tmp_path) == []
    assert (view(engine, mine)["status"], view(engine, mine)["error_code"]) == ("cancelled", "shop_suspended")
    assert calls(engine, mine) == [(1, "cancelled", 0, 0)]
    with engine.connect() as conn:
        assert jobs.get_job(conn, shop_b, theirs)["status"] == "queued"
    assert spent(engine, settings) == 400000  # B's reservation only
    assert jobs.claim(engine, ("scene",))["id"] == theirs and jobs.claim(engine, ("scene",)) is None
    with write_tx(engine) as conn:
        shops.enable(conn, 1)
    sent = enqueue(engine, settings, creation)
    assert jobs.claim(engine, ("scene",))["id"] == sent
    jobs.dispatch(engine, sent)
    suspended(engine)
    jobs.recover(engine, tmp_path)
    assert (view(engine, sent)["status"], view(engine, sent)["error_code"]) == ("interrupted", "outcome_unknown")
    assert calls(engine, sent) == [(1, "interrupted", 400000, 1)]


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
    assert spent(engine, settings) == 400000
    with engine.connect() as conn:
        assert conn.execute(text("SELECT cost_is_estimate FROM poster_calls WHERE job_id=:id"), {"id": id}).scalar_one() == 1


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
    # One credit for the job, a 429 retry included: spent by its version, given back by any other end.
    assert balance(engine) == {"available": 99 if expected == "succeeded" else 100, "pending": 0}


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
