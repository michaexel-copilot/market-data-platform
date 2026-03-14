## MODIFIED Requirements

### Requirement: SMA spinner hx-include chains
All spinner `hx-include` attributes and hidden inputs on non-chart tabs SHALL be extended to carry the new params: `sl_short`, `sl_long`, `strategy_tab`, and `hl_long` in addition to the existing `sma`, `sma_high`, `pos`, and `tab` inputs.

#### Scenario: Full param set on spinner change
- **WHEN** any spinner changes on the Chart & Trades tab
- **THEN** the HTMX request includes `sma`, `sma_high`, `pos`, `tab`, `sl_short`, `sl_long`, `strategy_tab`, `hl_short`, `hl_long`

#### Scenario: Hidden inputs on non-chart tabs
- **WHEN** the Performance, Fundamentals, or Order tab is active
- **THEN** hidden inputs for `sma_high`, `sl_short`, `sl_long`, `strategy_tab`, `hl_short`, `hl_long` are present in the DOM so their values are preserved
