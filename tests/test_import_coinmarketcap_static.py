"""Tests for the CoinMarketCap static importer."""
from __future__ import annotations

import csv
import logging
from datetime import datetime, timezone
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers to create fixture TSV files
# ---------------------------------------------------------------------------

SNAPSHOT_TS = datetime(2025, 8, 5, 11, 12, 20, tzinfo=timezone.utc)
PREFIX = "2025-08-05_111220"


def _write_listing(directory: Path) -> Path:
    path = directory / f"{PREFIX}_listing_data.tsv"
    rows = [
        {
            "id": "1",
            "name": "Bitcoin",
            "symbol": "BTC",
            "slug": "bitcoin",
            "num_market_pairs": "12275",
            "date_added": "2010-07-13T00:00:00.000Z",
            "tags": "['mineable', 'pow', 'sha-256']",
            "max_supply": "21000000",
            "circulating_supply": "19902171",
            "total_supply": "19902171",
            "infinite_supply": "False",
            "platform": "",
            "cmc_rank": "1",
            "self_reported_circulating_supply": "",
            "self_reported_market_cap": "",
            "tvl_ratio": "",
            "last_updated": "2025-08-05T09:11:00.000Z",
            "price": "114344,90",
            "volume_24h": "56596793048,34",
            "volume_change_24h": "17,34",
            "percent_change_1h": "0,32",
            "percent_change_24h": "-0,29",
            "percent_change_7d": "-3,86",
            "percent_change_30d": "5,79",
            "percent_change_60d": "10,35",
            "percent_change_90d": "17,91",
            "market_cap": "2275711791574,03",
            "market_cap_dominance": "60,88",
            "fully_diluted_market_cap": "2401242940936,18",
            "tvl": "",
        },
        {
            "id": "1027",
            "name": "Ethereum",
            "symbol": "ETH",
            "slug": "ethereum",
            "num_market_pairs": "10429",
            "date_added": "2015-08-07T00:00:00.000Z",
            "tags": "['pos', 'smart-contracts']",
            "max_supply": "",
            "circulating_supply": "120709546,70",
            "total_supply": "120709546,70",
            "infinite_supply": "True",
            "platform": "",
            "cmc_rank": "2",
            "self_reported_circulating_supply": "",
            "self_reported_market_cap": "",
            "tvl_ratio": "",
            "last_updated": "2025-08-05T09:10:00.000Z",
            "price": "3638,88",
            "volume_24h": "31825798039,84",
            "volume_change_24h": "38,30",
            "percent_change_1h": "0,67",
            "percent_change_24h": "2,38",
            "percent_change_7d": "-6,13",
            "percent_change_30d": "44,68",
            "percent_change_60d": "47,66",
            "percent_change_90d": "97,76",
            "market_cap": "439247363197,45",
            "market_cap_dominance": "11,75",
            "fully_diluted_market_cap": "439247363197,45",
            "tvl": "",
        },
    ]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    return path


def _write_map(directory: Path) -> Path:
    path = directory / f"{PREFIX}_map_data.tsv"
    rows = [
        {"id": "1", "rank": "1", "name": "Bitcoin", "symbol": "BTC", "slug": "bitcoin",
         "is_active": "1", "status": "1", "first_historical_data": "2010-07-13T00:05:00.000Z",
         "last_historical_data": "2025-08-05T08:55:00.000Z", "platform": ""},
        {"id": "1027", "rank": "2", "name": "Ethereum", "symbol": "ETH", "slug": "ethereum",
         "is_active": "1", "status": "1", "first_historical_data": "2015-08-07T00:00:00.000Z",
         "last_historical_data": "2025-08-05T08:55:00.000Z", "platform": ""},
    ]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    return path


def _write_categories(directory: Path) -> Path:
    path = directory / f"{PREFIX}_categories_data.tsv"
    rows = [
        {"id": "cat001", "name": "Layer 1", "title": "Layer 1", "description": "L1 chains",
         "num_tokens": "50", "avg_price_change": "1,23", "market_cap": "5000000000,00",
         "market_cap_change": "0,50", "volume": "100000000,00", "volume_change": "5,00",
         "last_updated": "2025-08-05T09:00:00.000Z"},
    ]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    return path


