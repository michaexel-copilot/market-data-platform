## Why

The current `#heading-strategy-controls` accordion hard-codes a single SMA-vs-SMA crossover strategy with fixed Short/Long roles. This limits the user to one trading approach and does not support systematic parameter optimization across multiple indicator types and exposure modes. The redesign replaces the existing controls with a flexible, `backtesting.py`-powered engine that sweeps indicator ranges, splits data into train/validation sets, and surfaces the best parameters for the chosen asset.

## What Changes

- **REMOVE** all existing GUI elements inside the `#heading-strategy-controls` accordion (SMA LOW / SMA HIGH spinners, SL Short / SL Long inputs, "Find Best SMA" button, current trade tables produced by the old strategy controls).
- **ADD** an Indicator 1 dropdown (`Price`, `SMA`, `EMA`) and an Indicator 2 dropdown (`SMA`, `EMA`) with their respective period-range inputs inside the accordion.
- **ADD** an Exposure dropdown (`Long+Cash`, `Short+Cash`, `Long+Short`) inside the accordion.
- **ADD** Backtest Date-Range inputs: training cutoff (default 31.12.2024) and validation end (default: most current data); both adjustable.
- **ADD** a "Run Backtest" button that triggers a parameter sweep over the indicator ranges, finds the combination with the highest net profit on training data, then evaluates it on validation data.
- **ADD** a results section below the button: best parameters, net profit + loss for training and validation periods, and a trade table for the validation period.
- **ADD** a new backend endpoint `/asset/{symbol}/backtest` (GET) and `/asset/{symbol}/backtest` (POST) powered by `backtesting.py` — replacing the old `find-best-sma` endpoint for parameter optimization.
- **ADD** a disk cache for backtest results (keyed by symbol + indicator combination + date-range), invalidatable via a "Clear Cache" button or TTL.
- The old `backtest_short_strategy` / `backtest_long_strategy` functions in `draw_chart.py` are **retained** for chart rendering but no longer drive the strategy-controls UI.

## Capabilities

### New Capabilities

- `indicator-selector`: UI dropdowns for Indicator 1 (Price / SMA / EMA) and Indicator 2 (SMA / EMA) with configurable period ranges (default 1–200), plus an Exposure dropdown (Long+Cash / Short+Cash / Long+Short). Served via a dedicated endpoint for option lists.
- `crossover-backtest-engine`: `backtesting.py`-based backtest runner that implements the three exposure modes (Long+Cash, Short+Cash, Long+Short) using indicator crossover signals with a minimum 1-day holding period and 24-hour signal blackout. Accepts symbol, indicator specs, exposure mode, and date range; returns trades and statistics.
- `backtest-param-optimization`: Grid search over the indicator period ranges on training data (oldest available → 31.12.2024). Scores each parameter pair by net profit; returns the best configuration.
- `backtest-results-display`: Results section showing best parameters found, P&L summary (training + validation), and a paginated trade table for the validation period (01.01.2025 → most current).
- `backtest-cache`: File-based cache for backtest results (keyed by symbol + indicator type + range + exposure + date-range hash), invalidatable on demand.

### Modified Capabilities

- `find-best-sma-optimization`: The existing "Find Best SMA" button and `/asset/{symbol}/best-sma` endpoint are superseded by the new `backtest-param-optimization` capability. The old endpoint can be deprecated once the new one is stable.

## Impact

- **`templates/asset_detail.html`**: `#heading-strategy-controls` accordion body is replaced with new indicator/exposure inputs and results section.
- **`web.py`**: New FastAPI routes for `/asset/{symbol}/backtest` (GET for cached results, POST to trigger run) and `/indicators` (returns indicator list). Old best-sma route kept temporarily.
- **`draw_chart.py`**: No changes required; existing `backtest_short_strategy` / `backtest_long_strategy` remain for chart rendering.
- **New dependency**: `backtesting` (backtesting.py) added to `pyproject.toml`.
- **Cache directory**: New subdirectory `cache/backtest/` for serialized backtest results (JSON).
- **No breaking API changes** for existing chart endpoints.
