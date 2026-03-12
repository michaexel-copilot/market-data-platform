"""DuckDB connection manager — single shared connection, WAL mode enabled."""
from __future__ import annotations

import os
import threading
from pathlib import Path

import duckdb
from dotenv import load_dotenv

load_dotenv()

_lock = threading.Lock()
_conn: duckdb.DuckDBPyConnection | None = None


def get_db_path() -> str:
    return os.getenv("DUCKDB_PATH", "market_data.duckdb")


def get_connection() -> duckdb.DuckDBPyConnection:
    """Return the shared DuckDB connection, creating it on first call."""
    global _conn
    if _conn is None:
        with _lock:
            if _conn is None:
                db_path = get_db_path()
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
                _conn = duckdb.connect(db_path)
                # DuckDB uses WAL internally by default; no extra configuration needed
    return _conn


def close_connection() -> None:
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None
