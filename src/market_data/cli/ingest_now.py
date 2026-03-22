"""ingest-now CLI — manually trigger an ingestion job for a specific interval/connector."""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone


def _parse_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Manually trigger an ingestion job for a specific interval and/or connector. "
            "By default runs all active instruments against all connectors registered for the interval."
        )
    )
    parser.add_argument(
        "--interval",
        required=True,
        choices=["1m", "5m", "1h", "1d"],
        help="OHLCV interval to ingest",
    )
    parser.add_argument(
        "--connector",
        default=None,
        help="Connector name to use (e.g. eodhd). Default: all connectors for the interval.",
    )
    parser.add_argument(
        "--symbol",
        default=None,
        help="Restrict to a single ticker symbol (e.g. BTC). Default: all active instruments.",
    )
    parser.add_argument(
        "--asset-class",
        default=None,
        dest="asset_class",
        choices=["crypto", "equity", "etf", "fx", "commodity", "index", "future"],
        help="Restrict to instruments of this asset class (e.g. equity). Default: all classes.",
    )
    parser.add_argument(
        "--since",
        default=None,
        metavar="ISO8601",
        help="Start of fetch window in UTC (e.g. 2026-03-01T00:00:00). Default: lookback heuristic.",
    )
    parser.add_argument(
        "--until",
        default=None,
        metavar="ISO8601",
        help="End of fetch window in UTC. Default: now.",
    )
    parser.add_argument(
        "--fill-gaps",
        action=argparse.BooleanOptionalAction,
        default=True,
        dest="fill_gaps",
        help=(
            "Detect and fill historical data gaps (default: on). "
            "Scans back up to 30 days for 1h, 7 days for 5m, 24 h for 1m, "
            "1 year for 1d. Use --no-fill-gaps to disable."
        ),
    )
    args = parser.parse_args()

    import dotenv
    dotenv.load_dotenv()

    from market_data.db import migrate
    migrate()

    since: datetime | None = None
    until: datetime | None = None
    try:
        if args.since:
            since = _parse_dt(args.since)
        if args.until:
            until = _parse_dt(args.until)
    except ValueError as exc:
        print(f"Error: invalid date — {exc}", file=sys.stderr)
        sys.exit(1)

    from market_data.models.enums import AssetClass, Interval

    _INTERVAL_MAP: dict[str, Interval] = {
        "1m": Interval.ONE_MIN,
        "5m": Interval.FIVE_MIN,
        "1h": Interval.ONE_HOUR,
        "1d": Interval.ONE_DAY,
    }
    interval = _INTERVAL_MAP[args.interval]

    asset_class = AssetClass(args.asset_class) if args.asset_class else None

    instrument_id: str | None = None
    if args.symbol:
        from market_data.db.resolver import resolve_symbol
        from market_data.models.api import AmbiguousSymbolError, SymbolNotFoundError
        try:
            instrument_id = resolve_symbol(args.symbol, asset_class=asset_class)
        except AmbiguousSymbolError as exc:
            print(
                f"Error: {exc}. Use --asset-class to disambiguate.",
                file=sys.stderr,
            )
            sys.exit(1)
        except SymbolNotFoundError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)

    from market_data.ingestion.jobs import _run_interval_job
    try:
        stats = asyncio.run(
            _run_interval_job(
                interval,
                connector_name=args.connector,
                instrument_id=instrument_id,
                asset_class=asset_class,
                since=since,
                until=until,
                fill_gaps=args.fill_gaps,
            )
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"OK  written={stats['written']} errors={stats['errors']} skipped={stats['skipped']}")
    if stats["errors"] > 0:
        sys.exit(1)
