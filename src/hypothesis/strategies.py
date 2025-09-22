"""Extremely small subset of Hypothesis strategies used for property-style tests."""

from __future__ import annotations

import random
import string
from typing import Any, Callable, Iterable, List, Sequence, TypeVar

T = TypeVar("T")


class Strategy:
    def __init__(self, generator: Callable[[], T]) -> None:
        self._generator = generator

    def example(self) -> T:
        return self._generator()

    def map(self, fn: Callable[[T], T]) -> "Strategy":  # pragma: no cover - convenience
        return Strategy(lambda: fn(self.example()))


def text(min_size: int = 0, max_size: int = 20, alphabet: Sequence[str] | None = None) -> Strategy[str]:
    pool = list(alphabet) if alphabet is not None else list(string.ascii_letters + string.digits + " ")

    def generate() -> str:
        length = max(min_size, min(max_size, random.randint(min_size, max(max_size, min_size + 1))))
        return "".join(random.choice(pool) for _ in range(length))

    return Strategy(generate)


def integers(min_value: int = -10, max_value: int = 10) -> Strategy[int]:
    def generate() -> int:
        return random.randint(min_value, max_value)

    return Strategy(generate)


def lists(strategy: Strategy[T], min_size: int = 0, max_size: int = 5) -> Strategy[List[T]]:
    def generate() -> List[T]:
        length = random.randint(min_size, max_size)
        return [strategy.example() for _ in range(length)]

    return Strategy(generate)


def sampled_from(items: Iterable[T]) -> Strategy[T]:
    pool = list(items)
    if not pool:
        raise ValueError("sampled_from requires at least one item")

    def generate() -> T:
        return random.choice(pool)

    return Strategy(generate)


__all__ = ["Strategy", "builds", "integers", "lists", "sampled_from", "text"]


def builds(function: Callable[..., T], *strategies: "Strategy[Any]") -> "Strategy[T]":
    def generate() -> T:
        values = [strategy.example() for strategy in strategies]
        return function(*values)

    return Strategy(generate)
