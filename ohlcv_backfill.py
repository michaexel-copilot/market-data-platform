"""
ohlcv_backfill: fill the TimescaleDB OHLCV store with deep history from free sources.

Sources:
  binance      Binance Public Data ZIPs (data.binance.vision), spot or USDⓈ-M futures,
               full history since listing, monthly files plus daily files for the
               current month
  kraken       Kraken's downloadable OHLCVT dump (a local ZIP, full history per pair)
  okx          OKX REST /api/v5/market/history-candles, paged backwards
  hyperliquid  Hyperliquid candleSnapshot (only the latest 5000 candles per interval,
               so run `update` daily to keep an archive)

Every source yields Candle tuples which are upserted into the OHLCV hypertable keyed
by (coin, interval, source, ts). Existing rows are never overwritten. Which exchange
symbol belongs to which coin comes from seed/backfill_symbols.csv.

CLI (uv run backfill --help):
  backfill init-schema                         create table, indexes, views (idempotent)
  backfill binance  --coins bitcoin --interval 1h --start 2017-08
  backfill kraken   --zip ~/Downloads/Kraken_OHLCVT.zip --coins bitcoin,ethereum
  backfill okx      --coins bitcoin --interval 1h --start 2019-01-01
  backfill hyperliquid --interval 1h
  backfill update   --days 3                   daily increment for all mapped coins
  backfill coverage                            print depth / fill ratio per series

Database connection comes from DATABASE_URL (libpq URL), the table name from
OHLCV_TABLE (default "ohlcv").
"""
import argparse
import csv
import io
import os
import sys
import time
import zipfile
from collections.abc import Iterable, Iterator
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple

import requests

ROOT = Path(__file__).parent
SYMBOLS_CSV = ROOT / "seed" / "backfill_symbols.csv"
SCHEMA_SQL = ROOT / "db" / "ohlcv_schema.sql"

INTERVAL_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}

BINANCE_VISION = "https://data.binance.vision/data"
OKX_HISTORY_URL = "https://www.okx.com/api/v5/market/history-candles"
HL_INFO_URL = "https://api.hyperliquid.xyz/info"

# OKX bar names; "1Dutc" keeps daily candles aligned to UTC midnight ("1D" is UTC+8).
OKX_BARS = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1H", "4h": "4Hutc", "1d": "1Dutc"}
# Kraken dump file suffix (minutes) -> our interval
KRAKEN_MINUTES = {1: "1m", 5: "5m", 15: "15m", 60: "1h", 240: "4h", 1440: "1d"}

HTTP_TIMEOUT = 30


class Candle(NamedTuple):
    ts: datetime          # candle open time, UTC
    open: float
    high: float
    low: float
    close: float
    volume: float         # base-asset volume
    trade_count: int | None = None
    vwap: float | None = None


def _utc(ms: int | float) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def _vwap(quote_volume: float, volume: float) -> float | None:
    return quote_volume / volume if volume else None


# ---------------------------------------------------------------------------
# Symbol map
# ---------------------------------------------------------------------------

def load_symbol_map(path: Path = SYMBOLS_CSV) -> dict[str, dict[str, str]]:
    """coin -> {source: exchange symbol}; empty cells mean "not listed there"."""
    with open(path, newline="") as f:
        return {
            row["coin"]: {k: v for k, v in row.items() if k != "coin" and v}
            for row in csv.DictReader(f)
        }


def _select(symbols: dict[str, dict[str, str]], coins: str | None, source: str) -> list[tuple[str, str]]:
    wanted = set(coins.split(",")) if coins else None
    unknown = (wanted or set()) - symbols.keys()
    if unknown:
        raise SystemExit(f"unknown coin(s) {sorted(unknown)}; add them to {SYMBOLS_CSV.name}")
    return [(c, m[source]) for c, m in symbols.items() if source in m and (wanted is None or c in wanted)]


# ---------------------------------------------------------------------------
# Binance Public Data
# ---------------------------------------------------------------------------

def parse_binance_kline_csv(text: str) -> Iterator[Candle]:
    """Binance kline CSV: open_time, o, h, l, c, volume, close_time, quote_volume,
    trades, taker_base, taker_quote, ignore. Futures files carry a header row; spot
    files from 2025 on use microsecond timestamps."""
    for row in csv.reader(io.StringIO(text)):
        if not row or not row[0].isdigit():
            continue
        open_time = int(row[0])
        if open_time > 10**14:          # microseconds
            open_time //= 1000
        volume = float(row[5])
        yield Candle(
            ts=_utc(open_time),
            open=float(row[1]), high=float(row[2]), low=float(row[3]), close=float(row[4]),
            volume=volume, trade_count=int(row[8]), vwap=_vwap(float(row[7]), volume),
        )


