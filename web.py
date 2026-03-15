"""
web: FastAPI + HTMX two-pane chart viewer.

Start with:   uv run serve
Then open:    http://localhost:8000
"""
import csv
import sys
from datetime import date
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from cmc_info import fetch_cmc_info, fetch_cmc_info_batch, fetch_market_caps  # noqa: E402
from cg_market import fetch_cg_market  # noqa: E402
from draw_chart import backtest_short_strategy, backtest_long_strategy, draw_chart, get_data_source, prepare_chart_data, fetch_ohlcv, resolve_source_key, sma as _sma, K_SCALE_SET  # noqa: E402
from lists_db import add_item, get_lists, remove_item  # noqa: E402
from perf_data import compute_perf_rows, fetch_4h_candles, fetch_5y_candles  # noqa: E402
from hl_order import get_pair_meta, place_order as hl_place_order  # noqa: E402

HL_PAIRS_CSV = Path("/mnt/ds420/data/hyperliquid/hl-main-pairs.csv")
assert HL_PAIRS_CSV.exists(), f"Asset list not found: {HL_PAIRS_CSV}"
HL_TESTNET_PAIRS_CSV = ROOT / "hl_testnet_pairs_with_mcap.csv"

PNG_DIR   = ROOT / "png"
TEMPLATES = Jinja2Templates(directory=str(ROOT / "templates"))


def _fmt_usd(v: float | None) -> str:
    """Compact USD formatter: $1.23B / $456.78M / $1.23K / $0.99"""
    if v is None:
        return "\u2014"
    if v >= 1e9:
        return f"${v / 1e9:.2f}B"
    if v >= 1e6:
        return f"${v / 1e6:.2f}M"
    if v >= 1e3:
        return f"${v / 1e3:.2f}K"
    return f"${v:.2f}"


TEMPLATES.env.filters["fmt_usd"] = _fmt_usd


# ---------------------------------------------------------------------------
# EUR/USD exchange rate (cached per day)
# ---------------------------------------------------------------------------

import json as _json  # noqa: E402 (needed here for module-level cache)
import requests as _requests  # noqa: E402

_EUR_RATE_CACHE: dict = {}


def fetch_eur_usd_rate() -> float:
    """
    Return today's USD→EUR rate (i.e. 1 USD = ? EUR).
    Source: open.er-api.com (free, no key required).
    Falls back to 0.92 if unavailable.
    """
    today = date.today().isoformat()
    if _EUR_RATE_CACHE.get("date") == today:
        return _EUR_RATE_CACHE["rate"]

    cache_path = ROOT / "cache" / f"eur_usd_{today}.json"
    if cache_path.exists():
        try:
            rate = float(_json.loads(cache_path.read_text())["rate"])
            _EUR_RATE_CACHE.update(date=today, rate=rate)
            return rate
        except Exception:  # noqa: BLE001
            pass

    try:
        resp = _requests.get(
            "https://open.er-api.com/v6/latest/USD",
            timeout=10,
        )
        resp.raise_for_status()
        rate = float(resp.json()["rates"]["EUR"])
    except Exception as exc:  # noqa: BLE001
        print(f"[web] EUR/USD fetch failed: {exc}; using fallback 0.92")
        rate = 0.92

    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(_json.dumps({"rate": rate}))
    except Exception:  # noqa: BLE001
        pass

    _EUR_RATE_CACHE.update(date=today, rate=rate)
    return rate


app = FastAPI(title="Short Opportunities")
app.mount("/png", StaticFiles(directory=str(PNG_DIR)), name="png")

# ---------------------------------------------------------------------------
# Asset list — loaded once at startup
# ---------------------------------------------------------------------------

