"""Content-addressed asset store (D-PV-001): files under data_dir/assets, one `assets` row per distinct content.

Write the file with `put` before the DB transaction, then `record` its row inside it. A crash in between leaves an
orphan file, which is harmless: the next `put` of the same bytes finds it.
"""
# ponytail: no GC of orphan files; add a sweep when disk use matters.
import hashlib
import os
import tempfile
from pathlib import Path

from sqlalchemy import Connection, text

from affiche.db import utc_now


def path(data_dir: Path, sha: str, ext: str) -> Path:
    return data_dir / "assets" / sha[:2] / f"{sha}.{ext}"


def put(data_dir: Path, data: bytes, ext: str) -> str:
    """Stores the bytes once and returns their sha256 hex. An existing file is never rewritten."""
    sha = hashlib.sha256(data).hexdigest()
    final = path(data_dir, sha, ext)
    if final.exists():
        return sha
    final.parent.mkdir(parents=True, exist_ok=True)
    # The temp file sits in the final folder: os.replace is atomic only within one volume.
    fd, tmp_name = tempfile.mkstemp(dir=final.parent, prefix=f"{sha}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as tmp:
            tmp.write(data)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_name, final)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise
    # ponytail: the folder is not fsynced (Windows cannot fsync a directory). A power cut just after the replace
    # can lose the new name while the row committed later survives; fsync the folder on POSIX if that matters.
    return sha


def record(conn: Connection, *, sha: str, kind: str, mime: str, width: int, height: int, size: int) -> None:
    """Inserts the asset row in the caller's transaction. The same bytes are one asset: the first kind wins."""
    conn.execute(text(
        "INSERT INTO assets (sha256, mime, width, height, bytes, created_at, kind)"
        " VALUES (:sha, :mime, :width, :height, :size, :now, :kind)"
        " ON CONFLICT (sha256) DO NOTHING"),
        {"sha": sha, "mime": mime, "width": width, "height": height, "size": size, "now": utc_now(), "kind": kind})