def _binance_zip_url(market: str, period: str, symbol: str, interval: str, stamp: str) -> str:
    base = "spot" if market == "spot" else "futures/um"
    return f"{BINANCE_VISION}/{base}/{period}/klines/{symbol}/{interval}/{symbol}-{interval}-{stamp}.zip"


def _download_zip_csv(session: requests.Session, url: str) -> str | None:
    resp = session.get(url, timeout=HTTP_TIMEOUT)
    if resp.status_code == 404:        # before listing, or not published yet
        return None
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        return zf.read(zf.namelist()[0]).decode()


def binance_file_stamps(start: date, end: date) -> list[tuple[str, str]]:
    """(period, stamp) pairs covering [start, end]: monthly files for complete past
    months, daily files for the month `end` falls in (its monthly file does not
    exist yet)."""
    stamps: list[tuple[str, str]] = []
    month = date(start.year, start.month, 1)
    current_month = date(end.year, end.month, 1)
    while month < current_month:
        stamps.append(("monthly", f"{month:%Y-%m}"))
        month = (month + timedelta(days=32)).replace(day=1)
    day = max(start, current_month)
    while day <= end:
        stamps.append(("daily", f"{day:%Y-%m-%d}"))
        day += timedelta(days=1)
    return stamps


def fetch_binance(symbol: str, interval: str, start: date, end: date, market: str = "spot",
                  session: requests.Session | None = None) -> Iterator[Candle]:
    session = session or requests.Session()
    for period, stamp in binance_file_stamps(start, end):
        text = _download_zip_csv(session, _binance_zip_url(market, period, symbol, interval, stamp))
        if text:
            yield from parse_binance_kline_csv(text)


# ---------------------------------------------------------------------------
# Kraken OHLCVT dump
# ---------------------------------------------------------------------------

def parse_kraken_csv(text: str) -> Iterator[Candle]:
    """Kraken dump CSV without header: time(s), o, h, l, c, volume, trades."""
    for row in csv.reader(io.StringIO(text)):
        if not row:
            continue
        yield Candle(
            ts=datetime.fromtimestamp(int(row[0]), tz=timezone.utc),
            open=float(row[1]), high=float(row[2]), low=float(row[3]), close=float(row[4]),
            volume=float(row[5]), trade_count=int(row[6]),
        )


def kraken_members(zf: zipfile.ZipFile, pair: str) -> dict[str, str]:
    """interval -> member name for files like 'XBTUSD_60.csv' (any folder depth)."""
    found = {}
    for name in zf.namelist():
        stem = Path(name).stem
        p, _, minutes = stem.rpartition("_")
        if p == pair and minutes.isdigit() and int(minutes) in KRAKEN_MINUTES:
            found[KRAKEN_MINUTES[int(minutes)]] = name
    return found


# ---------------------------------------------------------------------------
# OKX
# ---------------------------------------------------------------------------

def parse_okx_rows(rows: list[list[str]]) -> Iterator[Candle]:
    """OKX rows: ts, o, h, l, c, vol (base), volCcy, volCcyQuote, confirm."""
    for r in rows:
        if r[8] != "1":                 # candle still open
            continue
        volume = float(r[5])
        yield Candle(
            ts=_utc(int(r[0])),
            open=float(r[1]), high=float(r[2]), low=float(r[3]), close=float(r[4]),
            volume=volume, vwap=_vwap(float(r[7]), volume),
        )


def fetch_okx(inst_id: str, interval: str, start: datetime, end: datetime,
              session: requests.Session | None = None) -> Iterator[Candle]:
    """Pages backwards from `end` (100 candles per call, public limit 20 calls / 2 s)."""
    session = session or requests.Session()
    after = int(end.timestamp() * 1000)
    start_ms = int(start.timestamp() * 1000)
    while after > start_ms:
        resp = session.get(OKX_HISTORY_URL, timeout=HTTP_TIMEOUT, params={
            "instId": inst_id, "bar": OKX_BARS[interval], "after": after, "limit": 100,
        })
        resp.raise_for_status()
        body = resp.json()
        if body.get("code") != "0":
            raise RuntimeError(f"OKX {inst_id}: {body.get('msg')}")
        rows = body["data"]
        if not rows:
            return
        yield from (c for c in parse_okx_rows(rows) if c.ts.timestamp() * 1000 >= start_ms)
        after = int(rows[-1][0])        # newest first, so the last row is the oldest
        time.sleep(0.11)


