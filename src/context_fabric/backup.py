"""Offline recovery helpers for SQLite deployments.

Restore creates a NEW database file. It NEVER overwrites live DBs or WAL files.
Stop the API and workers before switching to a recovered file.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
from pathlib import Path


def restore_as_new(source: str | Path, destination: str | Path) -> dict:
    src = Path(source).expanduser().resolve(strict=True)
    dst = Path(destination).expanduser().absolute()
    if not src.is_file() or src == dst or dst.exists():
        raise ValueError("source must be a file and destination must not exist")
    with sqlite3.connect(f"file:{src}?mode=ro", uri=True) as check:
        if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("backup failed SQLite integrity check")
    dst.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(dst, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "wb") as out, src.open("rb") as inp:
            shutil.copyfileobj(inp, out, length=1024 * 1024)
            out.flush()
            os.fsync(out.fileno())
        with sqlite3.connect(str(dst)) as check:
            if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("restored database failed SQLite integrity check")
        return {"restored_as_new": str(dst), "bytes": dst.stat().st_size, "integrity": "ok"}
    except Exception:
        dst.unlink(missing_ok=True)
        raise
