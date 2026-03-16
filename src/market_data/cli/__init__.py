"""market-data CLI — command-line entry points for the market data platform."""
from __future__ import annotations

import argparse
import logging
import os
import sys


def _import_cmc_static(args: argparse.Namespace) -> int:
    base_url = args.url or os.getenv("MARKET_DATA_URL", "http://localhost:8010").rstrip("/")
    endpoint = f"{base_url}/v1/admin/import-cmc-static"

    payload: dict = {}
    if args.dir:
        payload["dir"] = args.dir

    try:
        import httpx
        response = httpx.post(endpoint, json=payload, timeout=600.0)
    except Exception as exc:  # noqa: BLE001
        print(f"Error: could not connect to {endpoint}: {exc}", file=sys.stderr)
        return 1

    if not response.is_success:
        detail = response.json().get("detail") or response.text
        print(f"Error: {detail}", file=sys.stderr)
        return 1

    counts = response.json()
    if counts:
        print("Import complete:")
        for key, val in counts.items():
            print(f"  {key}: {val}")
    return 0


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(prog="market-data", description="Market Data Platform CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    cmc = sub.add_parser("import-cmc-static", help="Import CoinMarketCap static TSV snapshots via the REST service")
    cmc.add_argument("dir", nargs="?", default=None, help="Directory containing TSV snapshots (default: $CMC_STATIC_DIR on the server)")
    cmc.add_argument(
        "--url",
        default=None,
        help="Base URL of the REST service (default: $MARKET_DATA_URL or http://localhost:8010)",
    )

    args = parser.parse_args()

    if args.command == "import-cmc-static":
        sys.exit(_import_cmc_static(args))
