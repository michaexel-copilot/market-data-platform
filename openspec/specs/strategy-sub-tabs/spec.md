## Purpose

Provides Short / Long pill-style sub-tab navigation within the Chart & Trades section, allowing the user to switch between the short strategy trades table and the long strategy trades table while keeping all other state (SMA periods, SL %, position size, chart highlights) intact.

## Requirements

### Requirement: Short / Long strategy sub-tab navigation
The Chart & Trades section SHALL display a Short / Long pill-style sub-tab navigation below the chart and above the trades content. The active tab SHALL be driven by the `strategy_tab` URL parameter ("short" default, "long" alternative). Clicking a sub-tab SHALL fire an HTMX request that reloads the Chart & Trades partial with the updated `strategy_tab` value while preserving all other URL params.

#### Scenario: Default active tab
- **WHEN** `strategy_tab` is absent from the URL
- **THEN** the "Short" sub-tab is rendered as active

#### Scenario: Switching to Long tab
- **WHEN** the user clicks the "Long" pill
- **THEN** `strategy_tab=long` is sent and the Long trades table is rendered

---

### Requirement: Sub-tab state preserved on spinner change
A hidden `<input id="strategy-tab-input" name="strategy_tab">` SHALL be included in the `hx-include` chain of every spinner (SMA LOW, SMA HIGH, SL Short %, SL Long %, Position Size) so that the active sub-tab is preserved when any spinner value changes.

#### Scenario: SMA change preserves active tab
- **WHEN** the SMA LOW spinner changes while the Long tab is active
- **THEN** the reloaded partial still shows the Long tab as active

---

### Requirement: Long trades table
The long strategy sub-tab SHALL render a trades table and summary bar identical in structure to the short trades table, using the long strategy's backtest results. The table columns SHALL be: #, Entry Date, Entry $, Exit Date, Exit $, P&L, Max Δ P&L.

#### Scenario: Long trades displayed
- **WHEN** the Long sub-tab is active and long trades exist
- **THEN** a table of long trades is shown with all 7 columns

#### Scenario: No long trades
- **WHEN** no long signals were found in the lookback period
- **THEN** a "No signals found" message is shown instead of a table

---

### Requirement: Long trades summary bar
The long sub-tab SHALL display a summary bar above the table showing the count of closed long trades, their total P&L, and average P&L per trade, with the same colour coding (green ≥ 0, red < 0) as the short summary.

#### Scenario: Summary bar values
- **WHEN** there are 5 closed long trades with total P&L of +$3.50
- **THEN** the summary shows "5 trades · Total P&L: +3.50 · Avg: +0.70/trade"

---

### Requirement: Independent highlight params for short and long
Trade row clicks in the short table SHALL update `hl_short`; clicks in the long table SHALL update `hl_long`. Both SHALL be carried in the URL and in hidden inputs so that one highlight does not clear the other.

#### Scenario: Clicking a long trade row preserves short highlight
- **WHEN** `hl_short=2` is set and the user clicks long trade row #4
- **THEN** the chart shows both the short #2 and long #4 crosshairs simultaneously
