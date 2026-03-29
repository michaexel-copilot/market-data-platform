# Spec: crossover-backtest-engine

## Purpose

Defines the `CrossoverStrategy` family built on `backtesting.py`, covering Long+Cash, Short+Cash, and Long+Short exposure modes, plus the OHLCV data conversion and commission settings required to run backtests.

## Requirements

### Requirement: CrossoverStrategy class using backtesting.py
The backend SHALL provide a `CrossoverStrategy` (or subclass family) built on `backtesting.py`'s `Strategy` base class. Indicators SHALL be computed using `self.I()`. The strategy SHALL accept `ind1_type` (price/sma/ema), `ind2_type` (sma/ema), `ind1_period` (int, ignored when `ind1_type=price`), and `ind2_period` (int) as class-level parameters compatible with `Backtest.optimize()`.

#### Scenario: Strategy class is a backtesting.py Strategy subclass
- **WHEN** the `CrossoverStrategy` is inspected
- **THEN** it SHALL be a subclass of `backtesting.Strategy`

#### Scenario: Indicator 1 = Price uses close price directly
- **WHEN** `ind1_type` is `price`
- **THEN** Indicator 1 SHALL be `self.data.Close` and no SMA/EMA calculation SHALL occur for Indicator 1

#### Scenario: Indicator 1 = SMA computes rolling mean
- **WHEN** `ind1_type` is `sma`
- **THEN** Indicator 1 SHALL be computed as a simple moving average of close with period `ind1_period`

#### Scenario: Indicator 1 = EMA computes exponential mean
- **WHEN** `ind1_type` is `ema`
- **THEN** Indicator 1 SHALL be computed as an exponential moving average of close with period `ind1_period`

---

### Requirement: Long+Cash exposure mode
`LongCashStrategy` SHALL go long when Indicator 1 crosses above Indicator 2. It SHALL hold the position for at least 1 bar. It SHALL ignore any new entry signal for 1 bar after entering. It SHALL exit (sell) when Indicator 1 crosses below Indicator 2 after the minimum holding period.

#### Scenario: Long entry on upward crossover
- **WHEN** `ind1[prev] <= ind2[prev]` and `ind1[curr] > ind2[curr]` and no position is open and the blackout period has passed
- **THEN** a long (buy) order SHALL be placed at the current bar

#### Scenario: Long exit on downward crossover
- **WHEN** a long position is open and `ind1[prev] >= ind2[prev]` and `ind1[curr] < ind2[curr]` and at least 1 bar has elapsed since entry
- **THEN** the long position SHALL be closed (sell order)

#### Scenario: Signal blackout after entry
- **WHEN** a long entry was placed at bar N
- **THEN** no new entry signal SHALL be processed at bar N+1 (1-bar minimum hold)

---

### Requirement: Short+Cash exposure mode
`ShortCashStrategy` SHALL go short when Indicator 1 crosses below Indicator 2. It SHALL hold the position for at least 1 bar. It SHALL ignore any new entry signal for 1 bar after entering. It SHALL exit (cover) when Indicator 1 crosses above Indicator 2 after the minimum holding period.

#### Scenario: Short entry on downward crossover
- **WHEN** `ind1[prev] >= ind2[prev]` and `ind1[curr] < ind2[curr]` and no position is open and the blackout period has passed
- **THEN** a short (sell) order SHALL be placed at the current bar

#### Scenario: Short exit on upward crossover
- **WHEN** a short position is open and `ind1[prev] <= ind2[prev]` and `ind1[curr] > ind2[curr]` and at least 1 bar has elapsed since entry
- **THEN** the short position SHALL be closed (buy order)

---

### Requirement: Long+Short exposure mode
`LongShortStrategy` SHALL combine Long+Cash and Short+Cash: it goes long on upward crossovers and short on downward crossovers. When a long is open and a downward crossover fires (after the holding period), it SHALL first close the long, then immediately open a short. The reverse applies when a short is open and an upward crossover fires.

#### Scenario: Reverse from long to short on downward crossover
- **WHEN** a long position is open, the minimum hold has elapsed, and a downward crossover fires
- **THEN** the long position SHALL be closed and a short position SHALL be opened in the same bar

#### Scenario: Reverse from short to long on upward crossover
- **WHEN** a short position is open, the minimum hold has elapsed, and an upward crossover fires
- **THEN** the short position SHALL be closed and a long position SHALL be opened in the same bar

---

### Requirement: OHLCV data converted to backtesting.py DataFrame format
Before passing candles to `Backtest`, the system SHALL convert the `list[dict]` candle format (keys: `date`, `open`, `high`, `low`, `close`, `volume`) to a `pandas.DataFrame` with a `DatetimeIndex` and columns `Open`, `High`, `Low`, `Close`, `Volume` as required by `backtesting.py`.

#### Scenario: DataFrame has correct column names
- **WHEN** candles are converted for use with backtesting.py
- **THEN** the resulting DataFrame SHALL have columns `Open`, `High`, `Low`, `Close`, `Volume` and a `DatetimeIndex`

---

### Requirement: Commission set to zero
The `Backtest` instance SHALL be created with `commission=0` to match existing hand-rolled strategy behaviour.

#### Scenario: No commission applied to trades
- **WHEN** a `Backtest` is constructed for optimisation or validation
- **THEN** `commission=0` SHALL be passed to the `Backtest` constructor
