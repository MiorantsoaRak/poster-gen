"""The evaluation CLI (D-PRODUCT-VISUALS-008), owner 'cli'. Commands and exit codes: see build_parser (--help)."""

import argparse
import asyncio
import codecs
import csv
import hashlib
import io
import itertools
import json
import re
import sys
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import TextIO

from sqlalchemy import Connection, Engine, Row, text

from affiche import assets, runtime
from affiche.config import ENV_FILE, ConfigError, Settings, load_settings
from affiche.db import utc_now, write_tx
from affiche.runtime import AlreadyRunning, ProviderModeMismatch, Runtime
from affiche.visuals import review
from affiche.visuals.admission import (
    LOW_RESOLUTION, Admitted, Refused, request_background, request_revision, request_scene, spent_micros,
)
from affiche.visuals.cutout import Cutout, CutoutUnavailable, MaskFn, make_cutout
from affiche.visuals.execution import execute
from affiche.visuals.fixtures import REF, FixtureError, Product, load_products
from affiche.visuals.gateway import RATES, OpenAIProvider, StubProvider, make_provider
from affiche.visuals.sheet import COLUMNS, IN_SCOPE, TREATMENTS, write_sheet

EXIT_OK, EXIT_ERROR, EXIT_USAGE, EXIT_BUDGET = 0, 1, 2, 3
RUN_SIZE = "1088x1920"
MAX_ATTEMPT_LIMIT = 5  # runs.attempt_limit CHECK; 4-5 for the evaluation only (ADR-011)
REQUEST_NS = uuid.uuid5(uuid.NAMESPACE_URL, "urn:affiche:visuals:evaluate")  # the CLI's deterministic request ids
EXPECTED_REFUSALS = {"review_pending", "use_revision", "attempt_limit_reached", "abandoned"}  # the scope's state
UNEXPECTED = "unexpected"  # a task's outcome when it raised: the batch goes on, the command exits 1
Say = Callable[..., None]

# apply (D-PV-008): per action, the kinds it takes and the optional columns it reads.
CANDIDATE_DECISIONS = {"approve": "approved", "reject": "rejected"}
CUTOUT_DECISIONS = {"confirm_cutout": "confirmed", "reject_cutout": "rejected"}
GENERATIONS = ("revise", "background")
KINDS = {"approve": TREATMENTS, "reject": TREATMENTS, "confirm_cutout": ("cutout",), "reject_cutout": ("cutout",),
         "abandon": TREATMENTS, "revise": TREATMENTS, "background": ("cutout",)}
READS = {"approve": {"framing"}, "reject": {"reasons", "note"}, "abandon": {"note"}}
SCOPE_ID = re.compile(rf"({REF.pattern}):({REF.pattern}):([1-9][0-9]*)")  # variant_ref:run_label:cycle_no


class _Refusal(Exception):
    """Ends the command with exit 2, before anything is written."""


@dataclass
class _Job:
    product: Product
    photo_assets: list[str]  # the photos' sha256, in CSV order
    low_res: bool  # some photo is low-resolution, and that was acknowledged
    cycle_no: int = 1

    @property
    def ref(self) -> str:
        return self.product.variant_ref


@dataclass
class _Batch:
    scenes: list[tuple[_Job, Admitted]] = field(default_factory=list)  # admitted now: to execute
    cutouts: list[_Job] = field(default_factory=list)  # their scope has no proposed or confirmed cutout
    not_started: list[str] = field(default_factory=list)  # from the first budget refusal on
    errors: int = 0  # refusals that are not the scope's state: request_id_reused, or a bug


def qualities(model: str) -> tuple[str, ...]:
    """The SDK's images.edit docstring (openai 3.46.0): low, medium and high for GPT image models, plus xhigh and max
    for the gpt-image-2.5 ones. Not "auto": a run names the quality it measures."""
    return ("low", "medium", "high") + (("xhigh", "max") if model.startswith("gpt-image-2.5-") else ())


def generate(rt: Runtime, args: argparse.Namespace, *, provider: OpenAIProvider | StubProvider | None = None,
             mask_fn: MaskFn | None = None, stdin: TextIO | None = None, out: TextIO | None = None) -> int:
    say = partial(print, file=out or sys.stdout, flush=True)
    try:
        config, new = _run_config(rt, args)
        products = load_products(args.fixtures, args.photos or args.fixtures.parent / "photos",
                                 arm_required=config["corrections_mode"] == "by_arm")
        _refuse_changed_rows(rt, args.run, products)  # every row of the file, not only the --only ones
        products = _selected(products, args.only)
    except FixtureError as error:
        say(f"{args.fixtures}: {len(error.errors)} error(s), nothing loaded:", *error.errors, sep="\n  ")
        return EXIT_USAGE
    except _Refusal as refusal:
        say(f"refused: {refusal}")
        return EXIT_USAGE
    shas = _snapshot(rt, args.run, config, new, products)
    batch = _admit(rt, args.run, _acknowledge(rt.settings, products, shas, args.acknowledge_low_res,
                                              stdin or sys.stdin, say), say)
    say("committed = the recorded costs plus the reservations of the calls still running")
    outcomes = asyncio.run(_finish(rt, args.run, provider or make_provider(rt.settings), mask_fn, batch, say))
    with rt.engine.connect() as conn:
        say(_committed_line(conn, rt.settings))
    if batch.not_started:
        say(f"budget_exhausted: not started: {', '.join(batch.not_started)}")
    if batch.not_started or "budget_exhausted" in outcomes:
        return EXIT_BUDGET
    return EXIT_ERROR if batch.errors or UNEXPECTED in outcomes else EXIT_OK


