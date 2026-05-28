"""In-process TTL cache for market data (per worker process)."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")

# TTLs (seconds)
TTL_DAILY_BARS = 15 * 60
TTL_SNAPSHOT = 3 * 60
TTL_OPTION_IV_MAP = 3 * 60
TTL_POLYGON_REFS = 3 * 60

_store: dict[str, tuple[float, object]] = {}
_locks: dict[str, asyncio.Lock] = {}


def _lock_for(key: str) -> asyncio.Lock:
    if key not in _locks:
        _locks[key] = asyncio.Lock()
    return _locks[key]


def cache_get(key: str) -> object | None:
    entry = _store.get(key)
    if not entry:
        return None
    expires_at, value = entry
    if time.monotonic() >= expires_at:
        _store.pop(key, None)
        return None
    return value


def cache_set(key: str, value: object, ttl: float) -> None:
    _store[key] = (time.monotonic() + ttl, value)


async def cached_async(key: str, ttl: float, factory: Callable[[], Awaitable[T]]) -> T:
    hit = cache_get(key)
    if hit is not None:
        return hit  # type: ignore[return-value]

    lock = _lock_for(key)
    async with lock:
        hit = cache_get(key)
        if hit is not None:
            return hit  # type: ignore[return-value]
        value = await factory()
        cache_set(key, value, ttl)
        return value


def clear_cache() -> None:
    """Test helper."""
    _store.clear()


async def cached_yfinance_daily_bars(
    ticker: str, from_date: str, to_date: str
) -> list[dict]:
    from app.tools.providers import get_yfinance_client

    key = f"yf:bars:{ticker.upper()}:{from_date}:{to_date}"

    async def _fetch() -> list[dict]:
        return await get_yfinance_client().daily_bars(ticker, from_date, to_date)

    return await cached_async(key, TTL_DAILY_BARS, _fetch)
