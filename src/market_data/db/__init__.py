"""Database package — exposes migrate() as the uv run migrate entry point."""
from market_data.db.migrate import migrate

__all__ = ["migrate"]
