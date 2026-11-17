"""The operator's actions on shops and their credits (D-MULTI-SHOP-003, D-BALANCE-005), and the operator's own password
(D-ADMIN-001). Each function takes a connection and never commits: the caller holds the transaction (write_tx), so that
a later record of the action can join it. Passwords are hashed by the caller, outside the transaction.

    python -m affiche.shops list
    python -m affiche.shops create <identifier> [--name "Nom affiché"] [--welcome 5]   prints the password once
    python -m affiche.shops set-password <identifier>                     prints the new password once; ends its sessions
    python -m affiche.shops end-sessions (<identifier> | --all | --operator)   --all: every shop's and the operator's
    python -m affiche.shops operator-password                             the dashboard's password, printed once; ends
                                                                          every operator session
    python -m affiche.shops suspend <identifier> --yes                    without --yes, only shows the shop
    python -m affiche.shops enable <identifier>
    python -m affiche.shops grant <identifier> <credits> --offered --ref <reference> [--note "…"]
    python -m affiche.shops grant <identifier> <credits> --bought --amount-ar <ariary> --method <mvola|…> --ref <payment>
    python -m affiche.shops move-payment <payment reference> <from identifier> <to identifier> --note "<why>"
    python -m affiche.shops correct <identifier> <+n|-n> --ref <reference> --note "<reason>" [--job <job id>]
    python -m affiche.shops correct <identifier> 0 --ref <payment reference> --amount-ar <±ariary> --note "<reason>"
    python -m affiche.shops pause --yes                                   without --yes, only says whether it is paused
    python -m affiche.shops resume
    python -m affiche.shops purchase-text ["…"]                          without a text, prints the current one
    python -m affiche.shops after-restore <kept database> [--apply]      without --apply, only reports

The command reads the data folder from the settings, as the other commands do, and never migrates: it refuses unless
the database is at this code's head. It takes no lock, so it runs beside the API. Exit 0 done, 1 refused (one line on
stderr, nothing written), 2 usage.
"""
import argparse
import secrets
import shlex
import sqlite3
import sys
from collections import Counter
from collections.abc import Sequence
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_EVEN, Decimal
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from pydantic import ValidationError
from sqlalchemy import Connection, bindparam, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from affiche.config import BACKEND_DIR, ENV_FILE, ConfigError, load_settings
from affiche.db import make_engine, utc_now, write_tx
from affiche.posters import credits, jobs
from affiche.posters.auth import OPERATOR_KEY, PASSWORDS, identifier_key
from affiche.posters.models import Profile
from affiche.visuals.admission import spent_micros
from affiche.visuals.gateway import usd_to_micros

# No 0/o, 1/l/i: read aloud and typed on a phone. Twelve of them: about 59 bits; the operator's 26, about 129.
ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"


def new_password(length: int = 12) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def find_shop(conn: Connection, identifier: str):
    """The shop of an identifier in any spelling (identifier_key), or None."""
    return conn.execute(text("SELECT id, identifier, name, state FROM shop_profile WHERE identifier=:key"),
                        {"key": identifier_key(identifier)}).first()


def list_shops(conn: Connection) -> list:
    """Whether a shop has a password, never its hash: shop 1 has none after a backup from before 0013 is restored."""
    return conn.execute(text("SELECT id, identifier, name, state, created_at, password_hash IS NOT NULL AS has_password"
                             " FROM shop_profile ORDER BY id")).all()


def create_shop(conn: Connection, identifier: str, name: str | None, password_hash: str) -> int:
    """An active shop; its identifier is stored normalised, so the UNIQUE column refuses one taken in any spelling
    (IntegrityError). Returns its id."""
    key = identifier_key(identifier)
    if not 3 <= len(key) <= 32:
        raise ValueError("an identifier needs 3 to 32 letters or digits")
    now = utc_now()
    return conn.execute(text("INSERT INTO shop_profile (revision,name,updated_at,identifier,password_hash,state,created_at)"
                             " VALUES (1,:name,:now,:identifier,:hash,'active',:now) RETURNING id"),
                        {"name": Profile(name=name).name, "now": now, "identifier": key, "hash": password_hash}).scalar_one()


def set_password(conn: Connection, shop_id: int, password_hash: str) -> None:
    """A new password ends every session of that shop, and no other shop's."""
    if conn.execute(text("UPDATE shop_profile SET password_hash=:hash WHERE id=:shop"),
                    {"hash": password_hash, "shop": shop_id}).rowcount != 1:
        raise LookupError(f"no shop {shop_id}")
    end_sessions(conn, shop_id)


