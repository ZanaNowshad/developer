"""Real-time utilities supporting WebSocket style broadcasts."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class Subscriber:
    queue: "asyncio.Queue[Dict[str, Any]]"


class RealTimeHub:
    def __init__(self) -> None:
        self._subscribers: List[Subscriber] = []
        self._lock = asyncio.Lock()

    async def connect(self) -> Subscriber:
        subscriber = Subscriber(queue=asyncio.Queue())
        async with self._lock:
            self._subscribers.append(subscriber)
        return subscriber

    async def disconnect(self, subscriber: Subscriber) -> None:
        async with self._lock:
            if subscriber in self._subscribers:
                self._subscribers.remove(subscriber)

    async def broadcast(self, event: str, payload: Dict[str, Any]) -> None:
        message = {"event": event, "payload": payload}
        async with self._lock:
            targets = list(self._subscribers)
        for subscriber in targets:
            await subscriber.queue.put(message)


__all__ = ["RealTimeHub", "Subscriber"]
