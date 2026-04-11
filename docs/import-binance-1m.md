# Binance 1-Minute Historical OHLCV Importer

Import historical 1-minute OHLCV data from [Binance data.binance.vision](https://data.binance.vision)
into the platform database.

## Overview

Binance publishes free, publicly accessible monthly ZIP archives of kline (candlestick) data
for all spot pairs going back to August 2017.  This two-step workflow downloads the archives
and imports them into the `ohlcv` table as `interval = '1m'` rows attributed to the
`binance_hist` data source.

**No API key is required.**

## Workflow

### Step 1 — Download

```bash
# Download all BTCUSDT 1m monthly archives (2017-08 to last completed month)
download-binance-1m --symbol BTC

# Download a specific date range
download-binance-1m --symbol BTC --from 2020-01 --to 2024-12

# Use a custom local directory
download-binance-1m --symbol BTC --data-dir /mnt/ds420/data/binance/1-minute

# Override the trading-pair symbol (e.g. for an asset priced in BTC rather than USDT)
download-binance-1m --symbol XYZ --pair XYZBTC
```

Archives are saved and extracted to `--data-dir` as:

```
/mnt/ds420/data/binance/1-minute/BTCUSDT-1m-2024-01.csv
/mnt/ds420/data/binance/1-minute/BTCUSDT-1m-2024-02.csv
...
```

Already-downloaded months are skipped automatically (idempotent).

### Step 2 — Import

```bash
# Import all downloaded BTCUSDT 1m CSVs into the database
import-binance-1m --symbol BTC

# Use a custom directory
import-binance-1m --symbol BTC --data-dir /mnt/ds420/data/binance/1-minute
```

The import is idempotent — re-running on the same files will upsert identical values.

## CSV Format

Binance klines CSVs have **no header row**.  Columns:

| # | Name | Description |
|---|------|-------------|
| 0 | `open_time` | Open time (Unix milliseconds) |
| 1 | `open` | Open price |
| 2 | `high` | High price |
| 3 | `low` | Low price |
| 4 | `close` | Close price |
| 5 | `volume` | Base asset volume |
| 6 | `close_time` | Close time (Unix milliseconds) |
| 7 | `quote_asset_volume` | Quote asset volume |
| 8 | `number_of_trades` | Number of trades |
| 9 | `taker_buy_base_vol` | Taker buy base asset volume |
| 10 | `taker_buy_quote_vol` | Taker buy quote asset volume |
| 11 | `ignore` | Unused |

The importer uses columns 0–5 and 8 (`open_time_ms`, `open`, `high`, `low`, `close`,
`volume`, `number_of_trades`).

## Pair Name Resolution

The Binance trading-pair symbol is derived from the instrument's canonical ticker:

1. If `instrument_id` has an entry in `config/binance_pairs.yaml`, that value is used.
2. Otherwise, the pair is constructed as `{TICKER}USDT` (e.g. ticker `ETH` → `ETHUSDT`).

`config/binance_pairs.yaml` lists exceptions (assets that trade against a currency other
than USDT).

## Database

Imported rows land in `ohlcv` with:

| Column | Value |
|--------|-------|
| `interval` | `1m` |
| `source` | `binance` |
| `is_aggregated` | `FALSE` |
| `tick_1m` | `epoch_seconds / 60` |

After a successful import, `ohlcv_data_available` is updated with `has_1m = TRUE` for the
`binance_hist` data source (`data_source_id = 6`).

## Data Availability

| Asset | Pair | Earliest available |
|-------|------|--------------------|
| Bitcoin | BTCUSDT | 2017-08 |
| Ethereum | ETHUSDT | 2017-08 |
| Most major altcoins | {TICKER}USDT | Varies by listing date |

Visit [data.binance.vision](https://data.binance.vision/?prefix=data/spot/monthly/klines/)
to browse available symbols and date ranges.
