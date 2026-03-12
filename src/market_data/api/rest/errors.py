"""FastAPI exception handlers for the REST API."""
from __future__ import annotations

import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from market_data.models.api import AmbiguousSymbolError, SymbolNotFoundError

logger = logging.getLogger(__name__)


async def symbol_not_found_handler(request: Request, exc: SymbolNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"code": "SYMBOL_NOT_FOUND", "message": str(exc)},
    )


async def ambiguous_symbol_handler(request: Request, exc: AmbiguousSymbolError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "code": "AMBIGUOUS_SYMBOL",
            "message": str(exc),
            "matches": exc.matches,
        },
    )


async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"code": "VALIDATION_ERROR", "message": exc.errors()},
    )


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"code": "INTERNAL_ERROR", "message": "An internal error occurred"},
    )
