"""
perf_data: compute price-performance statistics from OHLCV candles.

Provides:
  fetch_5y_candles(hl_symbol)                       -> list of daily candle dicts
  compute_perf_rows(candles_5y)                     -> list of period stat dicts
  fetch_4h_candles(hl_symbol, days=90)              -> list of 4H candle dicts
  draw_perf_chart(hl_symbol, perf_rows, candles_4h) -> Path to PNG

Candle dict keys:  date, open, high, low, close, volume (float|None, USD)

Period stat dict keys: label, high, low, vwap, volume_usd (all float|None)
"""
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import requests

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from draw_chart import K_SCALE_SET, PNG_DIR, resolve_source_key  # noqa: E402

CACHE_DIR = ROOT / "cache" / "ohlcv"

CG_MARKET_CHART_URL = "https://api.coingecko.com/api/v3/coins/{id}/market_chart"

# ---------------------------------------------------------------------------
# 5-year candle fetch
# ---------------------------------------------------------------------------

def _5y_cache_path(source_key: str) -> Path:
    safe = source_key.replace("/", "_").replace(":", "_")
    return CACHE_DIR / f"{safe}_5y_{date.today()}.json"


def _load_5y_cache(source_key: str) -> list[dict] | None:
    path = _5y_cache_path(source_key)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text())
        for c in raw:
            c["date"] = datetime.fromisoformat(c["date"])
        return raw
    except Exception:  # noqa: BLE001
        return None