def _run_config(rt: Runtime, args: argparse.Namespace) -> tuple[dict, bool]:
    """Run L's configuration, and whether L is new. A run is immutable, and a (model, quality) pair is one run, so that
    a new label cannot reset the scene allowance (D-PV-001)."""
    if not REF.fullmatch(args.run):
        raise _Refusal(f"--run {args.run!r} must match {REF.pattern}")
    given = {"model": args.model, "quality": args.quality, "attempt_limit": args.attempt_limit,
             "corrections_mode": args.corrections}
    with rt.engine.connect() as conn:
        run = conn.execute(text("SELECT * FROM runs WHERE label = :label"), {"label": args.run}).first()
        if run is None:
            config = _new_run_config(rt.settings, given)
            same = conn.execute(text("SELECT label FROM runs WHERE model = :model AND quality = :quality"),
                                {"model": config["model"], "quality": config["quality"]}).scalar()
            if same is not None:
                raise _Refusal(f"run {same!r} already has model {config['model']} and quality {config['quality']}:"
                               f" use --run {same}")
            return config, True
    config = {name: getattr(run, name) for name in given}
    if differ := [f"{name} {given[name]!r} (the run has {config[name]!r})" for name in given
                  if given[name] is not None and given[name] != config[name]]:
        raise _Refusal(f"run {args.run!r} is immutable: {', '.join(differ)}; use a new --run label")
    _require_rates(config["model"])
    return config, False


def _new_run_config(settings: Settings, given: dict) -> dict:
    model, quality = given["model"] or settings.openai_image_model, given["quality"] or settings.openai_image_quality
    if model is None or quality is None:
        raise _Refusal("a new run needs --model and --quality (or OPENAI_IMAGE_MODEL and OPENAI_IMAGE_QUALITY)")
    _require_rates(model)
    if quality not in qualities(model):
        raise _Refusal(f"quality {quality!r} is not one of {', '.join(qualities(model))} for {model}")
    attempt_limit = given["attempt_limit"] or settings.attempt_limit
    if attempt_limit > MAX_ATTEMPT_LIMIT:  # ATTEMPT_LIMIT has no upper bound of its own
        raise _Refusal(f"attempt limit {attempt_limit}: a run takes 1 to {MAX_ATTEMPT_LIMIT} (set --attempt-limit)")
    return {"model": model, "quality": quality, "attempt_limit": attempt_limit,
            "corrections_mode": given["corrections_mode"] or "on"}


def _require_rates(model: str) -> None:
    if model not in RATES:  # ADR-015: no budget is reserved for a model without token rates
        raise _Refusal(f"model {model!r} has no token rates; known models: {', '.join(RATES)}")


def _selected(products: list[Product], only: list[str] | None) -> list[Product]:
    if only is None:
        return products
    if unknown := sorted(set(only) - {product.variant_ref for product in products}):
        raise _Refusal(f"--only: not in the fixtures: {', '.join(unknown)}")
    return [product for product in products if product.variant_ref in only]


def _refuse_changed_rows(rt: Runtime, label: str, products: list[Product]) -> None:
    """Check the whole supplied fixture before --only, asset writes or spend (D-PV-008)."""
    with rt.engine.connect() as conn:
        snapshot = {row.variant_ref: row for row in conn.execute(text(
            "SELECT variant_ref, fixture_row_sha256, photo_assets_json FROM run_products WHERE run_label = :label"),
            {"label": label})}
    if changed := [product.variant_ref for product in products
                   if product.variant_ref in snapshot
                   and snapshot[product.variant_ref].fixture_row_sha256 != product.row_sha256]:
        raise _Refusal(f"the CSV rows of {', '.join(changed)} differ from run {label!r}'s snapshot:"
                       " restore them, or use a new --run label")
    if legacy := [product.variant_ref for product in products
                  if product.variant_ref in snapshot and snapshot[product.variant_ref].photo_assets_json is None]:
        raise _Refusal(f"run {label!r} has no original-photo snapshot for {', '.join(legacy)}:"
                       " legacy inputs cannot be verified; use sheet/apply on stored assets, not generate")
    if changed := [product.variant_ref for product in products if product.variant_ref in snapshot
                   and json.loads(snapshot[product.variant_ref].photo_assets_json)
                   != [hashlib.sha256(photo.data).hexdigest() for photo in product.photos]]:
        raise _Refusal(f"the photo content of {', '.join(changed)} differs from run {label!r}'s snapshot:"
                       " restore the original files; no new work was started")


