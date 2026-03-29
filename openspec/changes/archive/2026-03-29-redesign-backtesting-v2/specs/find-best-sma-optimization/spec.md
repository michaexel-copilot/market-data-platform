## REMOVED Requirements

### Requirement: Find Best SMA button triggers optimization search
**Reason**: Superseded by the new `backtest-param-optimization` capability. The new "Run Backtest" button and `POST /asset/{symbol}/backtest` endpoint replace this functionality with a more flexible, multi-indicator, `backtesting.py`-powered approach.
**Migration**: Use the new "Run Backtest" button in the strategy-controls accordion with Indicator 1 = Price, Indicator 2 = SMA, Exposure = Short+Cash to approximate the former behaviour.

---

### Requirement: Backend endpoint searches SMA grid
**Reason**: Replaced by `POST /asset/{symbol}/backtest` which uses `backtesting.py` `Backtest.optimize()`.
**Migration**: Call `POST /asset/{symbol}/backtest` with appropriate indicator and exposure parameters.

---

### Requirement: Spinner values updated after search
**Reason**: The new backtest flow displays results inline in `#backtest-results` rather than updating the SMA spinner inputs.
**Migration**: Results are displayed in the validation trade table; the SMA spinner inputs are no longer present in the strategy-controls accordion.

---

### Requirement: Auto-trigger fires exactly once per ticker selection
**Reason**: Auto-triggering the SMA optimisation on ticker selection is removed along with the SMA spinner UI.
**Migration**: The user explicitly clicks "Run Backtest" to trigger optimisation.
