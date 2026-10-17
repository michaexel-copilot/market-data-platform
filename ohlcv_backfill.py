"""
ohlcv_backfill: fill the existing TimescaleDB `ohlcv` table with deep history from
free sources.

Sources (value written to ohlcv.source):
  binance      Binance Public Data spot ZIPs (data.binance.vision), full history since
               listing, monthly files plus daily files for the current month
  kraken       Kraken's downloadable OHLCVT dump (a local ZIP, full history per pair)
  okx          OKX REST /api/v5/market/history-candles, paged backwards
  hyperliquid  Hyperliquid candleSnapshot (only the latest 5000 candles per interval,
               so run `update` daily to keep an archive)

Rows go into ohlcv keyed by its primary key (instrument_id, interval, ts) with
ON CONFLICT DO NOTHING: an existing candle from any source is never overwritten, the
loader only fills holes and extends history. tick_1m / tick_1h / tick_1d are derived
from ts (epoch // 60, 3600, 86400); candles failing the table's price sanity check
are skipped. After each load, ohlcv_data_available is flagged for the source's
data_source row. Which exchange symbol belongs to which instrument_id comes from
seed/backfill_symbols.csv; instruments missing from `instruments` are skipped.

CLI (uv run backfill --help):
  backfill init-views                          create backfill_coverage / backfill_gaps
  backfill binance  --coins bitcoin --interval 1h --start 2017-08
  backfill kraken   --zip ~/Downloads/Kraken_OHLCVT.zip --coins bitcoin,ethereum
  backfill okx      --coins bitcoin --interval 1h --start 2019-01-01
  backfill hyperliquid --interval 1h
  backfill update   --days 3                   daily increment for all mapped coins
  backfill coverage                            print depth / fill ratio per series

Database connection comes from DATABASE_URL (libpq URL).
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
VIEWS_SQL = ROOT / "db" / "backfill_views.sql"

# Only the intervals the ohlcv table accepts (ohlcv_interval_check).
INTERVAL_SECONDS = {"1m": 60, "5m": 300, "1h": 3600, "1d": 86400}

BINANCE_VISION = "https://data.binance.vision/data"
OKX_HISTORY_URL = "https://www.okx.com/api/v5/market/history-candles"
HL_INFO_URL = "https://api.hyperliquid.xyz/info"

# OKX bar names; "1Dutc" keeps daily candles aligned to UTC midnight ("1D" is UTC+8).
OKX_BARS = {"1m": "1m", "5m": "5m", "1h": "1H", "1d": "1Dutc"}
# Kraken dump file suffix (minutes) -> our interval
KRAKEN_MINUTES = {1: "1m", 5: "5m", 60: "1h", 1440: "1d"}
# ohlcv.source -> data_source.short_name, for flagging ohlcv_data_available
DATA_SOURCE_SHORT_NAMES = {"binance": "binance_hist", "kraken": "kraken_hist", "hyperliquid": "hl"}

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
    """instrument_id -> {source: exchange symbol}; empty cells mean "not listed there"."""
    with open(path, newline="") as f:
        return {
            row["instrument_id"]: {k: v for k, v in row.items() if k != "instrument_id" and v}
            for row in csv.DictReader(f)
        }


def _select(symbols: dict[str, dict[str, str]], coins: str | None, source: str) -> list[tuple[str, str]]:
    wanted = set(coins.split(",")) if coins else None
    unknown = (wanted or set()) - symbols.keys()
    if unknown:
        raise SystemExit(f"unknown instrument_id(s) {sorted(unknown)}; add them to {SYMBOLS_CSV.name}")
    return [(c, m[source]) for c, m in symbols.items() if source in m and (wanted is None or c in wanted)]


# ---------------------------------------------------------------------------
# Binance Public Data
# ---------------------------------------------------------------------------

def parse_binance_kline_csv(text: str) -> Iterator[Candle]:
    """Binance kline CSV: open_time, o, h, l, c, volume, close_time, quote_volume,
    trades, taker_base, taker_quote, ignore. Some files carry a header row; spot
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


def _binance_zip_url(period: str, symbol: str, interval: str, stamp: str) -> str:
    return f"{BINANCE_VISION}/spot/{period}/klines/{symbol}/{interval}/{symbol}-{interval}-{stamp}.zip"


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


def fetch_binance(symbol: str, interval: str, start: date, end: date,
                  session: requests.Session | None = None) -> Iterator[Candle]:
    session = session or requests.Session()
    for period, stamp in binance_file_stamps(start, end):
        text = _download_zip_csv(session, _binance_zip_url(period, symbol, interval, stamp))
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


