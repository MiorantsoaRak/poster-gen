"""The CLI `sheet`, `apply` and `new-cycle` (T-PV-010), on the stub data `generate` makes (T-PV-009): the stub
provider and drawn masks, no network."""
import codecs
import csv
import io
import json
import uuid
from dataclasses import replace
from html.parser import HTMLParser

import pytest
from sqlalchemy import exc, text

from affiche.runtime import recover
from affiche.visuals import evaluate, review
from affiche.visuals.admission import Refused, request_revision
from affiche.visuals.evaluate import (
    EXIT_BUDGET, EXIT_ERROR, EXIT_OK, EXIT_USAGE, REQUEST_NS, apply, build_parser, main, new_cycle, sheet,
)
from affiche.visuals.gateway import StubProvider
from affiche.visuals.prompts import REASON_CODES
from affiche.visuals.sheet import REASON_LABELS
from test_admission import _settings, settings  # noqa: F401  (settings: fixture, DATA_DIR = tmp_path)
from test_config import env  # noqa: F401  (fixture)
from test_fixtures_generate import (  # noqa: F401  (folder, rt: fixtures)
    NEW_RUN, P1, P2, FirstCallRaises, _all, _count, _csv, _generate, folder, rt,
)

HEADER = "target_id;kind;action;reasons;note;framing"


@pytest.fixture
def ids(rt, folder):
    """generate on P1 and P2: each gets a pending scene candidate (C1, C2) and a proposed cutout (K1, K2)."""
    assert _generate(rt, _csv(folder, P1, P2), *NEW_RUN)[0] == EXIT_OK
    found = {}
    for number in ("1", "2"):
        found[f"C{number}"] = _all(rt, f"SELECT id FROM candidates WHERE variant_ref = 'P{number}'")[0][0]
        found[f"K{number}"] = _all(rt, f"SELECT id FROM cutouts WHERE variant_ref = 'P{number}'")[0][0]
    return found


class Page(HTMLParser):
    """The sections of the page, each with its class and the start tags in it; every img src; the text."""

    def __init__(self, html):
        super().__init__()
        self.sections, self.srcs, self.text = [], [], ""
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "section":
            self.sections.append((attrs.get("class"), []))
        elif self.sections:
            self.sections[-1][1].append((tag, attrs))
        if tag == "img":
            self.srcs.append(attrs["src"])

    def handle_data(self, data):
        self.text += data

    def of(self, kind):
        return [tags for section_class, tags in self.sections if section_class == kind]


def _row(target, kind, action, reasons="", note="", framing=""):
    return ";".join((target, kind, action, reasons, note, framing))


def _file(tmp_path, *rows):
    path = tmp_path / "review" / "decisions.csv"
    path.parent.mkdir(exist_ok=True)
    path.write_text("\n".join([HEADER, *rows]) + "\n", encoding="utf-8")
    return path


def _apply(rt, path, provider=None):
    out = io.StringIO()
    code = apply(rt, build_parser().parse_args(["apply", str(path)]), provider=provider or StubProvider(delay=0),
                 out=out)
    return code, out.getvalue()


def _results(path):
    with path.with_name("apply-result.csv").open(encoding="utf-8-sig", newline="") as file:
        return [row["result"] for row in csv.DictReader(file, delimiter=";")]


def _sheet(rt, out_dir, *options):
    out = io.StringIO()
    code = sheet(rt, build_parser().parse_args(["sheet", "--out", str(out_dir), *options]), out=out)
    return code, out.getvalue()


def _decisions(out_dir):
    raw = (out_dir / "decisions.csv").read_bytes()
    assert raw.startswith(codecs.BOM_UTF8)
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""), delimiter=";"))


def _new_cycle(rt, *skus):
    out = io.StringIO()
    return new_cycle(rt, build_parser().parse_args(["new-cycle", *skus]), out=out), out.getvalue()


def _statuses(rt):
    return (_all(rt, "SELECT variant_ref, status FROM candidates ORDER BY 1"),
            _all(rt, "SELECT variant_ref, status FROM cutouts ORDER BY 1"))


