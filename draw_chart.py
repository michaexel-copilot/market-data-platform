import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import requests

import matplotlib
matplotlib.use("Agg")  # non-interactive backend for saving to file
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import yfinance as yf

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

PNG_DIR   = ROOT / "png"
CACHE_DIR = ROOT / "cache" / "ohlcv"

# Map Hyperliquid symbols to Yahoo Finance tickers.
# K-prefix tokens represent 1000 × the underlying coin — map to the underlying
# and apply a ×1000 price multiplier.
# Rebranded tokens are kept under their still-listed Yahoo Finance ticker.
YF_SYMBOL_MAP: dict[str, str] = {
    # K-prefix (kilo-unit) tokens → underlying Yahoo Finance ticker
    "KBONK":    "BONK-USD",
    "KDOGS":    "DOGS-USD",
    "KFLOKI":   "FLOKI-USD",
    "KLUNC":    "LUNC-USD",
    "KNEIRO":   "NEIRO-USD",
    "KPEPE":    "PEPE-USD",
    "KSHIB":    "SHIB-USD",
    # Rebranded tokens — use the ticker Yahoo Finance still lists
    "FTM":      "FTM-USD",      # Fantom (rebranded to Sonic / S)
    "MATIC":    "POL-USD",      # Polygon MATIC → POL
    "RNDR":     "RNDR-USD",     # Render (old ticker still on YF)
    "NEIROETH": "NEIRO-USD",    # Neiro on Ethereum
}

# Symbols whose HL price = Yahoo price × 1000
K_SCALE_SET: set[str] = {
    "KBONK", "KDOGS", "KFLOKI", "KLUNC", "KNEIRO", "KPEPE", "KSHIB",
}

# CoinGecko coin IDs for symbols not listed on Yahoo Finance.
# Source key format: "cg:{coin_id}" (e.g. "cg:hyperliquid").
CG_COIN_ID_MAP: dict[str, str] = {
    "CC":     "canton-network",          # Canton
    "HYPE":   "hyperliquid",             # Hyperliquid
    "SUI":    "sui",                     # Sui — YF "SUI-USD" is Salmonation (wrong coin)
    "WLFI":   "world-liberty-financial", # World Liberty Financial
    "MNT":    "mantle",                  # Mantle
    "TAO":    "bittensor",               # Bittensor
    "KPEPE":  "pepe",                    # KPEPE = 1000 × PEPE (scaled by K_SCALE_SET)
    "POL":    "polygon-ecosystem-token", # Polygon POL (rebranded from MATIC)
    "RNDR":   "render-token",            # Render
    "PUMP":   "pump-fun",                # Pump.fun
    "MORPHO": "morpho",                  # Morpho
    "STABLE": "stable-2",               # Stable
    "ZRO":    "layerzero",               # LayerZero
    "PENGU":  "pudgy-penguins",          # Pudgy Penguins
    "IMX":    "immutable-x",             # Immutable X
    "SPX":    "spx6900",                 # SPX6900
    "ZK":     "zksync",                  # zkSync
    "COMP":   "compound-governance-token", # Compound
    "VVV":    "venice-token",            # Venice Token
    "FTM":    "fantom",                  # Fantom
    "S":      "sonic-3",                 # Sonic (rebranded from FTM)
    "STG":    "stargate-finance",        # Stargate
    "UNI":    "uniswap",                 # Uniswap — YF "UNI-USD" is UNICORN Token (wrong coin)
    "ZORA":   "zora",                    # Zora
    "WCT":    "connect-token-wct",       # WalletConnect Token
}

CG_MARKET_CHART_URL = "https://api.coingecko.com/api/v3/coins/{id}/market_chart"


def get_data_source(hl_symbol: str) -> str:
    """Return the human-readable OHLCV data source for a given HL symbol."""
    key, _ = resolve_source_key(hl_symbol)
    return "CoinGecko" if key.startswith("cg:") else "Yahoo Finance"


def resolve_source_key(hl_symbol: str) -> tuple[str, float]:
    """
    Return (source_key, price_multiplier) for the given HL symbol.
    source_key is either a Yahoo Finance ticker (e.g. "SOL-USD") or
    a CoinGecko key prefixed with "cg:" (e.g. "cg:hyperliquid").
    """
    sym = hl_symbol.upper()
    multiplier = 1000.0 if sym in K_SCALE_SET else 1.0
    if sym in CG_COIN_ID_MAP:
        return f"cg:{CG_COIN_ID_MAP[sym]}", multiplier
    ticker = YF_SYMBOL_MAP.get(sym, f"{sym}-USD")
    return ticker, multiplier


