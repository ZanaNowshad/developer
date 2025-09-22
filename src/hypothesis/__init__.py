"""Minimal Hypothesis compatible API for offline CI.

This is intentionally tiny and only implements the decorators and strategies used in
the automated tests. It should not be relied on outside of this repository.
"""

from __future__ import annotations

import asyncio
import inspect
from functools import wraps
from typing import Any, Callable, Dict

from . import strategies as st

__all__ = ["assume", "given", "settings", "st"]


class _UnsatisfiedAssumption(Exception):
    pass


def assume(condition: bool) -> None:
    if not condition:
        raise _UnsatisfiedAssumption()


def given(*strategies: st.Strategy, **kw_strategies: st.Strategy) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        def build_call(args: tuple[Any, ...], kwargs: Dict[str, Any]) -> tuple[list[Any], Dict[str, Any]]:
            call_kwargs: Dict[str, Any] = dict(kwargs)
            call_args = list(args)
            generated_args = [strategy.example() for strategy in strategies]
            call_args.extend(generated_args)
            for name, strategy in kw_strategies.items():
                call_kwargs[name] = strategy.example()
            return call_args, call_kwargs

        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> None:
                for _ in range(5):
                    call_args, call_kwargs = build_call(args, kwargs)
                    try:
                        result = func(*call_args, **call_kwargs)
                        if inspect.isawaitable(result):
                            await result
                    except _UnsatisfiedAssumption:
                        continue

            async_wrapper.__signature__ = inspect.Signature()  # type: ignore[attr-defined]
            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> None:
            for _ in range(5):
                call_args, call_kwargs = build_call(args, kwargs)
                try:
                    result = func(*call_args, **call_kwargs)
                    if inspect.isawaitable(result):
                        asyncio.run(result)
                except _UnsatisfiedAssumption:
                    continue

        sync_wrapper.__signature__ = inspect.Signature()  # type: ignore[attr-defined]
        return sync_wrapper

    return decorator


def settings(**_: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        return func

    return decorator


# Re-export strategies module for `from hypothesis import strategies as st`
strategies = st
