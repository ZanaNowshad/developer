"""Caching backends with Redis support and in-memory fallback."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .config import AppSettings


class CacheBackend:
    async def get(self, key: str) -> Optional[Any]:  # pragma: no cover - interface
        raise NotImplementedError

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:  # pragma: no cover
        raise NotImplementedError

    async def invalidate(self, prefix: str) -> None:  # pragma: no cover
        raise NotImplementedError


@dataclass
class _CacheItem:
    value: Any
    expires_at: Optional[float]


class InMemoryCache(CacheBackend):
    def __init__(self) -> None:
        self._values: Dict[str, _CacheItem] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            item = self._values.get(key)
            if not item:
                return None
            if item.expires_at is not None and item.expires_at < time.time():
                del self._values[key]
                return None
            return item.value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        async with self._lock:
            expires_at = time.time() + ttl if ttl is not None else None
            self._values[key] = _CacheItem(value=value, expires_at=expires_at)

    async def invalidate(self, prefix: str) -> None:
        async with self._lock:
            for key in list(self._values):
                if key.startswith(prefix):
                    del self._values[key]


class RedisCache(CacheBackend):  # pragma: no cover - requires optional dependency
    def __init__(self, url: str) -> None:
        import redis.asyncio as redis  # type: ignore

        self._client = redis.from_url(url, encoding="utf-8", decode_responses=True)

    async def get(self, key: str) -> Optional[Any]:
        return await self._client.get(key)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        await self._client.set(key, value, ex=ttl)

    async def invalidate(self, prefix: str) -> None:
        pattern = f"{prefix}*"
        keys = [key async for key in self._client.scan_iter(match=pattern)]
        if keys:
            await self._client.delete(*keys)


def create_cache(settings: AppSettings) -> CacheBackend:
    if settings.redis_url.startswith("memory://"):
        return InMemoryCache()
    try:  # pragma: no cover - executed when dependency is available
        return RedisCache(settings.redis_url)
    except ModuleNotFoundError:
        return InMemoryCache()


__all__ = ["CacheBackend", "InMemoryCache", "RedisCache", "create_cache"]