# Keep old name as alias so existing callers don't break
def resolve_yf_ticker(hl_symbol: str) -> tuple[str, float]:
    return resolve_source_key(hl_symbol)


def _cache_path(yf_ticker: str) -> Path:
    """Return the cache file path for today's OHLCV data for the given ticker."""
    safe = yf_ticker.replace("/", "_")
    return CACHE_DIR / f"{safe}_{date.today()}.json"


def _load_cache(yf_ticker: str) -> list[dict] | None:
    path = _cache_path(yf_ticker)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text())
        # Restore datetime objects from ISO strings
        for c in raw:
            c["date"] = datetime.fromisoformat(c["date"])
        return raw
    except Exception:  # noqa: BLE001
        return None


def _save_cache(yf_ticker: str, candles: list[dict]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(yf_ticker)
    serialisable = [
        {**c, "date": c["date"].isoformat()}
        for c in candles
    ]
    path.write_text(json.dumps(serialisable))


def _fetch_from_yf(yf_ticker: str) -> list[dict]:
    """Fetch daily OHLCV candles from Yahoo Finance, from 2020-01-01 to today."""
    import math
    hist = yf.Ticker(yf_ticker).history(start="2020-01-01", interval="1d", auto_adjust=True)
    if hist.empty:
        raise ValueError(f"No data returned from Yahoo Finance for ticker '{yf_ticker}'")

    candles = []
    for ts, row in hist.iterrows():
        o, h, l, c = float(row["Open"]), float(row["High"]), float(row["Low"]), float(row["Close"])
        # Skip rows with NaN or zero prices (data quality gaps from early history)
        if any(math.isnan(v) or v == 0.0 for v in (o, h, l, c)):
            continue
        candles.append({
            "date":  ts.to_pydatetime(),
            "open":  o,
            "high":  h,
            "low":   l,
            "close": c,
        })
    if not candles:
        raise ValueError(f"No valid price data from Yahoo Finance for ticker '{yf_ticker}'")
    candles.sort(key=lambda c: c["date"])
    return candles


def _fetch_from_coingecko(cg_id: str) -> list[dict]:
    """Fetch daily close candles from CoinGecko market_chart (free tier).

    Uses /market_chart?days=365 which auto-returns one data point per day for
    ranges > 90 days, unlike /ohlc which silently degrades to 4-day candles.
    Returns close-only candles (open/high/low set equal to close).
    Retries once on 429 rate-limit responses after a short backoff.
    """
    import time as _time
    url = CG_MARKET_CHART_URL.format(id=cg_id)
    params = {"vs_currency": "usd", "days": "365"}
    for attempt in range(2):
        resp = requests.get(url, params=params, timeout=20)
        if resp.status_code == 429 and attempt == 0:
            _time.sleep(12)  # CG free tier: ~5 req/min sustained; wait and retry
            continue
        resp.raise_for_status()
        break
    data = resp.json()
    prices = data.get("prices", [])
    if not prices:
        raise ValueError(f"No market_chart data from CoinGecko for '{cg_id}'")

    candles = []
    for ts_ms, price in prices:
        # market_chart returns close prices only — set OHLC all to close
        candles.append({
            "date":  datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc),
            "open":  price,
            "high":  price,
            "low":   price,
            "close": price,
        })
    candles.sort(key=lambda c: c["date"])
    return candles


def fetch_ohlcv(source_key: str) -> list[dict]:
    """
    Fetch daily OHLCV candles.  Yahoo Finance-backed tokens return data from
    2020-01-01 to today; CoinGecko-backed tokens return the last 365 days
    (free-tier maximum for daily granularity).  source_key is either a Yahoo Finance
    ticker (e.g. "SOL-USD") or a CoinGecko key prefixed with "cg:"
    (e.g. "cg:hyperliquid").  Results are cached to disk for the current day.
    Returns a list of dicts sorted by date with keys: date, open, high, low, close.
    """
    cached = _load_cache(source_key)
    if cached is not None:
        print(f"  (OHLCV loaded from cache for {source_key})")
        return cached

    if source_key.startswith("cg:"):
        cg_id = source_key[3:]
        print(f"  (fetching from CoinGecko: {cg_id})")
        candles = _fetch_from_coingecko(cg_id)
    else:
        candles = _fetch_from_yf(source_key)

    _save_cache(source_key, candles)
    return candles


