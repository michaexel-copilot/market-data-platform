## ADDED Requirements

### Requirement: Backtest tracks max adverse and favourable excursion per trade
For each closed trade, `backtest_strategy()` SHALL compute:
- `max_adverse_pnl`: the worst unrealised P&L that occurred during the holding period, expressed in USD using the same formula as the final P&L. For a winning trade (exit profit) this is the most negative unrealised P&L (highest intra-period close minus entry). For a losing trade (exit at stop-loss) this is the most positive unrealised P&L (lowest intra-period close minus entry).
- `max_favourable_pnl`: the best unrealised P&L during the holding period. For a winning trade this is the largest positive unrealised gain; for a losing trade this is the closest the trade came to profit.

Both values SHALL be `None` for open trades (no exit yet).
Computation uses the daily **close** prices observed on each candle from entry (exclusive) through exit (inclusive).

#### Scenario: Winning trade records max adverse excursion
- **WHEN** a trade closes at profit and the daily close was higher than the entry price on at least one candle during the holding period
- **THEN** `max_adverse_pnl` SHALL be negative (a loss value) reflecting the worst unrealised loss

#### Scenario: Losing trade records max favourable excursion
- **WHEN** a trade closes at the stop-loss and the daily close was below the entry price on at least one candle during the holding period
- **THEN** `max_favourable_pnl` SHALL be positive (a gain value) reflecting the best unrealised profit

#### Scenario: Open trades have None for both fields
- **WHEN** a trade has no exit date
- **THEN** `max_adverse_pnl` and `max_favourable_pnl` SHALL both be `None`

---

### Requirement: Trade table shows "Max Δ P&L" column
The trades table in the Chart & Trades tab SHALL include a new column **"Max Δ P&L"** after the existing P&L column.
- For closed trades in profit: display `max_adverse_pnl` (negative, coloured red/danger).
- For closed trades in loss: display `max_favourable_pnl` (positive, coloured green/success).
- For open trades: display `—`.
- Values SHALL be formatted as `%+.2f` (USD, signed), same style as P&L column.
- The column header tooltip or label SHALL indicate the meaning: worst unrealised P&L contra the final outcome.

#### Scenario: Profitable closed trade shows worst unrealised loss
- **WHEN** a closed trade has `pnl > 0` and `max_adverse_pnl` is not None
- **THEN** the Max Δ P&L cell SHALL display `max_adverse_pnl` formatted as a signed USD value in danger (red) colour

#### Scenario: Loss closed trade shows best unrealised gain
- **WHEN** a closed trade has `pnl < 0` and `max_favourable_pnl` is not None
- **THEN** the Max Δ P&L cell SHALL display `max_favourable_pnl` formatted as a signed USD value in success (green) colour

#### Scenario: Open trade shows dash
- **WHEN** `trade.is_open` is True
- **THEN** the Max Δ P&L cell SHALL display `—`
