"""The review sheet (D-PRODUCT-VISUALS-008 `sheet`): a static sheet.html of what is left to review, its images copied
beside it, and the pre-filled decisions.csv that `apply` reads back. Stdlib only; every value in the page is
escaped."""

import csv
import json
import shutil
from collections.abc import Callable
from functools import partial
from html import escape
from pathlib import Path

from sqlalchemy import Connection, Row, text

from affiche import assets
from affiche.visuals.prompts import REASON_CODES

COLUMNS = ("target_id", "kind", "action", "reasons", "note", "framing", "info")  # apply reads all but info
TREATMENTS = ("scene", "photo_preserved")
IN_SCOPE = "variant_ref = :ref AND run_label = :run AND cycle_no = :cycle"
# The crops of the 1088x1920 master (D-PV-002): class, label, x, y, width, height.
FRAMES = (("story", "Story 1080×1920", 4, 0, 1080, 1920), ("feed", "Feed 1080×1350", 4, 285, 1080, 1350),
          ("square", "Carré 1080×1080", 4, 420, 1080, 1080))
REASON_LABELS = {  # the R-004 checklist, in REASON_CODES order
    "coloris": "Coloris", "logo": "Logo du fabricant", "cameras": "Disposition des caméras",
    "boutons": "Boutons et ports", "forme": "Forme et proportions", "extra": "Aucun produit ni accessoire en plus",
    "texte": "Texte ajouté hors du produit", "cadrage": "Produit entier dans les 3 formats",
    "integration": "Intégration réaliste (lumière, perspective)",
}
TREATMENT_LABELS = {"scene": "scène générée", "photo_preserved": "photo préservée sur fond généré"}
_SCOPES = (  # each run product in its variant's current cycle, in run then CSV order
    "SELECT rp.variant_ref, rp.run_label, rp.name, rp.variant, r.attempt_limit, COALESCE(vc.cycle_no, 1) AS cycle_no"
    " FROM run_products rp JOIN runs r ON r.label = rp.run_label"
    " LEFT JOIN variant_cycles vc ON vc.variant_ref = rp.variant_ref"
    " WHERE :only IS NULL OR rp.run_label = :only ORDER BY r.created_at, rp.rowid")
_TO_REVIEW = (  # every candidate or cutout (t) in a status, with its product, in run, CSV and creation order
    "SELECT t.*, rp.name, rp.variant, r.attempt_limit FROM {table} t"
    " JOIN run_products rp ON rp.run_label = t.run_label AND rp.variant_ref = t.variant_ref"
    " JOIN runs r ON r.label = t.run_label WHERE t.status = :status AND (:only IS NULL OR t.run_label = :only)"
    " ORDER BY r.created_at, rp.rowid, t.cycle_no, t.created_at")
_CLOSED = (f"SELECT treatment FROM abandonments WHERE {IN_SCOPE}"
           f" UNION SELECT treatment FROM candidates WHERE {IN_SCOPE} AND status = 'approved'")
_CSS = """
body{font-family:system-ui,sans-serif;margin:16px;background:#f2f2f2;color:#1d1d1d}
section{background:#fff;margin:0 0 24px;padding:12px 16px;border-radius:8px}
h2{font-size:1.1rem;margin:0 0 6px}
.row{display:flex;gap:16px;align-items:flex-start;overflow-x:auto}
figure{margin:0}figcaption{font-weight:600;margin:0 0 4px}
.stage{position:relative;overflow:hidden}.stage img{position:absolute;left:0;top:0}
.frame{position:absolute;box-sizing:border-box;border:4px dashed;pointer-events:none}
.frame span{position:absolute;left:6px;top:6px;padding:2px 8px;background:#fffd;font:600 22px system-ui}
.story{border-color:#d32f2f}.feed{border-color:#1565c0}.square{border-color:#2e7d32}
.checker{background:repeating-conic-gradient(#ccc 0 25%,#fff 0 50%) 0 0/32px 32px}
code{word-break:break-all}td{padding:2px 12px 2px 0}
"""