def _save_5y_cache(source_key: str, candles: list[dict]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _5y_cache_path(source_key)
    serialisable = [{**c, "date": c["date"].isoformat()} for c in candles]
    path.write_text(json.dumps(serialisable))


def _fetch_5y_yf(yf_ticker: str) -> list[dict]:
    """Fetch 5 years of daily OHLCV from Yahoo Finance. Volume returned in USD."""
    import yfinance as yf

    hist = yf.Ticker(yf_ticker).history(period="5y", interval="1d", auto_adjust=True)
    if hist.empty:
        raise ValueError(f"No 5Y data from Yahoo Finance for '{yf_ticker}'")

    candles = []
    for ts, row in hist.iterrows():
        dt = ts.to_pydatetime()  # type: ignore[union-attr]
        vol_usd = float(row.get("Volume") or 0)
        candles.append({
            "date":       dt,
            "open":       float(row["Open"]),
            "high":       float(row["High"]),
            "low":        float(row["Low"]),
            "close":      float(row["Close"]),
            # yfinance reports Volume in USD for -USD crypto pairs (the quote currency)
            "volume":     vol_usd if vol_usd > 0 else None,
        })
    candles.sort(key=lambda c: c["date"])
    return candles


def _fetch_5y_cg(cg_id: str) -> list[dict]:
    """
    Fetch up to 365 days of daily data from CoinGecko /market_chart (free-tier
    maximum). Longer history requires a paid key; periods beyond the available
    range are suppressed in compute_perf_rows.
    H/L/O/C are all set to the daily close price (no intraday H/L from this
    endpoint), but volume data IS included.
    """
    resp = requests.get(
        CG_MARKET_CHART_URL.format(id=cg_id),
        params={"vs_currency": "usd", "days": "365"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    prices  = data.get("prices", [])
    volumes = {v[0]: v[1] for v in data.get("total_volumes", [])}

    candles = []
    for ts_ms, price in prices:
        vol = volumes.get(ts_ms)
        candles.append({
            "date":   datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc),
            "open":   price,
            "high":   price,
            "low":    price,
            "close":  price,
            "volume": vol if vol and vol > 0 else None,
        })
    candles.sort(key=lambda c: c["date"])
    return candles


def fetch_5y_candles(hl_symbol: str) -> list[dict]:
    """
    Fetch ~5 years of daily candles for a Hyperliquid symbol.
    Uses the same source routing as draw_chart.py.
    Cached to disk for the current day.
    """
    source_key, multiplier = resolve_source_key(hl_symbol)

    cached = _load_5y_cache(source_key)
    if cached is not None:
        return cached

    if source_key.startswith("cg:"):
        cg_id = source_key[3:]
        print(f"[perf_data] fetching 5Y from CoinGecko: {cg_id}")
        candles = _fetch_5y_cg(cg_id)
    else:
        print(f"[perf_data] fetching 5Y from Yahoo Finance: {source_key}")
        candles = _fetch_5y_yf(source_key)

    if multiplier != 1.0:
        for c in candles:
            for key in ("open", "high", "low", "close"):
                c[key] *= multiplier
            # volume is already in USD (quote currency from YF / CoinGecko) — do not scale

    _save_5y_cache(source_key, candles)
    return candles


# ---------------------------------------------------------------------------
# Performance stats computation
# ---------------------------------------------------------------------------

PERIODS: list[tuple[str, int]] = [
    ("1D",   1),
    ("7D",   7),
    ("30D",  30),
    ("1Y",   365),
    ("5Y",   5 * 365),
]


def _vwap(candles: list[dict]) -> float | None:
    """Volume-weighted average price. Returns None if no volume data available."""
    numerator   = 0.0
    denominator = 0.0
    has_volume  = False
    for c in candles:
        v = c.get("volume")
        if v and v > 0:
            has_volume = True
            typical = (c["high"] + c["low"] + c["close"]) / 3
            numerator   += typical * v
            denominator += v
    if not has_volume or denominator == 0:
        return None
    return numerator / denominator


def compute_perf_rows(candles_5y: list[dict]) -> list[dict]:
    """
    Slice candles_5y into the standard period windows and compute stats.
    Periods that extend beyond the oldest available candle are suppressed (None).
    Returns a list of dicts: {label, high, low, vwap, volume_usd}.
    """
    now = datetime.now(timezone.utc)
    rows = []

    if not candles_5y:
        return [{"label": lbl, "high": None, "low": None, "vwap": None, "volume_usd": None}
                for lbl, _ in PERIODS]

    oldest = candles_5y[0]["date"]
    if oldest.tzinfo is None:
        oldest = oldest.replace(tzinfo=timezone.utc)

    for label, days in PERIODS:
        cutoff = now - timedelta(days=days)

        # Suppress periods the data doesn't cover (allow 7-day grace for rounding)
        if oldest > cutoff + timedelta(days=7):
            rows.append({"label": label, "high": None, "low": None, "vwap": None, "volume_usd": None})
            continue

        period_candles = []
        for c in candles_5y:
            dt = c["date"]
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt >= cutoff:
                period_candles.append(c)

        if not period_candles:
            rows.append({"label": label, "high": None, "low": None, "vwap": None, "volume_usd": None})
            continue

        high = max(c["high"] for c in period_candles)
        low  = min(c["low"]  for c in period_candles)
        vwap = _vwap(period_candles)

        raw_vols   = [c.get("volume") for c in period_candles]
        volume_usd = sum(v for v in raw_vols if v is not None) or None

        rows.append({
            "label":      label,
            "high":       high,
            "low":        low,
            "vwap":       vwap,
            "volume_usd": volume_usd,
        })

    return rows


# ---------------------------------------------------------------------------
# 4-hourly candle fetch
# ---------------------------------------------------------------------------

def _candle_cache_path(source_key: str, resolution: str) -> Path:
    safe = source_key.replace("/", "_").replace(":", "_")
    return CACHE_DIR / f"{safe}_{resolution}_{date.today()}.json"


# Keep legacy 4h names as thin wrappers so draw_perf_chart callers still work
def _4h_cache_path(source_key: str) -> Path:
    return _candle_cache_path(source_key, "4h")


def _load_candle_cache(source_key: str, resolution: str) -> list[dict] | None:
    path = _candle_cache_path(source_key, resolution)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text())
        for c in raw:
            c["date"] = datetime.fromisoformat(c["date"])
        return raw
    except Exception:  # noqa: BLE001
        return None


def _load_4h_cache(source_key: str) -> list[dict] | None:
    return _load_candle_cache(source_key, "4h")


def _save_candle_cache(source_key: str, resolution: str, candles: list[dict]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _candle_cache_path(source_key, resolution)
    serialisable = [{**c, "date": c["date"].isoformat()} for c in candles]
    path.write_text(json.dumps(serialisable))


def _save_4h_cache(source_key: str, candles: list[dict]) -> None:
    _save_candle_cache(source_key, "4h", candles)


def _resample_1h_to_4h(hourly: list[dict]) -> list[dict]:
    """
    Aggregate hourly candles into 4H blocks.
    Each block starts at hours 0, 4, 8, 12, 16, 20 UTC.
    """
    from collections import defaultdict

    buckets: dict[tuple, list[dict]] = defaultdict(list)
    for c in hourly:
        dt = c["date"]
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        # Floor to the nearest 4-hour boundary
        h4 = (dt.hour // 4) * 4
        key = (dt.year, dt.month, dt.day, h4)
        buckets[key].append(c)

    result = []
    for (yr, mo, day, h4), group in sorted(buckets.items()):
        group.sort(key=lambda c: c["date"])
        vol_vals = [c.get("volume") for c in group if c.get("volume")]
        result.append({
            "date":   datetime(yr, mo, day, h4, tzinfo=timezone.utc),
            "open":   group[0]["open"],
            "high":   max(c["high"]  for c in group),
            "low":    min(c["low"]   for c in group),
            "close":  group[-1]["close"],
            "volume": sum(vol_vals) if vol_vals else None,
        })
    return result


def _fetch_hourly_yf(source_key: str, multiplier: float) -> list[dict]:
    """Fetch 90 days of 1H candles from Yahoo Finance (raw, not resampled)."""
    import yfinance as yf

    hist = yf.Ticker(source_key).history(period="3mo", interval="1h", auto_adjust=True)
    if hist.empty:
        raise ValueError(f"No 1H data from Yahoo Finance for '{source_key}'")

    hourly = []
    for ts, row in hist.iterrows():
        dt = ts.to_pydatetime()  # type: ignore[union-attr]
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        vol_usd = float(row.get("Volume") or 0)
        hourly.append({
            "date":   dt,
            "open":   float(row["Open"])  * multiplier,
            "high":   float(row["High"])  * multiplier,
            "low":    float(row["Low"])   * multiplier,
            "close":  float(row["Close"]) * multiplier,
            "volume": vol_usd if vol_usd > 0 else None,
        })
    hourly.sort(key=lambda c: c["date"])
    return hourly


def _fetch_4h_yf(source_key: str, multiplier: float) -> list[dict]:
    """Fetch 90 days of hourly data from Yahoo Finance, resampled to 4H."""
    return _resample_1h_to_4h(_fetch_hourly_yf(source_key, multiplier))


def _fetch_hourly_cg(cg_id: str, multiplier: float) -> list[dict]:
    """
    Fetch 90 days of hourly data from CoinGecko (raw, not resampled).
    CoinGecko free-tier returns hourly data for days <= 90.
    H/L/O are all set to close (no intraday range available from this endpoint).
    """
    resp = requests.get(
        CG_MARKET_CHART_URL.format(id=cg_id),
        params={"vs_currency": "usd", "days": "90"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    prices  = data.get("prices", [])
    volumes = {v[0]: v[1] for v in data.get("total_volumes", [])}

    hourly = []
    for ts_ms, price in prices:
        scaled = price * multiplier
        vol = volumes.get(ts_ms)
        hourly.append({
            "date":   datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc),
            "open":   scaled,
            "high":   scaled,
            "low":    scaled,
            "close":  scaled,
            "volume": vol if vol and vol > 0 else None,
        })
    hourly.sort(key=lambda c: c["date"])
    return hourly


def _fetch_4h_cg(cg_id: str, multiplier: float) -> list[dict]:
    """Fetch 90 days of hourly data from CoinGecko, resampled to 4H."""
    return _resample_1h_to_4h(_fetch_hourly_cg(cg_id, multiplier))


def fetch_4h_candles(hl_symbol: str, resolution: str = "4h") -> list[dict]:
    """
    Fetch ~90 days of candles for a Hyperliquid symbol.

    resolution: "4h" (default) or "1h".
    YF symbols return true OHLCV; CG symbols return close-only data.
    Cached to disk per resolution per day.
    """
    source_key, multiplier = resolve_source_key(hl_symbol)

    cached = _load_candle_cache(source_key, resolution)
    if cached is not None:
        return cached

    if source_key.startswith("cg:"):
        cg_id = source_key[3:]
        print(f"[perf_data] fetching {resolution.upper()} from CoinGecko: {cg_id}")
        hourly = _fetch_hourly_cg(cg_id, multiplier)
    else:
        print(f"[perf_data] fetching {resolution.upper()} from Yahoo Finance: {source_key}")
        hourly = _fetch_hourly_yf(source_key, multiplier)

    candles = hourly if resolution == "1h" else _resample_1h_to_4h(hourly)
    _save_candle_cache(source_key, resolution, candles)
    return candles


# ---------------------------------------------------------------------------
# Performance chart drawing
# ---------------------------------------------------------------------------

# Reference-line config: (period_label, high_color, low_color)
_REF_LINES = [
    ("1D",  "#4a9eff", "#4a9eff"),   # blue
    ("7D",  "#ff9f40", "#ff9f40"),   # orange
    ("30D", "#4caf50", "#4caf50"),   # green
]


def draw_perf_chart(
    hl_symbol: str,
    perf_rows: list[dict],
    candles_4h: list[dict],
) -> Path | None:
    """
    Draw a 90-day 4H price chart with H/L reference lines for 1D, 7D, 30D.
    Saves to PNG_DIR and returns the Path. Returns None if no candles.
    Skips regeneration if today's file already exists.
    """
    if not candles_4h:
        return None

    today_str = date.today().isoformat()
    filename  = f"{hl_symbol.upper()}USD_{today_str}_PERF90.png"
    out_path  = PNG_DIR / filename
    if out_path.exists():
        return out_path

    # Detect if this is a CG source (close-only) by checking equality of H/L/C
    c0 = candles_4h[0]
    is_line_only = (c0["high"] == c0["low"] == c0["close"])

    dates  = [c["date"] for c in candles_4h]
    closes = [c["close"] for c in candles_4h]
    highs  = [c["high"]  for c in candles_4h]
    lows   = [c["low"]   for c in candles_4h]

    # Look up perf_rows by label for quick access
    rows_by_label = {r["label"]: r for r in perf_rows}

    fig, ax = plt.subplots(figsize=(30, 10), dpi=100)

    if is_line_only:
        # CoinGecko source — plain close-price line
        ax.plot(dates, closes, color="#888888", linewidth=0.8, label="Price (close)")
    else:
        # Yahoo Finance source — OHLC bars (thin, coloured by direction)
        width_4h = timedelta(hours=3.6)  # slightly narrower than 4H for gap
        for c in candles_4h:
            color = "#26a69a" if c["close"] >= c["open"] else "#ef5350"
            # High-low wick
            ax.plot([c["date"], c["date"]], [c["low"], c["high"]],
                    color=color, linewidth=0.6, alpha=0.8)
            # Body (open-close rectangle as thin vline with linewidth proportional to width)
            body_lo = min(c["open"], c["close"])
            body_hi = max(c["open"], c["close"])
            ax.plot([c["date"], c["date"]], [body_lo, body_hi],
                    color=color, linewidth=2.5, alpha=0.9)

    # Reference lines: 1D, 7D, 30D high and low
    for label, hcolor, lcolor in _REF_LINES:
        row = rows_by_label.get(label)
        if not row:
            continue
        if row["high"] is not None:
            ax.axhline(
                y=row["high"], color=hcolor, linewidth=1.2,
                linestyle="--", alpha=0.85,
                label=f"{label} H  ${row['high']:,.4g}",
            )
        if row["low"] is not None:
            ax.axhline(
                y=row["low"], color=lcolor, linewidth=1.2,
                linestyle=":", alpha=0.85,
                label=f"{label} L  ${row['low']:,.4g}",
            )

    # Weekly vertical separators
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=0))
    ax.xaxis.set_minor_locator(mdates.DayLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right", fontsize=9)
    ax.grid(which="major", axis="x", linestyle="--", linewidth=0.5, alpha=0.4)
    ax.grid(which="major", axis="y", linestyle="--", linewidth=0.4, alpha=0.4)

    # Y-axis: pad by 2%
    y_min = min(lows)  * 0.98
    y_max = max(highs) * 1.02
    ax.set_ylim(y_min, y_max)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.6g"))

    ax.set_title(f"{hl_symbol} — 4H price, last 90 days", fontsize=14)
    ax.set_ylabel("Price (USD)", fontsize=11)
    ax.legend(loc="upper left", fontsize=10, ncol=2)

    PNG_DIR.mkdir(exist_ok=True)
    fig.savefig(out_path, dpi=100, bbox_inches="tight")
    plt.close(fig)
    print(f"[perf_data] saved: {out_path}")
    return out_path