def _load_assets() -> list[dict[str, Any]]:
    import json as _json

    cache_path = ROOT / "cache" / f"assets_{date.today()}.json"
    if cache_path.exists():
        print("[web] Loading asset list from cache…")
        return _json.loads(cache_path.read_text())

    with open(HL_PAIRS_CSV, newline="") as f:
        symbols = [row["base"] for row in csv.DictReader(f)]

    print(f"[web] Fetching market caps + CMC info for {len(symbols)} symbols…")
    mcaps = fetch_market_caps(symbols)       # {hl_sym: float | None}
    infos = fetch_cmc_info_batch(symbols)    # {hl_sym: info_dict}

    assets: list[dict[str, Any]] = []
    for sym in symbols:
        mcap = mcaps.get(sym)
        info = infos.get(sym) or {}
        dl   = info.get("date_launched")
        assets.append({
            "rank":           0,
            "symbol":         sym,
            "cmc_symbol":     sym,
            "market_cap_usd": mcap,
            "date_launched":  dl[:10] if dl else None,
        })

    assets.sort(key=lambda a: (a["market_cap_usd"] or 0.0), reverse=True)
    for i, a in enumerate(assets, 1):
        a["rank"] = i

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(_json.dumps(assets))
    print(f"[web] Loaded {len(assets)} assets.")
    return assets


def _load_testnet_assets() -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    with open(HL_TESTNET_PAIRS_CSV, newline="") as f:
        for row in csv.DictReader(f):
            mcap_str = row.get("market_cap_usd", "")
            mcap = float(mcap_str) if mcap_str else None
            assets.append({
                "rank":           0,
                "symbol":         row["base"].upper(),
                "cmc_symbol":     row.get("cmc_symbol") or row["base"].upper(),
                "market_cap_usd": mcap,
                "date_launched":  None,
            })
    assets.sort(key=lambda a: (a["market_cap_usd"] or 0.0), reverse=True)
    for i, a in enumerate(assets, 1):
        a["rank"] = i
    print(f"[web] Loaded {len(assets)} testnet assets.")
    return assets


MAINNET_ASSETS: list[dict[str, Any]] = _load_assets()
TESTNET_ASSETS: list[dict[str, Any]] = _load_testnet_assets()
ASSET_BY_SYMBOL: dict[str, dict[str, Any]] = {
    **{a["symbol"]: a for a in TESTNET_ASSETS},
    **{a["symbol"]: a for a in MAINNET_ASSETS},  # mainnet takes precedence
}

# ---------------------------------------------------------------------------
# Out-of-sample validation cache (keyed by (symbol_upper, sma_low, sma_high, sl_short, sl_long, pos_usd))
# ---------------------------------------------------------------------------
OOS_CACHE: dict[tuple, dict] = {}

_BEST_SMA_MIN = 3
_BEST_SMA_MAX = 50


def _find_best_sma(
    symbol: str,
    sl_short: float,
    sl_long: float,
    pos: float,
) -> tuple[int, int, list, int]:
    """Brute-force search over SMA LOW × SMA HIGH ∈ [3,50] using the first 80% of candles.
    Returns (sma_low, sma_high, full_scaled_candles, split_idx)."""
    sym_upper = symbol.upper()

    # Fetch OHLCV once (disk-cached per day) and scale prices.
    source_key, multiplier = resolve_source_key(sym_upper)
    candles = fetch_ohlcv(source_key)
    if multiplier != 1.0:
        candles = [
            {**c, "open": c["open"] * multiplier, "high": c["high"] * multiplier,
             "low": c["low"] * multiplier, "close": c["close"] * multiplier}
            for c in candles
        ]

    # Use only the first 80% of candles for the optimisation grid search.
    split_idx = int(len(candles) * 0.8)
    train_candles = candles[:split_idx]
    closes = [c["close"] for c in train_candles]
    highs  = [c["high"]  for c in train_candles]
    lows   = [c["low"]   for c in train_candles]

    best_score = float("-inf")
    best_pair = (_BEST_SMA_MIN, _BEST_SMA_MIN)

    # Pre-compute all SMA arrays for the search range (training slice only).
    sma_low_arrays:  dict[int, list] = {p: _sma(lows, p)   for p in range(_BEST_SMA_MIN, _BEST_SMA_MAX + 1)}
    sma_high_arrays: dict[int, list] = {p: _sma(highs, p)  for p in range(_BEST_SMA_MIN, _BEST_SMA_MAX + 1)}

    for sma_low in range(_BEST_SMA_MIN, _BEST_SMA_MAX + 1):
        sma_low_vals = sma_low_arrays[sma_low]
        short_trades = backtest_short_strategy(
            train_candles, sma_low_vals,
            position_size_usd=pos,
            stop_loss_pct=sl_short / 100.0,
        )
        for sma_high in range(_BEST_SMA_MIN, _BEST_SMA_MAX + 1):
            sma_high_vals = sma_high_arrays[sma_high]
            long_trades = backtest_long_strategy(
                train_candles, sma_high_vals,
                position_size_usd=pos,
                stop_loss_pct=sl_long / 100.0,
            )
            closed_pnl = sum(
                t["pnl"] for t in short_trades
                if not t["is_open"] and t["pnl"] is not None
            ) + sum(
                t["pnl"] for t in long_trades
                if not t["is_open"] and t["pnl"] is not None
            )
            n_closed = sum(
                1 for t in short_trades if not t["is_open"] and t["pnl"] is not None
            ) + sum(
                1 for t in long_trades if not t["is_open"] and t["pnl"] is not None
            )
            score = closed_pnl / n_closed if n_closed > 0 else float("-inf")
            if score > best_score:
                best_score = score
                best_pair = (sma_low, sma_high)

    return best_pair[0], best_pair[1], candles, split_idx


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------

