"""The prepaid balance (D-BALANCE-001): which jobs take a credit, and the operator's lines. A shop's balance is the sum of
its lines minus its jobs that took a credit and are queued, running or succeeded; it is never stored.

Every job from before this migration reads takes_credit 0 and never counts. No line is written: the pilot's opening
balance is granted by the operator after the release. The table and the nine triggers are rehearse.GUARDS, checked
after every rehearsal: rebuilding a table by SQLite's procedure drops its triggers without a word. Their SQL holds no
comment, so that the text SQLite keeps is the guard's text.
"""
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

STATEMENTS = [
    "ALTER TABLE poster_jobs ADD COLUMN takes_credit INTEGER NOT NULL DEFAULT 0 CHECK (takes_credit IN (0, 1))",
    # origin labels a grant only; amount_ar is signed on a correction; job_id is a repayment, once per job. The CASE
    # is wrapped in COALESCE: a NULL inside it (a bought grant without amount) must refuse, and a CHECK passes on NULL.
    """CREATE TABLE credit_grants (
  id INTEGER PRIMARY KEY,
  shop_id INTEGER NOT NULL REFERENCES shop_profile(id),
  kind TEXT NOT NULL CHECK (kind IN ('grant', 'correction')),
  origin TEXT CHECK (origin IN ('offered', 'bought')),
  credits INTEGER NOT NULL CHECK (typeof(credits) = 'integer'),
  amount_ar INTEGER CHECK (amount_ar IS NULL OR (typeof(amount_ar) = 'integer' AND amount_ar <> 0)),
  method TEXT CHECK (method IS NULL OR length(method) BETWEEN 1 AND 40),
  ref TEXT NOT NULL CHECK (length(ref) BETWEEN 1 AND 100),
  job_id TEXT UNIQUE REFERENCES poster_jobs(id),
  note TEXT CHECK (note IS NULL OR length(note) BETWEEN 1 AND 500),
  actor TEXT NOT NULL CHECK (length(actor) BETWEEN 1 AND 64),
  created_at TEXT NOT NULL,
  CHECK (COALESCE(CASE kind
    WHEN 'grant' THEN credits > 0 AND job_id IS NULL AND (
         (origin = 'bought' AND amount_ar > 0 AND method IS NOT NULL)
      OR (origin = 'offered' AND amount_ar IS NULL AND method IS NULL))
    ELSE origin IS NULL AND method IS NULL AND note IS NOT NULL
      AND (credits <> 0 OR amount_ar IS NOT NULL)
      AND (job_id IS NULL OR (credits = 1 AND amount_ar IS NULL)) END, 0)),
  UNIQUE (shop_id, kind, ref)
)""",
    """CREATE TRIGGER credit_grants_never_changed BEFORE UPDATE ON credit_grants
  BEGIN SELECT RAISE(ABORT, 'a credit line is never changed'); END""",
    """CREATE TRIGGER credit_grants_never_removed BEFORE DELETE ON credit_grants
  BEGIN SELECT RAISE(ABORT, 'a credit line is never removed'); END""",
    # Each other shop's total apart: a negative total in one must not hide a positive one in another.
    """CREATE TRIGGER credit_grants_one_payment BEFORE INSERT ON credit_grants
  WHEN NEW.amount_ar > 0 AND EXISTS (SELECT 1 FROM credit_grants WHERE ref = NEW.ref AND shop_id <> NEW.shop_id
       GROUP BY shop_id HAVING SUM(amount_ar) > 0)
  BEGIN SELECT RAISE(ABORT, 'this payment is already counted in another shop'); END""",
    """CREATE TRIGGER credit_grants_payment_total BEFORE INSERT ON credit_grants
  WHEN NEW.kind = 'correction' AND NEW.amount_ar IS NOT NULL AND (
       (SELECT COALESCE(SUM(amount_ar), 0) FROM credit_grants WHERE shop_id = NEW.shop_id AND ref = NEW.ref) <= 0
    OR (NEW.credits = 0 AND (SELECT COALESCE(SUM(amount_ar), 0) FROM credit_grants
                             WHERE shop_id = NEW.shop_id AND ref = NEW.ref) + NEW.amount_ar <= 0)
    OR (NEW.credits <> 0 AND (SELECT COALESCE(SUM(amount_ar), 0) FROM credit_grants
                              WHERE shop_id = NEW.shop_id AND ref = NEW.ref) + NEW.amount_ar <> 0))
  BEGIN SELECT RAISE(ABORT, 'a payment''s corrected total must stay positive, or a reversal must bring it to zero'); END""",
    """CREATE TRIGGER poster_jobs_final BEFORE UPDATE OF status, takes_credit ON poster_jobs
  WHEN NEW.takes_credit IS NOT OLD.takes_credit
    OR (OLD.status IN ('succeeded', 'failed', 'interrupted', 'cancelled') AND NEW.status IS NOT OLD.status)
  BEGIN SELECT RAISE(ABORT, 'a finished job never changes status, and no job changes what it costs'); END""",
    # REPLACE deletes the row that collides on a unique key without firing DELETE triggers (recursive_triggers is off
    # by default), and a BEFORE INSERT trigger runs before that delete: refuse the collision there, on every unique key
    # (a new one must join). An automatic id or rowid reads -1 here and collides with nothing.
    """CREATE TRIGGER credit_grants_never_replaced BEFORE INSERT ON credit_grants
  WHEN EXISTS (SELECT 1 FROM credit_grants WHERE id = NEW.id OR job_id = NEW.job_id
               OR (shop_id = NEW.shop_id AND kind = NEW.kind AND ref = NEW.ref))
  BEGIN SELECT RAISE(ABORT, 'a credit line is never replaced'); END""",
    """CREATE TRIGGER poster_jobs_never_removed BEFORE DELETE ON poster_jobs
  BEGIN SELECT RAISE(ABORT, 'a job is never removed'); END""",
    # poster_one_image's predicate, repeated: REPLACE through that index removes another job's row.
    """CREATE TRIGGER poster_jobs_never_replaced BEFORE INSERT ON poster_jobs
  WHEN EXISTS (SELECT 1 FROM poster_jobs WHERE id = NEW.id OR rowid = NEW.rowid)
    OR (NEW.kind IN ('scene', 'refine', 'text_texture', 'background') AND NEW.status IN ('queued', 'running')
        AND EXISTS (SELECT 1 FROM poster_jobs WHERE creation_id = NEW.creation_id
                    AND kind IN ('scene', 'refine', 'text_texture', 'background') AND status IN ('queued', 'running')))
  BEGIN SELECT RAISE(ABORT, 'a job is never replaced'); END""",
    # With these fixed, an UPDATE OR REPLACE collides with no other row (it could enter poster_one_image only by moving
    # a finished job back, which poster_jobs_final refuses), and a credit cannot pass to another shop.
    """CREATE TRIGGER poster_jobs_same_job BEFORE UPDATE ON poster_jobs
  WHEN NEW.rowid IS NOT OLD.rowid OR NEW.id IS NOT OLD.id OR NEW.shop_id IS NOT OLD.shop_id
    OR NEW.creation_id IS NOT OLD.creation_id OR NEW.kind IS NOT OLD.kind
  BEGIN SELECT RAISE(ABORT, 'a job stays the same job: its id, shop, poster and kind never change'); END""",
]

# The rehearsal's contract (affiche.rehearse). PRESERVED: poster_jobs is widened, so it is hashed over its 0013 columns.
PRESERVED = {"poster_jobs": ("id", "shop_id", "creation_id", "origin_revision", "input_id", "kind", "input_json",
                             "input_hash", "status", "result_ref", "error_code", "created_at", "started_at",
                             "finished_at", "recovery_count")}
# ADDED: what it changes on purpose, as a query and the exact rows it must give after it.
ADDED = {
    "poster_jobs: no job from before 0014 takes a credit": (
        "SELECT count(*) FROM poster_jobs WHERE takes_credit <> 0", [(0,)]),
    "credit_grants: empty; no shop has a credit before the operator grants one": (
        "SELECT count(*) FROM credit_grants", [(0,)]),
}


def upgrade():
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade():
    raise NotImplementedError("Migrations are forward-only.")
