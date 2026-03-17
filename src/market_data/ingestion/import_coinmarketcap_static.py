"""Import CoinMarketCap static TSV snapshots into PostgreSQL.

File patterns (all share a ``<date>_<time>`` prefix):
- ``<prefix>_listing_data.tsv``   — per-coin price/market-cap/supply snapshot
- ``<prefix>_map_data.tsv``       — canonical CMC id ↔ slug mapping
- ``<prefix>_categories_data.tsv``— category master records
- ``<prefix>_category_data.tsv``  — per-category coin associations (one coin per row)

The import is idempotent: a ``cmc_import_log`` table records fully-processed snapshot
timestamps so re-running has no effect.
"""
from __future__ import annotations

import ast
import csv
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

from market_data.db.connection import get_connection

logger = logging.getLogger(__name__)

_DEFAULT_PROGRESS_INTERVAL = 100


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class SnapshotSet(NamedTuple):
    snapshot_ts: datetime
    listing_path: Path
    map_path: Path | None
    categories_path: Path | None
    category_path: Path | None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_float(value: str | None) -> float | None:
    """Normalise European comma-decimal and cast to float; return None on failure."""
    if not value or value.strip() in ("", "None", "null"):
        return None
    try:
        return float(value.strip().replace(",", "."))
    except ValueError:
        return None


def _parse_int(value: str | None) -> int | None:
    """Cast to int; return None on failure."""
    if not value or value.strip() in ("", "None", "null"):
        return None
    try:
        return int(float(value.strip().replace(",", ".")))
    except ValueError:
        return None


def _parse_bool(value: str | None) -> bool | None:
    if not value or value.strip() in ("", "None", "null"):
        return None
    return value.strip().lower() in ("true", "1", "yes")


def _parse_ts(value: str | None) -> datetime | None:
    if not value or value.strip() in ("", "None", "null"):
        return None
    try:
        s = value.strip().rstrip("Z")
        return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _parse_list_repr(value: str | None) -> list[str]:
    """Parse a Python list-repr string like ``['a', 'b']`` into a list."""
    if not value or value.strip() in ("", "None", "null", "[]"):
        return []
    try:
        result = ast.literal_eval(value.strip())
        if isinstance(result, list):
            return [str(item) for item in result]
    except (ValueError, SyntaxError):
        pass
    return []


def _parse_dict_repr(value: str | None) -> dict | None:
    """Parse a Python dict-repr string safely via ``ast.literal_eval``."""
    if not value or value.strip() in ("", "None", "null", "{}"):
        return None
    try:
        result = ast.literal_eval(value.strip())
        if isinstance(result, dict):
            return result
    except (ValueError, SyntaxError):
        pass
    return None


