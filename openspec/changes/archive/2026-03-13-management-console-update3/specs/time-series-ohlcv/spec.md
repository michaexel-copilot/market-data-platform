## NEW Requirements

### Requirement: OHLCV availability endpoint
The system SHALL expose a `GET /v1/instruments/{symbol}/ohlcv-availability` endpoint that returns the first and last available timestamp per OHLCV interval for the given instrument. The response SHALL include entries for native intervals (`1m`, `5m`, `1h`, `1d`) queried from the `ohlcv` table, and derived intervals (`1w` from `ohlcv_weekly`, `4w` approximated from weekly data in 4-week buckets, `1mth` from `ohlcv_monthly`, `1y` and `1ytd` from daily data). Intervals with no data SHALL be omitted from the response.

Response schema:
```json
{
  "instrument_id": "<id>",
  "intervals": {
    "<interval>": { "first": "<ISO8601>", "last": "<ISO8601>" }
  }
}
```

#### Scenario: Availability returned for populated instrument
- **WHEN** `GET /v1/instruments/bitcoin/ohlcv-availability` is called and the `ohlcv` table contains `1d` rows for `bitcoin`
- **THEN** the response contains an `intervals.1d` entry with `first` and `last` timestamps

#### Scenario: Empty instrument returns empty intervals
- **WHEN** `GET /v1/instruments/{symbol}/ohlcv-availability` is called and no OHLCV rows exist for that instrument
- **THEN** the response is `{ "instrument_id": "<id>", "intervals": {} }`

#### Scenario: Unknown symbol returns 404
- **WHEN** `GET /v1/instruments/nonexistent/ohlcv-availability` is called
- **THEN** the API returns HTTP 404