def sma(values: list[float], period: int) -> list[float | None]:
    """Simple moving average. Returns None for the first (period-1) entries."""
    result: list[float | None] = [None] * (period - 1)
    for i in range(period - 1, len(values)):
        window = values[i - period + 1 : i + 1]
        result.append(sum(window) / period)
    return result


def prepare_chart_data(
    hl_symbol: str,
    sma_period: int = 7,
    sma_high_period: int = 7,
) -> tuple[list[dict], list, list, list]:
    """
    Fetch & scale candles, compute SMA arrays.
    Returns (candles, sma_close, sma_high, sma_low).
    sma_period controls SMA Low and SMA Close; sma_high_period controls SMA High.
    Each call returns a fresh list (OHLCV cache is re-read every call).
    """
    source_key, multiplier = resolve_source_key(hl_symbol)
    print(f"Fetching OHLCV for {source_key} (\u00d7{multiplier:.0f}) \u2026")
    candles = fetch_ohlcv(source_key)
    if not candles:
        raise ValueError(f"No OHLCV data returned for {hl_symbol}")
    print(f"  Got {len(candles)} daily candles.")
    if multiplier != 1.0:
        for c in candles:
            c["open"]  *= multiplier
            c["high"]  *= multiplier
            c["low"]   *= multiplier
            c["close"] *= multiplier
    closes = [c["close"] for c in candles]
    highs  = [c["high"]  for c in candles]
    lows   = [c["low"]   for c in candles]
    return candles, sma(closes, sma_period), sma(highs, sma_high_period), sma(lows, sma_period)


def backtest_strategy(
    candles: list[dict],
    sma_low: list[float | None],
    position_size_usd: float = 100.0,
) -> list[dict]:
    """
    Short strategy backtest (daily close prices).
    Entry  : close crosses below sma_low (was >= yesterday, now <).
    Stop   : close >= entry x 1.10  -> exit at stop_loss price  (loss).
    Profit : close >= sma_low[i]    -> exit at sma_low[i]       (profit when sma fell below entry).
    No new entry while a position is open.  Returns all trades (incl. open).

    Each closed trade includes:
      max_adverse_pnl    — worst unrealised P&L seen (most negative for profit trades).
      max_favourable_pnl — best  unrealised P&L seen (most positive for loss trades).
    Both are None for open trades. Computed from daily close prices.
    """
    trades: list[dict] = []
    in_position = False
    entry_trade: dict | None = None
    _running_max_upnl: float = 0.0   # tracks maximum favourable unrealised P&L
    _running_min_upnl: float = 0.0   # tracks maximum adverse unrealised P&L

    for i in range(1, len(candles)):
        sl_prev = sma_low[i - 1]
        sl_curr = sma_low[i]
        if sl_prev is None or sl_curr is None:
            continue
        c_curr = candles[i]
        c_prev = candles[i - 1]

        if not in_position:
            if c_prev["close"] >= sl_prev and c_curr["close"] < sl_curr:
                entry_price = c_curr["close"]
                entry_trade = {
                    "entry_date":  c_curr["date"],
                    "entry_price": entry_price,
                    "stop_loss":   entry_price * 1.10,
                    "entry_idx":   i,
                    "exit_date":   None,
                    "exit_price":  None,
                    "exit_idx":    None,
                    "pnl":         None,
                    "is_open":     True,
                }
                _running_max_upnl = -float("inf")
                _running_min_upnl = float("inf")
                in_position = True
        else:
            assert entry_trade is not None
            upnl = (
                (entry_trade["entry_price"] - c_curr["close"])
                / entry_trade["entry_price"]
                * position_size_usd
            )
            if upnl > _running_max_upnl:
                _running_max_upnl = upnl
            if upnl < _running_min_upnl:
                _running_min_upnl = upnl
            if c_curr["close"] >= entry_trade["stop_loss"]:
                exit_price = entry_trade["stop_loss"]
                entry_trade.update({
                    "exit_date":  c_curr["date"],
                    "exit_price": exit_price,
                    "exit_idx":   i,
                    "pnl": (entry_trade["entry_price"] - exit_price)
                           / entry_trade["entry_price"] * position_size_usd,
                    "is_open": False,
                    "max_adverse_pnl":    _running_min_upnl,
                    "max_favourable_pnl": _running_max_upnl,
                })
                trades.append(entry_trade)
                entry_trade = None
                in_position = False
            elif c_curr["close"] >= sl_curr and sl_curr < entry_trade["entry_price"]:
                exit_price = sl_curr
                entry_trade.update({
                    "exit_date":  c_curr["date"],
                    "exit_price": exit_price,
                    "exit_idx":   i,
                    "pnl": (entry_trade["entry_price"] - exit_price)
                           / entry_trade["entry_price"] * position_size_usd,
                    "is_open": False,
                    "max_adverse_pnl":    _running_min_upnl,
                    "max_favourable_pnl": _running_max_upnl,
                })
                trades.append(entry_trade)
                entry_trade = None
                in_position = False

    if in_position and entry_trade:
        entry_trade["max_adverse_pnl"] = None
        entry_trade["max_favourable_pnl"] = None
        trades.append(entry_trade)

    return trades