def _snapshot(rt: Runtime, label: str, config: dict, new: bool, products: list[Product]) -> dict[str, list[str]]:
    """The run if new, the photos as 'original' assets and the missing run_products rows, in one transaction; the files
    are written first (ADR-017). Returns each product's photo sha256s, in CSV order."""
    data_dir = rt.settings.data_dir
    shas = {product.variant_ref: [assets.put(data_dir, photo.data, assets.extension(photo.mime))
                                  for photo in product.photos] for product in products}
    with write_tx(rt.engine) as conn:
        if new:
            conn.execute(text(
                "INSERT INTO runs (label, model, quality, size, attempt_limit, corrections_mode, created_at)"
                " VALUES (:label, :model, :quality, :size, :attempt_limit, :corrections_mode, :now)"),
                {"label": label, "size": RUN_SIZE, "now": utc_now(), **config})
        for product in products:
            for photo, sha in zip(product.photos, shas[product.variant_ref], strict=True):
                assets.record(conn, sha=sha, kind="original", mime=photo.mime, width=photo.width,
                              height=photo.height, size=len(photo.data))
            conn.execute(text(  # the rows already there have the same sha (_refuse_changed_rows)
                "INSERT INTO run_products (run_label, variant_ref, arm, fixture_row_sha256, name, variant,"
                " photo_assets_json) VALUES (:label, :ref, :arm, :sha, :name, :variant, :photos)"
                " ON CONFLICT DO NOTHING"),
                {"label": label, "ref": product.variant_ref, "arm": product.arm, "sha": product.row_sha256,
                 "name": product.name, "variant": product.variant,
                 "photos": json.dumps(shas[product.variant_ref])})
    return shas


def _acknowledge(settings: Settings, products: list[Product], shas: dict[str, list[str]], acknowledged: bool,
                 stdin: TextIO, say: Say) -> list[_Job]:
    """A product with a photo below MIN_SOURCE_SHORT_EDGE runs only once acknowledged (D-PV-003): by the flag, else by
    a y/N question on a terminal. Without a terminal it is skipped."""
    jobs, edge = [], settings.min_source_short_edge
    for product in products:
        low = [photo.name for photo in product.photos if min(photo.width, photo.height) < edge]
        if low and not acknowledged:
            warning = f"{product.variant_ref}: {', '.join(low)} below {edge} px on the short edge"
            if not stdin.isatty():
                say(f"{warning}: skipped (pass --acknowledge-low-res)")
                continue
            say(f"{warning}. Use them anyway? [y/N] ", end="")
            if stdin.readline().strip().lower() not in ("y", "yes"):
                say(f"{product.variant_ref}: skipped")
                continue
        jobs.append(_Job(product, shas[product.variant_ref], bool(low)))
    return jobs


def _admit(rt: Runtime, label: str, jobs: list[_Job], say: Say) -> _Batch:
    """The initial scene requests, in CSV order, until the budget refuses one."""
    batch = _Batch()
    for index, job in enumerate(jobs):
        with rt.engine.connect() as conn:
            job.cycle_no, failed, has_cutout = _scope(conn, label, job.ref)
        # k = the scope's failed or interrupted initial requests: a re-run finds the same request (no new spend), and
        # after a failure the next id is a new request.
        request_id = str(uuid.uuid5(REQUEST_NS, f"generate:{label}:{job.ref}:{job.cycle_no}:{failed}"))
        try:
            admitted = request_scene(rt.engine, rt.settings, id=request_id, variant_ref=job.ref, run_label=label,
                                     owner="cli", variant_photos=job.photo_assets, direction=job.product.direction,
                                     acknowledged_warnings=[LOW_RESOLUTION] if job.low_res else [])
        except Refused as refusal:
            if refusal.code == "budget_exhausted":
                batch.not_started = [later.ref for later in jobs[index:]]
                return batch
            if refusal.code not in EXPECTED_REFUSALS:
                batch.errors += 1
            say(f"{job.ref}: scene refused: {refusal.code}")
        else:
            if admitted.existing:
                say(f"{job.ref}: scene attempt {admitted.attempt_no} already requested")
            else:
                batch.scenes.append((job, admitted))
        if not has_cutout:
            batch.cutouts.append(job)
    return batch


def _scope(conn: Connection, label: str, ref: str) -> tuple[int, int, bool]:
    """The variant's current cycle; in that scope, the failed or interrupted initial scene requests, and whether a
    proposed or confirmed cutout exists."""
    cycle_no = _current_cycle(conn, ref)
    scope = {"ref": ref, "cycle_no": cycle_no, "label": label}
    in_scope = "variant_ref = :ref AND cycle_no = :cycle_no AND run_label = :label"
    failed = conn.execute(text(
        f"SELECT COUNT(*) FROM generation_requests WHERE {in_scope} AND purpose = 'scene' AND parent_id IS NULL"
        " AND status IN ('failed','interrupted')"), scope).scalar_one()
    has_cutout = conn.execute(text(
        f"SELECT EXISTS (SELECT 1 FROM cutouts WHERE {in_scope} AND status IN ('proposed','confirmed'))"),
        scope).scalar_one()
    return cycle_no, failed, bool(has_cutout)


def _current_cycle(conn: Connection, ref: str) -> int:
    return conn.execute(text(  # no row = cycle 1
        "SELECT COALESCE((SELECT cycle_no FROM variant_cycles WHERE variant_ref = :ref), 1)"),
        {"ref": ref}).scalar_one()


async def _finish(rt: Runtime, label: str, provider: OpenAIProvider | StubProvider, mask_fn: MaskFn | None,
                  batch: _Batch, say: Say) -> list[str | None]:
    """The admitted requests and the cutouts, overlapped in this one event loop. Every task catches its own errors,
    so that none can cancel another (an unfinished paid call would stay running). Returns their outcomes."""
    slots = asyncio.Semaphore(2)  # ADR-019: one per event loop, shared by all its requests
    masking = asyncio.Semaphore(1)  # D-PV-006: one mask at a time, in a thread, beside the provider calls
    results = await asyncio.gather(*(_scene(rt, provider, slots, f"{job.ref}: scene", admitted, say)
                                     for job, admitted in batch.scenes),
                                   *(_cutout(rt, label, mask_fn, masking, job, say) for job in batch.cutouts))
    scenes = len(batch.scenes)
    return [UNEXPECTED if raised else outcome for outcome, raised in results[:scenes]] + results[scenes:]


