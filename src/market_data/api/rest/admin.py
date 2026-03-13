"""Admin REST router — management operations not part of the public API."""
from __future__ import annotations

from fastapi import APIRouter

from market_data.db.connection import get_connection
from market_data.db.migrate import migrate
from market_data.ingestion.migrate_fundamentals import migrate_fundamentals

router = APIRouter(prefix="/v1/admin", tags=["admin"])


@router.post("/migrate-fundamentals")
async def run_migrate_fundamentals() -> dict:
    """Promote latest CoinMarketCap static data into canonical tables.

    Idempotent — safe to call multiple times.
    Returns ``{promoted, skipped, errors}``.
    """
    migrate()
    conn = get_connection()
    return migrate_fundamentals(conn)
