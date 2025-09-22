import asyncio

import developer.cache as cache_module
from developer.cache import InMemoryCache


class _FakeClock:
    def __init__(self, initial: float) -> None:
        self.value = initial

    def time(self) -> float:
        return self.value


def test_in_memory_cache_ttl(monkeypatch) -> None:
    cache = InMemoryCache()
    clock = _FakeClock(initial=1_000.0)
    monkeypatch.setattr(cache_module, "time", clock)

    async def scenario() -> None:
        await cache.set("tools:list", ["shell"], ttl=30)
        assert await cache.get("tools:list") == ["shell"]
        clock.value += 31
        assert await cache.get("tools:list") is None

    asyncio.run(scenario())


def test_in_memory_cache_invalidate_prefix(monkeypatch) -> None:
    cache = InMemoryCache()
    clock = _FakeClock(initial=1_000.0)
    monkeypatch.setattr(cache_module, "time", clock)

    async def scenario() -> None:
        await cache.set("tools:list", ["shell"], ttl=None)
        await cache.set("tools:details", ["text_editor"], ttl=None)
        await cache.set("other:key", ["workflow"], ttl=None)

        await cache.invalidate("tools:")

        assert await cache.get("tools:list") is None
        assert await cache.get("tools:details") is None
        assert await cache.get("other:key") == ["workflow"]

    asyncio.run(scenario())
