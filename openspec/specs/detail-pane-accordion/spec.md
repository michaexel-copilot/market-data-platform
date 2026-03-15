## ADDED Requirements

### Requirement: Detail pane uses accordion layout
The detail pane SHALL render all content sections as a Bootstrap 5 accordion with six independent panels (no mutual-exclusion parent), replacing the previous tab-bar navigation.

#### Scenario: Page loads with default panel states
- **WHEN** the user selects an asset and the detail pane loads
- **THEN** the "Fundamentals" panel (1st) and "Strategy Controls" panel (3rd) are expanded
- **AND** the "Chart" (2nd), "Trades" (4th), "Performance" (5th), and "Place Order" (6th) panels are collapsed

#### Scenario: User expands a collapsed panel
- **WHEN** the user clicks any collapsed accordion panel header
- **THEN** that panel expands to show its content
- **AND** all other panels remain in their current state (panels are independent)

#### Scenario: User collapses an expanded panel
- **WHEN** the user clicks an expanded accordion panel header
- **THEN** that panel collapses
- **AND** all other panels remain in their current state

### Requirement: HTMX state preserved across accordion interactions
The accordion SHALL preserve all HTMX form state (SMA periods, stop-loss values, position size, chart resolution, trade highlight) when panels are expanded or collapsed, without triggering a server reload.

#### Scenario: SMA spinner changed while chart panel is collapsed
- **WHEN** the user changes the SMA LOW or SMA HIGH spinner value
- **THEN** an HTMX request is sent and the detail pane partial is replaced
- **AND** the newly rendered partial has the same accordion structure with the same panels open/closed as before the change

#### Scenario: Trade row clicked to highlight a trade
- **WHEN** the user clicks a row in the Trades table
- **THEN** an HTMX request is sent, the partial reloads, and the matching candle is highlighted in the chart
- **AND** the accordion renders with all panels in their server-rendered default states

### Requirement: Hidden state inputs appear once per partial
Each HTMX hidden input (`sma`, `sma_high`, `sl_short`, `sl_long`, `pos`, `resolution`, `highlight`, `hl_long`, `strategy_tab`) SHALL appear as a single `<input type="hidden">` element with a unique `id` in the rendered partial.

#### Scenario: HTMX include operates correctly
- **WHEN** any spinner or button triggers an HTMX request using `hx-include` with a hidden input id
- **THEN** exactly one value is submitted for that parameter (no duplicate ids in the DOM)

### Requirement: No tab query parameter required for rendering
The detail pane partial SHALL render all six sections unconditionally in a single server response, without requiring a `tab` query parameter to select a branch.

#### Scenario: Request without tab parameter renders full accordion
- **WHEN** a `GET /asset/{symbol}` request is made without a `tab` parameter
- **THEN** all six accordion panels are present in the response HTML

#### Scenario: Request with legacy tab parameter still renders full accordion
- **WHEN** a `GET /asset/{symbol}` request is made with `?tab=chart` or any other tab value
- **THEN** all six accordion panels are present in the response HTML (tab parameter is ignored)
