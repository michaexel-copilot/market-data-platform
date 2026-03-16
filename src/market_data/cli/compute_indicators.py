"""compute-indicators CLI — bulk-compute strategy indicator values for all active instruments."""
from __future__ import annotations

import argparse
import json
import sys
import time


def _upsert_indicators(conn, instrument_id: str, strategy_name: str, indicators: dict, parameters: dict) -> None:
    params_json = json.dumps(parameters)
    for indicator_name, indicator_value in indicators.items():
        conn.execute(
            """
            INSERT INTO trading_strategies
                (instrument_id, strategy_name, indicator_name, indicator_value, parameters, computed_at)
            VALUES (?, ?, ?, ?, ?, now())
            ON CONFLICT (instrument_id, strategy_name, indicator_name)
            DO UPDATE SET
                indicator_value = excluded.indicator_value,
                parameters      = excluded.parameters,
                computed_at     = excluded.computed_at
            """,
            [instrument_id, strategy_name, indicator_name, float(indicator_value), params_json],
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute and store strategy indicator values for instruments."
    )
    parser.add_argument("--strategy", required=True, help="Strategy name (e.g. best_sma)")
    parser.add_argument("--symbol", default=None, help="Ticker symbol to process (default: all active)")
    parser.add_argument("--sl-short", type=float, default=10.0, help="Stop-loss %% for short strategy (default: 10)")
    parser.add_argument("--sl-long",  type=float, default=10.0, help="Stop-loss %% for long strategy (default: 10)")
    parser.add_argument("--pos-usd",  type=float, default=100.0, help="Position size in USD (default: 100)")
    args = parser.parse_args()

    from market_data.strategies.registry import STRATEGY_REGISTRY

    if args.strategy not in STRATEGY_REGISTRY:
        available = ", ".join(sorted(STRATEGY_REGISTRY))
        print(f"Error: unknown strategy {args.strategy!r}. Available: {available}", file=sys.stderr)
        sys.exit(1)

    strategy_fn = STRATEGY_REGISTRY[args.strategy]
    parameters = {
        "sl_short": args.sl_short,
        "sl_long":  args.sl_long,
        "pos_usd":  args.pos_usd,
    }

    from market_data.db.connection import get_connection
    conn = get_connection()

    if args.symbol:
        rows = conn.execute(
            "SELECT instrument_id, ticker FROM instruments WHERE upper(ticker) = upper(?) AND is_active = TRUE",
            [args.symbol],
        ).fetchall()
        if not rows:
            print(f"Error: instrument {args.symbol!r} not found or not active.", file=sys.stderr)
            sys.exit(1)
    else:
        rows = conn.execute(
            "SELECT instrument_id, ticker FROM instruments WHERE is_active = TRUE ORDER BY ticker"
        ).fetchall()

    any_error = False

    for instrument_id, ticker in rows:
        t0 = time.monotonic()
        try:
            indicators = strategy_fn(instrument_id, parameters)
            _upsert_indicators(conn, instrument_id, args.strategy, indicators, parameters)
            elapsed = time.monotonic() - t0
            print(f"{ticker:<12} OK  ({elapsed:.2f}s)")
        except Exception as exc:  # noqa: BLE001
            elapsed = time.monotonic() - t0
            print(f"{ticker:<12} ERROR: {exc}  ({elapsed:.2f}s)")
            print(f"  {ticker}: {exc}", file=sys.stderr)
            any_error = True

    sys.exit(1 if any_error else 0)
