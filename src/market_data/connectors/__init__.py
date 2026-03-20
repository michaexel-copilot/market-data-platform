"""Connector auto-discovery registry.

At import time, scans all sibling modules for a module-level ``connector``
object and registers it by name, asset class, and interval.

Usage::

    from market_data.connectors import registry

    # All connectors supporting crypto
    crypto_connectors = registry.by_asset_class(AssetClass.CRYPTO)

    # A specific connector by name
    cg = registry.by_name("coingecko")
"""
from __future__ import annotations

import importlib
import logging
import pkgutil
from pathlib import Path
from typing import Iterator

from market_data.connectors.protocol import Connector
from market_data.models.enums import AssetClass, Interval

logger = logging.getLogger(__name__)

_SKIP_MODULES = {"__init__", "protocol", "base", "rate_limiter"}


class ConnectorRegistry:
    def __init__(self) -> None:
        self._by_name: dict[str, Connector] = {}
        self._disabled: set[str] = set()
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        package_dir = Path(__file__).parent
        for mod_info in pkgutil.iter_modules([str(package_dir)]):
            if mod_info.name in _SKIP_MODULES:
                continue
            full_name = f"market_data.connectors.{mod_info.name}"
            try:
                module = importlib.import_module(full_name)
                conn = getattr(module, "connector", None)
                if conn is not None and isinstance(conn, Connector):
                    self._by_name[conn.name] = conn
                    logger.debug("Registered connector: %s", conn.name)
            except Exception as exc:
                logger.warning("Failed to load connector module %s: %s", full_name, exc)

    def disable(self, name: str) -> None:
        """Permanently disable a connector for the lifetime of this process."""
        if name not in self._disabled:
            self._disabled.add(name)
            logger.error("Connector '%s' has been disabled and will not be retried.", name)

    def _active(self) -> Iterator[Connector]:
        return (c for c in self._by_name.values() if c.name not in self._disabled)

    def by_name(self, name: str) -> Connector | None:
        self._ensure_loaded()
        if name in self._disabled:
            return None
        return self._by_name.get(name)

    def by_asset_class(self, asset_class: AssetClass) -> list[Connector]:
        self._ensure_loaded()
        return [c for c in self._active() if asset_class in c.supported_asset_classes]

    def by_interval(self, interval: Interval) -> list[Connector]:
        self._ensure_loaded()
        return [c for c in self._active() if interval in c.supported_intervals]

    def all(self) -> list[Connector]:
        self._ensure_loaded()
        return list(self._active())

    def __iter__(self) -> Iterator[Connector]:
        self._ensure_loaded()
        return self._active()


registry = ConnectorRegistry()
