"""DB helpers for the asset_not_found table.

Records (instrument_id, data_source, interval) triples that produced an HTTP 404,
and provides a fast bulk-read used by the scheduler to suppress future fetches.
"""
from __future__ import annotations

import psycopg


def record_not_found(
    conn: psycopg.Connection,
    instrument_id: str,
    data_source: str,
    interval: str,
    url: str,
) -> None:
    """Upsert a 404 event.

    On first occurrence inserts the row with both timestamps set to NOW().
    On repeat occurrences updates only last_seen_at; url and first_seen_at
    are preserved.
    """
    conn.execute(
        """
        INSERT INTO asset_not_found (instrument_id, data_source, interval, url)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (instrument_id, data_source, interval)
        DO UPDATE SET last_seen_at = NOW()
        """,
        [instrument_id, data_source, interval, url],
    )


def load_blocked(
    conn: psycopg.Connection,
    interval: str,
) -> frozenset[tuple[str, str]]:
    """Return all (instrument_id, data_source) pairs blocked for *interval*.

    Results are returned as a frozenset for O(1) membership tests.
    """
    rows = conn.execute(
        "SELECT instrument_id, data_source FROM asset_not_found WHERE interval = %s",
        [interval],
    ).fetchall()
    return frozenset((r[0], r[1]) for r in rows)
