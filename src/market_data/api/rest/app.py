"""FastAPI application factory — mounts REST routers and JSON-RPC handler."""
from __future__ import annotations

from fastapi import FastAPI
from pydantic import ValidationError

from market_data.api.rest.errors import (
    ambiguous_symbol_handler,
    generic_error_handler,
    symbol_not_found_handler,
    validation_error_handler,
)
from market_data.api.rest.instruments import router as instruments_router
from market_data.api.rest.ohlcv import router as ohlcv_router
from market_data.api.jsonrpc.handler import router as jsonrpc_router
from market_data.models.api import AmbiguousSymbolError, SymbolNotFoundError


def create_app() -> FastAPI:
    app = FastAPI(
        title="Market Data Platform",
        description="Unified market data API — REST, JSON-RPC, and gRPC",
        version="0.1.0",
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    # REST routers
    app.include_router(instruments_router)
    app.include_router(ohlcv_router)

    # JSON-RPC handler at /jsonrpc
    app.include_router(jsonrpc_router, prefix="/jsonrpc")

    # Exception handlers
    app.add_exception_handler(SymbolNotFoundError, symbol_not_found_handler)  # type: ignore[arg-type]
    app.add_exception_handler(AmbiguousSymbolError, ambiguous_symbol_handler)  # type: ignore[arg-type]
    app.add_exception_handler(ValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, generic_error_handler)

    return app


# Module-level app instance used by uvicorn
app = create_app()