async def _scene(rt: Runtime, provider: OpenAIProvider | StubProvider, slots: asyncio.Semaphore, name: str,
                 admitted: Admitted, say: Say) -> tuple[str | None, bool]:
    """Executes an admitted request, printed as `name`. Returns its outcome as stored (None when it succeeded, else
    its error kind, or its status when it has none; UNEXPECTED if it cannot be read), and whether an exception was
    raised on the way, in the execution or in the report: that makes the command exit 1."""
    outcome, raised = UNEXPECTED, False
    try:
        await execute(rt.engine, rt.settings, provider, admitted.request_id, slots=slots)
    except Exception as error:  # execute marks the request failed (invalid_request) before re-raising
        say(f"{name} error: {type(error).__name__}: {error}")
        raised = True
    try:
        with rt.engine.connect() as conn:
            request = conn.execute(text("SELECT status, error_kind FROM generation_requests WHERE id = :id"),
                                   {"id": admitted.request_id}).one()
            outcome = None if request.status == "succeeded" else request.error_kind or request.status
            kind = f" ({request.error_kind})" if request.error_kind else ""
            say(f"{name} attempt {admitted.attempt_no} {request.status}{kind}; {_committed_line(conn, rt.settings)}")
    except Exception as error:  # in the report: the outcome read before it stands
        say(f"{name} error: {type(error).__name__}: {error}")
        raised = True
    return outcome, raised


async def _cutout(rt: Runtime, label: str, mask_fn: MaskFn | None, masking: asyncio.Semaphore, job: _Job,
                  say: Say) -> str | None:
    """The cutout of the first photo (D-PV-006 step 1): None, or UNEXPECTED when it could not be made or stored
    (ADR-016: an error stays with its product)."""
    settings = rt.settings
    try:
        async with masking:
            result = await asyncio.to_thread(make_cutout, job.product.photos[0].data, mask_fn=mask_fn,
                                             rembg_model=settings.rembg_model, max_hole_ratio=settings.max_hole_ratio)
        _insert_cutout(rt, label, job, result)
    except CutoutUnavailable as error:
        say(f"{job.ref}: cutout_unavailable: {error}")
        return UNEXPECTED
    except Exception as error:  # MemoryError, an inference error, a file or database error: this product only
        say(f"{job.ref}: cutout_error: {type(error).__name__}: {error}")
        return UNEXPECTED
    say(f"{job.ref}: cutout " + ("proposed" if result.failure_reason is None else f"failed ({result.failure_reason})"))
    return None


def _insert_cutout(rt: Runtime, label: str, job: _Job, result: Cutout) -> None:
    """ADR-019: a proposed cutout has its asset and bbox_json = [x, y, w, h]; a failed one has only its reason."""
    source, settings = job.product.photos[0], rt.settings
    sha = None if result.png is None else assets.put(settings.data_dir, result.png, assets.extension("image/png"))
    with write_tx(rt.engine) as conn:
        if sha is not None:  # the cutout has the oriented source's size (D-PV-006)
            assets.record(conn, sha=sha, kind="cutout", mime="image/png", width=source.width, height=source.height,
                          size=len(result.png))
        conn.execute(text(
            "INSERT INTO cutouts (id, variant_ref, run_label, direction_json, source_asset, cutout_asset, bbox_json,"
            " status, failure_reason, low_res_warning, rembg_model, created_at, cycle_no) VALUES (:id, :ref, :label,"
            " :direction, :source, :cutout, :bbox, :status, :reason, :low_res, :model, :now, :cycle_no)"),
            {"id": str(uuid.uuid4()), "ref": job.ref, "label": label,
             "direction": job.product.direction.model_dump_json(), "source": job.photo_assets[0], "cutout": sha,
             "bbox": None if result.bbox is None else json.dumps(result.bbox),
             "status": "failed" if sha is None else "proposed", "reason": result.failure_reason,
             "low_res": int(min(source.width, source.height) < settings.min_source_short_edge),
             "model": settings.rembg_model, "now": utc_now(), "cycle_no": job.cycle_no})


def _committed_line(conn: Connection, settings: Settings) -> str:
    return f"committed ${spent_micros(conn, settings) / 1_000_000:.2f} / cap ${settings.spend_cap_usd:.2f}"


# --- sheet, apply, new-cycle ----------------------------------------------------------------------------------------

def sheet(rt: Runtime, args: argparse.Namespace, *, out: TextIO | None = None) -> int:
    say = partial(print, file=out or sys.stdout, flush=True)
    decisions = args.out / "decisions.csv"
    if decisions.exists():  # it may hold the operator's decisions
        say(f"refused: {decisions} exists: choose another --out")
        return EXIT_USAGE
    with rt.engine.connect() as conn:
        if args.run is not None and not conn.execute(text("SELECT 1 FROM runs WHERE label = :label"),
                                                     {"label": args.run}).first():
            say(f"refused: unknown run {args.run!r}")
            return EXIT_USAGE
        try:
            candidates, cutouts, rows = write_sheet(conn, rt.settings.data_dir, args.out, args.run)
        except OSError as error:
            say(f"error: {type(error).__name__}: {error}")
            return EXIT_ERROR
    say(f"{args.out / 'sheet.html'}: {candidates} candidate(s) and {cutouts} cutout(s) to review")
    say(f"{decisions}: {rows} row(s); fill in the action column, then run apply")
    return EXIT_OK