def _request_id(target, action, k=0):
    return str(uuid.uuid5(REQUEST_NS, f"{target}:{action}:{k}"))


# --- sheet ----------------------------------------------------------------------------------------------------------

def test_sheet_writes_a_portable_page_and_a_prefilled_decisions_file(rt, ids, tmp_path):
    out_dir = tmp_path / "review"
    code, out = _sheet(rt, out_dir)
    assert code == EXIT_OK and "2 candidate(s) and 2 cutout(s) to review" in out
    page = Page((out_dir / "sheet.html").read_text(encoding="utf-8"))
    assert page.srcs and all(src.startswith("img/") and (out_dir / src).is_file() for src in page.srcs)
    candidates = page.of("candidate")
    assert len(candidates) == 2 and len(page.of("cutout-review")) == 2
    for tags in candidates:
        assert sorted(attrs["class"] for tag, attrs in tags if tag == "div" and "frame" in attrs.get("class", "")) == [
            "frame feed", "frame square", "frame story"]
        sizes = [(attrs["width"], attrs["height"]) for tag, attrs in tags if tag == "img"]
        assert ("1088", "1920") in sizes and len(sizes) == 2  # the result and its original, at natural size
    assert "essai 1 / 3" in page.text
    for code in REASON_CODES:
        assert code in page.text and REASON_LABELS[code] in page.text
    assert "Texte ajouté hors du produit" in page.text and "Produit entier dans les 3 formats" in page.text

    rows = _decisions(out_dir)
    assert [(row["target_id"], row["kind"]) for row in rows] == [
        (ids["C1"], "scene"), (ids["C2"], "scene"), (ids["K1"], "cutout"), (ids["K2"], "cutout"),
        ("P1:r1:1", "scene"), ("P1:r1:1", "photo_preserved"), ("P2:r1:1", "scene"), ("P2:r1:1", "photo_preserved")]
    assert all(row["action"] == row["reasons"] == row["note"] == row["framing"] == "" for row in rows)
    assert "Samsung Galaxy A15" in rows[0]["info"] and "approve | reject" in rows[0]["info"]


def test_sheet_lists_every_decision_but_suggests_spending_in_the_open_scopes_only(rt, ids, tmp_path):
    review.reject(rt.engine, ids["C1"], reasons=["cameras"], note=None)
    review.confirm_cutout(rt.engine, ids["K1"])
    for treatment in ("scene", "photo_preserved"):  # P2's scopes close; its candidate and cutout stay to review
        review.abandon(rt.engine, variant_ref="P2", run_label="r1", cycle_no=1, treatment=treatment)
    assert _sheet(rt, tmp_path / "review")[0] == EXIT_OK
    rows = _decisions(tmp_path / "review")
    assert [(row["target_id"], row["kind"]) for row in rows] == [
        (ids["C2"], "scene"), (ids["K2"], "cutout"),  # approve | reject, confirm_cutout | reject_cutout
        (ids["C1"], "scene"), (ids["K1"], "cutout"),  # revise, background
        ("P1:r1:1", "scene"), ("P1:r1:1", "photo_preserved")]
    assert [row["info"].rpartition(": ")[2] for row in rows[:4]] == [
        "approve | reject", "confirm_cutout | reject_cutout", "revise", "background"]
    page = Page((tmp_path / "review" / "sheet.html").read_text(encoding="utf-8"))
    assert len(page.of("candidate")) == 1 and len(page.of("cutout-review")) == 1
    assert ids["C2"] in page.text and ids["K2"] in page.text

    review.reject_cutout(rt.engine, ids["K2"])
    review.approve(rt.engine, ids["C2"], framing_checked=True)  # allowed after the abandon (ADR-020)
    assert _sheet(rt, tmp_path / "again")[0] == EXIT_OK
    assert [(row["target_id"], row["kind"]) for row in _decisions(tmp_path / "again")] == [
        (ids["C1"], "scene"), (ids["K1"], "cutout"), ("P1:r1:1", "scene"), ("P1:r1:1", "photo_preserved")]


