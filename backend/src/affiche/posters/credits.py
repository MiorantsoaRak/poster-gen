"""The prepaid balance (D-BALANCE-001, 002, 005). A shop's credits are the operator's lines (credit_grants: grants and
corrections, never changed or removed) minus its jobs that took a credit and are queued, running or succeeded: a job that
ends without an image stops counting, and nothing is written. Each function takes a connection and never commits: the
caller holds the transaction (write_tx), so a balance and the write it allows are one BEGIN IMMEDIATE. The operator's
refusals are ValueError, one line, nothing written; migration 0014's rules and triggers hold whatever writes a line."""
from sqlalchemy import text

from affiche.db import utc_now
from .store import Refused

BALANCE = text(
    "SELECT (SELECT COALESCE(SUM(credits), 0) FROM credit_grants WHERE shop_id = :shop)"
    " - (SELECT COUNT(*) FROM poster_jobs WHERE shop_id = :shop AND takes_credit = 1"
    " AND status IN ('queued', 'running', 'succeeded')) AS available,"
    " (SELECT COUNT(*) FROM poster_jobs WHERE shop_id = :shop AND takes_credit = 1"
    " AND status IN ('queued', 'running')) AS pending")


def balance(conn, shop: int) -> dict:
    """{"available", "pending"}: pending is the counted jobs still queued or running (« en attente »)."""
    row = conn.execute(BALANCE, {"shop": shop}).one()
    return {"available": row.available, "pending": row.pending}


def require(conn, shop: int) -> None:
    """Inside the admission transaction, after the job's row: the sum of the grants minus the counted jobs, this one
    included, must not be below zero (D-BALANCE-002)."""
    if balance(conn, shop)["available"] < 0:
        raise Refused("no_credit", 402)


def purchase_text(conn, settings) -> str:
    """How a shop gets credits, never empty: the operator's text, else the support contact (D-BALANCE-004)."""
    stored = conn.execute(text("SELECT value FROM meta WHERE key='purchase_text_fr'")).scalar()
    return stored or f"Pour obtenir des crédits, contactez {settings.support_contact_fr or 'l’administrateur'}."


def _whole(value) -> bool:
    return type(value) is int  # not a bool, not 1.5


def _line(conn, shop, kind, credits, ref, actor, note, *, origin=None, amount_ar=None, method=None, job_id=None) -> int:
    return conn.execute(text(
        "INSERT INTO credit_grants (shop_id,kind,origin,credits,amount_ar,method,ref,job_id,note,actor,created_at)"
        " VALUES (:shop,:kind,:origin,:credits,:amount,:method,:ref,:job,:note,:actor,:now) RETURNING id"),
        {"shop": shop, "kind": kind, "origin": origin, "credits": credits, "amount": amount_ar, "method": method,
         "ref": ref, "job": job_id, "note": note, "actor": actor, "now": utc_now()}).scalar_one()


def _has_line(conn, shop, ref, kind=None) -> bool:
    return conn.execute(text("SELECT 1 FROM credit_grants WHERE shop_id=:shop AND ref=:ref AND kind=COALESCE(:kind,kind)"),
                        {"shop": shop, "ref": ref, "kind": kind}).first() is not None


def _bought(conn, shop, ref):
    return conn.execute(text("SELECT credits, amount_ar, method FROM credit_grants WHERE shop_id=:shop AND kind='grant'"
                             " AND origin='bought' AND ref=:ref"), {"shop": shop, "ref": ref}).first()


def grant(conn, shop, credits, *, origin, ref, actor, note=None, amount_ar=None, method=None) -> int:
    """Whole credits, offered or bought. A bought reference that any shop holds is refused, with no override: a payment
    changes shop only by move. Returns the line's id."""
    if not _whole(credits) or credits < 1:
        raise ValueError("a grant is 1 credit or more")
    if origin == "bought":
        if not _whole(amount_ar) or amount_ar <= 0 or not method:
            raise ValueError("a bought grant needs its amount in ariary and its payment method")
        method = method.lower()
    elif origin != "offered" or amount_ar is not None or method is not None:
        raise ValueError("a grant is offered (no amount, no method) or bought")
    line = conn.execute(text("SELECT id FROM credit_grants WHERE shop_id=:shop AND kind='grant' AND ref=:ref"),
                        {"shop": shop, "ref": ref}).scalar()
    if line is not None:
        raise ValueError(f"this shop already has a grant with the reference {ref!r} (line {line})")
    if origin == "bought":
        held = conn.execute(text("SELECT g.id, p.identifier FROM credit_grants g JOIN shop_profile p ON p.id=g.shop_id"
                                 " WHERE g.ref=:ref AND (g.origin='bought' OR g.amount_ar IS NOT NULL) ORDER BY g.id"),
                            {"ref": ref}).first()
        if held is not None:
            raise ValueError(f"the payment {ref!r} is already recorded in shop {held.identifier} (line {held.id}): "
                             "a payment changes shop only by move-payment")
    return _line(conn, shop, "grant", credits, ref, actor, note, origin=origin, amount_ar=amount_ar, method=method)


