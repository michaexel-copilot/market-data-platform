## ADDED Requirements

### Requirement: Performance-focused asset detail view
The system SHALL provide an asset-detail performance view that prioritizes cached-backtest analysis by removing redundant chart-only navigation and aligning related analysis sections in one flow.

#### Scenario: Redundant chart accordion removed
- **WHEN** the asset detail page is rendered
- **THEN** the accordion item `Chart & Trades: Chart` is not present

#### Scenario: Validation trades placed below cached backtests
- **WHEN** the asset detail page shows cached backtest results
- **THEN** the Validation Trades section is rendered directly below the Cached Backtests table

### Requirement: Performance accordion auto-open on cached backtest load
When a cached backtest is loaded (via the Load button or after invoking a new backtest run that loads cached results), the system SHALL automatically open the `Performance` accordion item.

#### Scenario: Auto-open after Load button
- **WHEN** the user clicks the cached backtest Load button and loading succeeds
- **THEN** the `Performance` accordion item is opened automatically

#### Scenario: Auto-open after new run load
- **WHEN** a new backtest run completes and cached backtest results are loaded into the asset detail page
- **THEN** the `Performance` accordion item is opened automatically

### Requirement: Daily price-plus-indicator performance chart
The `Performance` accordion SHALL render a chart overlaying price and indicators on daily granularity.

#### Scenario: Daily overlay chart shown
- **WHEN** a cached backtest is loaded and `Performance` is opened
- **THEN** the chart displays both price and indicator series on a 1-day basis

### Requirement: Context-aware chart time window
The performance chart SHALL use a deterministic time window:
- trade-context mode: from 5 days before the opened trade until today;
- fallback mode: at least the last 30 days until today when trade-open context is unavailable.

#### Scenario: Trade-context window used
- **WHEN** an opened-trade timestamp exists for the loaded backtest
- **THEN** the chart start date is 5 days before that opened-trade timestamp and the end date is today

#### Scenario: Fallback 30-day window used
- **WHEN** no opened-trade timestamp is available for the loaded backtest
- **THEN** the chart covers at least the last 30 days up to today
