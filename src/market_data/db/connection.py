"""PostgreSQL connection manager — single shared connection via psycopg3."""
from __future__ import annotations

import os
import threading

import psycopg
from dotenv import load_dotenv

load_dotenv()

_lock = threading.Lock()
_conn: psycopg.Connection | None = None


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "Example: postgresql://market_data:<pw>@localhost/market_data_platform"
        )
    return url


def get_connection() -> psycopg.Connection:
    """Return the shared PostgreSQL connection, creating it on first call."""
    global _conn
    if _conn is None:
        with _lock:
            if _conn is None:
                _conn = psycopg.connect(get_database_url(), autocommit=True)
    return _conn


def close_connection() -> None:
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None
