"""The prepaid balance (D-BALANCE-001, 002, 005): migration 0014's rules and 0015's (a shop is never replaced), each
proven by a statement the database itself refuses, the module's functions, and the guards on a fresh database."""
import sqlite3
from types import SimpleNamespace

import pytest
from sqlalchemy import exc

from affiche import rehearse
from affiche.db import write_tx
from affiche.posters import credits
from affiche.posters.store import Refused
from test_db import bare_engine, engine  # noqa: F401

T = "2026-11-16T10:00:00.000000+00:00"
FINAL = ("succeeded", "failed", "interrupted", "cancelled")
STATUSES = ("queued", "running") + FINAL
CASE_RULE = r"CHECK constraint failed: COALESCE\(CASE kind"
ONE_PAYMENT = "this payment is already counted in another shop"
PAYMENT_TOTAL = "a payment's corrected total must stay positive, or a reversal must bring it to zero"
FINAL_JOB = "a finished job never changes status, and no job changes what it costs"
COLUMNS = "shop_id,kind,origin,credits,amount_ar,method,ref,job_id,note,actor,created_at"
JOB_COLUMNS = "id,shop_id,creation_id,origin_revision,input_id,kind,input_json,input_hash,status,created_at"


@pytest.fixture
def db(bare_engine):
    """Shop 1 (originalphone), shop 2 and shop 3, no line, no job."""
    with write_tx(bare_engine) as conn:
        for identifier in ("shopdeux", "shoptrois"):
            conn.exec_driver_sql("INSERT INTO shop_profile (revision,updated_at,identifier,state,created_at)"
                                 f" VALUES (1,'{T}',?,'active','{T}')", (identifier,))
        conn.exec_driver_sql(f"INSERT INTO product_inputs VALUES ('in1',1,'P1','JBL','Bleu','[]','{{}}',NULL,'{T}')")
    return bare_engine


def job(conn, id, status="queued", *, shop=1, takes=1):
    """A scene job on a poster of its own (one image job per poster at a time)."""
    conn.exec_driver_sql(f"INSERT INTO creations VALUES (?,?,NULL,1,'active','{T}','{T}')", (id, shop))
    conn.exec_driver_sql(f"INSERT INTO creation_versions VALUES (?,1,'{{}}','h','{T}')", (id,))
    conn.exec_driver_sql("INSERT INTO poster_jobs (id,shop_id,creation_id,origin_revision,input_id,kind,input_json,"
                         f"input_hash,status,created_at,takes_credit) VALUES (?,?,?,1,'in1','scene','{{}}','h',?,'{T}',?)",
                         (id, shop, id, status, takes))


def line(conn, shop=1, kind="grant", origin="offered", credits=10, amount=None, method=None, ref="r", job=None,
         note=None):
    """A line written straight into the table, as no function of the module would: only the database refuses it."""
    conn.exec_driver_sql(f"INSERT INTO credit_grants ({COLUMNS}) VALUES (?,?,?,?,?,?,?,?,?,'operator','{T}')",
                         (shop, kind, origin, credits, amount, method, ref, job, note))


def paid(conn, shop=1, ref="MV1", amount=1000, credits=10):
    line(conn, shop, origin="bought", credits=credits, amount=amount, method="mvola", ref=ref)


def fix(shop, amount, ref="MV1", credits=0):
    return dict(shop=shop, kind="correction", origin=None, credits=credits, amount=amount, ref=ref, note="montant")


def refused(engine, match, write):
    with pytest.raises(exc.IntegrityError, match=match), write_tx(engine) as conn:
        write(conn)


def rows(engine, sql):
    with engine.connect() as conn:
        return conn.exec_driver_sql(sql).all()


# A writer outside the application, on a connection of its own: the sqlite3 shell's defaults, the application's foreign
# keys, and recursive triggers (with which a REPLACE's implicit delete fires the DELETE triggers).
WRITERS = {"shell": (), "foreign keys": ("PRAGMA foreign_keys = ON",),
           "recursive triggers": ("PRAGMA foreign_keys = ON", "PRAGMA recursive_triggers = ON"),
           "recursive triggers alone": ("PRAGMA recursive_triggers = ON",)}


def outside(engine, writer, statement):
    db = sqlite3.connect(engine.url.database, isolation_level=None)
    try:
        for pragma in WRITERS[writer]:
            db.execute(pragma)
        db.execute(statement)
    finally:
        db.close()


# --- 0014's rules, refused by the database -----------------------------------------------------------------------

def test_a_job_takes_no_credit_unless_its_insert_says_so(db):
    with write_tx(db) as conn:
        job(conn, "counted")
        conn.exec_driver_sql("INSERT INTO creations VALUES ('old',1,NULL,1,'active',?,?)", (T, T))
        conn.exec_driver_sql(f"INSERT INTO creation_versions VALUES ('old',1,'{{}}','h','{T}')")
        conn.exec_driver_sql("INSERT INTO poster_jobs (id,shop_id,creation_id,origin_revision,input_id,kind,input_json,"
                             f"input_hash,status,created_at) VALUES ('old',1,'old',1,'in1','scene','{{}}','h','queued','{T}')")
    assert rows(db, "SELECT id, takes_credit FROM poster_jobs ORDER BY id") == [("counted", 1), ("old", 0)]
    refused(db, r"CHECK constraint failed: takes_credit IN \(0, 1\)", lambda conn: job(conn, "two", takes=2))
    refused(db, "NOT NULL constraint failed: poster_jobs.takes_credit", lambda conn: job(conn, "none", takes=None))


