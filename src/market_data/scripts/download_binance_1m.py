"""download-binance-1m — download Binance historical 1-minute OHLCV flat files.

Downloads monthly klines ZIP archives from data.binance.vision and extracts
the CSV files into a local directory for subsequent import with import-binance-1m.

URL pattern:
    https://data.binance.vision/data/spot/monthly/klines/{SYMBOL}/1m/{SYMBOL}-1m-{YYYY}-{MM}.zip

Usage:
    download-binance-1m --symbol BTC [--from 2017-08] [--to 2025-12]
                        [--data-dir /mnt/ds420/data/binance/1-minute]

Already-downloaded months are skipped (idempotent).
"""
from __future__ import annotations

import argparse
import io
import sys
import zipfile
from datetime import date
from pathlib import Path

import httpx

_BASE_URL = "https://data.binance.vision/data/spot/monthly/klines"
_DEFAULT_DATA_DIR = "/mnt/ds420/data/binance/1-minute"
_EARLIEST_MONTH = (2017, 8)  # BTCUSDT data starts August 2017


# ---------------------------------------------------------------------------
# Pair resolution
# ---------------------------------------------------------------------------

def _resolve_binance_symbol(instrument_ticker: str) -> str:
    """Return the Binance pair symbol for the given ticker.

    Defaults to {TICKER}USDT unless an override is provided via --pair.
    """
    return instrument_ticker.upper() + "USDT"


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def _parse_ym(value: str) -> tuple[int, int]:
    """Parse a YYYY-MM string into (year, month)."""
    try:
        parts = value.split("-")
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        raise argparse.ArgumentTypeError(
            f"Invalid date format {value!r}. Expected YYYY-MM."
        )


def _month_range(
    from_ym: tuple[int, int], to_ym: tuple[int, int]
) -> list[tuple[int, int]]:
    """Return a list of (year, month) tuples from from_ym to to_ym inclusive."""
    months = []
    year, month = from_ym
    end_year, end_month = to_ym
    while (year, month) <= (end_year, end_month):
        months.append((year, month))
        month += 1
        if month > 12:
            month = 1
            year += 1
    return months


# ---------------------------------------------------------------------------
# Download logic
# ---------------------------------------------------------------------------

def _download_month(
    symbol: str,
    year: int,
    month: int,
    data_dir: Path,
    client: httpx.Client,
) -> bool:
    """Download and extract one monthly ZIP archive.

    Returns True if the file was downloaded, False if already present (skipped).
    """
    csv_name = f"{symbol}-1m-{year:04d}-{month:02d}.csv"
    csv_path = data_dir / csv_name

    if csv_path.exists():
        print(f"  skip  {csv_name} (already present)")
        return False

    zip_name = f"{symbol}-1m-{year:04d}-{month:02d}.zip"
    url = f"{_BASE_URL}/{symbol}/1m/{zip_name}"

    try:
        resp = client.get(url, follow_redirects=True)
    except httpx.RequestError as exc:
        print(f"  error {csv_name}: {exc}", file=sys.stderr)
        return False

    if resp.status_code == 404:
        print(f"  404   {csv_name} (not yet available or symbol mismatch)")
        return False
    if resp.status_code != 200:
        print(
            f"  error {csv_name}: HTTP {resp.status_code}", file=sys.stderr
        )
        return False

    # Extract the single CSV from the ZIP payload.
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        members = zf.namelist()
        csv_members = [m for m in members if m.endswith(".csv")]
        if not csv_members:
            print(f"  error {csv_name}: no CSV in ZIP", file=sys.stderr)
            return False
        zf.extract(csv_members[0], path=data_dir)
        # Rename if the extracted name differs from our convention.
        extracted = data_dir / csv_members[0]
        if extracted != csv_path:
            extracted.rename(csv_path)

    print(f"  ok    {csv_name}")
    return True


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    today = date.today()
    prev_month = today.month - 1
    default_to = (
        f"{today.year}-{prev_month:02d}" if prev_month > 0 else f"{today.year - 1}-12"
    )

    parser = argparse.ArgumentParser(
        description="Download Binance historical 1-minute OHLCV flat files."
    )
    parser.add_argument(
        "--symbol",
        required=True,
        help="Ticker symbol (e.g. BTC). Pair is resolved as {SYMBOL}USDT unless --pair is given.",
    )
    parser.add_argument(
        "--pair",
        help=(
            "Override Binance trading-pair symbol (e.g. BTCUSDT). "
            "Derived from --symbol by default."
        ),
    )
    parser.add_argument(
        "--from",
        dest="from_ym",
        default="2017-08",
        help="Start month YYYY-MM (default: 2017-08, earliest available for BTCUSDT).",
    )
    parser.add_argument(
        "--to",
        dest="to_ym",
        default=default_to,
        help=f"End month YYYY-MM inclusive (default: {default_to}, last completed month).",
    )
    parser.add_argument(
        "--data-dir",
        default=_DEFAULT_DATA_DIR,
        help=f"Local directory to save extracted CSV files (default: {_DEFAULT_DATA_DIR}).",
    )
    args = parser.parse_args()

    binance_symbol = args.pair if args.pair else _resolve_binance_symbol(args.symbol)
    from_ym = _parse_ym(args.from_ym)
    to_ym = _parse_ym(args.to_ym)
    data_dir = Path(args.data_dir)

    if from_ym > to_ym:
        print("Error: --from must be before or equal to --to.", file=sys.stderr)
        sys.exit(1)

    data_dir.mkdir(parents=True, exist_ok=True)
    months = _month_range(from_ym, to_ym)

    print(
        f"Downloading {binance_symbol} 1m klines: "
        f"{from_ym[0]:04d}-{from_ym[1]:02d} → {to_ym[0]:04d}-{to_ym[1]:02d} "
        f"({len(months)} months) → {data_dir}"
    )

    downloaded = 0
    skipped = 0
    with httpx.Client(timeout=60) as client:
        for year, month in months:
            result = _download_month(binance_symbol, year, month, data_dir, client)
            if result:
                downloaded += 1
            else:
                skipped += 1

    print(f"\nDone: {downloaded} downloaded, {skipped} skipped.")
