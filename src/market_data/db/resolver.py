"""Symbol resolver — three-step priority lookup in PostgreSQL.

Resolution order:
1. Exact UUID match against instruments.instrument_id
2. Exact TICKER.MIC/EXCHANGE match (e.g. AAPL.XNAS)
3. Loose ticker match — raises AmbiguousSymbolError if multiple results
"""
from __future__ import annotations

from market_data.db.connection import get_connection
from market_data.models.api import AmbiguousSymbolError, SymbolNotFoundError
from market_data.models.enums import AssetClass


def resolve_symbol(
    symbol: str,
    asset_class: AssetClass | None = None,
) -> str:
    """Return the canonical instrument_id for *symbol*.

    Args:
        symbol: A UUID, a TICKER.EXCHANGE string, or a bare ticker.
        asset_class: Optional filter to narrow ambiguous bare-ticker lookups.

    Returns:
        The canonical ``instrument_id`` string stored in the database.

    Raises:
        SymbolNotFoundError: When no matching instrument is found.
        AmbiguousSymbolError: When a bare ticker matches more than one instrument.
    """
    conn = get_connection()

    # --- Step 1: exact instrument_id (UUID) match ---
    rows = conn.execute(
        "SELECT instrument_id FROM instruments WHERE instrument_id = %s",
        [symbol],
    ).fetchall()
    if rows:
        return rows[0][0]

    # --- Step 2: TICKER.EXCHANGE format ---
    if "." in symbol:
        parts = symbol.rsplit(".", 1)
        ticker, exchange = parts[0].upper(), parts[1].upper()
        query = "SELECT instrument_id FROM instruments WHERE upper(ticker) = %s AND upper(exchange) = %s"
        params: list[str] = [ticker, exchange]
        if asset_class is not None:
            query += " AND asset_class = %s"
            params.append(str(asset_class))
        rows = conn.execute(query, params).fetchall()
        if len(rows) == 1:
            return rows[0][0]
        if len(rows) > 1:
            raise AmbiguousSymbolError(symbol, [r[0] for r in rows])

    # --- Step 3: loose ticker match ---
    ticker_upper = symbol.upper().split(".")[0]  # strip exchange suffix if present
    query = "SELECT instrument_id FROM instruments WHERE upper(ticker) = %s"
    params = [ticker_upper]
    if asset_class is not None:
        query += " AND asset_class = %s"
        params.append(str(asset_class))
    rows = conn.execute(query, params).fetchall()
    if len(rows) == 1:
        return rows[0][0]
    if len(rows) > 1:
        raise AmbiguousSymbolError(symbol, [r[0] for r in rows])

    raise SymbolNotFoundError(symbol)
