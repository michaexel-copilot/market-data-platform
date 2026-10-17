"""download-cryptodatadownload-1h — download hourly OHLCV flat files from
cryptodatadownload.com for one or all available crypto instruments.

URL pattern (free, no account required, confirmed for the Binance listing):
    https://www.cryptodatadownload.com/cdd/{Exchange}_{PAIR}_1h.csv

Usage:
    download-cryptodatadownload-1h --symbol BTC [--exchange Binance]
                                    [--data-dir /mnt/ds420/data/cryptodatadownload/1-hour]
    download-cryptodatadownload-1h --all

Already-downloaded pairs are re-fetched every run (the site publishes a single
rolling file per pair, not dated archives), so this script is safe to re-run
on a schedule to pick up new hours.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx
import yaml

from market_data.db.connection import get_connection
from market_data.db.resolver import resolve_symbol
from market_data.models.api import SymbolNotFoundError

_BASE_URL = "https://www.cryptodatadownload.com/cdd"
_DEFAULT_DATA_DIR = "/mnt/ds420/data/cryptodatadownload/1-hour"
_DEFAULT_EXCHANGE = "Binance"
_PAIRS_YAML = Path(__file__).parent.parent / "config" / "cryptodatadownload_pairs.yaml"


# ---------------------------------------------------------------------------
# Pair resolution
# ---------------------------------------------------------------------------

def _load_pair_overrides() -> dict[str, str]:
    if _PAIRS_YAML.exists():
        with _PAIRS_YAML.open() as fh:
            return yaml.safe_load(fh) or {}
    return {}


def resolve_cdd_pair(instrument_id: str, ticker: str) -> str:
    """Return the CryptoDataDownload pair symbol for the given instrument.

    Checks config/cryptodatadownload_pairs.yaml for overrides; falls back to {TICKER}USDT.
    """
    overrides = _load_pair_overrides()
    if instrument_id in overrides:
        return overrides[instrument_id]
    return f"{ticker.upper()}USDT"


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _active_crypto_instruments() -> list[tuple[str, str]]:
    """Return (instrument_id, ticker) for every active crypto instrument."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT instrument_id, ticker FROM instruments "
        "WHERE asset_class = 'crypto' AND is_active = TRUE ORDER BY ticker"
    ).fetchall()
    return [(r[0], r[1]) for r in rows]


def _get_ticker(instrument_id: str) -> str:
    conn = get_connection()
    row = conn.execute(
        "SELECT ticker FROM instruments WHERE instrument_id = %s",
        [instrument_id],
    ).fetchone()
    return row[0] if row else instrument_id.upper()


# ---------------------------------------------------------------------------
# Download logic
# ---------------------------------------------------------------------------

def _download_pair(
    exchange: str,
    pair: str,
    data_dir: Path,
    client: httpx.Client,
) -> bool:
    """Download one pair's CSV. Returns True on success, False otherwise."""
    csv_name = f"{exchange}_{pair}_1h.csv"
    url = f"{_BASE_URL}/{csv_name}"
    csv_path = data_dir / csv_name

    try:
        resp = client.get(url, follow_redirects=True)
    except httpx.RequestError as exc:
        print(f"  error {csv_name}: {exc}", file=sys.stderr)
        return False

    if resp.status_code == 404:
        print(f"  404   {csv_name} (no such pair on cryptodatadownload.com)")
        return False
    if resp.status_code != 200:
        print(f"  error {csv_name}: HTTP {resp.status_code}", file=sys.stderr)
        return False

    csv_path.write_bytes(resp.content)
    print(f"  ok    {csv_name}")
    return True


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download hourly OHLCV flat files from cryptodatadownload.com."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--symbol",
        help="HL/CMC ticker symbol to download (e.g. BTC)",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Download for every active crypto instrument in the database",
    )
    parser.add_argument(
        "--exchange",
        default=_DEFAULT_EXCHANGE,
        help=f"Exchange listing on cryptodatadownload.com (default: {_DEFAULT_EXCHANGE}; "
        "only Binance is confirmed to follow this URL convention)",
    )
    parser.add_argument(
        "--data-dir",
        default=_DEFAULT_DATA_DIR,
        help=f"Local directory to save CSV files (default: {_DEFAULT_DATA_DIR})",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    if args.all:
        instruments = _active_crypto_instruments()
        if not instruments:
            print("No active crypto instruments found.", file=sys.stderr)
            sys.exit(1)
    else:
        try:
            instrument_id = resolve_symbol(args.symbol)
        except SymbolNotFoundError:
            print(f"Error: symbol {args.symbol!r} not found in database.", file=sys.stderr)
            sys.exit(1)
        instruments = [(instrument_id, _get_ticker(instrument_id))]

    print(
        f"Downloading {args.exchange} 1h data for {len(instruments)} instrument(s) → {data_dir}"
    )

    downloaded = 0
    skipped = 0
    with httpx.Client(timeout=60) as client:
        for instrument_id, ticker in instruments:
            pair = resolve_cdd_pair(instrument_id, ticker)
            if _download_pair(args.exchange, pair, data_dir, client):
                downloaded += 1
            else:
                skipped += 1

    print(f"\nDone: {downloaded} downloaded, {skipped} skipped.")


if __name__ == "__main__":
    main()
