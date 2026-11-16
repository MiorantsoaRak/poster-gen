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


# The most one line carries, in credits or in ariary. No business limit is decided: this one keeps every value and every
# sum inside SQLite's 64-bit integers (a SUM past them fails for good, as a line is never removed), far above any pack.
MOST = 1_000_000_000


def _whole(value) -> bool:
    return type(value) is int  # not a bool, not 1.5


def _key(ref: str) -> str:
    return " ".join(ref.split()).casefold()


def _ref(ref) -> tuple[str, str]:
    """(the reference as typed, ends trimmed; the key it is compared by). Both hold 1 to 100 characters: the stored one
    for 0014's CHECK, the key because case folding can lengthen it ("ß" is "ss")."""
    typed = (ref or "").strip()
    if not (1 <= len(typed) <= 100 and 1 <= len(_key(typed)) <= 100):
        raise ValueError("a reference has 1 to 100 characters")
    return typed, _key(typed)


# A reference is stored as first typed and compared by its key (inner spaces made one, case folded) here, inside the
# writing transaction: 0014's unique key and payment triggers compare the stored text exactly, so each new line takes
# the spelling its shop already uses, and a move or an amount fix the payment's own. Not covered: lines written outside
# these functions, and spellings that differ by more than case and spaces ("MV-123" and "MV123" are two references).
# Holding it for every writer needs a later migration (a stored key and its unique index).
LINES = text("SELECT g.id, g.kind, g.origin, g.credits, g.amount_ar, g.method, g.ref, p.identifier FROM credit_grants g"
             " JOIN shop_profile p ON p.id = g.shop_id WHERE g.shop_id = COALESCE(:shop, g.shop_id) ORDER BY g.id")


def _lines(conn, key, shop=None) -> list:
    """This shop's lines under this key, or every shop's. ponytail: folds every candidate line in Python (SQLite's
    lower() folds ASCII only); the later migration's stored key replaces the scan."""
    return [line for line in conn.execute(LINES, {"shop": shop}) if _key(line.ref) == key]


def _spelling(lines, typed) -> str:
    """The one stored spelling of these lines, else the typed one. Two spellings come only from lines written outside
    these functions: refused, never guessed."""
    spellings = {line.ref for line in lines}
    if len(spellings) > 1:
        raise ValueError(f"the reference {typed!r} matches lines written differently: "
                         + ", ".join(f"line {line.id} {line.ref!r}" for line in lines))
    return spellings.pop() if spellings else typed


def _line(conn, shop, kind, credits, ref, actor, note, *, origin=None, amount_ar=None, method=None, job_id=None) -> int:
    if abs(credits) > MOST or amount_ar is not None and abs(amount_ar) > MOST:  # before the driver's OverflowError
        raise ValueError(f"a line carries at most {MOST:,} credits and {MOST:,} Ar")
    return conn.execute(text(
        "INSERT INTO credit_grants (shop_id,kind,origin,credits,amount_ar,method,ref,job_id,note,actor,created_at)"
        " VALUES (:shop,:kind,:origin,:credits,:amount,:method,:ref,:job,:note,:actor,:now) RETURNING id"),
        {"shop": shop, "kind": kind, "origin": origin, "credits": credits, "amount": amount_ar, "method": method,
         "ref": ref, "job": job_id, "note": note, "actor": actor, "now": utc_now()}).scalar_one()


def _bought(lines):
    return next((line for line in lines if line.kind == "grant" and line.origin == "bought"), None)


def _of_kind(lines, kind):
    return next((line for line in lines if line.kind == kind), None)


def grant(conn, shop, credits, *, origin, ref, actor, note=None, amount_ar=None, method=None) -> int:
    """Whole credits, offered or bought. A bought reference that any shop holds is refused, with no override: a payment
    changes shop only by move. Returns the line's id."""
    typed, key = _ref(ref)
    if not _whole(credits) or credits < 1:
        raise ValueError("a grant is 1 credit or more")
    if origin == "bought":
        if not _whole(amount_ar) or amount_ar <= 0 or not method:
            raise ValueError("a bought grant needs its amount in ariary and its payment method")
        method = method.lower()
    elif origin != "offered" or amount_ar is not None or method is not None:
        raise ValueError("a grant is offered (no amount, no method) or bought")
    mine = _lines(conn, key, shop)
    if (line := _of_kind(mine, "grant")) is not None:
        raise ValueError(f"this shop already has a grant with the reference {line.ref!r} (line {line.id})")
    if origin == "bought":
        held = [line for line in _lines(conn, key) if line.origin == "bought" or line.amount_ar is not None]
        if held:
            raise ValueError(f"the payment {held[0].ref!r} is already recorded in shop {held[0].identifier} (line "
                             f"{held[0].id}): a payment changes shop only by move-payment")
    return _line(conn, shop, "grant", credits, _spelling(mine, typed), actor, note, origin=origin, amount_ar=amount_ar,
                 method=method)


def move(conn, ref, from_shop, to_shop, actor, note) -> tuple[int, int]:
    """One payment moved, in the caller's transaction: a correction takes its credits and ariary back from from_shop,
    then the same bought grant goes to to_shop. The correction comes first: credit_grants_payment_total requires it to
    bring the source's total to exactly zero, so that credit_grants_one_payment sees no other shop above zero when the
    grant comes. Refused, nothing written, unless the credits are still unspent. Returns both line ids."""
    typed, key = _ref(ref)
    if not note:
        raise ValueError("a move needs its reason (note)")
    if from_shop == to_shop:
        raise ValueError("a payment moves to another shop")
    source = _lines(conn, key, from_shop)
    paid = _bought(source)
    if paid is None:
        raise ValueError(f"the source shop has no bought grant with the reference {typed!r}")
    ref = _spelling(source, typed)  # the payment's own: both lines must carry it for 0014's exact-match rules
    if _of_kind(source, "correction") is not None:
        raise ValueError(f"the payment {ref!r} was already moved or corrected in the source shop")
    if there := _lines(conn, key, to_shop):
        raise ValueError(f"the destination shop already has a line with the reference {there[0].ref!r} "
                         f"(line {there[0].id})")
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
    typed, key = _ref(ref)
    if not note:
        raise ValueError("a correction needs its reason (note)")
    if not _whole(credits) or credits == 0 and amount_ar is None:
        raise ValueError("a correction changes the credits or the amount")
    mine = _lines(conn, key, shop)
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
        paid = _bought(mine)
        if paid is None:
            raise ValueError(f"this shop has no bought grant with the reference {typed!r}")
        if _of_kind(mine, "correction") is not None:
            raise ValueError(f"the payment {paid.ref!r} was already moved or corrected in this shop")
        if paid.amount_ar + amount_ar <= 0:  # its only line so far: the grant
            raise ValueError(f"the payment's total would be {paid.amount_ar + amount_ar} Ar: it must stay above zero")
    if (line := _of_kind(mine, "correction")) is not None:  # 0014's unique key is the backstop
        raise ValueError(f"this shop already has a correction with the reference {line.ref!r} (line {line.id})")
    if credits < 0:
        available = balance(conn, shop)["available"]
        if available + credits < 0:
            raise ValueError(f"the balance would go below zero (available {available})")
    return _line(conn, shop, "correction", credits, _spelling(mine, typed), actor, note, amount_ar=amount_ar,
                 job_id=job_id)