def _write_category(directory: Path) -> Path:
    path = directory / f"{PREFIX}_category_data.tsv"
    rows = [
        {"id": "cat001", "name": "Layer 1", "title": "Layer 1", "description": "L1 chains",
         "num_tokens": "50", "last_updated": "2025-08-05T09:00:00.000Z",
         "avg_price_change": "1,23", "market_cap": "5000000000,00",
         "market_cap_change": "0,50", "volume": "100000000,00", "volume_change": "5,00",
         "coins": "{'id': 1, 'name': 'Bitcoin', 'symbol': 'BTC', 'slug': 'bitcoin'}"},
        {"id": "cat001", "name": "Layer 1", "title": "Layer 1", "description": "L1 chains",
         "num_tokens": "50", "last_updated": "2025-08-05T09:00:00.000Z",
         "avg_price_change": "1,23", "market_cap": "5000000000,00",
         "market_cap_change": "0,50", "volume": "100000000,00", "volume_change": "5,00",
         "coins": "{'id': 1027, 'name': 'Ethereum', 'symbol': 'ETH', 'slug': 'ethereum'}"},
    ]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    return path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mem_conn(db_conn):
    """psycopg3 connection with all migrations applied; auto-rollback after each test."""
    yield db_conn


@pytest.fixture()
def snapshot_dir(tmp_path):
    """Temporary directory with one full snapshot set."""
    _write_listing(tmp_path)
    _write_map(tmp_path)
    _write_categories(tmp_path)
    _write_category(tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# Tests: discover_snapshots
# ---------------------------------------------------------------------------

def test_discover_snapshots_finds_full_set(snapshot_dir):
    from market_data.ingestion.import_coinmarketcap_static import discover_snapshots
    snaps = discover_snapshots(snapshot_dir)
    assert len(snaps) == 1
    snap = snaps[0]
    assert snap.snapshot_ts == SNAPSHOT_TS
    assert snap.listing_path.exists()
    assert snap.map_path is not None and snap.map_path.exists()
    assert snap.categories_path is not None and snap.categories_path.exists()
    assert snap.category_path is not None and snap.category_path.exists()


def test_discover_snapshots_missing_sibling(tmp_path):
    from market_data.ingestion.import_coinmarketcap_static import discover_snapshots
    _write_listing(tmp_path)
    # No map/categories/category files
    snaps = discover_snapshots(tmp_path)
    assert len(snaps) == 1
    assert snaps[0].map_path is None
    assert snaps[0].categories_path is None
    assert snaps[0].category_path is None


def test_discover_snapshots_empty_dir(tmp_path):
    from market_data.ingestion.import_coinmarketcap_static import discover_snapshots
    snaps = discover_snapshots(tmp_path)
    assert snaps == []


# ---------------------------------------------------------------------------
# Tests: import_listing_data
# ---------------------------------------------------------------------------

def test_import_listing_data_normalises_comma_decimal(mem_conn, snapshot_dir):
    from market_data.ingestion.import_coinmarketcap_static import import_listing_data, discover_snapshots
    snap = discover_snapshots(snapshot_dir)[0]
    import_listing_data(mem_conn, snap.listing_path, snap.snapshot_ts)
    row = mem_conn.execute(
        "SELECT price FROM cmc_listing_snapshots WHERE cmc_id = 1"
    ).fetchone()
    assert row is not None
    assert abs(row[0] - 114344.90) < 0.01


def test_import_listing_data_parses_tags(mem_conn, snapshot_dir):
    from market_data.ingestion.import_coinmarketcap_static import import_listing_data, discover_snapshots
    snap = discover_snapshots(snapshot_dir)[0]
    import_listing_data(mem_conn, snap.listing_path, snap.snapshot_ts)
    tags = {r[0] for r in mem_conn.execute(
        "SELECT tag FROM cmc_coin_tags WHERE cmc_id = 1"
    ).fetchall()}
    assert "mineable" in tags
    assert "pow" in tags
    assert "sha-256" in tags


def test_import_listing_data_idempotent(mem_conn, snapshot_dir):
    from market_data.ingestion.import_coinmarketcap_static import import_listing_data, discover_snapshots
    snap = discover_snapshots(snapshot_dir)[0]
    import_listing_data(mem_conn, snap.listing_path, snap.snapshot_ts)
    import_listing_data(mem_conn, snap.listing_path, snap.snapshot_ts)  # second run
    count = mem_conn.execute(
        "SELECT count(*) FROM cmc_listing_snapshots"
    ).fetchone()[0]
    assert count == 2  # only 2 coins, not 4


# ---------------------------------------------------------------------------
# Tests: import_map_data
# ---------------------------------------------------------------------------

def test_import_map_data_idempotent(mem_conn, snapshot_dir):
    from market_data.ingestion.import_coinmarketcap_static import import_map_data, discover_snapshots
    snap = discover_snapshots(snapshot_dir)[0]
    import_map_data(mem_conn, snap.map_path)
    import_map_data(mem_conn, snap.map_path)
    count = mem_conn.execute("SELECT count(*) FROM cmc_map").fetchone()[0]
    assert count == 2


# ---------------------------------------------------------------------------
# Tests: import_categories_data and import_category_data
# ---------------------------------------------------------------------------

def test_import_categories_data(mem_conn, snapshot_dir):
    from market_data.ingestion.import_coinmarketcap_static import import_categories_data, discover_snapshots
    snap = discover_snapshots(snapshot_dir)[0]
    import_categories_data(mem_conn, snap.categories_path)
    count = mem_conn.execute("SELECT count(*) FROM cmc_categories").fetchone()[0]
    assert count == 1


def test_import_category_data_upsert(mem_conn, snapshot_dir):
    from market_data.ingestion.import_coinmarketcap_static import import_category_data, discover_snapshots
    snap = discover_snapshots(snapshot_dir)[0]
    import_category_data(mem_conn, snap.category_path)
    count = mem_conn.execute("SELECT count(*) FROM cmc_category_coins").fetchone()[0]
    assert count == 2


def test_import_category_data_malformed_coins_skipped(mem_conn, tmp_path, caplog):
    from market_data.ingestion.import_coinmarketcap_static import import_category_data
    path = tmp_path / "bad_category_data.tsv"
    rows = [
        {"id": "cat001", "name": "X", "title": "X", "description": "", "num_tokens": "1",
         "last_updated": "", "avg_price_change": "", "market_cap": "",
         "market_cap_change": "", "volume": "", "volume_change": "",
         "coins": "INVALID {{{{ NOT A DICT"},
    ]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

    with caplog.at_level(logging.WARNING):
        import_category_data(mem_conn, path)

    count = mem_conn.execute("SELECT count(*) FROM cmc_category_coins").fetchone()[0]
    assert count == 0
    assert any("malformed" in r.message.lower() for r in caplog.records)


# ---------------------------------------------------------------------------
# Tests: run_import end-to-end
# ---------------------------------------------------------------------------

def test_run_import_end_to_end(mem_conn, snapshot_dir, monkeypatch):
    import market_data.db.connection as conn_mod
    import market_data.ingestion.import_coinmarketcap_static as importer_mod
    monkeypatch.setattr(conn_mod, "_conn", mem_conn)
    monkeypatch.setattr(importer_mod, "migrate", lambda: None)

    counts = importer_mod.run_import(snapshot_dir)

    assert counts["listing"] == 2
    assert counts["map"] == 2
    assert counts["categories"] == 1
    assert counts["category_coins"] == 2
    assert counts["skipped"] == 0


def test_run_import_idempotent(mem_conn, snapshot_dir, monkeypatch):
    import market_data.db.connection as conn_mod
    import market_data.ingestion.import_coinmarketcap_static as importer_mod
    monkeypatch.setattr(conn_mod, "_conn", mem_conn)
    monkeypatch.setattr(importer_mod, "migrate", lambda: None)

    importer_mod.run_import(snapshot_dir)
    counts2 = importer_mod.run_import(snapshot_dir)  # second run

    assert counts2["skipped"] == 1  # one snapshot skipped
    listing_count = mem_conn.execute("SELECT count(*) FROM cmc_listing_snapshots").fetchone()[0]
    assert listing_count == 2  # not 4


# ---------------------------------------------------------------------------
# Tests: enrich_instrument_crypto
# ---------------------------------------------------------------------------

def test_enrich_instrument_crypto_matching_slug(mem_conn):
    # Insert a minimal instruments + instrument_crypto row with slug = 'bitcoin'
    mem_conn.execute("""
        INSERT INTO instruments
            (instrument_id, ticker, full_name, asset_class, is_active, first_seen_at, last_updated_at)
        VALUES ('bitcoin', 'BTC', 'Bitcoin', 'crypto', true, now(), now())
    """)
    mem_conn.execute("""
        INSERT INTO instrument_crypto (instrument_id) VALUES ('bitcoin')
    """)
    mem_conn.execute("""
        INSERT INTO cmc_map (cmc_id, rank, name, symbol, slug, is_active, status)
        VALUES (1, 1, 'Bitcoin', 'BTC', 'bitcoin', 1, 1)
    """)

    from market_data.ingestion.import_coinmarketcap_static import enrich_instrument_crypto
    enrich_instrument_crypto(mem_conn)

    row = mem_conn.execute(
        "SELECT cmc_id, cmc_slug, cmc_rank FROM instrument_crypto WHERE instrument_id = 'bitcoin'"
    ).fetchone()
    assert row is not None
    assert row[0] == 1
    assert row[1] == "bitcoin"
    assert row[2] == 1


def test_enrich_instrument_crypto_no_match(mem_conn):
    mem_conn.execute("""
        INSERT INTO cmc_map (cmc_id, rank, name, symbol, slug, is_active, status)
        VALUES (9999, 999, 'Unknown', 'UNK', 'unknown-coin', 1, 1)
    """)

    from market_data.ingestion.import_coinmarketcap_static import enrich_instrument_crypto
    # Should not raise; instruments table has no row for 'unknown-coin'
    enrich_instrument_crypto(mem_conn)

    count = mem_conn.execute("SELECT count(*) FROM instrument_crypto").fetchone()[0]
    assert count == 0
