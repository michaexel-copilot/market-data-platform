## Purpose

Provides two independent SMA period spinners on the Chart & Trades tab — one for the SMA Low signal line and one for the SMA High reference line — with consistent keyboard shortcuts and tab-persistence via hidden inputs.

## Requirements

### Requirement: SMA period LOW spinner replaces existing SMA period spinner
The existing "SMA period" spinner in the Chart & Trades tab SHALL be renamed to **"SMA period LOW"**.
- Default value SHALL be **7**.
- The `Shift + "+/-"` keyboard shortcut SHALL increment/decrement by **7**.
- All other keyboard behaviour remains unchanged: `+/-` = ±1, `Ctrl+Shift+"+/-"` = ±10.
- The spinner continues to control the SMA Low line period used by the short strategy entry signal.
- The `sma` URL parameter name is unchanged; the form input id `sma-input` is unchanged.

#### Scenario: Shift shortcut increments by 7
- **WHEN** the SMA period LOW spinner is focused and the user presses `Shift + "+"`
- **THEN** the spinner value SHALL increase by 7

#### Scenario: Shift shortcut decrements by 7
- **WHEN** the SMA period LOW spinner is focused and the user presses `Shift + "-"`
- **THEN** the spinner value SHALL decrease by 7

#### Scenario: Default value is 7
- **WHEN** an asset detail page is loaded without an explicit `sma` URL parameter
- **THEN** the SMA period LOW spinner SHALL display 7

---

### Requirement: New SMA period HIGH spinner
A second spinner labelled **"SMA period HIGH"** SHALL be added to the Chart & Trades tab, below the SMA period LOW spinner.
- Default value SHALL be **7**.
- Range: 1 – 500.
- Keyboard shortcuts SHALL match SMA period LOW: `+/-` = ±1, `Shift+"+/-"` = ±7, `Ctrl+Shift+"+/-"` = ±10.
- Its value SHALL be submitted as the `sma_high` URL parameter.
- The spinner SHALL use the form input id `sma-high-input`.
- On non-chart tabs (Performance, Fundamentals, Order) a hidden `sma-high-input` SHALL be present so the value survives tab switching.
- The `sma_high` value SHALL be passed to `prepare_chart_data()` to control the SMA High line period independently.

#### Scenario: SMA HIGH spinner is present on chart tab
- **WHEN** the Chart & Trades tab is active
- **THEN** a visible "SMA period HIGH" spinner SHALL be rendered with its current value

#### Scenario: SMA HIGH value persists on tab switch
- **WHEN** the user switches to the Performance tab and back to Chart & Trades
- **THEN** the `sma_high` value SHALL be the same as before the tab switch

#### Scenario: SMA HIGH controls SMA High line period
- **WHEN** the user changes the SMA period HIGH spinner value
- **THEN** the chart SHALL reload with the SMA High line computed using the new period

#### Scenario: Default sma_high is 7
- **WHEN** an asset detail page is loaded without an explicit `sma_high` URL parameter
- **THEN** the SMA period HIGH spinner SHALL display 7

---

### Requirement: prepare_chart_data accepts independent sma_high_period
`prepare_chart_data()` in `draw_chart.py` SHALL accept a `sma_high_period: int = 7` parameter (in addition to the existing `sma_period` which drives SMA Low and SMA Close).
The SMA High line SHALL be computed using `sma_high_period`; the SMA Low and SMA Close lines SHALL continue to use `sma_period`.

#### Scenario: SMA High uses independent period
- **WHEN** `prepare_chart_data()` is called with `sma_period=7` and `sma_high_period=21`
- **THEN** the returned sma_high values SHALL be a 21-period SMA of daily highs
- **AND** the returned sma_low values SHALL be a 7-period SMA of daily lows
