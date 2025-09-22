"""Distributed task execution using Celery with graceful in-process fallback."""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Optional

from .config import AppSettings

try:  # pragma: no cover - executed when dependency exists
    from celery import Celery  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - fallback path
    from .stubs.celery import Celery  # type: ignore


class TaskQueue:
    """Simple wrapper that prefers Celery but can operate entirely in-process."""

    def __init__(
        self,
        settings: AppSettings,
        *,
        celery_app: Optional["Celery"] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        self._settings = settings
        self._loop = self._resolve_loop(loop)
        self._celery: Optional[Celery] = celery_app or self._initialise_celery()

    def _resolve_loop(
        self, loop: Optional[asyncio.AbstractEventLoop]
    ) -> asyncio.AbstractEventLoop:
        if loop is not None:
            return loop
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            return new_loop

    def _initialise_celery(self) -> Optional[Celery]:
        try:
            return Celery(
                "developer",
                broker=self._settings.celery_broker_url,
                backend=self._settings.celery_backend_url,
            )
        except Exception:  # pragma: no cover - celery unavailable
            return None

    def task(self, name: Optional[str] = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            if self._celery is not None:
                return self._celery.task(name=name)(func)

            async def run_async(*args: Any, **kwargs: Any) -> Any:
                result = func(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    return await result
                return result

            def delay(*args: Any, **kwargs: Any) -> asyncio.Future[Any]:
                return self._loop.create_task(run_async(*args, **kwargs))

            run_async.delay = delay  # type: ignore[attr-defined]
            return run_async

        return decorator

    async def dispatch(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        if self._celery is not None and hasattr(func, "delay"):
            result = func.delay(*args, **kwargs)
            if hasattr(result, "aget"):
                return await result.aget()
            return result

        outcome = func(*args, **kwargs)
        if asyncio.iscoroutine(outcome):
            return await outcome
        return outcome


__all__ = ["TaskQueue"]
