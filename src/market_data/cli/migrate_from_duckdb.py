"""CLI: migrate data from a DuckDB file to the PostgreSQL+TimescaleDB database.

Usage:
    uv run migrate-from-duckdb --source <path/to/market_data.duckdb> \
        [--url postgresql://...] [--dry-run] [--force]

Requires the ``duckdb`` package (available in the dev extras).
"""

import argparse
import logging
import sys

logger = logging.getLogger(__name__)

# Tables migrated in dependency order (parents before children).
TABLES = [
    "instruments",
    "instrument_identifiers",
    "instrument_crypto",
    "instrument_equity",
    "instrument_etf",
    "instrument_fx",
    "instrument_commodity",
    "ohlcv",
    "cmc_listings_latest",
    "cmc_listing_snapshots",
    "cmc_global_metrics",
    "cmc_category_coins",
    "data_source",
    "attribute_source_map",
    "ticker_source_map",
    "ohlcv_data_available",
    "trading_strategies",
]


def _table_exists_in_pg(pg_conn, table: str) -> bool:
    row = pg_conn.execute(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = %s)",
        [table],
    ).fetchone()
    return bool(row and row[0])


def _row_count_in_pg(pg_conn, table: str) -> int:
    row = pg_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    return row[0] if row else 0


def _copy_table(duck_conn, pg_conn, table: str, force: bool, dry_run: bool) -> int:
    """Copy all rows from DuckDB table into PostgreSQL. Returns rows copied."""
    try:
        rows = duck_conn.execute(f"SELECT * FROM {table}").fetchall()
    except Exception as exc:
        logger.warning("Skipping %s — not found in DuckDB source: %s", table, exc)
        return 0

    if not rows:
        logger.info("  %s: 0 rows in source — skipping", table)
        return 0

    if not _table_exists_in_pg(pg_conn, table):
        logger.warning("  %s: table does not exist in PostgreSQL — skipping", table)
        return 0

    existing = _row_count_in_pg(pg_conn, table)
    if existing > 0 and not force:
        logger.info(
            "  %s: %d rows already present — skipping (use --force to overwrite)",
            table,
            existing,
        )
        return 0

    if dry_run:
        logger.info("  %s: DRY RUN — would copy %d rows", table, len(rows))
        return len(rows)

    # Fetch column names from DuckDB cursor description.
    cur = duck_conn.execute(f"SELECT * FROM {table} LIMIT 0")
    cols = [d[0] for d in cur.description]
    placeholders = ", ".join(["%s"] * len(cols))
    col_names = ", ".join(cols)
    sql = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"

    if existing > 0 and force:
        logger.info("  %s: truncating %d existing rows before re-import", table, existing)
        pg_conn.execute(f"TRUNCATE TABLE {table} CASCADE")

    with pg_conn.cursor() as cur:
        cur.executemany(sql, rows)
    copied = len(rows)
    logger.info("  %s: copied %d rows", table, copied)
    return copied


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate data from a DuckDB file to PostgreSQL."
    )
    parser.add_argument(
        "--source",
        required=True,
        metavar="PATH",
        help="Path to the DuckDB database file to migrate from.",
    )
    parser.add_argument(
        "--url",
        metavar="DATABASE_URL",
        help=(
            "PostgreSQL connection URL. "
            "Defaults to the DATABASE_URL environment variable."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without writing to PostgreSQL.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Truncate existing tables before copying (use with care).",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(message)s",
    )

    try:
        import duckdb  # noqa: PLC0415
    except ImportError:
        logger.error(
            "The 'duckdb' package is required. Install dev extras: uv sync --extra dev"
        )
        sys.exit(1)

    import psycopg  # noqa: PLC0415

    from market_data.db.connection import get_database_url  # noqa: PLC0415

    db_url = args.url or get_database_url()

    logger.info("Source DuckDB: %s", args.source)
    logger.info("Target PostgreSQL: %s", db_url)

    duck_conn = duckdb.connect(args.source, read_only=True)
    pg_conn = psycopg.connect(db_url, autocommit=True)

    total_copied = 0
    try:
        for table in TABLES:
            total_copied += _copy_table(duck_conn, pg_conn, table, args.force, args.dry_run)
    finally:
        duck_conn.close()
        pg_conn.close()

    action = "Would copy" if args.dry_run else "Copied"
    logger.info("%s %d rows total across %d tables.", action, total_copied, len(TABLES))