def end_sessions(conn: Connection, shop_id: int | None = None) -> int:
    """One shop's sessions, or every shop's (after a backup is restored). Returns how many ended."""
    if shop_id is None:
        return conn.execute(text("DELETE FROM sessions")).rowcount
    return conn.execute(text("DELETE FROM sessions WHERE shop_id=:shop"), {"shop": shop_id}).rowcount


def end_operator_sessions(conn: Connection) -> int:
    """Every operator session, and no shop's. Returns how many ended."""
    return conn.execute(text("DELETE FROM operator_sessions")).rowcount


def set_operator_password(conn: Connection, password_hash: str) -> int:
    """D-ADMIN-001: the only writer of the operator's hash. Every operator session ends in the same transaction, so that
    none outlives the password it was opened with. Returns how many ended."""
    conn.execute(text("INSERT INTO meta VALUES (:key, :hash) ON CONFLICT(key) DO UPDATE SET value=excluded.value"),
                 {"key": OPERATOR_KEY, "hash": password_hash})
    return end_operator_sessions(conn)


def _state(conn: Connection, shop_id: int) -> str:
    state = conn.execute(text("SELECT state FROM shop_profile WHERE id=:shop"), {"shop": shop_id}).scalar()
    if state is None:
        raise LookupError(f"no shop {shop_id}")
    return state


def suspend(conn: Connection, shop_id: int) -> int | None:
    """D-MULTI-SHOP-006: its queued jobs are cancelled, their reserved calls released at cost 0. Its sessions are kept:
    the session read requires an active shop, so they stop at once and work again after enable. A call already reserved
    by a running job is cut where it is sent (jobs.dispatch, reads._send). Returns how many jobs were cancelled, or None
    when the shop was already suspended (nothing changed)."""
    if _state(conn, shop_id) == "suspended":
        return None
    conn.execute(text("UPDATE shop_profile SET state='suspended' WHERE id=:shop"), {"shop": shop_id})
    queued = conn.execute(text("SELECT id FROM poster_jobs WHERE shop_id=:shop AND status='queued'"),
                          {"shop": shop_id}).scalars().all()
    now = utc_now()
    for id in queued:
        jobs.cancel_queued(conn, id, now, "shop_suspended")
    return len(queued)


def enable(conn: Connection, shop_id: int) -> bool:
    """Data, profile, ledger and sessions were never touched; cancelled jobs stay cancelled. False: it was active."""
    if _state(conn, shop_id) == "active":
        return False
    conn.execute(text("UPDATE shop_profile SET state='active' WHERE id=:shop"), {"shop": shop_id})
    return True


def pause(conn: Connection) -> bool:
    """D-BALANCE-003: no new request to the AI for any shop (images, styles, text proposals, reads); what was admitted
    finishes, a 429 retry included (jobs.provider_guard). False: it was already paused."""
    return conn.execute(text("INSERT INTO meta VALUES ('generation_paused', :now) ON CONFLICT DO NOTHING"),
                        {"now": utc_now()}).rowcount == 1


def resume(conn: Connection) -> bool:
    """False: it was not paused."""
    return conn.execute(text("DELETE FROM meta WHERE key='generation_paused'")).rowcount == 1


def set_purchase_text(conn: Connection, sentence: str) -> None:
    """What a shop reads to buy credits (credits.purchase_text, D-BALANCE-004): packs, mobile money number, the reference
    to write, and when credits arrive."""
    sentence = sentence.strip()  # blank would read as set, and a shop would be told nothing
    if not 1 <= len(sentence) <= 500:
        raise ValueError("a purchase text has 1 to 500 characters")
    conn.execute(text("INSERT INTO meta VALUES ('purchase_text_fr', :sentence)"
                      " ON CONFLICT(key) DO UPDATE SET value=excluded.value"), {"sentence": sentence})


IMAGE_COSTS = text(
    "SELECT COUNT(*), COALESCE(SUM(cost_micros), 0) FROM (SELECT c.cost_micros FROM poster_calls c"
    " JOIN poster_jobs j ON j.id=c.job_id WHERE c.status='succeeded' AND c.cost_is_estimate=0 AND c.provider<>'stub'"
    " AND j.kind IN :kinds ORDER BY c.created_at DESC LIMIT 50)").bindparams(bindparam("kinds", expanding=True))