def _today_prefix(symbol: str, sma_period: int, sma_high_period: int, sl_short: int = 10, sl_long: int = 10) -> str:
    """Return the filename prefix used for today's chart."""
    return f"{symbol.upper()}USD_{date.today()}_SMAl{sma_period}_SMAh{sma_high_period}_SLs{sl_short}_SLl{sl_long}"


def _find_existing_chart(symbol: str, sma_period: int, sma_high_period: int, sl_short: int = 10, sl_long: int = 10) -> str | None:
    """Return the filename (not path) of the newest non-highlighted chart for today, or None."""
    prefix = _today_prefix(symbol, sma_period, sma_high_period, sl_short, sl_long)
    PNG_DIR.mkdir(exist_ok=True)
    matches = sorted(
        [f for f in PNG_DIR.glob(f"{prefix}_*.png") if "_hs" not in f.name and "_hl" not in f.name],
        reverse=True,
    )
    return matches[0].name if matches else None


def _get_or_create_chart(symbol: str, sma_period: int, sma_high_period: int, sl_short: int = 10, sl_long: int = 10) -> str | None:
    """Return the filename for today's chart, generating it if needed."""
    existing = _find_existing_chart(symbol, sma_period, sma_high_period, sl_short, sl_long)
    if existing:
        return existing
    try:
        path = draw_chart(
            symbol,
            sma_period=sma_period,
            sma_high_period=sma_high_period,
            sl_short=sl_short / 100.0,
            sl_long=sl_long / 100.0,
        )
        return path.name
    except Exception as exc:  # noqa: BLE001
        print(f"[web] Could not generate chart for {symbol}: {exc}")
        return None


def _get_or_create_highlighted_chart(
    symbol: str,
    sma_period: int,
    sma_high_period: int,
    sl_short: int,
    sl_long: int,
    hl_short: dict | None = None,
    hl_long: dict | None = None,
) -> str | None:
    """Generate (or reuse today's) chart PNG with entry/exit crosshairs for short and/or long."""
    hs_idx = hl_short.get("entry_idx") if hl_short else None
    hl_idx = hl_long.get("entry_idx") if hl_long else None
    hs_str = f"hs{hs_idx}" if hs_idx is not None else "hs-"
    hl_str = f"hl{hl_idx}" if hl_idx is not None else "hl-"
    filename = f"{symbol.upper()}USD_{date.today()}_SMAl{sma_period}_SMAh{sma_high_period}_SLs{sl_short}_SLl{sl_long}_{hs_str}_{hl_str}.png"
    if (PNG_DIR / filename).exists():
        return filename
    try:
        path = draw_chart(
            symbol,
            sma_period=sma_period,
            sma_high_period=sma_high_period,
            hl_short=hl_short,
            hl_long=hl_long,
            sl_short=sl_short / 100.0,
            sl_long=sl_long / 100.0,
        )
        return path.name
    except Exception as exc:  # noqa: BLE001
        print(f"[web] Could not generate highlighted chart for {symbol}: {exc}")
        return None


