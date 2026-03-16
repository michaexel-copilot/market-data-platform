"""import-ohlcv CLI — bulk-imports OHLCV from the local eodhd cache via the REST service."""
from __future__ import annotations

import argparse
import os
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import OHLCV data from the local eodhd cache into the database."
    )
    parser.add_argument("--interval", required=True, help="OHLCV interval to import (e.g. 1h)")
    parser.add_argument("--symbol", default=None, help="Ticker symbol to process (default: all active)")
    parser.add_argument(
        "--url",
        default=None,
        help="Base URL of the REST service (default: $MARKET_DATA_URL or http://localhost:8010)",
    )
    args = parser.parse_args()

    base_url = args.url or os.getenv("MARKET_DATA_URL", "http://localhost:8010").rstrip("/")
    endpoint = f"{base_url}/v1/admin/import-ohlcv"

    payload: dict = {"interval": args.interval}
    if args.symbol:
        payload["symbol"] = args.symbol

    try:
        import httpx
        response = httpx.post(endpoint, json=payload, timeout=600.0)
    except Exception as exc:  # noqa: BLE001
        print(f"Error: could not connect to {endpoint}: {exc}", file=sys.stderr)
        sys.exit(1)

    if response.status_code == 422:
        detail = response.json().get("detail") or response.text
        print(f"Error: {detail}", file=sys.stderr)
        sys.exit(1)

    if response.status_code == 404:
        detail = response.json().get("detail") or response.text
        print(f"Error: {detail}", file=sys.stderr)
        sys.exit(1)

    if not response.is_success:
        print(f"Error: server returned HTTP {response.status_code}: {response.text}", file=sys.stderr)
        sys.exit(1)

    data = response.json()
    for item in data.get("results", []):
        ticker = item["ticker"]
        elapsed = item.get("elapsed_s", 0.0)
        if item["status"] == "ok":
            rows = item.get("rows_imported", "?")
            print(f"{ticker:<12} OK  ({rows} rows, {elapsed:.2f}s)")
        else:
            error_msg = item.get("error", "unknown error")
            print(f"{ticker:<12} ERROR: {error_msg}  ({elapsed:.2f}s)", file=sys.stderr)

    sys.exit(1 if data.get("errors", 0) > 0 else 0)
