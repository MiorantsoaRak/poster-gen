"""Initial schema (design D-PRODUCT-VISUALS-001).

Revision ID: 0001
Revises:
Create Date: 2026-11-06

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# One statement per op.execute: sqlite3 refuses several statements in one execute.
STATEMENTS = [
    # meta.provider_mode = 'stub' | 'openai'
    "CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    """CREATE TABLE assets (
  sha256 TEXT PRIMARY KEY, mime TEXT NOT NULL, width INTEGER NOT NULL, height INTEGER NOT NULL,
  bytes INTEGER NOT NULL, created_at TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('original','style_ref','provider_input','scene','background_raw','background','cutout'))
)""",
    # Immutable run configuration. attempt_limit 4-5 is for the ADR-011 evaluation only; by_arm is for
    # CLI runs only. UNIQUE (model, quality): a new label for the same config must not grant a fresh allowance.
    # Estimates are not stored here: they apply prospectively (D-PV-003 rule 6).
    """CREATE TABLE runs (
  label TEXT PRIMARY KEY, model TEXT NOT NULL, quality TEXT NOT NULL, size TEXT NOT NULL,
  attempt_limit INTEGER NOT NULL CHECK (attempt_limit BETWEEN 1 AND 5),
  corrections_mode TEXT NOT NULL CHECK (corrections_mode IN ('on','by_arm')),
  created_at TEXT NOT NULL,
  UNIQUE (model, quality)
)""",
    # Snapshot taken at `generate`; later commands never re-read the CSV for these.
    """CREATE TABLE run_products (
  run_label TEXT NOT NULL REFERENCES runs(label), variant_ref TEXT NOT NULL,
  arm TEXT CHECK (arm IN ('A','B')), fixture_row_sha256 TEXT NOT NULL,
  PRIMARY KEY (run_label, variant_ref)
)""",
    # Explicit "abandoned" outcome (R-008 c.2).
    """CREATE TABLE abandonments (
  variant_ref TEXT NOT NULL, run_label TEXT NOT NULL REFERENCES runs(label), cycle_no INTEGER NOT NULL,
  treatment TEXT NOT NULL CHECK (treatment IN ('scene','photo_preserved')),
  note TEXT, created_at TEXT NOT NULL,
  PRIMARY KEY (variant_ref, run_label, cycle_no, treatment)
)""",
    # ADR-011 "Nouvelle campagne"; no row means cycle 1.
    """CREATE TABLE variant_cycles (
  variant_ref TEXT PRIMARY KEY, cycle_no INTEGER NOT NULL DEFAULT 1
)""",
    # direction_json is kept for the background request (CSV replay). cutout_asset is RGBA with alpha in
    # {0,255}, same size as the oriented source. A cutout belongs to one scope (variant, cycle, run).
    """CREATE TABLE cutouts (
  id TEXT PRIMARY KEY, variant_ref TEXT NOT NULL, run_label TEXT NOT NULL REFERENCES runs(label),
  direction_json TEXT NOT NULL,
  source_asset TEXT NOT NULL REFERENCES assets(sha256),
  cutout_asset TEXT REFERENCES assets(sha256),
  bbox_json TEXT,
  status TEXT NOT NULL CHECK (status IN ('proposed','confirmed','rejected','failed')),
  failure_reason TEXT CHECK (failure_reason IN ('no_product','multiple_products')),
  low_res_warning INTEGER NOT NULL, rembg_model TEXT NOT NULL, created_at TEXT NOT NULL, decided_at TEXT,
  cycle_no INTEGER NOT NULL
)""",
    # One LOGICAL request. id: client UUID (UI) or deterministic uuid5 (CLI apply). payload_hash: sha256 of
    # the canonical payload. parent_id is set for a revision; cutout_id for every background.
    """CREATE TABLE generation_requests (
  id TEXT PRIMARY KEY,
  payload_hash TEXT NOT NULL,
  purpose TEXT NOT NULL CHECK (purpose IN ('scene','background')),
  variant_ref TEXT NOT NULL, cycle_no INTEGER NOT NULL,
  run_label TEXT NOT NULL REFERENCES runs(label),
  parent_id TEXT REFERENCES candidates(id),
  cutout_id TEXT REFERENCES cutouts(id),
  request_json TEXT NOT NULL, corrections_applied INTEGER NOT NULL,
  owner TEXT NOT NULL CHECK (owner IN ('api','cli')),
  status TEXT NOT NULL CHECK (status IN ('running','succeeded','failed','interrupted')),
  error_kind TEXT, candidate_id TEXT REFERENCES candidates(id),
  created_at TEXT NOT NULL, finished_at TEXT,
  CHECK ((purpose = 'background') = (cutout_id IS NOT NULL))
)""",
    # Guards: a request stays 'running' through its retries, so these hold across retries. Together they make
    # each (variant, cycle, run, purpose) one linear chain: one live/succeeded initial request, then only
    # revisions of a rejected candidate, one live/succeeded revision per parent (R-002 c.2).
    """CREATE UNIQUE INDEX req_one_revision ON generation_requests(parent_id)
  WHERE parent_id IS NOT NULL AND status IN ('running','succeeded')""",
    """CREATE UNIQUE INDEX req_one_initial ON generation_requests(variant_ref, cycle_no, run_label, purpose)
  WHERE parent_id IS NULL AND status IN ('running','succeeded')""",
    "CREATE INDEX req_allowance ON generation_requests(variant_ref, run_label, purpose, cycle_no, status)",
    # One row per invocation (a retry is call_no 2).
    """CREATE TABLE provider_calls (
  id TEXT PRIMARY KEY, request_id TEXT NOT NULL REFERENCES generation_requests(id),
  call_no INTEGER NOT NULL CHECK (call_no IN (1,2)),
  provider TEXT NOT NULL, model TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('running','succeeded','failed','interrupted')),
  error_kind TEXT CHECK (error_kind IN ('refused','quota','budget_exhausted','timeout','rate_limited',
                        'provider_error','invalid_request','invalid_response','auth','storage','interrupted')),
  error_detail TEXT, usage_json TEXT, raw_asset TEXT REFERENCES assets(sha256),
  cost_micros INTEGER NOT NULL CHECK (cost_micros >= 0), cost_is_estimate INTEGER NOT NULL,
  started_at TEXT NOT NULL, finished_at TEXT,
  UNIQUE (request_id, call_no)
)""",
    "CREATE INDEX calls_budget ON provider_calls(started_at)",
    # attempt_no: for a scene, position in the variant's allowance; for photo_preserved, 1, 2, ...
    # framing_checked is set at approval, both treatments (R-002 c.4, R-004 c.2).
    """CREATE TABLE candidates (
  id TEXT PRIMARY KEY, variant_ref TEXT NOT NULL, cycle_no INTEGER NOT NULL,
  subject_name TEXT NOT NULL, subject_variant TEXT NOT NULL,
  treatment TEXT NOT NULL CHECK (treatment IN ('scene','photo_preserved')),
  status TEXT NOT NULL CHECK (status IN ('pending_review','approved','rejected')),
  request_id TEXT NOT NULL UNIQUE REFERENCES generation_requests(id),
  parent_id TEXT REFERENCES candidates(id),
  attempt_no INTEGER NOT NULL,
  direction_json TEXT NOT NULL, source_assets_json TEXT NOT NULL,
  prompt TEXT NOT NULL, corrections_applied INTEGER NOT NULL,
  provider TEXT NOT NULL, model TEXT NOT NULL, quality TEXT NOT NULL, size TEXT NOT NULL, run_label TEXT NOT NULL,
  image_asset TEXT NOT NULL REFERENCES assets(sha256),
  cutout_id TEXT REFERENCES cutouts(id), product_box_json TEXT,
  low_res_warning INTEGER NOT NULL,
  framing_checked INTEGER,
  rejection_reasons_json TEXT, rejection_note TEXT,
  created_at TEXT NOT NULL, reviewed_at TEXT,
  CHECK ((treatment = 'photo_preserved') = (cutout_id IS NOT NULL))
)""",
    "CREATE INDEX candidates_variant ON candidates(variant_ref, treatment, cycle_no, status)",
]


def upgrade() -> None:
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    raise NotImplementedError("Migrations are forward-only.")
