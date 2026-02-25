"""
draw-all-charts: iterate every symbol in hl_testnet_pairs_with_mcap.csv and
generate a price chart PNG using draw_chart.draw_chart().
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from draw_chart import draw_chart  # noqa: E402

CSV_PATH = ROOT / "hl_testnet_pairs_with_mcap.csv"


def main() -> None:
    with open(CSV_PATH, newline="") as f:
        rows = list(csv.DictReader(f))

    symbols = [row["base"] for row in rows]
    total = len(symbols)
    succeeded: list[str] = []
    failed: list[tuple[str, str]] = []

    for i, symbol in enumerate(symbols, start=1):
        print(f"[{i}/{total}] {symbol}")
        try:
            draw_chart(symbol)
            succeeded.append(symbol)
        except Exception as exc:  # noqa: BLE001
            print(f"  ERROR: {exc}")
            failed.append((symbol, str(exc)))

    print(f"\n{'='*50}")
    print(f"Done: {len(succeeded)} succeeded, {len(failed)} failed.")
    if failed:
        print("\nFailed symbols:")
        for sym, err in failed:
            print(f"  {sym}: {err}")
