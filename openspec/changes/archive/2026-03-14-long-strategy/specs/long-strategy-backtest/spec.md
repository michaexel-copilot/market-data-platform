## ADDED Requirements

### Requirement: Long strategy entry signal
The system SHALL enter a long position when the daily close crosses **above** the SMA High line: the previous candle's close was ≤ SMA High and the current candle's close is > SMA High. No new entry is allowed while a long position is already open.

#### Scenario: Entry on upward crossover
- **WHEN** `close[i-1] <= sma_high[i-1]` and `close[i] > sma_high[i]`
- **THEN** a long trade is opened at `close[i]` on `date[i]`

#### Scenario: No double entry
- **WHEN** a long position is already open
- **THEN** no new long entry is created regardless of SMA crossover

### Requirement: Long strategy stop loss exit
The system SHALL exit a long position with a stop loss when the close falls to or below `entry_price × (1 - stop_loss_pct)`. The exit price SHALL be exactly the stop loss price (not the close).

#### Scenario: Stop loss triggered
- **WHEN** `close[i] <= entry_price × (1 - stop_loss_pct)`
- **THEN** the trade closes at `entry_price × (1 - stop_loss_pct)` with a loss

### Requirement: Long strategy take profit exit
The system SHALL exit a long position with a profit when: the SMA High has risen above the entry price AND the current close is ≥ the current SMA High. The exit price SHALL be the current SMA High value.

#### Scenario: Take profit triggered
- **WHEN** `sma_high[i] > entry_price` and `close[i] >= sma_high[i]`
- **THEN** the trade closes at `sma_high[i]` with a profit

### Requirement: Long strategy P&L calculation
P&L SHALL be calculated as `(exit_price - entry_price) / entry_price × position_size_usd`. Open positions SHALL show an unrealised estimate using the current close as exit.

#### Scenario: Closed long profit trade P&L
- **WHEN** `exit_price > entry_price`
- **THEN** `pnl = (exit_price - entry_price) / entry_price × position_size_usd` (positive)

#### Scenario: Closed long loss trade P&L
- **WHEN** `exit_price < entry_price`
- **THEN** `pnl = (exit_price - entry_price) / entry_price × position_size_usd` (negative)

### Requirement: Long strategy excursion tracking
Each closed long trade SHALL record `max_adverse_pnl` (the most negative unrealised P&L seen while open — price fell) and `max_favourable_pnl` (the most positive unrealised P&L seen — price rose, but position was not yet closed). Both SHALL be `None` for open trades. Values are computed from daily close prices.

#### Scenario: Adverse excursion on profitable long trade
- **WHEN** a long trade closes with profit but the price dipped below entry during the hold
- **THEN** `max_adverse_pnl` is negative (the deepest dip expressed in USD)

#### Scenario: Never adverse profit trade
- **WHEN** a long trade closes with profit and the price never fell below entry
- **THEN** `max_adverse_pnl >= 0`

### Requirement: Long strategy chart crosshairs
The chart SHALL render long trade highlights as green crosshairs at the entry date/price and red crosshairs at the exit date/price. Long crosshairs SHALL be independent of short crosshairs and both MAY appear simultaneously on the same chart.

#### Scenario: Overlapping highlights
- **WHEN** both `hl_short` and `hl_long` are set
- **THEN** the chart shows both blue/orange (short) and green/red (long) crosshair pairs