def _ts_from_prefix(prefix: str) -> datetime | None:
    """Parse ``YYYY-MM-DD_HHMMSS`` prefix into a UTC datetime."""
    try:
        return datetime.strptime(prefix, "%Y-%m-%d_%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def discover_snapshots(directory: Path) -> list[SnapshotSet]:
    """Return all snapshot sets found in *directory*, sorted by timestamp."""
    snapshots: list[SnapshotSet] = []
    for listing_path in sorted(directory.glob("*_listing_data.tsv")):
        prefix = listing_path.name.replace("_listing_data.tsv", "")
        snapshot_ts = _ts_from_prefix(prefix)
        if snapshot_ts is None:
            logger.warning("Cannot parse timestamp from filename: %s — skipping", listing_path.name)
            continue

        def sibling(suffix: str) -> Path | None:
            p = directory / f"{prefix}_{suffix}.tsv"
            if p.exists():
                return p
            logger.warning("Missing sibling file for prefix %s: %s_%s.tsv", prefix, prefix, suffix)
            return None

        snapshots.append(SnapshotSet(
            snapshot_ts=snapshot_ts,
            listing_path=listing_path,
            map_path=sibling("map_data"),
            categories_path=sibling("categories_data"),
            category_path=sibling("category_data"),
        ))
    return snapshots


# ---------------------------------------------------------------------------
# Idempotency log
# ---------------------------------------------------------------------------


def is_imported(conn, snapshot_ts: datetime) -> bool:
    row = conn.execute(
        "SELECT 1 FROM cmc_import_log WHERE snapshot_ts = %s", [snapshot_ts]
    ).fetchone()
    return row is not None


def mark_imported(conn, snapshot_ts: datetime) -> None:
    conn.execute(
        "INSERT INTO cmc_import_log (snapshot_ts) VALUES (%s) ON CONFLICT DO NOTHING", [snapshot_ts]
    )


# ---------------------------------------------------------------------------
# Per-file importers
# ---------------------------------------------------------------------------


def import_listing_data(
    conn,
    path: Path,
    snapshot_ts: datetime,
    dry_run: bool = False,
) -> int:
    """Upsert listing_data rows into ``cmc_listing_snapshots`` and ``cmc_coin_tags``."""
    rows_listing: list[tuple] = []
    rows_tags: list[tuple] = []

    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for lineno, row in enumerate(reader, start=2):
            try:
                cmc_id = _parse_int(row.get("id"))
                if cmc_id is None:
                    logger.warning("%s line %d: missing cmc_id — skipped", path.name, lineno)
                    continue

                rows_listing.append((
                    snapshot_ts,
                    cmc_id,
                    row.get("name"),
                    row.get("symbol"),
                    row.get("slug"),
                    _parse_int(row.get("cmc_rank")),
                    _parse_int(row.get("num_market_pairs")),
                    _parse_ts(row.get("date_added")),
                    _parse_float(row.get("max_supply")),
                    _parse_float(row.get("circulating_supply")),
                    _parse_float(row.get("total_supply")),
                    _parse_bool(row.get("infinite_supply")),
                    _parse_float(row.get("self_reported_circulating_supply")),
                    _parse_float(row.get("self_reported_market_cap")),
                    _parse_float(row.get("tvl_ratio")),
                    _parse_float(row.get("price")),
                    _parse_float(row.get("volume_24h")),
                    _parse_float(row.get("volume_change_24h")),
                    _parse_float(row.get("percent_change_1h")),
                    _parse_float(row.get("percent_change_24h")),
                    _parse_float(row.get("percent_change_7d")),
                    _parse_float(row.get("percent_change_30d")),
                    _parse_float(row.get("percent_change_60d")),
                    _parse_float(row.get("percent_change_90d")),
                    _parse_float(row.get("market_cap")),
                    _parse_float(row.get("market_cap_dominance")),
                    _parse_float(row.get("fully_diluted_market_cap")),
                    _parse_float(row.get("tvl")),
                    _parse_ts(row.get("last_updated")),
                ))

                for tag in _parse_list_repr(row.get("tags")):
                    rows_tags.append((cmc_id, tag))

            except Exception as exc:
                logger.warning("%s line %d: unexpected error (%s) — skipped", path.name, lineno, exc)

    if dry_run:
        logger.info("[dry-run] %s: would write %d listing rows, %d tag rows", path.name, len(rows_listing), len(rows_tags))
        return len(rows_listing)

    if rows_listing:
        conn.executemany(
            """
            INSERT INTO cmc_listing_snapshots VALUES (
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
            ) ON CONFLICT (snapshot_ts, cmc_id) DO NOTHING
            """,
            rows_listing,
        )
    if rows_tags:
        conn.executemany(
            "INSERT INTO cmc_coin_tags (cmc_id, tag) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            rows_tags,
        )

    return len(rows_listing)


def import_map_data(
    conn,
    path: Path,
    dry_run: bool = False,
) -> int:
    rows: list[tuple] = []

    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for lineno, row in enumerate(reader, start=2):
            try:
                cmc_id = _parse_int(row.get("id"))
                if cmc_id is None:
                    logger.warning("%s line %d: missing cmc_id — skipped", path.name, lineno)
                    continue
                rows.append((
                    cmc_id,
                    _parse_int(row.get("rank")),
                    row.get("name"),
                    row.get("symbol"),
                    row.get("slug"),
                    _parse_int(row.get("is_active")),
                    _parse_int(row.get("status")),
                    _parse_ts(row.get("first_historical_data")),
                    _parse_ts(row.get("last_historical_data")),
                    row.get("platform"),
                ))
            except Exception as exc:
                logger.warning("%s line %d: unexpected error (%s) — skipped", path.name, lineno, exc)

    if dry_run:
        logger.info("[dry-run] %s: would write %d map rows", path.name, len(rows))
        return len(rows)

    if rows:
        conn.executemany(
            """
            INSERT INTO cmc_map VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (cmc_id) DO UPDATE SET
                rank                  = excluded.rank,
                name                  = excluded.name,
                symbol                = excluded.symbol,
                slug                  = excluded.slug,
                is_active             = excluded.is_active,
                status                = excluded.status,
                first_historical_data = excluded.first_historical_data,
                last_historical_data  = excluded.last_historical_data,
                platform              = excluded.platform
            """,
            rows,
        )
    return len(rows)


def import_categories_data(
    conn,
    path: Path,
    dry_run: bool = False,
) -> int:
    rows: list[tuple] = []

    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for lineno, row in enumerate(reader, start=2):
            try:
                cmc_id = row.get("id", "").strip()
                if not cmc_id:
                    logger.warning("%s line %d: missing id — skipped", path.name, lineno)
                    continue
                rows.append((
                    cmc_id,
                    row.get("name"),
                    row.get("title"),
                    row.get("description"),
                    _parse_int(row.get("num_tokens")),
                    _parse_float(row.get("avg_price_change")),
                    _parse_float(row.get("market_cap")),
                    _parse_float(row.get("market_cap_change")),
                    _parse_float(row.get("volume")),
                    _parse_float(row.get("volume_change")),
                    _parse_ts(row.get("last_updated")),
                ))
            except Exception as exc:
                logger.warning("%s line %d: unexpected error (%s) — skipped", path.name, lineno, exc)

    if dry_run:
        logger.info("[dry-run] %s: would write %d category rows", path.name, len(rows))
        return len(rows)

    if rows:
        conn.executemany(
            """
            INSERT INTO cmc_categories VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (cmc_id) DO UPDATE SET
                name             = excluded.name,
                title            = excluded.title,
                description      = excluded.description,
                num_tokens       = excluded.num_tokens,
                avg_price_change = excluded.avg_price_change,
                market_cap       = excluded.market_cap,
                market_cap_change= excluded.market_cap_change,
                volume           = excluded.volume,
                volume_change    = excluded.volume_change,
                last_updated     = excluded.last_updated
            """,
            rows,
        )
    return len(rows)


def import_category_data(
    conn,
    path: Path,
    dry_run: bool = False,
) -> int:
    rows: list[tuple] = []

    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for lineno, row in enumerate(reader, start=2):
            try:
                category_id = row.get("id", "").strip()
                coins_raw = row.get("coins", "")
                coin = _parse_dict_repr(coins_raw)
                if coin is None:
                    logger.warning(
                        "%s line %d: malformed coins column for category %s — skipped",
                        path.name, lineno, category_id,
                    )
                    continue
                cmc_coin_id = coin.get("id")
                if cmc_coin_id is None:
                    logger.warning(
                        "%s line %d: no id in coins dict for category %s — skipped",
                        path.name, lineno, category_id,
                    )
                    continue
                rows.append((category_id, int(cmc_coin_id)))
            except Exception as exc:
                logger.warning("%s line %d: unexpected error (%s) — skipped", path.name, lineno, exc)

    if dry_run:
        logger.info("[dry-run] %s: would write %d category-coin rows", path.name, len(rows))
        return len(rows)

    if rows:
        conn.executemany(
            "INSERT INTO cmc_category_coins (category_id, cmc_coin_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            rows,
        )
    return len(rows)


# ---------------------------------------------------------------------------
# Enrichment
# ---------------------------------------------------------------------------


def enrich_instrument_crypto(
    conn,
    dry_run: bool = False,
) -> int:
    if dry_run:
        count = conn.execute("""
            SELECT count(*) FROM cmc_map m
            JOIN instruments i ON i.instrument_id = m.slug
            WHERE EXISTS (SELECT 1 FROM instrument_crypto ic WHERE ic.instrument_id = i.instrument_id)
        """).fetchone()[0]
        logger.info("[dry-run] enrich_instrument_crypto: would update %d rows", count)
        return count

    result = conn.execute("""
        UPDATE instrument_crypto
        SET
            cmc_id   = m.cmc_id,
            cmc_slug = m.slug,
            cmc_rank = m.rank
        FROM cmc_map m
        JOIN instruments i ON i.instrument_id = m.slug
        WHERE instrument_crypto.instrument_id = i.instrument_id
        RETURNING instrument_crypto.instrument_id
    """)
    updated = len(result.fetchall())
    logger.info("Enriched %d instrument_crypto rows with CMC metadata", updated)
    return updated


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def run_import(
    directory: Path,
    dry_run: bool = False,
    progress_interval: int = _DEFAULT_PROGRESS_INTERVAL,
) -> dict[str, int]:
    """Run the full CMC static import pipeline.

    Returns a summary dict with counts for each table.
    """
    from market_data.db.migrate import migrate
    migrate()
    conn = get_connection()

    snapshots = discover_snapshots(directory)
    if not snapshots:
        logger.info("No snapshots found in %s", directory)
        return {}

    total = len(snapshots)
    logger.info("Found %d snapshot sets in %s", total, directory)

    counts = {
        "listing": 0,
        "map": 0,
        "categories": 0,
        "category_coins": 0,
        "skipped": 0,
    }

    for idx, snap in enumerate(snapshots, start=1):
        if is_imported(conn, snap.snapshot_ts) and not dry_run:
            logger.debug("Skipping already imported snapshot %s", snap.snapshot_ts)
            counts["skipped"] += 1
            continue

        n = import_listing_data(conn, snap.listing_path, snap.snapshot_ts, dry_run=dry_run)
        counts["listing"] += n

        if snap.map_path:
            n = import_map_data(conn, snap.map_path, dry_run=dry_run)
            counts["map"] += n

        if snap.categories_path:
            n = import_categories_data(conn, snap.categories_path, dry_run=dry_run)
            counts["categories"] += n

        if snap.category_path:
            n = import_category_data(conn, snap.category_path, dry_run=dry_run)
            counts["category_coins"] += n

        if not dry_run:
            mark_imported(conn, snap.snapshot_ts)

        if idx % progress_interval == 0:
            logger.info("Processed %d/%d snapshots", idx, total)

    logger.info("Processed %d/%d snapshots", total - counts["skipped"], total)

    enrich_instrument_crypto(conn, dry_run=dry_run)

    return counts
