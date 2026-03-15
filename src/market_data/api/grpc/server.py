"""Async gRPC server — listens on port 50060."""
from __future__ import annotations

import logging

import grpc

from market_data.api.grpc.generated.v1 import market_data_pb2_grpc
from market_data.api.grpc.servicer import MarketDataServicer

logger = logging.getLogger(__name__)

_DEFAULT_PORT = 50060
_MAX_WORKERS = 10


async def serve_grpc(port: int = _DEFAULT_PORT) -> grpc.aio.Server:
    """Start the gRPC server and return the server object.

    The caller is responsible for calling ``await server.wait_for_termination()``
    or stopping it gracefully with ``await server.stop(grace_period)``.
    """
    server = grpc.aio.server()
    market_data_pb2_grpc.add_MarketDataServiceServicer_to_server(
        MarketDataServicer(), server
    )
    listen_addr = f"[::]:{port}"
    server.add_insecure_port(listen_addr)
    await server.start()
    logger.info("gRPC server listening on port %d", port)
    return server