def test_sheet_never_overwrites_a_decisions_file_and_refuses_an_unknown_run(rt, ids, tmp_path):
    assert _sheet(rt, tmp_path / "a", "--run", "r1")[0] == EXIT_OK
    code, out = _sheet(rt, tmp_path / "a")
    assert code == EXIT_USAGE and "decisions.csv exists" in out
    code, out = _sheet(rt, tmp_path / "b", "--run", "r9")
    assert code == EXIT_USAGE and "unknown run 'r9'" in out and not (tmp_path / "b").exists()


def test_sheet_layers_the_cutout_over_the_background_at_the_product_box(rt, ids, tmp_path):
    path = _file(tmp_path, _row(ids["K1"], "cutout", "confirm_cutout"), _row(ids["K1"], "cutout", "background"))
    assert _apply(rt, path)[0] == EXIT_OK
    assert _sheet(rt, tmp_path / "sheet")[0] == EXIT_OK
    [(box_json, bbox_json, width, height)] = _all(rt, (
        "SELECT c.product_box_json, k.bbox_json, a.width, a.height FROM candidates c"
        " JOIN cutouts k ON k.id = c.cutout_id JOIN assets a ON a.sha256 = k.cutout_asset"))
    (box_x, box_y, box_width, _), (x, y, bbox_width, _) = json.loads(box_json), json.loads(bbox_json)
    scale = box_width / bbox_width
    page = Page((tmp_path / "sheet" / "sheet.html").read_text(encoding="utf-8"))
    [tags] = [tags for tags in page.of("candidate") if any(attrs.get("class") == "cutout" for _, attrs in tags)]
    [layer] = [attrs for _, attrs in tags if attrs.get("class") == "cutout"]
    assert layer["style"] == (f"left:{box_x - x * scale:.2f}px;top:{box_y - y * scale:.2f}px;"
                              f"width:{width * scale:.2f}px;height:{height * scale:.2f}px")
    assert len([attrs for tag, attrs in tags if "frame" in attrs.get("class", "")]) == 3
    assert "fond 1" in page.text


# --- apply: validation ----------------------------------------------------------------------------------------------

def test_one_invalid_row_applies_nothing_and_every_error_is_listed(rt, ids, tmp_path):
    c1, c2, k1, k2 = ids["C1"], ids["C2"], ids["K1"], ids["K2"]
    path = _file(
        tmp_path,
        _row(k1, "cutout", "confirm_cutout"),  # row 2, valid
        _row(c2, "scene", "reject", reasons="cameras"),  # row 3, valid
        _row(c2, "scene", "revise"),  # row 4, valid: rejected by row 3
        _row(c1, "scene", "approve"),
        _row(c1, "scene", "revise"),
        _row(c2, "scene", "approve", framing="ok"),
        _row(k2, "scene", "confirm_cutout"),
        _row(k2, "cutout", "background"),
        _row("nope", "scene", "reject", reasons="cameras"),
        _row(c2, "photo_preserved", "revise"),
        _row("P1:r1", "scene", "abandon"),
        _row("P1:r1:1", "cutout", "abandon"),
        _row("P9:r1:1", "scene", "abandon"),
        _row("P1:r1:2", "scene", "abandon"),
        _row(c1, "scene", "promote"),
        _row(k2, "cutout", "reject_cutout", reasons="cameras"),
        _row(k1, "cutout", "background", note="vite"),
    )
    before = _statuses(rt)
    code, out = _apply(rt, path)
    expected = [
        f"row 5: approve {c1}: framing_not_checked: approve needs framing=ok",
        f"row 6: revise {c1}: revise needs a rejected candidate; it is pending_review",
        f"row 7: approve {c2}: a second decision for this target (row 3)",
        f"row 8: confirm_cutout {k2}: kind 'scene': confirm_cutout takes cutout",
        f"row 9: background {k2}: background needs a confirmed cutout; it is proposed",
        "row 10: reject nope: unknown candidate id",
        f"row 11: revise {c2}: kind photo_preserved: the candidate is scene",
        "row 12: abandon P1:r1: not a scope id",
        "row 13: abandon P1:r1:1: kind 'cutout': abandon takes scene or photo_preserved",
        "row 14: abandon P9:r1:1: unknown scope: P9 is not in run r1",
        "row 15: abandon P1:r1:2: wrong_scope: P1 is in cycle 1",
        f"row 16: promote {c1}: unknown action",
        f"row 17: reject_cutout {k2}: reject_cutout does not read reasons",
        f"row 18: background {k1}: background does not read note",
    ]
    assert code == EXIT_USAGE and f"{len(expected)} error(s), nothing applied" in out
    for error in expected:
        assert error in out
    assert "row 2:" not in out and "row 3:" not in out and "row 4:" not in out
    assert _statuses(rt) == before
    assert _count(rt, "generation_requests") == 2 and _count(rt, "abandonments") == 0
    assert not path.with_name("apply-result.csv").exists()


