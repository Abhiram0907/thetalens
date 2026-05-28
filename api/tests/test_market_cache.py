import asyncio

import pytest

from app.services import market_cache as mc


@pytest.mark.asyncio
async def test_cached_async_dedupes_calls():
    mc.clear_cache()
    calls = 0

    async def factory() -> str:
        nonlocal calls
        calls += 1
        return "ok"

    a, b = await asyncio.gather(
        mc.cached_async("k1", 60.0, factory),
        mc.cached_async("k1", 60.0, factory),
    )
    assert a == b == "ok"
    assert calls == 1