# ---------------------------------------------------------------------------
# Hyperliquid
# ---------------------------------------------------------------------------

def parse_hl_candles(rows: list[dict], now_ms: int) -> Iterator[Candle]:
    for r in rows:
        if r["T"] >= now_ms:            # candle still open
            continue
        yield Candle(
            ts=_utc(r["t"]),
            open=float(r["o"]), high=float(r["h"]), low=float(r["l"]), close=float(r["c"]),
            volume=float(r["v"]), trade_count=int(r["n"]),
        )


def fetch_hyperliquid(coin: str, interval: str, start: datetime, end: datetime,
                      session: requests.Session | None = None) -> Iterator[Candle]:
    """Only the latest 5000 candles exist; older start times simply return less."""
    session = session or requests.Session()
    start_ms, end_ms = int(start.timestamp() * 1000), int(end.timestamp() * 1000)
    while start_ms < end_ms:
        resp = session.post(HL_INFO_URL, timeout=HTTP_TIMEOUT, json={
            "type": "candleSnapshot",
            "req": {"coin": coin, "interval": interval, "startTime": start_ms, "endTime": end_ms},
        })
        resp.raise_for_status()
        rows = resp.json()
        if not rows:
            return
        yield from parse_hl_candles(rows, int(time.time() * 1000))
        next_start = rows[-1]["t"] + INTERVAL_SECONDS[interval] * 1000
        if next_start <= start_ms:
            return
        start_ms = next_start


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def connect():
    import psycopg  # imported lazily so the parsers stay usable without a database

    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is not set")
    return psycopg.connect(url)


def _table() -> str:
    return os.environ.get("OHLCV_TABLE", "ohlcv")


def upsert(conn, coin: str, interval: str, source: str, candles: Iterable[Candle],
           batch_size: int = 50_000) -> int:
    """COPY into a temp table, then INSERT .. ON CONFLICT DO NOTHING. Returns new rows."""
    from psycopg import sql

    table = sql.Identifier(_table())
    inserted = 0
    batch: list[Candle] = []

    def flush() -> int:
        with conn.cursor() as cur:
            cur.execute(sql.SQL(
                "CREATE TEMP TABLE _ohlcv_load ON COMMIT DROP AS "
                "SELECT coin, interval, source, ts, open, high, low, close, volume, trade_count, vwap "
                "FROM {} WITH NO DATA").format(table))
            with cur.copy("COPY _ohlcv_load FROM STDIN") as cp:
                for c in batch:
                    cp.write_row((coin, interval, source, *c))
            cur.execute(sql.SQL(
                "INSERT INTO {} (coin, interval, source, ts, open, high, low, close, volume, trade_count, vwap) "
                "SELECT * FROM _ohlcv_load ON CONFLICT (coin, interval, source, ts) DO NOTHING").format(table))
            n = cur.rowcount
        conn.commit()
        batch.clear()
        return n

    for candle in candles:
        batch.append(candle)
        if len(batch) >= batch_size:
            inserted += flush()
    if batch:
        inserted += flush()
    return inserted


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_day(s: str) -> date:
    return date.fromisoformat(s + "-01" if len(s) == 7 else s)


def _log(coin: str, interval: str, source: str, n: int) -> None:
    print(f"{source:<16} {coin:<20} {interval:<4} +{n} rows", flush=True)


def cmd_init_schema(args: argparse.Namespace) -> None:
    with connect() as conn:
        conn.execute(SCHEMA_SQL.read_text().replace("{table}", _table()))
    print("schema ok")


def cmd_binance(args: argparse.Namespace) -> None:
    source = "binance" if args.market == "spot" else "binance_futures"
    start, end = _parse_day(args.start), _parse_day(args.end) if args.end else date.today()
    session = requests.Session()
    with connect() as conn:
        for coin, symbol in _select(load_symbol_map(), args.coins, source):
            n = upsert(conn, coin, args.interval, source,
                       fetch_binance(symbol, args.interval, start, end, args.market, session))
            _log(coin, args.interval, source, n)