@pytest.mark.parametrize(("row", "error"), [
    (("reject", "bogus,cameras,zz", "", ""), "unknown_reason: bogus, zz"),
    (("reject", "", " ", ""), "reason_or_note_required"),
    (("reject", "", "Prix 899000 Ar", ""), "commercial_terms: Prix, 899000, Ar"),
    (("approve", "", "", "non"), "framing_not_checked"),
])
def test_review_input_errors_refuse_the_file(rt, ids, tmp_path, row, error):
    path = _file(tmp_path, _row(ids["K1"], "cutout", "confirm_cutout"), _row(ids["C1"], "scene", *row))
    before = _statuses(rt)
    code, out = _apply(rt, path)
    assert code == EXIT_USAGE and f"row 3: {row[0]} {ids['C1']}: {error}" in out
    assert _statuses(rt) == before


def test_a_final_status_refuses_other_decisions_but_a_matching_replay_passes(rt, ids, tmp_path):
    review.reject(rt.engine, ids["C1"], reasons=["logo", "cameras", "logo"], note=" reflets ")
    review.approve(rt.engine, ids["C2"], framing_checked=True)
    review.reject_cutout(rt.engine, ids["K1"])
    path = _file(tmp_path, _row(ids["C1"], "scene", "reject", reasons="cameras,logo", note="reflets"),
                 _row(ids["C2"], "scene", "approve", framing="OK"), _row(ids["K1"], "cutout", "reject_cutout"))
    assert _apply(rt, path)[0] == EXIT_OK and _results(path) == ["already_applied"] * 3

    path = _file(tmp_path, _row(ids["C1"], "scene", "reject", reasons="cameras"),
                 _row(ids["C2"], "scene", "reject", reasons="cameras"), _row(ids["K1"], "cutout", "confirm_cutout"))
    code, out = _apply(rt, path)
    assert code == EXIT_USAGE and "3 error(s)" in out
    assert "the candidate is rejected" in out and "the candidate is approved" in out and "the cutout is rejected" in out


@pytest.mark.parametrize(("content", "error"), [
    ("target_id;kind;action;reasons;note\n", "row 1: the header must have the columns"),
    (f"{HEADER};comment\n", "row 1: the header must have the columns"),
    (f'{HEADER}\nx;scene;reject;cameras;"reflets;\n', "unexpected end of data (check the quotes)"),
    (f"{HEADER}\nx;scene;reject;cameras\n", "row 2: 4 fields, expected 6"),
])
def test_a_malformed_file_is_refused(rt, ids, tmp_path, content, error):
    path = tmp_path / "decisions.csv"
    path.write_text(content, encoding="utf-8")
    code, out = _apply(rt, path)
    assert code == EXIT_USAGE and error in out


# --- apply: decisions and generations -------------------------------------------------------------------------------

