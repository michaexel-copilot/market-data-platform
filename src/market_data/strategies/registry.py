"""Strategy registry — maps strategy names to callable compute functions."""
from __future__ import annotations

from typing import Callable

from market_data.strategies.best_sma import compute_best_sma

STRATEGY_REGISTRY: dict[str, Callable[[str, dict | None], dict]] = {
    "best_sma": compute_best_sma,
}
