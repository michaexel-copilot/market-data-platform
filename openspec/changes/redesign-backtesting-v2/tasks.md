## 1. Dependency & project setup

- [x] 1.1 Add `backtesting>=0.3.3` and `pandas` (if not already present) to `pyproject.toml` dependencies
- [x] 1.2 Run `uv sync` to install `backtesting` into the virtual environment
- [x] 1.3 Create `cache/backtest/` directory (or confirm auto-creation in code)

## 2. Backend: indicator & exposure endpoints

- [x] 2.1 Add `GET /indicators` endpoint in `web.py` returning hardcoded JSON array of indicator options (price, sma, ema)
- [x] 2.2 Add `GET /exposures` endpoint in `web.py` returning hardcoded JSON array of exposure options (long_cash, short_cash, long_short)

## 3. Backend: backtesting engine module

- [x] 3.1 Create `backtest_engine.py` with `candles_to_df()` helper (converts `list[dict]` → `pandas.DataFrame` with correct column names and DatetimeIndex)
- [x] 3.2 Implement `LongCashStrategy` class inheriting from `backtesting.Strategy` with `ind1_type`, `ind2_type`, `ind1_period`, `ind2_period` class params; implement `init()` with `self.I()` for SMA/EMA/Price and `next()` with crossover long-entry/exit logic and 1-bar blackout guard
- [x] 3.3 Implement `ShortCashStrategy` class with same params; `next()` uses crossover short-entry/exit logic
- [x] 3.4 Implement `LongShortStrategy` class that reverses position on each crossover (long→short and short→long) with 1-bar minimum hold before reversing
- [x] 3.5 Implement `optimize_and_validate()` function: slices df by train_end date, calls `Backtest.optimize()` with `commission=0` and stepped ranges (cap at 10 000 combos), then runs second `Backtest` on validation slice with winning params; returns dict with best_params, train_stats, val_stats, val_trades

## 4. Backend: POST & DELETE endpoints

- [x] 4.1 Add `POST /asset/{symbol}/backtest` endpoint in `web.py` accepting form fields `ind1_type`, `ind2_type`, `ind1_min`, `ind1_max`, `ind2_min`, `ind2_max`, `exposure`, `train_end`, `val_start`; checks cache first, then calls `optimize_and_validate()`, writes cache file, returns HTML fragment rendered from template
- [x] 4.2 Add `DELETE /asset/{symbol}/backtest-cache` endpoint in `web.py` accepting same params; deletes matching cache file and returns 200 or 404

## 5. Frontend: replace strategy-controls accordion body

- [x] 5.1 Remove existing content from `#collapse-strategy-controls` in `asset_detail.html` (SMA LOW/HIGH spinners, SL Short/Long inputs, Find Best SMA button and related scripts)
- [x] 5.2 Add Indicator 1 `<select>` loaded via HTMX GET `/indicators` on page load; set `price` as default selected
- [x] 5.3 Add Indicator 1 period-range inputs (min/max, defaults 1/200); hidden by default (Price selected), shown via JS when sma/ema selected
- [x] 5.4 Add Indicator 2 `<select>` loaded via HTMX GET `/indicators` (excluding `price`); set `sma` as default selected
- [x] 5.5 Add Indicator 2 period-range inputs (min/max, defaults 1/200); always visible
- [x] 5.6 Add Exposure `<select>` loaded from `/exposures`; default `long_cash`
- [x] 5.7 Add Train-end date input (default `2024-12-31`) and Validation-start date input (default `2025-01-01`)
- [x] 5.8 Add "Run Backtest" button wired to HTMX POST `/asset/{symbol}/backtest` with all form fields; target `#backtest-results`; show spinner/disable on htmx request in flight
- [x] 5.9 Add `<div id="backtest-results">` placeholder below the button

## 6. Frontend: backtest results HTML template

- [x] 6.1 Create `templates/backtest_results.html` partial with: best-params summary row, training P&L summary (date range, trade count, net P&L, win rate), validation P&L summary, validation trade table (Entry Date, Entry Price, Exit Date, Exit Price, P&L, Direction), "Clear Cache" button (HTMX DELETE → clears `#backtest-results`), empty-trades message

## 7. Remove / deprecate superseded code

- [x] 7.1 Mark `/asset/{symbol}/best-sma` endpoint in `web.py` as deprecated (add comment); do not remove yet
- [x] 7.2 Remove `auto_sma` / `load_best_sma_on_render` logic from `asset_detail` route and template since it depended on strategy-controls SMA spinners (verify no remaining references)