@pytest.mark.parametrize("values, rule", [  # what the rule table says each one stops
    (dict(credits=0), CASE_RULE),  # a grant of zero credits
    (dict(credits=-3), CASE_RULE),  # a grant of fewer
    (dict(credits=1.5), r"typeof\(credits\) = 'integer'"),  # a fraction of a credit (an INTEGER column keeps 1.5)
    (dict(origin="bought", amount=1000.5, method="mvola"), r"typeof\(amount_ar\) = 'integer'"),  # of an ariary
    (dict(origin="bought", amount=0, method="mvola"), "amount_ar <> 0"),
    (dict(origin="bought", method="mvola"), CASE_RULE),  # a bought grant without amount: the NULL in the CASE
    (dict(origin="bought", amount=1000), CASE_RULE),  # without method
    (dict(origin="bought", amount=-1000, method="mvola"), CASE_RULE),
    (dict(amount=1000), CASE_RULE),  # an offered grant with an amount
    (dict(method="mvola"), CASE_RULE),  # with a method
    (dict(origin=None), CASE_RULE),  # a grant that is neither
    (dict(job="paid"), CASE_RULE),  # a grant naming a job
    (dict(kind="correction", origin=None, credits=-1), CASE_RULE),  # a correction without its reason
    (dict(kind="correction", origin=None, credits=0, note="rien"), CASE_RULE),  # with nothing in it
    (dict(kind="correction", credits=1, note="n"), CASE_RULE),  # with an origin
    (dict(kind="correction", origin=None, credits=1, method="mvola", note="n"), CASE_RULE),  # with a method
    (dict(kind="correction", origin=None, credits=2, job="paid", note="n"), CASE_RULE),  # a repayment other than +1
    (dict(kind="correction", origin=None, credits=-1, job="paid", note="n"), CASE_RULE),
    # A repayment with money; its reversal's amount lets credit_grants_payment_total pass, so the CASE is what refuses.
    (dict(kind="correction", origin=None, credits=1, amount=-1000, ref="MV1", job="paid", note="n"), CASE_RULE),
])
def test_the_database_refuses_a_line_that_breaks_a_rule(db, values, rule):
    with write_tx(db) as conn:
        job(conn, "paid", "succeeded")
        paid(conn)
    refused(db, rule, lambda conn: line(conn, **values))
    assert rows(db, "SELECT count(*) FROM credit_grants") == [(1,)]


@pytest.mark.parametrize("dropped, by_reference, by_job", [
    (False, "a credit line is never replaced", "a credit line is never replaced"),
    # Under the trigger, the unique keys still refuse a plain INSERT (the trigger dropped, as no real path can).
    (True, "UNIQUE constraint failed: credit_grants.shop_id, credit_grants.kind, credit_grants.ref",
     "UNIQUE constraint failed: credit_grants.job_id")])
def test_a_reference_is_used_once_per_shop_and_kind_and_a_job_is_repaid_once(db, dropped, by_reference, by_job):
    with write_tx(db) as conn:
        job(conn, "paid", "succeeded")
        line(conn, ref="welcome")
        line(conn, kind="correction", origin=None, credits=-2, ref="welcome", note="trop")  # a grant and its correction
        line(conn, shop=2, ref="welcome")  # another shop's own reference
        line(conn, kind="correction", origin=None, credits=1, ref="defaut-1", job="paid", note="image floue")
        if dropped:
            conn.exec_driver_sql("DROP TRIGGER credit_grants_never_replaced")
    refused(db, by_reference, lambda conn: line(conn, ref="welcome"))  # a grant typed twice
    refused(db, by_reference, lambda conn: line(conn, kind="correction", origin=None, credits=1, ref="welcome", note="n"))
    refused(db, by_job,
            lambda conn: line(conn, kind="correction", origin=None, credits=1, ref="defaut-2", job="paid", note="n"))


@pytest.mark.parametrize("statement, rule", [("UPDATE credit_grants SET credits=100", "a credit line is never changed"),
                                             ("UPDATE credit_grants SET note='autre'", "a credit line is never changed"),
                                             ("DELETE FROM credit_grants", "a credit line is never removed")])
def test_a_line_is_never_changed_or_removed(db, statement, rule):
    with write_tx(db) as conn:
        line(conn, ref="welcome", note="bienvenue")
    refused(db, rule, lambda conn: conn.exec_driver_sql(statement))
    assert rows(db, "SELECT credits, note FROM credit_grants") == [(10, "bienvenue")]


def ledger(engine):
    with write_tx(engine) as conn:
        job(conn, "paid", "succeeded")
        line(conn, ref="welcome")  # line 1
        paid(conn)  # line 2: 1,000 Ar under MV1
        line(conn, **fix(1, -400))  # line 3: its total 600
        line(conn, kind="correction", origin=None, credits=1, ref="defaut-1", job="paid", note="floue")  # line 4
    return rows(engine, "SELECT * FROM credit_grants ORDER BY id")


@pytest.mark.parametrize("writer", WRITERS)
@pytest.mark.parametrize("statement, rule", [
    (f"INSERT OR REPLACE INTO credit_grants ({COLUMNS}) VALUES (1,'grant','offered',99,NULL,NULL,'welcome',NULL,NULL,"
     f"'operator','{T}')", "a credit line is never replaced"),  # the same (shop, kind, reference)
    # The payment's grant replaced by 100 Ar under its 600 Ar total: -300 Ar, past both payment triggers.
    (f"REPLACE INTO credit_grants ({COLUMNS}) VALUES (1,'grant','bought',10,100,'mvola','MV1',NULL,NULL,'operator','{T}')",
     "a credit line is never replaced"),
    (f"INSERT OR REPLACE INTO credit_grants ({COLUMNS}) VALUES (1,'correction',NULL,1,NULL,NULL,'defaut-2','paid','encore',"
     f"'operator','{T}')", "a credit line is never replaced"),  # the same repaid job
    (f"INSERT OR REPLACE INTO credit_grants (id,{COLUMNS}) VALUES (1,1,'grant','offered',99,NULL,NULL,'neuf',NULL,NULL,"
     f"'operator','{T}')", "a credit line is never replaced"),  # the same id only
    (f"INSERT OR REPLACE INTO credit_grants ({COLUMNS}) VALUES (2,'grant','offered',5,NULL,NULL,'deux',NULL,NULL,"
     f"'operator','{T}'), (2,'grant','offered',99,NULL,NULL,'deux',NULL,NULL,'operator','{T}')",
     "a credit line is never replaced"),  # two rows of one statement: the second sees the first
    (f"INSERT INTO credit_grants ({COLUMNS}) VALUES (1,'grant','offered',99,NULL,NULL,'welcome',NULL,NULL,'operator','{T}')"
     " ON CONFLICT DO UPDATE SET credits=99", "a credit line is never replaced"),
    ("UPDATE OR REPLACE credit_grants SET ref='MV1' WHERE id=4", "a credit line is never changed"),
])
def test_a_credit_line_is_never_replaced_whatever_the_conflict_clause_or_the_writer(db, statement, rule, writer):
    before = ledger(db)
    with pytest.raises(sqlite3.IntegrityError, match=rule):
        outside(db, writer, statement)
    assert rows(db, "SELECT * FROM credit_grants ORDER BY id") == before
    assert rows(db, "SELECT SUM(amount_ar) FROM credit_grants WHERE ref='MV1'") == [(600,)]


