Generate a comprehensive user manual as md file (from the user aspect)

describe all features and the parameters that are important for the features.
For example:
Feature: Short Strategy Trades.
Describe the entry points and the exit points, the parameters (SMA period) and anything else that is important for the user.
Do this for all other feeatures.

Add a task list under here with checkboxes what you have and what is missing.

---

## Task Checklist

- [x] **Interface Overview** — two-pane layout, URL
- [x] **Sidebar — Asset List** — network toggle, asset item display, three resizable panels, filter, Favourite/Ignore actions, badge counter, keyboard navigation
- [x] **Chart & Trades Tab** — 12-month daily OHLC chart, SMA lines (High/Low/Close), SMA period spinner with keyboard shortcuts, position size field, short strategy entry/exit/stop-loss logic, trade table with P&L and row-click highlighting
- [x] **Performance Tab** — resolution toggle (1H/4H), stats table (1D/7D/30D/1Y/5Y × High/Low/VWAP/Volume), EUR conversion, interactive 35-day chart with ATH/ATL y-axis pinning and H/L reference lines
- [x] **Fundamentals Tab** — market cap, launch date, ATH/ATL, OHLC source, chain/platform, contract address
- [x] **Place Order Tab** — Testnet/Mainnet warning, all form fields (Margin/Side/Leverage/OrderType/LimitPrice/Size), TP&SL defaults with levered P&L display, Reduce Only mode, confirmation modal
- [x] **Data Sources** — Yahoo Finance vs CoinGecko fallback, K-prefix tokens (×1000), EUR/USD rate caching
- [x] **Keyboard Reference** — sidebar nav, SMA spinner shortcuts
- [x] **Known Limitations** — market order slippage, CoinGecko close-only OHLC, missing data warning, daily EUR rate refresh, irreversible mainnet orders, testnet subset

