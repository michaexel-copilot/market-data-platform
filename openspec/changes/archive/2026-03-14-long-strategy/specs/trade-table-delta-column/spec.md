## MODIFIED Requirements

### Requirement: Max Δ P&L column for long trades
The Max Δ P&L column SHALL appear in the long trades table with mirrored excursion semantics: for profit long trades show `max_adverse_pnl` (price fell below entry) in red, or ✓ in green if never adverse; for loss long trades show `max_favourable_pnl` (price rose above entry) in green, or `—` if never favourable. Open trades show `—`.

#### Scenario: Profit long trade — was adverse
- **WHEN** a long trade is profitable but `max_adverse_pnl < 0`
- **THEN** the Max Δ P&L cell shows `max_adverse_pnl` in red

#### Scenario: Profit long trade — never adverse
- **WHEN** a long trade is profitable and `max_adverse_pnl >= 0`
- **THEN** the Max Δ P&L cell shows ✓ in green

#### Scenario: Loss long trade — was favourable
- **WHEN** a long trade is a loss and `max_favourable_pnl > 0`
- **THEN** the Max Δ P&L cell shows `max_favourable_pnl` in green

#### Scenario: Loss long trade — never favourable
- **WHEN** a long trade is a loss and `max_favourable_pnl <= 0`
- **THEN** the Max Δ P&L cell shows `—`