# ---------------------------------------------------------------------------
# Lists API (favourites & ignored)
# ---------------------------------------------------------------------------

@app.get("/lists")
async def lists_get() -> JSONResponse:
    return JSONResponse(get_lists())


@app.post("/lists/fav/{symbol}")
async def lists_fav_add(symbol: str) -> JSONResponse:
    add_item(symbol, "fav")
    return JSONResponse({"ok": True})


@app.delete("/lists/fav/{symbol}")
async def lists_fav_remove(symbol: str) -> JSONResponse:
    remove_item(symbol, "fav")
    return JSONResponse({"ok": True})


@app.post("/lists/ignore/{symbol}")
async def lists_ignore_add(symbol: str) -> JSONResponse:
    add_item(symbol, "ignored")
    return JSONResponse({"ok": True})


@app.delete("/lists/ignore/{symbol}")
async def lists_ignore_remove(symbol: str) -> JSONResponse:
    remove_item(symbol, "ignored")
    return JSONResponse({"ok": True})


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(
        "index.html",
        {"request": request, "assets": TESTNET_ASSETS},
    )


@app.get("/assets-list", response_class=HTMLResponse)
async def assets_list(request: Request, network: str = "testnet") -> HTMLResponse:
    assets = TESTNET_ASSETS if network == "testnet" else MAINNET_ASSETS
    return TEMPLATES.TemplateResponse(
        "asset_list_partial.html",
        {"request": request, "assets": assets},
    )