def is_sane(c: Candle) -> bool:
    """Mirror of the ohlcv_price_sanity check constraint; one bad row would abort the batch."""
    return (
        c.open > 0 and c.high > 0 and c.low > 0 and c.close > 0
        and c.high >= max(c.open, c.close) and c.low <= min(c.open, c.close)
        and c.volume >= 0 and (c.vwap is None or c.vwap >= 0)
        and (c.trade_count is None or c.trade_count >= 0)
    )


def _row(instrument_id: str, interval: str, source: str, c: Candle) -> tuple:
    epoch = int(c.ts.timestamp())
    return (
        instrument_id, interval, source, c.ts, c.open, c.high, c.low, c.close, c.volume,
        c.trade_count, c.vwap,
        epoch // 60 if interval == "1m" else None,
        epoch // 3600 if interval == "1h" else None,
        epoch // 86400 if interval == "1d" else None,
    )


def known_instruments(conn, ids: Iterable[str]) -> set[str]:
    rows = conn.execute("SELECT instrument_id FROM instruments WHERE instrument_id = ANY(%s)", (list(ids),))
    return {r[0] for r in rows}


def upsert(conn, instrument_id: str, interval: str, source: str, candles: Iterable[Candle],
           batch_size: int = 50_000) -> tuple[int, int]:
    """COPY into a temp table, then INSERT .. ON CONFLICT DO NOTHING.
    Returns (new rows, candles skipped by the sanity check)."""
    inserted = skipped = 0
    batch: list[tuple] = []

    def flush() -> int:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE TEMP TABLE _ohlcv_load ("
                " instrument_id text, interval text, source text, ts timestamptz,"
                " open double precision, high double precision, low double precision,"
                " close double precision, volume double precision, trade_count integer,"
                " vwap double precision, tick_1m bigint, tick_1h bigint, tick_1d bigint"
                ") ON COMMIT DROP")
            with cur.copy("COPY _ohlcv_load FROM STDIN") as cp:
                for row in batch:
                    cp.write_row(row)
            cur.execute(
                "INSERT INTO ohlcv (instrument_id, interval, source, ts, open, high, low, close,"
                " volume, trade_count, vwap, tick_1m, tick_1h, tick_1d) "
                "SELECT * FROM _ohlcv_load ON CONFLICT (instrument_id, interval, ts) DO NOTHING")
            n = cur.rowcount
        conn.commit()
        batch.clear()
        return n

    for candle in candles:
        if not is_sane(candle):
            skipped += 1
            continue
        batch.append(_row(instrument_id, interval, source, candle))
        if len(batch) >= batch_size:
            inserted += flush()
    if batch:
        inserted += flush()
    if inserted:
        mark_available(conn, instrument_id, interval, source)
    return inserted, skipped


def mark_available(conn, instrument_id: str, interval: str, source: str) -> None:
    """Set has_<interval> in ohlcv_data_available for sources that have a data_source row."""
    short_name = DATA_SOURCE_SHORT_NAMES.get(source)
    if not short_name:
        return
    col = f"has_{interval}"     # interval is one of INTERVAL_SECONDS, so the name is safe
    conn.execute(
        f"INSERT INTO ohlcv_data_available (instrument_id, data_source_id, {col}) "
        f"SELECT %s, data_source_id, true FROM data_source WHERE short_name = %s "
        f"ON CONFLICT (instrument_id, data_source_id) DO UPDATE SET {col} = true",
        (instrument_id, short_name))
    conn.commit()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_day(s: str) -> date:
    return date.fromisoformat(s + "-01" if len(s) == 7 else s)


def _targets(conn, coins: str | None, source: str) -> list[tuple[str, str]]:
    """Mapped (instrument_id, symbol) pairs for a source, minus ids missing in `instruments`."""
    pairs = _select(load_symbol_map(), coins, source)
    known = known_instruments(conn, (i for i, _ in pairs))
    for instrument_id, _ in pairs:
        if instrument_id not in known:
            print(f"skip {instrument_id}: not in instruments table", file=sys.stderr)
    return [(i, s) for i, s in pairs if i in known]


def _load(conn, instrument_id: str, interval: str, source: str, candles: Iterable[Candle]) -> None:
    n, skipped = upsert(conn, instrument_id, interval, source, candles)
    note = f" ({skipped} failed sanity check)" if skipped else ""
    print(f"{source:<12} {instrument_id:<24} {interval:<3} +{n} rows{note}", flush=True)


def cmd_init_views(args: argparse.Namespace) -> None:
    with connect() as conn:
        conn.execute(VIEWS_SQL.read_text())
    print("views ok")


