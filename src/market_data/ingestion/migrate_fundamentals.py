"""Migrate CoinMarketCap static data into the canonical instrument tables.

The function promotes data from ``cmc_listing_snapshots`` (latest snapshot)
into ``instruments`` and ``instrument_crypto``, then records per-attribute
provenance in ``attribute_source_map`` and cross-source ticker mappings in
``ticker_source_map``.

Matching is done by ``cmc_listing_snapshots.symbol`` = ``instruments.ticker``
scoped to ``asset_class = 'crypto'``.  The migration is idempotent — repeated
calls update existing rows rather than creating duplicates.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import duckdb

logger = logging.getLogger(__name__)

# Canonical CMC data source ID as seeded by migration 012_data_source.sql
_CMC_DATA_SOURCE_ID = 1

# Attributes promoted into instrument_crypto (cmc-specific numeric fields)
_CRYPTO_NUMERIC_ATTRS = ("total_supply", "max_supply", "circulating_supply", "cmc_id", "cmc_rank")
_CRYPTO_STR_ATTRS = ("cmc_slug",)
_ALL_CRYPTO_ATTRS = _CRYPTO_NUMERIC_ATTRS + _CRYPTO_STR_ATTRS
_INSTRUMENT_ATTRS = ("full_name",)


def migrate_fundamentals(conn: duckdb.DuckDBPyConnection) -> dict:
    """Promote latest CMC snapshot data into canonical tables.

    Returns a dict with keys ``promoted``, ``skipped``, ``errors``.
    """
    promoted = 0
    skipped = 0
    errors: list[str] = []
    now = datetime.now(timezone.utc)

    # ── Resolve CMC data source ──────────────────────────────────────────
    row = conn.execute(
        "SELECT data_source_id FROM data_source WHERE short_name = 'cmc' LIMIT 1"
    ).fetchone()
    if row is None:
        msg = "CoinMarketCap entry not found in data_source table — run migrations first"
        logger.error(msg)
        return {"promoted": 0, "skipped": 0, "errors": [msg]}
    cmc_id_ds = row[0]

    # ── Find latest snapshot ─────────────────────────────────────────────
    ts_row = conn.execute(
        "SELECT MAX(snapshot_ts) FROM cmc_listing_snapshots"
    ).fetchone()
    if ts_row is None or ts_row[0] is None:
        msg = "No CMC snapshot data found in cmc_listing_snapshots"
        logger.warning(msg)
        return {"promoted": 0, "skipped": 0, "errors": [msg]}
    latest_ts = ts_row[0]
    logger.info("Migrating from CMC snapshot at %s", latest_ts)

    # ── Clean up wrongly-mapped instruments ─────────────────────────────
    # The snapshot is the source of truth: for each symbol pick the entry
    # with the lowest cmc_rank (most established coin).  Any existing
    # instrument whose instrument_id (slug) doesn't match that canonical
    # slug is considered wrongly mapped and must be removed before the
    # correct row can be inserted.
    _cleanup_cte = """
        WITH canonical AS (
            SELECT symbol, slug AS canonical_slug
            FROM (
                SELECT symbol, slug,
                       ROW_NUMBER() OVER (
                           PARTITION BY upper(symbol)
                           ORDER BY COALESCE(cmc_rank, 999999) ASC
                       ) AS rn
                FROM cmc_listing_snapshots
                WHERE snapshot_ts = ?
            ) sub
            WHERE rn = 1
        ),
        wrong_ids AS (
            SELECT i.instrument_id
            FROM instruments i
            JOIN canonical c ON upper(c.symbol) = upper(i.ticker)
            WHERE i.instrument_id != c.canonical_slug
              AND i.asset_class = 'crypto'
        )
    """
    for dep_table in ("ticker_source_map", "attribute_source_map", "instrument_crypto"):
        conn.execute(
            f"{_cleanup_cte} DELETE FROM {dep_table} WHERE instrument_id IN (SELECT instrument_id FROM wrong_ids)",
            [latest_ts],
        )
    conn.execute(
        f"{_cleanup_cte} DELETE FROM instruments WHERE instrument_id IN (SELECT instrument_id FROM wrong_ids)",
        [latest_ts],
    )
    logger.info("Cleaned up wrongly-mapped instruments")

    # ── Create instrument rows from snapshot data ────────────────────────
    # Use the latest snapshot (not raw cmc_map) as the source so that the
    # canonical slug for each symbol is always the best-ranked listing entry.
    conn.execute(
        """
        INSERT OR IGNORE INTO instruments
            (instrument_id, ticker, full_name, asset_class, is_active, first_seen_at, last_updated_at)
        SELECT slug, symbol, name, 'crypto', TRUE, now(), now()
        FROM (
            SELECT slug, symbol, name,
                   ROW_NUMBER() OVER (
                       PARTITION BY upper(symbol)
                       ORDER BY COALESCE(cmc_rank, 999999) ASC
                   ) AS rn
            FROM cmc_listing_snapshots
            WHERE snapshot_ts = ?
              AND slug IS NOT NULL
              AND symbol IS NOT NULL
        ) sub
        WHERE rn = 1
        """,
        [latest_ts],
    )
    # Ensure instrument_crypto rows exist for all crypto instruments
    conn.execute(
        """
        INSERT OR IGNORE INTO instrument_crypto (instrument_id)
        SELECT instrument_id FROM instruments WHERE asset_class = 'crypto'
        """
    )
    logger.info("Ensured instrument rows from snapshot")

    # ── Fetch matched rows ───────────────────────────────────────────────
    # Use a window function to pick the best-ranked snapshot entry per
    # symbol so that instruments with ambiguous symbols (e.g. JOE, LUNA)
    # are only updated once, from the most canonical snapshot entry.
    rows = conn.execute(
        """
        WITH best_snapshot AS (
            SELECT *
            FROM (
                SELECT *,
                       ROW_NUMBER() OVER (
                           PARTITION BY upper(symbol)
                           ORDER BY COALESCE(cmc_rank, 999999) ASC
                       ) AS rn
                FROM cmc_listing_snapshots
                WHERE snapshot_ts = ?
            ) sub
            WHERE rn = 1
        )
        SELECT
            i.instrument_id,
            i.ticker,
            i.full_name          AS current_full_name,
            c.name               AS cmc_name,
            c.symbol             AS cmc_symbol,
            c.cmc_id             AS cmc_id_val,
            c.slug               AS cmc_slug_val,
            c.cmc_rank           AS cmc_rank_val,
            c.total_supply       AS total_supply_val,
            c.max_supply         AS max_supply_val,
            c.circulating_supply AS circulating_supply_val
        FROM instruments i
        JOIN best_snapshot c
          ON upper(c.symbol) = upper(i.ticker)
        WHERE i.asset_class = 'crypto'
        """,
        [latest_ts],
    ).fetchall()

    logger.info("Found %d matched instruments for CMC migration", len(rows))

    for row in rows:
        (
            instrument_id,
            _ticker,
            current_full_name,
            cmc_name,
            cmc_symbol,
            cmc_id_val,
            cmc_slug_val,
            cmc_rank_val,
            total_supply_val,
            max_supply_val,
            circulating_supply_val,
        ) = row

        try:
            attrs_updated: list[str] = []

            # ── Update instruments.full_name if missing ──────────────────
            if cmc_name and not current_full_name:
                conn.execute(
                    "UPDATE instruments SET full_name = ?, last_updated_at = ? WHERE instrument_id = ?",
                    [cmc_name, now, instrument_id],
                )
                attrs_updated.append("full_name")

            # ── Ensure instrument_crypto row exists ──────────────────────
            conn.execute(
                "INSERT OR IGNORE INTO instrument_crypto (instrument_id) VALUES (?)",
                [instrument_id],
            )

            # ── Update instrument_crypto numeric fields ───────────────────
            update_fields: list[tuple[str, object]] = []
            if cmc_id_val is not None:
                update_fields.append(("cmc_id", int(cmc_id_val)))
            if cmc_slug_val:
                update_fields.append(("cmc_slug", cmc_slug_val))
            if cmc_rank_val is not None:
                update_fields.append(("cmc_rank", int(cmc_rank_val)))
            if total_supply_val is not None:
                update_fields.append(("total_supply", float(total_supply_val)))
            if max_supply_val is not None:
                update_fields.append(("max_supply", float(max_supply_val)))
            if circulating_supply_val is not None:
                update_fields.append(("circulating_supply", float(circulating_supply_val)))

            if update_fields:
                set_clause = ", ".join(f"{col} = ?" for col, _ in update_fields)
                values = [v for _, v in update_fields] + [instrument_id]
                conn.execute(
                    f"UPDATE instrument_crypto SET {set_clause} WHERE instrument_id = ?",
                    values,
                )
                attrs_updated.extend(col for col, _ in update_fields)

            # ── Upsert attribute_source_map ──────────────────────────────
            for attr_name in attrs_updated:
                conn.execute(
                    """
                    INSERT INTO attribute_source_map (instrument_id, attribute_name, data_source_id, last_updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT (instrument_id, attribute_name)
                    DO UPDATE SET data_source_id = excluded.data_source_id,
                                  last_updated_at = excluded.last_updated_at
                    """,
                    [instrument_id, attr_name, cmc_id_ds, now],
                )

            # ── Upsert ticker_source_map ─────────────────────────────────
            if cmc_symbol:
                conn.execute(
                    """
                    INSERT INTO ticker_source_map (instrument_id, data_source_id, source_ticker, is_canonical)
                    VALUES (?, ?, ?, FALSE)
                    ON CONFLICT (instrument_id, data_source_id)
                    DO UPDATE SET source_ticker = excluded.source_ticker
                    """,
                    [instrument_id, cmc_id_ds, cmc_symbol],
                )

            promoted += 1

        except Exception as exc:  # noqa: BLE001
            msg = f"Error promoting instrument {instrument_id}: {exc}"
            logger.error(msg)
            errors.append(msg)
            skipped += 1

    logger.info("Migration complete: promoted=%d skipped=%d errors=%d", promoted, skipped, len(errors))
    return {"promoted": promoted, "skipped": skipped, "errors": errors}
