import asyncio

import developer.cache as cache_module
from developer.cache import InMemoryCache, create_cache
from developer.config import AppSettings


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


def test_in_memory_cache_without_ttl(monkeypatch) -> None:
    cache = InMemoryCache()
    clock = _FakeClock(initial=2_000.0)
    monkeypatch.setattr(cache_module, "time", clock)

    async def scenario() -> None:
        await cache.set("tools:list", ["shell"], ttl=None)
        clock.value += 10_000
        assert await cache.get("tools:list") == ["shell"]

    asyncio.run(scenario())


def test_in_memory_cache_zero_ttl(monkeypatch) -> None:
    cache = InMemoryCache()
    clock = _FakeClock(initial=5_000.0)
    monkeypatch.setattr(cache_module, "time", clock)

    async def scenario() -> None:
        await cache.set("tools:list", ["shell"], ttl=0)
        clock.value += 0.1
        assert await cache.get("tools:list") is None

    asyncio.run(scenario())


def test_create_cache_prefers_memory_backend() -> None:
    settings = AppSettings(redis_url="memory://")
    backend = create_cache(settings)
    assert isinstance(backend, InMemoryCache)


def test_create_cache_uses_redis_when_available(monkeypatch) -> None:
    class DummyRedis(cache_module.CacheBackend):
        def __init__(self, url: str) -> None:
            self.url = url

        async def get(self, key: str):
            return None

        async def set(self, key: str, value, ttl=None):
            return None

        async def invalidate(self, prefix: str) -> None:
            return None

    monkeypatch.setattr(cache_module, "RedisCache", DummyRedis)
    settings = AppSettings(redis_url="redis://localhost:6379/0")
    backend = create_cache(settings)
    assert isinstance(backend, DummyRedis)
    assert backend.url == "redis://localhost:6379/0"