@dataclass
class _Line:
    """A decisions.csv row: its values as read, for apply-result.csv, and its stripped fields."""

    number: int
    values: list[str]
    target: str
    kind: str
    action: str
    reasons: list[str]
    note: str | None
    framing: str
    result: str = ""
    request_id: str | None = None  # a generation's uuid5 id, with its k
    name: str = ""  # a generation's prefix in the output


class _RowError(Exception):
    """A row that fails apply's validation."""


def apply(rt: Runtime, args: argparse.Namespace, *, provider: OpenAIProvider | StubProvider | None = None,
          out: TextIO | None = None) -> int:
    say = partial(print, file=out or sys.stdout, flush=True)
    header, lines, errors = _read_decisions(args.file)
    with rt.engine.connect() as conn:
        errors += _validate(conn, lines)
    if errors:
        say(f"{args.file}: {len(errors)} error(s), nothing applied:", *errors, sep="\n  ")
        return EXIT_USAGE
    failures = 0
    for line in (line for line in lines if line.action and line.action not in GENERATIONS):  # step 2, in file order
        try:
            line.result = _decide(rt.engine, line)
        except Exception as error:  # this row only (ADR-022): the other rows are independent
            line.result = _error(line, error, say)
        say(f"row {line.number}: {line.action} {line.target}: {line.result}")
        failures += line.result not in ("applied", "already_applied")  # the row was valid a moment ago
    generations = [line for line in lines if line.action in GENERATIONS]
    new, admission_errors = _admit_generations(rt, generations, say)
    results = []
    if new:
        say("committed = the recorded costs plus the reservations of the calls still running")
        results = asyncio.run(_execute_generations(rt, provider or make_provider(rt.settings), new, say))
    for (line, _), (outcome, raised) in zip(new, results, strict=True):
        line.result = "applied" if outcome is None else f"request_failed:{outcome}"  # what the database holds
        failures += raised
    with rt.engine.connect() as conn:
        say(_committed_line(conn, rt.settings))
    say(f"{_write_results(args.file, header, lines)}: the result of each row")
    if not_started := [f"row {line.number}" for line in generations if line.result == "not_started"]:
        say(f"budget_exhausted: not started: {', '.join(not_started)}")
    if any(line.result.endswith(":budget_exhausted") for line in generations):  # refused or request_failed
        return EXIT_BUDGET
    return EXIT_ERROR if failures or admission_errors else EXIT_OK


def _error(line: _Line, error: Exception, say: Say) -> str:
    say(f"row {line.number}: {type(error).__name__}: {error}")
    return f"error:{type(error).__name__}"


def _read_decisions(path: Path) -> tuple[list[str], list[_Line], list[str]]:
    """The header, the rows (blank ones dropped; a blank action is kept, then skipped) and the format errors. ';' and
    strict quotes, so a broken quote cannot swallow the rows after it."""
    try:
        content = _decode(path.read_bytes())
    except OSError as error:
        return [], [], [f"{path}: cannot be read: {error}"]
    except UnicodeDecodeError as error:
        return [], [], [f"{path}: not UTF-8 (with or without a BOM) nor Windows-1252 text: {error}"]
    reader = csv.reader(io.StringIO(content, newline=""), delimiter=";", strict=True)
    try:
        rows = [(reader.line_num, values) for values in reader]
    except csv.Error as error:
        return [], [], [f"row {reader.line_num}: {error} (check the quotes)"]
    header = [name.strip() for name in rows[0][1]] if rows else []
    if not set(COLUMNS) - {"info"} <= set(header) <= set(COLUMNS) or len(set(header)) < len(header):
        return [], [], [f"row 1: the header must have the columns {';'.join(COLUMNS[:-1])}, and optionally info"]
    lines, errors = [], []
    for number, values in rows[1:]:
        if not any(value.strip() for value in values):
            continue
        if len(values) != len(header):
            errors.append(f"row {number}: {len(values)} fields, expected {len(header)} (quote a value holding ';')")
            continue
        cells = {name: value.strip() for name, value in zip(header, values)}
        lines.append(_Line(number, values, cells["target_id"], cells["kind"], cells["action"],
                           [code.strip() for code in cells["reasons"].split(",") if code.strip()],
                           cells["note"] or None, cells["framing"]))
    return header, lines, errors


def _decode(data: bytes) -> str:
    """UTF-8 when it starts with the BOM; else UTF-8, and failing that cp1252, which Excel saves on a French Windows.
    Strict: a byte invalid in the chosen encoding raises UnicodeDecodeError, never a replacement character."""
    if data.startswith(codecs.BOM_UTF8):
        return data.removeprefix(codecs.BOM_UTF8).decode("utf-8")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp1252")