def headroom(conn: Connection, settings) -> dict:
    """The cap is cumulative (D-BALANCE-003): what is left of it, against what every shop's unspent credits would cost at
    the average real cost of the last 50 images, or ESTIMATE_SCENE_USD before any. Micro-USD; the cost is rounded up
    once, at the end, so that a cap short by less than a credit still warns; the unit is for display."""
    outstanding = sum(max(credits.balance(conn, shop)["available"], 0)
                      for shop in conn.execute(text("SELECT id FROM shop_profile")).scalars().all())
    images, total = conn.execute(IMAGE_COSTS, {"kinds": sorted(jobs.IMAGE_KINDS)}).one()
    if not images:  # no real image cost yet: the estimate, as the cost of one image
        total = usd_to_micros(settings.estimate_scene_usd)
    count = images or 1
    return {"cap": usd_to_micros(settings.spend_cap_usd), "spent": spent_micros(conn, settings),
            "outstanding": outstanding, "images": images, "unit": total / count,
            "cost": -(-outstanding * total // count)}


# In the kept ledger's global insertion order: a move's reversal comes before its grant, whatever the shops' ids.
KEPT_LINES = ("SELECT g.id, p.identifier, g.kind, g.origin, g.credits, g.amount_ar, g.method, g.ref, g.job_id, g.note,"
              " g.actor, g.created_at FROM credit_grants g JOIN shop_profile p ON p.id = g.shop_id ORDER BY g.id")
KEPT_IMAGES = ("SELECT j.id, p.identifier FROM poster_jobs j JOIN shop_profile p ON p.id = j.shop_id"
               " WHERE j.takes_credit = 1 AND j.status = 'succeeded'")
LOSS = ("nothing to copy: the restore's loss policy applies (the grants and corrections made since the backup are "
        "gone); redo them from your payment records")


def _kept(kept: Path):
    """(names by identifier, lines, counted images) of the database a restore replaced, None when it is older than
    0014 (no line was ever granted there). Read through a read-only connection of its own: never written, and its -wal
    never checkpointed into it. No ATTACH: SQLite refuses one inside the copy's transaction."""
    try:
        if not kept.is_file():
            raise ValueError(f"no kept database at {kept}: {LOSS}")
        db = sqlite3.connect(f"{kept.resolve().as_uri()}?mode=ro", uri=True)
        try:
            db.row_factory = sqlite3.Row
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='credit_grants'").fetchone() is None:
                return None
            return (dict(db.execute("SELECT identifier, name FROM shop_profile").fetchall()),
                    db.execute(KEPT_LINES).fetchall(), db.execute(KEPT_IMAGES).fetchall())
        finally:
            db.close()
    except (sqlite3.Error, OSError) as error:
        raise ValueError(f"the kept database {kept} cannot be read ({error}): {LOSS}") from None


def _unpaid(job) -> str | None:
    """Why a repayment is not copied: its job here (D-BALANCE-005's table), or None when it is a counted image."""
    if job is None:
        return "its job is not here (made after the backup): the restore removed that image and its charge"
    if job.status in ("queued", "running"):
        return f"its job is still {job.status} here: decide after it ends, by running after-restore again"
    if job.status != "succeeded" or job.takes_credit != 1:
        return f"its job is {job.status} here and holds no credit"
    return None


def _kept_line(row) -> str:
    return f"line {row['id']} of the kept database ({row['identifier']} {row['kind']} {row['ref']!r})"


def _named_lines(lines) -> str:
    return ", ".join(f"{line['name']} {line['ref']!r}" for line in lines)


def after_restore(conn: Connection, kept: Path, *, apply: bool) -> tuple[list[str], list[str]]:
    """D-BALANCE-005, the restore's copy: (the report, the missing shops that block it). A line of the kept database is
    here when this database has its shop identifier, kind and reference key (credits._key), whatever the spelling. Each
    other one is copied with apply, in the kept ledger's order, by a plain INSERT that keeps its ref as stored, its
    date, actor, note, amounts and method, so that 0014's rules judge each as it came; a repayment only when its job is
    here a succeeded image that took a credit. A payment (a reference that carries ariary) is copied only when its lines
    here are the first ones of its kept history, shop, kind, credits and ariary: moved or typed otherwise since the restore, this database's history
    stands and the rest is skipped, as replaying it could take the payment out of every shop. Nothing is copied while
    one of the lines belongs to a missing shop. A refusal is a ValueError: the caller's transaction rolls back whatever was copied."""
    read = _kept(kept)
    if read is None:
        return [f"the kept database {kept} is older than migration 0014: no credit was ever granted there; nothing to "
                "copy"], []
    names, lines, images = read
    shops = dict(conn.execute(text("SELECT identifier, id FROM shop_profile")).all())
    jobs_here = {job.id: job for job in conn.execute(text("SELECT id, status, takes_credit FROM poster_jobs"))}
    here = [{"shop": line.identifier, "kind": line.kind, "ref": line.ref, "key": credits._key(line.ref),
             "credits": line.credits, "amount": line.amount_ar, "job": line.job_id, "name": f"line {line.id} here"}
            for line in conn.execute(credits.LINES, {"shop": None})]
    # By key: is it a payment; its lines in the kept ledger; its lines here, each with what it moves. Repayments stay
    # out: they carry no ariary, each has its own rule below, and one skipped while its job ran is copied later.
    paid, there, mine = set(), {}, {}
    for row in lines:
        if row["job_id"] is None:
            there.setdefault(credits._key(row["ref"]), []).append(
                (row["identifier"], row["kind"], row["credits"], row["amount_ar"]))
            paid |= {credits._key(row["ref"])} if row["amount_ar"] is not None else set()
    for line in here:
        if line["job"] is None:
            mine.setdefault(line["key"], []).append((line["shop"], line["kind"], line["credits"], line["amount"]))
            paid |= {line["key"]} if line["amount"] is not None else set()
    differs = {key for key in paid & mine.keys() if mine[key] != there.get(key, [])[:len(mine[key])]}
    # And a line here in the place of a kept one (same shop, kind, key) must be that line: a repayment typed under the
    # payment's reference would else pass for its reversal, and the payment be copied into a second shop.
    slots = {(line["shop"], line["kind"], line["key"]): (line["credits"], line["amount"], line["job"]) for line in here}
    differs |= {key for row in lines if (key := credits._key(row["ref"])) in paid
                and slots.get((row["identifier"], row["kind"], key), (row["credits"], row["amount_ar"], row["job_id"]))
                != (row["credits"], row["amount_ar"], row["job_id"])}
    held, copy, report, present = list(here), [], [], 0  # held: what this database will hold, line by line of the copy
    for row in lines:
        shop, key, what = row["identifier"], credits._key(row["ref"]), _kept_line(row)
        same = next((line for line in here if (line["shop"], line["kind"], line["key"]) == (shop, row["kind"], key)),
                    None)
        if row["job_id"] is not None:  # a repayment is here when its job is repaid here, whatever sits in its place
            repaid = next((line for line in here if line["job"] == row["job_id"]), None)
            if repaid is None and same is not None and not _unpaid(jobs_here.get(row["job_id"])):
                report.append(f"skipped {what}: its reference is used here by {same['name']} for another correction: "
                              f"repay job {row['job_id']} by hand under a reference not used yet (correct … --job)")
                continue
            same = repaid
        if same is not None:  # typed again after the restore, maybe in another spelling: never twice
            present += 1
            if same["ref"] != row["ref"]:
                report.append(f"here already: {what}, typed as {same['ref']!r} ({same['name']})")
            continue
        if key in differs and row["job_id"] is None:
            report.append(f"skipped {what}: this payment's lines here ("
                          + _named_lines([line for line in here if line["key"] == key])
                          + ") are not the first ones of its kept history: this database's history stands; check this "
                            "payment by hand (grant, move-payment)")
            continue
        if row["job_id"] is not None and (why := _unpaid(jobs_here.get(row["job_id"]))):
            report.append(f"skipped {what}: {why}")
            continue
        # 0014's unique key and payment triggers compare the stored text: a second spelling of one key would pass them.
        spelled = [line for line in held if line["shop"] == shop and line["key"] == key and line["ref"] != row["ref"]]
        if spelled:
            raise ValueError(f"{what} and {_named_lines(spelled)} write one reference two ways in {shop}: nothing "
                             "copied, nothing guessed")
        held.append({"shop": shop, "ref": row["ref"], "key": key, "name": f"line {row['id']} of the kept database"})
        copy.append(row)
    blocked = sorted({row["identifier"] for row in copy} - shops.keys())
    copied = apply and not blocked
    for row in copy:
        if copied:
            try:
                credits._line(conn, shops[row["identifier"]], row["kind"], row["credits"], row["ref"], row["actor"],
                              row["note"], origin=row["origin"], amount_ar=row["amount_ar"], method=row["method"],
                              job_id=row["job_id"], at=row["created_at"])
            except IntegrityError as error:
                raise ValueError(f"{_kept_line(row)} is refused here ({error.orig}): nothing copied") from None
        amount = f", {row['amount_ar']:+d} Ar" if row["amount_ar"] is not None else ""
        report.append(f"{'copied' if copied else 'to copy'}: {_kept_line(row)}, {row['credits']:+d} credits{amount}, "
                      f"written {row['created_at']} by {row['actor']}")
    lost = Counter(shop for id, shop in images if id not in jobs_here)
    report += [f"{shop}: {count} images made after the backup are gone and are not charged"
               for shop, count in sorted(lost.items())]
    for shop, id in sorted(shops.items()):
        now = credits.balance(conn, id)
        after = now["available"] + (0 if copied else sum(row["credits"] for row in copy if row["identifier"] == shop))
        if after < 0:
            report.append(f"{shop}: available {after} after the copy, below zero, with {now['pending']} generations "
                          "waiting or running: each of them that ends without an image gives one credit back; what "
                          "stays below zero is yours to settle")
    if missing := sorted(names.keys() - shops.keys()):
        report.append("shops of the kept database missing here: create each with this command, then run after-restore "
                      "again")
        report += ["  " + shlex.join(["python", "-m", "affiche.shops", "create", shop,
                                      *(["--name", names[shop]] if names[shop] else []), "--welcome", "0"])
                   for shop in missing]
    if not copy:
        report.append("nothing to copy")
    elif not apply:
        report.append("report only, nothing written: " + ("create the missing shops first, then run again with "
                                                          "--apply" if blocked else "run again with --apply to copy"))
    elif copied:
        report.append(f"copied {len(copy)} lines")
    return [f"the kept database {kept} holds {len(lines)} credit lines: {present} here already, {len(copy)} to copy, "
            f"{len(lines) - present - len(copy)} skipped", *report], blocked


class Refusal(Exception):
    """One line for the operator; nothing was written."""


def _shop(engine, identifier: str):
    with engine.connect() as conn:
        shop = find_shop(conn, identifier)
    if shop is None:
        raise Refusal(f"no shop has the identifier {identifier_key(identifier) or repr(identifier)}")
    return shop


def _named(shop) -> str:
    return f"{shop.identifier} (shop {shop.id}, « {shop.name or 'sans nom'} »)"


def _list(engine, _args):
    with engine.connect() as conn:
        for shop in list_shops(conn):
            print(f"{shop.id}\t{shop.identifier}\t{shop.state}\t{'password' if shop.has_password else 'no password'}"
                  f"\t{shop.created_at[:10]}\t{shop.name or ''}")


def _create(engine, args):
    password = new_password()
    password_hash = PASSWORDS.hash(password)  # Argon2 is slow on purpose: never inside the write transaction
    with write_tx(engine) as conn:
        try:
            id = create_shop(conn, args.identifier, args.name, password_hash)
        except IntegrityError:
            raise Refusal(f"the identifier {identifier_key(args.identifier)} is already taken") from None
        # In the shop's own transaction: a refused welcome leaves no shop behind (R-BALANCE-006).
        line = credits.grant(conn, id, args.welcome, origin="offered", ref="welcome", actor="operator",
                             note="Crédits de bienvenue") if args.welcome else None
    welcome = f"{args.welcome} offered welcome credits (line {line})" if line else "no welcome credits"
    print(f"shop {id} created: identifier {identifier_key(args.identifier)}, active, {welcome}\n"
          f"password (shown once, give it to the owner in person): {password}")


def _set_password(engine, args):
    shop = _shop(engine, args.identifier)
    password = new_password()
    password_hash = PASSWORDS.hash(password)
    with write_tx(engine) as conn:
        set_password(conn, shop.id, password_hash)
    print(f"new password for {_named(shop)}; every session of this shop ended\n"
          f"password (shown once, give it to the owner in person): {password}")


def _end_sessions(engine, args):
    shop = None if args.all or args.operator else _shop(engine, args.identifier)
    with write_tx(engine) as conn:
        done = [] if args.operator else [f"{end_sessions(conn, None if shop is None else shop.id)} sessions ended "
                                         f"({'every shop' if shop is None else _named(shop)})"]
        if shop is None:  # --all or --operator (D-ADMIN-007)
            done.append(f"{end_operator_sessions(conn)} operator sessions ended")
    print("; ".join(done))


def _operator_password(engine, _args):
    password = new_password(26)  # it controls every shop, with no second factor
    password_hash = PASSWORDS.hash(password)
    with write_tx(engine) as conn:
        ended = set_operator_password(conn, password_hash)
    print(f"new operator password; {ended} operator sessions ended\n"
          f"operator password (shown once; keep it in your password manager): {password}")


def _suspend(engine, args):
    shop = _shop(engine, args.identifier)
    if not args.yes:
        print(f"{_named(shop)}: {shop.state}")
        raise Refusal(f"nothing done: to suspend {shop.identifier}, run again with --yes")
    with write_tx(engine) as conn:
        cancelled = suspend(conn, shop.id)
    if cancelled is None:
        print(f"{_named(shop)} was already suspended: nothing changed")
    else:
        print(f"{_named(shop)} suspended: its sessions stop working (kept, they work again after enable); "
              f"{cancelled} queued jobs cancelled at no cost")


def _enable(engine, args):
    shop = _shop(engine, args.identifier)
    with write_tx(engine) as conn:
        changed = enable(conn, shop.id)
    print(f"{_named(shop)} {'enabled: its sessions work again' if changed else 'was already active: nothing changed'}")


def _usd(micros: int, rounding=ROUND_HALF_EVEN) -> str:
    return str((Decimal(micros) / 1_000_000).quantize(Decimal("0.01"), rounding))


def _number(typed: str) -> int:
    """A whole number one line can carry (credits.MOST): past it SQLite's integers, or the balance's SUM, overflow."""
    try:
        value = int(typed)
    except ValueError:
        value = None
    if value is None or abs(value) > credits.MOST:
        raise argparse.ArgumentTypeError(f"a whole number from {-credits.MOST:,} to {credits.MOST:,}: {typed!r}")
    return value


def _balance(conn, shop) -> str:
    now = credits.balance(conn, shop)
    return f"available {now['available']}, en attente {now['pending']}"


def _grant(engine, args):
    shop = _shop(engine, args.identifier)
    origin = "bought" if args.bought else "offered"
    with write_tx(engine) as conn:
        line = credits.grant(conn, shop.id, args.credits, origin=origin, ref=args.ref, actor="operator", note=args.note,
                             amount_ar=args.amount_ar, method=args.method)
        after, room = _balance(conn, shop.id), headroom(conn, args.settings)
    left, cost = room["cap"] - room["spent"], room["cost"]
    unit = f"average of the last {room['images']} images" if room["images"] else "ESTIMATE_SCENE_USD: no image cost yet"
    # What is left rounded down and the cost up, as the warning compares them.
    print(f"granted {args.credits} {origin} credits to {shop.identifier} (line {line}): {after}\n"
          f"service cap {_usd(room['cap'])} USD: {_usd(room['spent'])} spent since {args.settings.spend_cap_since}, "
          f"{_usd(left, ROUND_FLOOR)} left; credits outstanding in all shops {room['outstanding']} × "
          f"{room['unit'] / 1_000_000:.3f} USD ({unit}) = {_usd(cost, ROUND_CEILING)} USD")
    if cost > left:
        print("WARNING: the outstanding credits would cost more than what is left of the cap: raise SPEND_CAP_USD "
              "(deploy/README.md)")


def _move_payment(engine, args):
    source, destination = _shop(engine, args.source), _shop(engine, args.destination)
    with write_tx(engine) as conn:
        reversal, line = credits.move(conn, args.ref, source.id, destination.id, "operator", args.note)
        moved = (f"payment moved from {source.identifier} (line {reversal}: {_balance(conn, source.id)}) "
                 f"to {destination.identifier} (line {line}: {_balance(conn, destination.id)})")
    print(moved)


def _correct(engine, args):
    shop = _shop(engine, args.identifier)
    with write_tx(engine) as conn:
        line = credits.correct(conn, shop.id, args.credits, ref=args.ref, note=args.note, actor="operator",
                               amount_ar=args.amount_ar, job_id=args.job)
        after = _balance(conn, shop.id)
    what = [f"{args.credits:+d} credits"] if args.credits else []  # an amount fix changes no credit
    what += [f"{args.amount_ar:+d} Ar"] if args.amount_ar is not None else []
    what += [f"job {args.job} repaid"] if args.job else []
    print(f"corrected {shop.identifier} (line {line}): {', '.join(what)}; {after}")


def _pause(engine, args):
    if not args.yes:
        with engine.connect() as conn:
            since = jobs.paused(conn)
        print(f"the service is paused since {since}" if since else "the service is not paused")
        raise Refusal("nothing done: to pause new requests to the AI for every shop, run again with --yes")
    with write_tx(engine) as conn:
        changed, since = pause(conn), jobs.paused(conn)
    print(f"the service is paused since {since}: no new request reaches the AI for any shop (images, styles, text "
          "proposals, reads); what was admitted finishes; resume lifts it" if changed else
          f"the service was already paused since {since}: nothing changed")


def _resume(engine, _args):
    with write_tx(engine) as conn:
        changed = resume(conn)
    print("the service resumed: new requests reach the AI again" if changed else
          "the service was not paused: nothing changed")


def _purchase_text(engine, args):
    # Read back in the transaction that writes it: a failure rolls the text back, and no other writer comes between.
    with write_tx(engine) if args.text is not None else engine.connect() as conn:
        if args.text is not None:
            set_purchase_text(conn, args.text)
        stored = conn.execute(text("SELECT 1 FROM meta WHERE key='purchase_text_fr'")).first() is not None
        shown = credits.purchase_text(conn, args.settings)
    print(f"{'purchase text set' if args.text is not None else 'purchase text'}: « {shown} »"
          f"{'' if stored else ' (not set: the fallback every shop reads)'}")


def _after_restore(engine, args):
    with write_tx(engine) if args.apply else engine.connect() as conn:
        report, blocked = after_restore(conn, args.kept, apply=args.apply)
    print("\n".join(report))
    if args.apply and blocked:
        raise Refusal(f"nothing copied: {', '.join(blocked)} missing here; create each with the command above, then "
                      "run after-restore again")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m affiche.shops",
        description="The operator's shop and credit commands (D-MULTI-SHOP-003, D-BALANCE-005). Never migrates: the "
                    "database must be at this code's head. Exit codes: 0 done; 1 refused, nothing written; 2 usage.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="every shop: id, identifier, state, password or not, created, name").set_defaults(
        handler=_list)
    create = commands.add_parser("create", help="a new active shop; prints its password once")
    create.add_argument("identifier", help="3 to 32 letters or digits once case, accents, spaces and punctuation go")
    create.add_argument("--name", help="the shop's displayed name (the owner can change it)")
    create.add_argument("--welcome", type=_number, default=5,
                        help="offered credits granted with the shop, reference welcome (default 5); 0: none")
    create.set_defaults(handler=_create)
    reset = commands.add_parser("set-password", help="a new password, printed once; ends that shop's sessions")
    reset.add_argument("identifier")
    reset.set_defaults(handler=_set_password)
    end = commands.add_parser("end-sessions", help="sign one shop, every shop and the operator (after a restore), or the "
                                                   "operator alone, out everywhere")
    whom = end.add_mutually_exclusive_group(required=True)
    whom.add_argument("identifier", nargs="?")
    whom.add_argument("--all", action="store_true", help="every shop's sessions and the operator's")
    whom.add_argument("--operator", action="store_true", help="every operator session, and no shop's")
    end.set_defaults(handler=_end_sessions)
    commands.add_parser("operator-password", help="a new password for the operator's dashboard, printed once; ends every "
                                                  "operator session").set_defaults(handler=_operator_password)
    stop = commands.add_parser("suspend", help="stop a shop; enable reverses it. Without --yes, only shows the shop")
    stop.add_argument("identifier")
    stop.add_argument("--yes", action="store_true")
    stop.set_defaults(handler=_suspend)
    start = commands.add_parser("enable", help="a suspended shop works again, with its sessions")
    start.add_argument("identifier")
    start.set_defaults(handler=_enable)
    # A reference is stored as first typed and compared without case or extra spaces (credits.LINES' comment).
    grant = commands.add_parser("grant", help="credits to a shop, offered or bought; prints its balance and the cap's "
                                              "headroom")
    grant.add_argument("identifier")
    grant.add_argument("credits", type=_number)
    origin = grant.add_mutually_exclusive_group(required=True)
    origin.add_argument("--offered", action="store_true")
    origin.add_argument("--bought", action="store_true", help="with --amount-ar and --method")
    grant.add_argument("--amount-ar", type=_number, help="bought: the amount paid, in whole ariary")
    grant.add_argument("--method", help="bought: mvola, orange, airtel, cash, …")
    grant.add_argument("--ref", required=True, help="the payment's reference when bought, else one of your own; a shop "
                                                   "uses each once; case and extra spaces do not count")
    grant.add_argument("--note")
    grant.set_defaults(handler=_grant)
    move = commands.add_parser("move-payment", help="a whole payment, credits and ariary, to another shop; refused once "
                                                    "the source has spent some of its credits")
    move.add_argument("ref", help="the payment's reference")
    move.add_argument("source", help="the identifier of the shop that holds it")
    move.add_argument("destination", help="the identifier of the shop it belongs to")
    move.add_argument("--note", required=True, help="why")
    move.set_defaults(handler=_move_payment)
    correct = commands.add_parser("correct", help="credits added or taken back, a job repaid, or a mistyped amount fixed")
    correct.add_argument("identifier")
    correct.add_argument("credits", type=_number, help="+n or -n; +1 with --job; 0 with --amount-ar")
    correct.add_argument("--ref", required=True, help="one correction per reference and shop: under a payment's "
                                                     "reference, it uses the slot a move or an amount fix needs")
    correct.add_argument("--note", required=True, help="the reason")
    correct.add_argument("--job", help="a defective image repaid: its job id")
    correct.add_argument("--amount-ar", type=_number, help="the signed ariary that fix this shop's own payment")
    correct.set_defaults(handler=_correct)
    halt = commands.add_parser("pause", help="no new request to the AI for any shop; admitted ones finish. Without "
                                             "--yes, only says whether it is paused")
    halt.add_argument("--yes", action="store_true")
    halt.set_defaults(handler=_pause)
    commands.add_parser("resume", help="lifts the pause").set_defaults(handler=_resume)
    sentence = commands.add_parser("purchase-text", help="what a shop reads to buy credits; without a text, prints it")
    sentence.add_argument("text", nargs="?", help="the packs, the mobile money number, the reference to write, and when "
                                                  "credits arrive (1 to 500 characters)")
    sentence.set_defaults(handler=_purchase_text)
    restore = commands.add_parser("after-restore", help="after a restore: the credit lines of the database it replaced "
                                                        "that this one lacks; --apply copies them back")
    restore.add_argument("kept", type=Path, help="the database the restore replaced: "
                                                 "/data/affiche.db.before-restore-<time>, opened read-only")
    restore.add_argument("--apply", action="store_true", help="copy them in one transaction, in their order and with "
                                                              "their dates; without it, only report")
    restore.set_defaults(handler=_after_restore)
    return parser


def main(argv: Sequence[str] | None = None, env_file: Path | None = ENV_FILE) -> int:
    args = build_parser().parse_args(argv)  # a usage error exits 2 here
    engine = None
    try:
        args.settings = load_settings(env_file)  # grant's headroom and the purchase text's fallback read it
        database = args.settings.data_dir / "affiche.db"
        if not database.is_file():  # make_engine would create an empty one
            raise Refusal(f"no database at {database}: start the application once")
        engine = make_engine(database.parent)
        with engine.connect() as conn:
            version = MigrationContext.configure(conn).get_current_revision()
        head = ScriptDirectory.from_config(Config(BACKEND_DIR / "alembic.ini")).get_current_head()
        if version != head:
            raise Refusal(f"the database is at {version}, this code expects {head}: start the application of this "
                          "version once; this command never migrates")
        args.handler(engine, args)
        return 0
    except (Refusal, ConfigError, LookupError) as error:
        message = str(error)
    except ValidationError as error:  # the profile's own rule on the name
        message = f"name: {error.errors()[0]['msg']}"
    except ValueError as error:
        message = str(error)
    except SQLAlchemyError as error:  # the driver's message only: the statement's parameters may hold a hash
        message = str(getattr(error, "orig", None) or type(error).__name__)
    finally:
        if engine is not None:
            engine.dispose()
    print(f"refused: {message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
