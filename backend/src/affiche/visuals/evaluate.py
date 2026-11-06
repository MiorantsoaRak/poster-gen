"""The evaluation CLI (D-PRODUCT-VISUALS-008), owner 'cli'. Commands and exit codes: see build_parser (--help)."""

import argparse
import asyncio
import json
import sys
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import TextIO

from sqlalchemy import Connection, text

from affiche import assets, runtime
from affiche.config import ENV_FILE, ConfigError, Settings, load_settings
from affiche.db import utc_now, write_tx
from affiche.runtime import AlreadyRunning, ProviderModeMismatch, Runtime
from affiche.visuals.admission import LOW_RESOLUTION, Admitted, Refused, request_scene, spent_micros
from affiche.visuals.cutout import Cutout, CutoutUnavailable, MaskFn, make_cutout
from affiche.visuals.execution import execute
from affiche.visuals.fixtures import REF, FixtureError, Product, load_products
from affiche.visuals.gateway import RATES, OpenAIProvider, StubProvider, make_provider

EXIT_OK, EXIT_ERROR, EXIT_USAGE, EXIT_BUDGET = 0, 1, 2, 3
RUN_SIZE = "1088x1920"
MAX_ATTEMPT_LIMIT = 5  # runs.attempt_limit CHECK; 4-5 for the evaluation only (ADR-011)
REQUEST_NS = uuid.uuid5(uuid.NAMESPACE_URL, "urn:affiche:visuals:evaluate")  # the CLI's deterministic request ids
EXPECTED_REFUSALS = {"review_pending", "use_revision", "attempt_limit_reached", "abandoned"}  # the scope's state
UNEXPECTED = "unexpected"  # a task's outcome when it raised: the batch goes on, the command exits 1
Say = Callable[..., None]


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
    """A run's products are a snapshot (D-PV-008): a CSV row that changed since refuses the whole command."""
    with rt.engine.connect() as conn:
        snapshot = dict(conn.execute(text("SELECT variant_ref, fixture_row_sha256 FROM run_products"
                                          " WHERE run_label = :label"), {"label": label}).all())
    if changed := [product.variant_ref for product in products
                   if snapshot.get(product.variant_ref, product.row_sha256) != product.row_sha256]:
        raise _Refusal(f"the CSV rows of {', '.join(changed)} differ from run {label!r}'s snapshot:"
                       " restore them, or use a new --run label")


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
                "INSERT INTO run_products (run_label, variant_ref, arm, fixture_row_sha256, name, variant)"
                " VALUES (:label, :ref, :arm, :sha, :name, :variant) ON CONFLICT DO NOTHING"),
                {"label": label, "ref": product.variant_ref, "arm": product.arm, "sha": product.row_sha256,
                 "name": product.name, "variant": product.variant})
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
    cycle_no = conn.execute(text(  # no row = cycle 1
        "SELECT COALESCE((SELECT cycle_no FROM variant_cycles WHERE variant_ref = :ref), 1)"),
        {"ref": ref}).scalar_one()
    scope = {"ref": ref, "cycle_no": cycle_no, "label": label}
    in_scope = "variant_ref = :ref AND cycle_no = :cycle_no AND run_label = :label"
    failed = conn.execute(text(
        f"SELECT COUNT(*) FROM generation_requests WHERE {in_scope} AND purpose = 'scene' AND parent_id IS NULL"
        " AND status IN ('failed','interrupted')"), scope).scalar_one()
    has_cutout = conn.execute(text(
        f"SELECT EXISTS (SELECT 1 FROM cutouts WHERE {in_scope} AND status IN ('proposed','confirmed'))"),
        scope).scalar_one()
    return cycle_no, failed, bool(has_cutout)


async def _finish(rt: Runtime, label: str, provider: OpenAIProvider | StubProvider, mask_fn: MaskFn | None,
                  batch: _Batch, say: Say) -> list[str | None]:
    """The admitted requests and the cutouts, overlapped in this one event loop. Every task catches its own errors,
    so that none can cancel another (an unfinished paid call would stay running). Returns their outcomes."""
    slots = asyncio.Semaphore(2)  # ADR-019: one per event loop, shared by all its requests
    masking = asyncio.Semaphore(1)  # D-PV-006: one mask at a time, in a thread, beside the provider calls
    return await asyncio.gather(*(_scene(rt, provider, slots, job, admitted, say) for job, admitted in batch.scenes),
                                *(_cutout(rt, label, mask_fn, masking, job, say) for job in batch.cutouts))


async def _scene(rt: Runtime, provider: OpenAIProvider | StubProvider, slots: asyncio.Semaphore, job: _Job,
                 admitted: Admitted, say: Say) -> str | None:
    """The request's error kind (None when it succeeded), or UNEXPECTED."""
    try:
        await execute(rt.engine, rt.settings, provider, admitted.request_id, slots=slots)
        with rt.engine.connect() as conn:
            request = conn.execute(text("SELECT status, error_kind FROM generation_requests WHERE id = :id"),
                                   {"id": admitted.request_id}).one()
            kind = f" ({request.error_kind})" if request.error_kind else ""
            say(f"{job.ref}: scene attempt {admitted.attempt_no} {request.status}{kind};"
                f" {_committed_line(conn, rt.settings)}")
    except Exception as error:  # from execute, the request is failed (invalid_request) already
        say(f"{job.ref}: scene error: {type(error).__name__}: {error}")
        return UNEXPECTED
    return request.error_kind


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
