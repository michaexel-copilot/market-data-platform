-- 018_timescaledb_setup.sql
-- Enable the TimescaleDB extension.
-- NOTE: Requires superuser. If this fails, run as postgres superuser first:
--   psql -U postgres -d market_data_platform -c "CREATE EXTENSION timescaledb;"
-- The migration runner also attempts this automatically before running migrations.

CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