def _validate(conn: Connection, lines: list[_Line]) -> list[str]:
    """Step 1, writing nothing: each failing row's first error. The decisions are checked in file order, then the
    generations against the statuses the decisions leave, as steps 2 and 3 run them. A matching replay is valid."""
    errors: list[tuple[int, str]] = []
    first: dict[tuple[str, str, bool], int] = {}  # (target, kind, is a generation) -> its row
    statuses: dict[str, str] = {}  # candidate or cutout id -> its status after the file's decisions
    approved: set[tuple[str, str, int, str]] = set()  # (variant, run, cycle, treatment) approved by the file so far
    for line in sorted((line for line in lines if line.action), key=lambda line: line.action in GENERATIONS):
        try:
            _check_row(line, first)
            if line.action in GENERATIONS:
                _check_generation(conn, line, statuses)
            elif line.action == "abandon":
                _check_abandon(conn, line, approved)
            else:
                _check_decision(conn, line, statuses, approved)
        except _RowError as error:
            errors.append((line.number, f"row {line.number}: {line.action} {line.target}: {error}"))
    return [message for _, message in sorted(errors)]


def _check_row(line: _Line, first: dict[tuple[str, str, bool], int]) -> None:
    """The action, its kind and columns, and at most one decision and one generation per target."""
    if line.action not in KINDS:
        raise _RowError(f"unknown action; one of {', '.join(KINDS)}")
    if line.kind not in KINDS[line.action]:
        raise _RowError(f"kind {line.kind!r}: {line.action} takes {' or '.join(KINDS[line.action])}")
    given = {"reasons": line.reasons, "note": line.note, "framing": line.framing}
    if unread := [name for name, value in given.items() if value and name not in READS.get(line.action, ())]:
        raise _RowError(f"{line.action} does not read {' or '.join(unread)}: leave it blank")
    key = (line.target, line.kind, line.action in GENERATIONS)
    if key in first:
        raise _RowError(f"a second {'generation' if key[2] else 'decision'} for this target (row {first[key]})")
    first[key] = line.number


def _check_decision(conn: Connection, line: _Line, statuses: dict[str, str],
                    approved: set[tuple[str, str, int, str]]) -> None:
    """A matching replay passes, and is recognised before next_status, which refuses any move out of a final
    status. Cutouts have their own transitions."""
    row = _target(conn, line)
    if line.kind == "cutout":  # D-PV-006 step 2: proposed -> confirmed | rejected
        target = CUTOUT_DECISIONS[line.action]
        if row.status not in ("proposed", target):
            raise _RowError(f"invalid_transition: the cutout is {row.status}")
    else:
        target = CANDIDATE_DECISIONS[line.action]
        payload = _payload(line)
        if not (row.status == target and all(getattr(row, column) == value for column, value in payload.items())):
            try:
                review.next_status(row.status, line.action)
            except Refused:
                raise _RowError(f"invalid_transition: the candidate is {row.status}") from None
        if target == "approved":
            approved.add((row.variant_ref, row.run_label, row.cycle_no, row.treatment))
    statuses[line.target] = target


def _payload(line: _Line) -> dict[str, object]:
    """review.approve's and review.reject's input checks, and the canonical payload they store."""
    if line.action == "approve":
        if line.framing.lower() != "ok":
            raise _RowError("framing_not_checked: approve needs framing=ok (Produit entier dans les 3 formats)")
        return {"framing_checked": 1}
    try:
        codes, note = review.rejection_payload(line.reasons, line.note)
    except Refused as refusal:
        details = refusal.details or {}
        found = details.get("reasons") or details.get("matches")
        raise _RowError(f"{refusal.code}: {', '.join(found)}" if found else refusal.code) from None
    return {"rejection_reasons_json": json.dumps(codes), "rejection_note": note}


def _check_abandon(conn: Connection, line: _Line, approved: set[tuple[str, str, int, str]]) -> None:
    """review.abandon's refusals, checked here first; the replay first of all, so it holds after new-cycle."""
    if not (match := SCOPE_ID.fullmatch(line.target)):
        raise _RowError("not a scope id variant_ref:run_label:cycle_no")
    ref, run, cycle = match[1], match[2], int(match[3])
    scope = {"ref": ref, "run": run, "cycle": cycle, "treatment": line.kind}
    if conn.execute(text(f"SELECT 1 FROM abandonments WHERE {IN_SCOPE} AND treatment = :treatment"), scope).first():
        return
    if not conn.execute(text("SELECT 1 FROM run_products WHERE run_label = :run AND variant_ref = :ref"),
                        scope).first():
        raise _RowError(f"unknown scope: {ref} is not in run {run}")
    if cycle > (current := _current_cycle(conn, ref)):
        raise _RowError(f"wrong_scope: {ref} is in cycle {current}")
    # Any purpose, as review.abandon: else the file's other decisions would commit before its refusal. An API request
    # can be running: CLI startup recovers only the CLI's.
    if conn.execute(text(f"SELECT 1 FROM generation_requests WHERE {IN_SCOPE} AND status = 'running'"), scope).first():
        raise _RowError("request_running: a request of this scope is running")
    if (ref, run, cycle, line.kind) in approved or conn.execute(text(
            f"SELECT 1 FROM candidates WHERE {IN_SCOPE} AND treatment = :treatment AND status = 'approved'"),
            scope).first():
        raise _RowError(f"already_approved: the scope has an approved {line.kind}")


