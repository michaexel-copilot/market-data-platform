"""Asyncio token-bucket rate limiter."""
from __future__ import annotations

import asyncio
import time


class RateLimiter:
    """Token-bucket rate limiter for async code.

    Args:
        rate: tokens added per second
        burst: maximum token capacity
    """

    def __init__(self, rate: float, burst: float) -> None:
        self._rate = rate
        self._burst = burst
        self._tokens = burst
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0) -> None:
        """Wait until `tokens` tokens are available, then consume them."""
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self._last_refill
                self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
                self._last_refill = now

                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return

                wait = (tokens - self._tokens) / self._rate
                await asyncio.sleep(wait)
