"""One backup of the shop's data into a folder (D-HOSTED-PILOT-004):

    python -m affiche.backup <folder>        # reads DATA_DIR

Asset files first, then one consistent copy of the database, so that every asset a database copy names is in
the backup. Runs while the API serves: assets are immutable files named by their hash, and the database is read
through SQLite's online backup. It takes no process lock and starts nothing.

Any failure exits with code 1 and leaves `last-backup.json` as it was: its age is what shows a missing backup.
"""
import json
import os
import shutil
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

KEEP_DAYS = 14
STAMP = "%Y%m%dT%H%M%SZ"  # sorts as text in time order


def run(data_dir: Path, folder: Path, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    source = data_dir / "affiche.db"
    if not source.is_file():
        raise FileNotFoundError(f"no database at {source}")
    assets_in, assets_out, db_out = data_dir / "assets", folder / "assets", folder / "db"
    assets_out.mkdir(parents=True, exist_ok=True)
    db_out.mkdir(parents=True, exist_ok=True)
    for leftover in [*db_out.glob("*.partial*"), *assets_out.rglob("*.partial")]:
        leftover.unlink()  # an earlier run that failed; never counted as a backup

    copied = 0
    for file in sorted(assets_in.rglob("*")) if assets_in.is_dir() else []:
        if not file.is_file() or file.suffix == ".tmp":  # .tmp: an asset still being written by the API
            continue
        target = assets_out / file.relative_to(assets_in)
        if target.exists():  # immutable and named by its hash: never copied twice, never overwritten
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(target.name + ".partial")
        shutil.copyfile(file, partial)
        os.replace(partial, target)
        copied += 1

    partial = db_out / f"affiche-{now.strftime(STAMP)}.db.partial"
    # Read-only on the source: a backup must never be able to change the shop's database.
    reader = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        writer = sqlite3.connect(partial)
        try:
            reader.backup(writer)  # one step: a consistent snapshot, whatever the API writes meanwhile
            verdict = writer.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            writer.close()
    finally:
        reader.close()
    if verdict != "ok":
        raise RuntimeError(f"the copy failed its integrity check ({verdict}); kept as {partial.name} until the next run")
    copy = partial.with_suffix("")  # drops ".partial"
    os.replace(partial, copy)

    oldest_kept = f"affiche-{(now - timedelta(days=KEEP_DAYS)).strftime(STAMP)}.db"
    for old in sorted(db_out.glob("affiche-*.db"))[:-1]:  # the newest always stays
        if old.name < oldest_kept:
            old.unlink()

    summary = {"finished_at": datetime.now(UTC).isoformat(timespec="seconds"), "db_file": copy.name,
               "db_bytes": copy.stat().st_size, "asset_files": sum(1 for f in assets_out.rglob("*") if f.is_file()),
               "assets_copied": copied}
    marker = folder / "last-backup.json"
    marker.with_suffix(".json.tmp").write_text(json.dumps(summary), encoding="utf-8")
    os.replace(marker.with_suffix(".json.tmp"), marker)
    return summary


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    from affiche.config import ConfigError, load_settings
    try:
        summary = run(load_settings().data_dir, Path(argv[1]))
    except (OSError, sqlite3.Error, RuntimeError, ConfigError) as error:
        print(f"backup FAILED: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(f"backup ok: {summary['db_file']} ({summary['db_bytes']} bytes), {summary['asset_files']} asset files, "
          f"{summary['assets_copied']} new")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
