"""gRPC MarketData servicer implementation."""
from __future__ import annotations

import grpc

from market_data.api.grpc.generated.v1 import market_data_pb2 as pb2
from market_data.api.grpc.generated.v1.market_data_pb2_grpc import MarketDataServiceServicer
from market_data.db.connection import get_connection
from market_data.models.api import AmbiguousSymbolError, SymbolNotFoundError


def _row_to_instrument(row: tuple) -> pb2.Instrument:
    keys = [
        "instrument_id", "ticker", "full_name", "description", "asset_class",
        "exchange", "sector", "industry", "quote_currency", "launch_date",
        "is_active", "logo_url", "website_url",
    ]
    d = dict(zip(keys, row))
    return pb2.Instrument(
        instrument_id=d.get("instrument_id") or "",
        ticker=d.get("ticker") or "",
        full_name=d.get("full_name") or "",
        description=d.get("description") or "",
        exchange=d.get("exchange") or "",
        sector=d.get("sector") or "",
        industry=d.get("industry") or "",
        quote_currency=d.get("quote_currency") or "",
        launch_date=str(d.get("launch_date") or ""),
        is_active=bool(d.get("is_active", True)),
        logo_url=d.get("logo_url") or "",
        website_url=d.get("website_url") or "",
    )


class MarketDataServicer(MarketDataServiceServicer):
    """Concrete implementation of the MarketDataService gRPC service."""

    def ListInstruments(
        self, request: pb2.ListInstrumentsRequest, context: grpc.ServicerContext
    ) -> pb2.ListInstrumentsResponse:
        conn = get_connection()
        conditions = ["is_active = ?"]
        params: list = [request.is_active if request.HasField("is_active") else True]  # type: ignore[attr-defined]

        # In proto3 bools default to False; treat unset as "active only = True"
        params = [True]
        conditions = ["is_active = ?"]

        if request.asset_class != pb2.ASSET_CLASS_UNSPECIFIED:
            ac_name = pb2.AssetClass.Name(request.asset_class).replace("ASSET_CLASS_", "").lower()
            conditions.append("asset_class = ?")
            params.append(ac_name)
        if request.q:
            conditions.append("(upper(ticker) LIKE upper(?) OR upper(full_name) LIKE upper(?))")
            pattern = f"%{request.q}%"
            params.extend([pattern, pattern])

        page = max(request.page, 1)
        page_size = max(request.page_size, 1) if request.page_size > 0 else 50
        offset = (page - 1) * page_size
        where = " AND ".join(conditions)
        total = conn.execute(f"SELECT COUNT(*) FROM instruments WHERE {where}", params).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT instrument_id, ticker, full_name, description, asset_class, exchange,
                   sector, industry, quote_currency, launch_date, is_active, logo_url, website_url
            FROM instruments WHERE {where}
            ORDER BY ticker LIMIT ? OFFSET ?
            """,
            params + [page_size, offset],
        ).fetchall()
        return pb2.ListInstrumentsResponse(
            items=[_row_to_instrument(r) for r in rows],
            total=total,
            page=page,
            page_size=page_size,
        )

    def GetInstrument(
        self, request: pb2.GetInstrumentRequest, context: grpc.ServicerContext
    ) -> pb2.Instrument:
        from market_data.db.resolver import resolve_symbol
        try:
            instrument_id = resolve_symbol(request.symbol)
        except SymbolNotFoundError:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"Symbol not found: {request.symbol!r}")
            return pb2.Instrument()
        except AmbiguousSymbolError as exc:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(str(exc))
            return pb2.Instrument()

        conn = get_connection()
        row = conn.execute(
            """
            SELECT instrument_id, ticker, full_name, description, asset_class, exchange,
                   sector, industry, quote_currency, launch_date, is_active, logo_url, website_url
            FROM instruments WHERE instrument_id = ?
            """,
            [instrument_id],
        ).fetchone()
        if not row:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"Instrument not found: {instrument_id!r}")
            return pb2.Instrument()
        return _row_to_instrument(row)

    def GetOHLCV(
        self, request: pb2.GetOHLCVRequest, context: grpc.ServicerContext
    ):  # type: ignore[override]  # server streaming
        from market_data.db.resolver import resolve_symbol
        try:
            instrument_id = resolve_symbol(request.symbol)
        except SymbolNotFoundError:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"Symbol not found: {request.symbol!r}")
            return
        except AmbiguousSymbolError as exc:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(str(exc))
            return

        if request.interval == pb2.INTERVAL_UNSPECIFIED:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("Interval must be specified")
            return

        iv_name = pb2.Interval.Name(request.interval).replace("INTERVAL_", "").lower().replace("_", "")
        # Map proto enum names back to string values like "1m", "5m", "1h", "1d"
        interval_map = {
            "1min": "1m", "5min": "5m", "1hour": "1h", "1day": "1d",
            "1m": "1m", "5m": "5m", "1h": "1h", "1d": "1d",
        }
        interval_str = interval_map.get(iv_name, "1d")

        conn = get_connection()
        conditions = ["instrument_id = ?", "interval = ?"]
        params: list = [instrument_id, interval_str]
        if request.since:
            from datetime import datetime
            conditions.append("ts >= ?")
            params.append(datetime.fromisoformat(request.since.replace("Z", "+00:00")))
        if request.until:
            from datetime import datetime
            conditions.append("ts <= ?")
            params.append(datetime.fromisoformat(request.until.replace("Z", "+00:00")))

        where = " AND ".join(conditions)
        rows = conn.execute(
            f"""
            SELECT instrument_id, interval, ts, open, high, low, close,
                   volume, vwap, trade_count, market_cap, source
            FROM ohlcv WHERE {where} ORDER BY ts ASC
            """,
            params,
        ).fetchall()

        for row in rows:
            yield pb2.OHLCVBar(
                instrument_id=row[0] or "",
                ts=row[2].isoformat() if row[2] else "",
                open=float(row[3] or 0),
                high=float(row[4] or 0),
                low=float(row[5] or 0),
                close=float(row[6] or 0),
                volume=float(row[7] or 0),
                vwap=float(row[8] or 0),
                trade_count=int(row[9] or 0),
                source=row[11] or "",
            )

    def GetFundamentals(
        self, request: pb2.GetFundamentalsRequest, context: grpc.ServicerContext
    ) -> pb2.FundamentalsResponse:
        from market_data.db.resolver import resolve_symbol
        try:
            instrument_id = resolve_symbol(request.symbol)
        except SymbolNotFoundError:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"Symbol not found: {request.symbol!r}")
            return pb2.FundamentalsResponse()
        except AmbiguousSymbolError as exc:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(str(exc))
            return pb2.FundamentalsResponse()

        conn = get_connection()
        base = conn.execute(
            "SELECT asset_class FROM instruments WHERE instrument_id = ?", [instrument_id]
        ).fetchone()
        if not base:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"Instrument not found: {instrument_id!r}")
            return pb2.FundamentalsResponse()

        asset_class = base[0]
        resp = pb2.FundamentalsResponse(instrument_id=instrument_id)

        if asset_class == "crypto":
            row = conn.execute(
                "SELECT * FROM instrument_crypto WHERE instrument_id = ?", [instrument_id]
            ).fetchone()
            if row:
                desc = conn.execute("DESCRIBE instrument_crypto").fetchall()
                cols = [d[0] for d in desc]
                d = dict(zip(cols, row))
                resp.crypto.CopyFrom(
                    pb2.CryptoFundamentals(
                        instrument_id=instrument_id,
                        blockchain_network=d.get("blockchain_network") or "",
                        consensus_mechanism=d.get("consensus_mechanism") or "",
                        decimals=int(d.get("decimals") or 0),
                        whitepaper_url=d.get("whitepaper_url") or "",
                        github_url=d.get("github_url") or "",
                    )
                )
        elif asset_class in ("equity", "etf"):
            row = conn.execute(
                "SELECT * FROM instrument_equity WHERE instrument_id = ?", [instrument_id]
            ).fetchone()
            if row:
                desc = conn.execute("DESCRIBE instrument_equity").fetchall()
                cols = [d[0] for d in desc]
                d = dict(zip(cols, row))
                resp.equity.CopyFrom(
                    pb2.EquityFundamentals(
                        instrument_id=instrument_id,
                        isin=d.get("isin") or "",
                        cusip=d.get("cusip") or "",
                        figi=d.get("figi") or "",
                        composite_figi=d.get("composite_figi") or "",
                        country_of_incorporation=d.get("country_of_incorporation") or "",
                        shares_outstanding=int(d.get("shares_outstanding") or 0),
                        float_shares=int(d.get("float_shares") or 0),
                    )
                )
        return resp
