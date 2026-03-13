"""market-data CLI — command-line entry points for the market data platform."""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path


def _import_cmc_static(args: argparse.Namespace) -> int:
    from market_data.ingestion.import_coinmarketcap_static import run_import

    directory = Path(args.dir) if args.dir else Path(os.getenv("CMC_STATIC_DIR", ""))
    if not directory or not directory.exists():
        print(f"Error: directory does not exist: {directory or '<CMC_STATIC_DIR not set>'}", file=sys.stderr)
        return 1
    if not directory.is_dir():
        print(f"Error: path is not a directory: {directory}", file=sys.stderr)
        return 1

    counts = run_import(directory, dry_run=args.dry_run)
    if counts:
        print("Import complete:")
        for key, val in counts.items():
            print(f"  {key}: {val}")
    return 0


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(prog="market-data", description="Market Data Platform CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    cmc = sub.add_parser("import-cmc-static", help="Import CoinMarketCap static TSV snapshots into DuckDB")
    cmc.add_argument("dir", nargs="?", default=None, help="Directory containing TSV snapshots (default: $CMC_STATIC_DIR)")
    cmc.add_argument("--dry-run", action="store_true", help="Parse files without writing to the database")

    args = parser.parse_args()

    if args.command == "import-cmc-static":
        sys.exit(_import_cmc_static(args))