def cmd_binance(args: argparse.Namespace) -> None:
    start, end = _parse_day(args.start), _parse_day(args.end) if args.end else date.today()
    session = requests.Session()
    with connect() as conn:
        for instrument_id, symbol in _targets(conn, args.coins, "binance"):
            _load(conn, instrument_id, args.interval, "binance",
                  fetch_binance(symbol, args.interval, start, end, session))


def cmd_kraken(args: argparse.Namespace) -> None:
    wanted = set(args.intervals.split(","))
    with zipfile.ZipFile(args.zip) as zf, connect() as conn:
        for instrument_id, pair in _targets(conn, args.coins, "kraken"):
            for interval, member in sorted(kraken_members(zf, pair).items()):
                if interval in wanted:
                    _load(conn, instrument_id, interval, "kraken", parse_kraken_csv(zf.read(member).decode()))


def cmd_okx(args: argparse.Namespace) -> None:
    start = datetime.combine(_parse_day(args.start), datetime.min.time(), timezone.utc)
    end = datetime.now(timezone.utc)
    session = requests.Session()
    with connect() as conn:
        for instrument_id, inst in _targets(conn, args.coins, "okx"):
            _load(conn, instrument_id, args.interval, "okx", fetch_okx(inst, args.interval, start, end, session))


def cmd_hyperliquid(args: argparse.Namespace) -> None:
    end = datetime.now(timezone.utc)
    start = end - timedelta(seconds=INTERVAL_SECONDS[args.interval] * 5000)
    session = requests.Session()
    with connect() as conn:
        for instrument_id, hl in _targets(conn, args.coins, "hyperliquid"):
            _load(conn, instrument_id, args.interval, "hyperliquid",
                  fetch_hyperliquid(hl, args.interval, start, end, session))


def cmd_update(args: argparse.Namespace) -> None:
    """Daily increment: the last N days from every source each instrument is mapped to.
    Sources run in priority order, so a later one only fills what an earlier one lacks."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=args.days)
    session = requests.Session()
    with connect() as conn:
        for interval in args.intervals.split(","):
            for instrument_id, sym in _targets(conn, args.coins, "binance"):
                _load(conn, instrument_id, interval, "binance",
                      fetch_binance(sym, interval, start.date(), end.date(), session))
            for instrument_id, sym in _targets(conn, args.coins, "okx"):
                _load(conn, instrument_id, interval, "okx", fetch_okx(sym, interval, start, end, session))
            for instrument_id, sym in _targets(conn, args.coins, "hyperliquid"):
                _load(conn, instrument_id, interval, "hyperliquid",
                      fetch_hyperliquid(sym, interval, start, end, session))


def cmd_coverage(args: argparse.Namespace) -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM backfill_coverage ORDER BY instrument_id, interval, source")
        writer = csv.writer(sys.stdout)
        writer.writerow([d.name for d in cur.description])
        writer.writerows(cur.fetchall())


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="backfill", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    coins_help = "comma-separated instrument_ids from backfill_symbols.csv (default: all)"
    intervals = list(INTERVAL_SECONDS)

    sub.add_parser("init-views", help="create backfill_coverage / backfill_gaps views").set_defaults(
        func=cmd_init_views)

    b = sub.add_parser("binance", help="Binance Public Data spot ZIPs")
    b.add_argument("--coins", help=coins_help)
    b.add_argument("--interval", default="1h", choices=intervals)
    b.add_argument("--start", default="2017-08", help="YYYY-MM or YYYY-MM-DD")
    b.add_argument("--end", help="YYYY-MM-DD (default: today)")
    b.set_defaults(func=cmd_binance)

    k = sub.add_parser("kraken", help="Kraken OHLCVT dump ZIP")
    k.add_argument("--zip", required=True, type=Path)
    k.add_argument("--coins", help=coins_help)
    k.add_argument("--intervals", default="1m,5m,1h,1d")
    k.set_defaults(func=cmd_kraken)

    o = sub.add_parser("okx", help="OKX history-candles")
    o.add_argument("--coins", help=coins_help)
    o.add_argument("--interval", default="1h", choices=intervals)
    o.add_argument("--start", default="2018-01-01")
    o.set_defaults(func=cmd_okx)

    h = sub.add_parser("hyperliquid", help="Hyperliquid candleSnapshot (latest 5000 candles)")
    h.add_argument("--coins", help=coins_help)
    h.add_argument("--interval", default="1h", choices=intervals)
    h.set_defaults(func=cmd_hyperliquid)

    u = sub.add_parser("update", help="daily increment for all mapped instruments")
    u.add_argument("--coins", help=coins_help)
    u.add_argument("--days", type=int, default=3)
    u.add_argument("--intervals", default="1h,1d")
    u.set_defaults(func=cmd_update)

    sub.add_parser("coverage", help="depth and fill ratio per series as CSV").set_defaults(func=cmd_coverage)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
