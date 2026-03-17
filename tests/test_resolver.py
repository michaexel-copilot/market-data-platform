"""Tests for symbol resolver."""
from __future__ import annotations

import pytest

from market_data.models.api import AmbiguousSymbolError, SymbolNotFoundError


@pytest.fixture(autouse=True)
def patched_db(db_conn):
    """Seed test instruments for every resolver test."""
    db_conn.execute(
        """
        INSERT INTO instruments (instrument_id, ticker, exchange, asset_class, is_active)
        VALUES
            ('uuid-btc-001',  'BTC',  'BINANCE', 'crypto', TRUE),
            ('uuid-eth-001',  'ETH',  'BINANCE', 'crypto', TRUE),
            ('uuid-aapl-001', 'AAPL', 'XNAS',    'equity', TRUE),
            ('uuid-aapl-002', 'AAPL', 'XNYS',    'equity', TRUE)
        """
    )
    yield db_conn


def test_exact_uuid_match():
    from market_data.db.resolver import resolve_symbol
    assert resolve_symbol("uuid-btc-001") == "uuid-btc-001"


def test_ticker_exchange_match():
    from market_data.db.resolver import resolve_symbol
    assert resolve_symbol("AAPL.XNAS") == "uuid-aapl-001"
    assert resolve_symbol("AAPL.XNYS") == "uuid-aapl-002"


def test_unambiguous_loose_ticker():
    from market_data.db.resolver import resolve_symbol
    assert resolve_symbol("BTC") == "uuid-btc-001"


def test_ambiguous_bare_ticker_raises():
    from market_data.db.resolver import resolve_symbol
    with pytest.raises(AmbiguousSymbolError) as exc_info:
        resolve_symbol("AAPL")
    assert "uuid-aapl-001" in exc_info.value.matches
    assert "uuid-aapl-002" in exc_info.value.matches


def test_unknown_symbol_raises():
    from market_data.db.resolver import resolve_symbol
    with pytest.raises(SymbolNotFoundError):
        resolve_symbol("UNKNOWN_TICKER_XYZ")


def test_ticker_same_ticker_different_exchanges_raises(patched_db):
    """Bare ticker present on multiple exchanges raises AmbiguousSymbolError."""
    patched_db.execute(
        "INSERT INTO instruments (instrument_id, ticker, exchange, asset_class, is_active)"
        " VALUES ('dup-001', 'DUP', 'XNAS', 'equity', TRUE)"
    )
    patched_db.execute(
        "INSERT INTO instruments (instrument_id, ticker, exchange, asset_class, is_active)"
        " VALUES ('dup-002', 'DUP', 'XNYS', 'equity', TRUE)"
    )
    from market_data.db.resolver import resolve_symbol
    with pytest.raises(AmbiguousSymbolError):
        resolve_symbol("DUP")