def jobs_with_a_call(engine):
    with write_tx(engine) as conn:
        line(conn, credits=10, ref="welcome")
        job(conn, "done", "succeeded")  # counted, with its call
        conn.exec_driver_sql("INSERT INTO poster_calls (id,job_id,call_no,provider,model,rate_card_json,status,cost_micros,"
                             f"cost_is_estimate,created_at) VALUES ('call','done',1,'stub','m','{{}}','succeeded',0,0,'{T}')")
        job(conn, "bare", "succeeded")  # counted, no call
        job(conn, "waiting")  # counted and queued: poster_one_image holds its poster
        job(conn, "moving", takes=0)  # queued on its own poster, takes no credit
        job(conn, "lost", "failed")  # its credit is back
        assert credits.balance(conn, 1) == {"available": 7, "pending": 1}


def job_rows(engine):
    return rows(engine, "SELECT rowid, id, shop_id, creation_id, kind, status, takes_credit FROM poster_jobs ORDER BY id")


@pytest.mark.parametrize("writer", WRITERS)
@pytest.mark.parametrize("statement, rule", [
    (f"INSERT OR REPLACE INTO poster_jobs ({JOB_COLUMNS}) VALUES ('done',1,'done',1,'in1','scene','{{}}','h','queued','{T}')",
     "a job is never replaced"),  # by its id, with a call: succeeded and counted becomes queued and free
    (f"INSERT OR REPLACE INTO poster_jobs ({JOB_COLUMNS}) VALUES ('bare',1,'bare',1,'in1','scene','{{}}','h','queued','{T}')",
     "a job is never replaced"),  # by its id, no call
    (f"INSERT OR REPLACE INTO poster_jobs (rowid,{JOB_COLUMNS}) VALUES ((SELECT rowid FROM poster_jobs WHERE id='bare'),"
     f"'new',1,'lost',1,'in1','render','{{}}','h','succeeded','{T}')", "a job is never replaced"),  # by its rowid only
    (f"INSERT OR REPLACE INTO poster_jobs ({JOB_COLUMNS}) VALUES ('new',1,'waiting',1,'in1','scene','{{}}','h','queued','{T}')",
     "a job is never replaced"),  # another job's row, through poster_one_image
    ("DELETE FROM poster_jobs WHERE id='done'", "a job is never removed"),
    ("DELETE FROM poster_jobs WHERE id='bare'", "a job is never removed"),
    ("DELETE FROM poster_jobs", "a job is never removed"),
    ("UPDATE OR REPLACE poster_jobs SET id='bare' WHERE id='lost'", "a job stays the same job"),
    ("UPDATE OR REPLACE poster_jobs SET rowid=(SELECT rowid FROM poster_jobs WHERE id='bare') WHERE id='lost'",
     "a job stays the same job"),
    ("UPDATE OR REPLACE poster_jobs SET creation_id='waiting' WHERE id='moving'", "a job stays the same job"),
    ("UPDATE OR REPLACE poster_jobs SET kind='render' WHERE id='done'", "a job stays the same job"),
    ("UPDATE poster_jobs SET shop_id=2 WHERE id='done'", "a job stays the same job"),  # its credit to another shop
])
def test_a_job_is_never_removed_replaced_or_made_another_whatever_the_writer(db, statement, rule, writer):
    jobs_with_a_call(db)
    before = job_rows(db)
    with pytest.raises(sqlite3.IntegrityError, match=rule):
        outside(db, writer, statement)
    assert job_rows(db) == before and rows(db, "SELECT job_id FROM poster_calls") == [("done",)]
    with db.connect() as conn:
        assert [credits.balance(conn, shop) for shop in (1, 2)] == [{"available": 7, "pending": 1},
                                                                    {"available": 0, "pending": 0}]


def shops_with_credits(engine):
    with write_tx(engine) as conn:
        line(conn, shop=1, ref="welcome")
        job(conn, "one", "succeeded")
        line(conn, shop=2, credits=5, ref="welcome")
        job(conn, "two", "succeeded", shop=2)


def shop_state(engine):
    with engine.connect() as conn:
        return (conn.exec_driver_sql("SELECT rowid, * FROM shop_profile ORDER BY rowid").all(),
                [credits.balance(conn, shop) for shop in (1, 2, 3)])


SHOP_COLUMNS = "revision,updated_at,identifier,state,created_at"
NEVER_REPLACED = "a shop is never replaced"
SAME_SHOP = "a shop stays the same shop"