@app.get("/asset/{symbol}", response_class=HTMLResponse)
async def asset_detail(
    request: Request,
    symbol: str,
    sma: int = 7,
    sma_high: int = 7,
    pos: int = 100,
    highlight: str | None = None,
    tab: str = "chart",
    resolution: str = "4h",
    network: str = "testnet",
    sl_short: int = 10,
    sl_long: int = 10,
    hl_long: str | None = None,
    strategy_tab: str = "short",
    auto_sma: int = 0,
) -> HTMLResponse:
    hl_long_int: int | None = int(hl_long) if hl_long not in (None, "") else None
    sym_upper = symbol.upper()
    asset = ASSET_BY_SYMBOL.get(sym_upper)
    cmc_symbol = asset["cmc_symbol"] if asset else sym_upper

    info = fetch_cmc_info(cmc_symbol)
    cg   = fetch_cg_market(sym_upper)

    # Compute candles + SMAs for backtest
    candles: list[dict] = []
    try:
        candles, _, sma_high_vals, sma_low_vals = prepare_chart_data(sym_upper, sma, sma_high_period=sma_high)
        raw_trades = backtest_short_strategy(candles, sma_low_vals, position_size_usd=float(pos), stop_loss_pct=sl_short / 100.0)
        raw_long_trades = backtest_long_strategy(candles, sma_high_vals, position_size_usd=float(pos), stop_loss_pct=sl_long / 100.0)
    except Exception as exc:  # noqa: BLE001
        print(f"[web] backtest failed for {sym_upper}: {exc}")
        raw_trades = []
        raw_long_trades = []

    # Resolve highlighted short trade (index-based)
    highlight_trade: dict | None = None
    if highlight and raw_trades:
        try:
            idx = int(highlight)
            if 0 <= idx < len(raw_trades):
                highlight_trade = raw_trades[idx]
        except (ValueError, IndexError):
            highlight_trade = next(
                (t for t in raw_trades if t["entry_date"].strftime("%Y-%m-%d") == highlight),
                None,
            )

    # Resolve highlighted long trade (index-based)
    highlight_long_trade: dict | None = None
    if hl_long_int is not None and raw_long_trades:
        if 0 <= hl_long_int < len(raw_long_trades):
            highlight_long_trade = raw_long_trades[hl_long_int]

    if highlight_trade or highlight_long_trade:
        chart_filename = _get_or_create_highlighted_chart(
            sym_upper, sma, sma_high, sl_short, sl_long,
            hl_short=highlight_trade,
            hl_long=highlight_long_trade,
        )
    else:
        chart_filename = _get_or_create_chart(sym_upper, sma, sma_high, sl_short, sl_long)

    # Performance data for the accordion Performance panel
    import json as _json
    perf_rows: list[dict] = []
    candles_4h_json: str = "[]"
    try:
        candles_5y = fetch_5y_candles(sym_upper)
        perf_rows = compute_perf_rows(candles_5y)
    except Exception as exc:  # noqa: BLE001
        print(f"[web] perf data failed for {sym_upper}: {exc}")
    try:
        candles_4h = fetch_4h_candles(sym_upper, resolution=resolution)
        candles_4h_json = _json.dumps([
            {
                "time":  int(c["date"].timestamp()),
                "open":  c["open"],
                "high":  c["high"],
                "low":   c["low"],
                "close": c["close"],
            }
            for c in candles_4h
        ])
    except Exception as exc:  # noqa: BLE001
        print(f"[web] perf chart failed for {sym_upper}: {exc}")

    # Order context for the accordion Place Order panel
    order_ctx: dict | None = None
    pair_meta = get_pair_meta(sym_upper, testnet=(network == "testnet"))
    try:
        row_30d = next((r for r in perf_rows if r["label"] == "30D"), None)
    except Exception as exc:  # noqa: BLE001
        print(f"[web] order context 30D fetch failed for {sym_upper}: {exc}")
        row_30d = None
    order_ctx = {
        "high_30d":     row_30d["high"] if row_30d else None,
        "low_30d":      row_30d["low"]  if row_30d else None,
        "max_leverage": int(pair_meta.max_leverage) if pair_meta else 10,
        "lot_size":     pair_meta.lot_size          if pair_meta else 1.0,
        "hl_symbol":    pair_meta.hl_symbol         if pair_meta else f"{sym_upper}/USDC:USDC",
    }

    # Format trades for template (convert datetimes to strings)
    last_close = candles[-1]["close"] if candles else None
    trades = [
        {
            "idx":                i,
            "entry_date":         t["entry_date"].strftime("%Y-%m-%d"),
            "entry_price":        t["entry_price"],
            "exit_date":          t["exit_date"].strftime("%Y-%m-%d") if t["exit_date"] else None,
            "exit_price":         t["exit_price"],
            "pnl":                t["pnl"],
            "is_open":            t["is_open"],
            "max_adverse_pnl":    t.get("max_adverse_pnl"),
            "max_favourable_pnl": t.get("max_favourable_pnl"),
            "virtual_pnl":  (
                (t["entry_price"] - last_close) / t["entry_price"] * float(pos)
                if t["is_open"] and last_close is not None
                else None
            ),
        }
        for i, t in enumerate(raw_trades)
    ]
    long_trades = [
        {
            "idx":                i,
            "entry_date":         t["entry_date"].strftime("%Y-%m-%d"),
            "entry_price":        t["entry_price"],
            "exit_date":          t["exit_date"].strftime("%Y-%m-%d") if t["exit_date"] else None,
            "exit_price":         t["exit_price"],
            "pnl":                t["pnl"],
            "is_open":            t["is_open"],
            "max_adverse_pnl":    t.get("max_adverse_pnl"),
            "max_favourable_pnl": t.get("max_favourable_pnl"),
            "virtual_pnl":  (
                (last_close - t["entry_price"]) / t["entry_price"] * float(pos)
                if t["is_open"] and last_close is not None
                else None
            ),
        }
        for i, t in enumerate(raw_long_trades)
    ]

    # Look up out-of-sample validation results produced by a prior best-SMA search.
    oos_data = OOS_CACHE.get((sym_upper, sma, sma_high, sl_short, sl_long, pos))

    return TEMPLATES.TemplateResponse(
        "asset_detail.html",
        {
            "request":        request,
            "symbol":         sym_upper,
            "market_cap_usd": asset["market_cap_usd"] if asset else None,
            "info":           info,
            "cg":             cg,
            "last_close":     last_close,
            "chart_filename": chart_filename,
            "data_source":    get_data_source(sym_upper),
            "sma_period":        sma,
            "sma_high":          sma_high,
            "pos_usd":           pos,
            "trades":         trades,
            "long_trades":    long_trades,
            "highlight":      highlight,
            "hl_long":        hl_long_int,
            "sl_short":       sl_short,
            "sl_long":        sl_long,
            "strategy_tab":   strategy_tab,
            "tab":               tab,
            "perf_rows":         perf_rows,
            "candles_4h_json":   candles_4h_json,
            "chart_resolution":  resolution,
            "eur_usd_rate":      fetch_eur_usd_rate(),
            "order_ctx":         order_ctx,
            "auto_sma":          auto_sma,
            "oos_short_summary": oos_data["short_summary"]   if oos_data else None,
            "oos_long_summary":  oos_data["long_summary"]    if oos_data else None,
            "oos_train_from":    oos_data["train_date_from"] if oos_data else None,
            "oos_train_to":      oos_data["train_date_to"]   if oos_data else None,
            "oos_val_from":      oos_data["val_date_from"]   if oos_data else None,
            "oos_val_to":        oos_data["val_date_to"]     if oos_data else None,
        },
    )


