"""OHLCV cache importer — reads locally-cached provider files and upserts into ``ohlcv``."""
from __future__ import annotations

import csv
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from market_data.models.enums import Interval
from market_data.models.ohlcv import OHLCVRecord

logger = logging.getLogger(__name__)

# Interval → (data_class, interval_label) as defined in design.md
_INTERVAL_FOLDER_MAP: dict[str, tuple[str, str]] = {
    "1m": ("intraday_historical_data", "1-minute"),
    "5m": ("intraday_historical_data", "5-minute"),
    "1h": ("intraday_historical_data", "1-hour"),
    "1d": ("eod_historical_data", "1-day"),
}


def get_cache_path(source_short_name: str, interval: str) -> Path:
    """Return the expected cache folder path for *source_short_name* and *interval*.

    The root is controlled by ``APPDATA_DIR`` (default ``/appdata``).
    """
    appdata = Path(os.getenv("APPDATA_DIR", "/appdata"))
    mapping = _INTERVAL_FOLDER_MAP.get(interval)
    if mapping is None:
        raise ValueError(f"Unsupported interval for cache import: {interval!r}")
    data_class, interval_label = mapping
    return appdata / source_short_name / data_class / interval_label


def _find_matching_files(folder: Path, instrument_id: str, ticker: str) -> list[Path]:
    """Return `.json` and `.csv` files in *folder* whose stem matches *instrument_id* or *ticker*."""
    targets = {instrument_id.lower(), ticker.lower()}
    matches: list[Path] = []
    for ext in ("*.json", "*.csv"):
        for path in folder.glob(ext):
            if path.stem.lower() in targets:
                matches.append(path)
    return sorted(matches)


def _parse_timestamp(value: str) -> datetime:
    """Parse intraday ``"YYYY-MM-DD HH:MM:SS"`` or EOD ``"YYYY-MM-DD"`` to UTC datetime."""
    value = value.strip()
    if len(value) == 10:
        # Date-only: EOD
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    # Try with time component
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            dt = datetime.strptime(value, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"Unrecognised timestamp format: {value!r}")


def _record_from_row(
    row: dict,
    instrument_id: str,
    interval: str,
    source: str,
) -> OHLCVRecord | None:
    """Convert a raw dict row to an ``OHLCVRecord``. Returns ``None`` if required fields are missing."""
    ts_raw = row.get("datetime") or row.get("date")
    if ts_raw is None:
        return None
    try:
        ts = _parse_timestamp(str(ts_raw))
    except ValueError as exc:
        logger.warning("Skipping row with unparseable timestamp %r: %s", ts_raw, exc)
        return None

    try:
        return OHLCVRecord(
            instrument_id=instrument_id,
            interval=Interval(interval),
            ts=ts,
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["volume"]) if row.get("volume") is not None else None,
            vwap=float(row["vwap"]) if row.get("vwap") is not None else None,
            trade_count=int(row["trade_count"]) if row.get("trade_count") is not None else None,
            market_cap=float(row["market_cap"]) if row.get("market_cap") is not None else None,
            source=source,
        )
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning("Skipping malformed row: %s", exc)
        return None


def _parse_json(path: Path, instrument_id: str, interval: str, source: str) -> list[OHLCVRecord]:
    """Parse a JSON file containing an array of OHLCV objects."""
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        logger.warning("JSON file %s does not contain a list — skipping", path)
        return []
    records: list[OHLCVRecord] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        rec = _record_from_row(row, instrument_id, interval, source)
        if rec is not None:
            records.append(rec)
    return records


def _parse_csv(path: Path, instrument_id: str, interval: str, source: str) -> list[OHLCVRecord]:
    """Parse a CSV file with a header row containing OHLCV columns."""
    records: list[OHLCVRecord] = []
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            # Normalise keys to lowercase
            normalised = {k.lower().strip(): v for k, v in row.items()}
            rec = _record_from_row(normalised, instrument_id, interval, source)
            if rec is not None:
                records.append(rec)
    return records


def _insert_file_fast(
    path: Path,
    instrument_id: str,
    interval: str,
    source_short_name: str,
    conn,  # kept for API compatibility; not used directly (write_ohlcv uses get_connection())
) -> int:
    """Parse a cached OHLCV file and upsert records into ``ohlcv`` via write_ohlcv.

    Returns the number of records processed.
    """
    from market_data.ingestion.writer import write_ohlcv

    is_json = path.suffix.lower() == ".json"
    if is_json:
        records = _parse_json(path, instrument_id, interval, source_short_name)
    else:
        records = _parse_csv(path, instrument_id, interval, source_short_name)

    if records:
        write_ohlcv(records)
    return len(records)


def import_from_cache(
    instrument_id: str,
    ticker: str,
    source_short_name: str,
    interval: str,
    conn,  # kept for API compatibility; not used directly
) -> dict:
    """Import OHLCV data for *instrument_id* from the local cache folder.

    Returns a dict with one of these shapes:

    - ``{status: "ok", rows_imported: N, files_processed: M}``
    - ``{status: "folder_not_found", expected_path: "..."}``
    """
    try:
        folder = get_cache_path(source_short_name, interval)
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}

    if not folder.exists():
        return {"status": "folder_not_found", "expected_path": str(folder)}

    matching_files = _find_matching_files(folder, instrument_id, ticker)
    if not matching_files:
        logger.info("No matching cache files for %s in %s", instrument_id, folder)
        return {"status": "ok", "rows_imported": 0, "files_processed": 0}

    rows_imported = 0
    files_processed = 0
    for path in matching_files:
        try:
            n = _insert_file_fast(path, instrument_id, interval, source_short_name, conn)
            rows_imported += n
            files_processed += 1
            logger.info("Inserted/updated %d rows from %s", n, path)
        except Exception as exc:
            logger.error("Failed to import %s: %s", path, exc)

    return {
        "status": "ok",
        "rows_imported": rows_imported,
        "files_processed": files_processed,
    }