@pytest.mark.parametrize("writer", WRITERS)
@pytest.mark.parametrize("statement, rule", [
    # The bypass reproduced in review: a new identifier at shop 1's id takes its posters, jobs and credits.
    (f"INSERT OR REPLACE INTO shop_profile (id,{SHOP_COLUMNS}) VALUES (1,1,'{T}','intrus','active','{T}')", NEVER_REPLACED),
    (f"REPLACE INTO shop_profile (id,{SHOP_COLUMNS}) VALUES (2,1,'{T}','shopdeux','active','{T}')",
     NEVER_REPLACED),  # the same shop written again: its password and name gone
    (f"INSERT OR REPLACE INTO shop_profile (rowid,{SHOP_COLUMNS}) VALUES (2,1,'{T}','intrus','active','{T}')",
     NEVER_REPLACED),  # by its rowid
    (f"INSERT OR REPLACE INTO shop_profile ({SHOP_COLUMNS}) VALUES (1,'{T}','shopdeux','active','{T}')",
     NEVER_REPLACED),  # by its identifier: shop 2's row goes, its jobs and lines belong to no shop
    (f"INSERT OR REPLACE INTO shop_profile (id,{SHOP_COLUMNS}) VALUES (3,1,'{T}','shopdeux','active','{T}')",
     NEVER_REPLACED),  # the id of one, the identifier of another: both rows go
    (f"INSERT OR REPLACE INTO shop_profile ({SHOP_COLUMNS}) VALUES (1,'{T}','neuf','active','{T}'),"
     f" (1,'{T}','neuf','suspended','{T}')", NEVER_REPLACED),  # two rows of one statement: the second sees the first
    (f"INSERT INTO shop_profile (id,{SHOP_COLUMNS}) VALUES (1,1,'{T}','intrus','active','{T}')"
     " ON CONFLICT (id) DO UPDATE SET identifier=excluded.identifier", NEVER_REPLACED),
    (f"INSERT INTO shop_profile ({SHOP_COLUMNS}) VALUES (1,'{T}','shopdeux','active','{T}')"
     " ON CONFLICT (identifier) DO UPDATE SET id=9", NEVER_REPLACED),
    (f"INSERT OR REPLACE INTO shop_profile (id,{SHOP_COLUMNS}) SELECT 1,revision,updated_at,'intrus',state,created_at"
     " FROM shop_profile WHERE id=2", NEVER_REPLACED),  # from a SELECT
    ("UPDATE shop_profile SET id=-1 WHERE id=2", SAME_SHOP),
    ("UPDATE shop_profile SET id=9 WHERE id=2", SAME_SHOP),  # with foreign keys off, its jobs and lines stay behind
    ("UPDATE shop_profile SET rowid=9 WHERE id=2", SAME_SHOP),
    ("UPDATE OR REPLACE shop_profile SET id=1 WHERE id=2", SAME_SHOP),  # shop 1's row goes, its credits are shop 2's
    ("UPDATE OR REPLACE shop_profile SET identifier='originalphone' WHERE id=2", SAME_SHOP),  # shop 1's row goes
    ("UPDATE shop_profile SET identifier='originalphone' WHERE id=2", SAME_SHOP),  # before the UNIQUE key's refusal
    ("DELETE FROM shop_profile WHERE id=2", "shop cannot be deleted"),  # 0013's keep_shop
])
def test_a_shop_is_never_removed_replaced_or_made_another_whatever_the_writer(db, statement, rule, writer):
    shops_with_credits(db)
    before = shop_state(db)
    assert before[1] == [{"available": 9, "pending": 0}, {"available": 4, "pending": 0}, {"available": 0, "pending": 0}]
    with pytest.raises(sqlite3.IntegrityError, match=rule):
        outside(db, writer, statement)
    assert shop_state(db) == before


def test_a_shop_written_by_hand_at_id_minus_one_refuses_every_later_creation(db):
    """The accepted boundary: an automatic id reads -1 in a BEFORE INSERT trigger. Failed closed, never a replacement."""
    outside(db, "shell", f"INSERT INTO shop_profile (id,{SHOP_COLUMNS}) VALUES (-1,1,'{T}','moinsun','active','{T}')")
    with pytest.raises(sqlite3.IntegrityError, match=NEVER_REPLACED):
        outside(db, "shell", f"INSERT INTO shop_profile ({SHOP_COLUMNS}) VALUES (1,'{T}','suivant','active','{T}')")


def test_a_shop_may_take_a_free_identifier_and_stays_the_same_shop(db):
    # The multi-shop design leaves the pilot's identifier to a later migration: a rename keeps its id and credits.
    shops_with_credits(db)
    before = shop_state(db)
    with write_tx(db) as conn:
        conn.exec_driver_sql("UPDATE shop_profile SET identifier='shopdeux' WHERE id=2")  # unchanged
        conn.exec_driver_sql("UPDATE shop_profile SET identifier='boutiquedeux' WHERE id=2")
    after = shop_state(db)
    assert [row[:5] for row in after[0]] == [row[:5] for row in before[0]]  # rowid, id, revision, name, contact
    assert [row.identifier for row in after[0]] == ["originalphone", "boutiquedeux", "shoptrois"]
    assert after[1] == before[1]


def test_the_replacement_guards_cover_every_unique_key_of_their_tables(engine):
    # REPLACE deletes the row that collides on any unique key: a later one must join its table's never_replaced trigger.
    with engine.connect() as conn:
        keys = {table: sorted((tuple(conn.exec_driver_sql(f"SELECT name FROM pragma_index_info('{index}')").scalars()), partial)
                              for index, partial in conn.exec_driver_sql(
                                  f"SELECT name, partial FROM pragma_index_list('{table}') WHERE \"unique\"").all())
                for table in ("credit_grants", "poster_jobs", "shop_profile")}
        one_image = conn.exec_driver_sql("SELECT sql FROM sqlite_master WHERE name='poster_one_image'").scalar_one()
    assert keys == {"credit_grants": [(("job_id",), 0), (("shop_id", "kind", "ref"), 0)],  # and id, the rowid
                    "poster_jobs": [(("creation_id",), 1), (("id",), 0)],  # and the rowid
                    "shop_profile": [(("identifier",), 0)]}  # and id, the rowid
    assert " ".join(one_image.split()).endswith(  # the predicate poster_jobs_never_replaced repeats
        "WHERE kind IN ('scene','refine','text_texture','background') AND status IN ('queued','running')")