def test_reject_then_revise_and_confirm_then_background_in_one_file_and_its_replay(rt, ids, tmp_path):
    path = _file(tmp_path, _row(ids["C1"], "scene", "reject", reasons="cameras,logo"),
                 _row(ids["C1"], "scene", "revise"), _row(ids["K2"], "cutout", "confirm_cutout"),
                 _row(ids["K2"], "cutout", "background"))
    code, out = _apply(rt, path)
    assert code == EXIT_OK, out
    assert _results(path) == ["applied"] * 4
    assert "row 3: P1 revise attempt 2 succeeded" in out and out.endswith("the result of each row\n")
    assert "committed $0.00 / cap $20.00" in out
    assert _all(rt, f"SELECT status, parent_id, owner FROM generation_requests"
                    f" WHERE id = '{_request_id(ids['C1'], 'revise')}'") == [("succeeded", ids["C1"], "cli")]
    assert _all(rt, f"SELECT status, cutout_id FROM generation_requests"
                    f" WHERE id = '{_request_id(ids['K2'], 'background')}'") == [("succeeded", ids["K2"])]
    assert _all(rt, "SELECT variant_ref, treatment, status, attempt_no, parent_id IS NOT NULL,"
                    " product_box_json IS NOT NULL FROM candidates WHERE attempt_no > 1 OR cutout_id IS NOT NULL"
                    " ORDER BY 1") == [("P1", "scene", "pending_review", 2, 1, 0),
                                       ("P2", "photo_preserved", "pending_review", 1, 0, 1)]
    tables = ("generation_requests", "provider_calls", "candidates", "abandonments")
    before = {table: _count(rt, table) for table in tables}

    code, out = _apply(rt, path)
    assert code == EXIT_OK and _results(path) == ["already_applied"] * 4
    assert {table: _count(rt, table) for table in tables} == before


def test_after_a_failed_request_a_replay_makes_a_new_one(rt, ids, tmp_path):
    path = _file(tmp_path, _row(ids["C1"], "scene", "reject", reasons="cameras"), _row(ids["C1"], "scene", "revise"))
    code, out = _apply(rt, path, provider=StubProvider(["refused"], delay=0))
    assert code == EXIT_OK and _results(path) == ["applied", "request_failed:refused"]

    assert _apply(rt, path)[0] == EXIT_OK and _results(path) == ["already_applied", "applied"]
    assert sorted(_all(rt, f"SELECT id, status FROM generation_requests WHERE parent_id = '{ids['C1']}'")) == sorted(
        [(_request_id(ids["C1"], "revise", 0), "failed"), (_request_id(ids["C1"], "revise", 1), "succeeded")])
    assert _apply(rt, path)[0] == EXIT_OK and _results(path) == ["already_applied"] * 2
    assert _count(rt, "generation_requests", f"parent_id = '{ids['C1']}'") == 2


def test_revise_is_refused_while_another_revision_of_the_candidate_is_live(rt, ids, tmp_path):
    review.reject(rt.engine, ids["C1"], reasons=["cameras"], note=None)
    request_revision(rt.engine, rt.settings, id="from-the-api", parent_id=ids["C1"], owner="api")  # running
    path = _file(tmp_path, _row(ids["C1"], "scene", "revise"))
    code, out = _apply(rt, path)
    assert code == EXIT_USAGE and f"row 2: revise {ids['C1']}: revision_already_requested" in out
    assert _count(rt, "generation_requests") == 3


def test_abandon_is_refused_while_any_request_of_its_scope_runs(rt, ids, tmp_path):
    review.reject(rt.engine, ids["C1"], reasons=["cameras"], note=None)
    request_revision(rt.engine, rt.settings, id="from-the-api", parent_id=ids["C1"], owner="api")  # a scene, running
    path = _file(tmp_path, _row(ids["K1"], "cutout", "confirm_cutout"), _row("P1:r1:1", "photo_preserved", "abandon"))
    code, out = _apply(rt, path)
    assert code == EXIT_USAGE and "row 3: abandon P1:r1:1: request_running" in out
    assert _all(rt, f"SELECT status FROM cutouts WHERE id = '{ids['K1']}'") == [("proposed",)]  # not confirmed
    assert _count(rt, "abandonments") == 0


