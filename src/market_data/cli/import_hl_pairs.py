"""import-hl-pairs CLI — refresh Hyperliquid perpetual pairs in the database."""
from __future__ import annotations

import argparse
import os
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch Hyperliquid perpetual pairs and upsert into instrument_hyperliquid.",
    )
    parser.add_argument(
        "--network",
        default="mainnet",
        choices=["mainnet", "testnet"],
        help="Which Hyperliquid network to import (default: mainnet)",
    )
    parser.add_argument(
        "--url",
        default=None,
        help="Base URL of the REST service (default: $MARKET_DATA_URL or http://localhost:8010)",
    )
    args = parser.parse_args()

    base_url = args.url or os.getenv("MARKET_DATA_URL", "http://localhost:8010").rstrip("/")
    endpoint = f"{base_url}/v1/admin/import-hl-pairs"

    try:
        import httpx
        response = httpx.post(endpoint, json={"network": args.network}, timeout=120.0)
    except Exception as exc:  # noqa: BLE001
        print(f"Error: could not connect to {endpoint}: {exc}", file=sys.stderr)
        sys.exit(1)

    if not response.is_success:
        print(f"Error: server returned HTTP {response.status_code}: {response.text}", file=sys.stderr)
        sys.exit(1)

    data = response.json()
    upserted = data.get("upserted", 0)
    unmatched = data.get("unmatched", 0)
    deactivated = data.get("deactivated", 0)
    print(f"Imported {upserted} pairs ({unmatched} unmatched, {deactivated} deactivated) [{args.network}]")