def test_a_payment_counts_in_one_shop_at_a_time(db):
    with write_tx(db) as conn:
        paid(conn, 1)
    refused(db, ONE_PAYMENT, lambda conn: paid(conn, 2))  # granted to a second shop
    with write_tx(db) as conn:
        line(conn, shop=3, ref="MV1")  # an offered grant under the same reference counts no money
        line(conn, **fix(1, -1000, credits=-10))  # moved: the reversal, then the grant passes
        paid(conn, 2)
        paid(conn, 1, ref="MV2", amount=500)
        line(conn, **fix(1, 300, ref="MV2"))  # a mistyped amount fixed upwards in its own shop
    assert rows(db, "SELECT shop_id, ref, SUM(amount_ar) FROM credit_grants GROUP BY shop_id, ref") == [
        (1, "MV1", 0), (1, "MV2", 800), (2, "MV1", 1000), (3, "MV1", None)]


def test_a_payment_moved_along_a_chain_is_counted_once(db):
    with write_tx(db) as conn:
        paid(conn, 1)
        for source, destination in ((1, 2), (2, 3)):  # A to B to C, each move reversal first
            line(conn, **fix(source, -1000, credits=-10))
            paid(conn, destination)
    assert rows(db, "SELECT SUM(amount_ar) FROM credit_grants WHERE amount_ar > 0") == [(3000,)]  # receipts
    assert rows(db, "SELECT shop_id, SUM(amount_ar) FROM credit_grants GROUP BY shop_id") == [(1, 0), (2, 0), (3, 1000)]
    refused(db, PAYMENT_TOTAL, lambda conn: line(conn, **fix(3, -400, credits=-10)))  # a partial reversal
    # A fix where the payment was moved away: that shop's one correction under the reference is the reversal already.
    refused(db, "a credit line is never replaced", lambda conn: line(conn, **fix(1, 200)))


def test_an_amount_fix_keeps_the_payment_above_zero(db):
    with write_tx(db) as conn:
        paid(conn)
    for amount in (-1000, -2000):  # erased, negated
        refused(db, PAYMENT_TOTAL, lambda conn: line(conn, **fix(1, amount)))
    refused(db, PAYMENT_TOTAL, lambda conn: line(conn, **fix(1, 100, ref="none")))  # an amount without a payment
    refused(db, PAYMENT_TOTAL, lambda conn: line(conn, **fix(1, -100, ref="none", credits=-1)))
    with write_tx(db) as conn:
        line(conn, **fix(1, -400))
    assert rows(db, "SELECT SUM(amount_ar) FROM credit_grants") == [(600,)]


def test_a_negative_total_in_one_shop_does_not_hide_a_positive_one_in_another(db):
    with write_tx(db) as conn:
        paid(conn, 2)
        conn.exec_driver_sql("DROP TRIGGER credit_grants_payment_total")  # no real path can write the next line
        line(conn, **fix(1, -2000))
    assert rows(db, "SELECT shop_id, SUM(amount_ar) FROM credit_grants GROUP BY shop_id") == [(1, -2000), (2, 1000)]
    refused(db, ONE_PAYMENT, lambda conn: paid(conn, 3))  # one sum over the other shops would read -1000 and pass


@pytest.mark.parametrize("new", STATUSES)
@pytest.mark.parametrize("old", FINAL)
def test_a_finished_job_never_changes_status(db, old, new):
    with write_tx(db) as conn:
        job(conn, "done", old)
    def update(conn):
        conn.exec_driver_sql("UPDATE poster_jobs SET status=?, finished_at=? WHERE id='done'", (new, T))

    if new == old:  # the same final status written again
        with write_tx(db) as conn:
            update(conn)
    else:
        refused(db, FINAL_JOB, update)
    assert rows(db, "SELECT status FROM poster_jobs") == [(old,)]


@pytest.mark.parametrize("status", STATUSES)
def test_no_job_changes_what_it_costs(db, status):
    with write_tx(db) as conn:
        job(conn, "counted", status)
        job(conn, "free", status, takes=0)
        conn.exec_driver_sql("UPDATE poster_jobs SET takes_credit=takes_credit")  # unchanged: allowed
    refused(db, FINAL_JOB, lambda conn: conn.exec_driver_sql("UPDATE poster_jobs SET takes_credit=0 WHERE id='counted'"))
    refused(db, FINAL_JOB, lambda conn: conn.exec_driver_sql("UPDATE poster_jobs SET takes_credit=1 WHERE id='free'"))
    assert rows(db, "SELECT id, takes_credit FROM poster_jobs ORDER BY id") == [("counted", 1), ("free", 0)]


def test_a_job_waits_runs_is_requeued_and_ends_counted_once_with_nothing_written(db):
    with write_tx(db) as conn:
        line(conn, credits=2, ref="welcome")
        job(conn, "a")
        steps = [("running", 1, 1), ("queued", 1, 1), ("running", 1, 1), ("succeeded", 1, 0)]  # recover's requeue
        for status, available, pending in steps:
            conn.exec_driver_sql("UPDATE poster_jobs SET status=? WHERE id='a'", (status,))
            assert credits.balance(conn, 1) == {"available": available, "pending": pending}
        job(conn, "b")
        assert credits.balance(conn, 1) == {"available": 0, "pending": 1}
        conn.exec_driver_sql("UPDATE poster_jobs SET status='cancelled' WHERE id='b'")
        assert credits.balance(conn, 1) == {"available": 1, "pending": 0}  # given back
        # Other columns of a finished job may still change (tests rewrite input_json).
        conn.exec_driver_sql("UPDATE poster_jobs SET input_json='{\"n\":1}', result_ref='v1' WHERE id='a'")
    assert rows(db, "SELECT count(*) FROM credit_grants") == [(1,)]


@pytest.mark.parametrize("status, available, pending", [
    ("queued", 9, 1), ("running", 9, 1), ("succeeded", 9, 0), ("failed", 10, 0), ("interrupted", 10, 0),
    ("cancelled", 10, 0)])
