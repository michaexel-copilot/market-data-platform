"""Ingestion jobs — per-interval async fetch-and-write tasks."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx

from market_data.connectors import registry
from market_data.db.asset_not_found import load_blocked, record_not_found
from market_data.db.connection import get_connection
from market_data.ingestion.writer import write_ohlcv
from market_data.models.enums import AssetClass, Interval

logger = logging.getLogger(__name__)

# How far back each scheduler job looks when catching up after a restart
_LOOKBACK: dict[Interval, timedelta] = {
    Interval.ONE_MIN:  timedelta(minutes=5),
    Interval.FIVE_MIN: timedelta(minutes=30),
    Interval.ONE_HOUR: timedelta(hours=12),  # covers providers with multi-hour data lag (e.g. EODHD ~4-5h)
    Interval.ONE_DAY:  timedelta(days=3),
}

# Duration of one bar for each interval (used for gap detection)
_INTERVAL_DELTA: dict[Interval, timedelta] = {
    Interval.ONE_MIN:  timedelta(minutes=1),
    Interval.FIVE_MIN: timedelta(minutes=5),
    Interval.ONE_HOUR: timedelta(hours=1),
    Interval.ONE_DAY:  timedelta(days=1),
}

# How far back to scan for historical gaps when fill_gaps=True
_GAP_LOOKBACK: dict[Interval, timedelta] = {
    Interval.ONE_MIN:  timedelta(hours=24),
    Interval.FIVE_MIN: timedelta(days=7),
    Interval.ONE_HOUR: timedelta(days=30),
    Interval.ONE_DAY:  timedelta(days=365),
}


def _align_to_interval(dt: datetime, interval: Interval) -> datetime:
    """Truncate *dt* down to the nearest interval boundary (UTC)."""
    dt = dt.astimezone(timezone.utc)
    if interval == Interval.ONE_MIN:
        return dt.replace(second=0, microsecond=0)
    if interval == Interval.FIVE_MIN:
        return dt.replace(minute=(dt.minute // 5) * 5, second=0, microsecond=0)
    if interval == Interval.ONE_HOUR:
        return dt.replace(minute=0, second=0, microsecond=0)
    if interval == Interval.ONE_DAY:
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return dt


def _find_gaps(
    db,
    instrument_id: str,
    interval: Interval,
    since: datetime,
    until: datetime,
) -> list[tuple[datetime, datetime]]:
    """Return contiguous ranges of missing OHLCV data within [since, until].

    Compares the expected timestamp series (every *interval*) against all rows
    already in the ``ohlcv`` table for *instrument_id* (any source).  Uses
    PostgreSQL ``generate_series`` so the heavy lifting stays server-side.

    Returns a list of ``(gap_start, gap_end)`` tuples where both endpoints are
    the first/last *missing* timestamp in their contiguous run.
    """
    if since >= until:
        return []

    aligned_since = _align_to_interval(since, interval)
    interval_str = str(interval)
    delta = _INTERVAL_DELTA[interval]

    rows = db.execute(
        """
        WITH expected AS (
            SELECT generate_series(
                %s::timestamptz,
                %s::timestamptz,
                %s::interval
            ) AS ts
        ),
        actual AS (
            SELECT DISTINCT ts
            FROM ohlcv
            WHERE instrument_id = %s
              AND interval = %s
              AND ts BETWEEN %s AND %s
        )
        SELECT e.ts
        FROM expected e
        LEFT JOIN actual a ON a.ts = e.ts
        WHERE a.ts IS NULL
        ORDER BY e.ts
        """,
        [aligned_since, until, interval_str, instrument_id, interval_str, aligned_since, until],
    ).fetchall()

    if not rows:
        return []

    # Group consecutive missing timestamps into (start, end) ranges.
    # Where two adjacent missing timestamps are more than one delta apart,
    # there is existing data in between — start a new gap range.
    gaps: list[tuple[datetime, datetime]] = []
    gap_start = rows[0][0]
    prev_ts = rows[0][0]
    for (ts,) in rows[1:]:
        if ts - prev_ts > delta:
            gaps.append((gap_start, prev_ts))
            gap_start = ts
        prev_ts = ts
    gaps.append((gap_start, prev_ts))
    return gaps


def _active_instrument_ids(asset_class: AssetClass | None = None) -> list[str]:
    """Return instrument_ids for all active instruments tracked in the database."""
    conn = get_connection()
    if asset_class is not None:
        rows = conn.execute(
            "SELECT instrument_id FROM instruments WHERE is_active = TRUE AND asset_class = %s",
            [str(asset_class)],
        ).fetchall()
    else:
        rows = conn.execute("SELECT instrument_id FROM instruments WHERE is_active = TRUE").fetchall()
    return [r[0] for r in rows]


async def _run_interval_job(
    interval: Interval,
    *,
    connector_name: str | None = None,
    instrument_id: str | None = None,
    asset_class: AssetClass | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    fill_gaps: bool = False,
) -> dict[str, int]:
    _until = until or datetime.now(tz=timezone.utc)
    _since = since or (_until - _LOOKBACK[interval])
    connectors = registry.by_interval(interval)

    if connector_name is not None:
        connectors = [c for c in connectors if c.name == connector_name]
        if not connectors:
            raise ValueError(
                f"Connector {connector_name!r} is not registered or does not support interval {interval}"
            )

    instrument_ids = [instrument_id] if instrument_id is not None else _active_instrument_ids(asset_class)
    if not instrument_ids:
        logger.debug("No active instruments — skipping %s job", interval)
        return {"written": 0, "errors": 0, "skipped": 0}

    db = get_connection()
    blocked = load_blocked(db, str(interval))
    # When fill_gaps is on, scan backwards from _until to detect all missing ranges.
    # We scan the full [gap_scan_since, _until] window so gaps anywhere — historical
    # or within the recent lookback — are all found in one pass.
    gap_scan_since = _until - _GAP_LOOKBACK[interval] if fill_gaps else None

    written_total = 0
    error_count = 0
    skipped_count = 0

    for conn in connectors:
        connector_done = False
        for inst_id in instrument_ids:
            if connector_done:
                break
            if (inst_id, conn.name) in blocked:
                skipped_count += 1
                continue

            # Build an ordered list of (since, until) windows to fetch.
            # With fill_gaps: scan the full [gap_scan_since, _until] range and
            # fetch only the missing segments (gap ranges).  The recent window
            # is included automatically — if recent data is also missing it shows
            # up as a gap; if it's already present it isn't fetched again.
            # Without fill_gaps: just fetch the single normal [_since, _until] window.
            windows: list[tuple[datetime, datetime]] = []
            if gap_scan_since is not None:
                gaps = _find_gaps(db, inst_id, interval, gap_scan_since, _until)
                if gaps:
                    logger.info(
                        "[%s] %s via %s: %d gap range(s) detected, filling back to %s",
                        interval,
                        inst_id,
                        conn.name,
                        len(gaps),
                        gaps[0][0].isoformat(),
                    )
                windows.extend(gaps)
            else:
                windows.append((_since, _until))

            instrument_done = False
            for w_since, w_until in windows:
                if instrument_done:
                    break
                try:
                    records = await conn.fetch_ohlcv(inst_id, interval, w_since, w_until)
                    if records:
                        written = write_ohlcv(records)
                        written_total += written
                        logger.debug(
                            "[%s] %s via %s [%s – %s]: %d records",
                            interval,
                            inst_id,
                            conn.name,
                            w_since.isoformat(),
                            w_until.isoformat(),
                            written,
                        )
                except NotImplementedError:
                    skipped_count += 1
                    instrument_done = True
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 403:
                        logger.error(
                            "[%s] %s via %s: 403 Forbidden — disabling connector",
                            interval,
                            inst_id,
                            conn.name,
                        )
                        registry.disable(conn.name)
                        error_count += 1
                        instrument_done = True
                        connector_done = True
                    elif exc.response.status_code == 429:
                        logger.warning(
                            "[%s] %s via %s: 429 Too Many Requests — skipping for this run",
                            interval,
                            inst_id,
                            conn.name,
                        )
                        skipped_count += 1
                        instrument_done = True
                        connector_done = True
                    elif exc.response.status_code == 404:
                        url = str(exc.response.request.url)
                        record_not_found(db, inst_id, conn.name, str(interval), url)
                        logger.info(
                            "[%s] %s via %s: 404 Not Found — recorded and suppressed (%s)",
                            interval,
                            inst_id,
                            conn.name,
                            url,
                        )
                        skipped_count += 1
                        instrument_done = True
                    else:
                        logger.warning(
                            "[%s] %s via %s failed: %s",
                            interval,
                            inst_id,
                            conn.name,
                            exc,
                        )
                        error_count += 1
                        instrument_done = True
                except Exception as exc:
                    logger.warning(
                        "[%s] %s via %s failed: %s",
                        interval,
                        inst_id,
                        conn.name,
                        exc,
                    )
                    error_count += 1
                    instrument_done = True

    return {"written": written_total, "errors": error_count, "skipped": skipped_count}


async def run_1m_job() -> None:
    """Fetch and persist 1-minute OHLCV data for all active instruments."""
    await _run_interval_job(Interval.ONE_MIN)


async def run_5m_job() -> None:
    """Fetch and persist 5-minute OHLCV data for all active instruments."""
    await _run_interval_job(Interval.FIVE_MIN)


async def run_1h_job() -> None:
    """Fetch and persist 1-hour OHLCV data for all active instruments."""
    await _run_interval_job(Interval.ONE_HOUR)


async def run_1d_job() -> None:
    """Fetch and persist 1-day OHLCV data for all active instruments."""
    await _run_interval_job(Interval.ONE_DAY)