def cmd_kraken(args: argparse.Namespace) -> None:
    wanted = set(args.intervals.split(","))
    with zipfile.ZipFile(args.zip) as zf, connect() as conn:
        for coin, pair in _select(load_symbol_map(), args.coins, "kraken"):
            for interval, member in sorted(kraken_members(zf, pair).items()):
                if interval in wanted:
                    n = upsert(conn, coin, interval, "kraken", parse_kraken_csv(zf.read(member).decode()))
                    _log(coin, interval, "kraken", n)


def cmd_okx(args: argparse.Namespace) -> None:
    start = datetime.combine(_parse_day(args.start), datetime.min.time(), timezone.utc)
    end = datetime.now(timezone.utc)
    session = requests.Session()
    with connect() as conn:
        for coin, inst in _select(load_symbol_map(), args.coins, "okx"):
            n = upsert(conn, coin, args.interval, "okx", fetch_okx(inst, args.interval, start, end, session))
            _log(coin, args.interval, "okx", n)


def cmd_hyperliquid(args: argparse.Namespace) -> None:
    end = datetime.now(timezone.utc)
    start = end - timedelta(seconds=INTERVAL_SECONDS[args.interval] * 5000)
    session = requests.Session()
    with connect() as conn:
        for coin, hl in _select(load_symbol_map(), args.coins, "hyperliquid"):
            n = upsert(conn, coin, args.interval, "hyperliquid",
                       fetch_hyperliquid(hl, args.interval, start, end, session))
            _log(coin, args.interval, "hyperliquid", n)


def cmd_update(args: argparse.Namespace) -> None:
    """Daily increment: the last N days from every source each coin is mapped to."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=args.days)
    symbols = load_symbol_map()
    session = requests.Session()
    with connect() as conn:
        for interval in args.intervals.split(","):
            for coin, sym in _select(symbols, args.coins, "binance"):
                n = upsert(conn, coin, interval, "binance",
                           fetch_binance(sym, interval, start.date(), end.date(), "spot", session))
                _log(coin, interval, "binance", n)
            for coin, sym in _select(symbols, args.coins, "okx"):
                n = upsert(conn, coin, interval, "okx", fetch_okx(sym, interval, start, end, session))
                _log(coin, interval, "okx", n)
            for coin, sym in _select(symbols, args.coins, "hyperliquid"):
                n = upsert(conn, coin, interval, "hyperliquid",
                           fetch_hyperliquid(sym, interval, start, end, session))
                _log(coin, interval, "hyperliquid", n)


def cmd_coverage(args: argparse.Namespace) -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT * FROM {_table()}_coverage ORDER BY coin, interval, source")
        cols = [d.name for d in cur.description]
        writer = csv.writer(sys.stdout)
        writer.writerow(cols)
        writer.writerows(cur.fetchall())


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="backfill", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-schema").set_defaults(func=cmd_init_schema)

    b = sub.add_parser("binance", help="Binance Public Data ZIPs")
    b.add_argument("--coins", help="comma-separated coins from backfill_symbols.csv (default: all)")
    b.add_argument("--interval", default="1h", choices=list(INTERVAL_SECONDS))
    b.add_argument("--start", default="2017-08", help="YYYY-MM or YYYY-MM-DD")
    b.add_argument("--end", help="YYYY-MM-DD (default: today)")
    b.add_argument("--market", default="spot", choices=["spot", "futures"])
    b.set_defaults(func=cmd_binance)

    k = sub.add_parser("kraken", help="Kraken OHLCVT dump ZIP")
    k.add_argument("--zip", required=True, type=Path)
    k.add_argument("--coins")
    k.add_argument("--intervals", default="1m,5m,1h,1d")
    k.set_defaults(func=cmd_kraken)

    o = sub.add_parser("okx", help="OKX history-candles")
    o.add_argument("--coins")
    o.add_argument("--interval", default="1h", choices=list(OKX_BARS))
    o.add_argument("--start", default="2018-01-01")
    o.set_defaults(func=cmd_okx)

    h = sub.add_parser("hyperliquid", help="Hyperliquid candleSnapshot (latest 5000 candles)")
    h.add_argument("--coins")
    h.add_argument("--interval", default="1h", choices=list(INTERVAL_SECONDS))
    h.set_defaults(func=cmd_hyperliquid)

    u = sub.add_parser("update", help="daily increment for all mapped coins")
    u.add_argument("--coins")
    u.add_argument("--days", type=int, default=3)
    u.add_argument("--intervals", default="1h,1d")
    u.set_defaults(func=cmd_update)

    sub.add_parser("coverage", help="depth and fill ratio per series as CSV").set_defaults(func=cmd_coverage)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
