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

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from cmc_info import fetch_cmc_info, fetch_cmc_info_batch, fetch_market_caps  # noqa: E402
from cg_market import fetch_cg_market  # noqa: E402
from draw_chart import backtest_strategy, draw_chart, get_data_source, prepare_chart_data  # noqa: E402
from lists_db import add_item, get_lists, remove_item  # noqa: E402
from perf_data import compute_perf_rows, draw_perf_chart, fetch_4h_candles, fetch_5y_candles  # noqa: E402

HL_PAIRS_CSV = Path("/mnt/ds420/data/hyperliquid/hl-main-pairs.csv")
assert HL_PAIRS_CSV.exists(), f"Asset list not found: {HL_PAIRS_CSV}"

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


ASSETS: list[dict[str, Any]] = _load_assets()
ASSET_BY_SYMBOL: dict[str, dict[str, Any]] = {a["symbol"]: a for a in ASSETS}


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------

def _today_prefix(symbol: str, sma_period: int) -> str:
    """Return the filename prefix used for today's chart, e.g. SOLUSD_2026-02-24_SMA44"""
    return f"{symbol.upper()}USD_{date.today()}_SMA{sma_period}"


def _find_existing_chart(symbol: str, sma_period: int) -> str | None:
    """Return the filename (not path) of the newest non-highlighted chart for today, or None."""
    prefix = _today_prefix(symbol, sma_period)
    PNG_DIR.mkdir(exist_ok=True)
    matches = sorted(
        [f for f in PNG_DIR.glob(f"{prefix}_*.png") if "_hi_" not in f.name],
        reverse=True,
    )
    return matches[0].name if matches else None


def _get_or_create_chart(symbol: str, sma_period: int) -> str | None:
    """Return the filename for today's chart, generating it if needed."""
    existing = _find_existing_chart(symbol, sma_period)
    if existing:
        return existing
    try:
        path = draw_chart(symbol, sma_period=sma_period)
        return path.name
    except Exception as exc:  # noqa: BLE001
        print(f"[web] Could not generate chart for {symbol}: {exc}")
        return None


def _get_or_create_highlighted_chart(
    symbol: str, sma_period: int, highlight: dict
) -> str | None:
    """Generate (or reuse today's) chart PNG with entry/exit crosshairs."""
    entry_date_str = highlight["entry_date"].strftime("%Y-%m-%d")
    filename = f"{symbol.upper()}USD_{date.today()}_SMA{sma_period}_hi_{entry_date_str}.png"
    if (PNG_DIR / filename).exists():
        return filename
    try:
        path = draw_chart(symbol, sma_period=sma_period, highlight=highlight)
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
        {"request": request, "assets": ASSETS},
    )


@app.get("/asset/{symbol}", response_class=HTMLResponse)
async def asset_detail(
    request: Request,
    symbol: str,
    sma: int = 44,
    pos: int = 100,
    highlight: str | None = None,
    tab: str = "chart",
) -> HTMLResponse:
    sym_upper = symbol.upper()
    asset = ASSET_BY_SYMBOL.get(sym_upper)
    cmc_symbol = asset["cmc_symbol"] if asset else sym_upper

    info = fetch_cmc_info(cmc_symbol)
    cg   = fetch_cg_market(sym_upper)

    # Compute candles + SMAs for backtest
    try:
        candles, _, _, sma_low_vals = prepare_chart_data(sym_upper, sma)
        raw_trades = backtest_strategy(candles, sma_low_vals, position_size_usd=float(pos))
    except Exception as exc:  # noqa: BLE001
        print(f"[web] backtest failed for {sym_upper}: {exc}")
        raw_trades = []

    # Resolve highlighted trade (if any)
    highlight_trade: dict | None = None
    if highlight and raw_trades:
        highlight_trade = next(
            (t for t in raw_trades if t["entry_date"].strftime("%Y-%m-%d") == highlight),
            None,
        )

    if highlight_trade:
        chart_filename = _get_or_create_highlighted_chart(sym_upper, sma, highlight_trade)
    else:
        chart_filename = _get_or_create_chart(sym_upper, sma)

    # Performance data — only fetched when the Performance tab is active
    perf_rows: list[dict] = []
    perf_chart_filename: str | None = None
    if tab == "performance":
        try:
            candles_5y = fetch_5y_candles(sym_upper)
            perf_rows  = compute_perf_rows(candles_5y)
        except Exception as exc:  # noqa: BLE001
            print(f"[web] perf data failed for {sym_upper}: {exc}")
        try:
            candles_4h = fetch_4h_candles(sym_upper)
            path_4h    = draw_perf_chart(sym_upper, perf_rows, candles_4h)
            perf_chart_filename = path_4h.name if path_4h else None
        except Exception as exc:  # noqa: BLE001
            print(f"[web] perf chart failed for {sym_upper}: {exc}")

    # Format trades for template (convert datetimes to strings)
    last_close = candles[-1]["close"] if candles else None
    trades = [
        {
            "entry_date":   t["entry_date"].strftime("%Y-%m-%d"),
            "entry_price":  t["entry_price"],
            "exit_date":    t["exit_date"].strftime("%Y-%m-%d") if t["exit_date"] else None,
            "exit_price":   t["exit_price"],
            "pnl":          t["pnl"],
            "is_open":      t["is_open"],
            "virtual_pnl":  (
                (t["entry_price"] - last_close) / t["entry_price"] * float(pos)
                if t["is_open"] and last_close is not None
                else None
            ),
        }
        for t in raw_trades
    ]

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
            "sma_period":     sma,
            "pos_usd":        pos,
            "trades":         trades,
            "highlight":      highlight,
            "tab":               tab,
            "perf_rows":         perf_rows,
            "perf_chart_filename": perf_chart_filename,
        },
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    uvicorn.run("web:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