def test_after_an_interrupted_request_a_replay_makes_a_new_one(rt, ids, tmp_path):
    review.reject(rt.engine, ids["C1"], reasons=["cameras"], note=None)
    # An apply killed after admitting k = 0: the next CLI start marks it interrupted.
    request_revision(rt.engine, rt.settings, id=_request_id(ids["C1"], "revise"), parent_id=ids["C1"], owner="cli")
    assert recover(rt.engine, "cli") == (1, 1)
    path = _file(tmp_path, _row(ids["C1"], "scene", "revise"))
    assert _apply(rt, path)[0] == EXIT_OK and _results(path) == ["applied"]
    assert sorted(_all(rt, f"SELECT id, status FROM generation_requests WHERE parent_id = '{ids['C1']}'")) == sorted(
        [(_request_id(ids["C1"], "revise", 0), "interrupted"), (_request_id(ids["C1"], "revise", 1), "succeeded")])


@pytest.mark.parametrize("encoding", ["utf-8-sig", "utf-8", "cp1252"])
def test_accented_notes_read_alike_from_utf8_and_from_excel_cp1252(rt, ids, tmp_path, encoding):
    path = tmp_path / "decisions.csv"
    row = _row(ids["C1"], "scene", "reject", note="reflets trop marqués")
    path.write_text(f"{HEADER};info\n{row};à revoir\n", encoding=encoding)
    assert _apply(rt, path)[0] == EXIT_OK and _results(path) == ["applied"]
    assert _all(rt, f"SELECT rejection_note FROM candidates WHERE id = '{ids['C1']}'") == [("reflets trop marqués",)]
    assert _apply(rt, path)[0] == EXIT_OK and _results(path) == ["already_applied"]


@pytest.mark.parametrize("data", [
    codecs.BOM_UTF8 + f"{HEADER}\nx;scene;reject;;reflets trop marqu\xe9s;\n".encode("cp1252"),  # BOM, not UTF-8
    f"{HEADER}\nx;scene;reject;;reflets\x81;\n".encode("latin-1"),  # 0x81 is undefined in cp1252
])
def test_bytes_invalid_in_the_chosen_encoding_refuse_the_file(rt, ids, tmp_path, data):
    path = tmp_path / "decisions.csv"
    path.write_bytes(data)
    code, out = _apply(rt, path)
    assert code == EXIT_USAGE and "not UTF-8 (with or without a BOM) nor Windows-1252 text" in out


def test_a_refusal_after_validation_is_that_row_only_and_exits_1(rt, ids, tmp_path, monkeypatch):
    def lost_race(*_args, **_kwargs):
        raise Refused(409, "invalid_transition")

    monkeypatch.setattr(review, "approve", lost_race)
    path = _file(tmp_path, _row(ids["C1"], "scene", "approve", framing="ok"),
                 _row(ids["K1"], "cutout", "confirm_cutout"))
    code, out = _apply(rt, path)
    assert code == EXIT_ERROR and _results(path) == ["refused:invalid_transition", "applied"]


def test_a_report_error_after_a_success_keeps_applied_and_exits_1(rt, ids, tmp_path, monkeypatch):
    committed_line, calls = evaluate._committed_line, []

    def fails_once(*args):
        calls.append(args)
        if len(calls) == 1:  # the progress line printed after the generation
            raise RuntimeError("report failed")
        return committed_line(*args)

    monkeypatch.setattr(evaluate, "_committed_line", fails_once)
    path = _file(tmp_path, _row(ids["C1"], "scene", "reject", reasons="cameras"), _row(ids["C1"], "scene", "revise"))
    code, out = _apply(rt, path)
    assert code == EXIT_ERROR and _results(path) == ["applied", "applied"]
    assert "row 3: P1 revise error: RuntimeError: report failed" in out
    assert _all(rt, f"SELECT status FROM generation_requests WHERE id = '{_request_id(ids['C1'], 'revise')}'") == [
        ("succeeded",)]


