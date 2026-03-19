"""Strategy registry — maps strategy names to callable compute functions."""
from __future__ import annotations

from typing import Callable

from market_data.strategies.best_sma import compute_best_sma
from market_data.strategies.best_sma_exit_v1 import compute_best_sma_exit_v1

STRATEGY_REGISTRY: dict[str, Callable[[str, dict | None], dict]] = {
    "best_sma": compute_best_sma,
    "best_sma_exit_v1": compute_best_sma_exit_v1,
}