def _check_generation(conn: Connection, line: _Line, statuses: dict[str, str]) -> None:
    """The target's transition, after the file's decisions. Takes the request id: a request that exists is a replay.
    The scope's rules (abandoned, attempt limit, pending review, budget) stay admission's."""
    row = _target(conn, line)
    line.name = f"row {line.number}: {row.variant_ref} {line.action}"
    line.request_id, existing = _request_id(conn, line.target, line.action)
    if existing:
        return
    status = statuses.get(line.target, row.status)
    if line.action == "background":
        if status != "confirmed":
            raise _RowError(f"background needs a confirmed cutout; it is {status}")
        return
    if status != "rejected":
        raise _RowError(f"revise needs a rejected candidate; it is {status}")
    if conn.execute(text("SELECT 1 FROM generation_requests WHERE parent_id = :id"
                         " AND status IN ('running','succeeded')"), {"id": line.target}).first():
        raise _RowError("revision_already_requested")


def _target(conn: Connection, line: _Line) -> Row:
    table = "cutouts" if line.kind == "cutout" else "candidates"
    row = conn.execute(text(f"SELECT * FROM {table} WHERE id = :id"), {"id": line.target}).first()
    if row is None:
        raise _RowError(f"unknown {table[:-1]} id")
    if table == "candidates" and row.treatment != line.kind:
        raise _RowError(f"kind {line.kind}: the candidate is {row.treatment}")
    return row


def _request_id(conn: Connection, target: str, action: str) -> tuple[str, bool]:
    """uuid5(target:action:k), k = the first j whose request does not exist or neither failed nor was interrupted:
    a replay finds the same request (no new spend), and after a failure the next id is a new request. Also returns
    whether that request exists."""
    for k in itertools.count():
        request_id = str(uuid.uuid5(REQUEST_NS, f"{target}:{action}:{k}"))
        status = conn.execute(text("SELECT status FROM generation_requests WHERE id = :id"),
                              {"id": request_id}).scalar()
        if status not in ("failed", "interrupted"):
            return request_id, status is not None


def _decide(engine: Engine, line: _Line) -> str:
    """Step 2: review's conditional write; a replay returns already_applied, and a refusal is this row's result only."""
    try:
        if line.action == "approve":
            return review.approve(engine, line.target, framing_checked=True)
        if line.action == "reject":
            return review.reject(engine, line.target, reasons=line.reasons, note=line.note)
        if line.action == "confirm_cutout":
            return review.confirm_cutout(engine, line.target)
        if line.action == "reject_cutout":
            return review.reject_cutout(engine, line.target)
        ref, run, cycle = SCOPE_ID.fullmatch(line.target).groups()
        return review.abandon(engine, variant_ref=ref, run_label=run, cycle_no=int(cycle), treatment=line.kind,
                              note=line.note)
    except Refused as refusal:
        return f"refused:{refusal.code}"


def _admit_generations(rt: Runtime, lines: list[_Line], say: Say) -> tuple[list[tuple[_Line, Admitted]], int]:
    """Step 3's admissions, in file order, until the budget refuses one. Returns the new requests, and the number of
    rows refused for another reason than the scope's state or stopped by an unexpected error."""
    new, errors = [], 0
    for index, line in enumerate(lines):
        try:
            if line.action == "revise":
                admitted = request_revision(rt.engine, rt.settings, id=line.request_id, parent_id=line.target,
                                            owner="cli")
            else:
                admitted = request_background(rt.engine, rt.settings, id=line.request_id, cutout_id=line.target,
                                              owner="cli")
        except Refused as refusal:
            line.result = f"refused:{refusal.code}"
            say(f"{line.name}: {line.result}")
            if refusal.code == "budget_exhausted":
                for later in lines[index + 1:]:
                    later.result = "not_started"
                break
            errors += refusal.code not in EXPECTED_REFUSALS
            continue
        except Exception as error:  # this row only (ADR-022): the requests admitted before it still run
            line.result = _error(line, error, say)
            errors += 1
            continue
        if admitted.existing:
            line.result = "already_applied"
            say(f"{line.name} attempt {admitted.attempt_no}: {line.result}")
        else:
            new.append((line, admitted))
    return new, errors


async def _execute_generations(rt: Runtime, provider: OpenAIProvider | StubProvider,
                               new: list[tuple[_Line, Admitted]], say: Say) -> list[tuple[str | None, bool]]:
    slots = asyncio.Semaphore(2)  # ADR-019: one per event loop, shared by all its requests
    return await asyncio.gather(*(_scene(rt, provider, slots, line.name, admitted, say) for line, admitted in new))


def _write_results(path: Path, header: list[str], lines: list[_Line]) -> Path:
    """Step 4: apply-result.csv beside the file, its rows with a result column (the values: build_parser)."""
    results = path.with_name("apply-result.csv")
    with results.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file, delimiter=";")
        writer.writerow([*header, "result"])
        writer.writerows([*line.values, line.result] for line in lines)
    return results


def new_cycle(rt: Runtime, args: argparse.Namespace, *, out: TextIO | None = None) -> int:
    say = partial(print, file=out or sys.stdout, flush=True)
    refused = 0
    for sku in args.skus:
        try:
            say(f"{sku}: cycle {review.new_cycle(rt.engine, sku)}")
        except Refused as refusal:
            refused += 1
            say(f"{sku}: refused {refusal.code}")
    return EXIT_ERROR if refused else EXIT_OK