def test_an_execution_error_keeps_the_stored_error_kind_and_exits_1(rt, ids, tmp_path):
    path = _file(tmp_path, _row(ids["C1"], "scene", "reject", reasons="cameras"), _row(ids["C1"], "scene", "revise"))
    code, out = _apply(rt, path, provider=FirstCallRaises())  # execute fails the request (invalid_request), re-raises
    assert code == EXIT_ERROR and _results(path) == ["applied", "request_failed:invalid_request"]
    assert "row 3: P1 revise error: RuntimeError: bug" in out
    assert _apply(rt, path)[0] == EXIT_OK and _results(path) == ["already_applied", "applied"]  # k = 1


def test_an_unexpected_error_stays_with_its_row_and_the_rest_still_runs(rt, ids, tmp_path, monkeypatch):
    def confirm_fails(*_args, **_kwargs):
        raise RuntimeError("disk I/O error")

    admissions = []

    def second_admission_fails(*args, **kwargs):
        admissions.append(kwargs["parent_id"])
        if len(admissions) == 2:
            raise exc.OperationalError("INSERT ...", {}, Exception("database is locked"))
        return request_revision(*args, **kwargs)

    monkeypatch.setattr(review, "confirm_cutout", confirm_fails)
    monkeypatch.setattr(evaluate, "request_revision", second_admission_fails)
    path = _file(tmp_path, _row(ids["K1"], "cutout", "confirm_cutout"),
                 _row(ids["C1"], "scene", "reject", reasons="cameras"), _row(ids["C1"], "scene", "revise"),
                 _row(ids["C2"], "scene", "reject", reasons="logo"), _row(ids["C2"], "scene", "revise"))
    code, out = _apply(rt, path)
    assert code == EXIT_ERROR
    assert _results(path) == ["error:RuntimeError", "applied", "applied", "applied", "error:OperationalError"]
    assert "row 2: RuntimeError: disk I/O error" in out and "row 6: OperationalError:" in out
    assert _all(rt, "SELECT parent_id, status FROM generation_requests WHERE parent_id IS NOT NULL") == [
        (ids["C1"], "succeeded")]  # admitted before the error, then executed: no reservation stranded
    assert _count(rt, "provider_calls", "status = 'running'") == 0


def test_an_abandon_replay_after_new_cycle_still_addresses_the_original_scope(rt, ids, tmp_path):
    path = _file(tmp_path, _row("P1:r1:1", "scene", "abandon", note="trop de reflets"))
    assert _apply(rt, path)[0] == EXIT_OK and _results(path) == ["applied"]
    assert review.approve(rt.engine, ids["C1"], framing_checked=True) == "applied"  # allowed after abandon (ADR-020)
    assert _new_cycle(rt, "P1") == (EXIT_OK, "P1: cycle 2\n")

    code, out = _apply(rt, path)
    assert code == EXIT_OK and _results(path) == ["already_applied"]
    assert _all(rt, "SELECT variant_ref, run_label, cycle_no, treatment, note FROM abandonments") == [
        ("P1", "r1", 1, "scene", "trop de reflets")]
    assert _sheet(rt, tmp_path / "cycle2")[0] == EXIT_OK  # the new cycle is open, so not abandoned
    assert ("P1:r1:2", "scene") in [(row["target_id"], row["kind"]) for row in _decisions(tmp_path / "cycle2")]


def test_abandon_is_refused_once_the_file_approved_the_scope(rt, ids, tmp_path):
    path = _file(tmp_path, _row(ids["C1"], "scene", "approve", framing="ok"), _row("P1:r1:1", "scene", "abandon"))
    code, out = _apply(rt, path)
    assert code == EXIT_USAGE and "row 3: abandon P1:r1:1: already_approved: the scope has an approved scene" in out
    path = _file(tmp_path, _row("P1:r1:1", "scene", "abandon"), _row(ids["C1"], "scene", "approve", framing="ok"))
    assert _apply(rt, path)[0] == EXIT_OK and _results(path) == ["applied", "applied"]  # decisions run in file order