# ---------------------------------------------------------------------------
# Order placement API
# ---------------------------------------------------------------------------

class OrderRequest(BaseModel):
    side: str
    order_type: str
    size_usd: float
    leverage: int
    margin_type: str
    reduce_only: bool
    tp_price: float | None = None
    sl_price: float | None = None
    limit_price: float | None = None
    testnet: bool = True


@app.get("/asset/{symbol}/best-sma")
async def best_sma_endpoint(
    symbol: str,
    sl_short: int = 10,
    sl_long: int = 10,
    pos: int = 100,
) -> JSONResponse:
    """Return the best (sma_low, sma_high) pair for the given symbol."""
    try:
        sma_low, sma_high, candles_scaled, split_idx = _find_best_sma(symbol, sl_short, sl_long, float(pos))

        # Run validation backtest on the held-out 20% slice.
        val_candles   = candles_scaled[split_idx:]
        train_candles = candles_scaled[:split_idx]
        val_sma_lows  = _sma([c["low"]  for c in val_candles], sma_low)
        val_sma_highs = _sma([c["high"] for c in val_candles], sma_high)
        val_short = backtest_short_strategy(
            val_candles, val_sma_lows,
            position_size_usd=float(pos), stop_loss_pct=sl_short / 100.0,
        )
        val_long = backtest_long_strategy(
            val_candles, val_sma_highs,
            position_size_usd=float(pos), stop_loss_pct=sl_long / 100.0,
        )

        def _oos_summary(trades: list) -> dict:
            closed = [t for t in trades if not t["is_open"] and t["pnl"] is not None]
            total  = sum(t["pnl"] for t in closed)
            count  = len(closed)
            return {"count": count, "total_pnl": total, "avg_pnl": total / count if count else None}

        oos_data = {
            "short_summary":   _oos_summary(val_short),
            "long_summary":    _oos_summary(val_long),
            "train_date_from": str(train_candles[0]["date"])  if train_candles else "",
            "train_date_to":   str(train_candles[-1]["date"]) if train_candles else "",
            "val_date_from":   str(val_candles[0]["date"])    if val_candles else "",
            "val_date_to":     str(val_candles[-1]["date"])   if val_candles else "",
        }
        OOS_CACHE[(symbol.upper(), sma_low, sma_high, sl_short, sl_long, pos)] = oos_data

        return JSONResponse({"sma": sma_low, "sma_high": sma_high})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/asset/{symbol}/order")
async def place_order_endpoint(symbol: str, body: OrderRequest) -> JSONResponse:
    result = await hl_place_order(
        base_symbol=symbol.upper(),
        side=body.side,          # type: ignore[arg-type]
        order_type=body.order_type,  # type: ignore[arg-type]
        size_usd=body.size_usd,
        leverage=body.leverage,
        margin_type=body.margin_type,  # type: ignore[arg-type]
        reduce_only=body.reduce_only,
        tp_price=body.tp_price,
        sl_price=body.sl_price,
        limit_price=body.limit_price,
        testnet=body.testnet,
    )
    if result["ok"]:
        return JSONResponse({
            "ok": True,
            "order_id":    result["order_id"],
            "tp_order_id": result.get("tp_order_id"),
            "sl_order_id": result.get("sl_order_id"),
        })
    return JSONResponse({"ok": False, "error": result["error"]}, status_code=400)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    uvicorn.run("web:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