def draw_chart(
    hl_symbol: str,
    sma_period: int = 7,
    highlight: dict | None = None,
    sma_high_period: int = 7,
) -> Path:
    candles, sma_close, sma_high, sma_low = prepare_chart_data(hl_symbol, sma_period, sma_high_period)

    dates  = [c["date"] for c in candles]
    closes = [c["close"] for c in candles]
    highs  = [c["high"]  for c in candles]
    lows   = [c["low"]   for c in candles]

    # --- Build chart -----------------------------------------------------------
    fig, ax = plt.subplots(figsize=(30, 20), dpi=100)

    # Main line: daily close, black, 1 px
    ax.plot(dates, closes, color="black", linewidth=1, label="Close")

    # SMA lines — only plot from the first non-None index
    def plot_sma(ax, dates, sma_values, color, label):
        pairs = [(d, v) for d, v in zip(dates, sma_values) if v is not None]
        if pairs:
            d_, v_ = zip(*pairs)
            ax.plot(d_, v_, color=color, linewidth=1, label=label)

    plot_sma(ax, dates, sma_high,  "#99ccff", f"SMA{sma_high_period} High")
    plot_sma(ax, dates, sma_low,   "#327819", f"SMA{sma_period} Low")
    plot_sma(ax, dates, sma_close, "#bd44bd", f"SMA{sma_period} Close")

    # Crosshairs for highlighted trade
    if highlight:
        ei = highlight.get("entry_idx")
        xi = highlight.get("exit_idx")
        if ei is not None and ei < len(candles):
            ax.axvline(x=dates[ei], color="#0055cc", linewidth=1.5, linestyle="--", alpha=0.9, label="Entry")
            ax.axhline(y=closes[ei], color="#0055cc", linewidth=1.5, linestyle="--", alpha=0.9)
        if xi is not None and xi < len(candles):
            xprice = highlight.get("exit_price") or closes[xi]
            ax.axvline(x=dates[xi], color="#cc5500", linewidth=1.5, linestyle="--", alpha=0.9, label="Exit")
            ax.axhline(y=xprice,    color="#cc5500", linewidth=1.5, linestyle="--", alpha=0.9)

    # X-axis: tick at the 1st of each month, label as "Mon YYYY"
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonthday=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")

    # Y-axis: tight to [min(low), max(high)] across all candles, no padding
    y_min = min(lows)
    y_max = max(highs)
    ax.set_ylim(y_min, y_max)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.6g"))

    # Labels, title, legend
    ax.set_title(f"{hl_symbol} — Daily OHLC (last 12 months)", fontsize=18)
    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel("Price (USD)", fontsize=12)
    ax.legend(loc="upper left", fontsize=11)
    ax.grid(True, linestyle="--", linewidth=0.4, alpha=0.5)

    # --- Save ------------------------------------------------------------------
    PNG_DIR.mkdir(exist_ok=True)
    today_str = date.today().isoformat()
    if highlight and highlight.get("entry_idx") is not None:
        entry_date_str = candles[highlight["entry_idx"]]["date"].strftime("%Y-%m-%d")
        filename = f"{hl_symbol.upper()}USD_{today_str}_SMAl{sma_period}_SMAh{sma_high_period}_hi_{entry_date_str}.png"
    else:
        now = datetime.now()
        filename = f"{hl_symbol.upper()}USD_{today_str}_SMAl{sma_period}_SMAh{sma_high_period}_{now.strftime('%H-%M-%S')}.png"
    out_path = PNG_DIR / filename
    fig.savefig(out_path, dpi=100, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_path}")
    return out_path


def main():
    parser = argparse.ArgumentParser(
        description="Draw a 12-month daily OHLC price chart with SMA-44 overlays."
    )
    parser.add_argument(
        "symbol",
        metavar="SYMBOL",
        help="Hyperliquid base symbol to chart, e.g. SOL, BTC, KSHIB",
    )
    args = parser.parse_args()
    draw_chart(args.symbol)