def test_the_balance_counts_a_job_while_it_waits_runs_or_has_made_its_image(db, status, available, pending):
    with write_tx(db) as conn:
        line(conn, credits=10, ref="welcome")
        job(conn, "counted", status)
        job(conn, "free", status, takes=0)  # takes no credit: never counts
        job(conn, "theirs", status, shop=2)  # another shop's
        assert credits.balance(conn, 1) == {"available": available, "pending": pending}
        assert credits.balance(conn, 2) == {"available": available - 10, "pending": pending}
        assert credits.balance(conn, 3) == {"available": 0, "pending": 0}


# --- The module's functions --------------------------------------------------------------------------------------

def test_require_refuses_once_the_counted_jobs_pass_the_grants(db):
    with write_tx(db) as conn:
        credits.require(conn, 1)  # nothing granted, nothing counted
        line(conn, credits=1, ref="welcome")
        job(conn, "last")
        credits.require(conn, 1)  # the job that took the last credit
        job(conn, "one-too-many")
        with pytest.raises(Refused) as no_credit:
            credits.require(conn, 1)
    assert (no_credit.value.code, no_credit.value.status) == ("no_credit", 402)


def test_grants_offered_and_bought_and_what_they_refuse(db):
    with write_tx(db) as conn:
        assert credits.grant(conn, 1, 5, origin="offered", ref="welcome", actor="operator",
                             note="Crédits de bienvenue") == 1
        assert credits.grant(conn, 1, 10, origin="bought", ref="MV-1", actor="operator", amount_ar=10000,
                             method="MVola") == 2
        assert credits.balance(conn, 1) == {"available": 15, "pending": 0}
    assert rows(db, "SELECT origin, amount_ar, method, note FROM credit_grants ORDER BY id") == [
        ("offered", None, None, "Crédits de bienvenue"), ("bought", 10000, "mvola", None)]
    for shop, count, kwargs, match in (
            (1, 0, dict(origin="offered", ref="x"), "1 credit or more"),
            (1, 1.5, dict(origin="offered", ref="x"), "1 credit or more"),
            (1, 1, dict(origin="bought", ref="x", method="mvola"), "amount in ariary and its payment method"),
            (1, 1, dict(origin="bought", ref="x", amount_ar=100), "amount in ariary and its payment method"),
            (1, 1, dict(origin="bought", ref="x", amount_ar=-100, method="cash"), "amount in ariary"),
            (1, 1, dict(origin="offered", ref="x", amount_ar=100), "offered .no amount, no method. or bought"),
            (1, 1, dict(origin="gift", ref="x"), "offered .no amount, no method. or bought"),
            (1, 1, dict(origin="offered", ref="welcome"), r"already has a grant with the reference 'welcome' \(line 1\)"),
            (2, 10, dict(origin="bought", ref="MV-1", amount_ar=10000, method="mvola"),
             r"'MV-1' is already recorded in shop originalphone \(line 2\): a payment changes shop only by move-payment")):
        with pytest.raises(ValueError, match=match), write_tx(db) as conn:
            credits.grant(conn, shop, count, actor="operator", **kwargs)
    with write_tx(db) as conn:
        credits.grant(conn, 2, 3, origin="offered", ref="MV-1", actor="operator")  # an offered grant: no money
    assert rows(db, "SELECT count(*) FROM credit_grants") == [(3,)]


def test_a_payment_moves_whole_once_its_credits_are_unspent_and_never_back(db):
    with write_tx(db) as conn:
        credits.grant(conn, 1, 10, origin="bought", ref="MV-1", actor="operator", amount_ar=10000, method="mvola")
        assert credits.move(conn, "MV-1", 1, 2, "operator", "mauvaise boutique") == (2, 3)  # the reversal first
        assert [credits.balance(conn, shop)["available"] for shop in (1, 2)] == [0, 10]
    assert rows(db, "SELECT shop_id, kind, origin, credits, amount_ar, method, ref, note FROM credit_grants ORDER BY id") == [
        (1, "grant", "bought", 10, 10000, "mvola", "MV-1", None),
        (1, "correction", None, -10, -10000, None, "MV-1", "mauvaise boutique"),
        (2, "grant", "bought", 10, 10000, "mvola", "MV-1", "mauvaise boutique")]
    for args, match in ((("MV-1", 2, 1), "destination shop already has a line"),  # back where it was
                        (("MV-1", 1, 3), "already moved or corrected in the source shop"),
                        (("MV-1", 2, 2), "moves to another shop"),
                        (("MV-9", 2, 3), "no bought grant with the reference 'MV-9'")):
        with pytest.raises(ValueError, match=match), write_tx(db) as conn:
            credits.move(conn, *args, "operator", "encore")
    with pytest.raises(ValueError, match="needs its reason"), write_tx(db) as conn:
        credits.move(conn, "MV-1", 2, 3, "operator", None)
    for shop, match in ((1, "already has a grant"), (3, "already recorded in shop originalphone")):  # only a move
        with pytest.raises(ValueError, match=match), write_tx(db) as conn:
            credits.grant(conn, shop, 10, origin="bought", ref="MV-1", actor="operator", amount_ar=10000, method="mvola")
    with write_tx(db) as conn:
        credits.move(conn, "MV-1", 2, 3, "operator", "encore")  # on to a third shop: the first one's total is 0
        assert [credits.balance(conn, shop)["available"] for shop in (1, 2, 3)] == [0, 0, 10]
    assert rows(db, "SELECT SUM(amount_ar) FROM credit_grants") == [(10000,)]


def test_a_payment_whose_credits_are_spent_stays_where_it_is(db):
    with write_tx(db) as conn:
        credits.grant(conn, 1, 10, origin="bought", ref="MV-1", actor="operator", amount_ar=10000, method="mvola")
        job(conn, "spent")
    with pytest.raises(ValueError, match="has 9 credits left of the payment's 10: it stays where it is"), \
            write_tx(db) as conn:
        credits.move(conn, "MV-1", 1, 2, "operator", "mauvaise boutique")
    assert rows(db, "SELECT count(*) FROM credit_grants") == [(1,)]


