# Spec: indicator-selector

## Purpose

Defines the indicator and exposure selection controls in the strategy-controls accordion, including dropdowns, period-range inputs, date inputs, and the backend endpoints that serve the option lists.

## Requirements

### Requirement: Indicator options served by dedicated endpoints
The system SHALL expose `GET /indicators` and `GET /exposures` endpoints that return JSON arrays of available options. These SHALL be the canonical source for populating the indicator and exposure dropdowns in the UI.

#### Scenario: GET /indicators returns all three indicator types
- **WHEN** a GET request is made to `/indicators`
- **THEN** the response SHALL be a JSON array containing objects with `id` and `label` for: `{"id":"price","label":"Price"}`, `{"id":"sma","label":"Simple Moving Average (SMA)"}`, `{"id":"ema","label":"EMA"}`

#### Scenario: GET /exposures returns all three exposure modes
- **WHEN** a GET request is made to `/exposures`
- **THEN** the response SHALL be a JSON array containing objects with `id` and `label` for: `{"id":"long_cash","label":"Long+Cash"}`, `{"id":"short_cash","label":"Short+Cash"}`, `{"id":"long_short","label":"Long+Short"}`

---

### Requirement: Indicator 1 dropdown with default value Price
The strategy-controls accordion body SHALL contain a dropdown (Indicator 1) populated via `/indicators`. The default selected value SHALL be `price` (Price).

#### Scenario: Indicator 1 dropdown rendered with Price selected
- **WHEN** the strategy-controls accordion is rendered
- **THEN** the Indicator 1 `<select>` SHALL show "Price" as the initially selected option

---

### Requirement: Indicator 2 dropdown with default value SMA
The strategy-controls accordion body SHALL contain a dropdown (Indicator 2) populated via `/indicators`, excluding the `price` option. The default selected value SHALL be `sma` (Simple Moving Average).

#### Scenario: Indicator 2 dropdown rendered with SMA selected
- **WHEN** the strategy-controls accordion is rendered
- **THEN** the Indicator 2 `<select>` SHALL show "Simple Moving Average (SMA)" as the initially selected option

#### Scenario: Price is not available as Indicator 2
- **WHEN** the Indicator 2 dropdown is rendered
- **THEN** the `price` option SHALL NOT appear in Indicator 2's option list

---

### Requirement: Period range inputs shown/hidden based on indicator selection
When Indicator 1 is `price`, no period-range inputs SHALL be displayed for Indicator 1. When Indicator 1 is `sma` or `ema`, two numeric inputs (min period, max period) SHALL be shown with defaults 1 and 200. The same SHALL apply to Indicator 2.

#### Scenario: Indicator 1 = Price hides period inputs
- **WHEN** the user selects "Price" for Indicator 1
- **THEN** the Indicator 1 period range inputs SHALL be hidden

#### Scenario: Indicator 1 = SMA shows period inputs
- **WHEN** the user selects "Simple Moving Average (SMA)" for Indicator 1
- **THEN** two numeric inputs (min period = 1, max period = 200) SHALL be shown for Indicator 1

#### Scenario: Indicator 2 period inputs always visible
- **WHEN** the strategy-controls accordion is rendered
- **THEN** the Indicator 2 period range inputs (min period = 1, max period = 200) SHALL be visible by default

---

### Requirement: Exposure dropdown
The strategy-controls accordion body SHALL contain an Exposure dropdown populated via `/exposures`. The default selected value SHALL be `long_cash`.

#### Scenario: Exposure defaults to Long+Cash
- **WHEN** the strategy-controls accordion is rendered
- **THEN** the Exposure `<select>` SHALL show "Long+Cash" as the initially selected option

---

### Requirement: Adjustable train/validation date range inputs
The accordion SHALL contain two date inputs: training cutoff (default `2024-12-31`) and validation start (default `2025-01-01`). Both SHALL be editable by the user before running the backtest.

#### Scenario: Train end date defaults to 2024-12-31
- **WHEN** the strategy-controls accordion is rendered
- **THEN** the train-end date input SHALL show `2024-12-31`

#### Scenario: Validation start date defaults to 2025-01-01
- **WHEN** the strategy-controls accordion is rendered
- **THEN** the validation-start date input SHALL show `2025-01-01`
