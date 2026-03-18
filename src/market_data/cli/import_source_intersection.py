"""import-source-intersection CLI — seeds instrument_source_intersection from cc_hl_intersection.csv."""
from __future__ import annotations

import csv
import sys
from pathlib import Path

CSV_PATH = Path("/appdata/static_data/cc_hl_intersection.csv")


def main() -> None:
    if not CSV_PATH.exists():
        print(
            f"Error: CSV file not found at {CSV_PATH}\n"
            "Generate it first via: uv run eodhd-cli.py --list CC (or equivalent).",
            file=sys.stderr,
        )
        sys.exit(1)

    from market_data.db.connection import get_connection

    conn = get_connection()

    # Load all crypto instrument tickers once for fast lookup
    rows = conn.execute(
        "SELECT instrument_id, upper(ticker) FROM instruments WHERE asset_class = 'crypto'"
    ).fetchall()
    ticker_map: dict[str, str] = {upper_ticker: iid for iid, upper_ticker in rows}

    matched = 0
    skipped = 0
    total = 0

    with CSV_PATH.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            total += 1
            base = (row.get("base") or "").strip().upper()
            instrument_id = ticker_map.get(base)
            if instrument_id is None:
                skipped += 1
                continue

            conn.execute(
                """
                INSERT INTO instrument_source_intersection (instrument_id, source_short_name)
                VALUES (%s, 'eodhd')
                ON CONFLICT DO NOTHING
                """,
                (instrument_id,),
            )
            conn.execute(
                """
                INSERT INTO instrument_source_intersection (instrument_id, source_short_name)
                VALUES (%s, 'hl')
                ON CONFLICT DO NOTHING
                """,
                (instrument_id,),
            )
            matched += 1

    print(f"import-source-intersection: matched={matched}, skipped={skipped}, total={total}")
