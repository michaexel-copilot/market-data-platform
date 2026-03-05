"""
perf_data: compute price-performance statistics from OHLCV candles.

Provides:
  fetch_5y_candles(hl_symbol)       -> list of daily candle dicts
  compute_perf_rows(candles_5y)     -> list of period stat dicts

Candle dict keys:  date, open, high, low, close, volume (float|None, USD)

Period stat dict keys: label, high, low, vwap, volume_usd (all float|None)
"""
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from draw_chart import K_SCALE_SET, resolve_source_key  # noqa: E402

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
        dt = ts.to_pydatetime()
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