def test_a_move_interrupted_between_its_two_writes_leaves_neither(db):
    with write_tx(db) as conn:
        credits.grant(conn, 1, 10, origin="bought", ref="MV-1", actor="operator", amount_ar=10000, method="mvola")
    with pytest.raises(exc.IntegrityError, match="FOREIGN KEY"), write_tx(db) as conn:
        credits.move(conn, "MV-1", 1, 99, "operator", "aucune boutique 99")  # the grant fails after the reversal
    assert rows(db, "SELECT kind FROM credit_grants") == [("grant",)]


def test_a_job_is_repaid_once_and_only_when_it_made_its_image_and_took_a_credit(db):
    with write_tx(db) as conn:
        line(conn, credits=5, ref="welcome")
        for id, status, shop, takes in (("made", "succeeded", 1, 1), ("failed", "failed", 1, 1),
                                        ("free", "succeeded", 1, 0), ("theirs", "succeeded", 2, 1)):
            job(conn, id, status, shop=shop, takes=takes)
        assert credits.correct(conn, 1, 1, ref="defaut-1", note="produit déformé", actor="operator", job_id="made") == 2
        assert credits.balance(conn, 1)["available"] == 5
    for job_id, count, amount, match in (("failed", 1, None, "only a succeeded job of this shop that took a credit"),
                                         ("free", 1, None, "only a succeeded job"),
                                         ("theirs", 1, None, "only a succeeded job"),
                                         ("missing", 1, None, "only a succeeded job"),
                                         ("made", 1, None, r"already repaid \(line 2\)"),
                                         ("made", 2, None, "exactly 1 credit and no amount"),
                                         ("made", 1, 100, "exactly 1 credit and no amount")):
        with pytest.raises(ValueError, match=match), write_tx(db) as conn:
            credits.correct(conn, 1, count, ref="defaut-2", note="encore", actor="operator", amount_ar=amount,
                            job_id=job_id)


def test_an_amount_fix_corrects_only_the_shops_own_payment_and_keeps_it_above_zero(db):
    with write_tx(db) as conn:
        credits.grant(conn, 1, 10, origin="bought", ref="MV-1", actor="operator", amount_ar=1000, method="mvola")
        credits.grant(conn, 1, 5, origin="offered", ref="welcome", actor="operator")
        credits.grant(conn, 2, 10, origin="bought", ref="MV-2", actor="operator", amount_ar=1000, method="mvola")
    for count, ref, amount, match in ((0, "MV-1", -1000, "would be 0 Ar"), (0, "MV-1", -2000, "would be -1000 Ar"),
                                      (0, "welcome", 100, "no bought grant with the reference 'welcome'"),
                                      (0, "MV-2", 100, "no bought grant with the reference 'MV-2'"),
                                      (-1, "MV-1", -100, "changes no credit"), (0, "MV-1", 0, "changes no credit")):
        with pytest.raises(ValueError, match=match), write_tx(db) as conn:
            credits.correct(conn, 1, count, ref=ref, note="montant mal tapé", actor="operator", amount_ar=amount)
    with write_tx(db) as conn:
        credits.correct(conn, 1, 0, ref="MV-1", note="montant mal tapé", actor="operator", amount_ar=-400)
        assert credits.balance(conn, 1)["available"] == 15  # the credits are untouched
    with pytest.raises(ValueError, match="already moved or corrected in this shop"), write_tx(db) as conn:
        credits.correct(conn, 1, 0, ref="MV-1", note="encore", actor="operator", amount_ar=100)
    assert rows(db, "SELECT shop_id, SUM(amount_ar) FROM credit_grants GROUP BY shop_id") == [(1, 600), (2, 1000)]


def test_a_correction_has_its_reason_and_never_takes_the_balance_below_zero(db):
    with write_tx(db) as conn:
        line(conn, credits=3, ref="welcome")
        job(conn, "spent")
    for count, note, match in ((-3, "trop", r"below zero \(available 2\)"), (0, "rien", "changes the credits or the amount"),
                               (1, None, "needs its reason"), (1, "", "needs its reason")):
        with pytest.raises(ValueError, match=match), write_tx(db) as conn:
            credits.correct(conn, 1, count, ref="geste", note=note, actor="operator")
    with write_tx(db) as conn:
        credits.correct(conn, 1, -2, ref="erreur", note="crédits en trop", actor="operator")
        credits.correct(conn, 1, 4, ref="geste", note="geste commercial", actor="operator")
        assert credits.balance(conn, 1) == {"available": 4, "pending": 1}