def _skus(value: str) -> list[str]:
    if not (skus := [sku.strip() for sku in value.split(",") if sku.strip()]):
        raise argparse.ArgumentTypeError("give at least one SKU")
    return skus


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m affiche.visuals.evaluate",
        description="Product-visuals evaluation (D-PV-008). One process at a time per data folder. Exit codes: "
                    "0 done; 1 configuration or startup refused, or an unexpected error in the batch (the other "
                    "products still finish); 2 usage or validation errors, nothing written; 3 budget exhausted.")
    commands = parser.add_subparsers(dest="command", required=True)
    generate_parser = commands.add_parser(
        "generate", help="create or resume a run: one scene request and one cutout per product",
        description="Creates the run LABEL (immutable) or resumes it: snapshots the products, then makes one scene "
                    "request and one cutout per product. Re-running it makes nothing new for what is done.")
    generate_parser.add_argument("--fixtures", type=Path, required=True, help="the products CSV (UTF-8, ';')")
    generate_parser.add_argument("--run", required=True, metavar="LABEL", help="the run label, [A-Za-z0-9_-]+")
    generate_parser.add_argument("--photos", type=Path, metavar="DIR",
                                 help="the photos folder (default: <CSV folder>/photos)")
    generate_parser.add_argument("--model", help=f"new run: {', '.join(RATES)} (default: OPENAI_IMAGE_MODEL)")
    generate_parser.add_argument("--quality", help="new run: low, medium or high; also xhigh or max for "
                                                   "gpt-image-2.5-* (default: OPENAI_IMAGE_QUALITY)")
    generate_parser.add_argument("--attempt-limit", type=int, choices=range(1, MAX_ATTEMPT_LIMIT + 1), metavar="1..5",
                                 help="new run: scene attempts per product (default: ATTEMPT_LIMIT)")
    generate_parser.add_argument("--corrections", choices=("on", "by_arm"), help="new run: default on")
    generate_parser.add_argument("--only", type=_skus, metavar="SKU,SKU", help="only these products")
    generate_parser.add_argument("--acknowledge-low-res", action="store_true",
                                 help="use low-resolution photos without asking")
    generate_parser.add_argument("--paid", action="store_true",
                                 help="required with IMAGE_PROVIDER=openai, refused with the stub")
    generate_parser.set_defaults(handler=generate)
    sheet_parser = commands.add_parser(
        "sheet", help="write the review page and a pre-filled decisions.csv",
        description="Writes DIR/sheet.html (static; its images in DIR/img) with every pending candidate and proposed "
                    "cutout, and DIR/decisions.csv (UTF-8 with BOM, ';'): a row for each of them, plus the revise, "
                    "background and abandon rows of the open scopes, all with an empty action.")
    sheet_parser.add_argument("--out", type=Path, required=True, metavar="DIR",
                              help="a folder with no decisions.csv yet")
    sheet_parser.add_argument("--run", metavar="LABEL", help="only this run")
    sheet_parser.set_defaults(handler=sheet)
    apply_parser = commands.add_parser(
        "apply", help="apply a filled-in decisions.csv",
        description="Validates every row first (one error: nothing is applied), applies the decisions in file order, "
                    "then makes the revise and background requests. Writes apply-result.csv beside FILE, with each "
                    "row's result: applied; already_applied; refused:<code>; request_failed:<error kind>; not_started "
                    "(not tried once the budget refused a request); error:<exception> (unexpected, exit 1); blank "
                    "for a blank action. Running the same file again resumes: what is done is already_applied, and a "
                    "failed or interrupted request is made anew.")
    apply_parser.add_argument("file", type=Path, metavar="FILE",
                              help="columns target_id;kind;action;reasons;note;framing (info is ignored); UTF-8, or "
                                   "Windows-1252 as Excel saves it")
    apply_parser.add_argument("--paid", action="store_true",
                              help="required with IMAGE_PROVIDER=openai, refused with the stub")
    apply_parser.set_defaults(handler=apply)
    cycle_parser = commands.add_parser(
        "new-cycle", help="start the next cycle of approved products",
        description="Starts cycle n+1 of each SKU whose cycle n has an approved candidate (D-PV-005). Exit 1 if one "
                    "is refused.")
    cycle_parser.add_argument("skus", nargs="+", metavar="SKU")
    cycle_parser.set_defaults(handler=new_cycle)
    return parser


def main(argv: Sequence[str] | None = None, env_file: Path | None = ENV_FILE) -> int:
    args = build_parser().parse_args(argv)  # a usage error exits 2 here
    try:
        settings = load_settings(env_file)
        # The paid opt-in is checked before anything starts. Every command that can spend takes --paid.
        if "paid" in vars(args) and args.paid != (settings.image_provider == "openai"):
            print("refused: " + ("--paid, but IMAGE_PROVIDER is stub: nothing would be paid" if args.paid else
                                 "IMAGE_PROVIDER=openai spends money: add --paid"), file=sys.stderr)
            return EXIT_USAGE
        started = runtime.start(settings, "cli")
    except (ConfigError, AlreadyRunning, ProviderModeMismatch) as error:
        print(f"error: {error}", file=sys.stderr)  # ConfigError never holds an input value, so never the key
        return EXIT_ERROR
    try:  # the Runtime lives for the whole command: closing its lock file releases the lock (ADR-017)
        return args.handler(started, args)
    finally:
        started.engine.dispose()
        started.lock_file.close()


if __name__ == "__main__":
    sys.exit(main())
