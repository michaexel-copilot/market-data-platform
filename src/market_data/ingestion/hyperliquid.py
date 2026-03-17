"""Hyperliquid pairs DB persistence helpers."""
from __future__ import annotations

from datetime import datetime, timezone

from market_data.models.instrument import HLPairRecord


def upsert_hl_pairs(
    conn: object,
    network: str,
    pairs: list[tuple[str, HLPairRecord]],
) -> tuple[int, int]:
    """Atomically replace HL pairs for a network.

    Within a single transaction:
    1. Sets is_active = FALSE for all existing rows for this network.
    2. Upserts each (instrument_id, pair) with is_active = TRUE.

    Returns:
        (upserted_count, deactivated_count): counts of upserted and deactivated rows.
    """
    now = datetime.now(tz=timezone.utc)

    # Count currently active rows before deactivation
    active_before = conn.execute(  # type: ignore[union-attr]
        "SELECT COUNT(*) FROM instrument_hyperliquid WHERE network = %s AND is_active = TRUE",
        (network,),
    ).fetchone()[0]

    # Deactivate all existing rows for this network
    conn.execute(  # type: ignore[union-attr]
        "UPDATE instrument_hyperliquid SET is_active = FALSE, last_refreshed_at = %s WHERE network = %s",
        (now, network),
    )

    # Upsert fresh pairs
    for instrument_id, pair in pairs:
        conn.execute(  # type: ignore[union-attr]
            """
            INSERT INTO instrument_hyperliquid
                (instrument_id, network, hl_symbol, lot_size, tick_size, max_leverage, is_active, last_refreshed_at)
            VALUES (%s, %s, %s, %s, %s, %s, TRUE, %s)
            ON CONFLICT (instrument_id, network)
            DO UPDATE SET
                hl_symbol         = EXCLUDED.hl_symbol,
                lot_size          = EXCLUDED.lot_size,
                tick_size         = EXCLUDED.tick_size,
                max_leverage      = EXCLUDED.max_leverage,
                is_active         = TRUE,
                last_refreshed_at = EXCLUDED.last_refreshed_at
            """,
            (instrument_id, network, pair.hl_symbol, pair.lot_size, pair.tick_size, pair.max_leverage, now),
        )

    upserted = len(pairs)
    deactivated = max(0, active_before - upserted)
    return upserted, deactivated


def get_hl_tradeable_instrument_ids(conn: object, network: str) -> set[str]:
    """Return set of instrument_ids with is_active=TRUE for the given network."""
    rows = conn.execute(  # type: ignore[union-attr]
        "SELECT instrument_id FROM instrument_hyperliquid WHERE network = %s AND is_active = TRUE",
        (network,),
    ).fetchall()
    return {row[0] for row in rows}


def get_hl_metadata_for_instruments(
    conn: object,
    network: str,
    instrument_ids: list[str],
) -> dict[str, dict]:
    """Return HL metadata keyed by instrument_id for the given IDs and network.

    Args:
        conn: Active DB connection.
        network: "mainnet" or "testnet".
        instrument_ids: List of instrument_id values to look up.

    Returns:
        Dict mapping instrument_id -> {"hl_symbol": ..., "lot_size": ..., "tick_size": ..., "max_leverage": ...}
    """
    if not instrument_ids:
        return {}
    rows = conn.execute(  # type: ignore[union-attr]
        """
        SELECT instrument_id, hl_symbol, lot_size, tick_size, max_leverage
        FROM instrument_hyperliquid
        WHERE network = %s AND is_active = TRUE AND instrument_id = ANY(%s)
        """,
        (network, instrument_ids),
    ).fetchall()
    return {
        row[0]: {
            "hl_symbol": row[1],
            "lot_size": row[2],
            "tick_size": row[3],
            "max_leverage": row[4],
        }
        for row in rows
    }