def move(conn, ref, from_shop, to_shop, actor, note) -> tuple[int, int]:
    """One payment moved, in the caller's transaction: a correction takes its credits and ariary back from from_shop,
    then the same bought grant goes to to_shop. The correction comes first: credit_grants_payment_total requires it to
    bring the source's total to exactly zero, so that credit_grants_one_payment sees no other shop above zero when the
    grant comes. Refused, nothing written, unless the credits are still unspent. Returns both line ids."""
    if not note:
        raise ValueError("a move needs its reason (note)")
    if from_shop == to_shop:
        raise ValueError("a payment moves to another shop")
    paid = _bought(conn, from_shop, ref)
    if paid is None:
        raise ValueError(f"the source shop has no bought grant with the reference {ref!r}")
    if _has_line(conn, from_shop, ref, "correction"):
        raise ValueError(f"the payment {ref!r} was already moved or corrected in the source shop")
    if _has_line(conn, to_shop, ref):
        raise ValueError(f"the destination shop already has a line with the reference {ref!r}")
    # No other shop's total needs checking: while from_shop holds this uncorrected payment, the two payment triggers
    # leave every other shop at zero.
    available = balance(conn, from_shop)["available"]
    if available < paid.credits:
        raise ValueError(f"the source shop has {available} credits left of the payment's {paid.credits}: "
                         "it stays where it is")
    reversal = _line(conn, from_shop, "correction", -paid.credits, ref, actor, note, amount_ar=-paid.amount_ar)
    return reversal, _line(conn, to_shop, "grant", paid.credits, ref, actor, note, origin="bought",
                           amount_ar=paid.amount_ar, method=paid.method)


def correct(conn, shop, credits, *, ref, note, actor, amount_ar=None, job_id=None) -> int:
    """A correction with its reason: credits added or taken back; a job repaid (+1, once, only a succeeded job of this
    shop that took a credit); or a mistyped amount of this shop's own payment fixed (0 credits), its total kept above
    zero. Never takes the balance below zero. Returns the line's id."""
    if not note:
        raise ValueError("a correction needs its reason (note)")
    if not _whole(credits) or credits == 0 and amount_ar is None:
        raise ValueError("a correction changes the credits or the amount")
    if job_id is not None:
        if credits != 1 or amount_ar is not None:
            raise ValueError("a job is repaid with exactly 1 credit and no amount")
        job = conn.execute(text("SELECT status, takes_credit FROM poster_jobs WHERE id=:id AND shop_id=:shop"),
                           {"id": job_id, "shop": shop}).first()
        if job is None or job.status != "succeeded" or job.takes_credit != 1:
            raise ValueError("only a succeeded job of this shop that took a credit can be repaid")
        repaid = conn.execute(text("SELECT id FROM credit_grants WHERE job_id=:id"), {"id": job_id}).scalar()
        if repaid is not None:
            raise ValueError(f"this job was already repaid (line {repaid})")
    elif amount_ar is not None:
        if credits != 0 or not _whole(amount_ar) or amount_ar == 0:
            raise ValueError("an amount fix changes no credit and needs a non-zero amount in ariary")
        paid = _bought(conn, shop, ref)
        if paid is None:
            raise ValueError(f"this shop has no bought grant with the reference {ref!r}")
        if _has_line(conn, shop, ref, "correction"):
            raise ValueError(f"the payment {ref!r} was already moved or corrected in this shop")
        if paid.amount_ar + amount_ar <= 0:  # its only line so far: the grant
            raise ValueError(f"the payment's total would be {paid.amount_ar + amount_ar} Ar: it must stay above zero")
    if credits < 0:
        available = balance(conn, shop)["available"]
        if available + credits < 0:
            raise ValueError(f"the balance would go below zero (available {available})")
    return _line(conn, shop, "correction", credits, ref, actor, note, amount_ar=amount_ar, job_id=job_id)
