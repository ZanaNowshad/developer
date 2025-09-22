"""Tiny Celery-compatible API used for offline execution."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Optional


class _EagerResult:
    def __init__(self, coro: Awaitable[Any]) -> None:
        self._coro = coro

    def get(self, timeout: Optional[float] = None) -> Any:  # pragma: no cover - synchronous compatibility
        return asyncio.run(self._coro)

    async def aget(self) -> Any:
        return await self._coro


class Celery:
    def __init__(self, name: str, broker: Optional[str] = None, backend: Optional[str] = None) -> None:
        self.name = name
        self.broker = broker
        self.backend = backend

    def task(self, name: Optional[str] = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            async def run_async(*args: Any, **kwargs: Any) -> Any:
                result = func(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    return await result
                return result

            def delay(*args: Any, **kwargs: Any) -> _EagerResult:
                return _EagerResult(run_async(*args, **kwargs))

            run_async.delay = delay  # type: ignore[attr-defined]
            run_async.__name__ = name or func.__name__
            return run_async

        return decorator

    def send_task(self, name: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> _EagerResult:
        async def _missing() -> Any:
            raise RuntimeError(f"Task {name} is not registered in the stub Celery app")

        return _EagerResult(_missing())


__all__ = ["Celery"]
