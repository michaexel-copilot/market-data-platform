# Short Opportunities — User Manual

A web application for identifying and trading short opportunities on Hyperliquid perpetuals.

---

## Table of Contents

1. [Interface Overview](#1-interface-overview)
2. [Sidebar — Asset List](#2-sidebar--asset-list)
3. [Fundamentals Panel](#3-fundamentals-panel)
4. [Chart Panel](#4-chart-panel)
5. [Strategy Controls Panel](#5-strategy-controls-panel)
6. [Trades Panel](#6-trades-panel)
7. [Performance Panel](#7-performance-panel)
8. [Place Order Panel](#8-place-order-panel)
9. [Data Sources](#9-data-sources)
10. [Keyboard Reference](#10-keyboard-reference)
11. [Known Limitations](#11-known-limitations)

---

## 1. Interface Overview

Open the application at `http://localhost:8000`.

The screen is divided into two panes:

- **Left — Sidebar**: the asset list with filter, Favourites and Ignored panels, and the Testnet/Mainnet network toggle.
- **Right — Detail pane**: charts, stats, and order forms for the selected asset, organised as a **vertical accordion**. Each section can be expanded or collapsed independently by clicking its header.

Click any asset in the sidebar to load its detail view. The **Fundamentals** and **Strategy Controls** panels open automatically; the rest start collapsed.

---

## 2. Sidebar — Asset List

### Network Toggle

At the very top of the sidebar is a **Testnet / Mainnet** toggle.

| Option | Behaviour |
|--------|-----------|
| **Testnet** (default) | Loads the Hyperliquid testnet asset list. Safe for practice trading. |
| **Mainnet** | Loads the full Hyperliquid mainnet asset list. Switches the Place Order tab to real-money mode (red border). |

Switching the toggle immediately reloads the asset list. Your Favourites and Ignored state is preserved across switches.

### Asset Item Display

Each asset in the list shows:

- **Rank** — CoinMarketCap market-cap rank (`#1`, `#2`, …)
- **Symbol** — trading symbol (e.g. `BTC`, `SOL`)
- **Market cap** — in $B (billions), shown in grey below the symbol
- **Launch date** — date the token was launched, if available

### Three Panels

The sidebar has three resizable panels separated by draggable dividers:

| Panel | Default Size | Purpose |
|-------|-------------|---------|
| **Main** | 30% | All assets, sorted by market cap descending |
| **Favourites** | 60% | Assets you have starred |
| **Ignored** | 10% | Assets you have hidden from the Main list |

**Resizing panels**: Drag the horizontal divider bar between panels up or down. Heights are saved to `localStorage` and restored on reload.

### Filter

The search box at the top of the sidebar filters the Main list in real time by symbol. Press **Escape** to clear the filter and return focus to the filter input.

### Managing Assets

| Action | How |
|--------|-----|
| Add to Favourites | Click the ★ button on the asset row, or press **F** while the asset is focused |
| Remove from Favourites | Click the ★ button again in the Favourites panel |
| Ignore (hide) an asset | Click the ✕ button on the asset row, or press **I** while the asset is focused |
| Restore an ignored asset | Click the asset name in the Ignored panel (or the ↩ button) |

The selection focus automatically moves to the next visible asset when you ignore the currently selected one.

### Badge Counter

The asset count badge next to "Assets" shows the total number of items in the current network's list. When a filter is active it shows `visible / total`.

---

## 3. Fundamentals Panel

Shows metadata for the selected asset assembled from CoinMarketCap and CoinGecko.

| Field | Source | Description |
|-------|--------|-------------|
| **Market Cap** | CoinMarketCap | Total market capitalisation in USD |
| **Launched** | CoinMarketCap | Token launch date (YYYY-MM-DD) |
| **ATH** | CoinGecko | All-time high price, the date it occurred, and % difference vs current price |
| **ATL** | CoinGecko | All-time low price, the date it occurred, and % difference vs current price |
| **OHLC Source** | Internal | Whether OHLCV data is fetched from Yahoo Finance or CoinGecko |
| **Chain / Platform** | CoinMarketCap | Blockchain or platform the token lives on, with contract address if available |

The asset name at the top is a clickable link to the CoinMarketCap page (when available).

---

## 4. Chart Panel

### Chart

The main chart shows **12 months of daily OHLC data** as a price line (close price) with three SMA overlays (7-day by default):

| Line | Colour | Meaning |
|------|--------|---------|
| Close | Black | Daily closing price |
| SMA High | Light blue | Simple moving average of daily **highs** |
| SMA Low | Green | Simple moving average of daily **lows** — the **strategy signal line** |
| SMA Close | Purple | Simple moving average of daily closes |

The three SMA lines use a fixed period of **7 days**. There is no input field for them in the interface; the periods can only be changed by adding `?sma=<days>&sma_high=<days>` to the asset URL. They are independent of the periods found by the backtest in the [Strategy Controls Panel](#5-strategy-controls-panel).

The chart is a static image. Trades cannot be highlighted on it.

### Strategy parameters

The SMA period spinners, stop-loss inputs, Position Size field and the **Find Best SMA** button no longer exist. The SMA periods are now found by the backtest optimiser; see [Backtest Controls](#5-strategy-controls-panel) below. The endpoint behind the old button (`GET /asset/{symbol}/best-sma`) is disabled and returns HTTP 410.

---

## 5. Strategy Controls Panel

This panel (expanded by default) contains the **Backtest Controls**. It optimises the indicator periods on a training window and then checks the best pair on a separate validation window.

### Backtest Controls

| Control | Options | Meaning |
|---------|---------|---------|
| **Indicator 1** | Price (default), SMA, EMA | The fast line. With **Price**, the closing price itself is used and no period range is shown. With SMA or EMA, a **Min – Max** period range appears (1–500, default 1–200). |
| **Indicator 2** | SMA (default), EMA | The slow line, always with a **Min – Max** period range (1–500, default 1–200). |
| **Exposure** | Long+Cash (default), Short+Cash, Long+Short | Which side the strategy trades (see below). |
| **Train start** / **Train end** | Dates, default 2020-01-01 – 2024-12-31 | The training window used to select the best periods. Train start is moved forward to the oldest available candle if the asset has no data that far back. |
| **Validation start** | Date, default 2025-01-01 | First day of the validation window, which runs to the latest candle. |

**Exposure modes** (signals are crossovers of Indicator 1 and Indicator 2 on daily closes):

- **Long+Cash** — buys when Indicator 1 crosses above Indicator 2 and exits to cash when it crosses back below.
- **Short+Cash** — sells short when Indicator 1 crosses below Indicator 2 and exits to cash when it crosses back above.
- **Long+Short** — always in the market: long while Indicator 1 is above Indicator 2, short while it is below, reversing on each crossover.

A position is held for at least one bar. Each trade invests 99 % of the current account value, so gains and losses compound. The account starts with $1,000 at the beginning of each window (training and validation separately), and no commission is charged. Net P&L is the final account value minus $1,000, so a training P&L in the tens of thousands over several years is possible.

### Running a backtest

Click **Run Backtest**. A spinner is shown on the button while it runs.

1. All period combinations in the Min – Max ranges are tested on the **training window**. The pair with the highest final equity wins. If the number of combinations exceeds 10,000, the periods are stepped to keep the search within that limit.
2. The winning pair is then run once on the **validation window**, which the optimiser never saw. This is the honest estimate of how the pair performs on new data.

Results for identical inputs are cached on disk, so repeating a run returns instantly (a first run with a 5–50 period range takes a few seconds).

### Results

- **Best Parameters Found** — the winning indicator types, periods and the exposure mode (shown as `long_cash`, `short_cash` or `long_short`).
- **Training** and **Validation** cards — date range, number of trades, net P&L (green when positive, red when negative) and win rate. The Validation card also shows the **open position** (direction, entry date and price, current price, unrealised P&L), if there is one.
- **Validation Trades** — click **Show trades** to expand the table of validation trades with direction, entry and exit date and price, and P&L. An open position is listed at the end, marked **OPEN**.

### Cached Backtests

Below the results, a table lists every cached backtest for the asset. Click a column header to sort. Columns: train start, train end, validation start, both indicators with their best periods (e.g. `Price`, `SMA-38`, `EMA-10`), exposure, training net P&L, validation net P&L (in `$`, green or red) and validation trades. Different settings are cached as separate rows.

- **Load** — fills the form with that run's settings (the period range is set to the winning period) and shows its results.
- **✕** — deletes the cached run.

---

## 6. Trades Panel

There is no separate trades panel any more. The old short and long strategies with stop-loss and the combined trade table (with Max Δ P&L and click-to-highlight) have been replaced by the backtest.

Trades are shown in the **Validation Trades** table of the [Strategy Controls Panel](#5-strategy-controls-panel). It lists the trades of the best parameter pair on the validation window: direction, entry and exit date and price, and P&L. A position that is still open is listed last, marked **OPEN**, with its unrealised P&L. The table is collapsed by default; click **Show trades** to expand it.

Stop-loss levels and a free position size are not part of the backtest. Each trade invests 99 % of the current account value (starting at $1,000), so the P&L of later trades grows or shrinks with earlier results.

---

## 7. Performance Panel

Shows recent price statistics and an interactive candlestick chart. Collapsed by default.

### Stats Table

| Column | Description |
|--------|------------|
| **Period** | Time window: 1D, 7D, 30D, 1Y, 5Y |
| **High** | Highest price reached in the period |
| **Low** | Lowest price reached in the period |
| **VWAP** | Volume-weighted average price `(sum of typical_price × volume) / total_volume` |
| **Volume** | Total traded USD volume in the period |
| **Chart lines** | Colour-coded legend for the H/L reference lines on the chart |

Prices are shown in **USD** and **EUR** (EUR values appear below in blue, based on today's exchange rate).

Periods older than the available data are suppressed (shown as `—`).

### Legend (right of table)

Explains the chart line styles:

- **Dashed line** = period High
- **Dotted line** = period Low
- Colours: blue = 1D, orange = 7D, green = 30D

### Interactive Chart

An interactive price chart using **~90 days** of data at the selected resolution:

- **Resolution toggle**: **1H** or **4H** (default 4H) bars. Switch using the buttons above the chart within this panel.
- **Visible window**: the last **35 days** are shown by default on the x-axis
- **Y-axis**: pinned so the **30D high sits at the 95% mark** and the **30D low sits at the 5% mark**, giving context to where the current price sits within the 30-day range
- **Reference lines**: 30D, 7D, and 1D high (dashed) and low (dotted) are drawn as horizontal lines spanning their respective window
- **Candlestick mode**: available when data comes from Yahoo Finance (full OHLCV with real H/L). CoinGecko-sourced assets show a line chart instead (close-only data)
- The chart is interactive — hover to see exact values on the crosshair. Pan and zoom with the mouse wheel or by dragging

---

## 8. Place Order Panel

Places perpetual futures orders on Hyperliquid directly from the app. Collapsed by default.

> ⚠️ **Warning**: When the sidebar is set to **Mainnet**, this form places real orders with real money. The order card is outlined in **red** as a reminder.

### Network

The network (Testnet or Mainnet) is controlled by the toggle at the **top of the sidebar**, not within this form. Switch to Testnet for practice orders; switch to Mainnet only when you intend to trade with real funds.

### Form Fields

| Field | Default | Options / Range | Notes |
|-------|---------|-----------------|-------|
| **Margin** | Cross | Cross, Isolated | Cross margin shares your full account balance as collateral |
| **Position** | Sell / Short | Sell / Short, Buy / Long | Changing side resets the leverage and swaps the TP/SL defaults |
| **Leverage** | 2× (Short), 1× (Long) | 1× – max× (slider) | Maximum depends on the asset; shown at the right end of the slider |
| **Order Type** | Market | Market, Limit | Limit reveals the Limit Price field |
| **Limit Price** | Last close | Any positive number | Only visible when Limit is selected |
| **Size (USD)** | — | ≥ $10 | Required. Enter the notional USD value of the position |

### Risk Management

Choose one mode:

**Take Profit & Stop Loss** (default)

| Sub-field | Default | Description |
|-----------|---------|-------------|
| Take Profit ($) | 30D Low (for Short) / 30D High (for Long) | Target exit price. The % gain is calculated and shown automatically. |
| Stop Loss ($) | 30D High (for Short) / 30D Low (for Long) | Maximum loss exit price. The % loss is calculated and shown automatically. |

When leverage > 1×, the **levered gain** and **levered loss** percentages are shown below the TP/SL fields — these reflect the actual return on your margin, not the notional position.

**Reduce Only** — Places a position-closing order only (no TP/SL).

### Placing an Order

1. Fill in all fields and click **Place Order**
2. A confirmation dialog appears summarising all parameters
3. Review carefully — the Network (Testnet / ⚠️ MAINNET), symbol, side, leverage, size, TP, and SL are all shown
4. Click **Confirm & Place** to send the order, or **Cancel** to go back
5. On success, the order ID (and TP/SL order IDs if applicable) are displayed

---

## 9. Data Sources

### OHLCV Price Data

Price data is fetched automatically and cached to disk for the current day.

| Source | Used when |
|--------|-----------|
| **EODHD** (local service) | **Decommissioned** (Board decision O1(c), HED-19, 2026-10-06). The local service at `http://localhost:8010` no longer runs and no symbol is routed to it. Historical EODHD rows remain in the database table `ohlcv`. |
| **Yahoo Finance** | Default source. Provides full daily OHLCV (open, high, low, close, volume) from 2020-01-01. |
| **CoinGecko** | For assets not listed on Yahoo Finance (e.g. HYPE, SUI, MNT). Provides close-only daily data; the Performance chart shows a line chart. |

To keep the market-data database (table `ohlcv`) up to date, use the OHLCV backfill loader (`ohlcv_backfill.py`, e.g. `backfill update --days 3 --intervals 1h,1d`); see `docs/ohlcv-backfill.md`.

**K-prefix tokens** (KBONK, KPEPE, KSHIB, etc.) represent 1000 × the underlying coin. Prices are fetched from the underlying token and multiplied by 1000 automatically.

The **OHLC Source** is shown in the Fundamentals panel.

### EUR / USD Exchange Rate

Performance tab prices are converted to EUR using an exchange rate fetched once per day from `open.er-api.com`. The rate is cached and reused for the rest of the day.

---

## 10. Keyboard Reference

### Sidebar

| Key | Action |
|-----|--------|
| `↑` / `↓` | Move selection up / down through the visible Main list |
| `Enter` (on an asset) | Load the asset's detail view |
| `F` (on a focused asset) | Toggle Favourite |
| `I` (on a focused asset) | Ignore (hide) the asset |
| `Escape` | Clear the filter box and focus it |
| `↓` (from filter box) | Move focus to the first visible asset |

The Backtest Controls use ordinary form fields and have no special keyboard shortcuts.

---

## 11. Known Limitations

- **Market orders**: Executed at the current best bid/ask. Actual fill price may differ from the displayed last close, especially in thin markets.
- **CoinGecko OHLC**: The Performance chart shows a line (close-only) for CoinGecko-sourced assets. High/Low values in the stats table reflect CoinGecko's daily OHLC candles, which use a different aggregation method than exchange data.
- **Assets with no price data**: If neither Yahoo Finance nor CoinGecko has data for an asset, a warning is shown in place of the chart. The Performance and Place Order panels still function using other data sources.
- **Exchange rate**: The USD→EUR rate is refreshed once per day. Prices shown in EUR during the session reflect the rate at the time of the last refresh.
- **Mainnet orders are irreversible**: Once confirmed, orders are sent directly to the Hyperliquid exchange. Always review the confirmation dialog before clicking Confirm.
- **Testnet asset list**: The testnet list contains a subset of assets compared to mainnet. Not all mainnet assets are available for testnet trading.
