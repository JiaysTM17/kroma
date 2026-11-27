from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from app.storage.sqlite_repo import SQLiteRepo

from .config import SQLITE_PATH


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    target = db_path or Path(os.getenv("KROMA_SQLITE_PATH", str(SQLITE_PATH)))
    conn = sqlite3.connect(str(target), timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


def init_db(db_path: Path | None = None) -> None:
    target = db_path or Path(os.getenv("KROMA_SQLITE_PATH", str(SQLITE_PATH)))
    SQLiteRepo(target).initialize()