def write_sheet(conn: Connection, data_dir: Path, out_dir: Path, run_label: str | None) -> tuple[int, int, int]:
    """out_dir/sheet.html, out_dir/img/ and out_dir/decisions.csv, of every run or only run_label.

    Every pending candidate and proposed cutout is listed, whatever its scope's state: a decision is free, and a
    candidate pending when its scope was abandoned can still be approved (ADR-020). The suggestions that spend (revise,
    background) and the abandon rows are for the open scopes only: the variant's current cycle, per treatment neither
    abandoned nor approved. Returns the number of candidates and cutouts shown and of decisions.csv rows. OSError when
    an asset file is missing."""
    (out_dir / "img").mkdir(parents=True, exist_ok=True)
    image = partial(_copy_image, conn, data_dir, out_dir)
    candidates, cutouts, rows = [], [], []
    for candidate in conn.execute(text(_TO_REVIEW.format(table="candidates")),
                                  {"status": "pending_review", "only": run_label}).all():
        label = f"{_where(candidate)}, {TREATMENT_LABELS[candidate.treatment]}"
        attempt = _attempt(candidate, candidate.attempt_limit)
        candidates.append(_candidate_html(conn, image, f"{label}, {attempt}", candidate))
        rows.append(_row(candidate.id, candidate.treatment, f"{label}, {attempt} à revoir: approve | reject"))
    for cutout in conn.execute(text(_TO_REVIEW.format(table="cutouts")),
                               {"status": "proposed", "only": run_label}).all():
        cutouts.append(_cutout_html(image, _where(cutout), cutout))
        rows.append(_row(cutout.id, "cutout", f"{_where(cutout)}, détourage proposé: confirm_cutout | reject_cutout"))
    rows += _open_scope_rows(conn, run_label)
    (out_dir / "sheet.html").write_text(_page(candidates, cutouts), encoding="utf-8")
    # The BOM makes Excel read the accents as UTF-8.
    with (out_dir / "decisions.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file, delimiter=";")
        writer.writerow(COLUMNS)
        writer.writerows(rows)
    return len(candidates), len(cutouts), len(rows)


def _open_scope_rows(conn: Connection, run_label: str | None) -> list[list[str]]:
    """The revise, background and abandon rows of the open scopes, in that order."""
    revisable, confirmed, scopes = [], [], []
    for scope in conn.execute(text(_SCOPES), {"only": run_label}).all():
        params = {"ref": scope.variant_ref, "run": scope.run_label, "cycle": scope.cycle_no}
        closed = set(conn.execute(text(_CLOSED), params).scalars())
        for treatment in (treatment for treatment in TREATMENTS if treatment not in closed):
            label = f"{_where(scope)}, {TREATMENT_LABELS[treatment]}"
            # The chain is linear: only its tip can be revised.
            latest = conn.execute(text(f"SELECT * FROM candidates WHERE {IN_SCOPE} AND treatment = :treatment"
                                       " ORDER BY attempt_no DESC LIMIT 1"), {**params, "treatment": treatment}).first()
            if latest is not None and _revisable(conn, latest, scope.attempt_limit):
                revisable.append(_row(latest.id, treatment,
                                      f"{label}, {_attempt(latest, scope.attempt_limit)} refusé: revise"))
            if treatment == "photo_preserved":
                confirmed += [_row(cutout_id, "cutout", f"{_where(scope)}, détourage confirmé: background")
                              for cutout_id in conn.execute(text(f"SELECT id FROM cutouts WHERE {IN_SCOPE}"
                                                                 " AND status = 'confirmed' ORDER BY created_at"),
                                                            params).scalars()]
            scopes.append(_row(f"{scope.variant_ref}:{scope.run_label}:{scope.cycle_no}", treatment,
                               f"{label}: abandon"))
    return revisable + confirmed + scopes


def _revisable(conn: Connection, latest: Row, attempt_limit: int) -> bool:
    """Rejected, with no live revision, and for a scene a slot left: a succeeded scene's attempt_no counts the live
    scene requests of its scope (D-PV-005)."""
    if latest.status != "rejected" or latest.treatment == "scene" and latest.attempt_no >= attempt_limit:
        return False
    return not conn.execute(text("SELECT 1 FROM generation_requests WHERE parent_id = :id"
                                 " AND status IN ('running','succeeded')"), {"id": latest.id}).first()


def _where(row: Row) -> str:
    return f"{row.variant_ref} {row.name} ({row.variant}), run {row.run_label}, cycle {row.cycle_no}"


def _attempt(candidate: Row, attempt_limit: int) -> str:
    if candidate.treatment == "scene":
        return f"essai {candidate.attempt_no} / {attempt_limit}"
    return f"fond {candidate.attempt_no} (hors limite des scènes)"


def _row(target_id: str, kind: str, info: str) -> list[str]:
    return [target_id, kind, "", "", "", "", info]


def _copy_image(conn: Connection, data_dir: Path, out_dir: Path, sha: str) -> tuple[str, int, int]:
    """The asset copied to out_dir/img once, so the page is portable: its relative src, width and height."""
    asset = conn.execute(text("SELECT mime, width, height FROM assets WHERE sha256 = :sha"), {"sha": sha}).one()
    ext = assets.extension(asset.mime)
    src = f"img/{sha}.{ext}"
    if not (out_dir / src).exists():
        shutil.copyfile(assets.path(data_dir, sha, ext), out_dir / src)
    return src, asset.width, asset.height


def _img(src: str, width: int, height: int, attributes: str = "") -> str:
    return f'<img src="{escape(src)}" width="{width}" height="{height}" alt=""{attributes}>'


def _figure(caption: str, content: str) -> str:
    return f"<figure><figcaption>{escape(caption)}</figcaption>{content}</figure>"


def _candidate_html(conn: Connection, image: Callable, title: str, candidate: Row) -> str:
    """The originals and the result at natural size, with the three crop frames over the result."""
    originals = "".join(_figure("Original", _img(*image(sha))) for sha in json.loads(candidate.source_assets_json))
    src, width, height = image(candidate.image_asset)
    layers = _img(src, width, height)
    if candidate.cutout_id is not None:
        layers += _cutout_layer(conn, image, candidate)
    frames = "".join(f'<div class="frame {name}" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px">'
                     f"<span>{escape(caption)}</span></div>" for name, caption, x, y, w, h in FRAMES)
    stage = f'<div class="stage" style="width:{width}px;height:{height}px">{layers}{frames}</div>'
    return (f'<section class="candidate"><h2>{escape(title)}</h2>'
            f"<p>Candidat <code>{escape(candidate.id)}</code></p>"
            f'<div class="row">{originals}{_figure("Résultat", stage)}</div></section>')


def _cutout_layer(conn: Connection, image: Callable, candidate: Row) -> str:
    """The cutout over the baked background, scaled and moved so that its bbox covers the product box (D-PV-006).
    The page scales the display only, as the poster will."""
    cutout = conn.execute(text("SELECT cutout_asset, bbox_json FROM cutouts WHERE id = :id"),
                          {"id": candidate.cutout_id}).one()
    src, width, height = image(cutout.cutout_asset)
    x, y, bbox_width, _ = json.loads(cutout.bbox_json)
    box_x, box_y, box_width, _ = json.loads(candidate.product_box_json)
    scale = box_width / bbox_width  # place() scales both sides alike
    position = (f"left:{box_x - x * scale:.2f}px;top:{box_y - y * scale:.2f}px;"
                f"width:{width * scale:.2f}px;height:{height * scale:.2f}px")
    return _img(src, width, height, f' class="cutout" style="{position}"')


def _cutout_html(image: Callable, where: str, cutout: Row) -> str:
    src, width, height = image(cutout.cutout_asset)
    checker = f'<div class="checker" style="width:{width}px;height:{height}px">{_img(src, width, height)}</div>'
    return (f'<section class="cutout-review"><h2>{escape(f"{where}, détourage proposé")}</h2>'
            f"<p>Détourage <code>{escape(cutout.id)}</code></p>"
            f'<div class="row">{_figure("Détourage", checker)}</div></section>')


def _page(candidates: list[str], cutouts: list[str]) -> str:
    legend = "".join(f"<tr><td><code>{code}</code></td><td>{escape(REASON_LABELS[code])}</td></tr>"
                     for code in REASON_CODES)
    return ('<!doctype html>\n<html lang="fr"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>Revue des visuels</title><style>{_CSS}</style></head><body>"
            f"<h1>Revue des visuels</h1><p>{len(candidates)} visuel(s) et {len(cutouts)} détourage(s)"
            " à revoir. Remplissez la colonne <code>action</code> de <code>decisions.csv</code>, puis lancez"
            " <code>apply</code>. Pour approuver, vérifiez que le produit est entier dans les 3 formats et mettez"
            " <code>framing=ok</code>.</p>"
            '<section class="legend"><h2>Motifs de refus (colonne <code>reasons</code>, séparés par des virgules)'
            f"</h2><table>{legend}</table></section>"
            f"{''.join(candidates)}{''.join(cutouts)}</body></html>\n")