def test_a_reference_that_differs_only_by_case_or_spaces_is_the_same_reference(db):
    """Stored as first typed (ends trimmed), compared with inner spaces made one and case folded, inside the writing
    transaction: another spelling is the same reference, and a payment keeps its first spelling, so 0014's exact-match
    rules see one spelling per payment."""
    with write_tx(db) as conn:
        credits.grant(conn, 1, 10, origin="bought", ref=" Straße ", actor="operator", amount_ar=1000, method="mvola")
        credits.grant(conn, 1, 2, origin="offered", ref="Geste  du Mois", actor="operator")
        credits.correct(conn, 1, -1, ref="Erreur", note="en trop", actor="operator")
    assert rows(db, "SELECT ref FROM credit_grants ORDER BY id") == [("Straße",), ("Geste  du Mois",), ("Erreur",)]
    for shop, ref, match in ((2, "STRASSE", r"the payment 'Straße' is already recorded in shop originalphone \(line 1\)"),
                             (3, "strasse\n", r"the payment 'Straße' is already recorded in shop originalphone"),
                             (1, "STRASSE", r"already has a grant with the reference 'Straße' \(line 1\)")):  # typed again
        with pytest.raises(ValueError, match=match), write_tx(db) as conn:
            credits.grant(conn, shop, 10, origin="bought", ref=ref, actor="operator", amount_ar=1000, method="mvola")
    for write, match in ((lambda conn: credits.grant(conn, 1, 1, origin="offered", ref="geste du\tmois", actor="o"),
                          r"this shop already has a grant with the reference 'Geste  du Mois' \(line 2\)"),
                         (lambda conn: credits.correct(conn, 1, -1, ref="ERREUR ", note="encore", actor="o"),
                          r"this shop already has a correction with the reference 'Erreur' \(line 3\)")):
        with pytest.raises(ValueError, match=match), write_tx(db) as conn:
            write(conn)
    for ref in ("", " \t ", None, "x" * 101, "ß" * 51):  # "ß" folds to "ss": 102 characters compared
        with pytest.raises(ValueError, match="a reference has 1 to 100 characters"), write_tx(db) as conn:
            credits.grant(conn, 1, 1, origin="offered", ref=ref, actor="operator")
    with write_tx(db) as conn:  # typed in other spellings: moved, then its amount fixed, under its stored spelling
        credits.move(conn, "STRASSE", 1, 2, "operator", "mauvaise boutique")
        credits.correct(conn, 2, 0, ref="strasse", note="montant", actor="operator", amount_ar=-400)
        credits.grant(conn, 3, 5, origin="bought", ref="OM-7", actor="operator", amount_ar=500, method="orange")
        credits.correct(conn, 3, 1, ref="om-7", note="geste", actor="operator")  # takes the payment's correction
    assert rows(db, "SELECT shop_id, kind, ref, amount_ar FROM credit_grants WHERE id > 3 ORDER BY id") == [
        (1, "correction", "Straße", -1000), (2, "grant", "Straße", 1000), (2, "correction", "Straße", -400),
        (3, "grant", "OM-7", 500), (3, "correction", "OM-7", None)]
    with pytest.raises(ValueError, match="the payment 'OM-7' was already moved or corrected"), write_tx(db) as conn:
        credits.move(conn, "OM-7", 3, 1, "operator", "mauvaise boutique")


def test_a_reference_written_twice_outside_the_functions_is_refused_as_ambiguous(db):
    with write_tx(db) as conn:  # two spellings of one reference: only a writer outside credits.py can leave them
        paid(conn, ref="MV-5")
        paid(conn, ref="mv-5", amount=500)
    ambiguous = r"the reference 'Mv-5' matches lines written differently: line 1 'MV-5', line 2 'mv-5'"
    for write in (lambda conn: credits.move(conn, "Mv-5", 1, 2, "operator", "mauvaise boutique"),
                  lambda conn: credits.correct(conn, 1, 1, ref="Mv-5", note="geste", actor="operator")):
        with pytest.raises(ValueError, match=ambiguous), write_tx(db) as conn:
            write(conn)
    assert rows(db, "SELECT count(*) FROM credit_grants") == [(2,)]


@pytest.mark.parametrize("field, value", [("credits", 10**9 + 1), ("credits", 2**63), ("amount_ar", 2**63),
                                          ("amount_ar", -(10**9) - 1)])
def test_a_line_carries_at_most_a_billion_credits_or_ariary(db, field, value):
    """The functions' own bound, before any binding: past SQLite's 64-bit range the driver raises OverflowError, and two
    lines inside it can still overflow the balance's SUM for good, since a line is never removed."""
    with write_tx(db) as conn:
        credits.grant(conn, 1, 10, origin="bought", ref="MV-1", actor="operator", amount_ar=1000, method="mvola")
    if field == "credits":
        writes = (lambda conn: credits.grant(conn, 1, value, origin="offered", ref="x", actor="operator"),
                  lambda conn: credits.correct(conn, 1, value, ref="x", note="n", actor="operator"))
    else:
        writes = (lambda conn: credits.grant(conn, 2, 1, origin="bought", ref="x", actor="operator", amount_ar=abs(value),
                                             method="mvola"),
                  lambda conn: credits.correct(conn, 1, 0, ref="MV-1", note="n", actor="operator", amount_ar=abs(value)))
    for write in writes:
        with pytest.raises(ValueError, match="a line carries at most 1,000,000,000 credits and 1,000,000,000 Ar"), \
                write_tx(db) as conn:
            write(conn)
    assert rows(db, "SELECT count(*) FROM credit_grants") == [(1,)]


def test_the_purchase_text_is_never_empty(db):
    with write_tx(db) as conn:
        assert credits.purchase_text(conn, SimpleNamespace(support_contact_fr=None)) == \
            "Pour obtenir des crédits, contactez l’administrateur."
        assert credits.purchase_text(conn, SimpleNamespace(support_contact_fr="034 00 000 00")) == \
            "Pour obtenir des crédits, contactez 034 00 000 00."
        conn.exec_driver_sql("INSERT INTO meta VALUES ('purchase_text_fr', 'Pack 10 : 10 000 Ar par MVola.')")
        assert credits.purchase_text(conn, SimpleNamespace(support_contact_fr="034 00 000 00")) == \
            "Pack 10 : 10 000 Ar par MVola."


# --- The guards --------------------------------------------------------------------------------------------------

def test_a_fresh_database_holds_every_guard_as_its_migration_wrote_it(engine):
    with engine.connect() as conn:
        raw = conn.connection.dbapi_connection
        assert rehearse.guard_differences(raw) == []
        assert list(rehearse.guards(raw)) == [
            "guard table credit_grants", "guard trigger credit_grants_never_changed",
            "guard trigger credit_grants_never_removed", "guard trigger credit_grants_never_replaced",
            "guard trigger credit_grants_one_payment", "guard trigger credit_grants_payment_total",
            "guard trigger poster_jobs_final", "guard trigger poster_jobs_never_removed",
            "guard trigger poster_jobs_never_replaced", "guard trigger poster_jobs_same_job", "guard trigger keep_shop",
            "guard trigger shop_profile_never_replaced", "guard trigger shop_profile_same_shop",
            "guard column poster_jobs.takes_credit"]