def test_budget_exhausted_stops_admitting_finishes_the_rest_and_exits_3(rt, ids, tmp_path, env):
    rt = replace(rt, settings=_settings(env, DATA_DIR=str(tmp_path), SPEND_CAP_USD="0.5"))  # one 0.40 reservation
    path = _file(tmp_path, _row(ids["C1"], "scene", "reject", reasons="cameras"), _row(ids["C1"], "scene", "revise"),
                 _row(ids["C2"], "scene", "reject", reasons="logo"), _row(ids["C2"], "scene", "revise"),
                 _row(ids["K1"], "cutout", "confirm_cutout"), _row(ids["K1"], "cutout", "background"))
    code, out = _apply(rt, path)
    assert code == EXIT_BUDGET
    assert _results(path) == ["applied", "applied", "applied", "refused:budget_exhausted", "applied", "not_started"]
    assert "budget_exhausted: not started: row 7" in out
    assert _all(rt, "SELECT parent_id, status FROM generation_requests WHERE parent_id IS NOT NULL") == [
        (ids["C1"], "succeeded")]


def test_apply_needs_paid_with_openai_before_anything_starts(env, tmp_path, capsys):
    data_dir = tmp_path / "data"
    env.setenv("DATA_DIR", str(data_dir))
    env.setenv("IMAGE_PROVIDER", "openai")
    env.setenv("OPENAI_API_KEY", "sk-test-not-a-real-key")
    code = main(["apply", str(tmp_path / "decisions.csv")], env_file=None)
    captured = capsys.readouterr()
    assert code == EXIT_USAGE and "refused: IMAGE_PROVIDER=openai spends money: add --paid" in captured.err
    assert "sk-test" not in captured.out + captured.err
    assert not data_dir.exists()


def test_a_filled_in_sheet_file_applies(rt, ids, tmp_path):
    out_dir = tmp_path / "review"
    assert _sheet(rt, out_dir)[0] == EXIT_OK
    path = out_dir / "decisions.csv"
    with path.open(encoding="utf-8-sig", newline="") as file:
        header, *rows = list(csv.reader(file, delimiter=";"))
    for row in rows:
        if row[0] == ids["C1"]:
            row[2:6] = ["approve", "", "", "ok"]
        elif row[0] == ids["C2"]:
            row[2:4] = ["reject", "cameras,logo"]
    rows.append([ids["C2"], "scene", "revise", "", "", "", "ajouté à la main"])
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        csv.writer(file, delimiter=";").writerows([header, *rows])
    code, out = _apply(rt, path)
    assert code == EXIT_OK, out
    assert _results(path) == ["applied", "applied", *[""] * 6, "applied"]
    assert _all(rt, "SELECT variant_ref, status, framing_checked, rejection_reasons_json FROM candidates"
                    " ORDER BY variant_ref, attempt_no") == [
        ("P1", "approved", 1, None), ("P2", "rejected", None, '["logo", "cameras"]'),
        ("P2", "pending_review", None, None)]


# --- new-cycle ------------------------------------------------------------------------------------------------------

def test_new_cycle_needs_an_approval_in_the_current_cycle(rt, ids):
    assert _new_cycle(rt, "P1", "P2") == (
        EXIT_ERROR, "P1: refused cycle_not_approved\nP2: refused cycle_not_approved\n")
    review.approve(rt.engine, ids["C1"], framing_checked=True)
    assert _new_cycle(rt, "P1") == (EXIT_OK, "P1: cycle 2\n")
    assert _new_cycle(rt, "P1") == (EXIT_ERROR, "P1: refused cycle_not_approved\n")  # cycle 2 has no approval yet
    with rt.engine.connect() as conn:
        assert conn.execute(text("SELECT variant_ref, cycle_no FROM variant_cycles")).all() == [("P1", 2)]
