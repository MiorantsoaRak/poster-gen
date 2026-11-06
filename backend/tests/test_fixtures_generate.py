"""The fixtures CSV, runs and the CLI `generate` (T-PV-009), with the stub provider and injected masks: no network, no
model. Every photo is drawn here."""
import hashlib
import io
import json
from dataclasses import replace

import pytest
from PIL import Image, ImageDraw
from sqlalchemy import text

from affiche.runtime import start
from affiche.visuals import execution, review
from affiche.visuals.cutout import CutoutUnavailable
from affiche.visuals import evaluate
from affiche.visuals.evaluate import EXIT_BUDGET, EXIT_ERROR, EXIT_OK, EXIT_USAGE, build_parser, generate, main
from affiche.visuals.gateway import StubProvider
from affiche.visuals.prompts import Direction
from test_admission import _settings, settings  # noqa: F401  (settings: fixture, DATA_DIR = tmp_path)
from test_config import env  # noqa: F401  (fixture)
from test_cutout import centred_ellipse

HEADER = "variant_ref;name;variant;photos;price_ar;facts;mood;description;arm;notes"
P1 = "P1;Samsung Galaxy A15;Noir 128 Go;p1.jpg;899000;Garantie 6 mois;studio;;A;look-alike of A16"
P2 = "P2;Redmi 13;Bleu 256 Go;p2.jpg;699000;;neon;Fond sombre;B;"
LOW = "P3;Redmi 13;Vert 128 Go;low.jpg;;;;;A;"
NEW_RUN = ("--run", "r1", "--model", "gpt-image-2", "--quality", "medium")
UNREADABLE_RGB_PROFILE = b"\0" * 16 + b"RGB " + b"\0" * 108  # says RGB, but no ICC library can read it


class Masks:
    """A mask_fn: a centred ellipse (one product), or, for the photo of the given width, an exception or no product."""

    def __init__(self, by_width: dict | None = None) -> None:
        self.by_width = by_width or {}

    def __call__(self, image: Image.Image) -> Image.Image:
        outcome = self.by_width.get(image.width)
        if isinstance(outcome, Exception):
            raise outcome
        return Image.new("L", image.size, 0) if outcome == "empty" else centred_ellipse(image.size)


class Terminal(io.StringIO):
    def isatty(self) -> bool:
        return True


