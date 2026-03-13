"""API package — entry point for `uv run serve`."""
from __future__ import annotations

import asyncio
import logging
import signal

import uvicorn

logger = logging.getLogger(__name__)

import os
_REST_PORT = int(os.environ.get("HTTP_PORT", 8010))
_GRPC_PORT = int(os.environ.get("GRPC_PORT", 50051))


def serve() -> None:
    """Entry point for `uv run serve` — starts REST (HTTP_PORT, default 8010) and gRPC (GRPC_PORT, default 50051)."""
    import dotenv
    dotenv.load_dotenv()

    from market_data.db import migrate as _migrate
    _migrate()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(_serve_all())


async def _serve_all() -> None:
    from market_data.api.grpc.server import serve_grpc
    from market_data.api.rest.app import create_app

    app = create_app()
    config = uvicorn.Config(app, host="0.0.0.0", port=_REST_PORT, log_level="info")
    http_server = uvicorn.Server(config)

    grpc_server = await serve_grpc(port=_GRPC_PORT)

    loop = asyncio.get_running_loop()

    def _shutdown() -> None:
        logger.info("Shutdown signal received")
        loop.create_task(_graceful_shutdown(http_server, grpc_server))

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _shutdown)

    logger.info("Starting REST server on port %d and gRPC server on port %d", _REST_PORT, _GRPC_PORT)
    await asyncio.gather(
        http_server.serve(),
        grpc_server.wait_for_termination(),
    )


async def _graceful_shutdown(http_server: uvicorn.Server, grpc_server) -> None:  # type: ignore[type-arg]
    """Stop scheduler, flush writes, close DuckDB, then stop servers."""
    logger.info("Initiating graceful shutdown…")

    # Stop APScheduler if running
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from market_data.ingestion.scheduler import build_scheduler
    except Exception:
        pass

    # Stop gRPC with 5s grace period
    await grpc_server.stop(grace=5)

    # Stop uvicorn
    http_server.should_exit = True

    # Close DuckDB
    try:
        from market_data.db.connection import close_connection
        close_connection()
    except Exception:
        pass

    logger.info("Shutdown complete")