def _phone(path, size, **options):
    image = Image.new("RGB", size, (220, 215, 205))
    width, height = size
    ImageDraw.Draw(image).rounded_rectangle((width // 4, height // 4, 3 * width // 4, 3 * height // 4), 30, "black")
    image.save(path, format="JPEG", **options)


@pytest.fixture
def folder(tmp_path):
    """fixtures/ with photos/: p1 (900 px wide) and p2 (1000) are full size, low is 600 x 900."""
    photos = tmp_path / "fixtures" / "photos"
    photos.mkdir(parents=True)
    for name, size in {"p1.jpg": (900, 1200), "p2.jpg": (1000, 1200), "low.jpg": (600, 900)}.items():
        _phone(photos / name, size)
    return photos.parent


@pytest.fixture
def rt(settings):
    started = start(settings, "cli")
    yield started
    started.engine.dispose()
    started.lock_file.close()


def _csv(folder, *rows, name="products.csv"):
    path = folder / name
    path.write_text("\n".join([HEADER, *rows]) + "\n", encoding="utf-8")
    return path


def _generate(rt, csv, *options, mask_fn=None, stdin=None, provider=None):
    out = io.StringIO()
    args = build_parser().parse_args(["generate", "--fixtures", str(csv), *options])
    code = generate(rt, args, provider=provider or StubProvider(delay=0), mask_fn=mask_fn or Masks(),
                    stdin=stdin or io.StringIO(), out=out)
    return code, out.getvalue()


def _all(rt, sql):
    with rt.engine.connect() as conn:
        return conn.execute(text(sql)).all()


def _count(rt, table, where="1"):
    return _all(rt, f"SELECT COUNT(*) FROM {table} WHERE {where}")[0][0]


def _nothing_written(rt):
    return all(_count(rt, table) == 0 for table in ("runs", "run_products", "assets", "generation_requests",
                                                   "cutouts"))


# --- Validation -----------------------------------------------------------------------------------------------------

def test_every_validation_error_is_listed_and_nothing_loads(rt, folder):
    photos = folder / "photos"
    (photos / "fake.jpg").write_bytes(b"\0\0\0\x18ftypheic" + bytes(64))  # a HEIC renamed .jpg
    (photos / "broken.jpg").write_bytes(b"not an image")
    Image.new("CMYK", (900, 1200)).save(photos / "cmyk.jpg", format="JPEG")  # passes the provider rules only
    _phone(photos / "badicc.jpg", (900, 1200), icc_profile=UNREADABLE_RGB_PROFILE)  # passes the cutout rules only
    rows = ["P1;N;V;p1.jpg;;;;;A;", "P1;N;V;p2.jpg;;;;;A;", "bad ref!;N;V;p1.jpg;;;;;A;", "P5;N;V;missing.jpg;;;;;A;",
            "P6;N;V;photo.heic;;;;;A;", "P7;N;V;p1.jpg|p2.jpg|p1.jpg|p2.jpg;;;;;A;", "P8;N;V;p1.jpg;;;disco;;A;",
            "P9;N;V;p1.jpg;;;;Garantie 6 mois;A;", "P10;N;V;p1.jpg;;;;;;", "P11; ;V;p1.jpg;;;;;B;",
            "P12;N;V;fake.jpg;;;;;A;", "P13;N;V;broken.jpg;;;;;A;", "P14;N;V;cmyk.jpg;;;;;A;",
            "P15;N;V;badicc.jpg;;;;;A;", "P16;N;V;p1.jpg;;;;;A;extra;field"]
    code, out = _generate(rt, _csv(folder, *rows), *NEW_RUN, "--corrections", "by_arm")
    expected = ["row 3, variant_ref: 'P1' is already on row 2", "row 4, variant_ref: 'bad ref!' must match",
                "row 5, photos: missing.jpg: not found", "row 6, photos: photo.heic: HEIC/HEIF is not supported",
                "row 7, photos: 4 photo(s)", "row 8, mood: Input should be", "row 9, description: commercial terms",
                "row 10, arm: A or B (required with --corrections by_arm)", "row 11, name: required",
                "row 12, photos: fake.jpg: HEIC/HEIF is not supported", "row 13, photos: broken.jpg: cannot be decoded",
                "row 14, photos: cmyk.jpg: the photo is CMYK", "row 15, photos: badicc.jpg: the photo's ICC colour",
                "row 16: 11 fields, expected 10"]
    assert code == EXIT_USAGE
    assert f"{len(expected)} error(s), nothing loaded" in out
    for error in expected:
        assert error in out
    assert "row 2," not in out  # the valid row
    assert _nothing_written(rt)


def test_a_missing_column_is_refused(rt, folder):
    csv = folder / "products.csv"
    csv.write_text(HEADER.replace(";notes", "") + "\n" + P1.rpartition(";")[0] + "\n", encoding="utf-8")
    assert _generate(rt, csv, *NEW_RUN)[0] == EXIT_USAGE
    assert _nothing_written(rt)


def test_an_unclosed_quote_refuses_the_file_instead_of_swallowing_the_next_rows(rt, folder):
    unclosed = P1.rpartition(";")[0] + ';"look-alike of A16'  # without strict, P2 would become part of this note
    code, out = _generate(rt, _csv(folder, unclosed, P2), *NEW_RUN)
    assert code == EXIT_USAGE and "unexpected end of data (check the quotes)" in out
    assert _nothing_written(rt)


def test_a_utf8_bom_file_is_read(rt, folder):
    csv = folder / "products.csv"
    csv.write_text("\n".join([HEADER, P1]) + "\n", encoding="utf-8-sig")
    assert _generate(rt, csv, *NEW_RUN)[0] == EXIT_OK
    assert _all(rt, "SELECT name FROM run_products") == [("Samsung Galaxy A15",)]


# --- Runs -----------------------------------------------------------------------------------------------------------

def test_a_run_is_immutable_and_one_model_and_quality_is_one_run(rt, folder):
    csv = _csv(folder, P1, P2)
    assert _generate(rt, csv, *NEW_RUN)[0] == EXIT_OK

    code, out = _generate(rt, csv, "--run", "r2", "--model", "gpt-image-2", "--quality", "medium")
    assert code == EXIT_USAGE and "run 'r1' already has model gpt-image-2 and quality medium" in out
    code, out = _generate(rt, csv, "--run", "r1", "--quality", "high")
    assert code == EXIT_USAGE and "run 'r1' is immutable: quality 'high' (the run has 'medium')" in out
    code, out = _generate(rt, csv, "--run", "r1", "--attempt-limit", "4", "--corrections", "by_arm")
    assert code == EXIT_USAGE and "attempt_limit 4" in out and "corrections_mode 'by_arm'" in out
    assert _all(rt, "SELECT label, model, quality, size, attempt_limit, corrections_mode FROM runs") == [
        ("r1", "gpt-image-2", "medium", "1088x1920", 3, "on")]
    assert _count(rt, "generation_requests") == 2


@pytest.mark.parametrize(("options", "message"), [
    (("--run", "bad label", "--model", "gpt-image-2", "--quality", "medium"), "--run 'bad label' must match"),
    (("--run", "r1", "--model", "dall-e-3", "--quality", "medium"), "model 'dall-e-3' has no token rates"),
    (("--run", "r1", "--model", "gpt-image-2", "--quality", "xhigh"), "quality 'xhigh' is not one of"),
    (("--run", "r1", "--model", "gpt-image-2", "--quality", "auto"), "quality 'auto' is not one of"),
    (("--run", "r1", "--quality", "medium"), "a new run needs --model and --quality"),
])
def test_a_refused_new_run_writes_nothing(rt, folder, options, message):
    code, out = _generate(rt, _csv(folder, P1), *options)
    assert code == EXIT_USAGE and message in out
    assert _nothing_written(rt)


def test_a_new_run_takes_its_defaults_from_the_settings(rt, folder, env, tmp_path):
    rt = replace(rt, settings=_settings(env, DATA_DIR=str(tmp_path), OPENAI_IMAGE_MODEL="gpt-image-2.5-flare",
                                        OPENAI_IMAGE_QUALITY="xhigh", ATTEMPT_LIMIT="5"))
    assert _generate(rt, _csv(folder, P1), "--run", "r1")[0] == EXIT_OK
    assert _all(rt, "SELECT model, quality, attempt_limit, corrections_mode FROM runs") == [
        ("gpt-image-2.5-flare", "xhigh", 5, "on")]


def test_a_changed_csv_row_refuses_the_whole_command(rt, folder):
    assert _generate(rt, _csv(folder, P1, P2), *NEW_RUN, "--only", "P1")[0] == EXIT_OK
    calls = _all(rt, "SELECT id, cost_micros FROM provider_calls")

    code, out = _generate(rt, _csv(folder, P1.replace("look-alike", "lookalike"), P2), "--run", "r1")
    assert code == EXIT_USAGE and "the CSV rows of P1 differ from run 'r1'" in out
    assert _all(rt, "SELECT variant_ref FROM run_products") == [("P1",)]  # P2 was not taken either
    assert _count(rt, "generation_requests") == 1 and _count(rt, "cutouts") == 1
    assert _all(rt, "SELECT id, cost_micros FROM provider_calls") == calls

    code, out = _generate(rt, _csv(folder, P1.replace("look-alike", "lookalike"), P2), "--run", "r1", "--only", "P2")
    assert code == EXIT_USAGE and "the CSV rows of P1 differ" in out  # --only does not hide a changed row
    assert _count(rt, "generation_requests") == 1 and _count(rt, "run_products") == 1


# --- The paid opt-in (through main, with no env file) -----------------------------------------------------------------

@pytest.mark.parametrize(("provider", "paid", "message"), [
    ("openai", (), "refused: IMAGE_PROVIDER=openai spends money: add --paid"),
    ("stub", ("--paid",), "refused: --paid, but IMAGE_PROVIDER is stub: nothing would be paid"),
])
def test_the_paid_opt_in_must_match_the_provider_before_anything_starts(env, folder, tmp_path, capsys, provider,
                                                                        paid, message):
    data_dir = tmp_path / "data"
    env.setenv("DATA_DIR", str(data_dir))
    env.setenv("IMAGE_PROVIDER", provider)
    env.setenv("OPENAI_API_KEY", "sk-test-not-a-real-key")
    code = main(["generate", "--fixtures", str(_csv(folder, P1)), *NEW_RUN, *paid], env_file=None)
    captured = capsys.readouterr()
    assert code == EXIT_USAGE and message in captured.err
    assert "sk-test" not in captured.out + captured.err
    assert not data_dir.exists()  # runtime.start never ran: no lock, no database


# --- generate -------------------------------------------------------------------------------------------------------

def _row_sha256(row):
    fields = dict(zip(HEADER.split(";"), row.split(";"), strict=True))
    return hashlib.sha256(json.dumps(fields, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
                          ).hexdigest()


def test_generate_makes_one_scene_candidate_and_one_proposed_cutout_per_product(rt, folder):
    code, out = _generate(rt, _csv(folder, P1, P2), *NEW_RUN)
    assert code == EXIT_OK
    assert _all(rt, "SELECT variant_ref, arm, fixture_row_sha256, name, variant FROM run_products ORDER BY 1") == [
        ("P1", "A", _row_sha256(P1), "Samsung Galaxy A15", "Noir 128 Go"),
        ("P2", "B", _row_sha256(P2), "Redmi 13", "Bleu 256 Go")]
    assert _all(rt, "SELECT width, height FROM assets WHERE kind = 'original' ORDER BY width") == [
        (900, 1200), (1000, 1200)]
    assert _all(rt, "SELECT variant_ref, treatment, status, attempt_no, low_res_warning FROM candidates ORDER BY 1"
                ) == [("P1", "scene", "pending_review", 1, 0), ("P2", "scene", "pending_review", 1, 0)]
    cutouts = _all(rt, "SELECT c.variant_ref, c.status, c.bbox_json, c.direction_json, c.low_res_warning,"
                       " c.rembg_model, c.cycle_no, a.kind, a.width, s.kind FROM cutouts c"
                       " JOIN assets a ON a.sha256 = c.cutout_asset JOIN assets s ON s.sha256 = c.source_asset"
                       " ORDER BY 1")
    assert [(ref, status, direction, low_res, model, cycle, kind, width, source)
            for ref, status, _bbox, direction, low_res, model, cycle, kind, width, source in cutouts] == [
        ("P1", "proposed", Direction(mood="studio").model_dump_json(), 0, rt.settings.rembg_model, 1, "cutout", 900,
         "original"),
        ("P2", "proposed", Direction(mood="neon", description="Fond sombre").model_dump_json(), 0,
         rt.settings.rembg_model, 1, "cutout", 1000, "original")]
    for _ref, _status, bbox, *_rest in cutouts:
        assert len(json.loads(bbox)) == 4 and all(type(value) is int for value in json.loads(bbox))
    assert "P1: scene attempt 1 succeeded; committed $" in out  # the other request may still hold its reservation
    assert out.count("committed = the recorded costs plus the reservations of the calls still running") == 1
    assert "P2: cutout proposed" in out
    assert out.endswith("\ncommitted $0.00 / cap $20.00\n")  # the stub costs nothing once done


def test_a_rerun_makes_nothing_new(rt, folder):
    csv = _csv(folder, P1, P2)
    assert _generate(rt, csv, *NEW_RUN)[0] == EXIT_OK
    tables = ("generation_requests", "provider_calls", "candidates", "cutouts", "assets", "run_products")
    before = {table: _count(rt, table) for table in tables}

    code, out = _generate(rt, csv, *NEW_RUN)  # the same values as the run's are accepted
    assert code == EXIT_OK
    assert {table: _count(rt, table) for table in tables} == before
    assert "P1: scene attempt 1 already requested" in out and "cutout" not in out


@pytest.mark.parametrize(("decide", "statuses"), [
    (review.confirm_cutout, [("confirmed",)]),  # the scope has its cutout
    (review.reject_cutout, [("proposed",), ("rejected",)]),  # a rejected cutout is replaced
])
def test_a_rerun_makes_a_cutout_only_while_the_scope_has_none(rt, folder, decide, statuses):
    csv = _csv(folder, P1)
    assert _generate(rt, csv, *NEW_RUN)[0] == EXIT_OK
    decide(rt.engine, _all(rt, "SELECT id FROM cutouts")[0][0])
    assert _generate(rt, csv, "--run", "r1")[0] == EXIT_OK
    assert _all(rt, "SELECT status FROM cutouts ORDER BY status") == statuses


def test_after_a_failed_request_a_rerun_makes_a_new_one(rt, folder):
    csv = _csv(folder, P1)
    code, out = _generate(rt, csv, *NEW_RUN, provider=StubProvider(["auth"], delay=0))
    assert code == EXIT_OK and "P1: scene attempt 1 failed (auth)" in out
    assert _generate(rt, csv, "--run", "r1")[0] == EXIT_OK
    assert _generate(rt, csv, "--run", "r1")[0] == EXIT_OK
    assert _all(rt, "SELECT status FROM generation_requests ORDER BY created_at") == [("failed",), ("succeeded",)]
    assert _count(rt, "cutouts") == 1


def test_only_limits_the_products(rt, folder):
    csv = _csv(folder, P1, P2)
    code, out = _generate(rt, csv, *NEW_RUN, "--only", "P9,P2")
    assert code == EXIT_USAGE and "--only: not in the fixtures: P9" in out
    assert _generate(rt, csv, *NEW_RUN, "--only", "P2")[0] == EXIT_OK
    for table in ("run_products", "generation_requests", "cutouts"):
        assert _all(rt, f"SELECT DISTINCT variant_ref FROM {table}") == [("P2",)]


def test_budget_exhausted_admits_what_fits_lists_the_rest_and_exits_3(rt, folder, env, tmp_path):
    rt = replace(rt, settings=_settings(env, DATA_DIR=str(tmp_path), SPEND_CAP_USD="0.5"))  # one 0.40 reservation
    code, out = _generate(rt, _csv(folder, P1, P2), *NEW_RUN)
    assert code == EXIT_BUDGET
    assert "budget_exhausted: not started: P2" in out
    assert _all(rt, "SELECT variant_ref, status FROM generation_requests") == [("P1", "succeeded")]
    assert _all(rt, "SELECT variant_ref FROM cutouts") == [("P1",)]


def test_a_retry_refused_by_the_budget_also_exits_3(rt, folder, env, tmp_path, monkeypatch):
    monkeypatch.setattr(execution, "RETRY_DELAY_S", 0)
    rt = replace(rt, settings=_settings(env, DATA_DIR=str(tmp_path), SPEND_CAP_USD="0.5"))
    code, out = _generate(rt, _csv(folder, P1), *NEW_RUN, provider=StubProvider(["rate_limited"], delay=0))
    assert code == EXIT_BUDGET and "P1: scene attempt 1 failed (budget_exhausted)" in out
    assert "not started" not in out


class FirstCallRaises(StubProvider):
    """A bug in the first call: execute fails that request and re-raises."""

    def __init__(self) -> None:
        super().__init__(delay=0)
        self.calls = 0

    async def generate(self, **request):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("bug")
        return await super().generate(**request)


def test_an_unexpected_request_error_stays_with_its_request_and_exits_1(rt, folder):
    code, out = _generate(rt, _csv(folder, P1, P2), *NEW_RUN, provider=FirstCallRaises())
    assert code == EXIT_ERROR and "scene error: RuntimeError: bug" in out
    assert sorted(_all(rt, "SELECT status, error_kind FROM generation_requests")) == [
        ("failed", "invalid_request"), ("succeeded", None)]
    assert _count(rt, "cutouts", "status = 'proposed'") == 2


def test_a_cutout_that_cannot_be_stored_does_not_cancel_a_running_request(rt, folder, monkeypatch):
    def disk_full(*_args):
        raise OSError("disk full")

    monkeypatch.setattr(evaluate, "_insert_cutout", disk_full)
    # The masks finish while the provider still sleeps: an escaping error would cancel the running requests.
    code, out = _generate(rt, _csv(folder, P1, P2), *NEW_RUN, provider=StubProvider(delay=0.5))
    assert code == EXIT_ERROR and "P1: cutout_error: OSError: disk full" in out
    assert _all(rt, "SELECT status FROM generation_requests") == [("succeeded",), ("succeeded",)]
    assert _count(rt, "candidates") == 2 and _count(rt, "cutouts") == 0


def test_a_replay_with_another_payload_is_reported_and_exits_1(rt, folder, env, tmp_path):
    csv = _csv(folder, P1)
    assert _generate(rt, csv, *NEW_RUN)[0] == EXIT_OK
    # P1 (900 px) becomes low-resolution: the acknowledgement changes its request payload under the same id.
    rt = replace(rt, settings=_settings(env, DATA_DIR=str(tmp_path), MIN_SOURCE_SHORT_EDGE="1000"))
    code, out = _generate(rt, csv, "--run", "r1", "--acknowledge-low-res")
    assert code == EXIT_ERROR and "P1: scene refused: request_id_reused" in out
    assert _count(rt, "generation_requests") == 1


def test_a_low_resolution_product_needs_the_acknowledgement(rt, folder):
    csv = _csv(folder, P1, LOW)
    code, out = _generate(rt, csv, *NEW_RUN)  # stdin is not a terminal
    assert code == EXIT_OK and "P3: low.jpg below 800 px on the short edge: skipped" in out
    assert _all(rt, "SELECT DISTINCT variant_ref FROM generation_requests") == [("P1",)]

    code, out = _generate(rt, csv, "--run", "r1", "--acknowledge-low-res")
    # P1 has no low-resolution photo, so the flag leaves its payload unchanged: a replay, not request_id_reused.
    assert code == EXIT_OK and "P1: scene attempt 1 already requested" in out and "refused" not in out
    assert _all(rt, "SELECT low_res_warning FROM candidates WHERE variant_ref = 'P3'") == [(1,)]
    assert _all(rt, "SELECT low_res_warning FROM cutouts WHERE variant_ref = 'P3'") == [(1,)]


@pytest.mark.parametrize(("answer", "requested"), [("y\n", 1), ("\n", 0), ("n\n", 0)])
def test_a_terminal_is_asked_once_per_low_resolution_product(rt, folder, answer, requested):
    code, out = _generate(rt, _csv(folder, LOW), *NEW_RUN, stdin=Terminal(answer))
    assert code == EXIT_OK and "Use them anyway? [y/N]" in out
    assert _count(rt, "generation_requests") == requested == _count(rt, "cutouts")


@pytest.mark.parametrize(("error", "message"), [
    (RuntimeError("inference failed"), "P1: cutout_error: RuntimeError: inference failed"),
    (MemoryError("out of memory"), "P1: cutout_error: MemoryError: out of memory"),
    (CutoutUnavailable("model missing"), "P1: cutout_unavailable: model missing"),
])
def test_a_cutout_error_stays_with_its_product_and_exits_1(rt, folder, error, message):
    code, out = _generate(rt, _csv(folder, P1, P2), *NEW_RUN, mask_fn=Masks({900: error}))
    assert code == EXIT_ERROR and message in out
    assert _all(rt, "SELECT variant_ref, status FROM cutouts") == [("P2", "proposed")]
    assert _count(rt, "candidates", "status = 'pending_review'") == 2


def test_a_failed_cutout_is_recorded_with_its_reason(rt, folder):
    code, out = _generate(rt, _csv(folder, P1, P2), *NEW_RUN, mask_fn=Masks({900: "empty"}))
    assert code == EXIT_OK and "P1: cutout failed (no_product)" in out
    assert _all(rt, "SELECT variant_ref, status, failure_reason, cutout_asset, bbox_json FROM cutouts ORDER BY 1"
                )[0] == ("P1", "failed", "no_product", None, None)
    assert _count(rt, "cutouts", "status = 'proposed'") == 1
